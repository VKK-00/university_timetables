from __future__ import annotations

from timetable_scraper.adapters.pdf import _parse_pdf_table


def test_pdf_grid_table_merges_teacher_room_continuation_line() -> None:
    table = [
        ["Програма", None, "ГЕОГРАФІЯ", None],
        ["", "ПОНЕДІЛОК", "1 курс", None],
        ["", "10.00 – 11.20", "Ландшафти України (пр)", None],
        ["", "", "Удовиченко В.В. 506", None],
    ]

    records = _parse_pdf_table(table, sheet_name="grid", faculty="test", program="test")

    assert len(records) == 1
    assert records[0].values["subject"] == "Ландшафти України (пр)"
    assert records[0].values["teacher"] == "Удовиченко В.В."
    assert records[0].values["room"] == "506"


def test_pdf_grid_table_merges_teacher_room_and_link_continuation_line() -> None:
    table = [
        ["Програма", None, "ГЕОГРАФІЯ", None],
        ["", "ВІВТОРОК", "1 курс", None],
        ["", "10.00 – 11.20", "Міське планування (сем)", None],
        ["", "", "Аріон О.В. 402 https://knu-ua.zoom.us/j/84855063638?pwd=test", None],
    ]

    records = _parse_pdf_table(table, sheet_name="grid", faculty="test", program="test")

    assert len(records) == 1
    assert records[0].values["subject"] == "Міське планування (сем)"
    assert records[0].values["teacher"] == "Аріон О.В."
    assert records[0].values["room"] == "402"
    assert "zoom.us" in records[0].values["link"]
