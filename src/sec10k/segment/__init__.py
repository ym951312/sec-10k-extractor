"""Stage 2 — deterministic segmentation (the cheap layer; zero API cost).

Anchors on the ``Item N`` enumerator + order (NEVER on the caption/title string,
which changes topic by year and disappears on merge — CLAUDE.md rule 2). The
output (candidate items + residual) flows straight back through the Stage 3
gate, which is the fixed arbiter.

Submodules:

* :mod:`sec10k.segment.anchors`   — variant-tolerant ``Item N`` anchor detection
* :mod:`sec10k.segment.segmenter` — disambiguation, structure, span assembly
"""

from .segmenter import run_stage2

__all__ = ["run_stage2"]
