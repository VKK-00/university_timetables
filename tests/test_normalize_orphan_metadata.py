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
    sheet = ParsedSheet(
        sheet_name="pdf-table-p1-t1",
        program="\u041f\u0440\u0430\u0432\u043e",
        faculty="\u042e\u0440\u0438\u0434\u0438\u0447\u043d\u0438\u0439 \u0444\u0430\u043a\u0443\u043b\u044c\u0442\u0435\u0442",
        records=records,
    )
    return ParsedDocument(asset=fetched, sheets=[sheet])


def test_normalize_document_drops_orphan_metadata_only_slot_row_without_context() -> None:
    records = [
        RawRecord(
            values={
                "program": "\u041f\u0440\u0430\u0432\u043e",
                "faculty": "\u042e\u0440\u0438\u0434\u0438\u0447\u043d\u0438\u0439 \u0444\u0430\u043a\u0443\u043b\u044c\u0442\u0435\u0442",
                "day": "\u0412\u0456\u0432\u0442\u043e\u0440\u043e\u043a",
                "start_time": "09:40",
                "end_time": "11:00",
                "teacher": "\u0434\u043e\u0446. \u0417\u0430\u044f\u0440\u043d\u0430 \u0406. \u0421.",
                "room": "\u0430\u0443\u0434. 403",
            },
            row_index=3,
            sheet_name="pdf-table-p1-t1",
            raw_excerpt="orphan metadata row",
        ),
    ]

    rows = normalize_document(_make_document(records))

    assert rows == []


def test_normalize_document_drops_completely_blank_payload_row() -> None:
    records = [
        RawRecord(
            values={
                "program": "\u041f\u0440\u0430\u0432\u043e",
                "faculty": "\u042e\u0440\u0438\u0434\u0438\u0447\u043d\u0438\u0439 \u0444\u0430\u043a\u0443\u043b\u044c\u0442\u0435\u0442",
                "day": "\u0412\u0456\u0432\u0442\u043e\u0440\u043e\u043a",
                "start_time": "09:40",
                "end_time": "11:00",
            },
            row_index=4,
            sheet_name="pdf-table-p1-t1",
            raw_excerpt="blank payload row",
        ),
    ]

    rows = normalize_document(_make_document(records))

    assert rows == []
