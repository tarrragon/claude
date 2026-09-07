---
name: ticket
description: 'Use whenever the user wants to create, track, query, or manage tickets: claim, release, complete, handoff, resume, migrate IDs, plan-to-ticket, split, evaluate granularity. Triggers: /ticket, task tracking, ticket lifecycle.'
argument-hint: '<subcommand> [args]'
allowed-tools: Bash(ticket *), Read, Write, Edit, Grep, Glob
metadata:
  version: 2.21.0
---

# Ticket System

統一 Ticket 系統，整合 create/track/handoff/resume/migrate/generate 等頂層子命令。

---

## 系統模型（設計自我描述）

本系統的參照模型是 **issue tracker + CI runner**（batch job queue 為輔助類比），不是 OS process：

| 對應 | 參照 | 含義 |
|------|------|------|
| ticket = issue | issue tracker（Jira/Linear/GitHub 類） | 狀態機轉移經 CLI 驗證、stale 需 triage 儀式、ID 為全域引用錨點 |
| agent = CI runner | ephemeral runner | 身份在派發/認領時綁定（`claim --as`）、工作區以隔離 checkout 為優先、逾時由 watchdog 回收 |
| wave = batch cohort | job queue 批次 | blockedBy DAG 之外的隱式排序層 |

三個與 OS process 直覺相反的預設：**身份晚綁定**、**共享工作區**、**type 與 instance 一對多**；另有 scheduler 層類比與 named agent running/idle/stopped 三態生命週期。完整定義與論證：Read `references/architecture.md`「系統模型（設計自我描述，完整版）」

---

## Ticket 狀態與程式碼提交的 root 分離（worktree 場景）

linked worktree 內執行 `ticket track` 系列命令時，ticket 狀態（md 讀寫）與程式碼提交走**兩條不同的 root 解析路徑**：狀態一律反向回推寫入主倉庫，提交維持 worktree 感知進該分支——此為刻意設計，非 cwd 解析漏洞，誤判並「修復」會重新引入票面分裂風險。

> 完整設計理由（Why/Consequence/Action）與查證方式：Read `references/track-command.md`「Ticket 狀態與程式碼提交的 root 分離」

---

## 執行方式

> **禁止直接執行 Python 檔案。** `ticket_system` 是 Python 套件，必須透過 `pyproject.toml` 定義的入口點執行。

全局安裝（推薦，shim 化）：`python3 .claude/scripts/install-skill-clis.py`，之後任何目錄可直接執行 `ticket track summary` 等命令。完整安裝機制（shim 原理、`--check`、本地不安裝執行）見 `references/architecture.md`「安裝與執行方式」章節。

### subagent 派發時 claim 推薦用法

被派發的 subagent 認領自身 ticket 時，推薦使用 `ticket track claim <id> --as <self-agent-name>` 申報自身身份（不加 `--verify`）。Why/Consequence/Action 與命令對照表見 `references/track-command.md`「claim 推薦用法（subagent 派發時的身份申報）」章節。

**覆核測試指令**（skill 自身測試套件）：唯一標準指令為裸 `pytest`（不帶路徑參數）。完整規則見 `references/architecture.md`「覆核測試指令（skill 自身測試套件）」章節。

---

## 無子命令時的預設行為（dashboard-first，v2.7.0 起）

當用戶輸入 `/ticket`（無子命令或參數）時，依序執行以下流程：

1. **取得接手聚合視圖** — 執行 `ticket track dashboard --top 5`

   dashboard 一次回傳 `[In Progress]` + `[Handoff Target]` + `[Ready Top N]` + `[Stale Warning]` 四區塊，Ready 區塊含可直接 claim 的編號 `[1] [2] [N]` 與 priority 標籤。設計目的與 tool call 量測：見 `references/track-command.md`〈track dashboard 子命令（W10-114 / W10-113 M1+M4'）〉### 設計目的。

   [In Progress] 條目帶 lease 狀態標記（判準同 registry heartbeat）：`[LIVE]` = FRESH session 正在處理；`[RECLAIMABLE]` = 已知無 FRESH session 佐證持有（可能已 STALE，也可能 registry 根本未追蹤此票——含 graceful SessionEnd 釋放後 entry 已刪除的情形，兩者現統一標記，皆須走 reclaim 鑑識判定）；無標記 = registry 本身不可用（模組載入失敗 / 非 git 環境 / 讀取降級），無法判定。**`[LIVE]` 票禁止列入接手選項**——活躍 session 正在處理，接手即與其重複處理同一張票（framework issue tarrragon/claude#78）。

   - **dashboard 有 in_progress 或 ready 任務** → 使用 AskUserQuestion 依 dashboard 順序列出選項：
     - `[LIVE]` 的 in_progress 票**不列入選項**，僅在 AUQ 前的回覆文字中資訊性提及（「N 張由其他 session 處理中」）
     - 非 `[LIVE]` 的 in_progress 任務優先列出（label: `[ip] {ticket_id} - {title}`；`[RECLAIMABLE]` 者 description: `無 FRESH session 佐證持有（走 reclaim 鑑識，非直接 resume）`；無標記者 description: `registry 無法判定（resume 接手）`——正常環境下極少出現，僅 registry 本身不可用時觸發）
     - Ready 任務依 dashboard `[1] [2] [N]` 編號順序列出（label: `[{N}] {ticket_id} - {title}`, description: `[{priority}]`）
     - 額外選項：「建立新 Ticket」（description: `執行 /ticket create`）
     - 用戶選擇：
       - 無標記 in_progress 任務 → `ticket resume <selected_id>`
       - `[RECLAIMABLE]` 任務 → `ticket track reclaim <selected_id>`（dry-run 鑑識通過再 `--confirm`，詳見 `references/track-command.md`〈track reclaim 子命令（multi-PM 協調層 Phase 3，issue tarrragon/claude#77）〉）
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

3. **無任何待辦** → 顯示子命令路由表（下方表格）

> **完整待恢復清單檢視/除錯**：可改用 `ticket resume --list`（子命令保留，獨立於 dashboard-first 流程）。
> **scheduler 接手建議單獨查詢**：可改用 `ticket track runqueue --context=resume --top 3`（保留作除錯/腳本用途，但 PM 接手流程不再呼叫）。

---

## 統一命令格式

```bash
/ticket <subcommand> [options]
```

> **命令層級慣例**：`create` / `batch-create` / `show` / `handoff` / `resume` / `migrate` / `generate` / `version-shift` 是**頂層命令**（`ticket create ...`）；`claim` / `complete` / `append-log` / `query` / `list` / `set-acceptance` 等狀態操作在 **`track` 之下**（`ticket track <op> ...`）。常見誤打：`ticket track create`（錯，create 非 track 子命令）、`ticket claim`（錯，claim 在 track 下）。本標註僅說明既有慣例，零 CLI 行為變更（Never break userspace）。

## 子命令路由表

> 下表以子命令為鍵，合併原三節（子命令總覽／子命令詳細說明／參考資料，WRAP 裁決見 issue tarrragon/claude#94）。列序：create→track（含子族）→handoff→resume→migrate→generate→batch-create→show→version-shift→（跨子命令）；跨子命令通用檔案（architecture／field-semantics／ticket-lifecycle-details）殿於相關群組或表尾。涵蓋章節欄與各 `references/*.md` 的 `##` 標題逐字雙向齊全（判準見 `skill-design-guide`〈按需讀取〉前言），僅計 fenced block 外的 `##`（`awk '/^```/{f=!f;next} !f && /^## /'`）；`batch-create`／`show`／`version-shift` 無獨立 reference，見表後小節。

| 子命令 | 用途 | 範例 | 檔案 | 涵蓋章節 |
| --- | --- | --- | --- | --- |
| `create` | 建立 Atomic Ticket，支援 5W1H 引導式建立、子 Ticket 建立；版本目錄不存在時自動建立（無獨立 init 子命令） | `/ticket create --version 0.31.0 --wave 1 --action "實作" --target "XXX"` | `references/workflow-create.md` | 〈主流程判斷〉〈建立流程決策樹〉 |
| `create` |  |  | `references/create-command.md` | 〈基本用法〉〈版本歸屬引導〉〈主題歸屬（自動推導）〉〈多值參數格式〉〈類型說明〉〈決策樹路由參數〉〈重複偵測（兩層防護）〉〈--source-ticket 參數（衍生關係）〉 |
| `track` | 追蹤和更新 Ticket 狀態：READ 操作（summary/query/dashboard/list/runqueue/board/5W1H/validate 等）與 UPDATE 操作（claim/complete/release/set-*/append-log/dispatch 等），主要子命令清單見下列 `references/track-command.md`；`list` 支援 `--wave`、`--status`、`--format`、`--top`、`--all`（預設 `--top 10`，priority 排序） | `/ticket track summary` | `references/workflow-execute.md` | 〈執行流程決策樹〉〈更新操作決策樹〉〈批量操作決策樹〉〈完成判斷決策樹〉〈完成後同步提醒〉 |
| `track` |  | `ticket track query <id>` | `references/workflow-query.md` | 〈查詢流程決策樹〉 |
| `track` |  | `ticket track claim <id>` / `ticket track complete <id>` / `ticket track complete <id> --no-stage` / `ticket track complete <id> --force` | `references/track-command.md` | 〈READ 操作〉〈track runqueue 子命令（Scheduler）〉〈UPDATE 操作〉〈UPDATE 操作補充：commit 副作用與欄位語意〉〈Ticket 狀態與程式碼提交的 root 分離（worktree 場景）〉〈驗收條件操作詳解〉〈CLI 可修改欄位 vs 手動編輯欄位〉〈track deps / depth 子命令〉〈track parallel-check 子命令〉〈track board 子命令〉〈track audit 子命令〉〈統一錯誤訊息格式（W17-008.5.2）〉〈CLI 錯誤分類（W17-008.5.4）〉〈track stale-list 子命令（W17-200）〉〈track stuck-anas 子命令（W17-008.15 方案 D 第 1 項）〉〈track dashboard 子命令（W10-114 / W10-113 M1+M4'）〉〈track list 子命令（W10-115 / W10-113 M3）〉〈track dispatch-validate 子命令（W17-003）〉〈track dispatch-readiness 子命令（W17-053）〉〈track sessions 子命令（multi-PM 協調層 Phase 1，issue tarrragon/claude#77）〉〈track reclaim 子命令（multi-PM 協調層 Phase 3，issue tarrragon/claude#77）〉〈track activity 子命令（multi-PM 協調層 Phase 2，L1 新鮮度）〉〈track conflicts 子命令（multi-PM 協調層 Phase 2，where.files 交集）〉〈track onboard 子命令（multi-PM 協調層 Phase 2，入場四節彙整）〉〈track hook-liveness 子命令〉〈track register-artifact / resolve-artifact / list-artifacts 子命令〉〈空狀態字面規範（track 系列命令通用）〉<!-- rule8-exempt: relocation:自 references/track-command.md 逐字搬移 --> |
| `track dashboard` | PM 接手聚合視圖，見 track-command.md〈track dashboard 子命令（W10-114 / W10-113 M1+M4'）〉 | `ticket track dashboard --top 5` | — | — |
| `track list` | 預設 top 10 priority 排序，見 track-command.md〈track list 子命令（W10-115 / W10-113 M3）〉 | `ticket track list --status pending --top 20` | — | — |
| `track td-status` | TD 清單校準，見 track-command.md〈td-status — 校準 TD 清單（PC-094）〉 | `ticket track td-status <id>` | — | — |
| `track reclaim` | 已鎖 ticket 受控釋放（ghost 鑑識三查，multi-PM Phase 3），見 track-command.md〈track reclaim 子命令（multi-PM 協調層 Phase 3，issue tarrragon/claude#77）〉 | `ticket track reclaim <id> --confirm` | — | — |
| `track stuck-anas` | 列出卡住的 ANA（spawned_tickets／children 全完成卻未收尾），見 track-command.md〈track stuck-anas 子命令（W17-008.15 方案 D 第 1 項）〉 | `ticket track stuck-anas --wave 3` | — | — |
| `track depth` | 查詢嵌套深度與 can_descend（沿 parent_id 鏈），見 track-command.md〈track deps / depth 子命令〉 | `ticket track depth <id>.5` | — | — |
| `track parallel-check` | 偵測子任務/兄弟 ticket 檔案衝突（對齊 askuserquestion-rules 規則 7），見 track-command.md〈track parallel-check 子命令〉 | `ticket track parallel-check <id>` | — | — |
| `track dispatch-validate` | Context Bundle 自動填料合理性檢查（C 方案安全網；exit code 語意見 `references/track-command.md`〈track dispatch-validate 子命令（W17-003）〉，與 `dispatch-check` 不共享） | `ticket track dispatch-validate <id>` | — | — |
| `track dispatch-readiness` | 派發前綜合就緒度檢查（六項檢查：功能職責數／修改檔案數／Context Bundle tokens／acceptance 一致性／where.files 存在性／acceptance 路徑涵蓋；exit code 與閾值語意見 `references/track-command.md`〈track dispatch-readiness 子命令（W17-053）〉，與 `dispatch-check`／`dispatch-validate` 不共享） | `ticket track dispatch-readiness <id>` | — | — |
| `track` | 設定或釐清 Ticket 5W1H 欄位語意、阻擋情境判斷 | — | `references/field-semantics.md` | 〈適用範圍〉〈六欄位定義〉〈阻擋語意對照表〉〈用戶情境對照表〉〈欄位選擇決策樹〉〈反模式速查〉〈相關文件〉 |
| `track` | 查詢 Ticket 生命週期詳細規則（建立格式、驗收條件、決策樹路徑等） | — | `references/ticket-lifecycle-details.md` | 〈任務鏈後續步驟建議〉〈任務鏈 ID 格式〉〈Ticket 建立格式範本〉〈驗收條件 4V 格式要求〉〈Ticket 有效性驗證〉〈驗收前置條件檢查流程〉〈acceptance-gate-hook 技術細節〉〈驗收提示訊息模板〉〈P0 緊急任務處理〉〈簡化驗收檢查清單〉〈與其他流程的整合〉〈變更日誌〉 |
| `handoff` | 任務鏈管理與 Context 交接：支援自動判斷方向、指定交接到父/子/兄弟任務，含絕對指向（`--next`）與從 worklog 批次補建（`--from-worklog`）。五種交接情境 | `/ticket handoff <id> --to-sibling <id2>` | `references/workflow-handoff.md` | 〈交接流程決策樹〉〈狀態-命令映射規則〉〈任務鏈結束決策樹〉〈恢復流程決策樹〉 |
| `handoff` |  |  | `references/handoff-command.md` | 〈設計意圖〉〈指向語意：source vs target（W17-164）〉〈基本用法〉〈用法〉〈自動偵測行為〉〈Session 結束時的使用方式〉〈按 Ticket 狀態選擇命令〉〈任務鏈結束時的替代流程〉〈五種情境〉<!-- rule8-exempt: relocation:自 references/handoff-command.md 逐字搬移 --> |
| `resume` | 恢復任務：從 handoff 檔案載入 context；SessionStart hook 僅被動提醒，實際觸發見〈無子命令時的預設行為（dashboard-first）〉；`/ticket resume <id>` 可明確恢復指定任務（交接/恢復決策樹與 `handoff` 共用 `references/workflow-handoff.md`，見上列） | `/ticket resume <id>` | `references/resume-command.md` | 〈用法〉〈恢復機制（v2.0.0 - 顯式觸發）〉〈參數說明〉〈handoff JSON 格式〉〈相關 Hook〉 |
| `migrate` | Ticket ID 遷移：支援單一和批量遷移，自動更新所有 ID 引用和 chain 資訊 | `/ticket migrate <old-id> <new-id>` | `references/workflow-migrate.md` | 〈ID 遷移決策樹〉 |
| `migrate` |  |  | `references/migrate-command.md` | 〈基本用法〉〈前置檢查（強制）〉〈單一遷移範例〉〈批量遷移配置檔案格式〉〈遷移邏輯〉〈Collision Detection（W14-048）〉〈備份機制〉〈選項說明〉<!-- rule8-exempt: relocation:自 references/migrate-command.md 逐字搬移 --> |
| `generate` | Plan 轉換為 Tickets：從 Plan 檔案自動生成 Atomic Tickets（Plan-to-Ticket 轉換） | `/ticket generate plan.md --version 0.31.0 --wave 5` | `references/generate-command.md` | 〈用法〉〈參數說明〉〈範例〉〈流程〉 |
| `batch-create` | 批次建立 Tickets：從模板 + 目標清單快速建立多個 Tickets，適用大量同質任務場景（如 30 個實作子任務）。詳見表後「batch-create 補充」 | `ticket batch-create --template impl-parsley --targets "a,b,c" --wave 28` | — | — |
| `show` | 顯示 Ticket（含 Markdown 渲染）。終端閱讀專用，詳見表後「show 補充」 | `ticket show <id>` / `ticket show <id> -r` | — | — |
| `version-shift` | 版本遷移：批次更新 ticket 版本號與 todolist.yaml | `ticket version-shift <from_version> <to_version>` | — | — |
| （跨子命令） | 查詢目錄結構、共用模組設計、自動化分析功能、系統模型設計自我描述完整版、CLI 安裝與執行方式，或覆核 skill 自身測試套件 | — | `references/architecture.md` | 〈系統模型（設計自我描述，完整版）〉〈目錄結構〉〈共用模組設計〉〈自動化分析功能〉〈安裝與執行方式〉〈覆核測試指令（skill 自身測試套件）〉 |

拆分邊界判讀（測試變綠驗收點）見 `/tdd` skill 的 task-granularity-rules；本 skill 負責建立/拆分 ticket 本身。

其餘 Ticket 生命週期規範散於框架文件（僅指名身分，不納入上表涵蓋章節雙向驗證）：Ticket body 各 type（ANA/IMP/DOC）章節要求見 `ticket-body-schema` 規則；Atomic Ticket 拆分原則見 `atomic-ticket-methodology` 方法論；Ticket 生命週期管理見 `ticket-lifecycle-management` 方法論；PM 端生命週期流程見 `ticket-lifecycle` 規則。

### batch-create 補充

`batch-create` 只建立 tickets，不派發 agents。多任務派發前先寫 dispatch-plan，保留每張 ticket 的獨立 prompt、commit policy 與 Exit Status；禁止把 batch-create 誤用為 batch dispatch CLI。

**使用情境**：W28 場景快速建立 30 個相同類型的實作任務；需要多個同質 Ticket，避免逐一手工填寫。

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

**參數說明**：`--template`（必填，模板名稱如 `impl-parsley`）／`--targets`（必填，逗號分隔目標清單）／`--version`（建議明示；本專案自動偵測失效，缺此參數會回「無法偵測版本，請使用 --version 指定」，版本偵測與 `create` 不同源已建 0.2.1-W3-1296 待修）／`--wave`（必填；缺或 < 1 會回「Wave 編號無效」）／`--parent`（可選，建立子任務）／`--dry-run`（預演模式）。

**預定義模板**：`impl-parsley`（parsley-flutter-developer 實作 Ticket 模板，type: IMP, who: parsley-flutter-developer）；更多模板可在 `ticket_system/templates/` 目錄中定義。

### show 補充

TTY 下自動以 `glow`/`mdcat`/`bat` 渲染；pipe 時自動降純文字，避免汙染下游消費者。

```bash
ticket show <full-id>          # 完整 ID（含版本號）
ticket show <short-id>         # 短 ID（自動補當前版本）
ticket show <short-id> -r      # 純文字（同 track full）
ticket show <short-id> -R bat  # 指定渲染器
ticket show <short-id> -P      # 停用分頁
```

短 flag：`-r` raw / `-R` renderer / `-p` pager / `-P` no-pager。完整說明 `ticket show --help`。

與 `ticket track full <id>` 差異：`track full` 永遠純文字（腳本友善，向後相容）；`show` 預設渲染（閱讀友善）。

## Ticket Body Schema（type-aware）

不同 type（ANA/IMP/DOC）的 body 各章節必填/選填/免填要求，與 `ticket create` 自動插入的 `<!-- Schema[TYPE/Section]: 狀態 -->` 標註機制，權威見 `ticket-body-schema` 規則。

---

版本紀錄在同目錄的 `CHANGELOG.md`。
