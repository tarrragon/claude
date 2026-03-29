# Commit 責任邊界

> **來源**：從 parallel-dispatch.md 抽取（0.4.0-W3-020）

---

## Commit 責任分配

> **核心原則**：TDD Phase 1-3 代理人自行 commit，Phase 3b+ 由 PM 管理 commit。

| 階段 | 誰 commit | 誰 push | commit message 格式 |
|------|----------|---------|-------------------|
| Phase 1/2/3a | 代理人自行 | 禁止（PM 統一 push） | `feat({ticket-id}): Phase X 完成 - {摘要}` |
| Phase 3b | PM（收到回報後） | PM | 依 commit-as-prompt 規範 |
| Phase 4a/4b/4c | PM（收到回報後） | PM | 依 commit-as-prompt 規範 |

---

## 代理人自治 commit 規則

| 規則 | 說明 |
|------|------|
| commit 前測試通過 | 代理人必須確保相關測試通過才 commit |
| commit 後更新 Ticket | `ticket track append-log` 記錄產出物 |
| 禁止 push | push 權限保留給 PM，避免分支衝突 |
| 禁止 amend | 每次 commit 獨立，不修改歷史 |

**Hook 相容性**：commit-handoff-hook 在 subagent 中觸發時，因 subagent 禁止使用 AskUserQuestion，Handoff 提醒自然跳過——這是預期行為，Phase 1-3 的 commit 不需要 PM 介入 Handoff 決策。

---

**Last Updated**: 2026-03-29
**Version**: 1.0.0 - 從 parallel-dispatch.md 抽取（0.4.0-W3-020）
