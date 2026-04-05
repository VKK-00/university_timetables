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


def parse_pdf_asset(fetched_asset: FetchedAsset, *, ocr_enabled: bool) -> ParsedDocument:
    faculty = infer_faculty_from_locator(fetched_asset.asset.source_root_url or fetched_asset.asset.locator)
    program = fetched_asset.asset.display_name
    warnings: list[str] = []

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


def _extract_pdf_text_lines(content: bytes) -> list[str]:
    lines: list[str] = []
    with pdfplumber.open(io.BytesIO(content)) as pdf:
        for page in pdf.pages:
            text = page.extract_text() or ""
            for line in text.splitlines():
                flat = flatten_multiline(line)
                if flat:
                    lines.append(flat)
    return lines


def _filter_valid_pdf_records(records: list[RawRecord]) -> list[RawRecord]:
    return [record for record in records if _is_valid_pdf_record(record)]


def _parse_pdf_records(lines: list[str], *, sheet_name: str, faculty: str, program: str) -> list[RawRecord]:
    current_day = ""
    records: list[RawRecord] = []
    for index, line in enumerate(lines, start=1):
        start_time, end_time = parse_time_range(line)
        if not start_time or not end_time:
            if _looks_like_day_heading(line):
                current_day = flatten_multiline(line)
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


def _looks_like_day_heading(value: str) -> bool:
    text = flatten_multiline(value)
    if not text or "|" in text:
        return False
    if parse_time_range(text) != ("", ""):
        return False
    return normalize_day(text) in DAY_NAMES.values()


def _looks_like_subject_text(value: str) -> bool:
    lowered = value.casefold()
    if len(value) < 4:
        return False
    if re.fullmatch(r"[\d.() /|:-]+", value):
        return False
    if "розклад" in lowered:
        return False
    compact = re.sub(r"[\s|._:/()-]+", "", value)
    return len(compact) >= 4


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
                text = flatten_multiline(token)
                conf_raw = str(data["conf"][idx]).strip()
                conf = int(float(conf_raw)) if conf_raw not in {"", "-1"} else -1
                if not text or conf < 0:
                    continue
                bucket = round(int(data["top"][idx]) / 12)
                grouped[bucket].append((int(data["left"][idx]), text))
            for _, words in sorted(grouped.items()):
                words.sort(key=lambda item: item[0])
                line = " ".join(word for _, word in words)
                if line:
                    lines.append(line)
    finally:
        pdf.close()
    if not lines:
        warnings.append("OCR produced no lines.")
    return lines, warnings
