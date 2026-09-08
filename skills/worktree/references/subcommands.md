# 子命令詳細說明

> 何時讀：需要 `/worktree create` 或 `/worktree status` 的完整參數表、推導規則、成功範例或錯誤情境時。`SKILL.md`〈快速開始〉只給最小指令示範，本檔補齊 CLI 參考細節。
>
> 同目錄：cc 自動建立 agent worktree 的行為說明在 `agent-isolation-worktree.md`；核心功能、快速開始、使用場景、Hook 整合、常見問題留在 `SKILL.md`。
>
> 溯源：自 `SKILL.md` 的〈子命令詳細說明〉節搬移（v1.4.0）。移出理由是本節屬 CLI 參考手冊性質，只有需要查特定參數或錯誤訊息的讀者才需要，一般讀者用〈快速開始〉的最小範例即可上手。

## create — 建立 Worktree

```bash
/worktree create <ticket-id> [--base <branch>] [--dry-run]
```

### 參數

| 參數 | 類型 | 必填 | 說明 | 範例 |
|------|------|------|------|------|
| `ticket-id` | positional | 是 | Ticket ID | `1.0.0-W9-002.1` <!-- rule8-exempt: relocation:自 .claude/skills/worktree/SKILL.md 逐字位置搬移 --> |
| `--base` | option | 否 | 基礎分支（預設 main） | `--base develop` |
| `--dry-run` | flag | 否 | 只顯示操作，不執行 | `--dry-run` |

### 推導規則

Ticket ID 自動推導為：

| 組件 | 規則 | 範例 |
|------|------|------|
| 分支名稱 | `feat/{ticket-id}` | `feat/1.0.0-W9-002.1` <!-- rule8-exempt: relocation:自 .claude/skills/worktree/SKILL.md 逐字位置搬移 --> |
| Worktree 路徑 | `{parent-dir}/{project-name}-{ticket-id}` | `../ccsession-1.0.0-W9-002.1` <!-- rule8-exempt: relocation:自 .claude/skills/worktree/SKILL.md 逐字位置搬移 --> |

### 成功範例

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
正在同步最新 main...
main 無新變更，worktree 已是最新。
```

> 建立完成後會確定性執行一次 `git merge main`（issue #77 決議 A）：共享
> `.git` 下 local main 為全機單一事實來源，此步驟消除 base 解析與 worktree
> 可用之間、其他 worktree 併行推進 main 的競態視窗。無新變更時為 no-op；
> 有衝突時會停下並輸出後果與下一步（不自動解），見下方〈錯誤情境〉表最後一列。

### 錯誤情境

| 情境 | 錯誤訊息 | 建議操作 |
|------|---------|---------|
| Ticket ID 格式無效 | `無效的 Ticket ID 格式："my-feature"` | 格式應為 X.X.X-WN-NNN（如：1.0.0-W9-002.1） <!-- rule8-exempt: relocation:自 .claude/skills/worktree/SKILL.md 逐字位置搬移 --> |
| 分支已存在 | `分支已存在：feat/1.0.0-W9-002.1` | `git branch -d feat/1.0.0-W9-002.1` <!-- rule8-exempt: relocation:自 .claude/skills/worktree/SKILL.md 逐字位置搬移 --> |
| Worktree 路徑已存在 | `目錄已存在：../ccsession-1.0.0-W9-002.1` | 使用其他 ticket-id 或刪除目錄 <!-- rule8-exempt: relocation:自 .claude/skills/worktree/SKILL.md 逐字位置搬移 --> |
| base 分支不存在 | `基礎分支不存在：develop` | 確認分支名稱，或省略 --base 使用預設 |
| merge main 衝突（worktree 已建立） | `[阻擋] 合併 main 發生衝突，worktree 需要人工處理才能安全使用。` | `cd` 進 worktree 手動解衝突後 `git add`+`git commit`，或 `git merge --abort` 放棄本次合併 |

## status — 查看 Worktree 狀態

```bash
/worktree status [<ticket-id>]
```

### 參數

| 參數 | 類型 | 必填 | 說明 | 範例 |
|------|------|------|------|------|
| `ticket-id` | positional | 否 | 指定查詢特定 Ticket | `1.0.0-W9-002.1` <!-- rule8-exempt: relocation:自 .claude/skills/worktree/SKILL.md 逐字位置搬移 --> |

### 成功範例（無參數，顯示全部）

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

### 成功範例（指定 ticket-id）

```bash
$ /worktree status 1.0.0-W9-002.1

[1.0.0-W9-002.1]
  路徑：   /path/to/project-1.0.0-W9-002.1
  分支：   feat/1.0.0-W9-002.1
  領先：   +3 commits ahead of main
  落後：   -0 commits behind main
  變更：   2 個未 commit
```

### 無 Worktree 範例

```bash
$ /worktree status

目前沒有任何 worktree（除主倉庫外）。

建立新的 worktree：
  /worktree create <ticket-id>
```
