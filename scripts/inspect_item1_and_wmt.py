"""READ-ONLY diagnosis. (1) For BRK-B / JPM / NKE: locate where 'Item 1.'
Business-type headings actually sit in the raw text and in the Stage-1 ruler,
to tell apart 'front-matter isolation swallowed Item 1' vs 'anchor regex
missed the heading'. (2) Spot-check WMT (a PASS filing) item-by-item by
printing the first line of each item's span. Imports/inspects only; writes
nothing but stdout."""
import gzip
import re
from pathlib import Path

from sec10k.pipeline import run_pipeline

EVAL = Path("tests/fixtures/eval_recent")
GROUP_A = ["brkb_10k_20251231.htm.gz", "jpm_10k_20251231.htm.gz", "nke_10k_20230531.htm.gz"]
WMT = "wmt_10k_20260131.htm.gz"

def read(name):
    p = EVAL / name
    b = p.read_bytes()
    return gzip.decompress(b) if p.suffix == ".gz" else b

def es(x):
    return getattr(x, "name", None) or str(x)

def build_ruler_text(raw):
    """Run the pipeline and, from the ruler, get the normalized text the
    segmenter actually sees, plus where Stage 1 placed the content start."""
    ruler, result = run_pipeline(raw)
    # try common attribute names for the ruler's text / offsets (best-effort, read-only)
    text = None
    for attr in ("text", "normalized", "normalized_text", "body", "content"):
        v = getattr(ruler, attr, None)
        if isinstance(v, str) and v:
            text = v
            break
    return ruler, result, text

def show_heading_hits(label, raw):
    print("=" * 78)
    print(label)
    print("=" * 78)
    ruler, result, text = build_ruler_text(raw)
    # decode raw for a source-of-truth scan (independent of ruler internals)
    try:
        raw_txt = raw.decode("utf-8", "replace")
    except Exception:
        raw_txt = str(raw)
    # find candidate 'Item 1.' Business headings in the RAW bytes (not 1A/1B/1C)
    pat = re.compile(r"item\s*1\s*[.\u2014:\-]?\s*business", re.IGNORECASE)
    hits = [(m.start(), raw_txt[m.start():m.start()+70].replace("\n", " ")) for m in pat.finditer(raw_txt)]
    print(f"[RAW] 'Item 1 ... Business' heading candidates found: {len(hits)}")
    for off, snip in hits[:8]:
        print(f"    raw_offset={off}  «{snip}»")
    # what Stage 1 kept: print ruler length + first item span start for reference
    print(f"[RULER] text attr found: {'yes' if text else 'NO (attr name unknown)'}"
          f"{'  len=' + str(len(text)) if text else ''}")
    items = result.items
    first = items[0] if items else None
    if first is not None:
        cs = getattr(first, "char_span", None)
        start = getattr(cs, "start", None)
        print(f"[RESULT] first item id={first.item_id} status={es(first.status)} "
              f"span_start={start}")
    # if ruler text is available, show what sits right before the first item start
    if text and first is not None and getattr(getattr(first, 'char_span', None), 'start', None) is not None:
        s = first.char_span.start
        print(f"[RULER] 120 chars BEFORE first item start ({s}):")
        print("    «" + text[max(0, s-120):s].replace("\n", " ") + "»")
        print(f"[RULER] 80 chars AT first item start:")
        print("    «" + text[s:s+80].replace("\n", " ") + "»")
        # also: does the ruler text contain an 'Item 1. Business' heading at all?
        rhits = list(pat.finditer(text))
        print(f"[RULER] 'Item 1 ... Business' candidates inside ruler text: {len(rhits)}")
        for m in rhits[:5]:
            print(f"    ruler_offset={m.start()}  «{text[m.start():m.start()+70].replace(chr(10),' ')}»")
    print()

def spotcheck(name):
    print("#" * 78)
    print(f"WMT SILENT-FAILURE SPOT-CHECK: {name}")
    print("#" * 78)
    ruler, result, text = build_ruler_text(read(name))
    if not text:
        print("Ruler text attr not found under common names; "
              "printing item spans only (cannot show text).")
    for it in result.items:
        cs = getattr(it, "char_span", None)
        if cs is None:
            print(f"  {it.item_id:<5} {es(it.status):<26} span=None")
            continue
        head = ""
        if text:
            head = text[cs.start:cs.start+90].replace("\n", " ")
        print(f"  {it.item_id:<5} {es(it.status):<26} [{cs.start},{cs.end}) len={cs.end-cs.start}")
        if text:
            print(f"        «{head}»")
    print()

def main():
    for name in GROUP_A:
        show_heading_hits(name, read(name))
    spotcheck(WMT)
    print("NOTE: if [RULER] text attr = NO, tell me and I will adjust the attribute "
          "name; the [RAW] heading scan is still valid on its own.")

if __name__ == "__main__":
    main()
