---
name: worktree
description: "Use this skill for managing git worktrees for Ticket-based development. Triggers include: creating a worktree for a new ticket, checking worktree status, viewing all worktrees, or any mention of /worktree, worktree management, feature branches, or setting up development environment."
argument-hint: "<subcommand> [args]"
allowed-tools: Bash, Read, Write, Edit
---

# Worktree Management SKILL

統一 Git Worktree 管理工具 — 簡化並行開發流程。

## 核心功能

管理 git worktree，自動從 Ticket ID 推導分支名和路徑。支援多 Ticket 並行開發時的環境隔離。

---

## 快速開始

### 建立 Worktree

```bash
/worktree create 0.1.1-W9-002.1
```

自動建立：
- 分支：`feat/0.1.1-W9-002.1`
- Worktree：`../ccsession-0.1.1-W9-002.1`

建立完成後輸出 `cd` 指令，一鍵切換工作環境。

### 查看 Worktree 狀態

```bash
# 查看所有 worktree
/worktree status

# 查看特定 Ticket 的 worktree
/worktree status 0.1.1-W9-002.1
```

顯示：
- 路徑和分支
- 相對於 main 的 commit 領先/落後情況
- 未 commit 的變更數

---

## 子命令詳細說明

### create — 建立 Worktree

```bash
/worktree create <ticket-id> [--base <branch>] [--dry-run]
```

#### 參數

| 參數 | 類型 | 必填 | 說明 | 範例 |
|------|------|------|------|------|
| `ticket-id` | positional | 是 | Ticket ID | `0.1.1-W9-002.1` |
| `--base` | option | 否 | 基礎分支（預設 main） | `--base develop` |
| `--dry-run` | flag | 否 | 只顯示操作，不執行 | `--dry-run` |

#### 推導規則

Ticket ID 自動推導為：

| 組件 | 規則 | 範例 |
|------|------|------|
| 分支名稱 | `feat/{ticket-id}` | `feat/0.1.1-W9-002.1` |
| Worktree 路徑 | `{parent-dir}/{project-name}-{ticket-id}` | `../ccsession-0.1.1-W9-002.1` |

#### 成功範例

```bash
$ /worktree create 0.1.1-W9-002.1

正在建立 worktree...
  Ticket: 0.1.1-W9-002.1
  分支:   feat/0.1.1-W9-002.1
  基礎:   main
  路徑:   /path/to/project-0.1.1-W9-002.1

建立成功。

下一步：
  cd /path/to/project-0.1.1-W9-002.1
```

#### 錯誤情境

| 情境 | 錯誤訊息 | 建議操作 |
|------|---------|---------|
| Ticket ID 格式無效 | `無效的 Ticket ID 格式："my-feature"` | 格式應為 X.X.X-WN-NNN（如：0.1.1-W9-002.1） |
| 分支已存在 | `分支已存在：feat/0.1.1-W9-002.1` | `git branch -d feat/0.1.1-W9-002.1` |
| Worktree 路徑已存在 | `目錄已存在：../ccsession-0.1.1-W9-002.1` | 使用其他 ticket-id 或刪除目錄 |
| base 分支不存在 | `基礎分支不存在：develop` | 確認分支名稱，或省略 --base 使用預設 |

### status — 查看 Worktree 狀態

```bash
/worktree status [<ticket-id>]
```

#### 參數

| 參數 | 類型 | 必填 | 說明 | 範例 |
|------|------|------|------|------|
| `ticket-id` | positional | 否 | 指定查詢特定 Ticket | `0.1.1-W9-002.1` |

#### 成功範例（無參數，顯示全部）

```bash
$ /worktree status

Worktree 狀態（共 3 個）
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

[主倉庫]
  路徑：   /path/to/project
  分支：   main
  變更：   0 個未 commit

[0.1.1-W9-002.1]
  路徑：   /path/to/project-0.1.1-W9-002.1
  分支：   feat/0.1.1-W9-002.1
  領先：   +3 commits ahead of main
  落後：   -0 commits behind main
  變更：   2 個未 commit

[0.1.1-W9-002.2]
  路徑：   /path/to/project-0.1.1-W9-002.2
  分支：   feat/0.1.1-W9-002.2
  領先：   +1 commits ahead of main
  落後：   -1 commits behind main
  變更：   0 個未 commit
```

#### 成功範例（指定 ticket-id）

```bash
$ /worktree status 0.1.1-W9-002.1

[0.1.1-W9-002.1]
  路徑：   /path/to/project-0.1.1-W9-002.1
  分支：   feat/0.1.1-W9-002.1
  領先：   +3 commits ahead of main
  落後：   -0 commits behind main
  變更：   2 個未 commit
```

#### 無 Worktree 範例

```bash
$ /worktree status

目前沒有任何 worktree（除主倉庫外）。

建立新的 worktree：
  /worktree create <ticket-id>
```

---

## 使用場景

### 場景 1：新 Ticket 開發

```bash
# 1. 收到 Ticket 0.1.1-W9-002.1
# 2. 建立 worktree（自動推導名稱）
/worktree create 0.1.1-W9-002.1

# 3. 一鍵切換環境
cd /path/to/project-0.1.1-W9-002.1

# 4. 開始開發...
```

### 場景 2：多 Ticket 並行開發

```bash
# 建立多個 worktree（隔離環境）
/worktree create 0.1.1-W9-002.1
/worktree create 0.1.1-W9-002.2
/worktree create 0.1.1-W9-002.3

# 查看整體狀態
/worktree status

# 查看特定 Ticket 進度
/worktree status 0.1.1-W9-002.1
```

### 場景 3：檢查進度

```bash
# 在任何 worktree 中執行，檢查全局狀態
/worktree status

# 確認該 Ticket 有多少未提交變更
/worktree status 0.1.1-W9-002.1
```

---

## 與 Hook 系統的整合

### branch-verify-hook

在保護分支（main）上編輯時：
- **允許**：`.claude/`、`docs/` 路徑的編輯（規則更新、文檔維護）
- **阻止**：程式碼路徑編輯（如 `ui/lib/main.dart`）
- **建議**：使用 `/worktree create <ticket-id>` 建立隔離環境

### branch-status-reminder

Session 啟動時：
- **正確環境**（在 worktree + allowed 分支）→ 靜默
- **異常環境**（主倉庫保護分支）→ 警告 + 建議使用 `/worktree create`

---

## 常見問題

### Q: Worktree 與分支的對應關係是什麼？

**A**: 一個 worktree = 一個獨立的分支 + 隔離的檔案系統。

- 建立 worktree 時同時建立分支
- 多個 worktree 間檔案變更隔離
- 每個 worktree 有獨立的 git working directory

### Q: 能否指定 base 分支？

**A**: 支援。使用 `--base` 參數：

```bash
/worktree create 0.1.1-W9-002.1 --base develop
```

### Q: Dry-run 模式有什麼用？

**A**: 檢查將要執行的 git 命令，不實際建立分支和 worktree。適合驗證操作是否正確。

```bash
/worktree create 0.1.1-W9-002.1 --dry-run
```

### Q: 如何刪除 Worktree？

**A**: 使用 git 命令（本 SKILL 暫不支援刪除）：

```bash
# 刪除 worktree（保留分支）
git worktree remove ../ccsession-0.1.1-W9-002.1

# 刪除分支
git branch -d feat/0.1.1-W9-002.1
```

---

## 參考資料

- Phase 1 功能規格：`docs/work-logs/v0.1.1/tickets/0.1.1-W9-002.4-phase1-design.md`
- 設計決策：`docs/work-logs/v0.1.1/tickets/0.1.1-W9-002.6-phase3a-strategy.md`
- Git Worktree 官方文檔：https://git-scm.com/docs/git-worktree

---

**Version**: 1.0.0
**Last Updated**: 2026-03-18
**Status**: MVP (create + status 子命令)
