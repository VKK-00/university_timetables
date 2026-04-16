from __future__ import annotations

from io import BytesIO
from pathlib import Path
import zipfile

from openpyxl import Workbook

from timetable_scraper.manual_reference import REFERENCE_COLUMNS, audit_manual_reference_zip


def test_audit_manual_reference_zip_summarizes_canonical_workbook(tmp_path: Path) -> None:
    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "1 курс"
    sheet["A1"] = "Соціологія"
    for column_index, header in enumerate(REFERENCE_COLUMNS, start=1):
        sheet.cell(2, column_index).value = header
    sheet.append(
        [
            "1-13 верхній",
            "Понеділок",
            "08:30",
            "09:50",
            "Соціологічна теорія",
            "доц. Іваненко І.І.",
            "лекція",
            "",
            "ауд. 312",
            "1.0",
            "1.0",
            "ручний еталон",
        ]
    )
    buffer = BytesIO()
    workbook.save(buffer)

    zip_path = tmp_path / "drive-download-20260416T062121Z-3-001.zip"
    with zipfile.ZipFile(zip_path, "w") as archive:
        archive.writestr("Соціологія.xlsx", buffer.getvalue())

    summary = audit_manual_reference_zip(zip_path)

    assert summary["workbook_count"] == 1
    assert summary["sheet_count"] == 1
    assert summary["sampled_data_rows"] == 1
    assert summary["canonical_sheets"] == 1
    assert summary["top_titles"][0] == {"value": "Соціологія", "count": 1}
    assert summary["top_week_values"][0] == {"value": "1-13 верхній", "count": 1}
    assert summary["top_group_values"][0] == {"value": "1", "count": 1}
    assert summary["top_course_values"][0] == {"value": "1", "count": 1}
