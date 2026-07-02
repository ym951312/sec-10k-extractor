"""READ-ONLY. Dump the current per-item `part` for every eval fixture plus the
MSFT FY1994 ground-truth fixture, to serve as a regression baseline before the
part-assignment fix. Prints a compact, copy-pasteable mapping per file.
Imports/inspects only; writes only stdout; no file edits."""
import gzip
from pathlib import Path

from sec10k.pipeline import run_pipeline

EVAL = Path("tests/fixtures/eval_recent")
REAL = Path("tests/fixtures/real")

# all 11 recent eval fixtures
EVAL_FILES = [
    "aapl_10k_20230930.htm.gz",
    "nke_10k_20230531.htm.gz",
    "pg_10k_20230630.htm.gz",
    "jpm_10k_20251231.htm.gz",
    "brkb_10k_20251231.htm.gz",
    "pfe_10k_20251231.htm.gz",
    "tsla_10k_20251231.htm.gz",
    "wmt_10k_20260131.htm.gz",
    "dvn_10k_20251231.htm.gz",
    "pld_10k_20251231.htm.gz",
    "nee_10k_20251231.htm.gz",
]
# MSFT FY1994 ground-truth fixture (the defect case: Item 14 should be IV)
REAL_FILE = "msft_10k_fy1994_ascii.txt.gz"

def load(p: Path):
    b = p.read_bytes()
    return gzip.decompress(b) if p.suffix == ".gz" else b

def es(x):
    return getattr(x, "name", None) or str(x)

def dump(dirpath: Path, name: str):
    p = dirpath / name
    if not p.exists():
        print(f"{name}: !! FILE NOT FOUND at {p}")
        return
    _ruler, result = run_pipeline(load(p))
    # compact mapping: item_id -> part  (merged items show part too)
    pairs = [f"{it.item_id}:{(it.part if it.part is not None else '-')}"
             for it in result.items]
    print(f"{name}")
    print(f"    status={es(result.filing_status)}  items={len(result.items)}")
    print(f"    parts= {', '.join(pairs)}")

def main():
    print("=" * 78)
    print("PART BASELINE — 11 recent eval fixtures")
    print("=" * 78)
    for name in EVAL_FILES:
        dump(EVAL, name)
    print()
    print("=" * 78)
    print("PART BASELINE — MSFT FY1994 ground-truth (defect case)")
    print("=" * 78)
    dump(REAL, REAL_FILE)
    print()
    print("NOTE: If msft_10k_fy1994 is not found under tests/fixtures/real/, run:")
    print("      ls tests/fixtures/real/   and paste the output so the path can be fixed.")

if __name__ == "__main__":
    main()
