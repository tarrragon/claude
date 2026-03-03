# Hook Architect 技術參考

本文件包含 basil-hook-architect 的詳細技術參考資料，從主代理人定義外移。
代理人需要查閱時讀取此檔案。

> 主文件：.claude/agents/basil-hook-architect.md

---

## Hook 類型深度理解

### SessionStart / SessionEnd
- **用途**: Session 生命週期管理
- **輸入**: session_id, transcript_path, source
- **輸出**: additionalContext (載入初始 context)
- **特點**: 無 Matcher，每次啟動/結束都執行

### UserPromptSubmit
- **用途**: Prompt 提交前的檢查和 Context 注入
- **輸入**: prompt, session_id, transcript_path
- **輸出**: decision (block/允許), additionalContext
- **特點**: 可阻止 Prompt 處理，stdout 加入 context

### PreToolUse
- **用途**: 工具執行前的權限控制和參數驗證
- **輸入**: tool_name, tool_input
- **輸出**: permissionDecision (allow/deny/ask)
- **特點**: 可阻止工具呼叫，Exit code 2 阻塊

### PostToolUse
- **用途**: 工具執行後的日誌記錄和後處理
- **輸入**: tool_name, tool_input, tool_response
- **輸出**: decision (block), additionalContext
- **特點**: 工具已執行，只能回饋訊息

### Stop / SubagentStop
- **用途**: 防止對話過早停止
- **輸入**: session_id, transcript_path
- **輸出**: decision (block), reason
- **特點**: 可延續對話，要求完成特定工作

---

## UV 單檔模式

### PEP 723 Inline Script Metadata

```python
#!/usr/bin/env -S uv run
# /// script
# requires-python = ">=3.12"
# dependencies = [
#     "jsonschema>=4.0",
# ]
# ///

import json
import sys
```

**優點**: 依賴隔離、可移植性、零配置、UV 快取機制

**注意**: Claude Code 執行 `.py` Hook 時直接使用系統 `python3`，完全忽略 shebang。
shebang 保留供終端機直接執行時使用。

---

## JSON 處理

### stdin 輸入讀取

```python
try:
    input_data = json.load(sys.stdin)
except json.JSONDecodeError as e:
    print(f"Error: Invalid JSON input: {e}", file=sys.stderr)
    sys.exit(1)
```

### hookSpecificOutput 格式

```json
{
  "hookSpecificOutput": {
    "hookEventName": "PreToolUse",
    "permissionDecision": "allow",
    "permissionDecisionReason": "説明原因"
  },
  "suppressOutput": true
}
```

### permissionDecision 控制
- **allow**: 繞過權限檢查，直接允許
- **deny**: 阻止執行
- **ask**: 要求使用者確認

---

## 可觀察性模式

### Bash 日誌記錄

```bash
LOG_DIR="$CLAUDE_PROJECT_DIR/.claude/hook-logs"
LOG_FILE="$LOG_DIR/my-hook-$(date +%Y%m%d-%H%M%S).log"

echo "[$(date '+%Y-%m-%d %H:%M:%S')] Hook 執行開始" >> "$LOG_FILE"
echo "  Tool: $TOOL_NAME" >> "$LOG_FILE"
```

### 追蹤檔案管理

```bash
mkdir -p "$CLAUDE_PROJECT_DIR/.claude/hook-logs/my-hook-reports"
REPORT_FILE="$CLAUDE_PROJECT_DIR/.claude/hook-logs/my-hook-reports/report-$(date +%Y%m%d-%H%M%S).md"
```

---

## 錯誤處理

### 友善錯誤訊息範例

```bash
if [ ! -f "$FILE_PATH" ]; then
    cat >&2 << EOF
錯誤: 檔案不存在
檔案路徑: $FILE_PATH

修復建議:
1. 確認檔案路徑是否正確
2. 檢查檔案是否已刪除

詳細日誌: .claude/hook-logs/
EOF
    exit 2  # 阻塊錯誤
fi
```

### Exit Code 控制

```bash
exit 0  # 成功
exit 2  # 阻塊錯誤（stderr 回饋給 Claude）
exit 1  # 非阻塊錯誤（顯示給用戶，繼續執行）
```

---

## 輸出模板

### Hook 設計文件模板

```markdown
# Hook 名稱: [Hook 名稱]

## 基本資訊
- **Hook 類型**: PreToolUse / PostToolUse / Stop / 等
- **實作語言**: Python / Bash
- **版本**: v1.0

## 目的
[Hook 的業務目的和需求說明]

## 觸發時機
- **Hook 事件**: [事件類型]
- **Matcher**: [Matcher 模式]
- **觸發條件**: [觸發條件說明]

## 輸入格式
[JSON 輸入範例]

## 輸出格式
[JSON 輸出範例和決策說明]

## 實作方式
- **語言選擇原因**: [說明]
- **核心邏輯**: [邏輯說明]

## 測試方法
1. [測試步驟]

## 可觀察性
- **日誌位置**: `.claude/hook-logs/[hook-name]/`
```

### Incident Report 模板

```markdown
# Hook 問題報告

## 問題摘要
- **Hook 名稱**: [Hook 名稱]
- **問題類型**: [故障類型]
- **影響範圍**: [受影響的功能]

## 問題詳情
- **症狀**: [觀察到的問題]
- **錯誤訊息**: [完整錯誤訊息]

## 根本原因分析
- **根本原因**: [根源]

## 修復方案
- **修復方式**: [具體步驟]
- **測試方法**: [驗證修復]

## 預防建議
[如何避免再次發生]
```

---

## 最佳實踐原則

### 1. 單一職責原則
每個 Hook 專注一個明確目標，避免功能重疊。

### 2. 可觀察性優先
詳細記錄所有操作，提供完整的追蹤資訊。Python Hook 使用 hook_utils。

### 3. 單檔隔離原則
使用 UV 確保依賴獨立，提升可移植性。

### 4. 語意化命名原則
命名模式: `[action]-[object]-hook.py`

### 5. 修復模式原則
失敗時提供具體指引（修復步驟 + 日誌位置）。

### 6. 效能考量原則

| 複雜度 | Timeout |
|--------|---------|
| 簡單檢查 | 5-10 秒 |
| 中等複雜度 | 30-60 秒 |
| 複雜處理 | 2-5 分鐘 |

### 7. 向下相容原則

```bash
PROJECT_ROOT="${CLAUDE_PROJECT_DIR:-$(git rev-parse --show-toplevel 2>/dev/null)}"
```

### 8. 測試驅動原則
先設計測試案例，再實作 Hook 邏輯。

---

## 常見陷阱

| 陷阱 | 問題 | 解決 |
|------|------|------|
| 忽略 stdin JSON | 直接用環境變數 | `json.load(sys.stdin)` |
| 錯誤的決策欄位 | PreToolUse 用 `decision` | 用 `permissionDecision` |
| 不用官方環境變數 | 手動定位根目錄 | 用 `$CLAUDE_PROJECT_DIR` |
| 缺少可觀察性 | 無日誌 | hook_utils 或手動 log |
| Timeout 設定不當 | 預設不足/過長 | 依複雜度設定 |

---

## 配置範例

```json
{
  "hooks": {
    "PreToolUse": [
      {
        "matcher": "Write|Edit",
        "hooks": [
          {
            "type": "command",
            "command": "$CLAUDE_PROJECT_DIR/.claude/hooks/my-hook.py",
            "timeout": 60000
          }
        ]
      }
    ]
  }
}
```

---

**Last Updated**: 2026-02-25
**Source**: basil-hook-architect.md v2.1.0 精簡外移
