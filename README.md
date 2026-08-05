# sec10k — SEC 10-K item-level segmentation

> **評測零金鑰、零祕密。** 核心管線(Stage 1–3)是純確定性 Python,**不需要任何 API key、不需要任何外部服務**即可執行與評測。Stage 4 的 LLM 輔助是**可選、預設關閉、BYO-key**,本里程碑不包含它。**任何金鑰都不會、也不應寫進這個 repo。**

## 這是什麼

把一份雜亂的 raw 10-K 可靠**分段**成各個 item(`Item 1`、`Item 1A`、…),讓每個 item 能被獨立取用;在**無 ground truth** 下用不變量自我驗證;並**誠實回報**信心與失敗。任務是 **segmentation**,**不是**判斷公司是否違規。

完整設計見 [`docs/DESIGN.md`](docs/DESIGN.md);建置/成本見 [`docs/BUILD_OPS.md`](docs/BUILD_OPS.md)。

## 本里程碑範圍:地基兩塊

1. **Stage 1 — 認證完整的尺**:raw bytes → 正規化文本(座標系)+ provenance(回指原始位元組)+ **完整性檢查(正規化不可掉字)** + 剝除每頁重複頁首頁尾(記入 ledger)+ 隔離封面頁/目錄為候選 residual。
2. **Stage 3 — 不變量閘門**:`docs/DESIGN.md` §5 的九項不變量,確定性驗證器。

Stage 2（切割）**已實作**（anchors → disambiguation → structure → spans,見 `src/sec10k/segment/`),並由 162 個測試涵蓋;Stage 4（LLM)依設計為可選、預設關閉、自帶金鑰,交件版本不啟用;Stage 3 以合成 span fixtures 驗證閘門邏輯本身。

## 安裝與執行(零金鑰)

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -e .            # 只裝 pydantic
sec10k tests/fixtures/synthetic/<sample>.txt   # 跑 Stage1 → Stage3 印報告
```

測試:

```bash
pip install -e '.[dev]'
pytest
```

## 硬規則(摘自 CLAUDE.md / DESIGN)

- 切割錨點 = **item 編號 + 順序**,不是標題字串。
- 尺必須**認證完整**;刻意剝除須記錄;item 與 residual **都正面辨識**,不可互為補集。
- `reserved` 與 `incorporated_by_reference` = 正確地空 = **PASS**。
- `confidence` 是證據分數,非正確率;未校準前以 high/med/low 三檔處理。

## Validation / 正確性驗證

This pipeline's segmentation correctness was validated at two levels of strength: strong verification against 3 filings with hand-built ground truth (MSFT FY1994, MSFT FY2023, APA FY2023), and a breadth extension over 21 deliberately-diverse recent filings, added across two rounds (11 + 10), with no ground truth — validated via the structural invariants (count listed above) plus manual head-and-tail spot-checks. Clean passes on the breadth set are corroborated, not proven; filings that fail the invariant gate are loudly flagged, not hidden. Two defect classes were located and fixed under a test-first workflow — a loud table-of-contents boundary failure (JPM/NKE/PG) and a silent era-blind `part` mis-assignment (MSFT FY1994 Item 14) — after which 162 tests pass with no regressions. "All tests green" is treated as a floor, not proof of correctness. Level-3/4 sampling and the performance/cost/scalability analysis are noted as future work.

完整報告（繁體中文，含英文摘要）詳見 `docs/VALIDATION_part_1.md`。

## 下游用途：一個後來才出現的方向（探索中，尚未實作）

這個專案原本的範圍到分段為止——把 raw 10-K 切成 item，在無 ground truth 下自我驗證，誠實回報信心與失敗。在後續討論中浮現一個原本不在規劃內的問題：切好的 section 本身，能不能成為量化研究的原料？

這個問題有具體的文獻對應。學界有一條研究線的原料正是 per-section 的 10-K 文本，其中最知名的是 Cohen, Malloy & Nguyen 的 *Lazy Prices*：比較同一家公司今年與去年的申報文字，改動幅度較大的公司，後續股價表現較差。該研究全程不需 LLM——方法是文本相似度與字典計數——與本專案「零金鑰、零網路、確定性」的核心屬同一血統。

想嘗試的方向，是把目前「一份 filing 進、一份分段結果出」的 pipeline，延伸成跨公司、跨年度的 **feature panel**：每份申報產出一筆結構化紀錄（各 item 的有無、長度、conditional 旗標、confidence、reason codes），並在同公司、同 item 上做逐年比對。其中一個看起來還沒被涵蓋的角度是**結構異常本身**——以 regex 解析的研究通常會丟棄格式異常的申報檔，而那正是本 pipeline 當一等公民處理、並會主動標紅的那一類。它是否帶有訊息，是待檢驗的假設，不是結論。

**現況必須講清楚：目前只有分析，沒有任何實作，是否執行尚未決定。** 本 repo 不含任何回測、訊號或報酬資料；三條鐵律不因此變動。

分析紀錄（含已查證的文獻事實、被否決的候選方向、以及尚未回答的統計前提）見 [`docs/reports/2026-08-05_notes_downstream-quant-use.md`](docs/reports/2026-08-05_notes_downstream-quant-use.md)。

> Cohen, L., Malloy, C., & Nguyen, Q. (2020). Lazy Prices. *The Journal of Finance*, 75(3), 1371–1415. https://doi.org/10.1111/jofi.12885

## AI 協助環節

本專案全程以 AI 輔助開發，分工與原則如下：

- **分析與規格（Claude，對話）**：問題分解、設計決策、era ruleset 與不變量的規格、以及分析報告的撰寫，透過與 Claude 的策略對話完成。
- **檔案操作與增量開發（Claude Code，VS Code 擴充）**：所有實際的檔案讀寫、測試執行與唯讀查證由 Claude Code 執行；每次只做一件小事、先唯讀查證再改動、改動前印出 staged diff 供人工核對。
- **協作原則**：人工主導、逐決策點核可；修改 pipeline 一律測試先行（先寫會抓到現況錯誤的紅燈測試、確認紅、再改 code、確認轉綠且全套零回歸）；嚴格區分「實跑得到的事實」與「尚未驗證的假設」。

主要 prompt 紀錄（含與 Claude 的策略對話整理版）見 `prompts/`。

## 線上 Demo 與前端

- **線上 demo（零金鑰，可直接於瀏覽器操作）**：https://sec-10k-extractor-pvu3iqphchcmmzpwezq6wq.streamlit.app 。支援 7 份策劃 fixture 下拉選擇，或上傳任意 filing（`.htm` / `.txt` / `.gz`）；即時執行 pipeline，顯示 `filing_status`、`filing_confidence`、invariants N/9、item 數，並以 Items、Invariants（PASS/FAIL）、Violations、Raw JSON 四個分頁呈現結果。
- **本機執行前端（零金鑰、零網路）**：於專案根目錄先執行 `pip install -r requirements.txt`，再執行 `streamlit run streamlit_app.py`。pipeline 吃未壓縮 bytes；壓縮的 `.gz` fixture 由前端自動以 gzip magic bytes 嗅探解壓。
