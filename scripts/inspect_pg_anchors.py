"""READ-ONLY. Check whether PG's failure shares the A-group root cause:
'Item N' body headings sitting just after a TOC listing, causing anchors to be
discarded. Prints, from the Stage-1 ruler text, where key Item headings occur
and where the pipeline actually placed each detected item. Writes only stdout."""
import gzip
import re
from pathlib import Path

from sec10k.pipeline import run_pipeline

EVAL = Path("tests/fixtures/eval_recent")
PG = "pg_10k_20230630.htm.gz"

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
    raw = read(PG)
    ruler, result = run_pipeline(raw)
    text = ruler_text(ruler)
    print("=" * 78)
    print(f"PG anchor diagnosis: {PG}")
    print("=" * 78)
    print(f"[RULER] text found: {'yes len=' + str(len(text)) if text else 'NO'}")

    if text:
        # locate Item 1 / 2 / 5 / 7 / 8 Business-and-early headings in ruler text
        for label, pat in [
            ("Item 1 Business", r"item\s*1\s*[.\u2014:\-]?\s*business"),
            ("Item 2 Properties", r"item\s*2\s*[.\u2014:\-]?\s*propert"),
            ("Item 5 Market", r"item\s*5\s*[.\u2014:\-]?\s*market"),
            ("Item 7 Management", r"item\s*7\s*[.\u2014:\-]?\s*management"),
            ("Item 8 Financial", r"item\s*8\s*[.\u2014:\-]?\s*financial"),
        ]:
            hits = list(re.finditer(pat, text, re.IGNORECASE))
            print(f"\n[{label}] occurrences in ruler: {len(hits)}")
            for m in hits[:6]:
                print(f"    offset={m.start()}  «{text[m.start():m.start()+80].replace(chr(10),' ')}»")

    print("\n[RESULT] detected items (id / status / span):")
    for it in result.items:
        cs = getattr(it, "char_span", None)
        s = getattr(cs, "start", None)
        e = getattr(cs, "end", None)
        print(f"    {it.item_id:<5} {es(it.status):<26} "
              f"{('[' + str(s) + ',' + str(e) + ')') if cs else 'None'}")
    print("\n[RESULT] first detected item start (compare with Item 1 offset above):")
    if result.items:
        first = result.items[0]
        cs = getattr(first, "char_span", None)
        print(f"    first item id={first.item_id} start={getattr(cs,'start',None)}")

if __name__ == "__main__":
    main()
