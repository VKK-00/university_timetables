from __future__ import annotations

from pathlib import Path
import json

from openpyxl import load_workbook

from timetable_scraper.export import export_rows
from timetable_scraper.models import NormalizedRow


def test_export_rows_apply_uniform_body_style_across_written_rows(tmp_path: Path) -> None:
    template_path = next(Path(".").glob("*.xlsx")).resolve()
    rows = [
        NormalizedRow(
            program="Demo Program",
            faculty="Demo Faculty",
            week_type="Обидва",
            day="Понеділок",
            start_time="08:00",
            end_time="09:20",
            subject=f"Предмет {index}",
            teacher="доц. Іваненко",
            lesson_type="лекція",
            room="101",
            groups="1",
            course="1",
            sheet_name="1 курс",
        )
        for index in range(8)
    ]
    exported_files, _, _ = export_rows(rows, [], template_path=template_path, output_dir=tmp_path / "out")
    workbook = load_workbook(exported_files[0])
    sheet = workbook.active

    early_cell = sheet["A3"]
    late_cell = sheet["A10"]

    assert early_cell.font.name == late_cell.font.name
    assert early_cell.font.sz == late_cell.font.sz
    assert early_cell.alignment.horizontal == late_cell.alignment.horizontal
    assert early_cell.alignment.vertical == late_cell.alignment.vertical
    assert early_cell.alignment.wrap_text == late_cell.alignment.wrap_text
    assert late_cell.font.name != "Calibri"
    assert late_cell.value == "Обидва"


def test_export_rows_clear_template_sample_rows_when_sheet_is_short(tmp_path: Path) -> None:
    template_path = next(Path(".").glob("*.xlsx")).resolve()
    rows = [
        NormalizedRow(
            program="Short Program",
            faculty="Short Faculty",
            week_type="Обидва",
            day="Вівторок",
            start_time="09:30",
            end_time="10:50",
            subject="Мікроекономіка",
            teacher="доц. Петренко",
            lesson_type="семінар",
            room="202",
            groups="2",
            course="2",
            sheet_name="1 курс",
        )
    ]
    exported_files, _, _ = export_rows(rows, [], template_path=template_path, output_dir=tmp_path / "out")
    workbook = load_workbook(exported_files[0])
    sheet = workbook.active

    assert sheet["A3"].value == "Обидва"
    assert sheet["E3"].value == "Мікроекономіка"
    assert sheet["A4"].value is None
    assert sheet["E4"].value is None


def test_manifest_serializes_provenance_fields(tmp_path: Path) -> None:
    template_path = next(Path(".").glob("*.xlsx")).resolve()
    rows = [
        NormalizedRow(
            program="Demo Program",
            faculty="Demo Faculty",
            week_type="Обидва",
            day="Понеділок",
            start_time="08:00",
            end_time="09:20",
            subject="Предмет",
            source_name="demo-source",
            source_kind="web_page",
            source_root_url="https://example.edu/schedule",
            asset_locator="https://docs.google.com/spreadsheets/d/demo/edit",
        )
    ]
    _, manifest_path, _ = export_rows(rows, [], template_path=template_path, output_dir=tmp_path / "out")
    payload = json.loads(manifest_path.read_text(encoding="utf-8").splitlines()[0])
    assert payload["source_name"] == "demo-source"
    assert payload["source_root_url"] == "https://example.edu/schedule"
    assert payload["asset_locator"] == "https://docs.google.com/spreadsheets/d/demo/edit"


def test_export_rows_preserve_literal_text_that_starts_with_equals(tmp_path: Path) -> None:
    template_path = next(Path(".").glob("*.xlsx")).resolve()
    rows = [
        NormalizedRow(
            program="Demo Program",
            faculty="Demo Faculty",
            week_type="Обидва",
            day="Понеділок",
            start_time="08:00",
            end_time="09:20",
            subject="=encoded-token",
            sheet_name="1 курс",
        )
    ]
    exported_files, _, _ = export_rows(rows, [], template_path=template_path, output_dir=tmp_path / "out")
    workbook = load_workbook(exported_files[0], data_only=False)
    sheet = workbook.active
    assert sheet["E3"].value == "=encoded-token"
    assert sheet["E3"].data_type == "s"
