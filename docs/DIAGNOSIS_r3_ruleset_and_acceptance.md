# r3 診斷：ruleset 分類缺陷與接受規則升級

## 0. 本輪範圍與證據等級

### 0.1 起點與實際產出
本輪（r3）起點是承接 `DIAGNOSIS_r2_failures.md` 的三個失敗案例（INTC / C / KKR），原意是探索其修復可行性。實際產出偏離了原定目標：在探查 KKR 的過程中，**挖出兩個先前未知的 ruleset 系統性缺陷**（Item 4 分類錯誤、CONDITIONAL item 內容被沉默吞併），其中一個（Item 4）正是既有 PFE FAILED 案例的根因。

### 0.2 唯讀聲明
**本輪全程唯讀，未修改任何 pipeline code、未修改任何既有文件。** 所有結論來自 session scratchpad 中的一次性 probe 腳本（腳本置於 repo 外），這些 probe 一律 `import` 實際的 pipeline 函式（`build_ruler` / `find_anchors` / `_greedy_monotonic` / `load_ruleset` / `allowed_absences` / `OPTIONAL_ITEMS` / `run_pipeline`），不重刻邏輯。本檔為本輪唯一新增檔案。

### 0.3 證據標籤定義
本檔每個結論都標記證據等級，三選一：

| 標籤 | 定義 |
|---|---|
| **【實測】** | 本輪有實跑輸出（或直接讀取的 code 原文）支撐 |
| **【推論】** | 由實測事實推導、但未直接驗證 |
| **【假設】** | 尚未驗證，待實測 |

標籤錯置比缺漏更嚴重。不確定歸屬者一律降級標【推論】並註明理由。

### 0.4 本輪推翻或補完的既有結論（僅記錄，不修改舊檔）

| 既有文件段落 | 原結論 | 本輪狀態 |
|---|---|---|
| `DIAGNOSIS_r2_failures.md` §5.2 | 否決「將 `_greedy_monotonic` 換成 LIS/最大覆蓋演算法」，理由之一為「爆炸半徑巨大（第一輪 125 test 與全部 PASS 檔皆依賴此核心）」 | **【實測推翻此理由】** 離線模擬實測顯示，換用繼承自動機後 24 檔中 23 檔接受清單逐錨完全一致，爆炸半徑為**一檔**（KKR），且方向為修正。詳見 §3。**注意：僅推翻「爆炸半徑」這一條理由，不等於「應該做」——詳見 §3.8。** |
| `DIAGNOSIS_r2_failures.md` §6 | 未竟事項：「KKR 是否修復 `_greedy_monotonic`（傾向不修、只記錄）待最終定案」 | **本輪補上決策所需證據**（行為保守性實測 + 驗證標準修正），但**未定案、未動 code**。 |
| `VALIDATION_part_1.md` §7.1 | 「**PFE**（FAILED、7/8）：缺 Item 4（Mine Safety），should_exist 舉旗。單一主 item 缺失，**根因未定性**。」 | **【實測定性】** 根因為 ruleset 將 Item 4 分類為 REQUIRED 且不在任何可缺席集合，而 PFE 合法省略之。詳見 §1。 |

---

## 1. 發現一：Item 4 分類錯誤導致 should_exist 偽陽性（PFE）

### 1.1 症狀【實測】
對 `tests/fixtures/eval_recent/pfe_10k_20251231.htm.gz` 跑現行完整 pipeline（`run_pipeline`）：

```
filing_status    = FilingStatus.FAILED
filing_confidence = ConfidenceTier.LOW

invariant_results (9 條)：
   PASS  order
   PASS  no_overlap
   PASS  coverage
   PASS  residual_sanity
   PASS  legal_structure
   FAIL  should_exist          <-- 唯一 FAIL
   PASS  item8_xbrl
   PASS  cross_method
   PASS  cover_dominance

violations (共 1 條，hard_violations = 1)：
  [1] severity=HARD  code=MISSING_EXPECTED_ITEM  item_id=4
      msg: expected item 4 is absent and not reserved / incorporated-by-reference / optional
```

**明確結論【實測】：Item 4 的 `MISSING_EXPECTED_ITEM` 是 PFE 的唯一 violation，9 條不變量中僅 `should_exist` FAIL。** 這代表若 Item 4 的分類被修正，PFE 的 `filing_status` 會**由 FAILED 直接轉為 PASS**（而非只少一條 violation）。

### 1.2 Item 4 在 24 檔的印/省分布【實測】
對全部 24 份 fixture 取「決策前錨流」（Stage-1 `build_ruler` → `find_anchors` → 套用 segmenter 的 front 排除），檢查是否存在 Item 4 錨：

| 檔案 | 輪次 | era | Item 4 錨 | 位置 |
|---|---|---|---|---|
| apa_10k_fy2023_merged12 | GT | era_2023 | 有 | 110578 |
| msft_10k_fy2023 | GT | era_2020 | 有 | 158672 |
| msft_10k_fy1994_ascii | GT | era_1994 | 有 | 45570 |
| aapl_10k_20230930 | r1 | era_2020 | 有 | 94887 |
| brkb_10k_20251231 | r1 | era_2023 | 有 | 175400 |
| dvn_10k_20251231 | r1 | era_2023 | 有 | 127056 |
| jpm_10k_20251231 | r1 | era_2023 | 有 | 159579 |
| nee_10k_20251231 | r1 | era_2023 | 有 | 169008 |
| nke_10k_20230531 | r1 | era_2020 | 有 | 139501 |
| **pfe_10k_20251231** | r1 | era_2023 | **無（省略）** | — |
| pg_10k_20230630 | r1 | era_2020 | 有 | 60984 |
| pld_10k_20251231 | r1 | era_2023 | 有 | 150219 |
| tsla_10k_20251231 | r1 | era_2023 | 有 | 143904 |
| wmt_10k_20260131 | r1 | era_2023 | 有 | 161390 |
| amd_10k_20251227 | r2 | era_2023 | 有 | 203111 |
| apo_10k_20251231 | r2 | era_2023 | 有 | 342706 |
| avgo_10k_20251102 | r2 | era_2023 | 有 | 150090 |
| bac_10k_20251231 | r2 | era_2023 | 有 | 163773 |
| blk_10k_20251231 | r2 | era_2023 | 有 | 265525 |
| **c_10k_20251231** | r2 | era_2023 | **無（省略）** | — |
| googl_10k_20251231 | r2 | era_2023 | 有 | 122743 |
| intc_10k_20251227 | r2 | era_2023 | 有 | 491359 |
| kkr_10k_20251231 | r2 | era_2023 | 有 | 391518 |
| nvda_10k_20260125 | r2 | era_2023 | 有 | 178012 |

**分布：22 檔有印 / 2 檔省略（PFE、C）。**

補充【實測】：`c_10k_20251231` 的「無 Item 4」不足以歸因於 Item 4 分類——該檔決策前錨數為 **0**（原始錨數亦為 0），屬另一類既有問題（見 §7），與 Item 4 分類正交。

補充【實測】：`intc_10k_20251227` 的 Item 4 錨位於 char 491359，落在 INTC 文末索引表區段內（見 §4），並非正文章節錨——此再次印證 INTC 的方法邊界性質。

### 1.3 機制【實測】
- `ERA_2023` 中 Item 4 宣告為 `ItemExpectation.REQUIRED`、`part=Part.PART_I`（`src/sec10k/ruleset/era.py`）。
- 因是 REQUIRED，adapter（`loader.py` `_era_to_ruleset`）將其納入 `expected_items`。實跑：modern(2023) `expected_items = ['1','1A','1B','1C','2','3','4','5','6','7','7A','8','9','9A','9B','10','11','12','13','14','15']`，**含 '4'**。
- Item 4 **不在** `allowed_absences`：實跑 `allowed_absences(era_2023) = ['10','11','12','13','14','6']`。
- Item 4 **不在** `OPTIONAL_ITEMS`：實跑 `OPTIONAL_ITEMS = {'1B','1C','9B','9C','16'}`（`invariants/checks.py:37`）。
- inv-6 `check_should_exist` 的 `permitted_absent = allowed_absences(ruleset) | OPTIONAL_ITEMS`（`checks.py:215`）。實跑 `permitted_absent(era_2023) = ['10','11','12','13','14','16','1B','1C','6','9B','9C']`，**不含 '4'**。

→ Item 4 在 `expected_items` 中、卻不在 `permitted_absent` 中 → 一旦某 filing 省略 Item 4，`should_exist` 必然舉旗。**這是 ruleset 的建模缺陷，不是 pipeline 的偵測錯誤。**

### 1.4 法規定性【假設 — 待 SEC 出處確認】
Item 4（Mine Safety Disclosures）**推定**為條件適用：僅對經營礦場之 registrant 適用，非礦業公司省略應屬合法。PFE 為製藥公司、Citigroup 為銀行，皆無礦場。

> **⚠ 明確標註：此法規定性尚未經 SEC 原始出處（如 Regulation S-K Item 104 / Dodd-Frank Act §1503 相關條文）查證。**
> **在完成 grounding 之前，此條不得作為修法依據。** 缺乏出處的情況下，把 Item 4 移入可缺席集合與「為了讓測試變綠而放寬門檻」在客觀上無法區分——這正是 CLAUDE.md 鐵律明文禁止的行為。**grounding 是此工項的前置閘門，非事後補件。**

旁證【實測，僅為旁證非出處】：`era.py` 的 `ERA_2023` pending_notes 中已記載一筆真實檔觀察——「Item 4（Mine Safety）：APA 為石油天然氣公司，但其 Item 4 為 'Not applicable'（Mine Safety 針對煤/金屬礦，油氣不適用）。Item 4 仍 REQUIRED，此為真實檔觀察。」此註記顯示既有設計已察覺 Item 4 的適用性問題，但當時的處置是「印出標題但內容 Not applicable」，未考慮「整個 item 連標題一併省略」的情形（PFE 即為後者）。**此旁證不能取代 SEC 出處。**

### 1.5 額外警示：Item 4 在不同 era 指涉不同項目【實測 — code 原文】
讀取 `src/sec10k/ruleset/era.py` 原文，Item 4 的 topic 逐 era 不同：

| era | Item 4 的 topic（code 原文） | expectation |
|---|---|---|
| `ERA_1994` | `"Submission of Matters to a Vote of Security Holders"` | REQUIRED |
| `ERA_2005` | `"Submission of Matters to a Vote of Security Holders"` | REQUIRED |
| `ERA_2020` | `"Mine Safety Disclosures"` | REQUIRED |
| `ERA_2023` | `"Mine Safety Disclosures"` | REQUIRED |

**→ 修正 Item 4 分類時必須逐 era 處理，絕不可跨 era 一併修改。** `ERA_1994` / `ERA_2005` 的 Item 4 是「股東表決事項提交」，其可缺席性與 Mine Safety 完全無關，法規依據也不同。若一律把 `'4'` 塞進可缺席集合，等於在 1994/2005 era 引入一個未經任何法規論證的放寬。

佐證【實測】：MSFT FY1994（era_1994）實跑 `expected_items = ['1','2','3','4','5','6','7','8','9','10','11','12','13','14']`，其 Item 4 錨實際存在於 char 45570（該檔有印 Item 4）。**era_1994 / era_2005 的 Item 4 可缺席性完全未經探查，本輪無任何證據。**

### 1.6 修法方向【推論】
正解為**將（近代 era 的）Item 4 移入 `allowed_absences`**，而非改為 `CONDITIONAL`。

理由【推論，依據 §2 的實測機制】：
- 移入 `allowed_absences`：Item 4 **保留在 `expected_items`** → 仍有 `order_index` → 有印時錨照常被接受、照常切 span；缺席時 `should_exist` 不舉旗。**這正是我們要的語意。**
- 改為 `CONDITIONAL`：依 `loader.py` 的 adapter 邏輯，CONDITIONAL 會被**排除於 `expected_items`** → `order_index` 變 `None` → 有印時錨會被 `_greedy_monotonic` 當 unknown id 丟棄 → **落入 §2 所述的「內容被前項沉默吞併」陷阱**。對 22 份有印 Item 4 的檔而言，這會把一個偽陽性換成 22 個沉默失敗，是嚴重的退步。

**此為本輪的一個關鍵洞見：`CONDITIONAL` 這個分類本身帶有一個未被察覺的副作用（§2），因此不能拿來當「這個 item 可以不存在」的通用解。**

### 1.7 合規性論證（以及它的前提）
此修正的性質是「**修正錯誤的法規建模**」（ruleset 把一個條件適用的 item 誤標為無條件必要），而非「**放寬不變量門檻**」（CLAUDE.md 鐵律「不要為了『通過』而放寬 Stage 3 不變量門檻」明文禁止）。

**但這個區分完全依賴 §1.4 的 SEC grounding。** 無出處 → 兩者在客觀上不可區分 → 此工項不得執行。這不是形式主義：Item 4 的可缺席性若實際上不成立，則 PFE 的 FAILED 是**正確的**，而我們會把一個真陽性改成偽陰性。

---

## 2. 發現二：CONDITIONAL item（9C/16）的內容被前項沉默吞併（新 silent failure）

### 2.1 機制【實測】
`src/sec10k/ruleset/loader.py` 的 `_era_to_ruleset` adapter，其排除邏輯與註解原文：

```python
    # expected_items = items the era expects to be PRESENT, in item order.
    #   * REQUIRED / RESERVED are kept (RESERVED is a present-but-empty slot).
    #   * ABSENT excluded (the item does not exist in this era).
    #   * CONDITIONAL excluded (present-or-absent both legal; putting it here
    #     would make downstream flag a filing that legally omits 9C/16 as missing).
    #   Order is preserved from era.items, so Ruleset.order_index() works.
    expected_items = [
        r.item_id for r in era.items
        if r.expectation in (ItemExpectation.REQUIRED, ItemExpectation.RESERVED)
    ]
```

此排除的**動機是正確的**（避免把合法省略的 9C/16 誤判為 missing），但產生了一條未被預見的因果鏈【實測】：

```
CONDITIONAL
  → 排除於 expected_items            (loader.py 上列邏輯)
  → ruleset.order_index(item) = None (contracts.py order_index 查表失敗)
  → _greedy_monotonic 視為 unknown id 並丟棄 (segmenter.py:54-55: `if idx is None or idx <= last: continue`)
  → 該位置不產生錨界
  → 前一個被接受的 item 的 span 延伸至下一個「被接受」的錨
  → 該 CONDITIONAL item 的標題與內容被前項 span 沉默吞併
```

實跑確認：`9C in modern expected_items? False`、`16 in modern expected_items? False`。

### 2.2 實證：APA【實測】
對 `tests/fixtures/real/apa_10k_fy2023_merged12.htm.gz` 跑完整 pipeline：

| 項目 | 實測值 |
|---|---|
| 9C 錨位置（決策前錨流中存在） | char **166989** |
| item 9B 的最終 span | **[166473, 167068)** |
| → 9C 錨是否落在 item 9B 的 span 內？ | **True（被吞併）** |
| 16 錨位置（決策前錨流中存在） | char **177411** |
| item 15 的最終 span | **[168094, 177445)** |
| → 16 錨是否落在 item 15 的 span 內？ | **True（被吞併）** |
| `'9C'` 是否在最終 item 集合？ | **False** |
| `'16'` 是否在最終 item 集合？ | **False** |
| APA `filing_status` | **PASS**（item_count = 21） |

**兩個 CONDITIONAL item 的內容被前項吞併，最終 item 集合中不存在，而 filing 通過全部不變量、判為 PASS、無任何 violation。**

### 2.3 定性
這是**設計層的系統性沉默失敗**：
- 結構完整（不重疊、覆蓋、順序皆成立 → 全部不變量 PASS）
- 語義錯置（9C 的內容被計入 9B；16 的內容被計入 15）
- **無任何機制舉手**

與 `VALIDATION_part_1.md` §6 記載的 MSFT FY1994 Item 14 案例**同族**（結構完整、語義錯置、不變量抓不到），但性質更嚴重：
- MSFT Item 14 是**單點的 part 判錯**（已修）。
- 本案是**設計層的系統性缺陷**：**任何印出 9C 或 16 的 filing 都會中招**，且中招後仍判 PASS。

這也直接說明了為何 §1.6 的「Item 4 不可改為 CONDITIONAL」——CONDITIONAL 這個分類本身就是這個沉默失敗的來源。

### 2.4 影響面【推論】
KKR 的決策前錨流中確實含有真 9C 錨（char 1089378）【實測】。因此 KKR 【推論】亦受此缺陷影響。

但**除 APA 外，未逐檔實測確認**其他檔的 9C/16 吞併情形（未對每檔跑 span-level 比對）。標【推論】而非【實測】的理由：其他檔的 item 數形狀與此缺陷吻合，但「形狀吻合」不等於「已驗證吞併」，須逐檔比對 9C/16 錨位置與前項 span 才能升格。

### 2.5 修法方向【推論】
與 Item 4 **同構**：正解為引入一個「**留在 `expected_items`（因而有 `order_index`、有印照收、照切 span）但允許缺席（因而缺席時 `should_exist` 不舉旗）**」的中間分類。現行的四態（REQUIRED / RESERVED / ABSENT / CONDITIONAL）缺這一態；`allowed_absences` 機制實際上已提供此語意，只是 CONDITIONAL 沒有走這條路。

**本輪不修，記錄為獨立工項。** 理由【實測】：修正後 9C/16 會成為獨立 item，將**變動多檔的 item 數與 span 邊界**，直接衝擊 `tests/test_part_era_regression.py` 中 13 份 fixture 的 `(item_id, part)` 序列基線（該檔註明「Baselines below are pre-fix real pipeline outputs; do not edit them.」）。此為獨立且有回歸足跡的工程，須單獨測試先行。

---

## 3. 發現三：繼承自動機（inheritance automaton）與其行為保守性實測

### 3.1 設計動機【實測】
現行 `_greedy_monotonic`（`segmenter.py:41-58`）的接受條件是**弱條件**：只要求 `order_index` 嚴格遞增。

```python
def _greedy_monotonic(anchors, ruleset):
    accepted = []; last = -1
    for a in anchors:
        idx = ruleset.order_index(a.item_id)
        if idx is None or idx <= last:   # unknown id, or backward/repeat -> drop
            continue
        accepted.append(a); last = idx
    return accepted
```

此條件對「**向前跳的假錨**」零抵抗：任何 `order_index` 大於當前值的假錨都會被接受，並把 `last` 推高，導致其後所有真錨（`order_index` 較小）被連鎖丟棄。KKR 的假 Item 10 正是此類。

升級構想：把接受條件從「順序遞增」強化為「**只接受 ruleset 允許的合法繼承者**」——即當前狀態下，依 ruleset 的合法 item 序列，下一個「可以合法出現」的 item 集合（`allowed_next`）。

### 3.2 規格（本輪 scratchpad 原型）
狀態：`last_idx`（初始 -1）、`consumed`（初始空集合）。逐錨處理：

```python
def inheritance_automaton(anchors, ruleset, extra_skippable=frozenset()):
    expected = ruleset.expected_items
    permitted_absent = set(allowed_absences(ruleset)) | set(OPTIONAL_ITEMS) | set(extra_skippable)
    last_idx, consumed, accepted = -1, set(), []
    for a in anchors:
        idx = ruleset.order_index(a.item_id)
        if idx is None:                       # unknown id -> 丟棄（與舊規則同等，行為保守性要求）
            continue
        # 計算 allowed_next：從 last_idx+1 沿 expected 走
        allowed_next, j = [], last_idx + 1
        while j < len(expected):
            item = expected[j]
            if item in consumed:              # 已被消費（含被 merge 吸收）-> 跳過續走
                j += 1
                continue
            allowed_next.append(item)
            if item not in permitted_absent:  # 硬邊界「必須出現」-> 收錄後停止
                break
            j += 1
        if a.item_id in allowed_next:         # 接受
            last_idx = idx
            consumed.add(a.item_id)
            if a.merged_id is not None and a.merged_id in expected:
                consumed.add(a.merged_id)     # merge 吸收項亦計入 consumed
            accepted.append(a)
        # else 丟棄
    return accepted
```

三個設計要點：
- **`allowed_next` 的硬邊界**：沿 `expected_items` 前進，遇到「不可缺席」的 item 就停——它是一道牆，其後的 item 在此狀態下不是合法繼承者。這正是擋掉 KKR 假 Item 10 的機制（接受真 7A 後，牆立在 Item 8，`10` 不在 `allowed_next` 內）。
- **`consumed` 的 merge 處理**【實測依據】：APA 的 `Items 1 and 2` 在錨層是**單一 anchor**（`item_id='1'`, `merged_id='2'`, `is_plural=True`, start=12526，heading 原文 `'ITEMS 1 and 2.\nBUSINESS AND PROPERTIES...'`），item 2 不會有自己的錨。故接受此錨時須把 `merged_id` 一併加入 `consumed`，否則後續 `allowed_next` 會卡在「等待 item 2 出現」。
- **unknown id 與舊規則同等丟棄**：刻意保留 `idx is None → 丟棄` 的行為，以維持行為保守性（不在同一次變更中同時改變兩種行為）。**副作用：§2 的 9C/16 吞併問題在新規則下依然存在**——新規則不解決發現二。

### 3.3 離線雙自動機模擬器：方法
在**不動任何 pipeline code** 的前提下實測回歸面：

1. 對全部 24 份 fixture，用 pipeline 實際路徑取得「**決策前錨流**」：`build_ruler` → `find_anchors` → 套用 segmenter 的 front 排除（`_in_any(a.enum_start, front)`，`front` 取自 `ruler.residual_candidates` 的 COVER_PAGE / TOC）。
2. 把**同一條**錨流同時餵給：(a) `import` 的實物 `_greedy_monotonic`；(b) scratchpad 中的新規則原型。
3. 逐錨 diff 兩邊的接受清單。

> **待交叉核對項**：front 排除的**判定謂詞** `_in_any` 為 import 實物；但「從 `residual_candidates` 選出 COVER_PAGE/TOC 區段」的 2 行資料選取 comprehension 係比照 `segmenter.py:139-143` 在 scratchpad 中重建（非 import）。此段若與實際 segmenter 行為有出入，模擬結果需重驗。

#### 3.3.1 上述待核對項的獨立佐證【實測】

**驗算邏輯**：若 scratchpad 重建的 front 排除與實際 segmenter 一致，則模擬器的「**舊規則接受錨數**」應對得上真實 pipeline 記錄的「**item 數**」。兩者的預期關係為：

```
item 數 = 舊規則接受錨數 + (帶 merged_id 的被接受錨數)
```

差額來自 merge：`Items 1 and 2` 在錨層是**單一 anchor**，但在 span assembly 時會 materialize 成**兩個 Item**（代表項持 span、被吸收項無 span）【實測，見 §3.2】。故無 merge 的檔應**完全相等**，有 merge 的檔應**恰好 +1**。

**對帳表**（「記錄 item 數」取自既有文件；「舊規則接受錨數」取自本輪模擬器實跑；兩者為獨立來源）：

| 檔案 | 記錄 item 數 | 來源 | 舊規則接受錨數（本輪實跑） | 差額 | 判定 |
|---|---|---|---|---|---|
| AAPL | 20 | `VALIDATION_part_1.md` §4.1 | 20 | 0 | ✅ |
| NKE | 20 | 同上 | 20 | 0 | ✅ |
| PG | 20 | 同上 | 20 | 0 | ✅ |
| JPM | 21 | 同上 | 21 | 0 | ✅ |
| TSLA | 21 | 同上 | 21 | 0 | ✅ |
| WMT | 21 | 同上 | 21 | 0 | ✅ |
| PLD | 21 | 同上 | 21 | 0 | ✅ |
| NEE | 21 | 同上 | 21 | 0 | ✅ |
| **DVN** | **21** | 同上 | **20** | **+1** | ✅ **差額來自 merge**（`Items 1 and 2`；§4.2 明載「1&2 merge 正確」） |
| BRK-B | 16 | 同上 | 16 | 0 | ✅ |
| PFE | 19 | 同上 | 19 | 0 | ✅ |
| INTC | 21 | `DIAGNOSIS_r2_failures.md` §2.1 | 21 | 0 | ✅ |
| C | 0 | 同上 §3.1 | 0 | 0 | ✅ |
| KKR | 17 | 同上 §4.1 | 17 | 0 | ✅ |
| **APA** | **21** | 本輪 `run_pipeline` 實跑 | **20** | **+1** | ✅ **差額來自 merge**（`Items 1 and 2`，單一 anchor + `merged_id='2'`） |
| MSFT FY1994 | 14 | 本輪 `run_pipeline` 實跑 | 14 | 0 | ✅ |

**結果：16 檔全數對上，無任何一檔對不上。** 兩個 +1 差額（DVN、APA）恰為兩份已知的 `Items 1 and 2` 合併檔，與預期完全吻合。

**額外的跨輪交叉驗證【實測】**：本輪模擬器獨立測得的 KKR 假 10 @ **623410**、真 10 @ **1089469**，與 `DIAGNOSIS_r2_failures.md` §4.2 記載的「假 10 @ 623,410」「真 10 @ 1,089,469」**逐字吻合**；INTC 的 `ruler.text` 長度 **493929** 亦與 r2 §2.2 記載的 493,929 吻合。這是兩輪、兩套腳本、獨立取得的相同座標。

**結論【佐證，非證明】**：
- 此對帳**將 §3.3 待交叉核對項的風險由「未緩解」降為「已佐證」，而非「已排除」。**
- 理由：item 數吻合只證明**數量相同**，**不證明逐錨位置相同**。理論上仍可能存在「兩個互相抵消的錯誤」（例如重建的 front 區段偏移，導致少排除一個假錨、又多排除一個真錨，總數不變）。要真正排除，須逐錨比對模擬器的接受清單與 pipeline 實際產出的 item span 起點——**本輪未做此比對**。
- 但考量到 16 檔（涵蓋 5 種 era、含 merge / IBR / FAILED / 0-錨 等多種形態）全數對上、且兩個差額精確落在唯二的 merge 檔上，「重建的 front 排除與實際 segmenter 不一致」這個風險已顯著降低。

### 3.4 中途發現：第一版模擬器在 PFE 上死鎖【實測】——本輪方法論的關鍵事件
第一版模擬（未對 Item 4 做任何假設）跑出**兩個**差異檔，而非預期的一個：

| 檔案 | 舊規則接受數 | 新規則接受數 | 判定 |
|---|---|---|---|
| pfe_10k_20251231 | 19 | **5** | 預測外差異 |
| kkr_10k_20251231 | 17 | 21 | 預期內差異 |

PFE 實測：新規則接受 `1@40418, 1A@131416, 1C@218509, 2@225478, 3@227096` 後**完全卡死**，其後 14 個真 item（5, 6, 7, 7A, 8, 9, 9A, 9B, 10, 11, 12, 13, 14, 15）全遭誤丟。

死鎖機制【實測】：PFE 的決策前錨流中**不存在 Item 4 錨**（亦不存在 1B 錨）。接受 `3`（`order_index=5`）後，`allowed_next` 從 `j=6` 起走：`expected[6] = '4'`，`'4'` 不在 `consumed`、也不在 `permitted_absent` → 命中硬邊界 → **收錄 `'4'` 後 break** → `allowed_next = ['4']`。但 Item 4 的錨永遠不會到來 → `last_idx` 永遠停在 5 → 其後每個錨算出的 `allowed_next` 恆為 `['4']` → 全數拒收。

**這是本輪方法論最重要的事件**：
- 這個洞**在動任何 pipeline code 之前**就被離線模擬器攔下。若直接改 `segmenter.py` 再跑測試，症狀會是「PFE 從 1 個 violation 暴增成大量 violation」，除錯方向極可能被誤導到自動機邏輯本身。
- 更關鍵的是，它**反向定位到 §1 的 ruleset 缺陷**：新規則不是寫錯了，而是它**忠實執行了一個錯誤的 ruleset**。舊規則因為條件太弱，反而「意外容忍」了這個 ruleset 錯誤（`5` 的 `order_index=7 > 5`，照收不誤）。
- **教訓：強化接受條件會把 ruleset 的建模錯誤從「無害」變成「致命」。** 這確立了 §8 的依賴關係——ruleset 分類修正**必須**先於繼承自動機。

### 3.5 結果：在「Item 4 已可跳過」假設下的重跑【實測】
把 `'4'` 加入新規則的可跳集合（比照「Item 4 已移入 `allowed_absences`」的假設情境；**此為模擬器內的假設，未修改任何 repo code**），重跑全部 24 檔：

**24 檔中 23 檔的接受清單逐錨完全一致；唯一差異為 KKR。**

三個預測全數命中：

| 預測 | 內容 | 實測 |
|---|---|---|
| 1 | PFE 新規則恢復與舊規則完全一致（19 個） | ✅ 成立（old=19, new=19，序列完全相同） |
| 2 | KKR 差異維持原形狀，不受此假設影響 | ✅ 成立 |
| 3 | 其餘 22 檔維持完全一致，無任何新差異 | ✅ 成立（預測外差異檔 = 空集合） |

### 3.6 KKR 逐錨差異表【實測】
KKR（era_2023，決策前錨數 26）：

舊規則接受（17）：
```
1@24316  1A@104674  1B@385506  1C@385543  2@390922  3@391239  4@391518
5@391578  6@398832  7@398854  7A@621249  10@623410  11@1126197  12@1174550
13@1181483  14@1210993  15@1213589
```
新規則接受（21）：
```
1@24316  1A@104674  1B@385506  1C@385543  2@390922  3@391239  4@391518
5@391578  6@398832  7@398854  7A@621249  8@662958  9@1085222  9A@1085318
9B@1089349  10@1089469  11@1126197  12@1174550  13@1181483  14@1210993  15@1213589
```

逐錨差異：

| 差異方向 | item | char 位置 | order_index | 說明 |
|---|---|---|---|---|
| **舊收新丟** | 10 | **623410** | 15 | **假 Item 10**（引用式假錨，向前跳） |
| 舊丟新收 | 8 | 662958 | 11 | 真 Item 8 |
| 舊丟新收 | 9 | 1085222 | 12 | 真 Item 9 |
| 舊丟新收 | 9A | 1085318 | 13 | 真 Item 9A |
| 舊丟新收 | 9B | 1089349 | 14 | 真 Item 9B |
| **舊丟新收** | 10 | **1089469** | 15 | **真 Item 10** |

**差異方向為修正**：新規則拒掉假 10、救回真 8/9/9A/9B 與真 10。舊規則因接受假 10 而把 `last` 推到 15，導致其後 `order_index` 為 11–14 的真錨全被連鎖丟棄。

（補充【實測】：KKR 錨流中另有 `7@635753`、`7@642446`、`9C@1089378`、`16@1247395` 等錨，兩規則皆丟棄——前兩者為重複的 7、後兩者為 unknown id。）

### 3.7 模擬器的邊界 —— 必須明確寫出
**模擬器只驗證「接受規則」這一段（`_greedy_monotonic` 的替換）。**

**未驗證**（模擬器完全沒碰）：
- span 切割（`_first_cut`、part divider / signatures 的裁切）
- `status` 判定（RESERVED / INCORPORATED_BY_REFERENCE / MERGED / EXTRACTED）
- residual 分類與 `_fill_gaps`
- 任何 invariant 的結果
- 最終 `filing_status` / `filing_confidence`

因此：「23 檔接受清單逐錨一致」→【推論】其下游輸出（span、status、invariant、filing_status）亦不變。**此推論未經驗證**，理由：接受清單相同確實蘊含 `starts` 陣列相同，【推論】span 計算的輸入相同故輸出相同；但這條推理鏈未實跑驗證，且 KKR 那一檔的下游輸出必然改變（多了 5 個 item、span 邊界重排）。**須待真正動 `src/` 後跑全套回歸（含 `tests/test_part_era_regression.py` 的 13 份基線）才能證實。**

### 3.8 對 `DIAGNOSIS_r2_failures.md` §5.2 否決的影響
§5.2 以兩個理由否決「換演算法」：
1. 「**爆炸半徑巨大**（第一輪 125 test 與全部 PASS 檔皆依賴此核心）」 → **【實測推翻】** 實測爆炸半徑為**一檔**（KKR），其餘 23 檔接受清單逐錨不變，且該一檔的變化方向為修正。（**但此推翻受 §3.7 邊界限制**：實測的是接受規則層，非全下游。）
2. 「**KKR 已正確 loud fail、無答案鍵驗證『修對』**」 → 見 §5 的驗證標準修正。
3. （§5.2 另有「**非最小修**」一語）→ **此點未被推翻**：繼承自動機確實不是最小修。

**精確結論**（三個理由須分別處置，不可一概而論）：

| §5.2 的否決理由 | 本輪狀態 | 性質 |
|---|---|---|
| 「爆炸半徑巨大」 | **【實測推翻】**（23/24 檔接受清單逐錨不變） | 曾是**決定性否決事由** → 已失效 |
| 「無答案鍵驗證『修對』」 | **已由 §5 的驗證標準修正解決**（KKR 不需逐筆 GT；r1 對 8 份無 GT 檔的標準即為「結構不變量 + head+tail 抽查」，要求 KKR 更高標準屬雙重標準） | 曾是**決定性否決事由** → 已失效 |
| 「非最小修」 | **仍然成立**（繼承自動機確實不是最小修） | **成本考量，非否決事由**——它描述的是代價，不是「不可為」 |

**→ 正確結論是：「§5.2 的兩個決定性否決理由已失效 → 決策重開」，而非「§5.2 的否決不再成立」。**

「非最小修」這一條並未被推翻，它作為**成本項**仍應計入決策；但成本高不等於否決——否則任何架構性修正都將永遠無法進行。真正的問題已從「**能不能做**」轉為「**值不值得做、以及以什麼順序做**」。

仍待決之事：SEC grounding（§1.4）、Item 4 的前置修正（§8.1 的硬依賴）、全下游回歸（§3.7 的未驗證範圍）、以及「是否值得為單一檔案（KKR）承擔核心演算法變更」這個**成本/效益判斷**——後者正是「非最小修」一條所指向的、尚未被回答的問題。

---

## 4. 發現四：INTC 標題字串 fallback 假設，經實測否證

### 4.1 背景
本輪曾提出一個 fallback 假設：「當 inv 9（cover_dominance）觸發時，改用章節標題字串（Business / Risk Factors 等）切割 INTC」。

### 4.2 實測否證【實測】
對 `tests/fixtures/eval_recent_r2/intc_10k_20251227.htm.gz` 跑 pipeline 實際的 Stage-1（`build_ruler`），得 `ruler.text` 長度 = **493929**（與 r2 診斷記載的 493,929 一致）。在此 `ruler.text` 上做不分大小寫全文搜尋：

| 候選標題字（對應 Item） | 出現次數 | 訊號品質 |
|---|---|---|
| Business (1) | **233** | 散文中大量出現 |
| Risk Factors (1A) | **7** | 全為句中 cross-reference |
| Unresolved Staff Comments (1B) | **1** | 唯一命中 @ 491259 |
| Cybersecurity (1C) | 32 | 叢集於 ~217k–282k + 散落 |
| Properties (2) | 2 | — |
| Legal Proceedings (3) | 5 | 含文末索引 @ 491327 |
| Mine Safety (4) | **1** | 唯一命中 @ 491367 |
| Market for Registrant (5) | **1** | 唯一命中 @ 491408 |
| Management's Discussion (7) | **1** | 唯一命中 @ 491554 |
| Quantitative and Qualitative (7A) | 3 | — |
| Financial Statements (8) | **115** | 散文中大量出現 |
| Changes in and Disagreements (9) | **1** | 唯一命中 @ 491801 |
| Controls and Procedures (9A) | 4 | — |

「Business」前 10 次出現的 context 樣本【實測】——**無一為章節標題，全為散文**：
```
#1 @ 4670:  ...how we organize and manage our business. See "Form 10-K Cross-Reference Index"...
#3 @ 6617:  ...statements regarding:\n▪our business plans and strategy and anticipated benefits...
#7 @ 8980:  ...and export controls, and their potential impact on our business;\n▪tax- and accounting...
#9 @ 12218: ...disclose risks and uncertainties that may affect our business. \nUnless specifically...
```
「Risk Factors」全 7 次出現【實測】——**無一為獨立標題，全為句中引用或索引列**：
```
#1 @ 83811:  ...For a discussion of IP-related risks, see "Risk Factors" within Risk Factors...
#3 @ 96020:  ...Climate Transition Action Plan and "Risk Factors" within this Form 10-K...
#5 @ 173533: ...could decline. These risk factors do not identify all risks that we face...
#7 @ 277734: ...See "Risk Factors" for more information on our cybersecurity risks...
```

**關鍵事實【實測】**：可辨識的多字標題（Unresolved Staff Comments / Mine Safety / Market for Registrant / Management's Discussion / Changes in and Disagreements）**各僅出現 1 次**，且全部集中於 char **491098–491801** 區間——即文末的「Form 10-K Cross-Reference Index」索引表區段（`ruler.text` 全長 493929，此區段落在最後約 2.8k 字元內）。**這些唯一命中不是章節本體的標題，而是索引表的列。**

### 4.3 結論
確定性標題字串切法對 INTC 只有兩種下場【實測】：
- **常見字**（Business 233 次、Financial Statements 115 次）→ 產生數百個假陽性，無從篩選。
- **可辨識字**（多字專有標題）→ 唯一命中落在**錯誤位置**（文末索引表），切出來的是索引列而非章節。

**INTC 的方法邊界由【推論】升格為【實測】。** 現行行為（inv 9 大聲拒絕）即正確行為。

### 4.4 此提案另有兩個獨立否決理由（即使實測結果相反亦不成立）
1. **違反 CLAUDE.md 鐵律 2**：「切割錨點 = item 編號 + 順序，**不是**標題字串」。`DIAGNOSIS_r2_failures.md` §5.2 已明文封死此方向（「改 anchor 去比對標題主題字串（Business/Risk Factors）以救 INTC/C：違反『錨點=編號+順序，絕不用標題字串』。**封死。**」）。
2. **INTC 無 GT，無法測試先行**：沒有答案鍵，無從驗證「切對了」。

**→ 此提案的否決是三重的（鐵律 + 無法驗證 + 實測無訊號），任一條單獨成立即足以否決。**

（附帶記錄：§5.2 同時封死了「用文末索引表當結構圖反推正文」——本輪 §4.2 的實測正好說明為何：INTC 的可辨識標題**只**存在於該索引表中，任何想用它的方案都等於在用「Item→標題」對應定位，繞道違反 enumerator 契約。）

### 4.5 方法論意義
此為「**提出假設 → 設計可否證 probe → 實測推翻自己的想法**」的完整案例。假設是本輪自己提出的，probe 是為了給它最好的機會而設計的（直接數標題字在真實 ruler 上的分布），結果是乾淨的否證。**記錄此案例的價值不亞於記錄成功的修復。**

---

## 5. 修正：KKR 的驗證標準（先前高估）

### 5.1 先前立場
KKR 需**人工逐筆 ground truth** 才能驗證修復（此標準隱含於 `DIAGNOSIS_r2_failures.md` §5.2 的「無答案鍵驗證『修對』」）。

### 5.2 修正依據
依 `VALIDATION_part_1.md` §2.3（head+tail 人工抽查）與 §4（近年檔結果總表），**r1 對 8 份無 GT 檔所採用的驗證標準即為「結構不變量 + head+tail 人工抽查」**，而非逐筆 GT。

**→ 要求 KKR 達到更高的標準（逐筆 GT）屬雙重標準。** 若 head+tail 抽查足以驗證 8 份無 GT 檔的正確性，它也應足以驗證 KKR——除非 KKR 的病灶性質特殊（見 §5.3 (c)）。

### 5.3 修正後的驗證標準
(a) **結構層紅燈測試**：現行演算法下 KKR 必紅、修復後轉綠（測試先行）。
(b) **修復後 head+tail 逐項抽查**：與 r1 對其他無 GT 檔的標準一致。
(c) **額外加驗（因 KKR 病灶特殊）**：KKR 的病灶是 **span 中段吞併**（假 Item 10 導致 item 7A 的 span 從 621249 一路延伸、吞掉真 8/9/9A/9B），**不是頭尾錯誤**。head+tail 抽查在設計上抓不到中段錯誤。故須**加驗 span 內部的關鍵座標**：

| 加驗項 | 座標（本輪實測的錨位置） | 修復後應成立的斷言 |
|---|---|---|
| 真 Item 8 錨 | char **662958** | 應為 item 8 的**起點**（而非落在 item 7A 的 span 內） |
| 真 Item 9 錨 | char **1085222** | 應為 item 9 的起點 |
| 真 Item 9A 錨 | char **1085318** | 應為 item 9A 的起點 |
| 真 Item 9B 錨 | char **1089349** | 應為 item 9B 的起點 |
| 真 Item 10 錨 | char **1089469** | 應為 item 10 的**起點** |
| 假 Item 10 錨 | char **623410** | 應**落在某個 item 的 span 內部**（被正確視為引用文字），**不得**成為任何 item 的起點 |

> `TODO: 需重跑取得` — KKR 在**現行**演算法下的最終 item 清單、各 item span 範圍、`filing_status` 與 violation 明細，本輪**未實跑**（本輪只跑到錨層與接受清單）。上表的「修復後斷言」是依實測錨座標推導的檢查點【推論】，但「修復前的實際 span 長相」需重跑 `run_pipeline` 取得，才能寫出完整的紅燈測試。

### 5.4 邊界【依 `VALIDATION_part_1.md` §4.3 / §7.3】
`VALIDATION_part_1.md` §7.3 已記載抽查手法的邊界：head+tail 抽查**無法排除**「頭尾正常、中段夾入外來內容」的隱蔽錯誤。

§5.3 (c) 的加驗關鍵座標**可降低**此風險（因為它直接針對中段），但**不能歸零**：
- 加驗的是「錨座標是否成為 item 起點」，不是「span 內的每個字是否都屬於該 item」。
- 若存在第三個未被發現的假錨、或某段內容在兩個真錨之間錯置，此加驗抓不到。

**→ 修復後的 KKR 仍是「掙來的地板」，不是「證明正確」。** 這與 `VALIDATION_part_1.md` §8.2 的認識論定調一致。

---

## 6. 三案最終定位

| 案例 | 本輪定位 | 證據等級 | 處置 |
|---|---|---|---|
| **INTC** | **方法邊界，確定性方法無解。** 正文根本不存在 item 編號錨；可辨識標題僅存在於文末索引表（char 491098–491801）。標題字串 fallback 經實測否證（§4）。 | 【實測】（由 r2 的【推論】升格） | **現行行為（inv 9 大聲拒絕）即正確行為。不再投入。** |
| **C（Citigroup）** | 狀態**變更為【待實測】**。r2 原定位為「與 INTC 同源、無解」；本輪提出**裸編號錨點**的新可能（§7）。本輪實測：C 的原始錨數 = 0、決策前錨數 = 0。 | 【假設】（新方向未驗證） | **不定案。** 依 §7 的三段實測規劃執行後再定位。 |
| **KKR** | **唯一架構上可解之案。** 假錨劫持機制明確，繼承自動機的修法已有行為保守性實測支撐（23/24 檔逐錨不變，唯一差異方向為修正）。入場費經 §5 修正後下修（不需逐筆 GT）。 | 【實測】（接受規則層）+【推論】（下游） | **決策重開**（§3.8），但**須先完成 Item 4 前置修正**（§8）。 |

---

## 7. 待實測工項（明確標為假設，尚未執行）

### 7.1 Citi 裸編號錨點【假設】
**假設內容**：Citi 的 cross-reference index 使用**裸編號**（`1A.` / `2.` / `3.`），正文亦無 `"Item"` 前綴 → 現行 `find_anchors` 的 regex 命中 0 個 → `find_anchors = 0`。放寬錨點的**詞法形式**以接受裸編號，可能救回 C。

**現行 `_ANCHOR` regex 原文**（取自 `src/sec10k/segment/anchors.py`，verbatim；注意實際路徑為 `segment/anchors.py`，非 `sec10k/anchors.py`）：

```python
_ANCHOR = re.compile(
    # The optional item letter must be ATTACHED to the number ("1A", no space),
    # otherwise the letter group would swallow the "A" of "1 AND 2" and misread a
    # merged heading as item "1A".
    r"(?im)^[^\S\n]*(items?)[^\S\n]+(\d{1,2})([a-z])?"
    r"(?:[^\S\n]+and[^\S\n]+(\d{1,2})([a-z])?)?"
    r"\b[^\S\n]*[.:–—-]?",
)
```

**原文與先前轉述版本（`^\s*(items?)\s+\d`）的差異**【實測】：

| 面向 | 轉述版本 | regex 原文 | 是否實質差異 |
|---|---|---|---|
| 空白字元類 | `\s`（含換行） | `[^\S\n]`（**僅水平空白，明確排除換行**） | **是**：原文要求 `Item` 與編號**必須在同一行**；轉述版本會誤讓人以為可跨行 |
| flags | 未標示 | `(?im)`：ignorecase + **MULTILINE**（`^` 為行首而非文首） | **是**：轉述版本未標示，易誤解為僅比對文首 |
| 編號位數 | `\d`（單位數） | `\d{1,2}`（1–2 位數） | **是**：轉述版本過窄，實際可比對 `10`–`16` |
| 字母後綴 | 未表達 | `([a-z])?` **緊貼**數字（`1A`，不可有空白） | 轉述版本遺漏 |
| 合併形式 | 未表達 | `(?:[^\S\n]+and[^\S\n]+(\d{1,2})([a-z])?)?`（`Items 1 and 2`） | 轉述版本遺漏 |
| 尾綴標點 | 未表達 | `\b[^\S\n]*[.:–—-]?`（可選的 `.` `:` 破折號） | 轉述版本遺漏 |
| **`items?` 字面詞為必要** | **有**（`(items?)` 非可選群組） | **有**（`(items?)` 非可選群組） | **無差異——此為關鍵項** |

**重新檢視「Citi 為何 0 錨」的敘述是否仍成立**【實測】：**仍然成立，且理由更明確。** 上述所有差異都發生在「`Item` 這個字之後」的細節（空白類、位數、後綴、標點），而 `(items?)` 這個**字面詞群組在 regex 中是必要的、非可選的**——任何候選字串若不含字面的 `item` / `items`，無論其後編號寫成什麼樣子，都**不可能**匹配。因此裸編號（`1A.` / `2.`）在現行 regex 下必然命中 0 次，與轉述版本的結論一致。

**但差異對 §7.1 的修法規劃有實質影響**：放寬 regex 以接受裸編號，等於要把 `(items?)` 從**必要**改為**可選**（例如 `(?:(items?)[^\S\n]+)?`）。這是對 regex 的**核心約束**動刀，而非邊緣調整——`(items?)` 正是現行設計中「排除一般數字清單」的唯一屏障。這使 §7.1 的「最大風險」（對全部 24 檔開放新候選錨）比原先評估的**更高**，也更凸顯三段實測規劃中第 3 步（其餘 23 檔回歸面預檢）作為 go/no-go 閘門的必要性。

證據狀態：
- 【實測，本輪】C 的原始錨數 = **0**、決策前錨數 = **0**、舊/新規則接受數皆為 **0**。
- 【實測，r2 非本輪】`DIAGNOSIS_r2_failures.md` §3.4 記載此根因已於 2026-07-03 結案為「裸編號索引 + 正文無 Item N」。
- 【假設】「放寬 regex 可救回 C」——**完全未驗證**。

**鐵律相容性論證**：裸編號（`1A.`）**仍然是 item 編號**，不是標題主題字串。故此方向屬「**放寬編號的書寫形式**」（詞法層），而非「**改變判準的類別**」（從編號改為標題）。與 §4 的 INTC 標題字串提案有**本質區別**：後者違反鐵律 2，前者不違反。

**風險【假設】**：
- 帶字母的編號（`1A.` / `7A.` / `9B.`）辨識度可能較高（字母後綴罕見於一般清單）。
- **裸數字（`8.` / `3.`）可能與財務附註編號、表格列號、頁碼、條列清單大量撞車。**
- modern era 的 item 中僅少數帶字母後綴（`1A/1B/1C/7A/9A/9B/9C`；其餘 `1,2,3,4,5,6,7,8,9,10..16` 皆為裸數字）→ **無法只靠字母後綴解決，必須正面處理裸數字的歧義。**

**最大風險【假設】**：放寬 regex 會對**全部 24 檔**開放新的候選錨（regex 是全域的，不是 per-file 的）。故真正的門檻不是「能不能救 C」，而是「**救 C 的代價是否為污染其餘 23 份現行乾淨的檔**」。

**三段實測規劃**（唯讀，依序執行）：
1. **Citi 候選錨盤點與 context 分類**：在 C 的 `ruler.text` 上以放寬的 regex 掃出全部候選錨，逐一分類（真章節標題 / 索引列 / 附註編號 / 表格 / 其他）。目的：確認裸編號假說成立，並量化歧義密度。
2. **餵入繼承自動機**：把 C 的候選錨流餵給繼承自動機，看接受序列是否收斂為合法的 item 序列。目的：測試「強接受條件能否從高噪音錨流中撈出正確結構」——這正是繼承自動機相對 `_greedy_monotonic` 的理論優勢所在。
3. **其餘 23 檔的回歸面預檢**：對其餘 23 檔跑放寬 regex，用**離線雙自動機模擬器**（§3.3 的同一手法）比對接受清單是否維持不變。**這一步是 go/no-go 閘門**：若放寬 regex 污染了現行乾淨檔，此方向即告終止。

### 7.2 Stage-1 保真度升級【假設】
**僅當 §7.1 證明「純文字層面無解」（即 ruler.text 中確實不存在足以定位章節的編號訊號）時才考慮。**

- **爆炸半徑最大**：`ruler` 的 char 座標是**所有 span、所有 GT 斷言、所有測試基線的參照系**。改變 Stage-1 的正規化 = 改變座標系 = 所有既有斷言全部失效。
- **明確記錄【實測依據 §4.2】：此方向不能救 INTC。** INTC 的問題**不是**「標題在但格式訊號被 Stage-1 洗掉」，而是「**正文根本沒有 item 標題**」（可辨識標題只存在於文末索引表）。無論 Stage-1 保真度多高，都無法從不存在的東西中還原結構。**任何把 Stage-1 升級當成 INTC 解方的提案，都與 §4.2 的實測直接矛盾。**

---

## 8. 工項優先序與依賴關係

| # | 工項 | 前置條件 | 回歸足跡 | 需 GT？ | 風險 |
|---|---|---|---|---|---|
| **1** | **Item 4 ruleset 修正**（逐 era，移入 `allowed_absences`） | **SEC grounding（§1.4）—— 硬閘門，無出處不得動工**；逐 era 分別論證（§1.5） | 小：【推論】僅 PFE 由 FAILED→PASS；22 份有印 Item 4 的檔【實測】接受清單不變 | 否 | **中**（風險全部集中在 grounding；grounding 錯 → 把真陽性改成偽陰性） |
| **2** | **9C/16 分類修正**（引入「在 expected_items 但可缺席」的中間態） | 需先設計新的 expectation 態或改走 `allowed_absences` 路徑 | **大**：9C/16 成為獨立 item → 變動多檔 item 數與 span → 直接衝擊 `test_part_era_regression.py` 的 13 份基線 | 否（結構層可驗） | **中高**（回歸足跡大，但方向明確、且修正的是一個已實測的沉默失敗） |
| **3** | **繼承自動機**（替換 `_greedy_monotonic`） | **硬相依工項 1**（見下）；§5.3 的紅燈測試；`TODO: 需重跑取得` KKR 現行 span 基線 | 中：【實測】23/24 檔接受清單不變；KKR 一檔改變（方向為修正）。**下游（span/status/invariant）未驗證（§3.7）** | 否（依 §5 修正後標準） | **中**（實測支撐強，但屬核心演算法變更、非最小修） |
| **4** | **Citi 裸編號實測**（§7.1 三段規劃） | 無（唯讀探查即可啟動） | 唯讀階段：零。若後續真要放寬 regex → **潛在最大**（全域 regex 影響 24 檔） | 否 | **低**（探查階段）／ **高**（若進到改 regex） |

### 8.1 硬依賴：工項 1 必須先於工項 3
**繼承自動機對 ruleset 分類有硬相依**——其 `allowed_next` 的可跳集合直接由 `allowed_absences(ruleset) | OPTIONAL_ITEMS` 導出（§3.2 的 `permitted_absent`）。

**【實測證據】**：在**未**修正 Item 4 的情況下直接導入繼承自動機，PFE 會**死鎖**——新規則卡在 `allowed_next = ['4']`，誤丟其後 14 個真 item，接受數由 19 崩到 5（§3.4）。

**→ 若先做工項 3、後做工項 1，PFE 會從「1 個 violation」惡化為「大規模誤丟」。順序不可調換。**

### 8.2 建議順序
1. **工項 4 的唯讀探查階段**（零風險、可立即啟動、且其結果會影響 C 的最終定位）。
2. **工項 1 的 SEC grounding**（硬閘門；grounding 完成前，工項 1 與工項 3 皆凍結）。
3. **工項 1 的實作**（測試先行、逐 era）。
4. **工項 3**（在工項 1 完成後；須先補齊 §5.3 的 KKR 紅燈測試與現行 span 基線）。
5. **工項 2**（獨立，可與上述並行排程，但因回歸足跡大，建議單獨一輪）。

---

*本檔為 r3 唯讀探查的診斷紀錄。全程未修改任何 pipeline code、未修改任何既有文件。所有具體數字取自本輪 scratchpad probe 的實跑輸出。修法方向為分析建議，任何 code 變更均須依鐵律測試先行、全量回歸。*
