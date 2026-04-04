from __future__ import annotations

from collections import defaultdict
from copy import copy
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

from openpyxl import Workbook, load_workbook

from .models import NormalizedRow
from .utils import ensure_parent, json_dumps, slugify_filename, truncate_sheet_title


REVIEW_COLUMNS = [
    "program",
    "faculty",
    "sheet_name",
    "confidence",
    "warnings",
    "source_kind",
    "source_url_or_path",
    "raw_excerpt",
    "week_type",
    "day",
    "start_time",
    "end_time",
    "subject",
    "teacher",
    "lesson_type",
    "link",
    "room",
    "groups",
    "course",
    "notes",
]

BODY_COLUMNS = [
    "week_type",
    "day",
    "start_time",
    "end_time",
    "subject",
    "teacher",
    "lesson_type",
    "link",
    "room",
    "groups",
    "course",
    "notes",
]


@dataclass(slots=True)
class CellStyleSnapshot:
    font: object
    fill: object
    border: object
    alignment: object
    protection: object
    number_format: str


@dataclass(slots=True)
class TemplateStylePack:
    title_style: CellStyleSnapshot
    header_style: CellStyleSnapshot
    body_style: CellStyleSnapshot
    title_row_height: float | None
    header_row_height: float | None
    body_row_height: float | None


def export_rows(
    rows: list[NormalizedRow],
    review_rows: list[NormalizedRow],
    *,
    template_path: Path,
    output_dir: Path,
) -> tuple[list[Path], Path, Path]:
    exported_files = _export_program_workbooks(rows, template_path=template_path, output_dir=output_dir)
    manifest_path = output_dir / "manifest.jsonl"
    review_queue_path = output_dir / "review_queue.xlsx"
    _write_manifest([*rows, *review_rows], manifest_path)
    _write_review_queue(review_rows, review_queue_path, template_path=template_path)
    return exported_files, manifest_path, review_queue_path


def _export_program_workbooks(rows: list[NormalizedRow], *, template_path: Path, output_dir: Path) -> list[Path]:
    grouped: dict[tuple[str, str], list[NormalizedRow]] = defaultdict(list)
    for row in rows:
        grouped[(row.faculty, row.program)].append(row)
    exported: list[Path] = []
    for (faculty, program), program_rows in grouped.items():
        workbook = load_workbook(template_path)
        template_sheet = workbook.active
        style_pack = _capture_template_styles(template_sheet)
        _prepare_output_sheet(template_sheet, program=program, style_pack=style_pack)
        sheet_map: dict[str, list[NormalizedRow]] = defaultdict(list)
        for row in sorted(program_rows, key=_sort_key):
            sheet_map[row.sheet_name or "Аркуш1"].append(row)
        first_sheet = True
        for sheet_name, sheet_rows in sheet_map.items():
            sheet = template_sheet if first_sheet else workbook.copy_worksheet(template_sheet)
            first_sheet = False
            sheet.title = truncate_sheet_title(sheet_name)
            if sheet is not template_sheet:
                _prepare_output_sheet(sheet, program=program, style_pack=style_pack)
            for row_index, row in enumerate(sheet_rows, start=3):
                _write_body_row(sheet, row_index, row, style_pack)
        target = output_dir / slugify_filename(faculty) / f"{slugify_filename(program)}.xlsx"
        ensure_parent(target)
        workbook.save(target)
        exported.append(target)
    return exported


def _write_manifest(rows: Iterable[NormalizedRow], path: Path) -> None:
    ensure_parent(path)
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(
                json_dumps(
                    {
                        "program": row.program,
                        "faculty": row.faculty,
                        "sheet_name": row.sheet_name,
                        "week_type": row.week_type,
                        "day": row.day,
                        "start_time": row.start_time,
                        "end_time": row.end_time,
                        "subject": row.subject,
                        "teacher": row.teacher,
                        "lesson_type": row.lesson_type,
                        "link": row.link,
                        "room": row.room,
                        "groups": row.groups,
                        "course": row.course,
                        "notes": row.notes,
                        "source_kind": row.source_kind,
                        "source_url_or_path": row.source_url_or_path,
                        "confidence": row.confidence,
                        "warnings": row.warnings,
                        "raw_excerpt": row.raw_excerpt,
                        "content_hash": row.content_hash,
                    }
                )
                + "\n"
            )


def _write_review_queue(rows: list[NormalizedRow], path: Path, *, template_path: Path) -> None:
    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "review_queue"
    style_pack = _capture_template_styles(load_workbook(template_path).active)
    for column, title in enumerate(REVIEW_COLUMNS, start=1):
        cell = sheet.cell(1, column)
        cell.value = title
        _apply_cell_style(cell, style_pack.header_style)
    if style_pack.header_row_height is not None:
        sheet.row_dimensions[1].height = style_pack.header_row_height
    for row_index, row in enumerate(rows, start=2):
        values = {
            "program": row.program,
            "faculty": row.faculty,
            "sheet_name": row.sheet_name,
            "confidence": row.confidence,
            "warnings": ", ".join(row.warnings),
            "source_kind": row.source_kind,
            "source_url_or_path": row.source_url_or_path,
            "raw_excerpt": row.raw_excerpt,
            "week_type": row.week_type,
            "day": row.day,
            "start_time": row.start_time,
            "end_time": row.end_time,
            "subject": row.subject,
            "teacher": row.teacher,
            "lesson_type": row.lesson_type,
            "link": row.link,
            "room": row.room,
            "groups": row.groups,
            "course": row.course,
            "notes": row.notes,
        }
        for column, title in enumerate(REVIEW_COLUMNS, start=1):
            cell = sheet.cell(row_index, column)
            cell.value = values.get(title, "")
            _apply_cell_style(cell, style_pack.body_style)
        if style_pack.body_row_height is not None:
            sheet.row_dimensions[row_index].height = style_pack.body_row_height
    ensure_parent(path)
    workbook.save(path)


def _prepare_output_sheet(sheet, *, program: str, style_pack: TemplateStylePack) -> None:
    sheet["A1"] = program
    _apply_cell_style(sheet["A1"], style_pack.title_style)
    if style_pack.title_row_height is not None:
        sheet.row_dimensions[1].height = style_pack.title_row_height
    if style_pack.header_row_height is not None:
        sheet.row_dimensions[2].height = style_pack.header_row_height
    for row_index in range(3, sheet.max_row + 1):
        for column in range(1, len(BODY_COLUMNS) + 1):
            sheet.cell(row_index, column).value = None


def _write_body_row(sheet, row_index: int, row: NormalizedRow, style_pack: TemplateStylePack) -> None:
    values = [
        row.week_type,
        row.day,
        row.start_time,
        row.end_time,
        row.subject,
        row.teacher,
        row.lesson_type,
        row.link,
        row.room,
        row.groups,
        row.course,
        row.notes,
    ]
    for column, value in enumerate(values, start=1):
        cell = sheet.cell(row_index, column)
        cell.value = value
        _apply_cell_style(cell, style_pack.body_style)
    if style_pack.body_row_height is not None:
        sheet.row_dimensions[row_index].height = style_pack.body_row_height


def _capture_template_styles(template_sheet) -> TemplateStylePack:
    return TemplateStylePack(
        title_style=_snapshot_cell_style(template_sheet["A1"]),
        header_style=_snapshot_cell_style(template_sheet["A2"]),
        body_style=_snapshot_cell_style(template_sheet["A3"]),
        title_row_height=template_sheet.row_dimensions[1].height,
        header_row_height=template_sheet.row_dimensions[2].height,
        body_row_height=template_sheet.row_dimensions[3].height,
    )


def _snapshot_cell_style(cell) -> CellStyleSnapshot:
    return CellStyleSnapshot(
        font=copy(cell.font),
        fill=copy(cell.fill),
        border=copy(cell.border),
        alignment=copy(cell.alignment),
        protection=copy(cell.protection),
        number_format=cell.number_format,
    )


def _apply_cell_style(cell, style: CellStyleSnapshot) -> None:
    cell.font = copy(style.font)
    cell.fill = copy(style.fill)
    cell.border = copy(style.border)
    cell.alignment = copy(style.alignment)
    cell.protection = copy(style.protection)
    cell.number_format = style.number_format


def _sort_key(row: NormalizedRow) -> tuple[int, str, str, str]:
    day_order = {
        "Понеділок": 1,
        "Вівторок": 2,
        "Середа": 3,
        "Четвер": 4,
        "П'ятниця": 5,
        "Субота": 6,
        "Неділя": 7,
    }
    return (day_order.get(row.day, 99), row.start_time, row.week_type, row.subject)
