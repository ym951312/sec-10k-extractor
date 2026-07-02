"""File-generation format detection (DESIGN.md §1, §4 Stage 1 step 2).

Reg S-T governs how EDGAR filings are encoded across generations:

* ASCII      — early (~pre-2001) plain text, paginated with form-feeds / <PAGE>.
* HTML       — HTML markup, no inline XBRL.
* HTML+XBRL  — HTML carrying inline XBRL (``<ix:...>`` tags), the modern form.

Detection is deterministic and cheap. It drives parser-strategy selection; it is
NOT a content claim.
"""

from __future__ import annotations

import re

from ..enums import FileGeneration

# HEURISTIC format detection by an enumerated allow-list of genuine HTML-document
# markers. <table> is deliberately EXCLUDED: EDGAR ASCII-era filings use SGML
# <TABLE> (with <S>/<C> column markers) to lay out financial tables, so keying on
# it misclassified pure-ASCII filings as HTML and bypassed the ASCII code path.
#
# Failure mode of an enumerated list: if a genuine HTML tag is missing from this
# list, the misclassification direction is "a rare HTML file that uses ONLY
# table/tr/td with no <div>/<span>/<p>/<font>/<html>/<body> could be read as
# ASCII". This does not trigger for any known fixture. The direction is also the
# safer one: the ASCII path is an identity normalization, so any resulting anomaly
# is more likely to surface downstream (completeness / segmentation) than to be
# silently wrong. (Tracked in docs/reports/known-limitations-notes.md.)
_HTML_HINT = re.compile(
    rb"<\s*(?:html|body|div|p|font|span)\b|<!doctype\s+html", re.IGNORECASE
)
_IX_HINT = re.compile(rb"<\s*ix:", re.IGNORECASE)
_XBRL_NS_HINT = re.compile(rb"xmlns:ix\s*=", re.IGNORECASE)


def detect_generation(raw: bytes) -> FileGeneration:
    """Classify the file generation of ``raw`` filing bytes."""
    head = raw[:200_000]  # inline-XBRL namespace + ix tags appear early
    if _IX_HINT.search(raw) or _XBRL_NS_HINT.search(head):
        return FileGeneration.HTML_XBRL
    if _HTML_HINT.search(head):
        return FileGeneration.HTML
    return FileGeneration.ASCII


def decode_bytes(raw: bytes) -> str:
    """Decode raw filing bytes to text. EDGAR is ASCII/Latin-1/UTF-8; we try
    UTF-8 then fall back to Latin-1 (which never errors) to avoid losing bytes
    — losing bytes here would violate the certified-complete-ruler contract."""
    try:
        return raw.decode("utf-8")
    except UnicodeDecodeError:
        return raw.decode("latin-1")
