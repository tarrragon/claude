# 工具選擇規則（Tool Selection）

本文件規範 PM 與代理人在編輯/寫入檔案時的工具選擇優先序，配合 PreToolUse hook 形成「規則層 + Hook 層」雙重防護。

> **核心理念**：寫入工具的選擇應依「檔案類型」而非「工具名稱聽起來精準度」決定。一般文字檔修改用 Edit / Write 即可，serena MCP 寫入工具僅限符號級重構。

---

## 適用對象

| 對象 | 是否適用 | 載入方式 |
|------|---------|---------|
| PM（主線程） | 是 | `.claude/rules/core/` 自動載入 |
| 子代理人（subagent） | 是 | 透過 AGENT_PRELOAD 規則 7 + 本檔 |
| Hook 強制層 | `.claude/hooks/mcp-write-tool-on-text-file-guard-hook.py` | settings.json PreToolUse 註冊 |

---

## 強制規則

### 規則 1：依檔案類型選工具

| 檔案類型 / 任務 | 首選工具 | 禁用工具 |
|---------------|---------|---------|
| `.md` / `.txt` / `.yaml` / `.yml` / `.json` / `.toml` 修改 | **Edit**（首選）/ Write | `mcp__serena__replace_content` / `replace_symbol_body` / `insert_after_symbol` / `insert_before_symbol` / `safe_delete_symbol` |
| 程式碼檔（`.py` / `.js` / `.ts` / `.dart` / `.go` 等）一般修改 | **Edit**（首選）/ Write | — |
| 程式碼檔符號級重構（跨檔 rename、函式移動） | `mcp__serena__rename_symbol` 等 | 一般修改不用 serena |
| 新建檔案 | **Write** | — |
| 讀取 / 查找特定符號 | `mcp__serena__find_symbol`（read-only 不受本規則限制） | — |

**Why/Consequence**：LLM 傾向選「單步高精度」工具（PC-088 偏誤），對 `.md` / `.yaml` 等非程式碼檔誤選 serena MCP 寫入工具（AST 符號級設計，對純文字檔語意過度且 subagent 環境常不在 allow list）；會被 hook deny，代理人若錯誤泛化「所有寫入工具都被拒」會 self-imposed early stop（W17-088 / PC-112 根因），任務失敗且 PM 難察覺其實 Edit 可行。

**Action**：修改非程式碼檔時**直接用 Edit / Write**，不嘗試 serena 寫入工具；MCP 寫入工具被拒時必須降級至 Edit，禁 self-imposed early stop。

### 規則 2：Hook 被拒時的 Fallback

| 觸發 | 必要動作 | 禁止行為 |
|------|---------|---------|
| MCP 寫入工具對非程式碼檔被本 hook deny | 改用 Edit 完成同一修改 | 推論「Edit 也會被拒」而停止 |
| Edit 對非程式碼檔被拒（其他 hook） | 在 ticket Problem Analysis 記錄並回報 PM | 不嘗試 Edit 直接放棄 |

**判別準則**：`mcp__serena__*` 寫入工具屬 MCP 層限制；Edit / Write 屬 Claude Code 內建工具層，兩者限制機制完全不同，被拒原因不可互推。

---

## 邊界與違規偵測

**邊界**：`tool-discovery.md` 處理「做不到」前的探索檢查（找 deferred tools），本規則處理「已知多工具可用時的選擇」；AGENT_PRELOAD 規則 7 是 subagent prompt-time 提醒；`bash-tool-usage-rules.md` 聚焦命令語法，非工具選擇。

**雙層防護**：規則文件（本檔 + AGENT_PRELOAD 規則 7）為自我約束層；`.claude/hooks/mcp-write-tool-on-text-file-guard-hook.py` 為強制層（PreToolUse 偵測 `mcp__serena__` 寫入工具 + 非程式碼副檔名 → exit 2 + deny）。

---

## 相關文件

- `.claude/error-patterns/process-compliance/PC-112-subagent-mcp-write-tool-misselection-on-text-files.md` — 動機案例
- `.claude/error-patterns/process-compliance/PC-088-llm-tool-selection-bias.md` — 工具選擇偏誤理論基礎
- `.claude/agents/AGENT_PRELOAD.md` 規則 7 — subagent 層的 soft enforcement
- `.claude/hooks/mcp-write-tool-on-text-file-guard-hook.py` — 本規則的 hard enforcement

---

**Last Updated**: 2026-04-28
**Version**: 1.0.0 — 從 W17-090 落地：PC-112 三層防護的 framework rule 層（PM + subagent 通用），配合 hook 強制層形成雙層閉環
