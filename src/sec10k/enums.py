"""Enumerations for the data contracts (DESIGN.md §2).

Two classification enums are kept **deliberately separate** (per the approved
plan §3.3 and reviewer note 2):

* :class:`ResidualClass` — classes of spans that live **on the ruler** (they
  occupy real char positions and participate in the coverage invariant).
* :class:`StrippedClass` — classes of content **removed from the ruler** and
  recorded in the StrippedLedger (they are *off* the ruler; they participate
  in the normalization-completeness conservation equation, not coverage).

DESIGN.md §2 originally listed ``page_header_footer`` under residual, but §3's
logic strips repeated headers/footers during normalization to clean the ruler,
so it belongs to the ledger (off-ruler), not a residual span. We pin that here.
"""

from __future__ import annotations

from enum import Enum


class FileGeneration(str, Enum):
    """File-generation format (Reg S-T governed). DESIGN.md §1, §4 Stage 1."""

    ASCII = "ascii"          # early (~pre-2001) plain text + form-feed pages
    HTML = "html"            # HTML without inline XBRL
    HTML_XBRL = "html_xbrl"  # HTML with inline XBRL (modern)


class ItemStatus(str, Enum):
    """Status of an extracted item segment. DESIGN.md §2."""

    EXTRACTED = "extracted"
    RESERVED = "reserved"                              # legally empty -> PASS
    INCORPORATED_BY_REFERENCE = "incorporated_by_reference"  # body external -> PASS
    MERGED = "merged"                                  # shares one heading/body
    FAILED = "failed"                                  # could not segment reliably


class ResidualClass(str, Enum):
    """Classification of a residual span that sits ON the ruler. DESIGN.md §2/§3.

    These are *positively identified* known non-item structures, NOT "everything
    that is not an item" (never a complement). A large ``UNCLASSIFIED`` block is
    a red flag (invariant 4).
    """

    COVER_PAGE = "cover_page"
    TOC = "toc"
    PART_DIVIDER = "part_divider"
    SIGNATURES = "signatures"
    EXHIBIT_INDEX = "exhibit_index"
    UNCLASSIFIED = "unclassified"


class StrippedClass(str, Enum):
    """Classification of content removed from the ruler and logged. DESIGN.md §3.

    Off-ruler; recorded in the StrippedLedger so nothing is silently dropped.
    """

    PAGE_HEADER_FOOTER = "page_header_footer"  # repeated per-page chrome (visible)
    XBRL_HIDDEN = "xbrl_hidden"                # <ix:hidden> facts (never visible; audit-only)


class FilingStatus(str, Enum):
    """Filing-level outcome of the Stage 3 gate. DESIGN.md §5."""

    PASS = "pass"
    REVIEW = "review"
    FAILED = "failed"


class ConfidenceTier(str, Enum):
    """Pre-calibration confidence. DESIGN.md §5: do not treat as probability
    until calibrated against an eval set; use high/med/low tiers for now."""

    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class Severity(str, Enum):
    """Whether an invariant violation is a hard constraint (forces ``failed``)
    or a soft signal (lowers confidence). DESIGN.md §5: ``failed`` = any HARD
    invariant violation (categorical)."""

    HARD = "hard"
    SOFT = "soft"


class ReasonCode(str, Enum):
    """Stable codes for violations / low-confidence reasons. DESIGN.md §2, §5.

    The ``DIAG_*`` codes are the *non-scoring* "violation vs formatting"
    diagnostic notes (DESIGN.md §0/§2): they annotate failures, they never
    emit a verdict about whether a company is non-compliant.
    """

    # --- Stage 1 (ruler) ---
    NORMALIZATION_INCOMPLETE = "normalization_incomplete"  # token conservation broke

    # --- Stage 3 hard invariants (DESIGN.md §5) ---
    ORDER_VIOLATION = "order_violation"            # inv 1
    OVERLAP = "overlap"                            # inv 2
    COVERAGE_GAP = "coverage_gap"                  # inv 3
    COVERAGE_OVERLAP = "coverage_overlap"          # inv 3
    UNCLASSIFIED_RESIDUAL = "unclassified_residual"  # inv 4 (large block)
    ILLEGAL_STRUCTURE = "illegal_structure"        # inv 5
    MISSING_EXPECTED_ITEM = "missing_expected_item"  # inv 6
    XBRL_MISMATCH = "xbrl_mismatch"                # inv 7
    CROSS_METHOD_DISAGREE = "cross_method_disagree"  # inv 8

    # --- Soft / low-confidence signals ---
    LOW_EVIDENCE = "low_evidence"
    AMBIGUOUS_ANCHOR = "ambiguous_anchor"

    # --- Non-scoring diagnostic notes (never a verdict) ---
    DIAG_POSSIBLE_FORMATTING = "diag_possible_formatting"
    DIAG_POSSIBLE_NONCOMPLIANCE = "diag_possible_noncompliance"
