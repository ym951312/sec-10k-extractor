"""Stage 1 — the certified-complete ruler.

Submodules:

* :mod:`sec10k.ruler.tokens`        — shared word-token tokenizer
* :mod:`sec10k.ruler.formats`       — file-generation detection
* :mod:`sec10k.ruler.normalize`     — raw bytes -> ruler text + provenance
* :mod:`sec10k.ruler.completeness`  — normalization-completeness check (§3)
* :mod:`sec10k.ruler.headers_footers` — repeated header/footer stripping
* :mod:`sec10k.ruler.front_matter`  — cover-page / TOC isolation
"""
