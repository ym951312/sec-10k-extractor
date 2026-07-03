# 完整對話紀錄 — SEC 10-K 逐項擷取 Pipeline：第二輪擴大抽樣、根因診斷與 inv 9 修復（Part 2）

> **關於本文件**：本文件依時間順序完整重建本次對話（第二輪擴大抽樣任務，接續 Part 1）的內容與決策脈絡。對於冗長的終端機/Claude Code 原始輸出，本文件保留其**關鍵數據、判讀結論與決策**，而非逐字重貼每一段畫面；所有具體數字、檔名、CIK、commit hash 均取自對話中實際出現的內容，未經編造。使用者在關鍵節點提出的問題或決策以粗體標題＋引用區塊標出，供日後回顧「哪些地方是使用者主導、哪些是 Claude 主導」時參照。

---

## 目錄

0. 任務起點：第二輪擴大抽樣交接摘要與查證方式拍板
1. TSM/SCU 查證與名單定案（AVGO、KKR 替補）
2. Fixture 資料夾與抓檔腳本形式決策
3. 抓檔腳本建立：唯讀查證、草擬、Claude Code 唯讀模式衝突與修正
4. 執行抓檔：10/10 成功與 CIK 驗證；Commit 1
5. 進入 eval pipeline：runner 現況查證、PYTHONPATH 環境問題、白話解釋
6. Runner 修復路線決策：另寫 vs 參數化（甲/乙的框架轉換）
7. 測試先行方式、安全參數化實作、零回歸驗證、Commit 2
8. r2 首次執行結果：6 PASS／3 FAILED／1 個 silent 隱患
9. 與第一輪失敗案例的關聯分析、診斷優先序拍板
10. INTC 根因診斷：三階段唯讀探查
11. 呈現層方法論釐清：法規是否強制 Item N 格式
12. C（Citigroup）根因診斷：三重零
13. KKR 根因診斷：假錨劫持 greedy-monotonic
14. 三案診斷收斂與 findings 摘要拍板
15. 診斷筆記撰寫、審閱、Commit 3
16. Gate 修法設計：指標選擇辯論與保守閾值決策
17. 21 家實測量測、原始碼補讀、實作規格拍板
18. 測試先行：紅燈確認（含 anchor 衝突與修正）
19. inv 9 實作與全套回歸驗收、Commit 4
20. 下半場時間規劃討論
21. Citi C-2 假說驗證與推翻
22. 失敗分析併入報告的決策；診斷筆記更新、Commit 5
23. 下半輪交接文件撰寫
24. 本輪任務的一次誤解與更正

---

## 0. 任務起點：第二輪擴大抽樣交接摘要與查證方式拍板

使用者貼上 `HANDOFF_round2_report.md` 交接摘要，內容涵蓋：第一輪（層級二驗證 + TOC 修復 + part era-blind 修復 + `VALIDATION_part_1.md` + 6 commits）已全部落地、125 tests passed；本輪任務是**第二輪擴大抽樣（科技 5 家＋金融 5 家）**；並明確標記兩個需要新對話先查證、不可直接假設的風險點——**TSMC 很可能申報 Form 20-F 而非 10-K**、**Sculptor Capital 已於 2023 年被收購下市，可能已無近年 10-K**。

Claude 確認理解摘要內容後，詢問查證方式：本對話直接用 web search 查（A）或交給 Claude Code 唯讀查（B）。

> **使用者拍板〔A：本對話直接查〕**

## 1. TSM/SCU 查證與名單定案（AVGO、KKR 替補）

Claude 用 web search 查證：**TSMC 確認申報 Form 20-F**（外國私人發行人，自 2002 年起皆以 20-F 申報年報，現有 era ruleset 不適用）；**Sculptor Capital 確認 2023-11-17 被 Rithm Capital 以每股 12.70 美元、總值約 7.198 億美元收購下市，最後一份 10-K 為 FY2022**（CIK 1403256，E&Y 於 2023-03-03 簽署審計報告；Part III 明文 IBR 至 proxy，正中「資管公司 Part III 大量 IBR」的預期觀察點）。

Claude 提出處理選項（甲：記錄為邊界案例不抓檔／乙：換一家公司）。

> **使用者拍板〔TSM → 乙：換公司；SCU → 乙：換公司〕**

Claude 提出替補候選：科技組（AVGO/QCOM/ORCL/TXN）、金融組（KKR/BX/ARES/GS）。

> **使用者拍板〔科技 → AVGO；金融 → KKR〕**

Claude 查證兩家替補：**AVGO**（CIK 1730168「Broadcom Inc.」，FY2024 10-K 已確認為 Form 10-K，FYE 為非曆年制、結束於最接近 10/31 的星期日）；**KKR**（CIK 1404912「KKR & Co. Inc.」，需注意 EDGAR 上另有一個易混淆實體 CIK 1957845「KKR Private Equity Conglomerate」，抓檔時須顯式鎖定 1404912）。最終 10 家名單定案：科技 NVDA/GOOGL/AMD/INTC/AVGO；金融 BAC/C/BLK/APO/KKR。

## 2. Fixture 資料夾與抓檔腳本形式決策

Claude 提出兩組決策：

- **決策 A（fixture 存哪個資料夾）**：甲＝新開 `tests/fixtures/eval_recent_r2/`（兩輪分離）／乙＝沿用 `eval_recent/`（合併 21 家）。
- **決策 B（抓檔腳本形式）**：甲＝另寫 `fetch_eval_set_r2.py`（不動第一輪腳本）／乙＝擴充現有 `fetch_eval_set.py`。

> **使用者拍板〔A → 甲；B → 甲〕**——兩輪 fixture 與腳本都分離，符合「爆炸半徑最小」原則。

## 3. 抓檔腳本建立：唯讀查證、草擬、Claude Code 唯讀模式衝突與修正

依「先讀後改」，Claude 先要求 Claude Code 唯讀讀取第一輪 `scripts/fetch_eval_set.py` 完整原始碼（不能憑摘要寫 r2 版）。取得原始碼後確認：ticker→CIK 解析用 `company_tickers.json`、抓年度 10-K 用 submissions JSON 篩 `form=="10-K"` 精確排除 10-K/A、`cik_override` 欄位早已存在（DVN/PLD 已用過）——所以 KKR/AVGO 的 CIK 鎖定只需填這個既有欄位，不需新邏輯。

Claude 在自己環境草擬並語法檢查 `fetch_eval_set_r2.py`（COMPANIES 清單含 AVGO/KKR 的 `cik_override`），交給使用者建檔。**第一次建檔指令失敗**：Claude Code 仍處於前一步唯讀查證設下的唯讀模式，回報「read-only — 不會建立或執行任何東西，除非你明確解除限制」，安全拒絕建檔。

> **使用者提問〔為什麼之前每則都有唯讀/自足指令，現在沒有？〕**

Claude 說明：唯讀是配合任務性質切換的開關，不是無條件掛在每則指令上的標籤；建檔步驟需要明確聲明「本步允許建立這一個檔案」才能解除前一步遺留的唯讀狀態——這正是第一次建檔失敗的原因。**第二次指令**明確解除唯讀限制、只允許建立這一個檔案，成功建檔並通過語法檢查與內容驗證。

## 4. 執行抓檔：10/10 成功與 CIK 驗證；Commit 1

使用者拍板執行抓檔（本輪首次連網）。結果 **10/10 全部成功**：

| ticker | CIK | 實體名稱 | reportDate | raw 大小 |
|---|---|---|---|---|
| NVDA | 1045810 | NVIDIA CORP | 2026-01-25 | 2.0 MB |
| GOOGL | 1652044 | Alphabet Inc. | 2025-12-31 | 2.6 MB |
| AMD | 2488 | ADVANCED MICRO DEVICES INC | 2025-12-27 | 2.2 MB |
| INTC | 50863 | INTEL CORP | 2025-12-27 | 3.3 MB |
| AVGO | 1730168 | Broadcom Inc. | 2025-11-02 | 2.7 MB |
| BAC | 70858 | BANK OF AMERICA CORP /DE/ | 2025-12-31 | 12.8 MB |
| C | 831001 | CITIGROUP INC | 2025-12-31 | 16.2 MB |
| BLK | 2012383 | BlackRock, Inc. | 2025-12-31 | 12.6 MB |
| APO | 1858681 | Apollo Global Management, Inc. | 2025-12-31 | 9.8 MB |
| KKR | 1404912 | KKR & Co. Inc. | 2025-12-31 | 20.0 MB |

KKR 成功解析到 CIK 1404912（避開 1957845 conglomerate）、AVGO 解析到 1730168，兩個鎖定的 CIK 都正確。金融組檔案明顯大於科技組（KKR 20MB、C 16.2MB），符合「金融業揭露量大」的預期。

暫存清單核對乾淨後，**Commit 1（`799c9c3`）：「Add round-2 eval fetch script and 10 fixtures (tech + finance)」**，11 files changed，132 insertions。

（本節穿插一次流程提醒：使用者指出「你應該要提醒我貼完整輸出」——Claude 承認先前幾輪未每次堅持要求原始 output、只接受 Claude Code 的總結，這違反了使用者規範「一律從真實資料實跑取得」的精神，往後每則指令會固定要求「把完整輸出貼回、不要只給摘要」。）

## 5. 進入 eval pipeline：runner 現況查證、PYTHONPATH 環境問題、白話解釋

Claude 先唯讀讀取 `scripts/eval_recent_run.py` 完整原始碼，確認它的 `EVAL_DIR` 寫死指向 `tests/fixtures/eval_recent`（第一輪目錄）。同一則指令也嘗試驗證 pipeline import，但 **Claude 自己漏寫了 `PYTHONPATH=src`**，導致 `ModuleNotFoundError`——Claude 承認這是指令寫錯、不是專案問題，並用正確的 `PYTHONPATH=src .venv/bin/python` 重新驗證，確認 `run_pipeline importable OK`、`extract_fiscal_year_end importable OK`，並唯讀確認 `src/sec10k/` 套件結構（`pipeline.py`/`metadata.py`/`invariants/`/`ruler/`/`ruleset/`/`segment/` 等）印證為何需要這個環境變數（src-layout）。

> **使用者要求〔用白話但不失嚴謹的方式，解釋現在在發生的事情，以及在整個策略下為什麼要做這些事〕**

Claude 說明：抓完檔要跑分段前卡在兩個地基問題（程式怎麼啟動、runner 只認第一輪資料夾），並串起「每一步先唯讀查證、每次只做一件小事」的紀律為什麼重要——這正是防止 AI 憑印象動錯地方的機制，也解釋了為何「先讀後改」貫穿全程。

## 6. Runner 修復路線決策：另寫 vs 參數化（甲/乙的框架轉換）

Claude 提出兩條路線：**甲**＝另寫 `eval_recent_r2_run.py`（不動已驗證的第一輪 runner，零風險）；**乙**＝參數化現有 runner（單一 runner，但動到已驗證檔）。Claude 傾向甲（爆炸半徑最小）。

使用者傾向甲，但接著提出一個框架轉換的問題：

> **使用者提問〔如果站在往後這份 project 可以繼續拿來抽取其他感興趣公司的前提下，你建議甲還是乙？就可用性來說是不是甲乙不一定誰好誰壞？那就維護性來說呢？〕**

Claude 重新評估：若定位是「一次性作業」則甲最穩；若定位是「長期反覆使用的工具」，則乙（單一通用 runner）在維護性上明顯較優（改進 runner 邏輯不用同步複製到多份檔案），但需用「安全參數化」（不帶參數時完全等同舊行為）把「動已驗證檔」的風險壓到最低。

> **使用者拍板〔乙：長期工具定位 → 安全參數化（向下相容＋實跑驗證 r1 不變）〕**

## 7. 測試先行方式、安全參數化實作、零回歸驗證、Commit 2

因為要動已驗證的 runner，鐵律 3「測試先行」適用。Claude 提出兩種落實方式：**理解 A**＝為 runner 另寫正式 pytest 護欄；**理解 B**＝改前存基準、改後逐字 diff 比對（不寫 pytest，因 runner 非 pipeline 核心、本來就是「跑出來看」的驗證方式）。

> **使用者拍板〔理解 B：實跑 diff 回歸〕**

Claude 唯讀跑一次現有 runner（不帶參數＝r1 原行為），把完整輸出存成 `/tmp/eval_r1_baseline.txt`（500 行，供 diff 比對用、不進 git）。基準顯示 11 家的即時實跑結果（8 PASS、brkb/nee/pfe FAILED），與交接摘要記載一致。

改動：`scripts/eval_recent_run.py` 第 23 行改為 `EVAL_DIR = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("tests/fixtures/eval_recent")`——只改這一行，`git diff` 確認僅此一處變動。回歸驗證：不帶參數重跑，與基準逐字 diff，**`PASS：與基準逐字相同，r1 行為零變化`**。

**Commit 2（`2a1ea90`）：「Parametrize eval runner to accept an optional fixtures dir (backward-compatible)」**，1 file changed，1 insertion 1 deletion。

## 8. r2 首次執行結果：6 PASS／3 FAILED／1 個 silent 隱患

帶 r2 參數執行 runner，10 家結果：

| 檔案 | items | status | inv | viol |
|---|---|---|---|---|
| amd | 21 | PASS | 8/8 | 0 |
| apo | 21 | PASS | 8/8 | 0 |
| avgo | 21 | PASS | 8/8 | 0 |
| bac | 21 | PASS | 8/8 | 0 |
| blk | 21 | PASS | 8/8 | 0 |
| c | 0 | **FAILED** | 7/8 | 12 |
| googl | 21 | PASS | 8/8 | 0 |
| intc | 21 | **PASS（可疑）** | 8/8 | 0 |
| kkr | 17 | **FAILED** | 6/8 | 4 |
| nvda | 21 | **FAILED** | 7/8 | 1 |

**6 家乾淨 PASS、3 家大聲 FAILED（C/KKR/NVDA）**。但 Claude 核對 span 數字後發現 INTC 雖顯示 PASS 8/8，21 個 item 卻**全擠在 char 491090–492575（raw 3.3MB 裡的一個窄帶）**，前約 49 萬字正文完全沒進任何 item——這是 PASS 卻幾乎確定錯誤的**沉默失敗**，比三個大聲失敗更危險。

## 9. 與第一輪失敗案例的關聯分析、診斷優先序拍板

> **使用者提問〔上一輪三個 failed case（BRK/PFE/NEE），跟這一輪 failed 或可疑案例的關聯為何？因為上一輪沒修，就是想說可能跟這一輪有類似病灶〕**

Claude 逐一比對症狀（unclassified residual 規模、位置、缺失 item 型態），提出假設性的根因家族分類（家族 A：front-matter/TOC 邊界，含 INTC/C；家族 B：Part III 交界殘留，含 BRK-B/NVDA/KKR；家族 C：複雜版面/多註冊人，含 NEE；家族 D：reserved/status 分類，含 PFE），並明確標記這整張地圖是「未看內容前的症狀級假設，待唯讀診斷驗證或推翻」。

> **使用者拍板〔INTC 優先：家族 A、沉默最危險，可能同時解開 C〕**

## 10. INTC 根因診斷：三階段唯讀探查

**第一階段**：唯讀讀取 `pipeline.py`/`ruler/front_matter.py`/`segment/anchors.py`/`segment/segmenter.py` 完整原始碼，確認各階段介面（`detect_toc`/`find_anchors`/`_greedy_monotonic` 的簽名與行為），才能設計精準的探查。

**第二階段**：對 INTC 實跑探查——`ruler.text` 全長 493,929；`find_anchors` 只找到 23 個，**全部** `enum_start ≥ 491,090`；前段（<491,090，佔全文 99.4%）錨點總數 = **0**；`detect_toc` = None；Stage-1 把 `[0,491,090)` 整塊判為單一 `COVER_PAGE`。末端那 23 個「錨點」實為 Intel 文末的「Item Number/Pages」交叉索引表（`Item 1.` … `Item 16.` 各自成行、完美遞增）。

> **使用者提問〔有考慮過 item N 這種型態嗎？（i 是小寫）〕**

Claude 確認：探查用的 regex 與 pipeline 真正的 `_ANCHOR` 正則都帶 `re.IGNORECASE`，已涵蓋任何大小寫組合；前段命中 0 已排除任何大小寫的 `item N` 開頭行存在的可能。

**第三階段**：對 INTC 正文（char 0–491,090）做寬鬆搜尋，確認正文裡 `Item 1` 出現 0 次（唯二的 `Item N` 樣式是 `Item 601(a)(5)-(6)` 這種 Regulation S-K 條文引用）；所有 `Item N` 樣式共 2 個、行首 0、非行首 2——判定為「**形態乙**：標題根本不帶 Item N 編號」。再對 **raw HTML（Stage-1 之前）** 做同樣搜尋，去標籤純文字裡 `Item 1/1A/1B/1C` 出現 4 次，**全部在文末索引表**——確認正文源頭本來就沒有 Item N 編號，不是 Stage-1 弄丟的。

## 11. 呈現層方法論釐清：法規是否強制 Item N 格式

> **使用者提問〔所以法規沒有硬性規定一定要有類似 Item N 的格式在正文裡面嗎？此外，他有在法規明確規定可以有的彈性裡面嗎（例如可以合併 Item）？如果是，那就代表我們前面的規則不夠 general？但我理解，這種現象也有可能是法規沒說不行，所以屬於難以窮盡的呈現層變形之一〕**

Claude 回應：法規規定的是「內容與順序」，不是排版形式，Intel 不印 enumerator 在法規上是允許的。**關鍵區分兩種彈性**：類型一是「法規明確授權的結構性彈性」（如 Item 1&2 合併、Part III IBR）——這類 pipeline 已支援、規則是 general 的；類型二是「法規沒禁止的呈現層變體」（如 Intel 不印 enumerator）——這類**理論上無法窮盡**，不屬於「規則不夠 general」的疏漏，而是設計文件早就寫明的「結構層可證明封閉、呈現層可估計但無法證明封閉」這條界線的必然體現。使用者最後那句自我判斷（「難以窮盡的呈現層變形之一」）被確認完全正確。

## 12. C（Citigroup）根因診斷：三重零

對 C 跑相同結構的唯讀探查：`ruler.text` = 1,056,191；raw = 16,150,764；`ruler.residual_candidates` **完全為空**（無 COVER_PAGE、無 TOC，與 INTC 截然不同）；`find_anchors` = **0**；`ruler.text` 裡 `Item 1` = 0；raw 去標籤後 `Item 1/1A/1B/1C` = 0——「**三重零**」。因完全無錨點，`accepted=[]` → `should_exist` 對 12 個 expected item 全部舉手 → **loud FAILED**，gate 運作正確。

> **使用者提問〔隱含：INTC 與 C 是否同根因？〕**（見第 9 節的家族分類延伸討論）

Claude 分析：C 與 INTC 的對比是很好的 eval 材料——同樣切不出正文，C 誠實失敗（錨點=0 → id 全不在 → 舉手）、INTC 假裝成功（索引表給了 21 個假 id → id 全在 → 放行）。真正的破口是 gate 的 `should_exist` 只檢查「item id 在不在」、不檢查「是否有實質覆蓋率」。此時 C 的「16MB 連 raw 都 0 個 Item N」仍列為未驗證假說（C-2：版式拆分），待後續驗證（見第 21 節）。

## 13. KKR 根因診斷：假錨劫持 greedy-monotonic

KKR 是三家裡唯一「有正常切出東西、但被吞併」的型態：`ruler.text` = 1,248,574；raw = 20,008,121；Stage-1 有正常 `COVER_PAGE[0,4119)` + `TOC[4119,5352)`；`find_anchors` = 49。

探查發現 body 區有**兩個 Item 10**：**假 10 @ 623,410**——context 是 `'Item 10. Directors, Executive Officers, and Corporate Governance—Board Committees.” '`，這其實是 Item 7A（MD&A）內文裡一句**引用式 cross-reference**，剛好被斷行斷在行首，被 `find_anchors` 的 `^` 誤判成真錨；**真 10 @ 1,089,469**——全大寫、位置正確（在真 9B 之後）。

崩壞機制：`_greedy_monotonic` 收到真 7A（order 10）後，下一個 body 錨點是假 10（order 15），15>10 → 接受；之後真正的 8(11)/9(12)/9A(13)/9B(14) 全部 <15 → 被當「回跳」丟棄。假 Item 10 的 span 因此從 623,410 吃到 1,089,460（**466,050 字**），把真財報（`ITEM 8. FINANCIAL STATEMENTS`，pos 662,958）整包吞入；真 Item 10 區（36,729 字）無人認領 → UNCLASSIFIED red flag。**gate 正確 loud FAILED**（should_exist + residual_sanity 雙觸發）。

## 14. 三案診斷收斂與 findings 摘要拍板

三家診斷完成，收斂成一句話：**anchor 契約的三個隱含假設各被一家打破**——INTC 打破「正文一定有編號」、C 打破「編號一定找得到」、KKR 打破「行首編號一定是真標題」。三者中只有 INTC 是 silent（gate 被騙），C 與 KKR 皆已 loud（gate 正確）。

> **使用者拍板〔A：先寫三家 findings 摘要（固化診斷階段）再進修復〕**

Claude 提出三個子決策：findings 摘要寫成獨立檔還是直接進報告、何時 commit、由誰寫（Claude 直接寫好內容供審閱，或交給 Claude Code 邊查邊寫）。

> **使用者拍板〔獨立診斷筆記 `docs/DIAGNOSIS_r2_failures.md`（之後再摘進報告）；寫完單獨 commit〕**

## 15. 診斷筆記撰寫、審閱、Commit 3

Claude 在自己環境寫出完整診斷筆記（§0 範圍與證據層級、§1 三家根因總表、§2–4 逐家詳細診斷、§5 修法方向與鐵律界線、§6 已知未竟事項），內容包含明確否決 Claude Code 曾提議的兩個修法方向（換掉 `_greedy_monotonic`——爆炸半徑過大；抑制引用式假錨——滑向語意判斷，違反鐵律），完整貼給使用者審閱三件事：數字有無誤、§5.2 鐵律封死方向是否認同、KKR 傾向不修是否同意。

> **使用者確認〔沒問題〕**——經 Claude 追問釐清具體對應哪一層後，**確認為 A：三件事都同意，直接落檔＋commit**。

Claude Code 建檔（149 行，行數與章節結構核對通過），暫存清單核對乾淨後，**Commit 3（`f027385`）：「Add r2 failure diagnosis note (INTC / C / KKR root causes)」**。

## 16. Gate 修法設計：指標選擇辯論與保守閾值決策

使用者主動表態：

> **使用者決定〔我自己同意要修改 gate 的 code，讓他對 INTC 也大聲報錯〕**

這是本輪唯一必須動 pipeline 核心的修復。Claude 先指出一個危險前提：不能用「某 item 本該有大量內文」當判準（這綁定呈現慣例，違反鐵律），改提議用「cover page 佔比」這種結構性比例。

> **使用者糾正〔我認為說「本該有大量內文」的 item，這想法很危險，因為這是基於你自己的價值判斷，不是客觀事實。萬一未來法規允許 Item 1 用引用方式呈現，就會變得超短〕**

Claude 接受糾正，改提議兩個候選指標：`cover/ext`（cover page ÷ item 總和）與 `cover/all`（cover page ÷ 全文）。

> **使用者提出邊界案例〔我還是想回到我前面第三點的極端怪例子。在那個例子裡，由於本文過短，cover 佔的篇幅很大，所以我才想要把規模也實際納入考量。只考慮 cover/all 等於又丟棄了這個考慮。但我也同意，把規模訂一個數字，在現階段是沒有統計證據下的臆測——你覺得呢？〕**

這個追問直接推翻了「純 cover/all、閾值定在分布中點」的方案，因為它會誤殺「全文極短、cover page 佔比天生偏高」的合法小檔。Claude 提出解法：**「保守閾值＋誠實記錄校準邊界」**——閾值不定在分布中點，而是推向極端保守（如 0.9，「文件幾乎全是封面」的物理荒謬區），讓怪例自然被涵蓋，同時在 code 註解裡誠實記錄「閾值只在已測範圍內驗證過、對遠小於此範圍的文件行為未經實證」。

> **使用者拍板〔那就「保守閾值 + 誠實記錄校準邊界」吧！閾值定 0.9〕**

## 17. 21 家實測量測、原始碼補讀、實作規格拍板

唯讀量測全 21 家（r1 11 家 + r2 10 家）的 `cover/ext`、`cover/all`、`ext/all` 三個比例，關鍵數字：

| 指標 | 合法檔（20 家）範圍 | 最接近的合法檔 | INTC | C |
|---|---|---|---|---|
| cover/ext | 0.0–0.1 | pfe 0.1 | 340.8 | inf |
| cover/all | 0.005–0.055 | pfe 0.055 | 0.994 | 0.970 |
| ext/all | 0.580–0.989 | blk 0.580 | 0.003 | 0.000 |

三個指標都能乾淨隔離 INTC，但 `cover/ext` 在 C 身上出現除零產生的 `inf`——**證實它數學上不穩健**（分母可趨近 0）。Claude 確認採用 `cover/all`，閾值 0.9（合法檔最高 0.055，margin 極寬）。

Claude 要求 Claude Code 補讀 `invariants/gate.py`、`invariants/checks.py`、`invariants/report.py`、`tests/fixtures/spans/__init__.py`（`standard_valid_layout()`）、`test_stage2.py` 的完整原始碼（**這兩個檔案第一輪時只給了轉述、原文從未進對話，依「先讀後改」要求補**），確認：`decide_filing` 不用改（HARD violation 自動轉 FAILED）；`standard_valid_layout()` cover/all ≈ 0.05（安全）；落點選新增獨立的 **inv 9**（而非塞進既有 inv 4），理由是語意乾淨、簽名更小、爆炸半徑最小、且測試對不變量數量無任何 count 斷言（grep 確認）。

完整實作規格（enums.py +1 個 ReasonCode、checks.py +常數+函數、gate.py +1 行註冊、test_invariants.py +測試對）貼給使用者。

> **使用者拍板〔核准，進測試先行的第一步〕**

## 18. 測試先行：紅燈確認（含 anchor 衝突與修正）

前置量測：`mini_10k.txt`（合成回歸點）cover/all = **0.0476**；`standard_valid_layout()` cover/all = **0.0497**——兩者都遠低於 0.9，確認安全。

建立 `tests/test_cover_dominance_regression.py`（真實檔護欄：INTC 應 FAILED、C 應含新 code、其餘 19 家 status 不變、全 21 家不抽樣）：紅燈確認成功——`test_intc_is_failed_by_cover_dominance` 如預期失敗（INTC 現在仍 PASS）。

插入 `test_invariants.py` 的合成 pass/fail 測試對時，**第一次因 anchor 字串「# inv 5 — legal structure」在檔中出現 2 次（一次是內文註解、一次是真正區塊標題）而觸發 `assert count==1` 安全中止，檔案完全未被寫入**——這是守衛正確發揮作用。第二次改用「inv 4 測試結尾唯一一行」當精準 anchor，插入成功，`2 failed, 28 passed`（新增的 2 條如預期紅：`KeyError: 'cover_dominance'`）。

## 19. inv 9 實作與全套回歸驗收、Commit 4

改動三個 src 檔（均為純加法，`git diff` 逐行核對確認沒動任何既有邏輯）：`enums.py` +1 行 `OVERSIZED_COVER_PAGE`；`checks.py` +45 行（含校準邊界註解的 `check_cover_dominance(ruler, residual)`，只用 span 幾何＋residual 類別，不碰標題字串）；`gate.py` +1 行註冊 `cover_dominance`、docstring "eight→nine"。

**驗收結果（實跑）**：
- 單元測試＋回歸測試：**全綠**（`2 passed` + `35 passed`）。
- 全套 pytest：**`162 passed, 0 failed`**——零回歸。
- r2 CROSS-FILE SUMMARY：**INTC 從 PASS 8/8 → FAILED 8/9**（cover_dominance 觸發，修復目標達成）；**C 維持 FAILED，viol 12→13**（預期冗餘命中，已 pin 進測試）；其餘 8 家 r2 檔案 status 零變化（8/8→9/9）。
- r1 CROSS-FILE SUMMARY：**11 家 status 逐字不變**，denominator 全部 8/8→9/9，對第一輪零影響。

**Commit 4（`4a2749b`）：「Add inv 9 (cover_dominance): turn INTC-type silent PASS into loud FAILED」**，5 files changed，173 insertions 1 deletion，message 完整記錄問題、修法、校準邊界、驗收數據、以及「C/KKR 依設計維持 loud FAILED、未在本輪修復」的誠實聲明。

## 20. 下半場時間規劃討論

使用者上傳作業原文（`Whaleforce-AI-Coding-Test-ZH.md`）與設計文件（`10K_抽取策略_設計文件_v2.md`），提出下午計畫：修完 INTC 後 → 進 Stage 6 前端 → 效能/成本/擴充性分析（Stage 4 概念分析、不寫 code）→ 資料提交管理與收尾。

> **使用者要求〔評估這個規劃，如果覺得還有作業提到但我漏掉的，跟我說〕**

Claude 逐條對照作業共同要求，指出使用者規劃裡**沒明確涵蓋的三項**：`prompts/` 資料夾（完全未提及）、push 到公開 repo（repo 目前未 push、無 remote）、把「部署成可公開 URL」當成獨立風險項提早試（原規劃把它隱含在「做前端」裡，但部署本身是高風險的獨立工序）。建議把路線圖改為「風險優先」排序：先補交件硬門檻（push、部署試跑、prompts），再深化分析報告。

## 21. Citi C-2 假說驗證與推翻

在進入下半場前，使用者提出：

> **使用者提議〔希望在進下半場前，至少了解 Citi 那份文件真正的樣子，提出可能的改進方式（不用真的實作），本輪再收尾。這應該不會很久？〕**

Claude 區分「層次 A」（快、了解形式＋記錄改進方向）與「層次 B」（慢、深挖到 HTML 表格細節），建議做層次 A（估 15–25 分鐘）。使用者同意。

唯讀探查 C 的 raw HTML：**[Q2]** "Item" 單獨字詞僅 55 次，幾乎全是普通名詞（notable item）、法規引用（Item 402(v)）、或單一欄標題（Item Number）；**[Q3]** Citi 的文末交叉索引表用**裸編號** `1A. Risk Factors 49–62`、`2. Properties Not Applicable`、`3. Legal Proceedings`——"Item" 只當整表欄標題、非每列重複；**[Q4]** 放寬「Item 與 1 之間夾 ≤200 字」在 raw 仍只配到 15 個垃圾匹配，無任何被標籤拆開的證據。

> **使用者提醒〔希望你不要因為時間好像比較吃緊就判讀變隨便，要一樣很嚴謹〕**

Claude 逐項核對後確認：**C-2「版式拆分」假說被推翻**。真正根因：C 全文無 per-section Item N token，索引用裸編號、"Item" 僅欄標題，正文用主題標題。**C 是 INTC 的更極端表親**——兩者正文皆無編號，差別僅在索引表列舉子帶不帶 "Item"：INTC 帶（23 假錨→silent PASS）、C 不帶（0 錨→loud FAILED，且 inv 9 現已能攔截 INTC 型的變體）。

## 22. 失敗分析併入報告的決策；診斷筆記更新、Commit 5

> **使用者提議〔這一輪要不要包含並分類目前所有已知的失敗例子，說明方法侷限性與改進方式？一樣不寫 code〕**

Claude 評估兩條路徑：路徑 A（併進最終報告 `VALIDATION_part_2.md` 的一章，素材已齊、避免重複、優先補交件硬門檻）／路徑 B（現在獨立做完）。

> **使用者拍板〔先收 Citi commit，然後走 A〕**

Claude 精準改寫診斷筆記 §3.4（從「未解點/假設」改寫為「根因（已結案）」，保留「這原本是假設、後來被驗證推翻」的誠實敘事，而非抹掉軌跡）與 §6（兩條「未竟事項」更新為「已結案」，並誠實註明 inv 9「只轉 loud、未切對 INTC」，不誇大修復程度）。`git diff` 核對只有這三處改動。

**Commit 5（`1135aca`）：「Update C diagnosis: C-2 (layout-split) hypothesis disproven by raw HTML probe」**，1 file changed，8 insertions 4 deletions。

## 23. 下半輪交接文件撰寫

使用者要求撰寫交接文件，供同一 Project 開新對話接手下半輪任務（唯讀盤點 repo → 前端＋部署 → `prompts/` 資料夾 → 最終報告 → README＋push）。

針對 `prompts/` 資料夾，Claude 誠實說明一個限制：**無法提供「對話第幾行到第幾行」的定位**（對話不是帶行號的逐字稿，硬編行號等於捏造），提議改用 commit hash ＋ 階段標題當定位方式。

> **使用者確認〔內容都沒問題，另外我自己一個小 comment，其實可以從完整對話的 .md 檔匯出行號，但我發現那個匯出很耗時，怕沒有佔到多大方便性，因此可以採用你現在的 commit hash 方案〕**

Claude 撰寫並輸出 `HANDOFF_second_half.md`（184 行），內容涵蓋：專案現況（11 commit、162 tests passed、未 push）、本輪成果（三案診斷＋inv 9）供報告引用、下半輪路線圖、交件硬門檻逐條對照表、以及使用者逐字提供的完整協作規範（防新對話漂移）。

## 24. 本輪任務的一次誤解與更正

使用者上傳 `抽樣驗證_part_1對話_整理版.md`（即本文件所依循風格的 Part 1 對話紀錄），要求 Claude 自我判斷「哪些地方使用者起到了關鍵性角色」，依該檔風格生成完整對話紀錄整理 `.md` 檔。

**Claude 誤解了任務對象**：把上傳的 Part 1 檔案本身重新整理、加上一套自創的「A–G 貢獻類型分級表＋排名表」，而不是依該檔的**風格**去總結**這次對話**（第二輪任務本身）。

> **使用者糾正〔我仔細看了一下你的對話總結，你誤解我意思了，我意思是要你依照那個檔案的風格，總結「這個對話」，並不是對那個檔案再整理一次！重做〕**

Claude 承認誤解，重做——即本文件：捨棄自創的分級表格系統，改為貼近 Part 1 原始風格的寫法（章節式時間軸敘事＋粗體標題引出使用者的原文引用區塊），總結對象改為本次對話（第二輪任務，第 0–23 節），而非重新處理上傳的參考檔案本身。

---

## 附錄：關鍵檔案、commit 與現況索引

**新增/修改檔案（本輪）**：
- `scripts/fetch_eval_set_r2.py`（新增，r2 抓檔腳本）
- `tests/fixtures/eval_recent_r2/`（新增，10 份 fixture）
- `scripts/eval_recent_run.py`（修改，第 23 行安全參數化）
- `docs/DIAGNOSIS_r2_failures.md`（新增，149 行，後續更新 §3.4/§6）
- `src/sec10k/enums.py`（修改，+1 個 ReasonCode）
- `src/sec10k/invariants/checks.py`（修改，+45 行 `check_cover_dominance`）
- `src/sec10k/invariants/gate.py`（修改，+1 行註冊、docstring 更新）
- `tests/test_invariants.py`（修改，+1 對 inv 9 單元測試）
- `tests/test_cover_dominance_regression.py`（新增，35 條全 21 家回歸護欄）
- `HANDOFF_second_half.md`（新增，供下半輪新對話使用）

**本輪 5 個 commit（皆本機、未 push）**：

| # | hash | 內容 |
|---|---|---|
| 1 | `799c9c3` | r2 抓檔 script + 10 家 fixtures |
| 2 | `2a1ea90` | runner 參數化（向下相容） |
| 3 | `f027385` | r2 三案診斷筆記 |
| 4 | `4a2749b` | inv 9 `cover_dominance`（INTC silent→loud） |
| 5 | `1135aca` | C-2 假說推翻、診斷筆記結案 |

**全套測試：162 passed，0 failed。Git：本輪 5 個 commit（連同第一輪共 11 個），工作區乾淨，未 push。**
