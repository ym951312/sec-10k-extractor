"""Raw bytes -> ruler text + provenance map (DESIGN.md §3, Stage 1 step 5).

The normalizer is the **engine that builds the ruler**. Two design choices make
the resulting ruler *certifiably complete*:

1. **Position-aware parsing via the stdlib** ``html.parser``. Unlike a DOM
   library, ``HTMLParser`` streams over the raw input and exposes source
   positions (``getpos``), so every ruler character can be mapped back to a raw
   byte offset — this is the provenance map (``source_ref``) the §3 contract
   requires. ``convert_charrefs=False`` lets us see entities as events and map
   ``&nbsp;`` (6 raw chars) -> ``" "`` (1 ruler char) exactly.

2. **An independent baseline** for the completeness check (:func:`visible_baseline_text`)
   built by a *separate* regex code path. Comparing the DOM-walked ruler against
   the regex baseline is non-circular: a normalizer bug that silently drops a
   visible ``<td>`` shows up as a token the baseline has and the ruler lacks.

Visibility scoping (this milestone, documented honestly):

* Removed from BOTH the ruler and the baseline: ``<script>``, ``<style>``,
  comments, and ``<ix:hidden>`` inline-XBRL fact blocks. ``<ix:hidden>`` is the
  standard wrapper for the duplicate machine-value facts; dropping it on both
  sides is exactly what prevents a false FAIL / double-count of a number that
  appears once as visible text and again as a hidden XBRL fact.
* Inline ``<ix:nonFraction>`` / ``<ix:nonNumeric>`` wrap *visible* text — kept
  once (the tag is a transparent wrapper); their machine values live in
  attributes, which tag-stripping drops, so no double count.
* General CSS ``display:none`` (non-ix) is treated as visible for now — a CSS
  visibility engine is out of scope and SEC hidden facts are structurally
  ``<ix:hidden>``. Deferred, not silently assumed.
"""

from __future__ import annotations

import html
import re
from dataclasses import dataclass, field
from html.parser import HTMLParser

from ..contracts import ProvenanceMap, ProvenanceSegment, StrippedEntry
from ..enums import FileGeneration, StrippedClass
from .formats import decode_bytes, detect_generation

# Tags whose text never reaches the ruler.
_DROP_TEXT_TAGS = {"script", "style"}

# --- Inline-XBRL exclusion: a MECHANISM RULE, not a named-tag blacklist. ------
# DESIGN.md §1 (flexibility B is not exhaustible) and §5 (classify the
# presentation layer by *mechanism* + sample to saturation) tell us NOT to chase
# an ever-growing list like {"ix:header", "ix:hidden", ...}. Instead we exclude
# content that satisfies the INTERSECTION of two conditions:
#
#   (1) it is inline-XBRL machinery — in the ``ix:`` namespace, AND
#   (2) it is computed-not-displayed to the reader — either inside a
#       non-presentation iXBRL container, or styled display:none/visibility:hidden.
#
# Being ``ix:`` ALONE is never enough (condition 1 without 2 keeps it). The
# load-bearing counter-example: ``<ix:nonFraction>1,234</ix:nonFraction>`` and
# ``<ix:nonNumeric>`` wrap VISIBLE text — they are real ruler content and MUST
# be kept and counted in the conservation equation.
#
# We realise "computed-not-displayed for an ix: element" structurally: the iXBRL
# rendering model says the *fact-wrapper* elements below render their content
# inline, while every other ix: element is non-presentation machinery (the
# ix:header subtree: ix:hidden / ix:references / ix:resources, holding
# xbrli:context/unit, member names, dates). So the small, stable set is the
# VISIBLE one; the invisible machinery set is left open-ended on purpose.
#
# Guarantee level: this is ESTIMABLE (sampled to saturation against real
# filings), NOT provably closed — a brand-new *visible* ix: fact element would
# need adding to the whitelist below. That is the §5 asymmetry: we can prove a
# drop (conservation FAILs loudly), we can only corroborate completeness.
# The VISIBLE inline-XBRL elements (render their content to the reader; treated
# as transparent inline wrappers). ``ix:exclude`` was added after sampling real
# filings (MSFT FY2023): it marks a sub-portion excluded from a fact's *value*
# but STILL DISPLAYED — visible content, not machine data. That discovery is the
# §5 "sample to saturation" loop in action; the set is estimable, not closed.
_IX_FACT_WRAPPERS = {
    "ix:nonnumeric", "ix:nonfraction", "ix:fraction",
    "ix:numerator", "ix:denominator", "ix:footnote", "ix:continuation",
    "ix:exclude",
}

# Block-level tags: emit a separator so neighbouring text does not fuse.
_BLOCK_TAGS = {
    "p", "div", "br", "hr", "table", "tr", "td", "th", "li", "ul", "ol",
    "h1", "h2", "h3", "h4", "h5", "h6", "section", "article", "header",
    "footer", "blockquote", "pre", "caption", "figcaption", "dd", "dt",
    "body", "html", "tbody", "thead", "title",
}


# Inline-style "computed not displayed" signal (condition 2, CSS branch).
_RE_STYLE_HIDDEN = re.compile(
    r"(?:display\s*:\s*none|visibility\s*:\s*hidden)", re.IGNORECASE)


def _style_hidden(attrs) -> bool:
    """True if an element's inline style computes to not-displayed.

    A pragmatic approximation of computed style: we read the inline ``style``
    attribute (the dominant case in SEC iXBRL hidden facts). Full CSS cascade
    resolution is out of scope — part of the "estimable, not provably closed"
    guarantee."""
    for name, value in attrs:
        if name == "style" and value and _RE_STYLE_HIDDEN.search(value):
            return True
    return False


def _is_xbrl_excluded(tag: str, attrs) -> bool:
    """Mechanism predicate: should this element's subtree be excluded from the
    ruler as non-displayed inline-XBRL machinery?

    Returns True iff BOTH conditions hold (see the module comment):
      (1) ``ix:`` namespace, AND
      (2) computed-not-displayed = (not a visible fact wrapper) OR style-hidden.

    A visible fact wrapper (``ix:nonFraction``/``ix:nonNumeric``/…) with no
    hiding style fails condition (2) and is therefore KEPT (transparent inline).
    """
    if not tag.startswith("ix:"):
        return False  # condition (1) fails: never exclude non-iXBRL on style alone
    if tag in _IX_FACT_WRAPPERS and not _style_hidden(attrs):
        return False  # visible fact wrapper -> keep its text on the ruler
    return True       # ix: container, OR a fact wrapper explicitly hidden by style


@dataclass
class NormalizedDoc:
    """Output of normalization, before completeness certification."""

    text: str
    provenance: ProvenanceMap
    ledger: list[StrippedEntry] = field(default_factory=list)
    generation: FileGeneration = FileGeneration.HTML_XBRL


# --------------------------------------------------------------------------- #
# Independent regex baseline (for the completeness check)
# --------------------------------------------------------------------------- #
_RE_SCRIPT = re.compile(r"<script\b[^>]*>.*?</script\s*>", re.IGNORECASE | re.DOTALL)
_RE_STYLE = re.compile(r"<style\b[^>]*>.*?</style\s*>", re.IGNORECASE | re.DOTALL)
_RE_COMMENT = re.compile(r"<!--.*?-->", re.DOTALL)
# Independent-path realisation of the SAME mechanism the DOM walker applies
# (ix: ∩ not-displayed). The two non-presentation iXBRL container subtrees:
_RE_IX_HEADER = re.compile(r"<ix:header\b[^>]*>.*?</ix:header\s*>", re.IGNORECASE | re.DOTALL)
_RE_IX_HIDDEN = re.compile(r"<ix:hidden\b[^>]*>.*?</ix:hidden\s*>", re.IGNORECASE | re.DOTALL)
# ...and an ix: fact wrapper explicitly hidden by inline style (CSS branch of
# condition 2). A *visible* fact wrapper has no such style and is left intact.
_RE_IX_FACT_HIDDEN = re.compile(
    r"<ix:(?:nonfraction|nonnumeric|fraction)\b[^>]*\bstyle\s*=\s*['\"][^'\"]*"
    r"(?:display\s*:\s*none|visibility\s*:\s*hidden)[^'\"]*['\"][^>]*>"
    r".*?</ix:(?:nonfraction|nonnumeric|fraction)\s*>",
    re.IGNORECASE | re.DOTALL)
_RE_TAG = re.compile(r"<[^>]*>")
# Block-level open/close tags -> a separator space; inline tags -> nothing. This
# mirrors the DOM walker (block tags inject a separator, inline tags are
# transparent), so a word interrupted by an inline tag — ``B<span>usiness</span>``
# — is NOT split by the baseline either. The block/inline distinction is shared
# HTML semantics, not the segmentation logic under test, so the check stays
# non-circular.
_RE_BLOCK_TAG = re.compile(
    r"</?(?:" + "|".join(sorted(_BLOCK_TAGS, key=len, reverse=True)) + r")\b[^>]*>",
    re.IGNORECASE,
)


def visible_baseline_text(raw_text: str, generation: FileGeneration) -> str:
    """Independent extraction of visible text, used ONLY by the completeness
    check. Deliberately NOT the DOM walker, so the comparison is non-circular.

    Applies the SAME mechanism (ix: ∩ not-displayed) by a regex path: drop the
    non-presentation iXBRL container subtrees (ix:header / ix:hidden) and any
    style-hidden ix fact wrapper, but keep VISIBLE fact wrappers' text. Then
    strip script/style/comments and remaining tags and decode entities.
    """
    if generation is FileGeneration.ASCII:
        return raw_text
    t = _RE_COMMENT.sub(" ", raw_text)
    t = _RE_SCRIPT.sub(" ", t)
    t = _RE_STYLE.sub(" ", t)
    t = _RE_IX_HEADER.sub(" ", t)       # non-presentation container subtree
    t = _RE_IX_HIDDEN.sub(" ", t)       # ...and a standalone hidden block
    t = _RE_IX_FACT_HIDDEN.sub(" ", t)  # ...and a style-hidden ix fact
    t = _RE_BLOCK_TAG.sub(" ", t)       # block tags -> separator
    t = _RE_TAG.sub("", t)              # remaining inline tags -> transparent
    return html.unescape(t)


# --------------------------------------------------------------------------- #
# Position-aware HTML normalizer
# --------------------------------------------------------------------------- #
@dataclass
class _Frame:
    tag: str
    kind: str           # "drop" | "xbrl_hidden"
    src_start: int
    text_parts: list[str] = field(default_factory=list)


class _RulerBuilder(HTMLParser):
    """Walks raw HTML, emitting ruler text with a precise provenance map."""

    def __init__(self, raw_text: str) -> None:
        super().__init__(convert_charrefs=False)
        self._raw = raw_text
        # line-start offsets, to turn getpos() (line, col) into an absolute offset
        self._line_starts = [0]
        for i, ch in enumerate(raw_text):
            if ch == "\n":
                self._line_starts.append(i + 1)
        self._chunks: list[str] = []
        self._cursor = 0  # current length of ruler
        self.segments: list[ProvenanceSegment] = []
        self.ledger: list[StrippedEntry] = []
        self._stack: list[_Frame] = []

    # -- offset helpers --
    def _abs(self) -> int:
        line, col = self.getpos()
        return self._line_starts[line - 1] + col

    def _suppressed(self) -> bool:
        return len(self._stack) > 0

    def _hidden_frame(self) -> _Frame | None:
        for fr in reversed(self._stack):
            if fr.kind == "xbrl_hidden":
                return fr
        return None

    def _emit(self, ruler_text: str, src_start: int, src_len: int, kind: str) -> None:
        if not ruler_text:
            return
        r0 = self._cursor
        self._chunks.append(ruler_text)
        self._cursor += len(ruler_text)
        self.segments.append(ProvenanceSegment(
            ruler_start=r0, ruler_end=self._cursor,
            source_start=src_start, source_end=src_start + src_len,
            source_kind=kind,
        ))

    def _emit_separator(self) -> None:
        # Injected whitespace carries no source; map to a zero-length anchor so
        # the provenance map stays ordered and continuous. Whitespace is never a
        # token, so this cannot affect completeness accounting.
        if self._chunks and self._chunks[-1].endswith("\n"):
            return
        self._emit("\n", self._abs(), 0, "injected")

    # -- HTMLParser callbacks --
    def handle_starttag(self, tag: str, attrs) -> None:
        if tag in _DROP_TEXT_TAGS:
            self._stack.append(_Frame(tag, "drop", self._abs()))
            return
        if _is_xbrl_excluded(tag, attrs):
            # if already inside a hidden frame (e.g. an ix: fact within
            # ix:header), don't open a second record — the outer frame covers it
            if self._hidden_frame() is None:
                self._stack.append(_Frame(tag, "xbrl_hidden", self._abs()))
            else:
                self._stack.append(_Frame(tag, "drop", self._abs()))
            return
        if not self._suppressed() and tag in _BLOCK_TAGS:
            self._emit_separator()

    def handle_startendtag(self, tag: str, attrs) -> None:
        if not self._suppressed() and tag in _BLOCK_TAGS:
            self._emit_separator()

    def handle_endtag(self, tag: str) -> None:
        # pop down to the matching frame (defensive against malformed nesting)
        for idx in range(len(self._stack) - 1, -1, -1):
            if self._stack[idx].tag == tag:
                closed = self._stack[idx]
                del self._stack[idx:]
                if closed.kind == "xbrl_hidden":
                    text = "".join(closed.text_parts)
                    self.ledger.append(StrippedEntry(
                        source_start=closed.src_start, source_end=self._abs(),
                        classification=StrippedClass.XBRL_HIDDEN,
                        reason="inline XBRL hidden fact (<ix:hidden>); never rendered",
                        text=text,
                    ))
                if not self._suppressed() and tag in _BLOCK_TAGS:
                    self._emit_separator()
                return
        if not self._suppressed() and tag in _BLOCK_TAGS:
            self._emit_separator()

    def handle_data(self, data: str) -> None:
        if self._suppressed():
            hf = self._hidden_frame()
            if hf is not None:
                hf.text_parts.append(data)
            return
        self._emit(data, self._abs(), len(data), "dom_text")

    def handle_entityref(self, name: str) -> None:
        decoded = html.unescape(f"&{name};")
        raw_len = len(name) + 2  # '&' + name + ';'
        if self._suppressed():
            hf = self._hidden_frame()
            if hf is not None:
                hf.text_parts.append(decoded)
            return
        self._emit(decoded, self._abs(), raw_len, "dom_text")

    def handle_charref(self, name: str) -> None:
        decoded = html.unescape(f"&#{name};")
        raw_len = len(name) + 3  # '&#' + name + ';'
        if self._suppressed():
            hf = self._hidden_frame()
            if hf is not None:
                hf.text_parts.append(decoded)
            return
        self._emit(decoded, self._abs(), raw_len, "dom_text")

    def result_text(self) -> str:
        return "".join(self._chunks)


def normalize(raw: bytes) -> NormalizedDoc:
    """Normalize raw filing bytes into a :class:`NormalizedDoc`.

    ASCII filings are an identity mapping (1:1 provenance); HTML/XBRL go through
    the position-aware walker. Repeated-header/footer stripping and cover/TOC
    isolation happen in later Stage 1 steps, not here.
    """
    generation = detect_generation(raw)
    raw_text = decode_bytes(raw)

    if generation is FileGeneration.ASCII:
        prov = ProvenanceMap(segments=[ProvenanceSegment(
            ruler_start=0, ruler_end=len(raw_text),
            source_start=0, source_end=len(raw_text),
            source_kind="raw_byte",
        )]) if raw_text else ProvenanceMap()
        return NormalizedDoc(text=raw_text, provenance=prov, ledger=[], generation=generation)

    builder = _RulerBuilder(raw_text)
    builder.feed(raw_text)
    builder.close()
    return NormalizedDoc(
        text=builder.result_text(),
        provenance=ProvenanceMap(segments=builder.segments),
        ledger=list(builder.ledger),
        generation=generation,
    )
