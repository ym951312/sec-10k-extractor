"""Fetch a small, deliberately diverse set of recent 10-K filings from SEC
EDGAR for the eval sample. It only downloads PUBLIC filings and writes them
(gzipped) into tests/fixtures/eval_recent/. It imports nothing from sec10k and
modifies no existing files. EDGAR needs no API key (zero-secrets)."""
import gzip
import json
import re
import sys
import time
import urllib.request
from pathlib import Path

# SEC requires a descriptive User-Agent with contact info. You MAY replace the
# email below with your own; a generic one generally works for low volume.
UA = "sec-10k-extractor eval-set (contact: research@example.com)"
HEADERS = {"User-Agent": UA}
OUT_DIR = Path("tests/fixtures/eval_recent")
SLEEP = 0.4  # be polite; SEC caps ~10 req/sec

# (ticker, target_report_year | None=latest, cik_override | None, why-chosen)
COMPANIES = [
    ("AAPL", "2023", None, "tech, Sep FYE -> expect era_2020, clean baseline"),
    ("NKE",  "2023", None, "consumer, May FYE -> expect era_2020"),
    ("PG",   "2023", None, "consumer staples, Jun FYE -> expect era_2020"),
    ("JPM",  None,   None, "bank, Part III IBR-to-proxy -> expect era_2023"),
    ("BRK-B", None,  None, "plain-formatting stress test -> expect era_2023"),
    ("PFE",  None,   None, "pharma -> expect era_2023"),
    ("TSLA", None,   None, "auto/tech -> expect era_2023"),
    ("WMT",  None,   None, "retail, Jan FYE -> expect era_2023"),
    ("DVN",  None,   1090012, "oil&gas E&P, Items 1&2 merge -> expect era_2023"),
    ("PLD",  None,   1045609, "REIT, dual-registrant -> expect era_2023"),
    ("NEE",  None,   None, "utility -> expect era_2023"),
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
