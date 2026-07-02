# 第二輪失敗案例診斷筆記（INTC / C / KKR）

> 本檔為第二輪擴大抽樣（tech 5 + finance 5）中 3 個 FAILED/可疑案例的根因診斷紀錄。
> 診斷方法：症狀（runner 輸出）→ 唯讀探查（看實際 char span / 錨點序列）→ 逐層剝到根因。
> 所有具體數字均來自對本地 fixture 的實跑探查，非估算。
> 本檔僅為診斷紀錄，不含任何 pipeline code 修改。修法方向見 §5，但落實須另行測試先行。

---

## 0. 範圍與證據層級（先講清楚，避免高估結論強度）

- 本輪 10 家 fixture 為近年真實 EDGAR 申報，**無答案鍵（no ground truth）**，屬 **Level-2 廣度延伸**（breadth extension），證據強度弱於 ground-truth 檔（第一輪的 MSFT FY1994 / MSFT FY2023 / APA FY2023）、強於空白。
- 因此本檔對「切得對不對」的判斷，依據的是 **SEC 10-K 結構常識**（例如 Item 1 Business 正文通常有數萬字、不該只有 138 字），並明確標示為「基於結構常識的推斷」，而非「對照答案鍵的證明」。
- 三家中，**只有 INTC 是 silent 失敗（通過全部不變量卻幾乎確定錯誤）**；C 與 KKR 均為 loud 失敗（gate 正確標紅）。這個區分決定了修法優先序（§5）。

## 1. 三家根因總表

三家各打破了 enumerator-anchor 契約的一個隱含假設：

| 案例 | 打破的假設 | 錨點狀況（實跑） | 分段結果 | gate 表現 |
|---|---|---|---|---|
| **INTC** | 「正文一定有 Item N 編號」 | find_anchors=23，全來自文末索引表 | 21 個假 item（全指向索引列） | **silent PASS（8/8）— 漏洞** |
| **C** | 「Item N 編號一定找得到」 | find_anchors=0（連 raw 去標籤也 0） | 0 個 item | loud FAILED（7/8，12 viol）— 正確 |
| **KKR** | 「行首的 Item N 一定是真標題」 | 真錨齊全，但被假錨劫持而誤殺 | 財報被吞、缺 8/9/9A | loud FAILED（6/8，4 viol）— 正確 |

**收斂觀察**：anchor 契約的三個假設（(1) 正文有編號、(2) 編號找得到且連續、(3) 行首編號是真標題）各被一家打破。第二輪金融/科技檔對 segmentation 的壓力測試因此比第一輪（8 家 PASS 的科技/消費檔）更到位。

---

## 2. INTC — 正文源頭無 Item N，pipeline 誤用文末索引表（silent PASS）

### 2.1 症狀（runner 輸出，實跑）
- `filing_status=PASS`、`invariants=8/8`、`items=21`，表面完全正常。
- 但 span 露餡：raw 3,320,720 bytes；21 個 item 全部擠在 char **491,090–492,575** 這約 1,500 字的窄帶內（item 1 len=138、1A len=22、1C len=11…）。前約 49 萬字正文完全未被納入任何 item。

### 2.2 逐層探查（實跑數字）
- **Stage-1 之後（ruler.text，全長 493,929）**：
  - `find_anchors` 共 23 個，**全部** `enum_start ≥ 491,090`。
  - 前段 char<491,090 的錨點總數 = **0**（佔全文 99.4% 的正文，一個行首 Item N 都沒有）。
  - 正文裡 `Item 1`（排除 Item 10~16、含大小寫）出現 = **0**；唯二的 `Item N` 樣式是 `Item 601(a)(5)-(6)`、`Item 601(b)(10)(iv)`（Regulation S-K 條文引用，非 10-K item 標題）。
  - `detect_toc` = None；Stage-1 將 [0,491,090) 整塊判為單一 `COVER_PAGE`。
- **Stage-1 之前（raw HTML，去標籤後純文字 627,836）**：
  - `Item 1/1A/1B/1C` 出現 = **4**，全部在 pos ~622,777+（純文字尾端），context 明確是文末「Item Number / Part I / Item 1. Business / Item 1A. Risk Factors / Item 1C. Cybersecurity」交叉索引表。
  - 正文的 `Business`、`Risk Factors` 全是純主題標題或句中 cross-reference，不帶列舉編號。

### 2.3 根因定性（乙-1：源頭即無，非 Stage-1 bug）
Intel FY2025 主文件正文**從頭到尾不帶 Item N 列舉字**，只在文末索引表列出「Item N → 頁碼」對應。`find_anchors` 在正文無錨可下，只能抓到末端索引表那 23 列完美遞增的 Item 1~16，誤當本體。

**崩壞機制（對照 code）**：
1. 正文無行首 Item N → `detect_cover_page`（toc=None 時 boundary=第一個行首 Item anchor）將 boundary 設在 491,090（末端索引表首列）→ Stage-1 自身將整份正文判為 COVER_PAGE [0,491,090)。
2. Stage-2：末端 23 個錨點不在 front 內 → 全送入 `_greedy_monotonic`，索引表 1→16 嚴格遞增完美通過 → 產出 21 個指向索引列的假 item。
3. `first_item=491,090`，其前已被 COVER_PAGE 佔用 → `_fill_gaps` 不再產 unclassified。
4. Gate 8/8 PASS：coverage OK、residual_sanity OK（COVER_PAGE 視為 benign）、should_exist OK（21 個 item id「都在」）。

**這是 gate 的 silent 放行閥**：`_emit_gap` 對 first-item 之前的 gap 一律給 benign COVER_PAGE，且 Stage-1 的 cover page 不設上限 → 一個佔全文 99.4% 的假 cover page，沒有任何硬不變量會舉手。

### 2.4 這是方法邊界，不只是 bug（重要）
法規並未硬性規定正文必須印出 Item N enumerator（法規規定的是揭露「內容」與「順序」，非排版形式）。Intel 不印 enumerator 於法規允許，屬「法規未禁止的呈現層變體」——這類變體**無法窮盡**，正對應本專案原則「結構/法規層可證明封閉、呈現層可估計但無法證明封閉」。

因此 INTC 的正解**不是**改 anchor 去比對標題字串（違反「錨點=編號+順序，絕不用標題字串」），而是**補 gate 紅旗讓其 loud fail + 記錄為已知邊界案例**。INTC 是「方法論誠實知道自己邊界」的活教材。

---

## 3. C（Citigroup）— 全文無可辨識 Item N 錨點（loud FAILED，gate 正確）

### 3.1 症狀（runner 輸出，實跑）
- `filing_status=FAILED`、`invariants=7/8`、`items=0`、12 個 `MISSING_EXPECTED_ITEM`（1,1A,2,3,4,5,7,7A,8,9,9A,15 全缺）、confidence=LOW。

### 3.2 逐層探查（實跑數字）— 「三重零」
- ruler.text = 1,056,191；raw = 16,150,764。
- `ruler.residual_candidates` **完全為空**（無 COVER_PAGE、無 TOC）— 與 INTC（有 491k 假 COVER_PAGE）截然不同。
- `find_anchors` = **0**；錨點分類統計全 0（落在 front=0、order_index=None=0、非front且order有效=0）。
- ruler.text 裡 `Item 1` = **0**；raw 去標籤後 `Item 1/1A/1B/1C` = **0**。

### 3.3 根因定性 + gate 正確性
C 與 INTC **不同**：C 是「三重零」（Stage-1 之後、Stage-1 之前、去標籤 raw 皆無 Item N），連文末索引表都沒有被當錨點。

**gate 運作正確**：完全無錨點 → `accepted=[]` → `should_exist` 對 12 個 expected item 全部舉手 → loud FAILED + LOW confidence。這正是「無法分段時誠實大聲失敗」的設計目標。**C 不是漏洞，是誠實失敗。**

**C 與 INTC 的對比本身是很好的 eval 材料**：同樣切不出正文，一個誠實失敗（C，錨點=0 → id 全不在 → 舉手）、一個假裝成功（INTC，索引表給了 21 個假 id → id 全在 → 放行）。真正的破口是 gate 的 `should_exist` 只檢查「item id 在不在」、不檢查「item 是否有實質內容/覆蓋率」。

### 3.4 未解點（明確標記為假設）
一份 16 MB 的 Citi 10-K，連去標籤 raw 都 0 個 Item N，本身反常。已排除：非 gate 丟棄（統計全 0）、非 Stage-1 剝除（去標籤 raw 獨立於 Stage-1 也是 0）、非 INTC 式索引表誤用。**剩餘最可能假說（未驗證）**：C-2「版式將 Item 與編號拆到不同表格 cell，中間夾其他可見文字，使 `item[\s]+1` 永遠配不到」。此假說**尚未探查證實**，且因對修法無決定性影響（C 已正確 loud fail、且無答案鍵可驗證「切對」）而暫列為已知未竟事項。

---

## 4. KKR — 引用式假錨向前跳，劫持 greedy-monotonic（loud FAILED，gate 正確）

### 4.1 症狀（runner 輸出，實跑）
- `filing_status=FAILED`、`invariants=6/8`、`items=17`、4 viol。
- 缺 item 8/9/9A；item 10 span 異常巨大 466,050 字（[623,410,1,089,460]）；一個 36,729 字 UNCLASSIFIED 殘留塊（[1,089,468,1,126,197]），卡在 item 10 與 11 之間。

### 4.2 逐層探查（實跑數字）— body 區有「兩個 Item 10」
- ruler.text = 1,248,574；raw = 20,008,121。Stage-1 有正常 COVER_PAGE [0,4119) + TOC [4119,5352)。
- `find_anchors` = 49。完整 item_id 序列分三段：
  - **idx 0–22**（全 in_front=True，前段 TOC）：1,1A,…,16 — 已被 front 正確排除。
  - **idx 23–34**（body）：1,1A,1B,1C,2,3,4,5,6,7,7A,**10** — 7A 之後直接跳到 10。
  - **idx 35–48**：7,7,8,9,9A,9B,9C,10,11,12,13,14,15,16 — 後半段其實有真正的 8/9/9A/9B/10。
- 兩個 body Item 10：
  - **假 10 @ 623,410**：context `'Item 10. Directors, Executive Officers, and Corporate Governance—Board Committees.” '`（結尾 `.”` 收尾引號）— 這是 Item 7A（MD&A）內文引用章節名的一句 cross-reference，被 Stage-1 斷行斷在行首，`find_anchors` 的 `^` 誤判為真錨。
  - **真 10 @ 1,089,469**：context `'ITEM 10.\xa0 DIRECTORS, EXECUTIVE OFFICERS, AND CORPO...'`（全大寫、位置正確，在真 9B 之後）。
- `Item 8` 在 ruler.text 出現 3 次：pos 4,639（前段 TOC）、pos 662,958（`ITEM 8. FINANCIAL STATEMENTS`，落在假 item 10 的 466k 範圍內）、pos 1,213,735（句中引用 "Item 8 above"）。

### 4.3 根因定性（Stage-2 精度問題，非安全漏洞）
`_greedy_monotonic` 走文件順序、只收 order_index 嚴格遞增：
1. 收到真 7A（order 10）後，下一個 body 錨點是假 10（order 15），15>10 → 接受，last=15。
2. 之後文件順序才輪到真正的 8(11)、9(12)、9A(13)、9B(14) — 全 < 15 → 全被當「回跳」丟棄。
3. 真 10(15) 不嚴格 > 15 → 也丟；11(16) 才恢復接受。

**後果**：假 Item 10 的 span 從 623,410 一路吃到 1,089,460（466k 字），將 pos 662,958 的真財報（ITEM 8 FINANCIAL STATEMENTS）整包吞入；真 8/9/9A 消失 → should_exist 舉手；真 Item 10 區（36,729 字）無人認領 → UNCLASSIFIED red flag。

**為何別家未中招**：其他檔的 "Item 10" cross-reference 多為句中（"see Item 10"），被 `^` 行首錨定擋掉。KKR 這句剛好引號跨行、"Item 10." 落在行首才騙過。真正脆弱點是 `_greedy_monotonic` 對「向前跳的單一假錨」毫無抵抗力：accept-first，一旦收了一個跳太前面的假錨，其後一整段真錨全被誤殺。

**gate 運作正確**：should_exist（8/9/9A 缺）+ residual_sanity（36k 塊）雙雙觸發 → loud FAILED（6/8）。**KKR 不是漏洞，是誠實失敗。**

---

## 5. 修法方向與鐵律界線（僅陳述方向；落實一律測試先行）

### 5.1 最高優先且唯一必須動 code：INTC 的 gate 紅旗
- **問題精確化**（由 C vs INTC 對比逼出）：gate 的 `should_exist` 只檢查「item id 在不在」，不檢查「item 是否有實質覆蓋率」。C 因 id 全不在被抓；INTC 因 id 全在（皆空殼）而放行。
- **紅旗應對準的**：不是籠統的「覆蓋率下限」，而是「**item id 齊全 vs 實質覆蓋率極低之間的矛盾**」（INTC：21 個 id 皆在、每個 span 11~205 字、加總約 1,500 字 vs 490k 殘留）。可能形式例如「存在一塊遠大於所有 item 總和的 COVER_PAGE/UNCLASSIFIED 殘留」時舉旗。
- **合規性**：此為**收緊、非放寬**（讓 silent PASS 轉 loud FAILED），符合鐵律 3。
- **必要條件**：閾值型不變量最易誤殺合法案例（例如大量 IBR/reserved 導致 body 短的合法檔）。新不變量須用**全部 21 家真實檔（第一輪 11 + 第二輪 10）** 驗證不誤殺任何既有 PASS——不抽樣。

### 5.2 鐵律封死、不得採用的方向（明確記錄，防修復階段漂移）
以下方向在診斷中被提出（部分由 Claude Code 建議），經對照鐵律後判定**不採用**：
- **改 anchor 去比對標題主題字串**（Business/Risk Factors）以救 INTC/C：違反「錨點=編號+順序，絕不用標題字串」。**封死。**
- **用文末索引表當結構圖反推正文**：等於用「Item→頁碼/標題」對應定位，繞道違反 enumerator 契約精神。**不採用。**
- **抑制「行末以 `.”`/引號收尾、其後接散文而非章節本體」的假錨**（KKR）：「其後接散文而非章節本體」屬語意判斷，滑向以內容當判準、edge case 無邊界。**否決。**
- **將 `_greedy_monotonic` 換成 LIS/最大覆蓋演算法**（KKR）：非最小修、爆炸半徑巨大（第一輪 125 test 與全部 PASS 檔皆依賴此核心），且 KKR 已正確 loud fail、無答案鍵驗證「修對」。**不在本輪採用**；若未來要做，須作為獨立的、以全量真實檔測試先行的大工程。

### 5.3 KKR / C 的處置傾向
- **KKR**：已 loud FAILED、gate 正確。根因為 Stage-2 精度限制（假錨劫持）。傾向**只記錄為已知精度限制、本輪不動 `_greedy_monotonic`**（理由見 5.2）。
- **C**：已 loud FAILED、gate 正確。版式謎團（C-2 假說）未驗證，對修法無決定性影響。傾向**記錄為已知未竟事項**，版式探查可選做。

---

## 6. 已知未竟事項

- C 的「16 MB 文件連 raw 都 0 個 Item N」根因（C-2 版式拆分假說）尚未探查證實。
- KKR 是否修復 `_greedy_monotonic`（傾向不修、只記錄）待最終定案。
- INTC gate 紅旗的具體指標與閾值尚待設計，並須經全 21 家回歸驗證不誤殺。
- 與第一輪的關聯（**均為假設，待更多實證**）：KKR 的 Part III 交界殘留 vs 第一輪 BRK-B（421 字殘留）可能共享「Part III 交界處理」家族，但規模差兩個數量級、是否同一 code 路徑未證實；INTC 為第一輪未見的全新型態（正文無編號）。
- Level-3（飽和抽樣）、Level-4（全母體頻率估計）尚未進行；三種失敗型態在母體中的頻率未知。

---

*本檔為事後整理的診斷紀錄，數字來源為第二輪各次唯讀探查的實跑輸出。修法方向為分析建議，任何 code 變更均須依鐵律 3 測試先行、全量回歸。*
