---
name: ticket
description: 'Use this skill whenever the user wants to create, track, query, or manage tickets. Triggers include: creating new tickets, claiming or releasing tickets, checking ticket status or progress, completing tickets, handing off work between agents, resuming interrupted tasks, migrating tickets between versions, converting plans to tickets, splitting tickets into subtasks, evaluating ticket granularity, or any mention of /ticket, task tracking, ticket lifecycle operations, or ticket splitting. 拆分相關：當用戶問「ticket 怎麼拆」「拆分粒度」時，建立/拆分 ticket 用本 skill，拆分邊界判讀（測試變綠驗收點）見 /tdd skill 的 task-granularity-rules。'
argument-hint: '<subcommand> [args]'
allowed-tools: Bash(ticket *), Read, Write, Edit, Grep, Glob
metadata:
  version: 2.20.0
---

# Ticket System v1.0

統一 Ticket 系統 - 整合 create/track/handoff/resume/migrate/generate 六大功能。

---

## 系統模型（設計自我描述）

本系統的參照模型是 **issue tracker + CI runner**（batch job queue 為輔助類比），不是 OS process：

| 對應 | 參照 | 含義 |
|------|------|------|
| ticket = issue | issue tracker（Jira/Linear/GitHub 類） | 狀態機轉移經 CLI 驗證、stale 需 triage 儀式、ID 為全域引用錨點 |
| agent = CI runner | ephemeral runner | 身份在派發/認領時綁定（`claim --as`）、工作區以隔離 checkout 為優先、逾時由 watchdog 回收 |
| wave = batch cohort | job queue 批次 | blockedBy DAG 之外的隱式排序層 |

**三個與 OS process 直覺相反的預設**（設計回顧確認：誤用 process 直覺是共享樹競態與身份回填缺口兩類歷史事故的共同根因）：

1. **身份晚綁定**：ticket 建立時不知道執行者（submit 與 assign 分離）；身份在 claim 時以 `--as` 綁定，不是 fork 即繼承。
2. **共享工作區**：agent 預設共享 working tree（thread 語意）而非 process 隔離；檔案變更型派發應優先採 feat branch / worktree 隔離。
3. **type 與 instance 一對多**：agent 類型（能執行某類任務的角色，如「能做 IMP 的類型」）與執行體（實際在跑的 process）不是一對一，同一類型可同時 spawn 多個獨立執行體；「該類型只有一種」不等於「同時只能跑一個」。**反向風險**：誤讀為可無限開執行體同樣危險，真正的並行上限來自三項約束——共享 git index 的寫入競爭、主線程自身序列化的驗收與建票工作、單一執行體 context 隨任務數累積而飽和，而非類型數。

> scheduler 層類比（runqueue/dashboard 對應 Linux schedule()/top）仍然準確，保留使用。

**named agent 生命週期三態**（v2.9.0 擴展）：`agent = CI runner` 類比原僅二態（running → stopped），named agent（Agent tool 帶 name 參數 spawn）完工後不自動終止，實際存在第三態：

| 狀態 | 含義 | 觸發 | 對應 CI runner 語意 |
|------|------|------|---------------------|
| running | agent 正在執行 ticket 工作 | Agent tool spawn / SendMessage 派發新任務 | job 執行中 |
| idle | agent 完工無新任務，process 保持存活且可定址 | agent 完成回報後 CC runtime 發送 `idle_notification` | warm runner（跑完不銷，省下次冷啟動成本） |
| stopped | agent process 終止 | SubagentStop（自然結束）/ `shutdown_request` approve / session 結束 | job 完成後 runner 回收 |

idle 態不改變 agent = runner 的核心類比（身份仍在 claim 綁定、工作區仍隔離），只是擴展 runner 生命週期從「單 job 即銷」到「可選續用多 job」。PM 對 idle agent 的續用/放生判準與回收 SOP 見 `.claude/pm-rules/parallel-dispatch.md`「idle agent 回收 SOP」章節。

---

## Ticket 狀態與程式碼提交的 root 分離（worktree 場景）

在 linked worktree（`/worktree create` 建立）內執行 `ticket track` 系列命令時，ticket 狀態（md 讀寫與其 auto-commit）與程式碼提交走**兩條不同的 root 解析路徑**，行為刻意相反：

| 操作類型 | 對應函式 | linked worktree 內的 root 解析 |
|---------|---------|-------------------------------|
| ticket 狀態（`claim` / `append-log` / `check-acceptance` / `set-*` 等讀寫 ticket md） | `paths.py:get_ticket_state_root()` | **反向回推主倉庫根目錄**，統一寫入主倉庫，不進 worktree 分支 |
| 程式碼提交（`ticket track commit`） | `project_root.py:resolve_project_cwd()` | 維持 worktree 感知，commit 進該 worktree 對應分支 |

**Why**：若 ticket 狀態也採 worktree 感知（跟隨呼叫端 cwd），多個隔離 agent 會各自把票面寫進自己的 worktree 分支——PM 在主倉庫看不到最新狀態（觀察性失效），且 body 內容不會隨 worktree 分支合併帶回主倉庫。受控實驗實測：並行派發的 worktree agent 在此設計下全數出現票面分裂。統一寫入主倉庫消除分裂，使 ticket 狀態恆有單一事實來源。

**Consequence（誤判為缺陷時）**：worktree 內執行 `ticket track full <id>` 讀到的內容是主倉庫版本，不是該 worktree 分支上的版本；這是設計行為，不是 CLI 的 cwd 解析漏洞。誤判並「修復」（例如讓 ticket 狀態也改用 worktree 感知）會反轉此設計，重新引入票面分裂風險——曾有 IMP ticket 依此誤判方向規劃修復，經查證後改為本節文件澄清。

**Action**：worktree 內需要確認「某次 ticket 狀態寫入是否已進入主倉庫」時，直接在主倉庫 cwd（或用 `git -C <主倉庫路徑>`）查詢，不依賴該 worktree working tree 內的 ticket md 檔案內容（後者不會被 ticket 狀態寫入更新）。完整設計理由見 `.claude/skills/ticket/ticket_system/lib/paths.py` 的 `get_ticket_state_root()` docstring；worktree 隔離邊界的完整脈絡（含 daemon-rooted 寫入工具洩漏等其他項目）見 `.claude/skills/worktree/SKILL.md`「Base ref 與隔離邊界」節。

---

## 執行方式

> **禁止直接執行 Python 檔案！** `ticket_system` 是 Python 套件，必須透過 `pyproject.toml` 定義的入口點執行。

### 全局安裝（推薦）

`ticket` CLI 透過 cwd-resolving shim 安裝（非 `uv tool install`，ARCH-APP-002 / framework issue #12）。shim 依當前 cwd 所在專案的 git toplevel 解析 `.claude/skills/ticket` 源碼並 `uv run`，故源碼即時生效、不需 reinstall、多專案共用同名 skill 不碰撞。

```bash
# 首次安裝（一次安裝 ticket / doc / worktree 三個 shim）
python3 .claude/scripts/install-skill-clis.py

# 之後在任何目錄執行
ticket track summary
ticket track claim <id>
```

**修改原始碼後無需重新安裝**：shim 每次執行都 `uv run` 當前專案源碼，改動即時生效。
（檢查是否已 shim 化：`python3 .claude/scripts/install-skill-clis.py --check`）

### 本地執行

```bash
(cd .claude/skills/ticket && uv run ticket track summary)
```

### 常用範例

```bash
ticket track summary                                    # 摘要
ticket track query <id>                               # 查詢
ticket track claim <id>                               # 認領
ticket track complete <id>                            # 完成（自動以隔離索引提交本票 md + worklog index，排除 children/siblings 以避免夾帶他票 WIP，不留 staged 殘留於共用 index，成功時 stdout 印出 commit SHA；cascade 狀態解鎖機制詳見下方「父 ticket 含未完成 children」說明，屬另一機制）
ticket track complete <id> --no-stage                 # 完成但跳過自動提交（保留用戶手動掌控 commit 範圍）
ticket track complete <id> --force                    # 強制完成（旁路未完成 children 阻擋）
ticket create --version 0.31.0 --wave 4 --action "實作" --target "XXX"  # 建立
```

### subagent 派發時 claim 推薦用法

被派發的 subagent 認領自身 ticket 時，**推薦使用 `ticket track claim <id> --as <self-agent-name>`**（申報自身身份；不加 `--verify`）。

**Why**：`claim --as <agent>` 在認領時把 `who.current` 寫成執行者身份，使後續 `complete --as <self>` 與 identity-guard 對稱通過，無需 `set-who` 繞過。`--as` 在 `file_lock` 內與 status 寫入同一原子操作（load → modify → save），不執行 AC 驗證、不讀 stdin、不偵測 TTY，subagent 無 TTY 的互動環境受限完全無影響。`--as` 與 `--verify` 正交：`--as` 只設身份，不觸發任何驗證副作用。

> **為何需要 `--as`**：建立 ticket 未指定 `--who` 時 `who.current` 預設為字面 `"pending"`。裸 `claim`（不帶 `--as`）不寫 `who.current`，後續 `complete --as <agent>` 因 `"pending" != <agent>` 被 identity-guard deny（情境 4），agent 須先 `set-who` 繞過。`--as` 從源頭消除此縫隙。裸 `claim`（不帶 `--as`）維持向後相容，仍可用，但收尾時須自行 `set-who`。

**Consequence**：若 subagent 改用 `--verify`（明示啟用 AC 自動驗證，僅供除錯場景），在無 TTY 環境下會觸發 fail-closed：未加 `--yes` 時直接 return 1 並印出「非互動環境且未指定 --yes，已取消」，subagent 可能誤判 ticket 未 claim 而重試或放棄。`--verify` 還會在 claim 時跑 AC 對應的驗證指令（如 npm test 全套件），造成同 wave 並行 claim 衝突（PC-078）。

**Action**：

| 場景 | 推薦命令 | 說明 |
|------|---------|------|
| subagent 認領被派發的 ticket（常態） | `ticket track claim <id> --as <self-agent-name>` | 設 who.current，後續 complete --as 對稱通過 identity-guard，免 set-who |
| 不申報身份的裸認領（向後相容） | `ticket track claim <id>` | 不碰 who.current；收尾若需 complete --as 須自行 set-who |
| 除錯時想 claim 並同時跑 AC 驗證 | `ticket track claim <id> --verify --yes` | `--yes` 在非互動環境短路驗證 prompt 為 y，避免 fail-closed |
| 只想看 AC 驗證結果不 claim | `ticket track verify <id>` | 與 claim 解耦（`--skip-verify` 已移除，改用此子命令） |

> **半成功歷史背景**：早期 `claim --yes` 在 subagent 無 TTY 環境曾因互動受限出現 metadata 部分寫入、需 `--skip-verify` 二次嘗試確認的半成功狀態。此 root cause 已由「claim 預設不驗證」+「移除 `--skip-verify`」兩階段修正消除；現行裸 `claim` 路徑無此問題。

---

## 無子命令時的預設行為（dashboard-first，v2.7.0 起）

當用戶輸入 `/ticket`（無子命令或參數）時，依序執行以下流程：

1. **取得接手聚合視圖** — 執行 `ticket track dashboard --top 5`

   dashboard 一次回傳 `[In Progress]` + `[Ready Top N]` + `[Stale Warning]` 三章節，Ready 章節含可直接 claim 的編號 `[1] [2] [N]` 與 priority 標籤。設計目的：將 PM 接手流程從 baseline 7 tool call 降至 2-3 tool call（ANA 結論方向 a）。

   [In Progress] 條目帶 lease 狀態標記（判準同 registry heartbeat）：`[LIVE]` = FRESH session 正在處理；`[RECLAIMABLE]` = 已知無 FRESH session 佐證持有（可能已 STALE，也可能 registry 根本未追蹤此票——含 graceful SessionEnd 釋放後 entry 已刪除的情形，兩者現統一標記，皆須走 reclaim 鑑識判定）；無標記 = registry 本身不可用（模組載入失敗 / 非 git 環境 / 讀取降級），無法判定。**`[LIVE]` 票禁止列入接手選項**——活躍 session 正在處理，接手即與其重複處理同一張票（framework issue tarrragon/claude#78）。

   - **dashboard 有 in_progress 或 ready 任務** → 使用 AskUserQuestion 依 dashboard 順序列出選項：
     - `[LIVE]` 的 in_progress 票**不列入選項**，僅在 AUQ 前的回覆文字中資訊性提及（「N 張由其他 session 處理中」）
     - 非 `[LIVE]` 的 in_progress 任務優先列出（label: `[ip] {ticket_id} - {title}`；`[RECLAIMABLE]` 者 description: `無 FRESH session 佐證持有（走 reclaim 鑑識，非直接 resume）`；無標記者 description: `registry 無法判定（resume 接手）`——正常環境下極少出現，僅 registry 本身不可用時觸發）
     - Ready 任務依 dashboard `[1] [2] [N]` 編號順序列出（label: `[{N}] {ticket_id} - {title}`, description: `[{priority}]`）
     - 額外選項：「建立新 Ticket」（description: `執行 /ticket create`）
     - 用戶選擇：
       - 無標記 in_progress 任務 → `ticket resume <selected_id>`
       - `[RECLAIMABLE]` 任務 → `ticket track reclaim <selected_id>`（dry-run 鑑識通過再 `--confirm`，詳見 track reclaim 章節）
       - Ready 任務 → `ticket track claim <selected_id>`
       - 建立新 Ticket → 引導進入 `/ticket create` 流程
     - 流程結束
   - **dashboard 只有 `[LIVE]` in_progress、無其他任務** → 回覆文字告知處理中清單後進入步驟 2 fallback（fallback 清單同樣不把 `[LIVE]` 票列為選項）
   - **dashboard 無 in_progress 也無 ready** → 進入步驟 2 fallback

2. **Fallback：完整 pending/in_progress 清單**（僅當步驟 1 dashboard 無結果時觸發） — 執行 `ticket track list --status pending in_progress`

   - **有待辦任務** → 使用 AskUserQuestion 列出選項：
     - 各待辦任務作為選項（label: `{ticket_id} - {title}`, description: `狀態: {status}`）
     - 額外選項：「建立新 Ticket」（description: `執行 /ticket create`）
     - 用戶選擇既有任務 → 依狀態處理（pending → claim，in_progress → resume）
     - 用戶選擇「建立新 Ticket」→ 引導進入 `/ticket create` 流程
     - 流程結束

3. **無任何待辦** → 顯示子命令總覽（下方表格）

> **完整待恢復清單檢視/除錯**：可改用 `ticket resume --list`（子命令保留，獨立於 dashboard-first 流程）。
> **scheduler 接手建議單獨查詢**：可改用 `ticket track runqueue --context=resume --top 3`（保留作除錯/腳本用途，但 PM 接手流程不再呼叫）。

---

## 統一命令格式

```bash
/ticket <subcommand> [options]
```

> **命令層級慣例**：`create` / `batch-create` / `show` / `handoff` / `resume` / `migrate` / `generate` 是**頂層命令**（`ticket create ...`）；`claim` / `complete` / `append-log` / `query` / `list` / `set-acceptance` 等狀態操作在 **`track` 之下**（`ticket track <op> ...`）。常見誤打：`ticket track create`（錯，create 非 track 子命令）、`ticket claim`（錯，claim 在 track 下）。本標註僅說明既有慣例，零 CLI 行為變更（Never break userspace）。

## 子命令總覽

| 子命令              | 用途                       | 範例                                                                       |
| ------------------- | -------------------------- | -------------------------------------------------------------------------- |
| `create`            | 建立新 Ticket              | `/ticket create --version 0.31.0 --wave 1 --action "實作" --target "XXX"`  |
| `batch-create`      | 批次建立 Tickets           | `/ticket batch-create --template impl-parsley --targets "a,b,c" --wave 28` |
| `track`             | 追蹤 Ticket 狀態           | `/ticket track summary`                                                    |
| `track dashboard`   | PM 接手聚合視圖 | `ticket track dashboard --top 5`                                           |
| `track list`        | 預設 top 10 priority 排序 | `ticket track list --status pending --top 20`                  |
| `track td-status`   | TD 清單校準（PC-094）      | `ticket track td-status <id>`                                    |
| `track reclaim`     | 已鎖 ticket 受控釋放（ghost 鑑識三查，multi-PM Phase 3） | `ticket track reclaim <id> --confirm` |
| `track stuck-anas`  | 列出卡住的 ANA（in_progress 且落地路徑 spawned_tickets／children 全 completed） | `ticket track stuck-anas --wave 3`         |
| `track depth`       | 查詢嵌套深度與 can_descend（沿 parent_id 鏈） | `ticket track depth <id>.5`                          |
| `track parallel-check` | 偵測子任務/兄弟 ticket 檔案衝突（對齊 askuserquestion-rules 規則 7） | `ticket track parallel-check <id>` |
| `track dispatch-validate` | Context Bundle 自動填料合理性檢查（C 方案安全網；exit 0=pass / 1=軟警告 / 2=硬失敗或 IO 錯誤；**與 dispatch-check 的 exit code 語意不共享**，需以命令名稱判別） | `ticket track dispatch-validate <id>` |
| `track dispatch-readiness` | 派發前認知負擔閾值檢查（三項閾值：功能職責數 / 修改檔案數 / Context Bundle tokens；exit 0=pass / 1=軟警告 / 2=強制拆分或 IO 錯誤；**與 dispatch-check / dispatch-validate 的 exit code 語意不共享**；閾值 1 以 acceptance 條目近似，含驗證類條目時可能高估，PM 於 WARN/FAIL 應手動覆核——詳見 references/track-command.md） | `ticket track dispatch-readiness <id>` |
| `show`              | 顯示 Ticket（含渲染）      | `ticket show <id>` / `ticket show <id> -r`                           |
| `handoff`           | 任務交接                   | `/ticket handoff <id> --to-sibling <id2>`                   |
| `resume`            | 恢復任務                   | `/ticket resume <id>`                                                      |
| `migrate`           | Ticket ID 遷移             | `/ticket migrate <old-id> <new-id>`                                |
| `generate`          | Plan 轉換為 Tickets        | `/ticket generate plan.md --version 0.31.0 --wave 5`                       |

---

## 子命令詳細說明

各子命令的完整用法和參數說明，請參閱對應的 reference 檔案：

### create - 建立新 Ticket

建立 Atomic Ticket，支援 5W1H 引導式建立、子 Ticket 建立、版本目錄初始化（init）。

> **版本歸屬引導**：create 時根據 `--type` 和 `--action` 自動建議目標版本。新功能（IMP + 實作/新增/建立/開發）→ 大版本（0.x+1.0）；修復/改善/分析/文件 → 小版本（最新已完成版本 +1 patch）。未指定 `--version` 時自動套用建議；指定但與建議不符時輸出 WARNING（不阻擋）。

> 決策樹：Read `references/workflow-create.md`
> 詳細用法：Read `references/create-command.md`
> 血緣 vs 衍生：`--parent` vs `--source-ticket` 對比表見 `references/create-command.md`「--parent vs --source-ticket 對比表」章節（PC-073）
> 重複偵測：Tier 1 警告層（相似度 >= 0.3，不阻擋）+ Tier 2 阻擋層（同窗口高相似度 exit 1，`--allow-duplicate` 旁路）；見 `references/create-command.md`「重複偵測（兩層防護）」章節

> **主題歸屬（自動推導）**：未指定 `--topic` / `--new-topic` 時，`create` 依三條判準自動推導主題，命中即自動指派並印出依據，建票者可否決後改派：
>
> | 判準 | 條件 | 成本 |
> |------|------|------|
> | S1 上游繼承 | `--source-ticket` 或 `--parent` 的上游已有主題 | 約 32 ms |
> | S2 檔案叢集 | `--where` 路徑與某主題既有涵蓋路徑交集達 3 段特異性 | 約 350-490 ms（僅 S1 未命中時執行） |
> | S3 ANA 標記 | `--type ANA` 且 S1/S2 皆未命中 | 僅輸出提示，不阻擋 |
>
> 三判準皆未命中時印 WARNING 但**不改 rc**（過渡期 warn-only）：以 exit code 表達強制力會讓代理人誤判建票失敗而重試。要免除警告有兩條路——指定主題，或以 `--no-topic` 明示不指派（該旗標與 `--topic` / `--new-topic` 互斥，同給時於任何持久化前 exit 1）。
>
> 顯式 `--topic` / `--new-topic` 一律優先，推導只在兩者皆未給時啟動。S2 設 3 段特異性門檻是因為 `docs/` 這類單段路徑與該目錄下任何路徑都相交，不設門檻會使擁有淺層路徑的主題成為所有新票的推導結果。改派用 `ticket track topic-backfill-assign --reassign`。

> **`--discovered-during` vs `--source-ticket`（發現衍生 vs 規劃衍生）**：兩者皆記錄衍生血緣，但語意不同、彼此互斥（同給時於任何持久化前 exit 1）：
>
> | 旗標 | 適用情境 | 上游主題的意義 | 對 S1 判準的影響 |
> |------|---------|---------------|-----------------|
> | `--source-ticket` | 規劃衍生：ANA 拆 IMP、父票拆子票，上游本就決定了新票主題 | 主題必然相同 | S1 正常繼承 |
> | `--discovered-during` | 發現衍生：執行中撞到跨主題問題，主題取決於撞到什麼，與上游無關 | 只反映「當時剛好在改哪個檔案」 | S1 短路不觸發 |
>
> 新票的 `discovered_during` frontmatter 欄位記錄血緣供追溯，但不驅動任何主題指派——S2 檔案叢集判準不受影響，仍依新票自身 `--where` 正常運作（可能命中，也可能未命中）。

**常用範例**：

```bash
# 建立根任務（必須提供 decision-tree 三參數）
ticket create --version 0.2.0 --wave 2 --action "實作" --target "HTTP Handler" --type IMP \
  --decision-tree-entry "第五層:TDD" \
  --decision-tree-decision "Phase 3b 完成後建立重構 Ticket" \
  --decision-tree-rationale "quality-baseline-rule-5"

# 建立子任務（--parent 自動產生子序號，可省略 decision-tree 參數）
ticket create --parent "<id>" --action "實作" --target "事件融合層"

# DOC 類型（可省略 decision-tree 參數）
ticket create --version 0.2.0 --wave 2 --action "撰寫" --target "工作日誌" --type DOC

# 多值參數格式
#   --acceptance：多次指定或用分隔符（vertical bar）分隔
ticket create ... --acceptance "條件A" --acceptance "條件B"
ticket create ... --acceptance "條件A|條件B|條件C"
#   注意：分隔符是 --acceptance 的多條拆分字元。
#   若 acceptance 內文本身需含該字元（如描述 shell pipe「-q | tail」），
#   用反斜線跳脫保留字面，避免被靜默拆條：
ticket create ... --acceptance "重現實證 -q \| tail 導致 0 行"
#   未跳脫時，單一 --acceptance 值被拆成多條會印出 [WARNING] 供確認。

#   --where：逗號分隔
ticket create ... --where "file1.py,file2.py"

#   --blocked-by / --related-to：逗號分隔
ticket create ... --blocked-by "<id>.1,<id>.2"
```

### batch-create - 批次建立 Tickets

從模板 + 目標清單快速建立多個 Tickets。適用於大量同質任務場景（如 30 個實作子任務）。

> **邊界**：`batch-create` 只建立 tickets，不派發 agents。多任務派發前先寫 dispatch-plan，保留每張 ticket 的獨立 prompt、commit policy 與 Exit Status；禁止把 batch-create 誤用為 batch dispatch CLI。

**使用情境**：

- W28 場景：快速建立 30 個相同類型的實作任務
- 需要多個同質 Ticket，避免逐一手工填寫

**命令格式**：

```bash
# 基本用法
ticket batch-create --template impl-parsley --targets "目標1,目標2,目標3" --wave 28

# 指定版本
ticket batch-create --template impl-parsley --targets "a,b,c" --version 0.31.0 --wave 28

# 預演模式（只顯示摘要，不建立檔案）
ticket batch-create --template impl-parsley --targets "a,b,c" --dry-run

# 建立子任務
ticket batch-create --template impl-parsley --targets "a,b" --parent <id>
```

**參數說明**：

- `--template` (必填)：使用的模板名稱（如 `impl-parsley`）
- `--targets` (必填)：目標清單，逗號分隔（如 `"BookCard Widget,LibraryListPage"`）
- `--version` (可選)：目標版本，預設自動偵測
- `--wave` (可選)：Wave 編號，預設為 1
- `--parent` (可選)：父 Ticket ID，用於建立子任務
- `--dry-run`：預演模式，只顯示摘要不建立檔案

**預定義模板**：

- `impl-parsley`：parsley-flutter-developer 實作 Ticket 模板（type: IMP, who: parsley-flutter-developer）
- 更多模板可在 `ticket_system/templates/` 目錄中定義

> 詳細設計：參考評估報告（CLI 設計、使用者體驗、批次操作流程）

### track - 追蹤和更新 Ticket 狀態

包含 READ 操作（summary/query/version/tree/chain/deps/full/log/list/board/agent/5W1H/validate/**runqueue**/**dashboard**/stale-list/td-status/stuck-anas/**list-artifacts**）和 UPDATE 操作（claim/complete/release/reclaim/set-who/set-what/set-when/set-where/set-why/set-how/phase/check-acceptance/set-acceptance/**set-closed-by**/append-log/**dispatch**/add-child/**set-parent**/batch-claim/batch-complete/audit/accept-creation/add-spawn-request/resolve-spawn-request/**register-artifact**/**resolve-artifact**/**add-exempt-marker**）。`list` 支援 `--wave`、`--status`、`--format`、`--top`、`--all` 篩選參數（預設 `--top 10`，priority 排序）。

> **Scheduler — `runqueue`**：回答「下一個該做哪個 ticket」。Linux schedule()/runqueue/top/ps 類比。合併原 next+schedule+resume-hint 為單一命令。
>
> ```bash
> ticket track runqueue --wave 17                    # 可執行清單（blockedBy=[] pending，priority 排序）
> ticket track runqueue --wave 17 --format=dag       # 完整 DAG + 關鍵路徑高亮
> ticket track runqueue --context=resume --top 3     # 與 handoff/pending 交集（接手建議）
> ticket track runqueue --wave 17 --groups           # 依 where.files 交集取貪婪極大獨立集，切可並行集合與本輪未選入清單（優先於 --format，multi-PM Phase 3）
> ```
>
> 新 session 啟動時 `session-start-scheduler-hint-hook` 自動呼叫 `runqueue --context=resume`，結果以 hook additionalContext 顯示。PM 迷失方向時優先執行，免靠記憶判斷先後順序。清單項可能疊加 `[STALE]`（票面 `started_at` 判定久未更新）與 `[RECLAIMABLE]`（registry 已知無 FRESH session 佐證持有——持有者已死或 registry 根本無此票紀錄，僅輕量 heartbeat 判準，非 `reclaim` 實際放行判定）兩種並列標記。詳見 `references/track-command.md`「track runqueue 子命令」章節。
>
> **`blockedBy=` 語意提醒**（2026-08-24）：輸出中的 `blockedBy=[...]` 與 ticket frontmatter 的 `blockedBy` 欄位同名，但值不同——輸出只列**尚未解除**的 blocker，blocker 一旦 completed/closed 就從清單移除；frontmatter 原值則保留宣告時的完整清單，不隨 blocker 狀態變動而改寫（見 `track_runqueue.py` 的 `_unresolved_blockers()`）。此為刻意設計：scheduler 只回答「此票現在能否接手」，混入已解除的 blocker 會誤導可執行性判斷。**做血緣或狀態對帳時（例如查證某票是否曾被阻擋、比對兩份資料是否一致）必須以 frontmatter 的 `blockedBy` 原值為準**——直接拿 `blockedBy=[]` 當作「此票從未被阻擋」會誤判血緣關係，或誤以為其中一份資料是壞資料。

> **Board 分組軸 — `board --group-by`**：`board` 新增 `--group-by {wave,topic}`。`wave` 為預設，輸出與本旗標引入前逐字相同；`topic` 依主題分組，一次呈現全部主題連同其票，供「先選主題再選票」的派發決策使用（`topics` 只給票數與 status 分佈、`topic` 只給單一主題的鏈，皆無法一次看到所有主題的內容）。
>
> ```bash
> ticket track board                          # 預設：Wave 分組加 ID 排序
> ticket track board --group-by topic         # 依主題分組，未歸屬票獨立成節置底
> ticket track board --wave W3 --group-by topic
> ```
>
> 主題節標題為 `<主題名> (N tasks, 最高優先級=PX)`，排序第一鍵為最高優先級、第二鍵為票數降冪。主題歸屬讀自 `lib/topic_assignments`（append-only 中央清單，非 frontmatter 欄位），未指派票落入 `未歸屬` 節。詳見 `references/track-command.md`「track board 子命令」章節。

> **Dashboard — `dashboard`**：PM 接手新 session 的聚合視圖。一次回傳 `[In Progress]` + `[Ready Top N]` + `[Stale Warning]` 三章節，Ready 章節含可直接 claim 的編號 `[1] [2] [3]` 與 priority 標籤，免拼 ID。
>
> ```bash
> ticket track dashboard                      # 預設：top 5 ready，stale 60min，text 格式
> ticket track dashboard --top 10             # 擴大 ready 列數
> ticket track dashboard --wave 10            # 限定 wave 範圍
> ticket track dashboard --no-stale           # 隱藏 stale 章節
> ticket track dashboard --stale-threshold 30 # 調整 stale 判定門檻（分鐘）
> ticket track dashboard --format=json        # JSON 輸出（自動化用）
> ```
>
> 設計目的：將 `/ticket` 裸命令流程從 7 個 tool call（list + runqueue + stale + ToolSearch + AUQ + claim + read）降至 3 個（dashboard + claim by number + 後續動作）。詳見 `references/track-command.md`「track dashboard 子命令」章節。

> **Parallel-check — `parallel-check`**：偵測目標 ticket 的 children（或同 parent 兄弟）pending 集合中，依 `where.files` 路徑前綴判斷哪些可平行派發、哪些互相衝突。輸出三章節（可平行派發 / 衝突任務 / 單獨派發）並對「可平行集合中 >= 3 個觸及 `.claude/` 的 ticket」發出 PC-137 警告，輔助 PM 套用 `.claude/pm-rules/askuserquestion-rules.md` 規則 7。
>
> ```bash
> ticket track parallel-check <id>   # 分析目標票的 children pending 集合
> ```
>
> 路徑比較使用 `pathlib.PurePosixPath`（禁 string startswith）。共同祖先深度 >= 3 段視為弱衝突（如 `.claude/skills/ticket/` 級）。exit code：0=分析成功 / 1=ticket 不存在或無 pending children / 2=ID 格式或 IO 錯誤。

> **List 預設行為 — `list --top` / `--all`**：`list` 預設 `--top 10` 並依 `priority(P0>P1>P2>P3) → created → id` 排序，避免 dump 全量 67+ 筆造成 PM 認知負擔。
>
> ```bash
> ticket track list                            # 預設 top 10 by priority
> ticket track list --top 20                   # 擴大列數
> ticket track list --all                      # 取全量（覆蓋 --top；共存時 --all 優先並 emit warning）
> ticket track list --format ids               # 純 ID 輸出（適合 pipe 到 xargs）
> ticket track list --status pending --top 5   # 篩選 pending 且只取 top 5
> ```
>
> `--format` 可選值：`table`（預設）/ `ids`（每行一個 ID，適合 pipe）/ `yaml`。詳見 `references/track-command.md`「track list 子命令」章節。

> **Stale ticket 明細 — `stale-list`**：列舉 pending 且建立日期超過閾值的 ticket，補 `list` 命令僅顯示彙總計數無法定位個別 ticket 的缺口。
>
> ```bash
> ticket track stale-list                           # 預設 --threshold warning（warning + critical）
> ticket track stale-list --threshold info          # 三級全收（info + warning + critical）
> ticket track stale-list --threshold all           # 同 info
> ticket track stale-list --threshold critical      # 僅 critical
> ticket track stale-list --wave 17 --format ids    # 僅輸出 ID（適合 pipe）
> ```
>
> 閾值複用 `lib/staleness.py`：info ≥ 7 天 / warning ≥ 14 天 / critical ≥ 30 天。輸出依 days 降序。table 格式另附 stale in-progress 章節（>= 24h，依 frontmatter `started_at` 單平面判定，附 `ticket track release <id>` 釋放提示）；`ids`/`yaml` 維持 pending-only 向後相容。詳見 `references/track-command.md`「track stale-list 子命令」章節。

> **TD 清單校準 — `td-status`**（PC-094）：掃描指定 ticket 的 body 與 git commit 訊息，將 TD 編號分類為「已處理 / 無需處理 / 仍待處理」三狀態。用於 Phase 3a/3b/4 結束時即時校準 TD 清單，防止 Phase 4 評估時誤判已完成項（PC-094 根因）。
>
> ```bash
> ticket track td-status <id>          # 校準指定 ticket 的 TD 清單
> ticket track td-status <id> --version 0.18.0  # 明確指定版本
> ```
>
> 輸出分三組：`[已處理]` / `[無需處理]` / `[仍待處理]`，pending TD 會附 PC-094 校準提示，建議於 body 標註或在 commit 訊息引用 TD 編號。呼叫時機：Phase 3a 策略文件完成後、Phase 3b commit 前、Phase 4 派發前。詳見 `.claude/pm-rules/tech-debt.md`「TD 清單即時校準（td-status）」章節。

> **受控釋放已鎖 Ticket — `reclaim`**（multi-PM 協調層 Phase 3，issue tarrragon/claude#77）：`claim` 永不過期，PM session 崩潰後持票永久鎖死；`reclaim` 提供強制 ghost 鑑識三查（未合併分支 / 髒檔交集 / 缺 Exit Status）後的受控釋放路徑，任一查命中或無法判定即拒絕。
>
> ```bash
> ticket track reclaim <id>              # dry-run：僅印鑑識報告
> ticket track reclaim <id> --confirm     # 三查全過才轉回 pending 並清 lease
> ```
>
> **設計取捨**：真正硬崩潰的 session 幾乎必觸發三查其一（來不及寫 Exit Status），`--confirm` 對這類票持續拒絕是刻意的保守設計，非功能故障。`sessions` 的 `reclaimable` 欄與 `runqueue` 的 `[RECLAIMABLE]` 標記僅為輕量 heartbeat 判準（列表級粗篩候選），與本命令的 ghost 鑑識三查（逐票精確判定）是兩層判定，粗篩顯示候選不保證 `--confirm` 會放行。詳見 `references/track-command.md`「track reclaim 子命令」章節。

> **注意**：`complete` 在父 ticket 含未完成 children（非 terminal：pending / in_progress / blocked）時會以 exit 1 阻擋。提供 `--force` 旁路強制完成，會在 stderr 列出未完成 children 作為警告，cascade 解鎖機制仍會執行。建議優先完成 children 後再 complete 父 ticket。
>
> **副作用 — ticket metadata 與程式碼變更恆分兩個 commit**：`complete` 的自動提交（見上方「常用範例」）於呼叫當下以隔離索引提交 ticket metadata（本票 md + 主 worklog），而非留待 PM 事後核對共用 index 手動 commit。**Why**：提交時機從「人工事後裸 commit」改為「CLI 呼叫當下自動提交」，是為了根除過期 index 快照被誤 commit 進 HEAD 的風險；本框架既有慣例本就是「代理人先 commit 程式碼、`complete` 再 commit metadata」兩步驟，此變更只是讓既有語意變得可觀察，非新增缺陷。**Consequence**：ticket metadata 與對應的程式碼變更**必然分屬兩個 commit**——單靠 `git log --grep <票號>` 只會命中 metadata commit（`chore(<id>): complete` / `chore(<id>): append-log ...`），不含實作變更；依「一票一 commit」假設做追溯的下游流程（含 sync 本框架的其他 consumer 專案）須知情此語意，否則會誤判追溯不完整或漏算變更範圍。**Action**：追溯某票完整變更時，搜尋範圍須同時涵蓋 metadata commit 與程式碼 commit（可用票號關鍵字掃兩者的 commit message，或查詢 ticket body 的 Test Results / Completion Info 章節記錄的程式碼 commit SHA）。
>
> **`--no-stage` 的覆蓋範圍**：`--no-stage` 會完整跳過本次 auto-commit（metadata 與 worklog 兩者皆跳過），ticket md 停留在 working tree 的未提交、未 staged 狀態，不產生任何 metadata commit。**Action**：想讓 ticket metadata 與程式碼變更合併成單一 commit 時，`--no-stage` 已足夠覆蓋——先完成程式碼變更，`complete <id> --no-stage` 後 ticket md 仍是未提交的工作區變更，可與程式碼檔案一併 `git add` 後裸 commit（無 pathspec / `--only` / `-o` / `-a`，見 `.claude/rules/core/bash-tool-usage-rules.md` 規則七）。**Consequence**：選擇 `--no-stage` 等於放棄自動提交機制帶來的「不留未提交 metadata」保護，working tree 中的 ticket md 變更在手動 commit 之前仍可能被 `git checkout --`／`git reset --hard`／`git stash` 覆蓋回舊版本（與 Spawn Requests 章節「繞道手改會失去 auto-commit 保護」同類風險），故僅建議在確定會立即手動 commit 時使用。
>
> **注意**：5W1H 欄位由 `set-who` ~ `set-how` 6 個命令更新。`title` 用 `set-title`、`blockedBy` 用 `set-blocked-by`、`relatedTo` 用 `set-related-to`（均支援 `--add`/`--remove`）、`priority` 用 `set-priority`。完整對照表見 `references/track-command.md`。
>
> **`parent_id` 修正（誤用 `--parent` 後的正確路徑）**：`add-child <parent-id> <child-id>` 只能新增父子關係，無法修正或清除。誤把 `--source-ticket` 打成 `--parent` 建錯關係時，用 `set-parent <child-id> <new-parent-id>` 改指到正確的父票，或 `set-parent <child-id> --clear` 清除（`new_parent_id` 與 `--clear` 互斥，不可同時提供或同時缺席）。兩種操作都會同步維護上游票的 `children`（移除舊值、寫入新值），不留下 `parent_id` 指向、`children` 不承認（或反之）的懸空引用；因 `children` 的異動永遠由此命令驅動，不需要獨立的「移除 children 成員」命令。
>
> **`title` 與 `what` 是兩個獨立欄位，`set-what` 刻意不同步 `title`**：`title` 是清單顯示用的短標籤（dashboard / runqueue 顯示的是它），`what` 是完整任務敘述（可含檔案清單、括號補充）。2026-08-18 量測 741 張票，124 張（17%）兩者刻意不同。票的範圍事後縮小時（如依上游評估結論移除 acceptance），**兩個欄位都要更新**——只改 `what` 會讓清單上的 `title` 繼續以舊範圍誤導接手者。
>
> **其餘 frontmatter 欄位若無對應命令，不要手動編輯**：`ticket-file-access-guard-hook` 會以 exit 2 阻擋直接編輯 frontmatter，繞道不可行。找不到對應命令代表該欄位缺少合法更新途徑（PC-BAL-047），應建 ticket 回報補上命令。
>
> **注意**：`append-log` 必須加上 `--section` 必填參數：`ticket track append-log <id> --section "Problem Analysis" "內容"`。有效區段值（SSOT：`ticket_system/constants.py` 的 `CANONICAL_BODY_SECTIONS`，共 10 章）：`Task Summary`、`Problem Analysis`、`重現實驗結果`、`Solution`、`Test Results`、`Context Bundle`、`NeedsContext`、`Exit Status`、`Spawn Requests`、`Completion Info`。`Execution Log` 是 body 的 H1 容器標題而非 H2 章節，明確不受 append-log 支援（該支援納入白名單後從未生效，見 DOC-007）。body-schema 全必填章節（含 `Completion Info`）皆可經 append-log 寫入，不需 Edit 繞道。`重現實驗結果` 為 ANA type 必填章節（PC-063 / ticket-body-schema.md）。`Context Bundle` 用於派發前寫入 PCB（PC-040）；`NeedsContext`/`Exit Status` 用於代理人結束狀態協議。
>
> **Status precondition**：`append-log` 要求 ticket status 為 `in_progress`（`completed` 亦放行，補 review 場景）。**例外**：派發前章節 `Problem Analysis` / `Context Bundle` 允許 `pending` 直寫——PM 依 PC-040 / PC-100 於 create 後立即寫入派發 context 屬合法 bookkeeping，不需 `--force`、不記 audit。其餘章節（`Solution` / `Test Results` / `Completion Info` 等執行產出）於 pending / blocked / closed 仍阻擋（status 失敗 exit 2）；`--force` 逃生閥行為與 hook-logs audit 紀錄不變。
>
> **副作用**：`append-log` 寫入 body 後會 **auto-commit 該 ticket md**（精確路徑，commit message `chore(<id>): append-log <section>`）。**Why**：body 即時進 commit 歷史可使 `git checkout -- <file>` / `git reset --hard` / `git stash` 三種還原全失效，根除「未 commit body 被 git 還原覆蓋回 placeholder」遺失問題。**Consequence**：每次 append-log 會新增一個 `chore` commit（碎 commit 為設計取捨，對 ticket md chore 類可接受）；body 無變更時 graceful skip 不產生空 commit。**Action**：非 git repo / index.lock 競爭 / commit 失敗時 append-log 仍 exit 0 + stderr 警告，body 保留 working tree 可手動 commit。不使用 `--no-verify`（維持 pre-commit hook 把關；ticket md 非 JS，lint-staged 無匹配）。
>
> **補標記 — `add-exempt-marker`**：自由撰寫章節（Solution / Test Results / NeedsContext 等）以 `append-log` 寫入後即無法修改——`append-log` 僅能追加、CLI 無編輯指令、該區段不在 `ticket-file-access-guard-hook` 白名單內故 Edit 工具被拒，三層疊加使 `PC-093-exempt` 這類行級標記完全無法事後補上。`add-exempt-marker` 補這條路，且**僅追加獨立標記行、不修改原文字**：
>
> ```bash
> ticket track add-exempt-marker <id> --section "Solution" --match "命中行的文字子字串" \
>   --category ticket-tracked --reason "W<wave>-<seq> hook 訊息改善"
> ```
>
> `--match` 是文字比對定位（非行號——行號隨後續編輯漂移）：命中恰好一行才寫入；0 命中或多重命中一律拒絕並回報候選行，要求提供更精確的 `--match` 收窄。marker 固定插入為命中行的**前一行**（獨立新行），與 `phase4-decision-enforcement-hook` 的豁免距離規則（同行或前 1 行生效）一致。`--category` 限定 `tdd-transition` / `baseline-gated` / `ticket-tracked` / `user-override` / `rule-quote` / `history`，`--reason` 格式驗證與該 hook 同規則（`baseline-gated` 需含數字、`ticket-tracked`/`history` 需含 `W{wave}-{seq}` ticket ID、`rule-quote` 需含 `.claude/rules/` 或 `.claude/pm-rules/` 路徑）。**防濫用**：本命令不能憑空產生新內容、只能指向既有行；marker 是否真正生效仍由該 hook 於 phase4 轉換 / complete 時重新掃描判定，本命令不繞過該把關層。Status precondition 與 auto-commit 副作用與 `append-log` 同（見上）。
>
> **派發即落票 — `dispatch`**：`ticket track dispatch <id> --as <agent> [--note "..."] [--kind normal|review] [--task-summary "..."]`。單一命令合併「暫態約束落票」與「骨架 prompt 輸出」：`--note` 非空時帶時間戳寫入票的「派發日誌」章節（非 Schema 章節，不進 Context Bundle），stdout 輸出骨架文字供 PM 複製派發。`--kind normal`（預設）輸出含讀取/認領/收尾協議的完整骨架；`--kind review` 輸出審查派發變體（欄位為審查標的/審查視角/裁決問題/回報格式），不含 `claim`/`complete`（審查非執行票，不觸發生命週期）。`--review-perspective` / `--decision-question` 僅 `--kind review` 使用。CLI 骨架常數（`SKELETON_TEMPLATE_NORMAL` / `SKELETON_TEMPLATE_REVIEW`，見 `ticket_system/commands/track_dispatch.py`）為單一權威，`agent-dispatch-template.md` 改為引用其輸出，不再手動同步逐字模板。
>
> **注意**：`check-acceptance` 只接受**單一** index（如 `1`）或 `--all`；不支援 `1 2 3` 多索引。一次勾選多項請改用 `set-acceptance --check 1 2 3`。先用 `ticket track query <id>` 查看驗收條件清單和編號。詳見 `references/track-command.md`「驗收條件操作詳解」（含決策樹 + 5 常見錯誤）。
>
> **注意**：`set-acceptance` 是 `check-acceptance` 的明確語意版：`--check <index>` / `--uncheck <index>`（可多個）、`--all-check` / `--all-uncheck`。禁止 subagent 直接 Edit frontmatter 的 acceptance 欄位。
>
> **建票後修訂（`--add`/`--edit`/`--remove`）**：`set-acceptance` 額外支援建票後修訂 acceptance 條目本身（非僅勾選狀態）——`--add <text>`（可多個）追加條目，預設未勾選；`--edit <index> <text>`（可重複指定多組）覆寫指定 index 的文字，原勾選狀態不變；`--remove <index>`（可多個）移除條目，其餘條目依原內容正確對位不漂移。三者與 `--check`/`--uncheck`/`--all-check`/`--all-uncheck` 互斥（每次呼叫僅能指定一種模式）。**已勾選（`[x]`）條目移除須另加 `--force`**（防止事後抹除驗收證據）；`completed` 票的任一子操作同樣受既有 status precondition 保護，需 `--force` 才能修訂。
>
> **多值寫法**：`--check` / `--uncheck` / `--add` / `--remove` 四個旗標的「可多個」涵蓋兩種形式，兩者等價也可混用——空白分隔（`--add "A" "B"`）與重複旗標（`--add "A" --add "B"`）。重複旗標形式曾因 argparse 未設 `action="append"` 而互相覆寫、只保留最後一個值且無警告，該缺陷已修復。`--edit` 語意為成對 `(index, text)`，一律用重複旗標形式。
>
> **注意**：`validate <id>` 驗證 Ticket frontmatter 4 關鍵欄位（status/completed_at/acceptance/who）合規性，違規時給出建議修復命令。
>
> **closed 票欄位修正（`set-closed-by`）**：`close` 對已 closed 票拒絕覆寫既有值；`set-closed-by <id> --value <ticket-id>` 補上 `closed_by` 填錯後的合法修正路徑，取代直接 Edit ticket md（該路徑被 `ticket-file-access-guard-hook` 阻擋）。僅適用 `status=closed` 的票；`--value` 須為合法且存在的 Ticket ID，格式錯誤或指向不存在的 Ticket 皆拒絕。修正動作輸出舊值與新值並走 auto-commit。
>
> **身份申報（`--as`）**：`complete` / `check-acceptance` / `set-acceptance` 三個寫入命令支援選用 `--as <agent-name>`，與 ticket `who.current` 精確對照。**Why**：防 generic agent 收 Ticket ID 即越權收尾（PC-V1-002 前提一，探針實證）。判定邏輯——`--as` 值 ≠ `who.current`（含空值）→ deny（exit 1，純前置檢查不寫入狀態）；`--as rosemary-project-manager` 一律放行（PM bookkeeping 豁免，如代收尾 / stale cleanup）；未提供 `--as` 時 `complete`（`finish` 別名同列）已轉強制 deny，`check-acceptance` / `set-acceptance` 仍僅 stderr 警告不阻擋（過渡期 warn-only，見 `identity_guard.py` `ENFORCED_COMMANDS`）。**Action**：subagent 收尾時帶自身身份，例 `ticket track complete <id> --as thyme-python-developer`；其餘 warn-only 命令轉強制的結束條件與偵測承擔者已明訂（7 日滾動 warn 率 < 5% 且樣本數 >= 30，由 PM 於 version-release 發布前檢查階段執行 `identity_guard_adoption.py` 判定），非待評估的無 trigger 狀態。
>
> **注意**：`deps <id>` 顯示衍生關係（`spawned_tickets` + `source_ticket`），與 `tree`/`chain` 純血緣語意（`parent_id`/`children`/`chain`）分離，對齊 Jira/Linear/GitHub 業界慣例。支援遞迴展開與循環引用防護（標記 `CYCLE DETECTED`）。用法：`ticket track deps <ticket-id>`。
>
> **注意**：`depth <id>` 沿 `parent_id` 鏈計算嵌套深度（**非** ID 字串數點，避免完整版本前綴如 `<version>-W<wave>-<seq>.<sub>` 本身即含 3 個點，被誤算為 depth 4 的 linux F1 fatal bug）。輸出 `depth` / `max_depth`（= `MAX_TICKET_DEPTH=3`）/ `can_descend`（depth < MAX_TICKET_DEPTH）。深度定義：根任務（`parent_id: null`）= depth 1，每往下一層 +1。用途：agent 自檢層級自覺（協議 v2 D3），無需上層 prompt 傳遞層級資訊。用法：`ticket track depth <ticket-id>`。
>
> **注意**：`create --parent <id>` 時，若新子任務深度 >= `MAX_TICKET_DEPTH`（3）會 emit warning（**不硬擋**，留旁路）。深度同樣沿 parent_id 鏈計算（協議 v2 D3）。此為嵌套派發深度上限的 CLI 強制層，使協議深度上限不只是文件建議。
>
> **六欄位語意 SSOT**：parent_id / children / source_ticket / spawned_tickets / blockedBy / relatedTo 的權威定義、阻擋語意、用戶情境對照表、決策樹見 `references/field-semantics.md`。其他規則 / 方法論 / error-pattern 涉及這些欄位時應引用該檔，不重複定義。

> **派發前提示**：當 ticket 是 group、含 children、含 spawned_tickets，或同輪會派 2+ agents 時，先在 Ticket Problem Analysis / Solution 寫 dispatch-plan。欄位使用 `.claude/references/agent-dispatch-template.md`：`ticket` / `agent` / `files` / `deps` / `context source` / `commit policy` / `run mode`。dispatch-plan 是 orchestration description，不是 batch dispatch CLI。

> **實驗器材登記 — `register-artifact` / `resolve-artifact` / `list-artifacts`**：跨 session 實驗器材（sentinel/探針/對照組樣本，其存在本身即為觀測手段的檔案）的票面登記 CLI 化，取代規範原僅要求「登記三項但格式自由發揮」的手工條款。完整規範見 `.claude/pm-rules/parallel-dispatch.md`「跨 session 實驗器材的自我標示與存活期治理（強制）」。
>
> ```bash
> ticket track register-artifact <id> --path <路徑> --purpose <用途> --expiry <存活期> [--type 明示|盲測]
> ticket track list-artifacts <id> [--json]
> ticket track resolve-artifact <id> EXP-N --status removed|kept [--successor <ticket-id>] [--reason <說明>]
> ```
>
> `register-artifact` 自動編號（`EXP-N`）寫入 Solution 章節固定子章節，同時輸出可直接複製貼上的首行 header 文字（供落地條件一的檔案端標示）。`list-artifacts` 提供結構化讀回（含 `--json`），供收尾檢查程式化消費，不需人工掃描章節。`resolve-artifact` 標記存活期治理的收尾處置：`--status kept` 強制要求 `--successor`（CLI 層面阻止「未指名接手者」漏處置，非僅文件提醒）。

> 決策樹：Read `references/workflow-execute.md` 和 `references/workflow-query.md`
> 詳細用法：Read `references/track-command.md`

### show - 顯示 Ticket 內容（含 Markdown 渲染）

終端閱讀專用。TTY 下自動以 `glow`/`mdcat`/`bat` 渲染；pipe 時自動降純文字，避免污染下游消費者。

```bash
ticket show <full-id>          # 完整 ID（含版本號）
ticket show <short-id>         # 短 ID（自動補當前版本）
ticket show <short-id> -r      # 純文字（同 track full）
ticket show <short-id> -R bat  # 指定渲染器
ticket show <short-id> -P      # 停用分頁
```

短 flag：`-r` raw / `-R` renderer / `-p` pager / `-P` no-pager。完整說明 `ticket show --help`。

與 `ticket track full <id>` 差異：`track full` 永遠純文字（腳本友善，向後相容）；`show` 預設渲染（閱讀友善）。

### handoff - 任務鏈管理與 Context 交接

支援自動判斷方向、指定交接到父/子/兄弟任務。五種交接情境。

> **設計原則**：handoff = 純指針，禁含任務描述 / acceptance / 5W1H（這些屬 ticket md 範圍）。完整原則見 `.claude/methodologies/handoff-design-principle-methodology.md`。

`--next <target-ticket-id>` 子旗標：以**絕對指向**語意建立 handoff，直接寫入 `target_ticket_id` 欄位，讓下 session 從「該做的 ticket」（target）讀取，而非從 source + direction 間接推導。

```bash
ticket handoff --next <target-ticket-id> --from-ticket-id <source-id>
```

`--next` 與 `--auto` 互斥；產生的 JSON `direction="context-refresh"`、`auto_generated=False`。讀取端（GC / SessionStart hint / Stop hook / resume）優先讀 `target_ticket_id`，缺則 fallback 至 direction 後綴解析（向後相容，舊 JSON 不破）。

新增 `--from-worklog` 子命令：解析 worklog 最新交接段，提取 ticket ID 並批次補建 `.claude/handoff/pending/<id>.json`，修復「worklog 寫了但未執行 CLI」雙軌不同步缺口。搭配 `stop-worklog-handoff-sync-check-hook`（Stop event 偵測）形成自動防護。

```bash
ticket handoff --from-worklog [--worklog-path PATH] [--dry-run]
```

> 決策樹：Read `references/workflow-handoff.md`
> 詳細用法：Read `references/handoff-command.md`

### resume - 恢復任務

從 handoff 檔案載入 context。SessionStart hook 提醒 → 用戶 `/ticket` 或 `/ticket resume <id>` 觸發。

> 決策樹：Read `references/workflow-handoff.md`
> 詳細用法：Read `references/resume-command.md`

### migrate - Ticket ID 遷移

支援單一和批量遷移，自動更新所有 ID 引用和 chain 資訊。

> 決策樹：Read `references/workflow-migrate.md`
> 詳細用法：Read `references/migrate-command.md`

### generate - Plan 轉換為 Tickets

從 Plan 檔案自動生成 Atomic Tickets（Plan-to-Ticket 轉換）。

> 詳細用法：Read `references/generate-command.md`

---

## 參考資料

| 資料                                     | 說明                                     |
| ---------------------------------------- | ---------------------------------------- |
| `references/architecture.md`             | 目錄結構、共用模組設計、自動化分析功能   |
| `references/workflow-create.md`          | 建立流程決策樹                           |
| `references/workflow-execute.md`         | 執行+更新+批量+完成流程決策樹            |
| `references/workflow-query.md`           | 查詢流程決策樹                           |
| `references/workflow-handoff.md`         | 交接+恢復流程決策樹                      |
| `references/workflow-migrate.md`         | ID 遷移流程決策樹                        |
| `references/completeness-check.md`       | 指令完整性驗證（39 個指令/選項覆蓋狀態） |
| `references/ticket-lifecycle-details.md` | Ticket 生命週期詳細規則                  |
| `references/track-command.md`            | track 子命令；含 `format_error()` 雙路徑（legacy str / `ErrorEnvelope` 結構化）、`ArgparseFormatErrorParser` 業務 vs 語法錯誤分流、版本標記 `__error_envelope_v1__` |

## Ticket Body Schema（type-aware）

不同 type 的 body 章節填寫要求：

| Section          | ANA            | IMP  | DOC                |
| ---------------- | -------------- | ---- | ------------------ |
| Problem Analysis | 必填           | 選填 | 選填               |
| 重現實驗結果     | 必填（PC-063） | 免填 | 免填               |
| Solution         | 必填           | 選填 | 免填               |
| Test Results     | 選填           | 必填 | 免填               |
| Completion Info  | 必填           | 必填 | 必填（附變更摘要） |

`ticket create --type ANA/IMP/DOC` 會在 body 各章節插入 `<!-- Schema[TYPE/Section]: 狀態 -->` 標註，指引填寫者。完整規則見 `.claude/pm-rules/ticket-body-schema.md`。

## 相關文件

- `.claude/pm-rules/ticket-body-schema.md` - Ticket body type-aware schema
- `.claude/methodologies/atomic-ticket-methodology.md` - Atomic Ticket 方法論
- `.claude/methodologies/ticket-lifecycle-management-methodology.md` - Ticket 生命週期管理
- `.claude/pm-rules/ticket-lifecycle.md` - Ticket 生命週期流程

---

## 修改 source 後無需重新安裝（shim 化）

> **重要**：本 skill 已改用 cwd-resolving shim（ARCH-APP-002 / framework issue #12），不再走 `uv tool install`。shim 每次執行都 `uv run --directory .claude/skills/ticket` 當前專案源碼，修改 source 後改動即時生效，無 stale installed 問題（取代舊 `uv-tool-staleness-check-hook` / `ticket-reinstall-hook` 機制）。

**檢查 / 安裝指令**：

```bash
# 安裝 / 更新 shim（一次安裝 ticket / doc / worktree）
python3 .claude/scripts/install-skill-clis.py

# 檢查是否已 shim 化（exit 0/1）
python3 .claude/scripts/install-skill-clis.py --check
```

---

## 覆核測試指令（skill 自身測試套件）

> **唯一標準指令**：裸 `pytest`，不帶任何路徑參數。`pyproject.toml` 的 `[tool.pytest.ini_options]` 已設定 `testpaths = ["tests", "ticket_system/tests"]`，一次 pytest session 涵蓋 skill 根層 `tests/` 與 `ticket_system/tests/` 兩個目錄，無需（也不應）分開執行。

```bash
(cd .claude/skills/ticket && uv run --with pytest --with pyyaml --with filelock python -m pytest -q)
```

**禁止**：以顯式路徑（如 `pytest tests/`、`pytest ticket_system/tests`）作為覆核依據。顯式路徑參數會**覆蓋** `testpaths` 設定，僅收集單一目錄下的測試，另一目錄的測試會被靜默漏跑而不觸發任何錯誤或警告——覆核者若只跑其中一個目錄卻在 Test Results 宣稱「測試通過率 100%」，該宣稱在結構上未涵蓋另一半測試。

`ticket_system/tests/` 與 `tests/` 兩目錄並存的分裂現況、路徑推導細節見 `references/track-command.md`「Python 測試路徑推導」小節。

---

版本紀錄在同目錄的 `CHANGELOG.md`。
