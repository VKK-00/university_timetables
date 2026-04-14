from __future__ import annotations

from timetable_scraper.models import NormalizedRow
from timetable_scraper.qa import sanitize_export_rows
from timetable_scraper.utils import looks_like_bad_program_label


def test_bad_program_label_detection_rejects_phys_semester_date_header() -> None:
    assert looks_like_bad_program_label("1 sem. 2025 2026 28.08.2025")


def test_sanitize_export_rows_recovers_phys_program_from_single_group_label() -> None:
    row = NormalizedRow(
        program="1 sem. 2025 2026 28.08.2025",
        faculty="Фізичний факультет",
        week_type="Обидва",
        day="Понеділок",
        start_time="08:40",
        end_time="10:15",
        subject="Електрика і магнетизм",
        teacher="доц. Кудря В.Ю.",
        groups="Група 1 Фізика",
        course="2",
        confidence=0.99,
        source_name="phys-schedule",
        asset_locator="https://phys.knu.ua/timetable.xlsx",
        sheet_name="Лист1",
    )

    accepted, review = sanitize_export_rows([row], [])

    assert len(accepted) == 1
    assert not review
    assert accepted[0].program == "Фізика"
    assert "program_label_recovered" in accepted[0].autofix_actions


def test_sanitize_export_rows_does_not_recover_phys_program_from_group_aggregate() -> None:
    row = NormalizedRow(
        program="1 sem. 2025 2026 28.08.2025",
        faculty="Фізичний факультет",
        week_type="Обидва",
        day="Понеділок",
        start_time="08:40",
        end_time="10:15",
        subject="Електрика і магнетизм",
        teacher="доц. Кудря В.Ю.",
        groups="Група 1 Фізика ; Група 5 Фізика",
        course="2",
        confidence=0.99,
        source_name="phys-schedule",
        asset_locator="https://phys.knu.ua/timetable.xlsx",
        sheet_name="Лист1",
    )

    accepted, review = sanitize_export_rows([row], [])

    assert not accepted
    assert len(review) == 1
    assert "bad_program_label" in review[0].qa_flags
