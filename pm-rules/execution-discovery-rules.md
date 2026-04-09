# 決策樹 — 執行 Domain

> 本文件從 decision-tree.md 按 DDD domain 邊界拆分。
> 路由入口：.claude/pm-rules/decision-tree.md
> 來源：0.17.2-W3-007.1

---

## 第三層半：執行中額外發現規則（技術債/問題/超範圍需求）

> 當 PM 或 Agent 在 Ticket 執行過程中發現任何需要追蹤的問題時，適用本規則。

**核心規則：發現即建立，不詢問確認**

- 發現了需要追蹤的問題嗎？→ 是 → **直接 /ticket create**
- 要不要處理、優先級高不高 → 這是後續 acceptance-auditor 審核的職責，不是此刻的決策點

### 子任務 vs 獨立 Ticket 判斷

| 判斷條件 | 建立方式 | 範例 |
|---------|---------|------|
| 因執行當前 Ticket 而產生（因果關係） | 子任務（`/ticket create --parent {current_id}`） | 實作中發現需要先重構某模組 |
| 與當前 Ticket 相同功能模組 | 子任務 | 同一個 feature 的額外驗收條件 |
| 獨立問題、不同模組 | 獨立 Ticket | 發現另一個模組的 bug |
| 跨版本的技術債 | 獨立 Ticket（歸入 todolist） | 長期架構改善 |

> 識別條件、強制處理流程、禁止行為清單：.claude/pm-rules/plan-to-ticket-flow.md（「執行中額外發現」章節）

### 效能問題發現後的代理人更新（強制）

> **來源**：v0.2.1 W5-002/003/004（記憶體洩漏）、W6-002（狀態機終態）、W7-003（Widget 重建）— 多次效能問題修復後教訓未即時內化到代理人定義，導致同類問題可能重複發生。

當修復效能相關問題（記憶體洩漏、不必要的重建、資源未清理、狀態機問題等）時，除了建立 Ticket 追蹤外，**必須同時評估是否需要更新對應代理人的開發注意事項**。

| 效能問題類型 | 更新目標代理人 | 更新內容 |
|------------|--------------|---------|
| 記憶體洩漏（集合無上限、訂閱未清理） | 對應語言的開發代理人 | 資源管理章節 |
| Widget/Component 不必要重建 | UI 開發代理人 | 重建效能意識章節 |
| 狀態機設計問題 | 對應語言的開發代理人 | 狀態保護原則 |
| goroutine/async 洩漏 | 對應語言的開發代理人 | 並行資源管理 |

**執行時機**：效能修復 Ticket 完成後（Phase 4 或 complete 時），PM 檢查對應代理人是否已有相關注意事項，沒有則補充。

---

## 第四層：Ticket 執行流程

```
[Ticket 驗證通過]
    |
    v
是「繼續任務鏈」類請求? ─是→ [強制] 並行可行性分析 → 主動建議並行
    |
    └─否→ pending? → creation_accepted?
          |           ─否→ [強制] 並行審核（acceptance-auditor + system-analyst）
          |                → 通過後設定 creation_accepted: true
          |           ─是→ claim → 階段判斷
          in_progress? → 繼續執行
          completed? → [AskUserQuestion] 後續步驟選擇
          blocked? → 升級 PM
```

**建立後審核檢查（強制）**：pending Ticket 認領前必須 `creation_accepted: true`，否則強制並行派發 acceptance-auditor + system-analyst 審核。豁免：已審核父 Ticket 的子任務。

**Wave 邊界檢查（強制）**：當用戶指定「繼續 Wx」時，**必須**只處理該 Wave 的任務，禁止跨 Wave 執行。

**Handoff 方向選擇（AskUserQuestion）**：當 handoff 有多個可能方向時，**必須**使用 AskUserQuestion 讓使用者選擇。

> **Worktree 隔離**：派發會修改檔案的代理人（parsley, fennel, thyme-python, cinnamon, pepper, mint）必須使用 `Agent(isolation: "worktree")`。詳見 parallel-dispatch.md（Worktree 隔離章節）。

> Ticket 生命週期：.claude/pm-rules/ticket-lifecycle.md
> 並行派發規則：.claude/pm-rules/parallel-dispatch.md

---

**Last Updated**: 2026-04-09
**Version**: 1.0.1 - 版本日期更新（W9-004，二元化拆分後多視角審查修正）
