# track 子命令（READ 操作、runqueue、deps/depth、parallel-check、board、list）

> **用途**：`track` 子命令詳解之一：READ 操作、runqueue、deps/depth、parallel-check、board、list。
>
> **同族檔**：`track-command-commit.md`、`track-command-update.md`、`track-command-dispatch.md`、`track-command-session.md`、`track-command-query.md`、`track-command-health.md`。原檔 `track-command.md` 保留檔頭與保留段落，並為各被移走段標保留路由，被移走段標在原檔以同名標題加一行路由保留，既有〈段標〉引用不需改寫。

---

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

**Exit Status tag（W17-031.1）**：`--context=resume` 模式下，list 視圖讀取 handoff JSON 的 `exit_status.status` 欄位，四類狀態以 `[<status>]` 取代 `blockedBy=[]` runnable 標記，避免 scheduler 誤把待補料 ticket 當可直接接手： <!-- rule8-exempt: relocation:自 .claude/skills/ticket/references/track-command.md 逐字搬移 -->

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
2. **本 Wave 已 completed ANA 的 `spawned_tickets` 皆非 `pending`**（W17-037 落地） <!-- rule8-exempt: relocation:自 .claude/skills/ticket/references/track-command.md 逐字搬移 -->

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

（此範例對前例追加一張 live in_progress 票 `0.2.1-W3-201`，其宣告與 `0.2.1-W3-200` 交集；同樣以 `file_conflict.compute_parallel_groups` / `render_groups` 直接呼叫取得逐字輸出。`0.2.1-W3-201` 的衝突邊排除了 `0.2.1-W3-200`，使其落在「本輪未選入」；`0.2.1-W3-201` 本身不出現於「可並行群組」或「本輪未選入」，改列於「施工中佔用節點」。）  <!-- rule8-exempt: illustration:命令輸出範例的示意 ID 說明文字 --> <!-- rule8-exempt: relocation:自 .claude/skills/ticket/references/track-command.md 逐字搬移 -->

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
| 規則面（本章節）               | 已落地                                       | `.claude/skills/ticket/references/track-command.md`（W17-040）   | <!-- rule8-exempt: relocation:自 .claude/skills/ticket/references/track-command.md 逐字搬移 -->
| Wave 完成判定                  | 已落地                                       | `.claude/pm-rules/completion-checkpoint-rules.md` L76（W17-037） | <!-- rule8-exempt: relocation:自 .claude/skills/ticket/references/track-command.md 逐字搬移 -->
| CLI 排序邏輯（第二層加權實作） | 未實作（若未來發現序列差異造成問題再建 IMP） | `.claude/skills/ticket/ticket_system/commands/track_runqueue.py` |

第二層加權項 `spawned_from_completed_ana`（`source_ticket` 存在且該 source ANA status=completed → 排在同 tier 其他 ticket 前面）來源 W17-036 軸 C 分析。**Why**: ANA 結論已產出的衍生 IMP 推進急迫性高於一般 pending —— source ANA 已結案代表分析完成、結論等待落地；若與其他同 priority pending 同等對待會造成結論擱置（PC-075 下游傳播防護；詳見 `.claude/error-patterns/process-compliance/PC-075-spawned-children-status-check-asymmetric.md`）。實作沿革（W17-011.1 基礎 runqueue、W17-009 ANA 三視角審查收斂結論、W17-036 軸 C 補強）見 `CHANGELOG.md`。 <!-- rule8-exempt: relocation:自 .claude/skills/ticket/references/track-command.md 逐字搬移 -->

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

沿 `parent_id` 鏈計算嵌套深度（**非** ID 字串數點，避免完整版本前綴如 `<version>-W<wave>-<seq>.<sub>` 本身即含 3 個點，被誤算為 depth 4 的 fatal bug）。輸出 `depth` / `max_depth`（= `MAX_TICKET_DEPTH=3`）/ `can_descend`（`depth < MAX_TICKET_DEPTH`）。深度定義：根任務（`parent_id: null`）= depth 1，每往下一層 +1。用途：agent 自檢層級自覺（協議 v2 D3），無需上層 prompt 傳遞層級資訊。輸出附一行 `[用途]` 說明：`can_descend` 供持有該票的呼叫者判斷能否再往下派發，不用於判斷該票能否被派發（被派發票僅在 depth > `MAX_TICKET_DEPTH` 時被派發守衛擋下）。

> **與 frontmatter `chain.depth` 的基數差異**：本命令輸出的 `depth` 是即時沿 `parent_id` 鏈計算的動態值，根任務 = 1（1-based）。`ticket-lifecycle-details.md`〈chain 欄位說明〉的 frontmatter `chain.depth` 是建立當下依 ID 序號點數寫入的靜態快照，根任務 = 0（0-based），與本命令為同名不同來源的獨立量測值，不可互換代入（詳見該節注記）。`can_descend` 與 `MAX_TICKET_DEPTH` 比較一律以本命令輸出為準。

`create --parent <id>` 時，若新子任務深度 > `MAX_TICKET_DEPTH`（3）會 emit warning（**不硬擋**，留旁路；深度 == 3 為合法最深層，不 warn）。此為嵌套派發深度上限的預警：主線程派發此票不受影響，子代理人持有此票時不可再往下派發。派發端的 `agent-ticket-validation-hook` 對子代理人派發以派發者持有票的 `can_descend` 判定（持有票映射缺失時退回被派發票 depth > `MAX_TICKET_DEPTH` 才 deny，裁決 E）；`can_descend`（`depth < MAX`）是呼叫者判斷自己能否再往下派發，不用於被派發票。

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

## track list 子命令

> 來源：W10-115 / W10-113 M3 <!-- rule8-exempt: relocation:自 .claude/skills/ticket/references/track-command.md 逐字搬移 -->

通用 ticket 篩選命令。W10-115 起預設加入 `--top 10` 與 priority 排序，避免 dump 67+ 筆全量造成 PM 認知負擔。 <!-- rule8-exempt: relocation:自 .claude/skills/ticket/references/track-command.md 逐字搬移 -->

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

W10-115 引入的預設排序： <!-- rule8-exempt: relocation:自 .claude/skills/ticket/references/track-command.md 逐字搬移 -->

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

- 預設 `--top 10` 與 priority 排序為**行為變更**（W10-115）；既有腳本若依賴全量輸出需顯式加 `--all` <!-- rule8-exempt: relocation:自 .claude/skills/ticket/references/track-command.md 逐字搬移 -->
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
