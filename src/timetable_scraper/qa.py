from __future__ import annotations

from collections import Counter, defaultdict
from pathlib import Path
import re

from openpyxl import Workbook, load_workbook

from .models import NormalizedRow, WorkbookQaSheetSummary, WorkbookQaSummary
from .utils import (
    coalesce_label,
    contains_link_text,
    ensure_parent,
    json_dumps,
    looks_like_admin_text,
    looks_like_technical_label,
    looks_like_garbage_text,
    looks_like_room_text,
    looks_like_roomish_subject_text,
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
    "implausible_time",
    "service_text_subject",
}
LESSON_TEXT_RE = re.compile(r"(?iu)\((?:лек|прак|сем|лаб|lek|sem|prac)")
TRAILING_ROOM_RE = re.compile(r"(?iu)(?:\s*/\s*|\s+)(?:\d{3,4}[А-ЯІЇЄҐA-Z]?|[А-ЯІЇЄҐA-Z]-?\d{2,4}|(?:хімічний|географічний)\s+ф-?т\s+\d{2,4})$")
EXTENDED_DURATION_SUBJECT_RE = re.compile(
    r"(?iu)\b(?:кваліфікаційн\w+\s+робот\w+|захист\w+|атестаці\w+|dissertation|thesis)\b"
)
ABBREVIATED_SUBJECT_RE = re.compile(r"(?iu)^(?:ст|ас|доц|проф|викл)\.?$")


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


def refine_group_quality(accepted: list[NormalizedRow], review: list[NormalizedRow]) -> tuple[list[NormalizedRow], list[NormalizedRow]]:
    groups: dict[tuple[str, str, str, str, str, str, str, str], list[NormalizedRow]] = defaultdict(list)
    for row in accepted:
        if not row.sheet_name.startswith("pdf"):
            continue
        key = (
            row.source_root_url,
            row.asset_locator,
            row.sheet_name,
            row.day,
            row.start_time,
            row.end_time,
            row.course,
            row.groups,
        )
        groups[key].append(row)

    demoted: set[int] = set()
    for rows in groups.values():
        bare_rows = [
            row
            for row in rows
            if not any(value.strip() for value in (row.teacher, row.room, row.link, row.notes))
        ]
        if len(bare_rows) < 2:
            continue
        if not any(_looks_like_fragment_subject(row.subject) for row in bare_rows):
            continue
        for row in bare_rows:
            row.qa_flags = list(dict.fromkeys([*row.qa_flags, "inconsistent_columns"]))
            row.qa_severity = "fail"
            review.append(row)
            demoted.add(id(row))
    return [row for row in accepted if id(row) not in demoted], review


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
    if subject and looks_like_roomish_subject_text(subject):
        flags.append("subject_contains_room")
    if subject and TRAILING_ROOM_RE.search(subject):
        flags.append("subject_contains_room")
    if subject and looks_like_teacher_text(subject):
        flags.append("subject_contains_teacher")
    if subject and contains_link_text(subject):
        flags.append("subject_contains_link")
    if subject and looks_like_admin_text(subject):
        flags.append("service_text_subject")
    if subject and len(subject) > 140:
        flags.append("subject_too_long")
    if row.teacher and len(row.teacher) > 180:
        flags.append("teacher_too_long")
    if row.teacher and (LESSON_TEXT_RE.search(row.teacher) or re.search(r"\b\d{3,4}\b", row.teacher) or re.search(r"\b\d{1,2}[.:]\d{2}\b", row.teacher)):
        flags.append("inconsistent_columns")
    if subject and looks_like_service_text(subject):
        flags.append("service_text_subject")
    if subject and looks_like_garbage_text(subject):
        flags.append("garbage_text")
    if subject and any(token in subject.casefold() for token in ("?pwd=", "?p=", ".us")):
        flags.append("garbage_text")
    if subject and subject.count(" / ") >= 2:
        flags.append("inconsistent_columns")
    if subject and re.search(r"\d{2}\.\d{2}\.\d{4}", subject):
        flags.append("inconsistent_columns")
    if subject and ("-----" in subject or "––––" in subject or "лек....." in subject or "практ....." in subject):
        flags.append("inconsistent_columns")
    if row.teacher and ("лек" in row.teacher.casefold() or "практ" in row.teacher.casefold() or row.teacher.count(";") >= 5):
        flags.append("inconsistent_columns")
    if row.notes and len(row.notes) > 240:
        flags.append("inconsistent_columns")
    if row.notes and len(row.notes) > 80 and looks_like_service_text(row.notes):
        flags.append("inconsistent_columns")
    if subject and subject.startswith("="):
        flags.append("garbage_text")
    if subject and subject.isdigit():
        flags.append("garbage_text")
    if subject and not any(character.isalpha() for character in subject):
        flags.append("garbage_text")
    if subject and ABBREVIATED_SUBJECT_RE.fullmatch(subject):
        flags.append("garbage_text")
    compact_subject = subject.replace(" ", "")
    if (
        subject
        and " " not in subject
        and re.fullmatch(r"[A-Za-z0-9+/=_-]{8,}", compact_subject)
        and (
            any(character.isdigit() for character in compact_subject)
            or any(character in "+/=_-" for character in compact_subject)
            or (re.search(r"[A-Z]", compact_subject) and re.search(r"[a-z]", compact_subject))
        )
    ):
        flags.append("garbage_text")
    if subject and " " not in subject and re.fullmatch(r"[A-Za-z0-9=._-]{10,}", subject):
        flags.append("garbage_text")
    if _has_implausible_time(row.start_time, row.end_time, subject):
        flags.append("implausible_time")

    severity = "none"
    if any(flag in HARD_FAIL_FLAGS for flag in flags):
        severity = "fail"
    elif flags:
        severity = "warning"

    row.qa_flags = list(dict.fromkeys(flags))
    row.qa_severity = severity
    return row


def _looks_like_fragment_subject(subject: str) -> bool:
    stripped = subject.strip()
    if not stripped:
        return True
    if stripped[0].islower():
        return True
    if any(token in stripped.casefold() for token in (".us", "?pwd=", "pwd=", "ідентифікатор", "идентификатор", "конференції", "конференции")):
        return True
    if stripped.count("(") != stripped.count(")"):
        return True
    if stripped.endswith(("-", "/", ":")):
        return True
    if re.fullmatch(r"\([^)]{1,12}\)\s*\d{1,4}", stripped):
        return True
    return False


def _has_implausible_time(start_time: str, end_time: str, subject: str = "") -> bool:
    bounds = []
    for value in (start_time, end_time):
        if not value or ":" not in value:
            continue
        try:
            hours, minutes = (int(part) for part in value.split(":", 1))
        except ValueError:
            return True
        bounds.append(hours * 60 + minutes)
    if any(minutes < 7 * 60 or minutes > 22 * 60 + 30 for minutes in bounds):
        return True
    if len(bounds) == 2:
        duration = bounds[1] - bounds[0]
        if duration < 30:
            return True
        if duration > 240:
            if EXTENDED_DURATION_SUBJECT_RE.search(subject) and duration <= 360:
                return False
            return True
    return False


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
            if subject and looks_like_roomish_subject_text(subject):
                issue_counter["subject_contains_room"] += 1
            if subject and looks_like_teacher_text(subject):
                issue_counter["subject_contains_teacher"] += 1
            if subject and contains_link_text(subject):
                issue_counter["subject_contains_link"] += 1
            if subject and looks_like_admin_text(subject):
                issue_counter["service_text_subject"] += 1
            if subject and looks_like_garbage_text(subject):
                issue_counter["garbage_text"] += 1
            if subject and len(subject) > 140:
                issue_counter["subject_too_long"] += 1
            if teacher and len(teacher) > 180:
                issue_counter["teacher_too_long"] += 1
            if _has_implausible_time(start_time, end_time, subject):
                issue_counter["implausible_time"] += 1
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
