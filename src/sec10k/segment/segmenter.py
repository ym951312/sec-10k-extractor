"""Stage 2 segmentation: anchors -> disambiguation -> structure -> spans.

Produces candidate ``items`` + ``residual`` on the ruler's coordinates, both
*positively identified* (never one as the complement of the other). The only
complement-like move is filling leftover non-whitespace gaps with an explicitly
flagged ``unclassified`` residual — that is the §3 red-flag catch, not a silent
absorption. The result flows back through the Stage 3 gate unchanged.
"""

from __future__ import annotations

import re

from ..contracts import CharSpan, Item, ResidualSpan, Ruler, Ruleset
from ..enums import ItemStatus, ResidualClass
from ..ruleset.loader import part_of
from .anchors import AnchorMatch, find_anchors

# Body of a reserved slot is short and says "[Reserved]" (DESIGN.md §2).
_RESERVED = re.compile(r"\breserved\b", re.IGNORECASE)
_RESERVED_BODY_MAX = 80
# Incorporation-by-reference cues (Part III -> proxy statement).
_IBR = re.compile(r"incorporated\s+by\s+reference|proxy\s+statement|see\s+proxy", re.IGNORECASE)
_PART_III = {"10", "11", "12", "13", "14"}
# A line that is a Part divider: "PART I", "PART II — FINANCIAL", etc.
_PART_DIVIDER = re.compile(r"(?im)^[^\S\n]*part[^\S\n]+(i{1,3}|iv)\b[^\S\n]*[.:–—-]?[^\S\n]*$")
# A signatures heading near the end of the document.
_SIGNATURES = re.compile(r"(?im)^[^\S\n]*signatures?\b[^\S\n]*$")
# Unclassified residual smaller than this is not worth flagging as a red flag,
# but is still positively recorded (kept below the inv-4 threshold).
_MIN_GAP = 1


# --------------------------------------------------------------------------- #
# disambiguation
# --------------------------------------------------------------------------- #
def _in_any(pos: int, regions: list[CharSpan]) -> bool:
    return any(r.start <= pos < r.end for r in regions)


def _greedy_monotonic(anchors: list[AnchorMatch], ruleset: Ruleset) -> list[AnchorMatch]:
    """Keep anchors that advance the ruleset's legal order (DESIGN.md §4: the
    "expected next item" sequence is the strongest cheap false-positive filter).

    Walking in document order, accept an anchor only if its order index strictly
    exceeds the last accepted one. This drops TOC echoes and cross-references
    ("see Item 1A") that repeat or jump backward, and naturally dedups repeats.
    Unknown ids (not in the ruleset) are skipped here.
    """
    accepted: list[AnchorMatch] = []
    last = -1
    for a in anchors:
        idx = ruleset.order_index(a.item_id)
        if idx is None or idx <= last:
            continue
        accepted.append(a)
        last = idx
    return accepted


# --------------------------------------------------------------------------- #
# structure detection
# --------------------------------------------------------------------------- #
def _find_part_dividers(text: str, exclude: list[CharSpan]) -> list[CharSpan]:
    spans: list[CharSpan] = []
    for m in _PART_DIVIDER.finditer(text):
        s = text.rfind("\n", 0, m.start()) + 1
        e = m.end()
        if not _in_any(s, exclude):
            spans.append(CharSpan(start=s, end=e))
    return spans


def _find_signatures(text: str) -> CharSpan | None:
    last = None
    for m in _SIGNATURES.finditer(text):
        last = m
    if last is None:
        return None
    s = text.rfind("\n", 0, last.start()) + 1
    return CharSpan(start=s, end=len(text))


def _status_for(item_id: str, body: str) -> ItemStatus:
    stripped = body.strip()
    if _RESERVED.search(body) and len(stripped) <= _RESERVED_BODY_MAX:
        return ItemStatus.RESERVED
    if item_id in _PART_III and _IBR.search(body):
        return ItemStatus.INCORPORATED_BY_REFERENCE
    return ItemStatus.EXTRACTED


# --------------------------------------------------------------------------- #
# span assembly
# --------------------------------------------------------------------------- #
def _first_cut(seg_start: int, seg_end: int, cuts: list[int]) -> int:
    """Earliest cut point strictly inside (seg_start, seg_end), else seg_end."""
    best = seg_end
    for c in cuts:
        if seg_start < c < best:
            best = c
    return best


def _fill_gaps(text: str, claimed: list[CharSpan], first_item: int) -> list[ResidualSpan]:
    """Positively classify every leftover non-whitespace ruler region.

    A gap BEFORE the first item is front matter (preamble such as a
    forward-looking-statements note) — benign, classified ``cover_page``. A gap
    between or after items is genuinely unexplained content → ``unclassified``,
    the §3 red flag (a sign the segmenter missed or mis-cut an item).
    Whitespace-only gaps are left alone.
    """
    out: list[ResidualSpan] = []
    cursor = 0
    for sp in sorted(claimed, key=lambda s: s.start):
        if sp.start > cursor:
            _emit_gap(text, cursor, sp.start, first_item, out)
        cursor = max(cursor, sp.end)
    if cursor < len(text):
        _emit_gap(text, cursor, len(text), first_item, out)
    return out


def _emit_gap(text: str, start: int, end: int, first_item: int, out: list[ResidualSpan]) -> None:
    if end - start < _MIN_GAP or text[start:end].strip() == "":
        return
    cls = ResidualClass.COVER_PAGE if start < first_item else ResidualClass.UNCLASSIFIED
    out.append(ResidualSpan(char_span=CharSpan(start=start, end=end), classification=cls))


def run_stage2(ruler: Ruler, ruleset: Ruleset) -> tuple[list[Item], list[ResidualSpan]]:
    """Segment a certified ruler into candidate items + residual."""
    text = ruler.text
    n = len(text)

    # 1. front-matter regions isolated by Stage 1 (cover page, TOC) are off-limits
    #    for anchors and dividers — pre-dismantles the fake-title trap.
    front = [rc.char_span for rc in ruler.residual_candidates
             if rc.classification in (ResidualClass.COVER_PAGE, ResidualClass.TOC)]

    # 2. anchors -> drop those inside front matter -> order-monotonic accept
    anchors = [a for a in find_anchors(text) if not _in_any(a.enum_start, front)]
    accepted = _greedy_monotonic(anchors, ruleset)

    # 3. structure: part dividers (carved out) + signatures (trailing residual)
    parts = _find_part_dividers(text, front)
    signatures = _find_signatures(text)
    cuts = [p.start for p in parts] + ([signatures.start] if signatures else [])

    # 4. build item spans (each item runs to the next anchor, clipped at the
    #    first part-divider / signatures boundary inside it)
    items: list[Item] = []
    starts = [a.start for a in accepted] + [n]
    for i, a in enumerate(accepted):
        seg_start = a.start
        seg_end = _first_cut(seg_start, starts[i + 1], cuts)
        span = CharSpan(start=seg_start, end=seg_end)
        status = _status_for(a.item_id, text[seg_start:seg_end])
        items.append(Item(item_id=a.item_id, part=ruleset.part_of(a.item_id),
                          char_span=span, status=status))
        if a.merged_id is not None:
            # merged heading "Items X and Y": representative keeps the span,
            # the absorbed member carries no span (plan §3.3-B).
            items[-1] = items[-1].model_copy(update={"status": ItemStatus.MERGED})
            items.append(Item(item_id=a.merged_id, part=ruleset.part_of(a.merged_id),
                              status=ItemStatus.MERGED, merged_into=a.item_id, char_span=None))

    # 5. residual: cover/TOC (Stage 1) + part dividers + signatures, all positive
    residual: list[ResidualSpan] = list(ruler.residual_candidates)
    residual.extend(ResidualSpan(char_span=p, classification=ResidualClass.PART_DIVIDER)
                    for p in parts)
    if signatures is not None:
        residual.append(ResidualSpan(char_span=signatures,
                                     classification=ResidualClass.SIGNATURES))

    # 6. fill any remaining non-whitespace gaps: front matter before the first
    #    item (benign) vs unclassified red flag between/after items
    first_item = accepted[0].start if accepted else n
    claimed = [it.char_span for it in items if it.is_geometric] + [r.char_span for r in residual]
    residual.extend(_fill_gaps(text, claimed, first_item))

    return items, residual
