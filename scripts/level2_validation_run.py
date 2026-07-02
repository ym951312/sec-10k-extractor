"""Level-2 validation run (READ-ONLY). Runs run_pipeline on the three
ground-truth real filings and prints the segmentation result for
comparison against ground truth. This script ONLY imports and calls the
pipeline; it modifies nothing and writes no files (stdout only)."""
import gzip
import sys
import traceback
from pathlib import Path
from collections import Counter

from sec10k.pipeline import run_pipeline
from sec10k.metadata import extract_fiscal_year_end

# load_ruleset location not 100% known -> import defensively (optional evidence)
load_ruleset = None
for _mod in ("sec10k.ruleset.loader", "sec10k.loader", "sec10k.ruleset"):
    try:
        _m = __import__(_mod, fromlist=["load_ruleset"])
        load_ruleset = getattr(_m, "load_ruleset")
        break
    except Exception:
        continue

FILES = [
    ("MSFT FY1994 (expect era_1994)", "tests/fixtures/real/msft_10k_fy1994_ascii.txt.gz"),
    ("MSFT FY2023 (expect era_2020)", "tests/fixtures/real/msft_10k_fy2023.htm.gz"),
    ("APA  FY2023 (expect era_2023)", "tests/fixtures/real/apa_10k_fy2023_merged12.htm.gz"),
]

def es(x):
    return getattr(x, "name", None) or str(x)

def span_str(cs):
    if cs is None:
        return "None"
    try:
        return f"[{cs.start},{cs.end}) len={cs.end - cs.start}"
    except Exception:
        return repr(cs)

def dump_ruleset(fye):
    if load_ruleset is None:
        print("  (load_ruleset import failed - skipping explicit ruleset dump)")
        return
    try:
        rs = load_ruleset(fiscal_year_end=fye)
    except Exception as e:
        print(f"  (load_ruleset raised: {e!r})")
        return
    print(f"  picked ruleset type: {type(rs).__name__}")
    print(f"  ruleset.expected_items: {getattr(rs, 'expected_items', 'N/A')}")
    print(f"  ruleset.reserved_items: {getattr(rs, 'reserved_items', 'N/A')}")

def run_one(label, path):
    print("=" * 74)
    print(label)
    print(path)
    print("=" * 74)
    p = Path(path)
    if not p.exists():
        print(f"  !! FILE NOT FOUND: {path}\n")
        return
    raw = gzip.decompress(p.read_bytes()) if p.suffix == ".gz" else p.read_bytes()
    print(f"raw bytes: {len(raw)}")

    fye = extract_fiscal_year_end(raw)
    print(f"extracted FYE: {fye}")
    dump_ruleset(fye)

    ruler, result = run_pipeline(raw)

    print(f"filing_status    : {es(result.filing_status)}")
    print(f"filing_confidence: {es(result.filing_confidence)}")

    vr = result.verification_report
    print("invariant_results:")
    for k, v in vr.invariant_results.items():
        print(f"    {'PASS' if v else 'FAIL'}  {k}")
    print(f"violations: {len(vr.violations)}")
    for viol in vr.violations:
        print(f"    - {viol!s}")

    items = result.items
    geo = sum(1 for it in items if getattr(it, "is_geometric", False))
    print(f"items: total={len(items)}  geometric={geo}")
    print(f"item_ids in order: {[it.item_id for it in items]}")
    print(f"{'id':<7}{'status':<27}{'part':<6}{'conf':<7}{'merged_into':<13}span  | reason_codes")
    print("-" * 74)
    for it in items:
        rcs = ",".join(es(r) for r in it.reason_codes) if it.reason_codes else "-"
        print(f"{it.item_id:<7}{es(it.status):<27}{str(it.part or '-'):<6}{es(it.confidence):<7}{str(it.merged_into or '-'):<13}{span_str(it.char_span)}  | {rcs}")

    res = result.residual
    rc = Counter(es(r.classification) for r in res)
    print(f"residual spans: total={len(res)}  classes={dict(rc)}\n")

def main():
    print("PYTHON:", sys.version.split()[0])
    print("CWD   :", Path.cwd(), "\n")
    for label, path in FILES:
        try:
            run_one(label, path)
        except Exception:
            print(f"  !! ERROR while processing {path}:")
            traceback.print_exc()
            print()

if __name__ == "__main__":
    main()
