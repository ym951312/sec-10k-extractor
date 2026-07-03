"""The eight Stage 3 invariants (DESIGN.md §5).

Each invariant is a pure function returning a list of :class:`Violation` (empty =
passed). They are the fixed, non-learned arbiter: failure is *deductively*
provable against known constraints (order/overlap/coverage) without any ground
truth. All eight are HARD constraints (CLAUDE.md rule 4): any single violation
makes the filing ``failed``.

Geometry rule (plan §3.3-B): the no-overlap and coverage invariants operate over
the *geometry set* — each item's own span (only ``is_geometric`` items) plus
residual spans. Absorbed ``merged_into`` members contribute NO span (the merge
representative's single span covers their region), so a legal adjacent merge
cannot trip no-overlap. ``reserved`` / ``incorporated_by_reference`` items DO
contribute their heading/marker span (it is real ruler content) but are
correctly empty of a body — a PASS, never a coverage failure.
"""

from __future__ import annotations

from collections import defaultdict

from ..contracts import CharSpan, Item, ResidualSpan, Ruler, Ruleset, Violation
from ..enums import ReasonCode, ResidualClass, Severity
from ..ruleset.loader import allowed_absences

# A residual UNCLASSIFIED block longer than this is a red flag (inv 4).
_UNCLASSIFIED_RED_FLAG = 200
# Items that are commonly, legitimately absent ("None"/"Not applicable").
# Treated as allowed-absent for the should-exist invariant (inv 6).
#
# "1C" (Cybersecurity) is FISCAL-YEAR-CONDITIONAL: it is required only for fiscal
# years ending on/after 2023-12-15. With a single static ruleset and no
# fiscal-year-end extraction yet, we cannot assert it is required (a filing for
# FYE 2023-06-30 legitimately omits it), so we treat it as optional here. A real
# Stage 0 that selects the ruleset by fiscal_year_end would make this precise
# rather than blanket-optional.
OPTIONAL_ITEMS = {"1B", "1C", "9B", "9C", "16"}
# Cross-method boundary tolerance, in ruler characters (inv 8).
_CROSS_METHOD_TOL = 5


def _hard(code: ReasonCode, msg: str, item_id=None, span=None) -> Violation:
    return Violation(code=code, severity=Severity.HARD, message=msg,
                     item_id=item_id, char_span=span)


def _geometry_spans(items: list[Item], residual: list[ResidualSpan]):
    """The (span, label) set used by no-overlap / coverage. Plan §3.3-B."""
    out: list[tuple[CharSpan, str]] = []
    for it in items:
        if it.is_geometric and it.char_span is not None:
            out.append((it.char_span, f"item {it.item_id}"))
    for r in residual:
        out.append((r.char_span, f"residual:{r.classification.value}"))
    return out


# --------------------------------------------------------------------------- #
# inv 1 — order
# --------------------------------------------------------------------------- #
def check_order(items: list[Item], ruleset: Ruleset) -> list[Violation]:
    anchored = [it for it in items if it.char_span is not None and it.merged_into is None]
    anchored.sort(key=lambda it: it.char_span.start)
    viols: list[Violation] = []
    prev_idx, prev_id = -1, None
    for it in anchored:
        oi = ruleset.order_index(it.item_id)
        if oi is None:
            continue  # unknown item id — not an ordering signal
        if oi <= prev_idx:
            viols.append(_hard(
                ReasonCode.ORDER_VIOLATION,
                f"item {it.item_id} appears after {prev_id} but precedes it in legal order",
                it.item_id, it.char_span))
        else:
            prev_idx, prev_id = oi, it.item_id
    return viols


# --------------------------------------------------------------------------- #
# inv 2 — no overlap (item spans)
# --------------------------------------------------------------------------- #
def check_no_overlap(items: list[Item]) -> list[Violation]:
    spans = sorted(
        [(it.char_span, it.item_id) for it in items if it.is_geometric and it.char_span],
        key=lambda t: t[0].start,
    )
    viols: list[Violation] = []
    for (a, aid), (b, bid) in zip(spans, spans[1:]):
        if a.overlaps(b):
            viols.append(_hard(
                ReasonCode.OVERLAP,
                f"item {aid} span overlaps item {bid}",
                bid, b))
    return viols


# --------------------------------------------------------------------------- #
# inv 3 — coverage (items ∪ residual = ruler; no gap, no overlap)
# --------------------------------------------------------------------------- #
def check_coverage(ruler: Ruler, items: list[Item], residual: list[ResidualSpan]) -> list[Violation]:
    spans = sorted(_geometry_spans(items, residual), key=lambda t: t[0].start)
    viols: list[Violation] = []
    cursor = 0
    for span, label in spans:
        if span.start > cursor:
            gap = ruler.text[cursor:span.start]
            if gap.strip() != "":  # whitespace-only gaps are fine
                viols.append(_hard(
                    ReasonCode.COVERAGE_GAP,
                    f"unexplained gap [{cursor},{span.start}) before {label}: {gap.strip()[:40]!r}",
                    span=CharSpan(start=cursor, end=span.start)))
        elif span.start < cursor:
            viols.append(_hard(
                ReasonCode.COVERAGE_OVERLAP,
                f"overlap at {label}: starts {span.start} before cursor {cursor}",
                span=span))
        cursor = max(cursor, span.end)
    if cursor < ruler.length and ruler.text[cursor:].strip() != "":
        viols.append(_hard(
            ReasonCode.COVERAGE_GAP,
            f"unexplained trailing gap [{cursor},{ruler.length})",
            span=CharSpan(start=cursor, end=ruler.length)))
    return viols


# --------------------------------------------------------------------------- #
# inv 4 — residual sanity
# --------------------------------------------------------------------------- #
def check_residual_sanity(residual: list[ResidualSpan]) -> list[Violation]:
    viols: list[Violation] = []
    for r in residual:
        if r.classification is ResidualClass.UNCLASSIFIED and r.char_span.length > _UNCLASSIFIED_RED_FLAG:
            viols.append(_hard(
                ReasonCode.UNCLASSIFIED_RESIDUAL,
                f"large unclassified residual block ({r.char_span.length} chars) — red flag",
                span=r.char_span))
    return viols


# --------------------------------------------------------------------------- #
# inv 5 — legal structure membership
# --------------------------------------------------------------------------- #
def _merge_groups(items: list[Item]) -> list[set[str]]:
    groups: dict[str, set[str]] = defaultdict(set)
    for it in items:
        if it.merged_into:
            groups[it.merged_into].add(it.merged_into)
            groups[it.merged_into].add(it.item_id)
    return list(groups.values())


def _is_subitem(item_id: str) -> bool:
    """A letter-suffixed item id (e.g. "1A", "7A", "9C") — a sub-item that extends
    its parent main item. Judged structurally (trailing letter), NEVER by numeric
    value; "1" / "10" are main items, "1A" is a sub-item."""
    return item_id[-1:].isalpha()


def _is_adjacent(group: frozenset[str], ruleset: Ruleset) -> bool:
    """A merge group is legal iff its members are ADJACENT in the era's
    ``expected_items`` order — genuinely consecutive items that may legally share
    one heading/body (e.g. "Items 1 and 2").

    Adjacency is judged by POSITION in ``expected_items``, never by the numeric
    value of the item id. Pure index-consecutiveness is too strict for the modern
    era, though: main items 1 and 2 are separated in ``expected_items`` by the
    sub-items 1A/1B/1C, yet "Items 1 and 2" is a legal merge. So a member missing
    from ``expected_items`` is treated as non-adjacent (defensive), and two group
    members count as adjacent when everything BETWEEN them in expected order is
    either a fellow member or a letter-suffixed sub-item (which does not break
    main-item adjacency). A letterless MAIN item sitting between them (e.g. item 2
    between 1 and 3) does break adjacency -> illegal, preserving diagnostic power."""
    indices: list[int] = []
    for item_id in group:
        oi = ruleset.order_index(item_id)
        if oi is None:
            return False  # unknown id -> cannot confirm adjacency -> illegal
        indices.append(oi)
    indices.sort()
    member_idx = set(indices)
    lo, hi = indices[0], indices[-1]
    for i in range(lo + 1, hi):
        if i in member_idx:
            continue  # a fellow member of the merge group
        if _is_subitem(ruleset.expected_items[i]):
            continue  # an intervening sub-item does not break main-item adjacency
        return False  # a full main item sits between members -> non-adjacent
    return True


def check_legal_structure(items: list[Item], ruleset: Ruleset) -> list[Violation]:
    """inv 5 — structure-driven (not declaration-driven): a detected merge group
    is legal iff its members are ADJACENT in the era's expected order. Adjacent
    merges are legal evidence and need no ``legal_structures`` declaration; a
    non-adjacent / skip-numbered merge (e.g. 1+9) is still flagged, so the
    invariant keeps its diagnostic power (it does NOT degrade to always-true)."""
    detected = {frozenset(g) for g in _merge_groups(items)}
    viols: list[Violation] = []
    for group in detected:
        if _is_adjacent(group, ruleset):
            continue
        pretty = "+".join(sorted(group))
        viols.append(_hard(
            ReasonCode.ILLEGAL_STRUCTURE,
            f"merge group {pretty} is not adjacent in expected order"))
    return viols


# --------------------------------------------------------------------------- #
# inv 6 — should-exist
# --------------------------------------------------------------------------- #
def check_should_exist(items: list[Item], ruleset: Ruleset) -> list[Violation]:
    present = {it.item_id for it in items}
    permitted_absent = allowed_absences(ruleset) | OPTIONAL_ITEMS
    viols: list[Violation] = []
    for exp in ruleset.expected_items:
        if exp in present or exp in permitted_absent:
            continue
        viols.append(_hard(
            ReasonCode.MISSING_EXPECTED_ITEM,
            f"expected item {exp} is absent and not reserved / incorporated-by-reference / optional",
            item_id=exp))
    return viols


# --------------------------------------------------------------------------- #
# inv 7 — Item 8 XBRL cross-check (only when XBRL evidence is available)
# --------------------------------------------------------------------------- #
def check_item8_xbrl(items: list[Item], xbrl_spans: list[CharSpan] | None) -> list[Violation]:
    if not xbrl_spans:
        return []  # no XBRL evidence -> invariant not exercised (not a failure)
    item8 = next((it for it in items if it.item_id == "8" and it.char_span), None)
    if item8 is None:
        return []
    if any(item8.char_span.overlaps(x) for x in xbrl_spans):
        return []
    return [_hard(
        ReasonCode.XBRL_MISMATCH,
        "Item 8 boundary is not corroborated by any XBRL-tagged financial region",
        item_id="8", span=item8.char_span)]


# --------------------------------------------------------------------------- #
# inv 8 — cross-method consistency (only when >1 method)
# --------------------------------------------------------------------------- #
def check_cross_method(items: list[Item], alt_items: list[Item] | None) -> list[Violation]:
    if not alt_items:
        return []  # single method -> invariant not exercised
    alt = {it.item_id: it for it in alt_items if it.char_span}
    viols: list[Violation] = []
    for it in items:
        if it.char_span is None:
            continue
        other = alt.get(it.item_id)
        if other is None:
            continue
        if abs(other.char_span.start - it.char_span.start) > _CROSS_METHOD_TOL:
            viols.append(_hard(
                ReasonCode.CROSS_METHOD_DISAGREE,
                f"methods disagree on item {it.item_id} start "
                f"({it.char_span.start} vs {other.char_span.start})",
                it.item_id, it.char_span))
    return viols


# --------------------------------------------------------------------------- #
# inv 9 — cover-page dominance
# --------------------------------------------------------------------------- #
# A single COVER_PAGE residual spanning at least this fraction of the whole
# ruler is a red flag: the "cover page" is physically implausible and the body
# has almost certainly been mis-segmented into it (INTC FY2025 pattern, where a
# body with no Item N enumerators made ~99.4% of the doc a benign COVER_PAGE
# while 21 shell items from a trailing index table satisfied should-exist).
#
# CALIBRATION BOUNDARY (honest scope): 0.9 was calibrated on 21 real filings
# (ruler lengths 194k-1,249k chars) plus 2 synthetic fixtures. Legit filings
# measured cover/all <= 0.055 (max PFE); the two known failures measured >=
# 0.970 (C 0.970, INTC 0.994). Behaviour on filings far SMALLER than this
# calibration range (e.g. a few thousand chars, where a fixed-size cover page
# is a large fraction) is UNVERIFIED; revisit if the sample includes such files.
_COVER_DOMINANCE_MAX = 0.9


def check_cover_dominance(ruler: Ruler, residual: list[ResidualSpan]) -> list[Violation]:
    """inv 9 — a COVER_PAGE residual must not dominate the document.

    Closes the silent-PASS valve found in INTC FY2025: no other invariant
    inspects COVER_PAGE size, so a filing whose whole body was classified as a
    benign cover page passed 8/8. This check TIGHTENS the gate (silent -> loud);
    it never loosens any threshold. Uses only span geometry + the residual
    class label (never title strings)."""
    viols: list[Violation] = []
    if ruler.length == 0:
        return viols
    for r in residual:
        if r.classification is ResidualClass.COVER_PAGE:
            frac = r.char_span.length / ruler.length
            if frac >= _COVER_DOMINANCE_MAX:
                viols.append(_hard(
                    ReasonCode.OVERSIZED_COVER_PAGE,
                    f"cover_page residual spans {frac:.1%} of the document "
                    f"({r.char_span.length}/{ruler.length} chars) — body almost "
                    f"certainly mis-segmented into it",
                    span=r.char_span))
    return viols
