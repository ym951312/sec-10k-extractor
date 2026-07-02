"""Normalization-completeness check (DESIGN.md §3, Stage 1 step toward step 2).

This is what *certifies* the ruler. The conservation equation (single direction,
matching the contract docstring and plan §3.2/§3.3-A):

    source visible tokens  ==  ruler tokens  ⊎  ledger(stripped-visible) tokens

i.e. "original visible text = what stayed on the ruler + what was deliberately
stripped-and-recorded". ``XBRL_HIDDEN`` ledger entries are audit-only and appear
on neither side (the regex baseline also drops ``<ix:hidden>``), so they cannot
cause a false FAIL or a double count.

The baseline comes from :func:`sec10k.ruler.normalize.visible_baseline_text`, a
regex path independent of the DOM walker, so the check is non-circular.
"""

from __future__ import annotations

from collections import Counter

from ..contracts import CompletenessReport, StrippedEntry
from ..enums import FileGeneration
from .normalize import visible_baseline_text
from .tokens import token_multiset

# Cap on how many example diff tokens we surface in the report.
_MAX_EXAMPLES = 50


def check_completeness(
    raw_text: str,
    generation: FileGeneration,
    ruler_text: str,
    ledger: list[StrippedEntry],
) -> CompletenessReport:
    """Certify (or reject) the ruler against the independent visible baseline."""
    baseline_ms = token_multiset(visible_baseline_text(raw_text, generation))

    ruler_ms = token_multiset(ruler_text)
    ledger_visible_ms: Counter[str] = Counter()
    for entry in ledger:
        if entry.is_visible:
            ledger_visible_ms.update(token_multiset(entry.text))

    accounted = ruler_ms + ledger_visible_ms

    missing = baseline_ms - accounted     # in source, lost from ruler+ledger
    extra = accounted - baseline_ms       # accounted but absent from source

    passed = not missing and not extra
    return CompletenessReport(
        passed=passed,
        source_visible_tokens=sum(baseline_ms.values()),
        ruler_tokens=sum(ruler_ms.values()),
        stripped_visible_tokens=sum(ledger_visible_ms.values()),
        missing_tokens=_examples(missing),
        extra_tokens=_examples(extra),
    )


def _examples(diff: Counter[str]) -> list[str]:
    out: list[str] = []
    for tok, n in diff.items():
        out.extend([tok] * n)
        if len(out) >= _MAX_EXAMPLES:
            return out[:_MAX_EXAMPLES]
    return out
