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


def test_normalize_record_repairs_split_teacher_prefix_between_subject_and_teacher() -> None:
    record = RawRecord(
        values={
            "program": "F7",
            "faculty": "Радіофізичний факультет",
            "day": "Середа",
            "start_time": "08:40",
            "end_time": "10:15",
            "subject": "Мар’ / Безпека / комп’ютерних / мереж та / систем (лек.)",
            "teacher": "яновський В.А.",
        },
        row_index=3,
        sheet_name="pdf-table-p2-t1",
        raw_excerpt="split teacher prefix row",
    )

    row = normalize_record(record, document=_make_document())

    assert row.subject == "Безпека комп’ютерних мереж та систем"
    assert row.lesson_type == "лекція"
    assert row.teacher == "Мар’яновський В.А."
    assert "subject_cleaned" in row.autofix_actions


def test_normalize_record_moves_curly_apostrophe_teacher_out_of_subject() -> None:
    record = RawRecord(
        values={
            "program": "F7",
            "faculty": "Радіофізичний факультет",
            "day": "Середа",
            "start_time": "08:40",
            "end_time": "10:15",
            "subject": "Мар’яновський В.А. / Безпека / комп’ютерних / мереж та / систем (лек.)",
        },
        row_index=4,
        sheet_name="pdf-table-p2-t1",
        raw_excerpt="curly apostrophe teacher row",
    )

    row = normalize_record(record, document=_make_document())

    assert row.subject == "Безпека комп’ютерних мереж та систем"
    assert row.lesson_type == "лекція"
    assert row.teacher == "Мар’яновський В.А."
    assert "teacher_from_subject" in row.autofix_actions
