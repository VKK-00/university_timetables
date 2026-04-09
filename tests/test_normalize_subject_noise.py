from __future__ import annotations

from timetable_scraper.models import DiscoveredAsset, FetchedAsset, ParsedDocument, RawRecord
from timetable_scraper.normalize import normalize_record


def _make_document() -> ParsedDocument:
    asset = DiscoveredAsset(
        source_name="geo-schedule",
        source_kind="web_page",
        source_url_or_path="https://geo.knu.ua/navchannya/rozklad-zanyat/",
        asset_kind="pdf",
        locator="https://geo.knu.ua/wp-content/uploads/2026/03/rozklad_1-k_2sem_2025-2026.pdf",
        display_name="rozklad_1-k_2sem_2025-2026.pdf",
    )
    fetched = FetchedAsset(
        asset=asset,
        content=b"",
        content_type="application/pdf",
        content_hash="geo",
        resolved_locator="rozklad_1-k_2sem_2025-2026.pdf",
    )
    return ParsedDocument(asset=fetched, sheets=[])


def test_normalize_record_strips_pdf_date_tail_from_subject() -> None:
    row = normalize_record(
        RawRecord(
            values={
                "day": "Вівторок",
                "start_time": "10:00",
                "end_time": "11:20",
                "subject": "Іноземна мова (пр) / 03.03.2026 16:00",
                "teacher": "Дідковська Т.Л.",
                "room": "ауд. 506",
            },
            row_index=8,
            sheet_name="pdf-table-p1-t1",
            raw_excerpt="geo date tail",
        ),
        document=_make_document(),
    )

    assert row.subject == "Іноземна мова (пр)"
    assert "03.03.2026 16:00" in row.notes


def test_normalize_record_strips_pdf_link_fragments_and_collapses_subject() -> None:
    row = normalize_record(
        RawRecord(
            values={
                "day": "Понеділок",
                "start_time": "11:30",
                "end_time": "12:50",
                "subject": "Топографія з / основами / геодезії (лаб) / 4502716?p=l9XZ / .com",
                "teacher": "Гончаренко О.С.",
                "room": "ауд. 603",
            },
            row_index=15,
            sheet_name="pdf-table-p1-t1",
            raw_excerpt="geo link fragment tail",
        ),
        document=_make_document(),
    )

    assert row.subject == "Топографія з основами геодезії (лаб)"
    assert "?p=l9XZ" not in row.subject
    assert ".com" not in row.subject


def test_normalize_record_keeps_short_latin_subject_and_moves_date_list_to_notes() -> None:
    row = normalize_record(
        RawRecord(
            values={
                "day": "Вівторок",
                "start_time": "10:30",
                "end_time": "11:50",
                "subject": "SQL / [30.09, 11.11, 25.11]",
                "teacher": "Духновська К. К.",
            },
            row_index=11,
            sheet_name="fit-like",
            raw_excerpt="fit sql subject",
        ),
        document=_make_document(),
    )

    assert row.subject == "SQL"
    assert "[30.09, 11.11, 25.11]" in row.notes
