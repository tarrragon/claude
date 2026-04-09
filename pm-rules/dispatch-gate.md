# 決策路由 — 派發閘門（第負一層）

> 所有派發前必須通過的兩道關卡。
>
> 路由入口：.claude/pm-rules/decision-tree.md

---

## 關卡一：複雜度關卡（Dispatch Complexity Gate）

評估認知負擔指數（變數數 + 分支數 + 巢狀深度 + 依賴數）。

| 結果 | 行動 |
|------|------|
| 指數 <= 10 | 通過，進入並行化判斷 |
| 指數 > 10 | [強制] 先拆分子任務再派發（AskUserQuestion #6，W15-004）。禁止整包派發給單一代理人。拆分後每個子任務重新通過本關卡 |

> 公式詳見：.claude/rules/core/cognitive-load.md

---

## 關卡二：Context Bundle 檢查

| # | 檢查項 | 通過條件 |
|---|--------|---------|
| 1 | Ticket 含分析結果 | Execution Log 有 PM 寫入的 Context Bundle |
| 2 | Agent prompt <= 30 行 | 只含 Ticket ID + 動作指令（Hook 自動攔截） |
| 3 | 重派已更新 Bundle | 前次失敗產出已納入 Ticket |

> 自動防護：`agent-prompt-length-guard-hook.py` 在 prompt 超過 30 行時阻擋（PC-040）。
> Context Bundle 模板：.claude/pm-rules/context-bundle-spec.md

---

## 並行化判斷

兩道關卡通過後，評估並行可行性：

```
可並行拆分? ─是→ 複雜度適合並行?
    |                      |
    |                      +─ 否 → [序列派發]
    |                      |
    |                      +─ 是 → Agent A 的發現會改變 Agent B?
    |                               |
    |                               +─ 否 → [並行派發 Task subagent]
    |                               |
    |                               +─ 是 → 3-4x 成本合理?
    |                                        |
    |                                        +─ 是 → [Agent Teams 派發]（/agent-team）
    |                                        +─ 否 → [Task subagent + PM 中轉]
    |
    +─── 否 → 進入第零層明確性檢查 → 第一層類型判斷（序列模式）
              分工路由在 command-routing.md 的 Ticket 類型表決定
```

**派發模式**：預設背景模式（`run_in_background: true`）。

---

## 豁免條件

| 豁免情境 | 說明 |
|---------|------|
| PM 前台任務（ANA/DOC） | PM 自己執行，無需 Context Bundle（無代理人接收） |
| 純狀態查詢 | PM 直接用 `ticket track` CLI，無需通過複雜度關卡 |

> PM 前台 vs 代理人背景的分工定義：command-routing.md（分工路由表）

---

## 代理人觸發優先級（派發時參考）

> 從 agent-dispatch-enforcement.md 合併，統一派發前參考。

| 優先級 | 代理人 | 觸發條件 |
|--------|-------|---------|
| 1（最高） | incident-responder | 錯誤/失敗發生 |
| 2 | saffron-system-analyst | 架構審查 |
| 3 | security-reviewer | 安全相關 |
| 4 | 其他專業代理人 | 專業領域 |
| 5 | TDD 階段代理人 + thyme-extension-engineer | 標準開發 |

> Hook 自動觸發（命令入口驗證等）不在此優先級表中，由 Hook 系統獨立處理。

---

## 相關文件

- .claude/pm-rules/parallel-dispatch.md - 完整並行化規則、派發模式
- .claude/pm-rules/context-bundle-spec.md - Context Bundle 規範
- .claude/pm-rules/askuserquestion-rules.md - AskUserQuestion 使用限制
- .claude/pm-rules/task-splitting.md - 任務拆分指南

---

**Last Updated**: 2026-04-09
**Version**: 1.0.0 - 從 decision-tree.md 拆分（決策樹二元化拆分）
