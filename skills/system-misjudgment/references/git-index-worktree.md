# git index／worktree／工作區

## GW-1 `index.lock` 錯誤，被讀成 git 損壞或串接違規

| 欄位 | 內容 |
|------|------|
| 症狀 | `fatal: Unable to create '.git/index.lock': File exists` |
| 常見誤判 | 立即 `rm -f .git/index.lock`，或判定是自己串接了 git 寫入 |
| 實際機制 | hook 的 `git status` 或並行 session 的 git 操作 refresh index 時會短暫建立鎖，與你的操作競爭；唯讀命令也會觸發 |
| 檢查方法 | 先重試一次；反覆失敗時 `ls -la .git/index.lock` 看建立時間，`ps -axo pid,etime,command \| grep "[g]it "` 看是否有 git 程序仍在跑 |
| 正向對照 | 鎖檔存在期間，`ps` 能找到持鎖的 git 程序；找不到且鎖檔建立已久，才是殘留 |
| 判讀標準 | 有活著的 git 程序 → 等待重試；無程序且鎖檔超過約 10 秒 → 殘留，才清除 |
| 來源 | `IMP-046` |

## GW-2 合併報 `Unable to write index`，被讀成合併已部分完成

| 欄位 | 內容 |
|------|------|
| 症狀 | merge 報 `Unable to write index. Automatic merge failed`，`git status` 顯示 "All conflicts fixed but you are still merging" 並有 unstaged 變更 |
| 常見誤判 | 合併已經大致完成，補一個 commit 即可 |
| 實際機制 | 合併解析寫到了 working tree，index 不含結果；此時 commit 產生的 merge commit 等同採用 main 版本，worktree 的變更被丟棄 |
| 檢查方法 | `git -C <repo> rev-parse -q --verify MERGE_HEAD`（有輸出即合併進行中）；`git -C <repo> diff --cached --stat` 看 index 是否真的含合併結果 |
| 正向對照 | 正常完成的合併，merge commit 對第二 parent 的 `git show --stat` 應顯示該分支的變更檔案 |
| 判讀標準 | index 為空而 working tree 有變更 → 狀態不一致，停手；不直接 commit、不直接重跑合併，處置見來源 |
| 來源 | `PC-169`；`bash-tool-usage-rules` 規則七 |

## GW-3 `git add` 後 commit，吸入他人未 stage 或過期的內容

| 欄位 | 內容 |
|------|------|
| 症狀 | commit 內含非自己改的檔案或 hunk，或檔案內容被回滾到舊版 |
| 常見誤判 | commit 範圍就是自己 add 的那幾個檔 |
| 實際機制 | 多 session 共用 index；`git add` 的最小單位是整個檔案；HEAD 在 add 之後被他方推進時，index entry 相對新 HEAD 已過期，檔名核對看不出來 |
| 檢查方法 | commit 前 `git diff --cached --name-only` 核對檔名；對共用檔再比對 `git show :<path>` 與 `git show HEAD:<path>` |
| 正向對照 | 對自己剛改的檔，`git diff --cached <path>` 的內容必須恰是自己的改動 |
| 判讀標準 | 檔名只有目標檔且 cached 內容只含自己的 hunk 才 commit；過期則 `git restore --staged <path>` 後重新 add |
| 來源 | `bash-tool-usage-rules` 規則七；`PC-BAL-008` |

## GW-4 worktree 內看到的狀態，被讀成主 checkout 的狀態

| 欄位 | 內容 |
|------|------|
| 症狀 | 在 worktree 內查到檔案、票或設定與預期不同 |
| 常見誤判 | 專案狀態本身有誤 |
| 實際機制 | worktree 是獨立的 working tree，與主 checkout 分屬不同分支；票務 CLI 的寫入作用於主倉庫，檔案編輯作用於 worktree |
| 檢查方法 | `git -C <path> rev-parse --show-toplevel` 與 `git -C <path> branch --show-current` 確認自己站在哪個 checkout 與分支 |
| 正向對照 | 在主 checkout 與 worktree 各查一次同一檔案的 `git log -1 --oneline -- <path>`，兩者差異即分支差異 |
| 判讀標準 | 先確認 toplevel 與分支，再判讀內容差異 |
| 來源 | `PC-166`（工作區觀測屬瞬時，持久結論須以 git 歷史交叉驗證） |

## GW-5 隔離派發 worktree 的鎖 pid，被讀成代理人的 pid

| 欄位 | 內容 |
|------|------|
| 症狀 | `git worktree list --porcelain` 顯示 `locked claude agent ... (pid N)`，pid N 存活 |
| 常見誤判 | pid N 是代理人本身：pid 存活就代表代理人還在跑，pid 是自己的祖先就代表代理人已交回、可以解鎖 |
| 實際機制 | Agent isolation 的代理人在派發方 session 的行程內執行，鎖記錄的是派發方 session 的 pid；代理人執行中與已交回，鎖的 pid 相同，只看 pid 無法區分兩者 |
| 檢查方法 | 改看分支交回狀態：`git rev-parse refs/heads/<branch>` 與 `git reflog show --format=%H refs/heads/<branch> \| tail -1`（建立點）比對，再 `git merge-base --is-ancestor <branch> main` |
| 正向對照 | 剛派發、尚無提交的分支：鎖 pid 同為派發方 session，tip 等於建立點，必須判為未交回 |
| 判讀標準 | tip 不等於建立點且已併入 main → 已交回；其餘（含任何 git 失敗）→ 視為代理人可能仍在執行，不解鎖 |
| 來源 | 實測：worktree skill `tests/test_worktree_cleanup.py` 的 `TestWorktreeLock`：祖先持有但未交回的兩個測試，在拿掉交回條件後轉紅 |
