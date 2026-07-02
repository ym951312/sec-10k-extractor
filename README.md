# sec10k — SEC 10-K item-level segmentation

> **評測零金鑰、零祕密。** 核心管線(Stage 1–3)是純確定性 Python,**不需要任何 API key、不需要任何外部服務**即可執行與評測。Stage 4 的 LLM 輔助是**可選、預設關閉、BYO-key**,本里程碑不包含它。**任何金鑰都不會、也不應寫進這個 repo。**

## 這是什麼

把一份雜亂的 raw 10-K 可靠**分段**成各個 item(`Item 1`、`Item 1A`、…),讓每個 item 能被獨立取用;在**無 ground truth** 下用不變量自我驗證;並**誠實回報**信心與失敗。任務是 **segmentation**,**不是**判斷公司是否違規。

完整設計見 [`docs/DESIGN.md`](docs/DESIGN.md);建置/成本見 [`docs/BUILD_OPS.md`](docs/BUILD_OPS.md)。

## 本里程碑範圍:地基兩塊

1. **Stage 1 — 認證完整的尺**:raw bytes → 正規化文本(座標系)+ provenance(回指原始位元組)+ **完整性檢查(正規化不可掉字)** + 剝除每頁重複頁首頁尾(記入 ledger)+ 隔離封面頁/目錄為候選 residual。
2. **Stage 3 — 不變量閘門**:`docs/DESIGN.md` §5 的八項不變量,確定性驗證器。

Stage 2(切割)/4(LLM)刻意尚未實作;Stage 3 以**合成 span fixtures** 驗證閘門邏輯本身。

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

This pipeline's segmentation correctness was validated at two levels of strength: strong verification against 3 filings with hand-built ground truth (MSFT FY1994, MSFT FY2023, APA FY2023), and a breadth extension over 11 deliberately-diverse recent filings (no ground truth; validated via 8 structural invariants plus manual head-and-tail spot-checks). Of the 11 recent filings, 8 pass cleanly (8/8 invariants) and all 8 were manually spot-checked with no content-misplacement found. Two defect classes were located and fixed under a test-first workflow — a loud table-of-contents boundary failure (JPM/NKE/PG) and a silent era-blind `part` mis-assignment (MSFT FY1994 Item 14) — after which 125 tests pass with no regressions. The 3 remaining FAILED filings are loudly flagged (not hidden); "all tests green" is treated as a floor, not proof of correctness. Level-3/4 sampling and the performance/cost/scalability analysis are noted as future work.

完整報告（繁體中文，含英文摘要）詳見 `docs/VALIDATION_part_1.md`。
