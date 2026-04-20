# PC-085: CJK 漢字相鄰 codepoint 在 `\uXXXX` escape 中的肉眼混淆

---

## 分類資訊

| 項目 | 值 |
|------|------|
| 編號 | PC-085 |
| 類別 | process-compliance |
| 風險等級 | 低（測試偽紅燈 / 清單設計誤用；不構成安全漏洞） |
| 首發時間 | 2026-04-17（W14-007 Phase 3b D1 測試案例筆誤） |
| 姊妹模式 | PC-074（繁簡共用字誤判）、PC-084（繁日共用字誤判）— CJK 清單設計三重奏 |

---

## 症狀

在 Python / JSON / 配置檔中以 `\uXXXX` Unicode escape 引用 CJK 漢字時，繁體 / 簡體 / 日文新字體等同義對應字元的 codepoint 高度相鄰（通常只差 1-3 位），肉眼極易寫錯。

首發案例：

| 意圖 | 正確 codepoint | 誤打 codepoint | 差異 |
|------|---------------|---------------|------|
| 簡體「遗」（測 SIMPLIFIED_CHARS 命中） | U+9057 | U+907A（繁體「遺」） | 末位 `7` → `A` |

當測試原意驗證「簡體字命中簡體偵測」，但測試字串寫成繁體字 codepoint，會產生**偽紅燈**：既有實作正確（繁體不應命中），但測試邏輯因字元錯誤而斷言失敗。

類似風險場景：

- SIMPLIFIED_CHARS / JAPANESE_ONLY 清單擴充時，從參考表抄 codepoint 誤植
- AUQ payload 測試資料中混用繁/簡/日漢字
- terminology-dictionary 或 i18n 檔案中對照表填寫

---

## 根本原因

### 已驗證事實

1. **codepoint 鄰近度高**：繁簡對應字 / 繁日新舊字體對應字常在同一 CJK block 內，差距 ≤ 3 位是常態
   - 遺（繁）U+907A / 遗（簡）U+9057 / 遺未變（日）
   - 讀（繁）U+8B80 / 読（日新）U+8AAD / 读（簡）U+8BFB
   - 鑑（繁日共用）U+9451 / 鑒（繁舊）U+9452
2. **`\uXXXX` 形式去視覺語意**：在 source code 中寫成 `\u9057` 時，閱讀者無法憑「字形」回推是繁是簡是日；只能查字典或執行程式確認
3. **PC-084 17 字可入清單**已列出完整 codepoint 對照，但測試資料編寫時若不逐字對查，仍會筆誤

### 真根因

1. **肉眼模式識別失效**：`\u9057` 和 `\u907A` 在等寬字型下僅相差最後一字元，高壓下易混淆
2. **測試資料未配交叉驗證**：D1 測試意圖「驗證簡體字命中」但用詞時混入繁體 codepoint；沒有「資料邊寫邊驗」的互動式確認
3. **對照表外部化成本**：每次查 PC-084 / terminology-dictionary 成本高，token 心智慣性直接拼 codepoint 易失誤

---

## 常見陷阱模式

| 陷阱表述 | 為何仍構成誤用 |
|---------|--------------|
| 「我剛才看過 PC-084 表格，背起來了」 | 記憶不可靠；codepoint 差 1-3 位的相鄰字易在工作記憶中互換 |
| 「`\uXXXX` 形式有註解說明，不會錯」 | 註解可能與 codepoint 不一致；本案例 D1 原註解寫「遗」但 codepoint 是「遺」 |
| 「測試失敗會紅燈，不會漏偵」 | 測試邏輯層失敗看似驗證實作錯，實則驗證資料錯，形成「偽紅燈誤判實作」 |

---

## 防護措施

| 層級 | 措施 | 狀態 |
|------|------|------|
| 資料驗證 | 新增測試資料或清單字元時，同行註解必須含正體中文字元（`"\u9057"  # 遗 U+9057 簡體`）且**字形可肉眼辨識** | 行為準則 |
| Lint 輔助 | 工具可擴充為：掃描 `\uXXXX` 後的註解字形，若註解字 codepoint ≠ escape codepoint 則警告 | 未實施（值得追蹤） |
| 測試輔助 | 將 PC-084 / PC-074 / terminology-dictionary 字對照表固化為 pytest fixture，測試直接引用避免重複手寫 | 未實施 |
| 互動驗證 | 寫完測試資料後立即跑一次 pytest，失敗時第一時間核對「是否實作錯 vs 是否資料錯」| 行為準則 |
| Memory | 記錄本模式作跨 session 提醒 | 已實施（配對本檔） |

---

## 除錯流程（測試意外紅燈時的檢查順序）

1. **查斷言訊息**：若看到「期待某 codepoint」→ 先驗證「測試資料是否正確含此 codepoint」
2. **反查 codepoint**：`python3 -c "print(hex(ord('字元')))"` 確認意圖字元的實際 codepoint
3. **查繁簡對照**：若測試意圖是簡體但 codepoint 顯示繁體，90% 是資料筆誤
4. **最後才檢查實作**：確認測試資料正確後，才懷疑實作邏輯

本流程可避免「修實作卻是資料錯」的反模式（本 ticket W14-007 D1 案例：紅燈 → 第一時間懷疑 SIMPLIFIED_CHARS 邏輯問題 → 查才發現是測試字串 codepoint 誤打）。

---

## 教訓

1. **codepoint 混淆比字形混淆更頻繁**：`\uXXXX` 形式雖安全（避免了字元編碼問題），但代價是肉眼辨識力降為零
2. **CJK 三重奏（簡 / 繁 / 日新字體）驗證責任相同**：PC-074、PC-084、PC-085 構成 CJK 字元清單設計的三重驗證框架，任何一環失守都會產生誤用
3. **「偽紅燈」的危害**：比「偽綠燈」更隱匿 — 偽紅燈讓開發者誤修正實作，可能引入真正的 bug

---

## 象限歸類

本模式的防護屬 **摩擦力管理 C 象限（增加摩擦）**：寫 `\uXXXX` 時多寫一行註解確認字形，以及測試紅燈時先驗資料再驗實作。代價（查 codepoint / 核對字形）低，收益（避免修錯實作）高。

---

## 相關文件

- `.claude/error-patterns/process-compliance/PC-074-charset-guard-hook-shared-char-false-positive.md` — 繁簡共用字誤判
- `.claude/error-patterns/process-compliance/PC-084-trad-jp-shared-char-false-positive.md` — 繁日共用字誤判
- `.claude/terminology-dictionary.md` — 專案用語規範字典
- `.claude/hooks/askuserquestion-charset-guard-hook.py` — SIMPLIFIED_CHARS / JAPANESE_ONLY 清單實際應用

---

**Last Updated**: 2026-04-17
**Version**: 1.0.0
**Source**: W14-007 Phase 3b D1 測試案例 `\u907a`（繁體「遺」）誤打為意圖的 `\u9057`（簡體「遗」），造成偽紅燈誤導
