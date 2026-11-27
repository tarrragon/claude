# 工具選擇規則（Tool Selection）

本文件規範 PM 與代理人在編輯/寫入檔案時的工具選擇優先序，配合 PreToolUse hook 形成「規則層 + Hook 層」雙重防護。

> **核心理念**：寫入工具的選擇應依「檔案類型」而非「工具名稱聽起來精準度」決定。一般文字檔修改用 Edit / Write 即可，serena MCP 寫入工具僅限符號級重構。

---

## 適用對象

| 對象 | 是否適用 | 載入方式 |
|------|---------|---------|
| PM（主線程） | 是 | `.claude/rules/core/` 自動載入 |
| 子代理人（subagent） | 是 | `.claude/rules/core/` 自動載入 |
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

**邊界**：本規則優先於 harness 層「優先用 Bash 改檔」類指令（Bash 寫入繞過全部 Edit/Write-only guard，已有實證）；唯讀 Bash 不受限。

**放寬範圍**：subagent 寫 checkout 外與非受管路徑（scratchpad、暫存目錄、不受任何守衛管的檔）時，可用 Bash 改檔。主線程不適用此放寬。

**受管路徑維持 Edit / Write**：`.claude/**`、`docs/**`、ticket md、產品碼（`lib/`、`test/`、`src/`）仍用 Edit / Write。理由是守衛覆蓋，不是正確率：內容守衛只掛在 Edit / Write，Bash 寫入要到 commit 層才被檢查（檔案已落地），部分守衛完全沒有 Bash 對應；路徑層另有 Bash 守衛直接 deny。

**Bash 改檔寫法條件（放寬範圍內，三項全守）**：

| 條件 | 要求 | 理由 |
|------|------|------|
| 字面替換 | 以固定字串取代，不用 regex 與 sed／awk 旗標（GNU 與 BSD 不同） | 只讀命令即可確定改了什麼 |
| 寫入前斷言出現次數 | 以出現次數（非行數）斷言，與預期不符即停 | 無斷言時比對落空會成為靜默錯誤 |
| 單檔或全部斷言後才寫入 | 一個命令只改一個檔；改多檔時全部斷言通過後才寫第一個檔 | 多檔腳本非原子，中途失敗已改的檔不回滾 |

實驗依據見 `.claude/references/tool-selection-details.md`〈Bash 改檔放寬的實驗依據〉。

**Why/Consequence**：LLM 傾向選「單步高精度」工具（PC-088 偏誤），對 `.md` / `.yaml` 等非程式碼檔誤選 serena MCP 寫入工具（AST 符號級設計，對純文字檔語意過度且 subagent 環境常不在 allow list）；會被 hook deny，代理人若錯誤泛化「所有寫入工具都被拒」會 self-imposed early stop（PC-112 根因），任務失敗且 PM 難察覺其實 Edit 可行。

**Action**：修改非程式碼檔時**直接用 Edit / Write**，不嘗試 serena 寫入工具；MCP 寫入工具被拒時必須降級至 Edit，禁 self-imposed early stop。

### 規則 2：Hook 被拒時的 Fallback

| 觸發 | 必要動作 | 禁止行為 |
|------|---------|---------|
| MCP 寫入工具對非程式碼檔被本 hook deny | 改用 Edit 完成同一修改 | 推論「Edit 也會被拒」而停止 |
| Edit 對非程式碼檔被拒（其他 hook） | 在 ticket Problem Analysis 記錄並回報 PM | 不嘗試 Edit 直接放棄 |
| Edit / Write 被非專案來源拒絕（auto mode classifier、permissionMode、OS 權限等） | 停手，於 ticket NeedsContext 記錄並回報 PM | 改用 Bash 內嵌腳本（`python3 -c` / `sed` / heredoc 重寫）繞過完成同一修改 |
| 例外：複合 Bash 命令被平台以「too complex to verify」拒絕 | 拆成原命令中的單一命令分次執行（每條仍由平台判定）；拆開後仍被拒即停手，於 ticket NeedsContext 記錄原命令與拒絕訊息並回報 PM | 改用 `python -c`／`bash -c`／`eval`、腳本檔等把實際操作藏起來的寫法 |

**判別準則**：`mcp__serena__*` 寫入工具屬 MCP 層限制；Edit / Write 屬 Claude Code 內建工具層，兩者限制機制完全不同，被拒原因不可互推。非專案來源拒絕的語意是「不該做這件事」，不是「選錯工具」——不可用 Bash 改寫檔案內容規避判斷。此禁令不受規則 1 放寬範圍影響：放寬只適用於未被拒絕的情況。

**PM 接到代理人被非專案來源拒絕的回報**（例：auto mode 以不在範圍內拒絕）：不得自行補 `where.files` 後代為修改，也不得改用 Bash 代改；將拒絕訊息與擬修改內容交用戶裁定，裁定後才動作。

「too complex to verify」例外只限該拒絕訊息，語意是「平台看不清」而非「不該做」，拆分後每條命令仍交平台判定；論證與邊界見 `.claude/references/tool-selection-details.md`。

---

## 邊界與違規偵測

**邊界**：`tool-discovery.md` 處理「做不到」前的探索檢查（找 deferred tools），本規則處理「已知多工具可用時的選擇」；本檔的生效管道是 `.claude/rules/core/` 自動載入（`AGENT_PRELOAD.md` 規則 7 立意相同但未自動送達，詳見該檔 header 註記）；`bash-tool-usage-rules.md` 聚焦命令語法，非工具選擇。

**雙層防護**：規則文件（本檔）為自我約束層；`.claude/hooks/mcp-write-tool-on-text-file-guard-hook.py` 為強制層（PreToolUse 偵測 `mcp__serena__` 寫入工具 + 非程式碼副檔名 → exit 2 + deny）。

---

## 相關文件

- `.claude/error-patterns/process-compliance/PC-112-subagent-mcp-write-tool-misselection-on-text-files.md` — 動機案例
- `.claude/error-patterns/process-compliance/PC-088-llm-tool-selection-heuristic-bias.md` — 工具選擇偏誤理論基礎
- `.claude/agents/AGENT_PRELOAD.md` 規則 7 — 立意同源，未自動送達（見上文邊界段）
- `.claude/hooks/mcp-write-tool-on-text-file-guard-hook.py` — 本規則的 hard enforcement

---

**Last Updated**: 2026-11-25
**Version**: 1.4.0 — 規則 1 依實驗結果放寬：subagent 寫 checkout 外與非受管路徑可用 Bash，附三項寫法條件；受管路徑維持 Edit／Write，理由為守衛覆蓋。規則 2 維持非專案來源拒絕禁 Bash，補 PM 接到拒絕回報後交用戶裁定、不自行補 where.files 代改（來源：用戶裁定 2026-11-24、25；實驗依據在 details）
**Version**: 1.3.0 — 規則 2 新增例外列：複合 Bash 命令被平台以「too complex to verify」拒絕時，可拆成原命令中的單一命令分次執行，禁改用 `python -c`／腳本檔隱藏實際操作，拆後仍拒即停手回報；判別準則補一句例外射程並路由新建的 `references/tool-selection-details.md`（來源：用戶裁決，2026-10-14）
**Version**: 1.2.0 — 規則 2 新增第三列：Edit/Write 被非專案來源（auto mode classifier、permissionMode、OS 權限）拒絕時停手回報，禁改用 Bash 內嵌腳本繞過；判別準則補一句「非專案來源拒絕的語意是不該做這件事，非選錯工具」（源自實測案例：代理人的 Edit 被 harness auto mode classifier 拒絕後誤以 Bash 內嵌腳本繞過完成修改）
**Version**: 1.1.0 — 規則 1 表格下補邊界一行：本規則優先於 harness 層改檔類指令，唯讀 Bash 不受限
**Version**: 1.0.0 — PC-112 三層防護的 framework rule 層落地（PM + subagent 通用），配合 hook 強制層形成雙層閉環
