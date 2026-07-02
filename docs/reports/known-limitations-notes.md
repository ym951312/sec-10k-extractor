# 已知局限 —— 候選清單(待整併進 README)

> 暫存區:記錄已知的、設計上可接受的局限與其失敗方向。之後由維護者整併進 README 的「已知局限」章節。

## L1 — 格式偵測為啟發式標記列舉(`ruler/formats.py::_HTML_HINT`)

- **性質:** 用一張「真正 HTML 文件標記」的 allow-list(`<html>`/`<body>`/`<div>`/`<p>`/`<font>`/`<span>`/`<!doctype html>`)判定 HTML,不在清單上即落 ASCII。`<table>` 刻意**不列入**(EDGAR ASCII 世代用 SGML `<TABLE>` 排財報,列入會誤判)。
- **失敗方向:** 若某個真正的 HTML 標記漏列,可能發生「罕見的、僅用 `table`/`tr`/`td` 而無 `div`/`span`/`p` 的 HTML 檔被誤判為 `ascii`」。
- **現況:** 對所有已知 fixture(MSFT 1994 ascii、MSFT 2023 / APA html_xbrl、合成 ascii)**不觸發**。
- **為何可接受:** 失敗方向相對安全——ASCII 路徑用 identity 正規化,異常較可能被下游(完整性對帳 / Stage 2 切割)顯現,而非 silent 錯誤。
- **來源:** 問題 1 修正(2026-07-01),見 `docs/reports/` 驗證脈絡。

## L2 — 現代靜態 ruleset 套用到所有世代(Stage 0 未實作)

- 目前只有單一「現代」ruleset;對舊世代(如 MSFT 1994,無 1A/7A/9A/15)`should_exist` 會誤報缺 item → `filing_status=failed`。屬 **Stage 0(按 `fiscal_year_end` 動態選 ruleset)** 範圍,尚未實作。Item 1C 因此暫以 optional 處理(見 `checks.OPTIONAL_ITEMS`)。

## L3 — 密度式 TOC 偵測(`ruler/front_matter.py`)

- density 路徑只在「群集起點落在 ruler 前 20%(`_TOC_FRONT_FRACTION`)」時採用,避免深處連續短 item 群被誤判 TOC。失敗方向:真 TOC 若位於文件 20% 之後會偵測不到(安全側:頂多目錄回音被當錨點,不會吞掉本體)。

## L5 — ASCII 路徑殘留 `<PAGE>` 分頁標記(未來候選精修)

- **性質:** ASCII 世代走 identity 正規化,`<PAGE>`(EDGAR 分頁標記)以字面文字保留在尺上;行級頁首頁尾偵測剝掉部分重複 chrome 後,仍有殘留(MSFT 1994:尺內仍有 38 個 `<PAGE>`)。
- **影響:** **不影響完整性**——baseline 與尺一致,守恆對帳仍平衡(`missing=0/extra=0`);但**語意上不精確**:`<PAGE>` 是分頁標記而非內容,其中的 `PAGE` 會被當作 word token。
- **候選精修:** ASCII 路徑可將 `<PAGE>` / form-feed 辨識為分頁標記並剝除、記入 ledger(比照頁首頁尾),讓尺更乾淨。屬未來 ASCII 分頁處理的精修項,**非** correctness bug。
- **來源:** 問題 1 修正(2026-07-01)後的順帶觀察。

## L4 — 驗證樣本尚未分層飽和

- 真實檔目前 3 份(MSFT 2023 HTML+XBRL、MSFT 1994 ASCII、APA 2023 合併 1&2);設計 §5 的分層抽樣(年代/產業/規模/本國 vs 外國、10-K/A 等)尚未到飽和;confidence 未經 eval set 校準,以 high/med/low 呈現。
