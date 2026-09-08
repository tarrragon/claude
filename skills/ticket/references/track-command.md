# track 子命令

追蹤和更新 Ticket 狀態。

> **何時讀**：執行或查詢 `track` 子命令時——READ 操作（`summary`/`query`/`dashboard`/`list`/`runqueue`/`board`/`5W1H`/`validate` 等）或 UPDATE 操作（`claim`/`complete`/`release`/`set-*`/`append-log`/`dispatch` 等）；worktree 場景下需確認 ticket 狀態與程式碼提交的 root 分離規則；subagent 認領自身 ticket 時查 claim 推薦用法。**亦由此進入**：`SKILL.md`〈Ticket 狀態與程式碼提交的 root 分離〉〈subagent 派發時 claim 推薦用法〉兩節正文；`SKILL.md` 子命令路由表 `track` 頂層列（完整子命令清單指標）與 `track dispatch-validate`／`track dispatch-readiness` 兩列（exit code 語意指標）；`CHANGELOG.md`（track board 子命令變更記錄）；`architecture.md`「覆核測試指令」節末（Python 測試路徑推導指標）；`field-semantics.md`〈相關文件〉（set-blocked-by / set-related-to 操作說明指標）；`ticket_system/lib/lease.py` 原始碼註解（STALE 判準分岔說明）。本檔內文首見的 15 個術語（`lease`／`STALE`／接手／`registry`／`heartbeat`／`FRESH`／`SessionEnd`／鑑識三查／票面／隔離索引／派發骨架／世界平面／落票／制式句／`ghost`）權威定義見 `architecture.md`〈術語〉，本檔不重複定義。
>
> **同目錄**：`workflow-execute.md`（UPDATE 操作的決策樹）、`workflow-query.md`（READ 操作的決策樹）、`field-semantics.md`（六欄位語意權威定義）、`ticket-lifecycle-details.md`（驗收條件與建立格式細節）、`architecture.md`（測試路徑推導與系統模型）。
>
> **溯源**：本檔內容為累積式增修，非單次外移——初始批次於本專案匯入 commit `f375ae675` 已存在，此後逐張 ticket 增補子命令（如 `sessions`／`reclaim`／`hook-liveness` 等）。近期兩次可查的外移：一次自 `SKILL.md`〈子命令詳細說明〉搬入 create/track 增量共 153 行；另一次將 `SKILL.md`〈subagent 派發時 claim 推薦用法〉整節（655 tokens）逐字搬入本檔「claim 推薦用法（subagent 派發時的身份申報）」章節（兩次外移皆發生於 2026-09-07，可用 `git log --oneline -- references/track-command.md` 查證）。

本檔章節：〈子命令總覽（全量對照 --help）〉〈READ 操作〉〈track runqueue 子命令（Scheduler）〉〈UPDATE 操作〉〈UPDATE 操作補充：commit 副作用與欄位語意〉〈track commit 子命令〉〈track set-exit-status 子命令〉〈Ticket 狀態與程式碼提交的 root 分離（worktree 場景）〉〈驗收條件操作詳解〉〈CLI 可修改欄位 vs 手動編輯欄位〉〈track deps / depth 子命令〉〈track parallel-check 子命令〉〈track board 子命令〉〈track audit 子命令〉〈track stale-list 子命令〉〈track stuck-anas 子命令〉〈track dashboard 子命令〉〈track list 子命令〉〈track dispatch 子命令〉〈track dispatch-validate 子命令〉〈track dispatch-readiness 子命令〉〈track dispatch-check 子命令〉〈track sessions 子命令〉〈track reclaim 子命令〉〈track activity 子命令〉〈track conflicts 子命令〉〈track onboard 子命令〉〈track hook-liveness 子命令〉〈track register-artifact / resolve-artifact / list-artifacts 子命令〉〈共用旗標語意（track 系列命令通用）〉〈空狀態字面規範（track 系列命令通用）〉。

## 子命令總覽（全量對照 --help）

`ticket track --help` 為子命令清單的權威來源，本表逐一列出其當下輸出的全部子命令（含旗標細節一律見 `--help` 本身，本表不重複展開）。右欄「章節」指向本檔內對應 `##` 章節；標「--help」者代表本檔目前只有旗標層說明或完全未展開，用法以 `ticket track <子命令> --help` 為準。子命令增減時本表可能落後，出現落差以 `ticket track --help` 現況為準。

| 子命令 | 一句話用途 | 章節 |
| --- | --- | --- |
| `claim` | 認領 Ticket | 〈UPDATE 操作〉 |
| `complete` | 標記完成 | 〈UPDATE 操作〉 |
| `finish` | `complete` 別名（worktree 派發避開 runtime guard 對 `complete` 的 basename 誤判） | 〈UPDATE 操作補充：commit 副作用與欄位語意〉 |
| `close` | 關閉 Ticket（已在其他 Ticket 一併解決） | --help |
| `set-closed-by` | 修正已 closed 票的 `closed_by` 欄位 | 〈UPDATE 操作補充：commit 副作用與欄位語意〉 |
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
| `add-acceptance` | 追加驗收條件 | --help |
| `remove-acceptance` | 移除驗收條件（按編號） | --help |
| `add-spawned` | 追加 `spawned_tickets` 項目 | 〈UPDATE 操作〉 |
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
| `fix-multi-view-status` | 覆寫 ANA Solution 的 `multi_view_status` 行值 | 〈UPDATE 操作補充：commit 副作用與欄位語意〉 |
| `register-artifact` | 登記實驗器材至 Solution 章節 | 〈track register-artifact / resolve-artifact / list-artifacts 子命令〉 |
| `resolve-artifact` | 標記實驗器材狀態為 removed/kept | 〈track register-artifact / resolve-artifact / list-artifacts 子命令〉 |
| `list-artifacts` | 列出 ticket 已登記的實驗器材 | 〈track register-artifact / resolve-artifact / list-artifacts 子命令〉 |
| `set-exit-status` | 設定 Exit Status 章節（CLI 生成 fenced YAML） | 〈track set-exit-status 子命令〉 |
| `set-completion-info` | 設定 Completion Info 章節（CLI 生成格式） | --help |
| `accept-creation` | 標記 Ticket 建立後驗收已通過 | 〈UPDATE 操作〉 |
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

## READ 操作

```bash
# 快速摘要
/ticket track summary

# 查詢單一 Ticket
/ticket track query <id>

# 版本進度
/ticket track version 0.31.0

# 樹狀查詢
/ticket track tree <id>

# 代理人進度
/ticket track agent parsley

# 關聯鏈查詢
/ticket track chain <id>

# 完整內容
/ticket track full <id>

# 完整內容（show 為 full 的 alias，對齊 git/docker/kubectl 慣例；W17-008.2）
/ticket track show <id>

# 執行日誌（全部）
/ticket track log <id>

# 執行日誌（過濾單一 section，W17-008.3；對齊 append-log 介面）
# 範例：/ticket track log <id> --section "Solution"
# 可用 section：見 constants.CANONICAL_BODY_SECTIONS（與 append-log 同一份清單）
/ticket track log <id> --section "<Section Name>"

# 列出 Tickets（預設 --top 10 by priority；詳見「track list 子命令」）
/ticket track list [--pending|--in-progress|--completed|--blocked] \
                   [--wave <wave>] [--status STATUS [STATUS ...]] \
                   [--format {table,ids,yaml}] [--top N] [--all] \
                   [--version VERSION]

# Dashboard 聚合視圖（PM 接手新 session；詳見「track dashboard 子命令」）
/ticket track dashboard [--top N] [--wave N] [--no-stale] \
                        [--stale-threshold MIN] [--format {text,json}] \
                        [--version V]

# 看板視圖（樹狀未完成任務總覽）
/ticket track board [--wave <wave>] [--all]

# Scheduler 排程視圖（可執行清單 / DAG / 關鍵路徑）
/ticket track runqueue [--format={list|dag|critical-path}] [--top N] [--context=resume] [--wave N]

# 5W1H 單欄位查詢
/ticket track who|what|when|where|why|how <id>

# 衍生關係查詢（spawned_tickets + source_ticket；詳見「track deps / depth 子命令」）
/ticket track deps <id>

# 嵌套深度查詢（沿 parent_id 鏈；詳見「track deps / depth 子命令」）
/ticket track depth <id>
```

## track runqueue 子命令（Scheduler）

**用途**：回答「下一個該做哪個 ticket」（Linux schedule() 類比）。合併原 next/schedule/resume-hint 三概念為單一命令。

**核心使用場景**：

| 場景                          | 命令                                                    | 輸出                                      |
| ----------------------------- | ------------------------------------------------------- | ----------------------------------------- |
| PM 迷失方向 / 新 session 接手 | `ticket track runqueue --wave N`                        | priority 排序的可執行清單（blockedBy=[]） |
| 查看完整依賴 DAG              | `ticket track runqueue --wave N --format=dag`           | 拓撲層級分組，關鍵路徑高亮                |
| 查看關鍵路徑節點              | `ticket track runqueue --wave N --format=critical-path` | slack=0 節點（CPM）                       |
| /clear 後接手（輔助／除錯入口，非首選） | `ticket track runqueue --context=resume --top 3`        | 與 handoff/pending 交集 top 3，含 exit_status tag；PM 實際接手流程以 `SKILL.md`〈無子命令時的預設行為（dashboard-first）〉為主，本命令與 `onboard` 同列為輔助/除錯查詢，兩支 SessionStart hook 會在用戶輸入前先印出此類提示作為歷史入口 |

**Exit Status tag（W17-031.1）**：`--context=resume` 模式下，list 視圖讀取 handoff JSON 的 `exit_status.status` 欄位，四類狀態以 `[<status>]` 取代 `blockedBy=[]` runnable 標記，避免 scheduler 誤把待補料 ticket 當可直接接手：

| Tag                 | 含義                              |
| ------------------- | --------------------------------- |
| `[needs_context]`   | agent 回報資料缺口，待 PM 補料     |
| `[blocked]`         | 環境/依賴阻塞，無法繼續           |
| `[failed]`          | 執行失敗                          |
| `[partial_success]` | 部分完成，剩餘子任務待跟進        |
| 無 tag（保留 `blockedBy=[]`） | success / 缺欄位 / 未知值（fail-open，相容舊 handoff JSON） |

**參數**：

| 參數               | 值域                                    | 語意                                             |
| ------------------ | --------------------------------------- | ------------------------------------------------ |
| `--format`         | `list`（預設）/ `dag` / `critical-path` | 輸出視圖                                         |
| `--top N`          | int                                     | 限制 N 筆（list / critical-path 有效，dag 忽略） |
| `--context=resume` | —                                       | 交集 `.claude/handoff/pending/`                  |
| `--wave N`         | int                                     | 過濾 wave                                        |
| `--groups`         | —                                        | 依 `where.files` 交集取貪婪極大獨立集，切分可並行集合與本輪未選入清單，**優先於 `--format`**（兩者同時給出時 `--groups` 生效渲染群組視圖，非互斥錯誤；`--top` 對 `--groups` 無效，同 `dag`） |

**`[RECLAIMABLE]` 標記（multi-PM 協調層 Phase 3）**：list 視圖逐票渲染時，若該票在 `pm-registry.json` 中已知無 FRESH session 佐證持有（`lease.is_lease_reclaimable` 輕量判準：持有者 heartbeat 逾 TTL，**或** registry 已載入但未追蹤此票 lease——含 graceful SessionEnd 釋放後 entry 已刪除的情形），於票號前加 `[RECLAIMABLE]`，可與 `[STALE]`（stale in_progress 判準，來源不同——見上方 Exit Status tag 段落與 stale-list 章節）並列疊加，兩者可各自獨立出現。`registry` 讀取本身降級（缺檔/損毀/schema 不合）時視同「無法判定」，不標記 `[RECLAIMABLE]`（與 registry 模組完全不可用同等處置，防止把 registry 讀取失敗誤標為可接手）。`[RECLAIMABLE]` 僅為候選提示，實際能否釋放需 `ticket track reclaim` 的 ghost 鑑識三查，詳見「track reclaim 子命令」章節「與 sessions/runqueue 顯示層判定的差異」。

**新 session 自動引導**：`session-start-scheduler-hint-hook.py` 在 SessionStart 時自動呼叫 `runqueue --context=resume --top 3`（若無 handoff 則 fallback `--format=list --top 1`），結果顯示為 hook additionalContext。

**`blockedBy=` 語意提醒（2026-08-24）**：輸出中的 `blockedBy=[...]` 與 ticket frontmatter 的 `blockedBy` 欄位同名，但值不同——輸出只列**尚未解除**的 blocker，blocker 一旦 completed/closed 就從清單移除；frontmatter 原值則保留宣告時的完整清單，不隨 blocker 狀態變動而改寫（見 `track_runqueue.py` 的 `_unresolved_blockers()`）。此為刻意設計：scheduler 只回答「此票現在能否接手」，混入已解除的 blocker 會誤導可執行性判斷。**做血緣或狀態對帳時（例如查證某票是否曾被阻擋、比對兩份資料是否一致）必須以 frontmatter 的 `blockedBy` 原值為準**——直接拿 `blockedBy=[]` 當作「此票從未被阻擋」會誤判血緣關係，或誤以為其中一份資料是壞資料。

### 排序規則（priority + spawned 加權）

**第一層：Priority tier 排序**

| Tier | 條件                 | 優先度   |
| ---- | -------------------- | -------- |
| L0   | priority=P0          | 最優先   |
| L1   | priority=P1          | 次之     |
| L2   | priority=P2          | 再次之   |
| L3   | priority=P3 或未指定 | 最低     |

**第二層：CLI 未實作，PM 手動判斷**：同 tier 內若有 `source_ticket` 存在且該 source ANA 已 `completed` 的衍生票，建議手動優先接手——`track_runqueue.py` 未實作此排序（`spawned` 關鍵字零命中），`track runqueue` 實際輸出僅套用第一層 Priority tier 排序。規則面設計細節見下方〈實作現況〉表。

**第三層：依存關係過濾**

`runqueue` 僅列出 `blockedBy=[]` 的 ticket（可執行清單）。被阻塞的 ticket 在 `--format=dag` 可見，在 `--format=list`（預設）不顯示。

### Wave 完成判定與 spawned 清點

Wave 完成判定規則（Checkpoint 2 情境 C 前置條件）：

1. 當前 Wave 無 `pending` / `in_progress` ticket
2. **本 Wave 已 completed ANA 的 `spawned_tickets` 皆非 `pending`**（W17-037 落地）

兩條件均滿足才算 Wave 完成。詳見 `.claude/pm-rules/completion-checkpoint-rules.md` 第八層 Checkpoint 2 情境 C。

### `--groups` 並行群組切分（multi-PM 協調層 Phase 3）

**用法**：跑 `ticket track runqueue --wave N --groups` → 讀輸出三段（可並行群組／本輪未選入／施工中佔用節點，後者僅在有相關 in_progress 票時出現）→ 認領可並行群組內的票 → 本批認領後可重跑（見下方安全性條件）。

```bash
ticket track runqueue --wave 3 --groups
```

輸出格式：

```
=== Parallel Groups ===
可並行群組（4 票，兩兩無交集）：
  - 0.2.1-W3-100
  - 0.2.1-W3-101
  - 0.2.1-W3-102
  - 0.2.1-W3-200

本輪未選入可並行集合（1 票）：
  - 0.2.1-W3-201

衝突對（1 組）：
  0.2.1-W3-200 <-> 0.2.1-W3-201 [heuristic]: test/domain/foo_test.dart  <!-- skill-residue-exempt: 命令輸出範例的示意路徑，非本專案實際檔案 -->
```

（此範例由 `file_conflict.compute_parallel_groups` / `render_groups` 對 5 票示意輸入實際執行取得，第一票與第二票因 impl→test 啟發式命中而衝突，貪婪走訪依輸入序先選入第一票，故其落在可並行群組、第二票落在本輪未選入。）  <!-- rule8-exempt: illustration:命令輸出範例的示意 ID 說明文字 -->

`[heuristic]` 標記代表該衝突僅由 impl→test 擴張啟發式衍生路徑觸發（票面原始宣告的 `where.files` 本身無交集），語意與〈track conflicts 子命令〉〈判定規則〉的 `[heuristic]` 相同。

若查詢當下存在 live in_progress 票且其衝突邊確實排除了某個鄰居，輸出會於「本輪未選入」之後插入「施工中佔用節點」段（僅列出「確實排除了某鄰居」的 in_progress 票，0 衝突邊的 in_progress 票不列，避免雜訊）：

```
=== Parallel Groups ===
可並行群組（3 票，兩兩無交集）：
  - 0.2.1-W3-100
  - 0.2.1-W3-101
  - 0.2.1-W3-102

本輪未選入可並行集合（1 票）：
  - 0.2.1-W3-200

施工中佔用節點（1 票，in_progress 且非stale，僅提供衝突邊排除鄰居，不參與選取）：
  - 0.2.1-W3-201

衝突對（1 組）：
  0.2.1-W3-200 <-> 0.2.1-W3-201: lib/domain/qux.dart, test/domain/qux_test.dart  <!-- skill-residue-exempt: 命令輸出範例的示意路徑，非本專案實際檔案 -->
```

（此範例對前例追加一張 live in_progress 票 `0.2.1-W3-201`，其宣告與 `0.2.1-W3-200` 交集；同樣以 `file_conflict.compute_parallel_groups` / `render_groups` 直接呼叫取得逐字輸出。`0.2.1-W3-201` 的衝突邊排除了 `0.2.1-W3-200`，使其落在「本輪未選入」；`0.2.1-W3-201` 本身不出現於「可並行群組」或「本輪未選入」，改列於「施工中佔用節點」。）  <!-- rule8-exempt: illustration:命令輸出範例的示意 ID 說明文字 -->

**Why**：連通分量整塊視為必須序列化是過度保守判定——傳遞關聯不代表互斥，只有直接衝突的節點對才不能同時進行。**Consequence**：「本輪未選入」不是佇列、系統不代為排入下一輪，未選入不代表彼此須序列，只是與本批已選票有直接衝突。**Action**：本批票認領後可重跑 `ticket track runqueue --groups`——認領後的票轉為 in_progress，下一輪衝突圖會將其納為 seed，其衝突邊不隨狀態轉換消失，不會被誤選為可並行（適用條件見下方安全性條件）。

> **多輪重跑的安全性條件**：上述「認領後重跑」的保護僅在**經 `--groups` 查詢**時成立——`track_runqueue.py` 每次 `--groups` 呼叫都重新篩出全部 live in_progress 票並傳入 seed，條件是「決定下一批認領前有跑過 `--groups`」，不是任何形式的認領都自動安全。以下兩種情境不在此保護範圍內，`--groups` 的衝突圖無法涵蓋：
>
> 1. **不經 `--groups` 的手動 `claim`**：直接對某張票下 `ticket track claim` 不會查詢衝突圖。此路徑改由 `lease` 層的自撞警告承接——同一 session 兩輪之間 claim 撞上自己已佔用的檔案會輸出警告，但警告不阻擋 claim，仍需讀者自行判斷是否停手。
> 2. **ANA 型票的宣告預設不貢獻衝突邊**：`where.files` 依 `type` 推導預設意圖，ANA 型票預設為 `read`，衝突判定僅比對 `write` 集合，`read` 集合不建邊。實測顯示約 19.3%（57 個 ANA 宣告樣本中 11 個）的 ANA 宣告實際仍會寫入其宣告的檔案；這部分票即使已在 in_progress，也不會出現在 `--groups` 的衝突圖中，屬已知假陰性，不因本次修復而消失。type 預設意圖完整表見 `field-semantics.md`〈where.files 宣告語意〉。
>
> 落在上述兩種情境時，仍建議以 `ticket track conflicts` 自行核對新選出的票與 in_progress 票之間有無 `where.files` 交集。

#### 判定機制

輸入集合與 `list` 視圖同（`blockedBy=[]` 的 pending 票，同一份 priority 排序結果），對此集合依 `where.files` 交集建無向衝突圖：節點為票 id，邊為兩兩交集命中（判定邏輯與 `track conflicts` 共用 `compute_pairwise_conflicts`，含 impl→test 擴張啟發式）。對全體節點依輸入序做單次全域貪婪極大獨立集走訪：逐一檢視節點，若尚未被先前選中節點的鄰居排除即選入「可並行群組」並排除其所有鄰居；孤立節點（度數為 0）必定入選。未被選入的節點歸入「本輪未選入」清單——僅代表與本批已選票有直接衝突邊，不代表這些節點彼此之間也必須序列，即使兩者在衝突圖上經由第三個節點傳遞關聯（A-B 有邊、B-C 有邊、A-C 無邊時，A 與 C 仍可能同時入選可並行群組）。

Live in_progress 票（非 stale，`staleness.is_live_occupied` 判準）以 seed 身份併入同一張衝突圖：其衝突邊在後續輪次仍然存在，使與其有 `where.files` 交集的鄰居於貪婪走訪時被排除；in_progress 票本身不出現於「可並行群組」或「本輪未選入」清單，若其衝突邊確實排除了某個鄰居，改於輸出第三段「施工中佔用節點」列出（見上方輸出格式範例）。Stale in_progress 票（session 已中斷或逾時）不納入 seed，維持可被視為未佔用，與〈track stale-list 子命令〉「stale in-progress 章節」段的 24h 判準（`is_stale_in_progress`）一致，避免同一票在 `list` 視圖顯示可接手、在 `--groups` 視圖卻擋住鄰居的矛盾指引。

### 實作現況

| 層                             | 狀態                                         | 檔案                                                             |
| ------------------------------ | -------------------------------------------- | ---------------------------------------------------------------- |
| 規則面（本章節）               | 已落地                                       | `.claude/skills/ticket/references/track-command.md`（W17-040）   |
| Wave 完成判定                  | 已落地                                       | `.claude/pm-rules/completion-checkpoint-rules.md` L76（W17-037） |
| CLI 排序邏輯（第二層加權實作） | 未實作（若未來發現序列差異造成問題再建 IMP） | `.claude/skills/ticket/ticket_system/commands/track_runqueue.py` |

第二層加權項 `spawned_from_completed_ana`（`source_ticket` 存在且該 source ANA status=completed → 排在同 tier 其他 ticket 前面）來源 W17-036 軸 C 分析。**Why**: ANA 結論已產出的衍生 IMP 推進急迫性高於一般 pending —— source ANA 已結案代表分析完成、結論等待落地；若與其他同 priority pending 同等對待會造成結論擱置（PC-075 下游傳播防護；詳見 `.claude/error-patterns/process-compliance/PC-075-spawned-children-status-check-asymmetric.md`）。實作沿革（W17-011.1 基礎 runqueue、W17-009 ANA 三視角審查收斂結論、W17-036 軸 C 補強）見 `CHANGELOG.md`。

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

# 追加執行日誌
# 有效 section: 見 constants.CANONICAL_BODY_SECTIONS（Task Summary / Problem Analysis /
#   重現實驗結果 / Solution / Test Results / Context Bundle / NeedsContext / Exit Status /
#   Spawn Requests / Completion Info）。"Execution Log" 是 H1 容器標題，不是合法值
# Status precondition（W3-044 / W1-058）：需 status=in_progress；completed 票不分 section 一律放行（補寫審查後回饋用途，execute_append_log 對此命令無條件傳入 allow_completed=True）；
# 派發前章節 Problem Analysis / Context Bundle 例外允許 pending 直寫（PM bookkeeping，不需 --force）
/ticket track append-log <id> --section "Problem Analysis" "內容"
/ticket track append-log <id> --section "Context Bundle" "PCB 內容（派發前分析結果，PC-040）"
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

# 設定相關關係（relatedTo 欄位）
/ticket track set-related-to <id> <related-id>         # 覆寫（設定單一 relatedTo）
/ticket track set-related-to <id> <id2> --add          # 追加（去重）
/ticket track set-related-to <id> <id2> --remove       # 移除指定 relatedTo
/ticket track set-related-to <id> "<id2> <id3>" --add  # 一次追加多個：value 是單一位置參數，須引號包成一個字串（否則 argparse 報 unrecognized arguments）

# 驗證 frontmatter 合規性
/ticket track validate <id>                            # 檢查 status/completed_at/acceptance/who 4 欄位

# 標記建立後驗收已通過
/ticket track accept-creation <id>

# 執行驗收檢查
/ticket track audit <id>

# 批量操作
/ticket track batch-claim "id1,id2,id3"
/ticket track batch-complete "id1,id2,id3"

# 追加 spawned_tickets（支援單 ID / 多 ID，對齊 Unix 慣例如 rm a b c）
/ticket track add-spawned <id> <spawned-id>                    # 單一 ID
/ticket track add-spawned <id> <spawned-1> <spawned-2> <s-3>   # 多 ID 空白分隔（W17-008.1）
# 重複 ID 會自動去重並列入「已存在略過」
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

`complete` 通過上表全部檢查後，自動以隔離索引提交本票 md + 主 worklog index，另有三項不在上表、但直接影響提交結果的副作用語意：**排除 children/siblings**（隔離索引僅收本票與 worklog 路徑，不夾帶他票尚未 commit 的 WIP 內容）、**不留 staged 殘留於共用 index**（全程走隔離索引，共用 index 提交前後狀態不變，非「先 add 進共用 index 再 commit」）、**成功時 stdout 印出 commit SHA**（`[OK] 已提交 <sha>` 格式，供呼叫端核對是否真正落地，見下方 `track commit` 子命令「Exit code」表的同款判讀原則）。

### complete 副作用：ticket metadata 與程式碼變更恆分兩個 commit

`complete` 在父 ticket 含未完成 children（非 terminal：pending / in_progress / blocked）時會以 exit 1 阻擋。提供 `--force` 旁路強制完成，會在 stderr 列出未完成 children 作為警告，cascade 解鎖機制仍會執行。建議優先完成 children 後再 complete 父 ticket。

`complete` 的自動提交於呼叫當下以隔離索引提交 ticket metadata（本票 md + 主 worklog），而非留待 PM 事後核對共用 index 手動 commit。**Why**：提交時機從「人工事後裸 commit」改為「CLI 呼叫當下自動提交」，是為了根除過期 index 快照被誤 commit 進 HEAD 的風險。**Consequence**：ticket metadata 與對應的程式碼變更**必然分屬兩個 commit**——單靠 `git log --grep <票號>` 只會命中 metadata commit（`chore(<id>): complete` / `chore(<id>): append-log ...`），不含實作變更；依「一票一 commit」假設做追溯的下游流程（含 sync 本框架的其他 consumer 專案）須知情此語意，否則會誤判追溯不完整或漏算變更範圍。**Action**：追溯某票完整變更時，搜尋範圍須同時涵蓋 metadata commit 與程式碼 commit（可用票號關鍵字掃兩者的 commit message，或查詢 ticket body 的 Test Results / Completion Info 章節記錄的程式碼 commit SHA）。

### `--no-stage` 的覆蓋範圍

`--no-stage` 會完整跳過本次 auto-commit（metadata 與 worklog 兩者皆跳過），ticket md 停留在 working tree 的未提交、未 staged 狀態，不產生任何 metadata commit。**Action**：想讓 ticket metadata 與程式碼變更合併成單一 commit 時，`--no-stage` 已足夠覆蓋——先完成程式碼變更，`complete <id> --no-stage` 後 ticket md 仍是未提交的工作區變更，可與程式碼檔案一併 `git add` 後裸 commit（無 pathspec / `--only` / `-o` / `-a`，見 `.claude/rules/core/bash-tool-usage-rules.md` 規則七）。**Consequence**：選擇 `--no-stage` 等於放棄自動提交機制帶來的「不留未提交 metadata」保護，working tree 中的 ticket md 變更在手動 commit 之前仍可能被 `git checkout --`／`git reset --hard`／`git stash` 覆蓋回舊版本（與「Spawn Requests」章節「繞道手改會失去 auto-commit 保護」同類風險），故僅建議在確定會立即手動 commit 時使用。

### `title` 與 `what` 是兩個獨立欄位，`set-what` 刻意不同步 `title`

`title` 是清單顯示用的短標籤（dashboard / runqueue 顯示的是它），`what` 是完整任務敘述（可含檔案清單、括號補充）；兩者常刻意不同（量測見 `CHANGELOG.md`）。票的範圍事後縮小時（如依上游評估結論移除 acceptance），**兩個欄位都要更新**——只改 `what` 會讓清單上的 `title` 繼續以舊範圍誤導接手者。更新用 `set-title <id> <value>`。

### 其餘 frontmatter 欄位若無對應命令，不要手動編輯

`ticket-file-access-guard-hook` 會以 exit 2 阻擋直接編輯 frontmatter，繞道不可行。找不到對應命令代表該欄位缺少合法更新途徑（PC-BAL-047），應建 ticket 回報補上命令。

### closed 票欄位修正 — `set-closed-by`

`close` 對已 closed 票拒絕覆寫既有值；`set-closed-by <id> --value <ticket-id>` 補上 `closed_by` 填錯後的合法修正路徑，取代直接 Edit ticket md（該路徑被 `ticket-file-access-guard-hook` 阻擋）。

```bash
ticket track set-closed-by <id> --value <ticket-id>
```

僅適用 `status=closed` 的票；`--value` 須為合法且存在的 Ticket ID，格式錯誤或指向不存在的 Ticket 皆拒絕。修正動作輸出舊值與新值並走 auto-commit。

### 身份申報（`--as`）判定邏輯

`complete` / `check-acceptance` / `set-acceptance` 三個寫入命令支援選用 `--as <agent-name>`，與 ticket `who.current` 精確對照。**Why**：防 generic agent 收 Ticket ID 即越權收尾（PC-V1-002 前提一，探針實證）。**判定邏輯**：`--as` 值 ≠ `who.current`（含空值）→ deny（exit 1，純前置檢查不寫入狀態）；`--as rosemary-project-manager` 一律放行（PM bookkeeping 豁免，如代收尾 / stale cleanup）；未提供 `--as` 時 `complete`（`finish` 別名同列）已轉強制 deny，`check-acceptance` / `set-acceptance` 仍維持 warn-only（僅輸出 stderr 訊息，不阻擋；過渡期設計，見 `identity_guard.py` 的 `ENFORCED_COMMANDS`）。**Action**：subagent 收尾時帶自身身份，例 `ticket track complete <id> --as thyme-python-developer`；其餘 warn-only 命令轉強制的結束條件與偵測承擔者已明訂（7 日滾動 warn 率 < 5% 且樣本數 >= 30，由 PM 於 `version-release` 發布前檢查階段執行 `identity_guard_adoption.py` 判定），非待評估的無 trigger 狀態。

**接手者收尾身份**（SKILL.md〈dashboard-first〉步驟 1「無標記 in_progress 任務」情境——票已 `in_progress`、非新 `claim`，接手者不必然是 `who.current` 原持有者）：維持原 `who.current` 不變逕行 `complete --as <self>` 會因情境 4（`--as` 與 `who.current` 不符）被 deny。**Action**：PM 前台接手裸 `/ticket` 用 `--as rosemary-project-manager` 走情境 2 豁免收尾；代理人接手（非原 `who.current` 者）須先 `ticket track set-who <id> --current <self>` 把 `who.current` 改為自身（`set-who` 不在 `ENFORCED_COMMANDS`，不受本節 `--as` 檢查），再以 `--as <self>` 收尾走情境 3 對稱通過。`set-who` 只覆寫 `who.current` 子欄位、不動 `who.history`（見 `execute_set_who`），接手事實須自行於 Solution 或 append-log 記一行「接手自 <原 who.current>」留痕，否則身份轉移在 `who.history` 上無痕跡。

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
| 接手既有 in_progress 票（非新 claim，dashboard-first「無標記 in_progress」情境） | 代理人：`ticket track set-who <id> --current <self>` 後 `complete --as <self>`；PM：直接 `--as rosemary-project-manager` | 見上方「接手者收尾身份」；`set-who` 不動 `who.history`，須自行記接手留痕 |

### 補標記 — `add-exempt-marker`

`append-log` 預設追加，`--replace` 可整段覆寫但會連同原文字一併取代（不可逆，執行前印摘要供核對），不適合只補一行 marker——該區段不在 `ticket-file-access-guard-hook` 白名單內故 Edit 工具被拒，兩者疊加使 `PC-093-exempt` 這類行級標記無法在不動原文的前提下事後補上。`add-exempt-marker` 補這條路，且**僅追加獨立標記行、不修改原文字**：

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

`files` 必須落在該 ticket `where.files`（寫入意圖，即無 `::read` 標記或帶 `::write` 標記的路徑）宣告範圍內；任一項超出範圍即拒絕整批提交，並列出超出項與宣告範圍供核對。目錄型宣告（結尾 `/` 或指向既有目錄）會展開為該目錄下實際變更（`git status --porcelain`）的具體檔案再提交。ANA 型票 `where.files` 預設全唯讀，`write_files()` 恆回空集合；需要寫入的路徑須額外標 `::write`。`::read`／`::write` 後綴語法與 type 預設意圖的完整規則見 `field-semantics.md`〈where.files 宣告語意〉。

**目錄展開的並行過濾**：展開時另讀取 `.claude/dispatch-active.json`，凡命中其他活躍派發（`ticket_id` 不同於本票）宣告路徑的變更檔一律排除，避免並行環境下把他 session 的變更一併吸入本次目錄展開（本票或無人宣告皆保留，僅排除已知歸屬他票者）。此過濾為並行防護的加強層，非安全邊界本身——安全邊界仍是上段的 `where.files` 子集檢查；registry 讀取失敗（檔案不存在／JSON 格式錯誤）視為無其他派發，fail-open 不擋下正常提交。

**同檔邊界（隔離索引不防同檔內容夾帶）**：上述並行過濾與 `where.files` 子集檢查防的是「誤觸他票宣告路徑之外的檔案」；當兩票 `where.files` 都宣告**同一檔案**時，兩者皆不提供保護。隔離索引（`git_ops.commit_files_isolated`）只隔離「不觸碰共用 git index」，`git add -- <path>` 取用的仍是該檔案當下的工作區內容——先提交者會把他票尚未提交的同檔編輯整檔一併寫入本次 commit。此邊界與 `.claude/rules/core/bash-tool-usage-rules.md` 規則七「核對步驟的粒度邊界（檔案內夾帶）」同根因：`git add` 的最小可定址單位是整個檔案，無法區分「誰寫的哪一行」；該條文原僅論及裸 commit 的核對步驟，本命令的隔離索引提交同樣適用（配方步驟見 `.claude/references/bash-tool-usage-details.md`「隔離索引提交」步驟 4）。**偵測**：提交後以 `git show <sha>:<path>` 對照自己實際編輯的內容範圍，出現非自己寫入的變更即為夾帶。**處置**：依上方 Commit 規範不 revert / reset / amend，記錄 commit SHA 與受影響檔案回報 PM。**Action**：兩票 `where.files` 宣告同一檔案時必須序列化，不因改用本命令而豁免；派發前以 `ticket track conflicts --for <本票>` 確認無其他 in_progress 票宣告該檔（見 `.claude/pm-rules/parallel-dispatch.md`「派發前 where.files 交集檢查」）。

### `--worktree` 條件

判斷條件是**呼叫 `ticket track commit` 當下 CLI process 的 cwd**；「檔案變更所在位置」不是判斷條件：未帶 `--worktree` 時，repo root 解析為 `resolve_project_cwd()` 所屬 repo，即 process cwd 所在的 repo（ticket shim 慣例於主 repo cwd 執行，故此路徑恆解析為主 repo）；帶 `--worktree <絕對路徑>` 時改以該路徑對應的 git repo root 為準（見 `track_commit.py:_resolve_repo_root` docstring）。**Consequence**：子代理人每次 Bash 呼叫的 cwd 依 harness 慣例重設回主倉庫，即使變更檔案實際存在於 linked worktree 內，只要呼叫當下 cwd 不在該 worktree，未帶 `--worktree` 就會綁定主 repo working tree 執行 git 操作——新檔案無法 `add`（不在主 repo working tree 認知範圍）、已修改檔案因主 repo 版本未變而誤判為空 tree 短路（見下方 Exit code 表）。**Action**：cwd 是否在目標 worktree 內不確定時，一律帶 `--worktree`；三種情境須逐一判斷（agent cwd 在 worktree 內／agent cwd 在主倉庫／PM cwd 被 runtime 切進 worktree，第三種見 `.claude/skills/worktree/references/agent-isolation-worktree.md`〈EnterWorktree mid-session 切換〉），檔案位置本身不足以推論是否需要此旗標。

### 與 append-log／complete auto-commit 的關係

本命令、`append-log`（每次寫入自動 commit ticket md）、`complete`（自動以隔離索引 commit ticket metadata）是三條互不重疊的 commit 路徑——本命令提交程式碼變更，另兩者提交 ticket 狀態，三者恆分屬不同 commit（見上方「complete 副作用」節）。

### Fallback 條件

僅當本命令因故失敗或不可用時，才降級為「精確 `git add` + `git diff --cached --name-only` 核對 + 裸 `git commit`」（無 pathspec / `--only` / `-o` / `-a`），見 `.claude/rules/core/bash-tool-usage-rules.md` 規則七。本命令走隔離索引、全程不觸碰共用 index，是本框架消除「共用 index 被反覆吸入他票內容」風險的權威路徑，非 fallback 的替代品，不因方便而優先選 fallback。**並行度註記**：fallback 一旦選用即回到共用 index，`append-log`／`complete` 的隔離索引 CAS 可能已在同一視窗把 HEAD 往前推進，使 fallback 前已 `git add` 的 entry 相對新 HEAD 過期；裸 commit 前須先比對 `git show :<path>` 與 `git show HEAD:<path>`，判定過期則 `git restore --staged <path>` 後重新 add，見 `.claude/rules/core/bash-tool-usage-rules.md` 規則七「版本邊界（過期 index 快照）」。

### Exit code

| 值 | 說明 |
|----|------|
| 0 | commit 成功，或檔案內容與 HEAD 相同（空 tree 短路，視為成功） |
| 1 | ticket 不存在／`where.files` 未宣告寫入路徑／檔案超出宣告範圍／`--worktree` 非合法 git 目錄／提交失敗 |

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

> **實測來源**（W17-008.16 補完）：以下症狀欄為實際 CLI 輸出觀察結果。

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
| status                      | `claim` / `complete` / `release`                | 由生命週期命令管理，禁止手動編輯                     |
| tdd_phase                   | `phase <id> <phase> <agent>`                    | Phase 進度更新                                       |
| children                    | `add-child <parent> <child>`                    | 父子關係                                             |
| parent_id                   | `set-parent <child> <new-parent>\|--clear`      | 改寫或清除，自動同步上游 `children`（雙向一致性）    |
| acceptance                  | `check-acceptance` / `set-acceptance`           | 勾選/取消勾選用 `--check`/`--uncheck`/`--all-check`/`--all-uncheck`；新增/改文字/刪除條目用 `set-acceptance --add`/`--edit`/`--remove`（建票後修訂） |
| frontmatter 驗證            | `validate <id>`                                 | 檢查 status/completed_at/acceptance/who 4 欄位合規性 |
| blockedBy                   | `set-blocked-by <id> <value> [--add\|--remove]` | 建立時用 `--blocked-by`；之後用 CLI 更新             |
| relatedTo                   | `set-related-to <id> <value> [--add\|--remove]` | 建立時用 `--related-to`；之後用 CLI 更新             |
| title                       | `set-title <id> <value>`                        | 清單顯示用短標籤，與 `what` 刻意分離；範圍變更時兩者需個別更新（見「UPDATE 操作補充」章節） |
| priority                    | `set-priority <id> <value>`                     | value 限 `PRIORITY_LEVELS`（P0-P3）                  |
| closed_by                   | `set-closed-by <id> --value <ticket-id>`        | 僅 `status=closed` 適用，修正 close 時填錯的值        |
| dispatch_reason             | 無 CLI 命令                                     | 依上方「其餘 frontmatter 欄位若無對應命令，不要手動編輯」處置：不可手動編輯，應建 ticket 回報補上命令 |

**不存在的操作**（禁止嘗試）：

| 錯誤呼叫       | 正確做法                              |
| -------------- | ------------------------------------- |
| `set-status`   | 使用 `claim` / `complete` / `release` |

---

## track deps / depth 子命令

### deps — 顯示衍生關係

```bash
ticket track deps <ticket-id>
```

顯示衍生關係（`spawned_tickets` + `source_ticket`），與 `tree`/`chain` 純血緣語意（`parent_id`/`children`/`chain`）分離，對齊 Jira/Linear/GitHub 業界慣例。支援遞迴展開與循環引用防護（標記 `CYCLE DETECTED`）。

### depth — 計算嵌套深度

```bash
ticket track depth <ticket-id>
```

沿 `parent_id` 鏈計算嵌套深度（**非** ID 字串數點，避免完整版本前綴如 `<version>-W<wave>-<seq>.<sub>` 本身即含 3 個點，被誤算為 depth 4 的 fatal bug）。輸出 `depth` / `max_depth`（= `MAX_TICKET_DEPTH=3`）/ `can_descend`（`depth < MAX_TICKET_DEPTH`）。深度定義：根任務（`parent_id: null`）= depth 1，每往下一層 +1。用途：agent 自檢層級自覺（協議 v2 D3），無需上層 prompt 傳遞層級資訊。

> **與 frontmatter `chain.depth` 的基數差異**：本命令輸出的 `depth` 是即時沿 `parent_id` 鏈計算的動態值，根任務 = 1（1-based）。`ticket-lifecycle-details.md`〈chain 欄位說明〉的 frontmatter `chain.depth` 是建立當下依 ID 序號點數寫入的靜態快照，根任務 = 0（0-based），與本命令為同名不同來源的獨立量測值，不可互換代入（詳見該節注記）。`can_descend` 與 `MAX_TICKET_DEPTH` 比較一律以本命令輸出為準。

`create --parent <id>` 時，若新子任務深度 >= `MAX_TICKET_DEPTH`（3）會 emit warning（**不硬擋**，留旁路）。此為嵌套派發深度上限的 CLI 強制層，使協議深度上限不只是文件建議。

---

## track parallel-check 子命令

偵測目標 ticket 的 children（或同 parent 兄弟）pending 集合中，依 `where.files` 路徑前綴判斷哪些可平行派發、哪些互相衝突。

### 用法

```bash
ticket track parallel-check <id>   # 分析目標票的 children pending 集合
```

### 輸出

三章節：可平行派發 / 衝突任務 / 單獨派發。對「可平行集合中 >= 3 個觸及 `.claude/` 的 ticket」發出 PC-137 警告，輔助 PM 套用 `.claude/pm-rules/askuserquestion-rules.md` 規則 7。**此「3」為並行數計數閾值**，有實測依據：`PC-137` 記錄 3 並行 deny 3/3、4 並行 deny 4/4，對照非並行 18/18 成功，故限並行數 <= 2；與下方判定規則的「3」是不同來源、不同對象的獨立門檻，不可互相套用。

### 判定規則

路徑比較使用 `pathlib.PurePosixPath`（禁 string startswith）。共同祖先深度 >= 3 段視為弱衝突（如 `.claude/skills/ticket/` 級）。**此「3」為路徑深度閾值**（常數 `_SHARED_ANCESTOR_DEPTH`），為對齊模組粒度的經驗值（例：`.claude/skills/ticket/` 恰為 3 段），非統計推導；與上方〈輸出〉章節 PC-137 的並行數計數閾值各自獨立，兩者數值相同純屬巧合。

### Exit code

| 值 | 說明 |
|----|------|
| 0 | 分析成功 |
| 1 | ticket 不存在或無 pending children |
| 2 | ID 格式或 IO 錯誤 |

### 與 track conflicts 的差異

`parallel-check` 的輸入集合限定「目標票的 children 或同 parent 兄弟」，服務單一父票拆分後的子票批次派發決策；`track conflicts`（見「track conflicts 子命令」章節）的輸入集合是「任意 pending/in_progress 票」，服務更廣泛的跨票衝突偵測。兩者各自獨立判定路徑交集，不共用同一份候選集合來源。

---

## track board 子命令

提供樹狀看板視圖，視覺化展示各 Wave 的未完成任務分佈。

### 用法

```bash
# 顯示未完成任務看板（預設）
/ticket track board

# 指定版本
/ticket track board --version 0.31.0

# 只顯示特定 Wave
/ticket track board --wave 7

# 顯示所有任務（包含已完成）
/ticket track board --all

# 依主題分組排列
/ticket track board --group-by topic
```

### Flag 說明

| Flag         | 說明                                              |
| ------------ | ------------------------------------------------- |
| `--version`  | 版本號（自動偵測）                                |
| `--wave`     | 只顯示特定 Wave                                   |
| `--all`      | 顯示所有任務（包含已完成）                        |
| `--group-by` | 分組軸：`wave`（預設）或 `topic`                  |

### 分組軸：`--group-by`

`wave`（預設）為 Wave 分組加 ID 排序，輸出與本旗標引入前逐字相同（以測試斷言鎖定）。

選用對映：

| 需求 | 用命令 |
|------|--------|
| 只看單一主題的鏈 | `track topic` |
| 只要各主題票數與 status 分佈 | `track topics` |
| 一次看到所有主題內容、依內容決定先做哪個（如票數相同的兩個主題） | `board --group-by topic` |

`topic` 依主題分組，一次呈現全部主題連同其票，供「先選主題再選票」的派發決策使用。

`topic` 模式的呈現規則：

| 規則 | 行為 |
|------|------|
| 主題節標題 | `<主題名> (N tasks, 最高優先級=PX)`；無有效 priority 時以佔位字串代替 |
| 主題排序 | 第一鍵最高優先級（P0 最前，無有效 priority 排最後），第二鍵票數降冪 |
| 節內票行 | 沿用 Wave 分組的樹狀縮排與 `short_id [priority] title` 格式 |
| 未歸屬票 | 獨立一節 `未歸屬 (N tasks)` 置於全部主題節之後，不與任一主題混列 |

主題歸屬讀自 `lib/topic_assignments.list_assignments()`（append-only 中央清單，
非 ticket frontmatter 欄位）。未經 `create --topic` / `--new-topic` 指派或回填的票
一律落入未歸屬節。

## track audit 子命令

執行驗收檢查，產出結構化的驗收報告。

### 用法

```bash
# 對特定 Ticket 執行驗收檢查
/ticket track audit <ticket-id>
```

### 檢查內容

七個檢查步驟，逐項判定 pass/fail/skip（來源：`acceptance_auditor.py` `run_audit()`）：

| 檢查步驟 | 判定依據 → 結果 |
|---------|----------------|
| 結構完整性檢查 | 必填 frontmatter 欄位缺漏 → fail；否則 pass |
| 子任務完成狀態檢查 | `children` 遞迴檢查非 terminal 狀態 → fail；`children` 為空 → skip |
| spawned_tickets 完成狀態檢查（僅 ANA） | 非 ANA 類型 → skip；`spawned_tickets` 存在非 terminal 項 → fail |
| 執行日誌完整性檢查 | body 執行日誌含未填寫占位符 → fail |
| 驗收條件一致性檢查 | acceptance 與 Solution／Test Results 內容不一致 → warning（不擋 overall） |
| 含糊驗收條件偵測 | acceptance 文字命中模糊詞彙（如「完成」「正常」）→ warning |
| 後續任務銜接檢查 | 應有後續任務銜接但未偵測到 → warning；不適用情境 → skip |

整體判定：任一步驟 `passed=False` 且非 skip → overall FAIL；僅有 warning 無 FAIL → PASS_WITH_WARNINGS。

---

> `lib/messages.py` 統一錯誤訊息格式（Legacy／結構化 Envelope 兩路徑、`__error_envelope_v1__` 版本標記與 hook 端跳過機制）與 CLI 錯誤分類（業務錯誤 vs 純語法錯誤）的完整說明已移出本檔——讀者是改 CLI 的開發者，不是執行 `track` 的 PM。業務錯誤會以 `[Error] __error_envelope_v1__` 多行結構輸出、純語法錯誤走 argparse 預設 usage；完整說明見 `references/architecture.md`〈共用模組設計〉### messages.py。

---

## track stale-list 子命令

> 來源：W17-200

列舉 pending 且建立日期超過閾值的 ticket 明細，補 `list` 命令僅顯示彙總計數而無法定位個別 stale ticket 的缺口。

**stale in-progress 章節**（1.5.0-W5-005.7）：table 格式在 pending 表格後追加 stale in_progress 明細——依 frontmatter `started_at` 單平面判定（閾值 `STALE_IN_PROGRESS_HOURS` = 24h，與 runqueue `[STALE]` tag 同源 `is_stale_in_progress`），附 `ticket track release <id>` 釋放提示。`ids` / `yaml` 格式維持 pending-only（pipe 消費者如 `xargs close` 預期 pending 集合，混入 in_progress 會誤傷）。與 `subagent-stop-dispatch-cleanup-hook` 職責分離：hook 在 SubagentStop 事件清理 dispatch-active.json 記錄平面；本命令於查詢時呈現 ticket 世界平面滯留狀態，兩者互不重疊、皆不自動 release。

### 用法

```bash
ticket track stale-list [--threshold {info,warning,critical,all}] \
                        [--wave N] [--version V] [--all] \
                        [--format {table,ids,yaml}]
```

### Flag 說明

| Flag | 預設 | 說明 |
|------|------|------|
| `--threshold` | `warning` | `warning`=warning+critical / `info`=三級 / `all`=同 info / `critical`=僅 critical |
| `--wave` | None | 僅列出指定 wave |
| `--version` | None | 指定版本（覆蓋自動偵測 active 版本） |
| `--all` | — | 見〈共用旗標語意（track 系列命令通用）〉 |
| `--format` | `table` | `table` / `ids`（每行一個 ID，適合 pipe） / `yaml` |

### 閾值定義

複用 `lib/staleness.py` 常數（依 frontmatter `created` 計算）：

| 等級 | 天數 |
|------|------|
| info | >= 7 天 |
| warning | >= 14 天 |
| critical | >= 30 天 |

### 輸出格式（table）

```
------------------------------------------------------------
Stale pending tickets (threshold=warning)
------------------------------------------------------------
0.18.0-W17-AAA | [critical] | 45 天 | 標題 A
0.18.0-W17-BBB | [warning]  | 15 天 | 標題 B
```

依 days 降序排序；無符合條件時輸出「（無符合條件的 stale ticket）」。

存在 >= 24h 的 in_progress 票時追加章節（依經過分鐘數降序）：

```
------------------------------------------------------------
Stale in-progress tickets (>= 24h, 依 frontmatter started_at)
------------------------------------------------------------
0.18.0-W17-CCC | in_progress 31h | agent=thyme-python-developer | 標題 C
   提示：確認對照 agent 已終止後，以 `ticket track release <id>` 釋放；進行中 agent 勿用
```

### 範例

```bash
# 預設：列出 warning + critical
ticket track stale-list

# 含 info 級
ticket track stale-list --threshold info

# 只看 critical（>= 30 天）
ticket track stale-list --threshold critical

# 拿 ID 串接其他命令
ticket track stale-list --threshold critical --format ids | xargs -I{} ticket track show {}
```

### 設計約束

- 僅列 `status=pending` ticket（in_progress 走 `is_stale_in_progress` 已由 runqueue 涵蓋）
- version-agnostic：見〈共用旗標語意（track 系列命令通用）〉
- 復用 `calculate_stale_level`，不重定義閾值或判定邏輯

---

## track stuck-anas 子命令

> 來源：W17-008.15 方案 D 第 1 項

掃描 `type=ANA` 且 `status=in_progress` 且**全部** `spawned_tickets` 已 terminal（completed 等）的 ticket，協助 PM 識別「衍生子任務全完成但 source ANA 未 complete」的卡住情境——ANA 分析已產出結論並拆出後續 ticket，但 ANA 本身忘記 complete，會使依賴其 completed 狀態的下游判定（如 runqueue 排序加權、Wave 完成判定）誤判。

### 用法

```bash
ticket track stuck-anas [--wave N] [--version V] [--all]
```

### Flag 說明

| Flag | 預設 | 說明 |
|------|------|------|
| `--wave` | None | 僅列出指定 wave 的 ANA |
| `--version` | None | 指定版本（覆蓋自動偵測 active 版本） |
| `--all` | — | 見〈共用旗標語意（track 系列命令通用）〉 |

### 判定規則

1. ticket `type == "ANA"` 且 `status == in_progress`
2. 落地路徑有兩個欄位：`spawned_tickets`（`create --source-ticket`）與 `children`（`create --parent`），各自可為空；兩者皆空 → 不視為卡住（避免誤報剛派發、尚無任何落地物的票）
3. 至少一個路徑非空時，所有非空路徑都必須「全部存在於 ticket 索引中，且狀態皆為 terminal」才視為卡住；任一路徑有 ID 找不到對應票或非 terminal，即不列入（採聯集全 terminal，優先避免誤報而非避免漏報）

### 輸出格式

```
────────────────────────────────────────────────────────────
卡住的 ANA（in_progress 且落地路徑全 completed）
────────────────────────────────────────────────────────────
  1. 0.2.1-W3-050  分析 XXX 根因
      spawned=3 全 completed → 可考慮 ticket track complete 0.2.1-W3-050
```

無符合條件時輸出「（無卡住的 ANA）」，與 `activity`/`conflicts`/`onboard`/`stale-list` 同款空狀態字面樣式（見「空狀態字面規範」章節）。

### Exit code

固定回傳 `0`（純查詢，無業務拒絕或錯誤分支）。

### 設計約束

- version-agnostic：見〈共用旗標語意（track 系列命令通用）〉
- 復用 `ticket_loader.list_tickets` / `get_active_versions`
- 僅提示「可考慮 complete」，不自動執行——是否真正卡住（vs 刻意保留分析未結案）由 PM 判斷；**判準**：依 `.claude/rules/core/quality-baseline.md` 規則 5 與 `.claude/pm-rules/ticket-body-schema.md`〈Spawn 落地確認〉——Solution 已有明確結論、且規劃的 spawn 項目已全數建票或登記終態（`resolve-spawn-request`）時應 complete；若 Solution 結論未定，或仍有 spawn 規劃停留 pending 未落地，應保留 `in_progress` 並在 Solution 註明保留理由，不因本命令的提示逕自 complete

---

## track dashboard 子命令

> 來源：W10-114 / W10-113 M1+M4'

PM 接手新 session 的聚合視圖。一次回傳 `[In Progress]` / `[Handoff Target]` / `[Ready Top N]` / `[Stale Warning]` 四區塊，Ready 區塊含可直接 claim 的編號（`[1]` `[2]` `[3]`），免拼 ID 即可 claim。

**`[In Progress]` 條目的 lease 狀態標記**（判準同 registry heartbeat，TTL 固定 30 分鐘、來源 `.claude/lib/pm_registry.py` `STALE_THRESHOLD_MINUTES`，見「track sessions 子命令」〈欄位定義〉與下方〈滯留判準閾值總表〉）：`[LIVE]` = FRESH session 正在處理，`[RECLAIMABLE]` = 已知無 FRESH session 佐證持有（可能已 STALE，也可能 registry 根本未追蹤此票——含 graceful SessionEnd 釋放後 entry 已刪除的情形，兩者現統一標記，皆須走 `track reclaim` 鑑識判定），無標記 = registry 本身不可用（模組載入失敗 / 非 git 環境 / 讀取降級），無法判定。`[LIVE]` 票不應列入接手選項——活躍 session 正在處理，接手即與其重複處理同一張票（framework issue tarrragon/claude#78）。`[RECLAIMABLE]` 標記與 `list` 視圖〈`[RECLAIMABLE]` 標記〉章節、`track reclaim` 子命令共用同一判準（`lease.is_lease_reclaimable`），詳見「track reclaim 子命令」章節「與 sessions/runqueue 顯示層判定的差異」。

### 用法

```bash
ticket track dashboard [--top N] [--wave N] [--no-stale] \
                       [--stale-threshold MIN] [--format {text,json}] \
                       [--version V]
```

### Flag 說明

| Flag | 預設 | 說明 |
|------|------|------|
| `--top` | `5` | Ready 章節列數上限 |
| `--wave` | None | 過濾 wave 範圍（None=全部 wave） |
| `--no-stale` | False | 隱藏 `[Stale Warning]` 章節 |
| `--stale-threshold` | `60` | stale 判定門檻（**分鐘**；in_progress ticket 超過此時長視為 stale） |
| `--format` | `text` | `text`（預設，含編號顯示）/ `json`（自動化用） |
| `--version` | None | 指定版本（預設自動偵測 active 版本） |

### 輸出格式（text）

```
=== Dashboard (wave=all, version=0.18.0) ===

[In Progress] 1 ticket(s)
  - 0.18.0-W10-116  更新 ticket SKILL.md 補 format 可選值 list 預設行為 dashboard 命令說明  (started_at: 2026-05-13T09:32:20, agent: rosemary-project-manager) [LIVE]

[Handoff Target] 0 ticket(s)
  （無 handoff target）

[Ready Top 5]  priority 排序，可直接 claim
  [1] [P2] [ready] 0.18.0-W10-103  評估 7 個 .claude/ 可能違反規則 8 檔案
  [2] [P2] [ready] 0.18.0-W10-109  修補 proposal-evaluation-gate-hook
  [3] [P2] [ready] 0.18.0-W10-111  重啟 W10-030 設計評估
  [4] [P2] [ready] 0.18.0-W10-112  監測 ANA WRAP 執行落差
  [5] [P2] [ready] 0.18.0-W10-119  重構 track_dashboard 跨模組私有函式

[Stale Warning] 0 ticket(s) over 60min
  （無 stale ticket）

Hint: ticket track claim <id>
```

### 設計目的

Dashboard 將裸 `/ticket` 流程的 tool call 數降至 3 次（dashboard + claim by number + 後續動作），符合 `/ticket` 與 resume 系統「加速 PM 接手」的原始設計目的；量測細節（W10-113 ANA：原流程 7 個 tool call）見 `CHANGELOG.md`。

### 與其他視圖的差異

| 命令 | 視角 | 主要消費者 |
|------|------|-----------|
| `dashboard` | 整合（in_progress + handoff target + ready + stale） | PM 接手新 session（**首選**） |
| `runqueue` | 純可執行清單（blockedBy=[]） | 「下一個該做哪個」 scheduler 決策 |
| `list` | 通用 ticket 篩選 | grep / 自動化腳本 / 細部過濾 |
| `stale-list` | 純 stale 列舉（pending 依 created 天數） | stale ticket 清理批次 |

### 設計約束

- 內部複用 `track_runqueue` 的排序與 unblocked 判定（`_priority_rank` / `_is_unblocked_pending` / `_filter_by_wave` / `_compute_readiness`）
- stale 判定複用 `lib/staleness.is_stale_in_progress`（in_progress 分鐘粒度），與 `stale-list` 的 pending 天數粒度互補不衝突
- 編號 `[1] [2] [3]` 僅出現在 Ready 章節，避免與 in_progress 章節混淆

---

## track list 子命令

> 來源：W10-115 / W10-113 M3

通用 ticket 篩選命令。W10-115 起預設加入 `--top 10` 與 priority 排序，避免 dump 67+ 筆全量造成 PM 認知負擔。

### 用法

```bash
ticket track list [--pending|--in-progress|--completed|--blocked] \
                  [--wave <wave>] [--status STATUS [STATUS ...]] \
                  [--format {table,ids,yaml}] [--top N] [--all] \
                  [--version VERSION]
```

### Flag 說明

| Flag | 預設 | 說明 |
|------|------|------|
| `--pending` / `--in-progress` / `--completed` / `--blocked` | False | 單一狀態快捷篩選（互斥用法） |
| `--status` | None | 多狀態篩選（如 `--status pending in_progress`，等同 `--pending`+`--in-progress`） |
| `--wave` | None | 僅顯示指定 wave |
| `--format` | `table` | 三選值：`table`（人類閱讀）/ `ids`（每行一個 ID，適合 pipe 到 `xargs`）/ `yaml`（結構化資料） |
| `--top` | `10` | 限制最多 N 筆，依 `priority (P0 > P1 > P2 > P3) → created → id` 排序 |
| `--all` | False | 取全量（覆蓋 `--top`；與 `--top` 共存時 `--all` 優先並 emit warning） |
| `--version` | None | 指定版本（預設自動偵測 active） |

### 排序規則

W10-115 引入的預設排序：

| 順序 | 排序依據 | 規則 | 括號說明的性質 |
|------|---------|------|--------------|
| 1 | priority | P0 > P1 > P2 > P3 | fallback 規則：未指定 priority 視為 P3 |
| 2 | created | 同 priority 內 ISO 8601 時間升序 | 同義改寫：早建立的優先 |
| 3 | id | 同 created 時間內字典序 | 目的：達成穩定排序 |

`--all` 旗標跳過排序與限制，輸出純粹按檔案系統載入順序。

### In Progress 列的 lease 標記（`table` 格式）

`table` 格式（預設）對 `status == in_progress` 的列附加與 `dashboard` 相同的
lease 三態標記：`[LIVE]`＝FRESH session 佐證持有；`[RECLAIMABLE]`＝已知無
FRESH session 佐證持有（含 STALE／registry 未追蹤，兩者統一標記，皆須走
`track reclaim` 鑑識判定）；無標記＝registry 不可用（無法判定）。判準與渲染
共用 `lease.determine_lease_state` / `lease.format_lease_tag`（單一來源，與
`dashboard`／`runqueue` 各自的標記邏輯同判準不同渲染路徑）。`ids`／`yaml`
格式不受影響，維持既有輸出。

### 範例

```bash
# 預設行為：top 10 by priority
ticket track list

# 擴大列數至 30
ticket track list --top 30

# 取全量（過去行為）— 會 emit warning 提醒已不是預設
ticket track list --all

# 篩選 pending + in_progress 各取 top 10
ticket track list --status pending in_progress --top 10

# 純 ID 輸出 pipe 到 ticket show
ticket track list --status pending --top 5 --format ids | xargs -I{} ticket track show {}

# YAML 輸出供腳本解析
ticket track list --completed --format yaml --version 0.18.0
```

### 設計約束

- 預設 `--top 10` 與 priority 排序為**行為變更**（W10-115）；既有腳本若依賴全量輸出需顯式加 `--all`
- `--top` 與 `--all` 共存時 `--all` 優先並 emit warning（破壞性低；不報錯避免 CI 中斷）
- `--format` 三選值對齊 `stale-list`（`table/ids/yaml`），保持 list-class 命令一致性
- 跨版本聚合（`--version=all` 或省略 + 多版本場景）依各版本內排序後合併

### 與 dashboard 的差異

| 場景 | 推薦命令 | 原因 |
|------|---------|------|
| PM 新 session 接手 | `dashboard` | 一次看到 in_progress + handoff target + ready + stale 四區塊 |
| 細部篩選（特定 wave/status/format） | `list` | flag 組合彈性高 |
| 自動化腳本（pipe 到其他命令） | `list --format ids` | 純 ID 輸出無裝飾 |
| 「下一個該做哪個」決策 | `runqueue` | 含關鍵路徑 / DAG 視圖

---

## track dispatch 子命令

派發即落票：輸出可直接貼進 Agent prompt 的骨架文字（`normal`／`review` 兩變體），並視旗標同步寫入票面的暫態記錄與冪等 Commit 規範子節。

### 用法

```bash
ticket track dispatch <ticket_id> --as <agent_name> --task-summary "一句話動作描述（≤ 40 字）"
ticket track dispatch <ticket_id> --as <agent_name> --note "並行派發，commit policy = agent commit"
ticket track dispatch <ticket_id> --kind review \
  --review-perspective "架構一致性" --decision-question "是否符合單一權威決策？"
ticket track dispatch <ticket_id> --as <agent_name> --dry-run   # 只看骨架，不落票
```

### Flag 說明

| Flag | 預設 | 說明 |
|------|------|------|
| `--as` | 無 | 派發對象 agent 名稱，代入骨架 claim/complete 的 `--as` |
| `--note` | 無 | 派發瞬間的暫態約束/步驟，帶時間戳寫入票的「派發日誌」子章節（`## Problem Analysis` 下 `### 派發日誌`）；**不進 Context Bundle** |
| `--kind` | `normal` | `normal`（含 claim/收尾協議完整骨架）／`review`（審查派發，不含 claim/收尾） |
| `--task-summary` | 無 | 一句話動作描述（≤ 40 字），代入骨架任務段 |
| `--review-perspective` | 無 | `--kind review` 專用：審查視角 |
| `--decision-question` | 無 | `--kind review` 專用：裁決問題 |
| `--commit-policy` | `agent` | `agent`（骨架嵌入精準 staging 制式句權威版全文，冪等寫入**票面 body**的「Commit 規範」子章節，非本檔章節）／`pm`（PM 統一 commit，agent 不執行）／`none`（本次派發不涉及 commit） |
| `--dry-run` | 關閉 | 只輸出骨架，不寫入票面（不落 `--note`、不冪等寫入「Commit 規範」子節、不呼叫派發前檢查）；輸出首行加浮水印 `[DRY-RUN 未落票]`；預設行為（非 dry-run）不變 |
| `--version` | 無 | 指定版本（預設自動偵測 active 版本） |

### 骨架去向

輸出的骨架文字**直接貼進 Agent prompt**，不需另行改寫。骨架文字的權威來源是 `ticket_system/lib/dispatch_skeleton.py` 的 `SKELETON_TEMPLATE_NORMAL` / `SKELETON_TEMPLATE_REVIEW`，`.claude/references/agent-dispatch-template.md`「骨架（3 段）」節引用其輸出，不手動同步逐字模板。

### `--dry-run` 與正常呼叫的差異

| 項目 | 正常呼叫 | `--dry-run` |
|------|---------|-------------|
| 骨架輸出 | 骨架本體逐字相同（組裝不依賴票面寫入結果） | 首行加浮水印 `[DRY-RUN 未落票]`，其餘骨架本體逐字與正常呼叫相同——貼入 prompt 後可辨識是否曾落票 |
| 內部呼叫 `dispatch-readiness`／`dispatch-validate`，exit code 落「派發日誌」（`readiness=N validate=N`） | 執行（診斷文字靜音，僅取 exit code） | 略過 |
| `--note` 寫入「派發日誌」 | 執行（與上列 exit code 同一則 entry） | 略過 |
| `--kind normal` 且 `--commit-policy agent` 時冪等寫入「Commit 規範」子節 | 執行 | 略過 |
| 票存在性檢查 | 執行（唯讀） | 執行（唯讀） |
| 適用情境 | 正式派發 | PM 量測骨架行數、預覽 prompt，可重複執行不需事後 checkout 還原票面 |

**派發日誌 entry 恆定寫入**：不論是否帶 `--note`，正常呼叫（非 dry-run）一律在「派發日誌」新增一則帶時間戳的 entry，格式為 `[時間戳] {--note 文字（若有）｜}readiness=N validate=N`——使「認真跑過派發前檢查」與「完全沒做」在票面產生可辨識差異，取代原本兩者骨架逐字相同、無從辨識是否曾落票的狀態。

### 設計約束

`where.files` 含未帶 `::read` 的目錄級寫入宣告時，`dispatch` 拒絕輸出骨架（`[BLOCKED]` 訊息列出受影響的同目錄活躍票）；`--note` 的暫態內容不可進 Context Bundle——Context Bundle 承載跨派發可重用的穩定任務脈絡，`--note` 只承載派發瞬間才出現、不需沉澱的約束/步驟，兩者定位不同不可互相取代。目錄型宣告判定與各階段（建立僅 WARNING、dispatch 硬擋、commit 展開）完整對照見 `field-semantics.md`〈where.files 宣告語意〉。

### 派發前檢查順序

六個派發前命令各自只回答單一問題，無單一命令涵蓋全部派發前檢查；建議順序：`dispatch-readiness`（單票認知負擔軟性拆分閾值是否過大）→ `dispatch-validate`（Context Bundle 自動填料是否可信）→ `parallel-check`（與其他候選票是否有 `where.files` 交集）→ `dispatch`（輸出骨架並落票）。`dispatch-check`（協調狀態檔案是否有其他活躍派發）與 `conflicts --among`（跨票交集的另一角度）為正交的輔助檢查，可在上述順序任一時點插入，不佔固定位置。外部 `.claude/pm-rules/parallel-dispatch.md`〈並行安全檢查〉的檢查項目僅 `conflicts` 有具名 CLI 對映，其餘多為判斷式描述；`.claude/pm-rules/task-splitting.md`〈3b 派發前檢查〉僅點名 `dispatch-readiness`。**Action**：兩份外部文件與本節六命令順序不一致時，以本節命令排序為準，外部文件視為對應子集的摘要。

**`dispatch` 已內部呼叫前兩項並落痕**：`dispatch`（非 `--dry-run`）執行時會內部呼叫 `dispatch-readiness`／`dispatch-validate`（診斷文字靜音，僅取 exit code），將兩者結果記入「派發日誌」（見上節）。這使得就算 PM 跳過手動先跑這兩個命令、直接呼叫 `dispatch`，票面仍留下「派發前檢查曾經跑過、結果是什麼」的痕跡——取代原本兩者完全不跑也無法從骨架/票面辨識的狀態。**仍建議** PM 派發前手動先跑 `dispatch-readiness`／`dispatch-validate`，因為手動呼叫才有完整診斷文字（各項細目與建議）；`dispatch` 內部呼叫只留 exit code 數字，用於稽核「是否曾檢查」而非取代診斷閱讀。

## track dispatch-validate 子命令

> 來源：W17-003

對 target ticket 的 Context Bundle 自動填料結果做合理性檢查，作為 C 方案
（`context_bundle_extractor` 自動抽取）的第二道防線。**與 W10-017.2 的
`dispatch-check`（活躍派發狀態查詢）職責正交**，獨立子命令不互相干擾。

**Why**：C 方案自動抽取可能產出「填料成功但內容空殼」的失敗模式（規則 1 hard fail / 規則 2-4 soft warn 即為此設計），需要 lightweight 檢查層攔截，避免空殼 Context Bundle 派發給 agent。

### 用法

```bash
ticket track dispatch-validate <ticket_id>
```

### 合理性檢查規則

| 規則 | 內容 | 違反後果 |
|------|------|---------|
| 1 | Context Bundle section 存在且 content 非全空白 | 硬性失敗 → exit 2 |
| 2 | Context Bundle content 長度 ≥ 50 字元（避免空殼填料） | 軟性警告 → exit 1 |
| 3 | frontmatter `where.files` 列出的檔案在檔案系統存在 | 軟性警告 → exit 1 |
| 4 | acceptance ≥ 3 項（4V 原則） | 軟性警告 → exit 1 |
| 5 | （保留）LLM 審查 Context Bundle 是否真能讓 agent 上手 | 本 ticket 不實作 |

> **規則 4「≥ 3」非逐一對應 4V 各原則的推導**：`track_dispatch_validate.py` 原始碼註解僅載「4V 原則，少於 3 項視為規格不足」，未進一步說明為何門檻是 3 而非 4（4V 四原則的字面數）或其他值；此為經驗閾值（「至少 3 項通常代表跨面向覆蓋」的粗略啟發），非由 4V 定義逐條推導所得，讀者不應假設每項 acceptance 對應唯一一個 V。

### Exit code

| code | 意義 |
|------|------|
| 0 | 全部規則通過 |
| 1 | 軟性警告（規則 2/3/4 至少一項違反） |
| 2 | 硬性失敗（規則 1 違反、ticket 不存在、IO/YAML 錯誤） |

### 設計約束

- **不**修改 ticket，僅輸出診斷
- **不**取代 hook / scheduler 的執行控制
- **不**負責產生 dispatch-plan、也**不**實作 batch dispatch CLI（與 W17-029 邊界）
- where.files 為空時規則 3 視為通過（DOC 類 ticket 常見情形）

### 範例

```bash
$ ticket track dispatch-validate 0.18.0-W17-003
dispatch-validate 0.18.0-W17-003:
  [PASS] 規則 1 欄位非空: Context Bundle section 存在且非空
  [PASS] 規則 2 內容長度: Context Bundle 內容長度 596 >= 50
  [PASS] 規則 3 檔案存在: where.files 3 個檔案皆存在
  [PASS] 規則 4 acceptance 項數: acceptance 5 項 >= 3
[PASS] 全部規則通過
```

---

## track dispatch-readiness 子命令

> 來源：W17-053

派發前認知負擔閾值與綜合就緒度檢查。讀取 ticket frontmatter `where.files`
與 `acceptance` 及 Context Bundle section，自動計算三項核心閾值並加跑三項
一致性啟發式檢查（共六項），輸出 pass/warn/fail 與建議。**與 `dispatch-check`
（活躍派發狀態，W10-017.2）和 `dispatch-validate`（CB 合理性，W17-003）
職責正交**，獨立子命令不互相干擾。

**Why**：派發前缺乏統一 CLI 入口檢查 ticket 是否符合認知負擔閾值、以及
acceptance 與寫入集（`where.files`）是否宣告一致，PM 需手動對照
`.claude/rules/core/cognitive-load.md` 與 `cognitive-load-execution-details.md`
判斷拆分需求，違反摩擦力方法論執行階段減摩擦原則（W17-049 ANA linux 視角）；
acceptance 明文點名的檔案未列入 `where.files` 時，代理人依 acceptance 動了
該檔，commit 時會被 bare-commit-guard 攔下（見檢查 6）。

**Consequence**：缺少自動化檢查會讓 PM 偶爾遺漏拆分判斷，將過大任務派
給代理人；3b 派發後常見症狀包含代理人 commit 遺漏部分職責、回合耗盡前
只完成一半、跨檔不一致導致測試失敗，或 acceptance 與宣告範圍矛盾迫使代理人
在「守寫入集」與「滿足 acceptance」間二選一。

**Action**：派發 3b 實作 ticket 前以本命令自檢；exit 0 直接派發、exit 1
評估是否豁免（如跨進程同步修復條款）、exit 2 依 fail 來源分流處置（見下方
Exit code 表與各檢查說明）——**不可一律視為「須拆票」**，檢查 6 未過時拆票
無效，正確處置是補 `where.files` 或改寫 acceptance（文件給的處置對新 fail
來源無效的舊 pattern：任何檢查新增後，本節的處置對照表都必須同批更新）。

### 用法

```bash
ticket track dispatch-readiness <ticket_id>
```

### 閾值 1-3（認知負擔軟性拆分閾值）

| 閾值 | 取得方式 | 軟上限 | 強制拆分 |
|------|---------|-------|---------|
| 1. 功能職責數（以 acceptance 條目近似） | `acceptance` 欄位計數 | > 2 | > 4 |
| 2. 修改檔案數 | `where.files` 欄位計數 | > 5 | > 10 |
| 3. Context Bundle tokens（以 chars/4 近似） | Context Bundle section 字元數 | > 3000 | > 5000 |

> **閾值來源**：軟上限（`> 2`／`> 5`／`> 3000`）源自 `.claude/references/cognitive-load-execution-details.md`「3b
> 派發前閾值」三項核心指標；強制拆分門檻（`> 4`／`> 10`／`> 5000`）該文件僅載
> tokens 一項（`> 5000`），閾值 1、2 的強制門檻（`4`、`10`）**不出現**於該文件，
> 僅見於 `track_dispatch_readiness.py` 原始碼常數 `_RESPONSIBILITY_HARD_MAX` /
> `_FILES_HARD_MAX` 的行內註解：`4` 有推導依據（「依據 7±2 取下限保守」，即
> Miller's Law 認知負擔上限的保守下界）；`10` 僅為軟上限 `5` 的兩倍，註解未
> 附加推導理由。閾值 1「功能職責數」CLI 無法精確自動推導，
> 沿用 acceptance 條目作為近似訊號，最終由 PM 判定。
>
> **近似性警告（W17-213）**：acceptance 若含「跑測試」「補文件」「執行驗證」
> 等驗證類條目，會讓 acceptance 條目數高於實際功能職責數（高估）；反之，若
> 多個職責被合併寫成單一 acceptance（低估），也會偏離真值。CLI 僅作近似訊號，
> 達 WARN/FAIL 時 PM 應手動覆核 acceptance 是否反映真實職責數，再決定是否拆分。

### 檢查 4-6（acceptance 與寫入集一致性啟發式）

| 檢查 | 判定內容 | 命中條件 | 上限 status |
|------|---------|---------|------------|
| 4. acceptance 與寫入集一致性 | 兩種訊號來源：(a) acceptance 含測試類關鍵詞（測試/test/覆蓋/回歸/regression/涵蓋）但 `where.files` 無任何測試型態路徑；(b) acceptance 提及含萬用字元 `*` 的 glob 路徑樣式（如 `app_localizations*.dart`）但 `where.files` 無檔案可被該樣式 fnmatch 涵蓋 | (a) 關鍵詞命中且無測試路徑，或 (b) glob token 未被 where.files 涵蓋 | warn（不產生 fail） |
| 5. where.files 路徑存在性 | `where.files` 含不存在路徑，且 acceptance 無新建語意（建立/新增/新檔/create/add） | 路徑不存在且無新建關鍵詞 | warn（不產生 fail） |
| 6. acceptance 提及路徑涵蓋性（唯一強制 fail 的啟發式） | acceptance 文字中具備已知副檔名的路徑樣式 token，未被 `where.files` 前綴或檔名比對涵蓋 | 任一提及路徑未涵蓋 | **fail（強制）** |

> 檢查 4、5 皆為啟發式，語意判定有邊界（未命中不代表無矛盾，關鍵詞比對
> 亦可能對非測試語境產生 false positive），故上限為 warn，PM 保留覆核空間。
> 檢查 6 抽取的是「acceptance 明文點名的具體檔案路徑」，誤判成本已由已知
> 副檔名 + ASCII 邊界收斂，故為全套件唯一產生 fail 的啟發式檢查。
>
> 閾值 2、檢查 5、檢查 6 讀取的 `where.files` 計數/存在性/涵蓋性皆以剝除
> `::read`／`::write` 後綴後的純路徑計算；後綴語法與目錄型宣告展開規則見
> `field-semantics.md`〈where.files 宣告語意〉。

### Exit code

| code | 意義 |
|------|------|
| 0 | 六項檢查全數通過 |
| 1 | 軟性警告（閾值 1-3 任一超軟上限，或檢查 4/5 命中矛盾，但未達下列任一強制失敗條件） |
| 2 | 硬性失敗（閾值 1-3 任一超強制拆分閾值 / 檢查 6 未過（acceptance 提及路徑未被 `where.files` 涵蓋）/ ticket 不存在 / IO／YAML 錯誤） |

**重要**：本命令 exit code 語意**不與** `dispatch-check`（W10-017.2，exit
1 = 有活躍派發）和 `dispatch-validate`（W17-003，exit 1 = CB 軟警告）共享；
呼叫端必須以命令名稱判別語意，禁止以 exit code 跨命令解讀。

**exit 2 的處置依 fail 來源分流，禁止一律拆票**：

| fail 來源 | 正確處置 | 錯誤處置（無效） |
|-----------|---------|-----------------|
| 閾值 1-3 任一超強制拆分閾值 | 拆分為多個 ticket 後重新派發 | — |
| 檢查 6 未過（acceptance 提及路徑未被 `where.files` 涵蓋） | 把該路徑加進 `where.files`，或改寫 acceptance 移除該路徑點名 | 拆票——拆分不會改變 acceptance 與 `where.files` 的宣告落差 |
| ticket 不存在 / IO／YAML 錯誤 | 修正呼叫參數（ticket ID、`--version`）或檢查 ticket 檔案完整性 | 拆票 |

### 設計約束

- **不**修改 ticket，僅輸出診斷
- **不**取代 hook / scheduler 的執行控制
- **不**觸碰既有 `dispatch-check`（W10-017.2）與 `dispatch-validate`（W17-003）
- 閾值 1 為近似訊號（acceptance 條目 ≠ 功能職責數），最終拆分判斷由 PM 決定
- Context Bundle section 不存在時閾值 3 視為 0 tokens 通過
- 檢查 4、5 為 warn-only 啟發式，未命中不代表無矛盾，PM 保留覆核空間
- 檢查 6 僅比對具備已知副檔名的路徑樣式 token，純數字版本號或 ticket ID 不會誤判為路徑

### 跨進程同步修復豁免

若 ticket 符合「跨進程同步修復」全部 5 特徵（見 `cognitive-load-execution-details.md`
「跨進程同步修復豁免條款」），可豁免閾值 1，本命令僅供 PM 參考，不應視
為強制阻擋訊號。此豁免僅適用閾值 1，不適用檢查 6（路徑涵蓋性與認知負擔
豁免條款無關）。

### 範例

```bash
$ ticket track dispatch-readiness 0.18.0-W17-053
dispatch-readiness 0.18.0-W17-053:
  [WARN] 閾值 1 功能職責數（acceptance 近似）: acceptance 條目 3 > 2（軟警告；建議拆分為多個 ticket）
  [PASS] 閾值 2 修改檔案數（where.files）: where.files 3 ≤ 5
  [PASS] 閾值 3 Context Bundle tokens: Context Bundle ~250 tokens ≤ 3000
  [PASS] 檢查 4 acceptance 與寫入集一致性（啟發式）: acceptance 無測試類關鍵詞命中，亦無未涵蓋的 glob 路徑提及
  [PASS] 檢查 5 where.files 路徑存在性（啟發式）: where.files 路徑全數存在
  [PASS] 檢查 6 acceptance 提及路徑涵蓋性（強制）: acceptance 未偵測到路徑樣式 token
[WARN] 軟性警告：建議審視拆分必要性
```

```bash
$ ticket track dispatch-readiness <ticket_id>
dispatch-readiness <ticket_id>:
  [PASS] 閾值 1 功能職責數（acceptance 近似）: acceptance 條目 2 ≤ 2
  [PASS] 閾值 2 修改檔案數（where.files）: where.files 2 ≤ 5
  [PASS] 閾值 3 Context Bundle tokens: Context Bundle ~600 tokens ≤ 3000
  [PASS] 檢查 4 acceptance 與寫入集一致性（啟發式）: acceptance 無測試類關鍵詞命中，亦無未涵蓋的 glob 路徑提及
  [PASS] 檢查 5 where.files 路徑存在性（啟發式）: where.files 路徑全數存在
  [FAIL] 檢查 6 acceptance 提及路徑涵蓋性（強制）: acceptance 提及 1 項路徑未被 where.files 涵蓋，請把該路徑加進 where.files 或改寫 acceptance
      - SKILL.md
[FAIL] 至少一項超強制拆分閾值，建議拆 ticket 後重新派發
```

> 上例 CLI 輸出文字仍沿用「建議拆 ticket 後重新派發」（來自
> `execute_dispatch_readiness` 的統一提示行），但此提示對檢查 6 觸發的
> fail 不適用——**判斷處置時以上方「exit 2 的處置依 fail 來源分流」表為準，
> 不依 CLI 輸出的統一提示行字面行事**。

---

## track dispatch-check 子命令

檢查 `.claude/dispatch-active.json` 是否有活躍派發，取代人工手動讀檔判讀。

### 用法

```bash
ticket track dispatch-check
```

不帶任何參數；讀取當下（依「Ticket 狀態與程式碼提交的 root 分離」節同一套 root 解析規則，統一指向主倉庫）的 `.claude/dispatch-active.json`。

### 判定規則

| 情境 | 輸出 | Exit code |
|------|------|-----------|
| 檔案不存在，或存在但 `dispatches` 為空陣列 | `[PASS] 無活躍派發，可繼續` | 0 |
| `dispatches` 非空 | `[WARN] 有 N 個活躍派發：` + 逐筆列出 `agent_description` / `ticket_id` / `dispatched_at` + 新鮮度標註（見下） | 1 |
| 檔案讀取失敗、JSON 格式錯誤、或 root/`dispatches` 結構不符 | `[FAIL] ...`（stderr） | 2 |

**新鮮度標註**：逐筆條目末尾附年齡標記，沿用 `track_dashboard.DEFAULT_STALE_THRESHOLD_MIN`（60 分鐘）同一新鮮度慣例——距今未逾 60 分鐘標 `(Nmin)`，逾閾值標 `[STALE Nmin]`。`dispatched_at` 缺失、格式錯誤或為未來時間時不猜測、不標記（fail-safe，年齡欄留空）。`[STALE]` 筆數 > 0 時，`[WARN]` 清單後另加一行彙總：`[WARN] 其中 N 筆逾 60 分鐘未見更新（[STALE] 標記），可能為遺留記錄，建議對照 track sessions 或執行 dispatch-check --prune（僅清理 session 確認不存在的條目）`。

**WARN 後下一步**：收到 `[WARN]` 時對照每筆條目的新鮮度標註與 `ticket track sessions` 的存活 session：`(Nmin)` 未逾閾值（該 agent 尚有機會回報）則暫緩新派發；`[STALE Nmin]` 且對應 session 已不存在，屬正常應由 `subagent-stop-dispatch-cleanup-hook.py`（SubagentStop 觸發）清除的殘留條目未被清除，改執行 `ticket track dispatch-check --prune` 交叉比對 pm-registry 清理，不再逕自手動改 `.claude/dispatch-active.json`（見下節）；不逕自視為「有活躍派發」而延後派發。

### `--prune`：清理「[STALE] 且 session 不存在」的條目

```bash
ticket track dispatch-check --prune
```

取代原「見 `[STALE]` 手動清理 `.claude/dispatch-active.json`」的無痕跡做法。判定條件為 AND：(1) 條目已標 `[STALE]`（見上方新鮮度標註）；(2) 條目 `session_id` 非空、且不在 `pm-registry.json`（`ticket track sessions` 同一來源）的 session 集合內。

| `session_id` 狀態 | 處置 |
|------|------|
| 非空，且不在 registry 內 | 判定為「不存在」，清理 |
| 非空，且仍在 registry 內（即使 registry 內該 session 本身標 STALE） | 保留——heartbeat 慢但仍存活的 agent，不可誤判為不存在 |
| 空字串（無 session_id，舊格式條目） | 保留——無法歸戶，不可判定 |
| registry 讀取失敗（git 不可用 / 檔案缺失 / 解析失敗） | 保留全部條目——無法判定時保守不清理，輸出 `[INFO] --prune：pm-registry 不可用，無法判定 session 是否存在，本次不清理` |

清理結果雙通道輸出：stderr 逐筆列出 `agent`／`ticket`／`session_id`／`dispatched_at`，同時寫入 `.claude/hook-logs/dispatch-check-prune/dispatch-check-prune-{YYYYMMDD}.log`（`INFO` 級別，供事後稽核，符合可觀測性規則 4）。無符合條件的條目時輸出 `[INFO] --prune：無符合「[STALE] 且 session 不存在」條件的條目`，不誤報為已清理。清理後若 `dispatches` 歸零，回傳 `[PASS]`（exit 0）；仍有剩餘活躍派發則照常輸出 `[WARN]`（exit 1）。

### 與 track dispatch-validate 的差異

`dispatch-check` 檢查的是**協調狀態檔案**（是否有其他派發正在進行，用於避免同時派發衝突）；`dispatch-validate`（見上節）檢查的是**單一 ticket 的派發合理性**（Context Bundle 自動填料是否可信）。兩者職責正交，可能同時需要在派發前執行。

### 設計約束

Exit code 2（IO 或 JSON 格式錯誤）刻意保守判定為 NO-GO，供 Hook 程式化判定；本命令只加格式化輸出與 exit code，不改變既有的「讀檔 + 判斷 dispatches 陣列空/非空」判定規則。

---

## track sessions 子命令

> 來源：multi-PM 協調層 Phase 1，issue tarrragon/claude#77

read-only 查詢 `pm-registry.json`，列出同專案 PM session 清單（heartbeat 新鮮度 / 認領 tickets 與 files 數），供多 PM 並行時互相察知彼此範圍。

### 用法

```bash
ticket track sessions [--format {table,json}]
```

### Flag 說明

| Flag | 預設 | 說明 |
|------|------|------|
| `--format` | `table` | `table`（人閱讀）/ `json`（腳本消費，輸出 `{"sessions": [...]}`） |

### Registry 位置與 Schema

- 路徑：`<git rev-parse --git-common-dir>/pm-registry.json`（worktree 內亦解析回主 repo `.git/`，跨 worktree 共用單一實例）
- 內容 schema（v2；`schema_version` 欄位標記）：`sessions.<session_id>` 含 `name` / `project` / `registered_at` / `heartbeat_ts` / `tickets` / `files`（v1 曾含 `parent_session_id`，v2 已移除——恆等 `session_id` 的冗餘欄位，見 `.claude/lib/pm_registry.py` 檔頭 docstring「v2 相對 v1 的變更」；舊版 v1 檔案仍可讀取，寫入時自然正規化為 v2 形狀）
- **契約住址**：`.claude/lib/pm_registry.py` 檔頭 docstring 自稱「Registry Schema 契約 v2（單一來源，本模組不得自行變更欄位/結構）」，為 registry schema 唯一權威定義；本節與其餘消費端（`.claude/references/bash-tool-usage-details.md`、`.claude/references/parallel-dispatch-agent-lifecycle-details.md` 等）僅描述讀取端行為，不重複定義 schema，變更 schema 須先改該 docstring 再同步消費端
- 寫入端（hooks 職責）：SessionStart 註冊 + heartbeat 更新、Stop/handoff 釋放；本命令僅讀取，不寫入

### 輸出格式（table）

```
=== PM Sessions ===
  session_id  name                 age(min)  status  tickets  files  reclaimable
  ---------------------------------------------------------------------------------
  session-a   flutter-balance-b6          5  FRESH         1      2  -
  session-b   flutter-balance-c2         45  STALE         2      3  0.2.1-W3-100, 0.2.1-W3-101
```

### 欄位定義

| 欄位 | 說明 |
|------|------|
| `session_id` | CC hook 輸入 JSON 的 `session_id` |
| `name` | session 名稱（未提供時退回 `session_id`） |
| `age(min)` | heartbeat 與查詢當下的分鐘差（整數，捨去）；無法解析時顯示 `?` |
| `status` | `FRESH`（heartbeat 30 分鐘內）/ `STALE`（逾 30 分鐘或無法解析） |
| `tickets` | 該 session 認領的 ticket 數 |
| `files` | 該 session 認領的檔案數 |
| `reclaimable` | `STALE` session 持有的全部 ticket id（逗號分隔）；`FRESH` 時恆為 `-`。僅 heartbeat 新鮮度輕量判準，非「track reclaim 子命令」實際執行前的 ghost 鑑識三查結果——兩者為兩層判定，見該章節「與 sessions/runqueue 顯示層判定的差異」 |

### 降級行為（不阻擋工作流）

| 情境 | 行為 |
|------|------|
| `pm-registry.json` 缺檔 | 輸出空表 + exit 0 |
| JSON 解析失敗 | stderr 提示 + 輸出空表 + exit 0 |
| 非 git repo / git 不可用 | 輸出空表 + exit 0 |
| session `heartbeat_ts` 缺失或格式錯誤 | fail-open 視為 `STALE`（不可靜默呈現「新鮮」假象） |

### 設計約束

- version-agnostic：見〈共用旗標語意（track 系列命令通用）〉
- 僅列 `project` 欄位等於當前 `git rev-parse --show-toplevel` 的 session（同專案篩選；git 不可用時不篩選，保留全部）
- stale 判定閾值固定 30 分鐘（`STALE_THRESHOLD_MINUTES`）；`reclaimable` 欄位僅為輕量標記（heartbeat 判準），實際執行 reclaim（轉回 pending + 清 lease）另見「track reclaim 子命令」章節（multi-PM 協調層 Phase 3）
- Registry Schema 契約 v2 為 hooks 與 CLI 兩職責共同 SSOT，本命令不得自行變更 schema

---

## track reclaim 子命令

> 來源：multi-PM 協調層 Phase 3，issue tarrragon/claude#77

現行 `claim` 永不過期，PM session 崩潰後持票永久鎖死。`reclaim` 提供受控釋放路徑：僅接受 `in_progress` 且無 FRESH session 佐證（或 registry 未追蹤）的票，並強制執行 ghost 鑑識三查，任一命中或無法判定即拒絕。

### 用法

```bash
ticket track reclaim <ticket_id> [--version V]              # dry-run：僅印鑑識報告
ticket track reclaim <ticket_id> [--version V] --confirm    # 三查全過才實際轉回 pending
```

### Flag 說明

| Flag | 預設 | 說明 |
|------|------|------|
| `--version` | 自動偵測 | 版本號（ticket_id 本身含版本段時可省略，CLI 自動解析） |
| `--confirm` | False | 三查鑑識全過才生效：轉回 pending 並清除 registry lease；未加此旗標僅印 dry-run 報告 |

### Ghost 鑑識三查

`--confirm` 是否放行取決於前兩查（未合併分支、髒檔交集）：任一命中或無法判定即拒絕（與 `--confirm` 是否給出無關——`--confirm` 只決定「前兩查皆通過後是否落地」，不能覆蓋其結果）。第 3 查（缺 Exit Status）為 soft warning，**不計入拒絕與否的判定**，僅記錄於鑑識報告供人工參考：

| 查 | 判定內容 | 命中條件 | 是否影響 `--confirm` 放行 |
|----|---------|---------|---------|
| 1. 未合併分支 | `git branch --no-merged` 是否存在含 ticket_id 的分支名 | 存在即命中 | 是，命中即拒絕 |
| 2. 髒檔交集 | `git status --porcelain` 路徑與票面 `where.files` 是否有交集 | 有交集即命中 | 是，命中即拒絕 |
| 3. 缺 Exit Status | 票面 `Exit Status` 章節是否仍為佔位符或未找到 | 缺失/佔位符即命中 | 否，警告，不計入結論（`lease.py` `GhostReport.clean` 明式排除本項） |

第 1、2 查依賴 git 查詢；查詢本身失敗（非「查到零筆」）時標記為「無法判定」，與「通過」區分對待——查詢失敗不可視為通過（防止 fail-open 誤放行），且與命中同樣導致拒絕。第 3 查為純票面內容比對，不受此影響，且不參與拒絕判定。

**判準（依實作改寫，非文件先前所述「三查任一命中即拒絕」）**：第 3 查刻意不計入拒絕判定。**Why**：遺留票的定義正是執行者已不在，`Exit Status` 章節必然無人能填——若把這種常態當拒絕條件，會使 reclaim 對它最該服務的對象（真正遺留的票）不可用，逼流量繞去零鑑識的 `ticket track release`。「執行中票不可 reclaim」的性質已由 `check_reclaimable` 的 FRESH lease 判定於呼叫鑑識前獨立把關；owner 為 None（registry 未追蹤 lease）時則由前兩查覆蓋——執行中的代理人通常仍有未合併分支或未提交變更，可視為間接把關。**Action**：`--confirm` 對某張明顯已死的 session 持票持續拒絕，只可能因命中前兩查其一，非因缺 Exit Status；判讀鑑識報告時，第 3 查「缺失/佔位符（警告，不影響鑑識結果）」不構成拒絕理由。

### 輸出格式（dry-run 範例）

```
[reclaim] 0.2.1-W3-100: registry 未追蹤此票 lease（無 FRESH session 佐證），允許依 ghost 鑑識判定
=== Ghost 鑑識報告: 0.2.1-W3-100 ===
  1. 未合併分支: 通過
  2. 髒檔交集: 通過
  3. Exit Status 章節: 已填寫
  結論: 鑑識通過，允許 reclaim
[reclaim] 0.2.1-W3-100: dry-run 完成，鑑識通過；加 --confirm 執行實際 reclaim
```

### 與 sessions/runqueue 顯示層判定的差異

**結論**：「`sessions`/`runqueue` 顯示為可 reclaim 候選」與「`reclaim --confirm` 實際放行」是兩層判定，前者是列表級的粗篩提示，後者才是逐票的精確判定；粗篩顯示候選不保證 `--confirm` 會放行。

`runqueue` 的 `[RECLAIMABLE]` 標記經 `is_lease_reclaimable` 判定：持有者 session heartbeat 逾 TTL，**或** registry 已載入但未追蹤此票 lease（含 graceful SessionEnd 釋放後 entry 已刪除的情形）。`sessions` 的 `reclaimable` 欄**不呼叫**本函式，而是 `track_sessions.py` 自算（僅 `status == "STALE"` 才列）——判準分岔，語意對象不同（一為接手提示，一為 session 逾時）。兩者皆**不含**本命令的 ghost 鑑識三查——鑑識涉及 git 呼叫，不適合逐票渲染表格時觸發。

### Exit code

| 值 | 說明 |
|----|------|
| 0 | dry-run 鑑識通過 / `--confirm` 且落地成功 |
| 1 | 找不到 ticket、票非 in_progress、有 FRESH session 佐證、鑑識未通過、或落地時票面更新失敗 |

### `--confirm` 落地：鑑識報告寫入 Solution

`--confirm` 且三查（依上方判準，僅第 1、2 查計入拒絕判定）全過、實際轉回 pending 後，鑑識報告額外 append-log 進票面 `Solution` 章節，供事後對帳（原僅印終端機，`--confirm` 決策無法回溯稽核）。dry-run（未帶 `--confirm`）與三查未通過兩路徑皆不落地寫入。落票為稽核強化，非 `reclaim` 成功的前提——落票本身失敗（如 hook 內部例外）不影響 `reclaim` 已完成的狀態轉換，僅記 stderr。

### 設計約束

- 外層流程跨兩把獨立鎖，非單一原子操作：`check_reclaimable` 讀 registry（無鎖快照）→ ghost 鑑識（純讀取，無鎖）→ 落地持 ticket md 的 `file_lock` → 之後才持 registry 的 `_registry_lock` 清 lease。理論上存在窄視窗（owner session 可能在鑑識後、落地前恢復心跳），影響侷限於「STALE 誤判為短暫失聯的 session 遺失一張已無在途工作證據的票」，非資料損毀風險
- registry 未追蹤該票 lease 時仍允許依 ghost 鑑識判定（registry 缺失非阻擋條件，同 Registry Schema 契約「損毀/缺檔處置」降級語意）

---

## track activity 子命令

> 來源：multi-PM 協調層 Phase 2，L1 新鮮度

票面進度是事件驅動更新（claim/append-log/complete），事件間有 27-35 分鐘常態靜默窗口（依歷史 ticket 事件時間戳觀察得出的經驗範圍，非正式統計抽樣結果；如需重算可對照近期 `.claude/hook-logs/` 或 ticket `updated` 時間戳間隔），靜默本身無法判斷「在做/卡住/session 已死」。`activity` 從既有副作用機械推導每張 `in_progress` 票的最後活動時間，把靜默從歧義降為可判定狀態。

### 用法

```bash
ticket track activity [--version V] [--all] [--format {table,json}]
```

### 三源（取最新者，附來源標記）

| 來源標記 | 說明 |
|---------|------|
| `md_mtime` | ticket md 檔案的磁碟 mtime |
| `git_commit` | `git log --grep=<id>` 最後一筆 commit 的 committer 時間 |
| `dirty_file` | working tree 髒檔命中該票 `where.files` 的歸屬，取命中檔案的磁碟 mtime |
| `no-signal` | 三源皆缺（非錯誤，票剛 claim 尚無任何副作用時的正常狀態） |

**父子票邊界**（判準）：子票 commit 不計入父票活動，父票 `git_commit` 源不會被子票覆蓋（實作機制：`git log --grep` 加 `--fixed-strings` 並在 Python 端逐一驗證候選 commit 的 subject 是否為「獨立引用」，見 `track_activity.py` 程式碼註解）。

### 輸出格式（table）

```
=== Ticket Activity (L1) ===
  id            last_activity              source      agent
  ---------------------------------------------------------------
  0.2.1-W3-001  2026-08-18T10:00:00+00:00  git_commit  thyme-python-developer
```

### 設計約束

- 共用旗標語意（--all、version-agnostic）：見〈共用旗標語意（track 系列命令通用）〉，本命令預設已掃描全部 active 版本的 `in_progress` 票
- 髒檔路徑比對用 `PurePosixPath` 前綴判定，非 `string.startswith`（避免 `lib/foo` 誤命中 `lib/foobar.dart`）  <!-- skill-residue-exempt: 說明路徑比對規則的示意路徑，非本專案實際檔案 -->
- git 呼叫一律經 `.claude/lib/git_utils.run_git_command`（已內建 `--no-optional-locks`，避免與並行 PM session 競爭 `.git/index.lock`），lazy import 比照 `ticket_system/lib/claude_lib_loader.py` 的 `_find_claude_dir()` 共用實作
- `attribute_dirty_files()` 為髒檔歸屬第三源的獨立輸出函式，供 `onboard` 命令複用

---

## track conflicts 子命令

> 來源：multi-PM 協調層 Phase 2，where.files 交集

並行派發前跑 `conflicts --among` 確認候選票是否互撞；宣告互斥不代表不撞（Phase 2 盲測實證：宣告 `where.files` 吻合度僅 3/10，即七成 completed 票的實際 commit 超出宣告範圍；來源見 `ticket_system/lib/file_conflict.py` 模組 docstring「Phase 2 盲測實證」，非 `CHANGELOG.md`——原指向已過期，CHANGELOG.md 現無此數字），故本命令內建 impl→test 擴張啟發式擴大偵測面，補「宣告實作檔、漏宣告伴生測試檔與關聯模組」這類缺漏。

### 用法

```bash
ticket track conflicts [--version V] [--all] [--format {table,json}]
ticket track conflicts --for <ticket-id> [--include-heuristic] [--format {table,json}]
ticket track conflicts --among <id1,id2,...> [--include-heuristic] [--format {table,json}]
```

`--for` 與 `--among` 為針對性查詢：PM 並行派發前只想問「這幾張會不會撞」，
不必人工 grep 全量輸出。二擇一（同時提供時 `--among` 優先）：

- `--for <ticket-id>`：列出該票與其他 `pending`/`in_progress` 票之間的全部衝突對
- `--among <id1,id2,...>`：僅比對指定票組彼此之間（逗號分隔，票組外的票不出現）

兩者皆預設隱藏純目錄層級宣告命中（如 `.claude/hooks/` 對任何位於該目錄下
的檔案宣告皆會匹配，屬噪音來源），需顯式加 `--include-heuristic` 開啟；
未帶 `--for`/`--among` 的既有全量輸出行為不受影響（仍照舊顯示目錄層級命中）。

### 判定規則

1. 兩兩比對 `pending`/`in_progress` 票的 `where.files`（原始宣告 + 啟發式衍生）
2. 路徑交集用 `PurePosixPath` 前綴比對（精確相符或互為上層目錄），非 `string startswith`
3. impl→test 擴張啟發式：對每個宣告檔案路徑額外推導可能的伴生測試檔路徑一併納入交集判定；目前覆蓋兩種慣例——Dart `lib/...` → `test/..._test.dart`（不查真實檔案系統）<!-- skill-residue-exempt: 描述推導慣例的模式示意，非本專案實際檔案 -->；Python `X.py` → 掃描真實檔案系統找出最近的 `tests/` 兄弟目錄（見「Python 測試路徑推導」），找不到真實 `tests/` 目錄時不衍生候選
4. 與 pm-registry 的 `files` 欄位交叉比對：僅採 **FRESH session**（heartbeat 未逾 30 分鐘）的宣告，`in_progress` 票若與其認領 session 的 registry files 完全無交集，輸出 stderr 警告（不影響 exit code）；STALE session 的殘留宣告排除在外，避免死 session 舊宣告誤觸發警告。警告文字附後果與下一步：「衝突判定僅採 write 集合；請校正票面宣告或重跑 claim」——說明本命令的判定基準只看票面宣告（不讀 registry），並指引兩種修正路徑。`write` 集合的判定依據（後綴標記與 type 預設意圖）見 `field-semantics.md`〈where.files 宣告語意〉
5. `[heuristic]` 標記：衝突僅由擴張啟發式衍生路徑觸發（原始宣告值本身無交集）

### Python 測試路徑推導

**規則**：`tests/` 為套件根目錄的兄弟層（非緊鄰檔案自身目錄下的子目錄），取最近（最深）一個實際存在的候選；找不到符合的 `tests/` 兄弟目錄時不猜測、不衍生候選。逐層往上檢查每個祖先目錄的演算法細節見 `file_conflict.py` 程式碼註解。

> **與覆核指令的區別**：以上是 `conflicts` 啟發式「推測」原始碼對應測試檔位置的演算法（用於偵測潛在衝突），非本 ticket skill 覆核自身測試套件時該如何執行測試——後者的標準覆核指令與禁止事項見 `references/architecture.md`「覆核測試指令（skill 自身測試套件）」章節（唯一權威版本，本檔不留副本）。

### Exit code

| 值 | 說明 |
|----|------|
| 0 | 無衝突 |
| 1 | 偵測到至少一組衝突（registry 警告不影響此判定） |

### 輸出格式（table）

```
=== File Conflicts ===
  0.2.1-W3-001 <-> 0.2.1-W3-002 [heuristic]: test/domain/foo_test.dart  <!-- skill-residue-exempt: 命令輸出範例的示意路徑，非本專案實際檔案 -->
```

### 設計約束

- 共用旗標語意（--all、version-agnostic）：見〈共用旗標語意（track 系列命令通用）〉
- registry 讀取一律經 `.claude/lib/pm_registry` 的 `get_registry_paths` + `read_registry`
- 純目錄級宣告（如 `lib/domain`）與巢狀檔案級宣告天然會被判為交集——這是已知取捨（issue #77 討論記錄：純目錄級 lease 會造成過度序列化），本命令僅負責偵測呈現，不負責治理宣告粒度

---

## track onboard 子命令

> 來源：multi-PM 協調層 Phase 2，入場四節彙整

`onboard` 為輔助入口，非 PM 接手流程首選（見 `SKILL.md`〈無子命令時的預設行為（dashboard-first）〉，裸 `/ticket` 一律先走 dashboard-first 流程）；本命令讀四節（活同事／孤兒 entry／髒檔歸屬／可認領建議），把 session 啟動已印的 30+ hook 輸出牆收斂為單一固定值表，供需要多 PM 協調細節時查詢。`/clear` 後入場是從世界平面重建三問（我是誰 / 同事是誰 / 我手上有什麼），不是恢復記憶。

### 用法

```bash
ticket track onboard [--version V] [--all] [--top N] [--format {table,json}]
```

### 四節

| 章節 | 資料來源 |
|------|---------|
| 活同事表 | 複用 `track_sessions._build_rows`（FRESH session） |
| 孤兒 entry 表 | 同上（STALE session：heartbeat 已死但 registry entry 未回收） |
| 髒檔歸屬 | 本檔獨立實作，僅比對 `in_progress` 票，見下方「髒檔歸屬設計」 |
| 可認領建議 | 複用 `track_dashboard.load_top_ready`（同 dashboard Ready 章節） |

### 髒檔歸屬設計：輸出判讀對映

| 輸出 | 判讀 | 下一步 |
|------|------|--------|
| 「泛目錄宣告命中 N 票（無鑑別力）」 | 宣告太淺（路徑段數 <= 2，如僅宣告 `.claude/`），無法判斷髒檔真正歸屬 | 收窄該票 `where.files` |
| 精確檔案層級的多票 tie | 真實衝突訊號（非噪音，不收斂） | 跑 `ticket track conflicts --among` 確認 |

呈現方向為 **file -> tickets**（PM 入場真正想知道的是「這個髒檔是誰的」，非「這張票碰了哪些髒檔」）；僅比對 `status == in_progress` 的票；歸屬採最長匹配前綴特異度（精確檔案相符 > 深層目錄相符 > 淺層目錄相符）。目錄型宣告的判定與展開規則見 `field-semantics.md`〈where.files 宣告語意〉。

### Flag 說明

| Flag | 預設 | 說明 |
|------|------|------|
| `--top` | 5 | 可認領建議章節列數上限 |
| `--version` / `--format` | 同 `activity`/`conflicts` | 版本範圍與輸出格式 |
| `--all` | — | 見〈共用旗標語意（track 系列命令通用）〉 |

### 設計約束

- registry 讀取一律經 `.claude/lib/pm_registry` 的 `get_registry_paths` + `read_registry`
- stale 判定完全交由 `track_sessions._build_rows` 內部既有邏輯處理，本命令不重新定義任何 stale 閾值常數
- registry 缺檔/損毀時各節優雅降級（活同事顯示「（無活同事）」、孤兒 entry 顯示「（無孤兒 entry）」，餘二節同款樣式），不阻擋其餘三節輸出

---

## track hook-liveness 子命令

輸入 hook 檔路徑或名稱，查 `.claude/hook-logs/_liveness/*.jsonl` 回報該
hook 的觸發記錄（依 session 聚合筆數、最近一筆 ts、今日筆數），並明確印出
「以什麼名字查」——取代憑檔名慣例（去 `-hook` 後綴等）手組 grep。

### 用法

```bash
ticket track hook-liveness <hook 檔路徑或名稱> [--since <ISO 時間>] [--session <session_id>] [--format table|json]
```

### 0 筆結果的判讀

部分 hook 的 `HOOK_NAME` 常數帶 `-hook` 後綴，與其餘同類 hook 的命名慣例不一致；憑慣例猜測名稱查 liveness 記錄得到「0 筆」，此結果與「hook 未觸發」這個合法結論無法區分，會產生有據可查但錯誤的驗收記錄。本命令解析真實的 `HOOK_NAME`（存在檔案時），並在 0 筆時明確區分兩種原因：

| 情境 | 訊息 |
|------|------|
| 輸入為檔路徑，已解析出 `HOOK_NAME`，該名稱 0 筆 | 「名稱已解析為 X，X 無任何記錄（hook 可能確實未觸發）」 |
| 輸入為字面名稱（非解析自既有檔案），0 筆 | 「名稱為字面輸入，0 筆可能代表名稱輸入錯誤或 hook 確實未觸發」 |

### 名稱解析順序

1. 輸入為存在的檔案路徑（相對於 cwd 或相對於 git toplevel 皆可）→ 讀原始碼解析 `HOOK_NAME = "..."` 常數
2. 無 `HOOK_NAME` 常數 → 退回檔名去 `.py`（`Path(x).stem`）
3. 輸入非存在的檔案路徑 → 視為字面名稱直接使用

### Flag 說明

| Flag | 預設 | 說明 |
|------|------|------|
| `--since` | 無 | 只計入此 ISO 時間之後的記錄 |
| `--session` | 無 | 只掃描指定 `session_id` 的 liveness 檔案 |
| `--format` | `table` | `table`（PM 預設視圖）/ `json`（自動化消費） |

> 防護類 hook ticket 的「本 session 實地觸發確認」標準寫法（以本命令前後差值取代手動 grep 或憑印象判斷）已移至 `.claude/pm-rules/ticket-body-schema.md`「防護類 hook ticket 額外 acceptance」節，內容是 ticket 收尾時的驗收手段規範，不是本命令本身的用法。

---

## track register-artifact / resolve-artifact / list-artifacts 子命令

跨 session 實驗器材（sentinel/探針/對照組樣本，其存在本身即為觀測手段的檔案）的票面登記 CLI 化，取代規範原僅要求「登記三項但格式自由發揮」的手工條款。完整規範見 `.claude/pm-rules/parallel-dispatch.md`「跨 session 實驗器材的自我標示與存活期治理（強制）」。

```bash
ticket track register-artifact <id> --path <路徑> --purpose <用途> --expiry <存活期> [--type 明示|盲測]
ticket track list-artifacts <id> [--json]
ticket track resolve-artifact <id> EXP-N --status removed|kept [--successor <ticket-id>] [--reason <說明>]
```

`register-artifact` 自動編號（`EXP-N`）寫入 Solution 章節固定子章節，同時輸出可直接複製貼上的首行 header 文字（供落地條件一的檔案端標示）。`list-artifacts` 提供結構化讀回（含 `--json`），供收尾檢查程式化消費，不需人工掃描章節。`resolve-artifact` 標記存活期治理的收尾處置：`--status kept` 強制要求 `--successor`（CLI 層面阻止「未指名接手者」漏處置，非僅文件提醒）。

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

`runqueue --format=list` 的 `[RECLAIMABLE]`（lease TTL）可與 `[STALE]`（`is_stale_in_progress`）並列疊加，兩者來源不同、各自獨立出現，見上方「track runqueue 子命令」段落。**Action**：判讀任一「stale／reclaimable」標記前，先確認該標記出自本表哪一套判準，不可假設全站僅一套滯留定義。

## 空狀態字面規範（track 系列命令通用）

`activity`、`conflicts`、`onboard`、`stale-list`、`stuck-anas`、`dashboard` 六個命令的空狀態一律採全形括號包裹的中文描述句 `（無 XXX）`，不使用英文 `(none)`：`activity` 為「（無 in_progress ticket）」、`conflicts` 為「（無衝突）」、`onboard` 四節分別為「（無活同事）」「（無孤兒 entry）」「（無髒檔）」「（無可認領建議）」、`stale-list` 為「（無符合條件的 stale ticket）」、`stuck-anas` 為「（無卡住的 ANA）」、`dashboard`（In Progress / Handoff Target / Ready Top N / Stale Warning 四區塊）分別為「（無 in_progress ticket）」「（無 handoff target）」「（無可認領建議）」「（無 stale ticket）」。技術術語（`in_progress`、`entry`、`handoff target`）依語言約束規則 4 保留原文，不強制中譯。
