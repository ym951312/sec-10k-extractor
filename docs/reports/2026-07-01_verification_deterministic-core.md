# 驗證報告 —— 目前版本於真實 MSFT FY2023 10-K 上的自我檢驗

> 對象檔:`tests/fixtures/real/msft_10k_fy2023.htm.gz`(Microsoft Corporation，Form 10-K，fiscal year ended **2023-06-30**,EDGAR primary document,inline XBRL,解壓後 **9,963,591 bytes**)。
> 本報告的所有數字皆由「跑現有 code / 現有測試」取得,**未修改任何 code、未改動任何門檻**。技術名詞保留英文。
> 管線:`pipeline.run_pipeline` = Stage 1(尺)→ Stage 2(切割)→ Stage 3(不變量閘門),全程零金鑰、零網路。

**一句話結論:** 這份真實 10-K 的尺被 **CERTIFIED 完整**(missing=0)、被切成 **22 個 item + residual**、送進 Stage 3 後**八項不變量全過、filing_status = pass、high confidence、0 violations**。以下四節給出各自「用什麼獨立方法檢驗、實際結果是什麼」的可核對證據,並在第 2、4 節誠實標註目前的邊界。

---

## 第 1 節:尺的完整性 —— 原文是否被忠實保留

### 1.1 原理:兩條互相獨立的方法做守恆對帳

「尺(ruler)」是正規化後的字元序列,是後續一切 `char_span` 的座標系。要證明正規化**沒有偷偷掉字**,我們用**兩條彼此獨立的路徑**計算同一份原文的可見 word token,再驗證守恆等式:

```
source 可見 token  ==  尺 token  ⊎  ledger(被剝除可見) token
```

- **方法 A(尺本身):** `html.parser` 的 streaming DOM walk。逐一走訪 tag/text node/entity 事件,把可見文字寫進尺、把 inline XBRL 機器資料與重複頁首頁尾記進 ledger。
- **方法 B(獨立 baseline):** `normalize.visible_baseline_text` 的 **regex path**。用完全不同的實作(正規表達式剝除 `<script>`/`<style>`/comment/`<ix:header>`/`<ix:hidden>`/style-hidden 的 ix fact、block tag→空白、inline tag→透明)抽出可見文字。

**為何彼此獨立:** 方法 A 是「事件驅動的 DOM 走訪 + 一個 tag 堆疊」,方法 B 是「對 raw 字串做一連串 regex 替換」——兩者**不共用任何解析邏輯**。因此若方法 A 有 bug 而漏掉某個可見 `<td>` 的文字,方法 B 仍會數到它 → 該 token 出現在 source 卻不在尺 → `missing` > 0 → **CERTIFIED 失敗、會響**。這使「完整性」不是自說自話(non-circular)。

> 補述:實務上「可見文字」的判準採**機制規則**而非具名黑名單——排除的是「`ix:` 命名空間 ∩ 計算後不顯示」的交集(見 `normalize._is_xbrl_excluded`);`<ix:nonFraction>`/`<ix:nonNumeric>` 這類包住可見數字/文字者**保留計入**。其保證等級為「抽樣可估計」,非「可證封閉」。

### 1.2 MSFT 檔的實際對帳數字

| 量 | 值 |
|---|---|
| source 可見 token 總數 | **49,837** |
| 尺(ruler)token 數 | **47,248** |
| ledger 被剝除(可見)token 數 | **2,589** |
| **對帳** | 47,248 + 2,589 = **49,837** ✓ |
| `missing`(source 有、尺+ledger 沒有) | **0** |
| `extra`(尺有、source 沒有) | **0** |
| 完整性結果 | **CERTIFIED** |
| ledger 總筆數 | 2,663(`page_header_footer` 2,662 + `xbrl_hidden` 1) |
| 尺長度 | 554,317 chars |

`xbrl_hidden` 那 1 筆是 **audit-only**(inline XBRL `<ix:header>` 機器資料,本就不顯示,兩條路徑都排除、不計入守恆等式任一邊),故不影響對帳。2,662 筆 `page_header_footer` 是每頁重複頁首頁尾,被剝除但**逐字記錄**,計入等式右邊的 2,589 token。

### 1.3 一小段:原文 ↔ 尺 ↔ 原始 byte 的三方對照

取 **Item 1A 標題行**中的 token `FACTORS`(來自 "ITEM 1A. RISK FACTORS")做三方比對:

| # | 來源 | 內容 |
|---|---|---|
| (a) | 原始 HTML 片段 | `...min-width:fit-content;">K FACTORS</span></p>` |
| (b) | 尺上文字(ruler `[86556, 86563)`) | `FACTORS` |
| (c) | 由尺區間 resolve 回原始 byte(source `[722717, 722724)`) | `FACTORS` |

- (b) 與 (c) **一字不差**,且 `char_span` 對得上:尺 `[86556,86563)` 經 `provenance.source_ref_for` resolve 到原始 `[722717,722724)`,取回的文字與尺上完全相同。
- (a) 這段還順帶佐證了一個真實難點:原文把 "RISK" 拆在跨 `<span>` 邊界(前一個 span 結尾 `RIS`、這個 span 開頭 `K FACTORS`);**尺仍把單字接回、且 provenance 仍指得回正確 byte**——這正是「inline tag 不得切斷單字」的處理生效。

### 1.4 反向自我檢驗:掉字不會 silent

完整性檢查附一條**負向測試** `tests/test_completeness.py::test_negative_dropped_word_fails`:對一段已正規化的尺**故意移除一個可見單字**(如 `sprockets`),再跑對帳——斷言結果**必須 FAIL** 且 `missing` 內含該字。此測試保證:一旦正規化真的掉了可見字,守恆等式會偵測到並「響」,而不是悄悄通過。此測試目前為綠。

---

## 第 2 節:法規輸入的誠實現況

### 2.1 明確聲明

目前使用的是**最小靜態 ruleset**(`ruleset/loader.py::minimal_modern_ruleset`),**不是**完整的 Reg S-K / Stage 0 攝入。它只放「足以行使 Stage 3 不變量、且不會誤判合法檔」的最小知識。

### 2.2 這張最小表對 MSFT 適用年度實際放了什麼

- **`expected_items`(法定順序):**
  `1, 1A, 1B, 1C, 2, 3, 4`(Part I)、`5, 6, 7, 7A, 8, 9, 9A, 9B, 9C`(Part II)、`10, 11, 12, 13, 14`(Part III)、`15, 16`(Part IV)。
- **`reserved_items`:** `{6}`(Selected Financial Data 移除後,Item 6 常態為 `[Reserved]`)。
- **`legal_structures`(合法結構集):**
  | name | merges | absences |
  |---|---|---|
  | `standard` | —(無合併) | — |
  | `items_1_2_merged` | `1+2` | — |
  | `items_2_3_merged` | `2+3` | — |
  | `part_iii_incorporated_by_reference` | — | `10, 11, 12, 13, 14` |
- **Item 1C(Cybersecurity)的處理:** Item 1C 只對「fiscal year ending 於 **2023-12-15 之後**」的 filing 才**法定必需**。MSFT 本檔 fiscal year ended **2023-06-30**,早於生效門檻,故**合法地沒有 Item 1C**。由於目前只有單一靜態 ruleset、且尚未從 filing 抽出 `fiscal_year_end` 來動態選表,系統把 **`1C` 視為 optional(allowed-absent)**,以避免對此檔誤報「缺 item」。(目前 `OPTIONAL_ITEMS = {1B, 1C, 9B, 9C, 16}`。)

### 2.3 本節局限(誠實標註)

- 「完整、且按 `fiscal_year_end` **動態**決定該年應有哪些 item / 哪些 reserved / Item 1C 是否必需」屬於**尚未實作的 Stage 0**。
- 現況把 1C 一律當 optional 是**單一靜態 ruleset 下的折衷**:它避免了對 pre-2023-12-15 檔的誤報,代價是對「確實應有 1C 卻缺」的較新檔**不會**舉旗。正式 Stage 0 依 `fiscal_year_end` 選表後,才能把「1C 必需 vs 不必需」判得精確。這是**已知邊界,非 bug**。

---

## 第 3 節:item 劃分與 MSFT 的實際切割

### 3.1 劃分單位與錨點原則

- **原子切割單位 = 每一個帶編號 item**;`1A`、`1C` 是**各自獨立**的 item(只共用開頭數字),不是 Item 1 的子內容。
- **容器階層 = Part ⊃ Item**;合併只發生在**相鄰**帶編號 item 之間。
- **錨點 = `Item N` enumerator + 順序,不是標題主題字串**(標題會因年換主題、因合併消失)。

### 3.2 MSFT 實際切割結果(全 22 個 item)

| item | part | status | char_span | 長度(chars) | confidence |
|---|---|---|---|---:|---|
| 1 | I | extracted | 12016–86524 | 74,508 | medium |
| 1A | I | extracted | 86524–155640 | 69,116 | medium |
| 1B | I | extracted | 155640–155948 | 308 | medium |
| 2 | I | extracted | 155948–158460 | 2,512 | medium |
| 3 | I | extracted | 158460–158672 | 212 | medium |
| 4 | I | extracted | 158672–158728 | 56 | medium |
| 5 | II | extracted | 158728–162990 | 4,262 | medium |
| **6** | II | **reserved** | 162990–163050 | 60 | **high** |
| 7 | II | extracted | 163050–231273 | 68,223 | medium |
| 7A | II | extracted | 231273–234201 | 2,928 | medium |
| **8** | II | extracted | 234201–514634 | **280,433** | medium |
| 9 | II | extracted | 514634–514758 | 124 | medium |
| 9A | II | extracted | 514758–521470 | 6,712 | medium |
| 9B | II | extracted | 521470–521862 | 392 | medium |
| 9C | II | extracted | 521862–521948 | 86 | medium |
| **10** | III | **incorporated_by_reference** | 521962–523218 | 1,256 | **high** |
| **11** | III | **incorporated_by_reference** | 523218–523543 | 325 | **high** |
| **12** | III | **incorporated_by_reference** | 523543–523860 | 317 | **high** |
| **13** | III | **incorporated_by_reference** | 523860–524145 | 285 | **high** |
| **14** | III | **incorporated_by_reference** | 524145–524574 | 429 | **high** |
| 15 | IV | extracted | 524574–551480 | 26,906 | medium |
| 16 | IV | extracted | 551480–552322 | 842 | medium |

切割結果的**量級也合理**:Item 8(財報)最大(280K chars)、Item 1 / 1A / 7 次大(業務 / 風險 / MD&A),與 10-K 的實際內容分布一致。

### 3.3 代表性案例佐證(各取一小段)

- **Item 8(財報,最大塊)** `[234201,514634)`,起頭:
  `Item 8 … ITEM 8. FINANCIAL STATEMENTS AND SUPPLEMENTARY DATA INCOME STATEMENTS …` → 分類 `extracted` 正確;長度 280,433 chars 佔全尺逾半,符合財報為主體。
- **Item 6([Reserved],正確地空)** `[162990,163050)`,完整內容為:
  `Item 6 … ITEM 6. [RESERVED] …`(僅 60 chars,無實質 body)→ 分類 `reserved`、confidence `high`。這是「正確地空 = PASS」,不被覆蓋不變量誤判為失敗。
- **Items 10–14(Part III,引用併入 proxy)**,例:
  - Item 11 body:`ITEM 11. EXECUTIVE COMPENSATION The information in the Proxy Statement set forth under the captions "Director Compensation," …` → 命中 IBR 線索(`Proxy Statement`)→ 分類 `incorporated_by_reference`、confidence `high`。
  - Item 14 body:`ITEM 14. PRINCIPAL ACCOUNTANT FEES AND SERVICES Information concerning fees and services provided by our principal accountant, Deloitte & To…` → 同屬 Part III IBR。
  五個 Part III item 全數判為 IBR,與 MSFT 把 Part III 併入 proxy 的實況一致。

### 3.4 錨點用 enumerator、且消歧有效(MSFT 實例)

錨點正則抓的是行首的 `Item N` enumerator,**不是**標題字串。以 **"Item 1A"** 為例,尺上共有 **16 處**行首 "Item 1A":

- 位於 offset **5939** 的那處落在**已隔離的 TOC residual `[5754,10219)`** 內 → **被排除**(這正是「預先拆掉目錄假標題陷阱」:MSFT 的 HTML 目錄以密度被 Stage 1 偵測並隔離)。
- Stage 2 實際採用的 Item 1A 邊界在 offset **86524**(本體標題),confidence 由 ruleset 序位單調(order-monotonic)接受。
- 其餘 90966、95918、101062 … 等多處 "Item 1A" 是 Item 1A **本體內文**對自己的回指,因序位不再前進 → **被單調過濾丟棄**,不會被誤當成新邊界。

另有**交叉引用**型態的實例:offset 517350 附近的 `in Item 9A.`(內文中段、非行首)與 `in Item 408 of Regulation …`(`Item 408` 非合法 10-K item 編號、`order_index` 為 None)——兩者都**不會**成為 item 邊界。前者非行首、後者不在 ruleset 序列,皆被消歧擋下。

---

## 第 4 節:Stage 3 不變量閘門 —— 對上述切割的獨立驗證

### 4.1 八項不變量各檢查什麼、為何與切割器獨立

Stage 2 負責「切」,Stage 3 負責「驗」,兩者**不共用邏輯**:切割器用 regex 錨點 + 序位啟發式產生候選 span;閘門只拿「候選 span + ruler + ruleset」做**確定性、演繹式**的一致性檢查,不回頭參考切割器怎麼切的。故閘門能對切割結果做**獨立**判定。

| # | 不變量 | 檢查什麼 |
|---|---|---|
| 1 | order | item 依 ruleset 法定編號順序出現 |
| 2 | no_overlap | item span 互不重疊(合併成員不計入幾何集合) |
| 3 | coverage | items ∪ residual = 尺,無未解釋 gap、無 overlap |
| 4 | residual_sanity | 每 residual span 可歸類;大塊 `unclassified` = 紅旗 |
| 5 | legal_structure | 偵測到的結構(含合併)∈ ruleset 的 `legal_structures` |
| 6 | should_exist | 必存在 item 都在,或以 `reserved` / `incorporated_by_reference` / optional 正當缺席 |
| 7 | item8_xbrl | (限 Item 8)財報邊界被 XBRL 標記佐證 |
| 8 | cross_method | (>1 方法時)邊界跨方法吻合 |

### 4.2 MSFT 切割送入閘門的逐項結果

| # | 不變量 | 結果 |
|---|---|---|
| 1 | order | **PASS** |
| 2 | no_overlap | **PASS** |
| 3 | coverage | **PASS**(無未解釋 gap、無 overlap) |
| 4 | residual_sanity | **PASS**(residual 全可歸類,見下) |
| 5 | legal_structure | **PASS**(無合併 → 命中 `standard`) |
| 6 | should_exist | **PASS**(Item 6 以 reserved、Items 10–14 以 IBR、1C 以 optional 正當缺席) |
| 7 | item8_xbrl | **PASS(未行使)** |
| 8 | cross_method | **PASS(未行使)** |

- **filing_status = pass;filing_confidence = high;violations = 0。**
- **覆蓋(inv 3)** 之所以無 gap:residual 被**正面辨識**為 `cover_page ×2`、`toc ×1`、`part_divider ×1`、`signatures ×1`——首個 item 之前的前言(如 Forward-Looking Statements)歸 front matter(`cover_page`),item 之間/之後若有未解釋大塊才會標 `unclassified`;本檔無 `unclassified` 殘塊,故 inv 4 亦 PASS。
- **reserved / IBR 判為 PASS(關鍵特例):** Item 6(reserved)與 Items 10–14(IBR)是「正確地空 / 本體在外部」,在 inv 6 被視為正當缺席、在 confidence 上判 `high`,**不被誤判為失敗**。
- **誠實標註 inv 7 / inv 8 為「未行使」:** 本管線這次呼叫 Stage 3 時**未傳入 XBRL 邊界證據、也只有單一 deterministic 方法**,故 inv 7、inv 8 都是「沒有證據可檢 → 不觸發違反 → 記為 PASS」,屬**未被行使(vacuously passed)**,**不是**「被正面佐證」。這與設計的不對稱一致:失敗可證、成功僅被佐證。

### 4.3 整體測試現況與其份量、邊界

現有測試 **52 passed**(執行約 5 秒),分布:

| 測試檔 | 數量 | 涵蓋 |
|---|---:|---|
| test_completeness.py | 6 | 守恆對帳 + 掉字負向 + inline XBRL 可見/隱藏 |
| test_formats.py | 4 | 三世代格式偵測 + decode fallback |
| test_provenance.py | 3 | 尺↔原始 byte round-trip |
| test_headers_footers.py | 3 | 頁首頁尾偵測 + 剝除守恆 + 不誤剝 |
| test_front_matter.py | 4 | 封面 / TOC 隔離 |
| test_invariants.py | 22 | §5 八項不變量各 pass + 違反 fixture;reserved/IBR/merged 特例 |
| test_stage2.py | 6 | 錨點 / 消歧 / merged / reserved / IBR / 全管線 PASS |
| test_pipeline_synthetic.py | 1 | 合成完整 10-K 端到端 |
| test_real_integration.py | 3 | 真實 MSFT:尺 CERTIFIED + 剝除 chrome + 管線找到 items |

**「全綠」的份量與邊界(誠實說明):**

- **份量:** 完整性有**獨立方法對帳 + 掉字負向**背書;八項不變量**每項都有「違反 fixture 必須舉旗」**的反向測試(不是只測 happy path);真實 10MB 檔端到端 CERTIFIED 並通過閘門。
- **邊界:** 目前真實樣本**只有 1 份**(MSFT FY2023,單一世代 HTML+XBRL、單一產業、本國發行人、大型公司)。設計 §5 要求的**分層抽樣到飽和**(沿年代 / 產業 / 規模 / 本國 vs 外國、含 ASCII 世代與 10-K/A 等 edge cases)**尚未進行**;confidence 也**尚未用 eval set 校準**,故現階段以 high/med/low 三檔呈現、**不當機率**。inv 7(XBRL)、inv 8(cross-method)在此管線設定下**未被行使**。「全綠」證明的是「在已測範圍內、會抓錯的檢查都沒抓到」,**不等於**「對所有 filing 都正確」——這正是設計所述「成功僅被佐證、非被證明」的立場。

---

## 附:如何重現本報告的數字

```bash
pip install -e '.[dev]'
pytest -q                                   # 52 passed
python -c "import gzip; open('/tmp/msft.htm','wb').write(gzip.decompress(open('tests/fixtures/real/msft_10k_fy2023.htm.gz','rb').read()))"
sec10k /tmp/msft.htm                        # 印出 Stage 1 認證 + Stage 2 切割 + Stage 3 閘門
```
