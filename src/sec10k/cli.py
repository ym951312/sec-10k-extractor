"""Command-line entry point. Runs Stage 1 -> Stage 3 on a filing and prints a
report. Requires NO API key and NO network access.

    sec10k path/to/filing.html          # human-readable report
    sec10k path/to/filing.html --json   # FilingResult as JSON

Honesty note: Stage 2 (deterministic segmentation) is intentionally NOT part of
this foundation milestone. With no segmenter, the Stage 3 gate runs on the
items available (currently the Stage 1 residual candidates only), so it will
honestly report low confidence / unmet should-exist — exactly the graceful
degradation the design calls for, not a silent false success.
"""

from __future__ import annotations

import argparse
import sys
from collections import Counter
from pathlib import Path

from .contracts import Ruler
from .pipeline import run_pipeline
from .ruleset.loader import load_ruleset


def _format_stage1(ruler: Ruler) -> str:
    lines = ["=" * 64, "STAGE 1 — CERTIFIED-COMPLETE RULER", "=" * 64]
    lines.append(f"file generation : {ruler.file_generation.value}")
    lines.append(f"ruler length    : {ruler.length} chars")
    if ruler.completeness is not None:
        c = ruler.completeness
        mark = "✓ CERTIFIED" if c.passed else "✗ FAILED"
        lines.append(f"completeness    : {mark}  ({c.summary()})")
        if not c.passed:
            if c.missing_tokens:
                lines.append(f"  missing (sample): {c.missing_tokens[:10]}")
            if c.extra_tokens:
                lines.append(f"  extra   (sample): {c.extra_tokens[:10]}")

    ledger_counts = Counter(e.classification.value for e in ruler.stripped_ledger)
    lines.append(f"stripped ledger : {dict(ledger_counts) or '{} (nothing stripped)'}")

    if ruler.residual_candidates:
        lines.append("residual cands  :")
        for rc in ruler.residual_candidates:
            sp = rc.char_span
            preview = " ".join(ruler.text[sp.start:sp.end].split())[:48]
            lines.append(f"  - {rc.classification.value:14s} [{sp.start},{sp.end})  {preview!r}")
    else:
        lines.append("residual cands  : (none detected)")
    return "\n".join(lines)


def _format_stage2(result) -> str:
    lines = ["", "=" * 64, "STAGE 2 — DETERMINISTIC SEGMENTATION", "=" * 64]
    lines.append(f"items detected  : {len(result.items)}")
    for it in result.items:
        span = f"[{it.char_span.start},{it.char_span.end})" if it.char_span else "(no span)"
        extra = f" -> merged_into {it.merged_into}" if it.merged_into else ""
        lines.append(f"  - Item {it.item_id:4s} {it.status.value:26s} {it.confidence.value:6s} {span}{extra}")
    from collections import Counter
    rc = Counter(r.classification.value for r in result.residual)
    lines.append(f"residual        : {dict(rc) or '{}'}")
    return "\n".join(lines)


def _format_stage3(result) -> str:
    lines = ["", "=" * 64, "STAGE 3 — INVARIANT GATE", "=" * 64]
    for name, passed in result.verification_report.invariant_results.items():
        lines.append(f"  [{'PASS' if passed else 'FAIL'}] {name}")
    lines.append("")
    lines.append(f"filing_status     : {result.filing_status.value}")
    lines.append(f"filing_confidence : {result.filing_confidence.value}")
    viols = result.verification_report.violations
    if viols:
        lines.append(f"violations ({len(viols)}, showing up to 8):")
        for v in viols[:8]:
            lines.append(f"  - [{v.severity.value}] {v.code.value}: {v.message}")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="sec10k",
        description="Run Stage 1 (certified ruler) -> Stage 3 (invariant gate) on a 10-K. No API key required.",
    )
    parser.add_argument("path", type=Path, help="path to a raw 10-K filing")
    parser.add_argument("--json", action="store_true", help="emit FilingResult as JSON")
    parser.add_argument("--fiscal-year-end", default=None, help="ruleset key (default: modern)")
    args = parser.parse_args(argv)

    if not args.path.is_file():
        print(f"error: no such file: {args.path}", file=sys.stderr)
        return 2

    raw = args.path.read_bytes()
    ruleset = load_ruleset(args.fiscal_year_end)
    ruler, result = run_pipeline(raw, ruleset)

    if args.json:
        print(result.model_dump_json(indent=2))
    else:
        print(_format_stage1(ruler))
        print(_format_stage2(result))
        print(_format_stage3(result))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
