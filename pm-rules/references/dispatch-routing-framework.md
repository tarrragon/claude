# 派發路由框架

> **來源**：從 parallel-dispatch.md 抽取（0.4.0-W3-020）

---

## 數量原則

依任務性質判斷，無固定上限。同一批次應為同類型代理人。單一失敗不影響其他任務。

**批量評估任務**：當 N 個獨立目標需要相同分析時（如掃描 59 個 agent 定義），預設 1 個目標 = 1 個 Agent（單一職責，最低認知負擔）。每個 Agent 只需讀取分析標準 + 自己負責的 1 個目標，不需要知道其他目標的存在。詳見 `.claude/skills/bulk-evaluate/SKILL.md`。

---

## 不適用並行派發

| 情況 | 處理方式 |
|------|---------|
| **跨 Wave 任務** | **禁止並行，一次一個 Wave**（見下方跨 Wave 優先級規則的例外條件） |
| TDD 跨階段 | 序列派發 |
| 跨架構層修改 | 序列派發 |
| 共享狀態/有邏輯依賴 | 序列派發 |
| 整合測試 | 單獨執行 |
| 任一任務認知負擔 > 10 | 序列派發（高複雜度需專注） |
| P0/P1 高風險修改 | 序列派發（需 PM 專注監控） |
| 涉及設計決策/架構變更 | 序列派發（需逐步驗證） |

---

## 派發模式：預設背景

所有代理人派發**預設使用 `run_in_background: true`**，讓主線程保持靈活。

**背景派發的含義**：
- PM 派發後立即釋放，可接收新指令、與用戶溝通、建立 Ticket
- 代理人執行結果寫入 Ticket，只回報成功/失敗
- PM 透過 `/ticket track` 查詢獲得詳細結果

**例外（前景執行）**：Skill/CLI 查詢、即時驗證等需要結果才能繼續的場景。

> 詳細規則：.claude/references/background-dispatch-rules.md

---

## 派發方式判斷

**核心問題**：「Agent A 的發現會改變 Agent B 正在進行的工作嗎？」

| 答案 | 路由 |
|------|------|
| 否（各自獨立） | Task subagent 並行派發 |
| 是 且成本合理 | Agent Teams 派發（3-4x 成本） |
| 是 但成本不合理 | Task subagent + PM 中轉 |

---

## 跨 Wave 優先級規則

| 規則 | 說明 |
|------|------|
| 同 Wave 優先 | 同一 Wave 的 Ticket 優先於其他 Wave |
| 低 Wave 號優先 | Wave 1 的 pending 優先於 Wave 2 的 pending |
| blockedBy 例外 | 若 Wave 1 被 Wave 2 的 Ticket 阻塞，先處理 Wave 2 的阻塞源 |

跨 Wave 並行：僅在兩個 Wave 的 Ticket 完全無依賴時才允許。

---

**Last Updated**: 2026-03-29
**Version**: 1.0.0 - 從 parallel-dispatch.md 抽取（0.4.0-W3-020）
