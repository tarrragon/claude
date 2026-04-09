# 決策樹 — 問題路由

> 訊息類型判斷為「問題」時的完整路由流程。
>
> 路由入口：.claude/pm-rules/decision-tree.md
> 來源：決策樹二元化拆分

---

## 明確性檢查（問題分支）

> 當定義不明確時，應該往上詢問確認，而非強行做出判斷。
> **工具要求**：向用戶呈現選項供選擇時，必須使用 AskUserQuestion 工具，禁止文字提問。

| 情境 | 觸發條件 | 確認目標 |
|------|---------|---------|
| 不確定性詞彙 | 包含「好像」「可能」「似乎」等 | 確認問題性質 |
| 模糊需求 | 無法用「動詞+目標」描述 | 確認具體需求 |

---

## 訊息類型識別

| 關鍵字 | 判斷為問題 |
|-------|-----------|
| "怎麼樣"、"進度"、"為什麼"、"如何"、"是什麼"、"?" | 進入本檔案的問題路由 |

---

## 問題處理流程

> **分工原則**：狀態查詢 PM 直接執行，資料收集型查詢派發代理人。主線程禁止直接執行 WebFetch、WebSearch。

| 問題類型 | 路由 | 理由 |
|---------|------|------|
| Ticket/版本狀態查詢 | **PM 直接執行**（`ticket track snapshot` 等） | 狀態查詢無需代理人，PM 直接用 CLI |
| 程式碼結構/架構查詢 | → Explore agent | 需深度讀取多檔案 |
| 外部資源 | → oregano-data-miner | 需 WebFetch/WebSearch |
| 架構/設計諮詢 | → system-analyst / system-designer | 專業知識 |
| 環境/安全/效能 | → system-engineer / security-reviewer / ginger | 專業知識 |

**SKILL 提示強制採納**：當 Hook 輸出 `[SKILL 提示]` 時，**必須**使用建議的 SKILL 指令。

> 完整派發對照表：.claude/pm-rules/query-vs-research.md

---

## 相關文件

- .claude/pm-rules/decision-tree.md - 路由索引
- .claude/pm-rules/query-vs-research.md - 完整查詢派發對照表
- .claude/pm-rules/askuserquestion-rules.md - AskUserQuestion 規則

---

**Last Updated**: 2026-04-09
**Version**: 1.0.0 - 從 decision-tree.md 拆分（決策樹二元化拆分）
