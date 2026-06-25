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

## Agent isolation worktree（cc 自動建 worktree-agent-*）

本章節說明 Claude Code runtime 自動建立的 agent worktree（與本 SKILL 的人工 `/worktree create` 為不同來源），重點在殭屍累積的成因與專案 GC 對策。

### 機制

Claude Code 的 Agent tool 設定 `isolation: "worktree"` 派發 subagent 時，cc runtime 會自動執行下列動作：

- 在 `.claude/worktrees/agent-XXXXXXXX` 建立隔離 worktree（XXXXXXXX 為隨機 hash）
- 對應分支命名為 `worktree-agent-XXXXXXXX`
- 同時對該 worktree 加 git lock，lock reason 內含 cc CLI process 的 PID，目的是阻止 git 自動 GC 在 agent 執行期間誤清

**Why**：worktree 隔離讓 subagent 的檔案改動與主 repo 解耦，避免並行派發時互相覆蓋；lock + PID 是 cc 對 git GC 的防護，確保長時間 agent 執行不被 `git worktree prune` 中斷。

### Base ref 與隔離邊界（W3-007 / W3-008）

| 議題 | 事實 | 對策 |
|------|------|------|
| worktree base 取自哪裡 | cc runtime 以 `origin/main`（remote-tracking ref）為 base，**非** local main HEAD。local main 領先 origin/main 時 worktree 建在 stale 基底（W3-007 實證） | 派發前先 `git push origin main`；`worktree-commit-before-dispatch-hook.py` 在 origin/main 落後時 stderr 警告 |
| daemon-rooted 寫入工具洩漏 | dart MCP（dart fix / dart format）daemon 的 analysis root 在 session 啟動時綁定主 repo，worktree 派發只改 shell cwd，無法切換 daemon root，寫入會洩漏到主 repo（W3-008 根因 2） | worktree 實作 agent **禁用 dart MCP 寫入工具，改用 Bash `dart fix` / `dart format`（尊重 agent cwd）或 Edit** |
| ticket CLI auto-commit 洩漏 | `paths.py:get_project_root()` 原優先讀 `CLAUDE_PROJECT_DIR`（恆指向主 repo），使 ticket md 寫入與 auto-commit 落在主 repo（W3-008 根因 1） | 已修：`get_project_root()` 加 worktree 感知，git root != CLAUDE_PROJECT_DIR 時優先用 git root |

**Why**：worktree 隔離只改變 agent 的 shell cwd，對「session 啟動時靜態綁定主 repo 根目錄」的寫入工具（dart MCP daemon、CLAUDE_PROJECT_DIR-rooted ticket CLI）不生效，這類工具的寫入會繞過隔離邊界洩漏到主 repo。

### 殭屍問題

cc runtime 在 agent 結束或 process 異常死亡時**不會自動 remove** agent worktree。後果：

- 殘留目錄不會自動消失（cc 只 unlock，不 remove，見下方 lock 行為說明）
- `.claude/worktrees/` 下殘留 worktree 目錄，累積佔用磁碟空間
- `git worktree list` 與 statusline 顯示大量無用 entries，干擾人工判讀

**Lock 行為（CC v2.1.157 起的變化）**：

| agent 結束方式 | lock 狀態 | 清理路徑 |
|---------------|----------|---------|
| 正常結束（v2.1.157+） | 自動 unlock | 可直接 `git worktree remove` / `git worktree prune`，免 unlock 前置 |
| process 異常死亡 | 可能殘留「殭屍 lock」（git 看 lock 不看 PID） | 仍需 `git worktree unlock` 前置（見手動清理指令第二段） |

**Why**：v2.1.157 起 cc 在 agent 正常結束時主動 unlock worktree（release note：「Worktrees managed by Claude are now left unlocked when the agent finishes」），使 `git worktree remove`/`prune` 能直接清理；但異常死亡（process 被 kill / crash）來不及 unlock，仍會殘留 lock，故 unlock 前置步驟對該情境保留。

**Consequence**：未清理的殭屍 worktree 會無上限累積，每次 cc session 派發 isolation:worktree subagent 都新增一個，數天內可達數十個，污染 git 視圖並佔用 GB 級空間。

**Action**：依賴下方「專案對策」自動 GC，或在察覺累積時執行「手動清理指令」。

### 專案對策（W17-119.1 SessionStart hook GC）

本專案在 `.claude/hooks/worktree-zombie-cleanup-hook.py` 實作 SessionStart 觸發的自動 GC，邏輯如下：

| 步驟 | 動作 |
|------|------|
| 1 | 列舉 `.claude/worktrees/agent-*` 下所有 worktree |
| 2 | 解析每個 worktree 的 lock reason，提取 PID |
| 3 | 對 PID 執行死活檢測（`ps -p <pid>`） |
| 4 | PID 已死 → `git worktree unlock` + `git worktree remove --force` |

**安全防護**：

- worktree 內 dirty 檔案數 != 0 時僅輸出警告，不自動清，避免誤刪未保存改動
- 排除建立時間 < 30 分鐘的 worktree，避免清掉剛啟動還沒來得及註冊的 agent
- 透過環境變數開關，可在偵錯時暫時關閉

**Why**：SessionStart 是 cc session 入口，每次新 session 都做一次清理可保證殭屍上限不超過上一 session 累積量。

### 手動清理指令

當自動 GC 失效或要主動清理時，使用以下指令：

```bash
# 列出殭屍（PID 已死的 agent worktree lock）
git worktree list --porcelain | grep "^locked" | grep -oE "pid [0-9]+" | awk '{print $2}' | while read p; do
  ps -p $p > /dev/null 2>&1 || echo "$p dead"
done

# 路徑 1（v2.1.157+ 首選）：清理已 unlock 的殘留（正常結束的 agent worktree）
# agent 正常結束已自動 unlock，prune 可直接回收，無需 unlock 前置
git worktree prune

# 路徑 2（異常死亡殘留 lock 時）：強制清所有 agent worktree（謹慎使用：不檢查 dirty）
git worktree list --porcelain | grep "^worktree .*\.claude/worktrees/agent-" | awk '{print $2}' | while read wt; do
  git worktree unlock "$wt" 2>/dev/null
  git worktree remove --force "$wt"
done
```

**Action**：第一段指令僅列舉，可安全執行確認殭屍數量；**路徑 1（`git worktree prune`）為 v2.1.157+ 首選**，清理正常結束（已 unlock）的殘留，安全且免 unlock 前置；路徑 2 為強制清理（含 unlock），用於異常死亡殘留 lock 的情境，執行前請先用 `git worktree list` 人工確認沒有正在進行中的 agent。

> **絆腳索**：若 `git worktree prune` 實測仍因 lock 無法清理某 worktree，表示該 worktree 屬異常死亡殘留 lock，改走路徑 2（unlock + remove --force）。

### 與人工 /worktree create 的區別

兩者表面都是 git worktree，但來源、生命週期、清理機制完全不同。混淆會導致誤清正在工作的 worktree。

| 維度 | cc Agent isolation:worktree | 人工 /worktree create |
|------|----------------------------|----------------------|
| 觸發者 | cc runtime（Agent tool 自動） | 使用者（本 SKILL） |
| 路徑 | `.claude/worktrees/agent-XXXXXXXX` | `../ccsession-<ticket-id>` |
| 分支命名 | `worktree-agent-XXXXXXXX` | `feat/<ticket-id>` |
| Lock | 自動加 lock（含 PID） | 不加 lock |
| 預期生命週期 | 單次 agent 執行（分鐘級） | 整個 ticket 開發（小時至天級） |
| 清理機制 | cc 不清，依 W17-119.1 hook GC | 使用者手動 `git worktree remove` |
| 殭屍風險 | 高（無自動清） | 低（使用者主動管理） |

**Action**：判斷某個 worktree 屬哪一類，看路徑前綴即可（`.claude/worktrees/agent-` vs `../ccsession-`）；自動 GC hook 僅處理前者，後者請使用本 SKILL 的人工流程管理。

### EnterWorktree mid-session 切換（CC v2.1.157）

CC v2.1.157 起 `EnterWorktree` 工具支援**在 session 中途切換** Claude-managed worktree（不必重啟 session），前一個 worktree 的工作狀態保留。

**Why**：可在同一 session 於多個工作目錄間切換（例如特性開發中途切到緊急 bugfix worktree），免去重啟成本。

**Consequence（查核必要性反而上升）**：mid-session 切換使 cwd 落點更易在無感知下改變。若不確認當前所在 worktree 就 commit / merge，變更可能落到非預期分支（與既有「PM cwd 被 runtime 自動切進 agent worktree」風險同源）。

**Action**：

| 時機 | 強制查核 |
|------|---------|
| 派發 isolation:worktree agent 後 | `git branch --show-current` + `pwd` 確認 cwd 落點 |
| 接收 agent task-notification 後 | 同上，確認 commit/merge 目標分支 |
| 主動 EnterWorktree 切換後 | 同上，切換完成立即確認新 worktree 身份 |

切換後 commit/merge 前未查核 → 變更落點不可信，須先 `git branch --show-current` + `pwd` 對齊預期再操作。

---

## 快速開始

### 建立 Worktree

```bash
/worktree create 1.0.0-W9-002.1
```

自動建立：
- 分支：`feat/1.0.0-W9-002.1`
- Worktree：`../ccsession-1.0.0-W9-002.1`

建立完成後輸出 `cd` 指令，一鍵切換工作環境。

### 查看 Worktree 狀態

```bash
# 查看所有 worktree
/worktree status

# 查看特定 Ticket 的 worktree
/worktree status 1.0.0-W9-002.1
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
| `ticket-id` | positional | 是 | Ticket ID | `1.0.0-W9-002.1` |
| `--base` | option | 否 | 基礎分支（預設 main） | `--base develop` |
| `--dry-run` | flag | 否 | 只顯示操作，不執行 | `--dry-run` |

#### 推導規則

Ticket ID 自動推導為：

| 組件 | 規則 | 範例 |
|------|------|------|
| 分支名稱 | `feat/{ticket-id}` | `feat/1.0.0-W9-002.1` |
| Worktree 路徑 | `{parent-dir}/{project-name}-{ticket-id}` | `../ccsession-1.0.0-W9-002.1` |

#### 成功範例

```bash
$ /worktree create 1.0.0-W9-002.1

正在建立 worktree...
  Ticket: 1.0.0-W9-002.1
  分支:   feat/1.0.0-W9-002.1
  基礎:   main
  路徑:   /path/to/project-1.0.0-W9-002.1

建立成功。

下一步：
  cd /path/to/project-1.0.0-W9-002.1
```

#### 錯誤情境

| 情境 | 錯誤訊息 | 建議操作 |
|------|---------|---------|
| Ticket ID 格式無效 | `無效的 Ticket ID 格式："my-feature"` | 格式應為 X.X.X-WN-NNN（如：1.0.0-W9-002.1） |
| 分支已存在 | `分支已存在：feat/1.0.0-W9-002.1` | `git branch -d feat/1.0.0-W9-002.1` |
| Worktree 路徑已存在 | `目錄已存在：../ccsession-1.0.0-W9-002.1` | 使用其他 ticket-id 或刪除目錄 |
| base 分支不存在 | `基礎分支不存在：develop` | 確認分支名稱，或省略 --base 使用預設 |

### status — 查看 Worktree 狀態

```bash
/worktree status [<ticket-id>]
```

#### 參數

| 參數 | 類型 | 必填 | 說明 | 範例 |
|------|------|------|------|------|
| `ticket-id` | positional | 否 | 指定查詢特定 Ticket | `1.0.0-W9-002.1` |

#### 成功範例（無參數，顯示全部）

```bash
$ /worktree status

Worktree 狀態（共 3 個）
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

[主倉庫]
  路徑：   /path/to/project
  分支：   main
  變更：   0 個未 commit

[1.0.0-W9-002.1]
  路徑：   /path/to/project-1.0.0-W9-002.1
  分支：   feat/1.0.0-W9-002.1
  領先：   +3 commits ahead of main
  落後：   -0 commits behind main
  變更：   2 個未 commit

[1.0.0-W9-002.2]
  路徑：   /path/to/project-1.0.0-W9-002.2
  分支：   feat/1.0.0-W9-002.2
  領先：   +1 commits ahead of main
  落後：   -1 commits behind main
  變更：   0 個未 commit
```

#### 成功範例（指定 ticket-id）

```bash
$ /worktree status 1.0.0-W9-002.1

[1.0.0-W9-002.1]
  路徑：   /path/to/project-1.0.0-W9-002.1
  分支：   feat/1.0.0-W9-002.1
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
# 1. 收到 Ticket 1.0.0-W9-002.1
# 2. 建立 worktree（自動推導名稱）
/worktree create 1.0.0-W9-002.1

# 3. 一鍵切換環境
cd /path/to/project-1.0.0-W9-002.1

# 4. 開始開發...
```

### 場景 2：多 Ticket 並行開發

```bash
# 建立多個 worktree（隔離環境）
/worktree create 1.0.0-W9-002.1
/worktree create 1.0.0-W9-002.2
/worktree create 1.0.0-W9-002.3

# 查看整體狀態
/worktree status

# 查看特定 Ticket 進度
/worktree status 1.0.0-W9-002.1
```

### 場景 3：檢查進度

```bash
# 在任何 worktree 中執行，檢查全局狀態
/worktree status

# 確認該 Ticket 有多少未提交變更
/worktree status 1.0.0-W9-002.1
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
/worktree create 1.0.0-W9-002.1 --base develop
```

### Q: Dry-run 模式有什麼用？

**A**: 檢查將要執行的 git 命令，不實際建立分支和 worktree。適合驗證操作是否正確。

```bash
/worktree create 1.0.0-W9-002.1 --dry-run
```

### Q: 如何刪除 Worktree？

**A**: 使用 git 命令（本 SKILL 暫不支援刪除）：

```bash
# 刪除 worktree（保留分支）
git worktree remove ../ccsession-1.0.0-W9-002.1

# 刪除分支
git branch -d feat/1.0.0-W9-002.1
```

---

## 參考資料

- Git Worktree 官方文檔：https://git-scm.com/docs/git-worktree

---

**Version**: 1.0.0
**Last Updated**: 2026-03-18
**Status**: MVP (create + status 子命令)

---

## 修改 source 後無需重新安裝（shim 化）

> **重要**：本 skill 已改用 cwd-resolving shim（ARCH-APP-002 / framework issue #12），不再走 `uv tool install`。shim 每次執行都 `uv run --directory .claude/skills/worktree` 當前專案源碼，修改 source 後改動即時生效，無 stale installed 問題（取代舊 `uv-tool-staleness-check-hook` 機制）。

**檢查 / 安裝指令**：

```bash
# 安裝 / 更新 shim（一次安裝 ticket / doc / worktree）
python3 .claude/scripts/install-skill-clis.py

# 檢查是否已 shim 化（exit 0/1）
python3 .claude/scripts/install-skill-clis.py --check
```
