"""Step 5 acceptance: end-to-end Stage 1 on the synthetic fixture.

The full ruler must be certified complete (after header/footer stripping) and
expose cover-page + TOC residual candidates.
"""

from __future__ import annotations

from pathlib import Path

from sec10k.enums import ResidualClass
from sec10k.stage1 import build_ruler

_FIXTURE = Path(__file__).parent / "fixtures" / "synthetic" / "mini_10k.txt"


def test_stage1_certifies_and_isolates():
    raw = _FIXTURE.read_bytes()
    ruler = build_ruler(raw)

    # ruler is certified complete
    assert ruler.completeness is not None
    assert ruler.completeness.passed, ruler.completeness.summary()

    # repeated running head was stripped to the ledger
    classes = {e.classification.value for e in ruler.stripped_ledger}
    assert "page_header_footer" in classes
    assert ruler.text.count("ACME ROBOTICS CORP - FORM 10-K") == 0

    # cover page + TOC isolated as residual candidates
    rc = {r.classification for r in ruler.residual_candidates}
    assert ResidualClass.COVER_PAGE in rc
    assert ResidualClass.TOC in rc

    # the real body survived
    assert "designs and manufactures industrial robots" in ruler.text
    assert "1,234" in ruler.text
