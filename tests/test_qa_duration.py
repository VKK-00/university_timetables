from timetable_scraper.qa import _has_implausible_time


def test_long_practice_block_is_allowed() -> None:
    assert _has_implausible_time("08:40", "13:55", "Переддипломна практика") is False
    assert _has_implausible_time("08:40", "13:55", "Науково-виробнича практика") is False


def test_long_non_practice_block_still_fails() -> None:
    assert _has_implausible_time("08:40", "13:55", "Електродинаміка") is True


def test_absurdly_long_practice_block_still_fails() -> None:
    assert _has_implausible_time("08:40", "15:10", "Переддипломна практика") is True
