"""Step 2 acceptance: normalization-completeness conservation check.

Includes the load-bearing NEGATIVE test: if the ruler silently drops a visible
word, the check MUST fail. That negative is the evidence the certification is
real and not vacuous.
"""

from __future__ import annotations

from sec10k.ruler.completeness import check_completeness
from sec10k.ruler.formats import decode_bytes
from sec10k.ruler.normalize import normalize


def _check(raw: bytes):
    doc = normalize(raw)
    return doc, check_completeness(decode_bytes(raw), doc.generation, doc.text, doc.ledger)


def test_html_completeness_passes():
    raw = b"<html><body><p>Item 1. Business</p><table><tr><td>We make widgets and gadgets.</td></tr></table></body></html>"
    _doc, report = _check(raw)
    assert report.passed, report.summary()
    assert report.missing_tokens == []
    assert report.extra_tokens == []


def test_ascii_completeness_passes():
    raw = b"ITEM 1. BUSINESS\nWe make widgets.\nITEM 1A. RISK FACTORS\nThings could go wrong.\n"
    _doc, report = _check(raw)
    assert report.passed, report.summary()


def test_negative_dropped_word_fails():
    """Simulate a normalizer bug that loses a visible word -> MUST FAIL."""
    raw = b"<html><body><p>We make widgets and gadgets and sprockets.</p></body></html>"
    doc = normalize(raw)
    tampered = doc.text.replace("sprockets", "")  # silent drop
    report = check_completeness(decode_bytes(raw), doc.generation, tampered, doc.ledger)
    assert not report.passed
    assert "sprockets" in report.missing_tokens


def test_visible_ix_nonfraction_is_kept():
    """Counter-example guarding the mechanism rule against over-exclusion: an
    ``<ix:nonFraction>`` / ``<ix:nonNumeric>`` wraps VISIBLE text — it is in the
    ix: namespace but IS displayed, so the number must reach the ruler and
    conservation must PASS. (Being ix: alone must never trigger exclusion.)"""
    raw = (
        b'<html xmlns:ix="http://www.xbrl.org/2013/inlineXBRL"><body>'
        b'<p>Document type: '
        b'<ix:nonNumeric name="dei:DocumentType">10-K</ix:nonNumeric>.</p>'
        b'<p>Total revenue was '
        b'<ix:nonFraction name="us-gaap:Revenue" contextRef="c1" unitRef="usd">2,026</ix:nonFraction>'
        b' million.</p></body></html>'
    )
    doc, report = _check(raw)
    assert report.passed, report.summary()
    # the visible fact text survived on the ruler...
    assert "2,026" in doc.text
    assert "10-K" in doc.text
    # ...and was NOT mistaken for hidden machine data (no ledger entry for it)
    assert all(e.classification.value != "xbrl_hidden" for e in doc.ledger)


def test_style_hidden_ix_fact_is_excluded():
    """The CSS branch of condition 2: an ix fact wrapper explicitly styled
    display:none is computed-not-displayed, so it is excluded (and ledgered),
    while its visible twin is kept — no double count, conservation PASS."""
    raw = (
        b'<html xmlns:ix="http://www.xbrl.org/2013/inlineXBRL"><body>'
        b'<ix:nonFraction name="us-gaap:Revenue" contextRef="c1" style="display:none">2026</ix:nonFraction>'
        b'<p>Revenue was '
        b'<ix:nonFraction name="us-gaap:Revenue" contextRef="c1">2,026</ix:nonFraction>'
        b' million.</p></body></html>'
    )
    doc, report = _check(raw)
    assert report.passed, report.summary()
    assert "2,026" in doc.text
    assert any(e.classification.value == "xbrl_hidden" for e in doc.ledger)


def test_ix_hidden_not_double_counted():
    """A number appears once as visible text (wrapped in ix:nonFraction) and
    again as a hidden ix fact. Completeness must PASS (no false FAIL, no double
    count): the visible '1,234' is on the ruler once; the hidden copy is dropped
    on both the ruler and the baseline."""
    raw = (
        b'<html xmlns:ix="http://www.xbrl.org/2013/inlineXBRL"><body>'
        b'<ix:hidden><ix:nonFraction name="us-gaap:Revenue" contextRef="c1">1234</ix:nonFraction></ix:hidden>'
        b'<p>Total revenue was <ix:nonFraction name="us-gaap:Revenue" contextRef="c1">1,234</ix:nonFraction> million.</p>'
        b"</body></html>"
    )
    doc, report = _check(raw)
    assert report.passed, report.summary()
    # the hidden fact was recorded for audit, not silently ignored
    assert any(e.classification.value == "xbrl_hidden" for e in doc.ledger)
    # and the visible number survived on the ruler
    assert "1,234" in doc.text
