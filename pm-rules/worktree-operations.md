# Worktree 操作流程 SOP

本文件定義 PM 使用 worktree 隔離派發代理人時的標準操作流程。

> **來源**：PC-019 — Worktree 合併流程中 Ticket 狀態遺失。

---

## 核心原則

> **先 commit 再派發**：main 上的任何修改必須在派發 worktree agent 前 commit，防止 stash/checkout 操作導致變更丟失。

---

## Worktree 狀態檢查觸發點（強制，來源 PC-039）

> **原則**：任何決策點之前，先確認 worktree 是否乾淨。代理人產出在 worktree 分支上，不合併就不可見。

| 觸發時機 | 檢查內容 | 防護機制 |
|---------|---------|---------|
| **Agent 完成後**（最重要） | worktree 未合併 commit | agent-commit-verification-hook（自動提醒）+ PM 主動合併 |
| **ticket complete 前** | 所有 worktree 合併狀態 | worktree-merge-reminder-hook（自動提醒）+ Checkpoint 1.9 |
| **切換 Ticket 前** | 殘留 worktree | PM 主動執行 `git worktree list` |
| **handoff/session 結束前** | 所有 worktree + 未提交 | PM 主動檢查 |
| **push 前** | 確認所有 worktree 已合併 | worktree-branch-check-hook（自動提醒） |

**PM 強制動作**（每個觸發點都必須執行）：

```bash
# 1. 列出 worktree
git worktree list

# 2. 檢查未合併 commit
git log main..{branch} --oneline

# 3. 合併（如有）
git merge {branch} --no-edit

# 4. 清理
git worktree remove {path}
git branch -d {branch}
```

---

## 三階段標準流程

### 階段 1：派發前（Pre-dispatch）

| 步驟 | 動作 | 原因 |
|------|------|------|
| 1 | 完成 Ticket 狀態更新（5W1H、claim、accept-creation） | 確保 Ticket 資訊完整 |
| 2 | `git add` + `git commit` main 上的變更 | **強制**，防止 stash 丟失（PC-019） |
| 3 | 確認 `git status` 為 clean | 確保無殘留未提交變更 |
| 4 | 派發 `Agent(isolation: "worktree")` | 代理人在隔離分支工作 |

**禁止**：main 上有未提交變更時派發 worktree agent。

### 階段 2：合併時（Post-agent）

| 步驟 | 動作 | 原因 |
|------|------|------|
| 1 | 確認工作目錄：`pwd && git branch --show-current` | Agent 可能污染 shell CWD |
| 2 | 若不在 main：`git checkout main`（不要 stash） | 回到 main 分支 |
| 3 | 查看 worktree 變更：`git -C .claude/worktrees/agent-{id} status --short` | 確認產出物 |
| 4 | 用 `cp` 從 worktree 提取檔案到 main | **推薦方式**，避免 merge 衝突 |
| 5 | 在 main 上跑測試確認 | 驗證產出物在 main 正常運作 |
| 6 | `git add` + `git commit` | 提交合併後的變更 |

**提取方式選擇**：

| 方式 | 適用場景 | 風險 |
|------|---------|------|
| `cp`（推薦） | 新增檔案、覆蓋已知檔案 | 低 |
| `git merge` | 大量變更、需保留 commit 歷史 | 中（可能衝突） |
| `git cherry-pick` | 需要特定 commit | 中 |

### 階段 3：清理後（Cleanup）

| 步驟 | 動作 | 原因 |
|------|------|------|
| 1 | 確認產出物已在 main 上且測試通過 | 清理前驗證 |
| 2 | `git worktree remove .claude/worktrees/agent-{id} --force` | 移除 worktree |
| 3 | `git branch -D worktree-agent-{id}` | 刪除對應分支 |
| 4 | 確認 `git worktree list` 無殘留 | 驗證清理完成 |

**批量清理**：

```bash
# 移除所有 agent worktree
git worktree list | grep "agent-" | awk '{print $1}' | while read wt; do
  git worktree remove "$wt" --force 2>/dev/null
done

# 刪除所有 worktree 分支
git branch | grep "worktree-agent-" | xargs git branch -D 2>/dev/null
```

---

## Shell 工作目錄保護

| 問題 | 原因 | 防護 |
|------|------|------|
| Agent 完成後 CWD 在 worktree 路徑 | Agent 工具可能改變 shell 狀態 | 每次 Agent 完成後執行 `pwd && git branch --show-current` |
| `git status` 顯示錯誤分支的狀態 | CWD 在 feature 分支 | 確認在 main 後才執行 git 操作 |
| `git stash` 後 `stash drop` 丟失變更 | main 上有未提交變更 | **禁止**：先 commit 再派發（階段 1 步驟 2） |

---

## 並行 Worktree 注意事項

| 場景 | 處理方式 |
|------|---------|
| 兩個 agent 修改不同檔案 | 安全，依序 `cp` 即可 |
| 兩個 agent 修改相同檔案 | 禁止，派發前確認檔案所有權互斥 |
| Agent A 依賴 Agent B 的產出 | 序列派發，不可並行 |

---

## 檢查清單

### 派發前
- [ ] main 上 `git status` 為 clean？
- [ ] Ticket 狀態已更新且 committed？
- [ ] Agent prompt 包含 `Ticket: {id}`？

### 合併時
- [ ] `pwd` 確認在 main？
- [ ] Worktree 有產出物？
- [ ] `cp` 到 main 後測試通過？

### 清理後
- [ ] 產出物已 commit 到 main？
- [ ] Worktree 和分支已刪除？

---

## 相關文件

- .claude/error-patterns/process-compliance/PC-019-worktree-merge-state-loss.md
- .claude/error-patterns/process-compliance/PC-039-worktree-unmerged-invisible-output.md
- .claude/pm-rules/parallel-dispatch.md - 並行派發規則
- .claude/pm-rules/decision-tree.md - Checkpoint 1.9 Worktree 合併
- .claude/rules/core/bash-tool-usage-rules.md - 禁止 cd 污染

---

**Last Updated**: 2026-04-05
**Version**: 2.0.0 - 新增 Worktree 狀態檢查觸發點（PC-039, 0.17.2-W2-018）
