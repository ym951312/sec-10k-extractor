# 10-K Item 抽取 Pipeline — 設計文件（v2）

> 本文講「**系統是什麼**」：資料契約、管線階段、不變量、驗證邏輯。
> 「**怎麼蓋、怎麼跑、怎麼控成本**」在另一份《Build & Ops 手冊》。
> 對應對話：SEC 10-K Item-level 結構化抽取 take-home。

---

## 0. 任務定義與範圍

- **任務 = segmentation（分段）**：把一份雜亂的 raw 10-K 可靠切成各個 item 區塊，讓每個 item 能被**獨立取用**；在**無公開 ground truth** 下自我驗證；並**誠實回報**每個抽取的信心與失敗案例。
- **不是任務**：不判斷「公司是否違規」。評的是「抽取得好的 filing vs 有困難的 filing」，衡量的是 **parser 的能力**，不是公司合規。
- **「違規 vs 格式 tension」**：兩者徵兆共用（都觸發同一個不變量偵測器），無法乾淨歸因。只當作失敗案例上的**非評分診斷註記（reason code）**，不對「是否違規」輸出機率、不下 verdict。
- **評測零祕密**：核心系統（Stage 1–3、5、6）不需任何 runtime 金鑰即可被評測者執行；Stage 4 的 LLM 輔助為**可選、預設關閉、BYO-key**，**絕不要求評測者提供金鑰**。

---

## 1. 核心概念：四層光譜、唯一可信不變量、容器階層

| 層 | 成因 | 可窮盡？ | 處置 |
|---|---|---|---|
| 硬性 | 規則強制（item 編號、法定主題、排列順序；檔案世代格式） | 可，讀規格 + 修訂史 | 切割依據（朋友） |
| 彈性 A：被授權裁量 | 規則明文允許（相鄰 item 合併、引用併入、省略） | 大致可，讀授權清單 | 列入合法結構集 |
| 彈性 B：規則沉默 | 規則未規定（排版樣式、標題大小寫/分隔、HTML 標籤選擇） | 不可，抽樣到飽和 | 偵測器兜底 + 升級 LLM |
| 違規 | 規則要求但沒照做（壞 HTML、typo、順序錯） | 不可 | 偵測器兜底（失敗時要「響」） |

- **唯一可信不變量 = item 編號 + 排列順序**，**不是**標題字串（標題會因年換主題、因公司換大小寫/分隔、因合併消失）。
- **容器階層 = Part ⊃ Item**。`1A / 1C` 是**各自獨立**的 item（只共用開頭數字），不是 Item 1 的子內容。原子切割單位 = 每一個帶編號 item（含 `1A`、`1C`）。合併只發生在**相鄰**帶編號 item 之間。

---

## 2. 資料模型 / 契約

> 欄位是 spec 草圖，名稱可直接對應未來資料結構。

- **Ruleset**（key = 會計年度結束日；離線建一次，見 Stage 0）
  - `expected_items`：該年應存在的 item 編號集合與**法定順序**
  - `reserved_items`：法定為空的槽
  - `legal_structures`：合法合併型態集合（彈性 A 授權；僅相鄰合併 → 組合數 2^(n-1)，實務上集合很小）
  - `file_generation`：該世代檔案格式（ASCII / HTML / HTML+XBRL；由 Reg S-T 治理）

- **Filing**
  - `cik`, `accession`, `fiscal_year_end`, `form_type`（10-K / 10-K/A）, `raw_bytes`

- **Item（Segment）**
  - `item_id`（如 `"1A"`）, `part`（`I`..`IV`）
  - `char_span`：正規化文本（尺，見 §3）上的 `(start, end)`
  - `status`：
    - `extracted`（正常有內容）
    - `reserved`（法定為空，例 `Item 6 [Reserved]`）→ **正確地空，PASS**
    - `incorporated_by_reference`（本體在外部文件，例 Part III → proxy）→ **PASS**
    - `merged`（與相鄰 item 合併在同一標題下；合併 span 計一次，其餘成員以 `merged_into:<id>` 指向）
    - `failed`（無法可靠切割）
  - `confidence`：`P(邊界抓對)` ∈ [0,1]（證據分數，非正確率；見 §5）
  - `method`：`deterministic` / `llm` / `human`
  - `reason_codes[]`：失敗/低信心原因（含可選的「違規 vs 格式」診斷註記）
  - `source_ref`：回指原始位元組/節點，供前端高亮

- **Residual**（尺**上**、不屬於任何 item 的內容）
  - `spans[]`，各自 `classification`：`cover_page` / `toc` / `part_divider` / `signatures` / `exhibit_index` / **`unclassified`**（大塊 unclassified = 紅旗）
- **StrippedLedger**（尺**外**、Stage 1 正規化時刻意剝除並記錄的內容）
  - 各筆 `(source_span, classification, reason)`，`classification`：`page_header_footer`（每頁重複頁首頁尾，已剝除）/ `xbrl_hidden`（`<ix:hidden>` 隱藏 facts，audit-only、不計入守恆等式）
  - 註：頁首頁尾在 Stage 1 被剝除洗乾淨尺，故歸 ledger（尺外）而非 residual span（尺上）；兩者分屬不同分類，不混用

- **FilingResult**
  - `items[]`（依序、可單獨取用）, `residual`, `filing_status`（pass / review / failed）, `filing_confidence`, `verification_report`

---

## 3. 座標系契約（地基，務必先釘死）

- **座標系 = 正規化後的整份文本字元序列（位置 0..N）**，是一把**尺**，邏輯上**先於** item 與 residual 兩者。`char_span` 只是這把尺上的區間。
- **它不是 item 的聯集。** item 與 residual 都是尺上的區間。
- **絕不可**把任一邊定義成另一邊的補集（`residual = 全文 − items` 或 `items = 全文 − residual`）——那會讓覆蓋不變量**恆真、失去診斷力**。
- **兩邊都正面辨識**，讓「沒被任何一邊認領的 **gap**」與「被兩邊重複認領的 **overlap**」當警報。residual 是「這幾種**已知**非 item 結構」+ `unclassified` 旗標，不是「不是 item 的全部」。
- **正規化完整性（raw-bytes 層自我驗證）**：覆蓋是量在這把尺上的，所以**正規化不可偷偷掉字**。Stage 1 必須驗證：原始**可見文字**都進了正規化序列，刻意剝除者（如每頁重複的頁首頁尾）須**記錄**。**尺要先被「認證完整」，其上的覆蓋宣稱才算數。**
- 非 item 內容**散落全篇**，非僅首尾，且分兩種去處：(1) **保留為尺上 residual span**——封面頁（常含 inline XBRL）、目錄、Part 分隔、簽名頁、exhibit index（嚴格說屬 Item 15）；(2) **在 Stage 1 正規化時剝除、記入 ledger（不在尺上）**——每頁重複的頁首頁尾（最便宜可偵測，剝掉以洗乾淨尺）。兩者分屬 residual 與 ledger，不混用。

---

## 4. 六階段管線

### Stage 0 — 規格攝入（離線，每個 ruleset 一次，不 sample filing）
讀 Form 10-K 官方規格 + Reg S-K + 修訂史（Federal Register）+ Reg S-T/EDGAR Filer Manual → 產出**依會計年度結束日索引的 Ruleset 表**（硬性 + 彈性 A 的可關閉知識來源）。

### Stage 1 — 攝入與正規化（= 第一部）
1. 取得 raw bytes
2. **偵測檔案世代格式**（ASCII / HTML / HTML+XBRL）
3. **依 `fiscal_year_end` 選 Ruleset**
4. **選 parser 策略**（純文字 regex / HTML DOM / XBRL-aware）
5. **建立「認證完整」的尺**（§3：正規化 + 完整性檢查 + 記錄剝除）
6. **先剝除每頁重複頁首頁尾**；**早期隔離封面頁與目錄**為候選 residual → 預先拆掉「目錄假標題」陷阱

### Stage 2 — 確定性切割（便宜層；零 API 成本）
- 錨點 = **enumerator「Item N」**，**不是** caption 主題字串
- 納入排版變體：`item n` / `Item n` / `ITEM N` / `Item N.` / `ITEM N—` / 夾 `&nbsp;`（case-insensitive、分隔/空白寬鬆）
- **消歧**（放寬 regex 會抬高 false positive：內文 "this item"、目錄回音、交叉引用 "see Item 1A"）：用 HTML 結構位置 / 是否在已隔離目錄區 / **ruleset 的「預期下一個 item」序位**（最強的便宜過濾器）
- 偵測**實際結構**（哪些 item 在、有無合併），輸出候選 Item spans

### Stage 3 — 驗證 / 不變量檢查（閘門；與三層正交）
對候選分段跑 §5 不變量，**產生每 item 的 confidence + reason_codes**，並彙總 filing 級狀態。低信心/失敗在此**舉旗**。

### Stage 4 — LLM fallback（昂貴層；只在被舉旗時；**可選、預設關閉**）
- **可選、預設關閉**：核心（Stage 1–3、5、6）不需任何外部 API/金鑰即可執行與評測；關閉時優雅降級為確定性抽取 + 誠實低信心標記。LLM 僅用開發者**自己的**金鑰啟用，**絕不要求評測者提供金鑰**。
- 觸發：Stage 3 對某 item/區段判低信心或不變量失敗
- **範圍限定在失敗的 span**（省 token）
- **LLM 是提案者，不是驗證者**：提案邊界 → **回流 Stage 3 同一個閘門驗證**，不盲信
- **確定性驗證器在 LLM 呼叫之外**；**重試設硬上限**（防跑分失控）
- model 分層升級（Haiku → Sonnet → Opus）與成本細節見《Build & Ops 手冊》

### Stage 5 — 人工兜底 / 誠實失敗
- 觸發：連 LLM 都過不了；或為建 eval set 抽樣
- 人工只看被舉旗殘渣
- 產出：(a) 在結果與前端**誠實標為失敗/低信心**；(b) 標註餵 **eval set（抽樣 gold）**，可轉成**新確定性規則**

### Stage 6 — 輸出與前端
- 每份 FilingResult：item 可**單獨取用**，各帶 confidence / status / reason_codes / 回指來源
- 顯示 residual；filing 級信心；明確的「抽取得好 vs 有困難」分類供 README/前端
- 前端：提交/選擇 filing、檢視 items、檢視信心與失敗案例

---

## 5. 驗證模型：無 ground truth 怎麼自我驗證

**兩個上游錨（讓本地比較有意義、非循環）**
- **法規層**：Ruleset（Stage 0）獨立於抽取地給「該年應有哪些 item、什麼順序」→ 順序/應存在性是拿抽取比*規格*，非自己比自己。
- **raw-bytes 層**：正規化完整性（§3）→ 覆蓋量在認證完整的尺上才有意義。

**不變量清單（Stage 3）**
1. 順序：item 依該 ruleset 法定編號順序出現
2. 不重疊：item span 互不重疊
3. 覆蓋：items ∪ residual = 全文（尺），無未解釋 gap、無 overlap
4. 殘留 sanity：每 residual span 可歸類；大塊 `unclassified` = 紅旗
5. 合法結構成員性：偵測結構（含合併）∈ ruleset 的 `legal_structures`
6. 應存在性：必存在 item 都在（或以 `reserved` / `incorporated_by_reference` 正當缺席）
7. （限 Item 8）XBRL 交叉檢查：財報區段邊界被 XBRL 標記佐證
8. 跨方法一致性（>1 方法時）：邊界吻合（方法須**獨立失效**才算數）

**confidence 的定義**
- `confidence = P(這個 item 邊界抓對)`，是上述檢查**收斂程度**的函數（過愈多獨立檢查、跨方法愈吻合愈高）
- **是證據分數，不是正確率**；無 ground truth，沒有 oracle 說「100% 對」

**可證失敗 vs 被佐證成功（不對稱）**
- **失敗可證**：違反順序/重疊/覆蓋 = 對已知約束的演繹矛盾，不需 ground truth 即可斷定錯
- **成功僅被佐證**：不變量全過只代表「會抓錯的檢查都沒抓到」，自洽但錯的切法仍可能全過

**pass / review / failed**
- `failed` = 觸發任一硬不變量違反（**類別判定**，一違反即 failed，與分數無關）
- 未違反者：`pass` vs `review` = 連續證據分數上的**校準門檻**
- **數值未經 eval set 校準前不當機率**；校準前以 high/med/low 三檔處理

**eval set（誠實的完整性）**
- **分層抽樣到飽和**：沿年代 / 產業 / 規模 / 本國 vs 外國發行人抽角落
- 畫「新類型發現率 vs 樣本數」曲線，趨平 = 接近飽和（實證非證明）
- 用 eval set **校準** confidence，並量出 **LLM 層的 false-pass 率**（判 pass 中人工複查實際對幾成）

---

## 6. 擴充點（含 ML hook；現在不建）

- **新檔案格式/世代** → Stage 1–2 加 parser 策略 + Stage 0 加 ruleset 欄位
- **新法規變動**（新增/廢止/換主題 item）→ Stage 0 加 ruleset 版本（**讀規格，不從歷史學**；如 Item 1C 在 2023 前不存在）
- **更多公司/filing** → Stage 1–2 平行化 + 快取
- **ML hook（設計保留）**：Stage 5 人工標註累積成資料集；未來可學 (i) 彈性 B 排版尾的 confidence/邊界，或 (ii) 預先把 filing 路由到正確層。
  - **硬約束**：學習只能**擴張處理能力（彈性 B）**，**絕不可放寬 Stage 3 不變量門檻**。不變量是固定、非學習的仲裁者。

---

## 7. 尚缺 / 可改進

1. ~~座標系契約未定~~ → 已於 §3 定義；實作時務必先把**尺與完整性檢查**寫對，這是地基。
2. `reserved` 與 `incorporated_by_reference` 必須當「正確地空」= PASS，不可被覆蓋不變量誤判失敗（status enum 已涵蓋，但這是最易出錯細節）。
3. confidence 未經 eval set 校準前只是啟發式，別過度相信早期數字。
4. 「抽取得好 vs 有困難」是交付物，需定分類門檻（綁 `filing_confidence` + 升級率）。
5. edge cases 進分層測試矩陣：10-K/A、超大 filing、exhibit-heavy、目錄假標題、合併缺標題、換主題錨點錯位。分層抽樣計畫本身就是「我完整了嗎」的有原則答案。
