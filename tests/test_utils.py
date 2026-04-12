from __future__ import annotations

from timetable_scraper.utils import (
    infer_asset_label_from_locator,
    looks_like_bad_program_label,
    looks_like_forbidden_subject_text,
    looks_like_garbage_text,
    looks_like_room_text,
    looks_like_roomish_subject_text,
    looks_like_technical_label,
    looks_like_urlish_text,
    normalize_day,
    normalize_program_candidate,
    normalize_service_tokens,
    parse_time_range,
    slugify_filename,
)


def test_normalize_service_tokens_collapses_dotted_lesson_markers() -> None:
    assert normalize_service_tokens("Course title (lek...........)") == "Course title (lek.)"


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
    assert infer_asset_label_from_locator("https://iht.knu.ua/wp-content/uploads/2026/02/RozkladННІВТ-2-25-26.pdf") == ""


def test_technical_label_detection_rejects_storage_query_tails() -> None:
    assert looks_like_technical_label("view?usp=drivesdk")
    assert looks_like_technical_label("edit?usp=sharing")


def test_roomish_subject_detection_supports_room_fragments() -> None:
    assert looks_like_roomish_subject_text("404 пр.")
    assert looks_like_roomish_subject_text("лаб.КЯФ 39")
    assert looks_like_roomish_subject_text("пр")
    assert looks_like_roomish_subject_text("113 ауд.")


def test_room_detection_does_not_treat_corporate_as_room() -> None:
    assert not looks_like_room_text("корпоративна")
    assert looks_like_room_text("ауд. 410")
    assert looks_like_room_text("корп. 2")


def test_forbidden_subject_detection_rejects_spaced_weekdays() -> None:
    assert looks_like_forbidden_subject_text("M O N D A Y")
    assert looks_like_forbidden_subject_text("F R I D A Y")


def test_bad_program_label_detection_rejects_multiple_program_codes() -> None:
    assert looks_like_bad_program_label("102 Хімія 091 Біологія та біохімія")


def test_bad_program_label_detection_rejects_contaminated_schedule_titles() -> None:
    assert looks_like_bad_program_label("Розклад занять на перший семестр 2025 2026 навчального року")
    assert looks_like_bad_program_label("Соціальна робота 1 курс Магістр розклад з 26.01.2026 01.02.2026 року")


def test_bad_program_label_detection_rejects_group_aggregate_and_session_titles() -> None:
    assert looks_like_bad_program_label("SCHEDULE OF CLASSES FACULTY OF SOCIOLOGY")
    assert looks_like_bad_program_label("настановча сесія")
    assert looks_like_bad_program_label("настановча 1 24 25")
    assert looks_like_bad_program_label("1 магістри")
    assert looks_like_bad_program_label("Група 1 Фізика ; Група 5 Фізика ; Група Астрономія")
    assert looks_like_bad_program_label("III ПОТІК ; 9 група 10 група 11 група 12 група")
    assert looks_like_bad_program_label("8 ; 18 академі")
    assert looks_like_bad_program_label("ГЕОДЕЗІЯ ТА")
    assert looks_like_bad_program_label("lcs3glm4")
    assert looks_like_bad_program_label("ямо11м ; 111 а к-ад е0м")
    assert looks_like_bad_program_label("практ. астрофіз")
    assert looks_like_bad_program_label("чл.-кор. НАНУ")
    assert looks_like_bad_program_label("Економічна географія ; Управління розвитком ; туризму та рекреації")


def test_normalize_program_candidate_applies_safe_aliases() -> None:
    assert normalize_program_candidate("генетичнии аналіз") == "Генетичний аналіз"
    assert normalize_program_candidate("доклінічнии аналіз продуктів біотехнологіі") == "Доклінічний аналіз продуктів біотехнології"


def test_slugify_filename_preserves_cyrillic_diacritics() -> None:
    assert slugify_filename("Генетичний аналіз") == "Генетичний аналіз"
    assert slugify_filename("Доклінічний аналіз продуктів біотехнології") == "Доклінічний аналіз продуктів біотехнології"
