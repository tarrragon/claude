# Hook Architect 技術參考

本文件包含 basil-hook-architect 的詳細技術參考資料，從主代理人定義外移。
代理人需要查閱時讀取此檔案。

> 主文件：.claude/agents/basil-hook-architect.md

---

## v2.1.139-145 變更總覽

以下表格彙整 Claude Code v2.1.139-2.1.145 與 hook 系統相關的變更，供後續開發者快速定位各章節說明。已覆蓋的變更標示引用位置；未覆蓋的新增說明章節。

| 變更 | 引入版本 | 性質 | 影響 hook 數 | 說明章節 |
|------|---------|------|------------|---------|
| args exec form 不需引號 | v2.1.139 | API 簡化 | 0（現有寫法已兼容） | Hook 設定 Schema → Command handler → Exec form |
| PostToolUse continueOnBlock | v2.1.139 | 新能力 | 0（純機會，無須強制） | Hook 類型深度理解 → PostToolUse |
| hooks 無 terminal access | v2.1.139 | 行為限制 | 0（stderr 仍有效） | 環境變數與 effort 感知 → v2.1.139+ 終端存取限制 |
| MCP stdio 收到 CLAUDE_PROJECT_DIR | v2.1.139 | 配置擴充 | 0（hooks 不受影響） | 環境變數與 effort 感知（欄位表格） |
| terminalSequence 通知 | v2.1.141 | 新 API | 0（可整合機會） | JSON 處理 → terminalSequence 通知 |
| Stop 8-block cap | v2.1.143 | 行為限制 | 5（Stop hook 評估通過） | Hook 類型深度理解 → Stop → v2.1.143 Stop 8-block cap |
| Stop/SubagentStop background_tasks | v2.1.145 | 新欄位 | 2（Stop + SubagentStop） | Hook 類型深度理解 → v2.1.145 Stop/SubagentStop input 新欄位 |
| Stop/SubagentStop session_crons | v2.1.145 | 新欄位 | 0（本專案未啟用） | 同上 |

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
- **輸入**: tool_name, tool_input, tool_response, **duration_ms**（工具執行毫秒數，v2.1.119 引入；v2.1.141 強化覆蓋失敗路徑）
- **輸出**: decision (block), additionalContext
- **特點**: 工具已執行，只能回饋訊息；`duration_ms` 可用於效能監控（如偵測執行時間超過閾值）
- **`continueOnBlock` 設定**（v2.1.139+）：在 settings.json 的 PostToolUse hook 條目可加 `"continueOnBlock": true`，hook 回傳 block 決策時不會中斷回合，而是把 `permissionDecisionReason` 回饋給 Claude 繼續推進。適合「補正後繼續」而非「阻擋退場」的場景

### PostToolUseFailure
- **用途**: 工具執行失敗後記錄錯誤、分類失敗、提供修復指引
- **輸入**: tool_name, tool_input, failure response, **duration_ms**（v2.1.119 引入；v2.1.141 確認 PostToolUseFailure 一併接收）
- **輸出**: decision 或 additionalContext
- **特點**: 適合失敗觀測，不適合阻止已發生的工具呼叫；`duration_ms` 可用於記錄失敗前的等待時間

### Stop
- **用途**: 主線程停止時的後處理（檢查未完成工作、強制完成檢查清單等）
- **輸入**: session_id, transcript_path, stop_hook_active, **background_tasks**（v2.1.145+）, **session_crons**（v2.1.145+）
- **輸出**: decision (block), reason
- **特點**: 觸發於主線程結束，**非代理人**結束。可阻擋停止以要求完成特定工作。

**v2.1.143 Stop 8-block cap**：Stop 後 Claude 最多連續處理 **8 個 blocks**（tool use rounds）。若多個 Stop hook 均阻擋（block）並要求繼續工作，Claude 處理這些 block 的輪次受此上限約束。本專案目前有 5 個 Stop hook（evaluate-session、handoff-auto-resume-stop-hook、session-experience-persistence-reminder、worktree-auto-commit、stop-worklog-handoff-sync-check），各佔 1 block，合計 5 blocks < 8，**在安全範圍內**。

**Why**：多 Stop hook 並行阻擋可能導致 Claude 進入無窮 block-continue 循環；v2.1.143 以 8-block 上限截斷，保護 session 不無止境延後退出。

**Consequence**：若未來新增 Stop hook 且啟用 block 決策，需重新評估各 hook 輸出量（8 blocks 非行數限制，而是 tool use block 計數），避免達到上限後 Claude 強制中斷尚未完成的收尾邏輯。

**Action**：新增 Stop hook 前，先清點現有 Stop hook 數量 × block 行為，確認合計不超過 7（保留 1 個緩衝）。輸出量大的 hook（如 evaluate-session）應實測確認在 1 block 內完成。

### SubagentStop
- **用途**: **代理人（subagent）真正完成時觸發**，提供代理人完成訊號源（清理派發記錄、驗證 commit、廣播完成、handoff 提醒等）
- **輸入**: session_id, transcript_path, stop_hook_active, **agent_id**, **agent_type**, **agent_transcript_path**, last_assistant_message (optional), **background_tasks**（v2.1.145+）, **session_crons**（v2.1.145+）
- **輸出**: decision (block), reason
- **特點**:
  - 涵蓋前台與 `run_in_background: true` 派發兩種模式
  - `agent_id` 為代理人精準識別碼，可用於匹配 `dispatch-active.json` 等狀態檔案
  - **與 PostToolUse(Agent) 區別**：PostToolUse(Agent) 在 background 派發時於**啟動時**觸發（非完成），SubagentStop 才是真完成訊號

> **重要**：「代理人完成」相關 Hook（清理派發、驗證 commit、廣播狀態、handoff 提醒等）一律使用 SubagentStop，**禁止使用 PostToolUse(Agent)**（時機錯位，詳見 ARCH-019）。

### v2.1.145 Stop/SubagentStop input 新欄位：background_tasks / session_crons

v2.1.145 起，Stop 與 SubagentStop 的 stdin JSON 新增兩個頂層欄位：

| 欄位 | 型別 | 觸發 event | 用途 |
|------|------|-----------|------|
| `background_tasks` | `list[dict]` | Stop, SubagentStop | 目前仍在執行的背景任務清單（每項為一個 task dict） |
| `session_crons` | `list[dict]` | Stop, SubagentStop | session 內排程的 cron 任務清單（本專案目前未啟用 CC session cron） |

**background_tasks 弱依賴策略**：

`background_tasks` 的 task dict 內部 schema 尚未正式文件化，且可能隨版本演進。本專案採**弱依賴策略**——只判斷 list 是否非空（代表有背景代理人執行中），不依賴 task dict 的內部欄位：

```python
def has_background_agents(input_data: dict, logger) -> bool:
    """只判斷 background_tasks list 非空，不讀 task dict 內部欄位。"""
    bg_tasks = input_data.get("background_tasks")
    if not isinstance(bg_tasks, list):
        return False
    return len(bg_tasks) > 0
```

**Why**：`background_tasks` 可直接取代過去依賴 `started_at` 時間戳推斷「30 分鐘內有無背景代理人」的魔術數字邏輯，提供更可靠的訊號。

**Consequence**：若 hook 不讀 `background_tasks` 而僅依賴 `started_at` 推斷，在背景代理人執行中時仍可能觸發誤報（如 stop-worklog-handoff-sync-check-hook 過去的誤報）。

**Action**：在 Stop / SubagentStop hook 需要判斷「是否有背景代理人執行中」時，優先讀 `background_tasks`；欄位不存在（舊版 CC）或空 list 時 fallback 到既有本地推斷邏輯。參考實作：`.claude/skills/ticket/hooks/handoff-auto-resume-stop-hook.py` 的 `has_background_agents()`（W3-026.1 落地）。

**session_crons**：

本專案目前**未啟用** Claude Code session cron 功能，`session_crons` 預計為空 list。列為已知能力，未來若啟用 session cron 需評估是否讀取此欄位做排程感知。

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
| `command` | **必填 string**。無 `args` 時為完整 shell 字串（shell form）；有 `args` 時為執行檔路徑（exec form） |
| `args` | 選填 `string[]`。出現時觸發 exec form，與 `command` 一起 spawn，不經 shell |
| `async` | true 時背景執行，不阻塞流程 |
| `asyncRewake` | true 時背景執行，exit code 2 會喚醒 Claude |
| `shell` | `bash` 或 `powershell` |

**Shell form（`args` 省略）**：

```json
{
  "type": "command",
  "command": "$CLAUDE_PROJECT_DIR/.claude/hooks/check-style.py --strict",
  "timeout": 30
}
```

`command` 完整字串走 shell 解析，可用 pipe / redirect / `&&`，但含空白路徑或 backtick 需自行 quote。

**Exec form（`args` 出現，v2.1.139+，無 shell 解析）**：

```json
{
  "type": "command",
  "command": "$CLAUDE_PROJECT_DIR/.claude/hooks/check-style.py",
  "args": ["--strict", "--report-dir=$CLAUDE_PROJECT_DIR/.claude/hook-logs"],
  "timeout": 30
}
```

**注意**：`command` 永遠是必填 string，**不能省略**。`args` 僅作為「執行檔的 argv」，不是 `command` 的替代品。本檔在 0.18.0-W14-031 / W14-040 之前曾錯誤示範「args 取代 command」並導致 settings.json schema 驗證失敗（`/doctor` 報 `command: Expected string, but received undefined`）；範例已更正為官方 schema。

> **官方來源**：https://code.claude.com/docs/en/hooks（Command hook fields 章節）。修改本段前必須 WebFetch 官方文件驗證 schema，禁止靠 release notes 推測。

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

### 環境變數與 effort 感知（v2.1.132-2.1.141）

Hook 進程可從以下環境變數和 JSON payload 欄位取得 session/runtime 上下文：

| 來源 | 欄位 | 引入版本 | 用途 |
|------|------|---------|------|
| env | `$CLAUDE_PROJECT_DIR` | 早期 | 專案根目錄絕對路徑（hook command 路徑展開首選） |
| env | `$CLAUDE_CODE_SESSION_ID` | v2.1.132+ | 與 hook stdin payload 的 `session_id` 一致；Bash 子進程也可取得 |
| env | `$CLAUDE_EFFORT` | v2.1.133+ | 當前 effort level（如 `low` / `medium` / `high`），與 stdin `effort.level` 同步 |
| env | `$CLAUDE_CODE_DISABLE_ALTERNATE_SCREEN` | v2.1.132+ | `=1` 時 opt-out 全螢幕渲染（影響終端型 hook 行為） |
| stdin payload | `effort.level` | v2.1.133+ | hook JSON 輸入新增頂層欄位 |
| MCP stdio server env | `CLAUDE_PROJECT_DIR` | v2.1.139+ | MCP stdio server 子進程現可取得 |
| MCP stdio server env | `CLAUDE_CODE_SESSION_ID` / `CLAUDECODE` | v2.1.154+ | MCP stdio server 子進程現可取得 session id 與 `CLAUDECODE=1` 標記，可用於將工具呼叫遙測關聯到特定 session（如 dispatch_stats / 日誌） |

> **可選增強（非強制）**：上述 MCP session 關聯能力為可選用途。hook / MCP 不必使用 session id；僅在需要把工具呼叫遙測關聯到特定 session 時採用。預設不依賴此能力即可正常運作。

**effort 感知範例**：

```python
import os

def main() -> int:
    logger = setup_hook_logging("my-hook")
    payload = read_json_from_stdin(logger)
    if payload is None:
        return 0

    effort = (payload.get("effort") or {}).get("level") or os.environ.get("CLAUDE_EFFORT", "medium")

    if effort == "low":
        return 0
    if effort == "high":
        run_full_validation(logger)
    else:
        run_quick_check(logger)
    return 0
```

`effort` 讓 hook 在低成本模式下放行、高成本模式下加嚴；同一 hook 可依 effort 動態調整驗證深度，避免高頻情境被阻塞。

### v2.1.139+ 終端存取限制

v2.1.139 起，hook process **無法直接存取宿主終端**（raw terminal file descriptor，如 `/dev/tty`）。此限制影響試圖繞過 stdout/stderr 直接操控終端的場景，但**不影響 stderr pipe**。

**Why**：理解此限制對正確詮釋規則 4（Hook 失敗必須可見）至關重要。若誤解為「stderr 被丟棄」，可能錯誤地認為規則 4 的 stderr 雙通道要求已失效。

**精確語意區分**：

| 場景 | 是否受限 | 說明 |
|------|---------|------|
| `sys.stderr.write(...)` / `print(..., file=sys.stderr)` | **不受限** | stderr pipe 由 Claude Code 讀取，仍呈現為 hook error 訊息（UI 可見，IMP-048 確認） |
| `/dev/tty` 直接寫入 | **受限** | hook process 無此 fd 存取權，無法直接操控宿主終端 |
| `terminalSequence` JSON 欄位 | **可用** | 透過 hookSpecificOutput 欄位傳遞終端通知，不依賴 terminal fd（v2.1.141+，詳見下方 terminalSequence 章節） |

**Consequence**：本專案所有 hook 均透過 `sys.stderr` 寫入（不直接操控終端 fd），規則 4 的「stderr 可見性機制」在 v2.1.139+ 下**仍然有效**，不需修訂規則 4 本體。

**Action**：hook 開發中若需要讓用戶在「非錯誤但需注意」情境下看到提示（而非僅 error-level 的 stderr），可使用 `terminalSequence` 欄位（v2.1.141+）作為第二可見通道，與 stderr 錯誤通道明確分工。禁止試圖直接寫入 `/dev/tty`，在 v2.1.139+ 下會靜默失敗。

### 設計鐵則：事實判斷型 hook 必擋 + effort 解耦

**Why**：hook 訊息可分為兩類：「事實判斷」（字元集違規、結構缺鍵、格式錯誤等客觀狀態）與「決策話術」（推薦、建議、評估等主觀語意）。前者違規是客觀事實，與使用者主觀意願無關；effort 只代表使用者投入深度，不代表對客觀事實的豁免。若事實判斷型 hook 允許 effort=low 放行，等同「省力模式下字元集可亂用」，強制力與設計意圖相互矛盾。

**Consequence**：事實判斷型 hook 若依 effort 短路放行，會在使用者切換 low effort 時靜默失去防護；違規在 low effort session 下累積，切回 high effort 才觸發大量阻擋，修復成本反而更高。

**Action**：設計新 hook 前先完成分類判斷（見下方判別表）。事實判斷型 hook 的核心 block 邏輯**永不依 effort 短路**；effort 只允許控制 audit log 詳細度或次要 annotation 的輸出量。

#### 事實判斷 vs 決策話術分類標準

| 類型 | 定義 | 典型訊號 | effort 可短路？ |
|------|------|---------|--------------|
| 事實判斷 | 客觀可驗證的狀態違規（缺鍵值、字元集錯誤、結構不符） | 缺鍵值 / 字元集錯誤 / 必填欄位缺失 / 格式結構違規 | 否（核心 block 永不短路） |
| 決策話術 | 主觀語意評估（推薦、建議、風格偏好） | 「建議」「推薦」「可考慮」「評估後」 | 是（適度依 effort 調整深度） |

#### 4 hook 落地案例對照

| Hook | 訊息類型 | effort 處置 | 設計依據 |
|------|---------|------------|---------|
| `phase4-decision-enforcement-hook` | 事實判斷（PC-093：延後話術偵測） | `low` 抑制 audit log；**block 邏輯永不放行** | 延後話術是事實，與 effort 無關 |
| `wrap-decision-tripwire-hook` | 事實訊號（PC-066/PC-093：缺必要欄位） | **不短路**，僅 logger 留痕 | 缺欄位是事實，low effort 不豁免 |
| `askuserquestion-charset-guard-hook` | 事實判斷（PC-074/PC-131：字元集違規） | **不短路**，僅 logger 留痕 | 字元集錯誤是事實，與努力程度無關 |
| `auq-option-pattern-detector-hook` | 事實判斷（PC-064：純文字選項結構違規） | **不短路**，僅 logger 留痕 | 結構違規是事實，不隨 effort 變動 |

#### 未來 hook 設計自問句

設計新 hook 時，在實作前回答以下兩問：

1. **「我的訊號是事實還是決策？」** — 若可用客觀條件判別（正規表達式、鍵值存在、字元集）即為事實；若需主觀評估（風格、推薦、評估質量）即為決策話術。
2. **「核心訊號 vs 詳細 audit 是否可分離？」** — 若可分離，核心 block 邏輯走事實路徑（永不短路），詳細 audit 可依 effort 調整輸出量（low 抑制、high 展開）；若不可分離，整體視為事實判斷處理。

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

### terminalSequence 通知（v2.1.141+）

Hook JSON output 新增 `terminalSequence` 欄位，讓 hook 在無 controlling terminal（如背景 / SSH / `run_in_background`）情境下仍能發出桌面通知、視窗標題、bell：

```json
{
  "hookSpecificOutput": {
    "hookEventName": "Notification",
    "terminalSequence": {
      "title": "TDD Phase 4 完成",
      "notification": "驗收通過，可 commit",
      "bell": true
    }
  }
}
```

| 子欄位 | 用途 |
|-------|------|
| `title` | 終端視窗標題（OSC 2） |
| `notification` | 桌面通知（macOS / Linux notify-osd / Windows toast） |
| `bell` | true 時發出終端 bell（`\x07`） |

適合長時 hook（pre-push、test runner、agent 完成廣播）通知用戶切回 Claude Code。取代過去自行送 OSC escape 的脆弱做法。

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

### 9. 跨平台編碼原則（UTF-8 強制）

Hook 不可依賴 locale codepage。Windows console 預設 cp950（Big5）/cp936（GBK），中文輸出與 subprocess 解碼會在該環境亂碼。每個 Hook 入口必須強制 UTF-8 I/O，subprocess 呼叫必須顯式指定 encoding。

UV 單檔範本（PEP 723 + UTF-8 強制）：

```python
#!/usr/bin/env -S uv run --script --quiet
# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""Hook 描述。"""
import sys
import json
import subprocess


def ensure_utf8_io() -> None:
    """強制 stdin/stdout/stderr 使用 UTF-8（Python 3.11+ reconfigure）。"""
    for stream in (sys.stdin, sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")


def main() -> int:
    ensure_utf8_io()  # 必須在 read_json_from_stdin 之前

    payload = json.load(sys.stdin)

    # subprocess 呼叫強制 utf-8 + errors='replace'
    result = subprocess.run(
        ["git", "log", "-1"],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )

    return 0


if __name__ == "__main__":
    sys.exit(main())
```

關鍵點：

| 項目 | 必要做法 |
|------|---------|
| stdin/stdout/stderr | 入口呼叫 `ensure_utf8_io()`（reconfigure 三 stream） |
| subprocess.run / Popen | 顯式 `encoding="utf-8", errors="replace"` |
| 檔案讀寫 | `open(..., encoding="utf-8")` 或 `Path.read_text(encoding="utf-8")` |
| 路徑分隔符 | settings.json 中的 hook command 用 forward slash（`/`） |

完整跨平台部署規範（含 shebang / CRLF / Windows 安裝）見 `.claude/methodologies/hook-system-methodology.md`「跨平台部署規範」章節。

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
| Windows console 中文亂碼 | 未呼叫 `ensure_utf8_io()`；subprocess 未指定 `encoding` | 入口強制 UTF-8；subprocess 帶 `encoding="utf-8", errors="replace"`（詳見原則 9） |

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

**Last Updated**: 2026-05-21
**Source**: basil-hook-architect.md v2.1.0 精簡外移；2026-05-14 同步 Claude Code v2.1.130-2.1.141 hook 系統能力（`args` exec 形式、`continueOnBlock`、`effort.level` payload、`$CLAUDE_EFFORT` / `$CLAUDE_CODE_SESSION_ID` env、`terminalSequence` 通知、MCP stdio `CLAUDE_PROJECT_DIR` 注入）；2026-05-21 同步 v2.1.142-2.1.145 新增能力（W3-026 + W3-031 ANA 結論落地）：

| 版本範圍 | 新增章節 | 內容 |
|---------|---------|------|
| v2.1.139-145 | v2.1.139-145 變更總覽 | 8 項變更彙整索引表，快速定位各章節說明 |
| v2.1.139 | v2.1.139+ 終端存取限制 | stderr vs raw terminal fd 區別；規則 4 仍有效釋疑 |
| v2.1.143 | Stop → v2.1.143 Stop 8-block cap | Stop hook 最多 8 blocks；本專案 5 個 Stop hook 安全評估 |
| v2.1.145 | v2.1.145 Stop/SubagentStop input 新欄位 | background_tasks / session_crons schema；弱依賴策略；參考實作 |
