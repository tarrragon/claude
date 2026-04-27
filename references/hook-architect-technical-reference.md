# Hook Architect 技術參考

本文件包含 basil-hook-architect 的詳細技術參考資料，從主代理人定義外移。
代理人需要查閱時讀取此檔案。

> 主文件：.claude/agents/basil-hook-architect.md

---

## Hook 類型深度理解

### Event 快速索引

| 節奏 | Events |
|------|--------|
| Session lifecycle | `SessionStart`, `InstructionsLoaded`, `SessionEnd` |
| Turn lifecycle | `UserPromptSubmit`, `Stop`, `StopFailure`, `PreCompact`, `PostCompact` |
| Tool lifecycle | `PreToolUse`, `PermissionRequest`, `PermissionDenied`, `PostToolUse`, `PostToolUseFailure` |
| Agent / task lifecycle | `SubagentStart`, `SubagentStop`, `TaskCreated`, `TaskCompleted`, `TeammateIdle` |
| Environment async | `Notification`, `ConfigChange`, `CwdChanged`, `FileChanged`, `WorktreeCreate`, `WorktreeRemove` |
| MCP elicitation | `Elicitation`, `ElicitationResult` |

### SessionStart / SessionEnd
- **用途**: Session 生命週期管理
- **輸入**: session_id, transcript_path, source
- **輸出**: additionalContext (載入初始 context)
- **特點**: 無 Matcher，每次啟動/結束都執行

### InstructionsLoaded
- **用途**: 偵測 CLAUDE.md 或 `.claude/rules/*.md` 載入 context
- **輸入**: session_id, transcript_path, cwd, hook_event_name, load reason
- **輸出**: additionalContext
- **特點**: 可用於規則載入審計、上下文補充，不應阻擋一般流程

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

### PermissionRequest / PermissionDenied
- **用途**:
  - `PermissionRequest`: 權限對話出現時記錄、補充審核或提示
  - `PermissionDenied`: auto mode classifier 拒絕工具時處理 retry 或提示
- **輸入**: tool_name, tool_input, permission context
- **輸出**: permission decision 或 retry decision
- **特點**: 適合權限審計；不得與一般 PreToolUse 安全檢查混淆

### PostToolUse
- **用途**: 工具執行後的日誌記錄和後處理
- **輸入**: tool_name, tool_input, tool_response, **duration_ms**（工具執行毫秒數，v2.1.119+）
- **輸出**: decision (block), additionalContext
- **特點**: 工具已執行，只能回饋訊息；`duration_ms` 可用於效能監控（如偵測執行時間超過閾值）

### PostToolUseFailure
- **用途**: 工具執行失敗後記錄錯誤、分類失敗、提供修復指引
- **輸入**: tool_name, tool_input, failure response, **duration_ms**（工具執行毫秒數，v2.1.119+）
- **輸出**: decision 或 additionalContext
- **特點**: 適合失敗觀測，不適合阻止已發生的工具呼叫；`duration_ms` 可用於記錄失敗前的等待時間

### Stop
- **用途**: 主線程停止時的後處理（檢查未完成工作、強制完成檢查清單等）
- **輸入**: session_id, transcript_path, stop_hook_active
- **輸出**: decision (block), reason
- **特點**: 觸發於主線程結束，**非代理人**結束。可阻擋停止以要求完成特定工作。

### SubagentStop
- **用途**: **代理人（subagent）真正完成時觸發**，提供代理人完成訊號源（清理派發記錄、驗證 commit、廣播完成、handoff 提醒等）
- **輸入**: session_id, transcript_path, stop_hook_active, **agent_id**, **agent_type**, **agent_transcript_path**, last_assistant_message (optional)
- **輸出**: decision (block), reason
- **特點**:
  - 涵蓋前台與 `run_in_background: true` 派發兩種模式
  - `agent_id` 為代理人精準識別碼，可用於匹配 `dispatch-active.json` 等狀態檔案
  - **與 PostToolUse(Agent) 區別**：PostToolUse(Agent) 在 background 派發時於**啟動時**觸發（非完成），SubagentStop 才是真完成訊號

> **重要**：「代理人完成」相關 Hook（清理派發、驗證 commit、廣播狀態、handoff 提醒等）一律使用 SubagentStop，**禁止使用 PostToolUse(Agent)**（時機錯位，詳見 ARCH-019）。

### SubagentStart
- **用途**: subagent spawn 時記錄派發、驗證 prompt、建立觀測狀態
- **輸入**: session_id, transcript_path, cwd, hook_event_name, agent metadata
- **輸出**: decision 或 additionalContext
- **特點**: 啟動時邏輯放這裡或 PreToolUse(Agent)；完成時邏輯仍放 SubagentStop

### TaskCreated / TaskCompleted
- **用途**: task 建立與完成狀態觀測
- **輸入**: task metadata
- **輸出**: `TaskCompleted` 可做完成後提醒或狀態同步
- **特點**: 無 matcher；每次 task 狀態事件都觸發

### StopFailure
- **用途**: turn 因 API error 結束時做觀測或紀錄
- **輸入**: error type（如 rate_limit、authentication_failed、billing_error、server_error）
- **輸出**: output 和 exit code 被忽略
- **特點**: 僅用於記錄，不可設計成流程阻擋

### TeammateIdle
- **用途**: agent team teammate 即將 idle 時補充工作或紀錄狀態
- **輸入**: teammate context
- **輸出**: decision
- **特點**: 無 matcher；只在 agent team 情境有意義

### ConfigChange / CwdChanged / FileChanged
- **用途**:
  - `ConfigChange`: 設定來源變更後重載或審計
  - `CwdChanged`: cwd 改變後做環境管理
  - `FileChanged`: watched file 在磁碟上變更時觸發
- **輸出**:
  - `CwdChanged` / `FileChanged` 可輸出環境或檔案變更後的補充 context
- **特點**: `FileChanged` matcher 是 literal filenames；`CwdChanged` 無 matcher

### WorktreeCreate / WorktreeRemove
- **用途**: worktree 建立/移除生命週期觀測與自訂行為
- **輸入**: worktree path、branch、建立或移除 context
- **輸出**:
  - `WorktreeCreate` 可取代預設 git 行為
  - `WorktreeRemove` 用於清理與記錄
- **特點**: 無 matcher；不可把未審查產出自動丟棄

### PreCompact / PostCompact
- **用途**: compact 前保存恢復提示、compact 後驗證上下文
- **輸入**: trigger (`manual` / `auto`)
- **輸出**: context 或記錄
- **特點**: compact 前後分離；不要把恢復提示生成放在 PostCompact 才做

### Elicitation / ElicitationResult
- **用途**: MCP server 要求使用者輸入與收到回覆的前後處理
- **輸入**: MCP server name、elicitation request 或 result
- **輸出**: elicitation decision 或 result handling
- **特點**: 僅適用 MCP elicitation 流程

---

## Hook 設定 Schema

### Handler 共通欄位

| 欄位 | 必填 | 說明 |
|------|------|------|
| `type` | 是 | `command` / `http` / `prompt` / `agent` / `mcp_tool` |
| `if` | 否 | permission rule syntax；只用於 tool events |
| `timeout` | 否 | handler timeout 秒數 |
| `statusMessage` | 否 | 執行時 spinner 訊息 |
| `once` | 否 | skill frontmatter 中可讓 hook 每 session 只跑一次 |

### Command handler

```json
{
  "type": "command",
  "command": "$CLAUDE_PROJECT_DIR/.claude/hooks/check-style.py",
  "timeout": 30
}
```

| 欄位 | 說明 |
|------|------|
| `command` | 要執行的 shell command |
| `async` | true 時背景執行，不阻塞流程 |
| `asyncRewake` | true 時背景執行，exit code 2 會喚醒 Claude |
| `shell` | `bash` 或 `powershell` |

### HTTP handler

```json
{
  "type": "http",
  "url": "http://localhost:8080/hooks/pre-tool-use",
  "timeout": 30,
  "headers": {
    "Authorization": "Bearer $HOOK_TOKEN"
  },
  "allowedEnvVars": ["HOOK_TOKEN"]
}
```

HTTP handler 將事件 JSON 以 POST body 送出，response body 使用與 command hook 相同的 JSON output 格式。非 2xx、連線失敗與 timeout 都是 non-blocking error；需要 block/deny 時，endpoint 必須回 2xx 且 body 含對應 JSON 決策。

### Prompt / agent handler

```json
{
  "type": "prompt",
  "prompt": "Return JSON decision for this hook input: $ARGUMENTS",
  "model": "fast"
}
```

```json
{
  "type": "agent",
  "prompt": "Inspect the changed files and return a JSON decision: $ARGUMENTS",
  "timeout": 60
}
```

Prompt hook 適合語意判斷。Agent hook 適合需要 Read/Grep/Glob 的複合檢查，屬實驗性能力，必須限制 scope。

### MCP tool handler（v2.1.118+）

```json
{
  "type": "mcp_tool",
  "server": "serena",
  "tool": "search_for_pattern",
  "arguments": {
    "pattern": "$HOOK_INPUT_TOOL_NAME"
  }
}
```

| 欄位 | 說明 |
|------|------|
| `server` | MCP server 名稱（必須已在 session 中連線） |
| `tool` | 要呼叫的 MCP tool 名稱 |
| `arguments` | 傳給 MCP tool 的參數（可引用 `$ARGUMENTS` 等 hook 環境變數） |

Hook 可直接呼叫 MCP tool，無需透過 command 腳本再橋接。適合需要 serena 語意操作（如符號查詢）或其他 MCP server 能力的 hook。**限制**：server 必須已在 session 中連線，否則 handler 失敗為 non-blocking error。

### `if` 條件範例

```json
{
  "type": "command",
  "if": "Bash(git push *)",
  "command": "$CLAUDE_PROJECT_DIR/.claude/hooks/pre-push-check.py"
}
```

```json
{
  "type": "command",
  "if": "Edit(*.md)",
  "command": "$CLAUDE_PROJECT_DIR/.claude/hooks/markdown-policy-check.py"
}
```

```json
{
  "type": "command",
  "if": "Bash(uv run *)",
  "command": "$CLAUDE_PROJECT_DIR/.claude/hooks/test-command-check.py"
}
```

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

**強制規範**：所有 Hook 必須使用 `hook_utils.read_json_from_stdin(logger)` 讀取 stdin，禁止直接 `json.load(sys.stdin)`。

```python
from hook_utils import setup_hook_logging, read_json_from_stdin

def main():
    logger = setup_hook_logging("hook-name")
    input_data = read_json_from_stdin(logger)
    if input_data is None:
        return 0  # 空輸入或解析失敗，正常退出（已記錄到日誌）
    # ... 處理邏輯 ...
```

**禁止的模式**：
```python
# 錯誤：直接 json.load — 已全面遷移移除
input_data = json.load(sys.stdin)
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
exit 0  # 成功（stdout JSON 作為 additionalContext）
exit 2  # 阻止操作（Hook 要求 CLI 不執行該動作）
# exit 1 — 避免使用：CLI 將 exit 1 視為 "hook error"，
#           會吞掉 stdout 訊息並顯示錯誤標籤（IMP-049 已知 CLI bug）
```

**Hook 錯誤處理原則**：

| 情境 | 正確做法 | 錯誤做法 |
|------|---------|---------|
| Hook 內部異常 | `run_hook_safely` 捕獲 + 記錄日誌檔 | `sys.exit(1)` |
| ImportError | `sys.exit(0)` + stderr 報錯 | `sys.exit(1)` |
| 輸入解析失敗 | `return 0`（靜默跳過） | `sys.exit(1)` |
| `__main__` CLI 工具 | `sys.exit(1)` 是正確的 | 不適用 |

> **注意**：`__main__` 區塊是 CLI 測試入口，不經過 Hook 系統，exit 1 是正確的 CLI 語義。
> Hook 執行路徑中應避免 `sys.exit(1)`，改用 `return 0` 或由 `run_hook_safely` 處理。

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
| 直接 json.load(sys.stdin) | 無統一錯誤處理，重複 IMP-048 | `read_json_from_stdin(logger)` |
| 忽略 stdin JSON | 直接用環境變數 | `read_json_from_stdin(logger)` |
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
