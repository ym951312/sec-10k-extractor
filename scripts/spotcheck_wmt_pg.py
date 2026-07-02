"""READ-ONLY head+tail spot-check for WMT and PG (PASS filings)."""
import gzip
from pathlib import Path
from sec10k.pipeline import run_pipeline

EVAL = Path("tests/fixtures/eval_recent")
TARGETS = ["wmt_10k_20260131.htm.gz", "pg_10k_20230630.htm.gz"]

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
        print("  (ruler text attr not found)")
        return
    prev_end = None
    for it in result.items:
        cs = getattr(it, "char_span", None)
        mid = getattr(it, "merged_into", None)
        status = es(it.status)
        part = str(getattr(it, "part", None) or "-")
        if cs is None:
            print(f"\n[{it.item_id}] status={status} part={part} merged_into={mid or '-'} span=None")
            continue
        length = cs.end - cs.start
        head = text[cs.start:cs.start + 90].replace("\n", " ")
        tail = text[max(cs.start, cs.end - 60):cs.end].replace("\n", " ")
        gapinfo = ""
        if prev_end is not None and cs.start - prev_end != 0:
            gapinfo = f"  (gap-from-prev={cs.start - prev_end})"
        flag = "  <-- SHORT main item?" if (is_main(it.item_id) and status == "EXTRACTED" and length < 200) else ""
        print(f"\n[{it.item_id}] status={status} part={part} merged_into={mid or '-'} len={length}{gapinfo}{flag}")
        print(f"    HEAD «{head}»")
        print(f"    TAIL «{tail}»")
        prev_end = cs.end
    print()

def main():
    for name in TARGETS:
        run_one(name)

if __name__ == "__main__":
    main()
