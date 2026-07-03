"""Streamlit demo UI for the sec10k 10-K item-level segmentation pipeline.

Zero-secret, zero-network: this UI only runs the deterministic Stage 1 -> Stage 3
pipeline on filing bytes and renders the result. No API key, ever.

Honesty framing (surfaced in the UI): this is SEGMENTATION, not a compliance
judgment. Confidence is an evidence score, not an accuracy rate. All invariants
passing does NOT prove the segmentation is correct -- structural integrity and
semantic correctness are different guarantees.

The app self-bootstraps src/ onto sys.path so it imports the package directly
from source (src-layout, no editable install needed) -- works both locally and
on Streamlit Community Cloud where the repo is checked out as-is.
"""

from __future__ import annotations

import gzip
import sys
from pathlib import Path

# --- import bootstrap: put the repo's src/ on sys.path -----------------------
_REPO_ROOT = Path(__file__).resolve().parent
_SRC = _REPO_ROOT / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

import streamlit as st

from sec10k.pipeline import run_pipeline

# --- curated demo fixtures ---------------------------------------------------
# Each entry: (label, path relative to repo root, evidence-tier note).
# Notes describe DOCUMENTED characteristics + evidence tier; they do NOT assert
# the live PASS/FAIL result -- the live panels below are the source of truth.
# "Success is only corroborated, never proven."
FIXTURES = [
    (
        "MSFT FY1994 (ASCII, oldest era)",
        "tests/fixtures/real/msft_10k_fy1994_ascii.txt.gz",
        "Oldest ASCII-era filing; era auto-selected to ERA_1994. Has hand-built "
        "ground truth in the test suite. SILENT FAILURE (documented): Item 14's "
        "part/status disagree with the hand-built ground truth -- a semantic "
        "error the structural invariants do not catch. 'All green != correct.'",
    ),
    (
        "MSFT FY2023 (HTML/XBRL, modern)",
        "tests/fixtures/real/msft_10k_fy2023.htm.gz",
        "Modern HTML/XBRL filing. Has hand-built ground truth in the test suite.",
    ),
    (
        "APA FY2023 (Items 1 & 2 merged)",
        "tests/fixtures/real/apa_10k_fy2023_merged12.htm.gz",
        "Modern filing where Items 1 and 2 are merged. Has hand-built ground "
        "truth in the test suite.",
    ),
    (
        "NVDA FY2025 (recent tech)",
        "tests/fixtures/eval_recent_r2/nvda_10k_20260125.htm.gz",
        "Recent technology 10-K. Level-2 breadth extension: NO ground truth "
        "(validated only by invariants + spot-checks). See the live panels below.",
    ),
    (
        "INTC FY2025 (documented loud FAILED)",
        "tests/fixtures/eval_recent_r2/intc_10k_20251227.htm.gz",
        "LOUD FAILED (documented): the body has no per-section 'Item N' headings; "
        "invariant 9 (cover_dominance) flips it from silent to loud. Level-2 "
        "breadth extension: NO ground truth.",
    ),
    (
        "Citigroup FY2025 (documented loud FAILED)",
        "tests/fixtures/eval_recent_r2/c_10k_20251231.htm.gz",
        "Extreme LOUD FAILED (documented): no per-section 'Item N' anywhere and a "
        "bare-numbered index (no 'Item' prefix), so find_anchors = 0. Level-2 "
        "breadth extension: NO ground truth.",
    ),
    (
        "KKR FY2025 (documented loud FAILED)",
        "tests/fixtures/eval_recent_r2/kkr_10k_20251231.htm.gz",
        "LOUD FAILED (documented): a citation-style false anchor ('Item 10.') "
        "hijacks the greedy-monotonic walk. Level-2 breadth extension: NO ground "
        "truth.",
    ),
]

UPLOAD_LABEL = "Upload your own filing (.htm / .txt / .gz)"


def _maybe_decompress(data: bytes) -> bytes:
    """Return decompressed bytes if `data` is gzip (magic 1f 8b), else as-is.

    The pipeline expects UNCOMPRESSED bytes; the repo's real fixtures are stored
    gzip-compressed, and uploaded files may be either.
    """
    if len(data) >= 2 and data[0] == 0x1F and data[1] == 0x8B:
        return gzip.decompress(data)
    return data


@st.cache_data(show_spinner=False)
def _analyze(raw: bytes):
    """Run the deterministic pipeline on (possibly gzipped) bytes. Cached by
    content so Streamlit's per-interaction reruns do not recompute."""
    decompressed = _maybe_decompress(raw)
    return run_pipeline(decompressed)


# --- page --------------------------------------------------------------------
st.set_page_config(page_title="sec10k -- 10-K segmentation", layout="wide")

st.title("sec10k -- SEC 10-K item-level segmentation")
st.caption(
    "Deterministic Stage 1 -> Stage 3 pipeline. Zero API key, zero network. "
    "All results below are computed live on this page, not pre-stored."
)

st.info(
    "How to read this demo. This is SEGMENTATION, not a compliance judgment "
    "about any company. The confidence is an evidence score, not an accuracy "
    "rate. All invariants passing does NOT prove the segmentation is correct -- "
    "structural integrity and semantic correctness are different guarantees. "
    "Filings marked 'breadth extension' have NO ground truth; a clean pass "
    "there is corroborated, not proven."
)

# --- source picker -----------------------------------------------------------
labels = [f[0] for f in FIXTURES] + [UPLOAD_LABEL]
choice = st.selectbox("Choose a filing", labels, index=0)

raw: bytes | None = None
note: str | None = None

if choice == UPLOAD_LABEL:
    up = st.file_uploader(
        "Upload a 10-K (.htm/.html, .txt, or .gz). Processed locally; nothing is "
        "sent anywhere.",
        type=["htm", "html", "txt", "gz"],
    )
    if up is not None:
        raw = up.read()
else:
    idx = labels.index(choice)
    _, rel_path, note = FIXTURES[idx]
    fpath = _REPO_ROOT / rel_path
    if fpath.is_file():
        raw = fpath.read_bytes()
    else:
        st.error("Fixture not found: " + rel_path)

if note:
    st.caption(note)

if raw is None:
    st.stop()

# --- run (loud on failure) ---------------------------------------------------
try:
    ruler, result = _analyze(raw)
except Exception as exc:
    st.error(
        "The pipeline raised an exception on this input:\n\n"
        + type(exc).__name__ + ": " + str(exc)
    )
    st.stop()

vr = result.verification_report

# --- headline ----------------------------------------------------------------
c1, c2, c3, c4 = st.columns(4)
c1.metric("Filing status", result.filing_status.value)
c2.metric("Filing confidence", result.filing_confidence.value)
n_pass = sum(1 for v in vr.invariant_results.values() if v)
n_total = len(vr.invariant_results)
c3.metric("Invariants", str(n_pass) + "/" + str(n_total) + " pass")
c4.metric("Items detected", str(len(result.items)))

st.divider()

tab_items, tab_inv, tab_viol, tab_json = st.tabs(
    ["Items", "Invariants", "Violations", "Raw JSON"]
)

with tab_items:
    rows = []
    for it in result.items:
        if it.char_span is not None:
            span = "[" + str(it.char_span.start) + ", " + str(it.char_span.end) + ")"
        else:
            span = "-"
        rows.append(
            {
                "Item": it.item_id,
                "Status": it.status.value,
                "Confidence": it.confidence.value,
                "Char span": span,
                "Merged into": it.merged_into or "-",
            }
        )
    if rows:
        st.dataframe(rows, use_container_width=True, hide_index=True)
    else:
        st.write("No items detected for this filing.")

    span_items = [it for it in result.items if it.char_span is not None]
    if span_items:
        st.markdown("**Inspect an item's extracted text**")
        pick = st.selectbox(
            "Item to view", [it.item_id for it in span_items], key="item_text_pick"
        )
        chosen = next(it for it in span_items if it.item_id == pick)
        text = ruler.text[chosen.char_span.start : chosen.char_span.end]
        st.caption(
            "Item " + chosen.item_id + " -- " + str(len(text)) + " chars ["
            + str(chosen.char_span.start) + ", " + str(chosen.char_span.end) + ")"
        )
        with st.container(height=400):
            st.text(text)

with tab_inv:
    inv_rows = [
        {"Invariant": name, "Result": "PASS" if passed else "FAIL"}
        for name, passed in vr.invariant_results.items()
    ]
    st.dataframe(inv_rows, use_container_width=True, hide_index=True)

with tab_viol:
    if vr.violations:
        st.write(str(len(vr.violations)) + " violation(s):")
        for v in vr.violations:
            st.markdown(
                "- **[" + v.severity.value + "]** `" + v.code.value + "` -- " + v.message
            )
    else:
        st.success("No violations.")

with tab_json:
    st.caption("Full FilingResult (result.model_dump_json).")
    st.code(result.model_dump_json(indent=2), language="json")
