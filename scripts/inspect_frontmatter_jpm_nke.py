"""READ-ONLY. Print the actual char_span of every Stage-1 residual candidate
(especially COVER_PAGE / TOC) for JPM and NKE, alongside where the real
'Item 1. Business' body heading sits and where segmentation actually starts,
to confirm the A-group shares one root cause (TOC end-boundary over-extends
just past the body Item 1 heading). Imports/inspects only; writes only stdout."""
import gzip
import re
from pathlib import Path

from sec10k.pipeline import run_pipeline

EVAL = Path("tests/fixtures/eval_recent")
TARGETS = ["jpm_10k_20251231.htm.gz", "nke_10k_20230531.htm.gz"]

def read(name):
    p = EVAL / name
    b = p.read_bytes()
    return gzip.decompress(b) if p.suffix == ".gz" else b

def es(x):
    return getattr(x, "name", None) or str(x)

def ruler_text(ruler):
    for attr in ("text", "normalized", "normalized_text", "body", "content"):
        v = getattr(ruler, attr, None)
        if isinstance(v, str) and v:
            return v
    return None

def main():
    pat = re.compile(r"item\s*1\s*[.\u2014:\-]?\s*business", re.IGNORECASE)
    for name in TARGETS:
        raw = read(name)
        ruler, result = run_pipeline(raw)
        text = ruler_text(ruler)
        print("=" * 80)
        print(name)
        print("=" * 80)
        print(f"[RULER] text len: {len(text) if text else 'NO'}")

        cands = list(getattr(ruler, "residual_candidates", []) or [])
        print(f"[STAGE-1] residual_candidates: {len(cands)}")
        print(f"    {'classification':<20}{'span':<22}{'len':<9}head")
        for rc in sorted(cands, key=lambda c: getattr(getattr(c, 'char_span', None), 'start', 0)):
            cs = getattr(rc, "char_span", None)
            cls = es(getattr(rc, "classification", "?"))
            if cs is None:
                print(f"    {cls:<20}{'None':<22}{'-':<9}")
                continue
            head = (text[cs.start:cs.start+46].replace("\n", " ") if text else "")
            print(f"    {cls:<20}{('[' + str(cs.start) + ',' + str(cs.end) + ')'):<22}"
                  f"{cs.end - cs.start:<9}«{head}»")

        front = [rc.char_span for rc in cands
                 if es(getattr(rc, "classification", "")) in ("COVER_PAGE", "TOC")]
        if front:
            fmin = min(cs.start for cs in front)
            fmax = max(cs.end for cs in front)
            print(f"[FRONT] COVER_PAGE+TOC spans: {len(front)}  "
                  f"min_start={fmin}  max_end={fmax}")
        else:
            print("[FRONT] no COVER_PAGE/TOC candidates found")

        if text:
            hits = [m.start() for m in pat.finditer(text)]
            print(f"[BODY] 'Item 1 ... Business' heading offsets in ruler: {hits[:8]}")
            # measure the over-extend: how far TOC end sits past the LAST body Item-1 heading
            if front and hits:
                body_last = hits[-1]
                print(f"[MEASURE] TOC/cover max_end={fmax}  last body Item1 offset={body_last}"
                      f"  -> end minus body = {fmax - body_last}")

        if result.items:
            first = result.items[0]
            cs = getattr(first, "char_span", None)
            print(f"[RESULT] first detected item id={first.item_id} "
                  f"start={getattr(cs, 'start', None)}")
        print()

if __name__ == "__main__":
    main()
