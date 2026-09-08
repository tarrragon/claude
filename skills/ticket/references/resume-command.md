# resume 子命令

恢復任務，從 handoff 檔案載入 context。

> **何時讀**：恢復已交接或中斷的任務時——需確認 `/ticket resume <id>` 與 `/ticket resume --list` 的用法、handoff JSON 格式欄位語意，或查詢〈相關 Hook〉三者（SessionStart 提醒／UserPromptSubmit 自動注入停用／Stop 阻止退出）的分工時。**亦由此進入**：`workflow-handoff.md`〈恢復流程決策樹〉節（resume 的完整決策路徑與命令對照，與本檔用法／參數細節互補）。
>
> **同目錄**：`workflow-handoff.md`（恢復決策樹）、`handoff-command.md`（上游建立 `pending/*.json` 的命令）。
>
> **溯源**：匯入時已存在（`f375ae675`），無拆分點。

## 用法

```bash
# 恢復特定任務
/ticket resume <id>

# 列出待恢復任務
/ticket resume --list

# 快捷方式：/ticket（無子命令）走 dashboard-first 流程
/ticket
```

## 恢復機制（顯式觸發）

> 來源：resume 顯式觸發機制（見 CHANGELOG 對應條目）

### 三個入口的分工

- **SessionStart hook**（`handoff-reminder-hook.py`）：被動提醒，顯示待恢復任務清單
- **`/ticket`**（裸指令）：走 dashboard-first 流程 → AskUserQuestion 讓用戶選擇（詳見 SKILL.md〈無子命令時的預設行為（dashboard-first）〉；僅當 dashboard 無 in_progress 也無 ready 時才 fallback 到完整 pending/in_progress 清單，handoff 提醒本身不觸發此流程）
- **`/ticket resume <id>`**：明確恢復指定任務，載入 context + 標記 resumed_at

### 恢復流程

```
/clear（新 session）
    |
    v
SessionStart hook → 顯示「Handoff 提醒」（僅提醒）
    |
    v
用戶輸入
    |
    +-- /ticket → dashboard-first → AskUserQuestion 選擇（走 dashboard-first）
    +-- /ticket resume <id> → 直接恢復
    +-- 其他輸入 → 正常處理，不受干擾
```

## Flag 說明

| 參數 | 說明 |
|------|------|
| `<id>` | Ticket ID（如 `1.0.0-W13-003`） |
| `--list` | 列出所有待恢復任務 |
| `--version` | 指定版本號（可選） |

## handoff JSON 格式

位置：`.claude/handoff/pending/*.json`

```json
{
  "ticket_id": "0.2.1-W3-047",
  "direction": "context-refresh",
  "target_ticket_id": "0.2.1-W3-050",
  "timestamp": "2026-08-07T12:43:21.722828",
  "from_status": "completed",
  "title": "任務標題",
  "what": "任務摘要",
  "chain": {},
  "resumed_at": null,
  "auto_generated": false
}
```

以上取自 `.claude/handoff/archive/` 實例的精簡欄位（`context_bundle` 為額外結構化欄位，記錄 context 萃取結果，實例常見但非本節重點，略；`exit_status` 見下方〈`exit_status` 欄位：票面 Exit Status 章節到 handoff JSON 的橋〉）。

- `direction` 值域（`handoff_utils._KNOWN_DIRECTION_VALUES`）：`to-parent` / `to-child` / `to-sibling` / `context-refresh` / `next-wave` / `auto`
- `resumed_at` 為 `null`：待接手
- `resumed_at` 有 ISO 時間戳：已接手（由 `/ticket resume` 寫入）

### `exit_status` 欄位：票面 Exit Status 章節到 handoff JSON 的橋

`exit_status` 非獨立輸入欄位，而是 `ticket handoff` 建立 JSON 當下，從**來源 ticket** body 的 `## Exit Status` H2 section 抽取而來（`handoff.py:_extract_exit_status_for_handoff`）：剝除樣板 HTML 註解、解析其中的 YAML 區塊（fenced ```yaml 優先，否則整段視為 YAML），取 `exit_status` 或 `status` 子欄位，寫入 handoff JSON 的 `exit_status` 物件。

三個消費端各自的角色（誰寫、誰讀、何時）：

| 角色 | 命令 | 動作 |
|------|------|------|
| 寫入端 | `ticket track set-exit-status` | 把 YAML 寫入來源 ticket body 的 `## Exit Status` 章節（見 `track-command.md`〈track set-exit-status 子命令〉） |
| 橋接端 | `ticket handoff` | 建立 JSON 當下讀該章節，抽取 `status` 寫入 JSON 的 `exit_status` 欄位；fail-open——缺段／YAML 解析失敗／`status` 非合法枚舉一律回 `None`，JSON 省略該欄位，不阻擋 handoff 主流程 |
| 讀取端（JSON） | `ticket track runqueue --context=resume` | 讀 JSON 的 `exit_status.status`，以 `[<status>]` tag 取代 `blockedBy=[]` runnable 標記（見 `track-command.md`〈track runqueue 子命令〉「Exit Status tag」） |
| 讀取端（票面，不經橋接） | `ticket track reclaim` 第 3 查 | 直接讀來源 ticket body 的 `## Exit Status` 章節（不經 handoff JSON），缺失/佔位符為 soft warning，不計入拒絕判定（見 `track-command.md`〈track reclaim 子命令〉） |

**Consequence**：來源 ticket 尚未執行 `set-exit-status` 時，橋接端回 `None`，JSON 省略 `exit_status`；此時 `runqueue --context=resume` 該筆不帶 tag，`reclaim` 第 3 查仍可獨立命中「缺失」（兩者為不同資料來源，非同一次讀取的兩種呈現）。

## 相關 Hook

| Hook | 事件 | 行為 |
|------|------|------|
| `handoff-reminder-hook.py` | SessionStart | 顯示待恢復任務提醒 |
| `handoff-prompt-reminder-hook.py` | UserPromptSubmit | v2.0.0 已停用自動注入，始終 suppressOutput |
| `handoff-auto-resume-stop-hook.py` | Stop | 阻止退出未完成任務的 session；GC 清理已完成 Ticket 的 stale pending JSON |
