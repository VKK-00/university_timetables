from __future__ import annotations

from timetable_scraper.normalize import map_headers, normalize_document, normalize_record, records_from_tabular_rows, score_record
from timetable_scraper.models import DiscoveredAsset, FetchedAsset, NormalizedRow, ParsedDocument, ParsedSheet, RawRecord
from timetable_scraper.qa import partition_rows, refine_group_quality, sanitize_export_rows
from timetable_scraper.utils import clean_numeric_artifact, flatten_multiline, looks_like_bad_program_label, parse_time_value


def test_map_headers_supports_known_variants() -> None:
    headers = [
        "Тиждень",
        "День",
        "Початок",
        "Кінець",
        "Назва предмету",
        "Викладач",
        "Курси",
    ]
    mapping = map_headers(headers)
    assert mapping["subject"] == 4
    assert mapping["course"] == 6


def test_parse_time_value_supports_excel_fractions_and_text() -> None:
    assert parse_time_value(0.3333333333333333) == "08:00"
    assert parse_time_value("8.40") == "08:40"
    assert parse_time_value("09:30") == "09:30"


def test_clean_numeric_artifact_preserves_non_excel_ids() -> None:
    assert clean_numeric_artifact("1.0") == "1"
    assert clean_numeric_artifact("1234") == "1234"
    assert clean_numeric_artifact("1.2") == "1.2"
    assert clean_numeric_artifact("2; 3; 4") == "2; 3; 4"


def test_flatten_multiline_merges_lines_cleanly() -> None:
    assert flatten_multiline("Бази\nданих\r\nі знань") == "Бази даних і знань"


def test_score_record_drops_for_missing_required_fields() -> None:
    strong = score_record(has_day=True, has_start=True, has_end=True, has_subject=True, warning_count=0)
    weak = score_record(has_day=True, has_start=False, has_end=False, has_subject=False, warning_count=3)
    assert strong > weak


def test_normalize_record_marks_low_confidence_row() -> None:
    asset = DiscoveredAsset(
        source_name="fixture",
        source_kind="zip",
        source_url_or_path="fixtures.zip",
        asset_kind="zip_entry",
        locator="fixtures.zip::demo.xlsx",
        display_name="demo.xlsx",
    )
    fetched = FetchedAsset(asset=asset, content=b"", content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", content_hash="abc", resolved_locator="demo.xlsx")
    record = RawRecord(values={"program": "Demo", "faculty": "FIT", "subject": "Алгоритми"}, row_index=3, sheet_name="1 курс", raw_excerpt="Алгоритми")
    row = normalize_record(record, document=ParsedDocument(asset=fetched, sheets=[]))
    assert row.confidence < 0.74
    assert "missing_day" in row.warnings
    assert row.week_type == "Обидва"
    assert row.week_source == "default"


def test_records_from_tabular_rows_skip_link_only_rows() -> None:
    rows = [
        ["Тиждень", "День", "Початок", "Кінець", "Назва предмета", "Викладач", "Тип заняття", "Посилання (якщо є)"],
        [None, None, None, None, None, None, None, "https://example.edu/only-link"],
        ["Обидва", "Понеділок", "09:30", "10:50", "Алгоритми", "доц. Іваненко", "лекція", "https://example.edu/class"],
    ]
    records, warnings = records_from_tabular_rows(rows, program="Demo", faculty="FIT", sheet_name="1 курс")
    assert not warnings
    assert len(records) == 1
    assert records[0].values["subject"] == "Алгоритми"


def test_normalize_record_demotes_standalone_self_study_subject() -> None:
    asset = DiscoveredAsset(
        source_name="fixture",
        source_kind="zip",
        source_url_or_path="fixtures.zip",
        asset_kind="zip_entry",
        locator="fixtures.zip::demo.xlsx",
        display_name="demo.xlsx",
    )
    fetched = FetchedAsset(asset=asset, content=b"", content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", content_hash="abc", resolved_locator="demo.xlsx")
    record = RawRecord(
        values={
            "program": "Demo",
            "faculty": "FIT",
            "week_type": "Обидва",
            "day": "Понеділок",
            "start_time": "09:30",
            "end_time": "10:50",
            "lesson_type": "самостійна робота",
            "groups": "Оптика",
            "course": "2",
        },
        row_index=3,
        sheet_name="1 курс",
        raw_excerpt="самостійна робота",
    )
    row = normalize_record(record, document=ParsedDocument(asset=fetched, sheets=[]))
    assert row.subject == ""
    assert row.notes == "самостійна робота"
    assert "subject_inferred_from_lesson_type" in row.warnings
    accepted, review = partition_rows([row], threshold=0.74)
    assert not accepted
    assert len(review) == 1
    assert "missing_subject" in review[0].qa_flags


def test_normalize_record_moves_session_marker_out_of_valid_subject() -> None:
    asset = DiscoveredAsset(
        source_name="fixture",
        source_kind="zip",
        source_url_or_path="fixtures.zip",
        asset_kind="zip_entry",
        locator="fixtures.zip::demo.xlsx",
        display_name="demo.xlsx",
    )
    fetched = FetchedAsset(asset=asset, content=b"", content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", content_hash="abc", resolved_locator="demo.xlsx")
    record = RawRecord(
        values={
            "program": "Demo",
            "faculty": "FIT",
            "week_type": "Обидва",
            "day": "Понеділок",
            "start_time": "09:30",
            "end_time": "10:50",
            "subject": "Теорія алгоритмів (ЗАЛІК)",
        },
        row_index=3,
        sheet_name="1 курс",
        raw_excerpt="Теорія алгоритмів (ЗАЛІК)",
    )
    row = normalize_record(record, document=ParsedDocument(asset=fetched, sheets=[]))
    assert row.subject == "Теорія алгоритмів"
    assert "Залік" in row.notes


def test_normalize_record_drops_short_service_subject_into_review() -> None:
    asset = DiscoveredAsset(
        source_name="fixture",
        source_kind="zip",
        source_url_or_path="fixtures.zip",
        asset_kind="zip_entry",
        locator="fixtures.zip::demo.xlsx",
        display_name="demo.xlsx",
    )
    fetched = FetchedAsset(asset=asset, content=b"", content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", content_hash="abc", resolved_locator="demo.xlsx")
    record = RawRecord(
        values={
            "program": "Demo",
            "faculty": "History",
            "week_type": "Обидва",
            "day": "Вівторок",
            "start_time": "11:20",
            "end_time": "12:40",
            "subject": "асист.",
            "groups": "Денна форма навчання ; Р О З К Л А Д ; занять студентів історичного факультету",
        },
        row_index=3,
        sheet_name="Лист1",
        raw_excerpt="асист.",
    )
    row = normalize_record(record, document=ParsedDocument(asset=fetched, sheets=[]))
    assert row.subject == ""
    assert row.groups == ""
    accepted, review = partition_rows([row], threshold=0.74)
    assert not accepted
    assert len(review) == 1
    assert "missing_subject" in review[0].qa_flags


def test_normalize_record_drops_self_study_subject_variants_into_review() -> None:
    asset = DiscoveredAsset(
        source_name="fixture",
        source_kind="zip",
        source_url_or_path="fixtures.zip",
        asset_kind="zip_entry",
        locator="fixtures.zip::demo.xlsx",
        display_name="demo.xlsx",
    )
    fetched = FetchedAsset(asset=asset, content=b"", content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", content_hash="abc", resolved_locator="demo.xlsx")
    record = RawRecord(
        values={
            "program": "Маркетинг",
            "faculty": "Економічний факультет",
            "week_type": "Обидва",
            "day": "Середа",
            "start_time": "12:50",
            "end_time": "14:00",
            "subject": "Самостій-на робота",
            "groups": "1 група 24; 2 група 24",
        },
        row_index=3,
        sheet_name="Маркетинг",
        raw_excerpt="Самостій-на робота",
    )
    row = normalize_record(record, document=ParsedDocument(asset=fetched, sheets=[]))
    assert row.subject == ""
    assert "Самостій-на робота" in row.notes
    accepted, review = partition_rows([row], threshold=0.74)
    assert not accepted
    assert len(review) == 1
    assert "missing_subject" in review[0].qa_flags


def test_normalize_record_drops_self_study_subject_with_slash_into_review() -> None:
    asset = DiscoveredAsset(
        source_name="fixture",
        source_kind="zip",
        source_url_or_path="fixtures.zip",
        asset_kind="zip_entry",
        locator="fixtures.zip::demo.xlsx",
        display_name="demo.xlsx",
    )
    fetched = FetchedAsset(asset=asset, content=b"", content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", content_hash="abc", resolved_locator="demo.xlsx")
    record = RawRecord(
        values={
            "program": "Маркетинг",
            "faculty": "Економічний факультет",
            "week_type": "Обидва",
            "day": "Середа",
            "start_time": "12:50",
            "end_time": "14:00",
            "subject": "Самостійна / робота",
            "groups": "1 група 24; 2 група 24",
        },
        row_index=3,
        sheet_name="Маркетинг",
        raw_excerpt="Самостійна / робота",
    )
    row = normalize_record(record, document=ParsedDocument(asset=fetched, sheets=[]))
    assert row.subject == ""
    assert "Самостійна / робота" in row.notes
    accepted, review = partition_rows([row], threshold=0.74)
    assert not accepted
    assert len(review) == 1
    assert "missing_subject" in review[0].qa_flags


def test_normalize_record_drops_program_like_group_payload_when_header_is_noisy() -> None:
    asset = DiscoveredAsset(
        source_name="fixture",
        source_kind="zip",
        source_url_or_path="fixtures.zip",
        asset_kind="zip_entry",
        locator="fixtures.zip::demo.xlsx",
        display_name="demo.xlsx",
    )
    fetched = FetchedAsset(asset=asset, content=b"", content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", content_hash="abc", resolved_locator="demo.xlsx")
    record = RawRecord(
        values={
            "program": "spreadsheets",
            "faculty": "Економічний факультет",
            "week_type": "Обидва",
            "day": "Понеділок",
            "start_time": "14:30",
            "end_time": "15:50",
            "subject": "Поведінкові фінанси",
            "groups": "(заочної форми навчання); проф. Ігнатюк А.І.; настановчої сесії на 2025; 2026 н.р.; Корпоративні фінанси; проф. Науменкова С.В.",
        },
        row_index=3,
        sheet_name="Лист1",
        raw_excerpt="Поведінкові фінанси",
    )
    row = normalize_record(record, document=ParsedDocument(asset=fetched, sheets=[]))
    assert row.groups == ""


def test_normalize_record_keeps_explicit_cluster_from_noisy_groups() -> None:
    asset = DiscoveredAsset(
        source_name="fixture",
        source_kind="zip",
        source_url_or_path="fixtures.zip",
        asset_kind="zip_entry",
        locator="fixtures.zip::demo.xlsx",
        display_name="demo.xlsx",
    )
    fetched = FetchedAsset(asset=asset, content=b"", content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", content_hash="abc", resolved_locator="demo.xlsx")
    record = RawRecord(
        values={
            "program": "Маркетинг",
            "faculty": "Економічний факультет",
            "week_type": "Обидва",
            "day": "Понеділок",
            "start_time": "14:30",
            "end_time": "15:50",
            "subject": "Бренд-менеджмент",
            "groups": "Економічний факультет; Міжнародна економіка; Кластер 1(с); https://us02web.zoom.us/j/12345; « » лютого 2026р.",
        },
        row_index=3,
        sheet_name="Лист1",
        raw_excerpt="Бренд-менеджмент",
    )
    row = normalize_record(record, document=ParsedDocument(asset=fetched, sheets=[]))
    assert row.groups == "Кластер 1(с)"


def test_sanitize_export_rows_recovers_program_from_groups_or_asset_label() -> None:
    accepted = [
        NormalizedRow(
            program="180 1297 5SWbMf",
            faculty="Фізичний факультет",
            week_type="Обидва",
            day="Понеділок",
            start_time="08:40",
            end_time="10:15",
            subject="Фізика наносистем",
            groups="Фізика наносистем",
            course="1",
            sheet_name="Лист1",
            source_name="phys-schedule",
            asset_locator="https://phys.knu.ua/wp-content/uploads/2026/01/knuphystimetable2sem2025x2026v2.xlsx",
        ),
        NormalizedRow(
            program="uploads",
            faculty="Географічний факультет",
            week_type="Обидва",
            day="Вівторок",
            start_time="10:35",
            end_time="12:10",
            subject="Маркетинг",
            groups="3 курс",
            course="3",
            sheet_name="pdf-table-p1-t1",
            source_name="geo-schedule",
            asset_locator="https://geo.knu.ua/wp-content/uploads/2026/02/3-kurs-2-s_2025-2026_turyzm.pdf",
        ),
        NormalizedRow(
            program="wp-content",
            faculty="Географічний факультет",
            week_type="Обидва",
            day="Середа",
            start_time="11:30",
            end_time="12:50",
            subject="Організація екскурсійних послуг (практична)",
            groups="3 курс",
            sheet_name="pdf-table-p1-t1",
            source_name="geo-schedule",
            asset_locator="https://geo.knu.ua/wp-content/uploads/2026/02/3-kurs-2-s_2025-2026_turyzm.pdf",
        ),
        NormalizedRow(
            program="spreadsheets",
            faculty="Економічний факультет",
            week_type="Обидва",
            day="Понеділок",
            start_time="14:30",
            end_time="15:50",
            subject="Поведінкові фінанси",
            groups="Корпоративні фінанси",
            sheet_name="Лист1",
            source_name="econom-schedule",
            asset_locator="https://docs.google.com/spreadsheets/d/1AKcTzSivJkvZ-kOEaX19-PqfHzh4U16N/edit?gid=397191710",
        ),
    ]

    sanitized, review = sanitize_export_rows(accepted, [])

    assert len(sanitized) >= 2
    assert sanitized[0].program == "Фізика наносистем"
    assert all(row.program not in {"uploads", "wp-content", "spreadsheets"} for row in sanitized)
    assert all(not looks_like_bad_program_label(row.program) for row in sanitized)
    assert "program_label_recovered" in sanitized[0].autofix_actions
    assert any("program_label_recovered" in row.autofix_actions for row in sanitized[1:])
    assert all("bad_program_label" in row.qa_flags for row in review)
    assert len(review) == 2


def test_sanitize_export_rows_demotes_unrecoverable_bad_program_label() -> None:
    accepted = [
        NormalizedRow(
            program="2 пара 10.00 11.20",
            faculty="Факультет психології",
            week_type="Обидва",
            day="Середа",
            start_time="10:00",
            end_time="11:20",
            subject="Психологія",
            sheet_name="2 пара 10.00 11.20",
            source_name="psy-schedule",
            asset_locator="https://psy.knu.ua/schedule/view",
        )
    ]

    sanitized, review = sanitize_export_rows(accepted, [])

    assert not sanitized
    assert len(review) == 1
    assert "bad_program_label" in review[0].qa_flags


def test_sanitize_export_rows_demotes_tiny_bad_schedule_bucket() -> None:
    accepted = [
        NormalizedRow(
            program="Начитка",
            faculty="Факультет психології",
            week_type="Обидва",
            day="Четвер",
            start_time="10:00",
            end_time="12:50",
            subject="Клієнтські групи в соціальній роботі",
            sheet_name="Начитка",
            source_name="psy-schedule",
            asset_locator="https://docs.google.com/spreadsheets/d/demo/edit#gid=0",
        )
    ]

    sanitized, review = sanitize_export_rows(accepted, [])

    assert not sanitized
    assert len(review) == 1
    assert "bad_program_label" in review[0].qa_flags


def test_looks_like_bad_program_label_catches_geo_technical_tails() -> None:
    assert looks_like_bad_program_label("03quyIffb4u2KQDbqMZyE9.1")
    assert looks_like_bad_program_label("0aegfNLd3WB.1")
    assert looks_like_bad_program_label("1264456?p=8PUgDjlKBmu7iBeZYc")
    assert looks_like_bad_program_label("kmj_hs=179&authuser=0&hl=ru")
    assert looks_like_bad_program_label("bbz-nrfu-gne ; 308-а ; 02.03.2026")
    assert looks_like_bad_program_label("yjw-wktj-mrf ; .com")
    assert looks_like_bad_program_label("dr. VOLODYMYR SUDAKOV")
    assert looks_like_bad_program_label("ауд. ; ЗАЛІК")
    assert looks_like_bad_program_label("Rozklad ННІВТ 2 25 26")
    assert looks_like_bad_program_label("асист.")
    assert looks_like_bad_program_label(". Губіна К.Є")
    assert looks_like_bad_program_label("3 курс")
    assert looks_like_bad_program_label("ІК_ 884 766 8136 КД")
    assert looks_like_bad_program_label("2 8 вересня (лекціі) 1 ии тиждень")
    assert looks_like_bad_program_label("СІЧЕНЬ ЛЮТИИ")
    assert looks_like_bad_program_label("АНГЛ.МОВА . ауд")
    assert not looks_like_bad_program_label("Економічна географія ; Управління розвитком ; туризму та рекреації")


def test_sanitize_export_rows_ignores_technical_notes_as_program_hint() -> None:
    accepted = [
        NormalizedRow(
            program="03quyIffb4u2KQDbqMZyE9.1",
            faculty="Географічний факультет",
            week_type="Обидва",
            day="Четвер",
            start_time="13:00",
            end_time="14:20",
            subject="Українська та зарубіжна культура (сем)",
            teacher="Мураткіна Т.М.",
            room="ауд. 312",
            notes="03quyIffb4u2KQDbqMZyE9.1",
            sheet_name="pdf-table-p7-t1",
            source_name="geo-schedule",
            asset_locator="https://geo.knu.ua/wp-content/uploads/2026/03/rozklad_2-k_2sem_2025-2026.pdf",
        ),
        NormalizedRow(
            program="0aegfNLd3WB.1",
            faculty="Географічний факультет",
            week_type="Обидва",
            day="Четвер",
            start_time="08:30",
            end_time="09:50",
            subject="ГІС в моніторингових системах (л)",
            teacher="Міхно О.Г.",
            room="ауд. 102",
            notes="0aegfNLd3WB.1",
            sheet_name="pdf-table-p7-t1",
            source_name="geo-schedule",
            asset_locator="https://geo.knu.ua/wp-content/uploads/2026/03/rozklad_2-k_2sem_2025-2026.pdf",
        ),
        NormalizedRow(
            program="bbz-nrfu-gne ; 308-а ; 02.03.2026",
            faculty="Географічний факультет",
            week_type="Обидва",
            day="Вівторок",
            start_time="13:00",
            end_time="14:20",
            subject="Іноземна мова (пр)",
            teacher="Тарасова Н.П.",
            notes="bbz-nrfu-gne ; 308-а ; 02.03.2026",
            sheet_name="pdf-table-p5-t1",
            source_name="geo-schedule",
            asset_locator="https://geo.knu.ua/wp-content/uploads/2026/03/rozklad_3-k_2sem_2025-2026.pdf",
        ),
        NormalizedRow(
            program="yjw-wktj-mrf ; .com",
            faculty="Географічний факультет",
            week_type="Обидва",
            day="Вівторок",
            start_time="10:00",
            end_time="11:20",
            subject="Іноземна мова (пр)",
            teacher="Шевченко О.К.",
            room="ауд. 411",
            notes="yjw-wktj-mrf ; .com",
            sheet_name="pdf-table-p5-t1",
            source_name="geo-schedule",
            asset_locator="https://geo.knu.ua/wp-content/uploads/2026/03/rozklad_1-k_2sem_2025-2026.pdf",
        ),
    ]

    sanitized, review = sanitize_export_rows(accepted, [])

    assert len(sanitized) == 4
    assert not review
    assert all(row.program == "Geo Schedule" for row in sanitized)
    assert all(not looks_like_bad_program_label(row.program) for row in sanitized)
    assert all("program_label_recovered" in row.autofix_actions for row in sanitized)


def test_sanitize_export_rows_recovers_teacher_like_program_to_sheet_name() -> None:
    accepted = [
        NormalizedRow(
            program="dr. VOLODYMYR SUDAKOV",
            faculty="Факультет соціології",
            week_type="Обидва",
            day="Четвер",
            start_time="14:00",
            end_time="15:20",
            subject="CURRENT ISSUES IN SOCIAL SCIENCES",
            teacher="проф. СУДАКОВ В.І.",
            sheet_name="2 mag Sociology 1s 23-24",
            notes="dr. VOLODYMYR SUDAKOV",
            source_name="sociology-schedule",
            asset_locator="https://docs.google.com/spreadsheets/d/demo/edit?usp=sharing",
        )
    ]

    sanitized, review = sanitize_export_rows(accepted, [])

    assert not review
    assert len(sanitized) == 1
    assert sanitized[0].program == "2 mag Sociology 1s 23-24"
    assert "program_label_recovered" in sanitized[0].autofix_actions


def test_sanitize_export_rows_demotes_unrecoverable_rozklad_program() -> None:
    accepted = [
        NormalizedRow(
            program="Rozklad ННІВТ 2 25 26",
            faculty="ННІ високих технологій",
            week_type="Обидва",
            day="Вівторок",
            start_time="12:20",
            end_time="13:55",
            subject="Академічне письмо англійською мовою",
            notes="E1 Біологія та біохімія, E3 Хімія",
            sheet_name="pdf-table-p1-t1",
            source_name="iht-schedule",
            asset_locator="https://iht.knu.ua/wp-content/uploads/2026/02/RozkladННІВТ-2-25-26.pdf",
        )
    ]

    sanitized, review = sanitize_export_rows(accepted, [])

    assert not sanitized
    assert len(review) == 1
    assert "bad_program_label" in review[0].qa_flags


def test_sanitize_export_rows_demotes_tiny_fragmented_geo_program() -> None:
    accepted = [
        NormalizedRow(
            program="використання та ; збереження водних",
            faculty="Географічний факультет",
            week_type="Обидва",
            day="Вівторок",
            start_time="10:35",
            end_time="12:10",
            subject="Управління водними ресурсами",
            sheet_name="pdf-table-p1-t1",
            source_name="geo-schedule",
            asset_locator="https://geo.knu.ua/wp-content/uploads/2026/03/rozklad_2-k_2sem_2025-2026.pdf",
        ),
        NormalizedRow(
            program="використання та ; збереження водних",
            faculty="Географічний факультет",
            week_type="Обидва",
            day="Четвер",
            start_time="10:35",
            end_time="12:10",
            subject="Водна політика",
            sheet_name="pdf-table-p1-t1",
            source_name="geo-schedule",
            asset_locator="https://geo.knu.ua/wp-content/uploads/2026/03/rozklad_2-k_2sem_2025-2026.pdf",
        ),
    ]

    sanitized, review = sanitize_export_rows(accepted, [])

    assert not sanitized
    assert len(review) == 2
    assert all("bad_program_label" in row.qa_flags for row in review)


def test_sanitize_export_rows_rejects_bad_note_based_program_hints() -> None:
    accepted = [
        NormalizedRow(
            program="uploads",
            faculty="Факультет соціології",
            week_type="Обидва",
            day="Вівторок",
            start_time="17:10",
            end_time="18:30",
            subject="МЕТОДИ ЗБОРУ СОЦІОЛОГІЧНИХ ДАНИХ",
            groups="1 група; 2 група",
            notes="АНГЛ.МОВА . ауд.",
            sheet_name="1",
            source_name="sociology-schedule",
            asset_locator="https://docs.google.com/spreadsheets/d/demo/edit?usp=sharing",
        ),
        NormalizedRow(
            program="Rozklad ННІВТ 2 25 26",
            faculty="ННІ високих технологій",
            week_type="Обидва",
            day="Вівторок",
            start_time="11:30",
            end_time="12:50",
            subject="Психологія спілкування",
            notes="091 Біологія / та біохімія",
            sheet_name="pdf-table-p2-t1",
            source_name="iht-schedule",
            asset_locator="https://iht.knu.ua/wp-content/uploads/2026/02/RozkladННІВТ-2-25-26.pdf",
        ),
    ]

    sanitized, review = sanitize_export_rows(accepted, [])

    assert not sanitized
    assert len(review) == 2
    assert all("bad_program_label" in row.qa_flags for row in review)


def test_records_from_tabular_rows_fill_down_merged_schedule_values() -> None:
    rows = [
        ["Тиждень", "День", "Початок", "Кінець", "Назва предмета", "Викладач", "Тип заняття", "Групи", "Курс"],
        ["Обидва", "Понеділок", "09:30", "10:50", "Анатомія", "доц. Іваненко", "лекція", "1", "2"],
        [None, None, None, None, "Біохімія", "ас. Петренко", "семінар", "2", "2"],
    ]
    records, warnings = records_from_tabular_rows(rows, program="Demo", faculty="FIT", sheet_name="1 курс")
    assert not warnings
    assert len(records) == 2
    assert records[1].values["day"] == "Понеділок"
    assert records[1].values["start_time"] == "09:30"
    assert records[1].values["subject"] == "Біохімія"


def test_records_from_tabular_rows_skip_repeated_headers_and_titles() -> None:
    rows = [
        ["Тиждень", "День", "Початок", "Кінець", "Назва предмета", "Викладач", "Тип заняття"],
        ["Соціологічне забезпечення управлінських процесів"],
        ["Тиждень", "День", "Початок", "Кінець", "Назва предмета", "Викладач", "Тип заняття"],
        ["Обидва", "Понеділок", "09:30", "10:50", "Соціологія організацій", "доц. Іваненко", "лекція"],
    ]
    records, warnings = records_from_tabular_rows(rows, program="Demo", faculty="FIT", sheet_name="1 курс")
    assert not warnings
    assert len(records) == 1
    assert records[0].values["subject"] == "Соціологія організацій"


def test_normalize_record_infers_missing_start_time_from_end_time() -> None:
    asset = DiscoveredAsset(
        source_name="fixture",
        source_kind="zip",
        source_url_or_path="fixtures.zip",
        asset_kind="zip_entry",
        locator="fixtures.zip::demo.xlsx",
        display_name="demo.xlsx",
    )
    fetched = FetchedAsset(asset=asset, content=b"", content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", content_hash="abc", resolved_locator="demo.xlsx")
    record = RawRecord(
        values={
            "program": "Demo",
            "faculty": "FIT",
            "day": "Вівторок",
            "end_time": "15:50",
            "subject": "Маркетинг",
            "teacher": "доц. Іваненко",
        },
        row_index=3,
        sheet_name="1 курс",
        raw_excerpt="Маркетинг | 15:50",
    )
    row = normalize_record(record, document=ParsedDocument(asset=fetched, sheets=[]))
    assert row.start_time == "14:30"
    assert row.end_time == "15:50"
    assert "missing_start_time" not in row.warnings
    assert row.confidence >= 0.74


def test_normalize_record_can_infer_non_class_subject_from_notes() -> None:
    asset = DiscoveredAsset(
        source_name="fixture",
        source_kind="zip",
        source_url_or_path="fixtures.zip",
        asset_kind="zip_entry",
        locator="fixtures.zip::demo.xlsx",
        display_name="demo.xlsx",
    )
    fetched = FetchedAsset(asset=asset, content=b"", content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", content_hash="abc", resolved_locator="demo.xlsx")
    record = RawRecord(
        values={
            "program": "Demo",
            "faculty": "FIT",
            "day": "Середа",
            "start_time": "14:30",
            "end_time": "15:50",
            "notes": "ВИХІДНИЙ",
        },
        row_index=3,
        sheet_name="1 курс",
        raw_excerpt="ВИХІДНИЙ",
    )
    row = normalize_record(record, document=ParsedDocument(asset=fetched, sheets=[]))
    assert row.subject == "Вихідний"
    assert "subject_inferred_from_non_class_note" in row.warnings
    assert "missing_subject" not in row.warnings
    assert row.confidence >= 0.74


def test_records_from_tabular_rows_skip_structural_and_informational_rows() -> None:
    rows = [
        ["Тиждень", "День", "Початок", "Кінець", "Назва предмета", "Примітки", "Курс"],
        ["Обидва", "Середа", None, "17:20", None, None, "3"],
        [None, None, None, None, None, "Розклад занять з 23 березня з'явиться пізніше", "1"],
        ["Обидва", "Четвер", "09:30", "10:50", "Мікроекономіка", "", "2"],
    ]
    records, warnings = records_from_tabular_rows(rows, program="Demo", faculty="FIT", sheet_name="1 курс")
    assert not warnings
    assert len(records) == 1
    assert records[0].values["subject"] == "Мікроекономіка"


def test_records_from_tabular_rows_skip_non_schedule_service_rows() -> None:
    rows = [
        ["Тиждень", "День", "Початок", "Кінець", "Назва предмета", "Примітки", "Курс"],
        ["Обидва", "П'ятниця", "14:40", "19:15", "Д Е Н Ь С А М О С Т І Й Н О Ї Р О Б О Т И", "", "2"],
        ["Обидва", "Четвер", "14:40", "16:10", "К у р с з а в и б о р о м :", "", "2"],
        ["Обидва", "Четвер", "09:30", "10:50", "Мікроекономіка", "", "2"],
    ]

    records, warnings = records_from_tabular_rows(rows, program="Demo", faculty="FIT", sheet_name="1 курс")

    assert not warnings
    assert len(records) == 1
    assert records[0].values["subject"] == "Мікроекономіка"


def test_records_from_tabular_rows_skip_non_schedule_service_rows_even_with_course_context() -> None:
    rows = [
        ["Тиждень", "День", "Початок", "Кінець", "Назва предмета", "Примітки", "Курс"],
        ["Обидва", "Субота", "08:00", "12:40", "ДЕНЬ САМОСТІЙНОЇ РОБОТИ", "", "2"],
        ["Обидва", "П'ятниця", "11:20", "12:40", "Курс за вибором: Оцінка бізнесу", "", "2"],
        ["Обидва", "Четвер", "09:30", "10:50", "Мікроекономіка", "", "2"],
    ]

    records, warnings = records_from_tabular_rows(rows, program="Demo", faculty="Econom", sheet_name="Лист1")

    assert not warnings
    assert len(records) == 1
    assert records[0].values["subject"] == "Мікроекономіка"


def test_partition_rows_routes_non_class_marker_without_time_slots_to_review() -> None:
    rows = [
        NormalizedRow(
            program="Demo",
            faculty="FIT",
            week_type="",
            day="Понеділок",
            start_time="",
            end_time="",
            subject="Вихідний",
            notes="Вихідний",
            confidence=0.25,
            warnings=["missing_start_time", "missing_end_time"],
        )
    ]
    accepted, review = partition_rows(rows, threshold=0.74)
    assert not accepted
    assert len(review) == 1
    assert "missing_time" in review[0].qa_flags


def test_normalize_document_drops_non_schedule_service_rows() -> None:
    asset = DiscoveredAsset(
        source_name="history-schedule",
        source_kind="web_page",
        source_url_or_path="https://history.univ.kiev.ua/studentam/schedule/",
        asset_kind="pdf",
        locator="https://history.univ.kiev.ua/files/history.pdf",
        display_name="history.pdf",
    )
    fetched = FetchedAsset(asset=asset, content=b"", content_type="application/pdf", content_hash="abc", resolved_locator="history.pdf")
    document = ParsedDocument(
        asset=fetched,
        sheets=[
            ParsedSheet(
                sheet_name="pdf-table-p1-t1",
                program="Денна форма навчання",
                faculty="Історичний факультет",
                records=[
                    RawRecord(
                        values={
                            "program": "Денна форма навчання",
                            "faculty": "Історичний факультет",
                            "day": "П'ятниця",
                            "start_time": "14:40",
                            "end_time": "19:15",
                            "subject": "Д Е Н Ь С А М О С Т І Й Н О Ї Р О Б О Т И",
                        },
                        row_index=3,
                        sheet_name="pdf-table-p1-t1",
                        raw_excerpt="Д Е Н Ь С А М О С Т І Й Н О Ї Р О Б О Т И",
                    ),
                    RawRecord(
                        values={
                            "program": "Денна форма навчання",
                            "faculty": "Історичний факультет",
                            "day": "Четвер",
                            "start_time": "09:30",
                            "end_time": "10:50",
                            "subject": "Історія України",
                        },
                        row_index=4,
                        sheet_name="pdf-table-p1-t1",
                        raw_excerpt="Історія України",
                    ),
                ],
            )
        ],
    )

    rows = normalize_document(document)

    assert len(rows) == 1
    assert rows[0].subject == "Історія України"


def test_normalize_record_repairs_short_or_reversed_time_slot() -> None:
    asset = DiscoveredAsset(
        source_name="econom-schedule",
        source_kind="web_page",
        source_url_or_path="https://econom.knu.ua/for_students/schedule/rozklad/",
        asset_kind="google_sheet",
        locator="https://docs.google.com/spreadsheets/d/test/edit#gid=0",
        display_name="econom.xlsx",
    )
    fetched = FetchedAsset(
        asset=asset,
        content=b"",
        content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        content_hash="econom",
        resolved_locator="econom.xlsx",
    )
    record = RawRecord(
        values={
            "program": "ПБД",
            "faculty": "Економічний факультет",
            "day": "Понеділок",
            "start_time": "17:20",
            "end_time": "07:50",
            "subject": "Комерціалізація підприємницької ідеї",
            "course": "2",
        },
        row_index=7,
        sheet_name="ПБД",
        raw_excerpt="17:20 | 07:50 | Комерціалізація підприємницької ідеї",
    )

    row = normalize_record(record, document=ParsedDocument(asset=fetched, sheets=[]))

    assert row.start_time == "17:20"
    assert row.end_time == "18:40"
    assert "end_time_repaired" in row.autofix_actions


def test_normalize_record_infers_subject_from_elective_note() -> None:
    asset = DiscoveredAsset(
        source_name="econom-schedule",
        source_kind="web_page",
        source_url_or_path="https://econom.knu.ua/for_students/schedule/rozklad/",
        asset_kind="google_sheet",
        locator="https://docs.google.com/spreadsheets/d/test/edit#gid=0",
        display_name="econom.xlsx",
    )
    fetched = FetchedAsset(
        asset=asset,
        content=b"",
        content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        content_hash="econom",
        resolved_locator="econom.xlsx",
    )
    record = RawRecord(
        values={
            "program": "Фінансовий бізнес",
            "faculty": "Економічний факультет",
            "day": "П'ятниця",
            "start_time": "11:20",
            "end_time": "12:40",
            "teacher": "проф. Чубук Л.П.",
            "room": "ауд.219",
            "course": "4",
            "notes": "Курс за вибором: Оцінка бізнесу; 2",
        },
        row_index=9,
        sheet_name="Лист1",
        raw_excerpt="Курс за вибором: Оцінка бізнесу",
    )

    row = normalize_record(record, document=ParsedDocument(asset=fetched, sheets=[]))

    assert row.subject == "Оцінка бізнесу"
    assert row.notes == "2"


def test_normalize_record_extracts_teacher_and_room_from_composite_subject() -> None:
    asset = DiscoveredAsset(
        source_name="fixture",
        source_kind="zip",
        source_url_or_path="fixtures.zip",
        asset_kind="zip_entry",
        locator="fixtures.zip::demo.xlsx",
        display_name="demo.xlsx",
    )
    fetched = FetchedAsset(asset=asset, content=b"", content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", content_hash="abc", resolved_locator="demo.xlsx")
    record = RawRecord(
        values={
            "program": "Demo",
            "faculty": "Law",
            "day": "Понеділок",
            "start_time": "09:30",
            "end_time": "10:50",
            "subject": "Конституційне право (с) / PhD, ас. Ольшевський І.П. / ауд. 159",
        },
        row_index=5,
        sheet_name="1 курс",
        raw_excerpt="Конституційне право",
    )
    row = normalize_record(record, document=ParsedDocument(asset=fetched, sheets=[]))
    assert row.subject == "Конституційне право (с)"
    assert "Ольшевський" in row.teacher
    assert row.room == "ауд. 159"


def test_partition_rows_marks_contaminated_subject_for_review() -> None:
    row = NormalizedRow(
        program="Demo",
        faculty="Law",
        week_type="Обидва",
        day="Понеділок",
        start_time="09:30",
        end_time="10:50",
        subject="Конституційне право / ауд. 159",
        confidence=0.98,
    )
    accepted, review = partition_rows([row], threshold=0.74)
    assert not accepted
    assert len(review) == 1
    assert "subject_contains_room" in review[0].qa_flags


def test_partition_rows_marks_numeric_subject_for_review() -> None:
    row = NormalizedRow(
        program="Demo",
        faculty="Geo",
        week_type="Обидва",
        day="Понеділок",
        start_time="09:30",
        end_time="10:50",
        subject="313",
        confidence=0.98,
    )
    accepted, review = partition_rows([row], threshold=0.74)
    assert not accepted
    assert len(review) == 1
    assert "garbage_text" in review[0].qa_flags


def test_partition_rows_marks_meeting_code_subject_for_review() -> None:
    row = NormalizedRow(
        program="Demo",
        faculty="Geo",
        week_type="Обидва",
        day="Понеділок",
        start_time="09:30",
        end_time="10:50",
        subject="Meeting ID: 871 2397 5892",
        confidence=0.98,
    )
    accepted, review = partition_rows([row], threshold=0.74)
    assert not accepted
    assert len(review) == 1
    assert any(flag in review[0].qa_flags for flag in ("garbage_text", "service_text_subject", "subject_contains_link"))


def test_partition_rows_marks_long_mixed_subject_for_review() -> None:
    row = NormalizedRow(
        program="Demo",
        faculty="Psy",
        week_type="Обидва",
        day="Середа",
        start_time="10:00",
        end_time="11:20",
        subject="Дизайн психологічного дослідження ----- Дизайн психологічного дослідження (сем.) . 122",
        teacher="доц ; Москаленко А.М. ; лек.....",
        confidence=0.98,
    )
    accepted, review = partition_rows([row], threshold=0.74)
    assert not accepted
    assert len(review) == 1
    assert "inconsistent_columns" in review[0].qa_flags


def test_partition_rows_keeps_english_subject_titles() -> None:
    row = NormalizedRow(
        program="Demo",
        faculty="Соціологія",
        week_type="Обидва",
        day="Понеділок",
        start_time="12:30",
        end_time="13:50",
        subject="GENDER ORDER TRANSFORMATION IN",
        teacher="доц. БАБЕНКО С.С.",
        confidence=0.98,
    )
    accepted, review = partition_rows([row], threshold=0.74)
    assert len(accepted) == 1
    assert not review


def test_normalize_record_can_infer_subject_from_notes_after_cleanup() -> None:
    asset = DiscoveredAsset(
        source_name="fixture",
        source_kind="zip",
        source_url_or_path="fixtures.zip",
        asset_kind="zip_entry",
        locator="fixtures.zip::demo.xlsx",
        display_name="demo.xlsx",
    )
    fetched = FetchedAsset(asset=asset, content=b"", content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", content_hash="abc", resolved_locator="demo.xlsx")
    record = RawRecord(
        values={
            "program": "Demo",
            "faculty": "FIT",
            "day": "Понеділок",
            "start_time": "09:00",
            "end_time": "10:20",
            "teacher": "Жабська Є. О.",
            "notes": "T=11; Комп’ютерна графіка та візуалізація",
        },
        row_index=5,
        sheet_name="1 курс",
        raw_excerpt="Комп’ютерна графіка та візуалізація",
    )
    row = normalize_record(record, document=ParsedDocument(asset=fetched, sheets=[]))
    assert row.subject == "Комп’ютерна графіка та візуалізація"
    assert row.notes == "T=11"


def test_normalize_record_extracts_teacher_from_split_subject_segments() -> None:
    asset = DiscoveredAsset(
        source_name="fixture",
        source_kind="web_page",
        source_url_or_path="https://example.edu/schedule",
        asset_kind="file_url",
        locator="https://example.edu/1.pdf",
        display_name="1.pdf",
    )
    fetched = FetchedAsset(asset=asset, content=b"", content_type="application/pdf", content_hash="abc", resolved_locator="1.pdf")
    record = RawRecord(
        values={
            "program": "Demo",
            "faculty": "Філософський факультет",
            "day": "П'ятниця",
            "start_time": "16:20",
            "end_time": "17:40",
            "subject": "Англ. мова / Даниліна / С.Ю. / 408",
            "teacher": "Доц",
        },
        row_index=5,
        sheet_name="pdf-table",
        raw_excerpt="Англ. мова / Даниліна / С.Ю. / 408",
    )
    row = normalize_record(record, document=ParsedDocument(asset=fetched, sheets=[]))
    assert row.subject == "Англ. мова"
    assert "Даниліна С.Ю." in row.teacher
    assert row.room == "ауд. 408"


def test_normalize_record_extracts_trailing_room_from_subject_tail() -> None:
    asset = DiscoveredAsset(
        source_name="fixture",
        source_kind="web_page",
        source_url_or_path="https://example.edu/schedule",
        asset_kind="file_url",
        locator="https://example.edu/1.pdf",
        display_name="1.pdf",
    )
    fetched = FetchedAsset(asset=asset, content=b"", content_type="application/pdf", content_hash="abc", resolved_locator="1.pdf")
    record = RawRecord(
        values={
            "program": "Demo",
            "faculty": "Geo",
            "day": "Понеділок",
            "start_time": "08:30",
            "end_time": "09:50",
            "subject": "Іноземна мова (пр) / 406",
            "teacher": "Дідковська Т.Л.",
        },
        row_index=5,
        sheet_name="pdf-table",
        raw_excerpt="Іноземна мова (пр) / 406",
    )
    row = normalize_record(record, document=ParsedDocument(asset=fetched, sheets=[]))
    assert row.subject == "Іноземна мова (пр)"
    assert row.room == "ауд. 406"


def test_normalize_record_moves_meeting_codes_out_of_subject() -> None:
    asset = DiscoveredAsset(
        source_name="fixture",
        source_kind="web_page",
        source_url_or_path="https://example.edu/schedule",
        asset_kind="file_url",
        locator="https://example.edu/1.pdf",
        display_name="1.pdf",
    )
    fetched = FetchedAsset(asset=asset, content=b"", content_type="application/pdf", content_hash="abc", resolved_locator="1.pdf")
    record = RawRecord(
        values={
            "program": "Demo",
            "faculty": "Geo",
            "day": "Вівторок",
            "start_time": "10:00",
            "end_time": "11:20",
            "subject": "ІК: 884 766 8136 КД:",
            "teacher": "доц. Моташко Т.П.",
        },
        row_index=5,
        sheet_name="pdf-table",
        raw_excerpt="ІК: 884 766 8136 КД:",
    )
    row = normalize_record(record, document=ParsedDocument(asset=fetched, sheets=[]))
    assert row.subject == ""
    assert "ІК: 884 766 8136 КД:" in row.notes


def test_normalize_record_moves_hyphenated_join_code_out_of_subject() -> None:
    asset = DiscoveredAsset(
        source_name="fixture",
        source_kind="web_page",
        source_url_or_path="https://example.edu/schedule",
        asset_kind="pdf",
        locator="https://example.edu/rex.pdf",
        display_name="rex.pdf",
    )
    fetched = FetchedAsset(asset=asset, content=b"", content_type="application/pdf", content_hash="abc", resolved_locator="rex.pdf")
    record = RawRecord(
        values={
            "program": "Demo",
            "faculty": "REX",
            "day": "Monday",
            "start_time": "09:30",
            "end_time": "10:50",
            "subject": "Security systems / operation and support / practice methods (lek.) / ugb-wppy-tnj",
        },
        row_index=5,
        sheet_name="pdf-table",
        raw_excerpt="Security systems / operation and support / practice methods (lek.) / ugb-wppy-tnj",
    )

    row = normalize_record(record, document=ParsedDocument(asset=fetched, sheets=[]))

    assert row.subject == "Security systems operation and support practice methods (lek.)"
    assert "ugb-wppy-tnj" in row.notes


def test_partition_rows_keeps_wrapped_rex_subject_with_lesson_marker() -> None:
    row = NormalizedRow(
        program="Demo",
        faculty="REX",
        week_type="Both",
        day="Monday",
        start_time="09:30",
        end_time="10:50",
        subject="Testing and expertise / of information security means / (lek.)",
        confidence=0.98,
    )

    accepted, review = partition_rows([row], threshold=0.74)

    assert len(accepted) == 1
    assert not review
    assert "inconsistent_columns" not in accepted[0].qa_flags


def test_normalize_record_does_not_infer_abbreviated_subject_from_notes() -> None:
    asset = DiscoveredAsset(
        source_name="fit-schedule",
        source_kind="google_sheet",
        source_url_or_path="https://fit.knu.ua/for-students/lessons-schedule",
        asset_kind="google_sheet",
        locator="https://docs.google.com/spreadsheets/d/test/edit#gid=0",
        display_name="fit.xlsx",
    )
    fetched = FetchedAsset(
        asset=asset,
        content=b"",
        content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        content_hash="fit",
        resolved_locator="fit.xlsx",
    )
    record = RawRecord(
        values={
            "program": "ІР, ВЕБ, ІРма",
            "faculty": "Факультет інформаційних технологій",
            "day": "П'ятниця",
            "start_time": "09:00",
            "end_time": "10:20",
            "notes": "Ст.",
            "teacher": "Михальчук В.В.",
            "room": "307 ауд.",
        },
        row_index=5,
        sheet_name="ІР, ВЕБ, ІРма",
        raw_excerpt="Ст.",
    )

    row = normalize_record(record, document=ParsedDocument(asset=fetched, sheets=[]))

    assert row.subject == ""
    assert "missing_subject" in row.warnings


def test_normalize_record_normalizes_trailing_auditory_room_format() -> None:
    asset = DiscoveredAsset(
        source_name="fit-schedule",
        source_kind="google_sheet",
        source_url_or_path="https://fit.knu.ua/for-students/lessons-schedule",
        asset_kind="google_sheet",
        locator="https://docs.google.com/spreadsheets/d/test/edit#gid=0",
        display_name="fit.xlsx",
    )
    fetched = FetchedAsset(
        asset=asset,
        content=b"",
        content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        content_hash="fit",
        resolved_locator="fit.xlsx",
    )
    record = RawRecord(
        values={
            "program": "ІПЗ, ІПЗм",
            "faculty": "Факультет інформаційних технологій",
            "day": "Понеділок",
            "start_time": "09:00",
            "end_time": "10:20",
            "subject": "Архітектура комп'ютера",
            "teacher": "Вовна О. В.",
            "room": "203 ауд.",
        },
        row_index=5,
        sheet_name="ІПЗ, ІПЗм",
        raw_excerpt="Архітектура комп'ютера",
    )

    row = normalize_record(record, document=ParsedDocument(asset=fetched, sheets=[]))

    assert row.room == "ауд. 203"


def test_partition_rows_moves_teacher_contamination_to_review() -> None:
    row = NormalizedRow(
        program="Demo",
        faculty="Psy",
        week_type="Обидва",
        day="Вівторок",
        start_time="14:30",
        end_time="15:50",
        subject="Базова загальновійськова підготовка",
        teacher="ас.; Бутенко Н.В.; Проектний менеджмент в соціальній роботі (прак) . 406",
        confidence=0.98,
    )
    accepted, review = partition_rows([row], threshold=0.74)
    assert not accepted
    assert len(review) == 1
    assert "inconsistent_columns" in review[0].qa_flags


def test_partition_rows_moves_pwd_fragment_subject_to_review() -> None:
    row = NormalizedRow(
        program="Geo Schedule",
        faculty="Географічний факультет",
        week_type="Обидва",
        day="Середа",
        start_time="08:30",
        end_time="09:50",
        subject="300?pwd=d2ZkMkxmYm5WdWIzcE",
        confidence=0.98,
    )
    accepted, review = partition_rows([row], threshold=0.74)
    assert not accepted
    assert len(review) == 1
    assert "garbage_text" in review[0].qa_flags


def test_partition_rows_moves_abbreviated_subject_to_review() -> None:
    row = NormalizedRow(
        program="ІР, ВЕБ, ІРма",
        faculty="Факультет інформаційних технологій",
        week_type="Обидва",
        day="П'ятниця",
        start_time="09:00",
        end_time="10:20",
        subject="Ст.",
        confidence=0.98,
    )

    accepted, review = partition_rows([row], threshold=0.74)

    assert not accepted
    assert len(review) == 1
    assert "garbage_text" in review[0].qa_flags


def test_refine_group_quality_demotes_fragmented_pdf_slot_rows() -> None:
    accepted = [
        NormalizedRow(
            program="Geo Schedule",
            faculty="Географічний факультет",
            week_type="Обидва",
            day="Понеділок",
            start_time="10:00",
            end_time="11:20",
            subject="Картографія",
            sheet_name="pdf-table-p1-t1",
            source_root_url="https://geo.knu.ua/navchannya/rozklad-zanyat/",
            asset_locator="https://geo.knu.ua/file.pdf",
            confidence=0.98,
        ),
        NormalizedRow(
            program="Geo Schedule",
            faculty="Географічний факультет",
            week_type="Обидва",
            day="Понеділок",
            start_time="10:00",
            end_time="11:20",
            subject="з основами топографії (л)",
            sheet_name="pdf-table-p1-t1",
            source_root_url="https://geo.knu.ua/navchannya/rozklad-zanyat/",
            asset_locator="https://geo.knu.ua/file.pdf",
            confidence=0.98,
        ),
    ]
    refined_accepted, review = refine_group_quality(accepted, [])
    assert not refined_accepted
    assert len(review) == 2
    assert all("inconsistent_columns" in row.qa_flags for row in review)


def test_normalize_record_uses_note_program_hint_for_technical_source_label() -> None:
    asset = DiscoveredAsset(
        source_name="history-schedule",
        source_kind="web_page",
        source_url_or_path="https://history.univ.kiev.ua/studentam/schedule/",
        asset_kind="pdf",
        locator="https://drive.google.com/file/d/11PUXfSjYa15alOPW0fU7PvM5cs-ZQVB6/view?usp=drivesdk",
        display_name="https: / / drive.google.com / file / d / 11PUXfSjYa15alOPW0fU7PvM5cs-ZQVB6 / view?usp=drivesdk",
    )
    fetched = FetchedAsset(asset=asset, content=b"", content_type="application/pdf", content_hash="abc", resolved_locator="history.pdf")
    record = RawRecord(
        values={
            "faculty": "Історичний факультет",
            "day": "Понеділок",
            "start_time": "13:05",
            "end_time": "14:25",
            "subject": "Академічне письмо англійською мовою",
            "notes": "032 Історія та археологія",
        },
        row_index=3,
        sheet_name="pdf-table-p1-t1",
        raw_excerpt="Академічне письмо англійською мовою",
    )
    row = normalize_record(record, document=ParsedDocument(asset=fetched, sheets=[]))
    assert row.program == "032 Історія та археологія"


def test_normalize_record_moves_trailing_program_codes_out_of_subject() -> None:
    asset = DiscoveredAsset(
        source_name="iht-schedule",
        source_kind="web_page",
        source_url_or_path="https://iht.knu.ua",
        asset_kind="pdf",
        locator="https://iht.knu.ua/wp-content/uploads/2026/02/RozkladННІВТ-2-25-26.pdf",
        display_name="https: / / iht.knu.ua / wp-content / uploads / 2026 / 02 / RozkladННІВТ-2-25-26.pdf",
    )
    fetched = FetchedAsset(asset=asset, content=b"", content_type="application/pdf", content_hash="abc", resolved_locator="iht.pdf")
    record = RawRecord(
        values={
            "day": "Вівторок",
            "start_time": "09:00",
            "end_time": "10:20",
            "subject": "Професійне проектне управління науковими дослідженнями 102 Хімія",
        },
        row_index=3,
        sheet_name="pdf-table-p1-t1",
        raw_excerpt="Професійне проектне управління науковими дослідженнями 102 Хімія",
    )
    row = normalize_record(record, document=ParsedDocument(asset=fetched, sheets=[]))
    assert row.program == "102 Хімія"
    assert row.subject == "Професійне проектне управління науковими дослідженнями"
    assert "102 Хімія" in row.notes


def test_partition_rows_moves_admin_subject_to_review() -> None:
    row = NormalizedRow(
        program="Постійний",
        faculty="Факультет психології",
        week_type="Обидва",
        day="П'ятниця",
        start_time="17:30",
        end_time="18:50",
        subject="В.о. декана факультету психології Іван ДАНИЛЮК",
        confidence=0.98,
    )
    accepted, review = partition_rows([row], threshold=0.74)
    assert not accepted
    assert len(review) == 1
    assert "service_text_subject" in review[0].qa_flags


def test_partition_rows_moves_roomish_subject_to_review() -> None:
    row = NormalizedRow(
        program="Лист1",
        faculty="Фізичний факультет",
        week_type="Обидва",
        day="Понеділок",
        start_time="10:35",
        end_time="11:55",
        subject="108 л",
        confidence=0.98,
    )
    accepted, review = partition_rows([row], threshold=0.74)
    assert not accepted
    assert len(review) == 1
    assert "subject_contains_room" in review[0].qa_flags


def test_partition_rows_moves_auditory_fragment_subject_to_review() -> None:
    row = NormalizedRow(
        program="ІПЗ, ІПЗм",
        faculty="Факультет інформаційних технологій",
        week_type="Обидва",
        day="Вівторок",
        start_time="12:10",
        end_time="13:30",
        subject="113 ауд.",
        confidence=0.98,
    )
    accepted, review = partition_rows([row], threshold=0.74)
    assert not accepted
    assert len(review) == 1
    assert "subject_contains_room" in review[0].qa_flags


def test_partition_rows_moves_implausible_time_to_review() -> None:
    row = NormalizedRow(
        program="Постійний",
        faculty="Факультет психології",
        week_type="Обидва",
        day="Вівторок",
        start_time="02:12",
        end_time="03:32",
        subject="День самостійної роботи",
        confidence=0.98,
    )
    accepted, review = partition_rows([row], threshold=0.74)
    assert not accepted
    assert len(review) == 1
    assert "implausible_time" in review[0].qa_flags


def test_partition_rows_moves_spaced_weekday_subject_to_review() -> None:
    row = NormalizedRow(
        program="English",
        faculty="Факультет соціології",
        week_type="Обидва",
        day="Понеділок",
        start_time="09:00",
        end_time="10:20",
        subject="M O N D A Y",
        confidence=0.98,
    )
    accepted, review = partition_rows([row], threshold=0.74)
    assert not accepted
    assert len(review) == 1
    assert "service_text_subject" in review[0].qa_flags


def test_partition_rows_keeps_extended_qualification_work_slot() -> None:
    row = NormalizedRow(
        program="Лист1",
        faculty="Фізичний факультет",
        week_type="Обидва",
        day="П'ятниця",
        start_time="08:40",
        end_time="13:55",
        subject="Кваліфікаційна робота магістра",
        confidence=0.98,
    )
    accepted, review = partition_rows([row], threshold=0.74)
    assert len(accepted) == 1
    assert not review


def test_normalize_record_replaces_bad_program_alias_with_non_bad_fallback() -> None:
    asset = DiscoveredAsset(
        source_name="psy-schedule",
        source_kind="web_page",
        source_url_or_path="https://psy.knu.ua/study/schedule",
        asset_kind="xlsx",
        locator="https://psy.knu.ua/uploads/psy.xlsx",
        display_name="НАЧИТКА!!!.xlsx",
    )
    fetched = FetchedAsset(asset=asset, content=b"", content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", content_hash="abc", resolved_locator="psy.xlsx")
    record = RawRecord(
        values={
            "program": "НАЧИТКА!!!",
            "day": "Понеділок",
            "start_time": "09:00",
            "end_time": "10:20",
            "subject": "Психологія розвитку",
        },
        row_index=3,
        sheet_name="Лист1",
        raw_excerpt="Психологія розвитку",
    )
    row = normalize_record(record, document=ParsedDocument(asset=fetched, sheets=[]))
    assert row.program
    assert row.program != "Начитка"
    assert not looks_like_bad_program_label(row.program)


def test_normalize_record_rejects_incomplete_program_hint_tail() -> None:
    asset = DiscoveredAsset(
        source_name="history-schedule",
        source_kind="web_page",
        source_url_or_path="https://history.univ.kiev.ua/studentam/schedule/",
        asset_kind="pdf",
        locator="https://drive.google.com/file/d/11PUXfSjYa15alOPW0fU7PvM5cs-ZQVB6/view?usp=drivesdk",
        display_name="history.pdf",
    )
    fetched = FetchedAsset(asset=asset, content=b"", content_type="application/pdf", content_hash="abc", resolved_locator="history.pdf")
    record = RawRecord(
        values={
            "day": "Середа",
            "start_time": "14:40",
            "end_time": "16:00",
            "subject": "Цивілізаційні процеси в Європі 032 Історія та",
        },
        row_index=4,
        sheet_name="pdf-table-p1-t1",
        raw_excerpt="Цивілізаційні процеси в Європі 032 Історія та",
    )
    row = normalize_record(record, document=ParsedDocument(asset=fetched, sheets=[]))
    assert row.subject == "Цивілізаційні процеси в Європі"
    assert row.program != "032 Історія та"


def test_normalize_record_recovers_program_hint_from_neighboring_note_segment() -> None:
    asset = DiscoveredAsset(
        source_name="history-schedule",
        source_kind="web_page",
        source_url_or_path="https://history.univ.kiev.ua/studentam/schedule/",
        asset_kind="pdf",
        locator="https://drive.google.com/file/d/11PUXfSjYa15alOPW0fU7PvM5cs-ZQVB6/view?usp=drivesdk",
        display_name="view?usp=drivesdk",
    )
    fetched = FetchedAsset(asset=asset, content=b"", content_type="application/pdf", content_hash="abc", resolved_locator="history.pdf")
    record = RawRecord(
        values={
            "faculty": "Історичний факультет",
            "day": "Середа",
            "start_time": "14:40",
            "end_time": "16:00",
            "subject": "Цивілізаційні процеси в Європі 032 Історія та",
            "teacher": "Конта Р.М.; проф",
            "notes": "археологія ; д.і.н., .; 032 Історія та",
        },
        row_index=4,
        sheet_name="pdf-table-p1-t1",
        raw_excerpt="https://drive.google.com/file/d/11PUXfSjYa15alOPW0fU7PvM5cs-ZQVB6/view?usp=drivesdk | Історичний факультет | Середа | 14:40 | 16:00 | Цивілізаційні процеси в Європі 032 Історія та археологія ; проф. Конта Р.М.",
    )
    row = normalize_record(record, document=ParsedDocument(asset=fetched, sheets=[]))
    assert row.subject == "Цивілізаційні процеси в Європі"
    assert row.program == "032 Історія та археологія"


def test_normalize_record_moves_lesson_and_subject_fragments_out_of_teacher_field() -> None:
    asset = DiscoveredAsset(
        source_name="fit-schedule",
        source_kind="google_sheet",
        source_url_or_path="https://fit.knu.ua/for-students/lessons-schedule",
        asset_kind="google_sheet",
        locator="https://docs.google.com/spreadsheets/d/test/edit#gid=0",
        display_name="fit.xlsx",
    )
    fetched = FetchedAsset(
        asset=asset,
        content=b"",
        content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        content_hash="fit",
        resolved_locator="fit.xlsx",
    )
    record = RawRecord(
        values={
            "program": "\u0406\u041f\u0417, \u0406\u041f\u0417\u043c",
            "faculty": "\u0424\u0430\u043a\u0443\u043b\u044c\u0442\u0435\u0442 \u0456\u043d\u0444\u043e\u0440\u043c\u0430\u0446\u0456\u0439\u043d\u0438\u0445 \u0442\u0435\u0445\u043d\u043e\u043b\u043e\u0433\u0456\u0439",
            "day": "\u041f\u043e\u043d\u0435\u0434\u0456\u043b\u043e\u043a",
            "start_time": "13:40",
            "end_time": "15:00",
            "subject": "\u0412\u0435\u0440\u0438\u0444\u0456\u043a\u0430\u0446\u0456\u044f \u0442\u0430 \u0432\u0430\u043b\u0456\u0434\u0430\u0446\u0456\u044f \u043f\u0440\u043e\u0433\u0440\u0430\u043c\u043d\u0438\u0445 \u0441\u0438\u0441\u0442\u0435\u043c",
            "teacher": "\u0406\u0432\u0430\u043d\u043e\u0432 \u0404. \u0412. ; (\u043b\u0430\u0431) ; \u0421\u0443\u0447\u0430\u0441\u043d\u0456 \u0431\u0430\u0437\u0438 \u0434\u0430\u043d\u0438\u0445 (\u041b) 8\u0442",
        },
        row_index=5,
        sheet_name="\u0406\u041f\u0417, \u0406\u041f\u0417\u043c",
        raw_excerpt="fit composite teacher",
    )

    row = normalize_record(record, document=ParsedDocument(asset=fetched, sheets=[]))

    assert "\u0406\u0432\u0430\u043d\u043e\u0432" in row.teacher
    assert "\u043b\u0430\u0431" not in row.teacher.casefold()
    assert "\u0421\u0443\u0447\u0430\u0441\u043d\u0456 \u0431\u0430\u0437\u0438 \u0434\u0430\u043d\u0438\u0445" not in row.teacher
    assert "\u0421\u0443\u0447\u0430\u0441\u043d\u0456 \u0431\u0430\u0437\u0438 \u0434\u0430\u043d\u0438\u0445" in row.notes


def test_sanitize_export_rows_demotes_tiny_iht_code_bucket() -> None:
    row = NormalizedRow(
        program="091 Біологія",
        faculty="ННІ високих технологій",
        week_type="Обидва",
        day="Понеділок",
        start_time="09:00",
        end_time="10:20",
        subject="Психологія спілкування",
        confidence=0.98,
        source_name="iht-schedule",
        source_root_url="https://iht.knu.ua/rozklad",
        asset_locator="https://iht.knu.ua/wp-content/uploads/iht.pdf",
        sheet_name="pdf-table-p2-t1",
        notes="091 Біологія / та біохімія",
    )

    accepted, review = sanitize_export_rows([row], [])

    assert not accepted
    assert len(review) == 1
    assert "bad_program_label" in review[0].qa_flags


def test_sanitize_export_rows_demotes_tiny_program_with_lesson_suffix() -> None:
    row = NormalizedRow(
        program="СФЕРІ ЕКОНОМІКИ (Л)",
        faculty="Факультет соціології",
        week_type="Обидва",
        day="Вівторок",
        start_time="11:00",
        end_time="12:20",
        subject="Економічна соціологія",
        confidence=0.98,
        source_name="sociology-schedule",
        source_root_url="https://sociology.knu.ua/uk/students",
        asset_locator="https://docs.google.com/spreadsheets/d/test/edit#gid=0",
        sheet_name="English",
    )

    accepted, review = sanitize_export_rows([row], [])

    assert not accepted
    assert len(review) == 1
    assert "bad_program_label" in review[0].qa_flags


def test_sanitize_export_rows_demotes_tiny_lowercase_fragment_program() -> None:
    row = NormalizedRow(
        program="зондування Землі",
        faculty="Географічний факультет",
        week_type="Обидва",
        day="Четвер",
        start_time="12:20",
        end_time="13:55",
        subject="Основи топографії",
        confidence=0.98,
        source_name="geo-schedule",
        source_root_url="https://geo.knu.ua/navchannya/rozklad-zanyat/",
        asset_locator="https://geo.knu.ua/wp-content/uploads/2026/03/rozklad.pdf",
        sheet_name="pdf-table-p4-t1",
    )

    accepted, review = sanitize_export_rows([row], [])

    assert not accepted
    assert len(review) == 1
    assert "bad_program_label" in review[0].qa_flags
