"""Stage 2 acceptance: deterministic segmentation + full pipeline.

Anchors on the ``Item N`` enumerator + order (never the title string), with TOC
echoes / cross-references disambiguated away. The end-to-end positive test is
that a complete (if tiny) synthetic 10-K segments and passes the whole Stage 3
gate; targeted tests cover merge, reserved, IBR, and echo rejection.
"""

from __future__ import annotations

from pathlib import Path

from sec10k.enums import FilingStatus, ItemStatus
from sec10k.pipeline import run_pipeline
from sec10k.ruleset.loader import load_ruleset
from sec10k.segment import run_stage2
from sec10k.segment.anchors import find_anchors
from sec10k.stage1 import build_ruler

_FIXTURE = Path(__file__).parent / "fixtures" / "synthetic" / "mini_10k.txt"
RS = load_ruleset()


def test_full_pipeline_passes_on_complete_filing():
    raw = _FIXTURE.read_bytes()
    _ruler, result = run_pipeline(raw, RS)
    assert result.filing_status is FilingStatus.PASS, [
        v.message for v in result.verification_report.violations]
    assert all(result.verification_report.invariant_results.values())

    by_id = {it.item_id: it for it in result.items}
    # reserved Item 6 -> correctly empty, high confidence
    assert by_id["6"].status is ItemStatus.RESERVED
    # Part III items -> incorporated by reference
    for i in ("10", "11", "12", "13", "14"):
        assert by_id[i].status is ItemStatus.INCORPORATED_BY_REFERENCE
    # normal item extracted with a real span
    assert by_id["1"].status is ItemStatus.EXTRACTED
    assert by_id["1"].char_span.length > 0


def test_anchors_use_enumerator_not_title():
    raw = b"ITEM 1. BUSINESS\nbody\nITEM 1A. RISK FACTORS\nbody\n"
    anchors = find_anchors(build_ruler(raw).text)
    ids = [a.item_id for a in anchors]
    assert ids == ["1", "1A"]


def test_toc_echoes_not_double_counted():
    """Every detected item id is unique — the TOC's "Item N" echoes (inside the
    isolated TOC residual) must not produce duplicate anchors."""
    _ruler, result = run_pipeline(_FIXTURE.read_bytes(), RS)
    ids = [it.item_id for it in result.items if it.char_span is not None]
    assert len(ids) == len(set(ids)), ids
    assert ids == sorted(ids, key=lambda x: RS.order_index(x))  # in legal order


def test_cross_reference_midline_is_not_an_anchor():
    raw = b"ITEM 7. MD AND A\nPlease see Item 1A for a discussion of risk factors.\nmore body\n"
    ruler = build_ruler(raw)
    items, _ = run_stage2(ruler, RS)
    ids = [it.item_id for it in items]
    assert ids == ["7"]  # the mid-sentence "see Item 1A" is not anchored


def test_merged_heading_items_1_and_2():
    raw = (b"ITEMS 1 AND 2. BUSINESS AND PROPERTIES\n"
           b"We build robots and we lease facilities.\n"
           b"ITEM 3. LEGAL PROCEEDINGS\nNone.\n")
    ruler = build_ruler(raw)
    items, _ = run_stage2(ruler, RS)
    by_id = {it.item_id: it for it in items}
    assert by_id["1"].status is ItemStatus.MERGED
    assert by_id["1"].char_span is not None      # representative owns the span
    assert by_id["2"].status is ItemStatus.MERGED
    assert by_id["2"].merged_into == "1"
    assert by_id["2"].char_span is None          # absorbed member has no span

    # the merge is legal under the ruleset
    from sec10k.invariants.checks import check_legal_structure
    assert check_legal_structure(items, RS) == []


def test_reserved_item_detected():
    raw = b"ITEM 5. MARKET\nStock trades on Nasdaq.\nITEM 6. [Reserved]\nITEM 7. MD AND A\nRevenue grew.\n"
    items, _ = run_stage2(build_ruler(raw), RS)
    by_id = {it.item_id: it for it in items}
    assert by_id["6"].status is ItemStatus.RESERVED
