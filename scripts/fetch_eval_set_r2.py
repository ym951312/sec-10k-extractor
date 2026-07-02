"""Fetch the ROUND-2 expanded eval set (tech + finance, 10 recent 10-K filings)
from SEC EDGAR into tests/fixtures/eval_recent_r2/. Same fetch logic as
scripts/fetch_eval_set.py (round 1); only the COMPANIES list and OUT_DIR differ.
It only downloads PUBLIC filings, imports nothing from sec10k, and modifies no
existing files. EDGAR needs no API key (zero-secrets)."""
import gzip
import json
import re
import sys
import time
import urllib.request
from pathlib import Path

# SEC requires a descriptive User-Agent with contact info. Same UA as round 1.
UA = "sec-10k-extractor eval-set (contact: research@example.com)"
HEADERS = {"User-Agent": UA}
OUT_DIR = Path("tests/fixtures/eval_recent_r2")
SLEEP = 0.4  # be polite; SEC caps ~10 req/sec

# (ticker, target_report_year | None=latest, cik_override | None, why-chosen)
# NOTE: every "expect era_XXXX" / FYE note below is an UNVERIFIED expectation used
# only as picking rationale; the real era/FYE is decided by the actual fetch +
# pipeline run, not asserted here. AVGO/KKR CIKs ARE verified (primary source).
COMPANIES = [
    # --- Tech (5) ---
    ("NVDA",  None, None,    "tech/GPU; late-Jan FYE (expect era_2023) [FYE unverified]"),
    ("GOOGL", None, None,    "tech; Dec FYE, dual-class (expect era_2023) [unverified]"),
    ("AMD",   None, None,    "tech/semi; Dec FYE (expect era_2023) [unverified]"),
    ("INTC",  None, None,    "tech/semi; Dec FYE (expect era_2023) [unverified]"),
    ("AVGO",  None, 1730168, "tech/semi; ~Oct-end non-cal FYE; ex-Singapore entity. "
                             "CIK 1730168 (Broadcom Inc.) verified from primary source."),
    # --- Finance (5) ---
    ("BAC",   None, None,    "bank; Dec FYE, Part III IBR (expect era_2023) [unverified]"),
    ("C",     None, None,    "bank; Dec FYE, possible multi-registrant (expect era_2023) [unverified]"),
    ("BLK",   None, None,    "asset manager; Dec FYE (expect era_2023) [unverified]"),
    ("APO",   None, None,    "alt asset mgr; Dec FYE; restructured 2022 - watch printed name [unverified]"),
    ("KKR",   None, 1404912, "alt asset mgr; Dec FYE. CIK 1404912 (KKR & Co. Inc.) "
                             "locked to avoid CIK 1957845 (KKR PE Conglomerate). Verified."),
]

def http_get(url):
    req = urllib.request.Request(url, headers=HEADERS)
    with urllib.request.urlopen(req, timeout=60) as r:
        data = r.read()
    if data[:2] == b"\x1f\x8b":          # handle gzip transfer encoding
        data = gzip.decompress(data)
    return data

def norm(t):
    return re.sub(r"[^A-Z0-9]", "", t.upper())

def load_ticker_map():
    obj = json.loads(http_get("https://www.sec.gov/files/company_tickers.json"))
    m = {}
    for _, row in obj.items():
        tk = str(row["ticker"]).upper()
        cik = int(row["cik_str"])
        m[tk] = cik
        m.setdefault(norm(tk), cik)
    return m

def resolve_cik(ticker, override, tmap):
    if override is not None:
        return int(override)
    return tmap.get(ticker.upper()) or tmap.get(norm(ticker))

def pick_10k(cik, target_year):
    sub = json.loads(http_get(f"https://data.sec.gov/submissions/CIK{cik:010d}.json"))
    name = sub.get("name", "?")
    rec = sub["filings"]["recent"]
    rows = []
    for i, form in enumerate(rec["form"]):
        if form != "10-K":               # exact: exclude 10-K/A etc.
            continue
        rows.append((rec["reportDate"][i], rec["filingDate"][i],
                     rec["accessionNumber"][i], rec["primaryDocument"][i]))
    if target_year:
        rows = [r for r in rows if (r[0] or "").startswith(target_year)]
    if not rows:
        return name, None
    rows.sort(key=lambda r: (r[0] or "", r[1] or ""), reverse=True)  # newest
    return name, rows[0]

def main():
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    print("Fetching ticker->CIK map from SEC ...")
    try:
        tmap = load_ticker_map()
    except Exception as e:
        print(f"FATAL: could not load company_tickers.json: {e!r}")
        sys.exit(1)
    print(f"ticker map entries: {len(tmap)}\n")
    ok = fail = 0
    for ticker, target_year, override, why in COMPANIES:
        tag = f"[{ticker}]"
        print("-" * 70)
        print(f"{tag} {why}")
        try:
            cik = resolve_cik(ticker, override, tmap)
            if cik is None:
                print(f"{tag} ERROR: ticker not in company_tickers.json (SKIPPED)")
                fail += 1
                continue
            time.sleep(SLEEP)
            name, sel = pick_10k(cik, target_year)
            print(f"{tag} resolved CIK {cik} ({name})")
            if sel is None:
                print(f"{tag} ERROR: no 10-K for year={target_year or 'any'} (SKIPPED)")
                fail += 1
                continue
            report_date, filing_date, accession, primary_doc = sel
            url = (f"https://www.sec.gov/Archives/edgar/data/{cik}/"
                   f"{accession.replace('-', '')}/{primary_doc}")
            print(f"{tag} selected 10-K reportDate={report_date} filed={filing_date} "
                  f"accession={accession}")
            print(f"{tag} downloading {url}")
            time.sleep(SLEEP)
            raw = http_get(url)
            fn = f"{ticker.lower().replace('-', '')}_10k_{report_date.replace('-', '')}.htm.gz"
            path = OUT_DIR / fn
            path.write_bytes(gzip.compress(raw))
            print(f"{tag} saved {path}  (raw {len(raw)/1e6:.1f} MB -> gz "
                  f"{path.stat().st_size/1e6:.1f} MB)")
            ok += 1
        except Exception as e:
            print(f"{tag} ERROR: {e!r} (SKIPPED)")
            fail += 1
    print("=" * 70)
    print(f"DONE. downloaded={ok}  failed={fail}  -> {OUT_DIR}")

if __name__ == "__main__":
    main()
