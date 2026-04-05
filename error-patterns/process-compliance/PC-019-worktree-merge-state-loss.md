# PC-019: Worktree 合併流程中 Ticket 狀態遺失

## 錯誤摘要

PM 在 main 分支上直接修改 Ticket 狀態（5W1H、claim、accept-creation），同時 worktree agent 在隔離分支上工作。Agent 完成後，PM 的 shell 工作目錄被污染到 feature 分支，執行 `git stash` + `git checkout main` 時，main 上的 Ticket 變更丟失（stash 被 drop）。最終需要重新執行所有 Ticket 狀態更新。

## 症狀

- `ticket track query` 顯示 Ticket 回到 `pending` 狀態
- 5W1H 欄位回到「待定義」
- `creation_accepted` 回到 `false`
- PM 需要重新執行 10+ 個 `ticket track set-*` 命令

## 根因分析

1. **主線程變更與 worktree 不同步**：PM 在 main 上修改 Ticket 檔案，worktree agent 基於 main 的舊版本工作
2. **shell 工作目錄污染**：Agent 完成後 shell CWD 可能指向 feature 分支
3. **stash 操作不安全**：PM 用 `git stash` → `git checkout main` → `git stash drop` 丟失了 main 上的未提交變更
4. **無「先 commit 再派發」規範**：PM 修改 Ticket 後未先 commit，直接派發 worktree agent

## 觸發條件

- PM 在 main 上修改 tracked 檔案（Ticket 狀態）
- 同時 worktree agent 在隔離分支上工作
- Agent 完成後 shell 被污染到其他分支
- PM 用 stash 切換分支時丟失變更

## 防護措施

1. **修改 Ticket 後立即 commit**：PM 在派發 worktree agent 前，先 commit Ticket 狀態變更
2. **Agent 派發後不切換分支**：確保 main 上的 shell 不被污染
3. **Worktree 合併標準流程需定義**：
   - 何時 commit main 上的變更
   - 如何從 worktree 提取產出物（cp vs merge）
   - 合併後清理步驟
4. **禁止 stash drop 未確認內容**：drop 前用 `git stash show` 確認

## 建議：全面分析 worktree 操作流程

本次事件暴露 worktree 分發和合併流程缺乏標準化。建議建立 ANA Ticket 全面分析：
- 派發前：main 上的 uncommitted changes 處理
- 派發中：shell 工作目錄保護
- 合併時：worktree → main 的檔案提取方式
- 清理後：worktree 和分支的清理順序

## 相關 Ticket

- 0.17.2-W2-002, 0.17.2-W2-003（首次發現）

## 發現日期

2026-04-05

---

**Last Updated**: 2026-04-05
**Version**: 1.0.0
