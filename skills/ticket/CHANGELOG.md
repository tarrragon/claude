# ticket 版本紀錄

新到舊。版號規則與兩個住址（本檔與 `SKILL.md` frontmatter 的 `metadata.version`）見專案的 skill 同步規範。frontmatter 版號同步由後續收尾票統一處理，本檔先行遞增記錄。

**Version**: 2.44.23（本地變更）— `git_ops.commit_files_isolated` 的提交範圍自我驗證由嚴格相等改為子集比對：列出但淨變更為零的路徑合法，僅清單外的變更判 failed（錯誤訊息附範圍外路徑，不 update-ref）；全部列出路徑皆無淨變更仍由空 tree 短路回報 no-op（exit 0、不建 commit）。此前多路徑寫入（如 `add-child` 子票的 parent 本已相同、`set-parent` 往返三檔只有一檔有變更）因嚴格相等誤報 exit 75，真實變更留在工作區。測試（`tests/test_commit_isolated_subset_scope.py`）：兩路徑其一無變更提交只含有變更者（修正前紅）、真實 CLI `add-child` 子票已連結 exit 0 且 commit 只含父票（修正前紅）；E2 對照：清單外路徑有變更時 failed 且 HEAD 不動，真實 CLI 構造同一情境 exit 75；全部無變更為 no-op。

**Version**: 2.44.22（本地變更）— `add-spawn-request` 的 SR 編號改為只取 Spawn Requests 章節內結構化條目（行首 `- **SR-N**`）的最大號加一，不再以全文 regex 掃整份票面。此前 Solution 等正文只要提到 `SR-N`（如草稿寫 SR-9）就被計入，首個 spawn request 會被編為 SR-10，出現空號。`resolve-spawn-request` 定位條目本就限章節內且錨定行首，正文提及不會誤命中，行為不變。E1 對照測試（`tests/test_spawn_request_numbering.py`）：正文含 SR-9 且章節為空時編為 SR-1；章節已有 SR-1、SR-2（條目內另提 SR-40）時編為 SR-3；resolve 定位不命中正文提及。

**Version**: 2.44.21（本地變更）— 破壞性變更：移除 `ticket version-shift` 命令。原因：三層目錄結構下 dry-run 即 exit 1（七處寫死扁平路徑）；扁平結構下也會整檔重寫 todolist、漏改他版本引用、遺失 topic 與舊 ID，且沒有任何流程依賴它。刪除 `commands/version_shift.py`、CLI 註冊、`VersionShiftMessages` 與對應測試。替代流程：`version-release start --version <目標版本>` 登記目標版本，`ticket migrate --config` 搬票，再手動完成 todolist 版本條目、worklog 主檔、舊目錄三步，每步驗證方式見 `references/migrate-command.md`〈整版改號流程〉。

**Version**: 2.44.20（本地變更）— `git_ops.commit_files_isolated` 在 `update-ref` 取 ref 鎖之前先以同一份 reference-transaction guard 預驗證新 commit，通過時於該次 `update-ref` 的環境帶 `GUARD_PREVALIDATED=<new>:<old>:<ref>`，hook shim（v4）命中即放行，持鎖期間不再啟動 python。此前 hook 內啟動 uv 與 python 掃描佔持鎖時間一半以上。（1）預驗證 `_prevalidate_guard_env(repo_root, commit_sha, old_head)`：分支以呼叫端已解析 repo_root 的 `symbolic-ref HEAD` 取得，不讀 CLAUDE_PROJECT_DIR（worktree 情境會指錯 checkout）；以預驗證模式（`GIT_REF_GUARD_PREVALIDATE_ONLY=1`）執行 guard，僅「無任何發現（含 WARN）、非合併、載入成功」才輸出乾淨標記並設 env；deny、WARN、MERGE_HEAD、detached HEAD、guard 缺席一律不設 env；guard 載入或執行失敗不設 env，且 stderr 與 `.claude/hook-logs/git-ops-prevalidate/` 日誌皆可見。（2）env 只隨該次 `update-ref` 傳遞，不寫入行程環境、其餘 git 呼叫不帶。（3）shim v4 先存整段 stdin，命中條件為整段 stdin 與 `<old> <new> <ref>` 單行逐字全等（單行、ref、old、new 一次綁定，且 old/new 須為十六進位、ref 須為 `refs/heads/` 開頭）；未命中把 stdin 原樣管線給 python，多 ref 交易含違規者照常以 rc=87 阻擋。（4）guard 本體新增預驗證模式輸出，一般 hook 行為不變。E1／E2 對照測試：shim 命中與 ref／new／old 不符、格式錯誤 env、多 ref 交易各一（不符者假 uv 皆回 87 且必須被呼叫並阻擋）；預驗證各條件不符即回 None；env 傳遞範圍；真實 git 倉庫端到端（乾淨提交鎖內零次 python、保護分支違規與 worktree 內違規皆被 hook 攔下）。

**Version**: 2.44.19（本地變更）— `complete` 與 `batch-complete` 的主 worklog 進度行改以行層級提交，不再整檔提交 worklog。（1）`worklog_appender.append_worklog_progress` 回傳值由 bool 改為實際插入的進度行（含結尾換行），未寫入（檔案不存在、冪等跳過、無日期區段、寫後驗證失敗、例外）回 None；新增 `worklog_append_spec(行)`，包成 `AppendSpec`，其 `replay` 以最後日期區段末尾為插入點在 HEAD 版本上重放。（2）`complete` 以 `append_lines={worklog: AppendSpec}` 併入同一筆 post-completion commit，`_auto_commit_completion_files` 新增選用參數 `append_lines`；worklog 不再列入整檔 `paths`，工作區 worklog 內他人未提交的修改不再被吸入。（3）`batch-complete` 此前只提交票檔，進度行留在工作區為已修改；現收集各票插入的行，以單一 `append_lines` 值併入批次提交，寫入後工作區乾淨。（4）他人修改了 worklog 既有行（工作區不是超集）時，進度行仍落在最後日期區段末尾，不落到檔尾。此前 2.44.11 對 `batch-complete` worklog 進度行「維持原行為」的註記由本版取代。測試：真實 repo 與真實 CLI 入口下，`batch-complete` 進度行與票檔同一 commit 且工作區乾淨（修正前 worklog 留為已修改）；工作區 worklog 含他人未提交行時 `complete` 與 `batch-complete` 的 HEAD 不含該行（修正前 `complete` 整檔吸入）；他人改了既有行時進度行落在日期區段內。`append_worklog_progress` 回傳契約測試同步改為斷言插入行與 None。

**Version**: 2.44.17（本地變更）— `git_ops.commit_files_isolated` 的 `append_lines` 值型別擴充：除純文字外可傳 `AppendSpec(text, replay)`，`replay(base, text)` 收 HEAD 版本全文與追加文字、回傳插入後全文。工作區缺檔或不是「HEAD + 本次行」超集時，有 `replay` 則在 HEAD 版本上重放插入，行落在呼叫端指定位置；此前一律接在 HEAD 末尾，中段插入型檔案（如 worklog 進度行）會落到檔尾。無 `replay` 的純文字值行為不變（超集依工作區行序投影，非超集接在 HEAD 末尾），`topic-assignments.txt` 等既有呼叫端不受影響。他人未提交內容在超集與非超集兩種情境下都不進入提交。測試（`tests/test_git_ops.py` 的 `TestAppendReplayFallback`）：非超集重放落點、無 replay 維持檔尾、超集忽略 replay 並排除他人行、非超集他人修改不被吸入。

**Version**: 2.44.16（本地變更）— `ticket migrate` 改為自動提交並補齊結構欄位改寫。（1）單票與批次 `--config` 的全部寫入（新檔、刪除的舊檔、各引用者、topic-assignments 追加行）以 `commit_ticket_mds_reporting` 單一隔離 commit 入庫，主路徑取仍存在的新檔；批次只提交成功項；提交最終失敗輸出 `[WARNING]`（列出全部路徑與未入庫的追加行）並回 exit 75，檔案保留在工作區。此前 migrate 寫完不提交且 exit 0，HEAD 會出現指向不存在 ID 的引用。（2）引用改寫補上 `discovered_during`、`closed_by`（字串或清單）與子孫的 `chain.root`／`chain.parent`。（3）`topic_assignments` 新增 `inherit_assignment`／`assignments_file_path`：新 ID 追加一行承接舊 ID 的主題，舊行保留（append-only），以 `append_lines` 只提交該行；此前新 ID 的 `list_assignments()` 回傳 None。（4）被遷移票新增 `previous_ids` 欄位（有序清單，每次遷移追加舊 ID，長度即遷移次數）；語意不同於撞號改號的 `migrated_from`（撞號前的原目標）。票面 body 與 Context Bundle 內的舊 ID 屬歷史事實，不改寫。E1 對照測試（`tests/test_migrate_autocommit.py`）：無鎖時 exit 0、工作區乾淨、恰增一個 commit 且含舊檔 D／新檔 A／引用者 M／topic 僅追加一行；殘留 ref 鎖時 exit 75、WARNING 列全部路徑；另含結構欄位改寫、previous_ids 與 body 保留、topic 承接、批次只提交成功項。

**Version**: 2.44.15（本地變更）— `complete` 的自動提交範圍加入本次被解鎖的票。範圍由「本票 md + 工作日誌」擴為再加上 cascade 解鎖的 children 與反向 blockedBy 解鎖的引用者（後者可跨版本），僅 save 成功者列入，save 失敗者不列入且原 WARNING 照常；同一筆 post-completion commit 的 body 列出被解鎖的票 ID，提交失敗時 exit 75 的補救指令 `git add` 列出全部路徑。變更理由：解鎖寫入是 complete 的連帶副作用，此前只提交本票與工作日誌，被解鎖的票留在工作區為已修改，可能被他人的提交吸入，或被還原回 blocked 而使解鎖靜默失效；跨版本不構成技術障礙，隔離索引提交本就以絕對路徑跨目錄。無解鎖對象時範圍不變（本票加工作日誌）。`_post_complete_cascade`、`_cascade_unblock_children`、`_reverse_unblock_blockedby` 新增選用參數 `saved_paths`（回傳值形狀不變），`_auto_commit_completion_files` 新增選用參數 `unblocked_paths`；移除程式內「不含 children 與 siblings」的過期註解。此前 2.44.11 對 complete 解鎖路徑「維持原行為」的註記由本版取代。測試（`tests/test_complete_auto_stage.py`）：真實 git repo 與真實 CLI 入口下，父票 complete 同時解鎖同版本 child 與跨版本引用者，三張票加工作日誌在同一 commit 且已追蹤檔案無未提交變更（修正前兩張被解鎖票留為已修改）；E1 對照無解鎖對象時範圍為本票加工作日誌；save 失敗的被解鎖票不列入；殘留 ref 鎖時 exit 75 且補救指令列出全部路徑。原先斷言 children／siblings 不進入提交清單的兩個 mock 測試改為斷言進入。

**Version**: 2.44.14（本地變更）— `git_ops.commit_files_isolated` 的提交範圍自我驗證改用 `git diff --no-renames`，不再受 `diff.renames` 設定影響。此前舊路徑刪除加新路徑新增（改名）時，diff 只回報新路徑，與預期的新舊兩路徑不符而誤判失敗並放棄提交。同時明確拒絕目錄路徑（回 failed 並說明須逐檔列出），docstring 寫明刪除與改名須列新舊路徑、主路徑須為存在的檔案。測試（`tests/test_git_ops.py`）：舊刪新增、改名並改內容加另一檔修改、跨目錄逐檔列舉三案（修正前紅），範圍外變更仍 failed 且不 update-ref，目錄路徑拒絕。

**Version**: 2.44.13（本地變更）— `git_ops._stage_appended_blob` 改依工作區行序投影 append-only 檔：提交內容為「HEAD 各行 + 本次各行」（multiset 配對，重複行按次數計，保留工作區順序，不含他人未提交的行）。兩個寫入者都在任一方提交前完成追加、且提交順序與追加順序相反時，提交後 HEAD 與工作區行序一致，檔案不再持續顯示已修改。工作區缺檔、不可讀或不是該 multiset 的超集時，退回原做法「HEAD 版本 + 本次行」。`commit_files_isolated` 的 `append_lines` 參數介面不變；docstring 契約由「提交內容只多出本次 text」改為「行集合恆為 HEAD + 本次，行序依工作區」。測試（`tests/test_git_ops.py`）：兩寫入者 6 種交錯順序（修正前 2 種持續為已修改）、他人未提交行夾在中間不被吸入、重複行 multiset 配對、缺檔與非超集退回。

**Version**: 2.44.12（本地變更，指向 tarrragon/claude#102）— `ticket track add-spawned` 寫入 spawned_tickets 時一併寫目標票的反向 `source_ticket`，與 `remove-spawned` 對稱。此前只寫單向，目標票 source_ticket 維持 null，`remove-spawned` 的反向清理對它無事可做、血緣視圖單向殘缺。規則：目標票 source_ticket 為空才寫入；已有值（無論是否為本票）保留原值不覆寫，已有不同值時沿用既有 WARNING；目標票不存在或版本無法解析時略過。跨版本成立（目標票各自依自身 ID 解析版本與路徑）。本票與被寫入的目標票改以 `commit_ticket_mds_reporting` 單一 commit 提交；反向寫入發生在本票 file_lock 釋放後，各目標票獨立上鎖不巢狀。新增 `_set_reverse_source_if_unset`（fields.py），無簽名變更。E1／E2 對照測試（`tests/test_add_spawned_reverse_source.py`）：寫入後 B.source_ticket 為 A（修前為 null）、已有不同 source 保留加 WARNING、add 後 remove 雙方欄位還原、跨版本、重複 add 冪等。

**Version**: 2.44.11（本地變更）— 一次寫多張票的命令納入 auto-commit 與失敗可見性：多張票以單一 commit 提交，最終失敗輸出 `[WARNING]` 並回 exit 75，非 git repo 仍只印 skipped 且 exit 0。（1）`git_utils` 新增 `commit_ticket_mds_reporting(label, ticket_paths, ticket_id, section, operation)`：路徑去重、第一個為主票、其餘走 `extra_paths` 併入同一提交，空清單不提交；`format_write_command_commit_failure` 新增選用參數 `extra_paths`，補救指令的 `git add` 列出全部路徑（既有呼叫形態不變，`commit_ticket_md_reporting` 亦會轉傳 `extra_paths`）。（2）改為單一 commit 並回 75：`add-child`（父加子兩張）、`set-parent`（子、舊父、新父，至多三張）、`batch-claim`／`batch-complete`（全部寫入成功的票，迴圈結束後一次提交；全失敗無檔可提交，維持 exit 2；提交失敗的 75 優先於 0）、`batch-create`（新建的全部票檔，75 優先於部分失敗的 1）、`generate`（新生成的全部票檔）。（3）單票但此前從未提交：`dispatch`（有落票才提交，骨架 prompt 照常輸出後回 75）、`claim`（提交置於 Context Bundle 抽取之後，使 claim 的全部寫入一次入庫）、`release`、`close`。（4）不改並註明理由：`version-shift`（搬移票檔與版本目錄、改寫 todolist 與跨版本引用、備份，含刪除與改名，不是「票檔集合寫入」）、`migrate`（改票號＝改名加全庫引用改寫，同理）、`complete` 的 cascade／反向 blockedBy 解鎖（先前定案 complete 的提交範圍為本票加 worklog，被解鎖的票可跨版本）、`batch-complete` 追加的 worklog 進度行（非票檔），四項維持原行為，另案追蹤。（5）讀 exit code 的消費者同步：`track.py` 的 `claim`／`release` 包裝原本只在 rc 為 0 時寫入或移除 lease，現與 `complete` 對稱，0 與 75 皆處理；`parallel-claim-audit-hook.is_claim_successful` 原以 stderr 子字串（含 `failed`）判斷失敗，claim 回 75 時原因文字可能含 `failed` 而漏記審計，現以 `exit_code == 75` 為權威、WARNING 固定片語為後備。其餘 hook 與 python 呼叫端全域盤點（`.claude/hooks`、`.claude/skills/*/hooks`、`.claude/skills` 內 python）無其他讀取這些命令 exit code 者。`tests/test_track_batch.py` 以 mock 取代 `save_ticket`（票檔不存在），加 autouse 樁停用批次尾端提交；提交行為改由 E1 測試覆蓋。E1 對照測試（`tests/test_multi_ticket_autocommit_scope.py`，fixture 沿用單票版並在 fixture repo 的 `.gitignore` 忽略 `.claude/hook-logs/`，使結果不依是否在 Claude session 內執行）：同一真實 git repo，無鎖時 exit 0、無 WARNING、工作區乾淨且恰增加一個 commit、涵蓋全部被寫的票檔；殘留 ref 鎖時 exit 75、輸出 `[WARNING]`、票檔仍在工作區；另含 `commit_ticket_mds_reporting` 單元測試（單一 commit、去重與空清單、補救指令列出每個路徑）。

**Version**: 2.44.10（本地變更）— 寫入票面的 `ticket track` 子命令統一走 `git_utils.commit_ticket_md_reporting`：預設自動提交，最終失敗輸出 `[WARNING]` 並回 exit 75（`EXIT_AUTO_COMMIT_FAILED`），非 git repo 仍只印 skipped 且 exit 0。（1）此前從未提交的 `execute_set_field` 家族（`set-who`／`set-title`／`set-what`／`set-when`／`set-why`／`set-how`／`set-priority`，以及 `set-where` 的整體覆寫路徑）改為在 file_lock 內寫入後立即提交，寫入後工作區不再留未提交的票檔；`set-where`／`set-how` 的子欄位路徑（`_execute_set_dict_subfields`）同樣納入。（2）此前失敗只印 skipped、rc 為 0 的命令改回 75：`set-scope-blocker`、`add-acceptance`、`set-acceptance`、`add-spawned`、`remove-spawned`（含反向 `source_ticket` 欄位的提交；`_clear_reverse_source_if_matches` 新增選用的 `commit_failures` 收集參數，回傳值語意不變）、`add-spawn-request`、`resolve-spawn-request`、`register-artifact`、`resolve-artifact`、`add-exempt-marker`、`fix-multi-view-status`、`set-closed-by`、`restore`。（3）新增提交：`remove-acceptance`、`set-decision-tree`、`phase`、`set-blocked-by`／`set-related-to`。（4）不改：`set-parent`／`add-child`（一次寫多張票，`commit_ticket_md_reporting` 目前只收單一路徑）、`batch-claim`／`batch-complete`、`dispatch`、`version-shift`、`migrate` 等多票或非欄位寫入命令，維持原行為，另案追蹤。（5）讀這些命令 exit code 的 hook 同步：`dispatch-identity-bind-hook` 對 `set-who` 的判讀由「非 0 即失敗」改為 0 與 75 皆視為已綁定；其餘 hook 在前一版已是 75 感知或只讀 stderr。E1 對照測試（`tests/test_write_command_autocommit_scope.py`）：同一真實 git repo、真實票檔、真實 CLI 入口下，無鎖時每個命令 exit 0、無 WARNING、`git status --porcelain` 為空；殘留 ref 鎖時每個命令 exit 75 並輸出 `[WARNING]`。hook 端對照見 `tests/test_hooks_exit_code_75.py`。

**Version**: 2.44.9（本地變更）— `ticket create --parent <ANA>`、`--blocked-by <ANA>` 與 `ticket track set-blocked-by`（replace／`--add`）新增耦合後果提示，只寫 stderr，exit code 不變。ANA 掛非終態 children 時不能 complete，被 blockedBy 的 ANA 不 complete 則依賴它的票一直等；提示把這條後果在建票或設依賴當下說出來。兩種觸發：`--parent` 指向的 ANA 已被其他非終態票 blockedBy（列出受影響的票）；blockedBy 目標為有非終態 children 的 ANA（列出 children）。判斷改讀票庫：依賴者以 `list_tickets` 反查 blockedBy，children 讀 ANA 的 `children` 欄位；終態判定用 `TERMINAL_STATUSES`。新增 `lib/ana_coupling_hint.py`。E1 對照測試（`test_ana_coupling_hint.py`）：同 fixture 下提示案與不提示案成對，不提示案為父票非 ANA、ANA 無依賴者、依賴者已終態、children 已終態、blockedBy 目標非 ANA、`--remove`；每案斷言 exit code 為 0。 參考文件已同步：`field-semantics.md` 阻擋語意表補 children 對 blockedBy 下游的傳遞效果列，`track-command.md` 的 `--force` 描述對齊 hook 實際旁路範圍，`create-command.md` 的 `--source-ticket` 兩處不再導向 ANA 落地；只改文件與註解，版號不升。

**Version**: 2.44.8（本地變更）— `ticket track set-parent`、`add-child`、`batch-claim`、`batch-complete` 未給 `--version` 時，版本改從 ID 位置參數解析，不再退回只看 active 版本的自動偵測。根因：`track.execute` 只讀 `args.ticket_id` 取版本，這四個子命令的位置參數名為 `child_id`／`parent_id`／`ticket_ids`，取不到而落到自動偵測，planned 版本的票回報「找不到 Ticket」。新增 `_ticket_id_arg_version`，依序取 `ticket_id`／`child_id`／`parent_id`／`ticket_ids`（逗號分隔取第一個）；ID 解析不出版本才退回自動偵測，`--version` 顯式值仍最優先。其餘 track 子命令位置參數皆為 `ticket_id`，本就共用同一段解析，無同型缺口。`batch-*` 一次只解析一個版本（取第一個 ID），跨版本混合清單須自行給 `--version`。E1 對照測試：planned 版本的票同 fixture 下 `set-parent --clear` 給 `--version` 成功、不給修前回報找不到而修後成功；`add-child` 同；顯式 `--version` 指向別版時仍尊重顯式值。

**Version**: 2.44.7（本地變更）— 修復 ticket CLI 提交後共用 index 留下過期 entry，並讓寫入命令的 auto-commit 最終失敗可見。（1）`git_ops._sync_shared_index_after_commit` 改讀「呼叫當下 HEAD」的 blob 寫回共用 index，不再寫本次 tree 的 blob：兩次 CAS 提交同一檔案且同步順序顛倒（路徑 B）時，晚到的舊同步不再把 entry 寫成比 HEAD 舊。他方保護：共用 index 該 entry 既不等於本次 commit 的 parent 版本、也不等於本次 tree 版本或當下 HEAD 版本時視為他方另外 stage，不覆寫並印 WARNING（含 `git restore --staged` 指令）。同步最終失敗（路徑 A，鎖重試用盡）的 WARNING 改為列出受影響路徑與補救指令。不刪鎖、不做全量 read-tree。函式簽名新增選用參數 `old_head`（既有三參數呼叫形態不變）。（2）`append-log`、`check-acceptance`（單筆與 `--all`）、`complete` 的 auto-commit 最終失敗比照 create：輸出 `[WARNING]`（原因、鎖檔路徑、補救指令），退出碼 75（`EXIT_AUTO_COMMIT_FAILED`）；非 git repo 仍只印 skipped 且 exit 0。共用收尾 `git_utils.commit_ticket_md_reporting`。`complete` 回 75 時票已完成，`track complete` 仍釋放 lease、`handoff` 的 complete 步驟視為完成。E1 對照測試：同 fixture 下無鎖成功（無 WARNING、exit 0）與殘鎖失敗（WARNING、exit 75）；同步順序正常 vs 顛倒；他方 stage vs 無他方 stage。未涵蓋：`set-how`／`set-who`／`set-priority` 等 `execute_set_field` 家族原本就不 auto-commit（非失敗被吞，是從未提交），以及 `set-where`、`add-acceptance`、`add-spawned`、spawn request、artifact 等其餘寫入命令仍為非致命 skipped，另案追蹤。（3）讀取 ticket 寫入命令 exit code 的 hook 同步調整：`parallel-dispatch-verification-hook`、`handoff-cleanup-hook`、`needs-context-listener-hook` 將 0 與 75 都視為「動作已完成」照常執行；`cli-error-feedback-hook` 把 75 當 0 處理，不補錯誤引導。原因是 75 的 stderr 是 WARNING，不是 CLI 錯誤。reclaim 遇 append-log 回 75 時，改印「日誌已寫入，自動提交失敗」。E1 對照：每個 hook 以 0、75、1 各跑一次。（4）合併後實測補修兩點。其一，他方保護規則會把過期 entry 永久卡住：第一次同步失敗後 entry 停在舊版，其後每次同步都因「不等於 parent／tree／HEAD」判為他方 stage 而不覆寫。判定「己方歷史版本」的依據加上「entry 的 blob 出現在該路徑 HEAD 可達的最近 50 次提交中」（`_OWN_HISTORY_LOOKBACK`；同步失敗罕見、其後累積的提交數遠低於 50，且只在前三項比對未命中時才進入，正常路徑零額外成本）。從未提交過的 blob 仍視為他方 stage，不覆寫。其二，共用 index 同步中持有 index.lock 的 `update-index`（`--index-info`、`--force-remove`）比照 update-ref 不設 timeout：被 `_GIT_TIMEOUT` 殺掉會殘留鎖。update-index 無 hook 可掛，測試以 `subprocess.run` 包裝模擬持鎖耗時超過 timeout。E1／E2 對照測試：三次提交且第一次同步失敗後第二次同步 entry 寫成 HEAD、從未提交的 blob 不覆寫、回溯上限為 1 時超出範圍不覆寫、update-index 遇模擬超時不殘留 index.lock。

**Version**: 2.44.6（本地變更）— `ticket create` 的 auto-commit 失敗不再靜默，並修正殘骸鎖的成因。實測根因：`commit_files_isolated` 的 `update-ref` 持有 HEAD.lock／分支 ref 鎖期間會執行 reference-transaction hook，高負載下 hook 超過 `_GIT_TIMEOUT`（10 秒），`subprocess.run` 逾時殺掉 git，鎖殘留，其後每次提交撞鎖失敗。修法：（1）`update-ref` 不設 timeout（`git_ops._run_git` 的 timeout 預設改為呼叫當下讀取模組層 `_GIT_TIMEOUT` 的哨兵，`None` 代表不設）；其餘持鎖步驟作用於私有臨時 index 或為毫秒級，維持預設。（2）`git_utils.auto_commit_ticket_md_with_retry`：git_failed 且屬暫時性鎖競爭（非過期殘骸診斷）時退避重試，等待總和上限約 5 秒；`_auto_commit_ticket_md` 新增 `result_out` 帶回失敗原因，非 git repo 回 `not_git_repo`。（3）最終失敗時 create 輸出 `[WARNING]`（原因、鎖檔路徑、補救指令），票檔保留，退出碼 75（`EXIT_AUTO_COMMIT_FAILED`，sysexits EX_TEMPFAIL），記於 `references/create-command.md`；工具絕不自動刪除鎖檔。E1／E2 對照測試：過期鎖警告加退出碼、新鮮鎖不判過期、鎖於重試期間釋放則靜默成功、慢 reference-transaction hook 不殘留鎖。

**Version**: 2.44.5（本地變更，2.44.4 的回歸修正）— 2.44.4 把 `create --where` 改為 `action="append"` 後，`args.where_files` 由字串變為字串清單，但主題推導 S2 的 `topic_inference.infer_topic_from_files` 仍對其呼叫 `.split(",")`：給 `--where` 且未給 `--topic`／`--new-topic`／`--no-topic` 時，`ticket create` 以 `AttributeError: 'list' object has no attribute 'split'` 崩潰。改用 `lib/list_args.py` 的 `expand_list_arg` 正規化，同時接受清單與逗號字串。2.44.4 的測試只覆蓋 create 解析函式內的消費點，未覆蓋繞過該函式直接讀 `args.where_files` 的主題推導路徑。E1 對照測試：清單與逗號字串兩種輸入推導結果相同；端到端以真實 argv `--where x --where y` 且不給主題旗標建票，rc=0 且 S2 照常推導。

**Version**: 2.44.4（本地變更）— `ticket create` 的 `--blocked-by`、`--related-to`、`--where` 改 `action="append"`，同批 `track set-where --files`、`track add-spawn-request --files` 一併處理（重複給同樣靜默丟值；set-where 整次呼叫仍整體覆寫 where.files），可重複給且相容逗號分隔（共用 `ticket_system/lib/list_args.py` 的 `expand_list_arg`：去空白、去空項、保序去重）。此前重複給只保留最後一個值且無警告，blockedBy 缺漏會讓 runqueue 誤判票可執行。E1 對照測試：重複旗標與逗號寫法結果相同、混合寫法保序去重。

**Version**: 2.44.3（本地變更，指向 tarrragon/claude#55）— `ticket create` 的可攜問題分流閘門（`PORTABLE_ISSUE_UNDEDUPED`）改以「路徑是否會被 sync-push 推到 canonical」判定，不再只看 `.claude/` 前綴：`field_validators.is_portable_where_files` 對每條 `.claude/` 路徑經 `claude_lib_loader.load_claude_lib` 載入 `sync_exclude_manifest`，重用 `load_sync_skills_config`／`should_exclude_skill(direction="push")`／`should_exclude`，sync-skills.yaml 宣告 private（或 mode=select 下不在 include、mode=none）的 skill 路徑與同步排除清單內路徑不算可攜；全數 `.claude/` 路徑皆不推送時不觸發閘門，含任一會推送的路徑仍觸發。manifest 不可用或設定檔解析失敗時退回原行為（視為會推送，stderr 留訊息）。E1／E2 對照測試：全在 private skill 下不觸發、同路徑無 private 宣告觸發、混入非 private `.claude/` 路徑仍觸發、mode=select 下 include 內外 skill 各異。版號取 2.44.3 而非 2.44.2：2.44.2 尚待推送，不論其是否已推送皆不撞號。

**Version**: 2.44.2（本地變更，指向 tarrragon/claude#55）— `ticket create` 的 auto-commit 連同建票旁路寫入進同一個隔離索引提交：`topic-assignments.txt` 的主題行、`--source-ticket` 來源票的 `spawned_tickets` 回填。此前只提交新票 md，兩者殘留工作區，被下一個不相干提交吸入或被誤認為他人遺留。`git_ops.commit_files_isolated` 新增 `append_lines`（路徑 -> 追加文字）：該檔提交內容為「HEAD 版本 + 追加文字」而非整檔，多寫入者 append-only 檔不會帶入他人未提交的行；提交範圍自我驗證與共用 index 同步一併涵蓋。`git_utils._auto_commit_ticket_md` 新增 `extra_paths`／`append_lines`（預設 None，既有呼叫端形態不變）。來源票僅在其內容含新票 ID 時才納入（回填失敗則無變更，納入會使自我驗證失敗）。同批涵蓋 `--new-topic` 的 `topics-registry.txt` 註冊（同樣走 `append_lines`，只帶本次追加的一行；先呼叫 `append_topic` 以得知本次是否真的追加）與 `--parent` 的母票 `children` 回填（與來源票同一判準：母票內容含新票 ID 才納入）。E1／E2 對照測試：有主題 vs `--no-topic`、來源票回填、母票回填、registry 行（新主題 vs 既有主題）、他人未提交的 assignments／registry 行不被吸入。 追加（同批發版）：worktree 派發骨架收尾句明示「只提交產品檔、票面由主 repo CLI 寫入並自動提交」，`ticket track commit --worktree` 輸入含票自身 md 時拒絕（票面依 root 分離設計不在 worktree 提交，副本為舊版本，合回 main 會使票面狀態倒退）；不帶 `--worktree` 的既有行為（ANA 票提交自身 md）不變。`agent-dispatch-template.md` 對應段同步。E1 對照測試：worktree 提交帶票面 vs 不帶，前者拒絕且 HEAD 不動、後者分支僅含產品檔；worktree 變體收尾句含「票面／產品檔／主 repo」而 none 變體不含。

**Version**: 2.44.1（本地變更，指向 tarrragon/claude#111）— 讀取 git 路徑清單改 `-z` 以 NUL 切分，不再受 `core.quotepath` 影響：`git_ops.commit_files_isolated` 的 `diff --name-only` 自我驗證與 `_sync_shared_index_after_commit` 的 `ls-tree` 解析同批修正（只修前者時 CJK 路徑會被判缺席，`update-index --force-remove` 誤刪共用 index 項目）；`track_commit` 目錄展開的 `status --porcelain`、`ticket_builder.list_ticket_files_from_main` 的 `ls-tree` 同改；`ticket-md-auto-commit-hook` 移除部分處理用的 `.strip('"')`（源頭已由共用層 `get_uncommitted_files` 改 `-z`）。E2 對照測試：tmp git repo 以 CJK／ASCII 檔名 fixture 跑隔離索引提交、目錄展開、ls-tree 列舉，CJK 案修前紅、修後綠，ASCII 兩態皆綠。

**Version**: 2.44.0（本地變更，指向 tarrragon/claude#101）— `agent-dispatch-validation-hook` 拆除審查模式關鍵字豁免（`REVIEW_MODE_KEYWORDS`、`_is_review_mode_prompt`、全文子字串放行分支）：實作票收尾標準用語「Phase 4 評估」必然命中子字串，實作派發被放行至共用主工作樹，守衛失效方向為放行。審查豁免唯一路徑為 prompt 首行 `Dispatch-Mode: readonly`。外部 `.claude/` 阻擋後放行順序改為 readonly 首行、`isolation=worktree`、純主 repo `.claude/`（ARCH-015）、阻擋；帶 isolation 的派發 log 記為 worktree 放行。E2 對照測試：含「Phase 4 評估」無 isolation 者阻擋、加首行宣告者放行、帶 isolation 者 log 為 worktree 放行。

**Version**: 2.43.0（本地變更，指向 tarrragon/claude#101）— `ticket track dispatch` 骨架感知派發位置：新增 `--isolation {worktree,none}`（預設不帶＝none），worktree 變體 normal 骨架收尾句改 `ticket track commit` → `ticket track finish` 並註明 finish 被隔離守衛拒絕時交還 PM 代跑（收尾句以 `CLOSING_BY_ISOLATION` 對表選用）；未帶旗標且 where.files 含非豁免路徑時 stderr WARNING（不阻擋，豁免清單同 branch-verify-hook）。`--kind review` 骨架首行加 `Dispatch-Mode: readonly`（normal 不帶）。E1 對照測試：帶與不帶 isolation 收尾句不同、review 與 normal 首行不同、警告三情境（非豁免／全豁免／明示旗標）各異。

**Version**: 2.42.5（本地變更，指向 tarrragon/claude#55）— 讀取端支援跨版本 blocker：`blocker_resolution` 新增 `resolve_blocker`（版本內 map 查無時以 blocker ID 自身的版本前綴載入，取不到版本或載入失敗維持「未解除」），`is_fully_unblocked` 與 `track_runqueue._unresolved_blockers` 共用，消除第二份判定實作的漂移空間。`complete` 的反向解鎖除本版本外，加掃 todolist 中尚未 completed 的其他版本（新增 `list_open_versions`；候選以 ID 去重、以候選自身版本落盤），被其他版本 blocker 擋住的票 complete 後可由 blocked 轉 pending 並列出。不變：`validate_blocked_by_references` 的循環偵測仍只看單一版本。E1／E2 對照測試：跨版本 completed／pending／真不存在三案判定各異，反向解鎖含無關票對照。

**Version**: 2.42.4（本地變更，指向 tarrragon/claude#55）— `set-related-to`、`set-blocked-by`、`create --blocked-by` 改以被引用 ID 自身的版本前綴驗證存在性（新增 `field_validators.resolve_reference_version`，取不到版本前綴才退回目標票版本），修復引用建在其他版本的 ticket 時一律回報找不到的問題。載入仍經 `track_relations` 與 `field_validators` 模組層的 `load_ticket`。不變：`validate_blocked_by_references` 的循環偵測仍只看單一版本。E1／E2 對照測試：替身以 `(version, id)` 為鍵，兩個方向的跨版本引用成功，真不存在的 ID 仍報找不到。讀取端（blocker 解除判定、runqueue、complete 反向解鎖）由後續子票處理。

**Version**: 2.42.3（本地變更，指向 tarrragon/claude#77）— `complete` 內建 auto-commit 只在工作日誌本次確實寫入時才把它列入提交範圍：`append_worklog_progress` 回傳 bool（True＝本次寫入；檔案不存在、冪等跳過、無日期標題區段、寫後驗證失敗、例外皆 False），`complete()` 據此決定 `modified_paths`。此前無條件列入，工作日誌未變更時 `commit_files_isolated` 自我驗證（實際變更須等於預期）失敗，整批提交放棄，連票面 md 也未提交。`commit_files_isolated` 的自我驗證不放寬（影響所有呼叫端）。`track_batch` 忽略回傳值，不受影響。E1 對照測試：同批 fixture 下追加回傳 True／False 兩案，提交範圍的工作日誌成員不同。

**Version**: 2.42.2（本地變更，指向 tarrragon/claude#55）— `ticket track commit` 將票自身 md 視為隱含可寫範圍：ANA 票 where.files 預設唯讀，導致無法提交自己的票面（誤報「未宣告任何寫入路徑」）。輸入僅票自身 md 時放行；輸入含其他路徑時判定不變（宣告為空仍沿用原錯誤與 ANA `::write` 說明，非票面路徑仍整批拒絕）。E2 對照測試：票自身 md 放行、票自身 md 搭配非票面路徑拒絕。

**Version**: 2.42.1（本地變更，指向 tarrragon/claude#102）— `acceptance_auditor._check_spawned_recursive` 改以衍生票自身 ID 的版本前綴載入 spawned（`extract_version_from_ticket_id`，取不到才退回父票版本），修復建在其他版本的合法衍生票在 complete ANA 票時一律被判 `not_found` 的問題（此前只能整批 `--yes-spawned` 放行）。`_check_children_recursive` 不受影響（children ID 恆以父票 ID 為前綴）。E1 對照測試：同批 fixture 下跨版本存在與真不存在兩案結果不同。

**Version**: 2.42.0 — `migrate` 碰撞行為改為改號而非拒絕：實際執行階段（無 `--force-overwrite`）目標 ID 已存在時，改取目標版本同 Wave 下一可用序號完成遷移，並於改號後票面寫入 `migrated_from: <原目標 ID>`；dry-run 對碰撞改判 FAIL（原為可放行的 WARNING）並印改號預覽，供 `version-release finish --dry-run` 對前移撞號提早止血。`--force-overwrite` 覆寫語意不變（仍記錄 audit log 後覆寫）。批量遷移移除碰撞 pre-scan fail-fast——碰撞不再是需要整批擋下的失敗，改由每筆遷移各自對當下檔案系統狀態判斷並改號，天然支援批次內連環碰撞（前一筆改號後的新目標仍會被下一筆的碰撞檢查看見）。動機：多 PM 或跨版本並行建票時，`finish` 只換版本前綴保留原序號，撞號必然發生；過渡期僅能人工遷到空號。

**Version**: 2.41.0 — 版本溢出目標規則改為優先路由至最近的「開放後繼版本」（todolist.yaml 中版本號較大、狀態 planned/active 且未 `scope: frozen` 者），未命中才依動詞算 patch+1／minor+1；`_suggest_next_patch` 對未凍結的 active 版本同步改為直接建議該 active，不再誤算未在 todolist.yaml 註冊的 patch+1（新增 `find_open_successor`，`references/create-command.md`〈版本範圍凍結硬閘門〉溢出目標表同步更新，WRAP canonical #55，2026-09-23）。

**Version**: 2.40.1 — `references/create-command.md`〈版本範圍凍結硬閘門〉三個範例的 `--where` 值由具體檔名改為 `<path>` 佔位符：具體檔名在 consumer 專案不存在，sync 守衛判為失效引用而中止推送；佔位符同時避免讀者把示意值當可複製的實值（2026-09-23）。

**Version**: 2.40.0 — 新增 `set-scope-blocker <id> --reason <text>|--clear` 子命令：事後設定或清除 frontmatter `scope_blocker` 欄位，`--reason`/`--clear` 互斥、空字串理由視同未給同樣拒絕。動機：`scope_blocker` 原僅在 `create` 建票當下可寫入（`--scope-blocker`），凍結前已存在的必要 pending 票沒有建立時機補這個欄位，發版檢查（依 `scope_blocker` 區分阻擋與前移）會把它們誤判為可前移，必要工作因此被搬到下一版本。配套 `.claude/pm-rules/version-progression.md`〈版本生命週期〉凍結步驟補「回溯標記既有必要票」動作。詳見 `references/track-command.md`〈UPDATE 操作〉、〈CLI 可修改欄位 vs 手動編輯欄位〉。

**Version**: 2.39.0 — `create` 版本註冊檢查放寬收 `planned` 版本（原僅收 `active`），修補 2.38.0 版本範圍凍結閘門提示的出路「先登記下一版本再建票」成為死路的問題——剛登記的版本狀態必為 `planned`，原判準仍會拒絕。動機：執行早已與版本解耦（生命週期模組對版本狀態零檢查），「planned = 要等啟用才能執行」的前提不成立。`VERSION_NOT_ACTIVE` 訊息改寫為「只有 planned 或 active 版本可建票」；`completed` 版本仍拒。同時退役 `_suggest_next_patch` 相對「最新已完成版本」計算版本歸屬引導的舊基準——版本推進後對非功能動詞根票恆建議未註冊版本，且與凍結閘門印出的溢出目標互相矛盾（基準不同源），改為相對 active 版本 patch+1，與 `suggest_overflow_version` 同一基準。`--scope-blocker` 放行理由新增持久化為 frontmatter 選填欄位 `scope_blocker`，供發版側查詢哪些票被明確放行進已凍結版本。詳見 `references/create-command.md`〈版本範圍凍結硬閘門〉、`references/field-semantics.md`〈scope_blocker 欄位語意〉。

**Version**: 2.38.0 — 新增 `create` 的版本範圍凍結硬閘門：`docs/todolist.yaml` 版本條目新增選填欄位 `scope`（值 `frozen`；缺席即開放，向後相容），目標版本凍結時，無 `--parent` 的根票被阻擋，訊息含相對凍結版本計算的溢出目標（IMP 且新功能動詞 → minor+1.0，其餘 → patch+1）與二擇一處置；`--scope-blocker` 須帶非空理由才放行，僅給旗標或空字串仍阻擋；`--parent` 子票繼承父票版本不經此閘門。動機：0.1.0 pending 池 83 張無法分辨必要與非必要，現有版本歸屬引導只有「功能 vs 修復」一個軸，缺「目標版本現在還收不收票」的軸。形態比照 2.36.0 可攜問題分流閘門（正交，同在 create 驗證層）。新增 `is_version_scope_frozen` / `suggest_overflow_version`（`lib/version.py`）、`validate_version_scope_gate`（`lib/field_validators.py`）。詳見 `references/create-command.md`〈版本範圍凍結硬閘門〉。

**Version**: 2.37.0 — 新增 `restore` 子命令：`closed` 票唯一合法出邊（closed -> pending），修補三條路同時封死的死局（`release`/`claim` 被 enum-gate 擋下、ticket md 直接 Edit 被 `ticket-file-access-guard-hook` 阻擋）。`--reason` 必填，落地清除 `close_reason`/`close_reason_note`/`closed_by`/`closed_at`/`completed_at` 五個 close 相關欄位，並寫入 `restored_at`/`restored_by`/`restore_reason` 還原記錄，走 auto-commit。`STATUS_TRANSITIONS` 新增 `closed -> pending` 唯一出邊，僅供本命令觸發：`release` 另補 app-level guard 明確拒絕 closed 票，`claim` 恆將 closed 導向 `in_progress`（不在新開放出邊內）——兩者對 closed 票仍被擋下，測試各附一個該紅輸入驗證。動機：一次誤判判準的關票掃蕩誤關 11 張執行票，而 closed 原無任何還原路徑，不可逆操作配上會誤判的判準等於把誤差率轉成永久損失。

**Version**: 2.36.0 — 新增 `create` 的可攜問題分流硬閘門：`--where` 全數落在 `.claude/` 之下時視為可攜問題（根源在框架通用資產，合法收件方是 canonical framework issue 非本地 ticket），未帶 `--dedup-checked` 查重結論即 `[ERROR]` + `exit 1` 阻擋。動機：單一 session 內新建多張票，其中半數以上的問題在 canonical 已有 open issue 卻全程未查重；既有的 where.files 撞檔熱度提示（僅警告）已證實對此類失效無效。`--dedup-checked` 的值即查重結論本身（issue 號或 `none`），純旗標存在不放行。新增 `is_portable_where_files` / `validate_portable_issue_gate`（`field_validators.py`），僅做路徑層級機械判準，不判斷 why 欄語意。**阻擋訊息明寫「命中 issue 不等於不該建票」**：`framework-issue` 的模型是「ticket 記執行，issue 記問題」，命中既有 issue 後仍須判斷本票是記錄/分析問題（observe 附加、不建票）還是執行該 issue 解法的程式碼變更（issue 號即查重結論，仍應建票）——此區分本身無法自動判準，發生在本票初次落地時：路徑判準字面上會擋下這張票自己（`where.files` 是純 `.claude/` 的 `create.py`），原始訊息文字誤導成「命中即不建票」，經一次誤關閉票的實例修正。詳見 `references/create-command.md`〈可攜問題分流硬閘門〉。

**Version**: 2.35.0 — 累積四項先前已落地但版號未遞增的修法，本次補記。(1) `create --no-topic` 改以哨兵短路 S1／S2 自動推導：原本旗標只在報告層生效，上游繼承路徑仍會指派主題，旗標對該路徑等同空操作。(2) ref 鎖重試條件與鎖齡判讀（`lib/git_ops.py`）：區分並行活鎖與崩潰殘骸，殘骸不自行移除而是回報鎖檔內容與鎖齡供溯源，並在 HEAD 於提交期間被並行移動時給出明確訊息。(3) `add-acceptance` 剝除誤帶入的核取方塊前綴並補 help 說明，附迴歸測試。(4) `create` 一律回報本次存入的驗收條數與逐條內容，使「存進去的與打算存的是否相同」不需另外查詢即可核對。另含 `track_dispatch_validate` 合理性檢查的判準調整與 `topic_inference` 的對應更新，測試同步新增。

**Version**: 2.34.0
**Last Updated**: 2026-09-08
**Status**: Completed

**Change Log**:

- v2.34.0 (2026-09-08): `hook-liveness` 以檔名查詢不再回 0 筆，且查無時的訊息不再與「hook 未觸發」同形
  - **成因**：`resolve_hook_name` 只認 `HOOK_NAME` 常數，但 82/122 個 `.claude/hooks/*.py` 是把字面字串直接傳給 `run_hook_safely(main, "...")`（與常數寫法互斥不重疊）；輸入為不含 `.py` 的檔名 stem 時完全不觸發檔案解析。實測 82 個有內部名稱的 hook：30 個檔名與內部名稱一致、51 個僅差 `-hook` 後綴、1 個結構性不同（`task-dispatch-readiness-check` 對 `agent-dispatch-check`）
  - **修法**：改以掃描 `run_hook_safely` 呼叫的字面參數為第一優先權威來源（那正是 liveness `hook` 欄位的實際寫入值），並新增「輸入不含副檔名時嘗試 `.claude/hooks/<輸入>.py`」的解析層。兩類不一致收斂到同一條「找到真實檔案、讀真實原始碼」路徑，**未採去後綴啟發式或硬編碼對照表**——啟發式涵蓋 51 個但會在第 52 個身上靜默回 0，複製本次要消除的失效
  - **訊息**：0 筆結果依解析來源是否「已由原始碼確認」分流。未確認時列出已嘗試的全部解析形式並明寫「0 筆不代表 hook 未觸發」，不再把 hook 未觸發列為候選解釋。查詢工具的失敗形態不得與它要偵測的失敗形態同形——否則驗證者可能去修一個沒壞的 hook，或撤掉一個正在運作的防護
  - TDD：還原舊實作驗證 11 個新測試 RED，修復後 21/21 GREEN

- v2.33.1 (2026-09-08): `--prune` 的寫入路徑改走框架 lib 的共用協定，修掉兩個獨立缺陷。前一版新增票終態判準提高了 `--prune` 的使用頻率，使既有缺口的暴露面隨之放大
  - **lost update**：原本 `_prune_stale_orphan_entries` 是無鎖純函式，其輸出直接餵進 `dispatch_file.write_text(...)`，讀取到寫入之間他方 `record_dispatch` 新增的記錄被整批覆蓋。紅燈測試先重現此競態（謂詞在鎖內卡住、另一執行緒同時寫入，修法前 `descriptions` 被清空）
  - **非原子寫入**：`write_text` 直寫在同一檔案系統內非原子，無鎖讀端（`is_file_under_dispatch` 等查詢路徑）可能讀到截斷內容。此問題在框架 lib 的 `_write_state` 早已改為暫存檔 + `os.replace` 修掉，本路徑仍停在修掉之前的形態
  - **修法**：刪除 `_prune_stale_orphan_entries`，改以 `_make_prune_predicate`（同一 A/B 判準，改為逐條 closure）傳入框架 lib 新增的 `prune_dispatches`，由後者在既有 `_state_lock` 內完成整個 read-modify-write 並沿用 `_write_state`。**不在本 skill 重新實作鎖與原子寫**——同一份狀態檔已有兩個寫入者，再加一份實作只會讓下一個寫入者重蹈覆轍
  - 模組不可用時 fail-open（跳過清理並寫 stderr），不回退到舊的不安全寫入
  - 已知取捨：謂詞 `_is_ticket_terminal` 會讀票檔，該 I/O 現在在鎖內執行，鎖持有時間變長。對 `--prune` 這類手動低頻命令方向正確；若日後搬到高頻路徑需重新評估

- v2.33.0 (2026-09-08): 派發記錄的清除改由事件觸發，不再只靠逾時。既有的 `cleanup_expired`（`turn_ended_at` 已設者 TTL 24 小時、未設者以 `dispatched_at` 起算 1 小時）會把記錄清光，但清光之前的窗口內，共用 git index 的並行守衛把已完成票的宣告當現行範圍，落在該範圍內的提交被誤擋且訊息指向早已結束的票（實測一次提交被迫拆成三次）
  - `complete()` 成功路徑呼叫 `_clear_dispatch_for_completed_ticket(ticket_id)`，fail-open（模組不可用或例外皆寫 stderr，不阻擋 complete）
  - `dispatch-check --prune` 新增獨立的票終態判準（`_is_ticket_terminal`），與既有「`[STALE]` 且 session 確認不存在」判準為 OR、互不依賴，且不受 registry 可用性影響
  - 驗收採反事實形式而非「全量記錄清空」：後者在不修任何東西的情況下等滿 TTL 也會成立，分不出修法生效與時間到了。落地的兩則測試各自構造距 TTL 邊界甚遠的記錄（`turn_ended_at` 設為呼叫當下；空 `ticket_id` + `dispatched_at` 65 分鐘前），斷言事件觸發後立即消失，全程不呼叫 `cleanup_expired`
  - 新增 `tests/test_complete_dispatch_cleanup.py`；`test_track_dispatch_check.py` 增 `TestIsTicketTerminal`／`TestPruneTerminalTicket`
  - 配套的 `clear_dispatch_by_ticket_id` 在框架 lib（非本 skill），空字串一律無操作以保護無票派發記錄那一類

- v2.32.1 (2026-09-08): `fields.py`／`test_fields_set_where.py`／`test_identity_guard.py` 隨框架 canonical 更新（由另一 consumer 撰寫並經 canonical 傳入）；本專案取回後補號，前一版兩側同號而內容不同

- v2.32.0 (2026-09-08): PM 先 claim 再派發時的身份死結補上自動出口。**本批由另一個 consumer 專案撰寫並經框架 canonical 傳入**，本專案取回後補號——兩側先前同標 2.31.1 而內容不同，依版號無從察覺
  - `complete`／`finish` 在身份對照之前，若 `who.current` 仍是 PM 且 `--as` 申報為具名非 PM 執行者，自動把 `who.current` 讓給該執行者再走既有比對（`reassign_who_from_pm_if_takeover`）。原本兩條路都不通：帶 `--as` 被判身份不符，不帶 `--as` 被要求必須提供，而 `who` 是權責歸屬欄位不該由執行者自行 `set-who` 繞過
  - 派發時另有一道事前防線（`dispatch-identity-bind-hook`），把 `who.current` 由 PM 改綁為實際派發的 subagent；本批的 complete 前置讓出是 worktree 隔離派發等前者未觸發時的保底
  - deny 訊息改為直接印出 `who.current` 當前值而非占位符——該值因票而異，派發者無法預知，沿用經驗寫死 `--as rosemary-project-manager` 反而會撞上身份不符
  - 新增 `tests/test_pm_takeover_reassignment.py`

- v2.31.1 (2026-09-08): `track-command.md` 兩處跨檔指涉隨 worktree skill 的內容外移同步更新——原指 `worktree/SKILL.md` 的節與行號，改指其 `references/agent-isolation-worktree.md` 的具名章節。內容變更本身發生於 2.31.0 推送之後而版號未動，兩側同號異容，本版補號使分歧可由版號察覺

- v2.31.0 (2026-09-08): 異源交換掃描的修法群——由另一個並行 session 拿同一份判準重掃本 skill，回報漏抓 8 則、誤判 6 則、已報未修 10 則，本版落地其可執行部分
  - **CLI**：`dispatch --dry-run` 輸出首行加 `[DRY-RUN 未落票]` 浮水印（正式骨架逐字不變），使貼進 prompt 的骨架可辨識是否曾落票；`dispatch` 不論有無 `--note` 一律把 `dispatch-readiness`／`dispatch-validate` 的 exit code 寫入派發日誌，取代原本無痕跡的分支；`dispatch-check` 新增 `--prune`，僅清理「`[STALE]` 且 `session_id` 確認不在 registry 內」的條目，`session_id` 為空或 registry 不可用一律保守保留，結果雙通道寫 stderr 與 hook 日誌。三者的共同形態是「認真做過與完全沒做，產物無差別」
  - **文件與實作對齊**：`architecture.md`〈術語〉鑑識三查改為第 3 查（缺 Exit Status）為 soft warning 不計入拒絕（對齊 `lease.py` 的 `GhostReport.clean`）；`complete` 對 pending／blocked 的 exit code 三檔統一為 2（對齊 `lifecycle.py`）；子任務未全完成為阻擋（exit 1、`--force` 可旁路），非原文的「交接流程」
  - **接手身份規則**：原文「接手時不改寫 `who.current`」與 `complete` 強制 `--as` 合成後，把非原持有者逼向冒用他人身份這條唯一省力路徑。改為明訂兩條路——PM 接手走既有豁免；代理人接手先 `set-who --current <self>` 再 `--as <self>`，並註明 `set-who` 不寫 `who.history`，接手事實須自行留痕
  - **同檔邊界**：〈track commit 子命令〉新增一節說明隔離索引只隔離共用 index、不隔離同一檔案的工作區內容——兩票宣告同一檔案時仍整檔取用，會吸入他票未提交的編輯（本批實測命中一次）；含偵測法與處置，並與框架的檔案內夾帶邊界互指
  - **指涉閉合**：`resume-command.md` 兩處不存在的 `ticket track handoff` 改頂層 `ticket handoff`；`--as` 支援清單訂正為六命令；`depth` 兩套基數（frontmatter `chain.depth` 根為 0、`track depth` 根為 1）各補互指與誤用後果；`create` 的 `--when` 必填補進文件；`migrate` 訊號表主詞、`handoff` 歷史值具名、`create`／`workflow-create` 的數量縮略等九處修正

- v2.30.1 (2026-09-08): `batch-create` 的版本自動偵測改與 `create` 同源——原先只讀 `--version` 未給即報「無法偵測版本」，現改呼叫 `lib/version.py` 的 `resolve_version()`，同一專案結構下兩命令行為一致；明確指定 `--version` 時仍以指定值為準
- v2.30.0 (2026-09-08): 拆分後續兩批修法（冷讀審查與 CLI 缺陷群）；SKILL.md 全檔 4,992 tokens、167 行，路由表雙向零命中
  - **CLI**：`set-blocked-by`／`set-related-to` 多值位置參數 help 明示引號包裹並附 epilog 範例；`track dashboard` 的 `[Handoff Target]` 改走 `resolve_target` 與 `resume --list` 一致，`is_handoff_stale` 補 closed 判定（`--gc`／`--from-worklog`／`resume --list` 共用），`create` 新增 `--dry-run`；`track list` 對 in_progress 列渲染與 dashboard 同源的 lease 標記（`lease.format_lease_tag`），`complete`／`finish` 的 `--as` help 改為強制 deny 語意；`AuditReport` 新增 `artifact_who`／`artifact_updated` 並於 `track audit` 輸出「執行者｜最後更新」行；dashboard auto-GC 歸檔寫持久日誌（`hook-logs/handoff-gc/`），Stop hook 的 stale handoff 由刪除改為歸檔並處理同名碰撞
  - **文件**：入口檔補五詞術語路由、路由表 field-semantics 用途欄與 root 分離節條件語意修正、裸 `complete` 範例補 `--as`；`architecture.md`〈術語〉鑑識三查第 3 查改為 soft warning（對齊 `lease.py`）並補三詞；三檔 `complete` 對 pending／blocked 的 exit code 統一為 2（對齊 `lifecycle.py`）；`track-command.md` 新增〈子命令總覽（全量對照 --help）〉涵蓋 89 個子命令，1-E 斷言支撐 F4–F17 補來源，`--as` 支援清單訂正為六命令；`resume-command.md` 兩處 `ticket track handoff` 改頂層 `ticket handoff`；`migrate`／`handoff`／`create`／`workflow-create` 指涉閉合與計數縮略修正；`create-command.md` 量測值補方法與環境
- **拆分總結**（依 skill-design-guide 重整，issue tarrragon/claude#94；來源：拆分系列，跨 v2.22.0–v2.29.0；before 取自重構前快照 `8f634fa43`，after 為本輪收尾實測）：入口檔 `SKILL.md` 全檔（含 frontmatter）14,347 → 4,971 tokens、body 14,133 → 4,875 tokens（框架分段估算公式：非 ASCII 1.3 字元/token、ASCII 4 字元/token；Progressive Disclosure 第 2 層門檻對象為全檔，< 5,000）、593 → 167 行、frontmatter `description` 596 → 224 字元、`##` 節數 12 → 5、`references/` 檔數 15 → 14；子命令路由表〈涵蓋章節〉欄與各 `references/*.md` 的 `##` 標題逐字雙向比對零命中（fenced block 排除）。逐版異動見下列各條目。
- v2.29.0 (2026-09-08): 同步 Round 3 CLI 缺陷修復群六項行為變更至文件（skill-cli-sync-check）
  - **track commit 目錄展開排除他票宣告檔案**（3-B B1）：〈track commit 子命令〉「files 子集規則」補「目錄展開的並行過濾」段，說明展開時讀取 `.claude/dispatch-active.json` 排除其他活躍派發宣告路徑的變更檔（並行防護加強層，非安全邊界本身；registry 讀取失敗 fail-open）
  - **track commit 空 tree 短路提示 --worktree**（3-H 案 3）：同節「Exit code」表的 exit 0 說明句更新為與實際 stdout 字面對齊，含「若變更實際發生在 linked worktree 但未帶 --worktree……」提示句
  - **track set-exit-status 加 --as／who.current 身份檢查**（3-F F3）：〈track set-exit-status 子命令〉Flag 說明表補 `--as` 列，並新增「`--as` 身份檢查與 `--force` 的邊界」段，說明未帶 `--as` 維持 warn-only、`--force` 不可旁路身份不符的 deny
  - **track reclaim --confirm 落地鑑識報告**（3-F 共用原則項目 5）：〈track reclaim 子命令〉「Exit code」後新增〈`--confirm` 落地：鑑識報告寫入 Solution〉子節，說明三查全過且 `--confirm` 落地後 append-log 進票面 Solution，落票失敗不影響 reclaim 本身狀態轉換
  - **track dispatch-check 新鮮度維度**（3-H 個案 1／2）：〈track dispatch-check 子命令〉「判定規則」表補新鮮度標註欄位，新增「新鮮度標註」段（沿用 `DEFAULT_STALE_THRESHOLD_MIN` 60 分鐘慣例，`(Nmin)`／`[STALE Nmin]` 兩態，逾時彙總行），「WARN 後下一步」段同步改寫（原「本命令不判斷條目是否逾時」已被新行為取代）
  - 逐項以 `ticket track <子命令> --help` 實跑核對旗標與字面；SKILL.md 路由表對應列摘要層級未含受影響細節，未發現需同步的不一致，本次不變更
- v2.28.0 (2026-09-08): 零住址前提承接章節（3-G G1／G4／G5、3-D P4）
  - **G1 where.files 宣告語意**：`field-semantics.md`〈適用範圍〉新增〈where.files 宣告語意〉子節作唯一住址（`::read`／`::write` 後綴、type 預設意圖、目錄型宣告展開／WARNING／dispatch 硬擋，來源 `ticket_system/lib/file_conflict.py`）；`track-command.md` 六處（`track commit`／`track dispatch`／`track runqueue --groups`／`track conflicts` 判定規則 4／`track onboard` 髒檔歸屬／`track dispatch-readiness` 閾值 2 檢查 5-6）與 `create-command.md`〈多值參數格式〉各追加一句指回新住址，各自角度不變
  - **G4 registry 契約住址**：`track-command.md`〈track sessions 子命令〉〈Registry 位置與 Schema〉補「契約住址」條目，明指 `.claude/lib/pm_registry.py` 檔頭 docstring 自稱「Registry Schema 契約 v2（單一來源）」為 schema 唯一權威
  - **G5 Exit Status→handoff JSON 橋**：`resume-command.md`〈handoff JSON 格式〉新增〈`exit_status` 欄位〉子節，說明 `ticket track handoff` 建立 JSON 當下讀來源 ticket body `## Exit Status` 章節（`handoff.py:_extract_exit_status_for_handoff`）並抽取寫入，列出寫入端／橋接端／兩個讀取端（`runqueue --context=resume` 讀 JSON；`reclaim` 第 3 查直接讀票面，不經橋接）四角色分工表
  - **P4 並行協調入口**：`SKILL.md`〈子命令路由表〉「（跨子命令）」列補一句指名 `.claude/pm-rules/parallel-dispatch.md`〈並行安全檢查〉與 `.claude/references/cross-session-coordination-details.md`
  - 反證方法：四項各先 `rg` 全站（pm-rules／references／methodologies／rules／hooks docstring）確認無既有住址後再建章／改路由

- v2.27.0 (2026-09-08): multi-round-review Round 3 修法（群 D-3：resume/generate 槽位名、三檔 footer 清理、acceptance-gate 表改實作分支、handoff 狀態表統一載體、workflow-query/execute 亦由此進入、4V/建立範本欄名對齊；併吞範圍重疊的驗收表覆核票，已標記 superseded 並 close）
  - **槽位名統一**（R-8）：`resume-command.md`／`generate-command.md`〈參數說明〉→〈Flag 說明〉，與其餘檔案一致；`SKILL.md` 路由表 `resume`／`generate` 兩列涵蓋章節欄同步
  - **Footer 清理**（3-A R5）：`field-semantics.md`／`handoff-command.md`／`ticket-lifecycle-details.md` 三檔尾 Last Updated／Version footer 整段刪除（歷史已在本檔 v2.22-2.25 條目載明）；`field-semantics.md` 初版 Source（ANA 多視角審查衍生的 SSOT 建立票，見該檔〈溯源〉段）移入該檔檔頭〈溯源〉段保留
  - **acceptance-gate-hook 技術細節改為實作分支**（3-H 必修 2）：`ticket-lifecycle-details.md`〈acceptance-gate-hook 技術細節〉檢查邏輯表改依 `check_acceptance_status()` 實際 5 個阻止情境（children 未完成、防護類 hook 票缺必含項、ANA spawn 規劃不一致、`multi_view_status` 值非法、實驗器材殘留）與 2 個警告情境（驗收記錄缺失、ANA 缺後續 ticket）改寫；舊「根任務／子任務分列」「所有子任務是否驗收」判準與程式碼無對應函式，已移除；阻止／警告場景固定文字範例（與實際訊息不符）改為指向對應 checker 模組；補「驗收方式判準」段說明僅 priority P0 且非 DOC/ANA 才提醒派 acceptance-auditor、subagent 呼叫一律略過提醒改由 PM 於 complete 後補派；〈驗證結果對應表〉更正為 `lifecycle.py complete()` CLI 層級（非 hook 層）之驗證結果，`pending`／`blocked` 狀態 Exit Code 由誤植的 1 修正為 2（`precondition.require_in_progress()` 實際回傳值）；〈驗收提示訊息模板〉三段固定文字模板（暗示驗收為前置關卡）改為條件分支表（對齊 `AskUserQuestionReminders.COMPLETE_REMINDER`／`COMPLETE_NEXT_STEP_REMINDER` 實際觸發條件）
  - **handoff 狀態→旗標兩表統一載體**（3-G D）：`handoff-command.md`〈按 Ticket 狀態選擇命令〉6 列表為載體，補回原缺的「`in_progress` 使用 `--to-sibling`／`--to-parent` CLI 拒絕」禁止行為列；`workflow-handoff.md`〈狀態-命令映射規則〉節內容改為一行指回 `handoff-command.md`，決策樹本身不動
  - **workflow-query／workflow-execute「亦由此進入：無」改寫**（3-A）：grep 反證顯示 `workflow-create.md` 首段引言句實際把讀者送到兩檔（任務已存在時改讀），兩檔檔頭改列此指標
  - **4V 節與建立範本欄名對齊**（3-G 小型）：〈驗收條件 4V 格式要求〉「標準格式」改為 frontmatter `acceptance` 清單示例（`set-acceptance --add`／`check-acceptance`，全 skill CLI 實際操作對象），原 body 表格式改標「報告格式（僅供人工呈現，CLI 不讀取）」；〈Ticket 建立格式範本〉frontmatter `assignee: pending` 改為 `who: {current: pending, history: {}}`，對齊 `track-command.md`〈CLI 可修改欄位〉與實際 ticket frontmatter 結構
- v2.26.0 (2026-09-08): multi-round-review Round 3 修法（群 D-1：SKILL.md 空殼節、reclaim 拒絕處置句、SessionStart hook 入口對齊、architecture.md 類比與術語指標）
  - **空殼節降級**（PM 通讀 R-1）：`## 系統模型（設計自我描述）`、`## Ticket Body Schema（type-aware）` 兩個僅剩一行路由的空殼節整節刪除，內容已分別由〈子命令路由表〉「（跨子命令）」列與表後既有一句涵蓋，不重複維護；入口檔 `##` 節數由 7 降為 5
  - **執行方式節首**（R-2）：去除與標題同名的粗體標籤「**執行方式**：」
  - **孤立來源句改寫**（R-3；3-D P1）：`> 來源：v2.7.0` 改為說明句，明寫 `track onboard`／`track runqueue` 為輔助／除錯入口、裸 `/ticket` 一律先走本節 dashboard-first 流程，版本沿革改指本檔 v2.7.0 條目
  - **他專案殘留措辭**（R-4）：`batch-create`〈使用情境〉的「W28 場景」改為通用措辭
  - **reclaim 拒絕處置句**（R-5；3-F F3；用戶裁決 D2）：刪除「補 `set-exit-status`」SOP（該動作等同接手者為他人票製造第 3 查通過條件，與實作第 3 查為 soft warning 不符），改為「拒絕：即停手回報 PM」
  - **身份句可執行化**（R-6）：「身份仍為 who.current」改為「接手時不改寫 `who.current`，依票面既有身份繼續操作」
  - **SessionStart hook 入口對齊**（3-B B3）：`:79` 除錯查詢句改寫為「兩支 SessionStart hook 會在用戶輸入前先印出此類提示作為歷史入口，PM 實際接手流程仍以 dashboard-first 為主」，不再宣稱「不再呼叫」（與 hook 實際輸出相符）
  - **track 子族選列判準**（3-B (1)）：路由表引言補一句宣告子族獨立成列的判準（具獨立 exit code 語意或需額外理解流程分支者才獨立成列，其餘於 track-command.md 以 `##` 子節呈現）
  - **選樹閘門**（3-G G3）：路由表後補一行「依處境選樹」對照（新任務／已認領／查現況／交接恢復／改 ID 各自對應的 workflow-*.md）
  - **路由表用途欄補齊**（重組後遺症可改）：create-command／workflow-query／track-command／handoff-command／migrate-command 5 列的第二列用途欄補回差異化「何時讀」句
  - **術語節指標前移**（3-A R4）：檔頭引言句補系統模型與術語指標，確保 `票面`／`接手`／`鑑識三查`／`落票`／`隔離索引` 等詞在 SKILL.md 內首見前已有 `references/architecture.md`〈術語〉指標（原指標隨系統模型節刪除而移除，改置於檔頭引言）
  - `references/architecture.md`〈系統模型〉補「類比邊界」說明（3-B (4)）：CI runner 類比僅在「身份晚綁定」「type/instance 一對多」成立，「共享工作區」為本系統相對 CI runner 隔離慣例的反向自身選擇，不在類比射程內；同節「named agent 生命週期三態」下「idle 態」段原「工作區仍隔離」與此矛盾，同步修正為「工作區仍為預設 2 的共享語意」
  - `references/architecture.md` `### named agent 生命週期三態` 標題後綴 `（v2.9.0 擴展）` 移除，溯源改節首「> 來源：」句（3-A R5 種子後綴殘留第 3 處）；檔頭「亦由此進入」對 SKILL.md 系統模型節末的指涉同步改為「SKILL.md 檔頭引言」（原節已刪除）
- v2.25.0 (2026-09-07): multi-round-review Round 2 修法（群 C2b：`track-command.md` 九個子命令節設計敘事後置、共用旗標節、槽位名統一、五檔 H2/H3 段標溯源後綴刪除、`messages.py` 落地 `architecture.md`）
  - **段標溯源後綴刪除**（17 處，決策：後綴對讀者零價值，溯源移各節首行「> 來源：……」）：`track-command.md` 11 個子命令 H2；`resume-command.md`〈恢復機制〉；`handoff-command.md`〈指向語意：source vs target〉+ `--from-worklog` 子命令 + `--next` 子旗標；`migrate-command.md`〈Collision Detection〉；`SKILL.md`〈無子命令時的預設行為（dashboard-first）〉。三面同步（各檔本檔章節行、`SKILL.md` 路由表涵蓋章節欄、`SKILL.md` 正文逐字引用）已以 fenced 外雙向 awk 比對驗證零命中
  - **九子命令節設計敘事後置**（`track-command.md`，2-D finding F8-F17）：`runqueue`（第二層加權改寫為 PM 手動判斷規則、`--groups` 演算法段後置為〈判定機制〉子節、實作沿革行移本檔）；`UPDATE 操作補充`（complete 副作用自辯句刪、title/what 量測移本檔、claim 半成功歷史背景移本檔）；`board`（`--group-by topic` 選型論證改選用對映表）；`dashboard`（tool call 量測移本檔，節首壓一句）；`reclaim`（判準句提前粗體、差異溯源句壓縮）；`activity`（父子票邊界演算法敘事壓成判準句，機制指向 `track_activity.py` 註解）；`conflicts`（lead 動作先行、Python 測試路徑推導演算法壓成規則句）；`onboard`（lead 動作先行、髒檔歸屬設計改輸出判讀對映表）；`hook-liveness`（〈動機〉子節名改〈0 筆結果的判讀〉）
  - **共用旗標語意（track 系列命令通用）**：新增章節統一定義 `--all`（無作用旗標）與 version-agnostic 註冊機制，六個掃描全部 active 版本的命令原逐段重複說明改為指標；「復用 X，不重 Y」7 處僅首例保留完整句，其餘只留「復用 X」
  - **槽位名統一**：`track-command.md`〈track board〉`選項說明`→`Flag 說明`、兩處`設計邊界`→`設計約束`（與本檔其餘 9 處一致）；`migrate-command.md`〈選項說明〉→〈Flag 說明〉；`handoff-command.md`〈基本用法〉（僅一句）併入〈用法〉首句。`resume-command.md`／`generate-command.md` 的〈參數說明〉槽位維持原名——後者不在本批修改範圍，單改前者會製造新的不一致，留待涵蓋該檔的後續修法一併處理
  - **`messages.py` 落地**：`track-command.md`〈統一錯誤訊息格式〉〈CLI 錯誤分類〉112 行全文併入 `architecture.md`〈共用模組設計〉### messages.py，新增「統一錯誤訊息格式」「CLI 錯誤分類」兩子節（CLI 錯誤分類新增「訊息形態→處置對映」句，設計理由三條 bullet 標為「依據，非動作」）；`track-command.md` 原位改一句路由
  - **Footer 清理**：`workflow-handoff.md` 檔尾 Last Updated／Version／Source 三行整段刪除（`SKILL.md` 已宣告版本紀錄在本檔，內容與下方保留摘要重複）；`handoff-command.md` 檔尾歷史版本壓縮為單行 Version 摘要，歷史保留於下方
  - `handoff-command.md` 原檔尾歷史版本（供查閱）：

    > **Version**: 1.4.0 — multi-round-review Round 2 修法：〈Session 結束時的使用方式〉步驟 0 命令改 `--gc --dry-run`（`--status` 不列 pending handoff 檔，命令與宣稱目的不符）並補「殘留」判準；〈任務鏈結束時的替代流程〉重述〈設計意圖〉首句的粗體段改一句指標；〈同目錄〉移除跨檔重複公式，只留角色標籤
    > **Version**: 1.3.0 — 檔頭「亦由此進入」改指實際節內段落（〈交接流程決策樹〉節內「讀取端」段）；〈任務鏈結束時的替代流程〉粗體段標問句改直述；〈五種情境〉表補 `--next`（絕對指向）歸屬說明
    > **Version**: 1.2.0 — 設計意圖段補「設計原則」引用指向 `handoff-design-principle-methodology.md`
    > **Version**: 1.1.0 — 同步落地：新增「指向語意：source vs target」章節（含 target_ticket_id 欄位 + resolve_target 優先序）、`--next` 子旗標說明、`--next` vs `--auto` 對比表

  - `workflow-handoff.md` 原檔尾（供查閱）：

    > **Last Updated**: 2026-05-08
    > **Version**: 1.1.0 — 同步落地：交接決策樹新增「絕對指向（target_ticket_id）」分支，加入 `--next` 模式對比表與覆蓋指令

  - `track dashboard`〈設計目的〉原量測（供查閱）：

    > ANA 量測：原 `/ticket` 裸命令流程從入口到顯示待辦需 **7 個 tool call**（含 1 次 `--format` 試錯與 5 次可消除的重複呼叫）。Dashboard 將此降至 **3 個 tool call**（dashboard + claim by number + 後續動作），符合 `/ticket` 與 resume 系統「加速 PM 接手」的原始設計目的。

  - `track runqueue`〈實作現況〉原「典範」行（供查閱）：

    > 基礎 runqueue 實作；三視角審查（Evidence/Alternatives/linux）收斂結論；軸 C 補強 spawned 加權規則。

  - `track UPDATE 操作補充`〈title 與 what 是兩個獨立欄位〉原量測（供查閱）：

    > 2026-08-18 量測 741 張票，124 張（17%）兩者刻意不同。

  - `track UPDATE 操作補充`〈claim 推薦用法〉原「半成功歷史背景」（供查閱）：

    > 早期 `claim --yes` 在 subagent 無 TTY 環境曾因互動受限出現 metadata 部分寫入、需 `--skip-verify` 二次嘗試確認的半成功狀態。此 root cause 已由「claim 預設不驗證」+「移除 `--skip-verify`」兩階段修正消除；現行裸 `claim` 路徑無此問題。
- v2.24.0 (2026-09-07): multi-round-review Round 2 修法（群 C3：`create-command.md`／`field-semantics.md`／`handoff-command.md`／`resume-command.md`）。
  - `create-command.md`〈基本用法〉五則範例原皆缺必填的 `--acceptance`，四則另缺 `--where-files`——`ticket_builder.py` 的 `validate_create_checklist` 要求至少一項兩者皆備，缺任一項於持久化前 `exit 1`；五則範例已全部補齊。〈重複偵測（兩層防護）〉的 Tier 2 設計用途與 birth time 判定兩段教材，原置於 `--allow-duplicate` 旁路命令之前，改為被擋時判準句（先問「是同 turn 重複 spawn 嗎」）置於旁路子節首，教材壓成依據句。〈必填條件〉「必須提供」兩條列表項原分列，實為 AND 關係（讀者易誤讀成各自獨立充分條件），改為單句「建立根任務且 type 不是 DOC 時」；「可省略」（OR 關係）維持清單並註明任一成立即可省略
  - `field-semantics.md`〈阻擋語意對照表〉:145 `spawned_tickets`（ANA 類型 source）表格格原寫「過渡狀態，IMP 收斂後將移除」，與同檔 :150 現況分層說明（hook 層舊機制已退場為 warn-only，但 `lifecycle.py`／`acceptance_auditor.py` 兩獨立機制仍實際阻擋）矛盾——前次修法只改了說明段、表格格殘留舊字。表格格改為「是（`lifecycle.py` 確認關卡＋`acceptance_auditor.py` 稽核，已定案）」。blockedBy 節內 Action 三條原置於量測論證段之後，資訊優先序倒置，改為 Action 在前、量測壓成一句「依據：既有量測（2285 票語料，精準度上限 25%），見本檔」。relatedTo 節兩則「裁決（2026-08 定案）」決策紀錄原為完整論證段，壓成一句保留裁決本身，論證移入本則
    - blockedBy 量測完整論證（原文保留供查閱）：2285 票語料、913 筆「When 含 ID 且 blockedBy 空」母體、61 筆系統抽樣；43% 的提及屬出處／並行標記／反向依賴而非依賴；依賴語意組中 32/35 於建立當日前置已完成（follow-up 慣例，warn 無效益）；即使限定「提及票尚未 terminal 才警」，精準度仍僅 25%（3 真漏標對 9 誤警——母票 umbrella in_progress、並行標記、反向依賴為結構性誤警源，散文層無法可靠排除）。真實漏標率約 5%，已有接手端補償 SOP
    - relatedTo 裁決一（儲存方向）完整論證：維持儲存單向 + 消費端 1-hop symmetric union，避免下游工具漏失多數未回填關聯（實測 1246 票語料，僅 13.3% 對稱率，改無向儲存需回填既有邊成本），同時不承擔改為無向儲存所需的既有邊回填成本；反向索引工具實作為獨立追蹤項目
    - relatedTo 裁決二（context bundle 消費）完整論證：relatedTo 是 context bundle 的合法消費來源，非規範外行為。本裁決取代先前「relatedTo 不作為任何流程訊號」中隱含的「不被任何工具消費」推論——流程訊號（排程、阻擋、血緣）與 context 供給是兩件事，前者維持無，後者已由既有實作（`context_bundle_extractor.py` 的 `SourceKind` 含 `related_to`）承擔
  - `handoff-command.md`〈Session 結束時的使用方式〉步驟 0 原命令 `ticket handoff --status`，但 `--status` 顯示的是任務鏈與建議下一步，不列 pending handoff 檔，命令與宣稱目的（確認無殘留 pending handoff）不符；改為 `ticket handoff --gc --dry-run`（實測輸出「無 stale handoff，pending 目錄已清潔」正是此目的），並補「殘留」判準：僅指已完成票的 stale JSON，不含待接手者的合法 pending。〈任務鏈結束時的替代流程〉原有一段粗體「理由」重述〈設計意圖〉首句，改為一句指標「理由見〈設計意圖〉」
  - 四檔〈同目錄〉欄原用跨檔重複公式「與本檔互補：決策樹在那份、細節在本檔」，改為僅留檔名＋簡短角色標籤；`resume-command.md`〈溯源〉原長句「本機 git log 對本檔僅見這一筆……」（14 檔中 7 檔逐字重複的模具句，本檔無實質拆分點內容）改短記號「匯入時已存在（`f375ae675`），無拆分點」；`resume-command.md`〈恢復流程〉與〈用法〉內三處逐字相同的 dashboard-first 路由句，保留〈三個入口的分工〉（原〈設計原則〉，改名以符實際內容為三入口→行為對映而非教材框架）節內一處完整路由，另兩處改短指「走 dashboard-first」
- v2.23.0 (2026-09-07): `resume-command.md` 的〈歷史變更〉章節（v1.0→v2.0 顯式觸發變更敘事）遷入本檔，該檔內同段刪除；同批修正 `resume-command.md` 三處誤稱裸 `/ticket` 為「自動偵測 pending handoff」，改指 `SKILL.md`〈無子命令時的預設行為（dashboard-first）〉；`track-command.md` 修正片假名中點 `IO・YAML`（2 處）為 `IO／YAML`、〈runqueue 排序規則〉第二層 `spawned_from_completed_ana` 加權標明僅為規則面設計、CLI 尚未實作（`track_runqueue.py` 零命中）、Priority tier 表補上缺漏的 `P0` 層級、`dashboard` 子命令節補齊 `[LIVE]`／`[RECLAIMABLE]` 標記語意與輸出範例、統一「三章節」與實際「四區塊（含 Handoff Target）」的描述落差、`reclaim`〈設計取捨〉與 `onboard` 首段的否定起手定義句改寫為正面先立、口語「真的」3 處刪除（含 `field-semantics.md` 1 處）、`list` 子命令排序規則的括號並列形態統一；`field-semantics.md` 檔頭「亦由此進入」兩條指涉修正為實際節名（`create-command.md`〈--source-ticket 參數（衍生關係）〉、`track-command.md`〈UPDATE 操作補充：commit 副作用與欄位語意〉### 六欄位語意 SSOT）、〈相關文件〉的 `SKILL.md` 死指涉改指 `track-command.md`〈READ 操作〉〈track deps / depth 子命令〉；`field-semantics.md` 與 `create-command.md` 對稱兩處「阻擋為過渡狀態、後續 hook 收斂後將回到不阻擋」改寫為現況分層說明——hook 層舊版 spawned 檢查已退場為 warn-only，但 `lifecycle.py` 的完成前確認關卡與 `acceptance_auditor.py` 的 spawned 全完成稽核 FAIL 判定仍實際阻擋，此為已定案現行設計，非等待收斂的過渡態
  - `resume-command.md` 原〈歷史變更〉內容（供查閱）：v1.0 使用 `handoff-prompt-reminder-hook.py`（UserPromptSubmit）自動注入 Ticket 完整內容；v2.0 改為顯式觸發，理由是 Hook 自動注入會劫持用戶意圖（任何第一條訊息都被覆蓋），因此停用
- v2.22.0 (2026-09-07): `ticket-lifecycle-details.md` 的〈變更日誌〉章節（一次性歷史敘事，v2.0.0-v4.0.0）遷入本檔，該檔內僅留指標句；同批修正該檔 P0 節否定起手定義句、檔頭重複舊引言、驗收提示訊息模板的死名節引用、驗收條件來源範例改節名形式、建立範本 `type` 欄位對齊正典 4 型（IMP/ADJ/ANA/DOC，原列 RES/INV 兩型已移出正典）、與 `field-semantics.md` 同目錄互引不對稱；`handoff-command.md` 檔頭「亦由此進入」指涉段落改實際節內段落、任務鏈結束替代流程的粗體段標問句改直述、〈五種情境〉表補充 `--next`（絕對指向）不列入該表的歸屬說明
  - `ticket-lifecycle-details.md` 原 v2.0.0-v4.0.0 版本歷史（供查閱）：v4.0.0 瘦身重構移出至 details 參考文件（從 ticket-lifecycle.md 移出格式規範、訊息模板、Hook 技術細節，精簡版保留核心決策規則）；v3.1.0 統一驗收派發規則移除 PM 直接驗收；v3.0.0 將驗收流程從 complete 之後改為 complete 之前；v2.9.0 新增執行日誌驗證機制；v2.8.0 取消驗收豁免機制改為契約式驗收；v2.7.0 強化驗收代理人派發要求；v2.6.0 新增任務層級判斷規則；v2.5.0 新增階段-標準流程對照表和任務鏈後續步驟建議；v2.4.0 新增建議追蹤流程整合章節；v2.3.0 新增驗收條件格式要求章節；v2.2.0 新增任務鏈 ID 格式章節；v2.1.0 新增 Ticket 有效性驗證章節；v2.0.0 重構為 TDD 含 SA 前置審查流程版本
- v2.21.0 (2026-09-07): 補記 2.20.0 之後累積但未 bump 版號的變更。版號未動使發佈庫與本庫的內容分歧無法由版號察覺——版號相同時它主動宣稱兩邊一致，分歧因此不會被例行同步檢查發現，故補此一版號涵蓋下列各項
  - `track commit` 新增 `--worktree <path>`：把 read-tree / add / diff 等 git 操作綁定到檔案實際變更所在的 linked worktree。未指定時行為不變（沿用 `resolve_project_cwd()`）；指定但非合法 git 目錄時拒絕提交
  - `paths.py` 新增 `get_ticket_state_root()`：linked worktree 內執行的 ticket 狀態操作（`claim` / `append-log` / `check-acceptance` / `set-*` 等 md 讀寫與其 auto-commit）反向回推主倉庫根目錄，統一寫入主倉庫。`track commit`（程式碼提交）維持 worktree 感知不變，兩者是不同的 root 解析路徑。SKILL.md 新增「Ticket 狀態與程式碼提交的 root 分離」章節說明此差異，避免被誤判為 cwd 解析缺陷
  - `track dispatch-readiness` 由三項認知負擔閾值擴為六項檢查：新增檢查 4（acceptance 與寫入集一致性）、檢查 5（`where.files` 路徑存在性）為 warn-only 啟發式，檢查 6（acceptance 提及路徑須被 `where.files` 涵蓋）為強制 fail。exit 2 的處置依 fail 來源分流（閾值 1-3 超標為拆票，檢查 6 為補 `where.files` 或改寫 acceptance），不依 CLI 統一提示行字面行事
  - `track conflicts` 新增 `--for <id>` 與 `--among <id1,id2,...>` 針對性查詢（`file_conflict.compute_targeted_conflicts`），並行派發前不必人工 grep 全量輸出。同時提供時 `--among` 優先
  - `fields set-where` 的範圍宣告變更改為獨立 auto-commit（與 `set-acceptance` / `append-log` 同保護等級）；`where.files` 路徑不存在時只警告不阻擋（新檔案的 where 宣告合法）
  - `parser.py` 新增 frontmatter 磁碟快取：以 `(mtime, size)` 為失效鍵，`save_ticket` 寫入時同步失效。僅生產路徑啟用，`TICKET_SYSTEM_TEST_ISOLATION` 存在時完全略過，避免 tmp_path 快速覆寫下 mtime 精度不足的假命中
  - `track dispatch` 的骨架組裝抽出至 `lib/dispatch_skeleton.py`；ANA ticket metadata 品質警告（who 代理人分工 / acceptance 長度分號 / tdd_phase 合理性）由 hook 遷入 CLI 的 `lib/ana_ticket_metadata_validator.py` 與 `lib/command_lifecycle_messages.py`
- v2.20.0 (2026-08-24): 新增子命令 `set-parent`：修正 `parent_id`（改寫或清除），並同步維護上游票 `children` 的雙向一致性；補上 `add-child` 一直缺少的反向修正路徑（誤用 `--parent` 建錯關係後的合法修正途徑）
- v2.19.0 (2026-08-24): `runqueue` callout 補一則語意提醒：輸出的 `blockedBy=[...]` 為未解除阻擋清單，與 ticket frontmatter 同名欄位的原值可能不同（後者保留宣告時完整清單，不隨 blocker 解除而改寫）；血緣或狀態對帳應以 frontmatter 為準
- v2.18.0 (2026-08-24): `create` 新增 `--discovered-during` 旗標，區分規劃衍生與發現衍生的建票語意
  - 與 `--source-ticket` 互斥：發現衍生（執行中撞到跨主題問題）的上游主題與新票內容無關，S1 判準在此情境下短路不觸發主題繼承
  - frontmatter 新增 `discovered_during` 欄位記錄血緣，但不驅動任何主題指派；S2 檔案叢集判準不受影響，仍依新票自身 `--where` 運作
  - create 章節新增「`--discovered-during` vs `--source-ticket`」對比表，體例比照既有 S1/S2/S3 判準表
- v2.17.0 (2026-08-21): `complete` 章節補兩則說明：(1) ticket metadata 自動提交時機改為呼叫當下的隔離索引提交後，metadata 與對應程式碼變更恆分屬兩個 commit，追溯下游流程（含 sync 本框架的其他 consumer 專案）須知情此語意；(2) 確認 `--no-stage` 已足夠覆蓋「想連同程式碼一起提交」的情境，並記錄選用該旗標放棄的保護與對應風險
- v2.16.0 (2026-08-21): 新增「覆核測試指令（skill 自身測試套件）」章節：明訂裸 `pytest`（不帶路徑參數）為唯一標準覆核指令，`pyproject.toml` 的 `testpaths` 已統一收斂 `tests/` 與 `ticket_system/tests/`；禁止以顯式路徑指令作為覆核依據（顯式路徑會覆蓋 testpaths，使另一目錄測試被靜默漏跑）
- v2.15.0 (2026-08-21): 彙整上次 canonical 同步後累積、未隨個別 commit 遞增版本號的多筆行為變更（分歧判定時發現，共 28 個 commit，僅列使用者可感知的介面差異）
  - 新增子命令 `set-closed-by`：修正已 closed 票的 `closed_by` 欄位
  - `append-log` 新增 `--replace` 旗標：整段覆寫指定章節內容，取代累積式 append
  - `create` 的 auto-commit 時點移至 Context Bundle 寫入之後（原本先 commit 後寫入 Context Bundle，導致該次寫入未隨 commit 一併留存）
  - `check-acceptance` 補上 auto-commit，對齊 `set-acceptance` 既有的保護等級
  - `create` 新增 when-blockedBy 一致性 WARNING：`--when` 語意與 `--blockedBy` 指定的前置票狀態衝突時提示
  - `create` 版本未註冊時，錯誤訊息新增 `--version` 繞過指令的 fallback hint
  - 修正 `set-blocked-by` / `set-related-to` 誤用逗號分隔時的提示文字：改回兩個子命令各自專屬的提示，不再共用易混淆的通用訊息
  - 修正 precondition 對已 completed 票的建議文案：原指向不存在的 `reopen` 命令，已修正為實際可用的操作
  - `audit_version` 新增 `detect_orphan_references` 雙向一致性檢查
  - `onboard` 新增「無主髒檔」小節
  - 修正 Context Bundle 讀取端 `blockedBy`/`relatedTo` 欄位雙態鍵名不相容導致的恆失效
- v2.14.0 (2026-08-20): `create` 新增 `--no-topic` 與過渡期 WARNING
  - 主題 callout 補 warn-only 語意：三判準未命中印 WARNING 但不改 rc，理由為避免代理人誤判建票失敗
  - 補 `--no-topic` 說明：明示不指派、與 `--topic` / `--new-topic` 互斥、衝突時於持久化前 exit 1

- v2.13.0 (2026-08-20): `create` 主題自動推導上線
  - create 章節新增「主題歸屬（自動推導）」callout：S1 上游繼承 / S2 檔案叢集 / S3 ANA 標記三判準與各自成本
  - 明示顯式 `--topic` / `--new-topic` 優先，推導僅在兩者皆未給時啟動（既有呼叫端行為不變）
  - 記錄 S2 的 3 段特異性門檻依據（淺層路徑會使單一主題成為所有新票的推導結果）

- v2.12.0 (2026-08-20): `board` 新增 `--group-by {wave,topic}` 分組軸
  - 新增「Board 分組軸 — `board --group-by`」callout：預設 `wave` 輸出逐字不變、`topic` 依主題分組
  - 主題節標題格式、排序雙鍵（最高優先級 → 票數降冪）、未歸屬節置底規則
  - 主題歸屬來源明示為 `lib/topic_assignments` 中央清單（非 frontmatter 欄位）
  - `references/track-command.md`「track board 子命令」同步補選項表與分組軸章節

- v2.11.0 (2026-08-18): dashboard-first 流程接手選項加入 lease 存活過濾（framework issue tarrragon/claude#78）
  - [In Progress] 條目帶 `[LIVE]` / `[RECLAIMABLE]` lease 狀態標記說明（CLI 同日落地，判準同 registry heartbeat）
  - `[LIVE]`（FRESH session 持有）票禁止列入 AUQ 接手選項，僅資訊性提及——防止跨 session 重複處理
  - `[RECLAIMABLE]` 票列入選項但路由至 `ticket track reclaim`（鑑識三查），非直接 resume

- v2.10.0 (2026-08-04): 系統模型章節新增第三條「type 與 instance 一對多」反直覺預設（列表由二條擴為三條，標題同步改「三個」）：明示 agent 類型與執行體非一對一、同類型可同時 spawn 多個獨立執行體；緊接帶出反向風險——並行上限來自共享 git index 寫入競爭、主線程序列化的驗收與建票工作、執行體 context 累積三項約束，而非類型數
- v2.9.0 (2026-07-08): 系統模型章節新增「named agent 生命週期三態」——擴展 agent=CI runner 類比從二態（running/stopped）為三態（新增 idle=warm runner），路由 PM 回收 SOP 到 parallel-dispatch.md
- v2.8.0 (2026-07-04): 新增「系統模型（設計自我描述）」章節——issue tracker + CI runner 為主類比、batch job queue 為輔，明示身份晚綁定與共享工作區兩個與 process 直覺相反的預設（設計回顧落地）；修正 stale 描述「priority 等欄位無 CLI 命令」（`set-priority` 已存在且完整接線，描述與 code 對齊）
- v2.7.0 (2026-05-27): `/ticket` 裸指令預設行為改為 dashboard-first 流程（源於 ANA 結論方向 a）
  - 步驟 1 從 `ticket track runqueue --context=resume --top 3` 改為 `ticket track dashboard --top 5`
  - AskUserQuestion 選項對齊 dashboard `[1] [2] [N]` 編號 + priority 標籤（用戶可直接說編號選擇）
  - in_progress 任務優先列出（label 加 `[ip]` 前綴），用戶選擇後走 `resume` 而非 `claim`
  - dashboard 無結果時 fallback 到原 `list --status pending in_progress` 路徑（向後相容）
  - `ticket resume --list` 與 `ticket track runqueue --context=resume` 子命令保留作除錯/腳本用途
  - 量測收益：baseline 7 tool call → dashboard-first 2-3 tool call（改善 57-71%）
- v2.6.0 (2026-05-13): 補 dashboard 命令與 list 預設行為文件
  - 子命令總覽表新增 `track dashboard` 與 `track list` 兩列
  - track 章節 READ 操作清單補 `dashboard` / `stale-list` / `td-status`，並註明 list `--top`/`--all` 預設行為
  - 新增 `Dashboard — dashboard` callout 說明聚合視圖、編號 claim、降低 7→3 tool call
  - 新增 `List 預設行為 — list --top / --all` callout 說明預設 top 10 排序與 `--format` 三選值
- v2.5.2 (2026-05-12): 子命令總覽表新增 `track td-status`；track 章節新增 td-status callout（PC-094 落地）
- v2.5.1 (2026-05-10): handoff 章節新增「設計原則」引用指向 `handoff-design-principle-methodology.md`
- v2.5.0 (2026-05-08): handoff 章節同步新增的 `--next` CLI 與 `target_ticket_id` 欄位
  - 新增 `--next <target-ticket-id>` 用法說明（絕對指向語意）
  - 註明與 `--auto` 互斥、direction 預設 `context-refresh`
  - 註明讀取端優先序：target_ticket_id > direction fallback（向後相容）
- v2.4.0 (2026-04-21): `/ticket` 裸指令入口切換為 scheduler 接手建議
  - 流程步驟 1 從 `ticket resume --list` 改為 `ticket track runqueue --context=resume --top 3`
  - AskUserQuestion 選項順序改反映 runqueue scheduler 排序
  - `ticket resume --list` 子命令保留，作為完整待恢復清單與除錯入口
- v2.3.0 (2026-03-11): `/ticket` 裸指令新增待辦任務檢查步驟
  - 流程調整為三層：(1) 檢查 handoff → (2) 檢查 pending/in_progress 待辦 → (3) 顯示子命令
  - 待辦任務以 AskUserQuestion 列出，含「建立新 Ticket」選項
- v2.2.0 (2026-03-02): `/ticket` 裸指令自動檢查 handoff 待恢復任務
  - 新增「無子命令時的預設行為」章節
  - `/ticket` → 檢查 pending handoff → AskUserQuestion 選擇 → resume
  - 搭配 handoff-prompt-reminder-hook v2.0.0 停用自動接手
- v2.1.0 (2026-03-02): 決策樹拆分為 5 個 workflow 檔案（Progressive Disclosure）
  - `decision-trees.md`（327 行）拆分為 5 個按工作流分組的檔案
  - 各子命令說明新增對應決策樹引用
  - 參考資料表更新為 5 個 workflow 檔案
- v2.0.0 (2026-02-10): SKILL.md 拆分為入口 + references
  - 從 1273 行精簡為 ~170 行入口文件
  - 9 個子命令/架構/決策樹/完整性驗證移至 references/ 目錄
  - 遵循官方 Supporting Files 模式（SKILL.md < 500 行）
  - 保留執行方式和命令總覽作為入口必讀資訊
- v1.9.0 (2026-02-06): 語意化重命名 commands_messages_a/b
- v1.8.0 (2026-02-06): 變更後文件一致性同步
- v1.7.0 (2026-02-06): 文件同步更新 - 新增 generate/board/audit 文件
