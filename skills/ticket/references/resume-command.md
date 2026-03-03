# resume 子命令

恢復任務，從 handoff 檔案載入 context。

## 用法

```bash
# 恢復特定任務
/ticket resume <id>

# 列出待恢復任務
/ticket resume --list

# 快捷方式：/ticket（無子命令）自動偵測 pending handoff
/ticket
```

## 恢復機制（v2.0.0 - 顯式觸發）

### 設計原則

- **SessionStart hook**（`handoff-reminder-hook.py`）：被動提醒，顯示待恢復任務清單
- **`/ticket`**（裸指令）：自動偵測 pending handoff → AskUserQuestion 讓用戶選擇
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
    +-- /ticket → 偵測 pending → AskUserQuestion 選擇
    +-- /ticket resume <id> → 直接恢復
    +-- 其他輸入 → 正常處理，不受干擾
```

### 歷史變更

v1.0 使用 `handoff-prompt-reminder-hook.py`（UserPromptSubmit）自動注入 Ticket 完整內容。
v2.0 改為顯式觸發：Hook 自動注入會劫持用戶意圖（任何第一條訊息都被覆蓋），因此停用。

## 參數說明

| 參數 | 說明 |
|------|------|
| `<id>` | Ticket ID（如 `0.31.0-W13-003`） |
| `--list` | 列出所有待恢復任務 |
| `--version` | 指定版本號（可選） |

## handoff JSON 格式

位置：`.claude/handoff/pending/*.json`

```json
{
  "ticket_id": "0.31.0-W13-003",
  "title": "任務標題",
  "direction": "parent_to_child",
  "resumed_at": null
}
```

- `resumed_at` 為 `null`：待接手
- `resumed_at` 有 ISO 時間戳：已接手（由 `/ticket resume` 寫入）

## 相關 Hook

| Hook | 事件 | 行為 |
|------|------|------|
| `handoff-reminder-hook.py` | SessionStart | 顯示待恢復任務提醒 |
| `handoff-prompt-reminder-hook.py` | UserPromptSubmit | v2.0.0 已停用自動注入，始終 suppressOutput |
| `handoff-auto-resume-stop-hook.py` | Stop | 阻止退出未完成任務的 session；GC 清理已完成 Ticket 的 stale pending JSON |
