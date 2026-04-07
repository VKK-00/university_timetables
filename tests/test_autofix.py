from __future__ import annotations

from timetable_scraper.models import DiscoveredAsset, FetchedAsset, ParsedDocument, RawRecord
from timetable_scraper.normalize import normalize_record


def _fixture_document() -> ParsedDocument:
    asset = DiscoveredAsset(
        source_name="fixture",
        source_kind="zip",
        source_url_or_path="fixtures.zip",
        asset_kind="zip_entry",
        locator="fixtures.zip::demo.xlsx",
        display_name="demo.xlsx",
    )
    fetched = FetchedAsset(
        asset=asset,
        content=b"",
        content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        content_hash="abc",
        resolved_locator="demo.xlsx",
    )
    return ParsedDocument(asset=fetched, sheets=[])


def test_normalize_record_tracks_defaulted_week_type_autofix() -> None:
    row = normalize_record(
        RawRecord(
            values={
                "program": "Demo",
                "faculty": "FIT",
                "day": "ÐŸÐ¾Ð½ÐµÐ´Ñ–Ð»Ð¾Ðº",
                "start_time": "09:30",
                "end_time": "10:50",
                "subject": "ÐÐ»Ð³Ð¾Ñ€Ð¸Ñ‚Ð¼Ð¸",
            },
            row_index=3,
            sheet_name="1 ÐºÑƒÑ€Ñ",
            raw_excerpt="ÐÐ»Ð³Ð¾Ñ€Ð¸Ñ‚Ð¼Ð¸",
        ),
        document=_fixture_document(),
    )
    assert row.week_source == "default"
    assert "week_type_defaulted" in row.autofix_actions


def test_normalize_record_tracks_time_inference_autofix() -> None:
    row = normalize_record(
        RawRecord(
            values={
                "program": "Demo",
                "faculty": "FIT",
                "day": "Ð’Ñ–Ð²Ñ‚Ð¾Ñ€Ð¾Ðº",
                "end_time": "15:50",
                "subject": "ÐœÐ°Ñ€ÐºÐµÑ‚Ð¸Ð½Ð³",
            },
            row_index=3,
            sheet_name="1 ÐºÑƒÑ€Ñ",
            raw_excerpt="ÐœÐ°Ñ€ÐºÐµÑ‚Ð¸Ð½Ð³ | 15:50",
        ),
        document=_fixture_document(),
    )
    assert row.start_time == "14:30"
    assert "start_time_inferred" in row.autofix_actions


def test_normalize_record_tracks_cleanup_autofixes() -> None:
    row = normalize_record(
        RawRecord(
            values={
                "program": "Demo",
                "faculty": "Law",
                "day": "ÐŸÐ¾Ð½ÐµÐ´Ñ–Ð»Ð¾Ðº",
                "start_time": "09:30",
                "end_time": "10:50",
                "subject": "ÐšÐ¾Ð½ÑÑ‚Ð¸Ñ‚ÑƒÑ†Ñ–Ð¹Ð½Ðµ Ð¿Ñ€Ð°Ð²Ð¾ (Ñ) / PhD, Ð°Ñ. ÐžÐ»ÑŒÑˆÐµÐ²ÑÑŒÐºÐ¸Ð¹ Ð†.ÐŸ. / Ð°ÑƒÐ´. 159",
            },
            row_index=5,
            sheet_name="1 ÐºÑƒÑ€Ñ",
            raw_excerpt="ÐšÐ¾Ð½ÑÑ‚Ð¸Ñ‚ÑƒÑ†Ñ–Ð¹Ð½Ðµ Ð¿Ñ€Ð°Ð²Ð¾",
        ),
        document=_fixture_document(),
    )
    assert "teacher_from_subject" in row.autofix_actions
    assert "room_from_subject" in row.autofix_actions
