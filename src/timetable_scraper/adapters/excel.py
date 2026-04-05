from __future__ import annotations

import csv
import re
from dataclasses import dataclass
from io import BytesIO, StringIO
from pathlib import Path
from typing import Any

import xlrd
from openpyxl import load_workbook
from openpyxl.worksheet.worksheet import Worksheet

from ..models import FetchedAsset, ParsedDocument, ParsedSheet, RawRecord
from ..normalize import records_from_tabular_rows
from ..utils import DAY_NAMES, excerpt_from_values, flatten_multiline, infer_faculty_from_locator, normalize_day, normalize_header, parse_time_range

DAY_OR_TIME_HEADERS = {"день", "час"}
FIT_TEACHER_RE = re.compile(
    r"(?i)(?:проф\.?|доц\.?|ас\.?|ст\.викл\.?|викл\.?)|[А-ЯІЇЄҐ][а-яіїєґ'-]+\s+[А-ЯІЇЄҐ]\.\s*[А-ЯІЇЄҐ]\."
)
FIT_ROOM_RE = re.compile(r"(?i)(ауд\.|корпус|корп\.|клінік|лаборатор|каб\.|online|онлайн)")
FIT_LINK_RE = re.compile(r"(?i)(https?://|zoom|meet|teams|google meet|knu-ua\.zoom|id:\s*\d|код[:\s])")
FIT_WEEK_RE = re.compile(r"(?i)(\[[^\]]+\]|\bч/т\b|\bпо\s+\d{2}\.\d{2}\b|\bз\s+\d{2}\.\d{2}\b)")
FIT_COUNT_RE = re.compile(r"^\d+(?:\.0)?$")
FIT_TRAILING_WEEKS_RE = re.compile(r"\s*(\[[^\]]+\])+\s*$")
FIT_T_COUNT_RE = re.compile(r"\b(\d+)\s*т\b", re.IGNORECASE)
FIT_LESSON_TYPES = {
    "л": "лекція",
    "лек": "лекція",
    "лекція": "лекція",
    "лаб": "лабораторна",
    "лабораторна": "лабораторна",
    "пр": "практика",
    "практ": "практика",
    "практика": "практика",
    "сем": "семінар",
    "семінар": "семінар",
}


@dataclass(slots=True)
class GridCell:
    text: str
    kind: str
    min_row: int
    max_row: int
    min_col: int
    max_col: int


def parse_excel_asset(fetched_asset: FetchedAsset) -> ParsedDocument:
    suffix = Path(fetched_asset.resolved_locator.split("::")[-1]).suffix.lower()
    if suffix == ".csv":
        return _parse_csv_asset(fetched_asset)
    if suffix == ".xls":
        return _parse_xls_asset(fetched_asset)
    return _parse_xlsx_asset(fetched_asset)


def _parse_xlsx_asset(fetched_asset: FetchedAsset) -> ParsedDocument:
    workbook = load_workbook(BytesIO(fetched_asset.content), data_only=True)
    faculty = _resolve_faculty(fetched_asset)
    sheets: list[ParsedSheet] = []
    warnings: list[str] = []
    for worksheet in workbook.worksheets:
        if _looks_like_fit_grid_schedule(worksheet):
            records, row_warnings = _parse_fit_grid_schedule_sheet(worksheet, faculty=faculty)
            if records or row_warnings:
                sheets.append(
                    ParsedSheet(
                        sheet_name=worksheet.title,
                        program=flatten_multiline(worksheet.title),
                        faculty=faculty,
                        records=records,
                        warnings=row_warnings,
                    )
                )
                warnings.extend(row_warnings)
            continue
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
    faculty = _resolve_faculty(fetched_asset)
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
    faculty = _resolve_faculty(fetched_asset)
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


def _resolve_faculty(fetched_asset: FetchedAsset) -> str:
    locator = fetched_asset.asset.locator
    source_name = fetched_asset.asset.source_name.casefold()
    if "fit.knu.ua" in locator or "fit" in source_name or "фіт" in source_name:
        return "Факультет інформаційних технологій"
    faculty = infer_faculty_from_locator(locator)
    if faculty == "docs.google.com":
        return "Невідомий факультет"
    return faculty


def _looks_like_fit_grid_schedule(worksheet: Worksheet) -> bool:
    if worksheet.max_column < 4 or worksheet.max_row < 10:
        return False
    header_row = [normalize_header(worksheet.cell(2, column).value) for column in range(1, min(worksheet.max_column, 16) + 1)]
    return "день" in header_row and "час" in header_row


def _parse_fit_grid_schedule_sheet(worksheet: Worksheet, *, faculty: str) -> tuple[list[RawRecord], list[str]]:
    merged_lookup = _build_merged_lookup(worksheet)
    header_context = _build_fit_header_context(worksheet, merged_lookup)
    schedule_columns = [column for column, header in header_context["course"].items() if header]
    slot_starts = [row for row in range(5, worksheet.max_row + 1) if parse_time_range(_expanded_value(worksheet, row, 2, merged_lookup))[0]]
    if not slot_starts:
        return [], [f"Could not detect FIT-style schedule slots in sheet '{worksheet.title}'."]
    records: list[RawRecord] = []
    warnings: list[str] = []
    for slot_start in slot_starts:
        day = normalize_day(_expanded_value(worksheet, slot_start, 1, merged_lookup))
        time_text = _expanded_value(worksheet, slot_start, 2, merged_lookup)
        start_time, end_time = parse_time_range(time_text)
        if not start_time or not end_time:
            continue
        block_cells = _collect_fit_block_cells(worksheet, slot_start, merged_lookup, schedule_columns)
        subject_cells = [cell for cell in block_cells if cell.kind == "subject"]
        for subject_cell in subject_cells:
            groups = _compose_fit_groups(header_context, subject_cell.min_col, subject_cell.max_col)
            course = _compose_fit_courses(header_context, subject_cell.min_col, subject_cell.max_col)
            teacher, room, link, notes = _collect_fit_metadata(subject_cell, block_cells)
            subject, lesson_type, subject_notes = _split_fit_subject(subject_cell.text)
            merged_notes = _merge_notes(subject_notes, notes)
            values = {
                "program": flatten_multiline(worksheet.title),
                "faculty": faculty,
                "day": day,
                "start_time": start_time,
                "end_time": end_time,
                "subject": subject,
                "teacher": teacher,
                "lesson_type": lesson_type,
                "link": link,
                "room": room,
                "groups": groups,
                "course": course,
                "notes": merged_notes,
            }
            if not values["subject"]:
                continue
            records.append(
                RawRecord(
                    values=values,
                    row_index=slot_start,
                    sheet_name=worksheet.title,
                    raw_excerpt=excerpt_from_values(values),
                )
            )
    if not records:
        warnings.append(f"Could not extract FIT-style rows from sheet '{worksheet.title}'.")
    return records, warnings


def _build_fit_header_context(worksheet: Worksheet, merged_lookup: dict[tuple[int, int], tuple[int, int, int, int]]) -> dict[str, dict[int, str]]:
    course_map: dict[int, str] = {}
    group_map: dict[int, str] = {}
    subgroup_map: dict[int, str] = {}
    current_course = ""
    current_group = ""
    current_subgroup = ""
    for column in range(3, worksheet.max_column + 1):
        raw_course = _expanded_value(worksheet, 2, column, merged_lookup)
        normalized_course = normalize_header(raw_course)
        if normalized_course in DAY_OR_TIME_HEADERS:
            current_course = ""
            current_group = ""
            current_subgroup = ""
        elif raw_course:
            current_course = raw_course
        raw_group = _expanded_value(worksheet, 3, column, merged_lookup)
        if raw_group:
            current_group = raw_group
        raw_subgroup = _expanded_value(worksheet, 4, column, merged_lookup)
        if raw_subgroup:
            current_subgroup = raw_subgroup
        course_map[column] = current_course
        group_map[column] = current_group
        subgroup_map[column] = current_subgroup
    return {"course": course_map, "group": group_map, "subgroup": subgroup_map}


def _collect_fit_block_cells(
    worksheet: Worksheet,
    slot_start: int,
    merged_lookup: dict[tuple[int, int], tuple[int, int, int, int]],
    schedule_columns: list[int],
) -> list[GridCell]:
    block_end = min(slot_start + 7, worksheet.max_row)
    seen_anchors: set[tuple[int, int, int, int]] = set()
    cells: list[GridCell] = []
    for row in range(slot_start, block_end + 1):
        for column in schedule_columns:
            value = worksheet.cell(row, column).value
            if value in ("", None):
                continue
            anchor = merged_lookup.get((row, column), (row, column, row, column))
            if anchor in seen_anchors:
                continue
            seen_anchors.add(anchor)
            text = flatten_multiline(worksheet.cell(anchor[0], anchor[1]).value)
            kind = _classify_fit_cell(text)
            if kind == "ignore":
                continue
            cells.append(
                GridCell(
                    text=text,
                    kind=kind,
                    min_row=anchor[0],
                    max_row=anchor[2],
                    min_col=anchor[1],
                    max_col=anchor[3],
                )
            )
    return cells


def _classify_fit_cell(text: str) -> str:
    cleaned = flatten_multiline(text)
    if not cleaned or FIT_COUNT_RE.fullmatch(cleaned):
        return "ignore"
    normalized = normalize_header(cleaned)
    if normalized in DAY_OR_TIME_HEADERS or normalize_day(cleaned) in DAY_NAMES.values():
        return "ignore"
    if parse_time_range(cleaned)[0]:
        return "ignore"
    if FIT_LINK_RE.search(cleaned):
        return "link"
    if FIT_ROOM_RE.search(cleaned):
        return "room"
    if FIT_TEACHER_RE.search(cleaned):
        return "teacher"
    if FIT_WEEK_RE.search(cleaned) and not _looks_like_subject_text(cleaned):
        return "week"
    if not any(character.isalpha() for character in cleaned):
        return "ignore"
    return "subject"


def _looks_like_subject_text(text: str) -> bool:
    lowered = text.casefold()
    return any(marker in lowered for marker in ("(", "лаб", "лек", "пр", "сем", "основи", "архітект", "матем", "комп", "кібер", "інозем"))


def _collect_fit_metadata(subject_cell: GridCell, block_cells: list[GridCell]) -> tuple[str, str, str, list[str]]:
    teacher_parts: list[str] = []
    room_parts: list[str] = []
    link_parts: list[str] = []
    note_parts: list[str] = []
    for cell in block_cells:
        if cell is subject_cell or cell.kind == "subject":
            continue
        if not _column_ranges_overlap(subject_cell, cell):
            continue
        cleaned = flatten_multiline(cell.text)
        if cell.kind == "teacher":
            teacher_text, extracted_notes = _split_bracket_notes(cleaned)
            if teacher_text:
                teacher_parts.append(teacher_text)
            note_parts.extend(extracted_notes)
        elif cell.kind == "room":
            room_parts.append(cleaned)
        elif cell.kind == "link":
            link_parts.append(cleaned)
        elif cell.kind == "week":
            note_parts.append(cleaned)
    return (
        _join_unique(teacher_parts),
        _join_unique(room_parts),
        _join_unique(link_parts, separator=" "),
        _unique_list(note_parts),
    )


def _split_fit_subject(text: str) -> tuple[str, str, list[str]]:
    cleaned = flatten_multiline(text)
    notes: list[str] = []
    trailing_weeks = FIT_TRAILING_WEEKS_RE.findall(cleaned)
    if trailing_weeks:
        notes.extend(trailing_weeks)
        cleaned = FIT_TRAILING_WEEKS_RE.sub("", cleaned).strip()
    lesson_type = ""
    lesson_type_match = re.search(r"\(([^()]{1,12})\)", cleaned)
    if lesson_type_match:
        raw_lesson_type = lesson_type_match.group(1).strip().casefold().rstrip(".")
        lesson_type = FIT_LESSON_TYPES.get(raw_lesson_type, lesson_type_match.group(1).strip())
        cleaned = cleaned.replace(lesson_type_match.group(0), "").strip()
    t_count_match = FIT_T_COUNT_RE.search(cleaned)
    if t_count_match:
        notes.append(f"T={t_count_match.group(1)}")
        cleaned = FIT_T_COUNT_RE.sub("", cleaned).strip()
    if lesson_type:
        cleaned = re.sub(r"\s{2,}", " ", cleaned).strip(" -/;")
    return cleaned or flatten_multiline(text), lesson_type, _unique_list(notes)


def _split_bracket_notes(text: str) -> tuple[str, list[str]]:
    notes = re.findall(r"\[[^\]]+\]", text)
    cleaned = re.sub(r"\[[^\]]+\]", "", text).strip()
    return cleaned, _unique_list(notes)


def _compose_fit_groups(header_context: dict[str, dict[int, str]], min_col: int, max_col: int) -> str:
    subgroup_values = _unique_list(
        header_context["subgroup"].get(column, "")
        for column in range(min_col, max_col + 1)
        if header_context["subgroup"].get(column, "")
    )
    if subgroup_values:
        return "; ".join(subgroup_values)
    group_values = _unique_list(
        header_context["group"].get(column, "")
        for column in range(min_col, max_col + 1)
        if header_context["group"].get(column, "")
    )
    return "; ".join(group_values)


def _compose_fit_courses(header_context: dict[str, dict[int, str]], min_col: int, max_col: int) -> str:
    course_values: list[str] = []
    for column in range(min_col, max_col + 1):
        header = header_context["course"].get(column, "")
        match = re.search(r"\b(\d+)\s*курс\b", header.casefold())
        if match:
            course_values.append(match.group(1))
    return "; ".join(_unique_list(course_values))


def _merge_notes(*note_groups: list[str]) -> str:
    notes: list[str] = []
    for group in note_groups:
        notes.extend(group)
    return "; ".join(_unique_list(notes))


def _join_unique(values: list[str], *, separator: str = "; ") -> str:
    return separator.join(_unique_list(values))


def _unique_list(values: Any) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        cleaned = flatten_multiline(value)
        if not cleaned or cleaned in seen:
            continue
        seen.add(cleaned)
        result.append(cleaned)
    return result


def _expanded_value(
    worksheet: Worksheet,
    row: int,
    column: int,
    merged_lookup: dict[tuple[int, int], tuple[int, int, int, int]],
) -> str:
    direct = flatten_multiline(worksheet.cell(row, column).value)
    if direct:
        return direct
    anchor = merged_lookup.get((row, column))
    if anchor is None:
        return ""
    return flatten_multiline(worksheet.cell(anchor[0], anchor[1]).value)


def _build_merged_lookup(worksheet: Worksheet) -> dict[tuple[int, int], tuple[int, int, int, int]]:
    lookup: dict[tuple[int, int], tuple[int, int, int, int]] = {}
    for merged_range in worksheet.merged_cells.ranges:
        anchor = (merged_range.min_row, merged_range.min_col, merged_range.max_row, merged_range.max_col)
        for row in range(merged_range.min_row, merged_range.max_row + 1):
            for column in range(merged_range.min_col, merged_range.max_col + 1):
                lookup[(row, column)] = anchor
    return lookup


def _column_ranges_overlap(left: GridCell, right: GridCell) -> bool:
    return not (left.max_col < right.min_col or right.max_col < left.min_col)
