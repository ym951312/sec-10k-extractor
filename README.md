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

## AI 協助環節

本專案全程以 AI 輔助開發，分工與原則如下：

- **分析與規格（Claude，對話）**：問題分解、設計決策、era ruleset 與不變量的規格、以及分析報告的撰寫，透過與 Claude 的策略對話完成。
- **檔案操作與增量開發（Claude Code，VS Code 擴充）**：所有實際的檔案讀寫、測試執行與唯讀查證由 Claude Code 執行；每次只做一件小事、先唯讀查證再改動、改動前印出 staged diff 供人工核對。
- **協作原則**：人工主導、逐決策點核可；修改 pipeline 一律測試先行（先寫會抓到現況錯誤的紅燈測試、確認紅、再改 code、確認轉綠且全套零回歸）；嚴格區分「實跑得到的事實」與「尚未驗證的假設」。

主要 prompt 紀錄（含與 Claude 的策略對話整理版）見 `prompts/`。

## 線上 Demo 與前端

- **線上 demo（零金鑰，可直接於瀏覽器操作）**：https://sec-10k-extractor-pvu3iqphchcmmzpwezq6wq.streamlit.app 。支援 7 份策劃 fixture 下拉選擇，或上傳任意 filing（`.htm` / `.txt` / `.gz`）；即時執行 pipeline，顯示 `filing_status`、`filing_confidence`、invariants N/9、item 數，並以 Items、Invariants（PASS/FAIL）、Violations、Raw JSON 四個分頁呈現結果。
- **本機執行前端（零金鑰、零網路）**：於專案根目錄先執行 `pip install -r requirements.txt`，再執行 `streamlit run streamlit_app.py`。pipeline 吃未壓縮 bytes；壓縮的 `.gz` fixture 由前端自動以 gzip magic bytes 嗅探解壓。
