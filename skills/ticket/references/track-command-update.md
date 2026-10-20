# track 子命令（UPDATE 操作、commit 副作用與欄位語意、驗收條件操作、CLI 可修改欄位）

> **用途**：`track` 子命令詳解之一：UPDATE 操作、commit 副作用與欄位語意、驗收條件操作、CLI 可修改欄位。
>
> **同族檔**：`track-command-commit.md`、`track-command-update.md`、`track-command-dispatch.md`、`track-command-session.md`、`track-command-query.md`、`track-command-health.md`。原檔 `track-command.md` 保留檔頭與保留段落，並為各被移走段標保留路由，被移走段標在原檔以同名標題加一行路由保留，既有〈段標〉引用不需改寫。

---

## UPDATE 操作

```bash
# 接手 Ticket
/ticket track claim <id>

# 完成 Ticket（complete 已轉強制身份申報，需帶 --as，見下方「身份申報」）
/ticket track complete <id> --as <agent-name>

# 放棄 Ticket（退回等待態）
# 目標狀態依 blockedBy 決定（W3-082）：
#   blockedBy=[]    → pending（trigger / 主動讓出的 ready ticket 回休眠態）
#   blockedBy=[...] → blocked（確實被其他 ticket 擋著）
/ticket track release <id>

# 更新 Phase
/ticket track phase <id> <phase> <agent>

# 添加子 Ticket
/ticket track add-child <parent-id> <child-id>

# 修正 parent_id（改寫或清除，同步上游 children，誤用 --parent 後的修正路徑）
/ticket track set-parent <child-id> <new-parent-id>    # 改寫（同步舊/新上游 children）
/ticket track set-parent <child-id> --clear            # 清除（同步舊上游 children）
# new_parent_id 與 --clear 互斥，不可同時提供或同時缺席

# 設定 5W1H 欄位（僅以下 6 個 set-* 命令）
/ticket track set-who <id> <value>
/ticket track set-what <id> <value>
/ticket track set-when <id> <value>
/ticket track set-where <id> <value>
# set-where 的 value 依形態分流（2026-08-10 起）：
# - 路徑型（逗號分隔且每項皆含 /）→ 只同步 where.files，where.layer 維持原值
# - 描述型（任一項不含 /，如 "Domain Layer"）→ 只寫 where.layer，files 不動
# 需明確設定單一子欄位時用旗標：--layer <架構層級> / --files <路徑清單>
# Why: layer 語意為架構層級，過去路徑型輸入會把逗號串接的檔案清單寫進該欄，
# 使其失去意義且操作者不會察覺（CLI 回報只顯示 files 已同步）
/ticket track set-why <id> <value>
/ticket track set-how <id> <value>

# 事後設定或清除 scope_blocker（凍結前已存在的必要票回溯標記用）
/ticket track set-scope-blocker <id> --reason "<發版阻擋理由>"
/ticket track set-scope-blocker <id> --clear
# --reason 與 --clear 互斥；空字串理由視同未給，同樣拒絕

# 追加執行日誌
# 有效 section: 見 constants.CANONICAL_BODY_SECTIONS（Task Summary / Problem Analysis /
#   重現實驗結果 / Solution / Test Results / Context Bundle / NeedsContext / Exit Status /
#   Spawn Requests / Completion Info）。"Execution Log" 是 H1 容器標題，不是合法值
# Status precondition（W3-044 / W1-058）：需 status=in_progress；completed 票不分 section 一律放行（補寫審查後回饋用途，execute_append_log 對此命令無條件傳入 allow_completed=True）；
# 派發前章節 Problem Analysis / Context Bundle 例外允許 pending 直寫（PM bookkeeping，不需 --force）
/ticket track append-log <id> --section "Problem Analysis" "內容"
/ticket track append-log <id> --section "Context Bundle" "PCB 內容（派發前分析結果，PC-040）"
# --content-file <path>：自檔案逐字讀取內容，與位置參數 content 擇一（同時給或都不給即拒絕；
# 讀檔失敗、或內容為空或僅空白，皆非 0 結束且票面不變）。內容不經命令列，適用含反引號、$(...)、git 命令形態而被 runtime 拒絕的長文；可與 --replace 併用
/ticket track append-log <id> --section "Solution" --content-file <path>
#
# Section 標題容錯（W17-008.9）：
# - 標題比對採 MULTILINE + \s+ 容許多空白 + \s*$ 容尾空白
# - 命中：「## Solution」、「## Solution 」（末尾空白）、「##  Solution」（雙空白）皆 OK
# - 不誤匹配：「## Solutions」、「## Solution alt」不會被視為 Solution
# - SECTION_NOT_FOUND 時錯誤訊息會列出該 ticket 所有現有 ## 標題引導用戶

# 派發即落票（--note 落票 + normal/review 骨架輸出）
# normal（預設）：輸出含讀取/認領/收尾協議的完整骨架
/ticket track dispatch <id> --as <agent_name> --task-summary "一句話動作描述"
# --note 非空時帶時間戳寫入票的「派發日誌」章節（非 Schema 章節，不進 Context Bundle）
/ticket track dispatch <id> --as <agent_name> --note "並行派發，commit policy = agent commit"
# review：審查派發變體，不含 claim/complete（審查非執行票）
/ticket track dispatch <id> --kind review \
  --review-perspective "架構一致性" --decision-question "是否符合單一權威決策？"
# 骨架文字權威來源：ticket_system/lib/dispatch_skeleton.py 的
# SKELETON_TEMPLATE_NORMAL / SKELETON_TEMPLATE_REVIEW（track_dispatch.py 僅引用）；
# .claude/references/agent-dispatch-template.md「骨架（3 段）」引用其輸出，不手動同步逐字模板。

# 勾選驗收條件（check-acceptance，舊語法）
/ticket track check-acceptance <id> 1                  # 勾選第 1 項（1-based 整數）
/ticket track check-acceptance <id> 1 --uncheck        # 取消勾選第 1 項
/ticket track check-acceptance <id> --all              # 勾選全部驗收條件
/ticket track check-acceptance <id> --all --uncheck    # 取消勾選全部
/ticket track check-acceptance <id> "實作完成"          # 文字搜尋勾選（模糊比對）

# 勾選驗收條件（set-acceptance）
/ticket track set-acceptance <id> --check 1 2 3        # 勾選多個 index（空白分隔）
/ticket track set-acceptance <id> --check 1 --check 3  # 同上（重複旗標，等價）
/ticket track set-acceptance <id> --uncheck 1 2        # 取消勾選多個 index
/ticket track set-acceptance <id> --all-check          # 勾選全部
/ticket track set-acceptance <id> --all-uncheck        # 取消勾選全部

# 建票後修訂驗收條目（set-acceptance --add/--edit/--remove）
/ticket track set-acceptance <id> --add "新條件"                    # 追加條目，預設未勾選
/ticket track set-acceptance <id> --add "條件二" "條件三"           # 一次追加多個（空白分隔）
/ticket track set-acceptance <id> --add "條件二" --add "條件三"      # 同上（重複旗標，等價且可與空白分隔混用）
/ticket track set-acceptance <id> --edit 2 "修訂後文字"             # 覆寫 index 2 文字，勾選狀態不變
/ticket track set-acceptance <id> --edit 1 "文字甲" --edit 3 "文字乙"  # 一次改多組（可重複 --edit）
/ticket track set-acceptance <id> --remove 2                       # 移除未勾選條目
/ticket track set-acceptance <id> --remove 2 --force                # 移除已勾選條目須加 --force（防抹驗收證據）

# 身份申報（--as，W1-048）— claim / complete（finish 同列）/ add-acceptance / check-acceptance / set-acceptance / set-exit-status 六命令支援
/ticket track complete <id> --as thyme-python-developer        # 申報身份，與 who.current 對照不符即 deny（exit 1）
/ticket track check-acceptance <id> --all --as thyme-python-developer
/ticket track set-acceptance <id> --all-check --as thyme-python-developer
/ticket track complete <id> --as rosemary-project-manager      # PM 身份一律放行（bookkeeping 豁免）
/ticket track complete <id>                                    # 未提供 --as：deny（exit 1，已轉強制申報，見下方「身份申報（--as）判定邏輯」）

# 設定阻擋關係（blockedBy 欄位）
/ticket track set-blocked-by <id> <blocked-by-id>      # 覆寫（設定單一 blockedBy）
/ticket track set-blocked-by <id> <id2> --add          # 追加（去重）
/ticket track set-blocked-by <id> <id2> --remove       # 移除指定 blockedBy
/ticket track set-blocked-by <id> "<id2> <id3>" --add  # 一次追加多個：value 是單一位置參數，須引號包成一個字串（否則 argparse 報 unrecognized arguments）
# 覆寫與 --add 指向有非終態 children 的 ANA 時，stderr 印 [HINT] 說明 ANA 將保持開啟；只提示，exit code 不變（見 create-command.md〈指向 ANA 的耦合後果提示〉）

# 設定相關關係（relatedTo 欄位）
/ticket track set-related-to <id> <related-id>         # 覆寫（設定單一 relatedTo）
/ticket track set-related-to <id> <id2> --add          # 追加（去重）
/ticket track set-related-to <id> <id2> --remove       # 移除指定 relatedTo
/ticket track set-related-to <id> "<id2> <id3>" --add  # 一次追加多個：value 是單一位置參數，須引號包成一個字串（否則 argparse 報 unrecognized arguments）

# 驗證 frontmatter 合規性
/ticket track validate <id>                            # 檢查 status/completed_at/acceptance/who 4 欄位

# 執行驗收檢查
/ticket track audit <id>

# 批量操作
/ticket track batch-claim "id1,id2,id3"
/ticket track batch-complete "id1,id2,id3"

# 追加 spawned_tickets（支援單 ID / 多 ID，對齊 Unix 慣例如 rm a b c）
/ticket track add-spawned <id> <spawned-id>                    # 單一 ID
/ticket track add-spawned <id> <spawned-1> <spawned-2> <s-3>   # 多 ID 空白分隔（W17-008.1）
# 重複 ID 會自動去重並列入「已存在略過」

# 移除 spawned_tickets（按 ID 非索引，介面對稱 add-spawned；補齊寫錯後的更正路徑）
/ticket track remove-spawned <id> <spawned-id>                     # 單一 ID
/ticket track remove-spawned <id> <spawned-1> <spawned-2>          # 多 ID
# 找不到的 ID 回報於 stderr（非靜默），rc 非 0；部分找到時已找到者照常移除
# 移除成功時，若目標票 source_ticket 恰回指本票，同步清除該反向欄位
```

## UPDATE 操作補充：commit 副作用與欄位語意

### append-log 副作用：auto-commit

`append-log` 寫入 body 後會 **auto-commit 該 ticket md**（精確路徑，commit message `chore(<id>): append-log <section>`）。**Why**：body 即時進 commit 歷史可使 `git checkout -- <file>` / `git reset --hard` / `git stash` 三種還原全失效，根除「未 commit body 被 git 還原覆蓋回 placeholder」遺失問題。**Consequence**：每次 `append-log` 會新增一個 `chore` commit（碎 commit 為設計取捨，對 ticket md chore 類可接受）；body 無變更時 graceful skip 不產生空 commit。**Action**：非 git repo / index.lock 競爭 / commit 失敗時 `append-log` 仍 exit 0 + stderr 警告，body 保留 working tree 可手動 commit。不使用 `--no-verify`（維持 pre-commit hook 把關；ticket md 非 JS，lint-staged 無匹配）。

### complete 前置清單

`ticket track complete` 呼叫時會依序跑過下列檢查（部分依 ticket type 才觸發），逐項先備妥可縮短來回次數。本表為原始碼逐項核對後的結果，項次順序依檢查觸發順序排列，非固定編號：

| 檢查項 | 觸發範圍 | 阻擋／警告 | 內容 | 準備方式 |
|--------|---------|-----------|------|---------|
| 子任務完成度 | 有 children | 阻擋 | children 須全數為 terminal 狀態（非 pending/in_progress/blocked） | 先完成 children，或 `--force` 旁路（stderr 列出未完成清單為警告） |
| 防護類 hook ticket 必含項 | `where.files` 觸及 `.claude/hooks/` | 阻擋 | acceptance 前三項語意（本 session 實地觸發確認／liveness 驗證方式／失敗語意）+ `how.strategy` 產生路徑盤點表 | 見 `.claude/pm-rules/ticket-body-schema.md`「防護類 hook ticket 額外 acceptance」節 |
| 驗收記錄（CLI 層，`lifecycle.py complete()` Step 3） | 全部 | 阻擋，無 `--force` 等旁路 | frontmatter `acceptance` 全數以 `[x]` 開頭 | `set-acceptance --all-check` 或 `check-acceptance --all-check` |
| 驗收記錄（Hook 層，`acceptance-gate-hook.py` PreToolUse，`acceptance_checker.py`） | 全部 | 警告，不阻擋 Bash 呼叫本身 | acceptance 全勾選，或 body 含必填章節關鍵字，二擇一成立 | 同左，或補齊 Solution／Test Results 等必填章節關鍵字 |
| ANA 後續票／spawn 規劃一致性 | ANA 型 | 警告／不一致時阻擋 | `spawned_tickets` 存在性 + Solution spawn 規劃表格與 `spawned_tickets`＋`children` 數量一致 | `add-spawned` 補登記，或於 Solution 逐項標豁免理由 |
| ANA `multi_view_status` 標註 | ANA 型 | 非法值阻擋／缺標註警告 | Solution 含 `multi_view_status`，值須為 `reviewed`／`skipped`／`n_a` | `ticket track fix-multi-view-status <id> --value <值> --reason "..."` |
| Spawn Requests 未處理條目 | 全部 | 警告 | 「Spawn Requests」章節內無 pending 條目 | `resolve-spawn-request` 標記 `processed`／`dismissed` |
| Error-pattern 衝突／新增 | 全部 | 資訊 | 修改模組與既有 error-pattern 是否衝突；本次是否新增 error-pattern 檔 | `/error-pattern query` 先行確認 |
| 5W1H 完整性 | 全部 | 警告 | `who`／`what`／`when`／`where`／`why`／`how` 六欄位皆已填 | `set-who`／`set-what` 等 6 個 set-* 命令補齊 |
| Execution log 填寫（CLI 層，`lifecycle.py complete()` Step 3.5） | 全部 | 阻擋，`--skip-body-check` 逃生閥（需於 Completion Info 附理由） | type-aware 必填章節已填寫（IMP：Test Results；ANA：Problem Analysis＋Solution；DOC：無） | `append-log` 補齊必填章節，或 `--skip-body-check` 旁路 |
| Execution log 填寫（Hook 層，`acceptance-gate-hook.py` 步驟 6） | 全部 | 警告，不阻擋 Bash 呼叫本身 | Solution／Test Results 等必填章節已填寫（非 placeholder） | `append-log` |
| Layer 1 自檢結果（CLI 層，`lifecycle.py complete()` Step 3.5，同一 `--skip-body-check` 旗標） | IMP／ANA 型 | 阻擋，`--skip-body-check` 逃生閥（與上列同一旗標，一次旁路兩檢查） | Solution 含 `### 自檢結果` 子章節 | 依 `.claude/references/agent-self-check-template.md` 執行並記錄，或 `--skip-body-check` 旁路 |
| Layer 1 自檢結果（Hook 層，`acceptance-gate-hook.py` 步驟 8，自檢可觀測性檢查） | IMP／ANA 型 | 警告，不阻擋 Bash 呼叫本身 | Solution 含 `### 自檢結果` 子章節 | 依 `.claude/references/agent-self-check-template.md` 執行並記錄 |
| Phase 4 審查證據 | IMP 型 | 警告 | Solution 含 Phase 4 重構評估關鍵字（並行評估／`parallel-evaluation`／`Layer 2` 等） | 執行 `/parallel-evaluation` 或等價審查並記錄結論 |
| 規模與職責邊界判準 | 全部 | 警告 | ticket 規模（god ticket scale）與 `where.files` 涉及模組多樣性是否超閾值 | 依提示考慮拆票，或於 Solution 說明理由 |
| 實驗器材殘留 | 有登記的實驗器材 | 阻擋 | 工作區無屬本票命名規範但未妥善處置的實驗器材 | `resolve-artifact` 收尾處置 |

> 另有 sibling tickets 完成度、自訂 H2 章節兩項為純資訊性輸出（不需事先準備，供 PM 排程參考），不列入上表。`--yes-spawned`（ANA 有 spawned 非 terminal 時旁路 blocking confirmation，非互動環境必需）與 `--skip-body-check`（逃生閥：跳過 type-aware body schema 必填章節驗證，需於 Completion Info 附理由）兩旗標分別對應上表「ANA 後續票」與「Execution log 填寫」兩項的旁路路徑。

> **worktree 分支已合併（不在上表，無 CLI 檢查）**：代理人在 linked worktree 內完成工作後 `complete`，票面轉 `completed`、metadata 進主倉庫，但該 worktree 分支是否已合併回主分支不受任何上表項目檢查——`stuck-anas`／`stale-list` 亦不看分支合併狀態。**Action**：worktree 場景下 complete 前，於 Completion Info 記錄分支名並人工確認已合併，避免票已收尾但程式碼變更停留在未合併分支形成靜默遺失。

主 worklog 的進度行插在最後一個 `### YYYY-MM-DD` 區段末尾；日誌尚無任何日期標題時，於 `## 開發日誌` 章節末尾建立當日標題再追加（冪等）；連 `## 開發日誌` 章節也沒有時印 WARNING（含日誌路徑與缺少的結構）並跳過，不自動建章節。

`complete` 通過上表全部檢查後，自動以隔離索引提交本票 md + 主 worklog 進度行（行層級：只提交本次插入的那一行，不整檔提交 worklog，工作區內他人未提交的 worklog 修改不被帶入；`batch-complete` 同，各票進度行併入同一批次 commit），另有三項不在上表、但直接影響提交結果的副作用語意：**被解鎖的票併入同一 commit**（本次 cascade 解鎖的 children 與反向 blockedBy 引用者，save 成功者整檔併入同一筆 post-completion commit，可跨版本，commit body 列出其票 ID；save 失敗者不列入並照常印 WARNING。其他未被本次寫入的票不進入提交範圍）、**不留 staged 殘留於共用 index**（全程走隔離索引，共用 index 提交前後狀態不變，非「先 add 進共用 index 再 commit」）、**成功時 stdout 印出 commit SHA**（`[OK] 已提交 <sha>` 格式，供呼叫端核對是否真正落地，見下方 `track commit` 子命令「Exit code」表的同款判讀原則）。

### complete 副作用：ticket metadata 與程式碼變更恆分兩個 commit

`complete` 在父 ticket 含未完成 children（非 terminal：pending / in_progress / blocked）時會以 exit 1 阻擋。提供 `--force` 旁路強制完成，cascade 解鎖機制仍會執行。建議優先完成 children 後再 complete 父 ticket。

**`--force` 的實際旁路範圍**：`acceptance-gate-hook` 辨識命令中引號外的 `ticket track complete <id> ... --force` 語句（同鏈其他命令的 `--force` 不算），**只旁路 children 檢查**，其他阻擋照常生效（hook 防護必含項、spawn 一致性、multi_view 非法值等）。旁路成立時：hook 的 additionalContext 列出被旁路的未完成 children（每項 `id: title (status)`），並在 `.claude/hook-logs/acceptance-gate/` 寫入 `FORCE_BYPASS` 稽核紀錄；解析失敗時維持阻擋（fail-closed）。CLI 層 `lifecycle.py` 亦於 stderr 列出未完成 children 作為警告。**Action**：`--force` 是逃生閥，不是 ANA 落地的收尾路徑；ANA 結論要求的落地用 `--parent`，等 children 終態後再 complete（PC-091）。

`complete` 的自動提交於呼叫當下以隔離索引提交 ticket metadata（本票 md + 主 worklog），而非留待 PM 事後核對共用 index 手動 commit。**Why**：提交時機從「人工事後裸 commit」改為「CLI 呼叫當下自動提交」，是為了根除過期 index 快照被誤 commit 進 HEAD 的風險。**Consequence**：ticket metadata 與對應的程式碼變更**必然分屬兩個 commit**——單靠 `git log --grep <票號>` 只會命中 metadata commit（`chore(<id>): complete` / `chore(<id>): append-log ...`），不含實作變更；依「一票一 commit」假設做追溯的下游流程（含 sync 本框架的其他 consumer 專案）須知情此語意，否則會誤判追溯不完整或漏算變更範圍。**Action**：追溯某票完整變更時，搜尋範圍須同時涵蓋 metadata commit 與程式碼 commit（可用票號關鍵字掃兩者的 commit message，或查詢 ticket body 的 Test Results / Completion Info 章節記錄的程式碼 commit SHA）。

### `--no-stage` 的覆蓋範圍

`--no-stage` 會完整跳過本次 auto-commit（metadata 與 worklog 兩者皆跳過），ticket md 停留在 working tree 的未提交、未 staged 狀態，不產生任何 metadata commit。**Action**：想讓 ticket metadata 與程式碼變更合併成單一 commit 時，`--no-stage` 已足夠覆蓋——先完成程式碼變更，`complete <id> --no-stage` 後 ticket md 仍是未提交的工作區變更，可與程式碼檔案一併 `git add` 後裸 commit（無 pathspec / `--only` / `-o` / `-a`，見 `.claude/rules/core/bash-tool-usage-rules.md` 規則七）。**Consequence**：選擇 `--no-stage` 等於放棄自動提交機制帶來的「不留未提交 metadata」保護，working tree 中的 ticket md 變更在手動 commit 之前仍可能被 `git checkout --`／`git reset --hard`／`git stash` 覆蓋回舊版本（與「Spawn Requests」章節「繞道手改會失去 auto-commit 保護」同類風險），故僅建議在確定會立即手動 commit 時使用。

### `title` 與 `what` 是兩個獨立欄位，`set-what` 刻意不同步 `title`

`title` 是清單顯示用的短標籤（dashboard / runqueue 顯示的是它），`what` 是完整任務敘述（可含檔案清單、括號補充）；兩者常刻意不同（量測見 `CHANGELOG.md`）。票的範圍事後縮小時（如依上游評估結論移除 acceptance），**兩個欄位都要更新**——只改 `what` 會讓清單上的 `title` 繼續以舊範圍誤導接手者。更新用 `set-title <id> <value>`。

**範圍欄位同步提示**：範圍由 `title`、`what`、`acceptance`、`where.files`、`how.strategy` 五欄共同表達。`set-title`／`set-what`／`set-where`（改到 files）／`set-acceptance`（`--add`／`--edit`／`--remove`）寫入後，stdout 會列出其餘非空範圍欄位的現值摘要與對應 set- 指令。被改欄位原值為空（首次填寫）時不印；勾選／取消勾選不印；只印不擋，exit code 不變。

### 其餘 frontmatter 欄位若無對應命令，不要手動編輯

`ticket-file-access-guard-hook` 會以 exit 2 阻擋直接編輯 frontmatter，繞道不可行。找不到對應命令代表該欄位缺少合法更新途徑（PC-BAL-047），應建 ticket 回報補上命令。

### closed 票欄位修正 — `set-closed-by`

`close` 對已 closed 票拒絕覆寫既有值；`set-closed-by <id> --value <ticket-id>` 補上 `closed_by` 填錯後的合法修正路徑，取代直接 Edit ticket md（該路徑被 `ticket-file-access-guard-hook` 阻擋）。

```bash
ticket track set-closed-by <id> --value <ticket-id>
```

僅適用 `status=closed` 的票；`--value` 須為合法且存在的 Ticket ID，格式錯誤或指向不存在的 Ticket 皆拒絕。修正動作輸出舊值與新值並走 auto-commit。

### closed 票還原 — `restore`

`closed` 為 `STATUS_TRANSITIONS` 定義的終態，`release` 與 `claim` 皆被 enum-gate 擋下、ticket md 直接 Edit 亦被 `ticket-file-access-guard-hook` 阻擋——誤關票原本無合法還原路徑。`restore <id> --reason <text> [--as <agent>]` 補上這條缺口，且刻意設計為 `closed -> pending` 唯一可觸發入口：`STATUS_TRANSITIONS` 只對 `closed` 開放 `pending` 這一個出邊，`release` 另有明確的 app-level guard 拒絕 closed 票，`claim` 恆將 closed 導向 `in_progress`（不在開放出邊內），兩者對 closed 票仍被擋下。

```bash
ticket track restore <id> --reason <text> [--as <agent>]
```

僅適用 `status=closed` 的票；`--reason` 必填（禁止靜默還原）。落地時清除 `close_reason` / `close_reason_note` / `closed_by` / `closed_at` / `completed_at` 五個 close 相關欄位，並寫入 `restored_at` / `restored_by` / `restore_reason` 三個還原記錄欄位，走 auto-commit。

### 身份申報（`--as`）判定邏輯

`complete` / `check-acceptance` / `set-acceptance` 三個寫入命令支援選用 `--as <agent-name>`，與 ticket `who.current` 精確對照。**Why**：防 generic agent 收 Ticket ID 即越權收尾（PC-V1-002 前提一，探針實證）。**判定邏輯**：`--as` 值 ≠ `who.current`（含空值）→ deny（exit 1，純前置檢查不寫入狀態）；`--as rosemary-project-manager` 一律放行（PM bookkeeping 豁免，如代收尾 / stale cleanup）；未提供 `--as` 時 `complete`（`finish` 別名同列）已轉強制 deny，`check-acceptance` / `set-acceptance` 仍維持 warn-only（僅輸出 stderr 訊息，不阻擋；過渡期設計，見 `identity_guard.py` 的 `ENFORCED_COMMANDS`）。**Action**：subagent 收尾時帶自身身份，例 `ticket track complete <id> --as thyme-python-developer`；其餘 warn-only 命令轉強制的結束條件與偵測承擔者已明訂（7 日滾動 warn 率 < 5% 且樣本數 >= 30，由 PM 於 `version-release` 發布前檢查階段執行 `identity_guard_adoption.py` 判定），非待評估的無 trigger 狀態。

**接手者收尾身份**（SKILL.md〈dashboard-first〉步驟 1「無標記 in_progress 任務」情境——票已 `in_progress`、非新 `claim`，接手者不必然是 `who.current` 原持有者）：維持原 `who.current` 不變逕行 `complete --as <self>` 會因情境 4（`--as` 與 `who.current` 不符）被 deny。**Action**：PM 前台接手裸 `/ticket` 用 `--as rosemary-project-manager` 走情境 2 豁免收尾；代理人接手（非原 `who.current` 者）須先 `ticket track set-who <id> --current <self>` 把 `who.current` 改為自身（`set-who` 不在 `ENFORCED_COMMANDS`，不受本節 `--as` 檢查），再以 `--as <self>` 收尾走情境 3 對稱通過。`set-who` 只覆寫 `who.current` 子欄位，並把原 current 追加進 `who.history`（`{ISO 時間: 原 current}`，current 未變不追加）；`complete` 以 current 或 history 中最後一個非 PM 者覆寫 Completion Info 的 Executing Agent，並依 Phase 4 證據寫 Review Status（IMP 有證據為 `reviewed`，ANA／DOC 為 `n/a`，其餘維持 `pending`）、非 manual 來源的 `tdd_phase` 推進為 `tdd_stage` 最後一項。

### claim 推薦用法（subagent 派發時的身份申報）

被派發的 subagent 認領自身 ticket 時，**推薦使用 `ticket track claim <id> --as <self-agent-name>`**（申報自身身份；不加 `--verify`）。

**Why**：`claim --as <agent>` 在認領時把 `who.current` 寫成執行者身份，使後續 `complete --as <self>` 與上方「身份申報（--as）判定邏輯」對稱通過，無需 `set-who` 繞過。`--as` 在 `file_lock` 內與 status 寫入同一原子操作（load → modify → save），不執行 AC 驗證、不讀 stdin、不偵測 TTY，subagent 無 TTY 的互動環境受限完全無影響。`--as` 與 `--verify` 正交：`--as` 只設身份，不觸發任何驗證副作用。

> **為何需要 `--as`**：建立 ticket 未指定 `--who` 時 `who.current` 預設為字面 `"pending"`。裸 `claim`（不帶 `--as`）不寫 `who.current`，後續 `complete --as <agent>` 因 `"pending" != <agent>` 被 identity-guard deny（情境 4：`--as` 與 `who.current` 不符即 deny，含 `who.current` 空值／字面 `"pending"` 的情形，定義見 `identity_guard.py` 判定路徑列舉「情境 1-4」），agent 須先 `set-who` 繞過。`--as` 從源頭消除此縫隙。裸 `claim`（不帶 `--as`）維持向後相容，仍可用，但收尾時須自行 `set-who`。

**Consequence**：若 subagent 改用 `--verify`（明示啟用 AC 自動驗證，僅供除錯場景），在無 TTY 環境下會觸發 fail-closed：未加 `--yes` 時直接 return 1 並印出「非互動環境且未指定 --yes，已取消」，subagent 可能誤判 ticket 未 claim 而重試或放棄。`--verify` 還會在 claim 時跑 AC 對應的驗證指令（如 npm test 全套件），造成同 wave 並行 claim 衝突（PC-078）。

**Action**：

| 場景 | 推薦命令 | 說明 |
|------|---------|------|
| subagent 認領被派發的 ticket（常態） | `ticket track claim <id> --as <self-agent-name>` | 設 who.current，後續 complete --as 對稱通過 identity-guard，免 set-who |
| 不申報身份的裸認領（向後相容） | `ticket track claim <id>` | 不碰 who.current；收尾若需 complete --as 須自行 set-who |
| 除錯時想 claim 並同時跑 AC 驗證 | `ticket track claim <id> --verify --yes` | `--yes` 在非互動環境短路驗證 prompt 為 y，避免 fail-closed |
| 只想看 AC 驗證結果不 claim | `ticket track verify <id>` | 與 claim 解耦（`--skip-verify` 已移除，改用此子命令） |
| 接手既有 in_progress 票（非新 claim，dashboard-first「無標記 in_progress」情境） | 代理人：`ticket track set-who <id> --current <self>` 後 `complete --as <self>`；PM：直接 `--as rosemary-project-manager` | 見上方「接手者收尾身份」；`set-who` 會在 `who.history` 追加原 current |

### 補標記 — `add-exempt-marker`

`append-log` 預設追加，`--replace` 可整段覆寫但會連同原文字一併取代（CLI 管理的 H3 子節「派發日誌」「Commit 規範」會保留並接在新內容之後；摘要列出將被取代的人寫 H3 標題，清單見 `track_dispatch.CLI_MANAGED_H3_HEADINGS`）（不可逆，執行前印摘要供核對），不適合只補一行 marker——該區段不在 `ticket-file-access-guard-hook` 白名單內故 Edit 工具被拒，兩者疊加使 `PC-093-exempt` 這類行級標記無法在不動原文的前提下事後補上。`add-exempt-marker` 補這條路，且**僅追加獨立標記行、不修改原文字**：

```bash
ticket track add-exempt-marker <id> --section "Solution" --match "命中行的文字子字串" \
  --category ticket-tracked --reason "W<wave>-<seq> hook 訊息改善"
```

`--match` 是文字比對定位（非行號——行號隨後續編輯漂移）：命中恰好一行才寫入；0 命中或多重命中一律拒絕並回報候選行，要求提供更精確的 `--match` 收窄。marker 固定插入為命中行的**前一行**（獨立新行），與 `phase4-decision-enforcement-hook` 的豁免距離規則（同行或前 1 行生效）一致。

`--category` 限定 `tdd-transition` / `baseline-gated` / `ticket-tracked` / `user-override` / `rule-quote` / `history`，`--reason` 格式驗證與該 hook 同規則：`baseline-gated` 需含數字；`ticket-tracked` / `history` 需含 `W{wave}-{seq}` ticket ID；`rule-quote` 需含 `.claude/rules/` 或 `.claude/pm-rules/` 路徑。

**防濫用**：本命令不能憑空產生新內容、只能指向既有行；marker 是否真正生效仍由 `phase4-decision-enforcement-hook` 於 phase4 轉換 / complete 時重新掃描判定，本命令不繞過該把關層。Status precondition 與 auto-commit 副作用與 `append-log` 同（見上「append-log 副作用」）。

### add-spawn-request / resolve-spawn-request 用法

`add-spawn-request` 把「發現應開新 ticket 的議題」以結構化欄位追加至 Spawn Requests 章節，取代自由格式手寫：

```bash
ticket track add-spawn-request <id> --what "<建議開票的目標描述>" --why "<發現原因/觸發情境>" \
  --type IMP|ADJ|ANA|DOC --priority P0|P1|P2|P3 [--files <逗號分隔路徑>] [--context "<補充>"]
```

`resolve-spawn-request` 標記某條 spawn request 的處理狀態，並在 `--status processed` 時同步回填 `spawned_tickets`（取代直接手改 ticket md 繞過 auto-commit 保護）：

```bash
ticket track resolve-spawn-request <id> SR-N --status processed --spawned-ticket <ticket-id> [<ticket-id-2> ...]
ticket track resolve-spawn-request <id> SR-N --status dismissed --reason "<評估後不建的理由>"
```

`--status` 限 `processed`（已建 ticket，`--spawned-ticket` 可傳多個）／`dismissed`（評估後不建，建議附 `--reason`）；兩者皆支援 `--force` 逃生閥旁路 status precondition 檢查（記入 hook-logs）。與上方「complete 前置清單」表「Spawn Requests 未處理條目」列對應——本命令是該檢查項的唯一合法收尾路徑。

`--spawned-ticket` 接受任意既有 ticket ID，不驗證其血緣——`processed` 回填 `spawned_tickets` 時（與 `add-spawned` 同），若目標票已有不同於本票的 `source_ticket`，會於 stderr 印出 WARNING（僅提示、不擋寫入，因「刻意關聯一張已有主的既有票」屬合法情境）。誤植血緣事後可用 `remove-spawned` 更正。

### td-status — 校準 TD 清單（PC-094）

掃描指定 ticket 的 body 與 git commit 訊息，將 TD 編號分類為「已處理 / 無需處理 / 仍待處理」三狀態，用於 Phase 3a/3b/4 結束時即時校準 TD 清單，防止 Phase 4 評估時誤判已完成項（PC-094 根因）。

```bash
ticket track td-status <id>
ticket track td-status <id> --version 0.18.0
```

輸出分三組：`[已處理]` / `[無需處理]` / `[仍待處理]`，pending TD 會附 PC-094 校準提示。呼叫時機：Phase 3a 策略文件完成後、Phase 3b commit 前、Phase 4 派發前。完整規則見 `.claude/pm-rules/tech-debt.md`「TD 清單即時校準（td-status）」章節。

### 六欄位語意 SSOT

`parent_id` / `children` / `source_ticket` / `spawned_tickets` / `blockedBy` / `relatedTo` 的權威定義、阻擋語意、用戶情境對照表、決策樹見 `references/field-semantics.md`。其他規則 / 方法論 / error-pattern 涉及這些欄位時應引用該檔，不重複定義。

### 派發前寫 dispatch-plan

dispatch-plan 的觸發條件、欄位定義與範本見 `.claude/references/agent-dispatch-template.md`「Dispatch-Plan Template」節，本檔不重複定義。

## 驗收條件操作詳解

### 語法組合完整表

#### check-acceptance 完整組合（舊語法，單索引）

| 組合         | 指令                                         | 行為                |
| ------------ | -------------------------------------------- | ------------------- |
| 單項勾選     | `check-acceptance <id> 1`                    | 勾選第 1 個驗收條件 |
| 單項取消勾選 | `check-acceptance <id> 1 --uncheck`          | 取消勾選第 1 項     |
| 全部勾選     | `check-acceptance <id> --all`                | 勾選全部驗收條件    |
| 全部取消勾選 | `check-acceptance <id> --all --uncheck`      | 取消勾選全部        |
| 文字搜尋勾選 | `check-acceptance <id> "實作完成"`           | 模糊比對後勾選      |
| 文字搜尋取消 | `check-acceptance <id> "實作完成" --uncheck` | 模糊比對後取消勾選  |

#### set-acceptance 完整組合（多索引）

| 組合         | 指令                                | 行為                  |
| ------------ | ----------------------------------- | --------------------- |
| 多項勾選     | `set-acceptance <id> --check 1 2 3` | 同時勾選第 1/2/3 項   |
| 多項取消勾選 | `set-acceptance <id> --uncheck 1 2` | 同時取消勾選第 1/2 項 |
| 全部勾選     | `set-acceptance <id> --all-check`   | 勾選全部驗收條件      |
| 全部取消勾選 | `set-acceptance <id> --all-uncheck` | 取消勾選全部          |

#### set-acceptance 建票後修訂組合（--add/--edit/--remove）

與 check/uncheck 系列操作**勾選狀態**不同，`--add`/`--edit`/`--remove` 操作的是條目本身（新增、改文字、刪除）。三者與 check/uncheck 系列互斥，每次呼叫僅能指定一種模式。

| 組合           | 指令                                               | 行為                                        |
| -------------- | --------------------------------------------------- | ------------------------------------------- |
| 追加單一條目   | `set-acceptance <id> --add "新條件"`                | 於清單末端新增一項，預設未勾選 `[ ]`        |
| 追加多個條目   | `set-acceptance <id> --add "甲" "乙"`               | 一次追加多項，皆未勾選                      |
| 覆寫單一文字   | `set-acceptance <id> --edit 2 "新文字"`             | 改寫 index 2 的文字，原勾選狀態不變         |
| 覆寫多組文字   | `set-acceptance <id> --edit 1 "甲" --edit 3 "乙"`   | 一次改多組（`--edit` 可重複指定）           |
| 移除未勾選條目 | `set-acceptance <id> --remove 2`                    | 直接移除，其餘 index 正確對位               |
| 移除已勾選條目 | `set-acceptance <id> --remove 2 --force`            | 已勾選（`[x]`）條目移除須加 `--force`，防止事後抹除驗收證據；不加 `--force` 會被拒絕且內容不變 |

**索引對位保證**：`--remove` 支援一次移除多個 index（如 `--remove 2 4`），實作由大到小依序刪除，確保刪除過程中前面索引的位移不會誤刪錯誤條目。

**與 completed 票的關係**：`--add`/`--edit`/`--remove` 與 check/uncheck 系列共用同一個 status precondition（`require_in_progress`）——票狀態為 `completed` 時預設拒絕修訂（exit 2），需加 `--force` 才能旁路（避免事後改條件使驗收記錄失真，且會記入 hook-logs audit）。

### set vs check 決策樹

```
需要操作驗收條件？
    |
    v
一次操作多個 index？
    |
    +── 是 ──> 用 set-acceptance --check 1 2 3（check-acceptance 不支援多索引）
    |
    +── 否 ──> 用文字搜尋？（不確定 index）
                  |
                  +── 是 ──> 用 check-acceptance <id> "關鍵字"（set-acceptance 不支援文字）
                  |
                  +── 否 ──> 兩者皆可，推薦 set-acceptance（語意清晰）
```

**場景對照（7 情境）**：

| 場景                     | 推薦命令                                       | 原因                             |
| ------------------------ | ---------------------------------------------- | -------------------------------- |
| 完成所有驗收條件         | `set-acceptance --all-check`                   | 語意清晰，等同批量操作           |
| 逐一勾選（不確定 index） | `check-acceptance "關鍵字"`                    | 唯一支援文字搜尋的命令           |
| 一次勾選多項             | `set-acceptance --check 1 3 5`                 | check-acceptance 不支援多索引    |
| 取消上一個勾選           | `set-acceptance --uncheck 2`                   | 語意明確，等同 check + --uncheck |
| 確認哪幾項已勾選         | `ticket track query <id>`                      | 先查再操作                       |
| 重置全部再重選           | `set-acceptance --all-uncheck` + `--check 1 2` | 分兩步清除後選取                 |
| 腳本自動化               | `set-acceptance --check ...`                   | 有具名 flag，腳本可讀性高        |

### index 三種格式（僅 check-acceptance 支援）

| 格式         | 範例          | 說明                                 |
| ------------ | ------------- | ------------------------------------ |
| 1-based 整數 | `1`, `2`, `3` | 標準格式，第 1 項 = 索引 1           |
| 0-based 整數 | `0`           | 特殊支援，視為第 1 項（等同 `1`）    |
| 文字搜尋     | `"實作完成"`  | 模糊比對 AC 條目文字；唯一比對才成功 |

> **注意**：`set-acceptance` 只接受 1-based 整數，不支援 0-based 或文字搜尋。

### 5 常見錯誤組合警示

> **實測來源**（W17-008.16 補完）：以下症狀欄為實際 CLI 輸出觀察結果。 <!-- rule8-exempt: relocation:自 .claude/skills/ticket/references/track-command.md 逐字搬移 -->

| 錯誤用法                                       | 實際症狀（CLI 輸出）                                              | 正確用法                              |
| ---------------------------------------------- | ----------------------------------------------------------------- | ------------------------------------- |
| `check-acceptance <id> 1 2 3`                  | `ticket: error: unrecognized arguments: 2 3`                       | `set-acceptance <id> --check 1 2 3`   |
| `check-acceptance <id> --uncheck`（無 index）  | `[Error] 必須提供 index 或使用 --all 參數`（含 usage hint）       | `check-acceptance <id> 1 --uncheck`   |
| `check-acceptance <id> --all 1`                | `[Error] --all 和 index 參數互斥，只能選擇其中之一`                | 二選一：要嘛 `--all`，要嘛指定 index  |
| `set-acceptance <id> --check`（無數字）        | argparse 錯誤（`--check` 需至少 1 個值）                          | `--check 1` 或 `--check 1 2 3`        |
| `check-acceptance <id> "關鍵字"`（比對多項）   | `匹配到 N 個項目，請使用索引` 錯誤（文字搜尋僅唯一比對成功）       | 改用具體 index 避免歧義               |

---

## CLI 可修改欄位 vs 手動編輯欄位

並非所有 frontmatter 欄位都有對應的 CLI 命令。修改欄位前請查閱此表：

| 欄位                        | CLI 命令                                        | 備註                                                 |
| --------------------------- | ----------------------------------------------- | ---------------------------------------------------- |
| who/what/when/where/why/how | `set-who` ~ `set-how`                           | 僅此 6 個 set-\* 命令                                |
| status                      | `claim` / `complete` / `release` / `restore`（僅 closed→pending） | 由生命週期命令管理，禁止手動編輯                     |
| tdd_phase                   | `phase <id> <phase> <agent>`                    | Phase 進度更新                                       |
| children                    | `add-child <parent> <child>`                    | 父子關係                                             |
| parent_id                   | `set-parent <child> <new-parent>\|--clear`      | 改寫或清除，自動同步上游 `children`（雙向一致性）    |
| acceptance                  | `check-acceptance` / `set-acceptance`           | 勾選/取消勾選用 `--check`/`--uncheck`/`--all-check`/`--all-uncheck`；新增/改文字/刪除條目用 `set-acceptance --add`/`--edit`/`--remove`（建票後修訂） |
| frontmatter 驗證            | `validate <id>`                                 | 檢查 status/completed_at/acceptance/who 4 欄位合規性 |
| blockedBy                   | `set-blocked-by <id> <value> [--add\|--remove]` | 建立時用 `--blocked-by`；之後用 CLI 更新             |
| relatedTo                   | `set-related-to <id> <value> [--add\|--remove]` | 建立時用 `--related-to`；之後用 CLI 更新             |
| creation_accepted           | 無（`accept-creation` 已移除）                  | 建票通過硬閘門後由 `create` 直接寫 `true`，認領不再檢查；2026-10-14 之前建立的票此欄位不具意義（多為 false），不回填 |
| title                       | `set-title <id> <value>`                        | 清單顯示用短標籤，與 `what` 刻意分離；範圍變更時兩者需個別更新（見「UPDATE 操作補充」章節） |
| priority                    | `set-priority <id> <value>`                     | value 限 `PRIORITY_LEVELS`（P0-P3）                  |
| closed_by                   | `set-closed-by <id> --value <ticket-id>`        | 僅 `status=closed` 適用，修正 close 時填錯的值        |
| scope_blocker                | `set-scope-blocker <id> --reason <text>\|--clear` | 建票時可用 `--scope-blocker` 一併寫入；事後補標或清除用本命令，`--reason`/`--clear` 互斥，空理由視同未給 |
| dispatch_reason             | 無 CLI 命令                                     | 依上方「其餘 frontmatter 欄位若無對應命令，不要手動編輯」處置：不可手動編輯，應建 ticket 回報補上命令 |

**不存在的操作**（禁止嘗試）：

| 錯誤呼叫       | 正確做法                              |
| -------------- | ------------------------------------- |
| `set-status`   | 使用 `claim` / `complete` / `release` |

---
