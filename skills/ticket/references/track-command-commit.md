# track 子命令（track commit、set-exit-status、worktree root 分離）

> **用途**：`track` 子命令詳解之一：track commit、set-exit-status、worktree root 分離。
>
> **同族檔**：`track-command-commit.md`、`track-command-update.md`、`track-command-dispatch.md`、`track-command-session.md`、`track-command-query.md`、`track-command-health.md`。原檔 `track-command.md` 保留檔頭與保留段落，並為各被移走段標保留路由，被移走段標在原檔以同名標題加一行路由保留，既有〈段標〉引用不需改寫。

---

## track commit 子命令

代理人端以隔離索引（`git_ops.commit_files_isolated`）提交 ticket `where.files` 寫入子集內的指定檔案，全程不觸碰共用 index，取代裸 `git add` + `git commit` 的制式句路徑。

### 用法

```bash
ticket track commit <ticket_id> -m "<commit message>" -- <exact files...>
ticket track commit <ticket_id> -m "<commit message>" --worktree <worktree 絕對路徑> -- <exact files...>
```

### Flag 說明

| Flag | 必要 | 說明 |
|------|------|------|
| `-m` / `--message` | 必要 | commit message |
| `--worktree` | 條件必要 | 檔案實際變更所在的 linked worktree 絕對路徑 |
| `files`（位置參數） | 必要 | 欲提交的檔案路徑，**須為 ticket `where.files` 寫入子集**，超出範圍整批拒絕提交（不部分提交、不自動裁切清單） |

### files 子集規則

`files` 必須落在該 ticket `where.files`（寫入意圖，即無 `::read` 標記或帶 `::write` 標記的路徑）宣告範圍內；任一項超出範圍即拒絕整批提交，並列出超出項與宣告範圍供核對。**隱含可寫（CLI 自己寫入的檔，不需列入 where.files）**：票自身 md、票所屬版本的工作日誌、`docs/work-logs/topic-assignments.txt`，由 `track_commit._cli_managed_paths` 集中定義；complete／create 收尾 CAS 失敗的補救指令會同時帶這幾個檔。他票票檔與一般 docs 檔不在此列，仍須宣告。目錄型宣告（結尾 `/` 或指向既有目錄）會展開為該目錄下實際變更（`git status --porcelain`）的具體檔案再提交。ANA 型票 `where.files` 預設全唯讀，`write_files()` 恆回空集合；需要寫入的路徑須額外標 `::write`。`::read`／`::write` 後綴語法與 type 預設意圖的完整規則見 `field-semantics.md`〈where.files 宣告語意〉。

**目錄展開的並行過濾**：展開時另讀取 `.claude/dispatch-active.json`，凡命中其他活躍派發（`ticket_id` 不同於本票）宣告路徑的變更檔一律排除，避免並行環境下把他 session 的變更一併吸入本次目錄展開（本票或無人宣告皆保留，僅排除已知歸屬他票者）。此過濾為並行防護的加強層，非安全邊界本身——安全邊界仍是上段的 `where.files` 子集檢查；registry 讀取失敗（檔案不存在／JSON 格式錯誤）視為無其他派發，fail-open 不擋下正常提交。

**同檔邊界（隔離索引不防同檔內容夾帶）**：上述並行過濾與 `where.files` 子集檢查防的是「誤觸他票宣告路徑之外的檔案」；當兩票 `where.files` 都宣告**同一檔案**時，兩者皆不提供保護。隔離索引（`git_ops.commit_files_isolated`）只隔離「不觸碰共用 git index」，`git add -- <path>` 取用的仍是該檔案當下的工作區內容——先提交者會把他票尚未提交的同檔編輯整檔一併寫入本次 commit。此邊界與 `.claude/rules/core/bash-tool-usage-rules.md` 規則七「核對步驟的粒度邊界（檔案內夾帶）」同根因：`git add` 的最小可定址單位是整個檔案，無法區分「誰寫的哪一行」；該條文原僅論及裸 commit 的核對步驟，本命令的隔離索引提交同樣適用（配方步驟見 `.claude/references/bash-tool-usage-details.md`「隔離索引提交」步驟 4）。**偵測**：提交後以 `git show <sha>:<path>` 對照自己實際編輯的內容範圍，出現非自己寫入的變更即為夾帶。**處置**：依上方 Commit 規範不 revert / reset / amend，記錄 commit SHA 與受影響檔案回報 PM。**Action**：兩票 `where.files` 宣告同一檔案時必須序列化，不因改用本命令而豁免；派發前以 `ticket track conflicts --for <本票>` 確認無其他 in_progress 票宣告該檔（見 `.claude/pm-rules/parallel-dispatch.md`「派發前 where.files 交集檢查」）。

**append-only 共用檔只提交本票的行**：輸入含 `docs/work-logs/topic-assignments.txt` 或票所屬版本工作日誌時，這兩檔不整檔 stage，改以 `commit_files_isolated` 的 `append_lines` 提交「HEAD 各行 + 本票新增的行」。本票的行 = 工作區相對 HEAD 新增、且 topic 行首欄等於票 ID／工作日誌行含票 ID（整詞比對，不命中較長 ID 前綴與 `.N` 子票）者；他票未提交的行留在工作區。共用檔無本票的行時不提交該檔並輸出 `[INFO]`；整批只剩這類檔且全無本票的行時 exit 0 不提交。只剩共用檔有本票的行時，以票自身 md 作主路徑（`commit_files_isolated` 在 paths 為空時直接回 empty、不處理 `append_lines`）；票面不存在於 repo root（例如 `--worktree`）則報錯。副作用：共用檔內對 HEAD 既有行的修改或刪除不會被本命令提交。

### 歸屬 trailer 自動補全

訊息缺 `Co-Authored-By:` 行時，CLI 讀 transcript 最後一則 assistant 訊息的 `model`，依通則 `claude-<family>-<major>-<minor>` 推為 `Claude <Family> <major>.<minor>`（`lib/commit_attribution.py` 的 `MODEL_DISPLAY_NAMES` 只收通則不正確的例外項），補在訊息最末段（`Co-Authored-By: <顯示名稱> <noreply@anthropic.com>`）。已含該行時不動；有 `Claude-Session:` 行但與 Co-Authored-By 不相鄰時，移到其後相鄰。transcript 位置：主 session 為 `~/.claude/projects/<專案目錄編碼>/<CLAUDE_CODE_SESSION_ID>.jsonl`；子代理人（以 cwd 的 git toplevel 位於 `.claude/worktrees/agent-<id>` 判定，不看 `AI_AGENT`）為 `.../<父 session id>/subagents/agent-<id>.jsonl`。共用 checkout 內的子代理人會被當成主 session（實作代理人由 hook 強制用 worktree，共用 checkout 者僅唯讀審查、不提交）。讀不到 transcript、或 model id 無法推導顯示名稱時，只印 `[WARNING]` 不補，提交照常成立（exit code 不變）；不使用父 session 的值。

### `--worktree` 條件

判斷條件是**呼叫 `ticket track commit` 當下 CLI process 的 cwd**；「檔案變更所在位置」不是判斷條件：未帶 `--worktree` 時，repo root 解析為 `resolve_project_cwd()` 所屬 repo，即 process cwd 所在的 repo（ticket shim 慣例於主 repo cwd 執行，故此路徑恆解析為主 repo）；帶 `--worktree <絕對路徑>` 時改以該路徑對應的 git repo root 為準（見 `track_commit.py:_resolve_repo_root` docstring）。**Consequence**：子代理人每次 Bash 呼叫的 cwd 依 harness 慣例重設回主倉庫，即使變更檔案實際存在於 linked worktree 內，只要呼叫當下 cwd 不在該 worktree，未帶 `--worktree` 就會綁定主 repo working tree 執行 git 操作——新檔案無法 `add`（不在主 repo working tree 認知範圍）、已修改檔案因主 repo 版本未變而誤判為空 tree 短路（見下方 Exit code 表）。**Action**：cwd 是否在目標 worktree 內不確定時，一律帶 `--worktree`；三種情境須逐一判斷（agent cwd 在 worktree 內／agent cwd 在主倉庫／PM cwd 被 runtime 切進 worktree，第三種見 `.claude/skills/worktree/references/agent-isolation-worktree.md`〈EnterWorktree mid-session 切換〉），檔案位置本身不足以推論是否需要此旗標。

### 與 append-log／complete auto-commit 的關係

本命令、`append-log`（每次寫入自動 commit ticket md）、`complete`（自動以隔離索引 commit ticket metadata）是三條互不重疊的 commit 路徑——本命令提交程式碼變更，另兩者提交 ticket 狀態，三者恆分屬不同 commit（見上方「complete 副作用」節）。

### Fallback 條件

僅當本命令發生**環境性失敗**（隔離索引的 git 步驟失敗、update-ref 撞鎖或 HEAD 競爭；先重跑本命令，持續失敗才降級）或不可用時，才降級為「精確 `git add` + `git diff --cached --name-only` 核對 + 裸 `git commit`」（無 pathspec / `--only` / `-o` / `-a`），見 `.claude/rules/core/bash-tool-usage-rules.md` 規則七。**判準性拒絕不適用 fallback**（worktree 票面、where.files 未宣告、範圍外檔案、提交範圍自我驗證失敗）：這是命令在執行範圍保護，改走裸 commit 等於繞過；應停手回報 PM 以 set-where 補宣告或移除檔案。輸入錯誤（ticket 不存在、`--worktree` 非 git 目錄）修正輸入後重跑本命令。拒絕訊息尾端的 `[NEXT]` 行即依此分類給出指示。本命令走隔離索引、全程不觸碰共用 index，是本框架消除「共用 index 被反覆吸入他票內容」風險的權威路徑，非 fallback 的替代品，不因方便而優先選 fallback。**並行度註記**：fallback 一旦選用即回到共用 index，`append-log`／`complete` 的隔離索引 CAS 可能已在同一視窗把 HEAD 往前推進，使 fallback 前已 `git add` 的 entry 相對新 HEAD 過期；裸 commit 前須先比對 `git show :<path>` 與 `git show HEAD:<path>`，判定過期則 `git restore --staged <path>` 後重新 add，見 `.claude/rules/core/bash-tool-usage-rules.md` 規則七「版本邊界（過期 index 快照）」。

### Exit code

| 值 | 說明 |
|----|------|
| 0 | commit 成功，或檔案內容與 HEAD 相同（空 tree 短路，視為成功） |
| 1 | ticket 不存在／`where.files` 未宣告寫入路徑／檔案超出宣告範圍／目標本身是 symlink 或其路徑解 symlink 後落在 repo 之外／`--worktree` 非合法 git 目錄或不屬本 repo 的 `git worktree list --porcelain`（`rev-parse` 或 `worktree list` 查詢失敗時同樣拒絕，保守一側）／提交失敗。symlink 與 worktree 歸屬拒絕屬判準性拒絕，不得改走 fallback，與 `track move-lines` 共用 `lib/write_scope.py` 同一判準 |

**exit 0 不等於已產生 commit**：兩種情形皆回傳 0，stdout 卻不同——`[OK] 已提交 <sha>` 才代表真正產生 commit；`[INFO] 檔案內容與 HEAD 相同，無需提交（空 tree 短路）。若變更實際發生在 linked worktree 但未帶 --worktree，本命令對該變更零感知；請確認已加 --worktree <worktree 絕對路徑>。` 代表本次呼叫未產生任何 commit（該 repo root 對比的 HEAD 版本已含此內容，或——見上方 `--worktree` 條件——cwd 誤判導致比對到錯誤 repo 的 HEAD，訊息句尾即為此情形的明確提示）。**Action**：判斷是否已產生 commit 一律讀 stdout 首行字面，不可僅憑 exit code 0 判定「已提交」；看到空 tree 短路訊息且變更確實發生在 worktree 內，依提示補 `--worktree` 重試。

## track set-exit-status 子命令

代理人結束時以結構化欄位回報執行結果，取代僅在 body 手動貼 YAML 區塊。

### 用法

```bash
ticket track set-exit-status <ticket_id> --status success --confidence 1.0
ticket track set-exit-status <ticket_id> --status needs_context --reason "缺少 X 的權威定義" \
  --confidence 0.6 --acceptance-met 1 2 --acceptance-unmet 3
```

### Flag 說明

| Flag | 必要 | 說明 |
|------|------|------|
| `--status` | 必要 | 枚舉：`success` / `needs_context` / `blocked` / `partial_success` / `failed` |
| `--confidence` | 必要 | 信心度（0.0-1.0） |
| `--reason` | 選填 | 狀態原因說明 |
| `--acceptance-met` | 選填 | 已完成的 acceptance index 列表 |
| `--acceptance-unmet` | 選填 | 未完成的 acceptance index 列表 |
| `--artifacts` | 選填 | 產出檔案路徑列表 |
| `--version` | 選填 | 指定版本（預設自動偵測 active 版本） |
| `--force` | 選填 | 逃生閥：旁路 status precondition 檢查（記入 hook-logs） |
| `--as` | 選填 | 申報執行身份，與票面 `who.current` 比對（委派給既有 `identity_guard.check_identity`，非重造）；未提供時 warn-only（向後相容，不阻擋）；提供且與 `who.current` 不符則 deny，不寫入 |

**`--as` 身份檢查與 `--force` 的邊界**：`set-exit-status` 不屬 `ENFORCED_COMMANDS`，故未帶 `--as` 時仍維持既有 warn-only 行為。`--force` 僅旁路上方 status precondition 檢查，與 `--as` 的身份比對是獨立檢查，不可用 `--force` 旁路身份不符的 deny——此檢查的目的即防止接手者代填他人票的 Exit Status 章節，製造 `reclaim` 鑑識三查第 3 查（缺 Exit Status）通過的假象（見〈track reclaim 子命令〉Ghost 鑑識三查）。

### 與骨架「遇阻」句的關係

派發骨架收尾句要求遇阻時寫 NeedsContext（`append-log`）並回報，本命令是該回報的結構化落地點；`--status` 對照 exit code 供上游程式化判讀：`success` / `partial_success` → 0，`needs_context` / `blocked` → 2，`failed` → 1。

## Ticket 狀態與程式碼提交的 root 分離（worktree 場景）

在 linked worktree（`/worktree create` 建立）內執行 `ticket track` 系列命令時，ticket 狀態（md 讀寫與其 auto-commit）與程式碼提交走**兩條不同的 root 解析路徑**，行為刻意相反：

| 操作類型 | 對應函式 | linked worktree 內的 root 解析 |
|---------|---------|-------------------------------|
| ticket 狀態（`claim` / `append-log` / `check-acceptance` / `set-*` 等讀寫 ticket md） | `paths.py:get_ticket_state_root()` | **反向回推主倉庫根目錄**，統一寫入主倉庫，不進 worktree 分支 |
| 程式碼提交（`ticket track commit`） | `project_root.py:resolve_project_cwd()` | 依呼叫當下 cwd 或 `--worktree` 旗標解析（見「track commit 子命令」〈`--worktree` 條件〉），非恆定「維持 worktree 感知」——未帶旗標且 cwd 不在目標 worktree 內時會誤綁主 repo |

**Why**：若 ticket 狀態也採 worktree 感知（跟隨呼叫端 cwd），多個隔離 agent 會各自把票面寫進自己的 worktree 分支——PM 在主倉庫看不到最新狀態（觀察性失效），且 body 內容不會隨 worktree 分支合併帶回主倉庫。受控實驗實測：5 個並行派發的 worktree agent 樣本中 5 個全數出現票面分裂（即 5/5，非估計值）。統一寫入主倉庫消除分裂，使 ticket 狀態恆有單一事實來源。

**Consequence（誤判為缺陷時）**：worktree 內執行 `ticket track full <id>` 讀到的內容是主倉庫版本，不是該 worktree 分支上的版本；這是設計行為，不是 CLI 的 cwd 解析漏洞。誤判並「修復」（例如讓 ticket 狀態也改用 worktree 感知）會反轉此設計，重新引入票面分裂風險——曾有 IMP ticket 依此誤判方向規劃修復，經查證後改為本節文件澄清。

**Action**：worktree 內需要確認「某次 ticket 狀態寫入是否已進入主倉庫」時，直接在主倉庫 cwd（或用 `git -C <主倉庫路徑>`）查詢，不依賴該 worktree working tree 內的 ticket md 檔案內容（後者不會被 ticket 狀態寫入更新）。完整設計理由見 `.claude/skills/ticket/ticket_system/lib/paths.py` 的 `get_ticket_state_root()` docstring；worktree 隔離邊界的完整脈絡（含 daemon-rooted 寫入工具洩漏等其他項目）見 `.claude/skills/worktree/references/agent-isolation-worktree.md`「Base ref 與隔離邊界」節。
