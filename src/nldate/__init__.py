"""nldate: turn natural-language date strings into datetime.date objects."""

from nldate.parser import parse

__all__ = ["main", "parse"]


def main() -> None:
    import sys

    text = " ".join(sys.argv[1:])
    print(parse(text).isoformat())
