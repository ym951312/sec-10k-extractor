"""Step 3 acceptance: repeated header/footer detection + ledger + conservation.

After stripping, the conservation equation must STILL hold (nothing silently
dropped, nothing over-stripped beyond what the ledger records).
"""

from __future__ import annotations

from sec10k.contracts import Ruler
from sec10k.ruler.completeness import check_completeness
from sec10k.ruler.formats import decode_bytes
from sec10k.ruler.headers_footers import (
    detect_header_footer_spans,
    strip_headers_footers,
)
from sec10k.ruler.normalize import normalize


def _ruler_from(raw: bytes) -> tuple[Ruler, str]:
    doc = normalize(raw)
    ruler = Ruler(
        text=doc.text, file_generation=doc.generation,
        provenance=doc.provenance, stripped_ledger=list(doc.ledger),
    )
    return ruler, decode_bytes(raw)


# 4 "pages" with identical running header + a page-number footer.
_ASCII_PAGES = b"".join(
    b"ACME CORP - FORM 10-K\n"
    b"ITEM " + str(i).encode() + b". BODY\n"
    b"Unique content for section " + str(i).encode() + b".\n"
    b"Page " + str(i).encode() + b"\n\f"
    for i in range(1, 5)
)


def test_detects_repeated_header():
    ruler, _ = _ruler_from(_ASCII_PAGES)
    spans = detect_header_footer_spans(ruler.text)
    found = {ruler.text[s.start:s.end].strip() for s in spans}
    assert "ACME CORP - FORM 10-K" in found
    # "Page N" folds to the same normalized chrome and is stripped too
    assert any(t.startswith("Page") for t in found)


def test_strip_records_ledger_and_preserves_conservation():
    ruler, raw_text = _ruler_from(_ASCII_PAGES)
    before = check_completeness(raw_text, ruler.file_generation, ruler.text, ruler.stripped_ledger)
    assert before.passed

    stripped = strip_headers_footers(ruler)
    # header text removed from the ruler...
    assert stripped.text.count("ACME CORP - FORM 10-K") == 0
    # ...and recorded in the ledger as page_header_footer
    classes = {e.classification.value for e in stripped.stripped_ledger}
    assert "page_header_footer" in classes
    # unique body content is untouched
    assert "Unique content for section 3." in stripped.text

    # conservation still holds after stripping
    after = check_completeness(raw_text, stripped.file_generation, stripped.text, stripped.stripped_ledger)
    assert after.passed, after.summary()


def test_no_false_strip_when_no_repetition():
    raw = b"ITEM 1. BUSINESS\nWe make widgets.\nITEM 1A. RISK\nThings vary.\n"
    ruler, _ = _ruler_from(raw)
    assert detect_header_footer_spans(ruler.text) == []
    assert strip_headers_footers(ruler) is ruler  # unchanged
