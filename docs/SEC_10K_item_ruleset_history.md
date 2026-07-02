# SEC Form 10-K 逐項（item-level）結構法規變動史

> **文件性質**：這是 Stage 0「era-appropriate ruleset」的**法規研究交付物**。
> 它把 SEC 對 Form 10-K item 結構的權威變動史，整理成一串「生效日 → item 結構」的稀疏分段函數基礎資料。
> **此文件僅為法規事實清單，尚未轉成 code。** 下一輪才據此設計 ruleset 資料結構。
>
> **產出方式**：所有生效日、trigger 措辭、item 影響均來自 SEC final rule / Federal Register / 真實 EDGAR 申報檔查證，附出處。
> 未經權威來源核實的部分一律標記「待補」，不憑印象填。

---

## 0. 如何閱讀本文件（佐證等級與核心原則）

### 佐證等級（Evidence Level）

每個變動點標註其佐證強度，這對應本專案「成功僅被佐證、失敗才可證」的認識論：

| 等級 | 標記 | 意義 |
|------|------|------|
| A | **【真實檔佐證】** | 有真實 EDGAR 申報檔可實跑驗證此 era 的 item 結構 |
| B | **【SEC 原始出處】** | 有 SEC final rule / Federal Register 權威文件佐證生效日與 item 影響，但目前 repo 無該 era 的真實檔 |
| C | **【待補】** | 已知此變動存在，但精確 final rule 出處 / 生效日尚未查證，且目前 repo 無對應真實檔，暫不納入強制判定 |

### 三條貫穿全文件的核心發現

1. **所有 trigger 都是 fiscal-year-end 語意。** 查證的每一個現代變動點，其適用條件都是「fiscal year ending on or after [生效日]」，**不是曆年、不是 filing date**。這與 Stage 0 柱子一擷取的 `fiscal_year_end` 完美對接：選 ruleset 時用 `fiscal_year_end` 比對這些門檻即為正確做法。

2. **reserved ≠ 刪除。** 某些 item（如 2020 的 Item 6）是「移除並保留（remove and reserve）」，item 編號仍在、只是變成合法空佔位。對應本專案鐵律「reserved = PASS（正確地空）」。

3. **效力未定的規則不進強制判定。** 通過但被暫停（stayed）、效力懸而未決的規則（如 2024 氣候揭露），**不作為 should_exist 依據**，僅標記存在。這是本專案「只給信心分數與原因代碼、不下合規判定」哲學的直接應用。

---

## 1. 已釘死的變動點（時間軸）

### 1.1　1994 era（古老世代）　**【真實檔佐證】**

**佐證來源**：多份真實 1994 EDGAR 申報檔（Schering Plough FY1994、Exxon FY1994、McCormick FY1994）；repo 內另有 MSFT FY1994 fixture。

**此 era 的 item 結構特徵（相對於現代結構的差異）**：

| 特徵 | 內容 | 佐證 |
|------|------|------|
| **Item 14 = Exhibits** | Item 14 標題為「Exhibits, Financial Statement Schedules, and Reports on Form 8-K」，屬於 Part IV | Schering Plough / Exxon FY1994 真實檔直接顯示 |
| **無 Item 1A** | Risk Factors 尚未存在（2005 才引入，見 §1.2） | 邏輯必然（1A 生效日 2005 > 1994） |
| **無 Item 7A** | Quantitative and Qualitative Disclosures About Market Risk 尚未存在 | 1994 真實檔 Item 7 後直接跳 Item 8 |
| **無 Item 9A** | Controls and Procedures 尚未存在（2002 SOX 後才有） | 1994 真實檔 Item 9 後直接進 Part III |
| **Part III 只到 Item 13** | 因 Item 14 屬 Exhibits（Part IV），故 Part III 範圍是 Item 10–13，**非現代的 10–14** | 由上述 Item 14=Exhibits 推得 |

**對現有 bug 的意義**：目前系統的 `_PART_III = {10..14}` 假設是現代結構，套到 1994 會把 1994 的 Item 14（Exhibits）誤當成 Part III 的「Principal Accountant Fees」，進而誤標 IBR。Stage 0 需讓 1994 era 使用 `Part III = {10..13}`、`Item 14 = Exhibits`。

**驗證期待**：Stage 0 完成後，MSFT 1994 用此 era ruleset 應正確判定 should_exist（本就無 1A/7A/9A）、Item 14 不再誤標 IBR。

---

### 1.2　2005：引入 Item 1A（Risk Factors）與 Item 1B（Unresolved Staff Comments）　**【SEC 原始出處】**

| 欄位 | 內容 |
|------|------|
| **Final Rule** | Release No. 33-8591（Securities Offering Reform） |
| **通過日** | 2005-07-19（adopting release）；2005-08-03 Federal Register |
| **SEC 出處** | https://www.sec.gov/files/rules/final/33-8591.pdf ；Federal Register: https://www.federalregister.gov/documents/2005/08/03/05-14560/securities-offering-reform |
| **item 影響** | Part I 新增 **Item 1A. Risk Factors**（依 Regulation S-K Item 503(c)，2020 後改為 Item 105）與 **Item 1B. Unresolved Staff Comments** |
| **Trigger（fiscal-year-end 語意）** | 適用「fiscal year ending on or after **2005-12-01**」的 10-K |

**對 MSFT 的意義（同構於 1C 的判定陷阱）**：MSFT FYE 為 6/30。財政年度結束於 2005-06-30 的 MSFT 10-K 早於 2005-12-01 門檻，**合法地沒有 Item 1A**，即使該檔是在 2006 年初才實際申報。若誤將 trigger 當成「filing date 在 2005/12/1 後」，會錯誤期待該檔要有 1A。

**備註**：1A 與 1B 是同一條 final rule、同一生效日一併引入，非兩個獨立變動點。

---

### 1.3　2020：Item 6（Selected Financial Data）改為 Reserved　**【SEC 原始出處】**

| 欄位 | 內容 |
|------|------|
| **Final Rule** | Release No. 33-10890（MD&A, Selected Financial Data, and Supplementary Financial Information） |
| **通過日** | 2020-11-19 |
| **SEC 出處** | https://www.sec.gov/files/rules/final/2020/33-10890.pdf ；Federal Register: https://www.federalregister.gov/documents/2021/01/11/2020-26090/... |
| **item 影響** | 將 Regulation S-K Item 301 與 Form 10-K Part II **Item 6「移除並保留（remove and reserve）」**。Item 6 編號仍在，但成為合法空佔位（Reserved）。 |
| **生效日** | 2021-02-10（rule effective date） |
| **Trigger（fiscal-year-end 語意）** | 強制適用「fiscal year ending on or after **2021-08-09**」 |

**灰色窗口（重要的邊界案例）**：本規則有「生效日（2021-02-10）」與「強制適用日（FYE ≥ 2021-08-09）」兩個日期，中間存在**早期適用窗口**。財政年度結束在 2021-02-10 至 2021-08-09 之間的公司：
- 有 Item 6（selected financial data）→ 合法（未早期適用）
- 無 Item 6（reserved）→ 合法（已早期適用）

**兩者皆合法**。此窗口期間，系統不應將「有無 Item 6」判定為對錯——正是「合法但格式不同」不該被誤判的實例。

**對應鐵律**：Item 6 為 reserved 時應判 PASS（正確地空），非缺件失敗。

---

### 1.4　2023：引入 Item 1C（Cybersecurity）　**【SEC 原始出處】**

| 欄位 | 內容 |
|------|------|
| **Final Rule** | Release No. 33-11216（Cybersecurity Risk Management, Strategy, Governance, and Incident Disclosure） |
| **通過日** | 2023-07-26 |
| **SEC 出處** | https://www.sec.gov/files/rules/final/2023/33-11216.pdf ；SEC 新聞稿: https://www.sec.gov/newsroom/press-releases/2023-139 |
| **item 影響** | Part I 新增 **Item 1C. Cybersecurity**（依 Regulation S-K 新設 Item 106），資訊須以 Inline XBRL 標記 |
| **Trigger（fiscal-year-end 語意）** | 適用「fiscal year ending on or after **2023-12-15**」的 10-K |

**對 MSFT FY2023 的意義（已在柱子一驗證）**：MSFT FY2023 的 FYE 為 2023-06-30，早於 2023-12-15 門檻，故**合法地沒有 Item 1C**。此判定已由柱子一擷取的 `fiscal_year_end = 2023-06-30` 佐證，並與本 final rule 的官方 trigger 一致。

**XBRL tagging 附加時程（供參考，非 item 結構變動）**：Inline XBRL 標記要求自「fiscal year ending on or after 2024-12-15」起適用。

---

### 1.5　2024／2025：Exhibit 19 + Item 408(b)（Insider Trading Policies）　**【SEC 原始出處】**

| 欄位 | 內容 |
|------|------|
| **Final Rule 來源** | 2022-12 通過的 Rule 10b5-1 相關 final rule |
| **首次適用** | 2024 財政年度的 10-K（於 2025 年初申報） |
| **item 影響** | 依 Regulation S-K 新設 **Item 408(b)**：須揭露是否採用內線交易政策與程序；並須將政策作為 **Exhibit 19** 附於 10-K |

**性質區別（重要）**：此變動**不是新增獨立編號的 top-level item**（不像 1C 那樣多一個「Item 1C」）。它是：
- Item 408(b) 揭露可放於 **Part III Item 10** 或 proxy statement（**位置彈性**）
- 新增一個 exhibit 編號（Exhibit 19）

**對應「四層法規光譜」**：這屬於「授權彈性（有界）」——規則明確給出兩個合法擺放位置，皆正確。系統不應將擺放位置差異判為對錯。

---

### 1.6　2024：氣候相關揭露（Climate Disclosure）　**【效力未定 — 不進強制判定】**

| 欄位 | 內容 |
|------|------|
| **Final Rule** | 2024-03-06 SEC 通過氣候揭露 final rule |
| **原定適用** | large accelerated filers 首次適用於 fiscal year ending 2025-12-31 |
| **⚠️ 當前狀態** | **已被 SEC 自願暫停（stayed），於合併訴訟司法審查期間效力凍結，目前非強制** |

**處理原則（經明確決定）**：此規則**不納入 ruleset 的強制 should_exist 判定**，僅在此標記其存在與未定狀態。理由：
- 它是「通過但效力凍結、可能被撤銷」的規則，非「效力明確」的門檻。
- 任何用它判定 should_exist 的邏輯，都會踩到本專案「違規與合法但格式不同無法乾淨區分」的核心洞見。
- 這正是本專案「只給信心、不下合規判定」哲學該發揮之處。

**若未來此規則效力確定或被撤銷**：屆時再依當時權威狀態，決定是否納入判定。

---

## 2. 標記為「待補」的區段　**【待補】**

以下變動點**已知存在**，但符合「精確 final rule 出處尚未查證，且目前 repo 無對應真實檔」的條件，故本輪暫不釘死、不納入強制判定。待未來有該年代真實檔進來、或需針對性測試該 era 時再補查。

### 2.1　1994 ↔ 2005 之間

- **Item 7A（市場風險揭露）引入的精確 final rule 與生效年份**：已知約在 1997 年（Regulation S-K Item 305 市場風險揭露規則），但精確 final rule 編號與 fiscal-year-end trigger 待補。
- **Item 9A（Controls and Procedures）引入**：已知源於 2002 年 Sarbanes-Oxley 後的內控揭露規則，精確 final rule 與生效日待補。
- **Item 14 → Item 15 的 Exhibits 編號位移**：現代 Item 15 = Exhibits、Item 14 = Principal Accountant Fees；1994 era 則 Item 14 = Exhibits。此「Exhibits 從 14 位移到 15、並插入新 Item 14」的精確發生年份與 final rule 待補。

### 2.2　2005 ↔ 2020 之間

- 此區間可能存在的其他 item 結構微調（如 Item 9B「Other Information」、Item 9C 等的引入年份）待補。
- Regulation S-K Item 503(c) → Item 105 的條號遷移（Risk Factors 依據條號在 2020 Release 33-10890 前後的變動）待補精確定位。

**待補原則**：這些區段一旦有對應真實檔進入 repo，或需要測試該 era，即針對性查證該段 final rule、補進本清單並升級佐證等級。此即「動態佐證台帳」在法規查證層的體現。

---

## 3. 現代 era 骨架的穩定性（供 ruleset 設計參考）

經查證確認：**2023-12-15（Item 1C 生效）至今，Form 10-K 的 top-level item 編號骨架未再新增或刪除。** 2024/2025 的變動集中於「既有 item 下的新揭露」（Item 408(b)）、「新 exhibit」（Exhibit 19）、以及「被暫停的氣候規則」，均未動到 item 編號骨架。

**意義**：現代 era 的 top-level item 清單（Item 1, 1A, 1B, 1C, 2–9, 9A, 9B, 9C, 10–16）自 2023-12-15 起是穩定的，可作為「最新 era」的 item 骨架。

**現代 era 官方 item 骨架來源**：SEC 官方 Form 10-K 空白表格 https://www.sec.gov/files/form10-k.pdf

---

## 4. 本清單與後續工作的銜接

**本輪（法規研究）完成**：釘死 1994 era、2005、2020、2023、2024/2025 主要變動點，附出處與佐證等級；標記待補區段；確立「效力未定不進判定」原則。

**下一輪（ruleset 資料結構設計）將決定**：
- 如何把本清單轉成「稀疏分段函數」的資料結構（生效日 → item 結構表）。
- 每個 era 的 item 表精確內容：`{item 編號 → (should_exist, part 歸屬, 是否 reserved, 正典 topic 標籤)}`。
- 佐證台帳如何實作（標記哪些 era 有真實檔佐證、哪些僅 SEC 出處、哪些待補；並在新真實檔進入時偵測法規缺口）。
- 灰色窗口（如 2020 Item 6 早期適用窗口）如何在判定邏輯中表達為「有無皆合法」。

**設計原則提醒**：ruleset 宜設計為**純資料**（結構化規則表），使未來補一個 era = 在資料表新增一筆（生效日 + item 清單 + 出處 + 佐證等級），而非修改 code 邏輯。

---

*本文件所有法規事實均附 SEC 權威出處。標記【待補】者為誠實反映查證邊界，非疏漏。*
