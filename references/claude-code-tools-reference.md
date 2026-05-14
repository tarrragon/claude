# Claude Code 工具參考索引

本文件收錄 Claude Code 提供的進階工具，作為按需查詢的參考來源。適合在遇到適用場景時查閱，確認工具名稱、啟用方式及使用限制。

> **載入方式**：按需讀取。需要調用 Chrome 自動化、Bash 沙盒隔離或背景腳本串流功能時讀取。
>
> **查證日期**：2026-05-13（對應 Claude Code v2.1.x 版本）
>
> **資料來源**：[code.claude.com/docs](https://code.claude.com/docs)

---

## 工具總覽

| 工具 | 最低版本 | 平台支援 | 狀態 |
|------|---------|---------|------|
| Claude in Chrome | —（需安裝 Chrome 擴充功能，無 CC 版本下限） | macOS / Windows / Linux | Beta |
| BashTool Sandbox 模式 | 2.0.24 | macOS / Linux / WSL2 | 穩定（預設關閉） |
| Monitor 工具 | 2.1.98 | 全平台 | 穩定 |

---

## 1. Claude in Chrome（瀏覽器整合）

### 用途

開發 Web App 時，切換視窗手動測試是主要摩擦點；Chrome 整合將瀏覽器測試與除錯動作內嵌於開發工作流，消除上下文切換。Claude Code 連接 Chrome 後可直接操控瀏覽器，讀取 console 錯誤、擷取 DOM 狀態、執行自動化任務，並共用瀏覽器的已登入狀態。

### 啟用方式

**方法 A：CLI 啟動時啟用**

```bash
claude --chrome
```

**方法 B：在現有 session 中啟用**

```
/chrome
```

`/chrome` 指令也可用於查看連線狀態、管理權限、重新連接。

**前置條件**：必須先安裝並更新「Claude in Chrome」Chrome 擴充功能。

**VS Code 整合語法**（在 prompt 前加 `@browser`）：

```
@browser go to localhost:3000 and check the console for errors
```

### 適用場景

| 場景 | 說明 |
|------|------|
| 實機除錯 | 讀取 console 錯誤和 DOM 狀態，直接定位並修復問題 |
| 設計驗證 | 從 Figma mock 建 UI 後，立即在瀏覽器中對比視覺結果 |
| Web App 測試 | 表單驗證、視覺回歸測試、使用者流程自動化 |
| 已驗證應用操作 | 操作 Google Docs、Gmail 等已登入的 Web App，無需 API 整合 |
| 資料擷取 | 從網頁提取結構化資訊 |
| 重複性任務自動化 | 批量填表、資料抄錄等重複操作 |
| 互動錄製 | 將瀏覽器互動錄製為 GIF |

### 限制

| 限制項目 | 說明 |
|---------|------|
| Beta 狀態 | 功能可能變動，不保證向後相容 |
| 需安裝擴充功能 | 必須在 Chrome 安裝官方擴充功能才能使用 |
| 手動介入情境 | 遇到登入頁或 CAPTCHA 時 Claude 會暫停，需手動處理 |
| 可見視窗執行 | 所有瀏覽器操作在真實 Chrome 視窗中即時進行，無法靜默背景執行 |
| 分頁管理 | Claude 開啟新分頁執行任務，共用瀏覽器的登入狀態 |

### MCP 工具層（chrome-devtools）

Chrome 整合也透過 `mcp__chrome-devtools__*` 系列 deferred tools 提供細粒度操作，包含：

- `navigate_page`、`take_screenshot`、`click`、`fill`、`evaluate_script`
- `get_console_message`、`list_network_requests`
- `lighthouse_audit`、`performance_start_trace`

使用前需透過 `ToolSearch("select:mcp__chrome-devtools__<tool_name>")` 載入 schema。

---

## 2. BashTool Sandbox 模式

### 用途

將 Bash 命令執行限制在沙盒隔離環境中，防止指令意外存取或修改檔案系統與網路。不啟用時，代理人的 Bash 命令對主機檔案系統和網路有完整存取權；高風險環境（CI/CD、教育平台、不可信程式碼執行）應主動評估是否啟用。預設關閉，需顯式設定。

### 啟用方式

**方法 A：settings.json 設定（推薦：設定持久生效，不需每次啟動時加 flag）**

```json
{
  "sandbox": {
    "enabled": true,
    "failIfUnavailable": false
  }
}
```

| 設定鍵 | 預設值 | 說明 |
|--------|-------|------|
| `enabled` | `false` | 是否啟用沙盒（macOS / Linux / WSL2 有效） |
| `failIfUnavailable` | `false` | 若沙盒無法啟動，`false` 顯示警告並繼續執行；`true` 直接終止 |

**方法 B：SDK 程式碼中啟用**（TypeScript / Python SDK）

```typescript
import { query } from "@anthropic-ai/claude-agent-sdk";

for await (const message of query({
  prompt: "Build and test my project",
  options: {
    sandbox: {
      enabled: true,
      autoAllowBashIfSandboxed: true,
      network: {
        allowLocalBinding: true
      }
    }
  }
})) {
  if ("result" in message) console.log(message.result);
}
```

**方法 C：Bash 工具參數停用沙盒（per-call 豁免）**

若已啟用全域沙盒，但特定命令需要完整存取權限，可在單次呼叫時使用 `dangerouslyDisableSandbox: true` 關閉沙盒：

```typescript
type BashInput = {
  command: string;
  timeout?: number;
  description?: string;
  run_in_background?: boolean;
  dangerouslyDisableSandbox?: boolean;  // true 則此次呼叫跳過沙盒
};
```

> **注意（v2.1.113+）**：`dangerouslyDisableSandbox: true` 現在會觸發權限提示，不再靜默繞過。

### 適用場景

| 場景 | 說明 |
|------|------|
| CI/CD 環境 | 防止代理人意外修改建置產物或系統設定 |
| 教育/示範環境 | 讓學習者在隔離環境執行程式碼，不影響主機 |
| 不可信程式碼執行 | 執行來源不確定的腳本時限制其影響範圍 |
| 嚴格合規部署 | 需要可驗證的命令隔離記錄 |

### 限制

| 限制項目 | 說明 |
|---------|------|
| 平台支援 | 僅 macOS、Linux、WSL2；原生 Windows 不支援 |
| 預設關閉 | 不會自動啟用，必須主動設定 |
| 相依套件 | 部分平台需要沙盒相依套件（缺失時依 `failIfUnavailable` 決定行為） |
| 網路限制 | 預設隔離網路存取；如需 localhost binding 需顯式設定 |
| `find -exec / -delete`（v2.1.113+） | `Bash(find:*)` 允許規則不再自動批准這兩種操作 |

---

## 3. Monitor 工具

### 用途

在背景執行一個 shell 腳本，並將每一行 stdout 輸出即時串流給 Claude 作為事件通知。讓 Claude 在等待期間能夠被動接收更新，而無需主動輪詢。

**與 `run_in_background` 的差異**：`run_in_background` 執行後需主動查詢結果（TaskOutput），適合只需最終結果的場景，開銷較低；Monitor 主動將每行輸出推送給 Claude，適合需要即時反應（逐行通知、條件觸發後續操作）的監控場景。若只需等待命令完成，優先選 `run_in_background`。

### Schema

**輸入參數**

| 參數 | 型別 | 預設值 | 說明 |
|------|------|-------|------|
| `command` | `string` | 必填 | Shell 腳本；每行 stdout 作為一個事件；腳本退出即結束監控 |
| `description` | `string` | 必填 | 通知中顯示的簡短說明 |
| `timeout_ms` | `int \| null` | 300000（5 分鐘） | 超時後強制終止（最大值 3600000 = 1 小時） |
| `persistent` | `bool \| null` | `false` | `true` 表示執行到 session 結束，或由 TaskStop 工具停止 |

**輸出欄位**

| 欄位 | 型別 | 說明 |
|------|------|------|
| `taskId` | `string` | 背景任務 ID，可傳給 TaskStop |
| `timeoutMs` | `int` | 實際超時設定（persistent 模式下為 0） |
| `persistent` | `bool \| null` | 是否為持續模式 |

### 使用範例

**場景一：等待測試套件完成並即時輸出**

```
Monitor(
  command="npm test 2>&1",
  description="Jest test suite",
  timeout_ms=120000
)
```

**場景二：持續監控 log 檔案**

```
Monitor(
  command="tail -F ./logs/app.log",
  description="Application log stream",
  persistent=true
)
```

**場景三：在 Plugin 中定義監控（v2.1.105+）**

```json
[
  {
    "name": "deploy-status",
    "command": "${CLAUDE_PLUGIN_ROOT}/scripts/poll-deploy.sh ${user_config.api_endpoint}",
    "description": "Deployment status changes"
  },
  {
    "name": "error-log",
    "command": "tail -F ./logs/error.log",
    "description": "Application error log",
    "when": "on-skill-invoke:debug"
  }
]
```

### 適用場景

| 場景 | 說明 |
|------|------|
| 等待長時間執行的指令 | 測試套件、建置腳本、部署腳本 |
| 即時 log 監控 | 追蹤 app.log、error.log 中的新事件 |
| 部署狀態追蹤 | 輪詢 CI/CD 狀態，出現特定結果時通知 Claude |
| 背景服務等待就緒 | 等待 dev server、資料庫等服務啟動完成 |
| 觸發式工作流 | 事件發生時（如 webhook 接收）驅動後續操作 |

### 限制

| 限制項目 | 說明 |
|---------|------|
| stdout 才串流 | stderr 不會自動串流，需在腳本中將 stderr 重導向至 stdout（`2>&1`） |
| 逐行觸發 | 以換行符為事件邊界，大量輸出可能產生大量事件 |
| persistent 需手動停止 | 必須用 TaskStop 工具停止，否則持續到 session 結束 |
| 最大超時 1 小時 | `timeout_ms` 不得超過 3600000；需更長執行時間應考慮其他方案 |
| 沙盒規則繼承 | Monitor 啟動的腳本遵循與 Bash 工具相同的 permission 規則 |

### 停止方式

```
TaskStop(taskId="<Monitor 回傳的 taskId>")
```

---

## 工具對比與選擇指引

| 需求 | 建議工具 |
|------|---------|
| 需要操作或驗證瀏覽器中的 Web App | Claude in Chrome |
| 在隔離環境執行可能有風險的 shell 命令 | BashTool Sandbox |
| 等待某個腳本執行，希望即時取得每行輸出 | Monitor |
| 執行背景指令，只需要最終結果 | `Bash(run_in_background: true)` + TaskOutput |
| 在 MCP 層操控瀏覽器 DOM/網路 | `mcp__chrome-devtools__*` deferred tools |

---

## 相關文件

- `.claude/references/claude-code-platform-limits.md` — Subagent 平台限制（per-turn tool calls / output token 上限）
- `.claude/references/plugin-management.md` — Plugin 安裝評估與 context 成本管理
- `.claude/rules/core/bash-tool-usage-rules.md` — Bash 工具使用規則（工作目錄、大輸出處理、git 串接）
- `.claude/rules/core/tool-selection.md` — 工具選擇優先序規則
- `.claude/rules/core/tool-discovery.md` — 宣告「做不到」前的工具發現流程

---

## 維護說明

本文件收錄的工具資訊可能隨 Claude Code 版本變動。以下情境應重新查證 code.claude.com/docs 並更新：

| 觸發條件 | 需更新項目 |
|---------|---------|
| CC 版本跳升 minor 版號（如 2.1.x → 2.2.x） | 確認各工具狀態（Beta/GA）、版本號、啟用語法是否變更 |
| Claude in Chrome 從 Beta 轉 GA | 更新總覽表狀態欄、移除 Beta 限制說明 |
| 新增工具的官方文件出現「Available since vX.Y.Z」 | 更新對應工具的最低版本欄位 |

---

**Last Updated**: 2026-05-13
**Version**: 1.1.0 — Layer 2 審查修正（basil-writing-critic + linux）：補 Chrome/Sandbox 用途段 Why 層、方法 C 節標題改「停用/豁免」、總覽表 Chrome 版本欄統一語意、方法 A 補推薦理由、Monitor 差異說明補選擇指引、新增維護說明章節
**Version**: 1.0.0 — 初始建立，收錄 Claude in Chrome（Beta）、BashTool Sandbox 模式、Monitor 工具三項 CC 進階工具的用途、啟用方式、適用場景與限制；查證自 code.claude.com/docs（2026-05-13）
