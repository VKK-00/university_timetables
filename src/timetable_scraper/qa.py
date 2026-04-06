from __future__ import annotations

from collections import Counter
from pathlib import Path
import re

from openpyxl import Workbook, load_workbook

from .models import NormalizedRow, WorkbookQaSheetSummary, WorkbookQaSummary
from .utils import (
    coalesce_label,
    contains_link_text,
    ensure_parent,
    json_dumps,
    looks_like_technical_label,
    looks_like_garbage_text,
    looks_like_room_text,
    looks_like_service_text,
    looks_like_teacher_text,
)


BODY_COLUMN_COUNT = 12
HARD_FAIL_FLAGS = {
    "missing_day",
    "missing_time",
    "missing_subject",
    "subject_contains_room",
    "subject_contains_teacher",
    "subject_contains_link",
    "subject_too_long",
    "teacher_too_long",
    "garbage_text",
    "inconsistent_columns",
}


def partition_rows(rows: list[NormalizedRow], threshold: float) -> tuple[list[NormalizedRow], list[NormalizedRow]]:
    accepted: list[NormalizedRow] = []
    review: list[NormalizedRow] = []
    for row in rows:
        analyze_row_quality(row)
        required_ok = bool(row.day and row.start_time and row.end_time and row.subject)
        hard_fail = any(flag in HARD_FAIL_FLAGS for flag in row.qa_flags)
        if required_ok and row.confidence >= threshold and not hard_fail:
            accepted.append(row)
        else:
            review.append(row)
    return accepted, review


def analyze_row_quality(row: NormalizedRow) -> NormalizedRow:
    flags = list(dict.fromkeys(row.qa_flags))
    subject = row.subject.strip()
    if not row.day:
        flags.append("missing_day")
    if not (row.start_time and row.end_time):
        flags.append("missing_time")
    if not subject:
        flags.append("missing_subject")
    if subject and looks_like_room_text(subject):
        flags.append("subject_contains_room")
    if subject and looks_like_teacher_text(subject):
        flags.append("subject_contains_teacher")
    if subject and contains_link_text(subject):
        flags.append("subject_contains_link")
    if subject and len(subject) > 140:
        flags.append("subject_too_long")
    if row.teacher and len(row.teacher) > 180:
        flags.append("teacher_too_long")
    if subject and looks_like_service_text(subject):
        flags.append("garbage_text")
    if subject and looks_like_garbage_text(subject):
        flags.append("garbage_text")
    if subject and subject.count(" / ") >= 2:
        flags.append("inconsistent_columns")
    if subject and re.search(r"\d{2}\.\d{2}\.\d{4}", subject):
        flags.append("inconsistent_columns")
    if subject and ("-----" in subject or "––––" in subject or "лек....." in subject or "практ....." in subject):
        flags.append("inconsistent_columns")
    if row.teacher and ("лек" in row.teacher.casefold() or "практ" in row.teacher.casefold() or row.teacher.count(";") >= 5):
        flags.append("inconsistent_columns")
    if subject and subject.startswith("="):
        flags.append("garbage_text")
    if subject and subject.isdigit():
        flags.append("garbage_text")
    if subject and not any(character.isalpha() for character in subject):
        flags.append("garbage_text")
    if subject and re.fullmatch(r"[A-Za-z0-9+/=_-]{8,}", subject.replace(" ", "")):
        flags.append("garbage_text")
    if subject and " " not in subject and re.fullmatch(r"[A-Za-z0-9=._-]{10,}", subject):
        flags.append("garbage_text")

    severity = "none"
    if any(flag in HARD_FAIL_FLAGS for flag in flags):
        severity = "fail"
    elif flags:
        severity = "warning"

    row.qa_flags = list(dict.fromkeys(flags))
    row.qa_severity = severity
    return row


def audit_exported_workbooks(exported_files: list[Path], *, output_dir: Path) -> tuple[list[WorkbookQaSummary], Path, Path]:
    summaries = [_audit_single_workbook(path) for path in sorted(exported_files)]
    json_path = output_dir / "qa_report.json"
    xlsx_path = output_dir / "qa_report.xlsx"
    _write_qa_report_json(summaries, json_path)
    _write_qa_report_xlsx(summaries, xlsx_path)
    return summaries, json_path, xlsx_path


def _audit_single_workbook(path: Path) -> WorkbookQaSummary:
    try:
        workbook = load_workbook(path, data_only=True)
    except Exception as exc:
        return WorkbookQaSummary(
            file_path=path,
            status="fail",
            row_count=0,
            issue_count=1,
            issues=[f"workbook_open_failed: {exc.__class__.__name__}"],
            sheets=[],
        )
    workbook_issues: list[str] = []
    sheet_summaries: list[WorkbookQaSheetSummary] = []
    total_rows = 0

    technical_name = coalesce_label(path.stem, fallback="")
    if not technical_name or looks_like_technical_label(path.stem):
        workbook_issues.append("technical_file_name")

    for sheet in workbook.worksheets:
        row_count = 0
        issue_counter: Counter[str] = Counter()
        non_class_rows = 0
        for row_index in range(3, sheet.max_row + 1):
            values = [sheet.cell(row_index, column).value for column in range(1, BODY_COLUMN_COUNT + 1)]
            if not any(value not in ("", None) for value in values):
                continue
            row_count += 1
            week_type, day, start_time, end_time, subject = (str(values[index]).strip() if values[index] is not None else "" for index in range(5))
            teacher = str(values[5]).strip() if values[5] is not None else ""
            if not week_type:
                issue_counter["missing_week_type"] += 1
            if not (day and start_time and end_time and subject):
                issue_counter["missing_required_cells"] += 1
            if subject and "самостій" in subject.casefold():
                non_class_rows += 1
            if subject and looks_like_room_text(subject):
                issue_counter["subject_contains_room"] += 1
            if subject and looks_like_teacher_text(subject):
                issue_counter["subject_contains_teacher"] += 1
            if subject and contains_link_text(subject):
                issue_counter["subject_contains_link"] += 1
            if subject and looks_like_garbage_text(subject):
                issue_counter["garbage_text"] += 1
            if subject and len(subject) > 140:
                issue_counter["subject_too_long"] += 1
            if teacher and len(teacher) > 180:
                issue_counter["teacher_too_long"] += 1
        if row_count == 0:
            issue_counter["empty_sheet"] += 1
        elif row_count == 1 and looks_like_technical_label(path.stem):
            issue_counter["suspicious_small_sheet"] += 1

        total_rows += row_count
        sheet_summaries.append(
            WorkbookQaSheetSummary(
                sheet_name=sheet.title,
                row_count=row_count,
                issue_count=sum(issue_counter.values()),
                issues=[name for name, _ in issue_counter.most_common(5)],
            )
        )
        workbook_issues.extend(name for name, _ in issue_counter.items())

    status = "pass"
    if "missing_required_cells" in workbook_issues or "empty_sheet" in workbook_issues or total_rows == 0:
        status = "fail"
    elif workbook_issues:
        status = "warning"

    issue_counter = Counter(workbook_issues)
    return WorkbookQaSummary(
        file_path=path,
        status=status,
        row_count=total_rows,
        issue_count=sum(issue_counter.values()),
        issues=[name for name, _ in issue_counter.most_common(8)],
        sheets=sheet_summaries,
    )


def _write_qa_report_json(summaries: list[WorkbookQaSummary], path: Path) -> None:
    ensure_parent(path)
    payload = [
        {
            "file_path": str(summary.file_path),
            "status": summary.status,
            "row_count": summary.row_count,
            "issue_count": summary.issue_count,
            "issues": summary.issues,
            "sheets": [
                {
                    "sheet_name": sheet.sheet_name,
                    "row_count": sheet.row_count,
                    "issue_count": sheet.issue_count,
                    "issues": sheet.issues,
                }
                for sheet in summary.sheets
            ],
        }
        for summary in summaries
    ]
    path.write_text(
        "[\n" + ",\n".join(json_dumps(item) for item in payload) + "\n]\n",
        encoding="utf-8",
    )


def _write_qa_report_xlsx(summaries: list[WorkbookQaSummary], path: Path) -> None:
    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "qa_report"
    headers = ["file", "sheet", "row_count", "issue_count", "status", "top_issues"]
    for column, title in enumerate(headers, start=1):
        sheet.cell(1, column).value = title
    row_index = 2
    for summary in summaries:
        if not summary.sheets:
            sheet.cell(row_index, 1).value = str(summary.file_path)
            sheet.cell(row_index, 3).value = summary.row_count
            sheet.cell(row_index, 4).value = summary.issue_count
            sheet.cell(row_index, 5).value = summary.status
            sheet.cell(row_index, 6).value = ", ".join(summary.issues)
            row_index += 1
            continue
        for qa_sheet in summary.sheets:
            sheet.cell(row_index, 1).value = str(summary.file_path)
            sheet.cell(row_index, 2).value = qa_sheet.sheet_name
            sheet.cell(row_index, 3).value = qa_sheet.row_count
            sheet.cell(row_index, 4).value = qa_sheet.issue_count
            sheet.cell(row_index, 5).value = summary.status
            sheet.cell(row_index, 6).value = ", ".join(qa_sheet.issues or summary.issues)
            row_index += 1
    ensure_parent(path)
    workbook.save(path)
