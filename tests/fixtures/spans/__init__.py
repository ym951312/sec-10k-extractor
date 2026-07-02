"""Synthetic span-list fixtures for Stage 3.

These hand-built layouts let us exercise the invariant gate's logic WITHOUT a
real Stage 2 segmenter (which is intentionally not built yet). Each builder
produces a ``(ruler, items, residual)`` triple where the spans partition a small
synthetic ruler, so we can craft both passing layouts and targeted violations.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from sec10k.contracts import CharSpan, Item, ResidualSpan, Ruler
from sec10k.enums import FileGeneration, ItemStatus, ResidualClass


@dataclass
class Seg:
    """One contiguous region to lay down on the synthetic ruler."""

    kind: str          # "item" | "residual" | "merged_member"
    key: str           # item_id, or residual class value
    body: str          # the text occupying this region
    status: ItemStatus = ItemStatus.EXTRACTED
    merged_into: str | None = None


@dataclass
class Layout:
    ruler: Ruler
    items: list[Item] = field(default_factory=list)
    residual: list[ResidualSpan] = field(default_factory=list)


def build_layout(segs: list[Seg]) -> Layout:
    """Lay segments contiguously over a synthetic ruler covering ``[0, N)``.

    ``merged_member`` segments still occupy ruler text (their heading), but the
    absorbed member Item carries no span (its region is owned by the merge
    representative whose span is widened to include it).
    """
    text_parts: list[str] = []
    items: list[Item] = []
    residual: list[ResidualSpan] = []
    cursor = 0
    # first pass: assign spans
    spans: list[tuple[Seg, CharSpan]] = []
    for seg in segs:
        start = cursor
        text_parts.append(seg.body)
        cursor += len(seg.body)
        spans.append((seg, CharSpan(start=start, end=cursor)))

    text = "".join(text_parts)
    ruler = Ruler(text=text, file_generation=FileGeneration.HTML_XBRL)

    # widen each merge representative's span to swallow its absorbed members
    rep_span: dict[str, CharSpan] = {}
    for seg, span in spans:
        if seg.kind == "merged_member" and seg.merged_into:
            rep = seg.merged_into
            cur = rep_span.get(rep)
            lo = span.start if cur is None else min(cur.start, span.start)
            hi = span.end if cur is None else max(cur.end, span.end)
            rep_span[rep] = CharSpan(start=lo, end=hi)
        elif seg.kind == "item":
            cur = rep_span.get(seg.key)
            if cur is None:
                rep_span[seg.key] = span
            else:
                rep_span[seg.key] = CharSpan(start=min(cur.start, span.start),
                                             end=max(cur.end, span.end))

    for seg, span in spans:
        if seg.kind == "residual":
            residual.append(ResidualSpan(
                char_span=span, classification=ResidualClass(seg.key)))
        elif seg.kind == "merged_member":
            items.append(Item(item_id=seg.key, status=ItemStatus.MERGED,
                              merged_into=seg.merged_into, char_span=None))
        else:  # item
            items.append(Item(item_id=seg.key, status=seg.status,
                              char_span=rep_span[seg.key]))
    return Layout(ruler=ruler, items=items, residual=residual)


def standard_valid_layout() -> Layout:
    """A clean, legal standard 10-K layout: cover + TOC residual, items in
    order, Item 6 reserved, Part III incorporated by reference."""
    segs = [
        Seg("residual", "cover_page", "COVER PAGE acme robotics form 10-k. "),
        Seg("residual", "toc", "TABLE OF CONTENTS item 1 .. 3 item 8 .. 40. "),
        Seg("item", "1", "ITEM 1 business we build robots. "),
        Seg("item", "1A", "ITEM 1A risk factors demand may fall. "),
        Seg("item", "1C", "ITEM 1C cybersecurity we manage cyber risk. "),
        Seg("item", "2", "ITEM 2 properties we lease space. "),
        Seg("item", "3", "ITEM 3 legal proceedings none material. "),
        Seg("item", "4", "ITEM 4 mine safety not applicable. "),
        Seg("item", "5", "ITEM 5 market for stock. "),
        Seg("item", "6", "ITEM 6 [Reserved]. ", status=ItemStatus.RESERVED),
        Seg("item", "7", "ITEM 7 md and a revenue grew. "),
        Seg("item", "7A", "ITEM 7A market risk interest rates. "),
        Seg("item", "8", "ITEM 8 financial statements total revenue 1,234. "),
        Seg("item", "9", "ITEM 9 changes none. "),
        Seg("item", "9A", "ITEM 9A controls effective. "),
        Seg("item", "10", "ITEM 10 directors see proxy. ",
            status=ItemStatus.INCORPORATED_BY_REFERENCE),
        Seg("item", "11", "ITEM 11 compensation see proxy. ",
            status=ItemStatus.INCORPORATED_BY_REFERENCE),
        Seg("item", "12", "ITEM 12 ownership see proxy. ",
            status=ItemStatus.INCORPORATED_BY_REFERENCE),
        Seg("item", "13", "ITEM 13 relationships see proxy. ",
            status=ItemStatus.INCORPORATED_BY_REFERENCE),
        Seg("item", "14", "ITEM 14 accountant fees see proxy. ",
            status=ItemStatus.INCORPORATED_BY_REFERENCE),
        Seg("item", "15", "ITEM 15 exhibits listed below. "),
        Seg("residual", "signatures", "SIGNATURES duly signed. "),
    ]
    return build_layout(segs)
