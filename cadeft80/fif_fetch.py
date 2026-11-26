"""Find and download the latest Payments Canada Banks Numeric List PDF."""

from __future__ import annotations

import re
import tempfile
import urllib.request
from urllib.parse import urljoin

from . import CadeftError

DIRECTORY_URL = "https://www.payments.ca/payment-resources/directories?field_directory_type=11"
_LINK = re.compile(r"""href=["']([^"']*?(\d{4}-\d{2}-\d{2})-Banks_Numeric_List\.pdf)["']""", re.I)
_HEADERS = {"User-Agent": "Mozilla/5.0 (cadeft80)"}


def _get(url: str) -> bytes:
    request = urllib.request.Request(url, headers=_HEADERS)
    try:
        with urllib.request.urlopen(request, timeout=60) as response:
            return response.read()
    except OSError as exc:
        raise CadeftError(f"could not fetch {url}: {exc}") from exc


def find_latest_url(html: str, base: str = DIRECTORY_URL) -> str:
    """Picks the link with the newest YYYY-MM-DD-Banks_Numeric_List.pdf date."""
    links = {(date, urljoin(base, href)) for href, date in _LINK.findall(html)}
    if not links:
        raise CadeftError("no '*-Banks_Numeric_List.pdf' link found on the directories page")
    return max(links)[1]


def download_latest(page_url: str = DIRECTORY_URL) -> str:
    """Downloads the latest PDF to a temporary file and returns its path."""
    url = find_latest_url(_get(page_url).decode("utf-8", "replace"), page_url)
    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as out:
        out.write(_get(url))
    return out.name
