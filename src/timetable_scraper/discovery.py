from __future__ import annotations

import re
import zipfile
from pathlib import Path
from urllib.parse import unquote, urldefrag, urljoin, urlparse

import requests
from bs4 import BeautifulSoup

from .models import DiscoveredAsset, DiscoveryIssue, DiscoveryResult, SourceConfig
from .utils import flatten_multiline, sha256_bytes


SUPPORTED_FILE_SUFFIXES = {".xlsx", ".xlsm", ".xls", ".csv", ".pdf", ".html", ".htm"}
LINK_RELEVANT_SUFFIXES = SUPPORTED_FILE_SUFFIXES | {".php", ".aspx", ""}
GOOGLE_FOLDER_RE = re.compile(r"/drive/folders/([A-Za-z0-9_-]+)")
GOOGLE_EMBEDDED_URL_RE = re.compile(r"https:[^<\s]*?(?=(?:\\x22|\"|'|<|\s))")
ABSOLUTE_URL_RE = re.compile(r"https?://[^\"'\\s<>]+", re.IGNORECASE)
RELATIVE_FILE_RE = re.compile(r"(?P<url>/[^\"'\\s<>]+(?:\.xlsx|\.xlsm|\.xls|\.csv|\.pdf)(?:\?[^\"'\\s<>]*)?)", re.IGNORECASE)
NEGATIVE_CANDIDATE_PATTERNS = (
    re.compile(r"(?iu)\bінформаційн(?:ий|ого)\s+проспект\b"),
    re.compile(r"(?iu)\bпостер\b"),
    re.compile(r"(?iu)\bзвіт(?:\s+декана)?\b"),
    re.compile(r"(?iu)\beras(?:mus)?\b"),
    re.compile(r"(?iu)\bdigiuni\b|\btransleader\b|\bdcomfra\b"),
    re.compile(r"(?iu)\bгуртожит"),
    re.compile(r"(?iu)\bстудентськ(?:е|ого)\s+самоврядування\b"),
    re.compile(r"(?iu)\bвступн"),
    re.compile(r"(?iu)\bконтакти\b"),
    re.compile(r"(?iu)\bрейтингов"),
    re.compile(r"(?iu)\bрекомендован"),
    re.compile(r"(?iu)\bрезультат"),
    re.compile(r"(?iu)\bсписки?\b"),
    re.compile(r"(?iu)\bнаука\b"),
    re.compile(r"(?iu)\bу\s+20\d{2}\s+році\b"),
    re.compile(r"(?iu)\b[ув][\s_-]*20\d{2}[\s_-]*роц[ії]\b"),
    re.compile(r"(?iu)\bрозподіл\s+навантаження\b"),
    re.compile(r"(?iu)\bтаблиц(?:я|і)\s+\d+\b"),
)


def discover_sources(sources: list[SourceConfig], session: requests.Session | None = None) -> DiscoveryResult:
    assets: list[DiscoveredAsset] = []
    issues: list[DiscoveryIssue] = []
    seen: set[tuple[str, str]] = set()
    session = session or requests.Session()
    for source in sources:
        result = discover_source(source, session=session)
        for asset in result.assets:
            key = (asset.source_name, asset.locator)
            if key in seen:
                continue
            seen.add(key)
            assets.append(asset)
        issues.extend(result.issues)
    return DiscoveryResult(assets=assets, issues=issues)


def discover_source(source: SourceConfig, session: requests.Session | None = None) -> DiscoveryResult:
    session = session or requests.Session()
    if source.kind == "folder":
        return _append_manual_assets(_discover_folder(source), source)
    if source.kind == "zip":
        return _append_manual_assets(_discover_zip(source), source)
    if source.kind in {"file_url", "google_sheet"}:
        root = source.url or ""
        result = DiscoveryResult(
            assets=[
                DiscoveredAsset(
                    source_name=source.name,
                    source_kind=source.kind,
                    asset_kind=source.kind,
                    locator=root,
                    display_name=root or source.name,
                    source_root_url=root,
                    source_url_or_path=root,
                    origin_kind="direct_file",
                )
            ],
            issues=[],
        )
        return _append_manual_assets(result, source)
    if source.kind == "web_page":
        result = _discover_web_page(
            source,
            session=session,
            url=source.url,
            root_url=source.url,
            current_depth=0,
            max_depth=source.follow_links_depth,
            visited=set(),
        )
        return _append_manual_assets(result, source)
    result = DiscoveryResult(
        assets=[],
        issues=[DiscoveryIssue(source_name=source.name, reason=f"Unsupported source kind: {source.kind}")],
    )
    return _append_manual_assets(result, source)


def _discover_folder(source: SourceConfig) -> DiscoveryResult:
    assert source.path is not None
    pattern = "**/*" if source.recurse else "*"
    assets = [
        DiscoveredAsset(
            source_name=source.name,
            source_kind=source.kind,
            asset_kind="local_file",
            locator=str(path.resolve()),
            display_name=path.name,
            source_root_url=str(source.path.resolve()),
            source_url_or_path=str(source.path.resolve()),
            origin_kind="direct_file",
        )
        for path in sorted(source.path.glob(pattern))
        if path.is_file() and path.suffix.lower() in SUPPORTED_FILE_SUFFIXES
    ]
    return DiscoveryResult(assets=assets, issues=[])


def _discover_zip(source: SourceConfig) -> DiscoveryResult:
    assert source.path is not None
    assets: list[DiscoveredAsset] = []
    issues: list[DiscoveryIssue] = []
    try:
        with zipfile.ZipFile(source.path) as archive:
            for entry_name in archive.namelist():
                if Path(entry_name).suffix.lower() not in SUPPORTED_FILE_SUFFIXES:
                    continue
                assets.append(
                    DiscoveredAsset(
                        source_name=source.name,
                        source_kind=source.kind,
                        asset_kind="zip_entry",
                        locator=f"{source.path.resolve()}::{entry_name}",
                        display_name=Path(entry_name).name,
                        source_root_url=str(source.path.resolve()),
                        source_url_or_path=str(source.path.resolve()),
                        origin_kind="direct_file",
                        metadata={"zip_path": str(source.path.resolve()), "entry_name": entry_name},
                    )
                )
    except Exception as exc:
        issues.append(DiscoveryIssue(source_name=source.name, reason=str(exc), locator=str(source.path)))
    return DiscoveryResult(assets=assets, issues=issues)


def _discover_web_page(
    source: SourceConfig,
    session: requests.Session,
    *,
    url: str | None,
    root_url: str | None,
    current_depth: int,
    max_depth: int,
    visited: set[str],
) -> DiscoveryResult:
    assert url is not None
    issues: list[DiscoveryIssue] = []
    normalized_url = urldefrag(url.rstrip("/"))[0]
    if normalized_url in visited:
        return DiscoveryResult(assets=[], issues=[])
    visited.add(normalized_url)

    try:
        response = session.get(url, timeout=30, headers={"User-Agent": "Mozilla/5.0"})
        response.raise_for_status()
    except Exception as exc:
        return DiscoveryResult(
            assets=[],
            issues=[DiscoveryIssue(source_name=source.name, reason=str(exc), locator=url)],
        )

    root_url = root_url or url
    html = response.text
    soup = BeautifulSoup(html, "lxml")
    page_title = flatten_multiline(soup.title.get_text(" ", strip=True) if soup.title else source.name)
    page_assets: list[DiscoveredAsset] = [
        DiscoveredAsset(
            source_name=source.name,
            source_kind=source.kind,
            asset_kind="html_page",
            locator=url,
            display_name=page_title or url,
            source_root_url=root_url,
            source_url_or_path=root_url,
            origin_kind="official_page",
            metadata={"html": html, "table_count": len(soup.find_all("table")), "discovered_from": url},
        )
    ]

    for index, table in enumerate(soup.find_all("table"), start=1):
        table_html = str(table)
        page_assets.append(
            DiscoveredAsset(
                source_name=source.name,
                source_kind=source.kind,
                asset_kind="html_table",
                locator=f"{url}#table-{index}-{sha256_bytes(table_html.encode('utf-8'))[:10]}",
                display_name=f"{page_title} [table {index}]",
                source_root_url=root_url,
                source_url_or_path=root_url,
                origin_kind="official_page",
                metadata={"html": table_html, "page_url": url, "page_title": page_title, "discovered_from": url},
            )
        )

    dropfiles_assets, dropfiles_issues = _discover_dropfiles_assets(
        source,
        session=session,
        root_url=root_url,
        page_url=url,
        soup=soup,
    )
    page_assets.extend(dropfiles_assets)
    issues.extend(dropfiles_issues)

    allowed_domains = _build_allowed_domains(source, url)
    for resolved, label in _extract_link_candidates(soup, html, page_url=url):
        parsed = urlparse(resolved)
        suffix = Path(parsed.path).suffix.lower()
        if suffix not in LINK_RELEVANT_SUFFIXES and not _is_storage_url(parsed.netloc):
            continue
        if not _is_allowed_domain(parsed.netloc, allowed_domains):
            issues.append(DiscoveryIssue(source_name=source.name, reason="Rejected by domain filter", locator=resolved))
            continue
        if _is_google_drive_folder(resolved):
            folder_assets, folder_issues = _discover_google_drive_folder(
                source,
                session=session,
                folder_url=resolved,
                root_url=root_url,
            )
            page_assets.extend(folder_assets)
            issues.extend(folder_issues)
            continue
        asset_kind, origin_kind = _classify_candidate(resolved, suffix=suffix)
        score = _score_page(f"{label} {resolved}", source.schedule_keywords)
        if _should_skip_candidate(label=label, resolved=resolved, asset_kind=asset_kind, score=score):
            continue
        if asset_kind == "web_link" and score <= 0:
            continue
        page_assets.append(
            DiscoveredAsset(
                source_name=source.name,
                source_kind=source.kind,
                asset_kind=asset_kind,
                locator=resolved,
                display_name=label or resolved,
                source_root_url=root_url,
                source_url_or_path=root_url,
                origin_kind=origin_kind,
                metadata={"score": score, "discovered_from": url},
            )
        )
        if asset_kind == "web_link" and current_depth < max_depth and score > 0:
            nested = _discover_web_page(
                source,
                session=session,
                url=resolved,
                root_url=root_url,
                current_depth=current_depth + 1,
                max_depth=max_depth,
                visited=visited,
            )
            page_assets.extend(nested.assets)
            issues.extend(nested.issues)

    page_assets = _dedupe_assets(page_assets)
    page_assets.sort(key=lambda asset: (-int(asset.metadata.get("score", 0)), asset.locator))
    return DiscoveryResult(assets=page_assets, issues=issues)


def _discover_google_drive_folder(
    source: SourceConfig,
    session: requests.Session,
    *,
    folder_url: str,
    root_url: str,
) -> tuple[list[DiscoveredAsset], list[DiscoveryIssue]]:
    try:
        response = session.get(folder_url, timeout=30, headers={"User-Agent": "Mozilla/5.0"})
        response.raise_for_status()
    except Exception as exc:
        return [], [DiscoveryIssue(source_name=source.name, reason=str(exc), locator=folder_url)]
    assets: list[DiscoveredAsset] = []
    seen: set[str] = set()
    for match in GOOGLE_EMBEDDED_URL_RE.findall(response.text):
        resolved = _decode_embedded_url(match)
        if "{" in resolved or "}" in resolved or "/encrypted/" in resolved:
            continue
        parsed = urlparse(resolved)
        if parsed.netloc not in {"docs.google.com", "drive.google.com"}:
            continue
        if not any(token in parsed.path for token in ("/spreadsheets/d/", "/file/d/", "/document/d/", "/presentation/d/")):
            continue
        if resolved in seen:
            continue
        seen.add(resolved)
        asset_kind = "google_sheet" if "/spreadsheets/d/" in parsed.path else "file_url"
        assets.append(
            DiscoveredAsset(
                source_name=source.name,
                source_kind=source.kind,
                asset_kind=asset_kind,
                locator=resolved,
                display_name=resolved,
                source_root_url=root_url,
                source_url_or_path=root_url,
                origin_kind="public_folder",
                metadata={
                    "score": _score_page(resolved, source.schedule_keywords),
                    "via_drive_folder": folder_url,
                    "discovered_from": folder_url,
                },
            )
        )
    if assets:
        return assets, []
    return [], [DiscoveryIssue(source_name=source.name, reason="No files found in public Google Drive folder", locator=folder_url)]


def _discover_dropfiles_assets(
    source: SourceConfig,
    session: requests.Session,
    *,
    root_url: str,
    page_url: str,
    soup: BeautifulSoup,
) -> tuple[list[DiscoveredAsset], list[DiscoveryIssue]]:
    assets: list[DiscoveredAsset] = []
    issues: list[DiscoveryIssue] = []
    seen_categories: set[str] = set()
    base_url = f"{urlparse(page_url).scheme}://{urlparse(page_url).netloc}"
    for container in soup.select(".dropfiles-content[data-category]"):
        top_category = flatten_multiline(container.get("data-category"))
        if not top_category:
            continue
        category_links = container.select(".dropfilescategory.catlink[data-idcat]")
        for link in category_links:
            category_id = str(link.get("data-idcat") or "").strip()
            if not category_id or category_id in seen_categories:
                continue
            seen_categories.add(category_id)
            category_assets, category_issues = _discover_dropfiles_category(
                source,
                session=session,
                base_url=base_url,
                root_url=root_url,
                page_url=page_url,
                top_category=top_category,
                category_id=category_id,
                category_label=flatten_multiline(link.get_text(" ", strip=True)) or flatten_multiline(link.get("title")) or category_id,
                visited=set(),
            )
            assets.extend(category_assets)
            issues.extend(category_issues)
    return _dedupe_assets(assets), issues


def _discover_dropfiles_category(
    source: SourceConfig,
    session: requests.Session,
    *,
    base_url: str,
    root_url: str,
    page_url: str,
    top_category: str,
    category_id: str,
    category_label: str,
    visited: set[str],
) -> tuple[list[DiscoveredAsset], list[DiscoveryIssue]]:
    if category_id in visited:
        return [], []
    visited.add(category_id)
    assets: list[DiscoveredAsset] = []
    issues: list[DiscoveryIssue] = []

    files_url = f"{base_url}/index.php?option=com_dropfiles&view=frontfiles&format=json&id={category_id}"
    try:
        files_response = session.get(files_url, timeout=30, headers={"User-Agent": "Mozilla/5.0"})
        files_response.raise_for_status()
        files_payload = files_response.json()
    except Exception as exc:
        return [], [DiscoveryIssue(source_name=source.name, reason=f"Dropfiles files load failed: {exc}", locator=files_url)]

    for file_item in files_payload.get("files", []):
        resolved = flatten_multiline(
            file_item.get("link")
            or file_item.get("link_download_popup")
            or file_item.get("openpdflink")
            or file_item.get("remoteurl")
        )
        if not resolved:
            continue
        parsed = urlparse(resolved)
        suffix = Path(parsed.path).suffix.lower()
        asset_kind, origin_kind = _classify_candidate(resolved, suffix=suffix)
        assets.append(
            DiscoveredAsset(
                source_name=source.name,
                source_kind=source.kind,
                asset_kind=asset_kind,
                locator=resolved,
                display_name=flatten_multiline(file_item.get("title")) or resolved,
                source_root_url=root_url,
                source_url_or_path=root_url,
                origin_kind=origin_kind,
                metadata={
                    "score": _score_page(f"{category_label} {file_item.get('title', '')}", source.schedule_keywords),
                    "dropfiles_category": category_id,
                    "dropfiles_category_label": category_label,
                    "discovered_from": page_url,
                },
            )
        )

    categories_url = f"{base_url}/index.php?option=com_dropfiles&view=frontcategories&format=json&id={category_id}&top={top_category}"
    try:
        categories_response = session.get(categories_url, timeout=30, headers={"User-Agent": "Mozilla/5.0"})
        categories_response.raise_for_status()
        categories_payload = categories_response.json()
    except Exception as exc:
        issues.append(DiscoveryIssue(source_name=source.name, reason=f"Dropfiles categories load failed: {exc}", locator=categories_url))
        return assets, issues

    for category in categories_payload.get("categories", []):
        child_id = str(category.get("id") or "").strip()
        if not child_id:
            continue
        child_assets, child_issues = _discover_dropfiles_category(
            source,
            session=session,
            base_url=base_url,
            root_url=root_url,
            page_url=page_url,
            top_category=top_category,
            category_id=child_id,
            category_label=flatten_multiline(category.get("title")) or child_id,
            visited=visited,
        )
        assets.extend(child_assets)
        issues.extend(child_issues)
    return assets, issues


def _extract_link_candidates(soup: BeautifulSoup, html: str, *, page_url: str) -> list[tuple[str, str]]:
    candidates: list[tuple[str, str]] = []
    for tag in soup.find_all(["a", "iframe", "embed", "source"]):
        href = flatten_multiline(tag.get("href") or tag.get("src") or tag.get("data-src") or tag.get("data-href"))
        if not href:
            continue
        resolved = _normalize_candidate_url(urljoin(page_url, href))
        if resolved:
            label = flatten_multiline(tag.get_text(" ", strip=True)) or flatten_multiline(tag.get("title")) or resolved
            candidates.append((resolved, label))

    for match in ABSOLUTE_URL_RE.findall(html):
        resolved = _normalize_candidate_url(_decode_embedded_url(match))
        if not resolved or not _looks_like_asset_candidate(resolved):
            continue
        candidates.append((resolved, resolved))

    for match in RELATIVE_FILE_RE.finditer(html):
        resolved = _normalize_candidate_url(urljoin(page_url, _decode_embedded_url(match.group("url"))))
        if resolved:
            candidates.append((resolved, resolved))
    return candidates


def _normalize_candidate_url(url: str) -> str:
    resolved = urldefrag(url.strip())[0]
    if not resolved:
        return ""
    return resolved.replace("&amp;", "&")


def _looks_like_asset_candidate(url: str) -> bool:
    parsed = urlparse(url)
    host = parsed.netloc.casefold().removeprefix("www.")
    if host and "." not in host and host != "localhost":
        return False
    suffix = Path(parsed.path).suffix.lower()
    return suffix in LINK_RELEVANT_SUFFIXES or _is_storage_url(parsed.netloc)


def _build_allowed_domains(source: SourceConfig, url: str) -> set[str]:
    allowed_domains = {domain.casefold().removeprefix("www.") for domain in source.allow_domains}
    base_host = urlparse(url).netloc.casefold().removeprefix("www.")
    if base_host:
        allowed_domains.add(base_host)
    return allowed_domains


def _is_allowed_domain(netloc: str, allowed_domains: set[str]) -> bool:
    host = netloc.casefold().removeprefix("www.")
    if _is_storage_url(netloc):
        return True
    if not allowed_domains:
        return True
    return any(host == domain or host.endswith(f".{domain}") for domain in allowed_domains)


def _is_storage_url(netloc: str) -> bool:
    host = netloc.casefold().removeprefix("www.")
    return host in {"docs.google.com", "drive.google.com", "1drv.ms", "onedrive.live.com"}


def _classify_candidate(url: str, *, suffix: str) -> tuple[str, str]:
    host = urlparse(url).netloc.casefold().removeprefix("www.")
    if host in {"docs.google.com", "drive.google.com"}:
        if "/spreadsheets/" in urlparse(url).path:
            return "google_sheet", "resolved_storage"
        return "file_url", "resolved_storage"
    if host in {"1drv.ms", "onedrive.live.com"}:
        return "file_url", "resolved_storage"
    if suffix in {".html", ".htm", ".php", ".aspx", ""}:
        return "web_link", "official_page"
    return "file_url", "direct_file"


def _dedupe_assets(assets: list[DiscoveredAsset]) -> list[DiscoveredAsset]:
    deduped: list[DiscoveredAsset] = []
    seen: set[tuple[str, str, str]] = set()
    for asset in assets:
        key = (asset.source_name, asset.asset_kind, asset.locator)
        if key in seen:
            continue
        seen.add(key)
        deduped.append(asset)
    return deduped


def _is_google_drive_folder(url: str) -> bool:
    parsed = urlparse(url)
    return parsed.netloc == "drive.google.com" and bool(GOOGLE_FOLDER_RE.search(parsed.path))


def _decode_embedded_url(value: str) -> str:
    return (
        value.replace("\\u003d", "=")
        .replace("\\u0026", "&")
        .replace("\\u002F", "/")
        .replace("\\=", "=")
        .replace("\\&", "&")
        .replace("\\/", "/")
    )


def _score_page(text: str, keywords: list[str]) -> int:
    lowered = text.casefold()
    return sum(1 for keyword in keywords if keyword.casefold() in lowered)


def _should_skip_candidate(*, label: str, resolved: str, asset_kind: str, score: int) -> bool:
    if asset_kind not in {"file_url", "web_link"}:
        return False
    text = _decode_candidate_filter_text(label=label, resolved=resolved)
    if any(pattern.search(text) for pattern in NEGATIVE_CANDIDATE_PATTERNS) and score <= 1:
        return True
    return False


def _decode_candidate_filter_text(*, label: str, resolved: str) -> str:
    decoded_label = unquote(label)
    decoded_resolved = unquote(resolved)
    return f"{decoded_label} {decoded_resolved}"


def _append_manual_assets(result: DiscoveryResult, source: SourceConfig) -> DiscoveryResult:
    if not source.manual_assets:
        return result
    assets = [*result.assets, *_build_manual_assets(source)]
    return DiscoveryResult(assets=_dedupe_assets(assets), issues=result.issues)


def _build_manual_assets(source: SourceConfig) -> list[DiscoveredAsset]:
    root = source.url or (str(source.path.resolve()) if source.path is not None else "")
    assets: list[DiscoveredAsset] = []
    for seed in source.manual_assets:
        parsed = urlparse(seed.url)
        suffix = Path(parsed.path).suffix.lower()
        inferred_kind = "google_sheet" if parsed.netloc.casefold().removeprefix("www.") in {"docs.google.com", "drive.google.com"} and "/spreadsheets/" in parsed.path else "file_url"
        asset_kind = seed.asset_kind or inferred_kind
        assets.append(
            DiscoveredAsset(
                source_name=source.name,
                source_kind=source.kind,
                asset_kind=asset_kind,
                locator=seed.url,
                display_name=seed.display_name or seed.url,
                source_root_url=root,
                source_url_or_path=root,
                origin_kind="manual_seed",
                metadata={
                    "manual_seed": True,
                    "score": _score_page(f"{seed.display_name} {seed.url}", source.schedule_keywords),
                    "discovered_from": root,
                    "suffix": suffix,
                },
            )
        )
    return assets
