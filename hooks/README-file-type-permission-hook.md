# File Type Permission Hook

## 基本資訊

- **Hook 名稱**: file-type-permission-hook.py
- **Hook 類型**: PreToolUse
- **Matcher**: Edit
- **版本**: v1.0
- **建立日期**: 2025-01-16

## 目的

根據編輯檔案的類型提供差異化的權限控制和提示：
- **Ticket 和 Worklog 檔案**: 需要人工確認（輸出提示訊息）
- **程式碼檔案**: 自動通過，靜默執行（無任何輸出）
- **其他檔案**: 靜默通過

## 觸發時機

- **Hook 事件**: PreToolUse
- **Matcher**: Edit
- **觸發條件**: 使用 Edit 工具編輯任何檔案

## 檔案分類

### Ticket 檔案
需要人工確認的檔案：
```
.claude/tickets/*
```

### Worklog 檔案
需要人工確認的檔案：
```
docs/work-logs/*
```

### 程式碼檔案
自動通過，靜默執行：
```
lib/*
test/*
integration_test/*
```

### 其他檔案
靜默通過。

## 輸入格式

來自 Edit 工具的 JSON 輸入結構：

```json
{
  "tool_name": "Edit",
  "tool_input": {
    "file_path": ".claude/tickets/my-ticket.md",
    "content": "file content",
    "old_content": "original content"
  }
}
```

## 輸出行為

### Ticket/Worklog 檔案

**stderr 輸出**（提示訊息）：
```
[File Permission Guard] 提示: 正在編輯 Ticket/Worklog 檔案

檔案: {file_path}
說明: 此類檔案的修改需要人工審查確認
```

**stdout 輸出**（JSON 格式）：
```json
{
  "hookSpecificOutput": {
    "hookEventName": "PreToolUse",
    "permissionDecision": "allow",
    "permissionDecisionReason": "TICKET/WORKLOG 檔案編輯提示已發送，請確認後繼續"
  }
}
```

**Exit Code**: 0（允許執行）

### 程式碼檔案 / 其他檔案

**無任何輸出**（靜默通過）

**Exit Code**: 0（允許執行）

## 實作細節

### 核心邏輯

1. 讀取 Edit 工具的 JSON 輸入
2. 從 `tool_input.file_path` 提取檔案路徑
3. 根據路徑判斷檔案類別
4. 根據檔案類別決定行為：
   - Ticket/Worklog: 輸出提示訊息 + 允許執行
   - 程式碼/其他: 靜默允許執行

### 依賴項目

- Python 3.11+ 標準庫（無外部依賴）

### 日誌位置

Hook 執行日誌記錄在：
```
.claude/hook-logs/file-type-permission/file-type-permission-YYYYMMDD.log
```

## 配置

在 `.claude/settings.local.json` 中配置：

```json
{
  "hooks": {
    "PreToolUse": [
      {
        "matcher": "Edit",
        "hooks": [
          {
            "type": "command",
            "command": "$CLAUDE_PROJECT_DIR/.claude/hooks/file-type-permission-hook.py",
            "timeout": 10000
          }
        ]
      }
    ]
  }
}
```

## 測試驗證

### 語法檢查

```bash
python3 -m py_compile .claude/hooks/file-type-permission-hook.py
```

### 功能測試 - Ticket 檔案

```bash
echo '{
  "tool_name": "Edit",
  "tool_input": {
    "file_path": ".claude/tickets/test.md",
    "content": "test"
  }
}' | python3 .claude/hooks/file-type-permission-hook.py
```

預期：輸出提示訊息到 stderr，包含 permissionDecision: "allow"

### 功能測試 - 程式碼檔案

```bash
echo '{
  "tool_name": "Edit",
  "tool_input": {
    "file_path": "lib/main.dart",
    "content": "test"
  }
}' | python3 .claude/hooks/file-type-permission-hook.py
```

預期：無任何輸出，exit code 0

### 功能測試 - Worklog 檔案

```bash
echo '{
  "tool_name": "Edit",
  "tool_input": {
    "file_path": "docs/work-logs/v1.0.0/worklog.md",
    "content": "test"
  }
}' | python3 .claude/hooks/file-type-permission-hook.py
```

預期：輸出提示訊息到 stderr，包含 permissionDecision: "allow"

## 可觀察性

### 執行日誌格式

```
[2025-01-16 10:30:00] 提示: TICKET 檔案 - .claude/tickets/my-ticket.md
[2025-01-16 10:30:01] 允許: code 檔案 - lib/main.dart
[2025-01-16 10:30:02] 警告: 無法取得 file_path
```

### 除錯

- 檢查 `.claude/hook-logs/file-type-permission/` 目錄下的日誌檔案
- 日誌包含所有 Hook 執行記錄和判斷邏輯
- 錯誤處理：JSON 解析錯誤、缺失欄位等均記錄到日誌

## 錯誤處理策略

| 情況 | 處理方式 | Exit Code |
|------|--------|----------|
| 無法解析 JSON | 記錄錯誤，直接允許 | 0 |
| 缺失 file_path | 記錄警告，直接允許 | 0 |
| 非 Edit 工具 | 記錄跳過訊息，直接允許 | 0 |
| 執行時異常 | 記錄異常，直接允許 | 0 |

## 設計特點

1. **非阻塞設計**: 所有錯誤情況都返回 exit code 0，確保不阻塊編輯操作
2. **靜默通過**: 程式碼檔案編輯無任何輸出，不干擾開發流程
3. **選擇性提示**: 只為需要確認的檔案輸出提示訊息
4. **詳細日誌**: 所有操作都記錄到日誌檔案，方便追蹤和除錯

## 參考資料

- [Hook 系統快速參考]($CLAUDE_PROJECT_DIR/.claude/hook-system-reference.md)
- [Hook 系統方法論]($CLAUDE_PROJECT_DIR/.claude/methodologies/hook-system-methodology.md)
- [PreToolUse Hook 規範]($CLAUDE_PROJECT_DIR/.claude/hook-specs/claude-code-hooks-official-standards.md)
