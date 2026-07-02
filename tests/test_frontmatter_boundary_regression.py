"""Regression tests for the Stage-1 TOC end-boundary defect.

These assert the GROUND-TRUTH structure of four recent real 10-Ks (from
tests/fixtures/eval_recent/). They are EXPECTED TO FAIL until the front_matter
TOC-boundary defect is fixed:

  * A-group (BRK-B / JPM / NKE): the body 'Item 1. Business' heading is wrongly
    swallowed by the TOC region, so Item 1 is never detected.
  * PG: the TOC run breaks at an internal 929-char gap; the tail TOC entries leak
    out and the downstream monotonic gate then suppresses the entire body, so
    Items 1..8 are missing and become one large unclassified residual.

Ground truth is structural (SEC Reg S-K item layout for the relevant era) and
verifiable by reading the filing; it is NOT copied from current pipeline output.
"""
import gzip
from pathlib import Path

import pytest

from sec10k.pipeline import run_pipeline

EVAL = Path(__file__).resolve().parents[1] / "tests" / "fixtures" / "eval_recent"

# resolve eval dir robustly whether tests/ is CWD or repo root is
if not EVAL.exists():
    EVAL = Path(__file__).resolve().parent / "fixtures" / "eval_recent"


def _load(name: str):
    p = EVAL / name
    raw = p.read_bytes()
    return gzip.decompress(raw) if p.suffix == ".gz" else raw


def _run(name: str):
    if not (EVAL / name).exists():
        pytest.skip(f"fixture not found: {name}")
    _ruler, result = run_pipeline(_load(name))
    return result


def _by_id(result):
    return {it.item_id: it for it in result.items}


def _status_name(it):
    s = getattr(it, "status", None)
    return getattr(s, "name", None) or str(s)


A_GROUP = [
    "brkb_10k_20251231.htm.gz",
    "jpm_10k_20251231.htm.gz",
    "nke_10k_20230531.htm.gz",
]


@pytest.mark.parametrize("fixture", A_GROUP)
def test_a_group_item1_business_is_detected(fixture):
    """Item 1 (Business) must be present and be real extracted content."""
    result = _run(fixture)
    items = _by_id(result)
    assert "1" in items, f"{fixture}: Item 1 (Business) was not detected at all"
    assert _status_name(items["1"]) == "EXTRACTED", (
        f"{fixture}: Item 1 present but status="
        f"{_status_name(items['1'])}, expected EXTRACTED"
    )


def test_pg_early_items_are_detected():
    """PG: Items 1..8 must all be detected (not swallowed into residual)."""
    result = _run("pg_10k_20230630.htm.gz")
    items = _by_id(result)
    expected_present = ["1", "1A", "2", "3", "4", "5", "7", "7A", "8"]
    missing = [i for i in expected_present if i not in items]
    assert not missing, f"PG: these Part I/II items were not detected: {missing}"
    assert _status_name(items["1"]) == "EXTRACTED", (
        f"PG: Item 1 status={_status_name(items['1'])}, expected EXTRACTED"
    )


def test_pg_body_not_lost_to_unclassified_residual():
    """PG: the body must not collapse into large unclassified residual blocks."""
    result = _run("pg_10k_20230630.htm.gz")

    def cls_name(rc):
        c = getattr(rc, "classification", None)
        return getattr(c, "name", None) or str(c)

    def span_len(rc):
        cs = getattr(rc, "char_span", None)
        try:
            return cs.end - cs.start
        except Exception:
            return 0

    big_unclassified = [
        rc for rc in result.residual
        if cls_name(rc) == "UNCLASSIFIED" and span_len(rc) > 1000
    ]
    assert not big_unclassified, (
        f"PG: found {len(big_unclassified)} large unclassified residual block(s) "
        f"(lens={[span_len(rc) for rc in big_unclassified]}); body was not segmented"
    )
