from timetable_scraper.models import DiscoveredAsset, FetchedAsset, ParsedDocument, RawRecord
from timetable_scraper.normalize import normalize_record


def _make_document() -> ParsedDocument:
    asset = DiscoveredAsset(
        source_name="rex-schedule",
        source_kind="web_page",
        source_url_or_path="https://rex.knu.ua/for-students/class-times/",
        asset_kind="file_url",
        locator="https://rex.knu.ua/wp-content/uploads/rex.pdf",
        display_name="rex.pdf",
        source_root_url="https://rex.knu.ua/for-students/class-times/",
    )
    fetched = FetchedAsset(
        asset=asset,
        content=b"",
        content_type="application/pdf",
        content_hash="rex",
        resolved_locator=asset.locator,
    )
    return ParsedDocument(asset=fetched, sheets=[])


def test_normalize_record_moves_leading_teacher_out_of_rex_subject() -> None:
    record = RawRecord(
        values={
            "program": "E6",
            "faculty": "Радіофізичний факультет",
            "day": "Середа",
            "start_time": "08:40",
            "end_time": "10:15",
            "subject": "Лень Ю.А / Мікро- та / наноелектроніка / (лек.) інд. граф.",
        },
        row_index=3,
        sheet_name="pdf-table-p2-t1",
        raw_excerpt="E6 | Середа | 08:40 | 10:15 | Лень Ю.А / Мікро- та / наноелектроніка / (лек.) інд. граф.",
    )

    row = normalize_record(record, document=_make_document())

    assert row.teacher == "Лень Ю.А"
    assert row.subject == "Мікро- та наноелектроніка інд. граф."
    assert row.lesson_type == "лекція"
    assert "teacher_from_subject" in row.autofix_actions
    assert "subject_cleaned" in row.autofix_actions


def test_normalize_record_keeps_non_teacher_wrapped_subject_intact() -> None:
    record = RawRecord(
        values={
            "program": "E6",
            "faculty": "Радіофізичний факультет",
            "day": "Середа",
            "start_time": "08:40",
            "end_time": "10:15",
            "subject": "Мікро- та / наноелектроніка / (лек.) інд. граф.",
        },
        row_index=3,
        sheet_name="pdf-table-p2-t1",
        raw_excerpt="E6 | Середа | 08:40 | 10:15 | Мікро- та / наноелектроніка / (лек.) інд. граф.",
    )

    row = normalize_record(record, document=_make_document())

    assert row.teacher == ""
    assert row.subject == "Мікро- та наноелектроніка інд. граф."
    assert row.lesson_type == "лекція"
