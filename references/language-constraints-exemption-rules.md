# 語言約束規則 3 豁免條款（按需讀取）

> **載入時機**：編輯規格文件（`docs/spec/**/*.md`）含 src code log 字面前讀取。本檔自 `.claude/rules/core/language-constraints.md` 規則 3 外移，主規則仍為禁止 emoji 的權威來源。

---

## 規則 3 豁免條款：規格文件對 src code log 字面的機械引用

規格文件（`docs/spec/**/*.md`）內**允許**保留 src code log 前綴的 emoji 字面，**限定**以下三條件同時成立：

| 條件 | 說明 |
|------|------|
| 1. 檔案位置 | 限 `docs/spec/**/*.md`（其他位置仍適用絕對禁令）|
| 2. 引用語意 | 限「結構化前綴對應表」內的 source-of-truth 機械引用（如 `[前綴 / 模組 / 用途 / 範例]` 表格）|
| 3. 字面一致性 | 必須與 src code log 字面完全相同（含字元、空格、冒號）|

**Why/Consequence**：規格文件本職為「契約字面 = 程式碼字面」（grep 對齊機制），spec 文件不自動載入不觸發 W12-002.3 污染風險；強制移除 emoji 或改 codepoint 標記會破壞 grep 對齊、違反 spec 本職造成契約失效，E2E 字面斷言與規格脫鉤。

**Action**：在規格文件結構化前綴對應表上方加豁免聲明引用本條款；非結構化散落 emoji 仍須遵守規則 3 絕對禁令（範例：`docs/spec/extraction/e2e-contract.md` §3.4）。本條款描述本身不展示 emoji 字面，僅以 U+XXXX codepoint 抽象敘述（W12-002.3 設計原則）。

> **來源**：W5-008 ANA（方案 A 變體）。

---

## 相關文件

- `.claude/rules/core/language-constraints.md` 規則 3 — 禁止 emoji 的權威來源（本豁免條款的上游）
