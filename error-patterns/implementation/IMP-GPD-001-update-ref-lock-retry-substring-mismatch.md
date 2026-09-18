---
id: IMP-GPD-001
title: 隔離索引 CAS 的鎖重試字串比對不涵蓋 update-ref 的 ref lock 錯誤
status: active
---

# IMP-GPD-001: 隔離索引 CAS 的鎖重試字串比對不涵蓋 update-ref 的 ref lock 錯誤

## 基本資訊

- **Pattern ID**: IMP-GPD-001
- **分類**: 實作 bug（implementation）
- **來源版本**: 0.1.0
- **發現日期**: 2026-09-09
- **風險等級**: 高
- **影響範圍**: `.claude/skills/ticket/ticket_system/lib/git_ops.py`（`commit_files_isolated` 隔離索引 CAS，供 `ticket track commit`、`ticket-md-auto-commit-hook.py`、`lifecycle.complete()` 共用）

---

## 問題描述

### 症狀

隔離索引 CAS（`commit_files_isolated`）在並行環境下對 `update-ref` 這一步撞上 ref lock 競爭（`refs/heads/<branch>.lock` 或 `HEAD.lock`）時，**一次都不重試**即回傳 `status: "failed"`，且已建好的 commit-tree 物件 SHA 不回傳給呼叫端（`commit_sha: None`）。執行者被迫繞出工具外，以 `git fsck --unreachable` 尋回孤兒 commit 物件並手動 `git update-ref` 完成提交——該手動路徑必然跳過 `commit_files_isolated` 內建的收尾同步（`_sync_shared_index_after_commit`，僅存在於函式內部成功分支），使共用 index 對受影響檔案停留在提交前的舊內容，最終被另一個無關的裸 commit 靜默回滾。

### 根因

`_run_git_with_lock_retry`（`git_ops.py:89-105`）的重試條件為 `while not ok and "index.lock" in err`（101 行）。此條件只匹配 git 操作 `.git/index` 檔案時的鎖錯誤文字（`Unable to create '.../index.lock': File exists`）。但 `commit_files_isolated` 的 CAS 步驟（267-269 行）呼叫的是 `git update-ref HEAD "$commit_sha" "$old_head"`，此命令競爭的是**分支 ref 鎖**，真實錯誤文字為：

```
fatal: update_ref failed for ref 'HEAD': cannot lock ref 'HEAD': Unable to create
'.../.git/refs/heads/main.lock': File exists.
```

（或 `.../.git/HEAD.lock`，視當下 HEAD 是否為 symbolic ref 展開路徑而定）。兩者皆不含子字串 `index.lock`，重試條件恆為 `False`——`update-ref` 這一步實質上從未受益於既有的重試設計，即使該步驟正是隔離索引 CAS 全流程中並行寫入者實際互相競爭的環節（read-tree/add/write-tree 操作的是每次呼叫獨立的臨時 index 檔，天然低碰撞）。

### 觸發條件

- 高並行度（多代理人同時對同一 repo 執行 `ticket track commit` / auto-commit hook / `ticket track complete`）
- 恰好撞上另一個並行 CAS 操作同時持有 `refs/heads/<branch>.lock` 或 `HEAD.lock`

### 影響

- `commit_files_isolated` 在此條件下立即失敗（實測 0.64 秒內），完全未觸發原本設計的重試（`_MAX_RETRIES=2`、`_RETRY_WAIT_SECONDS=1`）
- 已建好的 commit-tree 物件遺失於呼叫端視野之外，逼迫人工以 `git fsck --unreachable` 尋回並手動完成 CAS
- 手動完成路徑必然跳過 `_sync_shared_index_after_commit`，共用 index 對受影響檔案停留舊內容
- 後續任何精確 `git add` + 核對 + 裸 commit（規則七流程）若未察覺該過期 entry，會把舊內容一併提交，靜默回滾他票內容且 `git log` 外觀正常，無異常訊號

### 實證案例

某次六名代理人並行對 main 提交的 session 中，執行者 A 以 `ticket track commit` 提交某文件變更（commit-tree 建立時間經 `git cat-file -p` 驗證），連續遇 `HEAD.lock` 與 `refs/heads/main.lock` 競爭，經 lsof 確認無持有者後手動移除鎖檔並自行 `update-ref`（reflog 顯示 HEAD 實際移動時間與 commit-tree 建立時間相差近 10 分鐘）。約 10 分鐘後，執行者 B 依規則七完成裸 commit，沿用未同步的共用 index，回滾了執行者 A 落地的內容。`bare-commit-guard-hook.py` 的 PreToolUse 記錄顯示，執行者 B 核對當下 staged 檔案數確實只有 1 個——核對本身合法通過，過期 entry 的存在對核對步驟不可見。完整時序重建與程式碼證據見同批次分析結論落地的 spawn ticket 群組（IMP 修復票、DOC 補述票）之來源分析工作。

## 防護措施

### 已規劃修復

已建立 IMP 型 spawn ticket：擴充 `_run_git_with_lock_retry` 的重試判定以涵蓋 ref lock 錯誤文字；`update-ref` 最終失敗時於 error 訊息回報 commit-tree SHA，避免執行者需以 `git fsck` 尋回；補齊模擬 ref lock 競爭的單元測試。

已建立 DOC 型 spawn ticket：補述人工繞過 `ticket track commit` 失敗路徑時的收尾義務（必須執行隔離索引 CAS 配方步驟 10 的收尾清理），以及並行期核對與裸 commit 之間如有等待須重新核對的條文。

兩張 spawn ticket 的 ID 與現況見來源 ticket 的 `spawned_tickets` 欄位。

### 短期繞道（若尚未修復前遇到本問題）

`commit_files_isolated` 因 ref lock 競爭失敗時：

1. 優先重試同一次 `ticket track commit` 呼叫（新一輪呼叫會以當下 HEAD 為 `$OLD_HEAD` 重建 tree，不沿用舊的孤兒物件，避免基準漂移）
2. 若必須人工完成 CAS（如確認鎖檔為殘留且工具重試已用盡），完成 `update-ref` 後**必須**額外執行「規則七詳細：隔離索引 CAS 配方」步驟 10 的收尾清理（三平面比對 `git show :path` / `git show OLD_HEAD:path` / `git show HEAD:path`，過期則 `git restore --staged`），不可省略

### 跨框架性質

根源在 `.claude/skills/ticket/ticket_system/lib/git_ops.py`，為框架通用資產（非本專案專屬），已核對 framework issue 兩條 AND 判準（抽象可攜性、資產範圍）皆成立，並執行 `dedup` 查重；結果與後續處置記錄於來源 ticket 的 Solution 章節，留待 PM 決定是否對既有 open issue #55 追加 observe。

## 相關檔案

- `.claude/skills/ticket/ticket_system/lib/git_ops.py:89-105`（`_run_git_with_lock_retry`）
- `.claude/skills/ticket/ticket_system/lib/git_ops.py:267-278`（`commit_files_isolated` update-ref 分支與收尾同步呼叫點）
- `.claude/references/bash-tool-usage-details.md`「隔離索引 CAS 的時間維度要件」「規則七核對步驟的版本邊界：過期 index 快照」
- `.claude/hooks/bare-commit-guard-hook.py`（PreToolUse 核對的時序邊界，本案例的第二層放行證據）
- `IMP-046-git-index-lock-race-condition.md`（同大類問題的既有記載，本則為其在 `update-ref` 步驟的更窄子案例）
- `PC-BAL-008-shared-git-index-sweeps-parallel-agent-staged-files.md`（過期 index 快照回滾機制的既有案例庫，本則新增「CAS 失敗後人工繞出」觸發途徑）

---

**Created**: 2026-09-09
**Severity**: 高（並行環境下可重複發生，且發生時無異常訊號、需事後 diff 比對才能發現）
