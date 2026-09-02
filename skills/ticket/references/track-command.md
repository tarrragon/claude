# track 子命令

追蹤和更新 Ticket 狀態。

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
```

## track runqueue 子命令（Scheduler）

**用途**：回答「下一個該做哪個 ticket」（Linux schedule() 類比）。合併原 next/schedule/resume-hint 三概念為單一命令。

**核心使用場景**：

| 場景                          | 命令                                                    | 輸出                                      |
| ----------------------------- | ------------------------------------------------------- | ----------------------------------------- |
| PM 迷失方向 / 新 session 接手 | `ticket track runqueue --wave N`                        | priority 排序的可執行清單（blockedBy=[]） |
| 查看完整依賴 DAG              | `ticket track runqueue --wave N --format=dag`           | 拓撲層級分組，關鍵路徑高亮                |
| 查看關鍵路徑節點              | `ticket track runqueue --wave N --format=critical-path` | slack=0 節點（CPM）                       |
| /clear 後接手                 | `ticket track runqueue --context=resume --top 3`        | 與 handoff/pending 交集 top 3，含 exit_status tag |

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

### 排序規則（priority + spawned 加權）

**第一層：Priority tier 排序**

| Tier | 條件                 | 優先度 |
| ---- | -------------------- | ------ |
| L1   | priority=P1          | 最優先 |
| L2   | priority=P2          | 次之   |
| L3   | priority=P3 或未指定 | 最低   |

**第二層：同 tier 內加權（來源 W17-036 軸 C 分析）**

| 加權項                       | 觸發條件                                             | 效果                         |
| ---------------------------- | ---------------------------------------------------- | ---------------------------- |
| `spawned_from_completed_ana` | `source_ticket` 存在且該 source ANA status=completed | 排在同 tier 其他 ticket 前面 |

**Why**: ANA 結論已產出的衍生 IMP 推進急迫性高於一般 pending —— source ANA 已結案代表分析完成、結論等待落地；若與其他同 priority pending 同等對待會造成結論擱置（PC-075 下游傳播防護；詳見 `.claude/error-patterns/process-compliance/PC-075-spawned-children-status-check-asymmetric.md`）。

**第三層：依存關係過濾**

`runqueue` 僅列出 `blockedBy=[]` 的 ticket（可執行清單）。被阻塞的 ticket 在 `--format=dag` 可見，在 `--format=list`（預設）不顯示。

### Wave 完成判定與 spawned 清點

Wave 完成判定規則（Checkpoint 2 情境 C 前置條件）：

1. 當前 Wave 無 `pending` / `in_progress` ticket
2. **本 Wave 已 completed ANA 的 `spawned_tickets` 皆非 `pending`**（W17-037 落地）

兩條件均滿足才算 Wave 完成。詳見 `.claude/pm-rules/completion-checkpoint-rules.md` 第八層 Checkpoint 2 情境 C。

### `--groups` 並行群組切分（multi-PM 協調層 Phase 3）

輸入集合與 `list` 視圖同（`blockedBy=[]` 的 pending 票，同一份 priority 排序結果），對此集合依 `where.files` 交集建無向衝突圖：節點為票 id，邊為兩兩交集命中（判定邏輯與 `track conflicts` 共用 `compute_pairwise_conflicts`，含 impl→test 擴張啟發式）。對全體節點依輸入序做單次全域貪婪極大獨立集走訪：逐一檢視節點，若尚未被先前選中節點的鄰居排除即選入「可並行群組」並排除其所有鄰居；孤立節點（度數為 0）必定入選。未被選入的節點歸入「本輪未選入」清單——僅代表與本批已選票有直接衝突邊，不代表這些節點彼此之間也必須序列，即使兩者在衝突圖上經由第三個節點傳遞關聯（A-B 有邊、B-C 有邊、A-C 無邊時，A 與 C 仍可能同時入選可並行群組）。

Live in_progress 票（非 stale，`staleness.is_live_occupied` 判準）以 seed 身份併入同一張衝突圖：其衝突邊在後續輪次仍然存在，使與其有 `where.files` 交集的鄰居於貪婪走訪時被排除；in_progress 票本身不出現於「可並行群組」或「本輪未選入」清單，若其衝突邊確實排除了某個鄰居，改於輸出第三段「施工中佔用節點」列出（見下方輸出格式範例）。Stale in_progress 票（session 已中斷或逾時）不納入 seed，維持可被視為未佔用，與 `stale-list` 章節「仍可列示接手」判準一致，避免同一票在 `list` 視圖顯示可接手、在 `--groups` 視圖卻擋住鄰居的矛盾指引。

**Why**：連通分量整塊視為必須序列化是過度保守判定——傳遞關聯不代表互斥，只有直接衝突的節點對才真的不能同時進行。**Consequence**：「本輪未選入」不是佇列、系統不代為排入下一輪，未選入不代表彼此須序列，只是與本批已選票有直接衝突。**Action**：本批票認領後可重跑 `ticket track runqueue --groups`——認領後的票轉為 in_progress，下一輪衝突圖會將其納為 seed，其衝突邊不隨狀態轉換消失，不會被誤選為可並行（適用條件見下方安全性條件）。

> **多輪重跑的安全性條件**：上述「認領後重跑」的保護僅在**經 `--groups` 查詢**時成立——`track_runqueue.py` 每次 `--groups` 呼叫都重新篩出全部 live in_progress 票並傳入 seed，條件是「決定下一批認領前有跑過 `--groups`」，不是任何形式的認領都自動安全。以下兩種情境不在此保護範圍內，`--groups` 的衝突圖無法涵蓋：
>
> 1. **不經 `--groups` 的手動 `claim`**：直接對某張票下 `ticket track claim` 不會查詢衝突圖。此路徑改由 `lease` 層的自撞警告承接——同一 session 兩輪之間 claim 撞上自己已佔用的檔案會輸出警告，但警告不阻擋 claim，仍需讀者自行判斷是否停手。
> 2. **ANA 型票的宣告預設不貢獻衝突邊**：`where.files` 依 `type` 推導預設意圖，ANA 型票預設為 `read`，衝突判定僅比對 `write` 集合，`read` 集合不建邊。實測顯示約 19.3% 的 ANA 宣告實際仍會寫入其宣告的檔案；這部分票即使已在 in_progress，也不會出現在 `--groups` 的衝突圖中，屬已知假陰性，不因本次修復而消失。
>
> 落在上述兩種情境時，仍建議以 `ticket track conflicts` 自行核對新選出的票與 in_progress 票之間有無 `where.files` 交集。

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

`[heuristic]` 標記代表該衝突僅由 impl→test 擴張啟發式衍生路徑觸發（票面原始宣告的 `where.files` 本身無交集），語意與 `track conflicts` 章節「衝突判定規則」的 `[heuristic]` 相同。

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

### 實作現況

| 層                             | 狀態                                         | 檔案                                                             |
| ------------------------------ | -------------------------------------------- | ---------------------------------------------------------------- |
| 規則面（本章節）               | 已落地                                       | `.claude/skills/ticket/references/track-command.md`（W17-040）   |
| Wave 完成判定                  | 已落地                                       | `.claude/pm-rules/completion-checkpoint-rules.md` L76（W17-037） |
| CLI 排序邏輯（第二層加權實作） | 未實作（若未來發現序列差異造成問題再建 IMP） | `.claude/skills/ticket/ticket_system/commands/track_runqueue.py` |

**典範**：W17-011.1 實作（基礎 runqueue），W17-009 ANA 三視角審查（Evidence/Alternatives/linux）收斂結論；W17-036 軸 C 補強 spawned 加權規則。

## UPDATE 操作

```bash
# 接手 Ticket
/ticket track claim <id>

# 完成 Ticket
/ticket track complete <id>

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
# Status precondition（W3-044 / W1-058）：需 status=in_progress（completed 補 review 亦放行）；
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
# 骨架文字權威來源：ticket_system/commands/track_dispatch.py 的
# SKELETON_TEMPLATE_NORMAL / SKELETON_TEMPLATE_REVIEW；
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

# 身份申報（--as，W1-048）— complete / check-acceptance / set-acceptance 三命令通用
/ticket track complete <id> --as thyme-python-developer        # 申報身份，與 who.current 對照不符即 deny（exit 1）
/ticket track check-acceptance <id> --all --as thyme-python-developer
/ticket track set-acceptance <id> --all-check --as thyme-python-developer
/ticket track complete <id> --as rosemary-project-manager      # PM 身份一律放行（bookkeeping 豁免）
/ticket track complete <id>                                    # 未提供 --as：僅 stderr 警告不阻擋（過渡期向後相容）

# 設定阻擋關係（blockedBy 欄位）
/ticket track set-blocked-by <id> <blocked-by-id>      # 覆寫（設定單一 blockedBy）
/ticket track set-blocked-by <id> <id2> --add          # 追加（去重）
/ticket track set-blocked-by <id> <id2> --remove       # 移除指定 blockedBy

# 設定相關關係（relatedTo 欄位）
/ticket track set-related-to <id> <related-id>         # 覆寫（設定單一 relatedTo）
/ticket track set-related-to <id> <id2> --add          # 追加（去重）
/ticket track set-related-to <id> <id2> --remove       # 移除指定 relatedTo

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
| `check-acceptance <id> 1 2 3`                  | `argparse: unrecognized arguments: 2 3`                           | `set-acceptance <id> --check 1 2 3`   |
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
| priority                    | 無 CLI 命令                                     | 手動編輯 frontmatter                                 |
| dispatch_reason             | 無 CLI 命令                                     | 手動編輯 frontmatter                                 |

**不存在的操作**（禁止嘗試）：

| 錯誤呼叫       | 正確做法                              |
| -------------- | ------------------------------------- |
| `set-status`   | 使用 `claim` / `complete` / `release` |
| `set-priority` | 手動編輯 frontmatter `priority` 欄位  |

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

# 依主題分組排列（0.2.1-W3-805）
/ticket track board --group-by topic
```

### 選項說明

| 選項         | 說明                                              |
| ------------ | ------------------------------------------------- |
| `--version`  | 版本號（自動偵測）                                |
| `--wave`     | 只顯示特定 Wave                                   |
| `--all`      | 顯示所有任務（包含已完成）                        |
| `--group-by` | 分組軸：`wave`（預設）或 `topic`                  |

### 分組軸：`--group-by`

`wave`（預設）為 Wave 分組加 ID 排序，輸出與本旗標引入前逐字相同（以測試斷言鎖定）。

`topic` 依主題分組，一次呈現全部主題連同其票，供「先選主題再選票」的派發決策使用——
`track topics` 只給各主題的票數與 status 分佈，`track topic` 只給單一主題的鏈，兩者皆
無法一次看到所有主題的內容，而票數相同的兩個主題正是內容決定該先做哪個。

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

- Ticket 結構完整性（必填欄位）
- 驗收條件完成度
- 執行日誌填寫狀態
- 子任務完成狀態
- 品質標準符合性

---

## 統一錯誤訊息格式（W17-008.5.2）

`lib/messages.py` 的 `format_error()` 支援雙路徑：

### Legacy 路徑（向後相容）

```python
from ticket_system.lib.messages import ErrorMessages, format_error

format_error(ErrorMessages.TICKET_NOT_FOUND, ticket_id="0.31.0-W4-001")
# => "[Error] 找不到 Ticket 0.31.0-W4-001"
```

### 結構化 Envelope 路徑（推薦給 .5.3+ 後續呼叫）

```python
from ticket_system.lib.messages import ErrorEnvelope, format_error

env = ErrorEnvelope(
    component="track",         # CLI 子命令或模組名
    action="claim",            # 操作動詞
    errno="TICKET_NOT_FOUND",  # 錯誤分類代號
    hint="ticket track list",  # 修復建議（可選）
)
print(format_error(env))
```

輸出：

```text
[Error] __error_envelope_v1__
  component: track
  action: claim
  errno: TICKET_NOT_FOUND
  hint: ticket track list
```

### 版本標記 `__error_envelope_v1__`

Hook 偵測到此標記即視為已套用統一格式，**跳過重複補充**（W17-008.5.5）。grep 可用：

```bash
grep -n "__error_envelope_v1__" .claude/skills/ticket/ticket_system/
```

#### Hook 端跳過機制（`.claude/skills/ticket/hooks/cli-error-feedback-hook.py`）

Hook 在 PostToolUse 攔截 `ticket track` 系列命令的 stderr/stdout，若偵測到 `__error_envelope_v1__` 標記即直接放行，不再附加中文修復引導，避免「argparse 英文 + Hook 中文 markdown」雙軌訊息互相重疊：

```python
# .claude/skills/ticket/hooks/cli-error-feedback-hook.py（節錄；
# 原 skill-cli-error-feedback-hook.py 已於 0.0.1-W1-005 合併刪除）
ENVELOPE_VERSION_MARKER = "__error_envelope_v1__"

def is_envelope_output(stderr: str, stdout: str) -> bool:
    return ENVELOPE_VERSION_MARKER in (stderr or "") or ENVELOPE_VERSION_MARKER in (stdout or "")

# check_skill_cli_error() 內：
if is_envelope_output(stderr, stdout):
    return None  # 已是結構化訊息，跳過 hook 補充
```

**設計後果**：

| 命令輸出 | hook 行為 |
|---------|----------|
| 含 `__error_envelope_v1__`（業務錯誤經 `format_error(ErrorEnvelope)`） | 跳過補充；用戶看到單一結構化訊息 |
| 不含標記（純語法錯誤、legacy str 路徑、未遷移命令） | 補充中文修復建議（保留既有引導體驗） |

---

## CLI 錯誤分類（W17-008.5.4）

`ticket track` 系列命令的 argparse 錯誤分為兩類，由 `ArgparseFormatErrorParser`（`lib/messages.py`）分流：

| 錯誤類別 | 範例 | 輸出路徑 | exit code |
|---------|------|---------|----------|
| **業務錯誤** | `invalid choice` / `invalid <type> value` | `format_error(ErrorEnvelope)` 結構化（含版本標記） | 2 |
| **純語法錯誤** | `unrecognized arguments` / `the following arguments are required` | argparse 預設 POSIX 風格 | 2 |

### 業務錯誤範例

```bash
$ ticket track nonexistent_op
[Error] __error_envelope_v1__
  component: ticket track
  action: parse_args
  errno: INVALID_CHOICE
  hint: argument operation: invalid choice: 'nonexistent_op' (...)
```

### 純語法錯誤範例

```bash
$ ticket track claim
usage: ticket track claim [-h] ... ticket_id
ticket track claim: error: the following arguments are required: ticket_id
```

### 設計理由

- **業務錯誤**反映呼叫端對 CLI 語意的誤解（選錯子命令、傳錯型別），結構化輸出便於 hook 與後續工具偵測
- **純語法錯誤**屬 argparse 通用範疇，保留預設 usage 提示對熟悉 POSIX CLI 的使用者更友善
- 版本標記 `__error_envelope_v1__` 讓 hook 區分「已統一格式」vs「需補充」，可用 `grep` 偵測（見上節）

### 不在本機制範圍

- 業務邏輯錯誤（如 ticket id 不存在）：由各 command 自行用 `format_error` 產出，不經 argparse 路徑
- `commands/create.py` argparse 客製：W17-008.5.3 處理
- Hook 補充邏輯：W17-008.5.5 處理

---

## track stale-list 子命令（W17-200）

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
| `--all` | — | 無作用旗標：預設即掃描全部 active 版本；如需限縮請用 `--version` |
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
- version-agnostic（註冊於 `_create_version_agnostic_handlers()`）
- 復用 `calculate_stale_level`，不重定義閾值或判定邏輯

---

## track stuck-anas 子命令（W17-008.15 方案 D 第 1 項）

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
| `--all` | — | 無作用旗標：預設即掃描全部 active 版本；如需限縮請用 `--version` |

### 判定規則

1. ticket `type == "ANA"` 且 `status == in_progress`
2. `spawned_tickets` 非空（無 spawned 子項的 ANA 不算卡住，可能單純尚未拆分）
3. 全部 `spawned_tickets` 皆存在於 ticket 索引中，且狀態皆為 terminal（spawned ID 若找不到對應票，保守判為未完成，不列入卡住清單）

### 輸出格式

```
────────────────────────────────────────────────────────────
卡住的 ANA（in_progress 且 spawned 全 completed）
────────────────────────────────────────────────────────────
  1. 0.2.1-W3-050  分析 XXX 根因
      spawned=3 全 completed → 可考慮 ticket track complete 0.2.1-W3-050
```

無符合條件時輸出「（無卡住的 ANA）」，與 `activity`/`conflicts`/`onboard`/`stale-list` 同款空狀態字面樣式（見「空狀態字面規範」章節）。

### Exit code

固定回傳 `0`（純查詢，無業務拒絕或錯誤分支）。

### 設計約束

- version-agnostic（註冊於 `_create_version_agnostic_handlers()`）
- 復用 `ticket_loader.list_tickets` / `get_active_versions`，不重寫版本聚合邏輯
- 僅提示「可考慮 complete」，不自動執行——是否真正卡住（vs 刻意保留分析未結案）由 PM 判斷

---

## track dashboard 子命令（W10-114 / W10-113 M1+M4'）

PM 接手新 session 的聚合視圖。一次回傳 in_progress + top N ready + stale 三章節，Ready 章節含可直接 claim 的編號（`[1]` `[2]` `[3]`），免拼 ID 即可 claim。

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
  - 0.18.0-W10-116  更新 ticket SKILL.md 補 format 可選值 list 預設行為 dashboard 命令說明  (started_at: 2026-05-13T09:32:20, agent: rosemary-project-manager)

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

W10-113 ANA 量測：原 `/ticket` 裸命令流程從入口到顯示待辦需 **7 個 tool call**（含 1 次 `--format` 試錯與 5 次可消除的重複呼叫）。Dashboard 將此降至 **3 個 tool call**（dashboard + claim by number + 後續動作），符合 `/ticket` 與 resume 系統「加速 PM 接手」的原始設計目的。

### 與其他視圖的差異

| 命令 | 視角 | 主要消費者 |
|------|------|-----------|
| `dashboard` | 整合（in_progress + ready + stale） | PM 接手新 session（**首選**） |
| `runqueue` | 純可執行清單（blockedBy=[]） | 「下一個該做哪個」 scheduler 決策 |
| `list` | 通用 ticket 篩選 | grep / 自動化腳本 / 細部過濾 |
| `stale-list` | 純 stale 列舉（pending 依 created 天數） | stale ticket 清理批次 |

### 設計約束

- 內部複用 `track_runqueue` 的排序與 unblocked 判定（`_priority_rank` / `_is_unblocked_pending` / `_filter_by_wave` / `_compute_readiness`），不重複實作
- stale 判定複用 `lib/staleness.is_stale_in_progress`（in_progress 分鐘粒度），與 `stale-list` 的 pending 天數粒度互補不衝突
- 編號 `[1] [2] [3]` 僅出現在 Ready 章節，避免與 in_progress 章節混淆

---

## track list 子命令（W10-115 / W10-113 M3）

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
| `--top` | `10` | 限制最多 N 筆，依 `priority(P0>P1>P2>P3) → created → id` 排序 |
| `--all` | False | 取全量（覆蓋 `--top`；與 `--top` 共存時 `--all` 優先並 emit warning） |
| `--version` | None | 指定版本（預設自動偵測 active） |

### 排序規則

W10-115 引入的預設排序：

1. **priority 排序**：P0 > P1 > P2 > P3（未指定 priority 視為 P3）
2. **created 排序**：同 priority 內 ISO 8601 時間升序（早建立的優先）
3. **id 排序**：同 created 時間內字典序（穩定排序）

`--all` 旗標跳過排序與限制，輸出純粹按檔案系統載入順序。

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
| PM 新 session 接手 | `dashboard` | 一次看到 in_progress + ready + stale 三章節 |
| 細部篩選（特定 wave/status/format） | `list` | flag 組合彈性高 |
| 自動化腳本（pipe 到其他命令） | `list --format ids` | 純 ID 輸出無裝飾 |
| 「下一個該做哪個」決策 | `runqueue` | 含關鍵路徑 / DAG 視圖

---

## track dispatch-validate 子命令（W17-003）

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

### Exit code

| code | 意義 |
|------|------|
| 0 | 全部規則通過 |
| 1 | 軟性警告（規則 2/3/4 至少一項違反） |
| 2 | 硬性失敗（規則 1 違反、ticket 不存在、IO/YAML 錯誤） |

### 設計邊界

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

## track dispatch-readiness 子命令（W17-053）

派發前認知負擔閾值與綜合就緒度檢查。讀取 ticket frontmatter `where.files`
與 Context Bundle section 自動計算三項核心指標，輸出 pass/warn/fail 與
建議。**與 `dispatch-check`（活躍派發狀態，W10-017.2）和 `dispatch-validate`
（CB 合理性，W17-003）職責正交**，獨立子命令不互相干擾。

**Why**：派發前缺乏統一 CLI 入口檢查 ticket 是否符合認知負擔閾值，PM 需
手動對照 `.claude/rules/core/cognitive-load.md` 與 `cognitive-load-execution-details.md`
判斷拆分需求，違反摩擦力方法論執行階段減摩擦原則（W17-049 ANA linux 視角）。

**Consequence**：缺少自動化檢查會讓 PM 偶爾遺漏拆分判斷，將過大任務派
給代理人；3b 派發後常見症狀包含代理人 commit 遺漏部分職責、回合耗盡前
只完成一半、跨檔不一致導致測試失敗。

**Action**：派發 3b 實作 ticket 前以本命令自檢；exit 0 直接派發、exit 1
評估是否豁免（如跨進程同步修復條款）、exit 2 必須拆分後重新派發。

### 用法

```bash
ticket track dispatch-readiness <ticket_id>
```

### 三項閾值

| 閾值 | 取得方式 | 軟上限 | 強制拆分 |
|------|---------|-------|---------|
| 1. 功能職責數（以 acceptance 條目近似） | `acceptance` 欄位計數 | > 2 | > 4 |
| 2. 修改檔案數 | `where.files` 欄位計數 | > 5 | > 10 |
| 3. Context Bundle tokens（以 chars/4 近似） | Context Bundle section 字元數 | > 3000 | > 5000 |

> **閾值來源**：`.claude/references/cognitive-load-execution-details.md`「3b
> 派發前閾值」三項核心指標。閾值 1「功能職責數」CLI 無法精確自動推導，
> 沿用 acceptance 條目作為近似訊號，最終由 PM 判定。
>
> **近似性警告（W17-213）**：acceptance 若含「跑測試」「補文件」「執行驗證」
> 等驗證類條目，會讓 acceptance 條目數高於實際功能職責數（高估）；反之，若
> 多個職責被合併寫成單一 acceptance（低估），也會偏離真值。CLI 僅作近似訊號，
> 達 WARN/FAIL 時 PM 應手動覆核 acceptance 是否反映真實職責數，再決定是否拆分。

### Exit code

| code | 意義 |
|------|------|
| 0 | 三項閾值全數通過 |
| 1 | 軟性警告（任一項超軟上限但未達強制拆分） |
| 2 | 硬性失敗（任一項超強制拆分閾值 / ticket 不存在 / IO/YAML 錯誤） |

**重要**：本命令 exit code 語意**不與** `dispatch-check`（W10-017.2，exit
1 = 有活躍派發）和 `dispatch-validate`（W17-003，exit 1 = CB 軟警告）共享；
呼叫端必須以命令名稱判別語意，禁止以 exit code 跨命令解讀。

### 設計邊界

- **不**修改 ticket，僅輸出診斷
- **不**取代 hook / scheduler 的執行控制
- **不**觸碰既有 `dispatch-check`（W10-017.2）與 `dispatch-validate`（W17-003）
- 閾值 1 為近似訊號（acceptance 條目 ≠ 功能職責數），最終拆分判斷由 PM 決定
- Context Bundle section 不存在時閾值 3 視為 0 tokens 通過

### 跨進程同步修復豁免

若 ticket 符合「跨進程同步修復」全部 5 特徵（見 `cognitive-load-execution-details.md`
「跨進程同步修復豁免條款」），可豁免閾值 1，本命令僅供 PM 參考，不應視
為強制阻擋訊號。

### 範例

```bash
$ ticket track dispatch-readiness 0.18.0-W17-053
dispatch-readiness 0.18.0-W17-053:
  [WARN] 閾值 1 功能職責數（acceptance 近似）: acceptance 條目 3 > 2（軟警告；建議拆分為多個 ticket）
  [PASS] 閾值 2 修改檔案數（where.files）: where.files 3 ≤ 5
  [PASS] 閾值 3 Context Bundle tokens: Context Bundle ~250 tokens ≤ 3000
[WARN] 軟性警告：建議審視拆分必要性
```

---

## track sessions 子命令（multi-PM 協調層 Phase 1，issue tarrragon/claude#77）

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
- 內容 schema（v1）：`sessions.<session_id>` 含 `name` / `project` / `registered_at` / `heartbeat_ts` / `tickets` / `files` / `parent_session_id`
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

- version-agnostic（註冊於 `_create_version_agnostic_handlers()`），不需 active version
- 僅列 `project` 欄位等於當前 `git rev-parse --show-toplevel` 的 session（同專案篩選；git 不可用時不篩選，保留全部）
- stale 判定閾值固定 30 分鐘（`STALE_THRESHOLD_MINUTES`）；`reclaimable` 欄位僅為輕量標記（heartbeat 判準），實際執行 reclaim（轉回 pending + 清 lease）另見「track reclaim 子命令」章節（multi-PM 協調層 Phase 3）
- Registry Schema 契約 v1 為 hooks 與 CLI 兩職責共同 SSOT，本命令不得自行變更 schema

---

## track reclaim 子命令（multi-PM 協調層 Phase 3，issue tarrragon/claude#77）

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

`--confirm` 是否放行完全取決於三查結果，三查任一命中或無法判定即拒絕（與 `--confirm` 是否給出無關——`--confirm` 只決定「三查全過後是否真的落地」，不能覆蓋三查結果）：

| 查 | 判定內容 | 命中條件 |
|----|---------|---------|
| 1. 未合併分支 | `git branch --no-merged` 是否存在含 ticket_id 的分支名 | 存在即命中 |
| 2. 髒檔交集 | `git status --porcelain` 路徑與票面 `where.files` 是否有交集 | 有交集即命中 |
| 3. 缺 Exit Status | 票面 `Exit Status` 章節是否仍為佔位符或未找到 | 缺失/佔位符即命中 |

第 1、2 查依賴 git 查詢；查詢本身失敗（非「查到零筆」）時標記為「無法判定」，與「通過」區分對待——查詢失敗不可視為通過（防止 fail-open 誤放行）。三查任一「命中」或「無法判定」，鑑識結論即為未通過，`--confirm` 不生效。

**設計取捨（精確度優先，避免文件缺失時誤判為功能故障）**：一個真正硬崩潰的 session（尚在做事時被中斷）幾乎必然同時觸發第 3 查（來不及寫 Exit Status）、且高機率觸發第 1 或第 2 查（有未合併分支或未 commit 的髒檔）。因此 `--confirm` 的典型放行場景不是「找回真正崩潰遺失的票」，而是「session 已正常寫完 Exit Status、只是 lease 未被清除」這類乾淨收尾但 registry 殘留的情形。若 `--confirm` 對某張明顯已死的 session 持票持續拒絕，這是三查刻意保守的預期行為，非 bug。

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

`runqueue` 的 `[RECLAIMABLE]` 標記經 `is_lease_reclaimable` 判定：持有者 session heartbeat 逾 TTL，**或** registry 已載入但未追蹤此票 lease（含 graceful SessionEnd 釋放後 entry 已刪除的情形）。`sessions` 的 `reclaimable` 欄**不呼叫**本函式，而是 `track_sessions.py` 自算（僅 `status == "STALE"` 才列），兩者判準已分岔，非共用同一實作——差異來源：`is_lease_reclaimable` 服務於「哪些 in_progress 票值得提示接手」，`sessions` 的 `reclaimable` 欄服務於「哪個 session 本身已逾時」，語意對象不同。兩者皆**不含**本命令的 ghost 鑑識三查——鑑識涉及 git 呼叫，不適合逐票渲染表格時觸發。因此「`sessions`/`runqueue` 顯示為可 reclaim 候選」與「`reclaim --confirm` 實際放行」是兩層判定，前者是列表級的粗篩提示，後者才是逐票的精確判定；粗篩顯示候選不保證 `--confirm` 會放行。

### Exit code

| 值 | 說明 |
|----|------|
| 0 | dry-run 鑑識通過 / `--confirm` 且落地成功 |
| 1 | 找不到 ticket、票非 in_progress、有 FRESH session 佐證、鑑識未通過、或落地時票面更新失敗 |

### 設計約束

- 外層流程跨兩把獨立鎖，非單一原子操作：`check_reclaimable` 讀 registry（無鎖快照）→ ghost 鑑識（純讀取，無鎖）→ 落地持 ticket md 的 `file_lock` → 之後才持 registry 的 `_registry_lock` 清 lease。理論上存在窄視窗（owner session 可能在鑑識後、落地前恢復心跳），影響侷限於「STALE 誤判為短暫失聯的 session 遺失一張已無在途工作證據的票」，非資料損毀風險
- registry 未追蹤該票 lease 時仍允許依 ghost 鑑識判定（registry 缺失非阻擋條件，同 Registry Schema 契約「損毀/缺檔處置」降級語意）

---

## track activity 子命令（multi-PM 協調層 Phase 2，L1 新鮮度）

票面進度是事件驅動更新（claim/append-log/complete），事件間有 27-35 分鐘常態靜默窗口，靜默本身無法判斷「在做/卡住/session 已死」。`activity` 從既有副作用機械推導每張 `in_progress` 票的最後活動時間，把靜默從歧義降為可判定狀態。

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

**父子票邊界**：父票 ID 可能恰為子票 ID 的字首子字串（如父票 ID 去掉 `.N` 尾綴後即為子票 ID）。`git log --grep` 加 `--fixed-strings`（避免點號被當正規表示式萬用字元），並在 Python 端逐一驗證候選 commit 的 subject 是否為「獨立引用」（命中後緊接 `.` + 數字視為子票引用而跳過），避免父票的 `git_commit` 訊號被子票的 commit 覆蓋；全數候選皆非獨立引用時該源視為缺（`no-signal` 候選之一，不影響其餘兩源）。

### 輸出格式（table）

```
=== Ticket Activity (L1) ===
  id            last_activity              source      agent
  ---------------------------------------------------------------
  0.2.1-W3-001  2026-08-18T10:00:00+00:00  git_commit  thyme-python-developer
```

### 設計約束

- version-agnostic，預設已掃描全部 active 版本的 `in_progress` 票；`--all` 為無作用旗標，預設即掃描全部 active 版本，如需限縮請用 `--version`
- 髒檔路徑比對用 `PurePosixPath` 前綴判定，非 `string.startswith`（避免 `lib/foo` 誤命中 `lib/foobar.dart`）  <!-- skill-residue-exempt: 說明路徑比對規則的示意路徑，非本專案實際檔案 -->
- git 呼叫一律經 `.claude/lib/git_utils.run_git_command`（已內建 `--no-optional-locks`，避免與並行 PM session 競爭 `.git/index.lock`），lazy import 比照 `track_hook_health.py` 的 `_find_claude_dir()` 模式
- `attribute_dirty_files()` 為髒檔歸屬第三源的獨立輸出函式，供 `onboard` 命令複用，不重算最新活動時間

---

## track conflicts 子命令（multi-PM 協調層 Phase 2，where.files 交集）

盲測實證：宣告 `where.files` 吻合度僅 3/10，七成 completed 票的實際 commit 超出宣告範圍，主導缺漏是「宣告實作檔、漏宣告伴生測試檔與關聯模組」。純宣告值交集判定的錯誤方向是 false negative（宣告互斥、實際相撞），`conflicts` 因此內建 impl→test 擴張啟發式，擴大偵測面。

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
4. 與 pm-registry 的 `files` 欄位交叉比對：僅採 **FRESH session**（heartbeat 未逾 30 分鐘）的宣告，`in_progress` 票若與其認領 session 的 registry files 完全無交集，輸出 stderr 警告（不影響 exit code）；STALE session 的殘留宣告排除在外，避免死 session 舊宣告誤觸發警告。警告文字附後果與下一步：「衝突判定僅採 where.files；請校正票面宣告或重跑 claim」——說明本命令的判定基準只看票面宣告（不讀 registry），並指引兩種修正路徑
5. `[heuristic]` 標記：衝突僅由擴張啟發式衍生路徑觸發（原始宣告值本身無交集）

### Python 測試路徑推導

本專案 `tests/` 目錄一律為套件根目錄的兄弟層（如 `ticket_system/tests/` 對應 `ticket_system/commands/`、`ticket_system/lib/` 等子目錄下的模組；`hooks/tests/` 對應 `hooks/` 下直接放置的檔案），並非緊鄰檔案自身目錄下的子目錄。啟發式逐層往上檢查每個祖先目錄是否有 `tests` 兄弟目錄實際存在於檔案系統，取最近（最深）一個；專案內找不到任何符合的 `tests/` 兄弟目錄時不猜測、不衍生候選。

> **與覆核指令的區別**：以上是 `conflicts` 啟發式「推測」原始碼對應測試檔位置的演算法（用於偵測潛在衝突），非本 ticket skill 覆核自身測試套件時該如何執行測試。本 skill 的測試現況是 `tests/`（skill 根層）與 `ticket_system/tests/`（package 內層）兩個目錄並存，並非單一位置；`pyproject.toml` 的 `[tool.pytest.ini_options]` 已用 `testpaths = ["tests", "ticket_system/tests"]` 將兩者統一收斂進同一次 pytest session，唯一標準覆核指令為裸 `pytest`，不帶任何路徑參數：
>
> ```bash
> (cd .claude/skills/ticket && uv run --with pytest --with pyyaml --with filelock python -m pytest -q)
> ```
>
> 顯式指定路徑（如 `pytest tests/` 或 `pytest ticket_system/tests`）會覆蓋 `testpaths`，僅收集單一目錄，另一目錄的測試被靜默漏跑且不觸發任何錯誤或警告；禁止以顯式路徑指令作為覆核依據。詳見 `SKILL.md`「覆核測試指令（skill 自身測試套件）」章節。

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

- version-agnostic，預設已掃描全部 active 版本；`--all` 為無作用旗標，預設即掃描全部 active 版本，如需限縮請用 `--version`
- registry 讀取一律經 `.claude/lib/pm_registry` 的 `get_registry_paths` + `read_registry`，不重寫第三份讀取路徑
- 純目錄級宣告（如 `lib/domain`）與巢狀檔案級宣告天然會被判為交集——這是已知取捨（issue #77 討論記錄：純目錄級 lease 會造成過度序列化），本命令僅負責偵測呈現，不負責治理宣告粒度

---

## track onboard 子命令（multi-PM 協調層 Phase 2，入場四節彙整）

`/clear` = session 死亡 + 新生。入場不是恢復記憶，是從世界平面重建三問：我是誰 / 同事是誰 / 我手上有什麼。session 啟動已印 30+ hook 輸出牆，`onboard` 把入場資訊收斂為單一固定值表。

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

### 髒檔歸屬設計

呈現方向為 **file -> tickets**（PM 入場真正想知道的是「這個髒檔是誰的」，非「這張票碰了哪些髒檔」——後者在票數多、宣告目錄淺時噪音會被放大）。僅比對 `status == in_progress` 的票（completed/pending 票的髒檔歸屬對「進行式工作」章節語意無意義）。

歸屬採**最長匹配前綴特異度**：精確檔案相符 > 深層目錄相符 > 淺層目錄相符，僅保留特異度最高的票。若最高特異度落在「泛目錄」層級（宣告路徑段數 <= 2，如僅宣告 `.claude/`）且命中票數 > 1，代表這些宣告本身無鑑別力，收斂為單行摘要「泛目錄宣告命中 N 票（無鑑別力）」，不逐票展開；精確檔案層級的多票 tie 是有意義的真實衝突訊號，不收斂。

### Flag 說明

| Flag | 預設 | 說明 |
|------|------|------|
| `--top` | 5 | 可認領建議章節列數上限 |
| `--version` / `--format` | 同 `activity`/`conflicts` | 版本範圍與輸出格式 |
| `--all` | — | 無作用旗標：預設即掃描全部 active 版本；如需限縮請用 `--version` |

### 設計約束

- registry 讀取一律經 `.claude/lib/pm_registry` 的 `get_registry_paths` + `read_registry`，不重寫第三份讀取路徑
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

### 動機

部分 hook 的 `HOOK_NAME` 常數帶 `-hook` 後綴，與其餘同類 hook 的命名慣例
不一致；憑慣例猜測名稱查 liveness 記錄得到「0 筆」，此結果與「hook 未
觸發」這個合法結論無法區分，會產生有據可查但錯誤的驗收記錄。本命令解析
真實的 `HOOK_NAME`（存在檔案時），並在 0 筆時明確區分兩種原因：

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

### 防護類 hook ticket 的「本 session 實地觸發確認」標準寫法

防護類 hook（阻擋/攔截類，非診斷類）完成後若需在同 session 記錄「確認已
實地觸發」，統一改用本命令**前後差值**取代手動 grep 或憑印象判斷：

```bash
# 觸發前
ticket track hook-liveness .claude/hooks/<hook 檔名>.py --format json > /tmp/before.json

# ……執行會觸發此 hook 的操作……

# 觸發後
ticket track hook-liveness .claude/hooks/<hook 檔名>.py --format json > /tmp/after.json
```

比對 `before.total` 與 `after.total` 是否增加（或 `by_session` 中本 session
的計數是否增加）。Solution / Test Results 記錄時附上解析到的名稱（`resolution.name`）
與前後筆數差值，不記錄未經此命令驗證的口頭斷言。

---

## 空狀態字面規範（track 系列命令通用）

`activity`、`conflicts`、`onboard`、`stale-list`、`stuck-anas`、`dashboard` 六個命令的空狀態一律採全形括號包裹的中文描述句 `（無 XXX）`，不使用英文 `(none)`：`activity` 為「（無 in_progress ticket）」、`conflicts` 為「（無衝突）」、`onboard` 四節分別為「（無活同事）」「（無孤兒 entry）」「（無髒檔）」「（無可認領建議）」、`stale-list` 為「（無符合條件的 stale ticket）」、`stuck-anas` 為「（無卡住的 ANA）」、`dashboard`（In Progress / Handoff Target / Ready Top N / Stale Warning 四區塊）分別為「（無 in_progress ticket）」「（無 handoff target）」「（無可認領建議）」「（無 stale ticket）」。技術術語（`in_progress`、`entry`、`handoff target`）依語言約束規則 4 保留原文，不強制中譯。
