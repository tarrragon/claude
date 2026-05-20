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
# 可用 section：Problem Analysis / Context Bundle / Solution / Test Results / Execution Log
/ticket track log <id> --section "<Section Name>"

# 列出 Tickets（W10-115：預設 --top 10 by priority；詳見「track list 子命令」）
/ticket track list [--pending|--in-progress|--completed|--blocked] \
                   [--wave <wave>] [--status STATUS [STATUS ...]] \
                   [--format {table,ids,yaml}] [--top N] [--all] \
                   [--version VERSION]

# Dashboard 聚合視圖（W10-114：PM 接手新 session；詳見「track dashboard 子命令」）
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

# 放棄 Ticket
/ticket track release <id>

# 更新 Phase
/ticket track phase <id> <phase> <agent>

# 添加子 Ticket
/ticket track add-child <parent-id> <child-id>

# 設定 5W1H 欄位（僅以下 6 個 set-* 命令）
/ticket track set-who <id> <value>
/ticket track set-what <id> <value>
/ticket track set-when <id> <value>
/ticket track set-where <id> <value>
/ticket track set-why <id> <value>
/ticket track set-how <id> <value>

# 追加執行日誌
# 有效 section: Problem Analysis / Context Bundle / Solution / Test Results / Execution Log / NeedsContext / Exit Status
/ticket track append-log <id> --section "Problem Analysis" "內容"
/ticket track append-log <id> --section "Context Bundle" "PCB 內容（派發前分析結果，PC-040）"
#
# Section 標題容錯（W17-008.9）：
# - 標題比對採 MULTILINE + \s+ 容許多空白 + \s*$ 容尾空白
# - 命中：「## Solution」、「## Solution 」（末尾空白）、「##  Solution」（雙空白）皆 OK
# - 不誤匹配：「## Solutions」、「## Solution alt」不會被視為 Solution
# - SECTION_NOT_FOUND 時錯誤訊息會列出該 ticket 所有現有 ## 標題引導用戶

# 勾選驗收條件（check-acceptance，舊語法）
/ticket track check-acceptance <id> 1                  # 勾選第 1 項（1-based 整數）
/ticket track check-acceptance <id> 1 --uncheck        # 取消勾選第 1 項
/ticket track check-acceptance <id> --all              # 勾選全部驗收條件
/ticket track check-acceptance <id> --all --uncheck    # 取消勾選全部
/ticket track check-acceptance <id> "實作完成"          # 文字搜尋勾選（模糊比對）

# 勾選驗收條件（set-acceptance）
/ticket track set-acceptance <id> --check 1 2 3        # 勾選多個 index（空白分隔，支援 nargs）
/ticket track set-acceptance <id> --uncheck 1 2        # 取消勾選多個 index
/ticket track set-acceptance <id> --all-check          # 勾選全部
/ticket track set-acceptance <id> --all-uncheck        # 取消勾選全部

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
| acceptance                  | `check-acceptance` / `set-acceptance`           | 勾選/取消勾選驗收條件（set-acceptance 明確語意版）   |
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
```

### 選項說明

| 選項        | 說明                       |
| ----------- | -------------------------- |
| `--version` | 版本號（自動偵測）         |
| `--wave`    | 只顯示特定 Wave            |
| `--all`     | 顯示所有任務（包含已完成） |

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

#### Hook 端跳過機制（`.claude/hooks/skill-cli-error-feedback-hook.py`）

Hook 在 PostToolUse 攔截 `ticket track` 系列命令的 stderr/stdout，若偵測到 `__error_envelope_v1__` 標記即直接放行，不再附加中文修復引導，避免「argparse 英文 + Hook 中文 markdown」雙軌訊息互相重疊：

```python
# .claude/hooks/skill-cli-error-feedback-hook.py（節錄）
ENVELOPE_VERSION_MARKER = "__error_envelope_v1__"

def is_envelope_output(stderr: str, stdout: str) -> bool:
    return ENVELOPE_VERSION_MARKER in (stderr or "") or ENVELOPE_VERSION_MARKER in (stdout or "")

# main() 內：
if is_envelope_output(stderr, stdout):
    return EXIT_SUCCESS  # 已是結構化訊息，跳過 hook 補充
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
| `--all` | False | 跨所有 active 版本掃描 |
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
  (none)

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
