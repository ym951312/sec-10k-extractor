# CLAUDE.md

> 放在 repo 根目錄。Claude Code 每個 session 自動載入。保持精簡:完整設計在 `docs/DESIGN.md`。

## 專案
SEC 10-K Item-level 結構化抽取 pipeline(take-home)。任務 = 把 raw 10-K 可靠**分段**成各 item、可獨立取用,在無 ground truth 下自我驗證,並誠實回報信心與失敗案例。**不是**判斷公司是否違規。

## 開始前必讀
動任何 code 前,**先完整讀 `docs/DESIGN.md`**;其 §5 的結構不變量為**硬約束**,實作不得違反。建置/成本流程見 `docs/BUILD_OPS.md`(按步驟分段參照,勿一次全載)。動手前先用 **plan mode** 規劃;先立 **Stage 1(認證完整的尺)+ Stage 3(不變量)** 骨架,後面全靠它們驗。

## 硬規則(不可違反)
1. 任務是 **segmentation**,不是判公司違規。「違規 vs 格式」只當失敗的診斷註記,不下 verdict。
2. 切割錨點 = **item 編號 + 順序**,**不是**標題字串(標題會因年換主題、因合併消失)。
3. 先建「**認證完整的尺**」:正規化**不可掉字**,刻意剝除(如每頁重複頁首頁尾)須**記錄**。item 與 residual **都正面辨識**,**不可互為補集**(否則覆蓋不變量恆真、失去診斷力)。
4. **Stage 3 不變量**(順序 / 不重疊 / 覆蓋 / 殘留 sanity / 合法結構成員性 / 應存在性 / Item 8 XBRL / 跨方法一致)為硬約束。
5. `reserved` 與 `incorporated_by_reference` = 正確地空 = **PASS**,不可誤判為失敗。
6. `confidence` 是**證據分數,非正確率**(無 oracle)。`failed` = 觸發任一硬不變量違反(**類別判定**);`pass` vs `review` = 校準門檻,未校準前以 high/med/low 處理。
7. **Stage 4 的 LLM 是提案者,不是驗證者**:提案須**回流 Stage 3 閘門**;確定性驗證器在 LLM 呼叫**之外**;重試設**硬上限**。
8. **Stage 4 為可選、預設關閉。** 核心(Stage 1–3、5、6)**不需任何外部 API/金鑰**即可執行與評測;關閉 LLM 時優雅降級為確定性抽取 + 誠實低信心標記。LLM 僅用開發者**自己的** `ANTHROPIC_API_KEY` 啟用,**絕不要求評測者提供金鑰**。

## 不要做
- 不要把標題**主題字串**當錨點。
- 不要 silently 要求付費 API 才能跑;**任何金鑰不得寫進 repo**。
- 不要為了「通過」而**放寬 Stage 3 不變量門檻**。
- 不要在做完 Stage 1/Stage 3 骨架前,先寫 Stage 2/4 的細節。
