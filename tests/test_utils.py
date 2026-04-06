from __future__ import annotations

from timetable_scraper.utils import normalize_day, parse_time_range


def test_parse_time_range_supports_compact_pdf_formats() -> None:
    assert parse_time_range("800-920") == ("08:00", "09:20")
    assert parse_time_range("840–925") == ("08:40", "09:25")
    assert parse_time_range("8 0 0 - 9 2 0") == ("08:00", "09:20")


def test_normalize_day_handles_dates_and_vertical_text() -> None:
    assert normalize_day("Понеділок (02.09.2019)") == "Понеділок"
    assert normalize_day("П\nО\nН\nЕ\nД\nІ\nЛ\nО\nК") == "Понеділок"
    assert normalize_day("к\nо\nл\nі\nд\nе\nн\nо\nп") == "Понеділок"
