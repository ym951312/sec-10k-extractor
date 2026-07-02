"""Ruleset — per-fiscal-year legal expectations (Stage 0 product).

This milestone ships a minimal static table + interface; full Stage 0
spec-ingestion (Federal Register / Reg S-K revision history) is out of scope.
"""

from .loader import load_ruleset, minimal_modern_ruleset

__all__ = ["load_ruleset", "minimal_modern_ruleset"]
