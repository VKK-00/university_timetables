from timetable_scraper.models import DiscoveredAsset, FetchedAsset, ParsedDocument, RawRecord
from timetable_scraper.normalize import normalize_record
from timetable_scraper.qa import analyze_row_quality


def _make_document() -> ParsedDocument:
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
    return ParsedDocument(asset=fetched, sheets=[])


def test_normalize_record_merges_broken_teacher_chain() -> None:
    record = RawRecord(
        values={
            "program": "Право",
            "faculty": "Юридичний факультет",
            "day": "Вівторок",
            "start_time": "08:00",
            "end_time": "09:20",
            "subject": "Науковий образ світу (л)",
            "teacher": "проф ; Євтух А.А. ; ас ; Пилипова О.В.; проф.; ГригорукВ.І.; ВербицькийВ.Г.",
            "room": "ауд. 425",
        },
        row_index=3,
        sheet_name="pdf-table-p1-t1",
        raw_excerpt="Право | Вівторок | 08:00 | 09:20 | Науковий образ світу (л)",
    )

    row = normalize_record(record, document=_make_document())
    analyze_row_quality(row)

    assert row.teacher == "проф. Євтух А.А.; ас. Пилипова О.В.; Григорук В.І.; Вербицький В.Г."
    assert "inconsistent_columns" not in row.qa_flags


def test_normalize_record_normalizes_subject_derived_teacher_list() -> None:
    record = RawRecord(
        values={
            "program": "Право",
            "faculty": "Юридичний факультет",
            "day": "Вівторок",
            "start_time": "08:00",
            "end_time": "09:20",
            "subject": "Науковий образ світу (л) / проф.ГригорукВ.І.,проф.ВербицькийВ.Г., / ауд. 425",
        },
        row_index=3,
        sheet_name="pdf-table-p1-t1",
        raw_excerpt="Право | Вівторок | 08:00 | 09:20 | Науковий образ світу (л) / проф.ГригорукВ.І.,проф.ВербицькийВ.Г., / ауд. 425",
    )

    row = normalize_record(record, document=_make_document())

    assert row.subject == "Науковий образ світу (л)"
    assert row.room == "ауд. 425"
    assert row.teacher == "проф. Григорук В.І.; Вербицький В.Г."
