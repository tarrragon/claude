# worktree 版本紀錄

新到舊。版號規則與兩個住址（本檔與 `SKILL.md` frontmatter 的 `metadata.version`）見專案的 skill 同步規範。

**Version**: 1.6.7（2026-10-31）— cleanup 子命令（`cmd_cleanup`、`_cleanup_*`、Level 2／3 判定 `_is_branch_pushed`／`_is_branch_merged_to_base`、鎖處理、`_timed_git_remove`、`_recovery_unmet_conditions`、`WORKTREE_REMOVE_TIMEOUT_SECONDS`）移到 `scripts/cleanup_command.py`，行為不變；`worktree_manager.main()` 改呼叫 `cleanup_command.cmd_cleanup`，舊名稱經模組層 `__getattr__` 延遲轉出（`WORKTREE_REMOVE_TIMEOUT_SECONDS` 不轉出）。測試替換 cleanup 函式或其查找的名稱須 patch `cleanup_command`，見 `references/subcommands.md`〈cleanup — 模組位置〉。
**Version**: 1.6.6（2026-10-19）— `_is_branch_pushed` 改問「分支 tip 是否在任一遠端 ref 上」（`git for-each-ref --contains --format=%(refname) refs/remotes`，只看結束碼與是否有輸出），不再比對 origin 同名分支；feat／agent 分支從不推送，原判定恆為未推送，使 cleanup Level 2 恆報警。含遠端沒有的 commit、worktree checkout 中、分支不存在三種情況仍判為未推送。
**Version**: 1.6.5（2026-10-19）— `_is_branch_merged_to_base` 改用 `git merge-base --is-ancestor <branch> <base>` 判定，不再解析 `git branch --merged` 輸出；修正 worktree 已 checkout 的分支（輸出帶「+ 」前綴）恆判為未合併，使 cleanup Level 3 對已合併分支不再恆報警。未合併分支（含 worktree checkout 中者、分支不存在）仍判為未合併。
**Version**: 1.6.4（2026-10-19）— `cleanup` 新增 `--branch <分支名>`（與 ticket_id 擇一），用於萃取不到 ticket ID 的 `worktree-agent-<id>`，仍經三閘門；掃描報告對非 ticket 分支改印 `/worktree cleanup --branch <分支名>`（含 `--force` 版），ticket 分支印法不變。
**Version**: 1.6.3（2026-10-19）— 預檢無衝突時 gate 日誌於開始行與結束行之間多記一行 `[合併閘門] 預檢｜…｜結果 無衝突`，使無衝突的合併也能觀測預檢已執行；格式沿用 `gate_line`，`[合併前測試]` 行不變。
**Version**: 1.6.2（2026-10-19）— 合併閘門進場排隊前以 `merge_cas.precheck_merge_conflict` 預檢文字衝突，有衝突即不排隊、結束碼 1，結束行結果為「預檢衝突」；`_prepare_candidate` 與預檢共用 `_trial_merge`。取得名額後的衝突判定保留。

**Version**: 1.6.1（2026-10-19）— 隔離索引 CAS 合併引擎（CheckResult、PreMergeCheck、MergeOutcome、merge_branch_cas 及其輔助函式與 _sleep／_clock 測試接縫）移到 `scripts/merge_cas.py`，行為不變；`worktree_manager.py` 改為匯入。程式入口改為 `merge_cas.merge_branch_cas`，測試接縫只在 `merge_cas` 替換。`merge_branch_cas` 的 repo 為 None 時才延後匯入 get_project_root，worktree_manager 的呼叫端一律明確傳 repo。

**Version**: 1.6.0（2026-10-19）— 合併閘門：`worktree merge` 在快照內先取得 heavy 名額再跑全套件，持有至 update-ref，紅燈不合併並保留失敗細節；以隔離索引 CAS 完成合併，CAS 重試時若期間只改了豁免檔（ticket md、版本工作日誌、topic-assignments）就沿用前次驗證結果；新增 `--branch`、`--pre-acceptance`、`--message`、`--ticket`；名額佇列依先來後到並帶心跳，等待上限只用來偵測持有者卡住。其他：PreToolUse 提醒改走 `additionalContext`；唯讀 git 呼叫補 `--no-optional-locks`；zombie-cleanup 改溫和終止並以整體期限扣減逾時；merge-reminder 排除進行中的派發。

**Version**: 1.5.1 — `worktree-remove-deliverable-check-hook.py` 的 Guard A 對內容已由 main 取代的分支加出口：`git cherry main <branch>` 全為 `-` 時放行並記 info；含 `+` 時照擋，訊息附三步顯式丟棄出口（先以 `git diff main <branch>` 核對取代關係，再 `checkout --detach`、`branch -D`、`worktree remove`），不再建議 `merge -s ours`。另隨框架統一以 `-c core.quotepath=false`／`-z` 讀取 git 路徑清單。

**Version**: 1.5.0 — `worktree-remove-deliverable-check-hook.py` 的修復指引補合併被擋下時的處置：`git merge` 若回 `fatal: ref updates aborted by hook`，先 `git merge --abort` 清掉 MERGE_HEAD 殘局，再依 stderr 訊息修正重試；並註明合併本身已對 branch-verify 豁免，此時仍被擋通常來自其他內容 guard（如 reference-stability-rule8）。原指引只給「先 merge」而未涵蓋 merge 被擋的分支，讀者停在一個半完成的合併狀態上沒有下一步。豁免本體位於框架 `.claude/hooks/`，不在本 skill 範圍。

**Version**: 1.4.0（2026-09-08）— token 收斂：`SKILL.md` 5,690 -> 2,487 tokens。〈Agent isolation worktree〉節（原佔 50.6%）外移至 `references/agent-isolation-worktree.md`，入口留速查表逐項路由；〈子命令詳細說明〉節外移至 `references/subcommands.md`，入口留最小範例指標。同時修正一處既有 dangling 引用（「worktree 不含的狀態」節指向不存在的「worktree 快照過舊防護」節，改指向 `references/agent-isolation-worktree.md`〈Base ref 與隔離邊界〉），並同步外部檔案（`pm-rules/parallel-dispatch.md`、`agents/AGENT_PRELOAD.md`、`skills/ticket/references/track-command.md`、`error-patterns/process-compliance` 的相關 PC 檔）對已搬移章節的跨檔引用

**Version**: 1.3.0（2026-09-08）— 「與程式碼提交的分離」段補「`--worktree` 旗標為必帶」句：`resolve_project_cwd()` 依呼叫當下 process cwd 判斷 repo root，agent Bash 呼叫依 harness 慣例每次重設回主倉庫 cwd，未帶旗標會誤綁主 repo；原文「維持原 worktree 感知行為不變」易誤讀為自動跟隨，改「維持原 worktree 感知邏輯不變」並補旗標要求，與 ticket skill〈track commit 子命令〉〈`--worktree` 條件〉、`AGENT_PRELOAD.md` 措辭同步

**Version**: 1.2.1（2026-09-07）— 刪除「Base ref 與隔離邊界」表第 5 列：與第 2 列（daemon-rooted 寫入工具洩漏）議題欄與對策欄逐字重複，事實欄僅寫「同上一列」，退化為指回自身，讀者無從判斷是筆誤或另一路徑

**Version**: 1.2.0 — 補記 1.1.0 之後累積但未 bump 版號的變更（版號未動使發佈庫與本庫的內容分歧無法由版號察覺）。SKILL.md 新增「ticket 狀態統一寫入主倉庫」章節：`get_ticket_state_root()` 使 linked worktree 內的 ticket 狀態寫入反向回推主倉庫，與「Base ref 與隔離邊界」表原本記載的「ticket CLI auto-commit 洩漏」對策方向相反——該列因此改標為當時對策並註明已被取代，避免讀者照舊列行事。同章節說明程式碼提交（`ticket track commit`）維持 worktree 感知不變，兩者是不同的 root 解析路徑

**Version**: 1.1.0 — 新增「worktree 不含的狀態」章節（框架 issue 46 症狀一框架層部分）：worktree 是 git 層隔離，gitignore 產物/建置快取/依賴目錄三類非 git 狀態不隨之而來；不列舉任何專案專屬命令，指引 consumer 於專案層文件記錄並在派發時引用 agent-dispatch-template「環境前置欄位」

**Version**: 1.0.0
**Last Updated**: 2026-08-04
**Status**: MVP (create + status 子命令)
