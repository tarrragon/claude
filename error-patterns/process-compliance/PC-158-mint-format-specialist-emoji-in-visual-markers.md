# PC-158: mint-format-specialist 在視覺標記場景寫入 emoji（違反規則 3）

> **錯誤類別**：流程合規（代理人對既有規則的內化失敗）
> **嚴重度**：中（不阻擋執行但污染框架文件，需手動修正）
> **發現案例**：0.19.0-W6-001.3（mint 在 search-tools-guide SKILL.md 三刀流決策樹 ASCII 圖中用 ✓ 標記推薦工具）

---

## 症狀

mint-format-specialist 派發完成 DOC 類 ticket 後，產出的 markdown 文件含 emoji 字元（如 ✓ U+2713），違反 `.claude/rules/core/language-constraints.md` 規則 3 禁用 emoji。具體場景：

| 違規位置 | 違規字元 | mint 原意 |
|---------|---------|----------|
| ASCII 流程圖 `→ tool ✓` | ✓ (U+2713) | 標記推薦/支援工具 |
| 表格 `[x] / ✅` | ✅ | 視覺完成標記 |
| 標題或章節 `🎯 / 🔧 / ⚠️` | 各類 emoji | 視覺重點標記 |

PM merge 前用 ripgrep 偵測（`rg "[\x{1F300}-\x{1F9FF}]|[\x{2600}-\x{27BF}]"`）才能發現，否則 emoji 進主線並污染框架文件。

## 根因

mint-format-specialist 的職責定位是「format 修正與品質優化」，但既有 SKILL.md 與派發 prompt 未顯式強調規則 3。在「需要視覺標記時」mint 的預設行為是使用 emoji（符合一般 markdown 文件慣例），與專案規則 3 衝突。

代理人並未主動執行二次審查（document-writing-style 強制要求）掃描 emoji，導致違規字元進入 commit。

## 案例：W6-001.3 SKILL.md

| 行號 | 違規內容 | 替換為 |
|------|---------|--------|
| 103 | `→ codebase-memory-mcp (cbm) ✓` | `→ codebase-memory-mcp (cbm) [推薦]` |
| 118 | `→ Serena ✓ （唯一支援）` | `→ Serena [唯一支援]` |
| 123 | `→ codebase-memory-mcp ✓` | `→ codebase-memory-mcp [推薦]` |

PM 在 merge 前 emoji guard 偵測 3 處違規，用 Edit 工具替換並 fix commit（0847928b）。

## 防護要點

### 規則層（自律）

| 動作時機 | 強制查詢 |
|---------|---------|
| 派發 mint 前撰寫 prompt | 加 1 行「禁用 emoji（規則 3），需視覺標記用 `[x]` / `[推薦]` / `OK` 等 ASCII 替代」 |
| mint 自身回報前 | 二次審查清單必含「emoji/簡體字/拼寫」掃描（document-writing-style 強制） |
| PM 接收 mint 完成通知後 merge 前 | `rg "[\x{1F300}-\x{1F9FF}]\|[\x{2600}-\x{27BF}]" <changed_files>` 預檢 |

### Hook 層（建議實作）

PreToolUse:Bash 偵測 `git commit` 命令時，若 staged diff 含 emoji range 字元且檔案在 `.claude/` 或 `docs/` 下，立即 warn / block。

實作要點：
- 偵測 unicode range：U+1F300-U+1F9FF (Misc Symbols + Pictographs) + U+2600-U+27BF (Dingbats，含 ✓)
- 豁免機制：commit message 含 `--allow-emoji` 或 ticket type 為實驗性（如 ANA + 引用第三方原文）
- 對既有 emoji（如歷史 commit 留下的）：only block new additions in diff

### 中期：mint SKILL.md 強化

在 mint-format-specialist SKILL.md 的「禁止行為」章節（agent-definition-standard 規範三區塊）加：「禁止在任何輸出（程式碼、文件、commit message、PR 描述）使用 emoji，視覺標記改用 ASCII 等價物」。

## 修復建議

短期（自律）：PM 派發 mint 時，prompt 加「規則 3 提醒」單行；merge 前 emoji 預檢。

中期（mint SKILL）：mint SKILL.md 「禁止行為」章節新增明示條款。

長期（hook）：PreToolUse:Bash commit emoji guard hook。

## 相關規則

- `.claude/rules/core/language-constraints.md` 規則 3 — 禁用 emoji
- `.claude/rules/core/document-writing-style.md` — 二次審查強制執行
- `.claude/rules/core/agent-definition-standard.md` — 代理人禁止行為章節

## 相關 Memory

- `feedback_mint_emoji_violation_in_visual_markers.md`

---

**Last Updated**: 2026-05-25
**Source**: 0.19.0-W6-001.3 / W3-045 session 收尾發現
**Status**: 短期防護已落地（PM merge 預檢），中期/長期待 follow-up ticket
