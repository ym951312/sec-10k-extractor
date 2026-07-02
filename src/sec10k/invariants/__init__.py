"""Stage 3 — the invariant gate (DESIGN.md §5).

* :mod:`sec10k.invariants.checks` — the eight invariant functions
* :mod:`sec10k.invariants.report` — confidence aggregation + status decision
* :mod:`sec10k.invariants.gate`   — runs the checks, builds the report
"""

from .gate import run_gate

__all__ = ["run_gate"]
