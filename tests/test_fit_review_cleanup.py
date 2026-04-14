from __future__ import annotations

from timetable_scraper.models import NormalizedRow
from timetable_scraper.qa import sanitize_export_rows


def test_sanitize_export_rows_drops_fit_date_list_only_review_row() -> None:
    row = NormalizedRow(
        program="ПІ, ПП, СІ, ІС",
        faculty="Факультет інформаційних технологій",
        week_type="Обидва",
        day="Понеділок",
        start_time="09:00",
        end_time="10:20",
        subject="",
        notes="[03.11, 10.11, 17.11, 24.11, 01.12]; [29.09, 06.10, 13.10, 20.10, 27.10]",
        room="ауд. 209",
        confidence=0.2,
        qa_flags=["missing_subject"],
        source_name="fit-schedule",
    )

    accepted, review = sanitize_export_rows([], [row])

    assert not accepted
    assert not review


def test_sanitize_export_rows_drops_fit_date_placeholder_subject() -> None:
    row = NormalizedRow(
        program="АнД, КН, ТШІ",
        faculty="Факультет інформаційних технологій",
        week_type="Обидва",
        day="Понеділок",
        start_time="09:00",
        end_time="10:20",
        subject="[01.12] . .",
        notes="",
        room="",
        confidence=0.2,
        qa_flags=["garbage_text"],
        source_name="fit-schedule",
    )

    accepted, review = sanitize_export_rows([], [row])

    assert not accepted
    assert not review


def test_sanitize_export_rows_drops_fit_date_placeholder_with_inner_space() -> None:
    row = NormalizedRow(
        program="АнД, КН, ТШІ",
        faculty="Факультет інформаційних технологій",
        week_type="Обидва",
        day="Понеділок",
        start_time="09:00",
        end_time="10:20",
        subject="[30.03 ]",
        notes="",
        room="ауд. 211",
        confidence=0.2,
        qa_flags=["garbage_text"],
        source_name="fit-schedule",
    )

    accepted, review = sanitize_export_rows([], [row])

    assert not accepted
    assert not review
