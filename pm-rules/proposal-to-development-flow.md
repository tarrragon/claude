# 提案到開發的文件工作流程

PROP 提案核准後、進入開發前的強制文件更新流程。

> **來源**：v0.32.0 PROP-007 討論時，PM 差點在文件未更新的情況下直接進入開發。

---

## 觸發條件

| 條件 | 執行流程 |
|------|---------|
| PROP 完整核准 | 完整流程（下方 6 步） |
| PROP 部分核准 | 完整流程，Step 1/2/5 僅涵蓋核准範圍；排除項目標記 deferred |
| 跨專案提案 | 每個專案各自獨立執行完整流程 |
| 小型提案（修改 <= 2 檔案） | Step 1/2 視影響範圍決定，其餘正常 |
| 緊急修復（P0 bug） | 可先開發，48 小時內補齊 Step 1/2 |
| 純研究型提案 | 不觸發（建 ANA Ticket 追蹤研究任務） |
| 提案仍在討論中 / 被 rejected | 不觸發 |

**部分核准判斷**：用戶回覆含「X 先不做」「不需要 Y」等排除性語句。PM 記錄 approved_scope 和 deferred_scope。

**純研究型判斷**：產出不含任何程式碼、配置、UC/Spec、規則文件變更。研究結論若導出開發需求，建立新 PROP 進入本流程。

---

## 強制步驟

提案核准後，依序完成以下步驟才能開始開發：

| 步驟 | 檔案 | 內容 |
|------|------|------|
| 1. 更新需求規格 | `docs/app-requirements-spec.md` | 反映技術決策 |
| 2. 更新用例 | `docs/app-use-cases.md` | 反映受影響的 UC |
| 3. 更新版本索引 | `docs/todolist.yaml` | 新增/修改版本 |
| 4. 更新變更記錄 | `CHANGELOG.md` | 版本變更摘要 |
| 5. 建立 Worklog + Tickets | `docs/work-logs/` + tickets | Wave 規劃和 Atomic Tickets |
| 6. 提交文件 + 開始開發 | git commit → feature branch | Step 1-5 完成後才建分支 |

**禁止**：跳過步驟直接開發、先開發再補文件、只更新部分文件。

---

## 相關文件

- .claude/pm-rules/plan-to-ticket-flow.md - Plan 到 Ticket 轉換
- .claude/pm-rules/ticket-lifecycle.md - Ticket 生命週期
- .claude/pm-rules/decision-tree.md - PM 決策樹

---

**Last Updated**: 2026-04-02
**Version**: 1.1.0 - 精簡為表格格式，加入 CHANGELOG 步驟和觸發條件分類（0.31.1-W1-022）
