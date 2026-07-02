"""Document-level metadata extraction (Stage 0 prerequisite).

This module extracts the filing's fiscal-year-end from raw bytes so a future
Stage 0 can select the era-appropriate ruleset by ``fiscal_year_end``. It is
standalone: it depends on no other stage's product and only reads ``raw``.

Two eras, two authoritative sources (verified against real fixtures):

* ASCII-era EDGAR full submissions carry an SGML header field
  ``CONFORMED PERIOD OF REPORT`` whose value is ``YYYYMMDD`` (e.g. ``19940630``).
* Modern inline-XBRL ``.htm`` filings have no SGML header; the authoritative
  value is the inline-XBRL fact tagged ``name="dei:DocumentPeriodEndDate"``,
  whose visible text is human-readable (e.g. ``June 30, 2023``).

The two sources are mutually exclusive per filing, so we try SGML first and fall
back to XBRL. HTML parsing uses the stdlib ``html.parser`` (same choice as
``ruler/normalize.py``), so no third-party dependency is introduced.
"""

from __future__ import annotations

import re
from datetime import datetime
from html.parser import HTMLParser
from typing import Optional

# --- SGML header branch --------------------------------------------------- #
# The SGML header is plain text with a fixed layout: the field name, a colon,
# a tab, then the 8-digit YYYYMMDD value. Allow flexible whitespace after the
# colon to tolerate minor variation while staying anchored to this one line.
_SGML_PERIOD = re.compile(rb"CONFORMED PERIOD OF REPORT:\s*(\d{8})")

# --- XBRL branch ---------------------------------------------------------- #
_DEI_PERIOD_NAME = "dei:documentperiodenddate"  # html.parser lower-cases attrs? see below
# Human-readable date formats seen in dei:DocumentPeriodEndDate visible text.
_HUMAN_DATE_FORMATS = ("%B %d, %Y", "%b %d, %Y")


def _iso_from_yyyymmdd(value: str) -> Optional[str]:
    """``19940630`` -> ``1994-06-30`` (validated via datetime)."""
    try:
        return datetime.strptime(value, "%Y%m%d").date().isoformat()
    except ValueError:
        return None


def _iso_from_human(text: str) -> Optional[str]:
    """``June 30, 2023`` -> ``2023-06-30``; returns None if unparseable."""
    cleaned = " ".join(text.split())  # collapse whitespace
    for fmt in _HUMAN_DATE_FORMATS:
        try:
            return datetime.strptime(cleaned, fmt).date().isoformat()
        except ValueError:
            continue
    return None


def _extract_from_sgml(raw: bytes) -> Optional[str]:
    """Branch 1: SGML ``CONFORMED PERIOD OF REPORT`` (YYYYMMDD)."""
    m = _SGML_PERIOD.search(raw)
    if m is None:
        return None
    return _iso_from_yyyymmdd(m.group(1).decode("ascii"))


class _DeiPeriodParser(HTMLParser):
    """Find the inline-XBRL fact tagged ``name="dei:DocumentPeriodEndDate"`` and
    capture its visible text — mirrors the subclass-HTMLParser approach in
    ``ruler/normalize.py``. We key on the ``name`` attribute (the authoritative
    marker), NOT on any date string that may appear elsewhere in the document."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self._capturing = False
        self._depth = 0
        self.value: Optional[str] = None

    def handle_starttag(self, tag: str, attrs) -> None:
        if self.value is not None:
            return  # already captured the first authoritative tag
        if self._capturing:
            self._depth += 1  # a nested tag inside the fact (e.g. a <span>)
            return
        for name, val in attrs:
            if name == "name" and val is not None and val.strip().lower() == _DEI_PERIOD_NAME:
                self._capturing = True
                self._depth = 0
                self._parts: list[str] = []
                return

    def handle_data(self, data: str) -> None:
        if self._capturing:
            self._parts.append(data)

    def handle_endtag(self, tag: str) -> None:
        if not self._capturing:
            return
        if self._depth > 0:
            self._depth -= 1  # closing a nested inner tag
            return
        # closing the fact tag itself -> finalize
        self._capturing = False
        self.value = "".join(self._parts).strip()


def _extract_from_xbrl(raw: bytes) -> Optional[str]:
    """Branch 2: inline-XBRL ``dei:DocumentPeriodEndDate`` visible text."""
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError:
        text = raw.decode("latin-1")
    parser = _DeiPeriodParser()
    parser.feed(text)
    parser.close()
    if not parser.value:
        return None
    return _iso_from_human(parser.value)


def extract_fiscal_year_end(raw: bytes) -> Optional[str]:
    """Extract the filing's fiscal-year-end as ISO ``YYYY-MM-DD``, or ``None``.

    Tries the SGML-header branch first (ASCII-era full submissions); if that
    field is absent, falls back to the inline-XBRL ``dei:DocumentPeriodEndDate``
    branch (modern filings). Reads ``raw`` only; never mutates it.
    """
    return _extract_from_sgml(raw) or _extract_from_xbrl(raw)
