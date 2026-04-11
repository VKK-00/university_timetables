from __future__ import annotations

from timetable_scraper.models import DiscoveredAsset, FetchedAsset, NormalizedRow, ParsedDocument, ParsedSheet, RawRecord
from timetable_scraper.normalize import normalize_document
from timetable_scraper.qa import sanitize_export_rows
from timetable_scraper.utils import looks_like_bad_program_label, looks_like_roomish_subject_text


def _document(*records: RawRecord) -> ParsedDocument:
    asset = DiscoveredAsset(
        source_name="fixture",
        source_kind="file_url",
        source_url_or_path="https://example.test/schedule.xlsx",
        asset_kind="file_url",
        locator="https://example.test/schedule.xlsx",
        display_name="schedule.xlsx",
    )
    fetched = FetchedAsset(
        asset=asset,
        content=b"",
        content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        content_hash="abc",
        resolved_locator="schedule.xlsx",
    )
    return ParsedDocument(
        asset=fetched,
        sheets=[
            ParsedSheet(
                sheet_name="Sheet1",
                program="Demo",
                faculty="Demo faculty",
                records=list(records),
            )
        ],
    )


def test_normalize_document_merges_subject_continuation_rows() -> None:
    document = _document(
        RawRecord(
            values={
                "program": "\u0413\u0415\u041e\u0413\u0420\u0410\u0424\u0406\u042f \u0422\u0410 \u0420\u0415\u0413\u0406\u041e\u041d\u0410\u041b\u042c\u041d\u0406 \u0421\u0422\u0423\u0414\u0406\u0407",
                "faculty": "\u0413\u0435\u043e\u0433\u0440\u0430\u0444\u0456\u0447\u043d\u0438\u0439 \u0444\u0430\u043a\u0443\u043b\u044c\u0442\u0435\u0442",
                "week_type": "\u041e\u0431\u0438\u0434\u0432\u0430",
                "day": "\u041f\u043e\u043d\u0435\u0434\u0456\u043b\u043e\u043a",
                "start_time": "14:30",
                "end_time": "15:50",
                "subject": "\u041f\u0435\u0434\u0430\u0433\u043e\u0433\u0456\u043a\u0430 \u0432\u0438\u0449\u043e\u0457 \u0448\u043a\u043e\u043b\u0438 \u0442\u0430 \u043f\u0435\u0434\u0430\u0433\u043e\u0433\u0456\u0447\u043d\u0430",
                "groups": "\u0413\u0415\u041e\u0413\u0420\u0410\u0424\u0406\u042f \u0422\u0410 \u0420\u0415\u0413\u0406\u041e\u041d\u0410\u041b\u042c\u041d\u0406 \u0421\u0422\u0423\u0414\u0406\u0407",
            },
            row_index=3,
            sheet_name="Sheet1",
            raw_excerpt="part1",
        ),
        RawRecord(
            values={
                "program": "\u0413\u0415\u041e\u0413\u0420\u0410\u0424\u0406\u042f \u0422\u0410 \u0420\u0415\u0413\u0406\u041e\u041d\u0410\u041b\u042c\u041d\u0406 \u0421\u0422\u0423\u0414\u0406\u0407",
                "faculty": "\u0413\u0435\u043e\u0433\u0440\u0430\u0444\u0456\u0447\u043d\u0438\u0439 \u0444\u0430\u043a\u0443\u043b\u044c\u0442\u0435\u0442",
                "week_type": "\u041e\u0431\u0438\u0434\u0432\u0430",
                "day": "\u041f\u043e\u043d\u0435\u0434\u0456\u043b\u043e\u043a",
                "start_time": "14:30",
                "end_time": "15:50",
                "subject": "\u043c\u0430\u0439\u0441\u0442\u0435\u0440\u043d\u0456\u0441\u0442\u044c \u0432\u0438\u043a\u043b\u0430\u0434\u0430\u0447\u0430",
                "teacher": "\u041b\u0438\u0442\u0432\u0438\u043d\u0447\u0443\u043a \u041b.\u041c.",
                "lesson_type": "\u043b\u0435\u043a\u0446\u0456\u044f",
                "groups": "\u0413\u0415\u041e\u0413\u0420\u0410\u0424\u0406\u042f \u0422\u0410 \u0420\u0415\u0413\u0406\u041e\u041d\u0410\u041b\u042c\u041d\u0406 \u0421\u0422\u0423\u0414\u0406\u0407",
            },
            row_index=4,
            sheet_name="Sheet1",
            raw_excerpt="part2",
        ),
    )
    rows = normalize_document(document)
    assert len(rows) == 1
    assert rows[0].subject == "\u041f\u0435\u0434\u0430\u0433\u043e\u0433\u0456\u043a\u0430 \u0432\u0438\u0449\u043e\u0457 \u0448\u043a\u043e\u043b\u0438 \u0442\u0430 \u043f\u0435\u0434\u0430\u0433\u043e\u0433\u0456\u0447\u043d\u0430 \u043c\u0430\u0439\u0441\u0442\u0435\u0440\u043d\u0456\u0441\u0442\u044c \u0432\u0438\u043a\u043b\u0430\u0434\u0430\u0447\u0430"
    assert rows[0].teacher == "\u041b\u0438\u0442\u0432\u0438\u043d\u0447\u0443\u043a \u041b.\u041c."
    assert rows[0].lesson_type == "\u043b\u0435\u043a\u0446\u0456\u044f"
    assert "subject_continuation_merged" in rows[0].autofix_actions


def test_bad_program_labels_reject_sociology_noise_markers() -> None:
    assert looks_like_bad_program_label("English")
    assert looks_like_bad_program_label("\u0410\u041d\u0413\u041b.\u041c\u041e\u0412\u0410")
    assert looks_like_bad_program_label("\u041b-26\u0433\u043e\u0434")


def test_normalize_document_moves_trailing_teacher_out_of_subject_without_dots() -> None:
    document = _document(
        RawRecord(
            values={
                "program": "4 \u043a\u0443\u0440\u0441 \u0431\u0456\u043e\u043b\u043e\u0433\u0438",
                "faculty": "\u041d\u041d\u0426 \u0406\u043d\u0441\u0442\u0438\u0442\u0443\u0442 \u0431\u0456\u043e\u043b\u043e\u0433\u0456\u0457 \u0442\u0430 \u043c\u0435\u0434\u0438\u0446\u0438\u043d\u0438",
                "week_type": "\u041e\u0431\u0438\u0434\u0432\u0430",
                "day": "\u041f\u043e\u043d\u0435\u0434\u0456\u043b\u043e\u043a",
                "start_time": "08:40",
                "end_time": "10:00",
                "subject": "\u0406\u043d\u043e\u0437\u0435\u043c\u043d\u0430 \u043c\u043e\u0432\u0430 \u041a\u0443\u0440\u0434\u0456\u0448 \u041e \u041a.",
                "teacher": "\u0434\u043e\u0446. \u0410\u0444\u0430\u043d\u0430\u0441\u044c\u0454\u0432\u0430 \u041a.\u0421.",
            },
            row_index=3,
            sheet_name="Sheet1",
            raw_excerpt="teacher tail",
        )
    )
    rows = normalize_document(document)
    assert rows[0].subject == "\u0406\u043d\u043e\u0437\u0435\u043c\u043d\u0430 \u043c\u043e\u0432\u0430"
    assert "\u041a\u0443\u0440\u0434\u0456\u0448 \u041e \u041a." in rows[0].teacher


def test_roomish_subject_detection_catches_marker_room_combos() -> None:
    assert looks_like_roomish_subject_text("\u043b \u041a\u042f\u0424 27")
    assert looks_like_roomish_subject_text("423, \u043b.")
    assert looks_like_roomish_subject_text("\u043b / \u043f\u0440")
    assert looks_like_roomish_subject_text("\u041a\u042f\u0424, \u043b\u0430\u0431.")


def test_sanitize_export_rows_demotes_tiny_sociology_noise_programs() -> None:
    accepted = [
        NormalizedRow(
            program="English",
            faculty="\u0424\u0430\u043a\u0443\u043b\u044c\u0442\u0435\u0442 \u0441\u043e\u0446\u0456\u043e\u043b\u043e\u0433\u0456\u0457",
            week_type="\u041e\u0431\u0438\u0434\u0432\u0430",
            day="\u041f\u043e\u043d\u0435\u0434\u0456\u043b\u043e\u043a",
            start_time="16:00",
            end_time="17:20",
            subject="\u0404\u0412\u0420\u041e\u041f\u0415\u0419\u0421\u042c\u041a\u0406 \u0421\u0422\u0423\u0414\u0406\u0407",
            lesson_type="\u043b\u0435\u043a\u0446\u0456\u044f",
            notes=". \u0406\u0412\u0410\u0429\u0415\u041d\u041a\u041e \u041e.\u0412",
            source_name="sociology-schedule",
            source_root_url="https://example.test/soc",
            asset_locator="https://example.test/soc.xlsx",
            sheet_name="English",
        )
    ]
    final_rows, review = sanitize_export_rows(accepted, [])
    assert not final_rows
    assert len(review) == 1
    assert "bad_program_label" in review[0].qa_flags


def test_sanitize_export_rows_demotes_tiny_law_academ_bucket() -> None:
    accepted = [
        NormalizedRow(
            program="110 \u0430\u043a\u0430\u0434\u0435\u043c",
            faculty="\u042e\u0440\u0438\u0434\u0438\u0447\u043d\u0438\u0439 \u0444\u0430\u043a\u0443\u043b\u044c\u0442\u0435\u0442",
            week_type="\u041e\u0431\u0438\u0434\u0432\u0430",
            day="\u0421\u0435\u0440\u0435\u0434\u0430",
            start_time="13:05",
            end_time="14:25",
            subject="\u0414\u043e\u0433\u043e\u0432\u0456\u0440\u043d\u0435 \u0440\u0435\u0433\u0443\u043b\u044e\u0432\u0430\u043d\u043d\u044f \u0432\u0456\u0434\u043d\u043e\u0441\u0438\u043d \u0456\u043d\u0442\u0435\u043b\u0435\u043a\u0442\u0443\u0430\u043b\u044c\u043d\u043e\u0457 \u0432\u043b\u0430\u0441\u043d\u043e\u0441\u0442\u0456",
            teacher="\u043f\u0440\u043e\u0444. \u041a\u043e\u0434\u0438\u043d\u0435\u0446\u044c \u0410.\u041e.",
            source_name="law-schedule",
            source_root_url="https://example.test/law",
            asset_locator="https://example.test/law.pdf",
            sheet_name="110 \u0430\u043a\u0430\u0434\u0435\u043c",
        )
    ]
    final_rows, review = sanitize_export_rows(accepted, [])
    assert not final_rows
    assert len(review) == 1
    assert "bad_program_label" in review[0].qa_flags


def test_sanitize_export_rows_demotes_tiny_phys_roomish_subject_bucket() -> None:
    accepted = [
        NormalizedRow(
            program="\u0421\u0443\u0447.\u043f\u0440\u043e\u0431\u043b.\u0430\u0441\u0442\u0440\u043e\u0444\u0456\u0437\u0438\u043a\u0438",
            faculty="\u0424\u0456\u0437\u0438\u0447\u043d\u0438\u0439 \u0444\u0430\u043a\u0443\u043b\u044c\u0442\u0435\u0442",
            week_type="\u041e\u0431\u0438\u0434\u0432\u0430",
            day="\u0427\u0435\u0442\u0432\u0435\u0440",
            start_time="08:40",
            end_time="10:15",
            subject="423, \u043b.",
            course="1",
            source_name="phys-schedule",
            source_root_url="https://example.test/phys",
            asset_locator="https://example.test/phys.xlsx",
            sheet_name="\u0421\u0443\u0447.\u043f\u0440\u043e\u0431\u043b.\u0430\u0441\u0442\u0440\u043e\u0444\u0456\u0437\u0438\u043a\u0438",
        )
    ]
    final_rows, review = sanitize_export_rows(accepted, [])
    assert not final_rows
    assert len(review) == 1
    assert "bad_program_label" in review[0].qa_flags


def test_sanitize_export_rows_demotes_tiny_phys_initials_only_subject_bucket() -> None:
    accepted = [
        NormalizedRow(
            program="\u0420\u0435\u043b\u044f\u0442\u0438\u0432. \u043a\u0432\u0430\u043d\u0442. \u043c\u0435\u0445. \u0442\u0430 \u043c\u0435\u0442\u043e\u0434\u0438 \u0442\u0435\u043e\u0440. \u0433\u0440\u0443\u043f \u0432 \u0444\u0456\u0437. \u0435\u043b\u0435\u043c.\u0447\u0430\u0441\u0442.",
            faculty="\u0424\u0456\u0437\u0438\u0447\u043d\u0438\u0439 \u0444\u0430\u043a\u0443\u043b\u044c\u0442\u0435\u0442",
            week_type="\u041e\u0431\u0438\u0434\u0432\u0430",
            day="\u0427\u0435\u0442\u0432\u0435\u0440",
            start_time="12:20",
            end_time="13:55",
            subject="\u0410.\u0412.",
            teacher="\u0427\u0443\u043c\u0430\u0447\u0435\u043d\u043a\u043e",
            course="3",
            source_name="phys-schedule",
            source_root_url="https://example.test/phys",
            asset_locator="https://example.test/phys.xlsx",
            sheet_name="\u0420\u0435\u043b\u044f\u0442\u0438\u0432.",
        )
    ]
    final_rows, review = sanitize_export_rows(accepted, [])
    assert not final_rows
    assert len(review) == 1
    assert "bad_program_label" in review[0].qa_flags
