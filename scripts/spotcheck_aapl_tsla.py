"""READ-ONLY silent-failure spot-check for PASS filings (AAPL/TSLA).

For each item prints: id / status / part / merged_into / span-length, then the
HEAD (~90 chars) and TAIL (~60 chars) of its span from the Stage-1 ruler text.
Lets a human verify each item's content truly belongs to it and does not spill
into the next item. Imports/inspects only; writes only stdout; no file edits."""
import gzip
from pathlib import Path

from sec10k.pipeline import run_pipeline

EVAL = Path("tests/fixtures/eval_recent")
TARGETS = [
    "aapl_10k_20230930.htm.gz",
    "tsla_10k_20251231.htm.gz",
]

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

def is_main(item_id):
    return item_id[-1].isdigit()

def run_one(name):
    print("=" * 82)
    print(name)
    print("=" * 82)
    ruler, result = run_pipeline(read(name))
    text = ruler_text(ruler)
    print(f"filing_status={es(result.filing_status)}  items={len(result.items)}  "
          f"ruler_len={len(text) if text else 'NO'}")
    if not text:
        print("  (ruler text attr not found; cannot show head/tail)")
        return
    prev_end = None
    for it in result.items:
        cs = getattr(it, "char_span", None)
        mid = getattr(it, "merged_into", None)
        status = es(it.status)
        part = str(getattr(it, "part", None) or "-")
        if cs is None:
            print(f"\n[{it.item_id}] status={status} part={part} "
                  f"merged_into={mid or '-'} span=None")
            continue
        length = cs.end - cs.start
        head = text[cs.start:cs.start + 90].replace("\n", " ")
        tail = text[max(cs.start, cs.end - 60):cs.end].replace("\n", " ")
        gapinfo = ""
        if prev_end is not None:
            delta = cs.start - prev_end
            if delta != 0:
                gapinfo = f"  (gap-from-prev={delta})"
        flag = ""
        if is_main(it.item_id) and status == "EXTRACTED" and length < 200:
            flag = "  <-- SHORT main item?"
        print(f"\n[{it.item_id}] status={status} part={part} "
              f"merged_into={mid or '-'} len={length}{gapinfo}{flag}")
        print(f"    HEAD «{head}»")
        print(f"    TAIL «{tail}»")
        prev_end = cs.end
    print()

def main():
    for name in TARGETS:
        run_one(name)

if __name__ == "__main__":
    main()
