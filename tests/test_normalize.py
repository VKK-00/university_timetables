from __future__ import annotations

from timetable_scraper.normalize import map_headers, normalize_record, records_from_tabular_rows, score_record
from timetable_scraper.models import DiscoveredAsset, FetchedAsset, NormalizedRow, ParsedDocument, RawRecord
from timetable_scraper.qa import partition_rows, refine_group_quality
from timetable_scraper.utils import clean_numeric_artifact, flatten_multiline, parse_time_value


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


def test_normalize_record_can_infer_subject_from_lesson_type() -> None:
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
    assert row.subject == "самостійна робота"
    assert "subject_inferred_from_lesson_type" in row.warnings
    assert row.confidence >= 0.74


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
    assert "garbage_text" in review[0].qa_flags


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
