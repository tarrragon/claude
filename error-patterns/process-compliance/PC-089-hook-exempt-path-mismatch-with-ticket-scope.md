---
id: PC-089
title: Hook 豁免路徑與 Ticket 寫入範圍不一致導致 agent 派發後阻塞
category: process-compliance
severity: medium
created: 2026-04-18
source_ticket: 0.18.0-W15-023
related:
  - PC-019  # worktree 派發前 commit
  - ARCH-015  # worktree vs .claude/ 路徑限制
---

# PC-089: Hook 豁免路徑與 Ticket 寫入範圍不一致

## 觸發情境

PM 派發實作 agent 前未預先驗證 ticket 的 `where.files` 是否全部落在 `branch-verify-hook` 的 `exempt_prefixes` 內。agent 在 main 分支嘗試 Write 非豁免路徑時被阻擋，回報 blocker 中斷執行，PM 需二次介入修復 hook 或切換分支策略。

## 具體案例

W15-014 E3 audit ticket `where.files` 含 `scripts/experiments/pc088_v2_audit.py`。
`branch-verify-hook.py:exempt_prefixes` 僅含 `.claude/` 和 `docs/`，未含 `scripts/`。
Agent 在 main worktree 嘗試 Write 腳本時被 hook 擋下，回報需 PM 決策（worktree / feature branch / hook exempt / 改路徑）。

## 根因

- `branch-verify-hook` 設計僅豁免**文件類**路徑（`.claude/` 規則 + `docs/` 工作產物）
- 實驗類 ticket 同時產出**報告**（docs/experiments/）和**腳本**（scripts/experiments/），但 hook 僅豁免前者
- PM 派發時未做預檢：ticket where.files ⊆ hook exempt_prefixes ∪ CLAUDE.md/README.md/...

## 防護措施

### 派發前檢查

派發實作 agent 前，對照以下兩項：

1. Ticket `where.files` 所有路徑
2. `branch-verify-hook.py` 的 `exempt_prefixes` + `exempt_exact`

任一 where.files 不在豁免內 → 選擇：
- (a) 擴充 hook exempt（需獨立 Ticket）
- (b) 改 ticket where.files 到豁免路徑（若語意允許）
- (c) 改走 worktree + feature branch 策略

### Hook 豁免擴充原則

若新增豁免路徑：該路徑必須具備「實驗/文件/設定」性質，非產品程式碼（src/）。

| 性質 | 範例路徑 | 應否豁免 |
|------|---------|---------|
| 框架規則 | `.claude/` | 是 |
| 文件產出 | `docs/` | 是 |
| 實驗腳本 | `scripts/experiments/` | 是（W15-023 已加） |
| 產品程式碼 | `src/` | 否（TDD 必經分支流程） |
| 通用工具腳本 | `scripts/` 其他子目錄 | 視情況，預設否 |

## 對照：為何不使用 worktree

W15-014 agent 以 `isolation: "worktree"` 派發，但 worktree 實際仍綁定 main 分支（未切 feature branch），故 hook 仍判定為保護分支。worktree 隔離解決 `.git/HEAD` 污染，但不自動豁免保護分支限制。

若選 feature branch 策略：agent 需先 `git checkout -b feat/...`，完成後合併；流程較長且與「實驗一次性產物」不匹配。

## 升級建議

PM Ticket 建立 hook 可在 create 階段預檢 where.files ∩ exempt_prefixes 並給出警告，落地此防護。本 PC 暫不升級為 auto-hook，由 PM 派發前手動檢查。
