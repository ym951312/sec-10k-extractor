"""READ-ONLY. Dump current (item_id, part) ordered sequence for the two
ground-truth fixtures (MSFT FY2023, APA FY2023) as a regression baseline before
the part-assignment fix. Imports/inspects only; writes only stdout."""
import gzip
from pathlib import Path

from sec10k.pipeline import run_pipeline

REAL = Path("tests/fixtures/real")
FILES = [
    "msft_10k_fy2023.htm.gz",
    "apa_10k_fy2023_merged12.htm.gz",
]

def load(p: Path):
    b = p.read_bytes()
    return gzip.decompress(b) if p.suffix == ".gz" else b

def es(x):
    return getattr(x, "name", None) or str(x)

def dump(name: str):
    p = REAL / name
    if not p.exists():
        print(f"{name}: !! FILE NOT FOUND at {p}")
        return
    _ruler, result = run_pipeline(load(p))
    seq = [(it.item_id, (it.part if it.part is not None else "-")) for it in result.items]
    print(f"{name}")
    print(f"    status={es(result.filing_status)}  items={len(result.items)}")
    print(f"    ordered_parts= {seq}")

def main():
    print("=" * 78)
    print("PART BASELINE — ground-truth fixtures (MSFT FY2023, APA FY2023)")
    print("=" * 78)
    for name in FILES:
        dump(name)

if __name__ == "__main__":
    main()
