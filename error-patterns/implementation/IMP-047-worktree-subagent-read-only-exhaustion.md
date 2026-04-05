# IMP-047: Worktree Subagent 只讀不寫 — 回合耗盡前未產出程式碼

## 錯誤摘要

派發 worktree subagent 執行 Phase 3b 實作任務時，agent 持續讀取檔案理解 codebase，但在回合限制（約 15-20 輪）內未執行任何 Write 操作，導致 worktree 無任何程式碼產出。

## 症狀

- Worktree agent 完成後 `git diff --stat` 為空
- Agent output 中只有 Read/Grep/Bash(ls) 操作，Write 次數為 0
- Agent 最後一條訊息為 "Now let me check..." 或 "Let me create..." 但未實際執行

## 根因分析

1. **Subagent 預設行為**：傾向先完整理解 codebase 再動手寫程式碼
2. **回合數有限**：Worktree agent 的回合數約 15-20 輪，大型專案（100+ 檔案）的研究階段即可耗盡
3. **Specialized agent 更謹慎**：如 thyme-extension-engineer 比 general-purpose agent 更傾向先研究

## 觸發條件

- 派發 worktree subagent 實作程式碼（Phase 3b）
- 專案規模較大（src/ 目錄含 50+ 檔案）
- Prompt 未包含具體程式碼，只提供規格引用

## 解決方案

派發前評估 subagent 的 tool call 預算（~20 次/turn）。複雜任務使用分工模式。

詳見 `.claude/pm-rules/two-stage-dispatch.md`（平台限制數據、預算評估、分工流程）。

### 已棄用的方案

~~v1.0.0「prompt 含完整程式碼」~~ — W2-005 驗證失敗：200+ 行程式碼佔用 prompt context，代理人仍耗盡。

## 防護措施

1. **派發前評估 tool call 預算**（詳見 `two-stage-dispatch.md`）
2. **程式碼放 Ticket 而非 prompt**（減少 output token 佔用）
3. **反覆失敗時改用主線程在 feature 分支直接操作**

## 相關 Ticket

- 0.17.2-W2-002（首次發現，Phase 3b 派發 thyme-extension-engineer 3 次失敗）
- 0.17.2-W2-003（同上）
- 0.17.2-W2-005（二次驗證，4 次派發失敗，prompt 含完整程式碼方案失效）
- 0.17.2-W2-019（系統性分析，提出 Ticket 中心化方案）

## 發現日期

2026-04-05

---

**Last Updated**: 2026-04-06
**Version**: 2.0.0 - 從「prompt 含完整程式碼」修正為「Ticket 含完整程式碼」（0.17.2-W2-020）
