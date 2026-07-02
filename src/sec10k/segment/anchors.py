"""``Item N`` enumerator anchor detection (DESIGN.md §4 Stage 2).

The anchor is the **enumerator**, never the caption topic string. We tolerate
layout variants (case, separators, ``&nbsp;`` already decoded to spaces by Stage
1, optional trailing ``.`` / ``:`` / dash) and recognize the merged-heading form
``Items 1 and 2``. Disambiguation (TOC echoes, cross-references, ordering) is the
segmenter's job, not the regex's — a looser regex here is fine because the gate
and the order filter downstream catch false positives.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

# Line-anchored (``^`` in MULTILINE) — a real item heading starts a line/block.
# Stage 1 turned block-level tags into newlines, so this structural cue works for
# HTML and ASCII alike, and it already rejects mid-sentence cross-references like
# "see Item 1A" (which are not at a line start). Groups:
#   1 word (item/items)  2 num1  3 letter1  4 num2  5 letter2  (4/5 = merge form)
_ANCHOR = re.compile(
    # The optional item letter must be ATTACHED to the number ("1A", no space),
    # otherwise the letter group would swallow the "A" of "1 AND 2" and misread a
    # merged heading as item "1A".
    r"(?im)^[^\S\n]*(items?)[^\S\n]+(\d{1,2})([a-z])?"
    r"(?:[^\S\n]+and[^\S\n]+(\d{1,2})([a-z])?)?"
    r"\b[^\S\n]*[.:–—-]?",
)


def _item_id(num: str, letter: str | None) -> str:
    """Normalize an enumerator to an item id, e.g. ('1','a') -> '1A'."""
    return num + (letter.upper() if letter else "")


@dataclass(frozen=True, slots=True)
class AnchorMatch:
    """A candidate item anchor found on the ruler."""

    start: int                 # ruler offset of the heading line start (indent included)
    enum_start: int            # ruler offset of the word "Item"
    item_id: str               # e.g. "1", "1A"
    merged_id: str | None      # second id for a merged heading ("Items 1 and 2") else None
    is_plural: bool            # matched "Items" rather than "Item"


def find_anchors(text: str) -> list[AnchorMatch]:
    """Return all candidate anchors in document order (pre-disambiguation)."""
    out: list[AnchorMatch] = []
    for m in _ANCHOR.finditer(text):
        word, num1, let1, num2, let2 = m.group(1, 2, 3, 4, 5)
        merged = _item_id(num2, let2) if num2 else None
        # line start = offset of the indent before the enumerator
        line_start = text.rfind("\n", 0, m.start()) + 1
        out.append(AnchorMatch(
            start=line_start,
            enum_start=m.start(1),
            item_id=_item_id(num1, let1),
            merged_id=merged,
            is_plural=word.lower() == "items",
        ))
    return out
