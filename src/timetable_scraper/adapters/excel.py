from __future__ import annotations

import csv
from io import BytesIO, StringIO
from pathlib import Path

import xlrd
from openpyxl import load_workbook

from ..models import FetchedAsset, ParsedDocument, ParsedSheet
from ..normalize import records_from_tabular_rows
from ..utils import flatten_multiline, infer_faculty_from_locator


def parse_excel_asset(fetched_asset: FetchedAsset) -> ParsedDocument:
    suffix = Path(fetched_asset.resolved_locator.split("::")[-1]).suffix.lower()
    if suffix == ".csv":
        return _parse_csv_asset(fetched_asset)
    if suffix == ".xls":
        return _parse_xls_asset(fetched_asset)
    return _parse_xlsx_asset(fetched_asset)


def _parse_xlsx_asset(fetched_asset: FetchedAsset) -> ParsedDocument:
    workbook = load_workbook(BytesIO(fetched_asset.content), data_only=True)
    faculty = infer_faculty_from_locator(fetched_asset.asset.locator)
    sheets: list[ParsedSheet] = []
    warnings: list[str] = []
    for worksheet in workbook.worksheets:
        rows = [
            list(row)
            for row in worksheet.iter_rows(values_only=True)
            if any(cell not in ("", None) for cell in row)
        ]
        if not rows:
            warnings.append(f"Skipped empty sheet '{worksheet.title}'.")
            continue
        program = _extract_program_title(rows, fallback=worksheet.title)
        records, row_warnings = records_from_tabular_rows(rows, program=program, faculty=faculty, sheet_name=worksheet.title)
        sheets.append(
            ParsedSheet(
                sheet_name=worksheet.title,
                program=program,
                faculty=faculty,
                records=records,
                warnings=row_warnings,
            )
        )
        warnings.extend(row_warnings)
    return ParsedDocument(asset=fetched_asset, sheets=sheets, warnings=warnings)


def _parse_xls_asset(fetched_asset: FetchedAsset) -> ParsedDocument:
    workbook = xlrd.open_workbook(file_contents=fetched_asset.content)
    faculty = infer_faculty_from_locator(fetched_asset.asset.locator)
    sheets: list[ParsedSheet] = []
    warnings: list[str] = []
    for worksheet in workbook.sheets():
        rows = [
            worksheet.row_values(index)
            for index in range(worksheet.nrows)
            if any(value not in ("", None) for value in worksheet.row_values(index))
        ]
        if not rows:
            warnings.append(f"Skipped empty sheet '{worksheet.name}'.")
            continue
        program = _extract_program_title(rows, fallback=worksheet.name)
        records, row_warnings = records_from_tabular_rows(rows, program=program, faculty=faculty, sheet_name=worksheet.name)
        sheets.append(
            ParsedSheet(
                sheet_name=worksheet.name,
                program=program,
                faculty=faculty,
                records=records,
                warnings=row_warnings,
            )
        )
        warnings.extend(row_warnings)
    return ParsedDocument(asset=fetched_asset, sheets=sheets, warnings=warnings)


def _parse_csv_asset(fetched_asset: FetchedAsset) -> ParsedDocument:
    reader = csv.reader(StringIO(fetched_asset.content.decode("utf-8-sig", "ignore")))
    rows = [row for row in reader if any(cell not in ("", None) for cell in row)]
    faculty = infer_faculty_from_locator(fetched_asset.asset.locator)
    program = _extract_program_title(rows, fallback=fetched_asset.asset.display_name)
    records, warnings = records_from_tabular_rows(rows, program=program, faculty=faculty, sheet_name="Аркуш1")
    return ParsedDocument(
        asset=fetched_asset,
        sheets=[ParsedSheet(sheet_name="Аркуш1", program=program, faculty=faculty, records=records, warnings=warnings)],
        warnings=warnings,
    )


def _extract_program_title(rows: list[list[object]], fallback: str) -> str:
    for row in rows[:3]:
        values = [flatten_multiline(cell) for cell in row if flatten_multiline(cell)]
        if len(values) == 1:
            return values[0]
    return flatten_multiline(fallback)
