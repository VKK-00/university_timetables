from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from timetable_scraper.adapters.html import parse_html_asset
from timetable_scraper.discovery import discover_source
from timetable_scraper.models import DiscoveredAsset, FetchedAsset, ManualAssetSeed, SourceConfig

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


def test_discovery_expands_public_google_drive_folders() -> None:
    root_url = "https://example.edu/faculty/history"
    folder_url = "https://drive.google.com/drive/folders/folder123?usp=sharing"
    root_html = f"""
    <html><body>
      <a href="{folder_url}">Розклад бакалаврів</a>
    </body></html>
    """
    folder_html = r"""
    <html><body><script>
    window['_DRIVE_ivd'] = '\x5b\x22https:\/\/docs.google.com\/spreadsheets\/d\/sheet123\/edit?usp\u003ddrivesdk\u0026rtpof\u003dtrue\u0026sd\u003dtrue\x22,\x22https:\/\/drive.google.com\/file\/d\/file456\/view?usp\u003dsharing\x22';
    </script></body></html>
    """
    session = FakeSession({root_url: root_html, folder_url: folder_html})
    source = SourceConfig(
        kind="web_page",
        name="history-web",
        url=root_url,
        allow_domains=["example.edu", "drive.google.com", "docs.google.com"],
        schedule_keywords=["розклад", "schedule"],
    )
    result = discover_source(source, session=session)
    locators = {asset.locator for asset in result.assets}
    assert "https://docs.google.com/spreadsheets/d/sheet123/edit?usp=drivesdk&rtpof=true&sd=true" in locators
    assert "https://drive.google.com/file/d/file456/view?usp=sharing" in locators
    assert any(asset.metadata.get("via_drive_folder") == folder_url for asset in result.assets)
    assert all(asset.source_root_url == root_url for asset in result.assets if asset.locator != root_url)
    assert any(asset.origin_kind == "public_folder" for asset in result.assets if asset.locator != root_url)


def test_discovery_skips_non_schedule_promotional_assets() -> None:
    url = "https://example.edu/faculty/schedule"
    html = """
    <html><body>
      <a href="/files/rozklad_2_sem.pdf">Розклад 2 семестр</a>
      <a href="/files/information_booklet.pdf">Інформаційний проспект факультету</a>
      <a href="/files/dean_report.pdf">Звіт декана</a>
    </body></html>
    """
    session = FakeSession({url: html})
    source = SourceConfig(
        kind="web_page",
        name="faculty-web",
        url=url,
        allow_domains=["example.edu"],
        schedule_keywords=["розклад", "schedule"],
    )
    result = discover_source(source, session=session)
    locators = {asset.locator for asset in result.assets}
    assert "https://example.edu/files/rozklad_2_sem.pdf" in locators
    assert "https://example.edu/files/information_booklet.pdf" not in locators
    assert "https://example.edu/files/dean_report.pdf" not in locators


def test_discovery_skips_percent_encoded_non_schedule_assets() -> None:
    url = "https://example.edu/faculty/schedule"
    html = """
    <html><body>
      <a href="/files/%D1%80%D0%BE%D0%B7%D0%BA%D0%BB%D0%B0%D0%B4_2_%D1%81%D0%B5%D0%BC.pdf">Розклад 2 семестр</a>
      <a href="/files/%D0%A4%D0%86%D0%A2_%D0%B7%D0%B2%D1%96%D1%82_2020.pdf">ФІТ звіт 2020</a>
    </body></html>
    """
    session = FakeSession({url: html})
    source = SourceConfig(
        kind="web_page",
        name="faculty-web",
        url=url,
        allow_domains=["example.edu"],
        schedule_keywords=["розклад", "schedule"],
    )

    result = discover_source(source, session=session)
    locators = {asset.locator for asset in result.assets}

    assert "https://example.edu/files/%D1%80%D0%BE%D0%B7%D0%BA%D0%BB%D0%B0%D0%B4_2_%D1%81%D0%B5%D0%BC.pdf" in locators
    assert "https://example.edu/files/%D0%A4%D0%86%D0%A2_%D0%B7%D0%B2%D1%96%D1%82_2020.pdf" not in locators


def test_discovery_appends_manual_seed_assets_with_root_provenance() -> None:
    url = "https://example.edu/faculty/schedule"
    html = "<html><body><p>Schedule page</p></body></html>"
    session = FakeSession({url: html})
    source = SourceConfig(
        kind="web_page",
        name="iir-schedule",
        url=url,
        allow_domains=["example.edu"],
        manual_assets=[
            ManualAssetSeed(
                url="https://files.example.edu/official/iir_schedule.xlsx",
                display_name="IIR direct workbook",
                asset_kind="file_url",
            )
        ],
    )

    result = discover_source(source, session=session)

    manual_asset = next(asset for asset in result.assets if asset.locator.endswith("iir_schedule.xlsx"))
    assert manual_asset.origin_kind == "manual_seed"
    assert manual_asset.source_root_url == url
    assert manual_asset.metadata["manual_seed"] is True


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
