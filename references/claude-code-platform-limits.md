# Claude Code Subagent 平台限制參考

> **用途**：記錄 Claude Code subagent（Agent 工具）的已知平台限制。所有派發相關規則應引用本文件的數據，避免硬編碼數字散佈在多個檔案中。
>
> **維護**：當 Claude Code 版本更新導致限制變化時，只需更新本文件。

---

## 當前已知限制

**記錄日期**：2026-04-06
**Claude Code 版本**：2.1.92
**資料來源**：GitHub Issues + Web Search + 專案實測（W2-005）

| 限制項目 | 數值 | 來源 | 備註 |
|---------|------|------|------|
| Per-turn tool calls | ~20 次 | [GitHub #33969](https://github.com/anthropics/claude-code/issues/33969) | 2026-03 起從 60-80+ 降至 ~20，觸發 `stop_reason: "pause_turn"` |
| Subagent output token | 32K（硬編碼） | [GitHub #25569](https://github.com/anthropics/claude-code/issues/25569) | `CLAUDE_CODE_MAX_OUTPUT_TOKENS` 不套用到 subagent |
| Subagent context overhead | ~20K tokens | [morphllm.com 分析](https://www.morphllm.com/claude-subagents) | 系統 prompt + 規則載入 + 工具定義 |
| Subagent context exhaustion | 已知 bug | [GitHub #18240](https://github.com/anthropics/claude-code/issues/18240) | context limit 過早觸發，即使 usage 看似正常 |
| Output token 設定不生效 | 已知 bug | [GitHub #29488](https://github.com/anthropics/claude-code/issues/29488) | Opus 4.6 被限制在 32K |
| --max-turns（CLI） | 可配置 | [官方文件](https://code.claude.com/docs/en/sub-agents) | `claude -p "..." --max-turns N` |

---

## 實際影響

### 對派發的影響

Subagent 約有 **20 次工具呼叫** 完成任務。每次 Read、Edit、Bash、Grep 各算一次。

典型操作的 tool call 消耗估算：

| 操作 | 估算 tool calls |
|------|-----------------|
| 讀取 1 個檔案 | 1 |
| Grep 搜尋 | 1 |
| 讀取設計文件/規格 | 1-3 |
| 探索程式碼風格（多檔案） | 3-8 |
| Edit 寫入程式碼 | 1-3 |
| Bash 執行測試 | 1-2 |
| Bash git 操作 | 1-2 |

**經驗法則**：如果任務需要「探索 5+ 檔案 + 寫入 + 測試 + commit」，幾乎肯定超出 20 次預算。

### 對 output 的影響

32K output token 約等於 ~800 行程式碼（含格式化）。單次 Edit 寫入 200-300 行程式碼通常不會觸發此限制，但如果代理人同時產出大量思考文字（extended thinking），可用 output 會減少。

---

## 專案對應調整

以下是本專案針對這些限制所做的調整（2026-04-06）：

| 調整 | 檔案 | 版本 | 說明 |
|------|------|------|------|
| 分工模式 | `.claude/pm-rules/two-stage-dispatch.md` | v2.0.0 | 任務 A（探索設計）+ 任務 B（注入驗證）分離 |
| Tool call 預算評估 | `.claude/pm-rules/task-splitting.md` | v4.4.0 | 拆分觸發條件新增 subagent tool call 預算 |
| IMP-047 修正 | `.claude/error-patterns/implementation/IMP-047-*.md` | v2.0.0 | 從「prompt 含程式碼」改為「Ticket 含程式碼」|
| Phase 3b 派發指南 | `.claude/pm-rules/phase3b-dispatch-guide.md` | v2.0.0 | 引用 tool call 預算模型 |

---

## 變更歷史

| 日期 | Claude Code 版本 | 變更內容 | 來源 |
|------|-----------------|---------|------|
| 2026-03（約） | ~2.1.x | per-turn tool calls 從 60-80+ 降至 ~20 | GitHub #33969 |
| 2026-04-06 | 2.1.92 | 本文件建立，記錄已知限制和專案對應調整 | W2-005/W2-019/W2-020 |

---

## 驗證方式

當懷疑限制已變化時，可用以下方式驗證：

1. **Tool call 限制**：派發一個只做 Read 的測試代理人，計算它能執行幾次 Read 後結束
2. **Output token 限制**：檢查 `CLAUDE_CODE_MAX_OUTPUT_TOKENS` 環境變數是否生效
3. **GitHub Issues**：搜尋 `anthropics/claude-code` 的 Issues 確認最新狀態

---

**Last Updated**: 2026-04-06
**Version**: 1.0.0 - 初始建立（W2-005/W2-019/W2-020 經驗整理）
