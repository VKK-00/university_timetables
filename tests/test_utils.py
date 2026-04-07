from __future__ import annotations

from timetable_scraper.utils import (
    infer_asset_label_from_locator,
    looks_like_garbage_text,
    looks_like_roomish_subject_text,
    looks_like_urlish_text,
    normalize_day,
    parse_time_range,
)


def test_parse_time_range_supports_compact_pdf_formats() -> None:
    assert parse_time_range("800-920") == ("08:00", "09:20")
    assert parse_time_range("840–925") == ("08:40", "09:25")
    assert parse_time_range("8 0 0 - 9 2 0") == ("08:00", "09:20")


def test_normalize_day_handles_dates_and_vertical_text() -> None:
    assert normalize_day("Понеділок (02.09.2019)") == "Понеділок"
    assert normalize_day("П\nО\nН\nЕ\nД\nІ\nЛ\nО\nК") == "Понеділок"
    assert normalize_day("к\nо\nл\nі\nд\nе\nн\nо\nп") == "Понеділок"


def test_looks_like_garbage_text_does_not_flag_english_subject_titles() -> None:
    assert not looks_like_garbage_text("GENDER ORDER TRANSFORMATION IN")
    assert not looks_like_garbage_text("SOCIAL NETWORKS ANALYSIS")


def test_urlish_text_and_asset_label_detection() -> None:
    assert looks_like_urlish_text("https: / / drive.google.com / file / d / abc / view")
    assert infer_asset_label_from_locator("https://iht.knu.ua/wp-content/uploads/2026/02/RozkladННІВТ-2-25-26.pdf") == "Rozklad ННІВТ 2 25 26"


def test_roomish_subject_detection_supports_room_fragments() -> None:
    assert looks_like_roomish_subject_text("404 пр.")
    assert looks_like_roomish_subject_text("лаб.КЯФ 39")
    assert looks_like_roomish_subject_text("пр")
