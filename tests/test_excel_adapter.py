from __future__ import annotations

from io import BytesIO
from pathlib import Path

import pytest
from openpyxl import Workbook

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


def test_fit_style_grid_workbook_is_parsed() -> None:
    workbook = Workbook()
    worksheet = workbook.active
    worksheet.title = "ІПЗ"
    worksheet["A2"] = "день"
    worksheet["B2"] = "час"
    worksheet["C2"] = "1 курс ІПЗ"
    worksheet.merge_cells("C2:D2")
    worksheet["C3"] = "група ІПЗ-11"
    worksheet.merge_cells("C3:D3")
    worksheet["C4"] = "підгрупа ІПЗ-11/1"
    worksheet.merge_cells("C4:D4")
    worksheet["A5"] = "понеділок"
    worksheet["B5"] = "9:00-10:20"
    worksheet["C5"] = "Архітектура комп'ютера (лаб) 12т"
    worksheet.merge_cells("C5:D7")
    worksheet["C8"] = "[08.09-01.12]"
    worksheet.merge_cells("C8:D8")
    worksheet["C9"] = "Вовна О. В."
    worksheet.merge_cells("C9:D9")
    worksheet["C10"] = "109 ауд."
    worksheet["D10"] = "meet"

    buffer = BytesIO()
    workbook.save(buffer)
    asset = DiscoveredAsset(
        source_name="fit-grid",
        source_kind="google_sheet",
        source_url_or_path="https://fit.knu.ua/for-students/lessons-schedule",
        asset_kind="google_sheet",
        locator="https://docs.google.com/spreadsheets/d/test/edit#gid=0",
        display_name="fit-grid.xlsx",
    )
    fetched = FetchedAsset(
        asset=asset,
        content=buffer.getvalue(),
        content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        content_hash="fit-grid",
        resolved_locator="fit-grid.xlsx",
    )

    document = parse_excel_asset(fetched)
    total_records = sum(len(sheet.records) for sheet in document.sheets)

    assert total_records == 1
    record = document.sheets[0].records[0]
    assert record.values["day"] == "Понеділок"
    assert record.values["start_time"] == "09:00"
    assert record.values["end_time"] == "10:20"
    assert record.values["subject"] == "Архітектура комп'ютера"
    assert record.values["lesson_type"] == "лабораторна"
    assert record.values["teacher"] == "Вовна О. В."
    assert record.values["room"] == "109 ауд."
