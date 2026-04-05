from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

from .models import NormalizedRow, ParsedDocument, RawRecord
from .utils import (
    clean_numeric_artifact,
    coalesce_label,
    flatten_multiline,
    humanize_source_name,
    infer_faculty_from_locator,
    normalize_day,
    normalize_header,
    normalize_week_type,
    parse_time_range,
    parse_time_value,
)


HEADER_ALIASES = {
    "тиждень": "week_type",
    "день": "day",
    "початок": "start_time",
    "кінець": "end_time",
    "назва предмета": "subject",
    "назва предмету": "subject",
    "викладач": "teacher",
    "тип заняття": "lesson_type",
    "посилання": "link",
    "аудиторія": "room",
    "групи": "groups",
    "курс": "course",
    "курси": "course",
    "примітки": "notes",
}

SUBJECT_FALLBACK_LESSON_TYPES = {
    "самостійна робота",
    "кваліфікаційна робота бакалавра",
    "кваліфікаційна робота магістра",
    "лабораторні",
}

SUBJECT_FALLBACK_NOTES_PATTERNS = (
    "день самостійної роботи",
    "день самостiйної роботи",
)

NON_CLASS_MARKER_PATTERNS = (
    "вихідний",
    "вихiдний",
    *SUBJECT_FALLBACK_NOTES_PATTERNS,
)

INFORMATIONAL_NOTE_PATTERNS = (
    "розклад занять",
    "з'явиться пізніше",
    "з`явиться пізніше",
)

FILL_DOWN_FIELDS = ("week_type", "day", "start_time", "end_time")
DEFAULT_SLOT_DURATION_MINUTES = 80


def map_headers(headers: list[Any]) -> dict[str, int]:
    mapping: dict[str, int] = {}
    for index, header in enumerate(headers):
        canonical = HEADER_ALIASES.get(normalize_header(header))
        if canonical:
            mapping[canonical] = index
    return mapping


def records_from_tabular_rows(
    rows: list[list[Any]],
    *,
    program: str,
    faculty: str,
    sheet_name: str,
) -> tuple[list[RawRecord], list[str]]:
    header_index = None
    header_map: dict[str, int] = {}
    for index, row in enumerate(rows[:10]):
        candidate = map_headers(row)
        if {"day", "start_time", "end_time", "subject"} <= set(candidate):
            header_index = index
            header_map = candidate
            break
    if header_index is None:
        return [], [f"Could not detect header row in sheet '{sheet_name}'."]
    records: list[RawRecord] = []
    carry_values: dict[str, Any] = {}
    for row_number, row in enumerate(rows[header_index + 1 :], start=header_index + 2):
        if _is_repeated_header_row(row):
            carry_values = {}
            continue
        values = {
            field: row[column]
            for field, column in header_map.items()
            if column < len(row) and row[column] not in ("", None)
        }
        if not values:
            continue
        if _is_section_title_row(row, values):
            carry_values = {}
            continue
        values = _apply_fill_down(values, carry_values)
        if _should_skip_tabular_row(values):
            continue
        values["program"] = program
        values["faculty"] = faculty
        values.setdefault("raw_time", "")
        excerpt = " | ".join(flatten_multiline(value) for value in values.values() if flatten_multiline(value))
        records.append(RawRecord(values=values, row_index=row_number, sheet_name=sheet_name, raw_excerpt=excerpt))
        for field in FILL_DOWN_FIELDS:
            if values.get(field) not in ("", None):
                carry_values[field] = values[field]
    return records, []


def normalize_document(document: ParsedDocument) -> list[NormalizedRow]:
    return [normalize_record(record, document=document) for sheet in document.sheets for record in sheet.records]


def normalize_record(record: RawRecord, *, document: ParsedDocument) -> NormalizedRow:
    values = defaultdict(str, {key: flatten_multiline(value) for key, value in record.values.items()})
    source_asset = document.asset.asset
    source_name = source_asset.source_name
    source_root_url = source_asset.source_root_url or source_asset.source_url_or_path or source_asset.locator
    source_label = humanize_source_name(source_name)

    subject_inferred = False
    if not values["subject"] and values["lesson_type"].casefold() in SUBJECT_FALLBACK_LESSON_TYPES:
        values["subject"] = values["lesson_type"]
        subject_inferred = True
        record.warnings.append("subject_inferred_from_lesson_type")
    if not values["subject"] and any(pattern in values["notes"].casefold() for pattern in SUBJECT_FALLBACK_NOTES_PATTERNS):
        values["subject"] = values["notes"]
        subject_inferred = True
        record.warnings.append("subject_inferred_from_notes")
    if not values["subject"] and _looks_like_non_class_marker(values["notes"]):
        values["subject"] = _normalize_non_class_subject(values["notes"])
        subject_inferred = True
        record.warnings.append("subject_inferred_from_non_class_note")
    if (
        not values["subject"]
        and _looks_like_subject_candidate(values["groups"])
        and not any(values[field] for field in ("teacher", "lesson_type", "room"))
    ):
        values["subject"] = values["groups"]
        subject_inferred = True
        record.warnings.append("subject_inferred_from_groups")

    start_time = parse_time_value(values["start_time"])
    end_time = parse_time_value(values["end_time"])
    if (not start_time or not end_time) and values["raw_time"]:
        start_time, end_time = parse_time_range(values["raw_time"])
    start_time, end_time = _infer_missing_time_bounds(start_time, end_time, values)

    warnings = list(record.warnings)
    if not values["day"]:
        warnings.append("missing_day")
    if not start_time:
        warnings.append("missing_start_time")
    if not end_time:
        warnings.append("missing_end_time")
    if not values["subject"]:
        warnings.append("missing_subject")
    elif subject_inferred:
        warnings = [warning for warning in warnings if warning != "missing_subject"]

    confidence = score_record(
        has_day=bool(values["day"]),
        has_start=bool(start_time),
        has_end=bool(end_time),
        has_subject=bool(values["subject"]),
        warning_count=len(warnings),
    )

    faculty = coalesce_label(
        values["faculty"],
        infer_faculty_from_locator(source_root_url),
        source_label,
        fallback="Невідомий факультет",
    )
    display_stem = Path(flatten_multiline(source_asset.display_name) or source_label).stem
    program = coalesce_label(
        values["program"],
        record.sheet_name,
        display_stem,
        source_label,
        fallback="Невідома програма",
    )

    return NormalizedRow(
        program=program,
        faculty=faculty,
        week_type=normalize_week_type(values["week_type"]),
        day=normalize_day(values["day"]),
        start_time=start_time,
        end_time=end_time,
        subject=flatten_multiline(values["subject"]),
        teacher=flatten_multiline(values["teacher"]),
        lesson_type=flatten_multiline(values["lesson_type"]),
        link=flatten_multiline(values["link"]),
        room=flatten_multiline(values["room"]),
        groups=clean_numeric_artifact(values["groups"]),
        course=clean_numeric_artifact(values["course"]),
        notes=flatten_multiline(values["notes"]),
        sheet_name=record.sheet_name,
        source_name=source_name,
        source_kind=source_asset.source_kind,
        source_root_url=source_root_url,
        asset_locator=source_asset.locator,
        source_url_or_path=source_root_url,
        confidence=confidence,
        warnings=warnings,
        raw_excerpt=record.raw_excerpt,
        content_hash=document.asset.content_hash,
    )


def score_record(
    *,
    has_day: bool,
    has_start: bool,
    has_end: bool,
    has_subject: bool,
    warning_count: int,
) -> float:
    score = 0.0
    score += 0.28 if has_day else 0
    score += 0.24 if has_start else 0
    score += 0.24 if has_end else 0
    score += 0.24 if has_subject else 0
    score -= min(warning_count, 4) * 0.05
    return max(0.0, min(score, 1.0))


def _should_skip_tabular_row(values: dict[str, Any]) -> bool:
    signal_fields = {field for field, value in values.items() if flatten_multiline(value)}
    meaningful_fields = signal_fields - {"week_type", "day", "start_time", "end_time", "program", "faculty", "link"}
    if not meaningful_fields:
        return True
    if meaningful_fields <= {"course"}:
        return True
    return meaningful_fields <= {"notes", "course"} and _looks_like_informational_note(values.get("notes"))


def _apply_fill_down(values: dict[str, Any], carry_values: dict[str, Any]) -> dict[str, Any]:
    if not _has_schedule_payload(values):
        return values
    filled = dict(values)
    for field in FILL_DOWN_FIELDS:
        if filled.get(field) in ("", None) and carry_values.get(field) not in ("", None):
            filled[field] = carry_values[field]
    return filled


def _has_schedule_payload(values: dict[str, Any]) -> bool:
    return any(
        flatten_multiline(values.get(field))
        for field in ("subject", "teacher", "lesson_type", "link", "room", "groups", "course", "notes")
    )


def _has_class_payload(values: dict[str, Any]) -> bool:
    return any(
        flatten_multiline(values.get(field))
        for field in ("subject", "teacher", "lesson_type", "link", "room", "groups")
    )


def _is_repeated_header_row(row: list[Any]) -> bool:
    normalized = [normalize_header(cell) for cell in row if flatten_multiline(cell)]
    if not normalized:
        return False
    expected = {"тиждень", "день", "початок", "кінець", "назва предмета", "назва предмету", "викладач"}
    return len(normalized) >= 4 and len(expected.intersection(normalized)) >= 4


def _is_section_title_row(row: list[Any], values: dict[str, Any]) -> bool:
    non_empty = [flatten_multiline(cell) for cell in row if flatten_multiline(cell)]
    if len(non_empty) == 1:
        return True
    if set(values) == {"week_type"} and len(non_empty) <= 2:
        return True
    return False


def _looks_like_subject_candidate(value: Any) -> bool:
    text = flatten_multiline(value)
    if not text:
        return False
    if any(pattern in text.casefold() for pattern in SUBJECT_FALLBACK_NOTES_PATTERNS):
        return True
    return (any(ch.isalpha() for ch in text) and not text.isupper()) or ("," in text)


def _looks_like_non_class_marker(value: Any) -> bool:
    text = flatten_multiline(value).casefold()
    return bool(text) and any(pattern in text for pattern in NON_CLASS_MARKER_PATTERNS)


def _normalize_non_class_subject(value: Any) -> str:
    text = flatten_multiline(value)
    lowered = text.casefold()
    if "вихідний" in lowered or "вихiдний" in lowered:
        return "Вихідний"
    if any(pattern in lowered for pattern in SUBJECT_FALLBACK_NOTES_PATTERNS):
        return "День самостійної роботи"
    return text


def _looks_like_informational_note(value: Any) -> bool:
    text = flatten_multiline(value).casefold()
    return bool(text) and any(pattern in text for pattern in INFORMATIONAL_NOTE_PATTERNS)


def _infer_missing_time_bounds(start_time: str, end_time: str, values: dict[str, Any]) -> tuple[str, str]:
    if start_time and end_time:
        return start_time, end_time
    if not _has_class_payload(values) or _looks_like_non_class_marker(values.get("notes")):
        return start_time, end_time
    if start_time:
        return start_time, _shift_time(start_time, DEFAULT_SLOT_DURATION_MINUTES)
    if end_time:
        return _shift_time(end_time, -DEFAULT_SLOT_DURATION_MINUTES), end_time
    return start_time, end_time


def _shift_time(time_value: str, minutes: int) -> str:
    parsed = datetime.strptime(time_value, "%H:%M")
    shifted = parsed + timedelta(minutes=minutes)
    return shifted.strftime("%H:%M")
