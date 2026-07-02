"""Step 1 acceptance: file-generation detection across the three generations."""

from __future__ import annotations

from sec10k.enums import FileGeneration
from sec10k.ruler.formats import decode_bytes, detect_generation


def test_detect_ascii():
    raw = b"UNITED STATES\nSECURITIES AND EXCHANGE COMMISSION\n\fITEM 1. BUSINESS\n"
    assert detect_generation(raw) is FileGeneration.ASCII


def test_detect_html():
    raw = b"<html><body><p>Item 1. Business</p></body></html>"
    assert detect_generation(raw) is FileGeneration.HTML


def test_detect_html_xbrl():
    raw = (
        b'<html xmlns:ix="http://www.xbrl.org/2013/inlineXBRL"><body>'
        b'<ix:nonNumeric name="dei:DocumentType">10-K</ix:nonNumeric>'
        b"<p>Item 1. Business</p></body></html>"
    )
    assert detect_generation(raw) is FileGeneration.HTML_XBRL


def test_decode_latin1_fallback():
    # 0xA9 (©) is invalid standalone UTF-8; must not raise, must not lose bytes.
    raw = b"Item 1. Business \xa9 2023"
    text = decode_bytes(raw)
    assert "Item 1. Business" in text
    assert len(text) == len(raw)  # latin-1 is 1 byte -> 1 char
