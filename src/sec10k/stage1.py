"""Stage 1 orchestration — produce a certified-complete ruler. DESIGN.md §4.

Pipeline:

1. detect generation + decode bytes
2. normalize -> ruler text + provenance + xbrl_hidden ledger
3. strip repeated header/footer chrome -> ledger (clean the ruler)
4. run the completeness check -> CERTIFY the ruler (must pass for downstream
   coverage claims to mean anything)
5. isolate cover page + TOC as residual candidates (on the ruler)

The result is a :class:`~sec10k.contracts.Ruler`. Steps 2-5 require no API key
or network access.
"""

from __future__ import annotations

from .contracts import Ruler
from .ruler.completeness import check_completeness
from .ruler.formats import decode_bytes
from .ruler.front_matter import isolate_front_matter
from .ruler.headers_footers import strip_headers_footers
from .ruler.normalize import normalize


def build_ruler(raw: bytes) -> Ruler:
    """Run Stage 1 on raw filing bytes and return the certified ruler."""
    raw_text = decode_bytes(raw)
    doc = normalize(raw)

    ruler = Ruler(
        text=doc.text,
        file_generation=doc.generation,
        provenance=doc.provenance,
        stripped_ledger=list(doc.ledger),
    )

    # 3. clean the ruler (header/footer chrome -> ledger)
    ruler = strip_headers_footers(ruler)

    # 4. certify completeness against the independent baseline
    report = check_completeness(
        raw_text, ruler.file_generation, ruler.text, ruler.stripped_ledger
    )
    ruler = ruler.model_copy(update={"completeness": report})

    # 5. isolate cover page + TOC as residual candidates (kept on the ruler)
    ruler = ruler.model_copy(update={
        "residual_candidates": isolate_front_matter(ruler.text),
    })
    return ruler
