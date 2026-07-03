# 完整對話紀錄 — SEC 10-K 逐項擷取 Pipeline：層級二驗證、修復與交件（Part 1）

> **關於本文件**：本文件依時間順序完整重建這整段對話的內容與決策脈絡。對於冗長的終端機/Claude Code 原始輸出，本文件保留其**關鍵數據、判讀結論與決策**，而非逐字重貼每一段畫面（那會極度冗長且與後續摘要重複）；所有具體數字、檔名、行號、commit hash 均取自對話中實際出現的內容，未經編造。給 Claude Code 的完整指令文字（因其本身即為可重用的規格）予以保留。

---

## 目錄

0. 任務起點與交接摘要
1. 層級二驗證：路徑選擇（Path A vs B）
2. 三份 ground truth 實跑與 MSFT 1994 Item 14 沉默失敗的發現
3. 認識論釐清：ground truth 是什麼、層級二 vs 三 vs 四
4. 近年 11 家 eval set 設計與抓取
5. 首次 11 家實跑：結果判讀（8 PASS / 6 FAILED，confidence 機制）
6. 根因調查：A 組（BRK/JPM/NKE）Item 1 缺失
7. 根因調查：PG 的 run 斷裂
8. 根因判準最終定位（front_matter.py 逐字取碼）
9. 修復範圍決策（甲/乙；PG 是否一併修）
10. 測試先行：TOC 缺陷紅燈測試
11. 階段 1 修復（A 組 backjump）與回歸
12. 階段 2 修復（PG run 合併）與回歸
13. PASS 檔案人工抽查（8 家全數，head+tail 方法）
14. Part era-blind 缺陷：發現、辯論（修 vs 不修）、決策
15. Part 缺陷修復：查證、設計選擇（Y：不 fallback）、測試先行、修復、回歸
16. 層級二驗證報告：大綱協商與逐段擬定（0–9 段 + 英文摘要）
17. 報告落地：`docs/VALIDATION_part_1.md` 分段 append + README 新增節
18. Git 初始化與 6 個 commit 的分組提交
19. Git 用途說明（使用者提問的教學性回覆）
20. 交接報告與 Project Instructions（給第二輪擴大抽樣）

---

## 0. 任務起點與交接摘要

使用者一開始上傳了一份 `HANDOFF_next_session.md`，內容為台灣量化交易新創公司的實習作業交接摘要，核心要點：

- **背景**：子勳是實習生，作業是建構 SEC 10-K 年報**項目級分割管道（item-level segmentation pipeline）**，評分維度涵蓋評估紀律、系統性思維、工程權衡判斷、AI 協作品質。目標是把原始 10-K 申報文件可靠分割為 Item 1–15/16，誠實回報信心水準與失敗模式——**明確不做合規判斷**。
- **技術棧**：Python 3.14、Pydantic v2、stdlib html.parser、pytest；專案目錄 `~/Documents/sec-10k-extractor/`。
- **當時狀態**：Stage 0–3 全部完成（財年末抽取、四個時代規則集、picker、認證尺規、確定性分割、九項不變量閘門）；Streamlit 前端已部署；已對 MSFT FY1994、MSFT FY2023、APA FY2023 三份基準文件 + 11 份多元 EDGAR 近期申報文件做過 Level-2 抽樣驗證。
- **待辦**：README 更新、最終分析報告、prompts/ 資料夾、是否重新驗證關鍵數字。
- **關鍵學習**：錨點 = item 編號 + 順序（不用標題字串）；大聲失敗安全、無聲失敗優先威脅；結構層可證明封閉、呈現層只能估計；成功是「被佐證」而非「被證明」。

使用者接著明確說：「這是我的交接摘要，請以它為準，我們要做層級二驗證。」

---

## 1. 層級二驗證：路徑選擇（Path A vs B）

Claude 讀完交接摘要後，指出一個關鍵事實：**當時對話所在的 container 環境是空的**，沒有使用者本機的專案檔案，兩者是不同的執行環境。因此提出兩條路：

- **Path A**：使用者把專案打包上傳到這個對話，Claude 直接在 container 裡實跑。
- **Path B**：維持使用者慣用的 VS Code + Claude Code，由 Claude（此對話）撰寫指令，使用者貼給 Claude Code 執行、再回報結果。

使用者一開始選 Path A，Claude 給出了 macOS 下打包（zip，排除 `.venv`/`.git`/`__pycache__`）與上傳的具體步驟。但使用者隨後改變主意，明確選擇 **Path B**：「不然你就給我指令讓我丟給Claude code跑，我再回傳結果」。自此，整個對話的協作模式確立為：

> **Claude（本對話）負責分析、規劃、撰寫「自足」指令 → 使用者複製貼給 Claude Code（VS Code 擴充套件）執行 → 使用者以截圖或文字回報結果 → Claude 判讀、決策、產生下一步指令。**

Claude 同時建立了貫穿全程的紀律：**唯讀調查優先於任何修改**——每次要下判斷或改 code 前，先用不改動任何檔案的指令去看實際 code、實際數據，不憑印象或記憶。


---

## 2. 三份 ground truth 實跑與 MSFT 1994 Item 14 沉默失敗的發現

### 2.1 唯讀調查：確認 pipeline 進入點與結果結構

第一個下給 Claude Code 的指令是純唯讀調查，目的是搞清楚：

- **真實 fixture 位置**：`tests/fixtures/real/`，三份分別為 `msft_10k_fy1994_ascii.txt.gz`（110K）、`msft_10k_fy2023.htm.gz`（375K）、`apa_10k_fy2023_merged12.htm.gz`（242K），皆 gzip 壓縮。
- **Pipeline 進入點**：`src/sec10k/pipeline.py` 的 `run_pipeline(raw: bytes, ruleset: Ruleset | None = None) -> tuple[Ruler, FilingResult]`。吃「已解壓的 raw bytes」，內部自理 FYE 抽取、ruleset 載入、Stage1/2/3。
- **結果結構**：`FilingResult`（`items`/`residual`/`filing_status`/`filing_confidence`/`verification_report`）；`Item`（`item_id`/`part`/`char_span`/`status`/`confidence`/`method`/`reason_codes`/`source_ref`/`merged_into`）；`VerificationReport`（`violations`/`invariant_results`/`filing_status`/`filing_confidence`）。
- **既有測試**：`tests/test_real_integration.py` 會跑真實檔，但**只驗「有誠實產出結果」，不做 ground-truth 對照的分段正確性驗證**——這正是層級二要新增的部分。
- **讀檔方式**：`.gz` 需呼叫端自行 `gzip.decompress`，pipeline 內部不處理壓縮。
- **Python 版本**：3.14.0；import 根為 `src`，正確寫法 `from sec10k.pipeline import run_pipeline`。

### 2.2 三份真實檔實跑結果

用一支唯讀 `scripts/level2_validation_run.py` 對三份檔實跑，結果：

| 檔案 | FYE | Era | items | filing_status | 不變量 |
|---|---|---|---|---|---|
| MSFT FY1994 | 1994-06-30 | era_1994 | 14 | PASS | 8/8 |
| MSFT FY2023 | 2023-06-30 | era_2020 | 20 | PASS | 8/8 |
| APA FY2023 | 2023-12-31 | era_2023 | 21（geometric 20） | PASS | 8/8 |

**三份 era 全部正確挑選**：MSFT 1994 正確挑到 era_1994（此前貫穿全專案的原始 bug——1994 被現代規則誤判缺 1A/1C——已確認修好）；MSFT 2023 正確挑到 era_2020（無 1C，因 FYE 早於 12/15 門檻）；APA 2023 正確挑到 era_2023（含 1C）。

**APA 的 merge 完全正確**：Item 1 = MERGED（持 span）、Item 2 = MERGED（`merged_into=1`、無 span），`legal_structure` 不變量 PASS。

**一個關鍵發現：MSFT FY1994 的 Item 14 判錯**。實跑顯示 Item 14 = `part=III`、`status=INCORPORATED_BY_REFERENCE`，但依 §7 驗收條件，ground truth 是「Item 14 = Exhibits / Part IV / 實體內容」。**兩個維度都錯，但檔案的 filing_status 仍是 PASS、8/8 不變量全過、0 violations**——這是本輪驗證中第一個、也是最關鍵的「沉默失敗」案例。

Claude 同時釐清了一個交接摘要裡的措辭張力：摘要 §7 說 ground truth 是「18 筆 item」，但實跑只切出 14 筆。經釐清：**14 是「該實際出現並抽取」的數；18 是 era_1994 ruleset 宣告的 ItemRule 總數（14 個真實 item + 4 個 ABSENT 佔位：1A/1B/7A/9A）**。兩者不衝突，14 是對的。

### 2.3 根因初步定性：唯讀查證 era_1994 資料

透過唯讀取碼確認：
- `ERA_1994` 的 Item 14 宣告：`part=PART_IV`、`exp=REQUIRED`、`topic="Exhibits, Financial Statement Schedules, and Reports on Form 8-K"`——與 ground truth 完全一致，**era 端資料本身沒錯**。
- `ERA_1994.legal_structures` 只有一個 `part_iii_incorporated_by_reference`，其 `absences=['11','12','13']`——**14 不在 absences 裡**，即 era_1994 並未授權 Item 14 缺席/IBR。
- **part 判錯來源**：segmenter.py:160/166 建 Item 時 `part=part_of(a.item_id)`，這個 `part_of()` 讀的是 loader.py 的 `_PART_OF` 對照表，那是「現代」的固定表（現代 Item 14 = Principal Accountant Fees = Part III）。**segmenter 完全沒有查 era ruleset 的 per-item part**——不論哪個 era，item 14 一律被貼上現代的 Part III。這正是 MSFT 1994 的 Exhibits（應為 Part IV）被錯標成 Part III 的直接原因。是 **era-blind 的 part 指派**，與 era_1994 正確的 `part=PART_IV` 資料脫節。
- **status 判錯來源**：`status=INCORPORATED_BY_REFERENCE` 的唯一賦值點在 segmenter.py:89（依內文判定的函式內），是「讀該 item 區段的內文、偵測 IBR 語氣」得出的 runtime 觀察，同樣是 era-blind。MSFT 1994 的 Item 14 是 Exhibits 實體內容卻被判 IBR，屬內文式偵測的誤判，與 ruleset 無關。
- **為何 Stage 3 仍全 PASS**：`invariants/checks.py` 用 `allowed_absences(ruleset)`，但 part 標 III/IV 不是任何硬不變量的檢查對象，故 `no_overlap`/`coverage`/`order` 等都過；`should_exist` 因 Item 14 仍被判「存在」（IBR 也算存在）而不舉旗。**「part 標錯」與「Exhibits 誤判 IBR」都不在現有 8 項不變量的偵測面上，才會 filing_status=PASS 卻與 ground truth 不符。**

一句話定性：**根因 = segmenter 行為，且與 era 資料脫節：part 來自 loader 的現代 `_PART_OF` 字典，status 來自內文式 IBR 偵測；兩者都不查 era_1994 ruleset。era_1994 ruleset 的 Item 14 資料（Part IV / REQUIRED / 非 absences）本身完全正確，不是錯誤來源。**


---

## 3. 認識論釐清：ground truth 是什麼、層級二 vs 三 vs 四

在看到 Item 14 判讀後，使用者提出一個關鍵的方法論問題：**「為什麼你會說測試這幾份資料算是有 ground truth？一般來說沒有 ground truth，是因為每間公司各種年份的呈現方式近乎無限多種，是嗎？這樣的理解如果正確，又如何理解這幾個測試 case 呢？」**

Claude 的回答建立了貫穿全報告的核心認識論框架：

- **這裡的 ground truth 不是「知道所有申報檔的正確答案」**，而是「針對這三份特定檔案，有人逐字讀過、人工記下正確分段長怎樣」的答案卡，只涵蓋這三份。
- **「近乎無限多種呈現」只對了一半**——那是**呈現層**的無限。**結構/法規層**（某 era 該有哪些 item、編號、順序）**有界、可證明封閉**，直接由 SEC 規格決定，不需真實檔即可推定（era_2005 就是純用 SEC 規格建立、一份真實檔都沒有）。
- 兩種「沒有 ground truth」要分清楚：**分段的 ground truth**（人工讀就能確定，只是人力貴、做不了 at scale）vs **缺席歸因**（合法缺 vs 抓漏 vs 違規，三者症狀相同，原理上無法乾淨判定）。
- 回答「結構是不是 based on這幾個 case」：**一半對**——骨架來自 SEC 規格書，這三份真實檔的角色是（1）發現規格書沒寫的呈現層邊角、（2）確認規則在真實 bytes 上真的觸發。
- 「至少這幾個要全對」是**必要但不充分**的最低門檻——是地板不是天花板。且**這幾份的全對本身不是自動達成的**：MSFT 1994 Item 14 錯誤正好證明地板有洞，值得驗。

一句話收斂：**這三份的 ground truth 是人工逐份建立的答案卡；它們全對是必要的地板；但全對只是弱證據，真正的推廣性靠「規格封閉的結構層」+「抽樣估計的呈現層」，後者是後續工作。**

（這個框架在後續第 16 章擬報告第 1、2 段時被進一步精確化：報告不再籠統稱「層級二」，而是明確區分「3 家強驗證」與「11 家層級二廣度延伸（無 ground truth，較弱）」，並寫死「層級三、層級四未執行」——詳見第 16 章。）

---

## 4. 近年 11 家 eval set 設計與抓取

在確認 Item 14 根因定性（part 判錯出於 segmenter era-blind、status 判錯出於內文式 IBR 偵測過火）之後，使用者提出策略性問題：週四中午時間評估，決定「先將架構拿近年各公司實作、失敗案例回頭修改、達一定數量後改純記錄、再進前端 Stage 6」，並詢問 MSFT 1994 Item 14 的錯誤要不要先修。

Claude 判斷 **Item 14 的兩個子問題都不構成「必須先修」的理由**：
- **part 判錯**近年公司機制上不會復發（近年 era 本身就是現代結構，`_PART_OF` 表對它們剛好對，已由後續近年實跑的 part 欄位佐證）。
- **status 判錯**目前沒看到復發證據（近年 Exhibits 項都正確判 EXTRACTED），但無法完全排除，列入 watchlist。

使用者同意「先不修 Item 14，當錯誤報告」，並要 Claude 決定近年公司清單抓幾份、公司清單怎麼產生。使用者選擇「10–12 份」、「你用 web 工具去 EDGAR 幫我查證真實清單」。

Claude 用 web_search 查證了 EDGAR 上的 merge 案例，確認 **Devon Energy FY2023** 與 **Prologis FY2023** 為近年真實案例（Devon 是近年 Items 1&2 merge 案例，Prologis 是 REIT 雙註冊人合併申報），最終定案 **11 家清單**：

| 公司 | ticker | 預期 era | 分散軸 |
|---|---|---|---|
| Apple | AAPL | era_2020 | 科技、9 月 FYE、乾淨 baseline |
| Nike | NKE | era_2020 | 消費、5 月 FYE |
| P&G | PG | era_2020 | 消費必需品、6 月 FYE |
| JPMorgan | JPM | era_2023 | 銀行、Part III IBR-to-proxy |
| Berkshire Hathaway | BRK.B | era_2023 | 排版樸素、壓力測試 |
| Pfizer | PFE | era_2023 | 製藥 |
| Tesla | TSLA | era_2023 | 汽車/科技 |
| Walmart | WMT | era_2023 | 零售、1 月 FYE |
| Devon | DVN | era_2023 | 油氣 E&P、Items 1&2 merge |
| Prologis | PLD | era_2023 | REIT、雙註冊人 |
| NextEra | NEE | era_2023 | 公用事業 |

抓取方式：不憑記憶背 CIK/accession，而是寫兩支腳本 `scripts/fetch_eval_set.py`（先抓 `company_tickers.json` 把 ticker 對到 CIK、再抓 submissions JSON 找目標年度 10-K、下載主檔，SEC 要求 User-Agent header，`filings.recent` 是欄狀平行陣列且不保證新到舊排序）與 `scripts/eval_recent_run.py`（逐檔實跑並印出跨檔彙總表）。存放於新資料夾 `tests/fixtures/eval_recent/`，與 ground-truth 的 `tests/fixtures/real/` 分開，此區分正是「結構可證明 vs 呈現需抽樣」誠實敘事的一部分。

**抓取結果：11/11 全成功、0 失敗**，且 era 目標分佈精準命中——AAPL/NKE/PG 三家刻意抓 FY2023（早於 1C 門檻，落 era_2020），其餘八家抓最新（落 era_2023），配置為 **3 份 era_2020 + 8 份 era_2023**。

（過程中使用者中途詢問「Claude Code 開新對話會不會遺失紀錄」，Claude 查證 Claude Code 官方文件與已知 issue 後回答：官方設計上關閉分頁後歷史仍可從 Session history 找回，但 VS Code 擴充套件這塊有多個已知 bug（GitHub issue #45424/#9258/#13872 等）可能導致 UI 上找不到；建議若有需要保留的內容先複製走。）


---

## 5. 首次 11 家實跑：結果判讀（8 PASS / 6 FAILED，confidence 機制）

跑 `eval_recent_run.py` 後的 CROSS-FILE SUMMARY（首次結果）：

| 檔案 | items | status | inv | viol |
|---|---|---|---|---|
| AAPL | 20 | PASS | 8/8 | 0 |
| BRK-B | 15 | **FAILED** | 6/8 | 2 |
| DVN | 21 | PASS | 8/8 | 0 |
| JPM | 20 | **FAILED** | 7/8 | 1 |
| NEE | 21 | **FAILED** | 7/8 | 25 |
| NKE | 19 | **FAILED** | 7/8 | 1 |
| PFE | 19 | **FAILED** | 7/8 | 1 |
| PG | 9 | **FAILED** | 6/8 | 13 |
| PLD | 21 | PASS | 8/8 | 0 |
| TSLA | 21 | PASS | 8/8 | 0 |
| WMT | 21 | PASS | 8/8 | 0 |

**5 家 PASS、6 家 FAILED**。使用者詢問兩個問題：（1）為何很多 item 的 confidence 是 MEDIUM；（2）為何有些 FAILED，並好奇是不是誤讀了「JPM 的不變量看起來是錯的」。

Claude 的回答：
- **confidence 機制**：RESERVED/IBR 一律 HIGH（檔案自己白紙黑字寫的短標記，明確無歧義），EXTRACTED 一律 MEDIUM（框內容邊界屬估計，非證明）。
- **6 個 FAILED 分四組症狀**：(A) Item 1 未偵測（BRK-B/JPM/NKE，第一個抓到的是 1A）；(B) 前段整批丟失（PG，只抓到 9–15）；(C) 短的主 item 沒抓到（PFE 缺 Item 4）；(D) coverage 重疊（NEE，25 個 violation，游標卡在末尾）。
- 兩個亮點：DVN 的 Item 1+2 merge、PLD 的雙註冊人合併申報都正確過關。
- **JPM 誤讀更正**：Claude 承認上一則把 JPM（本身是 FAILED、不變量正確）錯誤地放進「PASS 需警惕」的段落舉例，造成誤導。更正後說明：真正想強調的重點是 JPM 內部出現 Item 8 僅 369 字、Item 15 卻吞了 89 萬字的極端不對稱——這種「內容錯位」現有不變量抓不到，是提醒「PASS 檔仍需人工抽查」的理由，與 JPM 本身是否 PASS 無關。

---

## 6. 根因調查：A 組（BRK/JPM/NKE）Item 1 缺失

使用者選擇「C：查 A 組根因，順便抽查一份 PASS 檔（WMT）有無沉默失敗」。

### 6.1 第一輪唯讀診斷

寫一支唯讀腳本印出三家的 `[RAW]`（原始 bytes 掃描）、`[RULER]`（Stage-1 正規化後文字）中「Item 1 ... Business」候選位置，並印第一個偵測到的 item 起點。結果：

- 真正的「Item 1. Business」body 標題在**正規化後的 ruler 文字裡確實存在**，且位置很前面（BRK offset=8148、JPM offset=6523、NKE offset=5707）。
- 但 pipeline 把第一個 item 錨點定在 **1A**（span_start 分別 134954/45363/44031），那個更早的 Item 1 body 標題**沒有被採納為錨點**。
- **排除假設 A**（Stage 1 前置資料隔離吞掉 Item 1）：文字仍在、未被切除。
- **定性為假設 B**：anchor 消歧邏輯判斷失誤。每家的「Item 1. Business」在 ruler 裡都出現多次且緊貼在 TOC 正後方（一筆是 TOC 目錄列，隔一兩千字後才是真正的 body 標題），body 標題離 TOC 太近（差距僅約 1.4k–2.8k 字），anchor 的「TOC vs 本文」消歧邏輯無法把 body 標題和上面的 TOC 目錄列分開，於是把早期所有 Item 1 命中都當成 TOC 而丟棄，序列直接從下一個乾淨、單一出現的 1A 起算。
- **WMT 沉默失敗抽查**：逐項 head line 與應有標題一一對上，未發現誤切，PASS 可信。

### 6.2 第二輪：anchors.py 的確切消歧判準

唯讀取碼 `src/sec10k/segment/anchors.py`：

- `find_anchors()` **不做任何消歧**，只用 `_ANCHOR` regex 找出所有候選、依文件順序回傳（docstring 明言：TOC echoes/cross-references/ordering 的消歧是 segmenter 的工作，不是 regex 的）。
- 真正的判準在 `segment/segmenter.py`，兩道閘：
  - **閘 (a) 前置區排除**（`run_stage2` 第 137–142 行）：`front = [rc.char_span for rc in ruler.residual_candidates if rc.classification in (ResidualClass.COVER_PAGE, ResidualClass.TOC)]`；`anchors = [a for a in find_anchors(text) if not _in_any(a.enum_start, front)]`。
  - **閘 (b) 單調遞增順序過濾**（`_greedy_monotonic`）：走文件順序，`idx = ruleset.order_index(a.item_id)`；只接受 `idx` 嚴格大於已接受的 `last` 者，否則丟棄。
- **確切判準與門檻**：系統沒有任何「這行看起來像 TOC 還是 body」的文字/樣式判準，也沒有距離門檻。只靠兩件事：(1) 位置——anchor 的 `enum_start` 是否落在 Stage-1 已標為 COVER_PAGE/TOC 的區間內；(2) 順序——存活候選中，只接受 `order_index` 嚴格遞增者。
- **關鍵結論**：TOC 消歧完全依賴「Stage-1 把 TOC 區間框對」。regex 一定會同時抓到 TOC 目錄列與 body 標題；能不能只保留 body，取決於 Stage-1 的 TOC/cover 區間邊界是否精準。


---

## 7. 根因調查：PG 的 run 斷裂

同步對 PG 做唯讀診斷，印出 Item 1/2/5/7/8 等關鍵標題在 ruler 文字裡的實際位置與偵測到的 item span。

**第一版判讀（後被推翻）**：Claude Code 起初判斷 PG 是「一行多 item」導致 anchor line 太少。**這是錯的，是 head 印字把換行換成空白造成的假象**——後續實測掃描證明 PG 的 TOC 其實是一 item 一行（Item 1@4668、1A@4686…各自獨立成行）。Claude 主動揭露此誤判並更正，這是本輪多次「AI 自我修正」實例之一。

**正確機制**：PG 的 TOC 目錄列在 Item 8@5187 與 Item 9@6116 之間有一個 **929 字的內部空隙**（推測是插了 PART 分隔之類的非 anchor 文字），把下一條目錄列的 start 推遠。這個空隙超過 `_TOC_GAP`(600) 也超過 `_DENSE_GAP`(700)，导致 `_runs()` 在此把 TOC 切成兩段：`run#0`（items 1–8，offset 4668..5187）與 `run#1`（items 9–16，offset 6116..6840，尾端還黏了一個往回跳的 body Item 1@6840）。`_first_run()` 只取第一個 len≥6 的 run 就 `return`，`run#1`（9–16）**永遠不會被標成 TOC**，於是漏出。

**後果鏈**：TOC 尾段 9–16 的 `enum_start` 都落在 front 之外 → 閘 (a) 放行；文件順序上先遇到它們，`order_index` 嚴格遞增 → 閘 (b) 全部接受，`last` 被推到最高；之後真正的 body（Item 1@6840、1A、2…）`order_index` 都 ≤ 尾段最高值 → 被 `idx <= last` 全數否決。結果只「抓到」TOC 尾段那 9 個微小目錄列，整份 body 變成巨大 unclassified residual——與先前 eval 完全吻合（items=9、四塊 unclassified 57941/202357/4655/12476 字）。

**A 組 vs PG 的差異（同一子系統的相反邊界誤差）**：A 組（BRK/JPM/NKE）是 Stage-1 TOC/cover 區間邊界落在真 Item 1 body 標題之後、1A body 之前，只多吞掉 body Item 1 一個錨點（over-extend，輕症，只缺 1 個 item）；PG 是 Stage-1 TOC 區間邊界落在 TOC 正中央（9–15 目錄列之前），TOC 尾段漏出成錨點，經單調過濾反噬、把整個 body 壓掉（under-extend，重症，缺 8+ 個 item）。**一句話**：是同一根因家族——Stage-1 的 TOC/cover 區間界定精度，透過 Stage-2 的 `_in_any(front)` 排除閘 + `_greedy_monotonic` 單調閘被放大；不是 regex、也不是掉字。

---

## 8. 根因判準最終定位（front_matter.py 逐字取碼）

使用者選擇先做「實測量化」而非直接下結論：唯讀印出 BRK 與 PG 的 Stage-1 `residual_candidates`（COVER_PAGE/TOC）的**實際 char_span**，量化越界幅度。

### 8.1 第一輪量測（BRK + PG）

- **BRK-B**：Stage-1 TOC span = `[5331, 8177)`；真 Item 1 body 標題在 offset **8148**。8148 < 8177 → body 標題的 `enum_start` 落在 TOC 區間內，被閘 (a) 丟棄。TOC 只多框了 `8177−8148=29` 個字，但剛好蓋過 Item 1 body 標題起點 → Item 1 消失。1A body 在 134954，遠在 front 之外，正常保留。**誤差量級 = 29 字**（此前 Claude 曾推論「Stage-1 吞掉整段 Item 1 正文（~12 萬字）」，這次實測**否證**了該推論，Claude 主動更正）。
- **PG**：Stage-1 TOC span = `[4668, 5194)`，長度只有 526 字——但實體 TOC 目錄列一路排到 ~6833。TOC 只框住前段（items 1–8 目錄列），尾段（9–15 目錄列，6116–6833）掉在 front 之外。**誤差量級 = TOC 至少短框了 1600+ 字**。

### 8.2 第二輪量測（JPM + NKE，補齊 A 組全部三家）

| 公司 | COVER_PAGE 結束 | TOC 結束（front max_end） | 真 body Item1 起點 | over-extend | first detected |
|---|---|---|---|---|---|
| BRK-B | 5331 | 8177 | 8148 | **+29 字** | 1A@134954 |
| JPM | 5113 | 6540 | 6523 | **+17 字** | 1A@45363 |
| NKE | 3964 | 5723 | 5707 | **+16 字** | 1A@44031 |

**A 組三家完全同一根因、同一量級**：TOC 結束邊界一律多框 ~16–29 字，剛好蓋過緊接其後的 body「Item 1. Business」標題起點，使該錨點 `enum_start` 落在 front 內、被閘 (a) 丟棄，序列因此從 1A 起算，單缺 Item 1（輕症）。過度延伸量級（~16–29 字）約等於「Item 1. Business」這串標題本身的長度，說明 TOC 區塊偵測的結束邊界吃進了 body 第一個標題的 enumerator，而非停在「最後一條目錄列」與「第一個 body 標題」之間。

（過程中一則 NKE 的量測腳本有小瑕疵：`[MEASURE]` 用 `hits[-1]`（body 深處第三筆回指，offset 150272）當比較基準，算出負值沒有意義；Claude Code 主動發現並改用 `hits[1]`（緊接 TOC 之後的真正 body 標題，offset 5707）重算，得到正確的 +16 字。這是又一次「AI 自我修正」的實例。）

### 8.3 front_matter.py 完整原始碼

在寫任何修改指令前，Claude 堅持先唯讀取得 `src/sec10k/ruler/front_matter.py` 的**完整逐字原始碼**（143 行），而非依賴 Claude Code 的摘要（因為摘要在此輪已出現過至少兩次錯誤：「相鄰=index 連續」定義的 bug、PG「一行多 item」的誤判）。取碼後確認核心結構：

- `_ITEM_LINE = re.compile(r"^\s*items?\s+(\d{1,2})([A-Za-z]?)\b", re.IGNORECASE)`：行首錨點正則，**只看「Item N」開頭，無法區分 TOC 列與 body 標題**。
- `_PAGE_REF`：判斷該行是否帶頁碼引導（dotted leader/trailing number）。
- 常數：`_TOC_GAP=600`（page-ref 路徑 gap）、`_MIN_TOC_ENTRIES=6`（最少目錄條目）、`_DENSE_GAP=700`（density 路徑 gap）、`_TOC_FRONT_FRACTION=0.2`（density-detected TOC 必須在文件前 20% 內開始，用以防止深處密集短 item 誤判成 TOC，docstring 明確提到 APA FY2023 的 9B/9C/10-15 深處密集 run 案例）。
- `_lines()`：逐行切分文字。
- `_anchor_lines()`：回傳 `(start, end, has_page_ref)` 元組陣列。
- `_runs(items, gap)`：把相鄰 `start` 差 ≤ gap 的行串成極大連續段（run）。
- `_first_run(items, gap, minlen)`：回傳第一個長度 ≥ minlen 的 run 的 span（`CharSpan(start=run[0][0], end=run[-1][1])`）。
- `detect_toc(text)`：先試 page-ref 路徑（`_first_run(refs, _TOC_GAP, _MIN_TOC_ENTRIES)`），沒有再試 density 路徑（`_first_run(anchors, _DENSE_GAP, _MIN_TOC_ENTRIES)`，且必須 `start <= len(text) * _TOC_FRONT_FRACTION`）。
- `detect_cover_page(text, toc)`：cover = `[0, toc.start)`，完全被動——TOC 一旦框錯，cover 也跟著錯。
- `isolate_front_matter(text)`：整合上述，回傳 `[ResidualSpan(cover), ResidualSpan(toc)]`。
- `CharSpan`（`contracts.py:41`）是 **frozen** 的 Pydantic model，`start`/`end` 皆 ≥0，`end<start` 會擲 `ValueError`；有 `.length`、`.overlaps()`。修改須用建構子重建，不可原地 mutate。


---

## 9. 修復範圍決策（甲/乙；PG 是否一併修）

在根因完全釘死後，使用者提出一個關鍵的策略性問題：**「如果其實多數其他我們未測到的公司，在我們的架構下，是落在 PG 這種例子中，那反而修 A 組可能會比較不好？」**

Claude 的回答建立了另一個重要框架：
- **A 組修法（往回跳剪除）確定碰不到 PG**——機制上是相反方向（over-extend vs under-extend），A 組修法對 PG 沒有東西可剪，也不會讓 PG 更糟。
- 但**「PG 型在母體中是否占多數」這個問題，用當前層級二證據原理上答不出來**——11 家是刻意分散、非隨機/非飽和抽樣，A 型 3 家、PG 型 1 家的比例不能推廣到母體。這正是「呈現層無法枚舉」的具體例證，只能靠層級三（飽和抽樣）+ 層級四（Good-Turing）估計，明確超出本次時限。
- 建議先修 A 組（機制已釘死、風險低），PG 當已記錄失敗案例，因為修的先後與母體分佈無關，是穩健的工程順序。

使用者接著補充一個關鍵情境：**「我還想再測試第二輪（主要集中在金融以及科技業），並且第二輪我也希望能夠盡量修正錯誤。時間應該很 ok。在這個大任務前提下，你有建議要不要也改 PG 嗎？」**

Claude 因此**更新建議為「乙：這一輪一次修 A+PG」**，理由：（1）第二輪要打金融/科技，PG 型版面（TOC 中段被 PART 分隔撐出大空隙）在大型金融公司也可能出現，先修好能讓第二輪受惠；（2）機制熱、脈絡全，趁勢修比冷掉再回頭便宜；（3）A 組與 PG 修法可共用同一套紅燈測試與同一次回歸驗證。使用者同意「乙」。

---

## 10. 測試先行：TOC 缺陷紅燈測試

新增 `tests/test_frontmatter_boundary_regression.py`，含 5 條測試：
- `test_a_group_item1_business_is_detected`（parametrize BRK-B/JPM/NKE）：斷言 Item 1 存在且 status=EXTRACTED。
- `test_pg_early_items_are_detected`：斷言 PG 的 Items 1–8 皆存在、Item 1 status=EXTRACTED。
- `test_pg_body_not_lost_to_unclassified_residual`：斷言沒有大型（>1000 字）unclassified residual。

**首次執行結果：5/5 全部 FAIL**，且每個失敗訊息都精準對應已釘死的根因（A 組「Item 1 not detected at all」；PG「these Part I/II items were not detected: [...]」、「found 4 large unclassified residual block(s) (lens=[57941, 202357, 4655, 12476])」）。這證明測試真的抓得到 bug，測試先行的證據成立。

---

## 11. 階段 1 修復（A 組 backjump）與回歸

在改 code 前，Claude 再次要求先唯讀取得 `front_matter.py` 的最新原始碼（不憑摘要），確認要改動的函式現況。

**設計（純增添，不動既有四函式）**：新增 `_order_key(raw)`（解析行的 enumerator 為 order key，如 `Item 1A` → `(1, 'A')`）、`_anchor_lines_keyed`、`_runs_keyed`、`_trim_trailing_backjump(run)`（剪除 run 尾端「編號往回跳到低於該 run 最大 key」的候選）、`_first_run_keyed`；`detect_toc()` 內部改用 keyed 版本，簽章不變。判準只用 item 編號 + 順序，不碰標題字串，符合 CLAUDE.md 硬規則 2。

**修復結果**：
- `tests/test_frontmatter_boundary_regression.py`：**A 組 3 個轉綠、PG 2 個續紅（預期，本階段不處理 PG）**。
- 全套：`2 failed, 108 passed`（唯二 FAIL 就是那 2 個 PG 測試），**無任何既有測試退步**。
- 逐家對照（修正前 → 修正後）：JPM `FAILED 20 7/8 1` → **PASS 21 8/8 0**（★完全修好）；NKE `FAILED 19 7/8 1` → **PASS 20 8/8 0**（★完全修好）；BRK-B `FAILED 15 6/8 2` → `FAILED 16 7/8 1`（Item 1 找回、15→16 項，剩 1 個「無關」violation：9B 與 15 之間 421 字 unclassified，屬 Part III/exhibit 區塊的獨立問題，非本階段病灶，依鐵律未動）；AAPL/DVN/PLD/TSLA/WMT **全數零退步**。

---

## 12. 階段 2 修復（PG run 合併）與回歸

同樣先唯讀取得階段 1 改動後的最新 `front_matter.py`（207 行）現況，再設計階段 2。

**設計**：新增 `_merged_run_keyed(items, gap, minlen, text)`，取代 `detect_toc()` 裡兩處 `_first_run_keyed` 呼叫。從第一個夠長的 run 當種子，只在**同時滿足**「(a) 起點仍在文件前段 `_TOC_FRONT_FRACTION`」與「(b) 首 order key 延續遞增（大於已併入的最大 key）」時，才把後續 run 併入；合併後再套用既有 `_trim_trailing_backjump`。這兩道結構性守門（前段位置 + 編號延續遞增）能防止把文件深處的密集短 item run（如 APA FY2023 的 9B/9C/10-15，~46% 深度）誤併，因它們既不在前段、編號也往回跳。

**修復結果**：
- `tests/test_frontmatter_boundary_regression.py`：**5/5 全綠**（A 組 3 個維持、PG 2 個轉綠）。
- 全套：**110 passed**，0 failed（先前 108 passed + 2 failed → 現在 110 全綠）。
- 逐家對照：PG `FAILED 9 6/8 13` → **PASS 20 8/8 0**（★完全修好）；BRK-B/PFE/NEE 維持原狀（非本階段範圍）；其餘皆不變。
- 合規：只改了 `front_matter.py` 一個檔，判準只用 item 編號+順序+文件前段位置，未放寬任何 Stage 3 不變量門檻。

至此，四家 FAILED 中的三家（JPM/NKE/PG）已被同一根因、兩階段修復解決；剩 BRK-B（部分修復，Item 1 找回）、PFE（缺 Item 4）、NEE（25 個 coverage_overlap）仍為 FAILED，根因未定性、列為已記錄的失敗案例。


---

## 13. PASS 檔案人工抽查（8 家全數，head+tail 方法）

在確認測試綠燈之後，使用者延續前面「回歸保護測試不要只挑代表性樣本」的嚴謹態度，要求對所有 PASS 檔案做**人工逐項抽查**，理由是不變量能抓「大聲失敗」但抓不到「沉默失敗」（如已發現的 Item 14 案例）。

### 13.1 抽查方法

寫 `scripts/spotcheck_*.py`，逐 item 印出：`id / status / part / merged_into / len`，以及該 item span 的**開頭約 90 字（HEAD）**與**結尾約 60 字（TAIL）**，並標記 `<-- SHORT main item?`（len<200 的主 item）與 `gap-from-prev`（與前一個 item 的間隙）供人工核對「內容是否真的屬於該 item、有無溢出到下一個 item」。

### 13.2 分批抽查與結果

- **第一批（JPM/DVN/PLD/NKE）**：全部乾淨、無沉默失敗。DVN 的 Items 1&2 merge 正確（Item 1 span 完整涵蓋、Item 2 span=None/merged_into=1）。JPM 的 Item 8 僅 369 字（先前被懷疑可能錯位）經 HEAD/TAIL 確認是**真實排版**（本文寫「Refer to … pages 165–314」把 MD&A 指到別處），非分段錯誤，之前的懷疑被否證並更正。所有 SHORT 旗標皆為「合法的短」（Mine Safety Not applicable / Item 9 None / Reserved / Part III IBR）。
- **第二批（AAPL/TSLA）**：同樣全部乾淨，Item 1C（Cybersecurity）正確獨立切出，無沉默失敗。
- **第三批（WMT + PG re-check）**：WMT 升級到 head+tail 標準（先前只做過 head-only），乾淨。**PG 修復後抽查是本輪最有意義的確認之一**：Item 1「Business. The Procter & Gamble Company…」len 13597（真本文，不再是 TOC 目錄列）、Item 7 MD&A len 94918、Item 8 財報 len 101897，HEAD/TAIL 正確、互不吞入——**證明修復是真的把 body 正確分段，不是靠放寬門檻或表面轉綠**。同時發現一個新的 reserved 措辭變體：PG 的 Item 6 寫「Intentionally Omitted.」而非「[Reserved]」，故未被判為 RESERVED（而判 EXTRACTED），不影響正確性但屬 status 分類精度的已知限制——這是繼 MSFT「[Reserved]」、APA「…Omitted」之後的**第三種變體**。

**結論：11 家 eval 中的 8 家 PASS 全數完成 head+tail 人工抽查，皆可信，無任何一家發現沉默失敗（內容錯位/歸錯 item/溢出到相鄰 item）**。


---

## 14. Part era-blind 缺陷：發現、辯論（修 vs 不修）、決策

在 PASS 抽查完成、準備進入整理交件材料之際，Claude 提出把新增「近年公司列表」、開新對話避免 context 過長等建議。使用者回頭問了一個關鍵問題，觸發了本輪最重要的一次方向修正：

> **「你上面回覆說到，那邊主要是 segmenter 指派時『沒有』依照該檔的 era 規則。那為什麼如果是這種錯誤，不要現在修復？依照該檔的 era 規則不是我們這個專案應該死守的鐵律之一嗎？這個錯誤沒修好，在未來（例如 2030），難道不會有類似的錯誤發生嗎？」**

Claude 的回應是本輪一次明確的**自我修正**：
- **承認之前的判斷有滑動**：先前用「近年範圍無影響」的急迫性理由，暗示可以不修，但這回答的是「急不急」，沒回答「對不對」——這是兩件事。
- **精確拆解「未來會不會復發」**：**part 判錯**（用寫死的 `_PART_OF` 現代表）在「檔案真實結構 = 那張表所編碼的結構」時剛好碰巧對，但**只要出現「檔案真實結構 ≠ 那張表」的情況就會復發**——不只在舊檔（era_1994），若未來 SEC 再做一次類似 2003 年 Item 14→15 位移的改制，同一錯誤會在當代檔上重演。這是**結構性脆弱點**，不是一次性特例，且明確違反專案「結構依 era 規格」的核心原則。**status 判錯**（IBR 內文偵測過火）是不同性質的精度問題，與此無關。
- **同時誠實攤開「修」的真實成本**：這不是改一行，而是要動**資料契約**（`contracts.Ruleset` 目前很可能沒有帶 per-item part）、picker 轉換、segmenter 三處，回歸面遠大於 TOC 那兩階段的單檔增添。
- **撤回原本「不修」的建議傾向**，把決定權交還使用者，並提出三個選項（修-A 立即修/修-B 記錄後排入後續/修-C 先唯讀查工程量再決定）。

使用者選擇 **修-A：這一輪就修**。


---

## 15. Part 缺陷修復：查證、設計選擇（Y：不 fallback）、測試先行、修復、回歸

### 15.1 唯讀取碼：part 資料流全貌

先唯讀取得 part 指派的完整資料流：

- `segmenter.py:160/166` 直接呼叫 `part_of(a.item_id)`（`from ..ruleset.loader import part_of`），**完全沒用 `run_stage2(ruler, ruleset)` 已持有的 ruleset**。
- `loader.py:140-142`：`part_of(item_id) = _PART_OF.get(item_id)`；`_PART_OF`（loader.py:39-44）是寫死的現代對照表（1-4=I、5-9C=II、10-14=III、15-16=IV）。
- **好消息：era 端早就有正確的 per-item part，只是載入時被丟棄**。`era.py` 的 `ItemRule`（75-88）本有 `part: Optional[Part] = None` 欄位；`Part` 是型別化 enum（`PART_I`.."IV"，docstring 明說是「a typed form of loader.py's `_PART_OF` dict」）；`EraRuleset` 的 validator 強制「REQUIRED/RESERVED 必須有 part」。但 `_era_to_ruleset()`（loader.py:103-137）**只萃取了 `expected_items`/`reserved_items`/`legal_structures`，完全沒把 `r.part` 帶進 `contracts.Ruleset`**；而 `contracts.Ruleset`（contracts.py:262-279）目前也**沒有 per-item part 欄位可承接**。

### 15.2 前置查證（動手前的兩個必要確認）

使用者要求「先唯讀把 PG 機制釘死」同樣的謹慎，在此重演為「先確認 era 資料是否真的填對、再確認改動的爆炸半徑」：

1. **四個 era 的 `ItemRule.part` 是否都填對，尤其 era_1994 Item 14**：唯讀取碼確認 `ERA_1994` 的 Item 14 = `part=Part.PART_IV`（topic「Exhibits, Financial Statement Schedules, and Reports on Form 8-K」），與 ground truth 完全一致。ERA_2005/2020/2023 的 part 分佈皆與 `_PART_OF` 一致（因近代結構未變）。**唯一與現代表分歧的就是 era_1994 的 Item 14（IV vs III）**——這正是缺陷案例本身，era 端資料正確、不是錯誤來源。
2. **`part_of()`/`_PART_OF` 的呼叫點與爆炸半徑**：`part_of()` 只有 segmenter.py:160、166 兩處呼叫；`_PART_OF` 只被 `part_of()` 自己引用；**`tests/` 完全沒有引用 `part_of` 或 `_PART_OF`**（grep 空）——改動風險極低。`minimal_modern_ruleset()` 是**死碼**（只在定義處與 `__init__.py` 的 import/`__all__` 出現，src 與 tests 皆無實際呼叫點）。

### 15.3 設計選擇：要不要 fallback？（使用者拍板）

Claude 提出一個關鍵設計岔路，交由使用者決定：

- **選項 X（有 fallback）**：`part_of()` 查無時回退舊 `_PART_OF`。優點：向後相容、`minimal_modern_ruleset` 死碼建的 Ruleset 仍能拿到 part。缺點：沒有完全根除 era-blind 精神，留了一條「悄悄用回現代表」的暗路。
- **選項 Y（無 fallback）**：查無時回 `None`，完全依 era。優點：徹底根除缺陷，若未來某 era 資料漏填會顯現成 `None`（逼出問題而非默默錯值）。缺點：需先確認沒有測試直接建構空 map 的 Ruleset。

再做一次唯讀查證後確認：**所有拿到 `contracts.Ruleset` 的測試都經 `load_ruleset()` → `_era_to_ruleset()`，沒有任何測試直接建構 `Ruleset(...)` 或呼叫 `minimal_modern_ruleset()`**。因此只要 `_era_to_ruleset` 帶入 part map，實際流程永遠有完整 map，不會走到 None 分支——**選項 Y 安全**。使用者選 **Y**。（附帶發現：`test_era_schema.py:146` 早已寫死斷言 `by_id["14"].part is Part.PART_IV`、註明「bug-fix core」，與本次修復方向完全一致，是既有測試就寫死的 ground truth，非新編。）

### 15.4 護欄範圍決策（使用者要求全部 14 份，最嚴格比對）

使用者對回歸測試的嚴謹度持續加碼：先問「回歸保護測試為什麼不要測全部？」，Claude 承認先前只挑三家的理由站不住，改為涵蓋**全部 11 家 eval**；使用者進一步要求「我想要全部 11 家…我希望所有狀況真的跟我們預期一樣」，並在下一輪追加**再納入 MSFT FY2023、APA FY2023**（合計 13 份護欄基準 + MSFT FY1994 的變更斷言）。比對嚴格度也選擇 **(乙) 比對 (item_id, part) 有序序列**（而非只比 part 值），能同時抓 part 漂移與 item 順序/集合意外改變。

先跑唯讀腳本抓齊 13 份基準（11 家 eval + MSFT FY2023 + APA FY2023），確認：
- 11 家近年 eval 全部 10-14=III、15=IV（含 DVN 的 1&2 merge：`1:I, 2:I, 1A:I...` 排序）。
- MSFT FY2023：20 項，標準現代分佈（無 1C，因 FYE 早於門檻）。
- APA FY2023：21 項，含 merge（`('1','I'),('2','I'),('1A','I')...`）。
- **MSFT FY1994 現況**：`14:III`（缺陷起點坐實）。

### 15.5 紅燈測試與修復

新增 `tests/test_part_era_regression.py`：
- `test_part_guardrail_ordered_sequence_unchanged`（parametrize，13 份護欄）：斷言各檔的有序 `(item_id, part)` 序列 == 修改前基準。
- `test_msft_fy1994_item14_is_part_IV`：斷言 Item 14 part == "IV"（**紅燈，現況 III**）。
- `test_msft_fy1994_items_1_to_13_parts_unchanged`：斷言 items 1-13 序列不變（護欄）。

**首次執行：`1 failed, 14 passed`**——剛好紅在缺陷那條，14 條全綠，測試先行證據成立。

**修復三處**（純增添 + 兩處帶入，符合 Y 設計）：
1. `contracts.py`：`Ruleset` 新增 `item_parts: dict[str, str] = Field(default_factory=dict)` + `part_of(self, item_id) -> str | None` 方法（查無回 None）。
2. `loader.py::_era_to_ruleset`：帶入 `item_parts={r.item_id: r.part.value for r in era.items if r.part is not None}`。
3. `loader.py::minimal_modern_ruleset`（死碼一致性）：也帶入（用 `_PART_OF` 當來源），避免未來若被呼叫會拿到空 part。
4. `segmenter.py:160/166`：`part=part_of(...)` 改為 `part=ruleset.part_of(...)`。`_PART_OF`/`part_of()` 保留不刪（`era.py` docstring 引用仍在）。

**修復結果**：
- `test_part_era_regression.py`：**15/15 全綠**（紅燈轉綠、14 條護欄維持）。
- 全套：**125 passed**（先前 124 passed + 1 failed → 125 全綠，無退步）。
- 11 家 eval CROSS-FILE SUMMARY 與修正前**完全相同**（part 分佈與 filing_status 零退步）。
- **MSFT FY1994 Item 14 現在 = Part IV（原 III），items 1-13 不變**，以交件前重跑核對確認。

### 15.6 修復的意義與誠實邊界

Claude 主動強調：這次修的是**沉默失敗**（filing_status 一直是 PASS、8/8 不變量全過），與 TOC 兩階段修的**大聲失敗**性質不同——這正是「不變量偵測不到的錯誤，補上一道專屬測試防線」的價值所在。同時明確保留邊界：**只修了 part 那一半，status（IBR 誤判）那一半本輪刻意未修**（使用者在此前已選擇「(a) 只驗 part，status 不寫測試」），報告與 commit message 都須誠實反映「Item 14 的 part 缺陷已修，status 判定仍為已知限制」，不可稱「Item 14 已完全修復」。


---

## 16. 層級二驗證報告：大綱協商與逐段擬定（0–9 段 + 英文摘要）

### 16.1 大綱提出與三個關鍵修正

Claude 先提出九段式大綱（0 摘要、1 目的與範圍、2 驗證方法、3 eval set 設計、4 抽取得好的公司、5 發現的問題/根因/修復、6 沉默失敗對照案例、7 已知限制、8 方法邊界與後續工作、9 AI 協作品質），並主動提醒「效能/成本/擴充性分析」不在此份報告範圍。

使用者提出三個關鍵修正，全部被採納：

1. **「目的與範圍」需要修正——是不是已經邁入層級三？** Claude 澄清：**不是**。層級三的靈魂是「抽樣規模與代表性足以對母體做涵蓋率估計」，11 家刻意分散、非飽和抽樣，構不成層級三。正確描述是「兩種強度：3 家強驗證（有 ground truth）+ 11 家層級二廣度延伸（無 ground truth，靠不變量+抽查）；層級三/四明確未做」。第 1、2 段據此改寫。
2. **放入 repo 跟 README 的差別？** Claude 說明兩者不衝突、分工互補：完整報告放 `docs/`（`VALIDATION_part_1.md`），README 只放摘要+連結（門面/導覽性質）。
3. **效能/成本/擴充性延到 Stage 6 + Stage 4 完成後的整體總覽**——使用者主動決定的排程，Claude 認同並在報告中加入一句佔位句，避免評審誤以為遺漏。

### 16.2 逐段內容協商重點

- **第 0 段（摘要）**：先擬「僅發現沉默失敗」版本，待 part 修復完成後**更新為「發現並修復兩類缺陷（大聲/沉默）」**，測試數同步更新為 125。
- **第 4 段（抽取得好的公司）**：MSFT FY1994 **不放入乾淨清單**（因 Item 14 缺陷），改在第 6 段完整交代——這是使用者確認過的分流決策。
- **第 6 段（沉默失敗案例）**：拆成「維度一：part 判錯（已修）」與「維度二：status 判錯（未修，列已知限制）」，明確不可稱「Item 14 已完全修復」。
- **第 7 段（已知限制）**：三家 FAILED（BRK-B/PFE/NEE）症狀 + 明寫「根因未定性」；使用者要求加一句前瞻——「這類問題可能於後續金融/科技擴大抽樣中再現，屆時彙集同型案例一併定性修復」（已加入）。
- **第 2 段**：對 `item8_xbrl`、`cross_method` 兩項不變量採**保守寫法並明標**——本輪未特別觸發、未取原始碼，故只描述大致職責、不逐字驗證細節；使用者明確要求「記得標明清楚」。
- **第 9 段（AI 協作品質）**：使用者要求加入「AI 協作分兩層：規劃/分析層與本機執行層（Claude Code）」的說明，並列出四個具體的「AI 自我修正」實例（相鄰性判準修正、PG 一行多 item 誤判推翻、量測基準取錯的自我揭露、指令禁止範圍內誠實回報而非越界）。

### 16.3 落地前的交件數字核對（誠實紀律）

使用者選擇「乙：落地前先重跑核對數字再寫檔」，且要求報告雙語（乙：繁中正文 + 英文摘要）。落地前先做一次乾淨的重跑（全套 pytest + 11 家 eval + part baseline），確認報告草稿中的每個數字都與「交件當下的真實 repo 狀態」一致：125 passed、8 家 PASS/3 家 FAILED、MSFT FY1994 Item 14=IV 且 1-13 不變——**全部核對通過，無出入**，才進入落地。

（完整報告的定稿全文——英文摘要 + 繁中第 0–9 段——已在對話中逐段擬定並經使用者逐段確認，最終落地為 repo 內的 `docs/VALIDATION_part_1.md`，見下一章節。）


---

## 17. 報告落地：`docs/VALIDATION_part_1.md` 分段 append + README 新增節

使用者選擇檔名 **`docs/VALIDATION_part_1.md`**（為第二輪的 `VALIDATION_part_2.md` 預留命名空間）、README 新增節標題 `## Validation / 正確性驗證`。

落地方式選 **(乙) 分段建檔**（而非一次到位）：每則指令只 append 一段（`cat >> ... <<'SEC_EOF'`），Claude Code 執行後印出檔案 tail 供核對，確認接續正確、既有內容未動，才進下一段。順序：骨架（Title + English Summary + 第 0 段）+ README 節 → 第 1 段 → 第 2 段 → 第 3 段（含分散軸表格）→ 第 4 段（含結果總表）→ 第 5 段（含 5.6 part 修復）→ 第 6 段 → 第 7 段 → 第 8 段 → 第 9 段（末段）。

每一次 append 都嚴格限定「只允許對 `docs/VALIDATION_part_1.md` 做 append，不得修改既有內容、不得動 README 或其他檔」，README 則以**單獨一次 append（不插入中間）**的方式加入新節，且事先唯讀印出 README 現況供核對，確認新節只出現在檔尾、既有五節（零金鑰聲明/這是什麼/里程碑範圍/安裝執行/硬規則）逐字未動。

**最終驗收（全文結構檢查）**：`grep -nE "^#" docs/VALIDATION_part_1.md` 顯示標題序列——Title + English Summary → §0 摘要 → §1(1.1-1.2) → §2(2.1-2.5) → §3(3.1-3.4) → §4(4.1-4.3) → §5(5.1-5.6) → §6(6.1-6.5) → §7(7.1-7.6) → §8(8.1-8.3) → §9(9.1-9.4)，**329 行，無跳號、無重複、無缺段**。報告正式完成落地。

（過程中 Claude 主動提醒 README 上半部「本里程碑範圍：Stage 1 + Stage 3、Stage 2 刻意尚未實作」的描述已與現況（Stage 2 已運作、TOC/part 已修）有落差，屬於日後可考慮更新的事項，本輪未動它。）

---

## 18. Git 初始化與 6 個 commit 的分組提交

### 18.1 環境問題與修復

使用者要求提交前先看 git 狀態，Claude Code 回報一個關鍵新事實：**這個目錄從一開始就不是 git 工作區（無 `.git`），且 git 指令當時因 Apple `xcrun`/Command Line Tools 失效而完全無法執行**。Claude 誠實承認自己先前預設「這是個 repo」的假設從未被驗證，並提供修復指引（`xcode-select --install`，需使用者親自在終端執行）。使用者自行修復後回報 `git version 2.39.5 (Apple Git-154)` 可用。

### 18.2 提交前盤點

在 `git init` 前，先唯讀盤點 `tests/fixtures/`（確認沒有夾帶答案鍵/祕密檔，只有 14 份公開 EDGAR 申報檔 + 合成樣本，共 3.9M）與既有 `.gitignore`（已涵蓋 `__pycache__/`/`*.pyc`/`.venv/`/`.pytest_cache/`/`.DS_Store`/`.env`/`*.key`/`*.egg-info/` 等，無需增補）。

### 18.3 提交策略：X（單一 commit）vs Y（6 個事後分組 commit）

`git add -A` 後暫存了 83 個檔，這與原訂「6 個 commit」計畫產生衝突。Claude 提出兩個選項並誠實說明取捨：X 是一次性 initial commit（因專案本來就從零開始，這其實是最誠實的做法）；Y 是拆成 6 個有結構的 commit（但這是**事後補分組，非開發當下逐步提交**）。使用者選 **Y**，但明確要求：**「要誠實說出這是事後的合理分組，不謊稱它是『開發當下逐步提交的』」**。

Claude 因此把這句誠實聲明**直接寫進 Commit 1 的 message**（而非只在對話裡口頭說），確保它進入版本歷史本身：

```
NOTE ON HISTORY: this and the following commits are an after-the-fact,
logical grouping made when an existing working tree was first placed under
version control. They do NOT represent a step-by-step development timeline;
the work predates this repository's initialization.
```

### 18.4 六個 commit 的最終結果

流程：`git add -A` → `git reset`（取消暫存，不刪檔）→ 逐組 `git add <指定路徑>` → 印暫存清單核對 → `git commit -F` → 逐組進行，每組完成後才進下一組。

| # | hash | 內容 | 檔數 |
|---|---|---|---|
| 1 | `9d2819d` | base（既有 pipeline Stage 0–3，含誠實聲明） | 43 |
| 2 | `14e95b7` | fix(front_matter)：TOC 邊界修復 | 2 |
| 3 | `f31efc7` | fix(part)：part 改由 era ruleset 決定（message 內含「已知限制：status 未修」） | 4 |
| 4 | `e4d4d19` | test：eval/診斷腳本 | 15 |
| 5 | `0b5c2fa` | test(fixtures)：真實 + 合成 fixture（message 內明寫「無答案鍵檔」） | 16 |
| 6 | `89a666f` | docs：驗證報告 + README 一節 | 2 |

**最終驗證**：工作區乾淨（`git status -s` 無輸出）、追蹤檔 82（43+2+4+15+16+2=82，差額為被 gitignore 排除的一個 `.pyc`）、全程未用 `git add -A`/`.` 做實際提交、未 push、未做任何破壞性指令。


---

## 19. Git 用途說明（使用者提問的教學性回覆）

Commit 全部完成後，使用者提出一個基礎但重要的問題：**「這些 git 到底在工程的目的是什麼？就是清楚的版本編輯歷史嗎？」**

Claude 的回答指出「清楚的版本歷史」只是其中一個、甚至不是最核心的用途，並用剛完成的實例逐點說明：

1. **時光機**：任何時刻都能回到過去的 commit 狀態，不需靠記憶手動改回去。
2. **安全網**：讓「大膽修改」變得沒有風險——改壞了一鍵回復，這正是本輪敢大幅修改 pipeline 核心（front_matter、part 指派）的底氣來源。
3. **歷史/紀錄**：每個 commit 的 message 記錄「什麼時候、為什麼、改了什麼」，例如 `f31efc7` 的 message 就明白記錄了修復內容與未修的 status 限制。
4. **協作**：多人同時改同一專案而不打架（本輪用不到，但是 git 存在的原始理由）。
5. **交件/發布依據**：作業要求「真實的 commit 歷史」，因為它證明工作是一步步做出來的、不是憑空生成，也是為何這次「事後分組」要如實聲明的原因。

一句話收斂：**git 的核心不是「記歷史」，而是「讓你能安全地在時間軸上前進與後退」——存檔、倒帶、實驗、合併；清楚的編輯歷史是這個能力的副產品。**

---

## 20. 交接報告與 Project Instructions（給第二輪擴大抽樣）

在確認第一輪全部完成、工作區乾淨、六個 commit 到位之後，使用者提出下一步規劃：**開始第二輪擴大抽樣**，範圍指定為：

- **科技（5 家）**：NVIDIA、Alphabet、TSMC、AMD、Intel
- **金融（5 家）**：Bank of America、Citigroup、BlackRock、Sculptor Capital Management、Apollo Global Management

並要求在協作規則中加入「必要時期就把階段結果寫成 git commit」的指示。

Claude 撰寫了一份**完整交接報告**（給下一個新對話開場使用），內容涵蓋：協作方式與三條鐵律、專案現況（pipeline 架構、第一輪三項修復的技術細節、11 家 eval 結果、診斷工具清單、文件與 git 現況）、當前任務（10 家公司名單，並**主動標記兩個需要新對話先查證、不可直接假設的風險點**：TSMC 作為外國私人發行人很可能申報 Form 20-F 而非 10-K，現有 pipeline 的 era ruleset 不適用；Sculptor Capital 已於 2023 年被收購下市，可能已無近年 10-K）、方法論資產、以及新的 git 紀律規則。

使用者接著釐清一個重要區分：**「我的 instruction，指的是寫在 project 當中給所有對話遵守的 instruction，你可能格式要調整一下」**——即 Claude Projects 的「Project 層級指示」欄位，這與「交接報告」性質不同：

- **交接報告**：一次性、任務專屬（本輪科技/金融名單、目前進度），每次開新任務輪次時貼給那個新對話。
- **Project 指示**：永久、跨輪次適用（協作風格、三條鐵律、方法論資產、git 紀律），貼進 Project 設定一次，之後每個新對話自動套用。

Claude 因此把交接報告內容拆成兩份不同格式的產出：**(A)** 交接報告存成獨立的 `.md` 檔（`HANDOFF_round2_report.md`，供下載、供貼入新對話開場）；**(B)** 一份精簡、去除任務專屬內容、改寫為「每次對話都要遵守」語氣的 **Project Instructions** 文字（協作方式、三條鐵律、與 Claude Code 的協作方式、git 紀律、方法論資產、接續脈絡六個區塊），供貼入 Claude Projects 的指示欄位。使用者確認這份 Project Instructions 格式後，即為本對話的最終產出。

---

## 附錄：關鍵檔案與路徑索引

- 專案根目錄：`~/Documents/sec-10k-extractor/`
- Pipeline 進入點：`src/sec10k/pipeline.py`（`run_pipeline`）
- Stage 1 TOC/cover 邏輯（本輪修改）：`src/sec10k/ruler/front_matter.py`
- Stage 2 錨點/消歧邏輯：`src/sec10k/segment/anchors.py`、`src/sec10k/segment/segmenter.py`（本輪修改）
- 資料契約：`src/sec10k/contracts.py`（本輪修改，新增 `item_parts`/`part_of()`）
- Ruleset 載入/picker：`src/sec10k/ruleset/loader.py`（本輪修改）、`src/sec10k/ruleset/era.py`
- Stage 3 不變量：`src/sec10k/invariants/checks.py`
- 本輪新增測試：`tests/test_frontmatter_boundary_regression.py`、`tests/test_part_era_regression.py`
- 診斷/評測腳本：`scripts/`（15 支，詳見第 18.4 節 Commit 4）
- Fixtures：`tests/fixtures/real/`（3 份 ground truth）、`tests/fixtures/eval_recent/`（11 份近年檔）
- 驗證報告：`docs/VALIDATION_part_1.md`（329 行，第二輪起將另有 `VALIDATION_part_2.md`）
- README：已於尾端新增「## Validation / 正確性驗證」節

**全套測試：125 passed。Git：6 個 commit，工作區乾淨，未 push。**
