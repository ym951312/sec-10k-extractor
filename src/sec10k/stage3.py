"""Stage 3 entry point — gate candidate segmentation, produce a FilingResult.

This is the public surface other stages call. Given a certified ruler plus
candidate items + residual (from a future Stage 2, or — for now — synthetic span
fixtures), it runs the invariant gate and assembles the deliverable.
"""

from __future__ import annotations

from .contracts import (
    CharSpan,
    FilingResult,
    Item,
    ResidualSpan,
    Ruler,
    Ruleset,
)
from .invariants.gate import run_gate
from .invariants.report import annotate_items
from .ruleset.loader import load_ruleset


def run_stage3(
    ruler: Ruler,
    items: list[Item],
    residual: list[ResidualSpan],
    ruleset: Ruleset | None = None,
    *,
    xbrl_spans: list[CharSpan] | None = None,
    alt_items: list[Item] | None = None,
) -> FilingResult:
    """Gate the candidate segmentation and return a :class:`FilingResult`."""
    if ruleset is None:
        ruleset = load_ruleset()
    report = run_gate(ruler, items, residual, ruleset,
                      xbrl_spans=xbrl_spans, alt_items=alt_items)
    annotated = annotate_items(items, report.violations)
    return FilingResult(
        items=annotated,
        residual=residual,
        filing_status=report.filing_status,
        filing_confidence=report.filing_confidence,
        verification_report=report,
    )
