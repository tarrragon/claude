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
| merge main 衝突（worktree 已建立） | `[阻擋] 合併 main 發生衝突，worktree 需要人工處理才能安全使用。` | `cd` 進 worktree 手動解衝突後精確 `git add <衝突檔>`，再 `GIT_EDITOR=true git merge --continue`（合併進行中 `bare-commit-guard-hook.py` 於 linked worktree 內同樣拒絕裸 `git commit`），或 `git merge --abort` 放棄本次合併 |

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

## merge — 以隔離索引 CAS 合併分支

```bash
/worktree merge <ticket-id>
/worktree merge --branch <分支名>                  # 如 worktree-agent-<id>，不查票狀態
/worktree merge <ticket-id> --pre-acceptance "<理由>"  # 合併前驗收：票未 completed 也合併
/worktree merge --branch <分支名> --ticket <票號>   # 預設訊息附 (<票號>)
/worktree merge --branch <分支名> --message "<訊息>" # 自訂完整合併訊息
```

| 入口 | 行為 |
|------|------|
| `--message` / `-m` | 合併 commit 訊息原文使用（含換行與 Co-Authored-By trailer）；優先於 `--ticket`；省略則用預設訊息 |
| `--ticket` | 預設訊息變為 `Merge branch '<分支>' (<票號>)`；以 `<ticket-id>` 合併時自動帶入該 ID；兩者皆無則維持 `Merge branch '<分支>'` |
| `--branch` | 以分支名指定對象，用於萃取不到 ticket ID 的代理人隔離 worktree；有 worktree 則檢查乾淨，不查票狀態；`<ticket-id>` 與 `--branch` 需擇一 |
| `--pre-acceptance` | 略過「票須 completed」；working tree 仍須乾淨；旗標與理由輸出並追加至 `.claude/logs/worktree-merge.log`；不加旗標維持原要求 |
| 落後 base | 僅提示落後 commit 數，不阻擋；無衝突由三方合併處理，有衝突由 `merge_branch_cas` 中止且 ref 不變 |

所有入口最終都經 `merge_branch_cas`，`pre_merge_check` 掛點語意不變。

前置驗證（Ticket completed、working tree 乾淨）通過後，**直接完成合併**，不再輸出 `git merge` 指令。

| 步驟 | 行為 |
|------|------|
| 計算 | `git merge-tree --write-tree` 對「當下 main 與分支」做三方合併，只寫物件庫，不碰任何 index |
| 空合併守衛 | 合併 tree 等於第一親代 tree 即中止，不寫任何 ref |
| 預檢 | 閘門進場排隊前先呼叫 `precheck_merge_conflict`（同一份試算），有文字衝突即回報並結束，不排隊；取得名額後仍重算，應對排隊期間的新衝突 |
| 衝突 | 有文字衝突即中止，列出衝突檔，HEAD 不變，不留 MERGE_HEAD |
| 提交 | `commit-tree`（親代：舊 main、分支）後，`update-ref refs/heads/main <新> <舊>` CAS |
| HEAD 被並行推進 | CAS 失敗即以新 HEAD 整段重做（重試預算與 ticket skill 的 `retry_commit_attempt` 相同：前 3 次必做，其後累計等待 5 秒內） |
| 同步共用 checkout | 僅對「index 與工作區皆等於舊 HEAD」的檔寫入 index 與工作區；其餘列為「未同步」不動；撞 index.lock 同預算重試；最後輸出三平面核對 |

檔案清單全程使用 git 的 NUL 分隔輸出，不經 shell 字詞切分。

### 合併前全套件閘門

`cmd_merge(..., skip_gate_reason=None, gate_runner=None)`：未注入 `pre_merge_check` 時預設掛上 `merge_gate.MergeGate`（範圍判準與重試規則見 SKILL.md〈合併前全套件〉）；`--skip-gate <理由>` 略過並寫日誌。`merge_branch_cas(..., max_retries=N)` 在 CAS 重試超過 N 次時中止並回報最後一次失敗原因。注意：`_run_with_retry` 第 4 次起的牆鐘預算（20 秒）對耗時數分鐘的全套件必然用盡，實際重試次數可能先被牆鐘預算截斷，兩者皆為中止且 ref 不變。

### 合併前檢查掛點（pre_merge_check）

程式入口 `merge_cas.merge_branch_cas(branch, repo=None, base="main", pre_merge_check=None, message=None)`，`cmd_merge(ticket_id, pre_merge_check=None, *, branch=None, pre_acceptance_reason=None)` 透傳。

| 項目 | 規格 |
|------|------|
| 簽名 | `(merge_commit_sha: str, target_ref: str, expected_old_sha: str, attempt: int) -> CheckResult`；`CheckResult(passed: bool, reason: str = "")` |
| 呼叫時機 | `commit-tree` 之後、`update-ref` 之前；`attempt` 從 1 起算 |
| 失敗語意 | 回傳 `passed=False` 或拋例外：不執行 `update-ref`，ref 不變，不留任何狀態，`reason`（或例外訊息）經 `[錯誤] 合併失敗：…` 印出，exit 1 |
| 預設 | `None`：不檢查，直接 `update-ref` |
| 重現待合併內容 | `merge_commit_sha` 已在物件庫但無 ref 指向，`git worktree add --detach <path> <merge_commit_sha>` 即可在隔離環境檢出（`worktree add` 需要 commit-ish，故傳 commit 而非 tree） |
| 重試成本 | CAS 重試時每次嘗試依新 HEAD 產生不同的合併 commit，**每次嘗試都以該次 commit 重新呼叫檢查**。檢查若很貴，總成本隨重試次數倍增；是否在檢查內快取、縮短或只重跑差異，由掛載檢查的一方（如全套件綠燈閘門）決定 |

## cleanup — 模組位置

行為與參數見 `SKILL.md`〈子命令詳細說明〉的 cleanup 列；本節只說明程式位置與測試替換規則。

| 項目 | 規格 |
|------|------|
| 實作 | `scripts/cleanup_command.py`：`cmd_cleanup`、三層閘門（`_cleanup_check_level1`～`3`、`_is_branch_pushed`、`_is_branch_merged_to_base`）、鎖處理、逾時移除與半刪收尾 |
| 入口分派 | `worktree_manager.main()` 的 cleanup 分支呼叫 `cleanup_command.cmd_cleanup` |
| 共用函式 | worktree 查找與 git 包裝（`_validate_and_find_worktree`、`_check_working_tree_clean`、`run_git_command` 等）留在 `worktree_manager`，`cleanup_command` 匯入使用 |
| 舊名稱取用 | `worktree_manager` 以模組層 `__getattr__` 延遲轉出 cleanup 的函式（清單 `_CLEANUP_REEXPORTS`），`from worktree_manager import <名稱>` 仍可用；不以頂層匯入轉出，避免與 `cleanup_command` 互相匯入 |
| 測試替換 | 要替換 cleanup 的函式，或 cleanup 函式查找的共用名稱，patch `cleanup_command`；patch `worktree_manager` 上的轉出名稱不影響 cleanup 行為。共用名稱同時被留在 `worktree_manager` 的函式查找時（例如 `get_worktree_list` 也被 `_validate_and_find_worktree` 使用），兩個模組都要 patch |
| 測試注入點 | `WORKTREE_REMOVE_TIMEOUT_SECONDS` 只在 `cleanup_command`，不轉出 |
