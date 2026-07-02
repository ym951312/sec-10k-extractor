"""sec10k — SEC 10-K item-level segmentation pipeline.

This milestone ships the two foundation stages only:

* Stage 1 — the certified-complete *ruler* (normalization + provenance +
  completeness check + header/footer stripping + cover/TOC isolation).
* Stage 3 — the invariant gate (DESIGN.md §5).

The core is pure-deterministic and requires no API key or network access.
"""

__version__ = "0.1.0"
