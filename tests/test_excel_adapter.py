from __future__ import annotations

from pathlib import Path

import pytest

from timetable_scraper.adapters.excel import parse_excel_asset
from timetable_scraper.models import DiscoveredAsset, FetchedAsset

WORKBOOKS_DIR = Path(__file__).parent / "fixtures" / "workbooks"


def _make_fetched(path: Path) -> FetchedAsset:
    asset = DiscoveredAsset(
        source_name="fixture",
        source_kind="zip",
        source_url_or_path="fixture.zip",
        asset_kind="zip_entry",
        locator=f"fixture.zip::{path.name}",
        display_name=path.name,
    )
    return FetchedAsset(
        asset=asset,
        content=path.read_bytes(),
        content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        content_hash=path.stem,
        resolved_locator=path.name,
    )


@pytest.mark.parametrize(
    "filename",
    ["veb.xlsx", "physics_2.xlsx", "mev.xlsx", "mk.xlsx", "pravo.xlsx", "econ.xlsx"],
)
def test_fixture_workbooks_parse(filename: str) -> None:
    document = parse_excel_asset(_make_fetched(WORKBOOKS_DIR / filename))
    total_records = sum(len(sheet.records) for sheet in document.sheets)
    assert document.sheets
    assert total_records > 0


def test_physics_fixture_supports_subjectu_header_variant() -> None:
    document = parse_excel_asset(_make_fetched(WORKBOOKS_DIR / "physics_2.xlsx"))
    first_record = document.sheets[0].records[0]
    assert first_record.values["subject"] == "Електродинаміка"


def test_pravo_fixture_skips_empty_sheet_with_warning() -> None:
    document = parse_excel_asset(_make_fetched(WORKBOOKS_DIR / "pravo.xlsx"))
    assert any("Skipped empty sheet" in warning for warning in document.warnings)
    assert any(sheet.sheet_name == "1 курс" for sheet in document.sheets)
