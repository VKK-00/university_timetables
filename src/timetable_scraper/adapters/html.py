from __future__ import annotations

from bs4 import BeautifulSoup

from ..models import FetchedAsset, ParsedDocument, ParsedSheet, RawRecord
from ..normalize import records_from_tabular_rows
from ..utils import DAY_NAMES, excerpt_from_values, flatten_multiline, infer_faculty_from_locator, normalize_day, parse_time_range


def parse_html_asset(fetched_asset: FetchedAsset) -> ParsedDocument:
    html = fetched_asset.content.decode("utf-8", "ignore")
    soup = BeautifulSoup(html, "lxml")
    faculty = infer_faculty_from_locator(fetched_asset.asset.locator)
    program = flatten_multiline(soup.title.get_text(" ", strip=True) if soup.title else fetched_asset.asset.display_name)
    sheets: list[ParsedSheet] = []
    warnings: list[str] = []
    for index, table in enumerate(soup.find_all("table"), start=1):
        rows = []
        for row in table.find_all("tr"):
            cells = row.find_all(["th", "td"])
            values = [flatten_multiline(cell.get_text(" ", strip=True)) for cell in cells]
            if any(values):
                rows.append(values)
        records, row_warnings = records_from_tabular_rows(rows, program=program, faculty=faculty, sheet_name=f"table-{index}")
        if records:
            sheets.append(
                ParsedSheet(
                    sheet_name=f"table-{index}",
                    program=program,
                    faculty=faculty,
                    records=records,
                    warnings=row_warnings,
                )
            )
            warnings.extend(row_warnings)
    if sheets:
        return ParsedDocument(asset=fetched_asset, sheets=sheets, warnings=warnings)
    records = _parse_block_records(soup.get_text("\n", strip=True), sheet_name="page", faculty=faculty, program=program)
    return ParsedDocument(
        asset=fetched_asset,
        sheets=[ParsedSheet(sheet_name="page", program=program, faculty=faculty, records=records)],
        warnings=warnings,
    )


def _parse_block_records(text: str, *, sheet_name: str, faculty: str, program: str) -> list[RawRecord]:
    lines = [flatten_multiline(line) for line in text.splitlines() if flatten_multiline(line)]
    current_day = ""
    records: list[RawRecord] = []
    for index, line in enumerate(lines, start=1):
        maybe_day = normalize_day(line)
        if line.casefold() in DAY_NAMES or maybe_day in DAY_NAMES.values():
            current_day = maybe_day
            continue
        start_time, end_time = parse_time_range(line)
        if not start_time or not end_time:
            continue
        after_time = line.split(end_time, 1)[-1].strip(" -|")
        parts = [part.strip() for part in after_time.split("|") if part.strip()]
        values = {
            "program": program,
            "faculty": faculty,
            "day": current_day,
            "start_time": start_time,
            "end_time": end_time,
            "subject": parts[0] if parts else after_time,
            "teacher": parts[1] if len(parts) > 1 else "",
            "lesson_type": parts[2] if len(parts) > 2 else "",
            "room": parts[3] if len(parts) > 3 else "",
        }
        records.append(
            RawRecord(
                values=values,
                row_index=index,
                sheet_name=sheet_name,
                raw_excerpt=excerpt_from_values(values),
            )
        )
    return records
