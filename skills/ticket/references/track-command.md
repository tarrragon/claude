# track 子命令

追蹤和更新 Ticket 狀態。

> **何時讀**：執行或查詢 `track` 子命令時——READ 操作（`summary`/`query`/`dashboard`/`list`/`runqueue`/`board`/`5W1H`/`validate` 等）或 UPDATE 操作（`claim`/`complete`/`release`/`set-*`/`append-log`/`dispatch` 等）；worktree 場景下需確認 ticket 狀態與程式碼提交的 root 分離規則；subagent 認領自身 ticket 時查 claim 推薦用法。**亦由此進入**：`SKILL.md`〈Ticket 狀態與程式碼提交的 root 分離〉〈subagent 派發時 claim 推薦用法〉兩節正文；`SKILL.md` 子命令路由表 `track` 頂層列（完整子命令清單指標）與 `track dispatch-validate`／`track dispatch-readiness` 兩列（exit code 語意指標）；`CHANGELOG.md`（track board 子命令變更記錄）；`architecture.md`「覆核測試指令」節末（Python 測試路徑推導指標）；`field-semantics.md`〈相關文件〉（set-blocked-by / set-related-to 操作說明指標）；`ticket_system/lib/lease.py` 原始碼註解（STALE 判準分岔說明）。本檔內文首見的 15 個術語（`lease`／`STALE`／接手／`registry`／`heartbeat`／`FRESH`／`SessionEnd`／鑑識三查／票面／隔離索引／派發骨架／世界平面／落票／制式句／`ghost`）權威定義見 `architecture.md`〈術語〉，本檔不重複定義。
>
> **同目錄**：`workflow-execute.md`（UPDATE 操作的決策樹）、`workflow-query.md`（READ 操作的決策樹）、`field-semantics.md`（六欄位語意權威定義）、`ticket-lifecycle-details.md`（驗收條件與建立格式細節）、`architecture.md`（測試路徑推導與系統模型）。
>
> **溯源**：本檔內容為累積式增修，非單次外移——初始批次於本專案匯入 commit `f375ae675` 已存在，此後逐張 ticket 增補子命令（如 `sessions`／`reclaim`／`hook-liveness` 等）。近期兩次可查的外移：一次自 `SKILL.md`〈子命令詳細說明〉搬入 create/track 增量共 153 行；另一次將 `SKILL.md`〈subagent 派發時 claim 推薦用法〉整節（655 tokens）逐字搬入本檔「claim 推薦用法（subagent 派發時的身份申報）」章節（兩次外移皆發生於 2026-09-07，可用 `git log --oneline -- references/track-command.md` 查證）。

**分檔**：依職責拆為同目錄六檔——`track-command-commit.md`（track commit、set-exit-status、root 分離）、`track-command-update.md`（UPDATE 操作、驗收條件、可修改欄位）、`track-command-dispatch.md`（dispatch 系列）、`track-command-session.md`（sessions、reclaim、activity、conflicts、onboard、hook-liveness、artifacts）、`track-command-query.md`（READ、runqueue、deps/depth、parallel-check、board、list）、`track-command-health.md`（audit、stale-list、stuck-anas、dashboard）。本檔對被移走的章節保留同名標題加一行路由。

本檔章節：〈子命令總覽（全量對照 --help）〉〈READ 操作〉〈track runqueue 子命令（Scheduler）〉〈UPDATE 操作〉〈UPDATE 操作補充：commit 副作用與欄位語意〉〈track commit 子命令〉〈track move-lines 子命令〉〈track set-exit-status 子命令〉〈Ticket 狀態與程式碼提交的 root 分離（worktree 場景）〉〈驗收條件操作詳解〉〈CLI 可修改欄位 vs 手動編輯欄位〉〈track deps / depth 子命令〉〈track parallel-check 子命令〉〈track board 子命令〉〈track audit 子命令〉〈track stale-list 子命令〉〈track stuck-anas 子命令〉〈track dashboard 子命令〉〈track list 子命令〉〈track dispatch 子命令〉〈track dispatch-validate 子命令〉〈track dispatch-readiness 子命令〉〈track dispatch-check 子命令〉〈track sessions 子命令〉〈track reclaim 子命令〉〈track activity 子命令〉〈track conflicts 子命令〉〈track onboard 子命令〉〈track hook-liveness 子命令〉〈track register-artifact / resolve-artifact / list-artifacts 子命令〉〈共用旗標語意（track 系列命令通用）〉〈空狀態字面規範（track 系列命令通用）〉。

## 子命令總覽（全量對照 --help）

`ticket track --help` 為子命令清單的權威來源，本表逐一列出其當下輸出的全部子命令（含旗標細節一律見 `--help` 本身，本表不重複展開）。右欄「章節」指向本檔或同族檔（`track-command-commit.md`、`-update.md`、`-dispatch.md`、`-session.md`、`-query.md`、`-health.md`）內對應 `##` 章節，被移走的章節在本檔以同名標題加一行路由保留；標「--help」者代表本檔目前只有旗標層說明或完全未展開，用法以 `ticket track <子命令> --help` 為準。子命令增減時本表可能落後，出現落差以 `ticket track --help` 現況為準。

| 子命令 | 一句話用途 | 章節 |
| --- | --- | --- |
| `claim` | 認領 Ticket | 〈UPDATE 操作〉 |
| `complete` | 標記完成 | 〈UPDATE 操作〉 |
| `finish` | `complete` 別名（CLI 仍保留；隔離代理人不以它收尾，收尾止於 `ticket track commit`，complete 由 PM 於合併後執行） | 〈UPDATE 操作補充：commit 副作用與欄位語意〉 |
| `close` | 關閉 Ticket（已在其他 Ticket 一併解決） | --help |
| `set-closed-by` | 修正已 closed 票的 `closed_by` 欄位 | 〈UPDATE 操作補充：commit 副作用與欄位語意〉 |
| `restore` | 還原 closed 票為 pending（closed 態唯一合法出邊，需 `--reason`） | 〈UPDATE 操作補充：commit 副作用與欄位語意〉 |
| `release` | 釋放 Ticket（退回等待態） | 〈UPDATE 操作〉 |
| `reclaim` | 回收 STALE session 持有的 in_progress 票（鑑識三查） | 〈track reclaim 子命令〉 |
| `verify` | 單獨執行 AC 驗證，不變更狀態 | 〈UPDATE 操作補充：commit 副作用與欄位語意〉 |
| `summary` | 快速摘要 | 〈READ 操作〉 |
| `query` | 查詢單一 Ticket | 〈READ 操作〉 |
| `tree` | 顯示任務鏈樹狀結構 | 〈READ 操作〉 |
| `list` | 列出 Tickets（支援狀態篩選） | 〈track list 子命令〉 |
| `search` | 搜尋 Tickets（依 UC/Spec/Prop 引用或檔案路徑） | --help |
| `chain` | 顯示完整任務鏈 | 〈READ 操作〉 |
| `deps` | 顯示衍生關係（`spawned_tickets` + `source_ticket`） | 〈track deps / depth 子命令〉 |
| `full` | 顯示 Ticket 完整內容 | 〈READ 操作〉 |
| `show` | `full` 的 alias（對齊 git/docker/kubectl 慣例） | 〈READ 操作〉 |
| `log` | 顯示執行日誌 | 〈READ 操作〉 |
| `version` | 指定版本進度摘要 | 〈READ 操作〉 |
| `who`/`title`/`what`/`when`/`where`/`why`/`how` | 查詢單一 5W1H 或 `title` 欄位 | 〈READ 操作〉 |
| `set-who`/`set-what`/`set-when`/`set-where`/`set-why`/`set-how` | 設定對應 5W1H 欄位 | 〈UPDATE 操作〉 |
| `set-title` | 設定清單顯示用短標籤（與 `what` 刻意分離） | 〈UPDATE 操作補充：commit 副作用與欄位語意〉 |
| `set-priority` | 設定 `priority` 欄位（`P0`-`P3`） | 〈CLI 可修改欄位 vs 手動編輯欄位〉 |
| `set-scope-blocker` | 事後設定或清除 `scope_blocker` 欄位（`--reason <text>`/`--clear` 互斥；供凍結前已存在的必要票回溯標記） | 〈UPDATE 操作〉 |
| `add-acceptance` | 追加驗收條件 | --help |
| `remove-acceptance` | 移除驗收條件（按編號） | --help |
| `add-spawned` | 追加 `spawned_tickets` 項目 | 〈UPDATE 操作〉 |
| `remove-spawned` | 移除 `spawned_tickets` 項目（按 ID，非索引；對不存在的 ID 回報而非靜默；成功移除時同步清除目標票回指本票的 `source_ticket`） | 〈UPDATE 操作〉 |
| `set-decision-tree` | 設定 `decision_tree_path` 欄位 | --help |
| `batch-claim` | 批量認領 Tickets | 〈UPDATE 操作〉 |
| `batch-complete` | 批量完成 Tickets | 〈UPDATE 操作〉 |
| `agent` | 查詢代理人的所有 Tickets | 〈READ 操作〉 |
| `phase` | 更新 Ticket 的 TDD Phase | 〈UPDATE 操作〉 |
| `add-child` | 建立 Ticket 父子關係 | 〈UPDATE 操作〉 |
| `set-parent` | 修正 `parent_id`（改寫或清除，同步上游 `children`） | 〈UPDATE 操作〉 |
| `set-blocked-by` | 設定 `blockedBy` 欄位 | 〈UPDATE 操作〉 |
| `set-related-to` | 設定 `relatedTo` 欄位 | 〈UPDATE 操作〉 |
| `check-acceptance` | 勾選或取消勾選驗收條件（舊語法） | 〈驗收條件操作詳解〉 |
| `set-acceptance` | 勾選/取消勾選/新增/改文字/刪除驗收條目 | 〈驗收條件操作詳解〉 |
| `validate` | 驗證 frontmatter 4 欄位合規性 | 〈UPDATE 操作〉 |
| `append-log` | 追加執行日誌到 Ticket | 〈UPDATE 操作補充：commit 副作用與欄位語意〉 |
| `add-spawn-request` | 追加結構化 spawn request 至 Spawn Requests 章節 | 〈UPDATE 操作補充：commit 副作用與欄位語意〉 |
| `resolve-spawn-request` | 標記 spawn request 狀態並回填 `spawned_tickets` | 〈UPDATE 操作補充：commit 副作用與欄位語意〉 |
| `add-exempt-marker` | 對既有行補上 PC-093-exempt marker | 〈UPDATE 操作補充：commit 副作用與欄位語意〉 |
| `fix-multi-view-status` | 覆寫 ANA Solution 的 `multi_view_status` 行值；skipped／n_a 同步寫入平鋪 `reason:` 行，章節缺欄位行時於章節末新增兩行 | 〈UPDATE 操作補充：commit 副作用與欄位語意〉 |
| `register-artifact` | 登記實驗器材至 Solution 章節 | 〈track register-artifact / resolve-artifact / list-artifacts 子命令〉 |
| `resolve-artifact` | 標記實驗器材狀態為 removed/kept | 〈track register-artifact / resolve-artifact / list-artifacts 子命令〉 |
| `list-artifacts` | 列出 ticket 已登記的實驗器材 | 〈track register-artifact / resolve-artifact / list-artifacts 子命令〉 |
| `set-exit-status` | 設定 Exit Status 章節（CLI 生成 fenced YAML） | 〈track set-exit-status 子命令〉 |
| `set-completion-info` | 設定 Completion Info 章節（CLI 生成格式） | --help |
| `audit` | 執行驗收檢查 | 〈track audit 子命令〉 |
| `audit-version` | 掃描並驗證 Ticket 版本歸屬一致性 | --help |
| `board` | 顯示樹狀看板視圖 | 〈track board 子命令〉 |
| `snapshot` | 產出專案全局狀態快照 | --help |
| `agent-status` | 印出 TaskOutput 安全查詢指引 | --help |
| `handoff-ready` | 檢查 /clear ready 狀態 | --help |
| `checkpoint-status` | 檢視當前 Checkpoint 詳情 | --help |
| `dispatch-check` | 檢查活躍派發（`.claude/dispatch-active.json`） | 〈track dispatch-check 子命令〉 |
| `parallel-check` | 分析 children/兄弟 pending 集合的檔案衝突 | 〈track parallel-check 子命令〉 |
| `runqueue` | 統一 scheduler CLI | 〈track runqueue 子命令（Scheduler）〉 |
| `dashboard` | 聚合視圖：in_progress + ready + stale warning | 〈track dashboard 子命令〉 |
| `stuck-anas` | 列出卡住的 ANA | 〈track stuck-anas 子命令〉 |
| `stale-list` | 列出 stale pending ticket 明細 | 〈track stale-list 子命令〉 |
| `td-status` | 校準 TD 清單（PC-094） | 〈UPDATE 操作補充：commit 副作用與欄位語意〉 |
| `hook-health` | 掃描 `.claude/hook-logs/` 評估 Hook 觸發頻率 | --help |
| `hook-liveness` | 從 hook 檔路徑解析後查 `_liveness` 觸發記錄 | 〈track hook-liveness 子命令〉 |
| `dispatch-validate` | 檢查 Context Bundle 自動填料合理性 | 〈track dispatch-validate 子命令〉 |
| `dispatch-readiness` | 派發前認知負擔閾值與綜合就緒度檢查 | 〈track dispatch-readiness 子命令〉 |
| `depth` | 查詢嵌套深度與 `can_descend` 判定 | 〈track deps / depth 子命令〉 |
| `sessions` | 列出同專案 pm-registry session 清單 | 〈track sessions 子命令〉 |
| `activity` | 機械推導每張 in_progress 票的最後活動時間 | 〈track activity 子命令〉 |
| `conflicts` | 偵測 pending/in_progress 票 `where.files` 交集 | 〈track conflicts 子命令〉 |
| `topics` | 列出全部主題（票數／status 分佈） | 〈track board 子命令〉 |
| `topic` | 檢視單一主題的任務鏈 map | 〈track board 子命令〉 |
| `topic-backfill-list` | 列出尚未歸屬主題的 pending 票 | --help |
| `topic-backfill-assign` | 批次指派主題 | --help |
| `onboard` | PM 入場彙整（活同事/孤兒/髒檔歸屬/可認領建議） | 〈track onboard 子命令〉 |
| `dispatch` | 派發即落票，輸出 prompt 骨架 | 〈track dispatch 子命令〉 |
| `commit` | 以隔離索引提交 `where.files` 子集內的指定檔案 | 〈track commit 子命令〉 |
| `move-lines` | 依行範圍把 src 的文字搬到 dst，驗證行數守恆後原子寫入（src、dst 皆須在 `where.files` 內） | 〈track move-lines 子命令〉 |

## READ 操作

> 已移至 `track-command-query.md`〈READ 操作〉。

---

## track runqueue 子命令（Scheduler）

> 已移至 `track-command-query.md`〈track runqueue 子命令（Scheduler）〉。

---

## UPDATE 操作

> 已移至 `track-command-update.md`〈UPDATE 操作〉。

---

## UPDATE 操作補充：commit 副作用與欄位語意

> 已移至 `track-command-update.md`〈UPDATE 操作補充：commit 副作用與欄位語意〉。

### append-log 副作用：auto-commit

> 已移至 `track-command-update.md`〈append-log 副作用：auto-commit〉。

### complete 前置清單

> 已移至 `track-command-update.md`〈complete 前置清單〉。

### complete 副作用：ticket metadata 與程式碼變更恆分兩個 commit

> 已移至 `track-command-update.md`〈complete 副作用：ticket metadata 與程式碼變更恆分兩個 commit〉。

### `--no-stage` 的覆蓋範圍

> 已移至 `track-command-update.md`〈`--no-stage` 的覆蓋範圍〉。

### claim 推薦用法（subagent 派發時的身份申報）

> 已移至 `track-command-update.md`〈claim 推薦用法（subagent 派發時的身份申報）〉。

### td-status — 校準 TD 清單（PC-094）

> 已移至 `track-command-update.md`〈td-status — 校準 TD 清單（PC-094）〉。

---

## track commit 子命令

> 已移至 `track-command-commit.md`〈track commit 子命令〉。

### 歸屬 trailer 自動補全

> 已移至 `track-command-commit.md`〈歸屬 trailer 自動補全〉。

### Fallback 條件

> 已移至 `track-command-commit.md`〈Fallback 條件〉。

---

## track set-exit-status 子命令

> 已移至 `track-command-commit.md`〈track set-exit-status 子命令〉。

---

## Ticket 狀態與程式碼提交的 root 分離（worktree 場景）

> 已移至 `track-command-commit.md`〈Ticket 狀態與程式碼提交的 root 分離（worktree 場景）〉。

---

## 驗收條件操作詳解

> 已移至 `track-command-update.md`〈驗收條件操作詳解〉。

---

## CLI 可修改欄位 vs 手動編輯欄位

> 已移至 `track-command-update.md`〈CLI 可修改欄位 vs 手動編輯欄位〉。

---

## track deps / depth 子命令

> 已移至 `track-command-query.md`〈track deps / depth 子命令〉。

### depth — 計算嵌套深度

> 已移至 `track-command-query.md`〈depth — 計算嵌套深度〉。

---

## track parallel-check 子命令

> 已移至 `track-command-query.md`〈track parallel-check 子命令〉。

---

## track board 子命令

> 已移至 `track-command-query.md`〈track board 子命令〉。

---

## track audit 子命令

> 已移至 `track-command-health.md`〈track audit 子命令〉。

---

## track stale-list 子命令

> 已移至 `track-command-health.md`〈track stale-list 子命令〉。

---

## track stuck-anas 子命令

> 已移至 `track-command-health.md`〈track stuck-anas 子命令〉。

---

## track dashboard 子命令

> 已移至 `track-command-health.md`〈track dashboard 子命令〉。

---

## track list 子命令

> 已移至 `track-command-query.md`〈track list 子命令〉。

---

## track dispatch 子命令

> 已移至 `track-command-dispatch.md`〈track dispatch 子命令〉。

---

## track dispatch-validate 子命令

> 已移至 `track-command-dispatch.md`〈track dispatch-validate 子命令〉。

---

## track dispatch-readiness 子命令

> 已移至 `track-command-dispatch.md`〈track dispatch-readiness 子命令〉。

---

## track dispatch-check 子命令

> 已移至 `track-command-dispatch.md`〈track dispatch-check 子命令〉。

---

## track sessions 子命令

> 已移至 `track-command-session.md`〈track sessions 子命令〉。

---

## track reclaim 子命令

> 已移至 `track-command-session.md`〈track reclaim 子命令〉。

---

## track activity 子命令

> 已移至 `track-command-session.md`〈track activity 子命令〉。

---

## track conflicts 子命令

> 已移至 `track-command-session.md`〈track conflicts 子命令〉。

---

## track onboard 子命令

> 已移至 `track-command-session.md`〈track onboard 子命令〉。

---

## track hook-liveness 子命令

> 已移至 `track-command-session.md`〈track hook-liveness 子命令〉。

---

## track register-artifact / resolve-artifact / list-artifacts 子命令

> 已移至 `track-command-session.md`〈track register-artifact / resolve-artifact / list-artifacts 子命令〉。

---

## 共用旗標語意（track 系列命令通用）

適用命令：`stale-list`／`stuck-anas`／`sessions`／`activity`／`conflicts`／`onboard`。

| 旗標／設計 | 語意 |
|-----------|------|
| `--all` | 無作用旗標：預設即掃描全部 active 版本；如需限縮請用 `--version` |
| version-agnostic | 命令註冊於 `_create_version_agnostic_handlers()`，不需 active version |

### 滯留判準閾值總表

「這張票／這個 session 還活著嗎」在本 skill 內由五套獨立閾值分別回答，判斷對象與資料來源互不相同，同一張票可能同時符合一套「活」與另一套「死」的判定：

| 判準 | 閾值 | 判斷對象 | 依據 | 原始碼位置 |
|------|------|---------|------|-----------|
| lease TTL | 30 分 | session heartbeat 新鮮度 | `heartbeat_ts` 與查詢當下的分鐘差 | `.claude/lib/pm_registry.py` `STALE_THRESHOLD_MINUTES` |
| dashboard `--stale-threshold` | 60 分（可覆寫） | `in_progress` 票的 stale 警告 | 同上 heartbeat 差值，門檻獨立於 lease TTL | `ticket_system/commands/track_dashboard.py` `DEFAULT_STALE_THRESHOLD_MIN` |
| `is_stale_in_progress` | 24 小時 | `in_progress` 票本身的存活期 | 依 `started_at` 與查詢當下的時差，不看 heartbeat | `ticket_system/lib/staleness.py` `STALE_IN_PROGRESS_HOURS` |
| stale-list pending 分級 | 7／14／30 天 | `pending` 票的建立年齡 | 依 `created` 與查詢當下的天數差 | `ticket_system/lib/staleness.py` `STALE_INFO_DAYS`／`STALE_WARNING_DAYS`／`STALE_CRITICAL_DAYS` |
| teammate idle 逾時判準（本 skill 外部） | 30 分 | teammate 是否仍在工作（無 commit 無 append-log） | 見 `.claude/pm-rules/parallel-dispatch.md`〈跨 session 同儕沉默時的接管判準〉 | 外部檔案，非本 CLI 常數 |

`runqueue --format=list` 的 `[RECLAIMABLE]`（lease TTL）可與 `[STALE]`（`is_stale_in_progress`）並列疊加，兩者來源不同、各自獨立出現，見 `track-command-query.md`〈track runqueue 子命令（Scheduler）〉。**Action**：判讀任一「stale／reclaimable」標記前，先確認該標記出自本表哪一套判準，不可假設全站僅一套滯留定義。

## 空狀態字面規範（track 系列命令通用）

`activity`、`conflicts`、`onboard`、`stale-list`、`stuck-anas`、`dashboard` 六個命令的空狀態一律採全形括號包裹的中文描述句 `（無 XXX）`，不使用英文 `(none)`：`activity` 為「（無 in_progress ticket）」、`conflicts` 為「（無衝突）」、`onboard` 四節分別為「（無活同事）」「（無孤兒 entry）」「（無髒檔）」「（無可認領建議）」、`stale-list` 為「（無符合條件的 stale ticket）」、`stuck-anas` 為「（無卡住的 ANA）」、`dashboard`（In Progress / Handoff Target / Ready Top N / Stale Warning 四區塊）分別為「（無 in_progress ticket）」「（無 handoff target）」「（無可認領建議）」「（無 stale ticket）」。技術術語（`in_progress`、`entry`、`handoff target`）依語言約束規則 4 保留原文，不強制中譯。

## track move-lines 子命令

依行範圍搬移文字，取代 Read 加 Write 全文重寫（284.1 阻擋 Bash 寫入後的受控搬移通道）。

```
ticket track move-lines <ticket-id> --src <path> --lines <起>-<迄> --dst <path> --at <行號|end> [--worktree <abs-path>]
```

| 旗標 | 語意 |
|------|------|
| `--lines` | 來源行範圍，1 起算、含兩端 |
| `--at` | 目標檔插入位置：N 表示搬移段第一行成為目標第 N 行；`end` 附加於尾端 |
| `--worktree` | 檔案所在 linked worktree 絕對路徑（路徑相對其 repo root 解析） |

**範圍**：`--src` 與 `--dst` 皆須在 ticket `where.files` 寫入範圍內（與 `track commit` 同一判準），否則拒絕。另拒絕 symlink 目標（含解 symlink 後落在 repo 之外者），且 `--worktree` 須屬本 repo 的 `git worktree list`；git 查詢失敗時拒絕。`--src` 與 `--dst` 不可為同一檔。

**守恆與原子性**：記憶體內先驗證「來源減少行數＝目標增加行數」且目標內搬移段與抽出段逐字相同，通過才以暫存檔加 rename 寫入；任一步失敗（含目標寫入失敗）還原兩檔並以 exit 1 結束，兩檔逐位元不變。命令只改檔案，不提交；提交仍走 `track commit`。

**Exit code**：0 成功；1 拒絕或失敗（範圍、行範圍非法、守恆失敗、寫入失敗）。
