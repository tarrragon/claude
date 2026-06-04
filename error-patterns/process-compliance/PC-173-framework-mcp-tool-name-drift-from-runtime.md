# PC-173: 框架文件引用的 MCP 工具名與實機暴露漂移

## 摘要

框架文件（skill 訊息常數、工具使用指南、settings template）靜態引用的 MCP 工具名與 server 前綴，會隨 MCP server 版本升級（工具改名 / 移除）或安裝方式（user-level vs plugin marketplace 前綴不同）而與當前實機暴露漂移。讀者依漂移的文件嘗試呼叫不存在的工具會浪費回合，或使 SessionStart 驗證指引失效。修正方向：以 session-start deferred tools 清單 / ToolSearch 為 ground truth（非文件、非 wrapper `--help`、非 init hook 提示），優先採版本無關描述，並注意終端對可呼叫 MCP 工具名的 redaction 會干擾 grep 判讀。

## 症狀

- 文件 / init hook 提示要求呼叫某 MCP 工具，但 `ToolSearch` 精確選取 + 關鍵字兩輪皆無命中（工具不存在）
- 同一速查表內多個工具名全部過時（短名 vs 實機 `<server>_<verb>` 全名；如 `callers` vs `get_callers`）
- 同一 MCP server 在文件中混用兩種前綴（`mcp__serena__` 與 `mcp__plugin_serena_serena__`），且部分工具名重複
- 權限 allowlist 引用的工具名不在實機清單（dead entries，不 match 即不生效）

## 根因（三層漂移）

| 層 | 漂移來源 | 範例 |
|----|---------|------|
| 工具存廢 | server 跨版本改名 / 移除工具 | `codegraph_status` 舊版存在、v0.16.6 移除 |
| 工具命名 | server 改用 `<prefix>_<verb>` 命名 | `callers` → `codegraph_get_callers`、`search_node` → `codegraph_symbol_search` |
| server 前綴 | 安裝方式決定 server id | user-level=`mcp__serena__` / plugin marketplace=`mcp__plugin_<name>_serena__` |

框架文件是靜態快照，MCP 實機暴露是動態 runtime；兩者無自動同步機制，必然累積漂移。延續 PC-172 / [[feedback_wrapper_arg_injection_diagnostic]] 的核心：靜態文件 / wrapper `--help` / init hook 提示不等於 runtime 真實暴露。

## 案例：codegraph_status 引發的三檔漂移盤點（2026-06-04）

起於用戶請求「呼叫 `mcp__codegraph__codegraph_status` 確認 codegraph 連線並建索引」。ToolSearch 兩輪確認該工具在 v0.16.6 不存在，改用 `codegraph_reindex_workspace`（force=true）成功建索引（750 檔）。後續盤點發現漂移橫跨 3 檔：

| 檔案 | 漂移 | 落地 ticket |
|------|------|-----------|
| `project-init/.../messages.py:260` | 索引驗證提示引用不存在的 `codegraph_status` | 0.19.1-W1-033 |
| `search-tools-guide/SKILL.md` 速查表 | codegraph 5 名 + cbm `__search` + serena `plugin_serena_serena__` 前綴全錯 | 0.19.1-W1-033 |
| `templates/settings-local-template.json` | serena 前綴漂移 + 7 個工具名不在實機清單 | 0.19.1-W1-034 |

全域 audit 與常駐 hook 評估排入 0.19.1-W1-035（P3 ANA）。

## 防護（驗證流程）

| 步驟 | 動作 | 目的 |
|------|------|------|
| 1 | 以 session-start system-reminder 的 deferred tools 清單 / `ToolSearch` 為 ground truth | 取得實機真實暴露，不採信文件 / wrapper help / init hook |
| 2 | 修正 MCP 工具名引用時用 **Read 工具** 讀檔確認真實內容 | 終端對可呼叫 MCP 工具名做 redaction（見下），bash grep 輸出不可靠 |
| 3 | 高危害（提示性 / 指引性引用，會誤導實際呼叫）優先修；低危害（allowlist dead entries）次之 | 依危害分級配置修正成本 |
| 4 | 修正採版本無關描述，跨環境檔加條件註解（前綴依安裝方式而定） | project-type-generic，避免硬編碼另一個會再漂移的名稱 |

### 終端 MCP 工具名 redaction（重要識別訊號）

bash `grep` / `rg` 輸出會把「實際可呼叫的 MCP 工具名」替換為 `n`（如搜 `codegraph_status` 命中行顯示 `mcp__codegraph__n`，serena 工具顯示 `mcp__ln`）。這是顯示層 redaction，不影響檔案真實內容。**驗證 MCP 工具名引用時改用 Read 工具**，勿單憑 bash grep 輸出判讀有無 / 是否修正成功。

**Why**：MCP 工具的真實暴露只在 runtime（deferred tools 清單 / ToolSearch）可見，靜態文件是過期快照。

**Consequence**：依漂移文件呼叫不存在工具會浪費回合並誤判「平台不支援」；init hook 提示引用失效工具名使其驗證指引形同失效；漂移橫跨多檔時逐一發現成本高（本案例 3 檔）。

**Action**：修改 / 驗證任何框架文件的 MCP 工具名引用前，先以 deferred tools 清單比對；驗證用 Read 而非 bash grep。

## 識別訊號表

| 訊號 | 判讀 |
|------|------|
| ToolSearch 精確選取某 MCP 工具回 "No matching deferred tools found" | 工具名漂移 / 不存在，需查實機正確名 |
| grep MCP 工具名命中行顯示 `mcp__<server>__n` / `mcp__ln` | 終端 redaction，改用 Read 驗證真實內容 |
| 速查表 / 範例回應含 nodes/edges 等具體數字但工具不存在 | 舊版工具的真實輸出快照，工具已改名 / 移除 |
| 同 server 文件中混用兩種前綴 | 安裝方式漂移（user-level vs plugin） |

## 與其他規則 / PC 的關係

| 對象 | 關係 |
|------|------|
| PC-172（wrapper 參數推斷未經 runtime 驗證） | 同源——靜態介面（help / 文件）不等於 runtime 真實行為 |
| PC-159（安裝指令 fresh shell 驗證） | 同源——靜態推斷不足採信，需實機驗證 |
| quality-baseline.md「測試綠燈不等於 Runtime 正確」 | 本 PC 是其在「文件 MCP 引用」面向的延伸 |
| memory `feedback_mcp_tool_name_drift_in_framework` | 本 PC 的跨對話記憶對應（雙通道記錄） |

## 案例文件來源

codegraph_status 漂移盤點與修復（2026-06-04，commit `d184ccd6` / `862602e2` / `61e588a7`；ticket 0.19.1-W1-033 / W1-034 / W1-035）。
