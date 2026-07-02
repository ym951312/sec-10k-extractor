"""Shared word-token tokenizer for the completeness conservation check.

The completeness invariant (DESIGN.md §3) is stated over *word tokens*, not raw
characters, so it is **robust to whitespace normalization** (collapsing runs of
spaces/newlines is allowed) while still catching any *visible word* that is
silently dropped.

A token = a maximal run of "word" characters: Unicode letters/digits plus a few
intra-word punctuation marks that occur inside numbers and identifiers in
filings (``. , / - & %``). Standalone punctuation and whitespace are not tokens.
"""

from __future__ import annotations

import re
from collections import Counter

# Keep intra-word punctuation that appears inside financial tokens like
# "1,234.5", "10-K", "S&P", "12%". Everything else is a separator.
_TOKEN_RE = re.compile(r"[^\W_]+(?:[.,/\-&%][^\W_]+)*", re.UNICODE)


def tokenize(text: str) -> list[str]:
    """Split ``text`` into normalized word tokens (lower-cased)."""
    return [m.group(0).lower() for m in _TOKEN_RE.finditer(text)]


def token_multiset(text: str) -> Counter[str]:
    """Multiset (Counter) of word tokens in ``text``."""
    return Counter(tokenize(text))
