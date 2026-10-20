# track 子命令（audit、stale-list、stuck-anas、dashboard）

> **用途**：`track` 子命令詳解之一：audit、stale-list、stuck-anas、dashboard。
>
> **同族檔**：`track-command-commit.md`、`track-command-update.md`、`track-command-dispatch.md`、`track-command-session.md`、`track-command-query.md`、`track-command-health.md`。原檔 `track-command.md` 保留檔頭與保留段落，並為各被移走段標保留路由，被移走段標在原檔以同名標題加一行路由保留，既有〈段標〉引用不需改寫。

---

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

> 來源：W17-200 <!-- rule8-exempt: relocation:自 .claude/skills/ticket/references/track-command.md 逐字搬移 -->

列舉 pending 且建立日期超過閾值的 ticket 明細，補 `list` 命令僅顯示彙總計數而無法定位個別 stale ticket 的缺口。

**stale in-progress 章節**（1.5.0-W5-005.7）：table 格式在 pending 表格後追加 stale in_progress 明細——依 frontmatter `started_at` 單平面判定（閾值 `STALE_IN_PROGRESS_HOURS` = 24h，與 runqueue `[STALE]` tag 同源 `is_stale_in_progress`），附 `ticket track release <id>` 釋放提示。`ids` / `yaml` 格式維持 pending-only（pipe 消費者如 `xargs close` 預期 pending 集合，混入 in_progress 會誤傷）。與 `subagent-stop-dispatch-cleanup-hook` 職責分離：hook 在 SubagentStop 事件清理 dispatch-active.json 記錄平面；本命令於查詢時呈現 ticket 世界平面滯留狀態，兩者互不重疊、皆不自動 release。 <!-- rule8-exempt: relocation:自 .claude/skills/ticket/references/track-command.md 逐字搬移 -->

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

> 來源：W17-008.15 方案 D 第 1 項 <!-- rule8-exempt: relocation:自 .claude/skills/ticket/references/track-command.md 逐字搬移 -->

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

> 來源：W10-114 / W10-113 M1+M4' <!-- rule8-exempt: relocation:自 .claude/skills/ticket/references/track-command.md 逐字搬移 -->

PM 接手新 session 的聚合視圖。一次回傳 `[In Progress]` / `[Handoff Target]` / `[Ready Top N]` / `[Stale Warning]` 四區塊，Ready 區塊含可直接 claim 的編號（`[1]` `[2]` `[3]`），免拼 ID 即可 claim。

**`[In Progress]` 條目的 lease 狀態標記**（判準同 registry heartbeat，TTL 固定 30 分鐘、來源 `.claude/lib/pm_registry.py` `STALE_THRESHOLD_MINUTES`，見 `track-command-session.md`「track sessions 子命令」〈欄位定義〉與 `track-command.md`〈滯留判準閾值總表〉）：`[LIVE]` = FRESH session 正在處理，`[RECLAIMABLE]` = 已知無 FRESH session 佐證持有（可能已 STALE，也可能 registry 根本未追蹤此票——含 graceful SessionEnd 釋放後 entry 已刪除的情形，兩者現統一標記，皆須走 `track reclaim` 鑑識判定），無標記 = registry 本身不可用（模組載入失敗 / 非 git 環境 / 讀取降級），無法判定。`[LIVE]` 票不應列入接手選項——活躍 session 正在處理，接手即與其重複處理同一張票（framework issue tarrragon/claude#78）。`[RECLAIMABLE]` 標記與 `list` 視圖〈`[RECLAIMABLE]` 標記〉章節、`track reclaim` 子命令共用同一判準（`lease.is_lease_reclaimable`），詳見「track reclaim 子命令」章節「與 sessions/runqueue 顯示層判定的差異」。

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

Dashboard 將裸 `/ticket` 流程的 tool call 數降至 3 次（dashboard + claim by number + 後續動作），符合 `/ticket` 與 resume 系統「加速 PM 接手」的原始設計目的；量測細節（W10-113 ANA：原流程 7 個 tool call）見 `CHANGELOG.md`。 <!-- rule8-exempt: relocation:自 .claude/skills/ticket/references/track-command.md 逐字搬移 -->

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
