# Phase 3b 派發指南

本文件定義 TDD Phase 3b（實作執行）的代理人派發規範。本文件是 `context-bundle-spec.md` 在 Phase 3b 的特化應用。

> **來源**：IMP-047 — Worktree subagent 平台限制（~20 tool calls/turn、32K output token）導致複雜任務耗盡。

---

## 核心原則

> 1. **Context Bundle 優先**：派發前 PM 必須在 Ticket 中填寫 Context Bundle（見 `context-bundle-spec.md`）
> 2. **Tool call 預算**：如果「探索 + 寫入 + 測試 + commit」超過 15 次，使用分工模式（見 `two-stage-dispatch.md`）

---

## 派發策略選擇

| 任務複雜度 | 策略 | 說明 |
|-----------|------|------|
| 簡單（<= 15 tool calls） | 直接派發 | 程式碼少、位置明確、不需探索 |
| 複雜（> 15 tool calls） | 分工模式 | 任務 A（設計→Ticket）+ 任務 B（注入→目標檔案） |
| 主線程在 feature 分支 | 直接操作 | 不受 subagent 限制，最可靠 |

### 簡單任務 Prompt 要點

- 提供精確的檔案路徑和注入位置
- 如有程式碼，放在 Ticket/設計文件中，prompt 只提�� Ticket 路徑
- 明確告知「不需要探��其他檔案」

### 複雜任務分工模式

參見 `two-stage-dispatch.md`：
- **任務 A**：sage/pepper 探索 + 設計，產出程式碼到 Ticket
- **任務 B**：general-purpose 從 Ticket 讀取程式碼並注入

---

## Agent 類型選擇

| 場景 | 推薦 Agent | 原因 |
|------|-----------|------|
| 注入已設計好的程式碼 | general-purpose | 最直接，tool calls 最少 |
| 需要框架專業知識 | specialized（thyme/parsley） | 但預算更緊，更傾向探索 |
| 反覆失敗 | 主線程在 feature 分支 | 繞過 subagent 限制 |

---

## 禁止行為

| 禁止 | 原因 |
|------|------|
| 只給規格引用讓 agent 自行研究和設計 | Agent 回合耗盡前只讀不寫（IMP-047） |
| prompt 中嵌入大量程式碼（200+ 行） | 佔用 output token 預算，改用 Ticket 存放 |
| 不評估 tool call 預算就派發 | 風險不可控 |

---

## 相關文件

- .claude/pm-rules/context-bundle-spec.md - Context Bundle 規範（本文件為其 Phase 3b 特化）
- .claude/pm-rules/two-stage-dispatch.md - 分工模式詳細規範
- .claude/error-patterns/implementation/IMP-047-worktree-subagent-read-only-exhaustion.md - 錯誤模式記錄
- .claude/pm-rules/tdd-flow.md - TDD 流程

---

**Last Updated**: 2026-04-06
**Version**: 2.0.0 - 從「prompt 含完整程式碼」改為「tool call 預算 + 分工模式」（多視角審查修正）
