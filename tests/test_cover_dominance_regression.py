"""Regression guard for inv 9 (cover_dominance): a COVER_PAGE residual must not
dominate the whole document.

This is the RED-first test for the INTC FY2025 silent-PASS fix. Before inv 9
exists, INTC passes 8/8 (a ~99.4% cover page is treated as benign); this file
asserts it MUST be FAILED. It also pins the *expected* redundant hit on C
(already loud-FAILED, now also carrying OVERSIZED_COVER_PAGE) and guards the
other 19 real fixtures against regression (their status must not change).

Fixtures are public EDGAR data with no answer keys (Level-2 breadth extension).
"""

from __future__ import annotations

import gzip
from pathlib import Path

import pytest

from sec10k.enums import FilingStatus, ReasonCode
from sec10k.pipeline import run_pipeline

_R1 = Path(__file__).parent / "fixtures" / "eval_recent"
_R2 = Path(__file__).parent / "fixtures" / "eval_recent_r2"


def _run(path: Path):
    raw = gzip.decompress(path.read_bytes()) if path.suffix == ".gz" else path.read_bytes()
    _ruler, result = run_pipeline(raw)
    return result


def _find(dir_: Path, stem_prefix: str) -> Path:
    hits = sorted(dir_.glob(f"{stem_prefix}_10k_*.htm.gz"))
    assert len(hits) == 1, f"expected exactly 1 fixture for {stem_prefix}, got {hits}"
    return hits[0]


def test_intc_is_failed_by_cover_dominance():
    """INTC FY2025: body has no Item N enumerators, so ~99.4% of the doc is a
    single COVER_PAGE. Before inv 9 this passed 8/8 (silent). It MUST fail, and
    the cover_dominance invariant specifically must be the tripped one."""
    result = _run(_find(_R2, "intc"))
    assert result.filing_status is FilingStatus.FAILED, (
        "INTC must be loud FAILED once cover_dominance exists")
    assert result.verification_report.invariant_results["cover_dominance"] is False
    assert ReasonCode.OVERSIZED_COVER_PAGE in {
        v.code for v in result.verification_report.violations}


def test_c_redundantly_flagged_but_still_failed():
    """C (Citigroup) already loud-FAILED (0 items -> missing-item violations).
    Its whole-doc fill-gap COVER_PAGE (~0.97) also trips inv 9 — a harmless
    redundant hit. Pinning it so the 12->13 violation count is not later
    mistaken for a regression."""
    result = _run(_find(_R2, "c"))
    assert result.filing_status is FilingStatus.FAILED
    assert result.verification_report.invariant_results["cover_dominance"] is False
    assert ReasonCode.OVERSIZED_COVER_PAGE in {
        v.code for v in result.verification_report.violations}


# status measured on the 21-fixture baseline BEFORE inv 9; inv 9 must not change
# any of these.
_UNCHANGED_STATUS = {
    ("eval_recent", "aapl"): FilingStatus.PASS,
    ("eval_recent", "brkb"): FilingStatus.FAILED,
    ("eval_recent", "dvn"):  FilingStatus.PASS,
    ("eval_recent", "jpm"):  FilingStatus.PASS,
    ("eval_recent", "nee"):  FilingStatus.FAILED,
    ("eval_recent", "nke"):  FilingStatus.PASS,
    ("eval_recent", "pfe"):  FilingStatus.FAILED,
    ("eval_recent", "pg"):   FilingStatus.PASS,
    ("eval_recent", "pld"):  FilingStatus.PASS,
    ("eval_recent", "tsla"): FilingStatus.PASS,
    ("eval_recent", "wmt"):  FilingStatus.PASS,
    ("eval_recent_r2", "amd"):   FilingStatus.PASS,
    ("eval_recent_r2", "apo"):   FilingStatus.PASS,
    ("eval_recent_r2", "avgo"):  FilingStatus.PASS,
    ("eval_recent_r2", "bac"):   FilingStatus.PASS,
    ("eval_recent_r2", "blk"):   FilingStatus.PASS,
    ("eval_recent_r2", "googl"): FilingStatus.PASS,
    ("eval_recent_r2", "kkr"):   FilingStatus.FAILED,
    ("eval_recent_r2", "nvda"):  FilingStatus.FAILED,
}


@pytest.mark.parametrize("key,expected", list(_UNCHANGED_STATUS.items()))
def test_other_fixtures_status_unchanged(key, expected):
    dir_name, stem = key
    base = _R1 if dir_name == "eval_recent" else _R2
    result = _run(_find(base, stem))
    assert result.filing_status is expected, (
        f"{stem}: status changed to {result.filing_status.name}, expected {expected.name}")


_PASS_FIXTURES = [(d, s) for (d, s), st in _UNCHANGED_STATUS.items()
                  if st is FilingStatus.PASS]


@pytest.mark.parametrize("key", _PASS_FIXTURES)
def test_pass_fixtures_do_not_trip_cover_dominance(key):
    dir_name, stem = key
    base = _R1 if dir_name == "eval_recent" else _R2
    result = _run(_find(base, stem))
    assert result.verification_report.invariant_results["cover_dominance"] is True, (
        f"{stem}: cover_dominance wrongly tripped on a PASS fixture")
