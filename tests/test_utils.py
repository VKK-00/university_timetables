from __future__ import annotations

from timetable_scraper.utils import (
    extract_week_type_notes,
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
    normalize_week_type,
    parse_time_range,
    slugify_filename,
)


def test_normalize_service_tokens_collapses_dotted_lesson_markers() -> None:
    assert normalize_service_tokens("Course title (lek...........)") == "Course title (lek.)"


def test_parse_time_range_supports_compact_pdf_formats() -> None:
    assert parse_time_range("800-920") == ("08:00", "09:20")
    assert parse_time_range("840–925") == ("08:40", "09:25")
    assert parse_time_range("8 0 0 - 9 2 0") == ("08:00", "09:20")


def test_normalize_week_type_preserves_ranges_as_notes() -> None:
    assert normalize_week_type("1-13 верхній") == "Верхній"
    assert normalize_week_type("1-13 нижній") == "Нижній"
    assert normalize_week_type("1-13") == "Обидва"
    assert normalize_week_type("14") == "Обидва"
    assert normalize_week_type("верхній/нижній") == "Обидва"
    assert normalize_week_type("Вехній") == "Верхній"
    assert normalize_week_type("Нижнй") == "Нижній"
    assert extract_week_type_notes("1-13 верхній") == ["Тижні: 1-13"]
    assert extract_week_type_notes("14") == ["Тижні: 14"]


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
    assert looks_like_forbidden_subject_text("І семестр тижнів: 13")


def test_forbidden_subject_detection_rejects_person_name_rows() -> None:
    assert looks_like_forbidden_subject_text("Андрєєв Назар Едуардович")
    assert looks_like_forbidden_subject_text("Шихизаде Інтігам Алісахіб огли")
    assert not looks_like_forbidden_subject_text("Міжнародна економіка")


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
    assert looks_like_bad_program_label("СУЧАСНОГО СУСПІЛЬСТВА (С)")
    assert looks_like_bad_program_label("3 к 1с")
    assert looks_like_bad_program_label("2с 25 26")
    assert looks_like_bad_program_label("1к 1с 25-26")
    assert looks_like_bad_program_label("2с 25-26")
    assert looks_like_bad_program_label("English 1c")
    assert looks_like_bad_program_label("НАСТАНОВЧА БАК25-26")
    assert looks_like_bad_program_label("e")
    assert looks_like_bad_program_label("Архипова Анастасія Олександрівна")
    assert looks_like_bad_program_label("Вірченко В.,В")
    assert looks_like_bad_program_label("Кластер 1(с)")
    assert looks_like_bad_program_label("1а . 1в . 1с . Павленко В.О")
    assert looks_like_bad_program_label("3а 3в 3с")
    assert looks_like_bad_program_label("Аркуш8")
    assert looks_like_bad_program_label("26.01 30.01 ІПЗ, ІПЗм")
    assert looks_like_bad_program_label("01.09-05.09 АнД, КН, ТШІ")
    assert looks_like_bad_program_label("1 2 курс")
    assert looks_like_bad_program_label("1 2маг")
    assert looks_like_bad_program_label("Nachytka 1 tyzhden 1 semestr 2019 2020 n.r")
    assert looks_like_bad_program_label("Завантажити")
    assert looks_like_bad_program_label("рік навчання")
    assert looks_like_bad_program_label("1 рік навчання")
    assert looks_like_bad_program_label("r.n. or mahistr pravo 2025 2026 2 sem")
    assert looks_like_bad_program_label("Розкдад занять 2 курс ОС бакалавр")
    assert looks_like_bad_program_label('Біологія, Біотехнологія, Екологія, "Ландшафтний дизайн')


def test_normalize_program_candidate_applies_safe_aliases() -> None:
    assert normalize_program_candidate("генетичнии аналіз") == "Генетичний аналіз"
    assert normalize_program_candidate("доклінічнии аналіз продуктів біотехнологіі") == "Доклінічний аналіз продуктів біотехнології"
    assert normalize_program_candidate("26.01 30.01 ІПЗ, ІПЗм") == "ІПЗ, ІПЗм"
    assert normalize_program_candidate("01.09-05.09 АнД, КН, ТШІ") == "АнД, КН, ТШІ"
    assert normalize_program_candidate("1-4 курси (Екологія)") == "Екологія"
    assert normalize_program_candidate('Психологія 1 курс "Магістр"') == "Психологія"
    assert normalize_program_candidate("r.n. or mahistr pravo 2025 2026 2 sem") == "Право"
    assert normalize_program_candidate("r.n. or mahistr iv 2025 2026 2 sem") == "Інтелектуальна власність"
    assert normalize_program_candidate("Медицина(укр) ДОСТАВИТИ") == "Медицина"
    assert normalize_program_candidate("Медицина(укр) магістр") == "Медицина"
    assert normalize_program_candidate('Планування та озеленення" ОС "Бакалавр"') == "Планування та озеленення"
    assert normalize_program_candidate("планування та озеленення") == "Планування та озеленення"
    assert normalize_program_candidate('ОП "Медицина", ОП "Лабораторна діагностика", ОС "Бакалавр", ОС "Магістр"') == "Медицина, Лабораторна діагностика"


def test_slugify_filename_preserves_cyrillic_diacritics() -> None:
    assert slugify_filename("Генетичний аналіз") == "Генетичний аналіз"
    assert slugify_filename("Доклінічний аналіз продуктів біотехнології") == "Доклінічний аналіз продуктів біотехнології"
