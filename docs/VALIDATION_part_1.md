# SEC 10-K 逐項擷取 pipeline — 層級二驗證報告（Part 1）

> 本報告為多輪驗證的第一部分（Part 1）。後續（第二輪：金融/科技擴大抽樣）另見 Part 2。

---

## English Summary

This document reports the correctness validation of the SEC 10-K item-segmentation pipeline. Validation was conducted at two levels of evidential strength: (1) **strong verification** against 3 filings with hand-built, item-by-item ground truth (Microsoft FY1994, Microsoft FY2023, APA FY2023); and (2) a **breadth extension** over 11 deliberately-diverse recent filings with no ground truth, relying on 8 structural invariants (self-checks requiring no answer key) plus manual head-and-tail item spot-checks.

Of the 11 recent filings, **8 pass cleanly** (filing_status=PASS, 8/8 invariants) and **all 8 were manually spot-checked** with no content-misplacement failures found. Two classes of defect were located and fixed, all under a test-first workflow: (a) a **loud failure** — an imprecise table-of-contents boundary in Stage 1 that caused missing items across 4 filings (fixed for JPM, NKE, PG); and (b) a **silent failure** — Microsoft FY1994's Item 14 was assigned the wrong Part despite passing every invariant (an era-blind `part` assignment; now fixed and locked with a dedicated regression test). After the fixes, **125 tests pass** with no regressions across the eval set.

The report is explicit about the limits of what this establishes. The 3 remaining FAILED filings are **loudly flagged** by the pipeline (not hidden). The silent-failure case demonstrates that "all tests green" does not mean "correct," and its `status`-assignment half remains a **documented, unfixed limitation**. **Level-3 (saturation sampling across issuers) and Level-4 (Good-Turing residual estimation) were not performed** and are noted as future work. Performance, cost, and scalability analysis is deferred to a later overall review, after the Stage 6 front-end and the (default-off) Stage 4 LLM fallback are complete.

*(Detailed report follows in Traditional Chinese.)*

---

## 0. 摘要（TL;DR）

本報告記錄 SEC 10-K 逐項擷取 pipeline 的正確性驗證。驗證分兩種強度：(1) **3 份具備人工逐筆 ground truth 的申報檔**（MSFT FY1994、MSFT FY2023、APA FY2023）作強驗證；(2) **11 份刻意分散的近年真實申報檔**作層級二廣度延伸驗證（無 ground truth，靠 8 項結構不變量自我檢查 + head+tail 人工抽查）。

主要結果：11 份近年檔中 **8 份乾淨通過**（filing_status=PASS、8/8 不變量），且 **8 份 PASS 全數通過 head+tail 人工逐項抽查**，未發現任何內容錯位型的沉默失敗。驗證過程中定位並修復了**兩類缺陷**：一是橫跨 4 份申報檔的**大聲失敗**（Stage-1 目錄邊界精度，修復 JPM、NKE、PG）；二是一個**沉默失敗**——MSFT FY1994 的 Item 14 在通過全部不變量的情況下 part 判定錯誤（era-blind），已修復並加上專屬測試防線。全部修復均採測試先行，最終 **125 項測試通過**、11 家 eval 零退步。

本報告同時誠實記錄方法邊界：3 份 FAILED 檔為 pipeline **主動標紅**的已定位問題（非隱藏失敗）；上述沉默失敗案例用以說明「測試全綠不等於正確」，且其 status 判定部分仍為**未修的已知限制**。**層級三（跨公司飽和抽樣）與層級四（Good-Turing 殘差估計）未在本輪執行**，列為後續工作。效能、成本、擴充性分析待 Stage 6 前端與 Stage 4（LLM fallback）完成後於整體總覽提供。

---

## 1. 目的與範圍

本報告回答一個問題：在缺乏公開 ground truth 的前提下，如何驗證一套 10-K 逐項分段系統的正確性，並誠實界定「驗證了什麼、沒驗證什麼」。

### 1.1 驗證的兩種強度

本輪驗證涵蓋兩種強度不同的證據，報告全程明確區分，不混為一談：

- **強驗證（有 ground truth，3 份）**：MSFT FY1994、MSFT FY2023、APA FY2023，先前已逐筆人工核對出「正確分段應長什麼樣」（哪些 item 存在、各屬哪個 part、status 為 extracted/reserved/IBR/merged）。這 3 份能支持「分段正確」或「找出具體錯誤」的強結論。
- **層級二廣度延伸（無 ground truth，11 份近年檔）**：這些檔沒有逐筆答案卡，驗證依靠 (a) 8 項結構不變量的自我檢查，與 (b) 對通過檔的 head+tail 人工逐項抽查。這一層能支持「未見大聲失敗、且逐項頭尾未見內容錯位」的結論，**但不宣稱逐 item 全部正確**——因為沒有答案卡可比對。

（註：11 份廣度延伸檔與 3 份 ground truth 檔完全不重疊；合計為 14 份不同的真實申報檔。）

### 1.2 明確的範圍邊界

依專案既有的「可知性分層」，本輪定位如下：

- **結構/法規層**（某 era 應有哪些 item、編號、順序）——可證明封閉，直接由 SEC 規格決定，不需真實檔即可推定（例如 era_2005 的規則即純由 SEC 出處建立）。
- **呈現層**（真實檔實際如何排版、標題如何書寫、如何合併/省略）——近乎無限、無法枚舉、無法證明封閉，僅能透過抽樣估計。
- **本輪所在位置**：完成了 3 份強驗證 + 11 份廣度延伸驗證。**層級三（跨公司飽和抽樣至涵蓋率收斂）與層級四（Good-Turing 殘差估計）未執行**，列為後續工作。

因此，本報告的所有「通過」結論，應理解為「在這些特定申報檔上、以這些檢查未發現錯誤」，而非「系統對母體整體正確」的證明。

---

## 2. 驗證方法（分層）

本輪以多層、彼此獨立的方式驗證，各層能力不同、刻意不互相取代。

### 2.1 結構不變量（自我檢查，跨所有檔自動執行）

系統對每份檔計算 8 項純函式結構不變量，無需 ground truth 即可執行——這是「零祕密、可離線自我驗證」的核心：

- `order` — item 依 era 規則的順序遞增
- `no_overlap` — item 的 char_span 互不重疊
- `coverage` — item 與 residual 合計覆蓋全文、無未歸屬缺口
- `residual_sanity` — 無過大的 unclassified residual 區塊（大塊即紅旗）
- `legal_structure` — 偵測到的 merge 群組成員須在 expected_items 中相鄰（相鄰性判準）
- `should_exist` — era 規則要求存在的 item 均存在，或為合法的 reserved / incorporated-by-reference / optional
- `item8_xbrl`、`cross_method` — 與 Item 8 財報/XBRL 及跨方法一致性相關的檢查

> 註：`item8_xbrl` 與 `cross_method` 兩項，本輪未特別觸發、亦未取其原始碼，故此處僅描述其大致職責，未逐字驗證其實作；精確語意以 invariants 模組為準。其餘 6 項的行為在本輪驗證中均有直接觀察到（should_exist 舉旗缺件、coverage 舉旗 overlap、residual_sanity 舉旗大塊 unclassified、legal_structure 判定 merge、order/no_overlap 未誤觸）。

這些不變量能自動抓出一大類「大聲失敗」：順序錯亂、span 重疊、覆蓋缺口、該有的 item 沒抓到、過大的未分類殘留、非法合併。對任何新檔都能立即給出 filing_status（PASS / REVIEW / FAILED）與 confidence 分層，無需人工答案卡。

### 2.2 Ground truth 逐筆比對（強驗證，3 份）

對 MSFT FY1994、MSFT FY2023、APA FY2023，以人工逐筆核對的答案卡比對系統輸出。這是**唯一能抓「沉默失敗」的層**——即輸出通過全部不變量、卻與真實分段不符的情況。

### 2.3 head+tail 人工抽查（針對通過檔，補抓內容錯位）

對每份 PASS 檔，逐 item 印出 span 的開頭（約 90 字）、結尾（約 60 字）與長度，人工核對「每個 item 框到的內容是否真的屬於它、有無溢出到下一個 item」。此手法專門補抓「內容錯位型」沉默失敗（不變量抓不到這類）。本輪 8 份 PASS 檔全數以此抽查、全數通過。

### 2.4 回歸測試（證明「沒退步」，非證明「正確」）

修改 pipeline 時採測試先行：先寫會抓到錯誤的紅燈測試，改 code 後轉綠，並回跑全套與乾淨檔。回歸只證明「改動沒弄壞原本會過的東西」，不證明「原本會過的東西本來就對」。

### 2.5 關鍵區分：大聲失敗 vs 沉默失敗

全篇貫穿一個區分：**大聲失敗**是不變量抓得到、系統會主動標紅的錯誤；**沉默失敗**是通過全部不變量、卻仍不正確的錯誤。第 6 段的 MSFT FY1994 Item 14 即後者的具體案例（8/8 不變量全 PASS，卻與 ground truth 不符）。這條界線界定了本系統自我驗證能力的上限。

---

## 3. Evaluation set 設計

### 3.1 為何「刻意分散」而非隨機或窮舉

由於呈現層無法枚舉，本輪不追求數量，而是以少量、刻意分散的樣本盡量踩到不同的版面型態與法規情境。這 11 份是為「製造多樣性」而選，**因此明確不是母體的代表性/飽和抽樣**——這正是它屬於層級二廣度延伸、而非層級三的原因。資料來源為 SEC EDGAR（公開、免 API 金鑰，符合零祕密要求）；由 ticker 經 SEC 權威端點解析至 CIK 與目標年度的 10-K 主檔後下載。

### 3.2 分散軸與覆蓋（11 份近年檔）

| 公司 | ticker | 擷取 FYE | era | 覆蓋的分散軸 |
|---|---|---|---|---|
| Apple | AAPL | 2023-09-30 | era_2020 | 科技、9 月 FYE、乾淨 baseline |
| NIKE | NKE | 2023-05-31 | era_2020 | 消費、5 月 FYE |
| Procter & Gamble | PG | 2023-06-30 | era_2020 | 消費必需品、6 月 FYE、reserved 變體 |
| JPMorgan | JPM | 2025-12-31 | era_2023 | 銀行、Part III 大量 IBR-to-proxy |
| Berkshire Hathaway | BRK-B | 2025-12-31 | era_2023 | 排版樸素、壓力測試 |
| Pfizer | PFE | 2025-12-31 | era_2023 | 製藥 |
| Tesla | TSLA | 2025-12-31 | era_2023 | 汽車/科技 |
| Walmart | WMT | 2026-01-31 | era_2023 | 零售、1 月 FYE |
| Devon | DVN | 2025-12-31 | era_2023 | 油氣 E&P、Items 1&2 merge |
| Prologis | PLD | 2025-12-31 | era_2023 | REIT、雙註冊人合併申報 |
| NextEra | NEE | 2025-12-31 | era_2023 | 公用事業 |

### 3.3 era 覆蓋（含 3 份 ground truth）

合計 14 份真實檔的 era 分佈：**era_1994** 一份（MSFT FY1994）、**era_2020** 四份（MSFT FY2023 + AAPL/NKE/PG）、**era_2023** 九份（APA + 其餘 8 份 era_2023 eval）。**era_2005 無任何真實檔**（僅由 SEC 規格建立規則）——這是佐證廣度的明確缺口，詳見第 7 段。

### 3.4 涵蓋的關鍵情境

- **Items 1&2 合併**：DVN（近年）、APA（ground truth）
- **雙註冊人合併申報（Inc. + L.P.）**：PLD
- **Item 6 reserved 措辭變體**：MSFT「[Reserved]」、APA「Selected Financial Data…Omitted」、PG「Intentionally Omitted」——三種不同寫法
- **Part III 大量 IBR-to-proxy**：JPM 等金融業
- **非曆年 FYE**：AAPL（9 月）、NKE（5 月）、PG（6 月）、WMT（1 月）

---

## 4. 結果：抽取表現良好的申報檔

「抽取良好」在此定義為：filing_status=PASS、8/8 結構不變量通過，且（對近年檔）通過 head+tail 人工逐項抽查未見內容錯位。以此標準，11 份近年檔中 **8 份達標**，另 3 份 ground truth 亦經逐筆比對確認（MSFT FY1994 除 Item 14 外、MSFT FY2023、APA FY2023；Item 14 詳見第 6 段）。

### 4.1 近年檔結果總表（修復後）

| 公司 | FYE | era | items | status | 不變量 | 抽查 |
|---|---|---|---|---|---|---|
| AAPL | 2023-09-30 | era_2020 | 20 | PASS | 8/8 | ✓ 乾淨 |
| NKE | 2023-05-31 | era_2020 | 20 | PASS | 8/8 | ✓ 乾淨（Item 1 修復後歸位） |
| PG | 2023-06-30 | era_2020 | 20 | PASS | 8/8 | ✓ 乾淨（修復後 body 正確分段） |
| JPM | 2025-12-31 | era_2023 | 21 | PASS | 8/8 | ✓ 乾淨（修復後） |
| TSLA | 2025-12-31 | era_2023 | 21 | PASS | 8/8 | ✓ 乾淨 |
| WMT | 2026-01-31 | era_2023 | 21 | PASS | 8/8 | ✓ 乾淨 |
| DVN | 2025-12-31 | era_2023 | 21 | PASS | 8/8 | ✓ 乾淨（1&2 merge 正確） |
| PLD | 2025-12-31 | era_2023 | 21 | PASS | 8/8 | ✓ 乾淨（雙註冊人） |
| BRK-B | 2025-12-31 | era_2023 | 16 | FAILED | 7/8 | 見第 7 段 |
| PFE | 2025-12-31 | era_2023 | 19 | FAILED | 7/8 | 見第 7 段 |
| NEE | 2025-12-31 | era_2023 | 21 | FAILED | 7/8 | 見第 7 段 |

### 4.2 值得標舉的正確處理

- **Items 1&2 合併（DVN）**：偵測到「Items 1 and 2. Business and Properties」合併——Item 1 status=MERGED 持完整 span、Item 2 status=MERGED / merged_into=1 / 無 span；legal_structure 不變量以「相鄰性判準」確認合法。人工抽查確認 Item 1 內容涵蓋 Business 與 Properties、Item 2 正確指回。
- **雙註冊人合併申報（PLD）**：Prologis Inc. 與 Prologis L.P. 於同一份 10-K 申報，此複雜結構下 21 個 item 仍全數正確分段、8/8 通過、抽查無錯位。
- **多產業/多 FYE 穩健**：通過檔橫跨科技（AAPL/TSLA）、金融（JPM）、零售（WMT）、能源（DVN）、REIT（PLD）、消費（NKE/PG），FYE 涵蓋 1/5/6/9/12 月——顯示分段對產業與財年變異有一定穩健性。
- **修復檔經抽查確認為真修復**：NKE（Item 1 找回）與 PG（body 從 unclassified 恢復為 20 個正確 item）於修復後經 head+tail 抽查，確認內容正確歸位、非表面轉綠。

### 4.3 一個重要的限定

「抽取良好」意為「在此檔、以上述檢查未發現錯誤」。由於這 8 份近年檔無 ground truth（見第 1 段），head+tail 抽查看的是每個 span 的頭尾與相鄰邊界，**非逐字全文**；因此可降低但無法完全排除「item 中段夾入不屬於它的內容、而頭尾正常」的極隱蔽錯誤。

---

## 5. 發現的問題、根因與修復

本輪最主要的發現，是四份申報檔的分段失敗**收斂到單一根因**，並揭示一個架構層級的設計脆弱點。此外，另修復了一個性質不同的沉默失敗（part era-blind，見 5.6）。

### 5.1 症狀（四份 FAILED）

初次跑 11 份近年檔時，6 份 FAILED。其中 4 份的失敗可歸為同一類：

- **A 組（BRK-B / JPM / NKE）**：Item 1（Business）未被偵測，第一個被抓到的 item 是 1A。
- **PG**：僅偵測到 9 個項目、Item 1~8 全部缺失並淪為大型 unclassified residual（單塊達 20 萬字級）。

（另 2 份 FAILED —— PFE、NEE —— 屬不同問題，見第 7 段。）

### 5.2 根因（經逐層唯讀實測釘死）

透過一連串唯讀診斷（不修改 code），將症狀逐層剝到根因：

- Item 1 的標題文字**確實存在**於 Stage-1 正規化後的文字中（未被刪除）——排除「文字被剝除」。
- 錨點消歧邏輯**本身沒有「這行像不像目錄」的文字判準**，而是完全依賴 Stage-1 是否把「目錄（TOC）區間」框對：落在 TOC 區間內的錨點會被丟棄。
- 直接量測 Stage-1 的 TOC 區間邊界，兩個病灶被數字釘死：
  - **A 組（over-extend）**：TOC 結束邊界多框十幾~二十幾字（BRK +29 / JPM +17 / NKE +16），剛好蓋過 body「Item 1. Business」標題起點，使該錨點被當成目錄而丟棄 → 缺 Item 1。
  - **PG（under-extend）**：TOC 目錄列中段有一個約 929 字的空隙（超過分群門檻），使 TOC 被切成兩段；系統只取第一段（Item 1~8 目錄列），尾段（Item 9~16 目錄列）漏出 → 下游單調過濾接受這些漏出的目錄列、反把真正的 body 全部判為「往回跳」而封殺。

### 5.3 架構洞見：兩道閘不是獨立防線

此根因揭示一個設計脆弱點：分段的兩道下游閘（front-matter 排除、單調順序過濾）並非彼此獨立的安全網——第二道閘**默認**第一道（Stage-1 的 TOC 邊界）是對的。一旦上游邊界有小誤差，下游不但不會攔截，反而會**放大**它（over-extend 丟一個 item；under-extend 連鎖封殺整個 body）。這說明：多層檢查若共用同一個上游假設，錯誤會沿鏈傳遞、而非被獨立攔下。

### 5.4 測試先行修復（兩階段）

依鐵律「測試先行、不放寬門檻」：先寫 5 個會抓到上述錯誤的紅燈測試（改 code 前確認全數 FAIL），再分兩階段修復，判準只用 item 編號 + 順序 + 位置（不碰標題字串）：

- **階段 1（A 組）**：偵測到 run 尾端「編號往回跳」時剪除該條，使 TOC 結束邊界收在最後一條真正遞增的目錄列。
- **階段 2（PG）**：允許將「仍在文件前段、且編號延續遞增」的相鄰 run 併回同一 TOC，使被空隙切斷的尾段目錄列不再漏出。

### 5.5 修復結果與零回歸

- 5 個回歸測試由全紅轉全綠。
- 全套測試通過、零既有測試退步。
- 5 份原本乾淨的檔（AAPL/DVN/PLD/TSLA/WMT）零退步（status/不變量/item 數均不變）。
- 修復三份：JPM、NKE 由 FAILED 轉為 PASS 8/8；PG 由「9 項 + 13 violation」恢復為「20 項 + 0 violation」；三者皆經 head+tail 抽查確認內容正確歸位。
- 修改僅限單一檔（front-matter 模組），未動其他 pipeline/測試，未放寬任何不變量門檻。

### 5.6 第三階段修復：一個沉默失敗（part era-blind）

與 5.1–5.5 的 TOC 缺陷不同，本階段修復的是**沉默失敗**——通過全部不變量、卻仍不正確的錯誤（詳見第 6 段的完整分析）。

- **缺陷**：segmenter 指派每個 item 的 part 時，讀取一張寫死的「現代」對照表，而非依該檔的 era ruleset；導致 era_1994 的 Item 14 被判 Part III（應為 Part IV）。
- **修法（測試先行，純依 era、不 fallback）**：正確 per-item part 資料本已存在於 era 端，只是載入時被丟棄；修復將其接上——資料契約新增 per-item part 對照、picker 轉換時帶入、segmenter 改讀 ruleset。判準只用 item 編號對應的 era 宣告，不碰標題字串。
- **驗證**：先寫 1 條紅燈（MSFT FY1994 Item 14 應為 IV，現況 III 故 FAIL）+ 14 條護欄（13 份真實檔的有序 (item_id, part) 序列不變）；修復後紅燈轉綠、14 條護欄維持綠、全套 125 passed、11 家 eval 的 part 分佈與 filing_status 逐字不變。
- **意義**：此缺陷因 filing_status 一直是 PASS、8/8 不變量全過而無法被自我檢查發現；修復的價值不僅在改對一格 part，更在於**為「不變量偵測不到的錯誤」補上一道專屬測試防線**。

---

## 6. 沉默失敗：一個通過全部不變量、卻不正確的案例

本段是全報告誠實度的核心：一個由 ground truth 抓到、卻能通過全部 8 項結構不變量的錯誤。它證明「filing_status=PASS、8/8 不變量」不等於「分段正確」。此案例包含兩個獨立的錯誤維度，本輪修復其一、誠實保留其二。

### 6.1 案例

MSFT FY1994（era_1994）的 **Item 14**：ground truth 為「Exhibits, Financial Statement Schedules, and Reports on Form 8-K」，屬 **Part IV**、且為**實體內容（EXTRACTED）**。系統修復前的輸出為：**part = III**、**status = INCORPORATED_BY_REFERENCE**——兩個維度都與 ground truth 不符。然而此檔 filing_status=PASS、8/8 不變量全數通過、0 violation。

### 6.2 為何不變量抓不到

8 項不變量檢查的是順序、不重疊、覆蓋、該有的 item 是否存在等**結構性**性質；它們**不檢查「某個 item 被指派的 part 是否正確」，也不檢查「被判為 IBR 的 item 內容是否真的是 IBR」**。因此：part 標成 III 或 IV 不在任何不變量的偵測面上；而 Item 14 被判為 IBR 時，`should_exist` 仍視其為「存在」（IBR 是合法存在狀態），故不舉旗。這正是此錯誤能「安靜地」通過的原因——它必須靠 ground truth 逐筆比對才能被發現。

### 6.3 維度一：part 判錯（已於本輪修復）

- **根因**：segmenter 指派 part 時，使用一張寫死的**現代** item→part 對照表，而非依該檔的 era 規則。現代結構中 Item 14 = Principal Accountant Fees = Part III；但 era_1994（2003 年位移前）的 Item 14 = Exhibits = Part IV。segmenter 對「哪些 item 該存在」是 era-aware 的，對「每個 item 屬哪個 part」卻是 **era-blind** 的。
- **為何這是必須修的結構缺陷（而非可忽略的小限制）**：它違反本專案「結構依 era 規格」的核心原則；且其復發條件是「檔案真實結構 ≠ 那張寫死的現代表」——不只在舊檔（era_1994）顯現，**未來若 SEC 再做一次類似 2003 的 item 位移，同一錯誤會在當代檔上重演**。這是結構性脆弱點，不是一次性特例。
- **修復**：見 5.6。part 現改由 era ruleset 決定；MSFT FY1994 Item 14 現為 Part IV，並以測試鎖定，近代 13 份檔的 part 分佈經護欄確認逐字不變。

### 6.4 維度二：status 判錯（本輪未修，列為已知限制）

- **現況**：Item 14 的 status 被判為 INCORPORATED_BY_REFERENCE，應為 EXTRACTED。
- **根因（假設）**：status 由內文偵測而來（此為刻意設計，對應「檔案自證變形」原則）；Item 14 的 Exhibits 內容中含指向財報的 incorporated-by-reference 字樣，偵測器據此**過度一般化**、將整個 item 判為 IBR。此為假設：已由 grep 定位賦值點，但「確切觸發字句」未逐字驗證，標明為未完全釘死。
- **為何本輪不修**：此為 IBR 內文偵測的**精度問題**，與 part 的 era 查表缺口是**不同性質**、需不同修法；為維持本輪範圍聚焦（只修 part）且避免範圍蔓延，status 判定列為已知限制，待未來專門處理。
- **誠實界線**：因此不可稱「Item 14 已完全修復」——正確陳述是「Item 14 的 part 缺陷已修，status 判定仍為已知限制」。

### 6.5 與主敘事的區隔

須與另一件事區分：貫穿專案早期的原始 bug 是「MSFT 1994 被現代規則誤判缺 1A/1C 等」，那是 **era 選擇**問題，**已修復並經本輪驗證**（era_1994 正確挑選、expected_items 正確、無 1A/1B/7A/9A）。本段的 Item 14 是**另外兩個、獨立的**缺陷（part 與 status），非該修復的回歸。

---

## 7. 已知限制與具體失敗案例

本段誠實列出未修的失敗、驗證手法的邊界、與佐證缺口。作業明文要求「具體失敗案例」——以下均附實際症狀。

### 7.1 三份 FAILED 檔：pipeline 主動標紅的已定位問題

這三份是**大聲失敗**（不變量抓到、系統標紅），非隱藏失敗。本輪已定位症狀，但根因未定性、依範圍與零回歸考量未修：

- **BRK-B**（FAILED、7/8）：Item 1 已於本輪修復找回；剩餘唯一 violation 為 Item 9B 與 Item 15 之間一塊約 421 字的 unclassified residual（位於 Part III 區塊附近）。根因未定性，為與 TOC 邊界無關的獨立問題。
- **PFE**（FAILED、7/8）：缺 Item 4（Mine Safety），should_exist 舉旗。單一主 item 缺失，根因未定性。
- **NEE**（FAILED、7/8、25 個 violation）：coverage 出現大量 overlap；症狀為走查游標卡在末尾、其餘各段被判為起點在游標之前。根因未定性，疑與其多註冊人/版面結構有關。
- **後續規劃**：BRK/NEE 這類問題可能於後續金融/科技擴大抽樣中再現；屆時彙集同型案例一併定性修復，較單獨處理更有效率。

### 7.2 已修缺陷的殘留邊界

- **MSFT FY1994 Item 14 的 status**：part 已修，但 status 誤判（IBR 應為 EXTRACTED）仍未修，為已知限制（見 6.4）。

### 7.3 抽查手法的邊界

head+tail 人工抽查看的是每個 span 的頭尾與相鄰邊界，**非逐字全文**；能有效抓「內容溢出/錯位」，但無法完全排除「item 中段夾入外來內容、而頭尾正常」的極隱蔽錯誤。抽查降低沉默失敗機率，不等於歸零。

### 7.4 佐證廣度的缺口

- **era_2005 無任何真實檔**：其規則純由 SEC 出處（final rule）建立，未經真實申報檔驗證。這是四個 era 中唯一無真實檔佐證者。
- **無 ground truth 的 8 份近年檔**：其「通過」為「未見錯誤」，非「證明無誤」。

### 7.5 呈現層的無界性（具體佐證）

- **reserved 措辭變體**：Item 6 的空置寫法至少有三種——「[Reserved]」（MSFT/多數近年檔）、「Selected Financial Data…Omitted」（APA）、「Intentionally Omitted」（PG）。目前 reserved 偵測靠「[Reserved]」字樣，故 APA 與 PG 的變體未被判為 RESERVED（而判為 EXTRACTED）——**不影響分段正確性**（item 仍正確切出、內容正確、不變量通過），但屬 status 分類精度的已知限制。
- **其他 marker 類**（not-applicable、authorized-omission 等）句式多樣，列為已知限制，未逐一處理。

### 7.6 母體分佈未知

本輪觀察到 TOC 邊界失效有兩種相反型態（over-extend 與 under-extend）；但「這兩型（及其他呈現型態）在母體中的相對頻率」無法由本輪證據估計——需層級三（飽和抽樣）與層級四（Good-Turing 殘差估計），兩者未執行。

---

## 8. 方法邊界與後續工作

### 8.1 本報告能宣稱什麼、不能宣稱什麼

本報告的所有「通過」結論，應理解為「在這些特定申報檔上、以這些檢查未發現錯誤」，而非「系統對母體整體正確」的證明。具體而言：

- **3 份 ground truth** 支持「這 3 份分段正確或找出具體錯誤」的強結論。
- **11 份廣度延伸** 支持「未見大聲失敗、且逐項頭尾未見內容錯位」，但**不宣稱逐 item 全部正確**（無答案卡可比）。
- 兩者皆**不支持**對母體（所有公司、所有年度的 10-K）的涵蓋率或錯誤率做估計。

### 8.2 認識論定調：綠燈是掙來的地板，不是正確性的天花板

本專案的核心區分貫穿始終：**結構/法規層可證明封閉**（由 SEC 規格決定，不需真實檔即可推定），**呈現層可估計但無法證明封閉**（近乎無限、無法枚舉）。8 項結構不變量是強而自動的自我檢查，但其偵測面有明確邊界——第 6 段的 part 沉默失敗即證明：通過全部不變量不等於正確。因此本輪除了不變量，另以 ground truth 比對與 head+tail 抽查補抓不變量看不到的錯誤，並為已發現的沉默失敗補上專屬測試。即便如此，「未發現錯誤」仍不等於「無錯誤」。

### 8.3 後續工作（明確未執行的部分）

- **層級三（跨公司飽和抽樣）**：對更大、更具代表性的樣本抽樣至涵蓋率收斂，以估計呈現層的實際涵蓋程度。本輪 11 份為刻意分散、非飽和抽樣，不構成層級三。
- **層級四（Good-Turing 殘差估計）**：估計「未見過的呈現型態」的殘餘機率。
- **era_2005 真實檔佐證**：目前僅由 SEC 規格建立，待補真實申報檔驗證。
- **未修缺陷**：MSFT FY1994 Item 14 的 status 判定；BRK/PFE/NEE 三份 FAILED 的根因定性與修復；reserved 措辭變體（APA/PG）的 status 分類精修。
- **效能、成本、擴充性分析**：待 Stage 6 前端與 Stage 4（LLM fallback，預設關閉）完成後，於整體總覽一併提供——因 Stage 4 接上前，成本與延遲數字尚不完整。

---

## 9. AI 協作品質

本專案以 AI coding 工具協作開發。作業重視「AI 協作能否放大產出」，以下記錄實際的協作方式與若干可佐證的實例。

### 9.1 紀律化的除錯迴路

面對失敗時，採一致的迴路：**症狀 → 唯讀查證 → 逐層剝到根因 → 測試先行 → 最小修 → 全套回歸**。關鍵原則有二：(a) 改任何 code 前，先以唯讀指令看實際 code，不憑印象或記憶；(b) 全程嚴格區分「實跑得到的事實」與「尚未驗證的假設」，並明確標記後者。這使診斷結論可被覆核、修復可被驗證。

### 9.2 測試先行、不放寬門檻

每一次修 pipeline 核心，都先寫「會抓到現況錯誤」的紅燈測試（改 code 前確認其 FAIL），再改 code 使其轉綠，並回跑全套與乾淨檔護欄。本輪三次修復（TOC 兩階段 + part）皆如此，最終 125 項測試通過、無既有測試退步、無放寬任何不變量門檻。

### 9.3 AI 自我修正的實例（可佐證）

（本專案的 AI 協作分兩層：**規劃/分析層**與**本機執行層**（Claude Code，在 VS Code 內實際讀寫檔案與跑測試）。以下實例主要發生在執行層，以及規劃層對自身框架的修正。）協作過程中，AI 工具數次以實測發現並修正自己先前的錯誤，而非沿用錯誤指令——這是「AI 不盲從、用實測發現問題、誠實更正」的具體展現：

- 將「相鄰性判準」從「index 純連續」修正為「字母子項不打斷、數字主項才打斷」，因前者會誤判現代 era 的 {1,2}。
- 推翻自己對 PG 失敗的初判（「一行多 item」），經逐行實測改判為「TOC 中段 929 字空隙導致 run 斷裂」。
- 主動揭露自身診斷腳本的瑕疵（某量測取錯比較基準），更正後重算。
- 在指令禁止改動某檔時，誠實回報「該修的地方在禁止範圍內」，而非擅自越界。

### 9.4 人為監督的角色

每一個決策點（改哪一層、修復範圍、比對嚴格度、驗證涵蓋範圍）均由人拍板後才推進；AI 產出的計畫與 diff 在落地前可被檢視。數個關鍵判斷由人的質疑推動修正——例如將 part 缺陷的處理從「記錄」提升為「修復」（因它違反核心原則、會復發），以及將 part 回歸護欄從少數樣本擴大為涵蓋全部真實檔。這種「AI 提出、人把關」的分工，是本輪能兼顧速度與嚴謹的原因。
