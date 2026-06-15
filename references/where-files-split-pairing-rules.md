# where.files 撰寫指引：拆分檔案配對

> **來源**：自 `.claude/methodologies/atomic-ticket-methodology.md` 外移（W8-034.4 瘦身）。本檔為「骨架 + references 拆分架構」下 where.files 撰寫的操作 SSOT，方法論主檔保留判準摘要 + 路由。

本檔回答一個問題：當 ticket 修改的規則檔採「骨架（索引）+ 實質內容（詳版）」雙檔架構時，where.files 該列哪些路徑，避免範圍漂移。

---

## 背景：骨架與實質內容的拆分架構

本專案 `.claude/` 規則目錄採「骨架（索引）+ 實質內容（詳版）」雙檔拆分架構（自 W10-076.1 落地）：

- **骨架**（auto-load）：`rules/core/X.md`、`pm-rules/X.md` — 每次 session 自動載入，只含觸發指標、摘要、索引表。
- **實質內容**（按需讀取）：`references/X.md`、`references/X-details.md` — 詳細規則、範例、深度說明。

骨架第一行通常含「完整規則：references/X.md（按需讀取）」明示引用。

**Why**：骨架只是索引——骨架的存在承諾讀者「內容看 references/」，因此擴充規則內容必然牽動 references/，而非骨架本身。忽略此結構會導致 where.files 僅列骨架，但 agent 實際修改 references/ 而產生範圍漂移。

---

## 規則 1：列「實質修改會發生的位置」

核心問題：「此 ticket 的修改本質是改變規則『入口索引』還是『規則本身的內容』？」

| 修改類型 | where.files 列法 | 判別問題 |
|---------|-----------------|---------|
| 骨架索引變更（版本號、索引表、導航連結） | 只列骨架路徑 | 「只改入口，不動內容」 |
| 實質內容擴充（新增規則、修改細節） | 列 references/ 實質檔路徑 | 「改的是規則內容本身」 |
| 同步變更（索引更新 + 細節同步） | 兩者都列 | 「入口和內容都要動」 |

**Consequence**：僅列骨架時，agent 必須自裁決定是否延伸到 references/，有範圍漂移風險且缺乏明示記錄。

---

## 規則 2：PM 撰寫 where.files 前的拆分偵測

列 where.files 時，若路徑含 `rules/core/` 或 `pm-rules/`，必須檢查是否存在對應的 references/ 拆分配對：

```bash
for path in $(echo "$where_files" | grep -E "(rules/core|pm-rules)/"); do
  basename=$(basename "$path" .md)
  find .claude/references -name "${basename}*.md"
done
```

**本專案已知 10+ 組拆分對**（任何修改這些規則內容的 ticket 都有 where.files 漂移風險）：

| 骨架（auto-load） | 實質內容（按需讀取） | 拆分類型 |
|-----------------|-------------------|---------|
| rules/core/quality-common.md | references/quality-common.md | 同名 |
| rules/core/bash-tool-usage-rules.md | references/bash-tool-usage-details.md | -details |
| pm-rules/askuserquestion-rules.md | references/askuserquestion-scene-details.md | -details |
| pm-rules/decision-tree.md | references/decision-tree-checkpoint-details.md | -details |
| pm-rules/incident-response.md | references/incident-response-details.md | -details |
| pm-rules/parallel-dispatch.md | references/parallel-dispatch-details.md | -details |
| pm-rules/tdd-flow.md | references/tdd-flow-details.md | -details |
| pm-rules/verification-framework.md | references/verification-framework-details.md | -details |
| pm-rules/version-progression.md | references/version-progression-details.md | -details |
| pm-rules/plan-to-ticket-flow.md | references/plan-to-ticket-details.md + references/plan-to-ticket-mapping-details.md | 1-to-many |

> 本規則適用於所有涉及上表拆分對的 ticket，不限於 quality-common。新增規則檔案後應同步維護上表。

---

## 規則 3：Agent 延伸 where.files 外檔的行為規範

| 情境 | 允許行為 |
|------|---------|
| 延伸符合 ticket 意圖（規則實質內容落在 references/） | 允許延伸，必須 append-log：「延伸至 X.md，原因：[理由]」 |
| 延伸超出 ticket 意圖（新增無關模組、修改非配對檔） | 禁止延伸，停止並回報 PM |

**預設禁止默默擴展未記錄**。Agent 每次「延伸符合意圖」時，立即在 Solution 寫一行：`延伸至 [path]，原因：[骨架第 N 行明示引用此 references/]`。

> 反例（W10-011）：where.files 僅列骨架 `quality-common.md`，遺漏 `references/quality-common.md`（實質內容在此），agent 須自裁延伸且未記錄，PM 無法追蹤實際修改範圍。正例：修改規則內容時同步列兩者，或僅改細節時只列實質檔。

---

## 相關文件

- `.claude/methodologies/atomic-ticket-methodology.md` §「where.files 撰寫指引」 — 判準摘要與本檔路由
- `.claude/references/acceptance-auditor-details.md` Step 2.5 — 骨架/references 配對完整性檢查（auditor 執行層）
- `.claude/pm-rules/ticket-lifecycle.md` — 骨架/references 雙向檢查規則

---

**Last Updated**: 2026-06-15
**Version**: 1.0.0 — 自 atomic-ticket-methodology.md 外移（W8-034.4 核心化瘦身），保留完整三規則 + 10 組拆分對表
