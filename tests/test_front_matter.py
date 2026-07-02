"""Step 4 acceptance: cover-page + TOC isolation as residual candidates.

The fake TOC (which echoes every "Item N") must be classified as ``toc`` so a
future Stage 2 won't treat its echoes as real anchors — the fake-title trap,
pre-dismantled.
"""

from __future__ import annotations

from pathlib import Path

from sec10k.enums import ResidualClass
from sec10k.ruler.front_matter import detect_cover_page, detect_toc, isolate_front_matter

_FIXTURE = Path(__file__).parent / "fixtures" / "synthetic" / "mini_10k.txt"


def _text() -> str:
    return _FIXTURE.read_text()


def test_toc_detected():
    text = _text()
    toc = detect_toc(text)
    assert toc is not None
    block = text[toc.start:toc.end]
    assert "Item 1. Business" in block
    assert "Item 8" in block
    # the TOC block must NOT swallow the real body that follows
    assert "designs and manufactures" not in block


def test_cover_page_detected():
    text = _text()
    toc = detect_toc(text)
    cover = detect_cover_page(text, toc)
    assert cover is not None
    block = text[cover.start:cover.end]
    assert "SECURITIES AND EXCHANGE COMMISSION" in block
    assert cover.end <= toc.start


def test_isolate_returns_both_classes():
    classes = {r.classification for r in isolate_front_matter(_text())}
    assert ResidualClass.COVER_PAGE in classes
    assert ResidualClass.TOC in classes


def test_no_false_toc_without_page_refs():
    # body anchors without page references must not be detected as a TOC
    text = "ITEM 1. BUSINESS\nWe build things.\nITEM 1A. RISK\nThings vary.\nITEM 2. PROPERTIES\nWe lease space.\n"
    assert detect_toc(text) is None
