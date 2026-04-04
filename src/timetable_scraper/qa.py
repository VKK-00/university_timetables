from __future__ import annotations

from .models import NormalizedRow


def partition_rows(rows: list[NormalizedRow], threshold: float) -> tuple[list[NormalizedRow], list[NormalizedRow]]:
    accepted: list[NormalizedRow] = []
    review: list[NormalizedRow] = []
    for row in rows:
        required_ok = bool(row.day and row.start_time and row.end_time and row.subject)
        non_class_ok = bool(row.day and row.subject and _is_non_class_row(row))
        if (required_ok and row.confidence >= threshold) or non_class_ok:
            accepted.append(row)
        else:
            review.append(row)
    return accepted, review


def _is_non_class_row(row: NormalizedRow) -> bool:
    marker_source = " ".join(part for part in (row.subject, row.notes) if part).casefold()
    return any(pattern in marker_source for pattern in ("вихідний", "вихiдний", "день самостійної роботи"))
