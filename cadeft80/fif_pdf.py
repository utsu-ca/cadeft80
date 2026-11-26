"""Extract routing numbers from a Payments Canada FIF directory PDF.

Each entry contains a routing number in two forms, 0BBBTTTTT and TTTTT-BBB, e.g.
`001000550 00550-010`; only that pair is extracted.
"""

from __future__ import annotations

import csv
import re
import shutil
import subprocess
from typing import TextIO

from . import CadeftError

CSV_COLUMNS = ("institution id", "transit")
# 0BBBTTTTT TTTTT-BBB: the only consistent part of an entry
_ROUTING = re.compile(r"(?<!\d)0(\d{3})(\d{5})\s+(\d{5})-(\d{3})(?!\d)")


def pdf_to_text(path: str) -> str:
    """Uses pypdf when installed (pip install pypdf), otherwise the `pdftotext` command."""
    try:
        from pypdf import PdfReader
    except ImportError:
        exe = shutil.which("pdftotext")
        if exe is None:
            raise CadeftError("reading PDFs needs the pypdf package or the pdftotext command") from None
        return subprocess.run([exe, "-layout", path, "-"], check=True, capture_output=True,
                              text=True).stdout
    return "\n".join(page.extract_text() or "" for page in PdfReader(path).pages)


def parse_fif_text(text: str) -> list[tuple[str, str]]:
    """Returns unique (institution id, transit) pairs in document order; both forms must agree."""
    found: dict[tuple[str, str], None] = {}
    for bank, transit, t2, b2 in _ROUTING.findall(text):
        if (bank, transit) == (b2, t2):
            found[(bank, transit)] = None
    if not found:
        raise CadeftError("no routing numbers found (expected '001000550 00550-010')")
    return list(found)


def write_fif_csv(entries: list[tuple[str, str]], out: TextIO) -> None:
    writer = csv.writer(out, lineterminator="\n")
    writer.writerow(CSV_COLUMNS)
    writer.writerows(entries)
