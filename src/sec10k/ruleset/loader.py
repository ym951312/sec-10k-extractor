"""Minimal static Ruleset table + loader (DESIGN.md §2, Stage 0 interface).

Only enough to exercise the Stage 3 invariants (5/6 especially) and avoid
misjudging legal filings. The interface (``load_ruleset``) is pinned so a real
Stage 0 can later index many rulesets by fiscal-year-end without changing
callers.

Knowledge here is read from the spec (DESIGN.md §6: "read the spec, do not learn
from history"): e.g. Item 6 has been ``[Reserved]`` since 2021 and Item 1C
(Cybersecurity) exists from FY2023.
"""

from __future__ import annotations

from ..contracts import LegalStructure, Ruleset
from ..enums import FileGeneration
from .era import (
    ERA_1994,
    ERA_2005,
    ERA_2020,
    ERA_2023,
    EraRuleset,
    ItemExpectation,
)

# Legal item order for a modern (FY>=2023) 10-K, by part. Anchor identity is the
# item NUMBER + order — never a caption string.
_MODERN_EXPECTED = [
    # Part I
    "1", "1A", "1B", "1C", "2", "3", "4",
    # Part II
    "5", "6", "7", "7A", "8", "9", "9A", "9B", "9C",
    # Part III
    "10", "11", "12", "13", "14",
    # Part IV
    "15", "16",
]

_PART_OF = {
    **{i: "I" for i in ("1", "1A", "1B", "1C", "2", "3", "4")},
    **{i: "II" for i in ("5", "6", "7", "7A", "8", "9", "9A", "9B", "9C")},
    **{i: "III" for i in ("10", "11", "12", "13", "14")},
    **{i: "IV" for i in ("15", "16")},
}

# The minimal legal-structure set (plan §3.3-C): standard, the two common
# adjacent merges, and Part III incorporation-by-reference.
_MODERN_LEGAL_STRUCTURES = [
    LegalStructure(name="standard"),
    LegalStructure(name="items_1_2_merged", merges=[["1", "2"]]),
    LegalStructure(name="items_2_3_merged", merges=[["2", "3"]]),
    LegalStructure(
        name="part_iii_incorporated_by_reference",
        absences=["10", "11", "12", "13", "14"],
    ),
]


def minimal_modern_ruleset(fiscal_year_end: str = "2023-12-31") -> Ruleset:
    """A minimal modern 10-K ruleset (FY>=2023)."""
    return Ruleset(
        fiscal_year_end=fiscal_year_end,
        expected_items=list(_MODERN_EXPECTED),
        reserved_items={"6"},  # Selected Financial Data removed -> Item 6 [Reserved]
        item_parts={i: p for i, p in _PART_OF.items() if p is not None},
        legal_structures=list(_MODERN_LEGAL_STRUCTURES),
        file_generation=FileGeneration.HTML_XBRL,
    )


# --------------------------------------------------------------------------- #
# Stage 0 picker: choose an EraRuleset by fiscal_year_end, then adapt it to the
# contracts.Ruleset the downstream (segmenter / checks / allowed_absences)
# already consumes ("route A" adapter — downstream is untouched).
# --------------------------------------------------------------------------- #
# Eras oldest -> newest. Each covers the half-open FYE interval
# [effective_from_fye, effective_until_fye): from is inclusive, until exclusive.
# ISO "YYYY-MM-DD" string comparison equals date comparison, so plain string
# ordering is used.
_ERAS: list[EraRuleset] = [ERA_1994, ERA_2005, ERA_2020, ERA_2023]


def _pick_era(fiscal_year_end: str | None) -> EraRuleset:
    """Select the EraRuleset whose [from, until) FYE window contains ``fye``.

    ``effective_from_fye=None`` means no lower bound (oldest era);
    ``effective_until_fye=None`` means no upper bound (newest, open interval).
    """
    # FYE missing (extraction failed): degrade to the newest era. Most filings we
    # process are recent, so the newest ruleset is the least-wrong default.
    if fiscal_year_end is None:
        return ERA_2023
    for era in _ERAS:
        lo, hi = era.effective_from_fye, era.effective_until_fye
        if (lo is None or lo <= fiscal_year_end) and (hi is None or fiscal_year_end < hi):
            return era
    # Windows are contiguous and cover all dates, so this is unreachable; fall
    # back to the newest era rather than raising, to stay honest-degrading.
    return ERA_2023


def _era_to_ruleset(era: EraRuleset, fiscal_year_end: str | None) -> Ruleset:
    """Adapt an EraRuleset to a contracts.Ruleset providing the four interfaces
    downstream relies on: expected_items (order), reserved_items, legal_structures,
    and (via expected_items) order_index()."""
    # expected_items = items the era expects to be PRESENT, in item order.
    #   * REQUIRED / RESERVED are kept (RESERVED is a present-but-empty slot).
    #   * ABSENT excluded (the item does not exist in this era).
    #   * CONDITIONAL excluded (present-or-absent both legal; putting it here
    #     would make downstream flag a filing that legally omits 9C/16 as missing).
    #   Order is preserved from era.items, so Ruleset.order_index() works.
    expected_items = [
        r.item_id for r in era.items
        if r.expectation in (ItemExpectation.REQUIRED, ItemExpectation.RESERVED)
    ]
    reserved_items = {
        r.item_id for r in era.items if r.expectation is ItemExpectation.RESERVED
    }
    return Ruleset(
        fiscal_year_end=fiscal_year_end or "2023-12-31",
        expected_items=expected_items,
        reserved_items=reserved_items,
        item_parts={r.item_id: r.part.value for r in era.items if r.part is not None},
        legal_structures=list(era.legal_structures),  # same LegalStructure type
        # file_generation is a placeholder here: the real generation is detected by
        # Stage 1 (detect_generation), not decided by the era. EraRuleset dropped
        # this field, so we fill the modern default to satisfy the Ruleset schema.
        file_generation=FileGeneration.HTML_XBRL,
    )


def load_ruleset(fiscal_year_end: str | None = None) -> Ruleset:
    """Load the ruleset for a fiscal-year-end (Stage 0 interface).

    Picks the era whose FYE window contains ``fiscal_year_end`` and adapts it to a
    contracts.Ruleset (route-A adapter, so downstream callers are unchanged). FYE
    ``None`` degrades to the newest era. Signature is unchanged from before."""
    era = _pick_era(fiscal_year_end)
    return _era_to_ruleset(era, fiscal_year_end)


def part_of(item_id: str) -> str | None:
    """Legal Part (I..IV) an item belongs to, per the modern ruleset."""
    return _PART_OF.get(item_id)


def allowed_absences(ruleset: Ruleset) -> set[str]:
    """Item ids that may be legitimately absent: reserved slots + every
    incorporation-by-reference absence authorized by a legal structure."""
    out: set[str] = set(ruleset.reserved_items)
    for ls in ruleset.legal_structures:
        out.update(ls.absences)
    return out
