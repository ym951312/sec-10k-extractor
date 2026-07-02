# 實作計畫 — Stage 1（認證完整的尺）+ Stage 3（不變量閘門）

## Context（為什麼做這個）

這是 SEC 10-K item-level 結構化抽取 take-home。目前 repo 只有 `CLAUDE.md` 與 `docs/`，無任何 code。
依 `docs/DESIGN.md` §3、§7 與 `CLAUDE.md` 硬規則,**地基只有兩塊**:

1. **Stage 1 — 「認證完整的尺」**:正規化後的整份文本字元序列(座標系),且必須**證明正規化沒有偷掉字**,刻意剝除(每頁重複頁首頁尾)須**記錄**。尺沒被認證完整,其上的覆蓋宣稱都不算數。
2. **Stage 3 — 不變量閘門**:§5 八項不變量的確定性驗證器。後面所有 stage(2/4/5/6)全靠這兩塊驗。

本計畫**只規劃這兩塊**,並刻意把 Stage 2(切割)/Stage 4(LLM)擋在門外(硬規則「先骨架後細節」)。Stage 3 在尚無真實 Stage 2 輸出時,**用手刻合成 span fixtures 來驗證閘門邏輯本身**——這正是「先立尺與閘門、後面靠它們驗」的落地方式。

已與使用者確認:**Python** / 前端用 **Streamlit(Stage 6 再做,本次不實作)** / fixtures **先合成後真實**。

---

## 1. 技術棧

| 項目 | 選擇 | 理由 |
|---|---|---|
| 語言 | **Python 3.11+** | SEC HTML/XBRL 解析生態最成熟;核心(Stage 1–3)純確定性、零外部 API。 |
| 資料契約 | **Pydantic v2** | §2 契約直接落為 model;免費得到 JSON 序列化(供日後 Streamlit / 快取 ship)+ 欄位驗證 + enum。 |
| HTML 解析 | **selectolax(主)+ lxml(備)** | selectolax 快且容錯,適合髒 SEC HTML;lxml 處理需 XPath / 命名空間(inline XBRL)的場合。 |
| ASCII 世代 | 標準庫 regex | 早期(~2001 前)10-K 為純文字 + form-feed 分頁;不需 HTML parser。 |
| 測試 | **pytest** + `hypothesis`(選用) | §5 不變量套件的骨幹;hypothesis 可對「完整性不變量」做 property-based(任何正規化都不得掉 token)。 |
| 套件管理 | **uv** + `pyproject.toml` | 快、可重現;README 一行裝起來,評測者零金鑰可跑。 |
| 前端(Stage 6,本次不做) | **Streamlit** | 單檔即可呈現 items/residual/confidence + char-span 高亮;**FilingResult 必須能序列化成 JSON** 是本次唯一前端相關約束。 |
| LLM(Stage 4,本次不做) | Anthropic Messages API(BYO-key) | 預設關閉;**任何金鑰不得進 repo**;本次完全不碰。 |

---

## 2. 專案結構

```
sec-10k-extractor/
  pyproject.toml          # uv / 依賴 / pytest 設定
  README.md               # 開頭明述「評測核心不需任何金鑰/祕密」
  CLAUDE.md  docs/        # 已存在
  src/sec10k/
    __init__.py
    contracts.py          # §2 全部資料模型 + enum(status / residual classification / reason_codes)
    enums.py              # ItemStatus / ResidualClass / StrippedClass / ReasonCode / FilingStatus / FileGeneration / Confidence(high/med/low)
                          #   ResidualClass(尺上 residual span) = cover_page / toc / part_divider / signatures / exhibit_index / unclassified
                          #   StrippedClass(ledger,不在尺上) = page_header_footer / xbrl_hidden  ← 兩者分屬不同 enum,不混用
    ruler/                # ── Stage 1 ──
      __init__.py
      formats.py          # 檔案世代偵測(ASCII / HTML / HTML+XBRL)
      provenance.py       # OffsetMap:ruler 字元位置 ↔ 原始 byte/節點(source_ref 基礎)
      normalize.py        # raw bytes → ruler 文本 + provenance(分世代策略)
      completeness.py     # 正規化完整性檢查(word-token multiset 對帳)
      strip_ledger.py     # StrippedLedger:被刻意剝除內容的記錄(分類 + 原因)
      headers_footers.py  # 偵測每頁重複頁首頁尾 → 剝除 + 記入 ledger
      front_matter.py     # 早期隔離封面頁 + 目錄 → 候選 residual(positively identified)
      ruler.py            # Ruler 物件:text / provenance / ledger / residual_candidates;Stage 1 的產物
    stage1.py             # 編排 Stage 1:raw → 認證完整的 Ruler(+ 候選 residual)
    invariants/           # ── Stage 3 ──
      __init__.py
      checks.py           # 八項不變量,每項一個純函數:(ruler, items, residual, ruleset) → list[Violation]
      gate.py             # 閘門:跑全部 check → VerificationReport;聚合 filing 級狀態
      report.py           # Violation / VerificationReport / confidence 聚合(未校準 → high/med/low)
    stage3.py             # 對外入口:run_gate(...)
    ruleset/
      loader.py           # Ruleset 介面 + 載入(Stage 0 產物);本次只給最小靜態表 + 介面,不做完整 Stage 0
    cli.py                # `python -m sec10k <filing-path>`:跑 Stage1 → Stage3 → 印報告(零金鑰)
  tests/
    fixtures/
      synthetic/          # 手刻最小文本:假 TOC / 重複頁首頁尾 / reserved / merged / 亂序 / gap / overlap
      spans/              # 手刻候選 item span 清單(給 Stage 3 在無 Stage 2 時驗閘門)
      real/               # 之後從 EDGAR 抓的跨世代代表性 10-K(整合測試;先留空)
    test_formats.py
    test_provenance.py    # ruler↔source round-trip
    test_completeness.py  # 含「故意掉字 → 必須失敗」負向測試
    test_headers_footers.py
    test_front_matter.py
    test_invariants.py    # §5 八項:每項 pass fixture + 違反 fixture;reserved/IBR → PASS
    test_pipeline_synthetic.py
    conftest.py
```

---

## 3. 落實 §2 資料契約 與 §3 的「尺」

### 3.1 §2 契約(`contracts.py` + `enums.py`)
- **Ruleset**:`expected_items`(編號集合 + 法定順序)、`reserved_items`、`legal_structures`(相鄰合併型態集合)、`file_generation`。key = 會計年度結束日。本次只放**最小靜態表 + 載入介面**(完整 Stage 0 不在範圍),但欄位與型別釘死,讓 Stage 3 能呼叫。
- **Filing**:`cik / accession / fiscal_year_end / form_type / raw_bytes`。
- **Item(Segment)**:`item_id / part / char_span(ruler 上的 (start,end)) / status / confidence / method / reason_codes[] / source_ref / merged_into?`。`status` enum 涵蓋 `extracted / reserved / incorporated_by_reference / merged / failed`。
- **Residual**:尺**上**的 span,`spans[]` 各帶 `classification: ResidualClass`(`cover_page / toc / part_divider / signatures / exhibit_index / unclassified`)。
- **StrippedLedger**:尺**外**(已剝除)的記錄,各帶 `classification: StrippedClass`(`page_header_footer / xbrl_hidden`)。註:DESIGN §2 原把 `page_header_footer` 列在 residual 下,但 §3 邏輯是 Stage 1 正規化時**剝除頁首頁尾洗乾淨尺** → 故歸 ledger(尺外),非 residual span(尺上);此處據此釘死,二者不混用。
- **FilingResult**:`items[] / residual / filing_status(pass|review|failed) / filing_confidence / verification_report`。
- 全部 Pydantic v2 → 免費 JSON 序列化(日後 Streamlit + 快取 ship)。
- **驗收**:`test_contracts`(本計畫併入 `conftest`/小測)round-trip(model → JSON → model)無損;enum 值穩定。

### 3.2 §3 的「尺」(地基中的地基,先釘死)
核心資料結構三件:

1. **Ruler.text**:正規化後字元序列(位置 `0..N`)。覆蓋只量在這把尺上。
2. **OffsetMap(provenance)**:一串 `(ruler_start, ruler_end, source_kind, source_start, source_end)` 區段,讓任一 ruler 字元可回指原始 byte(ASCII)或 DOM 節點偏移(HTML)→ 即 `source_ref`,供前端高亮、供 char_span 落地。
3. **StrippedLedger**:一串 `(source_span, classification, reason)`,記錄**刻意剝除**(頁首頁尾)的內容。

**「認證完整」的定義(可測,robust to whitespace)**:
> 把「原始可見文字」拆成 word-token multiset(連續英數/標點 run)。要求:
> **source 可見 token multiset == (ruler 內 token multiset) ⊎ (ledger 內被剝除 token multiset)**(互斥聯集、逐一對帳)。
> whitespace 正規化(collapse)允許;但**任何 word token 不得無紀錄消失**。

這把 §3 的「item 與 residual 都正面辨識、不可互為補集」原則,同構地用在 raw-bytes 層:**保留的字** ⊎ **記錄剝除的字** = 全部可見字,沒有 silent drop。尺先被認證,其上覆蓋宣稱才算數。

- **驗收**:(a) 真實/合成樣本完整性檢查 PASS;(b) **負向**:故意在 `normalize.py` 掉一個 word → 檢查必須 FAIL(這條負向測試是地基可信度的證據);(c) provenance round-trip:隨機 ruler 區間 → source → 取回文字一致。

### 3.3 地基決策補充(動工前先寫死)

#### (A) 完整性檢查的「可見文字」定義 + inline XBRL 決策
「尺」= **人看得到的 rendered reading text**。XBRL 機器值是**獨立佐證通道**(供不變量 7 Item 8 XBRL),**不屬於尺的座標**。token 對帳的「source 可見文字」明確定義為:

- **納入**:會 render 給讀者的 text node,經 entity decode(`&nbsp;`→空白等)後切 token。
- **排除**:`<script>` / `<style>` / HTML comment;`display:none` / `visibility:hidden` / `hidden` 屬性的元素;以及 **`<ix:hidden>` 區塊內的 XBRL facts**。
- **inline XBRL 標記(`<ix:nonFraction>` / `<ix:nonNumeric>` 等)包住可見文字時**:只計**其 text node 一次**(標記只是 wrapper);**絕不**再去計 XBRL 的屬性機器值(`contextRef` / 正規化後的 `1234`)→ 杜絕「同一數值同時以人看文字 `1,234` 與 XBRL 值存在」的**重複計數**。
- **`<ix:hidden>` 隱藏 facts**:本就無 visible rendering → 既不進 source baseline、也不進 ruler,**不算 dropped content、不觸 FAIL**;但為誠實/可審計,在 ledger 以 `xbrl_hidden` 記其存在(**audit-only**:記錄但不計入守恆等式任一邊的 token multiset)。

結論(與 §3.2 同方向,整份只用這一個方向):
> `source 可見 token == ruler token ⊎ ledger(被剝除可見) token`
> 即「原始可見文字 = 保留在尺上的 + 刻意剝除記錄的」。等式右邊的 ledger 項**只含可見剝除**(page_header_footer);XBRL 隱藏 facts 與機器值在等式之外(audit-only),故**不會假性 FAIL、不會重複計數**。

#### (B) merged item 的幾何對帳
**幾何單位 = 每個物理區段一個 span。** 合併群組(相鄰帶編號 item 共用一個標題+一段本體,如 `Items 1 & 2`)只貢獻**一個 span**:
- 群組代表(領頭 item,如 `1`)`status=merged` 持有該 span;
- 被吸收成員(如 `2`)`status=merged` + `merged_into="1"`,**無獨立 char_span**(其 span 為 null / 指向群組 span,但**排除於幾何集合外**)。
- **不重疊(inv 2)** 與 **覆蓋(inv 3)** 運算的「幾何集合」= 在跑檢查前**先濾掉所有 `merged_into` 成員**,只留:各獨立 item 自己的 span + 各合併群組的單一 span(計一次)+ residual spans。→ 合法相鄰合併**不會**誤觸不重疊。
- **順序(inv 1)** 仍用 enumerator 邏輯序;合併群組佔其成員連續序位(§1:只相鄰可合併),底層 item_id 序照查、共用 span 無妨。
- **合法結構(inv 5)** 查合併型態 ∈ `legal_structures`。
- **merged pass fixture**(放 `tests/fixtures/spans/`):`Items 1&2 merged` —— 一個 span 蓋 Item 1+2 區域,`item 1` status=merged 持 span、`item 2` status=merged + merged_into="1" 無自身 span;幾何集合 = {merged(1&2) span, item 3..15 spans, residual},**inv 2/3 PASS、inv 1 PASS、inv 5 PASS**。

#### (C) 最小靜態 `legal_structures` 內容
靜態表(本次最小、介面釘死)至少涵蓋,讓 inv 5 驗得出東西且不誤判合法檔:
1. `standard` —— 無合併,每個 expected 帶編號 item 各自獨立。
2. `items_1_2_merged` —— Items 1 & 2(Business + Properties)合併。
3. `items_2_3_merged` —— Items 2 & 3(Properties + Legal Proceedings)合併。
4. `part_iii_incorporated_by_reference` —— Items 10–14 引用併入(proxy)。註:此為**授權缺席**型態(§1 彈性 A),非「合併」;以 authorized-absence 條目併入此知識集,讓 **inv 6 應存在性**接受 10–14 以 `incorporated_by_reference` 正當缺席而**不舉旗**,同時 inv 5 對「標準/1&2/2&3」三種合併形狀都判合法。

---

## 4. 實作順序與驗收(每步綁 §5)

> 原則:**先建尺(真實實作)+ 建閘門(合成 span 驗證)**,兩者各自獨立被認證,完全不依賴尚未存在的 Stage 2。

**步驟 0 — 契約骨架**
`enums.py` + `contracts.py`。驗收:序列化 round-trip 測試綠。

**步驟 1 — 尺核心:formats + provenance + normalize(先 HTML 世代,當代主流)**
產出 `Ruler.text` + `OffsetMap`。驗收:`test_formats`(三世代偵測)、`test_provenance`(round-trip)。

**步驟 2 — 完整性檢查(completeness)**
word-token multiset 對帳。驗收:`test_completeness` 正向 PASS + **故意掉字負向 FAIL**。這步通過 = 尺被「認證完整」。

**步驟 3 — 頁首頁尾剝除 + ledger**
偵測每頁重複頁首頁尾(ASCII:form-feed / `<PAGE>` 分頁;HTML:重複文字 run + page-break 訊號),剝除並記入 ledger。驗收:`test_headers_footers` — 重複頁首頁尾被抓 + 記錄;且剝除後 **(ruler ⊎ ledger) token 對帳仍守恆**(沒 silent drop、沒過度剝)。

**步驟 4 — 封面頁 + 目錄隔離(front_matter)→ 候選 residual**
封面頁(首個真實 Item 錨點前)、目錄(高密度 `Item N` + 頁碼/點線 leader)正面分類為 `cover_page` / `toc`。**這是正面辨識,不是補集**。驗收:`test_front_matter` — 假 TOC 被歸 `toc`(預先拆掉「目錄假標題」陷阱)、封面歸 `cover_page`。

**步驟 5 — Stage 1 編排(stage1.py)**
串 0–4,輸出「認證完整的 Ruler + 候選 residual」。驗收:`test_pipeline_synthetic` 在合成樣本上,完整性 PASS + 候選 residual 分類正確。

**步驟 6 — Stage 3 閘門框架 + 八項不變量(invariants/)**
每項 §5 不變量一個純函數;`gate.py` 彙總 `VerificationReport` + filing 級狀態。
用 **`tests/fixtures/spans/` 手刻 span 清單**(非真實 Stage 2 輸出)驗閘門:

| §5 不變量 | pass fixture | 違反 fixture(必須舉旗) |
|---|---|---|
| 1 順序 | 合法序 | 亂序(1A 在 1 前) |
| 2 不重疊 | 鄰接;**含 `Items 1&2 merged` pass(§3.3-B)** | 兩 item span 重疊 |
| 3 覆蓋 | items ∪ residual = 尺(幾何集合先濾 `merged_into` 成員,§3.3-B) | 留 gap / 留 overlap |
| 4 殘留 sanity | 全可分類 | 大塊 `unclassified`(紅旗) |
| 5 合法結構 | ∈ legal_structures | 非法合併型態 |
| 6 應存在性 | 必存在 item 都在 | 缺 item 且非 reserved/IBR |
| 7 Item 8 XBRL | 邊界被 XBRL 佐證 | (有 XBRL 樣本時)不一致 |
| 8 跨方法一致 | 邊界吻合 | 方法分歧 |

**關鍵負向 + 特例**:
- `failed` = **觸發任一硬不變量違反**(類別判定,一違反即 failed,與分數無關)。
- `reserved` 與 `incorporated_by_reference` = **正確地空 = PASS**,**不可**被覆蓋/應存在性誤判為失敗 → 各給專屬 fixture 證明不舉旗(硬規則 #5,最易出錯處)。
- confidence:**未經 eval set 校準前不當機率**,以 **high/med/low** 三檔輸出;`pass` vs `review` 為校準門檻,本階段先以三檔近似。
- 第 5/6/7/8 項依賴 Ruleset/Stage 2/XBRL,本次以**最小靜態 Ruleset + 合成 span** 行使邏輯;真實行使待後續 stage(介面先釘死)。

**步驟 7 — CLI(cli.py)**
`python -m sec10k <path>` 跑 Stage1→Stage3 印報告。驗收:**零金鑰**可跑合成樣本,印出 items/residual/不變量報告。

**步驟 8(收尾)— 真實 EDGAR 整合測試**
依使用者策略「先合成、後真實」:抓**少量跨世代(ASCII / HTML / HTML+XBRL)、沿年代/產業/規模/本國 vs 外國分層**的真實 10-K 進 `tests/fixtures/real/`,當整合測試暴露未預期變異。驗收:真實樣本完整性 PASS、無未解釋大塊 `unclassified`、報告合理。

**hooks(選用,§BUILD_OPS)**:可設「每次改檔後自動跑不變量測試」,比靠模型自覺可靠——但屬建置流程,實作時再議。

---

## 5. 主要風險與處理

| 風險 | 處理 |
|---|---|
| **HTML 髒/多變**(inline XBRL、巢狀 table、entity)導致正規化掉字 | 完整性檢查(步驟 2)就是安全網:掉字會**大聲 FAIL**,不會 silent;selectolax 容錯解析 + lxml 備援。 |
| **頁首頁尾過度剝除**(把正文當頁首剝掉) | 保守偵測(要求跨頁高重複率);**所有剝除一律進 ledger**(可審計、可回復、計入對帳),絕不 silent drop。 |
| **HTML 無硬分頁**,頁界難定 | 多訊號(CSS page-break / 標記 / 重複文字 run);頁首頁尾偵測為 best-effort,守恆對帳兜底,不卡核心。 |
| **目錄假標題**汙染未來 Stage 2 錨點 | Stage 1 步驟 4 **先結構性隔離 TOC**(頁碼/點線 leader + Item 密度),預先拆陷阱(§4)。 |
| **provenance 算錯 → 所有 char_span 全錯** | provenance round-trip 單元測試;尺與完整性最先釘死(§3/§7 第 1 點)。 |
| **scope creep 進 Stage 2/4** | 硬規則:Stage 3 用**合成 span fixtures** 驗,不依賴真實 Stage 2;只釘 segmenter 介面,不寫其細節。 |
| **覆蓋不變量恆真、失去診斷力** | item 與 residual **都正面辨識**(residual = 已知非 item 結構 + `unclassified` 旗標),**絕不**定義成彼此補集。 |
| **誤把校準前數值當機率** | confidence 一律先以 high/med/low 呈現,README/報告註明未校準。 |

---

## 6. 驗證(整體 end-to-end)

1. `uv run pytest` 全綠:契約 round-trip、formats、provenance round-trip、completeness(含掉字負向)、headers_footers 守恆、front_matter 分類、八項不變量(各 pass + 違反)、reserved/IBR → PASS、合成 pipeline。
2. `python -m sec10k tests/fixtures/synthetic/<sample>`:**零金鑰**印出 Stage1 認證報告 + Stage3 不變量報告。
3. 步驟 8 後:對 `tests/fixtures/real/` 的跨世代真實 10-K 跑同一指令,確認完整性 PASS 且無未解釋大塊 `unclassified`。

---

## 嚴守的硬規則(自我檢查清單)
- [x] 錨點 = item 編號 + 順序,**不是標題字串**(本次只到 Stage 1/3;Stage 2 介面預留此語意)。
- [x] 尺必須**認證完整**(token 對帳)、剝除須記錄。
- [x] item 與 residual **都正面辨識**,不可互為補集。
- [x] `reserved` 與 `incorporated_by_reference` = PASS。
- [x] 任務是 segmentation,不判公司違規(「違規 vs 格式」僅做非評分 reason code)。
- [x] 核心零金鑰可跑;任何金鑰不得進 repo;不放寬 Stage 3 門檻。
