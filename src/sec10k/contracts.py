"""Data contracts (DESIGN.md §2 + §3 coordinate system).

All models are Pydantic v2 so the whole :class:`FilingResult` serializes to JSON
for free (future Streamlit frontend + cached "ship" of demo results).

The coordinate-system contract (DESIGN.md §3) is the foundation:

* :class:`Ruler` is a *ruler* — the normalized character sequence ``0..N``.
* :class:`CharSpan` is an interval on that ruler.
* item spans and residual spans are BOTH positively identified on the ruler;
  neither is defined as the complement of the other.
* :class:`ProvenanceMap` maps ruler positions back to raw source offsets.
* :class:`StrippedLedger` records content deliberately removed from the ruler,
  so the normalization-completeness conservation equation holds:

      source visible tokens  ==  ruler tokens  ⊎  ledger(stripped-visible) tokens
"""

from __future__ import annotations

from dataclasses import dataclass, field as dc_field
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field, model_validator

from .enums import (
    ConfidenceTier,
    FileGeneration,
    FilingStatus,
    ItemStatus,
    ReasonCode,
    ResidualClass,
    Severity,
    StrippedClass,
)


# --------------------------------------------------------------------------- #
# §3 coordinate system: spans, provenance, ledger, ruler
# --------------------------------------------------------------------------- #
class CharSpan(BaseModel):
    """A half-open interval ``[start, end)`` on the ruler. DESIGN.md §3."""

    model_config = ConfigDict(frozen=True)

    start: int = Field(ge=0)
    end: int = Field(ge=0)

    @model_validator(mode="after")
    def _check(self) -> "CharSpan":
        if self.end < self.start:
            raise ValueError(f"CharSpan end {self.end} < start {self.start}")
        return self

    @property
    def length(self) -> int:
        return self.end - self.start

    def overlaps(self, other: "CharSpan") -> bool:
        """True if the two half-open intervals share any position."""
        return self.start < other.end and other.start < self.end


class SourceRef(BaseModel):
    """A pointer back into the raw bytes/nodes, for frontend highlight. §2."""

    source_kind: str  # "raw_byte" (ascii) | "dom_text" (html)
    source_start: int = Field(ge=0)
    source_end: int = Field(ge=0)


@dataclass(frozen=True, slots=True)
class ProvenanceSegment:
    """Maps a contiguous ruler region to its origin in the raw source.

    ``ruler[ruler_start:ruler_end]`` came from raw source bytes
    ``[source_start:source_end]``. Lengths may differ (whitespace collapse,
    entity decode), but the mapping lets any ruler position resolve to a
    :class:`SourceRef`.

    Deliberately a plain slotted dataclass (not a Pydantic model): a large
    filing yields hundreds of thousands of these, and per-segment Pydantic
    validation dominated runtime. Provenance is internal (it is not part of the
    serialized :class:`FilingResult`), so it does not need Pydantic.
    """

    ruler_start: int
    ruler_end: int
    source_start: int
    source_end: int
    source_kind: str = "dom_text"


@dataclass(slots=True)
class ProvenanceMap:
    """Ordered, non-overlapping segments covering the whole ruler. §3."""

    segments: list[ProvenanceSegment] = dc_field(default_factory=list)

    def source_ref_for(self, span: CharSpan) -> Optional[SourceRef]:
        """Resolve a ruler span to a raw-source :class:`SourceRef`.

        Returns the source interval spanning from the segment containing
        ``span.start`` to the segment containing ``span.end``. Best-effort:
        returns ``None`` if the span falls outside all segments.
        """
        src_start: Optional[int] = None
        src_end: Optional[int] = None
        kind = "dom_text"
        for seg in self.segments:
            if seg.ruler_start <= span.start < seg.ruler_end or (
                span.start == seg.ruler_end and seg.ruler_end == span.start
            ):
                # offset within the segment, proportional fallback to seg start
                src_start = seg.source_start + (span.start - seg.ruler_start)
                kind = seg.source_kind
            if seg.ruler_start < span.end <= seg.ruler_end:
                src_end = seg.source_start + (span.end - seg.ruler_start)
        if src_start is None:
            return None
        if src_end is None:
            src_end = src_start
        return SourceRef(source_kind=kind, source_start=src_start, source_end=max(src_start, src_end))


class StrippedEntry(BaseModel):
    """One deliberately-removed chunk, recorded so nothing is silently dropped.

    DESIGN.md §3. ``text`` is retained for audit and (for visible classes) for
    the conservation-equation token accounting.
    """

    source_start: int = Field(ge=0)
    source_end: int = Field(ge=0)
    classification: StrippedClass
    reason: str
    text: str = ""

    @property
    def is_visible(self) -> bool:
        """Visible strips (page header/footer) participate in the conservation
        equation; ``XBRL_HIDDEN`` is audit-only and excluded (it was never
        visible, so it is on neither side of the equation)."""
        return self.classification != StrippedClass.XBRL_HIDDEN


class ResidualSpan(BaseModel):
    """A residual span ON the ruler, positively classified. DESIGN.md §2/§3."""

    char_span: CharSpan
    classification: ResidualClass


class CompletenessReport(BaseModel):
    """Result of the normalization-completeness check (DESIGN.md §3, Stage 1).

    ``passed`` certifies the ruler: every source visible token is accounted for
    as either a ruler token or a recorded (visible) stripped token.
    """

    passed: bool
    source_visible_tokens: int
    ruler_tokens: int
    stripped_visible_tokens: int
    missing_tokens: list[str] = Field(default_factory=list)  # in source, lost from ruler+ledger
    extra_tokens: list[str] = Field(default_factory=list)    # in ruler, not in source (injected)

    def summary(self) -> str:
        status = "CERTIFIED" if self.passed else "FAILED"
        return (
            f"completeness={status} "
            f"source={self.source_visible_tokens} "
            f"ruler={self.ruler_tokens} stripped={self.stripped_visible_tokens} "
            f"missing={len(self.missing_tokens)} extra={len(self.extra_tokens)}"
        )


class Ruler(BaseModel):
    """The Stage 1 product: a certified-complete ruler. DESIGN.md §3.

    ``text`` is the coordinate system; ``provenance`` maps it back to raw bytes;
    ``stripped_ledger`` records deliberate removals; ``residual_candidates`` are
    the early-isolated non-item structures (cover page, TOC). ``completeness``
    must be ``passed`` for downstream coverage claims to mean anything.
    """

    # provenance is a plain dataclass (see ProvenanceSegment); allow it here.
    model_config = ConfigDict(arbitrary_types_allowed=True)

    text: str
    file_generation: FileGeneration
    provenance: ProvenanceMap = Field(default_factory=ProvenanceMap)
    stripped_ledger: list[StrippedEntry] = Field(default_factory=list)
    residual_candidates: list[ResidualSpan] = Field(default_factory=list)
    completeness: Optional[CompletenessReport] = None

    @property
    def length(self) -> int:
        return len(self.text)

    def slice(self, span: CharSpan) -> str:
        return self.text[span.start:span.end]


# --------------------------------------------------------------------------- #
# §2 items, ruleset, filing
# --------------------------------------------------------------------------- #
class Item(BaseModel):
    """An item segment. DESIGN.md §2.

    The anchor identity is ``item_id`` + order, NEVER a title string. A
    ``merged`` member that was absorbed into a sibling carries ``merged_into``
    and has NO independent ``char_span`` (it is excluded from the geometry set;
    see §3.3-B of the plan / invariants module).
    """

    item_id: str                      # e.g. "1", "1A", "1C"
    part: Optional[str] = None        # "I".."IV"
    char_span: Optional[CharSpan] = None
    status: ItemStatus = ItemStatus.EXTRACTED
    confidence: ConfidenceTier = ConfidenceTier.LOW
    method: str = "deterministic"     # deterministic | llm | human
    reason_codes: list[ReasonCode] = Field(default_factory=list)
    source_ref: Optional[SourceRef] = None
    merged_into: Optional[str] = None

    @model_validator(mode="after")
    def _check_merged(self) -> "Item":
        if self.merged_into is not None and self.status != ItemStatus.MERGED:
            raise ValueError("merged_into requires status=merged")
        return self

    @property
    def is_geometric(self) -> bool:
        """Whether this item contributes its own span to the no-overlap /
        coverage geometry set (plan §3.3-B).

        Excluded: absorbed ``merged_into`` members (their region is covered by
        the merge representative's single span) and span-less items. INCLUDED:
        ``reserved`` / ``incorporated_by_reference`` items — they are
        *correctly empty* of a narrative body, but their heading/marker text
        (e.g. "Item 6 [Reserved]") is real ruler content that coverage must
        account for. Being correctly empty is a PASS, not a reason to vanish
        from the ruler's geometry.
        """
        return self.merged_into is None and self.char_span is not None


class LegalStructure(BaseModel):
    """An authorized structural shape (DESIGN.md §1 flex-A / §2 legal_structures).

    ``merges`` lists groups of adjacent item_ids that may legally share one
    heading/body. ``absences`` lists item_ids that may be legitimately absent
    via ``incorporated_by_reference`` (e.g. Part III 10-14 -> proxy).
    """

    name: str
    merges: list[list[str]] = Field(default_factory=list)
    absences: list[str] = Field(default_factory=list)


class Ruleset(BaseModel):
    """Per-fiscal-year legal expectations (Stage 0 product). DESIGN.md §2.

    This milestone ships a minimal static table + interface; full Stage 0
    spec-ingestion is out of scope.
    """

    fiscal_year_end: str               # key, e.g. "2023-12-31"
    expected_items: list[str]          # ordered legal sequence
    reserved_items: set[str] = Field(default_factory=set)
    legal_structures: list[LegalStructure] = Field(default_factory=list)
    file_generation: FileGeneration = FileGeneration.HTML_XBRL
    item_parts: dict[str, str] = Field(default_factory=dict)  # per-item Part ("I".."IV"), from the era ruleset; empty => part_of returns None

    def order_index(self, item_id: str) -> Optional[int]:
        try:
            return self.expected_items.index(item_id)
        except ValueError:
            return None

    def part_of(self, item_id: str) -> str | None:
        """Part membership for an item, decided by this era's ruleset (never a
        hard-coded modern table). Returns None if the item has no declared part."""
        return self.item_parts.get(item_id)


class Filing(BaseModel):
    """A raw filing to be processed. DESIGN.md §2."""

    cik: Optional[str] = None
    accession: Optional[str] = None
    fiscal_year_end: Optional[str] = None
    form_type: str = "10-K"
    raw_bytes: bytes


# --------------------------------------------------------------------------- #
# Stage 3 verification output
# --------------------------------------------------------------------------- #
class Violation(BaseModel):
    """One invariant violation or low-confidence signal. DESIGN.md §5."""

    code: ReasonCode
    severity: Severity
    message: str
    item_id: Optional[str] = None
    char_span: Optional[CharSpan] = None


class VerificationReport(BaseModel):
    """Aggregated Stage 3 result. DESIGN.md §5.

    ``failed`` = ANY hard invariant violation (categorical, score-independent).
    """

    violations: list[Violation] = Field(default_factory=list)
    invariant_results: dict[str, bool] = Field(default_factory=dict)  # name -> passed
    filing_status: FilingStatus = FilingStatus.PASS
    filing_confidence: ConfidenceTier = ConfidenceTier.LOW

    @property
    def hard_violations(self) -> list[Violation]:
        return [v for v in self.violations if v.severity == Severity.HARD]


class FilingResult(BaseModel):
    """The deliverable per filing. DESIGN.md §2."""

    items: list[Item] = Field(default_factory=list)
    residual: list[ResidualSpan] = Field(default_factory=list)
    filing_status: FilingStatus = FilingStatus.PASS
    filing_confidence: ConfidenceTier = ConfidenceTier.LOW
    verification_report: VerificationReport = Field(default_factory=VerificationReport)
