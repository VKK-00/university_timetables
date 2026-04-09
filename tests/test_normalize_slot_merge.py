from timetable_scraper.models import DiscoveredAsset, FetchedAsset, ParsedDocument, ParsedSheet, RawRecord
from timetable_scraper.normalize import normalize_document


def _make_document(records: list[RawRecord]) -> ParsedDocument:
    asset = DiscoveredAsset(
        source_name="law-schedule",
        source_kind="web_page",
        source_url_or_path="https://law.knu.ua/schedule/",
        asset_kind="file_url",
        locator="https://law.knu.ua/wp-content/uploads/law.pdf",
        display_name="law.pdf",
        source_root_url="https://law.knu.ua/schedule/",
    )
    fetched = FetchedAsset(
        asset=asset,
        content=b"",
        content_type="application/pdf",
        content_hash="law",
        resolved_locator=asset.locator,
    )
    sheet = ParsedSheet(sheet_name="pdf-table-p1-t1", program="Право", faculty="Юридичний факультет", records=records)
    return ParsedDocument(asset=fetched, sheets=[sheet])


def test_normalize_document_merges_unambiguous_metadata_only_slot_row() -> None:
    records = [
        RawRecord(
            values={
                "program": "Право",
                "faculty": "Юридичний факультет",
                "day": "Вівторок",
                "start_time": "09:40",
                "end_time": "11:00",
                "subject": "Науковий образ світу (л)",
                "groups": "IПОТІК",
            },
            row_index=3,
            sheet_name="pdf-table-p1-t1",
            raw_excerpt="subject row",
        ),
        RawRecord(
            values={
                "program": "Право",
                "faculty": "Юридичний факультет",
                "day": "Вівторок",
                "start_time": "09:40",
                "end_time": "11:00",
                "teacher": "доц. Заярна І. С.",
                "room": "ауд. 403",
                "groups": "IПОТІК",
            },
            row_index=4,
            sheet_name="pdf-table-p1-t1",
            raw_excerpt="metadata row",
        ),
    ]

    rows = normalize_document(_make_document(records))

    assert len(rows) == 1
    assert rows[0].subject == "Науковий образ світу (л)"
    assert rows[0].teacher == "доц. Заярна І. С."
    assert rows[0].room == "ауд. 403"
    assert "slot_metadata_merged" in rows[0].autofix_actions


def test_normalize_document_keeps_ambiguous_metadata_only_slot_row() -> None:
    records = [
        RawRecord(
            values={
                "program": "Право",
                "faculty": "Юридичний факультет",
                "day": "Вівторок",
                "start_time": "09:40",
                "end_time": "11:00",
                "subject": "Науковий образ світу (л)",
                "groups": "IПОТІК",
            },
            row_index=3,
            sheet_name="pdf-table-p1-t1",
            raw_excerpt="subject row 1",
        ),
        RawRecord(
            values={
                "program": "Право",
                "faculty": "Юридичний факультет",
                "day": "Вівторок",
                "start_time": "09:40",
                "end_time": "11:00",
                "subject": "Філософія права (с)",
                "groups": "IПОТІК",
            },
            row_index=4,
            sheet_name="pdf-table-p1-t1",
            raw_excerpt="subject row 2",
        ),
        RawRecord(
            values={
                "program": "Право",
                "faculty": "Юридичний факультет",
                "day": "Вівторок",
                "start_time": "09:40",
                "end_time": "11:00",
                "teacher": "доц. Заярна І. С.",
                "room": "ауд. 403",
                "groups": "IПОТІК",
            },
            row_index=5,
            sheet_name="pdf-table-p1-t1",
            raw_excerpt="metadata row",
        ),
    ]

    rows = normalize_document(_make_document(records))

    assert len(rows) == 3
    metadata_rows = [row for row in rows if not row.subject]
    assert len(metadata_rows) == 1
    assert metadata_rows[0].room == "ауд. 403"
