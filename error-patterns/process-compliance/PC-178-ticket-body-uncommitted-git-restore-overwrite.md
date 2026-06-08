# PC-178: ticket body append-log 寫入後未 commit 被 git 還原覆蓋

## 症狀

ticket body 經 append-log 寫入後若停留於未 commit 的 working tree，被 git 還原操作（`git checkout -- <file>` / `git restore` / `git reset --hard` / `git stash`）覆蓋回 create commit 的 placeholder 版本而遺失。`ticket track query` 顯示 body 回到 placeholder；若還原連 frontmatter 一起，status 異常回 `pending`、5W1H 回「待定義」。

## 根因

ticket CLI `create` 將 ticket 落盤為 `pending` + placeholder body 並 commit；後續 `claim` / `append-log` 只修改 working tree、未 commit；任一 git 還原操作將 ticket md 還原回 create commit 版本，body 暫態隨之消失。**非 CLI bug**，是「持久化資料停留易失中間狀態」的協作時機問題。

**generic 化**：此為跨領域可重現的「易失中間狀態被覆蓋」模式，防護三原則一致——縮短易失窗 + degrade 可觀測 + 人為 fallback。具體對映：持久化資料（ticket body / buffer / cache）寫入後停留易失中間狀態（未 commit working tree / 未 flush / 未 persist），被後續操作覆蓋遺失。

## 案例

1.0.0-W1-016 body（Problem Analysis / Solution WRAP 四方案）在執行中被 git 還原覆蓋回 create commit 的 placeholder。雙重物證確認非 CLI bug：(a) create commit 狀態 = pending + placeholder 與遺失後狀態逐字吻合；(b) 真實 CLI 序列（claim → append-log → release → re-claim）marker 全程保持不丟。根因定性為 git working-tree 還原（1.0.0-W1-017 ANA）。

## 防護

防護目標是消除「ticket 執行歷史靜默遺失」——body 遺失後，後人接手不知它曾存在，基於遺失 body 的決策鏈崩塌，回溯成本高。

**主防護（auto-commit 根因解，1.0.0-W7-001）**：append-log 寫入 body 後立即以精確路徑 `git commit -- <ticket-md>`，body 即時進 commit 歷史，使 `checkout --` / `reset --hard` / `stash` 三種還原全失效（已 commit 內容還原不掉）。實作 `.claude/skills/ticket/ticket_system/lib/git_utils.py`（`_auto_commit_ticket_md`）+ `commands/track_acceptance.py`。

**補充防護（人為 fallback）**：auto-commit graceful degrade 失敗（非 git repo / index.lock 競爭 / commit 失敗）時，stderr 警告提示 body 已在 working tree、需手動 commit 持久化；手動 `Edit` ticket md（非走 append-log，不觸發 auto-commit）時，git 還原前先 commit/stash 保護（PC-019 worktree 場景的延伸）。

## 相關

- 主防護工作流（PM/agent 行為變更）：memory append-log-auto-commit-workflow
- 同源「git 操作覆蓋 ticket 變更」：PC-019-worktree-merge-state-loss（worktree merge stash drop 場景）
- 根因分析雙重物證：1.0.0-W1-017 ANA
- 補充防護的 worktree 前置：feedback_worktree_commit_before_dispatch

---

Last Updated: 2026-06-08 | Source: 1.0.0-W7-002（W1-017 ANA 方案 D 固化，W7-001 auto-commit 落地後重定位為防護演進記錄）
