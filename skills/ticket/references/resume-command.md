# resume 子命令

恢復任務，從 handoff 檔案載入 context。

> **何時讀**：恢復已交接或中斷的任務時——需確認 `/ticket resume <id>` 與 `/ticket resume --list` 的用法、handoff JSON 格式欄位語意，或查詢〈相關 Hook〉三者（SessionStart 提醒／UserPromptSubmit 自動注入停用／Stop 阻止退出）的分工時。**亦由此進入**：`workflow-handoff.md`〈恢復流程決策樹〉節（resume 的完整決策路徑與命令對照，與本檔用法／參數細節互補）。
>
> **同目錄**：`workflow-handoff.md`（恢復流程的決策樹，決策樹在那份、命令用法與參數細節在本檔）、`handoff-command.md`（建立本檔讀取的 `pending/*.json` 的上游命令）。
>
> **溯源**：本檔於本專案匯入 commit `f375ae675` 時即已存在，本機 git log 對本檔僅見這一筆與本輪 Round 1 finding 修正，未見其他外移點（可用 `git log --oneline -- references/resume-command.md` 查證）。

## 用法

```bash
# 恢復特定任務
/ticket resume <id>

# 列出待恢復任務
/ticket resume --list

# 快捷方式：/ticket（無子命令）走 dashboard-first 流程，見 SKILL.md〈無子命令時的預設行為（dashboard-first）〉
/ticket
```

## 恢復機制（v2.0.0 - 顯式觸發）

### 設計原則

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
    +-- /ticket → dashboard-first → AskUserQuestion 選擇（見 SKILL.md〈無子命令時的預設行為（dashboard-first）〉）
    +-- /ticket resume <id> → 直接恢復
    +-- 其他輸入 → 正常處理，不受干擾
```

## 參數說明

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

以上取自 `.claude/handoff/archive/` 實例的精簡欄位（`context_bundle`／`exit_status` 為額外結構化欄位，分別記錄 context 萃取結果與來源 ticket 的收尾狀態，實例常見但非本節重點，略）。

- `direction` 值域（`handoff_utils._KNOWN_DIRECTION_VALUES`）：`to-parent` / `to-child` / `to-sibling` / `context-refresh` / `next-wave` / `auto`
- `resumed_at` 為 `null`：待接手
- `resumed_at` 有 ISO 時間戳：已接手（由 `/ticket resume` 寫入）

## 相關 Hook

| Hook | 事件 | 行為 |
|------|------|------|
| `handoff-reminder-hook.py` | SessionStart | 顯示待恢復任務提醒 |
| `handoff-prompt-reminder-hook.py` | UserPromptSubmit | v2.0.0 已停用自動注入，始終 suppressOutput |
| `handoff-auto-resume-stop-hook.py` | Stop | 阻止退出未完成任務的 session；GC 清理已完成 Ticket 的 stale pending JSON |
