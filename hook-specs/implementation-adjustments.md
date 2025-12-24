# Hook 實作規格調整建議

## 📖 文件資訊

- **版本**: v1.0
- **建立日期**: 2025-10-09
- **目的**: 基於官方規範調整實作設計
- **參考**: `claude-code-hooks-official-standards.md`

---

## 🎯 主要調整項目

### 1. ❌ 移除不存在的 Hook 事件

**問題**: 原規格使用了 `PostEdit Hook`，但官方沒有這個事件。

**修正**:
- 使用 `PostToolUse` Hook
- Matcher 設定為 `Edit|Write|MultiEdit`

**Before**:
```json
{
  "hooks": {
    "PostEdit": [...]  // ❌ 不存在
  }
}
```

**After**:
```json
{
  "hooks": {
    "PostToolUse": [
      {
        "matcher": "Edit|Write|MultiEdit",
        "hooks": [...]
      }
    ]
  }
}
```

---

### 2. ✅ 使用官方提供的環境變數

**問題**: 原規格手動定位專案根目錄。

**修正**: 使用官方提供的 `$CLAUDE_PROJECT_DIR`。

**Before**:
```bash
# 手動定位
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
```

**After**:
```bash
# 使用官方環境變數
PROJECT_ROOT="$CLAUDE_PROJECT_DIR"
```

**配置範例**:
```json
{
  "hooks": {
    "PostToolUse": [
      {
        "matcher": "Write|Edit",
        "hooks": [
          {
            "type": "command",
            "command": "$CLAUDE_PROJECT_DIR/.claude/hooks/main-thread-check.sh"
          }
        ]
      }
    ]
  }
}
```

---

### 3. 🔄 實作標準 JSON 輸入處理

**問題**: 原規格未明確處理 JSON 輸入。

**修正**: 所有 Hook 腳本必須從 stdin 讀取並解析 JSON。

#### Python 標準模板

```python
#!/usr/bin/env python3
import json
import sys

def main():
    # 1. 讀取 JSON 輸入
    try:
        input_data = json.load(sys.stdin)
    except json.JSONDecodeError as e:
        print(f"Error: Invalid JSON input: {e}", file=sys.stderr)
        sys.exit(1)

    # 2. 提取必要資訊
    hook_event = input_data.get("hook_event_name", "")
    tool_name = input_data.get("tool_name", "")
    tool_input = input_data.get("tool_input", {})

    # 3. 執行檢查邏輯
    # ...

    # 4. 回傳結果（Exit code 或 JSON）
    sys.exit(0)

if __name__ == "__main__":
    main()
```

#### Bash 標準模板

```bash
#!/bin/bash

# 1. 讀取 JSON 輸入（需要 jq）
INPUT=$(cat)

# 2. 提取必要資訊
HOOK_EVENT=$(echo "$INPUT" | jq -r '.hook_event_name')
TOOL_NAME=$(echo "$INPUT" | jq -r '.tool_name // empty')
FILE_PATH=$(echo "$INPUT" | jq -r '.tool_input.file_path // empty')

# 3. 執行檢查邏輯
# ...

# 4. 回傳結果
exit 0
```

---

### 4. 📤 使用正確的決策控制格式

**問題**: 原規格未使用官方的 `hookSpecificOutput` 格式。

**修正**: 使用正確的 JSON 輸出格式。

#### PreToolUse 權限決策

```json
{
  "hookSpecificOutput": {
    "hookEventName": "PreToolUse",
    "permissionDecision": "deny",
    "permissionDecisionReason": "主線程禁止修改程式碼"
  },
  "suppressOutput": true
}
```

#### PostToolUse 回饋

```json
{
  "decision": "block",
  "reason": "發現架構問題，需要修正",
  "hookSpecificOutput": {
    "hookEventName": "PostToolUse",
    "additionalContext": "檔案 X 違反 Clean Architecture 原則"
  }
}
```

#### UserPromptSubmit Context 注入

```python
# 方式 1: 簡單輸出（stdout 會加入 context）
print("Current time: 2025-10-09 14:00:00")
sys.exit(0)

# 方式 2: JSON 輸出
output = {
    "hookSpecificOutput": {
        "hookEventName": "UserPromptSubmit",
        "additionalContext": "Current time: 2025-10-09 14:00:00"
    }
}
print(json.dumps(output))
sys.exit(0)
```

---

### 5. ⚠️ 正確使用 Exit Code

**修正**: 理解不同 Exit Code 的行為。

| Exit Code | 用途 | 行為 |
|----------|------|------|
| **0** | 成功 | stdout 顯示給用戶（或加入 context） |
| **2** | 阻塞錯誤 | stderr 回饋給 Claude 處理 |
| **1, 3-255** | 非阻塞錯誤 | stderr 顯示給用戶，繼續執行 |

#### Exit Code 2 各 Hook 行為

| Hook 事件 | Exit Code 2 行為 |
|----------|-----------------|
| `PreToolUse` | 阻止工具呼叫，stderr → Claude |
| `PostToolUse` | 工具已執行，stderr → Claude |
| `UserPromptSubmit` | 阻止處理，清除 prompt，stderr → 用戶 |
| `Stop` | 阻止停止，stderr → Claude |
| `SessionStart` | N/A，stderr → 用戶 |
| `SessionEnd` | N/A，stderr → 用戶 |

---

## 📋 具體調整清單

### Hook 1: 主線程職責檢查

#### 原設計調整

**Before**:
- 整合到 `PostEdit Hook`
- 手動定位專案根目錄

**After**:
- 整合到 `PostToolUse` Hook，matcher: `Edit|Write|MultiEdit`
- 使用 `$CLAUDE_PROJECT_DIR`
- 從 stdin 讀取 JSON 輸入
- 使用 `hookSpecificOutput.permissionDecision` 阻止

#### 實作腳本範例

```bash
#!/bin/bash

# 使用官方環境變數
PROJECT_ROOT="$CLAUDE_PROJECT_DIR"
LOG_FILE="$PROJECT_ROOT/.claude/hook-logs/main-thread-check-$(date +%Y%m%d).log"

# 讀取 JSON 輸入
INPUT=$(cat)

# 提取資訊
TOOL_NAME=$(echo "$INPUT" | jq -r '.tool_name')
FILE_PATH=$(echo "$INPUT" | jq -r '.tool_input.file_path // empty')

# 檢查是否修改 lib/ 程式碼
if [[ "$FILE_PATH" =~ ^lib/.*\.dart$ ]]; then
    echo "[$(date)] ⚠️  主線程違規: 嘗試修改 $FILE_PATH" >> "$LOG_FILE"

    # 輸出 JSON 決策（阻止修改）
    cat <<EOF
{
  "decision": "block",
  "reason": "主線程禁止親自修改程式碼，請使用 Task 工具分派給專業 agent",
  "hookSpecificOutput": {
    "hookEventName": "PostToolUse",
    "additionalContext": "違規檔案: $FILE_PATH\n正確做法: 使用 Task 工具分派任務"
  }
}
EOF

    exit 2  # 阻塞錯誤
fi

# 允許
exit 0
```

---

### Hook 2: 任務分派準備度檢查

#### 配置調整

**Before**:
- 使用不存在的 `Pre-Task-Dispatch Hook`

**After**:
- 使用 `PreToolUse` Hook，matcher: `Task`
- 檢查 Task 工具的 prompt 參數是否包含必要參考文件

#### 配置範例

```json
{
  "hooks": {
    "PreToolUse": [
      {
        "matcher": "Task",
        "hooks": [
          {
            "type": "command",
            "command": "$CLAUDE_PROJECT_DIR/.claude/hooks/task-dispatch-readiness-check.sh"
          }
        ]
      }
    ]
  }
}
```

#### 實作腳本範例

```python
#!/usr/bin/env python3
import json
import sys
import re

def main():
    # 讀取 JSON 輸入
    input_data = json.load(sys.stdin)

    tool_name = input_data.get("tool_name", "")
    tool_input = input_data.get("tool_input", {})

    if tool_name != "Task":
        sys.exit(0)  # 不是 Task 工具，跳過

    # 檢查 prompt 參數
    prompt = tool_input.get("prompt", "")

    # 檢查必要參考文件
    missing_items = []

    if not re.search(r'UC-\d{2}', prompt):
        missing_items.append("UseCase 參考")

    if not re.search(r'Event \d+', prompt):
        missing_items.append("流程圖 Event 參考")

    if not re.search(r'(Clean Architecture|Domain 層|Application 層)', prompt):
        missing_items.append("架構規範引用")

    # 如果缺少必要項目，阻止分派
    if missing_items:
        output = {
            "hookSpecificOutput": {
                "hookEventName": "PreToolUse",
                "permissionDecision": "deny",
                "permissionDecisionReason": f"任務分派準備度不足，缺失: {', '.join(missing_items)}"
            },
            "systemMessage": "請補充完整的參考文件後重新分派任務"
        }
        print(json.dumps(output))
        sys.exit(0)

    # 通過檢查
    sys.exit(0)

if __name__ == "__main__":
    main()
```

---

### Hook 3: 三重文件一致性檢查

#### 原設計保持

**無需調整** - 原設計擴充 `check-version-sync.sh` 是正確的，不涉及 Hook 配置變更。

只需確保腳本使用 `$CLAUDE_PROJECT_DIR`:

```bash
#!/bin/bash

PROJECT_ROOT="$CLAUDE_PROJECT_DIR"
CHANGELOG="$PROJECT_ROOT/CHANGELOG.md"
WORK_LOGS_DIR="$PROJECT_ROOT/docs/work-logs"
```

---

### Hook 4: 階段完成驗證

#### 配置調整

**Before**:
- 使用不存在的 `Phase Completion Hook`

**After**:
- 整合到現有的版本檢查機制
- 或使用 `Stop` Hook 在 Claude 嘗試停止時觸發

#### 方案 A: 整合到 Version Check

在 `check-work-log.sh` 中檢測到階段完成時，呼叫驗證腳本：

```bash
if [[ "$WORK_STATUS" == "COMPLETED" ]]; then
    # 執行階段完成驗證
    "$CLAUDE_PROJECT_DIR/.claude/hooks/stage-completion-validation-check.sh"
    validation_result=$?

    if [ $validation_result -ne 0 ]; then
        echo -e "${RED}❌ 階段完成驗證失敗${NC}"
        exit 1
    fi
fi
```

#### 方案 B: 使用 Stop Hook

```json
{
  "hooks": {
    "Stop": [
      {
        "hooks": [
          {
            "type": "command",
            "command": "$CLAUDE_PROJECT_DIR/.claude/hooks/stage-completion-validation-check.sh"
          }
        ]
      }
    ]
  }
}
```

**Stop Hook 行為**: 如果返回 exit code 2，Claude 會被阻止停止。

---

### Hook 5: 代理人回報追蹤

#### 原設計保持

**無需調整** - 擴充 `pm-trigger-hook.sh` 是正確的。

只需確保使用 `$CLAUDE_PROJECT_DIR`:

```bash
PROJECT_ROOT="$CLAUDE_PROJECT_DIR"
REPORT_TRACKER="$PROJECT_ROOT/.claude/hook-logs/agent-reports-tracker.md"
```

---

## 📊 調整後的實作計畫

### Phase 1: 核心檢查（立即實作）

| 項目 | 調整內容 | 優先序 |
|------|---------|--------|
| **Hook 1: 主線程職責檢查** | 改用 PostToolUse + JSON 輸入 + hookSpecificOutput | 🔴 高 |
| **Hook 4: 階段完成驗證** | 整合到 check-work-log.sh 或使用 Stop Hook | 🔴 高 |

### Phase 2: 準備度檢查（優先實作）

| 項目 | 調整內容 | 優先序 |
|------|---------|--------|
| **Hook 2: 任務分派準備度** | PreToolUse (Task) + JSON 輸入 + permissionDecision | 🟡 中 |

### Phase 3: 一致性檢查（重要實作）

| 項目 | 調整內容 | 優先序 |
|------|---------|--------|
| **Hook 3: 三重文件一致性** | 使用 $CLAUDE_PROJECT_DIR | 🟢 低 |

### Phase 4: 追蹤管理（輔助實作）

| 項目 | 調整內容 | 優先序 |
|------|---------|--------|
| **Hook 5: 代理人回報追蹤** | 使用 $CLAUDE_PROJECT_DIR | 🟢 低 |

---

## ✅ 實作檢查清單

### 所有 Hook 腳本必須符合

- [ ] 從 stdin 讀取 JSON 輸入
- [ ] 使用 `$CLAUDE_PROJECT_DIR` 而非手動定位
- [ ] 使用正確的 `hookSpecificOutput` 格式
- [ ] 正確使用 Exit Code（0/2/其他）
- [ ] 設定合理的 timeout（如需要）
- [ ] 測試 JSON 輸入解析錯誤處理
- [ ] 測試阻塞行為（Exit Code 2）
- [ ] 使用 `claude --debug` 驗證 Hook 執行

### settings.json 配置必須符合

- [ ] 使用正確的 Hook 事件名稱（無 PostEdit）
- [ ] PostToolUse 使用 matcher
- [ ] 使用 `$CLAUDE_PROJECT_DIR` 路徑
- [ ] 設定合理的 timeout
- [ ] 測試 matcher 模式匹配

---

## 🚀 下一步行動

1. **更新實作規格文件** - 修正 `agile-refactor-hooks-specification.md`
2. **開始 Phase 1 實作** - 實作調整後的 Hook 1 和 Hook 4
3. **測試驗證** - 使用 `claude --debug` 測試每個 Hook

---

**版本**: v1.0
**建立日期**: 2025-10-09
**責任人**: rosemary-project-manager
**狀態**: ✅ 已識別所有需要調整的項目
