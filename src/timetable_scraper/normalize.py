from __future__ import annotations

import re
from collections import defaultdict
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

from .models import NormalizedRow, ParsedDocument, RawRecord
from .utils import (
    LINK_TEXT_RE,
    ROOM_TEXT_RE,
    TEACHER_TEXT_RE,
    clean_numeric_artifact,
    coalesce_label,
    contains_link_text,
    flatten_multiline,
    humanize_source_name,
    infer_faculty_from_locator,
    looks_like_garbage_text,
    looks_like_room_text,
    looks_like_service_text,
    looks_like_teacher_text,
    normalize_day,
    normalize_header,
    normalize_service_tokens,
    normalize_week_type_meta,
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
SEGMENT_SPLIT_RE = re.compile(r"\s*(?:\||;|/)\s*")
SURNAME_ONLY_RE = re.compile(r"(?iu)^[А-ЯІЇЄҐ][а-яіїєґ'-]+$")
INITIALS_ONLY_RE = re.compile(r"(?iu)^[А-ЯІЇЄҐ]\.\s*[А-ЯІЇЄҐ]\.?$")
TITLE_ONLY_RE = re.compile(r"(?iu)^(?:проф|доц|ас|асист|викл|ст\.?\s*викл|phd|к\.\s*[юф]\.\s*н|д\.\s*[юф]\.\s*н)\.?$")
ROOM_SEGMENT_RE = re.compile(r"(?iu)^(?:\d{3,4}[А-ЯІЇЄҐA-Z]?(?:/\d+)?|[А-ЯІЇЄҐA-Z]-?\d{2,4}|online|онлайн)$")
CODE_SEGMENT_RE = re.compile(r"(?iu)^(?:meeting id|passcode|код доступу|ідентифікатор конференції|идентификатор конференции|t=\d+)\b|^[A-Za-z0-9+/=_-]{10,}$")
TRAILING_ROOM_RE = re.compile(
    r"(?iu)^(?P<subject>.+?)(?:\s*/\s*|\s+)(?P<room>(?:\d{3,4}[А-ЯІЇЄҐA-Z]?|[А-ЯІЇЄҐA-Z]-?\d{2,4}|(?:хімічний|географічний)\s+ф-?т\s+\d{2,4}))$"
)
MEETING_NOTE_RE = re.compile(r"(?iu)\b(?:meeting id|passcode|код доступу|ідентифікатор конференції|идентификатор конференции)\b")
MEETING_ABBR_RE = re.compile(r"(?iu)^(?:ік|кд|id|pwd)\s*:")


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
    values = defaultdict(str, {key: normalize_service_tokens(value) for key, value in record.values.items()})
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

    cleaned_fields = _cleanup_structured_fields(values)
    if not cleaned_fields["subject"]:
        cleaned_fields, inferred_from_notes = _infer_subject_from_notes(cleaned_fields)
        if inferred_from_notes:
            subject_inferred = True
            record.warnings.append("subject_inferred_from_notes")
    week_type, week_source = normalize_week_type_meta(
        values["week_type"],
        cleaned_fields["subject"],
        cleaned_fields["notes"],
        record.raw_excerpt,
    )

    start_time = parse_time_value(values["start_time"])
    end_time = parse_time_value(values["end_time"])
    if (not start_time or not end_time) and values["raw_time"]:
        start_time, end_time = parse_time_range(values["raw_time"])
    start_time, end_time = _infer_missing_time_bounds(start_time, end_time, cleaned_fields)

    warnings = list(dict.fromkeys(record.warnings))
    if not cleaned_fields["day"]:
        warnings.append("missing_day")
    if not start_time:
        warnings.append("missing_start_time")
    if not end_time:
        warnings.append("missing_end_time")
    if not cleaned_fields["subject"]:
        warnings.append("missing_subject")
    elif subject_inferred:
        warnings = [warning for warning in warnings if warning != "missing_subject"]
    if cleaned_fields["subject"] and looks_like_service_text(cleaned_fields["subject"]):
        warnings.append("service_text_subject")
    if cleaned_fields["subject"] and looks_like_garbage_text(cleaned_fields["subject"]):
        warnings.append("garbage_text_subject")

    confidence = score_record(
        has_day=bool(cleaned_fields["day"]),
        has_start=bool(start_time),
        has_end=bool(end_time),
        has_subject=bool(cleaned_fields["subject"]),
        warning_count=len(warnings),
    )

    faculty = coalesce_label(
        cleaned_fields["faculty"],
        infer_faculty_from_locator(source_root_url),
        source_label,
        fallback="Невідомий факультет",
    )
    display_stem = Path(flatten_multiline(source_asset.display_name) or source_label).stem
    program = coalesce_label(
        cleaned_fields["program"],
        record.sheet_name,
        display_stem,
        source_label,
        fallback="Невідома програма",
    )

    return NormalizedRow(
        program=program,
        faculty=faculty,
        week_type=week_type,
        day=normalize_day(cleaned_fields["day"]),
        start_time=start_time,
        end_time=end_time,
        subject=cleaned_fields["subject"],
        teacher=cleaned_fields["teacher"],
        lesson_type=cleaned_fields["lesson_type"],
        link=cleaned_fields["link"],
        room=cleaned_fields["room"],
        groups=clean_numeric_artifact(cleaned_fields["groups"]),
        course=clean_numeric_artifact(cleaned_fields["course"]),
        notes=cleaned_fields["notes"],
        week_source=week_source,
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
    return any(flatten_multiline(values.get(field)) for field in ("subject", "teacher", "lesson_type", "link", "room", "groups"))


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


def _cleanup_structured_fields(values: dict[str, str]) -> dict[str, str]:
    subject_text, subject_teachers, subject_rooms, subject_links, subject_notes = _cleanup_subject(values["subject"])
    teacher_text, teacher_rooms, teacher_links, teacher_notes = _cleanup_aux_field(values["teacher"], keep="teacher")
    room_text, room_teachers, room_links, room_notes = _cleanup_aux_field(values["room"], keep="room")
    link_text = _merge_unique([values["link"], *subject_links, *teacher_links, *room_links, *_extract_links(values["notes"])], separator=" ")
    notes_text = _merge_unique(
        [
            *_split_free_notes(values["notes"]),
            *subject_notes,
            *teacher_notes,
            *room_notes,
        ]
    )
    cleaned = {
        "program": normalize_service_tokens(values["program"]),
        "faculty": normalize_service_tokens(values["faculty"]),
        "day": values["day"],
        "subject": subject_text,
        "teacher": _merge_unique([teacher_text, *subject_teachers, *room_teachers]),
        "lesson_type": normalize_service_tokens(values["lesson_type"]),
        "link": link_text,
        "room": _merge_unique([room_text, *subject_rooms, *teacher_rooms]),
        "groups": normalize_service_tokens(values["groups"]),
        "course": normalize_service_tokens(values["course"]),
        "notes": notes_text,
    }
    return _postprocess_structured_fields(cleaned)


def _cleanup_subject(text: str) -> tuple[str, list[str], list[str], list[str], list[str]]:
    if not text:
        return "", [], [], [], []
    subject_parts: list[str] = []
    teacher_parts: list[str] = []
    room_parts: list[str] = []
    link_parts: list[str] = []
    note_parts: list[str] = []
    segments = _split_segments(text)
    index = 0
    while index < len(segments):
        segment = segments[index]
        teacher_segment, consumed = _consume_compound_teacher_segment(segments, index)
        if teacher_segment:
            teacher_parts.append(teacher_segment)
            index += consumed
            continue
        if _looks_like_room_segment(segment):
            room_parts.append(_normalize_room_segment(segment))
            index += 1
            continue
        if _looks_like_code_segment(segment):
            note_parts.append(segment)
            index += 1
            continue
        residual, teachers, rooms, links = _extract_entities(segment)
        teacher_parts.extend(teachers)
        room_parts.extend(rooms)
        link_parts.extend(links)
        if not residual:
            index += 1
            continue
        if looks_like_service_text(residual):
            note_parts.append(residual)
            index += 1
            continue
        subject_parts.append(residual)
        index += 1
    return _merge_unique(subject_parts, separator=" / "), teacher_parts, room_parts, link_parts, note_parts


def _cleanup_aux_field(text: str, *, keep: str) -> tuple[str, list[str], list[str], list[str]]:
    if not text:
        return "", [], [], []
    residual, teachers, rooms, links = _extract_entities(text)
    notes: list[str] = []
    if keep == "teacher":
        teacher_value = _merge_unique([*teachers, residual] if residual and not looks_like_room_text(residual) else teachers)
        return teacher_value, rooms, links, notes
    room_value = _merge_unique([*rooms, residual] if residual and not looks_like_teacher_text(residual) else rooms)
    return room_value, teachers, links, notes


def _extract_entities(text: str) -> tuple[str, list[str], list[str], list[str]]:
    cleaned = normalize_service_tokens(text)
    links = _extract_links(cleaned)
    if links:
        cleaned = LINK_TEXT_RE.sub(" ", cleaned)

    rooms = [normalize_service_tokens(match.group(0)) for match in ROOM_TEXT_RE.finditer(cleaned)]
    if rooms:
        cleaned = ROOM_TEXT_RE.sub(" ", cleaned)

    teachers = [normalize_service_tokens(match.group(0)) for match in TEACHER_TEXT_RE.finditer(cleaned)]
    if teachers:
        cleaned = TEACHER_TEXT_RE.sub(" ", cleaned)

    residual = normalize_service_tokens(cleaned).strip(" -/,;")
    if residual and not any(character.isalnum() for character in residual):
        residual = ""
    if looks_like_garbage_text(residual):
        residual = ""
    return residual, _unique_list(teachers), _unique_list(rooms), _unique_list(links)


def _extract_links(text: str) -> list[str]:
    return _unique_list(match.group(0) for match in LINK_TEXT_RE.finditer(normalize_service_tokens(text)))


def _split_free_notes(text: str) -> list[str]:
    if not text:
        return []
    notes = [segment for segment in _split_segments(text) if segment and not contains_link_text(segment)]
    return _unique_list(notes)


def _split_segments(text: str) -> list[str]:
    if not text:
        return []
    if "/" not in text and "|" not in text and ";" not in text:
        return [normalize_service_tokens(text)]
    segments = [normalize_service_tokens(part) for part in SEGMENT_SPLIT_RE.split(text) if normalize_service_tokens(part)]
    return segments or [normalize_service_tokens(text)]


def _merge_unique(values: list[str], *, separator: str = "; ") -> str:
    return separator.join(_unique_list(values))


def _unique_list(values: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        cleaned = normalize_service_tokens(value)
        if not cleaned or cleaned in seen:
            continue
        seen.add(cleaned)
        result.append(cleaned)
    return result


def _postprocess_structured_fields(cleaned_fields: dict[str, str]) -> dict[str, str]:
    updated = dict(cleaned_fields)
    updated["subject"], trailing_room, trailing_notes = _peel_subject_tail_metadata(updated["subject"])
    if trailing_room:
        updated["room"] = _merge_unique([updated["room"], trailing_room])
    if trailing_notes:
        updated["notes"] = _merge_unique([updated["notes"], *trailing_notes])
    if MEETING_NOTE_RE.search(updated["subject"]) or MEETING_ABBR_RE.search(updated["subject"]):
        updated["notes"] = _merge_unique([updated["notes"], updated["subject"]])
        updated["subject"] = ""
    return updated


def _consume_compound_teacher_segment(segments: list[str], index: int) -> tuple[str, int]:
    current = normalize_service_tokens(segments[index])
    next_segment = normalize_service_tokens(segments[index + 1]) if index + 1 < len(segments) else ""
    after_next = normalize_service_tokens(segments[index + 2]) if index + 2 < len(segments) else ""
    if SURNAME_ONLY_RE.fullmatch(current) and INITIALS_ONLY_RE.fullmatch(next_segment):
        return f"{current} {_normalize_initials(next_segment)}", 2
    if TITLE_ONLY_RE.fullmatch(current) and SURNAME_ONLY_RE.fullmatch(next_segment) and INITIALS_ONLY_RE.fullmatch(after_next):
        return f"{current} {next_segment} {_normalize_initials(after_next)}", 3
    return "", 0


def _normalize_initials(value: str) -> str:
    return normalize_service_tokens(value).replace(" ", "")


def _looks_like_room_segment(value: str) -> bool:
    cleaned = normalize_service_tokens(value)
    return bool(cleaned) and bool(ROOM_SEGMENT_RE.fullmatch(cleaned))


def _normalize_room_segment(value: str) -> str:
    cleaned = normalize_service_tokens(value)
    if cleaned.casefold() in {"online", "онлайн"}:
        return cleaned
    if cleaned.casefold().startswith(("ауд.", "каб.", "корп.")):
        return cleaned
    return f"ауд. {cleaned}"


def _extract_trailing_room_from_subject(subject: str) -> tuple[str, str]:
    cleaned = normalize_service_tokens(subject)
    if not cleaned:
        return "", ""
    match = TRAILING_ROOM_RE.fullmatch(cleaned)
    if not match:
        return cleaned, ""
    subject_part = normalize_service_tokens(match.group("subject")).strip(" /")
    room_part = _normalize_room_segment(match.group("room"))
    return subject_part, room_part


def _looks_like_code_segment(value: str) -> bool:
    cleaned = normalize_service_tokens(value)
    if not cleaned:
        return False
    compact = cleaned.replace(" ", "")
    if CODE_SEGMENT_RE.fullmatch(cleaned):
        return True
    if len(compact) >= 6 and compact.isdigit():
        return True
    if len(compact) >= 6 and re.fullmatch(r"[A-Za-z0-9._=+-]+", compact):
        return any(character.isalpha() for character in compact) and any(character.isdigit() for character in compact)
    return False


def _peel_subject_tail_metadata(subject: str) -> tuple[str, str, list[str]]:
    segments = _split_segments(subject)
    if not segments:
        return "", "", []
    note_parts: list[str] = []
    room_part = ""
    while segments:
        tail = normalize_service_tokens(segments[-1])
        if _looks_like_code_segment(tail):
            note_parts.insert(0, tail)
            segments.pop()
            continue
        if not room_part and _looks_like_room_segment(tail):
            room_part = _normalize_room_segment(tail)
            segments.pop()
            continue
        break
    subject_part = _merge_unique(segments, separator=" / ")
    subject_part, trailing_room = _extract_trailing_room_from_subject(subject_part)
    room_value = _merge_unique([room_part, trailing_room])
    return subject_part, room_value, note_parts


def _infer_subject_from_notes(cleaned_fields: dict[str, str]) -> tuple[dict[str, str], bool]:
    note_segments = _split_segments(cleaned_fields.get("notes", ""))
    if not note_segments:
        return cleaned_fields, False
    subject_candidates: list[str] = []
    residual_notes: list[str] = []
    for segment in note_segments:
        cleaned = normalize_service_tokens(segment)
        if not cleaned:
            continue
        if (
            contains_link_text(cleaned)
            or looks_like_teacher_text(cleaned)
            or looks_like_room_text(cleaned)
            or _looks_like_code_segment(cleaned)
            or looks_like_service_text(cleaned)
            or looks_like_garbage_text(cleaned)
        ):
            residual_notes.append(cleaned)
            continue
        if _looks_like_subject_candidate(cleaned):
            subject_candidates.append(cleaned)
            continue
        residual_notes.append(cleaned)
    if len(subject_candidates) != 1:
        return cleaned_fields, False
    updated = dict(cleaned_fields)
    updated["subject"] = subject_candidates[0]
    updated["notes"] = _merge_unique(residual_notes)
    return updated, True
