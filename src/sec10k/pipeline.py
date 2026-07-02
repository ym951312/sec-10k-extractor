"""End-to-end pipeline: Stage 1 (ruler) -> Stage 2 (segment) -> Stage 3 (gate).

No API key, no network. Stage 4 (LLM) is optional/off and not part of this build;
when a segment is low-confidence the result simply says so (honest degradation).
"""

from __future__ import annotations

from .contracts import Filing, FilingResult, Ruler, Ruleset
from .metadata import extract_fiscal_year_end
from .ruleset.loader import load_ruleset
from .segment import run_stage2
from .stage1 import build_ruler
from .stage3 import run_stage3


def run_pipeline(raw: bytes, ruleset: Ruleset | None = None) -> tuple[Ruler, FilingResult]:
    """Run the full deterministic pipeline on raw filing bytes.

    Returns ``(ruler, filing_result)`` — the ruler is returned too so callers
    (CLI / frontend) can show the Stage 1 certification alongside the gate.
    """
    # Extract document-level metadata and carry it on a Filing (Stage 0 input).
    filing = Filing(raw_bytes=raw, fiscal_year_end=extract_fiscal_year_end(raw))
    if ruleset is None:
        ruleset = load_ruleset(fiscal_year_end=filing.fiscal_year_end)
    ruler = build_ruler(raw)
    items, residual = run_stage2(ruler, ruleset)
    result = run_stage3(ruler, items, residual, ruleset)
    return ruler, result
