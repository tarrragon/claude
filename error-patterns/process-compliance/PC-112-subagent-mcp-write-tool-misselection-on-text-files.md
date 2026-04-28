---
id: PC-112
title: Subagent 對非程式碼檔案誤選 MCP 寫入工具導致 early stop
category: process-compliance
severity: high
created: 2026-04-28
related:
 - PC-088
 - PC-059
---

# PC-112: Subagent 對非程式碼檔案誤選 MCP 寫入工具導致 early stop

## 症狀

Subagent（背景派發）執行 markdown / 一般文字檔修改任務時：

1. 自選 `mcp__serena__replace_content` 或 `mcp__serena__replace_symbol_body` 等 LSP-based 寫入工具，而非 Edit / Write
2. MCP 寫入工具不在 `settings.local.json` `permissions.allow` 列表 → 背景無人互動批准 → 自動拒絕
3. **錯誤泛化**：subagent 把「serena 寫入被拒」泛化為「所有寫入工具都被拒」，**未實際嘗試** Edit / Write 即停止
4. 回報「Both Edit and mcp__serena__* have been denied」誤導 PM，使 PM 誤以為是 runtime / 權限問題

## 觸發情境

| 條件 | 說明 |
|------|------|
| serena MCP 全域配置 | `~/.claude.json` 包含 serena server，所有 subagent 自動載入 |
| MCP server instructions 強制要求 | system-reminder 要求 subagent 啟動時 call `initial_instructions` → 看到 serena 全部能力清單 |
| 修改標的為非程式碼檔案 | `.md` / `.txt` / `.yaml` 等無 LSP 符號可解析的檔案 |
| 任務 prompt 未顯式指定工具 | 留給 subagent 自選 |
| 背景派發無互動 | 工具拒絕無法被人為批准，subagent 直接收到 deny |

## 根因

### 根因一：工具名稱誤導（核心 bias）

`mcp__serena__replace_content` 名稱暗示「結構化替換」，比 `Edit` 聽起來「更精準」。LLM 評估工具時被名稱誤導，未考量：

- serena 的價值是 **LSP 符號級操作**（rename_symbol、replace_symbol_body、find_referencing_symbols）
- 對 markdown / 一般文字檔，serena **沒有 AST 可解析**，`replace_content` 退化為 regex 替換，**等價於 Edit 甚至更差**（多一層 MCP overhead）

| 標的類型 | serena 寫入工具優勢 | 推薦工具 |
|---------|------------------|---------|
| 程式碼（.py / .ts / .dart 等有 LSP 支援） | 符號邊界 / 跨檔 rename / AST 安全 | `mcp__serena__rename_symbol` / `replace_symbol_body` |
| Markdown / 一般文字檔 | 無，退化為 regex | `Edit` / `Write` |
| 設定檔（YAML / JSON） | 無 LSP 結構優勢 | `Edit` / `Write` |

### 根因二：subagent 缺 fallback 規則

Subagent 對「工具被拒」缺乏標準應對流程，預設行為是：

- 收到第一個寫入工具 deny → 推論「所有寫入路徑都不通」→ stop & report
- **未實測** 其他寫入工具是否可行
- 把 MCP 工具的拒絕泛化到 native 工具（Edit / Write），錯誤地認定整個寫入路徑被封閉

### 根因三：規則層缺少跨 agent 工具選擇引導

`.claude/agents/AGENT_PRELOAD.md` 與各語言 agent 主文均未明示「程式碼 vs 文字檔的工具選擇規則」，subagent 啟動時只看到 serena 完整工具清單而無使用邊界。

## 案例：W17-088 派發失敗

**事件**：派發 `thyme-documentation-integrator`（permissionMode=acceptEdits）執行 Edit `.claude/agents/basil-writing-critic.md`（純 markdown 編輯）。

**結果**：thyme 回報「Both Edit and mcp__serena__replace_content have been denied」並停止；PM 誤以為是 runtime / `.claude/` 路徑保護問題，發起多輪根因分析。

**驗證實驗**（W17-088 後續）：

| 實驗 | prompt 限定 | 標的 | 結果 |
|------|-----------|------|------|
| A | 限定 Edit | `docs/struct.md` | Edit 成功 |
| C | 限定 Edit | `.claude/agents/AGENT_PRELOAD.md` | Edit 成功 |

實驗證明：thyme 用純 Edit 對 markdown 檔案（包括 `.claude/` 路徑）皆可成功。**原失敗根因確認為本 PC 描述的工具選擇 + early stop 雙因疊加**，非 runtime 限制。

## 防護措施

### 短期（規則層）

- `.claude/agents/AGENT_PRELOAD.md` 新增「工具選擇規則」章節，含程式碼 vs 文字檔對照表
- 影響範圍：所有 subagent 啟動時 auto-load，無例外

### 中期（agent 主文層）

- 文件操作型 agent（thyme-documentation-integrator、mint-format-specialist 等）加「Fallback 規則」
- 規則內容：MCP 寫入工具被拒時必須 fallback 嘗試 Edit / Write 再回報 deny；禁止 self-imposed early stop

### 長期（hook 層）

- 設計 `mcp-write-tool-on-text-file-guard-hook.py`（PreToolUse）
- 條件：`tool_name` 以 `mcp__serena__` 開頭且為寫入工具 + `file_path` 副檔名為 `.md` / `.txt` / `.yaml` / `.json`
- 行為：deny 並提示「請改用 Edit/Write，PC-112 規則」

### Subagent 啟動 self-check（建議）

派發 agent 時 prompt 顯式列出工具邊界：

```
[工具限定]
- 修改 markdown / 一般文字檔：使用 Edit / Write
- 修改程式碼（含符號級重構）：可用 mcp__serena__rename_symbol / replace_symbol_body
- 禁止 mcp__serena__replace_content / replace_symbol_body 用於非程式碼檔案
```

## 與其他 pattern 的關係

- **PC-088**（LLM 路徑步驟數估算偏誤）：本 PC 是 PC-088 的近親但本質不同。PC-088 是「步驟數估算錯誤」，本 PC 是「工具能力誤判 + early stop」
- **PC-059**（代理人 Tools 宣告 ≠ runtime 權限）：本 PC 案例最初被誤診為 PC-059 retry6（runtime 限制），實證後確認是工具選擇問題；PC-059 retry6 仍保留作為「`.claude/` 內 subagent Edit 的歷史誤診紀錄」

## 檢測訊號

Subagent 回報以下字串時，優先懷疑本 PC：

- 「Both Edit and mcp__serena__* have been denied」
- 「permission denied」+ 同時提及 Edit 與 mcp 工具
- 派發任務為 markdown / 文字檔修改（非程式碼）
- 修改標的副檔名為 `.md` / `.txt` / `.yaml` / `.json`

→ 立即重派並 prompt 顯式限定 Edit 工具

## 記錄於 Memory

對應 memory 升級候選：`feedback_subagent_mcp_write_tool_misselection.md`（待 framework 規則落地後同步）
