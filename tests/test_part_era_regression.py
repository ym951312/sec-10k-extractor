"""Test-first coverage for the era-blind `part` assignment defect.

RED (expected to FAIL until the fix): MSFT FY1994 Item 14 must be Part IV
(ERA_1994 declares Item 14 = Exhibits in Part IV), but the current segmenter
reads a hard-coded modern _PART_OF table and yields Part III.

GUARDRAIL (expected to PASS now and stay passing after the fix): the ordered
(item_id, part) sequence of 13 real fixtures must remain byte-for-byte unchanged
— catching any part drift OR item set/order change introduced by the fix.

Baselines below are pre-fix real pipeline outputs; do not edit them.
"""
import gzip
from pathlib import Path

import pytest

from sec10k.pipeline import run_pipeline

ROOT = Path(__file__).resolve().parents[1]
EVAL = ROOT / "tests" / "fixtures" / "eval_recent"
REAL = ROOT / "tests" / "fixtures" / "real"
if not EVAL.exists():  # fallback if CWD differs
    EVAL = Path("tests/fixtures/eval_recent")
    REAL = Path("tests/fixtures/real")

STD_MODERN = (  # 1-4=I, 5-9B=II, 10-14=III, 15=IV  (no 1C variant)
    ("1", "I"), ("1A", "I"), ("1B", "I"), ("2", "I"), ("3", "I"), ("4", "I"),
    ("5", "II"), ("6", "II"), ("7", "II"), ("7A", "II"), ("8", "II"), ("9", "II"),
    ("9A", "II"), ("9B", "II"), ("10", "III"), ("11", "III"), ("12", "III"),
    ("13", "III"), ("14", "III"), ("15", "IV"),
)
STD_MODERN_1C = (  # same, with 1C after 1B
    ("1", "I"), ("1A", "I"), ("1B", "I"), ("1C", "I"), ("2", "I"), ("3", "I"),
    ("4", "I"), ("5", "II"), ("6", "II"), ("7", "II"), ("7A", "II"), ("8", "II"),
    ("9", "II"), ("9A", "II"), ("9B", "II"), ("10", "III"), ("11", "III"),
    ("12", "III"), ("13", "III"), ("14", "III"), ("15", "IV"),
)
# DVN & APA: Items 1&2 merged -> "1","2" lead, then 1A/1B/1C...
MERGED_1C = (
    ("1", "I"), ("2", "I"), ("1A", "I"), ("1B", "I"), ("1C", "I"), ("3", "I"),
    ("4", "I"), ("5", "II"), ("6", "II"), ("7", "II"), ("7A", "II"), ("8", "II"),
    ("9", "II"), ("9A", "II"), ("9B", "II"), ("10", "III"), ("11", "III"),
    ("12", "III"), ("13", "III"), ("14", "III"), ("15", "IV"),
)
# BRK-B (FAILED): Item 1C present, Items 10-14 absent from detected set, 15=IV
BRKB = (
    ("1", "I"), ("1A", "I"), ("1B", "I"), ("1C", "I"), ("2", "I"), ("3", "I"),
    ("4", "I"), ("5", "II"), ("6", "II"), ("7", "II"), ("7A", "II"), ("8", "II"),
    ("9", "II"), ("9A", "II"), ("9B", "II"), ("15", "IV"),
)
# PFE (FAILED): no 1B, no 4, rest standard-with-1C
PFE = (
    ("1", "I"), ("1A", "I"), ("1C", "I"), ("2", "I"), ("3", "I"),
    ("5", "II"), ("6", "II"), ("7", "II"), ("7A", "II"), ("8", "II"), ("9", "II"),
    ("9A", "II"), ("9B", "II"), ("10", "III"), ("11", "III"), ("12", "III"),
    ("13", "III"), ("14", "III"), ("15", "IV"),
)

GUARDRAIL = {
    EVAL / "aapl_10k_20230930.htm.gz": STD_MODERN,
    EVAL / "nke_10k_20230531.htm.gz": STD_MODERN,
    EVAL / "pg_10k_20230630.htm.gz": STD_MODERN,
    EVAL / "jpm_10k_20251231.htm.gz": STD_MODERN_1C,
    EVAL / "tsla_10k_20251231.htm.gz": STD_MODERN_1C,
    EVAL / "wmt_10k_20260131.htm.gz": STD_MODERN_1C,
    EVAL / "pld_10k_20251231.htm.gz": STD_MODERN_1C,
    EVAL / "nee_10k_20251231.htm.gz": STD_MODERN_1C,
    EVAL / "dvn_10k_20251231.htm.gz": MERGED_1C,
    EVAL / "brkb_10k_20251231.htm.gz": BRKB,
    EVAL / "pfe_10k_20251231.htm.gz": PFE,
    REAL / "msft_10k_fy2023.htm.gz": STD_MODERN,
    REAL / "apa_10k_fy2023_merged12.htm.gz": MERGED_1C,
}

def _load(p: Path):
    b = p.read_bytes()
    return gzip.decompress(b) if p.suffix == ".gz" else b

def _ordered_parts(p: Path):
    _ruler, result = run_pipeline(_load(p))
    return tuple((it.item_id, (it.part if it.part is not None else "-")) for it in result.items)


@pytest.mark.parametrize("path,expected", list(GUARDRAIL.items()), ids=lambda x: getattr(x, "name", ""))
def test_part_guardrail_ordered_sequence_unchanged(path, expected):
    """13 real fixtures: (item_id, part) ordered sequence must stay unchanged."""
    if not path.exists():
        pytest.skip(f"fixture not found: {path}")
    assert _ordered_parts(path) == expected


def test_msft_fy1994_item14_is_part_IV():
    """RED until fix: ERA_1994 Item 14 = Exhibits (Part IV), not Part III."""
    p = REAL / "msft_10k_fy1994_ascii.txt.gz"
    if not p.exists():
        pytest.skip(f"fixture not found: {p}")
    _ruler, result = run_pipeline(_load(p))
    items = {it.item_id: it for it in result.items}
    assert "14" in items, "Item 14 not detected in MSFT FY1994"
    part = items["14"].part
    part = getattr(part, "value", part)
    assert part == "IV", f"MSFT FY1994 Item 14 part={part}, expected IV"


def test_msft_fy1994_items_1_to_13_parts_unchanged():
    """Guardrail: fixing Item 14 must not disturb items 1-13 of MSFT FY1994."""
    p = REAL / "msft_10k_fy1994_ascii.txt.gz"
    if not p.exists():
        pytest.skip(f"fixture not found: {p}")
    expected_1_13 = (
        ("1", "I"), ("2", "I"), ("3", "I"), ("4", "I"), ("5", "II"), ("6", "II"),
        ("7", "II"), ("8", "II"), ("9", "II"), ("10", "III"), ("11", "III"),
        ("12", "III"), ("13", "III"),
    )
    seq = _ordered_parts(p)
    assert seq[:13] == expected_1_13, f"MSFT FY1994 items 1-13 changed: {seq[:13]}"
