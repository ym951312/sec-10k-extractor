"""Tests for document-level fiscal-year-end extraction (Stage 0 prerequisite).

Runs against the REAL fixtures (no synthetic mini strings), one per era:

* MSFT FY1994 — ASCII full submission -> SGML ``CONFORMED PERIOD OF REPORT``.
* MSFT FY2023 — inline-XBRL .htm       -> ``dei:DocumentPeriodEndDate`` fact.

.gz fixtures are read the same way as tests/test_real_integration.py.
"""

from __future__ import annotations

import gzip
from pathlib import Path

from sec10k.contracts import Filing
from sec10k.metadata import extract_fiscal_year_end

_REAL = Path(__file__).parent / "fixtures" / "real"


def _read(name: str) -> bytes:
    return gzip.decompress((_REAL / name).read_bytes())


def test_fiscal_year_end_ascii_sgml_header():
    raw = _read("msft_10k_fy1994_ascii.txt.gz")
    assert extract_fiscal_year_end(raw) == "1994-06-30"


def test_fiscal_year_end_modern_inline_xbrl():
    raw = _read("msft_10k_fy2023.htm.gz")
    assert extract_fiscal_year_end(raw) == "2023-06-30"


def test_filing_object_carries_extracted_fiscal_year_end():
    """End-to-end guard: a Filing built the way run_pipeline builds it (raw_bytes
    + extract_fiscal_year_end) carries the correct FYE for each era. run_pipeline
    keeps Filing as a local, so we assert on the same construction it uses."""
    cases = {
        "msft_10k_fy1994_ascii.txt.gz": "1994-06-30",
        "msft_10k_fy2023.htm.gz": "2023-06-30",
        "apa_10k_fy2023_merged12.htm.gz": "2023-12-31",
    }
    for name, expected in cases.items():
        raw = _read(name)
        filing = Filing(raw_bytes=raw, fiscal_year_end=extract_fiscal_year_end(raw))
        assert filing.fiscal_year_end == expected, name
