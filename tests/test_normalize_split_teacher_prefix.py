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
            "faculty": "\u0420\u0430\u0434\u0456\u043e\u0444\u0456\u0437\u0438\u0447\u043d\u0438\u0439 \u0444\u0430\u043a\u0443\u043b\u044c\u0442\u0435\u0442",
            "day": "\u0421\u0435\u0440\u0435\u0434\u0430",
            "start_time": "08:40",
            "end_time": "10:15",
            "subject": "\u041c\u0430\u0440\u2019 / \u0411\u0435\u0437\u043f\u0435\u043a\u0430 / \u043a\u043e\u043c\u043f\u2019\u044e\u0442\u0435\u0440\u043d\u0438\u0445 / \u043c\u0435\u0440\u0435\u0436 \u0442\u0430 / \u0441\u0438\u0441\u0442\u0435\u043c (\u043b\u0435\u043a.)",
            "teacher": "\u044f\u043d\u043e\u0432\u0441\u044c\u043a\u0438\u0439 \u0412.\u0410.",
        },
        row_index=3,
        sheet_name="pdf-table-p2-t1",
        raw_excerpt="split teacher prefix row",
    )

    row = normalize_record(record, document=_make_document())

    assert row.subject == "\u0411\u0435\u0437\u043f\u0435\u043a\u0430 \u043a\u043e\u043c\u043f\u2019\u044e\u0442\u0435\u0440\u043d\u0438\u0445 \u043c\u0435\u0440\u0435\u0436 \u0442\u0430 \u0441\u0438\u0441\u0442\u0435\u043c (\u043b\u0435\u043a.)"
    assert row.teacher == "\u041c\u0430\u0440\u2019\u044f\u043d\u043e\u0432\u0441\u044c\u043a\u0438\u0439 \u0412.\u0410."
    assert "subject_cleaned" in row.autofix_actions


def test_normalize_record_moves_curly_apostrophe_teacher_out_of_subject() -> None:
    record = RawRecord(
        values={
            "program": "F7",
            "faculty": "\u0420\u0430\u0434\u0456\u043e\u0444\u0456\u0437\u0438\u0447\u043d\u0438\u0439 \u0444\u0430\u043a\u0443\u043b\u044c\u0442\u0435\u0442",
            "day": "\u0421\u0435\u0440\u0435\u0434\u0430",
            "start_time": "08:40",
            "end_time": "10:15",
            "subject": "\u041c\u0430\u0440\u2019\u044f\u043d\u043e\u0432\u0441\u044c\u043a\u0438\u0439 \u0412.\u0410. / \u0411\u0435\u0437\u043f\u0435\u043a\u0430 / \u043a\u043e\u043c\u043f\u2019\u044e\u0442\u0435\u0440\u043d\u0438\u0445 / \u043c\u0435\u0440\u0435\u0436 \u0442\u0430 / \u0441\u0438\u0441\u0442\u0435\u043c (\u043b\u0435\u043a.)",
        },
        row_index=4,
        sheet_name="pdf-table-p2-t1",
        raw_excerpt="curly apostrophe teacher row",
    )

    row = normalize_record(record, document=_make_document())

    assert row.subject == "\u0411\u0435\u0437\u043f\u0435\u043a\u0430 \u043a\u043e\u043c\u043f\u2019\u044e\u0442\u0435\u0440\u043d\u0438\u0445 \u043c\u0435\u0440\u0435\u0436 \u0442\u0430 \u0441\u0438\u0441\u0442\u0435\u043c (\u043b\u0435\u043a.)"
    assert row.teacher == "\u041c\u0430\u0440\u2019\u044f\u043d\u043e\u0432\u0441\u044c\u043a\u0438\u0439 \u0412.\u0410."
    assert "teacher_from_subject" in row.autofix_actions
