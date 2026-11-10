from datetime import date

import pytest

from nldate import parse

# A Monday.
TODAY = date(2025, 11, 10)


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        # Examples from the boss's email
        ("5 days before December 1st, 2025", date(2025, 11, 26)),
        ("1 year and 2 months after yesterday", date(2027, 1, 9)),
        ("next Tuesday", date(2025, 11, 11)),
        # Keywords
        ("today", TODAY),
        ("Today", TODAY),
        ("now", TODAY),
        ("tomorrow", date(2025, 11, 11)),
        ("yesterday", date(2025, 11, 9)),
        ("the day after tomorrow", date(2025, 11, 12)),
        ("the day before yesterday", date(2025, 11, 8)),
        # Absolute dates
        ("December 1st, 2025", date(2025, 12, 1)),
        ("December 1, 2025", date(2025, 12, 1)),
        ("Dec 1 2025", date(2025, 12, 1)),
        ("Dec. 1, 2025", date(2025, 12, 1)),
        ("1 December 2025", date(2025, 12, 1)),
        ("1st of December 2025", date(2025, 12, 1)),
        ("the first of December, 2025", date(2025, 12, 1)),
        ("December twenty-first 2025", date(2025, 12, 21)),
        ("Monday, December 1, 2025", date(2025, 12, 1)),
        ("December 25", date(2025, 12, 25)),
        ("July 4th", date(2025, 7, 4)),
        ("December 2025", date(2025, 12, 1)),
        ("2025-12-01", date(2025, 12, 1)),
        ("2025/12/01", date(2025, 12, 1)),
        ("12/01/2025", date(2025, 12, 1)),
        ("12-01-2025", date(2025, 12, 1)),
        ("12/1/25", date(2025, 12, 1)),
        ("20251201", date(2025, 12, 1)),
        # Weekdays (today is Monday)
        ("Tuesday", date(2025, 11, 11)),
        ("next Monday", date(2025, 11, 17)),
        ("last Monday", date(2025, 11, 3)),
        ("last Friday", date(2025, 11, 7)),
        ("this Friday", date(2025, 11, 14)),
        ("Friday next week", date(2025, 11, 21)),
        # Periods
        ("next week", date(2025, 11, 17)),
        ("last week", date(2025, 11, 3)),
        ("next month", date(2025, 12, 10)),
        ("last year", date(2024, 11, 10)),
        # Offsets
        ("in 3 days", date(2025, 11, 13)),
        ("in a week", date(2025, 11, 17)),
        ("in two weeks", date(2025, 11, 24)),
        ("3 days ago", date(2025, 11, 7)),
        ("a month ago", date(2025, 10, 10)),
        ("two weeks from now", date(2025, 11, 24)),
        ("two weeks from tomorrow", date(2025, 11, 25)),
        ("a fortnight from today", date(2025, 11, 24)),
        ("10 days after 2025-12-25", date(2026, 1, 4)),
        ("1 year, 2 months and 3 days after today", date(2027, 1, 13)),
        ("twenty one days from now", date(2025, 12, 1)),
        ("3 weeks before next Friday", date(2025, 10, 24)),
        ("tomorrow plus 2 days", date(2025, 11, 13)),
        ("in 3days", date(2025, 11, 13)),
    ],
)
def test_parse(text: str, expected: date) -> None:
    assert parse(text, today=TODAY) == expected


def test_month_end_clamping() -> None:
    assert parse("1 month after January 31, 2025") == date(2025, 2, 28)


def test_leap_year() -> None:
    assert parse("1 year after February 29, 2024") == date(2025, 2, 28)


def test_default_today() -> None:
    assert parse("today") == date.today()


@pytest.mark.parametrize(
    "text",
    [
        "",
        "   ",
        "banana",
        "next",
        "the day",
        "February 30, 2025",
        "13/45/2025",
        "5 bananas ago",
    ],
)
def test_invalid_raises(text: str) -> None:
    with pytest.raises(ValueError):
        parse(text, today=TODAY)
