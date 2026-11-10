"""Natural-language date parsing.

Supported inputs include (case-insensitive):

* Keywords: "today", "now", "tomorrow", "yesterday", "the day after tomorrow",
  "the day before yesterday"
* Absolute dates: "2025-12-01", "12/01/2025", "12/1/25", "December 1st, 2025",
  "Dec 1 2025", "1 December 2025", "the 1st of December, 2025",
  "Monday, December 1, 2025", "December 1" (current year), "December 2025"
* Weekdays: "Tuesday", "next Tuesday", "last Tuesday", "this Tuesday"
* Periods: "next week", "last month", "this year", "next year"
* Offsets: "in 3 days", "3 days ago", "two weeks from now",
  "5 days before December 1st, 2025", "1 year and 2 months after yesterday",
  "a week from tomorrow", "a fortnight from today"
"""

import calendar
import re
from datetime import date, timedelta

MONTHS: dict[str, int] = {}
for _i, _name in enumerate(calendar.month_name):
    if _i:
        MONTHS[_name.lower()] = _i
        MONTHS[_name[:3].lower()] = _i
MONTHS["sept"] = 9

WEEKDAYS: dict[str, int] = {}
for _i, _name in enumerate(calendar.day_name):
    WEEKDAYS[_name.lower()] = _i
    WEEKDAYS[_name[:3].lower()] = _i
WEEKDAYS.update({"tues": 1, "tue": 1, "wed": 2, "weds": 2, "thur": 3, "thurs": 3})

ONES = {
    "zero": 0,
    "one": 1,
    "two": 2,
    "three": 3,
    "four": 4,
    "five": 5,
    "six": 6,
    "seven": 7,
    "eight": 8,
    "nine": 9,
    "ten": 10,
    "eleven": 11,
    "twelve": 12,
    "thirteen": 13,
    "fourteen": 14,
    "fifteen": 15,
    "sixteen": 16,
    "seventeen": 17,
    "eighteen": 18,
    "nineteen": 19,
}
TENS = {
    "twenty": 20,
    "thirty": 30,
    "forty": 40,
    "fifty": 50,
    "sixty": 60,
    "seventy": 70,
    "eighty": 80,
    "ninety": 90,
}
ORDINAL_WORDS = {
    "first": 1,
    "second": 2,
    "third": 3,
    "fourth": 4,
    "fifth": 5,
    "sixth": 6,
    "seventh": 7,
    "eighth": 8,
    "ninth": 9,
    "tenth": 10,
    "eleventh": 11,
    "twelfth": 12,
    "thirteenth": 13,
    "fourteenth": 14,
    "fifteenth": 15,
    "sixteenth": 16,
    "seventeenth": 17,
    "eighteenth": 18,
    "nineteenth": 19,
    "twentieth": 20,
    "thirtieth": 30,
}

# unit -> (months, days)
UNITS: dict[str, tuple[int, int]] = {
    "day": (0, 1),
    "days": (0, 1),
    "week": (0, 7),
    "weeks": (0, 7),
    "wk": (0, 7),
    "wks": (0, 7),
    "fortnight": (0, 14),
    "fortnights": (0, 14),
    "month": (1, 0),
    "months": (1, 0),
    "mo": (1, 0),
    "mos": (1, 0),
    "year": (12, 0),
    "years": (12, 0),
    "yr": (12, 0),
    "yrs": (12, 0),
    "decade": (120, 0),
    "decades": (120, 0),
}

MONTH_RE = "|".join(sorted(MONTHS, key=len, reverse=True))
WEEKDAY_RE = "|".join(sorted(WEEKDAYS, key=len, reverse=True))
UNIT_RE = "|".join(sorted(UNITS, key=len, reverse=True))


def add_months(d: date, months: int) -> date:
    """Add months to a date, clamping the day to the end of the month."""
    total = d.year * 12 + (d.month - 1) + months
    year, month = divmod(total, 12)
    month += 1
    last = calendar.monthrange(year, month)[1]
    return date(year, month, min(d.day, last))


def _normalize(s: str) -> str:
    s = s.lower().strip()
    s = s.replace(",", " ").replace("-", " - ")
    # Rejoin ISO-style dashed dates that the line above split apart.
    s = re.sub(r"(\d)\s+-\s+(\d)", r"\1-\2", s)
    s = re.sub(r"\s+-\s+", " ", s)
    s = re.sub(r"(\d+)(st|nd|rd|th)\b", r"\1", s)
    s = re.sub(rf"\b(\d+)({UNIT_RE})\b", r"\1 \2", s)  # "3days" -> "3 days"
    s = re.sub(r"\b([a-z]{3,5})\.", r"\1", s)  # "dec." -> "dec"
    s = s.rstrip(".!?")
    s = re.sub(r"\s+", " ", s).strip()
    s = re.sub(r"^(on|at|by) ", "", s)
    return s


def _number(text: str) -> int | None:
    """Parse a cardinal number written as digits or English words."""
    text = text.strip()
    if re.fullmatch(r"\d+", text):
        return int(text)
    if text in ("a", "an", "one", "a single", "single"):
        return 1
    if text in ("a couple of", "a couple", "couple of", "a pair of"):
        return 2
    if text in ("a few", "few"):
        return 3
    words = text.replace("-", " ").split()
    words = [w for w in words if w != "and"]
    if not words:
        return None
    total = 0
    current = 0
    for w in words:
        if w in ONES:
            current += ONES[w]
        elif w in TENS:
            current += TENS[w]
        elif w == "hundred":
            current = max(current, 1) * 100
        elif w == "thousand":
            total += max(current, 1) * 1000
            current = 0
        else:
            return None
    return total + current


def _parse_duration(text: str) -> tuple[int, int]:
    """Parse '1 year and 2 months' into (months, days)."""
    text = re.sub(r"^(a period of|the next|the last|another)\s+", "", text.strip())
    # Find "<number> <unit>" chunks, joined by "and", "plus" or spaces.
    chunk_re = re.compile(rf"(.+?)\s*\b({UNIT_RE})\b")
    months = 0
    days = 0
    rest = text
    pos = 0
    found = False
    for m in chunk_re.finditer(rest):
        between = rest[pos : m.start()].strip()
        if between not in ("", "and", "plus", "&"):
            raise ValueError(f"Could not parse duration: {text!r}")
        num_text = re.sub(r"^(and|plus|&)\s+", "", m.group(1).strip())
        n = _number(num_text)
        if n is None:
            raise ValueError(f"Could not parse number: {num_text!r}")
        um, ud = UNITS[m.group(2)]
        months += n * um
        days += n * ud
        pos = m.end()
        found = True
    if not found or rest[pos:].strip():
        # Allow a bare unit like "week" meaning one week.
        if re.fullmatch(UNIT_RE, rest.strip()):
            um, ud = UNITS[rest.strip()]
            return um, ud
        raise ValueError(f"Could not parse duration: {text!r}")
    return months, days


def _apply(base: date, months: int, days: int, sign: int) -> date:
    return add_months(base, sign * months) + timedelta(days=sign * days)


def _year(text: str) -> int:
    y = int(text)
    if len(text) <= 2:
        y += 2000
    return y


def _day_number(text: str) -> int | None:
    if text.isdigit():
        return int(text)
    if text in ORDINAL_WORDS:
        return ORDINAL_WORDS[text]
    m = re.fullmatch(r"(twenty|thirty)[ -](\w+)", text)
    if m and m.group(2) in ORDINAL_WORDS:
        return TENS[m.group(1)] + ORDINAL_WORDS[m.group(2)]
    return None


def _absolute(s: str, today: date) -> date | None:
    # Strip a leading weekday name: "tuesday december 2 2025".
    m = re.fullmatch(rf"(?:{WEEKDAY_RE}) (.+)", s)
    if m:
        inner = _absolute(m.group(1), today)
        if inner is not None:
            return inner

    # ISO: 2025-12-01, 2025/12/01, 2025.12.01
    m = re.fullmatch(r"(\d{4})[-/.](\d{1,2})[-/.](\d{1,2})", s)
    if m:
        return date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
    # Compact: 20251201
    m = re.fullmatch(r"(\d{4})(\d{2})(\d{2})", s)
    if m:
        return date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
    # US: 12/01/2025, 12-01-2025, 12.1.25
    m = re.fullmatch(r"(\d{1,2})[-/.](\d{1,2})[-/.](\d{2}|\d{4})", s)
    if m:
        return date(_year(m.group(3)), int(m.group(1)), int(m.group(2)))
    # US without year: 12/01
    m = re.fullmatch(r"(\d{1,2})/(\d{1,2})", s)
    if m:
        return date(today.year, int(m.group(1)), int(m.group(2)))

    ords = "|".join(sorted(ORDINAL_WORDS, key=len, reverse=True))
    day_re = rf"(\d{{1,2}}|(?:(?:twenty|thirty)[ -])?(?:{ords}))"
    # Month D [YYYY]: "december 1 2025", "dec 1", "december first"
    m = re.fullmatch(rf"({MONTH_RE}) (?:the )?{day_re}(?: (?:of )?(\d{{4}}))?", s)
    if m:
        d = _day_number(m.group(2))
        if d is not None:
            y = int(m.group(3)) if m.group(3) else today.year
            return date(y, MONTHS[m.group(1)], d)
    # [the] D [of] Month [YYYY]: "1 december 2025", "the first of december"
    m = re.fullmatch(
        rf"(?:the )?{day_re} (?:of )?({MONTH_RE})(?: (\d{{4}}))?",
        s,
    )
    if m:
        d = _day_number(m.group(1))
        if d is not None:
            y = int(m.group(3)) if m.group(3) else today.year
            return date(y, MONTHS[m.group(2)], d)
    # Month YYYY: "december 2025" -> first of month
    m = re.fullmatch(rf"({MONTH_RE}) (\d{{4}})", s)
    if m:
        return date(int(m.group(2)), MONTHS[m.group(1)], 1)
    # Year alone is too ambiguous; reject by returning None.
    return None


def _relative_base(s: str, today: date) -> date | None:
    keywords = {
        "today": 0,
        "now": 0,
        "right now": 0,
        "tonight": 0,
        "this day": 0,
        "tomorrow": 1,
        "tmrw": 1,
        "tmr": 1,
        "yesterday": -1,
        "the day after tomorrow": 2,
        "day after tomorrow": 2,
        "the day before yesterday": -2,
        "day before yesterday": -2,
    }
    if s in keywords:
        return today + timedelta(days=keywords[s])

    # Weekdays
    m = re.fullmatch(
        rf"(?:(next|last|this|coming|this coming|past|previous) )?({WEEKDAY_RE})", s
    )
    if m:
        mod = m.group(1)
        target = WEEKDAYS[m.group(2)]
        delta = (target - today.weekday()) % 7
        if mod in ("last", "past", "previous"):
            back = (today.weekday() - target) % 7
            return today - timedelta(days=back or 7)
        if mod == "next":
            return today + timedelta(days=delta or 7)
        # bare, "this", "coming": nearest on or after today
        return today + timedelta(days=delta)

    # "<weekday> next week" / "next week <weekday>"
    m = re.fullmatch(rf"({WEEKDAY_RE}) (next|last|this) week", s) or re.fullmatch(
        rf"(next|last|this) week (?:on )?({WEEKDAY_RE})", s
    )
    if m:
        groups = m.groups()
        wd = groups[0] if groups[0] in WEEKDAYS else groups[1]
        mod = groups[1] if groups[0] in WEEKDAYS else groups[0]
        monday = today - timedelta(days=today.weekday())
        shift = {"next": 7, "last": -7, "this": 0}[mod]
        return monday + timedelta(days=shift + WEEKDAYS[wd])

    # next/last/this week|month|year
    m = re.fullmatch(rf"(next|last|this|previous|coming) ({UNIT_RE})", s)
    if m:
        months, days = UNITS[m.group(2)]
        sign = {"next": 1, "coming": 1, "last": -1, "previous": -1, "this": 0}[
            m.group(1)
        ]
        return _apply(today, months, days, sign)

    return None


def _parse(s: str, today: date) -> date:
    if not s:
        raise ValueError("Empty date string")

    result = _relative_base(s, today)
    if result is not None:
        return result

    result = _absolute(s, today)
    if result is not None:
        return result

    # "in 3 days", "in a week"
    m = re.fullmatch(r"in (.+)", s)
    if m:
        months, days = _parse_duration(m.group(1))
        return _apply(today, months, days, 1)

    # "3 days ago", "two weeks from now", "5 days later"
    m = re.fullmatch(
        r"(.+?) (ago|back|earlier|before now|from now|later|hence|from today)", s
    )
    if m:
        months, days = _parse_duration(m.group(1))
        sign = -1 if m.group(2) in ("ago", "back", "earlier", "before now") else 1
        return _apply(today, months, days, sign)

    # "5 days before december 1 2025", "a week from tomorrow"
    m = re.fullmatch(r"(.+?) (before|after|from|since|prior to|following) (.+)", s)
    if m:
        months, days = _parse_duration(m.group(1))
        base = _parse(m.group(3), today)
        sign = -1 if m.group(2) in ("before", "prior to") else 1
        return _apply(base, months, days, sign)

    # "tomorrow plus 3 days", "today minus 1 week"
    m = re.fullmatch(r"(.+?) (plus|\+|minus|-) (.+)", s)
    if m:
        base = _parse(m.group(1), today)
        months, days = _parse_duration(m.group(3))
        sign = 1 if m.group(2) in ("plus", "+") else -1
        return _apply(base, months, days, sign)

    raise ValueError(f"Unrecognized date: {s!r}")


def parse(s: str, today: date | None = None) -> date:
    """Parse a natural-language date string into a ``datetime.date``.

    Raises ``ValueError`` if the string is not a recognized date.
    """
    if today is None:
        today = date.today()
    try:
        return _parse(_normalize(s), today)
    except ValueError:
        raise
    except (KeyError, IndexError, OverflowError) as e:
        raise ValueError(f"Unrecognized date: {s!r}") from e
