"""Repeated per-page header/footer stripping (DESIGN.md §3, Stage 1 step 6).

Repeated page chrome (company name, "Form 10-K", page numbers, "Table of
Contents" running heads) is the cheapest residual to detect and is stripped here
to *clean the ruler*. Per §3 these go OFF the ruler and into the StrippedLedger
(class ``page_header_footer``) — they are NOT residual spans on the ruler.

Conservation is preserved by construction: every excised character's text is
copied verbatim into a ledger entry, so

    source visible tokens == ruler' tokens ⊎ ledger(page_header_footer) tokens

still holds (the completeness check re-runs after stripping to prove it).

Detection is deliberately conservative (high repetition required) because a
false strip removes real content; recording every strip in the ledger keeps it
auditable and recoverable.
"""

from __future__ import annotations

import re
from collections import defaultdict

from ..contracts import (
    CharSpan,
    ProvenanceMap,
    ProvenanceSegment,
    Ruler,
    StrippedEntry,
)
from ..enums import StrippedClass

_MIN_REPEAT = 3       # a line must recur at least this many times to be chrome
_MAX_LINE_LEN = 90    # running heads/feet are short; body paragraphs are not
_ITEM_ANCHOR = re.compile(r"^\s*item\s+\d", re.IGNORECASE)
# A whole line that is just a page marker: "12", "Page 12", "- 12 -".
_PAGENUM = re.compile(r"^(?:page\s+)?\d{1,4}$|^-\s*\d{1,4}\s*-$", re.IGNORECASE)
# split on newlines and ASCII form-feed page breaks
_LINE_SPLIT = re.compile(r"[\n\f]")


def _norm_ws(s: str) -> str:
    """Collapse whitespace and lowercase, for VERBATIM repeat matching.

    Deliberately does NOT fold digits: folding would collapse genuinely
    distinct body lines that differ only by a number (e.g. "...section 1." vs
    "...section 2.") into a false repeat. Page numbers are handled separately
    by the strict :data:`_PAGENUM` pattern instead.
    """
    return " ".join(s.split()).lower()


def _looks_like_prose(s: str) -> bool:
    """A running head/foot is a LABEL (company name, form type, page number),
    not a sentence. Boilerplate body text can repeat verbatim across items
    (e.g. the Part III "...incorporated by reference to our proxy statement."
    line appears under Items 10-14) — that is content, not chrome. Excluding
    prose-looking lines errs toward KEEPING text on the ruler, the safe
    direction: an un-stripped head merely stays visible; a falsely stripped
    sentence would lose real item body. (Completeness holds either way.)
    """
    return s.rstrip().endswith((".", "!", "?")) and len(s.split()) >= 6


def _line_spans(text: str) -> list[CharSpan]:
    """Char spans of each line (regions between newline/form-feed separators)."""
    spans: list[CharSpan] = []
    pos = 0
    for m in _LINE_SPLIT.finditer(text):
        if m.start() > pos:
            spans.append(CharSpan(start=pos, end=m.start()))
        pos = m.end()
    if pos < len(text):
        spans.append(CharSpan(start=pos, end=len(text)))
    return spans


def detect_header_footer_spans(text: str) -> list[CharSpan]:
    """Find char spans of repeated page chrome on the ruler ``text``."""
    spans = _line_spans(text)
    by_verbatim: dict[str, list[CharSpan]] = defaultdict(list)
    pagenum_spans: list[CharSpan] = []
    for sp in spans:
        raw = text[sp.start:sp.end].strip()
        if not raw or len(raw) > _MAX_LINE_LEN:
            continue
        if _ITEM_ANCHOR.match(raw):
            continue  # never strip an item anchor as if it were chrome
        if _PAGENUM.match(raw):
            pagenum_spans.append(sp)
            continue
        if _looks_like_prose(raw):
            continue  # repeated boilerplate sentence = content, not chrome
        by_verbatim[_norm_ws(raw)].append(sp)

    out: list[CharSpan] = []
    for occurrences in by_verbatim.values():
        if len(occurrences) >= _MIN_REPEAT:  # running head/foot repeating verbatim
            out.extend(occurrences)
    if len(pagenum_spans) >= _MIN_REPEAT:    # recurring page-number markers
        out.extend(pagenum_spans)
    out.sort(key=lambda s: s.start)
    return out


def _merge(spans: list[CharSpan]) -> list[CharSpan]:
    merged: list[CharSpan] = []
    for sp in sorted(spans, key=lambda s: s.start):
        if merged and sp.start <= merged[-1].end:
            if sp.end > merged[-1].end:
                merged[-1] = CharSpan(start=merged[-1].start, end=sp.end)
        else:
            merged.append(sp)
    return merged


def excise_spans(
    text: str, provenance: ProvenanceMap, remove: list[CharSpan]
) -> tuple[str, ProvenanceMap, list[tuple[int, int, str]]]:
    """Remove ``remove`` ranges from ``text``; rebuild text + provenance.

    Returns ``(new_text, new_provenance, removed)`` where ``removed`` is a list
    of ``(orig_start, orig_end, removed_text)``. Provenance for kept regions is
    re-sliced and shifted (linear within each old segment).
    """
    remove = _merge(remove)
    kept: list[tuple[int, int, int]] = []  # (old_start, old_end, new_start)
    pieces: list[str] = []
    removed: list[tuple[int, int, str]] = []
    cur = 0
    new_len = 0
    for sp in remove:
        if sp.start > cur:
            pieces.append(text[cur:sp.start])
            kept.append((cur, sp.start, new_len))
            new_len += sp.start - cur
        removed.append((sp.start, sp.end, text[sp.start:sp.end]))
        cur = sp.end
    if cur < len(text):
        pieces.append(text[cur:])
        kept.append((cur, len(text), new_len))
        new_len += len(text) - cur

    new_text = "".join(pieces)
    new_segments = _rebuild_provenance(provenance.segments, kept)
    return new_text, ProvenanceMap(segments=new_segments), removed


def _rebuild_provenance(
    old: list[ProvenanceSegment], kept: list[tuple[int, int, int]]
) -> list[ProvenanceSegment]:
    """Re-slice provenance onto the post-excision coordinates.

    Both inputs are sorted and internally non-overlapping (provenance segments
    in ruler order; kept ranges in ascending old-offset order), so this is a
    linear two-pointer merge — NOT the naive O(segments × ranges) product, which
    is quadratic and dominated runtime on large filings.
    """
    new_segs: list[ProvenanceSegment] = []
    n = len(kept)
    j = 0  # first kept range that might still overlap the current segment
    for seg in old:
        rs, re_, ss, se = seg.ruler_start, seg.ruler_end, seg.source_start, seg.source_end
        zero_src = se <= ss  # injected separators carry zero-length source
        # kept ranges ending at/before this segment start can never overlap a
        # later (>=) segment either -> advance j permanently
        while j < n and kept[j][1] <= rs:
            j += 1
        k = j
        while k < n and kept[k][0] < re_:
            o0, o1, n0 = kept[k]
            a = rs if rs > o0 else o0
            b = re_ if re_ < o1 else o1
            if a < b:
                if zero_src:
                    s_a = s_b = ss
                else:
                    s_a = ss + (a - rs)
                    s_b = ss + (b - rs)
                    if s_b > se:
                        s_b = se
                new_segs.append(ProvenanceSegment(
                    ruler_start=n0 + (a - o0), ruler_end=n0 + (b - o0),
                    source_start=s_a, source_end=s_b, source_kind=seg.source_kind,
                ))
            k += 1
    return new_segs


def strip_headers_footers(ruler: Ruler) -> Ruler:
    """Return a new :class:`Ruler` with repeated header/footer chrome excised
    and recorded in the ledger. Residual candidates' spans are re-mapped to the
    new coordinates."""
    spans = detect_header_footer_spans(ruler.text)
    if not spans:
        return ruler

    new_text, new_prov, removed = excise_spans(ruler.text, ruler.provenance, spans)

    ledger = list(ruler.stripped_ledger)
    for (s, e, txt) in removed:
        ledger.append(StrippedEntry(
            source_start=s, source_end=e,
            classification=StrippedClass.PAGE_HEADER_FOOTER,
            reason="repeated per-page header/footer chrome",
            text=txt,
        ))

    # remap any existing residual candidates onto the new (shorter) coordinates
    remap = _offset_remapper(ruler.text, spans)
    new_residuals = []
    for rc in ruler.residual_candidates:
        ns, ne = remap(rc.char_span.start), remap(rc.char_span.end)
        if ne > ns:
            new_residuals.append(rc.model_copy(update={"char_span": CharSpan(start=ns, end=ne)}))

    return ruler.model_copy(update={
        "text": new_text,
        "provenance": new_prov,
        "stripped_ledger": ledger,
        "residual_candidates": new_residuals,
    })


def _offset_remapper(old_text: str, removed: list[CharSpan]):
    """Build a function mapping an old ruler offset to its new offset after the
    removed ranges are excised (clamped to the start of a removed range)."""
    removed = _merge(removed)

    def remap(pos: int) -> int:
        shift = 0
        for sp in removed:
            if pos >= sp.end:
                shift += sp.end - sp.start
            elif pos > sp.start:
                # inside a removed range -> clamp to its (new) start edge
                return sp.start - shift
            else:
                break
        return pos - shift

    return remap
