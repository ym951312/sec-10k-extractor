"""The Stage 3 gate — run all invariants, build the verification report.

This is the fixed arbiter every later stage flows back through (including, in a
future Stage 4, LLM proposals: the LLM proposes, this gate disposes). It needs
no API key or network.
"""

from __future__ import annotations

from ..contracts import (
    CharSpan,
    Item,
    ResidualSpan,
    Ruler,
    Ruleset,
    VerificationReport,
)
from . import checks
from .report import decide_filing


def run_gate(
    ruler: Ruler,
    items: list[Item],
    residual: list[ResidualSpan],
    ruleset: Ruleset,
    *,
    xbrl_spans: list[CharSpan] | None = None,
    alt_items: list[Item] | None = None,
) -> VerificationReport:
    """Run the nine invariants and aggregate into a :class:`VerificationReport`.

    ``xbrl_spans`` (inv 7) and ``alt_items`` (inv 8) are optional evidence
    channels; when absent those invariants are simply not exercised (a pass, not
    a failure).
    """
    results: dict[str, bool] = {}
    violations = []

    def run(name: str, found):
        results[name] = len(found) == 0
        violations.extend(found)

    run("order", checks.check_order(items, ruleset))
    run("no_overlap", checks.check_no_overlap(items))
    run("coverage", checks.check_coverage(ruler, items, residual))
    run("residual_sanity", checks.check_residual_sanity(residual))
    run("legal_structure", checks.check_legal_structure(items, ruleset))
    run("should_exist", checks.check_should_exist(items, ruleset))
    run("item8_xbrl", checks.check_item8_xbrl(items, xbrl_spans))
    run("cross_method", checks.check_cross_method(items, alt_items))
    run("cover_dominance", checks.check_cover_dominance(ruler, residual))

    status, confidence = decide_filing(violations)
    return VerificationReport(
        violations=violations,
        invariant_results=results,
        filing_status=status,
        filing_confidence=confidence,
    )
