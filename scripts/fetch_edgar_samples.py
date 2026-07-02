#!/usr/bin/env python3
"""Fetch a few representative real 10-K filings from EDGAR into
``tests/fixtures/real/`` (gzipped), for the integration test.

This is a MANUAL, one-off helper — it is NOT run by the test suite, which stays
zero-network by default. SEC requires a descriptive User-Agent with contact
info; set ``SEC_USER_AGENT`` or edit ``_UA`` below.

Stratify across generations (DESIGN.md §5 eval-set strategy): ASCII / HTML /
HTML+XBRL, and across era / size / domestic vs foreign issuers. The list below is
a starting point; add more URLs to broaden coverage.

    python scripts/fetch_edgar_samples.py
"""

from __future__ import annotations

import gzip
import os
import sys
import urllib.request
from pathlib import Path

_UA = os.environ.get("SEC_USER_AGENT", "sec10k-research contact@example.com")
_DEST = Path(__file__).resolve().parents[1] / "tests" / "fixtures" / "real"

# (output filename, primary-document URL). Add cross-generation samples here.
_SAMPLES = [
    ("msft_10k_fy2023.htm.gz",
     "https://www.sec.gov/Archives/edgar/data/789019/000095017023035122/msft-20230630.htm"),
    # Example ASCII-generation filing (pre-HTML). Uncomment / replace with a
    # verified accession when broadening coverage:
    # ("acme_10k_1997.txt.gz",
    #  "https://www.sec.gov/Archives/edgar/data/XXdataXX/XXXXXX.txt"),
]


def fetch(url: str) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": _UA})
    with urllib.request.urlopen(req, timeout=60) as resp:  # noqa: S310 (trusted host)
        return resp.read()


def main() -> int:
    _DEST.mkdir(parents=True, exist_ok=True)
    for name, url in _SAMPLES:
        out = _DEST / name
        print(f"fetching {url}")
        try:
            raw = fetch(url)
        except Exception as exc:  # noqa: BLE001
            print(f"  FAILED: {exc}", file=sys.stderr)
            continue
        data = gzip.compress(raw) if name.endswith(".gz") else raw
        out.write_bytes(data)
        print(f"  wrote {out} ({len(data)} bytes, from {len(raw)} raw)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
