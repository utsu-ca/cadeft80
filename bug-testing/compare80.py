#!/usr/bin/env python3
"""Compare two 80-byte EFT files record by record.

Usage: python bug-testing/compare80.py expected.txt actual.txt

Each file is read in 80-byte records (a CRLF is expected after every record). Differences are reported per
record with 1-based column ranges, matching the positions used in the bank's field descriptions.
Exit status is 0 when the files are identical, 1 otherwise.
"""

from __future__ import annotations

from dataclasses import dataclass
from itertools import zip_longest
import sys

RECORD_LENGTH = 80
EOL = "\r\n"


@dataclass(frozen=True)
class Difference:
    record: int  # 1-based
    start: int  # 1-based column, inclusive; 0 for whole-record problems
    end: int
    expected: str
    actual: str

    def __str__(self) -> str:
        if self.start == 0:
            return f"record {self.record}: expected {self.expected}, got {self.actual}"
        cols = f"{self.start}" if self.start == self.end else f"{self.start}-{self.end}"
        return f"record {self.record} col {cols}: expected {self.expected!r}, got {self.actual!r}"


def split_records(text: str) -> list[str]:
    """Split on CRLF only; records are not trimmed or padded, so length problems stay visible."""
    records = text.split(EOL)
    if records and records[-1] == "":
        records.pop()
    return records


def compare_record(number: int, expected: str | None, actual: str | None) -> list[Difference]:
    if expected is None or actual is None:
        return [Difference(number, 0, 0, "<missing>" if expected is None else "a record",
                           "<missing>" if actual is None else "a record")]
    problems = [
        Difference(number, 0, 0, f"{RECORD_LENGTH} chars", f"{len(value)} chars in {label}")
        for label, value in (("expected", expected), ("actual", actual))
        if len(value) != RECORD_LENGTH
    ]
    run_start = None
    last = -2
    columns = [i for i, (a, b) in enumerate(zip_longest(expected, actual)) if a != b]
    for i in columns + [None]:
        if run_start is not None and (i is None or i != last + 1):
            problems.append(Difference(number, run_start + 1, last + 1,
                                       expected[run_start:last + 1], actual[run_start:last + 1]))
            run_start = None
        if i is not None:
            if run_start is None:
                run_start = i
            last = i
    return problems


def compare80(expected: str, actual: str) -> list[Difference]:
    """Return every difference between two files, comparing 80 bytes at a time."""
    pairs = zip_longest(split_records(expected), split_records(actual))
    result: list[Difference] = []
    for number, (exp, act) in enumerate(pairs, start=1):
        result.extend(compare_record(number, exp, act))
    return result


def main(argv: list[str]) -> int:
    if len(argv) != 3:
        print(__doc__, file=sys.stderr)
        return 2
    texts = []
    for path in argv[1:]:
        with open(path, encoding="utf-8", newline="") as source:
            texts.append(source.read())
    differences = compare80(*texts)
    for difference in differences:
        print(difference)
    print(f"{len(differences)} difference(s)")
    return 1 if differences else 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
