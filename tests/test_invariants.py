"""Step 6 acceptance: the §5 invariant gate.

For every invariant: a passing fixture and a targeted violation fixture that
MUST trip it. Plus the load-bearing special cases (CLAUDE.md rule 5):
``reserved`` / ``incorporated_by_reference`` are correctly empty => PASS, and a
legal adjacent merge (Items 1&2) does not trip no-overlap/coverage.

Stage 2 does not exist yet: these layouts are hand-built synthetic span lists,
which is exactly how the gate's logic is certified independently of the
not-yet-built segmenter.
"""

from __future__ import annotations

from fixtures.spans import Seg, build_layout, standard_valid_layout

from sec10k.contracts import CharSpan, Item, ResidualSpan, Ruler
from sec10k.enums import (
    ConfidenceTier,
    FileGeneration,
    FilingStatus,
    ItemStatus,
    ReasonCode,
    ResidualClass,
)
from sec10k.invariants.checks import check_legal_structure
from sec10k.invariants.gate import run_gate
from sec10k.ruleset.loader import load_ruleset

RS = load_ruleset()


def _gate(layout, **kw):
    return run_gate(layout.ruler, layout.items, layout.residual, RS, **kw)


def _codes(report):
    return {v.code for v in report.violations}


# --------------------------------------------------------------------------- #
# Whole-gate pass
# --------------------------------------------------------------------------- #
def test_standard_layout_passes_all():
    report = _gate(standard_valid_layout())
    assert report.filing_status is FilingStatus.PASS, _codes(report)
    assert report.filing_confidence is ConfidenceTier.HIGH
    assert all(report.invariant_results.values()), report.invariant_results


# --------------------------------------------------------------------------- #
# inv 1 — order
# --------------------------------------------------------------------------- #
def test_order_pass():
    assert _gate(standard_valid_layout()).invariant_results["order"]


def test_order_violation():
    layout = build_layout([
        Seg("item", "1A", "ITEM 1A risk factors. "),
        Seg("item", "1", "ITEM 1 business. "),  # 1 after 1A => out of order
    ])
    report = _gate(layout)
    assert report.invariant_results["order"] is False
    assert ReasonCode.ORDER_VIOLATION in _codes(report)
    # any hard violation => categorical failed
    assert report.filing_status is FilingStatus.FAILED


# --------------------------------------------------------------------------- #
# inv 2 — no overlap (incl. legal merge must NOT trip it)
# --------------------------------------------------------------------------- #
def test_no_overlap_pass():
    assert _gate(standard_valid_layout()).invariant_results["no_overlap"]


def test_overlap_violation():
    ruler = Ruler(text="X" * 40, file_generation=FileGeneration.HTML_XBRL)
    items = [
        Item(item_id="1", char_span=CharSpan(start=0, end=20)),
        Item(item_id="2", char_span=CharSpan(start=10, end=40)),  # overlaps 1
    ]
    report = run_gate(ruler, items, [], RS)
    assert report.invariant_results["no_overlap"] is False
    assert ReasonCode.OVERLAP in _codes(report)


def test_merged_items_1_and_2_pass():
    """Items 1&2 share one heading/body: representative '1' owns the span, '2'
    is merged_into='1' with no span. No-overlap, coverage, order, legal-structure
    all PASS (plan §3.3-B)."""
    layout = build_layout([
        Seg("residual", "cover_page", "COVER. "),
        Seg("item", "1", "ITEMS 1 AND 2 business and properties we build and lease. "),
        Seg("merged_member", "2", "", merged_into="1"),
        Seg("item", "3", "ITEM 3 legal none. "),
    ])
    report = _gate(layout)
    assert report.invariant_results["no_overlap"]
    assert report.invariant_results["coverage"]
    assert report.invariant_results["order"]
    assert report.invariant_results["legal_structure"]


# --------------------------------------------------------------------------- #
# inv 5 — legal structure is STRUCTURE-driven (adjacency), not declaration-driven.
# These call check_legal_structure directly with hand-built merged Items so the
# adjacency judgement is certified in isolation. The load-bearing case is
# "non-adjacent merge is STILL flagged" — proof inv 5 did not degrade to
# always-true when we dropped the legal_structures.merges declaration lookup.
# --------------------------------------------------------------------------- #
def _merged_pair(lead: str, absorbed: str) -> list[Item]:
    """A minimal two-item merge: representative ``lead`` owns a span, ``absorbed``
    is merged_into=lead with no span (the shape run_stage2 produces)."""
    return [
        Item(item_id=lead, status=ItemStatus.MERGED,
             char_span=CharSpan(start=0, end=10)),
        Item(item_id=absorbed, status=ItemStatus.MERGED, merged_into=lead,
             char_span=None),
    ]


def test_legal_structure_adjacent_merge_1_2_is_legal():
    # 1 and 2 are adjacent main items (only sub-items 1A/1B/1C sit between) -> legal
    assert check_legal_structure(_merged_pair("1", "2"), RS) == []


def test_legal_structure_adjacent_merge_2_3_is_legal():
    assert check_legal_structure(_merged_pair("2", "3"), RS) == []


def test_legal_structure_nonadjacent_merge_1_9_is_flagged():
    # DIAGNOSTIC-POWER GUARD: 1 and 9 are far apart -> must still be ILLEGAL.
    viols = check_legal_structure(_merged_pair("1", "9"), RS)
    assert viols, "non-adjacent merge 1+9 must be flagged"
    assert any(v.code is ReasonCode.ILLEGAL_STRUCTURE for v in viols)


def test_legal_structure_skip_numbered_merge_1_3_is_flagged():
    # 1 and 3 skip the intervening MAIN item 2 -> non-adjacent -> ILLEGAL.
    viols = check_legal_structure(_merged_pair("1", "3"), RS)
    assert viols, "skip-numbered merge 1+3 must be flagged"
    assert any(v.code is ReasonCode.ILLEGAL_STRUCTURE for v in viols)


def test_legal_structure_three_consecutive_merge_is_legal():
    items = [
        Item(item_id="1", status=ItemStatus.MERGED, char_span=CharSpan(start=0, end=10)),
        Item(item_id="2", status=ItemStatus.MERGED, merged_into="1", char_span=None),
        Item(item_id="3", status=ItemStatus.MERGED, merged_into="1", char_span=None),
    ]
    assert check_legal_structure(items, RS) == []


def test_legal_structure_no_merge_is_legal():
    # No merged_into anywhere -> no merge group -> nothing to flag.
    items = [
        Item(item_id="1", char_span=CharSpan(start=0, end=10)),
        Item(item_id="2", char_span=CharSpan(start=10, end=20)),
    ]
    assert check_legal_structure(items, RS) == []


# --------------------------------------------------------------------------- #
# inv 3 — coverage
# --------------------------------------------------------------------------- #
def test_coverage_pass():
    assert _gate(standard_valid_layout()).invariant_results["coverage"]


def test_coverage_gap_violation():
    text = "AAAAA" + "REALCONTENT" + "BBBBB"  # gap [5,16) is non-whitespace
    ruler = Ruler(text=text, file_generation=FileGeneration.HTML_XBRL)
    items = [
        Item(item_id="1", char_span=CharSpan(start=0, end=5)),
        Item(item_id="2", char_span=CharSpan(start=16, end=len(text))),
    ]
    report = run_gate(ruler, items, [], RS)
    assert report.invariant_results["coverage"] is False
    assert ReasonCode.COVERAGE_GAP in _codes(report)


def test_coverage_whitespace_gap_is_ok():
    text = "AAAAA" + "     " + "BBBBB"  # gap is whitespace only
    ruler = Ruler(text=text, file_generation=FileGeneration.HTML_XBRL)
    items = [
        Item(item_id="1", char_span=CharSpan(start=0, end=5)),
        Item(item_id="2", char_span=CharSpan(start=10, end=len(text))),
    ]
    report = run_gate(ruler, items, [], RS)
    assert report.invariant_results["coverage"] is True


# --------------------------------------------------------------------------- #
# inv 4 — residual sanity
# --------------------------------------------------------------------------- #
def test_residual_sanity_pass():
    assert _gate(standard_valid_layout()).invariant_results["residual_sanity"]


def test_large_unclassified_residual_violation():
    big = "z" * 300
    ruler = Ruler(text=big, file_generation=FileGeneration.HTML_XBRL)
    residual = [ResidualSpan(
        char_span=CharSpan(start=0, end=300),
        classification=ResidualClass.UNCLASSIFIED)]
    report = run_gate(ruler, [], residual, RS)
    assert report.invariant_results["residual_sanity"] is False
    assert ReasonCode.UNCLASSIFIED_RESIDUAL in _codes(report)


# --------------------------------------------------------------------------- #
# inv 5 — legal structure
# --------------------------------------------------------------------------- #
def test_legal_structure_pass_standard():
    assert _gate(standard_valid_layout()).invariant_results["legal_structure"]


def test_illegal_structure_violation():
    # merge {1,3} is non-adjacent and not in the ruleset's legal structures
    layout = build_layout([
        Seg("item", "1", "ITEM 1 business. "),
        Seg("merged_member", "3", "", merged_into="1"),
    ])
    report = _gate(layout)
    assert report.invariant_results["legal_structure"] is False
    assert ReasonCode.ILLEGAL_STRUCTURE in _codes(report)


# --------------------------------------------------------------------------- #
# inv 6 — should-exist (incl. reserved / IBR are NOT failures)
# --------------------------------------------------------------------------- #
def test_should_exist_pass_with_reserved_and_ibr():
    # standard layout has Item 6 reserved and Items 10-14 IBR; must pass
    assert _gate(standard_valid_layout()).invariant_results["should_exist"]


def test_part_iii_absent_entirely_is_allowed():
    """Items 10-14 absent (not even listed) is legal via the Part III
    incorporation-by-reference structure — not a missing-item violation."""
    segs = [Seg("item", i, f"ITEM {i} content. ") for i in
            ["1", "1A", "1C", "2", "3", "4", "5", "7", "7A", "8", "9", "9A", "15"]]
    segs.insert(8, Seg("item", "6", "ITEM 6 [Reserved]. ", status=ItemStatus.RESERVED))
    report = _gate(build_layout(segs))
    assert report.invariant_results["should_exist"], _codes(report)


def test_missing_required_item_violation():
    # Item 1 (required, not reserved/IBR/optional) is absent
    segs = [Seg("item", i, f"ITEM {i} content. ") for i in
            ["1A", "1C", "2", "3", "4", "5", "7", "7A", "8", "9", "9A", "15"]]
    segs.insert(7, Seg("item", "6", "ITEM 6 [Reserved]. ", status=ItemStatus.RESERVED))
    report = _gate(build_layout(segs))
    assert report.invariant_results["should_exist"] is False
    assert ReasonCode.MISSING_EXPECTED_ITEM in _codes(report)
    assert any(v.item_id == "1" for v in report.violations)


# --------------------------------------------------------------------------- #
# inv 7 — Item 8 XBRL (only when evidence supplied)
# --------------------------------------------------------------------------- #
def test_item8_xbrl_pass_when_corroborated():
    layout = standard_valid_layout()
    item8 = next(it for it in layout.items if it.item_id == "8")
    # an XBRL-tagged region overlapping Item 8
    xbrl = [CharSpan(start=item8.char_span.start + 1, end=item8.char_span.end - 1)]
    report = _gate(layout, xbrl_spans=xbrl)
    assert report.invariant_results["item8_xbrl"]


def test_item8_xbrl_mismatch_violation():
    layout = standard_valid_layout()
    # an XBRL region far from Item 8 (in the cover area)
    xbrl = [CharSpan(start=0, end=5)]
    report = _gate(layout, xbrl_spans=xbrl)
    assert report.invariant_results["item8_xbrl"] is False
    assert ReasonCode.XBRL_MISMATCH in _codes(report)


def test_item8_xbrl_not_exercised_without_evidence():
    # no xbrl_spans => invariant passes (not exercised, not a failure)
    assert _gate(standard_valid_layout()).invariant_results["item8_xbrl"]


# --------------------------------------------------------------------------- #
# inv 8 — cross-method consistency (only when >1 method)
# --------------------------------------------------------------------------- #
def test_cross_method_agreement_pass():
    layout = standard_valid_layout()
    alt = [it.model_copy() for it in layout.items]  # identical second method
    report = _gate(layout, alt_items=alt)
    assert report.invariant_results["cross_method"]


def test_cross_method_disagreement_violation():
    layout = standard_valid_layout()
    item8 = next(it for it in layout.items if it.item_id == "8")
    shifted = item8.model_copy(update={
        "char_span": CharSpan(start=item8.char_span.start + 50,
                              end=item8.char_span.end + 50)})
    report = _gate(layout, alt_items=[shifted])
    assert report.invariant_results["cross_method"] is False
    assert ReasonCode.CROSS_METHOD_DISAGREE in _codes(report)


# --------------------------------------------------------------------------- #
# Special cases: reserved / IBR confidence (correctly empty => PASS, HIGH)
# --------------------------------------------------------------------------- #
def test_reserved_and_ibr_items_score_high_and_unflagged():
    from sec10k.stage3 import run_stage3

    layout = standard_valid_layout()
    result = run_stage3(layout.ruler, layout.items, layout.residual, RS)
    by_id = {it.item_id: it for it in result.items}
    assert by_id["6"].status is ItemStatus.RESERVED
    assert by_id["6"].confidence is ConfidenceTier.HIGH
    assert by_id["6"].reason_codes == []
    assert by_id["10"].status is ItemStatus.INCORPORATED_BY_REFERENCE
    assert by_id["10"].confidence is ConfidenceTier.HIGH
    assert result.filing_status is FilingStatus.PASS
