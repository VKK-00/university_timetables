from __future__ import annotations

import io
from collections import defaultdict

import pdfplumber
import pypdfium2
import pytesseract

from ..models import FetchedAsset, ParsedDocument, ParsedSheet
from ..ocr import configure_tesseract, get_tessdata_dir
from ..utils import flatten_multiline, infer_faculty_from_locator
from .html import _parse_block_records


def parse_pdf_asset(fetched_asset: FetchedAsset, *, ocr_enabled: bool) -> ParsedDocument:
    faculty = infer_faculty_from_locator(fetched_asset.asset.locator)
    program = fetched_asset.asset.display_name
    text_chunks: list[str] = []
    warnings: list[str] = []
    with pdfplumber.open(io.BytesIO(fetched_asset.content)) as pdf:
        for page in pdf.pages:
            text = page.extract_text() or ""
            if text.strip():
                text_chunks.append(text)
    if text_chunks:
        records = _parse_block_records("\n".join(text_chunks), sheet_name="pdf", faculty=faculty, program=program)
        return ParsedDocument(asset=fetched_asset, sheets=[ParsedSheet(sheet_name="pdf", program=program, faculty=faculty, records=records)], warnings=warnings)
    warnings.append("No embedded text found in PDF.")
    if not ocr_enabled:
        return ParsedDocument(asset=fetched_asset, sheets=[ParsedSheet(sheet_name="pdf", program=program, faculty=faculty, records=[])], warnings=warnings)
    lines, ocr_warnings = _extract_ocr_lines(fetched_asset.content)
    warnings.extend(ocr_warnings)
    records = _parse_block_records("\n".join(lines), sheet_name="pdf-ocr", faculty=faculty, program=program)
    return ParsedDocument(asset=fetched_asset, sheets=[ParsedSheet(sheet_name="pdf-ocr", program=program, faculty=faculty, records=records)], warnings=warnings)


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
