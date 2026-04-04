from __future__ import annotations

import zipfile
from pathlib import Path
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

from .models import DiscoveredAsset, DiscoveryIssue, DiscoveryResult, SourceConfig
from .utils import flatten_multiline, sha256_bytes


SUPPORTED_FILE_SUFFIXES = {".xlsx", ".xlsm", ".xls", ".csv", ".pdf", ".html", ".htm"}
LINK_RELEVANT_SUFFIXES = SUPPORTED_FILE_SUFFIXES | {".php", ".aspx", ""}


def discover_sources(sources: list[SourceConfig], session: requests.Session | None = None) -> DiscoveryResult:
    assets: list[DiscoveredAsset] = []
    issues: list[DiscoveryIssue] = []
    seen: set[str] = set()
    session = session or requests.Session()
    for source in sources:
        result = discover_source(source, session=session)
        for asset in result.assets:
            if asset.locator in seen:
                continue
            seen.add(asset.locator)
            assets.append(asset)
        issues.extend(result.issues)
    return DiscoveryResult(assets=assets, issues=issues)


def discover_source(source: SourceConfig, session: requests.Session | None = None) -> DiscoveryResult:
    session = session or requests.Session()
    if source.kind == "folder":
        return _discover_folder(source)
    if source.kind == "zip":
        return _discover_zip(source)
    if source.kind in {"file_url", "google_sheet"}:
        return DiscoveryResult(
            assets=[
                DiscoveredAsset(
                    source_name=source.name,
                    source_kind=source.kind,
                    source_url_or_path=source.url or "",
                    asset_kind=source.kind,
                    locator=source.url or "",
                    display_name=source.url or source.name,
                )
            ],
            issues=[],
        )
    if source.kind == "web_page":
        return _discover_web_page(
            source,
            session=session,
            url=source.url,
            current_depth=0,
            max_depth=source.follow_links_depth,
            visited=set(),
        )
    return DiscoveryResult(
        assets=[],
        issues=[DiscoveryIssue(source_name=source.name, reason=f"Unsupported source kind: {source.kind}")],
    )


def _discover_folder(source: SourceConfig) -> DiscoveryResult:
    assert source.path is not None
    pattern = "**/*" if source.recurse else "*"
    assets = [
        DiscoveredAsset(
            source_name=source.name,
            source_kind=source.kind,
            source_url_or_path=str(source.path),
            asset_kind="local_file",
            locator=str(path.resolve()),
            display_name=path.name,
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
                        source_url_or_path=str(source.path),
                        asset_kind="zip_entry",
                        locator=f"{source.path.resolve()}::{entry_name}",
                        display_name=Path(entry_name).name,
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
    current_depth: int,
    max_depth: int,
    visited: set[str],
) -> DiscoveryResult:
    assert url is not None
    issues: list[DiscoveryIssue] = []
    normalized_url = url.rstrip("/")
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
    html = response.text
    soup = BeautifulSoup(html, "lxml")
    page_title = flatten_multiline(soup.title.get_text(" ", strip=True) if soup.title else source.name)
    page_assets = [
        DiscoveredAsset(
            source_name=source.name,
            source_kind=source.kind,
            source_url_or_path=url,
            asset_kind="html_page",
            locator=url,
            display_name=page_title or url,
            metadata={"html": html, "table_count": len(soup.find_all("table"))},
        )
    ]
    for index, table in enumerate(soup.find_all("table"), start=1):
        table_html = str(table)
        page_assets.append(
            DiscoveredAsset(
                source_name=source.name,
                source_kind=source.kind,
                source_url_or_path=url,
                asset_kind="html_table",
                locator=f"{url}#table-{index}-{sha256_bytes(table_html.encode('utf-8'))[:10]}",
                display_name=f"{page_title} [table {index}]",
                metadata={"html": table_html, "page_url": url, "page_title": page_title},
            )
        )
    allowed_domains = set(source.allow_domains)
    base_host = urlparse(url).netloc
    if base_host:
        allowed_domains.add(base_host)
    for tag in soup.find_all(["a", "iframe", "embed"]):
        href = tag.get("href") or tag.get("src")
        if not href:
            continue
        resolved = urljoin(url, href)
        parsed = urlparse(resolved)
        suffix = Path(parsed.path).suffix.lower()
        if suffix not in LINK_RELEVANT_SUFFIXES and "google.com" not in parsed.netloc and "drive.google.com" not in parsed.netloc:
            continue
        if allowed_domains and parsed.netloc and parsed.netloc not in allowed_domains and not parsed.netloc.endswith("google.com"):
            issues.append(DiscoveryIssue(source_name=source.name, reason="Rejected by domain filter", locator=resolved))
            continue
        asset_kind = "file_url"
        if "docs.google.com" in parsed.netloc or "drive.google.com" in parsed.netloc:
            asset_kind = "google_sheet"
        elif suffix in {".html", ".htm", ".php", ".aspx", ""}:
            asset_kind = "web_link"
        label = flatten_multiline(tag.get_text(" ", strip=True)) or tag.get("title") or resolved
        page_assets.append(
            DiscoveredAsset(
                source_name=source.name,
                source_kind=source.kind,
                source_url_or_path=url,
                asset_kind=asset_kind,
                locator=resolved,
                display_name=label,
                metadata={"score": _score_page(f"{label} {resolved}", source.schedule_keywords)},
            )
        )
        if asset_kind == "web_link" and current_depth < max_depth and _score_page(f"{label} {resolved}", source.schedule_keywords) > 0:
            nested = _discover_web_page(
                source,
                session=session,
                url=resolved,
                current_depth=current_depth + 1,
                max_depth=max_depth,
                visited=visited,
            )
            page_assets.extend(nested.assets)
            issues.extend(nested.issues)
    page_assets.sort(key=lambda asset: (-int(asset.metadata.get("score", 0)), asset.locator))
    return DiscoveryResult(assets=page_assets, issues=issues)


def _score_page(text: str, keywords: list[str]) -> int:
    lowered = text.casefold()
    return sum(1 for keyword in keywords if keyword.casefold() in lowered)
