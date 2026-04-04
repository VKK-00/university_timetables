from __future__ import annotations

import re
import zipfile
from pathlib import Path
from urllib.parse import parse_qs, urlparse

import requests

from .models import DiscoveredAsset, FetchedAsset
from .utils import ensure_parent, sha256_bytes


def fetch_asset(asset: DiscoveredAsset, session: requests.Session, cache_dir: Path) -> FetchedAsset:
    if asset.asset_kind == "local_file":
        path = Path(asset.locator)
        content = path.read_bytes()
        return FetchedAsset(asset, content, _guess_content_type(path.name), sha256_bytes(content), str(path))
    if asset.asset_kind == "zip_entry":
        with zipfile.ZipFile(asset.metadata["zip_path"]) as archive:
            content = archive.read(asset.metadata["entry_name"])
        return FetchedAsset(asset, content, _guess_content_type(asset.metadata["entry_name"]), sha256_bytes(content), asset.locator)
    if asset.asset_kind in {"html_page", "html_table"}:
        content = asset.metadata["html"].encode("utf-8")
        return FetchedAsset(asset, content, "text/html", sha256_bytes(content), asset.locator)
    if _is_google(asset.locator):
        try:
            response = _fetch_remote(asset.locator, session=session)
        except Exception:
            response = None
        response = _fetch_google_resolved(asset.locator, session=session, fallback=response)
    else:
        response = _fetch_remote(asset.locator, session=session)
    content = response.content
    content_type = response.headers.get("Content-Type", _guess_content_type(asset.locator))
    fetched = FetchedAsset(asset, content, content_type, sha256_bytes(content), response.url)
    suffix = _guess_suffix(content_type, asset.locator)
    cache_path = cache_dir / f"{fetched.content_hash[:16]}{suffix}"
    ensure_parent(cache_path)
    if not cache_path.exists():
        cache_path.write_bytes(content)
    return fetched


def _fetch_remote(url: str, session: requests.Session) -> requests.Response:
    response = session.get(url, timeout=30, headers={"User-Agent": "Mozilla/5.0"})
    response.raise_for_status()
    return response


def _fetch_google_resolved(url: str, session: requests.Session, fallback: requests.Response | None = None) -> requests.Response:
    parsed = urlparse(url)
    doc_id = _extract_google_id(url)
    gid = parse_qs(parsed.query).get("gid", ["0"])[0]
    candidates: list[str] = []
    if doc_id and "spreadsheets" in parsed.path:
        candidates.extend(
            [
                f"https://docs.google.com/spreadsheets/d/{doc_id}/export?format=xlsx",
                f"https://docs.google.com/spreadsheets/d/{doc_id}/export?format=csv&gid={gid}",
                f"https://docs.google.com/spreadsheets/d/{doc_id}/gviz/tq?tqx=out:html&gid={gid}",
                f"https://docs.google.com/spreadsheets/d/{doc_id}/htmlview?gid={gid}",
            ]
        )
    if doc_id and "file/d/" in parsed.path:
        candidates.append(f"https://drive.google.com/uc?export=download&id={doc_id}")
    if fallback is not None and "text/html" in fallback.headers.get("Content-Type", ""):
        for found in re.findall(r'https://[^"\\\']+(?:download|export)[^"\\\']+', fallback.text):
            candidates.append(found.encode("utf-8").decode("unicode_escape"))
    for candidate in candidates:
        try:
            response = _fetch_remote(candidate, session=session)
            if response.ok:
                return response
        except Exception:
            continue
    return fallback or _fetch_remote(url, session=session)


def _extract_google_id(url: str) -> str | None:
    match = re.search(r"/d/([A-Za-z0-9_-]+)", url)
    if match:
        return match.group(1)
    match = re.search(r"[?&]id=([A-Za-z0-9_-]+)", url)
    if match:
        return match.group(1)
    return None


def _is_google(url: str) -> bool:
    return "google.com" in urlparse(url).netloc


def _guess_content_type(name: str) -> str:
    suffix = Path(urlparse(name).path if "://" in name else name).suffix.lower()
    return {
        ".xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        ".xlsm": "application/vnd.ms-excel.sheet.macroEnabled.12",
        ".xls": "application/vnd.ms-excel",
        ".csv": "text/csv",
        ".pdf": "application/pdf",
        ".html": "text/html",
        ".htm": "text/html",
    }.get(suffix, "application/octet-stream")


def _guess_suffix(content_type: str, locator: str) -> str:
    content_type = content_type.lower()
    if "spreadsheetml" in content_type:
        return ".xlsx"
    if "ms-excel" in content_type:
        return ".xls"
    if "csv" in content_type:
        return ".csv"
    if "pdf" in content_type:
        return ".pdf"
    if "html" in content_type:
        return ".html"
    return Path(urlparse(locator).path).suffix or ".bin"
