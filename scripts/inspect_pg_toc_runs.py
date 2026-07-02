"""READ-ONLY. Pin down WHY PG's TOC run breaks early. Reuses the real
_ITEM_LINE / _runs from front_matter.py (imported, not reimplemented) and runs
them on PG's Stage-1 ruler text. Prints every 'Item N' line the regex finds
(offset, parsed number, text), then the runs at gap=600 and gap=700, so we can
see how many anchor lines exist, their item numbers (is the tail monotonic or a
back-jump?), and exactly where the run splits. Writes only stdout; no file edits."""
import gzip
import re
from pathlib import Path

from sec10k.pipeline import run_pipeline
from sec10k.ruler import front_matter as fm

EVAL = Path("tests/fixtures/eval_recent")
PG = "pg_10k_20230630.htm.gz"

def read(name):
    p = EVAL / name
    b = p.read_bytes()
    return gzip.decompress(b) if p.suffix == ".gz" else b

def ruler_text(ruler):
    for attr in ("text", "normalized", "normalized_text", "body", "content"):
        v = getattr(ruler, attr, None)
        if isinstance(v, str) and v:
            return v
    return None

def main():
    ruler, result = run_pipeline(read(PG))
    text = ruler_text(ruler)
    print("=" * 80)
    print(f"PG TOC-run diagnosis: {PG}")
    print("=" * 80)
    if not text:
        print("Ruler text attr not found; cannot proceed with line scan.")
        return
    print(f"[RULER] text len: {len(text)}")

    # --- reuse the REAL _ITEM_LINE regex from front_matter.py ---
    line_re = getattr(fm, "_ITEM_LINE", None)
    print(f"[REGEX] using front_matter._ITEM_LINE = {getattr(line_re,'pattern',line_re)!r}")

    # scan line by line exactly like _anchor_lines would (per-line, match at line start)
    anchors = []  # (line_start_offset, item_number_str, raw_line_head)
    pos = 0
    for line in text.splitlines(keepends=True):
        m = line_re.match(line) if line_re else None
        if m:
            num = "".join(g for g in m.groups() if g)  # e.g. '1','1A','9B'
            anchors.append((pos, num, line[:60].replace("\n", " ")))
        pos += len(line)

    print(f"\n[ANCHOR LINES] _ITEM_LINE matched {len(anchors)} lines "
          f"(min needed for TOC = _MIN_TOC_ENTRIES={getattr(fm,'_MIN_TOC_ENTRIES','?')})")
    for off, num, head in anchors[:40]:
        print(f"    offset={off:<8} item={num:<5} «{head}»")

    # --- reuse the REAL _runs to see how they cluster at each gap ---
    items_for_runs = [(off, off + 1) for off, _num, _h in anchors]  # (start,end)-ish
    for gapname, gap in (("_TOC_GAP", getattr(fm, "_TOC_GAP", 600)),
                         ("_DENSE_GAP", getattr(fm, "_DENSE_GAP", 700))):
        try:
            runs = fm._runs(items_for_runs, gap)
        except Exception as e:
            print(f"\n[RUNS gap={gapname}={gap}] could not call fm._runs directly: {e!r}")
            continue
        print(f"\n[RUNS gap={gapname}={gap}] produced {len(runs)} run(s):")
        for i, run in enumerate(runs):
            first_off = run[0][0]
            last_off = run[-1][0]
            # map run members back to their item numbers via offset
            nums = [num for (off, num, _h) in anchors if first_off <= off <= last_off]
            print(f"    run#{i}: {len(run)} lines  offsets [{first_off}..{last_off}]  items={nums}")

    print("\n[RESULT] first detected item / status:")
    if result.items:
        it = result.items[0]
        cs = getattr(it, "char_span", None)
        print(f"    id={it.item_id} start={getattr(cs,'start',None)}")

if __name__ == "__main__":
    main()
