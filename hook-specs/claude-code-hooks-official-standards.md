# Claude Code Hook 系統官方規範總結

## 📖 文件資訊

- **版本**: v1.0
- **建立日期**: 2025-10-09
- **資料來源**: Context7 查詢 Claude Code 官方文件
- **目的**: 確保實作符合官方規範

---

## 🎯 Hook 系統核心機制

### 可用的 Hook 事件

| Hook 事件 | 觸發時機 | 是否有 Matcher | 用途 |
|----------|---------|--------------|------|
| **SessionStart** | Session 啟動時 | ❌ 否 | 載入初始 context |
| **SessionEnd** | Session 結束時 | ❌ 否 | 清理任務 |
| **UserPromptSubmit** | 使用者提交 prompt | ❌ 否 | 控制 prompt 處理 |
| **PreToolUse** | 工具執行前 | ✅ 是 | 權限控制、驗證 |
| **PostToolUse** | 工具執行後 | ✅ 是 | 後處理、驗證 |
| **Stop** | Claude 嘗試停止時 | ❌ 否 | 防止過早停止 |
| **SubagentStop** | Subagent 停止時 | ❌ 否 | Subagent 控制 |
| **PreCompact** | Context 壓縮前 | ❌ 否 | Compact 前處理 |
| **Notification** | 通知事件 | ❌ 否 | 通知處理 |

---

## 📥 Hook 輸入格式

### 通用欄位（所有 Hook）

```json
{
  "session_id": "abc123",
  "transcript_path": "/Users/.../.claude/projects/.../transcript.jsonl",
  "cwd": "/Users/...",
  "hook_event_name": "PreToolUse"
}
```

### PreToolUse 輸入

```json
{
  "session_id": "abc123",
  "transcript_path": "/Users/.../transcript.jsonl",
  "cwd": "/Users/...",
  "hook_event_name": "PreToolUse",
  "tool_name": "Write",
  "tool_input": {
    "file_path": "/path/to/file.txt",
    "content": "file content"
  }
}
```

### PostToolUse 輸入

```json
{
  "session_id": "abc123",
  "transcript_path": "/Users/.../transcript.jsonl",
  "cwd": "/Users/...",
  "hook_event_name": "PostToolUse",
  "tool_name": "Write",
  "tool_input": {
    "file_path": "/path/to/file.txt",
    "content": "file content"
  },
  "tool_response": {
    "filePath": "/path/to/file.txt",
    "success": true
  }
}
```

### UserPromptSubmit 輸入

```json
{
  "session_id": "abc123",
  "transcript_path": "/Users/.../transcript.jsonl",
  "cwd": "/Users/...",
  "hook_event_name": "UserPromptSubmit",
  "prompt": "Write a function to calculate factorial"
}
```

### SessionStart 輸入

```json
{
  "session_id": "abc123",
  "transcript_path": "~/.claude/projects/.../transcript.jsonl",
  "hook_event_name": "SessionStart",
  "source": "startup"
}
```

---

## 📤 Hook 輸出格式

### 方式 1: Exit Code（簡單方式）

| Exit Code | 行為 | stdout | stderr |
|----------|------|--------|--------|
| **0** | 成功 | 顯示給用戶（transcript mode） | - |
| **2** | 阻塞錯誤 | - | 回饋給 Claude 自動處理 |
| **其他** | 非阻塞錯誤 | - | 顯示給用戶，繼續執行 |

**特殊規則**：
- `UserPromptSubmit` 和 `SessionStart` 的 stdout 會加入 context
- Exit code 2 的行為依 Hook 事件而異：
  - `PreToolUse`: 阻止工具呼叫
  - `PostToolUse`: 工具已執行，只回饋 stderr
  - `UserPromptSubmit`: 阻止 prompt 處理，清除 prompt

### 方式 2: JSON 輸出（進階方式）

#### PreToolUse 權限決策

```json
{
  "hookSpecificOutput": {
    "hookEventName": "PreToolUse",
    "permissionDecision": "allow" | "deny" | "ask",
    "permissionDecisionReason": "說明原因"
  }
}
```

- **allow**: 繞過權限檢查，直接允許
- **deny**: 阻止執行
- **ask**: 要求使用者確認

#### PostToolUse 回饋控制

```json
{
  "decision": "block" | undefined,
  "reason": "說明原因",
  "hookSpecificOutput": {
    "hookEventName": "PostToolUse",
    "additionalContext": "額外資訊給 Claude"
  }
}
```

#### UserPromptSubmit 控制

```json
{
  "decision": "block" | undefined,
  "reason": "說明原因",
  "hookSpecificOutput": {
    "hookEventName": "UserPromptSubmit",
    "additionalContext": "額外 context（如果不阻止）"
  }
}
```

#### SessionStart Context 載入

```json
{
  "hookSpecificOutput": {
    "hookEventName": "SessionStart",
    "additionalContext": "載入到 context 的內容"
  }
}
```

**注意**: 多個 Hook 的 `additionalContext` 會串接。

#### Stop/SubagentStop 控制

```json
{
  "decision": "block" | undefined,
  "reason": "必須提供，告訴 Claude 如何繼續"
}
```

### 通用欄位（所有 Hook）

```json
{
  "continue": true,              // 是否繼續（預設 true）
  "stopReason": "string",        // continue=false 時的原因
  "suppressOutput": true,        // 隱藏 stdout（transcript mode）
  "systemMessage": "string"      // 可選的警告訊息
}
```

---

## ⚙️ Hook 配置格式

### settings.json 結構

```json
{
  "hooks": {
    "EventName": [
      {
        "matcher": "ToolPattern",  // 可選，只用於 Tool 相關事件
        "hooks": [
          {
            "type": "command",
            "command": "your-command-here",
            "timeout": 60000  // 可選，預設 60 秒
          }
        ]
      }
    ]
  }
}
```

### Matcher 語法

```json
// 單一工具
"matcher": "Write"

// 多個工具（OR）
"matcher": "Write|Edit|MultiEdit"

// Bash 指令模式
"matcher": "Bash"

// MCP 工具模式
"matcher": "mcp__memory__.*"
"matcher": "mcp__.*__write.*"
```

### 環境變數使用

**重要**: 官方提供 `$CLAUDE_PROJECT_DIR` 環境變數

```json
{
  "hooks": {
    "PostToolUse": [
      {
        "matcher": "Write|Edit",
        "hooks": [
          {
            "type": "command",
            "command": "$CLAUDE_PROJECT_DIR/.claude/hooks/check-style.sh"
          }
        ]
      }
    ]
  }
}
```

### 無 Matcher 的 Hook

```json
{
  "hooks": {
    "UserPromptSubmit": [
      {
        "hooks": [
          {
            "type": "command",
            "command": "/path/to/prompt-validator.py"
          }
        ]
      }
    ]
  }
}
```

---

## 🔧 Hook 腳本實作標準

### Python 範例（PreToolUse）

```python
#!/usr/bin/env python3
import json
import sys

# 1. 從 stdin 讀取 JSON 輸入
try:
    input_data = json.load(sys.stdin)
except json.JSONDecodeError as e:
    print(f"Error: Invalid JSON input: {e}", file=sys.stderr)
    sys.exit(1)

# 2. 提取必要資訊
tool_name = input_data.get("tool_name", "")
tool_input = input_data.get("tool_input", {})

# 3. 執行檢查邏輯
if tool_name == "Write":
    file_path = tool_input.get("file_path", "")

    # 4a. 簡單方式：使用 exit code
    if file_path.endswith(".env"):
        print("Blocked: Cannot write to .env file", file=sys.stderr)
        sys.exit(2)  # 阻塞

    # 4b. 進階方式：使用 JSON 輸出
    if file_path.endswith((".md", ".txt")):
        output = {
            "hookSpecificOutput": {
                "hookEventName": "PreToolUse",
                "permissionDecision": "allow",
                "permissionDecisionReason": "Documentation file auto-approved"
            },
            "suppressOutput": True
        }
        print(json.dumps(output))
        sys.exit(0)

# 5. 預設允許
sys.exit(0)
```

### Bash 範例（PostToolUse）

```bash
#!/bin/bash

# 1. 從 stdin 讀取 JSON 輸入（使用 jq）
INPUT=$(cat)

# 2. 提取資訊
TOOL_NAME=$(echo "$INPUT" | jq -r '.tool_name')
FILE_PATH=$(echo "$INPUT" | jq -r '.tool_input.file_path // empty')

# 3. 執行檢查
if [[ "$TOOL_NAME" == "Write" ]] && [[ "$FILE_PATH" == *.dart ]]; then
    # 4. 執行格式化
    flutter format "$FILE_PATH" 2>&1

    if [ $? -eq 0 ]; then
        echo "✅ Formatted $FILE_PATH"
        exit 0
    else
        echo "❌ Format failed for $FILE_PATH" >&2
        exit 1  # 非阻塞錯誤
    fi
fi

# 5. 預設成功
exit 0
```

---

## 🚨 重要注意事項

### ❌ 常見錯誤

1. **沒有 PostEdit Hook** - 應該使用 `PostToolUse` with matcher `Edit|Write|MultiEdit`
2. **手動定位專案根目錄** - 應該使用 `$CLAUDE_PROJECT_DIR`
3. **不處理 JSON 輸入** - 所有 Hook 必須從 stdin 讀取 JSON
4. **錯誤的決策欄位** - PreToolUse 應使用 `hookSpecificOutput.permissionDecision`，不是 `decision`

### ✅ 最佳實踐

1. **使用 `$CLAUDE_PROJECT_DIR`**
   ```bash
   command: "$CLAUDE_PROJECT_DIR/.claude/hooks/my-hook.sh"
   ```

2. **處理 JSON 輸入**
   ```python
   input_data = json.load(sys.stdin)
   ```

3. **使用正確的決策格式**
   ```json
   {
     "hookSpecificOutput": {
       "hookEventName": "PreToolUse",
       "permissionDecision": "deny"
     }
   }
   ```

4. **設定合理的 timeout**
   ```json
   {
     "type": "command",
     "command": "long-running-script.sh",
     "timeout": 120000  // 2 分鐘
   }
   ```

5. **使用 Exit Code 2 阻塞**
   ```bash
   if [ condition ]; then
       echo "Error message" >&2
       exit 2  # 阻塞並回饋給 Claude
   fi
   ```

---

## 🔍 除錯方法

### 啟用 Debug 模式

```bash
claude --debug
```

### 檢查 Debug Log

```bash
tail -f ~/.claude/debug.log
```

### Debug 輸出範例

```bash
[DEBUG] Executing hooks for PostToolUse:Write
[DEBUG] Getting matching hook commands for PostToolUse with query: Write
[DEBUG] Found 1 hook matchers in settings
[DEBUG] Matched 1 hooks for query "Write"
[DEBUG] Found 1 hook commands to execute
[DEBUG] Executing hook command: <Your command> with timeout 60000ms
[DEBUG] Hook command completed with status 0: <Your stdout>
```

---

## 📚 參考文件

- **官方文件**: `/anthropics/claude-code` (Context7)
- **詳細文件**: `/ericbuess/claude-code-docs` (Context7)
- **Hook 指南**: `docs/hooks.md`
- **Hook 範例**: `docs/hooks-guide.md`

---

**版本**: v1.0
**建立日期**: 2025-10-09
**責任人**: rosemary-project-manager
**狀態**: ✅ 已驗證官方規範
