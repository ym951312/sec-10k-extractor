# 完整對話紀錄 — SEC 10-K Stage 0：Era Ruleset 設計與 Pillar 3 建置

> **關於本文件**：本文件依時間順序完整重建這整段對話的內容與決策脈絡，採主題分章而非逐輪照抄。對於冗長的 Claude Code 截圖回報，本文件保留其**關鍵數據、判讀結論與決策**；所有具體數字、item 編號、SEC Release 編號、測試數量均取自對話中實際出現的內容，未經編造。給 Claude Code 的完整指令文字予以保留關鍵規格內容。
>
> **關於「使用者關鍵貢獻」的標記**：本文件依使用者要求，誠實自我評估哪些地方使用者真正起到關鍵性角色（提出關鍵問題、糾正推理框架、否決 Claude 的建議、揭露決定性脈絡）——以 `🔑 使用者關鍵貢獻` 標記——而非把每一次「從甲/乙/丙選一個」都算作使用者主導。多數決策點是 Claude 列出選項、使用者選擇並偶爾補充理由，這是正常且必要的協作模式，但不等同於「使用者帶領 Claude」；本文件只在使用者的貢獻確實改變了方向、糾正了錯誤、或引入了 Claude 未觸及的考量時，才標記為關鍵。

---

## 使用者關鍵貢獻總覽（自我評估）

在進入逐章敘事前，先誠實列出整段對話中使用者真正起到關鍵性角色的時刻：

1. **功能判準洞見**（§2）：使用者質疑「完整列出所有現代 item 狀態」的意義，主動提出「應該只要在每個年份適當標上合規狀態就夠了」——這把 Claude 原本「精簡 vs 完整」的風格框架，重新定位成「功能判準」，是使用者主動糾正 Claude 推理框架的典型案例。
2. **一貫選擇更嚴謹的誠實標準**（§1, §2）：在多個「寬鬆 vs 嚴謹」的分岔點（標法一/二、ABSENT 的 part 是否給值、absences 是否含 Item 10），使用者一貫選擇更保守誠實的一方，這個持續的判斷模式塑造了整個系統的誠實基調。
3. **認知彈性、聽懂就改**（§3, §6）：在 file_generation 多值化與 era_2005 細分兩個議題上，使用者初次選擇都不是最終定案，但在 Claude 提出具體技術反駁後能夠「聽懂就改」而非為了面子堅持——反映科學態度，值得記錄。
4. **揭露時限、重塑優先順序**（§9）：「我沒有其他檔。不過我週五就要交出去」直接讓 Claude 從「繼續深挖 marker 框架」轉向「務實排序、確保柱子三核心先完成」。
5. **🔑 反駁 Claude 對評分重點的判斷**（§10）：「但我覺得，他們應該會更重視近年公司的抽取成功度與穩健性。所以我會覺得 legal_structures 那個問題很重要」——使用者用自己對評分情境的理解，推翻 Claude 原本「先延後 legal_structures」的建議，是全對話中使用者最強的一次策略性主導。
6. **🔑 要求擴大範疇為通用框架**（§10）：「我覺得丙不錯，但能不能納入更多可能？」——使用者不滿足於 Claude 提出的「只處理 merge」方案，主動要求一般化，直接催生了 variant-form marker 五類框架的設計。
7. **🔑 用具體風險否決 Claude 的務實妥協方案**（§10）：「但是 merge 宣告我不同意，因為我想要明或是後天多測幾間近年的公司，所以我擔心這個部分會讓近年公司的抽取結果很差」——使用者用「即將測試更多公司」這個具體下一步計畫作為理由，否決了 Claude 原本「先務實填一個 era 宣告」的建議，直接推動了「證據驅動 + 相鄰性判準」這個更根本、更穩健的解法。這是本對話中使用者最具體、最有技術後果的一次介入。
8. **觀察並質疑實作與指令的落差**（§11）：「然而，claude code 似乎在連續的定義上跟你不太一樣，但看起來他的決定蠻 ok 的？」——使用者注意到 Claude Code 實作與 Claude 指令間的細微差異並主動提問，促成 Claude 誠實揭露 Claude Code 自我修正 bug 的過程。
9. **兩次格式/流程糾正**（§13, §14）：先糾正 Claude 誤解「交接摘要」與「完整逐字記錄」的差異；後又進一步指出更好的整理格式範例——這兩次糾正直接決定了本文件最終的形式。

其餘多數決策點（例如 4 個確認裡選 A/B/C、9B/9C/16 怎麼處理、evidence tier 怎麼標）是 Claude 列出選項、使用者判斷選擇，屬正常協作分工，本文件不逐一標記為「關鍵」。

---

## 目錄

0. 任務起點（承接壓縮前對話）
1. era_1994 核對結果與誠實度分級決定
2. 🔑 功能判準：為什麼「完整列出」沒意義
3. era_1994 定稿與 schema 修正（Optional part + validator）
4. era_2005：SEC 法規補查與草案
5. file_generation 的維度錯位問題
6. era_2005 upper-bound 的細分辯論
7. FYE 查證意外發現：MSFT 2023 其實屬於 era_2020
8. era_2020 核對與 9B/9C/16 缺漏發現
9. era_2005 回補、era_2020 定稿、CONDITIONAL 的 part 語意
10. era_2023 完成與三個真實檔邊界現象
11. 🔑 legal_structures 的坑：延後決策與使用者的堅持
12. Pillar 3：picker 架構分岔（Path A vs B）
13. absences 語意修正（允許 vs 實際）
14. 🔑 merge 判定：從宣告驅動到證據驅動的相鄰性判準
15. Claude Code 的自我修正：相鄰性定義 bug
16. 交接文件的兩次迭代與格式修正

---

## 0. 任務起點（承接壓縮前對話）

本對話由前段壓縮摘要承接，當時狀態：子勳（台灣量化交易新創實習生）正在建構 SEC 10-K 逐項擷取 pipeline，作為帶回家的評分作業。核心任務是把 10-K 申報文件可靠分割為 Item 1–15/16，誠實回報信心與失敗模式，明確不做合規判斷。Stage 0 的三柱架構已規劃：柱子一（FYE 抽取）已完成，柱子二（四個 era ruleset）正在進行（schema 已設計、era_1994 正在填），柱子三（picker 連接）尚未開始。

本對話開頭，使用者上傳三張 MSFT 1994 真實檔的逐筆核對結果截圖，作為 era_1994 資料填寫的實證基礎。

---

## 1. era_1994 核對結果與誠實度分級決定

Claude 逐項核對三張截圖，確認絕大多數推定筆升級成真實檔佐證：Item 1–13 的標題、編號、Part 在 MSFT 1994 真實檔裡直接確認；Item 14 的關鍵修正（`Exhibits, Financial Statement Schedules and Reports on Form 8-K`，屬 `PART IV`）證實了現代假設 `_PART_III={10..14}` 對 1994 是錯的；Item 4 標題確認為「股東投票事項」而非現代的 Mine Safety；1A/1B/7A/9A 在檔中查無，佐證這些 item 尚未引入。

Claude Code 對 Part III（Item 10–13）的 IBR 內容採取了「A（結構/part 確認）+ 內容為 IBR」的複合標記，而非簡單粗暴地歸為「無法確認」，這個處理方式被 Claude 認可為比硬性二分更貼近檔案實況。

**誠實度分級的決定點**：由於核對只用了 MSFT 一家公司、一份檔案，Claude 提出「這些筆該標成純 REAL_FILING（標法一）還是 REAL_FILING + 單檔未跨公司抽樣的但書（標法二）」的問題，並傾向標法二。使用者選擇**標法二**——這個決定確立了整個專案「即使有真實檔佐證，也要標明佐證廣度」的紀律，後續三個 era 的證據等級標記都延續這個原則。

---

## 2. 🔑 功能判準：為什麼「完整列出」沒意義

Claude 提出 era_1994 定稿草案，附四個待確認問題，其中確認一是：era_1994 該不該完整列出所有現代 item（包括 1C、9B、9C 這些遠未來才出現的 item，標為 ABSENT），還是只列當時存在 + 少數關鍵 ABSENT。Claude 原本傾向「精簡」，但把它框定為一個風格選擇。

**使用者在此提出關鍵問題**：「就算我選擇完整列出所有現代item狀態，也沒什麼意義吧？如果我希望這一份龐大的code可以在未來繼續適應環境，應該就只要在每個年份適當的標上合規的狀態就夠了？」

Claude 認同這個直覺是對的，但進一步指出 Claude 原本「精簡 vs 完整」的框架本身是錯的——正確的判準不是風格選擇，而是**功能判斷**：只有「對判定有實質作用」的 ABSENT 才該列（例如 era_1994 標 1A/1B/7A/9A 為 ABSENT，因為它們是下一個 era 就會出現的鄰接邊界 item，系統需要明確宣告才能區分「合法沒有」與「漏抓」），而「遠未來、對判定當代檔案無實質意義」的 ABSENT（如 1C、9B、9C 對 1994）則不必列。

這個修正後的原則不只解決了 era_1994 的問題，還帶來一個長期架構好處：未來新增現代 item 時，不需要回頭修改所有舊 era（因為舊 era 本就不列與己無關的未來 item），符合「隔離、改一處不波及他處」的維護哲學。

---

## 3. era_1994 定稿與 schema 修正（Optional part + validator）

使用者依此原則確認 era_1994 為 18 筆 item。後續三個技術確認：

- **ABSENT item 的 part 欄位**：Claude 原傾向「照給 part」（路 A，不改 schema），但重新用功能判準檢視後，指出 ABSENT item 的 part 從不被判定邏輯使用，硬填一個「未來所屬 part」語意不誠實。使用者選擇**路 B**——把 `ItemRule.part` 改成 `Optional[Part]`，ABSENT 給 `None`，即使這需要改動剛寫好的 schema。
- **legal_structures 的 absences 是否含 Item 10**：核對顯示 Item 10 在 MSFT 1994 是「部分 IBR、部分在本文」，並非純缺席。使用者確認 absences 只放 `["11","12","13"]`，不含 10。

Claude Code 執行分兩步驟：先改 `ItemRule.part` 為 Optional 並新增 part↔expectation 一致性 validator（REQUIRED/RESERVED 必須有 part，ABSENT 必須 part=None），確認測試通過後才填入 ERA_1994 完整資料（18 筆，含 legal_structures、兩條 pending_notes：單檔未跨公司佐證的誠實但書 + era 上界粗略性但書）。測試套件由 5 條增至 9 條，全套 **70 passed**，零回歸。**era_1994 完成，四個 era 完成第一個。**

---

## 4. era_2005：SEC 法規補查與草案

era_2005 沒有真實檔（唯一手上的真實檔是 1994 和 2023 兩個年份），只能靠 SEC final rule 佐證，證據等級為 SEC_PRIMARY。Claude 詢問是否要補查 SEC 出處以提升骨架紮實度，使用者同意「補查」。

Claude 執行兩次 web_search：確認 **Item 7A**（市場風險揭露）的 final rule 是 Release 33-7386（1997），生效門檛 FYE≥1998-06-15，遠早於 era_2005 起點；確認 **Item 9A**（Controls and Procedures）的 final rule 是 Release 33-8124（2002 SOX §302），但其生效 trigger 是 **filing date**（2002-08-29 後申報），而非慣常的 fiscal-year-end 語意——這是個例外，Claude 特別記錄下來。

era_2005 草案定為 19 筆（Item 1–15），含三級證據標記（SEC 出處 / 反向出處 / 穩定性推導）。Item 9B 的引入時間未查證，使用者選擇不列、標待查；era_2005 上界定為 2021-08-09（呼應 2020 年 Item 6 改 reserved 的門檻）；沒有真實檔可核對的基礎 item（Item 1、2、3 等）接受標為「穩定性推導」。

---

## 5. file_generation 的維度錯位問題

在準備定稿 era_2005 前，Claude 發現一個尚未查證的假設：era_2005 的 Item 14/15 結構是否已經是「現代式」（14=Principal Accountant Fees、15=Exhibits）取決於 2003 年那次位移的精確時間點，此前一直標「待補」。使用者選擇**甲：補查**。Claude 執行 web_search 確認位移發生於 2003（依據 audit committee disclosure 規則，並有 FY2003 真實檔 Lehman Brothers 間接佐證 Item 15(a) 已在使用），確認 era_2005（FYE≥2005-12-01）晚於此位移，結構確定是現代式。

同時浮現另一個問題：`file_generation`（ASCII/HTML/HTML_XBRL）這個欄位該怎麼填？era_2005 橫跨 2005~2021 共 16 年，中間有 XBRL 強制（約 2009）的格式過渡，單一 era 對應單一 file_generation 值站不住。使用者提出的初步方案是「file_generation 該允許多值」。

Claude 沒有直接照做，而是指出這個方案治標不治本：多值會讓這個欄位失去判定力，且問題根源是「era 的定義維度（法規）」與「file_generation 的維度（檔案格式）」被混用了——格式該由 Stage 1 的 `detect_generation` 偵測那份檔的實際 bytes 決定，不該由 era 依 FYE 宣告。Claude 並指出一個強力旁證：現有 `Ruleset.file_generation` 宣告了卻從未被讀取，暗示這個欄位從一開始就是多餘的。Claude 提出三個選項（甲：維持多值；乙：從 EraRuleset 拿掉這個欄位；丙：細分 era），強烈建議乙。

**使用者選擇乙**，接受這是比自己原方案更根本的解法。這個決定同時修正了一個從既有 `Ruleset` 繼承來的設計錯位。動作拆成兩步：先改 schema（拿掉欄位、同步移除 ERA_1994 該行，保留 `FileGeneration` enum 因為 Stage 1 仍在用），查證確認欄位無任何 production code 讀取後執行，全套 **70 passed**，零回歸。

---

## 6. era_2005 upper-bound 的細分辯論

在 era_2020 開工前，一連串的真實檔核對（見 §7、§8）意外揪出 era_2005 遺漏了 Item 9B、9C、16 三個 item。Claude 執行 web_search 查證三者的引入時間：Item 9B（Release 33-8400，2004-08-23）、Item 16（2016 年 Form 10-K Summary rule，明確為 optional）、Item 9C（HFCAA 相關，2021-05-05 interim final rule，且**只對「Commission-Identified Issuer」這類特定審計轄區的公司實質適用**，一般美國公司如 MSFT 是「不適用」）。

Item 16 的引入時間（2016）落在 era_2005 的中段（2005–2021），暴露 era_2005 內部其實橫跨了這個變化點的問題。Claude 提出三個選項：甲（維持粗略、16 標 CONDITIONAL、pending_notes 誠實註記橫跨問題）、乙（把 era_2005 依 2016 切成兩個更精確的子 era）、丙（這輪只補 9B，其餘延後）。Claude 明確傾向甲。

**使用者選擇乙**，理由是「跟甲的誠實度一樣，但多了精確」。

Claude 在此明確踩了煞車，指出使用者的推理有一個具體的技術盲點：乙聲稱的「精確」——即 2016~2021 這個新切出的子 era 的 item 結構——**沒有任何真實檔可以驗證**，所以那是一個「你手上沒有東西能驗證它是不是真的精確」的未經驗證精確聲稱，在使用者自己的認識論鐵律（「成功僅被佐證」）下，這種聲稱其實比甲的「誠實承認粗略」更不誠實。Claude 進一步指出，若採用乙的邏輯，未來只要發現一個法規變化點就切一個 era，會導致 era 結構爆炸，且每個新切出的子 era 依然沒有真實檔驗證，精確度沒有真正提升。

**使用者聽完後回應**：「我懂你意思了。那我選甲，有道理」——不是被說服放棄立場，而是理解了論證後主動更新判斷，這個「聽懂就改、不為面子堅持」的態度被 Claude 認可為呼應整個專案的認識論精神。

---

## 7. FYE 查證意外發現：MSFT 2023 其實屬於 era_2020

在完成 era_2005 之後，Claude 準備進入 era_2020。原本預期 era_2020（2021~2023 區間）跟 era_2005 一樣沒有真實檔，但 Claude 主動提出一個假說：手上的 MSFT 2023 真實檔的 FYE 是 2023-06-30，這個日期早於 Item 1C 的引入門檻（2023-12-15），所以 MSFT 2023 有可能其實落在 era_2020 而非原先假設的 era_2023。

使用者同意先做查證。Claude 給出唯讀查證指令，實跑 `extract_fiscal_year_end` 確認：**MSFT 2023 的 FYE 確實是 2023-06-30，落在 era_2020 區間**；**APA 2023 的 FYE 是 2023-12-31，落在 era_2023 區間**。這個發現把原本預期「era_2020 無真實檔」的情況翻轉——era_2020 和 era_2023 現在都各自有一份真實檔可以逐筆核對。

這個查證同時把「MSFT 2023 合法地沒有 Item 1C」這句話，從一個推論性的解釋，升級成有實際 FYE 值與 era 區間佐證的結論。

---

## 8. era_2020 核對與 9B/9C/16 缺漏發現

比照 era_1994 的做法，使用者選擇先用 MSFT 2023 真實檔逐筆核對，再填 era_2020。核對結果確認三個關鍵特徵：**Item 6 = `[RESERVED]`**（檔內正文標題直接是 `ITEM 6. [RESERVED]`，其後無 Selected Financial Data 內容）——這是 era_2020 相對 era_2005 的唯一預期差異；**Item 1C 查無**（`item 1c` 全檔命中 0 次，與 `cybersecur` 字根散落出現區分開來）；**Item 4 = Mine Safety Disclosures**（現代標題，非 1994 的股東投票）。

核對同時揪出一個 Claude 自己的疏漏：**MSFT 2023 真實檔裡還有 Item 9B、9C、16 三個 item，是 Claude 給的 era_2020 預期表沒有列的**。這個疏漏源自 era_2005 當初複製 era_1994 骨架時的疏忽（era_1994 因功能判準原則不列遠未來 item，但這個理由不適用於現代 era——9B/9C/16 對現代檔案是實際存在的 item，不是遠未來的 ABSENT）。

Claude 誠實承認這是自己的錯誤，提出三個處理範疇：甲（徹底：查證引入時間 + 回頭修 era_2005 + 正確填 era_2020）、乙（先顧眼前，era_2005 記待辦）、丙（先查證再一起決定）。**使用者選擇甲**，這個範疇決定牽出了 §6 的辯論。

---

## 9. era_2005 回補、era_2020 定稿、CONDITIONAL 的 part 語意

依 §6 的最終結論（維持甲：不細分 era_2005），Claude 給出「三步驟」指令：步驟一放寬 validator（讓 REQUIRED/RESERVED 必須有 part、ABSENT/CONDITIONAL 可以 part=None，這個修正是為了容納 Item 16 這種跨全表、不屬單一 Part 的 optional item）；步驟二回補 era_2005（新增 Item 9B、16 兩筆，加一條誠實註記橫跨 2016 引入點的 pending_note）；步驟三新增 era_2020（相對 era_2005 的差異：Item 6 改 RESERVED、新增 Item 9C）。

三步驟依序執行，Claude Code 回報結果：era_2005 由 19 筆增至 21 筆；era_2020 為 22 筆，其中兩個 CONDITIONAL item 呈現不同的 part 語意——**Item 9C 標 CONDITIONAL 但有明確 part（PART_II，因為它有固定歸屬、只是適用性條件式，只對特定審計轄區公司強制）**，**Item 16 標 CONDITIONAL 且 part=None（因為它是跨全表的 optional summary，不屬任何單一 Part）**——這個區分驗證了四態設計裡 CONDITIONAL 這一態能同時容納兩種不同性質的「有無皆可」情境。全套 82 passed，零回歸。

回報結尾，Claude Code 主動指出 era_2005 有一條既有 pending_note（「Item 9B 未查證、未列入、待查」）現在與剛回補的資料自相矛盾，但依指令「只新增不動既有」而未擅自修改，回報請示。使用者上傳結果後，Claude 給出修正這條過期 note 的小指令，確認修好、82 passed 零回歸。

---

## 10. era_2023 完成與三個真實檔邊界現象

era_2023 用 APA 2023 真實檔逐筆核對。核對結果確認 **Item 1C 存在**（與 MSFT 2023 的「無 1C」構成 1C 於 2023-12-15 引入的完整正反佐證：門檻前無、門檻後有）、**Item 1C 屬 Part I**（由檔內 Part divider 位置判斷確認）。

核對同時揭露三個真實檔邊界現象：

- **Item 6 的字面呈現在不同公司不同**：MSFT 用 `[RESERVED]`，APA 用 `SELECTED FINANCIAL DATA...Omitted`——同一個「保留位」有不同標題字面，再次印證「錨點必須是編號、不能是標題字串」的鐵律。
- **APA 是這個專案第一個真實 merge 案例**：檔內 `PART I ITEMS 1 and 2. BUSINESS AND PROPERTIES`，Item 2 沒有獨立標題（standalone `ITEM 2.` 命中 0 次），內容併入 Item 1。
- **Part III 的省略法源不同**：MSFT 是 IBR 到 proxy statement；APA 是 `omitted pursuant to General Instruction I(2)(c)`（全資子公司簡化揭露的授權省略），性質不同但結果都是合法缺席。

三個現象各帶出一個要使用者拍板的決定：Item 6 的 topic 怎麼填（使用者選 A：沿用 era_2020 的中性描述，字面變體記進 pending_notes）；legal_structures 怎麼表達 APA 的 General Instruction I 省略（使用者初選 A：加第二個 LegalStructure）；merges 怎麼表達 Item 1+2 合併（使用者選 B：先記 pending_notes 待議）。

---

## 11. 🔑 legal_structures 的坑：延後決策與使用者的堅持

Claude 在具體落地「決定二（加第二個 LegalStructure）」時，發現這牽涉一個更深、尚未想清楚的問題：`legal_structures.absences` 究竟該表達「era 層允許缺席的最大集合」還是「某份檔實際缺席的內容」？如果是前者，現有 era_2005/2020 的 absences（只到 13，不含 14）其實也不精確，因為 MSFT 2023 的 Item 14 也是 IBR。Claude 因此**收回**了自己上一輪對「決定二」的支持，建議把整個 legal_structures 的複雜部分（第二個 LegalStructure、absences 語意、merge 架構位置）全部延後到柱子三，這輪先把 era_2023 的 23 筆 item 表填對就好。

使用者同意延後，但明確要求：**「延後好了。但我們柱子三要記得這個坑」**。Claude 沒有只是口頭承諾，而是把完整的五個子問題（absences 允許/實際語意未定、現有 absences 不精確缺 14、多法源未表達、merge 架構位置未定、核心語意區分未確立）逐字寫進 era_2023 的 pending_notes，讓這個坑成為 code 本身的一部分，不依賴任何人「記得」。era_2023 定稿為 23 筆，含 7 條 pending_notes，全套 **87 passed**，零回歸。**柱子二（四個 era ruleset）在此完成。**

使用者接著揭露一個關鍵的情境限制：「我沒有其他檔。不過我週五就要交出去，所以可能頂多只能到層級二？」——這句話讓 Claude 重新評估優先順序，明確指出「柱子三還沒做、MSFT 1994 還沒真正修好」才是最大風險，並提出兩天內的施工路線建議：柱子三核心（必做）→ 三份真實檔的層級二驗證（應做）→ 抓新檔擴充（有時間才做）。

**在柱子三尚未展開前，使用者對這個「先做最小可用版、legal_structures 深水區延後」的建議提出異議**：「但我覺得，他們應該會更重視近年公司的抽取成功度與穩健性。所以我會覺得 legal_structures 那個問題很重要」——這直接推翻了 Claude「先延後」的判斷。Claude 認同這個判斷站得住，因為 IBR 和 merge 這兩個現象正好是近年公司最常見、最容易造成誤判的地方，若不處理會直接砸掉近年公司 demo 的穩健性。雙方重新協商出一個更務實的折衷範圍：兩天內做 IBR（用現有 absences 機制）、absences 修正、merge 判定；General Instruction I 精細法源區分延後為已知限制。

---

## 12. Pillar 3：picker 架構分岔（Path A vs B）

柱子三動工前，Claude 先給出一個純唯讀調查指令，確認 `load_ruleset` 現況：目前不論 FYE 都回傳同一個「現代 ruleset」，且回傳型別是既有的 `contracts.Ruleset`（扁平清單結構），與柱子二新建的 `EraRuleset`（per-item 富物件結構）形狀完全不相容。更關鍵的是，下游（`segmenter.py`、`checks.py` 的 `allowed_absences`）硬依賴 `Ruleset` 才有的三個介面（`order_index()`、`expected_items`、`reserved_items`），`EraRuleset` 完全沒有。

這意味著 picker 不能只是「選出對應 era 再回傳」，還要解決新舊型別的落差。Claude 提出兩條路：路 A（picker 內部把選出的 `EraRuleset` 轉換成舊的 `Ruleset` 再回傳，下游零改動）、路 B（直接改下游三處讓它們吃新型別）。Claude 強烈建議路 A，理由是路 B 要改的是 Stage 2/3 最核心、最不能動壞的判定邏輯，風險過高；路 A 把新邏輯完全隔離在 picker 內部。

**使用者選擇路 A**。轉換函式的四個映射中，有一個關鍵判斷：**CONDITIONAL 的 item（如 9C、16）不進 `expected_items`**——因為 `expected_items` 語意是「一定存在」，若把「有無皆合法」的 CONDITIONAL 放進去，會讓下游把沒有 9C 的正常檔案（例如非中國審計的美國公司）誤判缺件。

Claude Code 實作後，FYE="1994-06-30" 呼叫 `load_ruleset` 回傳的 `expected_items` 只有 14 個（不含 1A/1B/7A/9A/1C/15/16）、`reserved_items` 為空——**這正是那個貫穿全專案的原始 bug（MSFT 1994 被現代規則誤判）修好的直接證據**。但這也讓三個既有測試（依賴「一律拿到現代規則」的舊行為）意料中地失敗——兩個跟 merge 有關、一個跟 Part III 全缺席有關，恰好精準命中 §11 那條寫進 pending_notes 的坑。

---

## 13. absences 語意修正（允許 vs 實際）

三個失敗中最容易修的一個，是 Part III 全缺席合法性判定失敗，根因是三個現代 era 的 `absences` 停在 `["10","11","12","13"]`（缺 14），而 MSFT 2023 的 Item 14 也是 IBR，證明 14 也該在允許缺席集合內。Claude 精確界定這步的範圍——只改 era_2005/2020/2023 三個現代 era，**era_1994 刻意不改**（因為 1994 的 Item 14 是 Exhibits/Part IV，不屬 Part III、也不是可 IBR 缺席的東西）。

修正後，`test_part_iii_absent_entirely_is_allowed` 轉綠，失敗數精確從 3 降到 2（剩下兩個 merge 相關），零回歸，證實這步的修正範圍界定準確、沒有波及不該動的部分。

---

## 14. 🔑 merge 判定：從宣告驅動到證據驅動的相鄰性判準

Claude 先給出一個純唯讀調查指令，摸清 merge 偵測與判定的完整資料流：偵測（`anchors.py` 的 regex 認出「Items X and Y」）本身沒問題，但合法性判定（`checks.py` 的 `check_legal_structure`）要求偵測到的合併群組必須跟 `ruleset.legal_structures.merges` 逐一比對相等才算合法——而 era_2023 的 `legal_structures` 目前完全沒有 merge 宣告，導致 APA 這種真實合併案例被誤判為 `ILLEGAL_STRUCTURE`。

Claude 提出兩條修復路徑：**做法 X**（改判定邏輯本身，讓「偵測到相鄰的合併」自動視為合法，不需要 era 事先宣告——真正的證據驅動，但這是動 Stage 3 不變量判定核心的決定，有踩到專案第四鐵律「不放寬門檻」的風險）；**做法 Y**（在各 era 的 legal_structures 補上 merge 宣告，不動判定邏輯，但仍是宣告驅動——必須為每一種公司的合併模式預先枚舉，漏填仍會誤判）。

**這裡是本對話中使用者介入最深、後果最直接的一次**。Claude 原本的傾向搖擺於「哪種做法更安全」，但使用者明確表態不接受純粹的宣告式補丁（做法 Y 或僅在單一 era 補宣告的折衷方案）：「但是 merge 宣告我不同意，因為我想要明或是後天多測幾間近年的公司，所以我擔心這個部分會讓近年公司的抽取結果很差（即使已經誠實宣告）」。使用者指出的具體風險是：油氣、REIT 這類會合併 Item 1/2 的公司，其 FYE 可能落在不同 era，若 merge 宣告只補在某一個 era，其他 era 的同類公司仍會被誤判——這個顧慮完全正確，且是 Claude 先前的方案沒有充分考慮到的。

這個否決把整個討論推向做法 X。Claude 進一步把做法 X 精煉成「相鄰性判準」版本——不是「偵測到任何合併就無腦放行」（那會讓 inv 5 判定退化成恆真、真正違反不放寬門檻的鐵律），而是「相鄰的合併（如 Items 1 and 2）視為合法證據、不需宣告；非相鄰或跳號的合併（如 Item 1 與 Item 9 被錯誤標成一組）依然舉旗」——這個版本同時滿足了使用者要的「證據驅動、涵蓋任何 era 任何公司」，也保留了不變量的診斷力，不算放寬門檻。使用者確認選擇 X。

Claude Code 實作後，兩個既有 merge 失敗測試轉綠，且新增的「非相鄰合併仍被舉旗」測試證明 inv 5 沒有退化成恆真，全套 **105 passed**，柱子三核心自此完整。

---

## 15. Claude Code 的自我修正：相鄰性定義 bug

使用者核對這輪結果時提出一個敏銳的觀察：「看起來先前遺留的兩個因為 merge 造成的 failed 也轉綠了。然而，claude code 似乎在連續的定義上跟你不太一樣，但看起來他的決定蠻 ok 的？」

Claude 檢視後確認：**Claude 自己給的「相鄰」定義（expected_items 裡的 index 純連續整數）有一個未預見的 bug**——現代 era 的 expected_items 是 `['1','1A','1B','1C','2',...]`，Item 1 的 index 是 0、Item 2 的 index 是 4，中間夾了三個子項，若直接照 Claude 的定義判斷，連最基本的 Item 1+2 合併都會被誤判為「非相鄰」，指令會直接失敗。

**Claude Code 在執行時自己發現了這個矛盾**，沒有盲從指令硬套、也沒有為了讓測試過而悄悄放寬判準，而是用實測證據指出問題、提出「子項不打斷主項相鄰性、只有主項才會打斷」的最小語意修正，並在回報中主動、完整地說明「我未假裝通過，而是做最小語意精修」。Claude 向使用者解釋，這正是「AI 不盲從錯誤指令、用實測發現問題、修對並誠實報告」的協作品質範例，且修正後的判準沒有削弱不變量的診斷力（非相鄰、跳號的偽合併仍被驗證會舉旗）。

---

## 16. 交接文件的兩次迭代與格式修正

柱子三核心完成後，使用者選擇下一步做層級二抽樣驗證，但要求先開新對話，並請 Claude 準備一份完整交接檔。Claude 第一次產出的 `HANDOFF_next_session.md` 是一份提煉過的專案狀態摘要（協作規則、三柱狀態、四個 era 細節、marker 框架現況、當前任務規劃）。

使用者接著貼出一份更精確、更完整的協作規範文字（含先前未涵蓋的 git 紀律、除錯迴路方法論等），並要求「把這個對話所有內容生成完整的 .md 檔」。Claude 第一次誤解為「把新協作規範併入交接摘要」，產出了一份更完整但本質仍是摘要的 `HANDOFF_next_session_complete.md`。

**使用者直接糾正**：「你搞錯重點了，我不是要寫交接摘要。我是要你把『這整段對話』，完整以.md記錄下來。」Claude 因此改而嘗試逐輪重建完整對話記錄（含前段壓縮摘要的還原說明），過程中一度誤植輪次順序（漏掉一段問答），經自行核對後修正。

在這份逐輪記錄接近完成時，**使用者再度打斷，提供一份風格更好的範例文件**（另一段對話產出的「完整對話紀錄」，採主題分章敘事、明確標記使用者關鍵角色，而非逐輪照抄），並要求 Claude 依此範例重新整理本對話——這正是本文件（含開頭的「使用者關鍵貢獻總覽」與主題分章結構）誕生的直接原因。

---

## 附錄：關鍵檔案與路徑索引

- 專案根目錄：`~/Documents/sec-10k-extractor/`
- Era ruleset 定義：`src/sec10k/ruleset/era.py`（`EraRuleset`、`ItemRule`、`ERA_1994`/`ERA_2005`/`ERA_2020`/`ERA_2023` 四常數）
- Picker / 舊 Ruleset 轉接層：`src/sec10k/ruleset/loader.py`（`load_ruleset`、`_pick_era`、`_era_to_ruleset`）
- Stage 3 不變量（含 merge 相鄰性判準）：`src/sec10k/invariants/checks.py`（`check_legal_structure`，inv 5）
- 資料契約：`src/sec10k/contracts.py`（`Ruleset`、`LegalStructure`）
- FYE 抽取（柱子一）：`src/sec10k/metadata.py`（`extract_fiscal_year_end`）
- 測試：`tests/test_era_schema.py`（era 資料驗證）、`tests/test_loader_picker.py`（picker 挑選正確性）、`tests/test_invariants.py`、`tests/test_stage2.py`
- 法規研究文件：`docs/SEC_10K_item_ruleset_history.md`
- 真實 fixture：`tests/fixtures/real/`（MSFT FY1994、MSFT FY2023、APA FY2023 三份）
- 交接文件：`HANDOFF_next_session.md`（第一版）、`HANDOFF_next_session_complete.md`（第二版，含完整協作規範）
- 盤點文件：`stage0_status_and_pillar3_plan.md`

**柱子一（FYE 擷取）完成 | 柱子二（四個 era ruleset）完成 | 柱子三（picker + merge 相鄰性判準）完成 | 全套 105 passed | MSFT 1994 原始 bug 已修好 | 下一步：層級二抽樣驗證**
