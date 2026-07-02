"""Run the pipeline on every filing in tests/fixtures/eval_recent/ and print
per-file segmentation results plus a cross-file summary. READ-ONLY: imports and
calls the existing pipeline only; modifies nothing, writes no files (stdout
only); no network (operates on already-downloaded local fixtures)."""
import gzip
import sys
import traceback
from pathlib import Path
from collections import Counter

from sec10k.pipeline import run_pipeline
from sec10k.metadata import extract_fiscal_year_end

load_ruleset = None
for _mod in ("sec10k.ruleset.loader", "sec10k.loader", "sec10k.ruleset"):
    try:
        _m = __import__(_mod, fromlist=["load_ruleset"])
        load_ruleset = getattr(_m, "load_ruleset")
        break
    except Exception:
        continue

EVAL_DIR = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("tests/fixtures/eval_recent")

def es(x):
    return getattr(x, "name", None) or str(x)

def span_str(cs):
    if cs is None:
        return "None"
    try:
        return f"[{cs.start},{cs.end}) len={cs.end - cs.start}"
    except Exception:
        return repr(cs)

def era_label(fye):
    if load_ruleset is None:
        return "?"
    try:
        rs = load_ruleset(fiscal_year_end=fye)
    except Exception:
        return "?"
    exp = list(getattr(rs, "expected_items", []) or [])
    res = set(getattr(rs, "reserved_items", set()) or set())
    if "1C" in exp:
        return "era_2023"
    if "6" in res:
        return "era_2020"
    if "1A" in exp:
        return "era_2005"
    return "era_1994"

def run_one(path, summary):
    print("=" * 78)
    print(path.name)
    print("=" * 78)
    raw = gzip.decompress(path.read_bytes()) if path.suffix == ".gz" else path.read_bytes()
    print(f"raw bytes: {len(raw)}")
    fye = extract_fiscal_year_end(raw)
    label = era_label(fye)
    print(f"extracted FYE: {fye}   derived-era(label, heuristic): {label}")

    ruler, result = run_pipeline(raw)
    vr = result.verification_report
    passed = sum(1 for v in vr.invariant_results.values() if v)
    total_inv = len(vr.invariant_results)
    items = result.items
    geo = sum(1 for it in items if getattr(it, "is_geometric", False))

    print(f"filing_status={es(result.filing_status)}  confidence={es(result.filing_confidence)}"
          f"  invariants={passed}/{total_inv}  violations={len(vr.violations)}")
    print("invariant_results:")
    for k, v in vr.invariant_results.items():
        print(f"    {'PASS' if v else 'FAIL'}  {k}")
    for viol in vr.violations:
        print(f"    VIOLATION: {viol!s}")
    print(f"items: total={len(items)}  geometric={geo}")
    print(f"item_ids: {[it.item_id for it in items]}")
    print(f"{'id':<6}{'status':<27}{'part':<6}{'conf':<7}{'merged':<8}span")
    print("-" * 78)
    for it in items:
        print(f"{it.item_id:<6}{es(it.status):<27}{str(it.part or '-'):<6}"
              f"{es(it.confidence):<7}{str(it.merged_into or '-'):<8}{span_str(it.char_span)}")
    rc = Counter(es(r.classification) for r in result.residual)
    print(f"residual: total={len(result.residual)} classes={dict(rc)}\n")

    flag = "" if (es(result.filing_status) == "PASS" and passed == total_inv) else "  <-- REVIEW"
    summary.append((path.name, str(fye), label, len(items), geo,
                    es(result.filing_status), f"{passed}/{total_inv}", len(vr.violations), flag))

def main():
    print("PYTHON:", sys.version.split()[0])
    print("EVAL_DIR:", EVAL_DIR.resolve(), "\n")
    files = sorted(EVAL_DIR.glob("*.htm.gz")) + sorted(EVAL_DIR.glob("*.txt.gz"))
    if not files:
        print("No fixtures in tests/fixtures/eval_recent/. Run fetch_eval_set.py first.")
        return
    summary = []
    for path in files:
        try:
            run_one(path, summary)
        except Exception:
            print(f"  !! ERROR while processing {path.name}:")
            traceback.print_exc()
            print()
            summary.append((path.name, "ERR", "ERR", "-", "-", "RUN_ERROR", "-", "-", "  <-- ERROR"))
    print("#" * 90)
    print("CROSS-FILE SUMMARY")
    print("#" * 90)
    print(f"{'file':<34}{'FYE':<12}{'era':<10}{'items':<6}{'geo':<5}{'status':<9}{'inv':<6}{'viol':<5}")
    print("-" * 90)
    for fn, fye, era, n, geo, st, inv, viol, flag in summary:
        print(f"{fn:<34}{fye:<12}{era:<10}{str(n):<6}{str(geo):<5}{st:<9}{inv:<6}{str(viol):<5}{flag}")
    print("\n(REVIEW/ERROR rows = 'loud' signals to inspect. PASS + full invariants does NOT "
          "prove correctness — silent mis-segmentation still needs manual spot-check.)")

if __name__ == "__main__":
    main()
