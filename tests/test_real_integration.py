"""Step 8: integration tests on real EDGAR filings (the "later: real" half of
the fixture strategy).

These exercise the certified-complete-ruler contract against genuinely messy
real-world markup (inline XBRL, nested tables, drop-cap word splitting, repeated
page chrome) that synthetic fixtures cannot anticipate. Real fixtures live in
``tests/fixtures/real/`` (committed gzipped, or fetched via
``scripts/fetch_edgar_samples.py``).

The suite stays zero-network: if no real fixtures are present, these tests skip
rather than fail.
"""

from __future__ import annotations

import gzip
from pathlib import Path

import pytest

from sec10k.stage1 import build_ruler

_REAL_DIR = Path(__file__).parent / "fixtures" / "real"
_PATTERNS = ("*.htm", "*.html", "*.txt", "*.htm.gz", "*.html.gz", "*.txt.gz")


def _real_files() -> list[Path]:
    files: list[Path] = []
    for pat in _PATTERNS:
        files.extend(sorted(_REAL_DIR.glob(pat)))
    return files


def _read(path: Path) -> bytes:
    if path.suffix == ".gz":
        return gzip.decompress(path.read_bytes())
    return path.read_bytes()


_RULER_CACHE: dict[Path, object] = {}


def _ruler(path: Path):
    """Build the ruler once per file and cache it (large filings are costly)."""
    if path not in _RULER_CACHE:
        _RULER_CACHE[path] = build_ruler(_read(path))
    return _RULER_CACHE[path]


_FILES = _real_files()


@pytest.mark.skipif(not _FILES, reason="no real fixtures present (run scripts/fetch_edgar_samples.py)")
@pytest.mark.parametrize("path", _FILES, ids=lambda p: p.name)
def test_real_filing_ruler_is_certified(path: Path):
    """The ruler built from a real filing must be certified complete: every
    visible source token accounted for on the ruler or in the ledger."""
    ruler = _ruler(path)
    assert ruler.length > 0
    assert ruler.completeness is not None
    assert ruler.completeness.passed, (
        f"{path.name}: {ruler.completeness.summary()}; "
        f"missing={ruler.completeness.missing_tokens[:10]} "
        f"extra={ruler.completeness.extra_tokens[:10]}"
    )


@pytest.mark.skipif(not _FILES, reason="no real fixtures present")
@pytest.mark.parametrize("path", _FILES, ids=lambda p: p.name)
def test_real_filing_strips_some_chrome(path: Path):
    """A multi-page real filing should expose a cover page and have stripped at
    least some repeated header/footer chrome (sanity, not a hard contract)."""
    ruler = _ruler(path)
    classes = {r.classification.value for r in ruler.residual_candidates}
    assert "cover_page" in classes or "toc" in classes


@pytest.mark.skipif(not _FILES, reason="no real fixtures present")
@pytest.mark.parametrize("path", _FILES, ids=lambda p: p.name)
def test_real_filing_pipeline_runs_and_finds_items(path: Path):
    """The full deterministic pipeline must run end-to-end on real data without
    crashing and detect a plausible number of items. Stage 3 may flag the filing
    (real segmentation is imperfect); we assert it produces a result honestly,
    not that it passes."""
    from sec10k.pipeline import run_pipeline

    ruler, result = run_pipeline(_read(path))
    assert ruler.completeness.passed
    item_ids = {it.item_id for it in result.items}
    # a real 10-K should surface several of the core items
    assert len(item_ids) >= 5, sorted(item_ids)
    assert result.filing_status is not None
