from __future__ import annotations

import re
from collections import defaultdict
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Iterable

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
    infer_asset_label_from_locator,
    infer_faculty_from_locator,
    looks_like_admin_text,
    looks_like_garbage_text,
    looks_like_room_text,
    looks_like_roomish_subject_text,
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
NON_SCHEDULE_ROW_MARKERS = (
    "деньсамостійноїроботи",
    "деньсамостiйноїроботи",
    "курсзавибором",
    "дисциплінивільноговиборустудента",
    "дисциплінивільноговибору",
    "вибірковадисципліна",
    "вибірковідисципліни",
    "іноземнамованормативнийкурс",
)
NON_SCHEDULE_FRAGMENT_MARKERS = {
    "самостійної",
    "самостiйної",
    "самостійна",
    "самостiйна",
    "роботи",
    "робота",
    "вибору",
    "вибіркова",
    "вибіркові",
    "вибірковадисципліна",
}

INFORMATIONAL_NOTE_PATTERNS = (
    "розклад занять",
    "з'явиться пізніше",
    "з`явиться пізніше",
)
ELECTIVE_SUBJECT_PATTERNS = (
    re.compile(r"(?iu)^курс\s+за\s+вибором\s*:?\s*(?P<subject>.+)$"),
    re.compile(r"(?iu)^дисципліни\s+вільного\s+вибору(?:\s+студента)?\s*:?\s*(?P<subject>.+)$"),
)
ELECTIVE_TRAILING_NOISE_RE = re.compile(r"(?iu)\s*(?:\+\s*\d+\s*пари?|;\s*\d+.*)$")
PROGRAM_LABEL_ALIASES = {
    "начитка!": "Начитка",
    "начитка!!!": "Начитка",
    "начитка": "Начитка",
    "начітка": "Начитка",
    "постійний!!!": "Постійний",
    "постійний": "Постійний",
    "постіиний": "Постійний",
    "постіиниии": "Постійний",
    "постійне": "Постійне",
    "постійний розклад": "Постійний розклад",
    "постiйний розклад": "Постійний розклад",
}

FILL_DOWN_FIELDS = ("week_type", "day", "start_time", "end_time")
DEFAULT_SLOT_DURATION_MINUTES = 80
SEGMENT_SPLIT_RE = re.compile(r"\s*(?:\||;|/)\s*")
SURNAME_ONLY_RE = re.compile(r"(?iu)^[А-ЯІЇЄҐ][а-яіїєґ'’ʼ-]+$")
INITIALS_ONLY_RE = re.compile(r"(?iu)^[А-ЯІЇЄҐ]\.\s*[А-ЯІЇЄҐ]\.?$")
TITLE_ONLY_RE = re.compile(r"(?iu)^(?:проф|доц|ас|асист|викл|ст\.?\s*викл|phd|к\.\s*[юф]\.\s*н|д\.\s*[юф]\.\s*н)\.?$")
COMPACT_SURNAME_INITIALS_RE = re.compile(r"(?iu)^([А-ЯІЇЄҐ][а-яіїєґ'’ʼ\-]+)([А-ЯІЇЄҐ]\.\s*[А-ЯІЇЄҐ]\.?)$")
PERSON_NAME_WITH_INITIALS_RE = re.compile(r"(?iu)^[А-ЯІЇЄҐ][а-яіїєґ'’ʼ\-]+\s+[А-ЯІЇЄҐ]\.\s*[А-ЯІЇЄҐ]\.?$")
ROOM_SEGMENT_RE = re.compile(r"(?iu)^(?:\d{3,4}[А-ЯІЇЄҐA-Z]?(?:/\d+)?|[А-ЯІЇЄҐA-Z]-?\d{2,4}|online|онлайн)$")
CODE_SEGMENT_RE = re.compile(r"(?iu)^(?:meeting id|passcode|код доступу|ідентифікатор конференції|идентификатор конференции|t=\d+)\b|^[A-Za-z0-9+/=_-]{10,}$")
TRAILING_ROOM_RE = re.compile(
    r"(?iu)^(?P<subject>.+?)(?:\s*/\s*|\s+)(?P<room>(?:\d{3,4}[А-ЯІЇЄҐA-Z]?|[А-ЯІЇЄҐA-Z]-?\d{2,4}|(?:хімічний|географічний)\s+ф-?т\s+\d{2,4}))$"
)
PROGRAM_FRAGMENT_RE = re.compile(r"(?iu)\s+(?P<trailing>(?:(?:0\d{2}|1\d{2}|E\d)\s+.+))$")
MEETING_NOTE_RE = re.compile(r"(?iu)\b(?:meeting id|passcode|код доступу|ідентифікатор конференції|идентификатор конференции)\b")
MEETING_ABBR_RE = re.compile(r"(?iu)^(?:ік|кд|id|pwd)\s*:")
LESSON_TYPE_PATTERNS = (
    (re.compile(r"(?iu)\b(?:л|л\.|лек|лекція)\b"), "лекція"),
    (re.compile(r"(?iu)\b(?:пр|пр\.|практ|практична)\b"), "практична"),
    (re.compile(r"(?iu)\b(?:лаб|лаб\.|лабораторна)\b"), "лабораторна"),
    (re.compile(r"(?iu)\b(?:сем|сем\.)\b"), "семінар"),
)
ABBREVIATED_SUBJECT_RE = re.compile(r"(?iu)^(?:ст|ас|доц|проф|викл)\.?$")
LEADING_TEACHER_SEGMENT_RE = re.compile(
    "(?iu)^(?:(?:\\u043f\\u0440\\u043e\\u0444|\\u0434\\u043e\\u0446|\\u0430\\u0441|\\u0432\\u0438\\u043a\\u043b)\\.?\\s+)?"
    "[\\u0410-\\u042f\\u0406\\u0407\\u0404\\u0490][\\u0430-\\u044f\\u0456\\u0457\\u0454\\u0491'’ʼ\\-]+"
    "\\s+[\\u0410-\\u042f\\u0406\\u0407\\u0404\\u0490]\\.\\s*[\\u0410-\\u042f\\u0406\\u0407\\u0404\\u0490]\\.?$"
)
SPLIT_TEACHER_PREFIX_RE = re.compile(r"(?iu)^[А-ЯІЇЄҐ][а-яіїєґ]{1,5}[\'’ʼ]$")
LOWERCASE_TEACHER_REMAINDER_RE = re.compile(r"(?iu)^[а-яіїєґ'’ʼ-]{2,24}\s+[А-ЯІЇЄҐ]\.\s*[А-ЯІЇЄҐ]\.?$")


CYRILLIC_TEXT_RE = re.compile(r"[А-ЯІЇЄҐа-яіїєґ]")
SUBJECT_FRAGMENT_DATE_RE = re.compile(r"(?iu)^\d{2}\.\d{2}\.\d{4}(?:\s+\d{1,2}[:.]\d{2})?$")
SUBJECT_FRAGMENT_DATE_LIST_RE = re.compile(r"(?iu)^\[\d{2}\.\d{2}(?:,\s*\d{2}\.\d{2})+\]$")
SUBJECT_FRAGMENT_LINK_RE = re.compile(
    r"(?i)(?:\?pwd=|[?&][a-z]{1,5}=|pwd=|zoom|teams|meet|us\d{2}web|knu-ua|meeting\s*id|passcode|\.com\b|\.us\b)"
)


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
    rows: list[NormalizedRow] = []
    for sheet in document.sheets:
        for record in sheet.records:
            row = normalize_record(record, document=document)
            if _should_drop_non_schedule_row(row):
                continue
            rows.append(row)
    return _merge_metadata_only_rows(rows)


def normalize_record(record: RawRecord, *, document: ParsedDocument) -> NormalizedRow:
    values = defaultdict(str, {key: normalize_service_tokens(value) for key, value in record.values.items()})
    source_asset = document.asset.asset
    source_name = source_asset.source_name
    source_root_url = source_asset.source_root_url or source_asset.source_url_or_path or source_asset.locator
    source_label = humanize_source_name(source_name)
    autofix_actions: list[str] = []

    subject_inferred = False
    if not values["subject"] and values["lesson_type"].casefold() in SUBJECT_FALLBACK_LESSON_TYPES:
        values["subject"] = values["lesson_type"]
        subject_inferred = True
        record.warnings.append("subject_inferred_from_lesson_type")
        autofix_actions.append("subject_from_lesson_type")
    if not values["subject"] and any(pattern in values["notes"].casefold() for pattern in SUBJECT_FALLBACK_NOTES_PATTERNS):
        values["subject"] = values["notes"]
        subject_inferred = True
        record.warnings.append("subject_inferred_from_notes")
        autofix_actions.append("subject_from_notes")
    if not values["subject"] and _looks_like_non_class_marker(values["notes"]):
        values["subject"] = _normalize_non_class_subject(values["notes"])
        subject_inferred = True
        record.warnings.append("subject_inferred_from_non_class_note")
        autofix_actions.append("subject_from_non_class_note")
    if (
        not values["subject"]
        and _looks_like_subject_candidate(values["groups"])
        and not any(values[field] for field in ("teacher", "lesson_type", "room"))
    ):
        values["subject"] = values["groups"]
        subject_inferred = True
        record.warnings.append("subject_inferred_from_groups")
        autofix_actions.append("subject_from_groups")

    cleaned_fields = _cleanup_structured_fields(values)
    if not cleaned_fields["subject"]:
        cleaned_fields, inferred_from_notes = _infer_subject_from_notes(cleaned_fields)
        if inferred_from_notes:
            subject_inferred = True
            record.warnings.append("subject_inferred_from_notes")
            autofix_actions.append("subject_from_notes")
    autofix_actions.extend(_detect_cleanup_autofixes(values, cleaned_fields))
    week_type, week_source = normalize_week_type_meta(
        values["week_type"],
        cleaned_fields["subject"],
        cleaned_fields["notes"],
        record.raw_excerpt,
    )
    if week_source == "default":
        autofix_actions.append("week_type_defaulted")
    elif week_source == "inferred":
        autofix_actions.append("week_type_inferred")

    start_time = parse_time_value(values["start_time"])
    end_time = parse_time_value(values["end_time"])
    parsed_start_time = start_time
    parsed_end_time = end_time
    if (not start_time or not end_time) and values["raw_time"]:
        start_time, end_time = parse_time_range(values["raw_time"])
    start_time, end_time = _infer_missing_time_bounds(start_time, end_time, cleaned_fields)
    start_time, end_time, repaired_time = _repair_implausible_time_bounds(start_time, end_time, cleaned_fields)
    if not parsed_start_time and start_time:
        autofix_actions.append("start_time_inferred")
    if not parsed_end_time and end_time:
        autofix_actions.append("end_time_inferred")
    if repaired_time:
        autofix_actions.append(repaired_time)

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
    note_program_hint = _extract_program_hint(cleaned_fields["notes"])
    asset_label = infer_asset_label_from_locator(source_asset.locator)
    if note_program_hint and not cleaned_fields["program"]:
        autofix_actions.append("program_from_notes")
    program = coalesce_label(
        cleaned_fields["program"],
        note_program_hint,
        record.sheet_name,
        display_stem,
        asset_label,
        source_label,
        fallback="Невідома програма",
    )
    normalized_program = _normalize_program_label(program)
    if normalized_program != program and normalized_program:
        autofix_actions.append("program_label_normalized")
    program = normalized_program

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
        autofix_actions=list(dict.fromkeys(autofix_actions)),
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
    if _looks_like_non_schedule_service_payload(values):
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
    compact = re.sub(r"[^\w]+", "", text, flags=re.UNICODE)
    if ABBREVIATED_SUBJECT_RE.fullmatch(text):
        return False
    if looks_like_roomish_subject_text(text):
        return False
    if _looks_like_code_segment(text):
        return False
    if looks_like_service_text(text) or looks_like_garbage_text(text):
        return False
    if " " not in text and len(compact) < 4 and "," not in text:
        return False
    return (any(ch.isalpha() for ch in text) and not text.isupper()) or ("," in text)


def _looks_like_non_class_marker(value: Any) -> bool:
    text = flatten_multiline(value).casefold()
    return bool(text) and any(pattern in text for pattern in NON_CLASS_MARKER_PATTERNS)


def _compact_marker_text(value: Any) -> str:
    text = flatten_multiline(value).casefold()
    return re.sub(r"[\W_]+", "", text, flags=re.UNICODE)


def _looks_like_non_schedule_service_text(value: Any) -> bool:
    compact = _compact_marker_text(value)
    return bool(compact) and any(marker in compact for marker in NON_SCHEDULE_ROW_MARKERS)


def _looks_like_non_schedule_fragment(value: Any) -> bool:
    compact = _compact_marker_text(value)
    return bool(compact) and compact in NON_SCHEDULE_FRAGMENT_MARKERS


def _looks_like_non_schedule_service_payload(values: dict[str, Any]) -> bool:
    marker_text = " ".join(
        flatten_multiline(values.get(field))
        for field in ("subject", "notes", "lesson_type")
        if flatten_multiline(values.get(field))
    )
    if not marker_text:
        return False
    if any(flatten_multiline(values.get(field)) for field in ("teacher", "room", "link")):
        return False
    return _looks_like_non_schedule_service_text(marker_text) or _looks_like_non_schedule_fragment(values.get("subject"))


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


def _should_drop_non_schedule_row(row: NormalizedRow) -> bool:
    if not any(getattr(row, field).strip() for field in ("subject", "teacher", "room", "link", "notes", "lesson_type", "groups", "course")):
        return True
    if any(getattr(row, field).strip() for field in ("teacher", "room", "link")):
        return False
    marker_text = " ".join(part for part in (row.subject, row.notes, row.lesson_type, row.raw_excerpt) if part.strip())
    if _looks_like_non_schedule_service_text(marker_text):
        return True
    return _looks_like_non_schedule_fragment(row.subject)


def _merge_metadata_only_rows(rows: list[NormalizedRow]) -> list[NormalizedRow]:
    if not rows:
        return rows
    survivors: list[NormalizedRow] = []
    consumed_ids: set[int] = set()
    for row in rows:
        row_id = id(row)
        if row_id in consumed_ids:
            continue
        if not _is_metadata_only_row(row):
            survivors.append(row)
            continue
        candidates = [candidate for candidate in rows if id(candidate) not in consumed_ids and _can_absorb_metadata_row(candidate, row)]
        if len(candidates) != 1:
            if _is_orphan_metadata_only_row(row):
                consumed_ids.add(row_id)
                continue
            survivors.append(row)
            continue
        target = candidates[0]
        target.teacher = _merge_unique([target.teacher, row.teacher])
        target.room = _merge_unique([target.room, row.room])
        target.link = _merge_unique([target.link, row.link], separator=" ")
        target.notes = _merge_unique([target.notes, row.notes])
        target.autofix_actions = list(dict.fromkeys([*target.autofix_actions, "slot_metadata_merged"]))
        consumed_ids.add(row_id)
    return survivors


def _is_metadata_only_row(row: NormalizedRow) -> bool:
    return not row.subject.strip() and any(value.strip() for value in (row.teacher, row.room, row.link, row.notes))


def _is_orphan_metadata_only_row(row: NormalizedRow) -> bool:
    return _is_metadata_only_row(row) and not row.groups.strip() and not row.course.strip()


def _can_absorb_metadata_row(candidate: NormalizedRow, metadata_row: NormalizedRow) -> bool:
    if candidate is metadata_row or not candidate.subject.strip():
        return False
    if candidate.sheet_name != metadata_row.sheet_name:
        return False
    if candidate.day != metadata_row.day or candidate.start_time != metadata_row.start_time or candidate.end_time != metadata_row.end_time:
        return False
    return _slot_context_matches(candidate.course, metadata_row.course) and _slot_context_matches(candidate.groups, metadata_row.groups)


def _slot_context_matches(left: str, right: str) -> bool:
    left_clean = _normalize_slot_context(left)
    right_clean = _normalize_slot_context(right)
    if not left_clean or not right_clean:
        return True
    return left_clean == right_clean or left_clean in right_clean or right_clean in left_clean


def _normalize_slot_context(value: str) -> str:
    cleaned = normalize_service_tokens(value).casefold()
    return re.sub(r"[\W_]+", "", cleaned, flags=re.UNICODE)


def _extract_program_hint(notes: str) -> str:
    segments = _split_segments(notes)
    for index, segment in enumerate(segments):
        cleaned = normalize_service_tokens(segment)
        if not cleaned:
            continue
        if (
            contains_link_text(cleaned)
            or looks_like_teacher_text(cleaned)
            or looks_like_room_text(cleaned)
            or looks_like_service_text(cleaned)
            or looks_like_garbage_text(cleaned)
        ):
            continue
        if re.fullmatch(r"(?iu)(?:0\d{2}|1\d{2}|E\d)\s+.+", cleaned):
            if len(re.findall(r"(?iu)\b(?:0\d{2}|1\d{2}|E\d)\b", cleaned)) > 1:
                continue
            if cleaned.casefold().endswith((" та", " і", " й", " з", " до", " по")):
                continuation = _find_program_continuation(segments, index)
                if continuation and _looks_like_program_continuation(continuation):
                    cleaned = f"{cleaned} {continuation}"
            if cleaned.casefold().endswith((" та", " і", " й", " з", " до", " по")):
                continue
            return cleaned
    return ""


def _normalize_program_label(value: str) -> str:
    cleaned = normalize_service_tokens(value).replace("_", " ").replace("-", " ")
    cleaned = re.sub(r"(?<=[A-Za-z])(?=[А-ЯІЇЄҐа-яіїєґ])", " ", cleaned)
    cleaned = re.sub(r"(?<=[А-ЯІЇЄҐа-яіїєґ])(?=[A-Za-z])", " ", cleaned)
    cleaned = normalize_service_tokens(cleaned).strip(" !.,;:-")
    if not cleaned:
        return ""
    return PROGRAM_LABEL_ALIASES.get(cleaned.casefold(), cleaned)


def _looks_like_program_continuation(value: str) -> bool:
    cleaned = normalize_service_tokens(value)
    if not cleaned:
        return False
    if contains_link_text(cleaned) or looks_like_teacher_text(cleaned) or looks_like_room_text(cleaned):
        return False
    if looks_like_service_text(cleaned) or looks_like_garbage_text(cleaned):
        return False
    return bool(re.fullmatch(r"(?iu)[А-ЯІЇЄҐа-яіїєґ][А-ЯІЇЄҐа-яіїєґ'’\-\s]{2,}", cleaned))


def _find_program_continuation(segments: list[str], index: int) -> str:
    forward = _scan_program_continuation(segments, range(index + 1, len(segments)))
    if forward:
        return forward
    backward = _scan_program_continuation(segments, range(index - 1, -1, -1))
    if backward:
        return backward
    return ""


def _scan_program_continuation(segments: list[str], indexes: Iterable[int]) -> str:
    for candidate_index in indexes:
        candidate = normalize_service_tokens(segments[candidate_index])
        if not candidate:
            continue
        if (
            contains_link_text(candidate)
            or looks_like_teacher_text(candidate)
            or looks_like_room_text(candidate)
            or looks_like_service_text(candidate)
            or looks_like_garbage_text(candidate)
        ):
            continue
        if not _looks_like_program_continuation(candidate):
            continue
        return candidate
    return ""


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


def _repair_implausible_time_bounds(start_time: str, end_time: str, values: dict[str, Any]) -> tuple[str, str, str]:
    if not start_time or not end_time:
        return start_time, end_time, ""
    if not _has_class_payload(values) or _looks_like_non_class_marker(values.get("notes")):
        return start_time, end_time, ""
    if _looks_like_non_schedule_service_payload(values):
        return start_time, end_time, ""
    start_minutes = _time_to_minutes(start_time)
    end_minutes = _time_to_minutes(end_time)
    if start_minutes is None or end_minutes is None:
        return start_time, end_time, ""
    duration = end_minutes - start_minutes
    if duration < 0 or duration <= 20:
        return start_time, _shift_time(start_time, DEFAULT_SLOT_DURATION_MINUTES), "end_time_repaired"
    return start_time, end_time, ""


def _shift_time(time_value: str, minutes: int) -> str:
    parsed = datetime.strptime(time_value, "%H:%M")
    shifted = parsed + timedelta(minutes=minutes)
    return shifted.strftime("%H:%M")


def _time_to_minutes(time_value: str) -> int | None:
    try:
        hours, minutes = (int(part) for part in time_value.split(":", 1))
    except ValueError:
        return None
    return hours * 60 + minutes


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
    primary_parts: list[str] = []
    teacher_parts: list[str] = []
    room_parts: list[str] = []
    link_parts: list[str] = []
    note_parts: list[str] = []
    segments = _split_segments(text)
    index = 0
    while index < len(segments):
        segment = segments[index]
        teacher_segment, consumed = _consume_compound_teacher_segment(segments, index)
        if keep == "teacher" and teacher_segment:
            primary_parts.append(teacher_segment)
            index += consumed
            continue
        if _looks_like_room_segment(segment) or looks_like_roomish_subject_text(segment):
            room_parts.append(_normalize_roomish_segment(segment))
            index += 1
            continue
        if contains_link_text(segment):
            link_parts.extend(_extract_links(segment))
            residual_link_text = normalize_service_tokens(LINK_TEXT_RE.sub(" ", segment)).strip(" ,;/")
            if residual_link_text:
                note_parts.append(residual_link_text)
            index += 1
            continue
        if _looks_like_code_segment(segment):
            note_parts.append(segment)
            index += 1
            continue
        residual, teachers, rooms, links = _extract_entities(segment)
        room_parts.extend(rooms)
        link_parts.extend(links)
        if keep == "teacher":
            primary_parts.extend(teachers)
            if residual:
                if looks_like_teacher_text(residual) or SURNAME_ONLY_RE.fullmatch(residual) or INITIALS_ONLY_RE.fullmatch(residual):
                    primary_parts.append(residual)
                elif _looks_like_room_segment(residual) or looks_like_roomish_subject_text(residual):
                    room_parts.append(_normalize_roomish_segment(residual))
                else:
                    note_parts.append(residual)
        else:
            primary_parts.extend(rooms)
            teacher_parts.extend(teachers)
            if residual:
                if _looks_like_room_segment(residual) or looks_like_roomish_subject_text(residual) or looks_like_room_text(residual):
                    primary_parts.append(_normalize_roomish_segment(residual))
                else:
                    note_parts.append(residual)
        index += 1
    if keep == "teacher":
        return _merge_unique(primary_parts), room_parts, link_parts, note_parts
    room_value = _merge_unique(primary_parts or room_parts)
    return room_value, teacher_parts, link_parts, note_parts


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


def _unique_list(values: Iterable[str]) -> list[str]:
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
    updated["subject"], updated["teacher"] = _repair_split_teacher_prefix(updated["subject"], updated["teacher"])
    updated["teacher"] = _normalize_teacher_field(updated["teacher"])
    updated["subject"], leading_teacher = _extract_leading_teacher_from_subject(updated["subject"])
    if leading_teacher:
        updated["teacher"] = _merge_unique([updated["teacher"], leading_teacher])
    updated["subject"], trailing_room, trailing_notes = _peel_subject_tail_metadata(updated["subject"])
    if trailing_room:
        updated["room"] = _merge_unique([updated["room"], trailing_room])
    if trailing_notes:
        updated["notes"] = _merge_unique([updated["notes"], *trailing_notes])
    updated["subject"], trailing_program_notes = _peel_subject_program_metadata(updated["subject"])
    if trailing_program_notes:
        updated["notes"] = _merge_unique([updated["notes"], *trailing_program_notes])
    updated["subject"], subject_noise_notes = _peel_subject_noise_segments(updated["subject"])
    if subject_noise_notes:
        updated["notes"] = _merge_unique([updated["notes"], *subject_noise_notes])
    updated["subject"] = _collapse_wrapped_subject(updated["subject"])
    if looks_like_roomish_subject_text(updated["subject"]):
        updated["subject"], room_fragment, lesson_fragment = _extract_roomish_subject_metadata(updated["subject"])
        if room_fragment:
            updated["room"] = _merge_unique([updated["room"], room_fragment])
        if lesson_fragment and not updated["lesson_type"]:
            updated["lesson_type"] = lesson_fragment
    if updated["subject"] and looks_like_admin_text(updated["subject"]):
        updated["notes"] = _merge_unique([updated["notes"], updated["subject"]])
        updated["subject"] = ""
    if MEETING_NOTE_RE.search(updated["subject"]) or MEETING_ABBR_RE.search(updated["subject"]):
        updated["notes"] = _merge_unique([updated["notes"], updated["subject"]])
        updated["subject"] = ""
    if ABBREVIATED_SUBJECT_RE.fullmatch(updated["subject"]):
        updated["notes"] = _merge_unique([updated["notes"], updated["subject"]])
        updated["subject"] = ""
    return updated


def _repair_split_teacher_prefix(subject: str, teacher: str) -> tuple[str, str]:
    cleaned_subject = normalize_service_tokens(subject)
    cleaned_teacher = normalize_service_tokens(teacher)
    if not cleaned_subject or not cleaned_teacher:
        return cleaned_subject, cleaned_teacher
    subject_segments = _split_segments(cleaned_subject)
    teacher_segments = _split_segments(cleaned_teacher)
    if len(subject_segments) < 2 or not teacher_segments:
        return cleaned_subject, cleaned_teacher
    teacher_head = normalize_service_tokens(teacher_segments[0]).strip(" ,;")
    subject_head = normalize_service_tokens(subject_segments[0]).strip(" ,;")
    if not SPLIT_TEACHER_PREFIX_RE.fullmatch(subject_head):
        return cleaned_subject, cleaned_teacher
    if not LOWERCASE_TEACHER_REMAINDER_RE.fullmatch(teacher_head):
        return cleaned_subject, cleaned_teacher
    repaired_subject = _merge_unique(
        [normalize_service_tokens(segment) for segment in subject_segments[1:] if normalize_service_tokens(segment)],
        separator=" / ",
    )
    if not repaired_subject:
        return cleaned_subject, cleaned_teacher
    repaired_teacher = _merge_unique([f"{subject_head}{teacher_head}", *teacher_segments[1:]])
    return repaired_subject, repaired_teacher


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


def _normalize_teacher_field(text: str) -> str:
    segments = _split_segments(text)
    if not segments:
        return ""
    normalized_parts: list[str] = []
    pending_title = ""
    for raw_segment in segments:
        cleaned = _normalize_teacher_segment(raw_segment)
        if not cleaned:
            continue
        if TITLE_ONLY_RE.fullmatch(cleaned):
            pending_title = cleaned.rstrip(".")
            continue
        if pending_title and (_looks_like_teacher_name(cleaned) or looks_like_teacher_text(cleaned)):
            normalized_parts.append(f"{pending_title}. {cleaned}")
            pending_title = ""
            continue
        normalized_parts.append(cleaned)
        pending_title = ""
    return _merge_unique(normalized_parts)


def _normalize_teacher_segment(value: str) -> str:
    cleaned = normalize_service_tokens(value).strip(" ,;")
    if not cleaned:
        return ""
    compact_name_match = COMPACT_SURNAME_INITIALS_RE.fullmatch(cleaned)
    if compact_name_match:
        cleaned = f"{compact_name_match.group(1)} {compact_name_match.group(2)}"
    return normalize_service_tokens(cleaned)


def _looks_like_teacher_name(value: str) -> bool:
    cleaned = _normalize_teacher_segment(value)
    return bool(cleaned) and bool(PERSON_NAME_WITH_INITIALS_RE.fullmatch(cleaned))


def _looks_like_room_segment(value: str) -> bool:
    cleaned = normalize_service_tokens(value)
    return bool(cleaned) and bool(ROOM_SEGMENT_RE.fullmatch(cleaned))


def _normalize_room_segment(value: str) -> str:
    cleaned = normalize_service_tokens(value)
    if cleaned.casefold() in {"online", "онлайн"}:
        return cleaned
    trailing_aud_match = re.fullmatch(r"(?iu)(\d{1,4}[A-Za-zА-ЯІЇЄҐ]?)\s*ауд\.?", cleaned)
    if trailing_aud_match:
        return f"ауд. {trailing_aud_match.group(1)}"
    trailing_cab_match = re.fullmatch(r"(?iu)(\d{1,4}[A-Za-zА-ЯІЇЄҐ]?)\s*каб\.?", cleaned)
    if trailing_cab_match:
        return f"каб. {trailing_cab_match.group(1)}"
    if cleaned.casefold().startswith(("ауд.", "каб.", "корп.")):
        return cleaned
    return f"ауд. {cleaned}"


def _normalize_roomish_segment(value: str) -> str:
    cleaned = normalize_service_tokens(value)
    if _looks_like_room_segment(cleaned):
        return _normalize_room_segment(cleaned)
    _, room_fragment, _ = _extract_roomish_subject_metadata(cleaned)
    return room_fragment or cleaned


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
    if re.fullmatch(r"(?i)[a-z]{3,4}(?:-[a-z]{3,4}){2,3}", compact):
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


def _peel_subject_program_metadata(subject: str) -> tuple[str, list[str]]:
    cleaned = normalize_service_tokens(subject)
    if not cleaned or len(cleaned) < 10:
        return cleaned, []
    match = PROGRAM_FRAGMENT_RE.search(cleaned)
    if not match:
        return cleaned, []
    subject_part = normalize_service_tokens(cleaned[: match.start("trailing")]).strip(" /,;")
    trailing = normalize_service_tokens(match.group("trailing"))
    if len(subject_part) < 6:
        return cleaned, []
    if not re.search(r"(?iu)\b(?:0\d{2}|1\d{2}|E\d)\b", trailing):
        return cleaned, []
    return subject_part, [trailing]


def _peel_subject_noise_segments(subject: str) -> tuple[str, list[str]]:
    cleaned = normalize_service_tokens(subject)
    if not cleaned:
        return "", []
    segments = _split_segments(cleaned)
    if not segments:
        return "", []

    subject_segments: list[str] = []
    note_segments: list[str] = []
    for segment in segments:
        normalized = normalize_service_tokens(segment)
        if not normalized:
            continue
        if _looks_like_subject_noise_segment(normalized):
            note_segments.append(normalized)
            continue
        subject_segments.append(normalized)
    if not subject_segments:
        return "", note_segments
    return _merge_unique(subject_segments, separator=" / "), note_segments


def _extract_leading_teacher_from_subject(subject: str) -> tuple[str, str]:
    cleaned = normalize_service_tokens(subject)
    segments = _split_segments(cleaned)
    if len(segments) < 2:
        return cleaned, ""
    first = normalize_service_tokens(segments[0]).strip(" ,;")
    if not first or not LEADING_TEACHER_SEGMENT_RE.fullmatch(first):
        return cleaned, ""
    remainder_segments = [normalize_service_tokens(segment) for segment in segments[1:] if normalize_service_tokens(segment)]
    remainder = _merge_unique(remainder_segments, separator=" / ")
    if not remainder or looks_like_room_text(remainder) or contains_link_text(remainder):
        return cleaned, ""
    return remainder, first


def _looks_like_subject_noise_segment(value: str) -> bool:
    cleaned = normalize_service_tokens(value)
    if not cleaned:
        return False
    if SUBJECT_FRAGMENT_DATE_RE.fullmatch(cleaned):
        return True
    if SUBJECT_FRAGMENT_DATE_LIST_RE.fullmatch(cleaned):
        return True
    if contains_link_text(cleaned) or MEETING_NOTE_RE.search(cleaned) or MEETING_ABBR_RE.search(cleaned):
        return True
    has_cyrillic = bool(CYRILLIC_TEXT_RE.search(cleaned))
    if not has_cyrillic and SUBJECT_FRAGMENT_LINK_RE.search(cleaned):
        return True
    if not has_cyrillic and cleaned.casefold() in {"j", "com"}:
        return True
    return False


def _collapse_wrapped_subject(subject: str) -> str:
    cleaned = normalize_service_tokens(subject)
    if cleaned.count(" / ") < 2:
        return cleaned
    if (
        contains_link_text(cleaned)
        or looks_like_teacher_text(cleaned)
        or looks_like_room_text(cleaned)
        or looks_like_roomish_subject_text(cleaned)
        or _looks_like_code_segment(cleaned)
        or re.search(r"\d{2}\.\d{2}\.\d{4}", cleaned)
    ):
        return cleaned
    segments = [normalize_service_tokens(segment) for segment in cleaned.split(" / ") if normalize_service_tokens(segment)]
    if len(segments) < 3:
        return cleaned
    if any(not any(character.isalpha() for character in segment) for segment in segments):
        return cleaned
    continuation_segments = sum(
        1 for segment in segments[1:] if segment.startswith("(") or segment[0].islower()
    )
    if continuation_segments < len(segments) - 1:
        return cleaned
    return normalize_service_tokens(" ".join(segments))


def _extract_roomish_subject_metadata(subject: str) -> tuple[str, str, str]:
    cleaned = normalize_service_tokens(subject)
    if not cleaned:
        return "", "", ""
    lesson_type = ""
    residual = cleaned
    for pattern, canonical in LESSON_TYPE_PATTERNS:
        if pattern.search(residual):
            lesson_type = canonical
            residual = pattern.sub(" ", residual)
            break
    residual = normalize_service_tokens(residual).strip(" ,;/")
    if not residual:
        return "", "", lesson_type
    return "", _normalize_room_segment(residual), lesson_type


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
        elective_subject = _extract_elective_subject_candidate(cleaned)
        if elective_subject:
            subject_candidates.append(elective_subject)
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


def _extract_elective_subject_candidate(value: str) -> str:
    cleaned = normalize_service_tokens(value)
    if not cleaned:
        return ""
    for pattern in ELECTIVE_SUBJECT_PATTERNS:
        match = pattern.fullmatch(cleaned)
        if not match:
            continue
        candidate = normalize_service_tokens(match.group("subject"))
        candidate = ELECTIVE_TRAILING_NOISE_RE.sub("", candidate).strip(" :;,-+")
        if not candidate or candidate.isdigit():
            return ""
        if looks_like_service_text(candidate) or looks_like_garbage_text(candidate):
            return ""
        if not _looks_like_subject_candidate(candidate):
            return ""
        return candidate
    return ""


def _detect_cleanup_autofixes(original_fields: dict[str, str], cleaned_fields: dict[str, str]) -> list[str]:
    actions: list[str] = []
    if original_fields["subject"] and not original_fields["teacher"] and cleaned_fields["teacher"]:
        actions.append("teacher_from_subject")
    if original_fields["subject"] and not original_fields["room"] and cleaned_fields["room"]:
        actions.append("room_from_subject")
    if original_fields["subject"] and not original_fields["link"] and cleaned_fields["link"]:
        actions.append("link_from_subject")
    if original_fields["subject"] and cleaned_fields["subject"] and cleaned_fields["subject"] != original_fields["subject"]:
        actions.append("subject_cleaned")
    if original_fields["subject"] and not cleaned_fields["subject"] and cleaned_fields["notes"]:
        actions.append("subject_moved_to_notes")
    return actions
