---
name: ticket
description: 'Use this skill whenever the user wants to create, track, query, or manage tickets. Triggers include: creating new tickets, claiming or releasing tickets, checking ticket status or progress, completing tickets, handing off work between agents, resuming interrupted tasks, migrating tickets between versions, converting plans to tickets, or any mention of /ticket, task tracking, or ticket lifecycle operations.'
argument-hint: '<subcommand> [args]'
allowed-tools: Bash(ticket *), Read, Write, Edit, Grep, Glob
---

# Ticket System v1.0

統一 Ticket 系統 - 整合 create/track/handoff/resume/migrate/generate 六大功能。

---

## 執行方式

> **禁止直接執行 Python 檔案！** `ticket_system` 是 Python 套件，必須透過 `pyproject.toml` 定義的入口點執行。

### 全局安裝（推薦）

```bash
# 首次安裝
(cd .claude/skills/ticket && uv tool install .)

# 之後在任何目錄執行
ticket track summary
ticket track claim 1.0.0-W4-001
```

**修改原始碼後必須重新安裝**（IMP-023）：

```bash
# 必須用 --reinstall（--force 不會更新套件程式碼）
uv tool install .claude/skills/ticket --reinstall
```

### 本地執行

```bash
(cd .claude/skills/ticket && uv run ticket track summary)
```

### 常用範例

```bash
ticket track summary                                    # 摘要
ticket track query 1.0.0-W4-001                       # 查詢
ticket track claim 1.0.0-W4-001                       # 認領
ticket track complete 1.0.0-W4-001                    # 完成（auto-stage：自動 git add ticket md + worklog md + cascade children，stdout 提示 commit 指令）
ticket track complete 1.0.0-W4-001 --no-stage         # 完成但跳過 auto-stage（保留用戶手動掌控 stage 範圍，W11-035）
ticket track complete 1.0.0-W4-001 --force            # 強制完成（旁路未完成 children 阻擋，W11-003.2）
ticket create --version 0.31.0 --wave 4 --action "實作" --target "XXX"  # 建立
```

---

## 無子命令時的預設行為（dashboard-first，v2.7.0 起）

當用戶輸入 `/ticket`（無子命令或參數）時，依序執行以下流程：

1. **取得接手聚合視圖** — 執行 `ticket track dashboard --top 5`

   dashboard 一次回傳 `[In Progress]` + `[Ready Top N]` + `[Stale Warning]` 三章節，Ready 章節含可直接 claim 的編號 `[1] [2] [N]` 與 priority 標籤。設計目的：將 PM 接手流程從 W10-113 baseline 7 tool call 降至 2-3 tool call（W3-013 ANA 結論方向 a）。

   - **dashboard 有 in_progress 或 ready 任務** → 使用 AskUserQuestion 依 dashboard 順序列出選項：
     - in_progress 任務優先列出（label: `[ip] {ticket_id} - {title}`，description: `進行中（resume 接手）`）
     - Ready 任務依 dashboard `[1] [2] [N]` 編號順序列出（label: `[{N}] {ticket_id} - {title}`, description: `[{priority}]`）
     - 額外選項：「建立新 Ticket」（description: `執行 /ticket create`）
     - 用戶選擇：
       - in_progress 任務 → `ticket resume <selected_id>`
       - Ready 任務 → `ticket track claim <selected_id>`
       - 建立新 Ticket → 引導進入 `/ticket create` 流程
     - 流程結束
   - **dashboard 無 in_progress 也無 ready** → 進入步驟 2 fallback

2. **Fallback：完整 pending/in_progress 清單**（僅當步驟 1 dashboard 無結果時觸發） — 執行 `ticket track list --status pending,in_progress`

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

## 子命令總覽

| 子命令              | 用途                       | 範例                                                                       |
| ------------------- | -------------------------- | -------------------------------------------------------------------------- |
| `create`            | 建立新 Ticket              | `/ticket create --version 0.31.0 --wave 1 --action "實作" --target "XXX"`  |
| `batch-create`      | 批次建立 Tickets           | `/ticket batch-create --template impl-parsley --targets "a,b,c" --wave 28` |
| `track`             | 追蹤 Ticket 狀態           | `/ticket track summary`                                                    |
| `track dashboard`   | PM 接手聚合視圖（W10-114） | `ticket track dashboard --top 5`                                           |
| `track list`        | 預設 top 10 priority 排序（W10-115） | `ticket track list --status pending --top 20`                  |
| `track td-status`   | TD 清單校準（PC-094）      | `ticket track td-status 0.18.0-W10-017`                                    |
| `track parallel-check` | 偵測子任務/兄弟 ticket 檔案衝突（W17-203.1，對齊 askuserquestion-rules 規則 7） | `ticket track parallel-check 0.18.0-W17-203` |
| `track dispatch-validate` | Context Bundle 自動填料合理性檢查（W17-003，C 方案安全網；exit 0=pass / 1=軟警告 / 2=硬失敗或 IO 錯誤；**與 dispatch-check 的 exit code 語意不共享**，需以命令名稱判別） | `ticket track dispatch-validate 0.18.0-W17-003` |
| `track dispatch-readiness` | 派發前認知負擔閾值檢查（W17-053；三項閾值：功能職責數 / 修改檔案數 / Context Bundle tokens；exit 0=pass / 1=軟警告 / 2=強制拆分或 IO 錯誤；**與 dispatch-check / dispatch-validate 的 exit code 語意不共享**；閾值 1 以 acceptance 條目近似，含驗證類條目時可能高估，PM 於 WARN/FAIL 應手動覆核——詳見 references/track-command.md） | `ticket track dispatch-readiness 0.18.0-W17-053` |
| `show`              | 顯示 Ticket（含渲染）      | `ticket show W17-015` / `ticket show W17-015 -r`                           |
| `handoff`           | 任務交接                   | `/ticket handoff 1.0.0-W1-002 --to-sibling 1.0.0-W2-003`                   |
| `resume`            | 恢復任務                   | `/ticket resume <id>`                                                      |
| `migrate`           | Ticket ID 遷移             | `/ticket migrate 1.0.0-W4-001 1.0.0-W5-001`                                |
| `generate`          | Plan 轉換為 Tickets        | `/ticket generate plan.md --version 0.31.0 --wave 5`                       |

---

## 子命令詳細說明

各子命令的完整用法和參數說明，請參閱對應的 reference 檔案：

### create - 建立新 Ticket

建立 Atomic Ticket，支援 5W1H 引導式建立、子 Ticket 建立、版本目錄初始化（init）。

> 決策樹：Read `references/workflow-create.md`
> 詳細用法：Read `references/create-command.md`
> 血緣 vs 衍生：`--parent` vs `--source-ticket` 對比表見 `references/create-command.md`「--parent vs --source-ticket 對比表」章節（PC-073）

**常用範例**：

```bash
# 建立根任務（必須提供 decision-tree 三參數）
ticket create --version 0.2.0 --wave 2 --action "實作" --target "HTTP Handler" --type IMP \
  --decision-tree-entry "第五層:TDD" \
  --decision-tree-decision "Phase 3b 完成後建立重構 Ticket" \
  --decision-tree-rationale "quality-baseline-rule-5"

# 建立子任務（--parent 自動產生子序號，可省略 decision-tree 參數）
ticket create --parent "1.0.0-W2-001" --action "實作" --target "事件融合層"

# DOC 類型（可省略 decision-tree 參數）
ticket create --version 0.2.0 --wave 2 --action "撰寫" --target "工作日誌" --type DOC

# 多值參數格式
#   --acceptance：多次指定或用分隔符（vertical bar）分隔
ticket create ... --acceptance "條件A" --acceptance "條件B"
ticket create ... --acceptance "條件A|條件B|條件C"
#   注意（W3-089）：分隔符是 --acceptance 的多條拆分字元。
#   若 acceptance 內文本身需含該字元（如描述 shell pipe「-q | tail」），
#   用反斜線跳脫保留字面，避免被靜默拆條：
ticket create ... --acceptance "重現實證 -q \| tail 導致 0 行"
#   未跳脫時，單一 --acceptance 值被拆成多條會印出 [WARNING] 供確認。

#   --where：逗號分隔
ticket create ... --where "file1.py,file2.py"

#   --blocked-by / --related-to：逗號分隔
ticket create ... --blocked-by "1.0.0-W2-001.1,1.0.0-W2-001.2"
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
ticket batch-create --template impl-parsley --targets "a,b" --parent 1.0.0-W28-001
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

包含 READ 操作（summary/query/version/tree/chain/deps/full/log/list/board/agent/5W1H/validate/**runqueue**/**dashboard**/stale-list/td-status）和 UPDATE 操作（claim/complete/release/set-who/set-what/set-when/set-where/set-why/set-how/phase/check-acceptance/set-acceptance/append-log/add-child/batch-claim/batch-complete/audit/accept-creation）。`list` 支援 `--wave`、`--status`、`--format`、`--top`、`--all` 篩選參數（W10-115 預設 `--top 10`，priority 排序）。

> **Scheduler — `runqueue`**（W17-011.1）：回答「下一個該做哪個 ticket」。Linux schedule()/runqueue/top/ps 類比。合併原 next+schedule+resume-hint 為單一命令。
>
> ```bash
> ticket track runqueue --wave 17                    # 可執行清單（blockedBy=[] pending，priority 排序）
> ticket track runqueue --wave 17 --format=dag       # 完整 DAG + 關鍵路徑高亮
> ticket track runqueue --context=resume --top 3     # 與 handoff/pending 交集（接手建議）
> ```
>
> 新 session 啟動時 `session-start-scheduler-hint-hook` 自動呼叫 `runqueue --context=resume`，結果以 hook additionalContext 顯示。PM 迷失方向時優先執行，免靠記憶判斷先後順序。詳見 `references/track-command.md`「track runqueue 子命令」章節。

> **Dashboard — `dashboard`**（W10-114 / W10-113 M1+M4'）：PM 接手新 session 的聚合視圖。一次回傳 `[In Progress]` + `[Ready Top N]` + `[Stale Warning]` 三章節，Ready 章節含可直接 claim 的編號 `[1] [2] [3]` 與 priority 標籤，免拼 ID。
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

> **Parallel-check — `parallel-check`**（W17-203.1）：偵測目標 ticket 的 children（或同 parent 兄弟）pending 集合中，依 `where.files` 路徑前綴判斷哪些可平行派發、哪些互相衝突。輸出三章節（可平行派發 / 衝突任務 / 單獨派發）並對「可平行集合中 >= 3 個觸及 `.claude/` 的 ticket」發出 PC-137 警告，輔助 PM 套用 `.claude/pm-rules/askuserquestion-rules.md` 規則 7。
>
> ```bash
> ticket track parallel-check 0.18.0-W17-203   # 分析 W17-203 的 children pending 集合
> ```
>
> 路徑比較使用 `pathlib.PurePosixPath`（禁 string startswith）。共同祖先深度 >= 3 段視為弱衝突（如 `.claude/skills/ticket/` 級）。exit code：0=分析成功 / 1=ticket 不存在或無 pending children / 2=ID 格式或 IO 錯誤。

> **List 預設行為 — `list --top` / `--all`**（W10-115 / W10-113 M3）：`list` 預設 `--top 10` 並依 `priority(P0>P1>P2>P3) → created → id` 排序，避免 dump 全量 67+ 筆造成 PM 認知負擔。
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

> **Stale ticket 明細 — `stale-list`**（W17-200）：列舉 pending 且建立日期超過閾值的 ticket，補 `list` 命令僅顯示彙總計數無法定位個別 ticket 的缺口。
>
> ```bash
> ticket track stale-list                           # 預設 --threshold warning（warning + critical）
> ticket track stale-list --threshold info          # 三級全收（info + warning + critical）
> ticket track stale-list --threshold all           # 同 info
> ticket track stale-list --threshold critical      # 僅 critical
> ticket track stale-list --wave 17 --format ids    # 僅輸出 ID（適合 pipe）
> ```
>
> 閾值複用 `lib/staleness.py`：info ≥ 7 天 / warning ≥ 14 天 / critical ≥ 30 天。輸出依 days 降序。詳見 `references/track-command.md`「track stale-list 子命令」章節。

> **TD 清單校準 — `td-status`**（W10-083 / PC-094）：掃描指定 ticket 的 body 與 git commit 訊息，將 TD 編號分類為「已處理 / 無需處理 / 仍待處理」三狀態。用於 Phase 3a/3b/4 結束時即時校準 TD 清單，防止 Phase 4 評估時誤判已完成項（PC-094 根因）。
>
> ```bash
> ticket track td-status 0.18.0-W10-017          # 校準指定 ticket 的 TD 清單
> ticket track td-status 0.18.0-W10-017 --version 0.18.0  # 明確指定版本
> ```
>
> 輸出分三組：`[已處理]` / `[無需處理]` / `[仍待處理]`，pending TD 會附 PC-094 校準提示，建議於 body 標註或在 commit 訊息引用 TD 編號。呼叫時機：Phase 3a 策略文件完成後、Phase 3b commit 前、Phase 4 派發前。詳見 `.claude/pm-rules/tech-debt.md`「TD 清單即時校準（td-status）」章節。

> **注意**：`complete` 在父 ticket 含未完成 children（非 terminal：pending / in_progress / blocked）時會以 exit 1 阻擋（W11-003.2）。提供 `--force` 旁路強制完成，會在 stderr 列出未完成 children 作為警告，cascade 解鎖機制仍會執行。建議優先完成 children 後再 complete 父 ticket。
>
> **注意**：5W1H 欄位由 `set-who` ~ `set-how` 6 個命令更新。`blockedBy` 用 `set-blocked-by`、`relatedTo` 用 `set-related-to`（均支援 `--add`/`--remove`）。`priority` 等欄位無 CLI 命令，需手動編輯 frontmatter。完整對照表見 `references/track-command.md`。
>
> **注意**：`append-log` 必須加上 `--section` 必填參數：`ticket track append-log <id> --section "Problem Analysis" "內容"`。有效區段值：`Problem Analysis`、`Context Bundle`、`重現實驗結果`、`Solution`、`Test Results`、`Execution Log`、`NeedsContext`、`Exit Status`。`重現實驗結果` 為 ANA type 必填章節（PC-063 / ticket-body-schema.md）。`Context Bundle` 用於派發前寫入 PCB（PC-040）；`NeedsContext`/`Exit Status` 用於代理人結束狀態協議（W17-010）。
>
> **注意**：`check-acceptance` 只接受**單一** index（如 `1`）或 `--all`；不支援 `1 2 3` 多索引。一次勾選多項請改用 `set-acceptance --check 1 2 3`。先用 `ticket track query <id>` 查看驗收條件清單和編號。詳見 `references/track-command.md`「驗收條件操作詳解」（含決策樹 + 5 常見錯誤）。
>
> **注意**：`set-acceptance` 是 `check-acceptance` 的明確語意版（：`--check <index>` / `--uncheck <index>`（可多個）、`--all-check` / `--all-uncheck`。禁止 subagent 直接 Edit frontmatter 的 acceptance 欄位。
>
> **注意**：`validate <id>` 驗證 Ticket frontmatter 4 關鍵欄位（status/completed_at/acceptance/who）合規性，違規時給出建議修復命令。
>
> **注意**：`deps <id>` 顯示衍生關係（`spawned_tickets` + `source_ticket`），與 `tree`/`chain` 純血緣語意（`parent_id`/`children`/`chain`）分離，對齊 Jira/Linear/GitHub 業界慣例（W15-004）。支援遞迴展開與循環引用防護（標記 `CYCLE DETECTED`）。用法：`ticket track deps <ticket-id>`。
>
> **六欄位語意 SSOT**：parent_id / children / source_ticket / spawned_tickets / blockedBy / relatedTo 的權威定義、阻擋語意、用戶情境對照表、決策樹見 `references/field-semantics.md`。其他規則 / 方法論 / error-pattern 涉及這些欄位時應引用該檔，不重複定義。

> **派發前提示**：當 ticket 是 group、含 children、含 spawned_tickets，或同輪會派 2+ agents 時，先在 Ticket Problem Analysis / Solution 寫 dispatch-plan。欄位使用 `.claude/references/agent-dispatch-template.md`：`ticket` / `agent` / `files` / `deps` / `context source` / `commit policy` / `run mode`。dispatch-plan 是 orchestration description，不是 batch dispatch CLI。

> 決策樹：Read `references/workflow-execute.md` 和 `references/workflow-query.md`
> 詳細用法：Read `references/track-command.md`

### show - 顯示 Ticket 內容（含 Markdown 渲染）

終端閱讀專用。TTY 下自動以 `glow`/`mdcat`/`bat` 渲染；pipe 時自動降純文字，避免污染下游消費者。

```bash
ticket show 0.18.0-W17-015     # 完整 ID
ticket show W17-015            # 短 ID（自動補當前版本）
ticket show W17-015 -r         # 純文字（同 track full）
ticket show W17-015 -R bat     # 指定渲染器
ticket show W17-015 -P         # 停用分頁
```

短 flag：`-r` raw / `-R` renderer / `-p` pager / `-P` no-pager。完整說明 `ticket show --help`。

與 `ticket track full <id>` 差異：`track full` 永遠純文字（腳本友善，向後相容）；`show` 預設渲染（閱讀友善）。

### handoff - 任務鏈管理與 Context 交接

支援自動判斷方向、指定交接到父/子/兄弟任務。五種交接情境。

> **設計原則**：handoff = 純指針，禁含任務描述 / acceptance / 5W1H（這些屬 ticket md 範圍）。完整原則見 `.claude/methodologies/handoff-design-principle-methodology.md`。

`--next <target-ticket-id>` 子旗標（W17-164 / L2-A）：以**絕對指向**語意建立 handoff，直接寫入 `target_ticket_id` 欄位，讓下 session 從「該做的 ticket」（target）讀取，而非從 source + direction 間接推導。

```bash
ticket handoff --next <target-ticket-id> --from-ticket-id <source-id>
```

`--next` 與 `--auto` 互斥；產生的 JSON `direction="context-refresh"`、`auto_generated=False`。讀取端（GC / SessionStart hint / Stop hook / resume）優先讀 `target_ticket_id`，缺則 fallback 至 direction 後綴解析（向後相容，舊 JSON 不破）。

新增 `--from-worklog` 子命令（W17-083.2）：解析 worklog 最新交接段，提取 ticket ID 並批次補建 `.claude/handoff/pending/<id>.json`，修復「worklog 寫了但未執行 CLI」雙軌不同步缺口。搭配 `stop-worklog-handoff-sync-check-hook`（Stop event 偵測）形成自動防護。

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
| `references/track-command.md`            | track 子命令；含 `format_error()` 雙路徑（legacy str / `ErrorEnvelope` 結構化）、`ArgparseFormatErrorParser` 業務 vs 語法錯誤分流、版本標記 `__error_envelope_v1__`（W17-008.5 group） |

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

**Version**: 2.7.0
**Last Updated**: 2026-05-27
**Status**: Completed

**Change Log**:

- v2.7.0 (2026-05-27): `/ticket` 裸指令預設行為改為 dashboard-first 流程（W3-013.1 落地，源於 W3-013 ANA 結論方向 a）
  - 步驟 1 從 `ticket track runqueue --context=resume --top 3` 改為 `ticket track dashboard --top 5`
  - AskUserQuestion 選項對齊 dashboard `[1] [2] [N]` 編號 + priority 標籤（用戶可直接說編號選擇）
  - in_progress 任務優先列出（label 加 `[ip]` 前綴），用戶選擇後走 `resume` 而非 `claim`
  - dashboard 無結果時 fallback 到原 `list --status pending,in_progress` 路徑（向後相容）
  - `ticket resume --list` 與 `ticket track runqueue --context=resume` 子命令保留作除錯/腳本用途
  - 量測收益：W10-113 baseline 7 tool call → dashboard-first 2-3 tool call（改善 57-71%）
- v2.6.0 (2026-05-13): 補 W10-114 dashboard 命令與 W10-115 list 預設行為文件（W10-116 落地）
  - 子命令總覽表新增 `track dashboard` 與 `track list` 兩列
  - track 章節 READ 操作清單補 `dashboard` / `stale-list` / `td-status`，並註明 list `--top`/`--all` 預設行為
  - 新增 `Dashboard — dashboard` callout 說明聚合視圖、編號 claim、降低 7→3 tool call
  - 新增 `List 預設行為 — list --top / --all` callout 說明預設 top 10 排序與 `--format` 三選值
- v2.5.2 (2026-05-12): 子命令總覽表新增 `track td-status`；track 章節新增 td-status callout（W10-083 / PC-094 落地，0.18.0-W10-106）
- v2.5.1 (2026-05-10): handoff 章節新增「設計原則」引用指向 `handoff-design-principle-methodology.md`（W17-175 落地）
- v2.5.0 (2026-05-08): handoff 章節同步 W17-164 落地的 `--next` CLI 與 `target_ticket_id` 欄位
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

---

## 修改 source 後必須重新安裝

> **重要**：本 skill 透過 `uv tool install` 安裝為獨立 CLI，source（本目錄）與 installed（`~/.local/share/uv/tools/<package>/`）是兩份獨立 Python package。修改 source 後若未 reinstall，CLI 仍使用 stale installed 版本，新增的函式會 AttributeError 或被 hasattr 包裝靜默吞掉（W11-037 根因）。

**修復指令**：

```bash
cd .claude/skills/<本 skill 目錄> && uv tool install . --force --reinstall
```

**自動偵測**：每次 SessionStart 由 `uv-tool-staleness-check-hook` 比對 source vs installed SHA256，偵測 stale 時提示修復指令。對應 ticket-skill 本身另有 `ticket-reinstall-hook` 自動 reinstall。
