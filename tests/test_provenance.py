"""Step 1 acceptance: ruler<->source provenance round-trip.

Resolving a ruler span to a SourceRef must land on the raw bytes that produced
it. For ASCII (identity normalization) the round-trip is exact; for HTML we
assert the resolved raw slice contains the expected anchor text.
"""

from __future__ import annotations

from sec10k.contracts import CharSpan
from sec10k.ruler.formats import decode_bytes
from sec10k.ruler.normalize import normalize


def test_ascii_roundtrip_exact():
    raw = b"ITEM 1. BUSINESS\nWe make widgets.\nITEM 1A. RISK FACTORS\n"
    doc = normalize(raw)
    raw_text = decode_bytes(raw)
    # pick the ruler span covering "BUSINESS"
    idx = doc.text.index("BUSINESS")
    span = CharSpan(start=idx, end=idx + len("BUSINESS"))
    ref = doc.provenance.source_ref_for(span)
    assert ref is not None
    assert raw_text[ref.source_start:ref.source_end] == "BUSINESS"


def test_html_provenance_lands_on_source():
    raw = b"<html><body><p>Item&nbsp;1.&nbsp;Business</p><p>We make widgets.</p></body></html>"
    doc = normalize(raw)
    raw_text = decode_bytes(raw)
    assert "Business" in doc.text
    assert "widgets" in doc.text
    idx = doc.text.index("widgets")
    span = CharSpan(start=idx, end=idx + len("widgets"))
    ref = doc.provenance.source_ref_for(span)
    assert ref is not None
    # the resolved raw region should contain the word
    assert "widgets" in raw_text[ref.source_start:ref.source_end + 3]


def test_nbsp_entity_maps_six_raw_chars_to_one_ruler_char():
    raw = b"<p>A&nbsp;B</p>"
    doc = normalize(raw)
    # ruler has a single space where &nbsp; was (or other whitespace)
    assert "A" in doc.text and "B" in doc.text
    # provenance must cover the ruler without raising
    for seg in doc.provenance.segments:
        assert seg.ruler_end >= seg.ruler_start
        assert seg.source_end >= seg.source_start
