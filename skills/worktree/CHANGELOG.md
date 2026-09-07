# worktree 版本紀錄

新到舊。版號規則與兩個住址（本檔與 `SKILL.md` frontmatter 的 `metadata.version`）見專案的 skill 同步規範。

**Version**: 1.2.1（2026-09-07）— 刪除「Base ref 與隔離邊界」表第 5 列：與第 2 列（daemon-rooted 寫入工具洩漏）議題欄與對策欄逐字重複，事實欄僅寫「同上一列」，退化為指回自身，讀者無從判斷是筆誤或另一路徑

**Version**: 1.2.0 — 補記 1.1.0 之後累積但未 bump 版號的變更（版號未動使發佈庫與本庫的內容分歧無法由版號察覺）。SKILL.md 新增「ticket 狀態統一寫入主倉庫」章節：`get_ticket_state_root()` 使 linked worktree 內的 ticket 狀態寫入反向回推主倉庫，與「Base ref 與隔離邊界」表原本記載的「ticket CLI auto-commit 洩漏」對策方向相反——該列因此改標為當時對策並註明已被取代，避免讀者照舊列行事。同章節說明程式碼提交（`ticket track commit`）維持 worktree 感知不變，兩者是不同的 root 解析路徑

**Version**: 1.1.0 — 新增「worktree 不含的狀態」章節（框架 issue 46 症狀一框架層部分）：worktree 是 git 層隔離，gitignore 產物/建置快取/依賴目錄三類非 git 狀態不隨之而來；不列舉任何專案專屬命令，指引 consumer 於專案層文件記錄並在派發時引用 agent-dispatch-template「環境前置欄位」

**Version**: 1.0.0
**Last Updated**: 2026-08-04
**Status**: MVP (create + status 子命令)
