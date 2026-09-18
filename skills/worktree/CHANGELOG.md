# worktree 版本紀錄

新到舊。版號規則與兩個住址（本檔與 `SKILL.md` frontmatter 的 `metadata.version`）見專案的 skill 同步規範。

**Version**: 1.5.0 — `worktree-remove-deliverable-check-hook.py` 的修復指引補合併被擋下時的處置：`git merge` 若回 `fatal: ref updates aborted by hook`，先 `git merge --abort` 清掉 MERGE_HEAD 殘局，再依 stderr 訊息修正重試；並註明合併本身已對 branch-verify 豁免，此時仍被擋通常來自其他內容 guard（如 reference-stability-rule8）。原指引只給「先 merge」而未涵蓋 merge 被擋的分支，讀者停在一個半完成的合併狀態上沒有下一步。豁免本體位於框架 `.claude/hooks/`，不在本 skill 範圍。

**Version**: 1.4.0（2026-09-08）— token 收斂：`SKILL.md` 5,690 -> 2,487 tokens。〈Agent isolation worktree〉節（原佔 50.6%）外移至 `references/agent-isolation-worktree.md`，入口留速查表逐項路由；〈子命令詳細說明〉節外移至 `references/subcommands.md`，入口留最小範例指標。同時修正一處既有 dangling 引用（「worktree 不含的狀態」節指向不存在的「worktree 快照過舊防護」節，改指向 `references/agent-isolation-worktree.md`〈Base ref 與隔離邊界〉），並同步外部檔案（`pm-rules/parallel-dispatch.md`、`agents/AGENT_PRELOAD.md`、`skills/ticket/references/track-command.md`、`error-patterns/process-compliance` 的相關 PC 檔）對已搬移章節的跨檔引用

**Version**: 1.3.0（2026-09-08）— 「與程式碼提交的分離」段補「`--worktree` 旗標為必帶」句：`resolve_project_cwd()` 依呼叫當下 process cwd 判斷 repo root，agent Bash 呼叫依 harness 慣例每次重設回主倉庫 cwd，未帶旗標會誤綁主 repo；原文「維持原 worktree 感知行為不變」易誤讀為自動跟隨，改「維持原 worktree 感知邏輯不變」並補旗標要求，與 ticket skill〈track commit 子命令〉〈`--worktree` 條件〉、`AGENT_PRELOAD.md` 措辭同步

**Version**: 1.2.1（2026-09-07）— 刪除「Base ref 與隔離邊界」表第 5 列：與第 2 列（daemon-rooted 寫入工具洩漏）議題欄與對策欄逐字重複，事實欄僅寫「同上一列」，退化為指回自身，讀者無從判斷是筆誤或另一路徑

**Version**: 1.2.0 — 補記 1.1.0 之後累積但未 bump 版號的變更（版號未動使發佈庫與本庫的內容分歧無法由版號察覺）。SKILL.md 新增「ticket 狀態統一寫入主倉庫」章節：`get_ticket_state_root()` 使 linked worktree 內的 ticket 狀態寫入反向回推主倉庫，與「Base ref 與隔離邊界」表原本記載的「ticket CLI auto-commit 洩漏」對策方向相反——該列因此改標為當時對策並註明已被取代，避免讀者照舊列行事。同章節說明程式碼提交（`ticket track commit`）維持 worktree 感知不變，兩者是不同的 root 解析路徑

**Version**: 1.1.0 — 新增「worktree 不含的狀態」章節（框架 issue 46 症狀一框架層部分）：worktree 是 git 層隔離，gitignore 產物/建置快取/依賴目錄三類非 git 狀態不隨之而來；不列舉任何專案專屬命令，指引 consumer 於專案層文件記錄並在派發時引用 agent-dispatch-template「環境前置欄位」

**Version**: 1.0.0
**Last Updated**: 2026-08-04
**Status**: MVP (create + status 子命令)
