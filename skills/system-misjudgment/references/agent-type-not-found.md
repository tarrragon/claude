# Claude Code 代理人載入（Agent 工具的可派清單）

## AGT-1 派發收到 Agent type not found，被讀成定義檔壞了或代理人不存在

| 欄位 | 內容 |
|------|------|
| 症狀 | Agent 工具回傳 `Agent type '<name>' not found`；本 session 的可派清單只列出部分專案代理人（實測為 4～6 個），`.claude/agents/<name>.md` 卻存在且格式正確 |
| 常見誤判 | 定義檔的 frontmatter 有錯、代理人已被刪除或改名，於是改派 general-purpose 繼續做 |
| 實際機制 | 可派清單在 session 啟動時載入，載入結果可能殘缺，而且每次啟動彼此獨立：同一 repo、同一版本、同一批定義檔，有的 session 全數載入，有的只載入部分；重開 session 是重抽一次，可能恢復也可能再度殘缺。清單也可能在 session 執行中途更新而縮小：先前派得出去的代理人變成 not found，期間不需要 /clear、/compact 或重開。所以成因可能在 session 層級，不在定義檔；「這個代理人剛才還派得出去」不能排除本條 |
| 檢查方法 | (1) 列出定義檔的名稱：`for f in .claude/agents/*.md; do awk '/^---$/{n++; next} n==1 && /^name:/{sub(/^name:[ ]*/,""); print; exit}' "$f"; done \| sort`；(2) 與本 session 的 Agent 工具可派清單逐一比對；(3) 請同 repo 的另一個 session 列出它的可派清單，看缺的那個代理人在對方是否可派 |
| 正向對照 | 第 (1) 步的輸出必須包含一個已知可派的專案代理人（例如本 session 清單上確實存在的那幾個之一）；第 (3) 步對方 session 的清單必須至少與本 session 一樣多，否則對方也殘缺，不能作為對照 |
| 判讀標準 | 對方 session 可派而本 session 不可派 → session 層級載入殘缺，定義檔不必改，依 `.claude/pm-rules/agent-failure-sop.md`〈派發被拒：Agent type not found（強制）〉停手回報；兩邊都不可派且第 (1) 步沒有該名稱 → 才查定義檔 |
| 來源 | 實測（2026-11，Claude Code 2.1.329～2.1.331，macOS）：8 個 session 共 32 次啟動，完整 17 次、殘缺 15 次，殘缺時只看得到 5 個（一次 6 個），沒有介於兩者之間的計數；同一版本、同一 cwd、相隔 12 秒啟動的兩個 session，一個 32 個全數可派、一個只有 5 個。期望總數含範本檔：範本以 frontmatter 的 `name`（`{language}-developer`）出現在清單，以檔名比對會誤判為缺 1 個 |
