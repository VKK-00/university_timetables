from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from timetable_scraper.adapters.html import parse_html_asset
from timetable_scraper.discovery import discover_source
from timetable_scraper.models import DiscoveredAsset, FetchedAsset, SourceConfig

WEB_DIR = Path(__file__).parent / "fixtures" / "web"


@dataclass
class FakeResponse:
    text: str
    url: str
    status_code: int = 200
    headers: dict[str, str] | None = None

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            raise RuntimeError(f"status {self.status_code}")


class FakeSession:
    def __init__(self, mapping: dict[str, str]) -> None:
        self.mapping = mapping

    def get(self, url: str, timeout: int = 30, headers: dict[str, str] | None = None) -> FakeResponse:
        return FakeResponse(text=self.mapping[url], url=url, headers={"Content-Type": "text/html"})


def test_discovery_finds_tables_and_links() -> None:
    url = "https://example.edu/faculty/schedule"
    html = (WEB_DIR / "faculty_links.html").read_text(encoding="utf-8")
    session = FakeSession({url: html})
    source = SourceConfig(
        kind="web_page",
        name="faculty-web",
        url=url,
        allow_domains=["example.edu"],
        schedule_keywords=["розклад", "schedule"],
    )
    result = discover_source(source, session=session)
    kinds = [asset.asset_kind for asset in result.assets]
    assert "html_page" in kinds
    assert "file_url" in kinds
    assert "google_sheet" in kinds


def test_discovery_follows_nested_pages_when_depth_is_enabled() -> None:
    root_url = "https://example.edu/faculty"
    nested_url = "https://example.edu/faculty/schedule-page"
    root_html = """
    <html><body>
      <a href="/faculty/schedule-page">Розклад занять</a>
    </body></html>
    """
    nested_html = (WEB_DIR / "faculty_table.html").read_text(encoding="utf-8")
    session = FakeSession({root_url: root_html, nested_url: nested_html})
    source = SourceConfig(
        kind="web_page",
        name="faculty-web-recursive",
        url=root_url,
        allow_domains=["example.edu"],
        schedule_keywords=["розклад", "занять"],
        follow_links_depth=1,
    )
    result = discover_source(source, session=session)
    assert any(asset.locator == nested_url for asset in result.assets)
    assert any(asset.asset_kind == "html_table" and asset.metadata.get("page_url") == nested_url for asset in result.assets)


def test_html_table_adapter_parses_rows() -> None:
    html = (WEB_DIR / "faculty_table.html").read_text(encoding="utf-8")
    asset = DiscoveredAsset(
        source_name="fixture",
        source_kind="web_page",
        source_url_or_path="https://example.edu",
        asset_kind="html_page",
        locator="https://example.edu/faculty",
        display_name="faculty",
    )
    fetched = FetchedAsset(asset=asset, content=html.encode("utf-8"), content_type="text/html", content_hash="html", resolved_locator=asset.locator)
    document = parse_html_asset(fetched)
    row = document.sheets[0].records[0]
    assert row.values["subject"] == "Алгоритми"
    assert row.values["day"] == "Понеділок"
