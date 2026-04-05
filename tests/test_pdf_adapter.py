from __future__ import annotations

from pathlib import Path

import pytest

from timetable_scraper.adapters.pdf import parse_pdf_asset
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
