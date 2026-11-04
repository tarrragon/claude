# 工具輸出與 AI 自身記錄

## TO-1 工具呼叫後同訊息續寫預期結果

| 欄位 | 內容 |
|------|------|
| 症狀 | 回報了從未真實返回的 commit、mutation 成功、grep 命中 |
| 常見誤判 | 該操作已成功，自己看過結果 |
| 實際機制 | 工具結果注入前，模型以預期分布填補出看似真實的 result，之後與真實 result 在 token 層無法區分 |
| 檢查方法 | 用固定值命令獨立查證：`git rev-parse HEAD`、`ls <path>`、`grep -c <pattern> <file>`、`git status --porcelain`；輸出可疑時同命令重發，兩次逐字一致才採信 |
| 正向對照 | 對已知存在的檔案跑 `ls`，必須看到它；對已知不存在的跑一次，必須看到 not found |
| 判讀標準 | 以固定值輸出為準，不以記憶或預期為準；工具 result 帶 code fence、中文旁白或 `System:` 訊息 → 視為自己生成的雜訊 |
| 來源 | `PC-166`；`tool-output-trust-rules` 規則 1-3 |

## TO-2 對話記憶中的「我做過」，被讀成世界已改變

| 欄位 | 內容 |
|------|------|
| 症狀 | 記得 commit、complete、spawn 過，但 `git status` 或票面找不到；或相反，世界有痕跡但無記憶 |
| 常見誤判 | 前者當成已完成，後者當成污染而 revert |
| 實際機制 | 記錄平面（transcript）與世界平面（filesystem、git、ticket）會雙向漂移；同 prompt 的異執行體可能留下真實副作用 |
| 檢查方法 | `git log --oneline -1`、`git cat-file -t <hash>`、`ticket track query <id>` 讀真實狀態 |
| 正向對照 | 對剛確定做過的一個操作查一次，確認查證命令能看到它 |
| 判讀標準 | 重大狀態（claim、complete、commit、spawn）一律以世界平面為準 |
| 來源 | `PC-166`；`tool-output-trust-rules` 規則 5 |

## TO-3 工作區觀測，被當成持久結論

| 欄位 | 內容 |
|------|------|
| 症狀 | 依 `git status` 或檔案內容宣告「已進 main」「已解決」「已違反」 |
| 常見誤判 | 工作區看到的就是永久狀態 |
| 實際機制 | 並行環境下工作區隨時被其他 session 改寫，僅在觀測當下成立；git 歷史才是持久事實 |
| 檢查方法 | `git show <commit>:<path>` 或 `git log` 交叉驗證該狀態是否已寫入歷史 |
| 正向對照 | 對已知已提交的變更，`git show` 必須能取回 |
| 判讀標準 | 持久結論前必須有 git 歷史佐證；僅工作區觀測只能寫成「觀測當下」 |
| 來源 | `tool-output-trust-rules` 規則 5 延伸 |
