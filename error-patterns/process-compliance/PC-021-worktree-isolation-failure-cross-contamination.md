# PC-021: Worktree 隔離失效導致跨任務變更污染

## 錯誤編號
PC-021

## 類別
process-compliance

## 症狀

執行 `git status` 時發現不屬於當前 Ticket 工作範圍的檔案變更（刪除、新增、修改），例如：
- 正在執行 W3 Ticket，但 `git status` 顯示 W1 Ticket 檔案被刪除或新增
- 兩個不同 Wave 的開發工作在同一個 worktree 中交叉出現

## 根因

多個開發任務（不同 Wave 或不同 Ticket）在同一個 git worktree（主倉庫的 main 分支）上操作，未使用獨立的 worktree 或 feature branch 進行隔離。

Worktree 機制的設計目的是讓每個 Ticket 在獨立的工作目錄中開發，避免不同任務的檔案變更互相干擾。當 PM 或代理人直接在主倉庫操作而非建立 worktree 時，所有任務的變更會混在同一個工作目錄中。

## 影響

- `git status` 顯示混合多個任務的變更，難以區分
- commit 時可能意外包含不相關的變更
- 需要手動篩選檔案以避免 commit 錯誤內容
- 破壞 Ticket 變更的可追溯性（一個 commit 混合多個 Ticket 的修改）

## 解決方案

1. 每個 Ticket 開發前使用 `/worktree create <ticket-id>` 建立獨立 worktree
2. 在獨立 worktree 中完成開發後，merge 回 main
3. 若已在主倉庫操作，commit 時必須手動指定檔案（`git add <specific-files>`），避免 `git add -A`

## 防護措施

1. `branch-status-reminder` hook 已在 SessionStart 時警告在 main 分支上開發
2. 應強化 worktree 工作流：PM 派發任務時主動建議建立 worktree
3. 考慮強化 `branch-verify-hook` 在 Edit/Write 操作時阻止非 .claude/ 路徑的修改（目前已部分實作）

## 發現版本
v0.1.2

## 相關 Ticket
0.1.2-W3-001.5

## 發現日期
2026-03-23
