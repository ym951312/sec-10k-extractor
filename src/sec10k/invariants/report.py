"""Confidence aggregation + status decision (DESIGN.md §5).

Key asymmetry encoded here:

* ``failed`` = ANY hard invariant violation — a categorical judgement, score
  independent (one violation => failed).
* Among non-failed filings, ``pass`` vs ``review`` is a calibration threshold.
  Until calibrated against an eval set we do NOT treat numbers as probabilities;
  we emit high/med/low tiers (DESIGN.md §5).

``reserved`` / ``incorporated_by_reference`` items are *correctly empty* and are
scored HIGH confidence (well-understood, deductively justified) — never punished
as failures (CLAUDE.md rule 5).
"""

from __future__ import annotations

from ..contracts import Item, Violation
from ..enums import ConfidenceTier, FilingStatus, ItemStatus, Severity


def decide_filing(violations: list[Violation]) -> tuple[FilingStatus, ConfidenceTier]:
    """Map the violation set to a filing status + pre-calibration tier."""
    if any(v.severity is Severity.HARD for v in violations):
        return FilingStatus.FAILED, ConfidenceTier.LOW
    if violations:  # only soft signals
        return FilingStatus.REVIEW, ConfidenceTier.MEDIUM
    return FilingStatus.PASS, ConfidenceTier.HIGH


def item_confidence(item: Item, violations: list[Violation]) -> ConfidenceTier:
    """Per-item evidence tier (not a probability; pre-calibration)."""
    related = [v for v in violations if v.item_id == item.item_id]
    if any(v.severity is Severity.HARD for v in related):
        return ConfidenceTier.LOW
    if item.status in (ItemStatus.RESERVED, ItemStatus.INCORPORATED_BY_REFERENCE):
        return ConfidenceTier.HIGH  # correctly empty, well-understood
    if item.status is ItemStatus.FAILED:
        return ConfidenceTier.LOW
    if related:
        return ConfidenceTier.MEDIUM
    # extracted/merged with no related violation: evidence present but, with a
    # single deterministic method and no oracle, not "high" by default.
    return ConfidenceTier.MEDIUM


def annotate_items(items: list[Item], violations: list[Violation]) -> list[Item]:
    """Return copies of ``items`` with confidence tiers + reason codes filled in
    from the violations that reference them."""
    out: list[Item] = []
    for it in items:
        related = [v for v in violations if v.item_id == it.item_id]
        codes = list(dict.fromkeys([*it.reason_codes, *(v.code for v in related)]))
        out.append(it.model_copy(update={
            "confidence": item_confidence(it, violations),
            "reason_codes": codes,
        }))
    return out
