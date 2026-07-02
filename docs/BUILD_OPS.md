# 10-K 抽取 Pipeline — Build & Ops 手冊（v1）

> 本文講「**怎麼蓋、怎麼跑、怎麼控成本**」。系統定義（契約、階段、不變量）見《設計文件 v2》。
> 注意：產品功能（subagents / headless / 定價 / model 字串）會演進，標 ⚠️ 者寫 code 前再核 docs。

---

## 1. 兩種「用 Claude」要分清（別混）

- **(A) 蓋 pipeline** → **Claude Code（VS Code）**。agentic loop：收集脈絡 → 行動 → 驗證 → 迴圈。
- **(B) pipeline 內部執行元件（Stage 4 的 LLM fallback）** → **Messages API（Client SDK）**，單次呼叫，**不是** Agent SDK。

兩者計費也不同：(A) 走 Claude Code/桌面訂閱；(B) 走**開發者自己的** Anthropic API key + Console 計費——且 (B) 為**可選**（見 §3），**絕不要求評測者/主管提供金鑰**。

---

## 2. 開發工作流（A）— 在 Claude Code

- **CLAUDE.md（repo 根目錄，每個 session 自動載入）= 設計文件進入建置的橋樑。** 保持精簡：放(1)專案一句話、(2)「動 code 前先讀 `docs/DESIGN.md`，§5 不變量為硬約束」、(3)最 load-bearing 的幾條規則內嵌（見 §5）。完整設計留在 `docs/DESIGN.md`，由 CLAUDE.md 指示去讀。
- **Plan mode 先行**：唯讀調查 → 產出影響檔案 / 風險 / 測試策略 → 人看過 → 才動手。
- **逐階段實作 + 不變量測試套件 + 迭代**。先把 Stage 1（認證完整的尺）+ Stage 3（不變量）骨架立起來，因為後面所有東西都靠它們驗。
- **subagents 克制使用** ⚠️：可切 parser / 驗證器 / 前端 / eval-harness 並行，但對 take-home 規模，大型多 agent 編排多半是過度工程，且有跑分失控風險。
- **hooks** ⚠️：可強制「每次改檔後跑一次不變量測試」，比靠模型自覺更可靠。
- 多 session 並行才需要 git worktrees。

---

## 3. 執行元件（B）— Stage 4 LLM fallback

- **可選、預設關閉。核心（Stage 1–3、5、6）不需金鑰即可被評測。** 啟用 LLM 只用**自己的** `ANTHROPIC_API_KEY`；**絕不要求評測者/主管提供金鑰**。展示用例：用自己的 key 離線跑全管線，把結果**快取後 ship**，使 demo 全品質且評測者免金鑰。**在 README 開頭明述「評測核心不需任何金鑰/祕密」**（資安與專業度加分點）。
- **用原始 Messages API，每個失敗 span 單次呼叫**（無工具迴圈，故 Agent SDK overkill）。
- **確定性驗證器放在 LLM 呼叫之外**；提案回流設計文件 §5 的閘門。
- **重試設硬上限**（防一份硬骨頭 filing 觸發無限重試 → 帳單爆掉）。
- **model 分層升級**（⚠️ 字串/思考參數寫 code 前核 docs）：
  - 預設：**Claude Haiku 4.5**，extended thinking **最低/關閉**
  - 升級：**Claude Sonnet 4.6**
  - 最硬殘渣才：**Claude Opus 4.8** + 少量 thinking
  - 理由：Stage 4 是「限定範圍小片段 + 結構樣式辨識 + 量大 + 輸出有驗證兜底」，用能過關的最便宜檔。

---

## 4. 成本槓桿（⚠️ 確切費率寫 code 前核 docs）

- **batch API**：離線大量處理多份 filing，有折扣。
- **prompt caching**：很多 span 呼叫共用同一段 schema/指令前綴 → 快取省大量 input token。
- **model 分層**：Haiku 預設。
- **span 限定範圍**（已在設計文件）。
- **重試硬上限**。
- **成本儀表**：把**升級率（% filing / % span 進 LLM）**與**每次升級 token** 當主要監測指標。
- 核對來源：`https://docs.claude.com/en/docs_site_map.md`

---

## 5. CLAUDE.md 應內嵌的「硬規則」（精簡版，供 §2 使用）

1. 任務是 segmentation，不是判公司違規。
2. 切割錨點 = item 編號 + 順序，**不是**標題字串。
3. 先建「認證完整的尺」（正規化不可掉字、剝除要記錄）；item 與 residual **都正面辨識**，不可互為補集。
4. Stage 3 不變量（順序/不重疊/覆蓋/殘留 sanity/合法結構/應存在性/XBRL/跨方法）是硬約束。
5. `reserved` 與 `incorporated_by_reference` = 正確地空 = PASS。
6. Stage 4 的 LLM 是提案者不是驗證者；驗證器在 LLM 之外；重試有上限。
7. confidence 是證據分數非正確率；failed = 硬不變量違反（類別）；pass/review = 校準門檻。
8. Stage 4 為可選、預設關閉；核心不需金鑰即可執行與評測；LLM 僅 BYO-key，**絕不要求評測者提供金鑰**；任何金鑰不得寫進 repo。

---

## 6. 開放 / 待查

- 精確定價、batch 折扣、caching 費率會變 → 寫 code 前查證。
- Claude Code 功能（subagents/headless/hooks）仍演進，本手冊引用為近期文件，實作時再核。
- Stage 4 的 **Anthropic API key 是開發者自己的**（與 Claude Code 訂閱分開），且 Stage 4 **可選**——**絕不要求評測者/主管提供金鑰**；核心不需金鑰即可被評測。
