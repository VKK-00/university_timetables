from __future__ import annotations

from pathlib import Path

import pytest

from timetable_scraper.adapters.pdf import _parse_pdf_table, parse_pdf_asset
from timetable_scraper.models import DiscoveredAsset, FetchedAsset
from timetable_scraper.ocr import find_tesseract_binary

PDF_DIR = Path(__file__).parent / "fixtures" / "pdf"


def _make_pdf_fetched(path: Path) -> FetchedAsset:
    asset = DiscoveredAsset(
        source_name="fixture",
        source_kind="file_url",
        source_url_or_path=str(path),
        asset_kind="file_url",
        locator=str(path),
        display_name=path.name,
    )
    return FetchedAsset(asset=asset, content=path.read_bytes(), content_type="application/pdf", content_hash=path.stem, resolved_locator=str(path))


def test_text_pdf_parses_without_ocr() -> None:
    document = parse_pdf_asset(_make_pdf_fetched(PDF_DIR / "text_schedule.pdf"), ocr_enabled=True)
    records = [record for sheet in document.sheets for record in sheet.records]
    assert document.warnings or records
    if records:
        assert any(record.values["start_time"] == "09:30" and record.values["room"] for record in records)
    else:
        assert any("complete day/time/subject rows" in warning for warning in document.warnings)


@pytest.mark.skipif(find_tesseract_binary() is None, reason="Tesseract is not installed")
def test_scanned_pdf_parses_with_ocr() -> None:
    document = parse_pdf_asset(_make_pdf_fetched(PDF_DIR / "scanned_schedule.pdf"), ocr_enabled=True)
    records = [record for sheet in document.sheets for record in sheet.records]
    assert document.warnings or records
    if records:
        assert any(record.values["subject"] for record in records)
    else:
        assert any("OCR" in warning for warning in document.warnings)


def test_pdf_rowwise_table_is_parsed() -> None:
    table = [
        ["№", "Шифр", "Назва дисципліни", "П.І.Б. викладача", "Понеділок", "Вівторок", "Середа"],
        ["1", "ОК.01", "Академічне письмо англійською мовою", "доц. Александрук І.В.", "", "12:20-13:55", ""],
    ]

    records = _parse_pdf_table(table, sheet_name="rowwise", faculty="test", program="test")

    assert records
    assert any(record.values["day"] == "Вівторок" for record in records)
    assert any(record.values["start_time"] == "12:20" for record in records)
    assert any("Академічне письмо" in record.values["subject"] for record in records)


def test_pdf_grid_table_is_parsed() -> None:
    table = [
        ["В10 Філософія", None, "1 курс", None],
        [None, None, "1 ГРУПА", None],
        ["КОЛІДЕНОП", "13.05 – 14.25", "", None],
        [None, "14.40 – 16.00", "Історія науки й техніки\ndоц. Шашкова Л.О.\nауд. 325", None],
    ]

    records = _parse_pdf_table(table, sheet_name="grid", faculty="test", program="test")

    assert len(records) == 1
    assert records[0].values["day"] == "Понеділок"
    assert records[0].values["start_time"] == "14:40"
    assert "Історія науки" in records[0].values["subject"]
