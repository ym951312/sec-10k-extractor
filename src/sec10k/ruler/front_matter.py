"""Cover-page and table-of-contents isolation (DESIGN.md §3, §4 Stage 1 step 6).

These are *positively identified* residual spans that stay ON the ruler (unlike
page header/footer chrome, which is excised). Isolating the TOC early
"pre-dismantles the fake-title trap": the TOC echoes every ``Item N`` enumerator,
and a future Stage 2 must not mistake those echoes for real anchors. We mark the
TOC region here so Stage 2 can exclude it.

Identity here is structural (enumerator density + page references / dotted
leaders), NOT title strings — consistent with the "anchor = item number, never a
caption string" rule.
"""

from __future__ import annotations

import re

from ..contracts import CharSpan, ResidualSpan
from ..enums import ResidualClass

# An item enumerator at the start of a line: "Item 1", "ITEM 1A.", "Item 1C",
# and the merged-heading plural "Items 1 and 2" — so cover-page detection stops
# at a merged first item instead of swallowing it.
_ITEM_LINE = re.compile(r"^\s*items?\s+(\d{1,2})([A-Za-z]?)\b", re.IGNORECASE)
# A page reference on a TOC line: dotted leader + number, or a trailing number.
_PAGE_REF = re.compile(r"(\.\s*){3,}\s*\d{1,4}\s*$|\t\s*\d{1,4}\s*$|\s\d{1,4}\s*$")
# Two consecutive page-ref TOC entries farther apart than this => left the TOC.
_TOC_GAP = 600
# Density path: a TOC packs many item enumerators close together. A run of this
# many consecutive anchors, each within _DENSE_GAP chars, is a table of contents
# — a real body always has at least one large item that breaks such a run. This
# catches HTML TOCs whose page numbers sit in separate table cells (no same-line
# page ref), e.g. MSFT: "Item 1.\n...\nBusiness\n...\nItem 1A.\n...".
_MIN_TOC_ENTRIES = 6
_DENSE_GAP = 700
# A density-detected TOC must BEGIN within the front of the document — a real
# table of contents sits near the front (right after the cover page). This guards
# against a run of genuinely-short consecutive BODY items (e.g. Part III IBR
# items + "None" items) deep in the filing being mistaken for a TOC, which would
# otherwise make cover-page detection swallow the whole preceding body (APA
# FY2023: a dense run of items 9B/9C/10-15 at ~46% depth). The page-ref path is
# NOT constrained — dotted-leader page numbers are TOC-specific on their own.
_TOC_FRONT_FRACTION = 0.2


def _lines(text: str):
    """Yield ``(start, end, raw_line)`` for each newline/form-feed line."""
    pos = 0
    n = len(text)
    for m in re.finditer(r"[\n\f]", text):
        if m.start() > pos:
            yield pos, m.start(), text[pos:m.start()]
        pos = m.end()
    if pos < n:
        yield pos, n, text[pos:]


def _anchor_lines(text: str):
    """All item-anchor lines: list of ``(start, end, has_page_ref)``."""
    out = []
    for s, e, raw in _lines(text):
        if _ITEM_LINE.match(raw):
            out.append((s, e, bool(_PAGE_REF.search(raw))))
    return out


def _runs(items: list[tuple[int, int]], gap: int) -> list[list[tuple[int, int]]]:
    """Split (start, end) lines into maximal runs where consecutive starts are
    within ``gap`` chars."""
    if not items:
        return []
    runs: list[list[tuple[int, int]]] = []
    cur = [items[0]]
    for s, e in items[1:]:
        if s - cur[-1][0] <= gap:
            cur.append((s, e))
        else:
            runs.append(cur)
            cur = [(s, e)]
    runs.append(cur)
    return runs


def _first_run(items: list[tuple[int, int]], gap: int, minlen: int) -> CharSpan | None:
    for run in _runs(items, gap):
        if len(run) >= minlen:
            return CharSpan(start=run[0][0], end=run[-1][1])
    return None


# --- number-aware TOC boundary refinement (added for A-group TOC end-boundary fix) ---

def _order_key(raw: str) -> tuple[int, str] | None:
    """Parse an anchor line's enumerator into an order key: 'Item 1' -> (1, ''),
    'Item 1A' -> (1, 'A'). Returns None if the line is not an item anchor."""
    m = _ITEM_LINE.match(raw)
    if not m:
        return None
    return (int(m.group(1)), (m.group(2) or "").upper())


def _anchor_lines_keyed(text: str):
    """Anchor lines with their order key: list of (start, end, has_page_ref, key)."""
    out = []
    for s, e, raw in _lines(text):
        key = _order_key(raw)
        if key is not None:
            out.append((s, e, bool(_PAGE_REF.search(raw)), key))
    return out


def _runs_keyed(items, gap: int):
    """Like _runs but preserves whole tuples (start is item[0])."""
    if not items:
        return []
    runs = []
    cur = [items[0]]
    for it in items[1:]:
        if it[0] - cur[-1][0] <= gap:
            cur.append(it)
        else:
            runs.append(cur)
            cur = [it]
    runs.append(cur)
    return runs


def _trim_trailing_backjump(run):
    """Drop trailing anchors whose order key is below the run's maximum key.

    A real TOC lists items in increasing order. When the body's first heading
    ('Item 1. Business') sits within one gap of the last TOC entry it gets pulled
    into the run — a jump *back* to a lower item number. Trimming it keeps the TOC
    end at the last genuine (increasing) TOC entry, so the body heading is not
    swallowed. Uses item number + order only (never caption strings)."""
    max_key = max(it[3] for it in run)
    end = len(run)
    while end > 1 and run[end - 1][3] < max_key:
        end -= 1
    return run[:end]


def _first_run_keyed(items, gap: int, minlen: int) -> CharSpan | None:
    for run in _runs_keyed(items, gap):
        if len(run) >= minlen:
            kept = _trim_trailing_backjump(run)
            return CharSpan(start=kept[0][0], end=kept[-1][1])
    return None


def _merged_run_keyed(items, gap: int, minlen: int, text: str) -> CharSpan | None:
    """Like :func:`_first_run_keyed`, but stitches back a TOC that a large
    intra-TOC gap has split into several runs.

    A non-anchor block inside the TOC (for example a 'PART II' page divider) can
    open a gap wider than ``gap`` between two genuine TOC entries (PG FY2023: a
    ~929-char gap between the 'Item 8' and 'Item 9' TOC lines). ``_runs_keyed``
    then breaks the TOC in two; taking only the first run leaves the tail entries
    (items 9-16) exposed, and Stage 2 mis-handles the body.

    Starting from the first run with at least ``minlen`` entries, absorb each
    following run only when it (a) begins within the document front
    (``_TOC_FRONT_FRACTION``) and (b) continues the item order, i.e. its first
    order key exceeds the maximum key seen so far. These two structural guards
    stop a genuinely-separate deep body run (for example the dense Part III IBR
    items in APA FY2023 at about 46% depth, whose numbers jump back) from being
    absorbed. The merged run is backjump-trimmed as usual, so a body heading
    pulled in at the tail is still dropped. Item number + order only; never
    caption strings."""
    front_limit = len(text) * _TOC_FRONT_FRACTION
    merged = None
    max_key = None
    for run in _runs_keyed(items, gap):
        if merged is None:
            if len(run) >= minlen:
                merged = list(run)
                max_key = max(it[3] for it in run)
            continue
        if run[0][0] > front_limit:
            break
        if run[0][3] <= max_key:
            break
        merged.extend(run)
        max_key = max(max_key, max(it[3] for it in run))
    if merged is None:
        return None
    kept = _trim_trailing_backjump(merged)
    return CharSpan(start=kept[0][0], end=kept[-1][1])


def detect_toc(text: str) -> CharSpan | None:
    """Return the char span of the first table-of-contents cluster, if any.

    Two complementary signals (first match wins, near the document front):

    * **page-ref path** — a run of item-anchor lines carrying explicit page
      references (dotted leaders / trailing numbers): the classic ASCII TOC.
    * **density path** — a run of densely-packed item-anchor lines with no
      same-line page number: the HTML-table TOC. Only accepted if it begins near
      the document front (see :data:`_TOC_FRONT_FRACTION`).

    A run's trailing entries are trimmed when they jump *back* to a lower item
    number: that is the body's first heading pulled in by proximity, not a TOC
    entry (see :func:`_trim_trailing_backjump`).
    """
    anchors = _anchor_lines_keyed(text)
    if len(anchors) < _MIN_TOC_ENTRIES:
        return None
    refs = [a for a in anchors if a[2]]
    by_ref = _merged_run_keyed(refs, _TOC_GAP, _MIN_TOC_ENTRIES, text)
    if by_ref is not None:
        return by_ref
    by_density = _merged_run_keyed(anchors, _DENSE_GAP, _MIN_TOC_ENTRIES, text)
    if by_density is not None and by_density.start <= len(text) * _TOC_FRONT_FRACTION:
        return by_density
    return None


def detect_cover_page(text: str, toc: CharSpan | None) -> CharSpan | None:
    """Cover page = the front matter before the first real (post-TOC) item.

    Bounded by the TOC start if a TOC exists; otherwise by the first item
    anchor. Returns ``None`` if the document starts at an item (no cover).
    """
    if toc is not None:
        boundary = toc.start
    else:
        anchors = _anchor_lines(text)
        if not anchors:
            return None
        boundary = anchors[0][0]
    # ignore leading whitespace-only cover
    if text[:boundary].strip() == "":
        return None
    return CharSpan(start=0, end=boundary)


def isolate_front_matter(text: str) -> list[ResidualSpan]:
    """Detect cover page + TOC as residual candidates (on the ruler)."""
    out: list[ResidualSpan] = []
    toc = detect_toc(text)
    cover = detect_cover_page(text, toc)
    if cover is not None:
        out.append(ResidualSpan(char_span=cover, classification=ResidualClass.COVER_PAGE))
    if toc is not None:
        out.append(ResidualSpan(char_span=toc, classification=ResidualClass.TOC))
    return out
