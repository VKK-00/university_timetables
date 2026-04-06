from __future__ import annotations

import io
import re
from collections import defaultdict

import pdfplumber
import pypdfium2
import pytesseract

from ..models import FetchedAsset, ParsedDocument, ParsedSheet, RawRecord
from ..ocr import configure_tesseract, get_tessdata_dir
from ..utils import DAY_NAMES, excerpt_from_values, flatten_multiline, infer_faculty_from_locator, normalize_day, parse_time_range


LINK_RE = re.compile(r"(?i)(https?://|zoom|teams|meet|id:\s*\d|pin:|код[:\s])")
ROOM_RE = re.compile(r"(?i)\b(?:ауд\.?|аудиторія|корпус|корп\.|каб\.?|online|онлайн)\b(?:\s*[\w./-]+)?")
TEACHER_RE = re.compile(
    r"(?i)(?:проф\.?|доц\.?|ас\.?|ст\.?\s*викл\.?|викл\.?|phd\.?|д\.\s*ю\.\s*н\.?|к\.\s*ю\.\s*н\.?|к\.\s*філос\.\s*н\.?)|[А-ЯІЇЄҐ][а-яіїєґ'-]+\s+[А-ЯІЇЄҐ]\.\s*[А-ЯІЇЄҐ]\."
)
GROUP_RE = re.compile(r"(?i)\b\d+\s*група\b")
COURSE_RE = re.compile(r"(?i)\b(\d+)\s*(?:курс|бакалавр|магістр|р\.?н\.?)\b")
CODE_RE = re.compile(r"(?i)^[A-ZА-ЯІЇЄҐ]\d+(?:\.\d+)?\b|^\d{3}\s+[А-Яа-яіїєґA-Za-z]")
PDF_TIME_RANGE_RE = re.compile(
    "(?P<start>(?:\\d{1,2}[:.]\\d{2}|\\d{3,4}|\\d(?:\\s+\\d){2,3}))\\s*(?:-|\\u2013|\\u2014)\\s*(?P<end>(?:\\d{1,2}[:.]\\d{2}|\\d{3,4}|\\d(?:\\s+\\d){2,3}))"
)


def parse_pdf_asset(fetched_asset: FetchedAsset, *, ocr_enabled: bool) -> ParsedDocument:
    faculty = infer_faculty_from_locator(fetched_asset.asset.source_root_url or fetched_asset.asset.locator)
    program = fetched_asset.asset.display_name
    warnings: list[str] = []

    table_records = _extract_pdf_table_records(fetched_asset.content, faculty=faculty, program=program)
    if table_records:
        return ParsedDocument(
            asset=fetched_asset,
            sheets=[ParsedSheet(sheet_name="pdf-table", program=program, faculty=faculty, records=table_records)],
            warnings=warnings,
        )

    text_lines = _extract_pdf_text_lines(fetched_asset.content)
    text_records = _filter_valid_pdf_records(_parse_pdf_records(text_lines, sheet_name="pdf", faculty=faculty, program=program))
    if text_records:
        return ParsedDocument(
            asset=fetched_asset,
            sheets=[ParsedSheet(sheet_name="pdf", program=program, faculty=faculty, records=text_records)],
            warnings=warnings,
        )
    if text_lines:
        warnings.append("Embedded PDF text did not yield complete day/time/subject rows.")
    else:
        warnings.append("No embedded text found in PDF.")

    if not ocr_enabled:
        return ParsedDocument(asset=fetched_asset, sheets=[], warnings=warnings)

    lines, ocr_warnings = _extract_ocr_lines(fetched_asset.content)
    warnings.extend(ocr_warnings)
    ocr_records = _filter_valid_pdf_records(_parse_pdf_records(lines, sheet_name="pdf-ocr", faculty=faculty, program=program))
    if ocr_records:
        return ParsedDocument(
            asset=fetched_asset,
            sheets=[ParsedSheet(sheet_name="pdf-ocr", program=program, faculty=faculty, records=ocr_records)],
            warnings=warnings,
        )
    warnings.append("PDF OCR did not yield complete day/time/subject rows.")
    return ParsedDocument(asset=fetched_asset, sheets=[], warnings=warnings)


def _extract_pdf_table_records(content: bytes, *, faculty: str, program: str) -> list[RawRecord]:
    records: list[RawRecord] = []
    with pdfplumber.open(io.BytesIO(content)) as pdf:
        for page_index, page in enumerate(pdf.pages, start=1):
            for table_index, table in enumerate(page.extract_tables(), start=1):
                if not table:
                    continue
                sheet_name = f"pdf-table-p{page_index}-t{table_index}"
                parsed = _parse_pdf_table(table, sheet_name=sheet_name, faculty=faculty, program=program)
                records.extend(parsed)
    return _filter_valid_pdf_records(records)


def _parse_pdf_table(
    table: list[list[str | None]],
    *,
    sheet_name: str,
    faculty: str,
    program: str,
) -> list[RawRecord]:
    header_index, day_columns = _find_rowwise_day_columns(table)
    if header_index >= 0 and len(day_columns) >= 2:
        return _parse_rowwise_schedule_table(table, sheet_name=sheet_name, faculty=faculty, program=program)
    return _parse_grid_schedule_table(table, sheet_name=sheet_name, faculty=faculty, program=program)


def _parse_rowwise_schedule_table(
    table: list[list[str | None]],
    *,
    sheet_name: str,
    faculty: str,
    program: str,
) -> list[RawRecord]:
    header_index, day_columns = _find_rowwise_day_columns(table)
    if header_index < 0 or len(day_columns) < 2:
        return []

    header_row = table[header_index]
    subject_col = 0
    teacher_col = 0
    for column, cell in enumerate(header_row):
        normalized = flatten_multiline(cell).casefold()
        if "назва дисципліни" in normalized:
            subject_col = column
        if "викладача" in normalized:
            teacher_col = column

    records: list[RawRecord] = []
    for row_index, row in enumerate(table[header_index + 1 :], start=header_index + 2):
        subject, extra_notes = _extract_rowwise_subject(row[subject_col] if subject_col < len(row) else "")
        teacher = _join_unique(_split_table_cell_lines(row[teacher_col] if teacher_col < len(row) else ""))
        if not subject:
            continue
        for column, day in day_columns.items():
            if column >= len(row):
                continue
            start_time, end_time = _time_span(_extract_time_ranges_from_text(row[column]))
            if not start_time or not end_time:
                continue
            values = {
                "program": program,
                "faculty": faculty,
                "day": day,
                "start_time": start_time,
                "end_time": end_time,
                "subject": subject,
                "teacher": teacher,
                "notes": "; ".join(extra_notes),
            }
            records.append(
                RawRecord(
                    values=values,
                    row_index=row_index,
                    sheet_name=sheet_name,
                    raw_excerpt=excerpt_from_values(values),
                )
            )
    return records


def _parse_grid_schedule_table(
    table: list[list[str | None]],
    *,
    sheet_name: str,
    faculty: str,
    program: str,
) -> list[RawRecord]:
    day_scores: dict[int, int] = defaultdict(int)
    time_scores: dict[int, int] = defaultdict(int)
    first_slot_row = -1
    max_columns = max((len(row) for row in table), default=0)

    for row_index, row in enumerate(table):
        row_has_axis = False
        for column in range(len(row)):
            cell = row[column]
            if _normalize_day_cell(cell):
                day_scores[column] += 1
                row_has_axis = True
            if _extract_time_ranges_from_text(cell):
                time_scores[column] += 1
                row_has_axis = True
        if row_has_axis and first_slot_row < 0:
            first_slot_row = row_index

    if first_slot_row < 0 or not day_scores or not time_scores:
        return []

    header_row = table[first_slot_row - 1] if first_slot_row > 0 else []
    axis_day_columns = {column for column, score in day_scores.items() if score >= 2}
    axis_time_columns = {column for column, score in time_scores.items() if score >= 2}
    for column, cell in enumerate(header_row):
        normalized = flatten_multiline(cell).casefold()
        if normalized == "день":
            axis_day_columns.add(column)
        if normalized == "час":
            axis_time_columns.add(column)

    if not axis_day_columns and day_scores:
        axis_day_columns.add(max(day_scores, key=day_scores.get))
    if not axis_time_columns and time_scores:
        axis_time_columns.add(max(time_scores, key=time_scores.get))

    if not axis_day_columns or not axis_time_columns:
        return []

    schedule_columns = [column for column in range(max_columns) if column not in axis_day_columns and column not in axis_time_columns]
    if not schedule_columns:
        return []

    header_context = _build_grid_header_context(table[:first_slot_row], schedule_columns)
    records: list[RawRecord] = []
    current_day = ""
    current_start = ""
    current_end = ""
    block_rows: list[list[str | None]] = []
    block_row_index = first_slot_row + 1

    for row_index, row in enumerate(table[first_slot_row:], start=first_slot_row + 1):
        next_day = _first_non_empty(_normalize_day_cell(row[column]) for column in axis_day_columns if column < len(row))
        next_start, next_end = _time_span(
            time_range
            for column in axis_time_columns
            if column < len(row)
            for time_range in _extract_time_ranges_from_text(row[column])
        )
        starts_new_block = bool(block_rows and (next_day or next_start))
        if starts_new_block:
            records.extend(
                _build_grid_block_records(
                    block_rows,
                    row_index=block_row_index,
                    sheet_name=sheet_name,
                    faculty=faculty,
                    program=program,
                    day=current_day,
                    start_time=current_start,
                    end_time=current_end,
                    schedule_columns=schedule_columns,
                    header_context=header_context,
                )
            )
            block_rows = []
            block_row_index = row_index
        if next_day:
            current_day = next_day
        if next_start and next_end:
            current_start, current_end = next_start, next_end
        block_rows.append(row)

    if block_rows:
        records.extend(
            _build_grid_block_records(
                block_rows,
                row_index=block_row_index,
                sheet_name=sheet_name,
                faculty=faculty,
                program=program,
                day=current_day,
                start_time=current_start,
                end_time=current_end,
                schedule_columns=schedule_columns,
                header_context=header_context,
            )
        )
    return records


def _build_grid_header_context(
    header_rows: list[list[str | None]],
    schedule_columns: list[int],
) -> dict[int, list[str]]:
    context: dict[int, list[str]] = {}
    for column in schedule_columns:
        values: list[str] = []
        for row in header_rows:
            if column >= len(row):
                continue
            for line in _split_table_cell_lines(row[column]):
                day = _normalize_day_cell(line)
                if day or _extract_time_ranges_from_text(line):
                    continue
                if line not in values:
                    values.append(line)
        context[column] = values
    return context


def _build_grid_block_records(
    block_rows: list[list[str | None]],
    *,
    row_index: int,
    sheet_name: str,
    faculty: str,
    program: str,
    day: str,
    start_time: str,
    end_time: str,
    schedule_columns: list[int],
    header_context: dict[int, list[str]],
) -> list[RawRecord]:
    if not day or not start_time or not end_time:
        return []

    records: list[RawRecord] = []
    for column in schedule_columns:
        entries: list[tuple[int, list[str]]] = []
        for offset, row in enumerate(block_rows):
            if column >= len(row):
                continue
            lines = _split_table_cell_lines(row[column])
            if lines:
                entries.append((offset, lines))
        if not entries:
            continue

        subject_indexes = [index for index, (_, lines) in enumerate(entries) if _entry_has_subject_payload(lines)]
        if not subject_indexes and _entry_has_subject_payload([line for _, lines in entries for line in lines]):
            subject_indexes = [0]
            entries = [(0, [line for _, lines in entries for line in lines])]
        for subject_index in subject_indexes:
            merged_lines = list(entries[subject_index][1])
            left = subject_index - 1
            while left >= 0 and not _entry_has_subject_payload(entries[left][1]):
                merged_lines = entries[left][1] + merged_lines
                left -= 1
            right = subject_index + 1
            while right < len(entries) and not _entry_has_subject_payload(entries[right][1]):
                merged_lines.extend(entries[right][1])
                right += 1
            values = _build_grid_record_values(
                merged_lines,
                header_lines=header_context.get(column, []),
                program=program,
                faculty=faculty,
                day=day,
                start_time=start_time,
                end_time=end_time,
            )
            if not values:
                continue
            records.append(
                RawRecord(
                    values=values,
                    row_index=row_index,
                    sheet_name=sheet_name,
                    raw_excerpt=excerpt_from_values(values),
                )
            )
    return records


def _build_grid_record_values(
    lines: list[str],
    *,
    header_lines: list[str],
    program: str,
    faculty: str,
    day: str,
    start_time: str,
    end_time: str,
) -> dict[str, str] | None:
    teacher_parts: list[str] = []
    room_parts: list[str] = []
    link_parts: list[str] = []
    note_parts: list[str] = []
    subject_parts: list[str] = []
    groups_parts: list[str] = []
    course_parts: list[str] = []

    for header_line in header_lines:
        cleaned = _normalize_pdf_line(header_line)
        if GROUP_RE.search(cleaned) or cleaned.isupper() or len(cleaned) <= 24:
            groups_parts.append(cleaned)
        course_match = COURSE_RE.search(cleaned)
        if course_match:
            course_parts.append(course_match.group(1))

    for raw_line in lines:
        cleaned = _normalize_pdf_line(raw_line)
        if not cleaned:
            continue
        groups_line, remainder = _split_group_prefix(cleaned)
        if groups_line:
            groups_parts.extend(groups_line)
            cleaned = remainder
        if not cleaned:
            continue
        if _normalize_day_cell(cleaned) or _extract_time_ranges_from_text(cleaned):
            continue
        if LINK_RE.search(cleaned):
            link_parts.append(cleaned)
            continue
        if ROOM_RE.search(cleaned) and not _strip_teacher_and_room(cleaned):
            room_parts.append(cleaned)
            continue
        if TEACHER_RE.search(cleaned) and not _strip_teacher_and_room(cleaned):
            teacher_parts.append(cleaned)
            continue
        if GROUP_RE.search(cleaned):
            groups_parts.append(cleaned)
            continue
        if CODE_RE.search(cleaned):
            note_parts.append(cleaned)
            continue
        subject_parts.append(cleaned)

    subject = _join_unique(subject_parts, separator=" / ")
    if not subject:
        return None

    values = {
        "program": program,
        "faculty": faculty,
        "day": day,
        "start_time": start_time,
        "end_time": end_time,
        "subject": subject,
        "teacher": _join_unique(teacher_parts),
        "link": _join_unique(link_parts, separator=" "),
        "room": _join_unique(room_parts),
        "groups": _join_unique(groups_parts),
        "course": _join_unique(course_parts),
        "notes": _join_unique(note_parts),
    }
    return values


def _find_rowwise_day_columns(table: list[list[str | None]]) -> tuple[int, dict[int, str]]:
    for row_index, row in enumerate(table[:6]):
        day_columns = {
            column: day
            for column, day in (
                (column, _normalize_day_cell(cell))
                for column, cell in enumerate(row)
            )
            if day in DAY_NAMES.values()
        }
        if len(day_columns) >= 3:
            return row_index, day_columns
    return -1, {}


def _extract_rowwise_subject(value: str | None) -> tuple[str, list[str]]:
    subject_parts: list[str] = []
    note_parts: list[str] = []
    for line in _split_table_cell_lines(value):
        if CODE_RE.search(line):
            note_parts.append(line)
            continue
        if not subject_parts:
            subject_parts.append(line)
            continue
        if _looks_like_subject_text(line) and len(subject_parts) < 2:
            subject_parts.append(line)
        else:
            note_parts.append(line)
    return _join_unique(subject_parts), _unique_list(note_parts)


def _entry_has_subject_payload(lines: list[str]) -> bool:
    values = _build_grid_record_values(
        lines,
        header_lines=[],
        program="",
        faculty="",
        day="Понеділок",
        start_time="08:00",
        end_time="09:20",
    )
    return bool(values and values.get("subject"))


def _extract_pdf_text_lines(content: bytes) -> list[str]:
    lines: list[str] = []
    with pdfplumber.open(io.BytesIO(content)) as pdf:
        for page in pdf.pages:
            text = page.extract_text() or ""
            for line in text.splitlines():
                flat = _normalize_pdf_line(line)
                if flat:
                    lines.append(flat)
    return lines


def _filter_valid_pdf_records(records: list[RawRecord]) -> list[RawRecord]:
    deduped: list[RawRecord] = []
    seen: set[tuple[str, str, str, str, str, str]] = set()
    for record in records:
        if not _is_valid_pdf_record(record):
            continue
        key = (
            flatten_multiline(record.values.get("day")),
            flatten_multiline(record.values.get("start_time")),
            flatten_multiline(record.values.get("end_time")),
            flatten_multiline(record.values.get("subject")),
            flatten_multiline(record.values.get("groups")),
            flatten_multiline(record.values.get("teacher")),
        )
        if key in seen:
            continue
        seen.add(key)
        deduped.append(record)
    return deduped


def _parse_pdf_records(lines: list[str], *, sheet_name: str, faculty: str, program: str) -> list[RawRecord]:
    current_day = ""
    pending_start = ""
    pending_end = ""
    buffer: list[str] = []
    records: list[RawRecord] = []

    def flush(row_index: int) -> None:
        nonlocal buffer, pending_start, pending_end
        values = _build_grid_record_values(
            buffer,
            header_lines=[],
            program=program,
            faculty=faculty,
            day=current_day,
            start_time=pending_start,
            end_time=pending_end,
        )
        if values:
            records.append(
                RawRecord(
                    values=values,
                    row_index=row_index,
                    sheet_name=sheet_name,
                    raw_excerpt=excerpt_from_values(values),
                )
            )
        buffer = []
        pending_start = ""
        pending_end = ""

    for index, line in enumerate(lines, start=1):
        day = _normalize_day_cell(line)
        if day:
            if buffer and pending_start and pending_end:
                flush(index)
            current_day = day
            continue

        start_time, end_time = _time_span(_extract_time_ranges_from_text(line))
        if start_time and end_time:
            if buffer and pending_start and pending_end:
                flush(index)
            pending_start, pending_end = start_time, end_time
            remainder = _strip_time_ranges(line)
            if remainder:
                buffer.append(remainder)
            continue

        if pending_start and pending_end:
            buffer.append(line)

    if buffer and pending_start and pending_end:
        flush(len(lines) + 1)
    return records


def _is_valid_pdf_record(record: RawRecord) -> bool:
    day = flatten_multiline(record.values.get("day"))
    start = flatten_multiline(record.values.get("start_time"))
    end = flatten_multiline(record.values.get("end_time"))
    subject = flatten_multiline(record.values.get("subject"))
    if not (day and start and end and subject):
        return False
    if normalize_day(day) not in DAY_NAMES.values():
        return False
    return _looks_like_subject_text(subject)


def _looks_like_subject_text(value: str) -> bool:
    lowered = value.casefold()
    if len(value) < 4:
        return False
    if not _strip_teacher_and_room(value):
        return False
    if re.fullmatch(r"[\d.() /|:;,\-]+", value):
        return False
    if "розклад" in lowered or lowered in {"час", "день"}:
        return False
    compact = re.sub(r"[\s|._:/()\-]+", "", value)
    return len(compact) >= 4 and any(character.isalpha() for character in compact)


def _strip_teacher_and_room(value: str) -> str:
    cleaned = flatten_multiline(value)
    cleaned = ROOM_RE.sub(" ", cleaned)
    cleaned = TEACHER_RE.sub(" ", cleaned)
    cleaned = re.sub(r"[А-ЯІЇЄҐ][а-яіїєґ'-]+\s+[А-ЯІЇЄҐ]\.[А-ЯІЇЄҐ]\.", " ", cleaned)
    cleaned = re.sub(r"\s+", " ", cleaned).strip(" ,.;")
    return cleaned


def _normalize_day_cell(value: str | None) -> str:
    if value is None:
        return ""
    normalized = normalize_day(_normalize_pdf_line(value))
    return normalized if normalized in DAY_NAMES.values() else ""


def _extract_time_ranges_from_text(value: str | None) -> list[tuple[str, str]]:
    text = _normalize_pdf_line(value)
    if not text:
        return []
    matches = []
    for match in PDF_TIME_RANGE_RE.finditer(text):
        start_time, end_time = parse_time_range(match.group(0))
        if start_time and end_time:
            matches.append((start_time, end_time))
    return matches


def _time_span(time_ranges) -> tuple[str, str]:
    ranges = list(time_ranges)
    if not ranges:
        return "", ""
    starts = [start for start, _ in ranges if start]
    ends = [end for _, end in ranges if end]
    if not starts or not ends:
        return "", ""
    return min(starts), max(ends)


def _strip_time_ranges(value: str) -> str:
    normalized = _normalize_pdf_line(value)
    if not normalized:
        return ""
    return flatten_multiline(PDF_TIME_RANGE_RE.sub(" ", normalized))


def _split_group_prefix(value: str) -> tuple[list[str], str]:
    matches = list(re.finditer(r"\d+\s*група", value, flags=re.IGNORECASE))
    if not matches or matches[0].start() > 3:
        return [], value
    prefix = [match.group(0) for match in matches]
    remainder = value[matches[-1].end() :].strip(" -")
    return prefix, remainder


def _normalize_pdf_line(value: str | None) -> str:
    text = flatten_multiline(value)
    if not text:
        return ""
    text = text.replace("’", "'").replace("`", "'")
    tokens = text.split()
    single_token_ratio = (
        sum(1 for token in tokens if len(re.sub(r"[^\w]", "", token, flags=re.UNICODE)) <= 1) / len(tokens)
        if tokens
        else 0
    )
    if len(tokens) >= 6 and single_token_ratio >= 0.6:
        text = "".join(tokens)
    return flatten_multiline(text)


def _split_table_cell_lines(value: str | None) -> list[str]:
    if value is None:
        return []
    raw = str(value).replace("\r", "\n")
    return [line for line in (_normalize_pdf_line(part) for part in raw.splitlines()) if line]


def _join_unique(values: list[str], *, separator: str = "; ") -> str:
    return separator.join(_unique_list(values))


def _unique_list(values) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        cleaned = flatten_multiline(value)
        if not cleaned or cleaned in seen:
            continue
        seen.add(cleaned)
        result.append(cleaned)
    return result


def _first_non_empty(values) -> str:
    for value in values:
        if value:
            return value
    return ""


def _extract_ocr_lines(content: bytes) -> tuple[list[str], list[str]]:
    configure_tesseract()
    tessdata_dir = get_tessdata_dir()
    tesseract_config = "--psm 6"
    if tessdata_dir:
        tesseract_config += f" --tessdata-dir {tessdata_dir}"
    pdf = pypdfium2.PdfDocument(io.BytesIO(content))
    lines: list[str] = []
    warnings: list[str] = []
    try:
        for page_index in range(len(pdf)):
            page = pdf[page_index]
            image = page.render(scale=2.0).to_pil()
            data = pytesseract.image_to_data(
                image,
                lang="ukr+eng",
                output_type=pytesseract.Output.DICT,
                config=tesseract_config,
            )
            grouped: dict[int, list[tuple[int, str]]] = defaultdict(list)
            for idx, token in enumerate(data["text"]):
                text = _normalize_pdf_line(token)
                conf_raw = str(data["conf"][idx]).strip()
                conf = int(float(conf_raw)) if conf_raw not in {"", "-1"} else -1
                if not text or conf < 0:
                    continue
                bucket = round(int(data["top"][idx]) / 12)
                grouped[bucket].append((int(data["left"][idx]), text))
            for _, words in sorted(grouped.items()):
                words.sort(key=lambda item: item[0])
                line = " ".join(word for _, word in words)
                normalized = _normalize_pdf_line(line)
                if normalized:
                    lines.append(normalized)
    finally:
        pdf.close()
    if not lines:
        warnings.append("OCR produced no lines.")
    return lines, warnings
