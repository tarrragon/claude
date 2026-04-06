# Context Bundle 規範

> **目標**：PM 在派發代理人前，將該代理人需要的所有資訊寫入 Ticket，代理人只需讀取 Ticket 即可開始工作。

---

## 定義

**Context Bundle** 是 Ticket 執行日誌中的一個區段。PM 在派發代理人前，透過 `ticket track append-log --section "Execution Log" "### Context Bundle\n..."` 寫入下一階段代理人所需的前置資訊。

---

## 核心原則

1. **Inline 優先**：關鍵資訊直接寫入，不是只給路徑讓代理人自己讀
2. **1 Read 原則**：代理人只需 1 次 Read Ticket 就能獲得全部 context
3. **簡短有效**：不超過 5K tokens，只寫代理人真正需要的

---

## 通用模板

所有 Phase 轉換和任務派發使用同一模板，PM 按需填寫相關欄位：

```markdown
### Context Bundle

**需求摘要**: {一句話描述代理人要做什麼}
**API 簽名**: {代理人需要知道的介面，inline}
**相關檔案**: {路徑 + 一句話說明，只列代理人必須讀的}
**驗收條件**: {從 Ticket 5W1H 提取}
**約束**: {代理人應知道的限制或注意事項}
**測試指令**: {如適用}
```

欄位按需填寫，不強制全填。各 Phase 有特定的額外欄位建議，詳見 `.claude/references/context-bundle-phase-guide.md`。

---

## PM 填寫流程

```
代理人完成 Phase N → PM 讀取回報 → 提取關鍵資訊 → 寫入 Context Bundle → 派發下一階段
```

**派發 prompt 只需**：Ticket 路徑 + 動作指令 + 「Context Bundle 已準備，讀取 Ticket 後開始」。

### 標準 Agent Prompt 模板

```
Ticket: {ticket_id}
任務: {ticket title}
Ticket 路徑: docs/work-logs/v{version}/tickets/{ticket_id}.md

請 Read Ticket 取得完整 Context Bundle 和驗收條件。
完成後用 ticket track append-log 更新 Solution 和 Test Results。
```

> **[強制] Prompt 長度上限**：Agent prompt 不得超過 30 行。超過表示 context 未正確存入 Ticket。（PC-040）

---

## 代理人完成摘要格式

代理人完成任務後，寫入 Ticket Solution 區段：

```markdown
### Phase {N} 完成摘要
**產出物**: {路徑}
**關鍵決策**: {1-3 個}
**下一階段需注意**: {代理人認為下一階段應知道的事}
**結果**: {數字摘要}
```

PM 從此摘要提取資訊填入下一個 Context Bundle。

---

## 禁止行為

| 禁止 | 原因 |
|------|------|
| 只給路徑不給內容 | 代理人還是要花 tool calls 讀檔案 |
| 要求代理人「自行探索」 | 浪費 50%+ tool calls |
| 跳過 Context Bundle 直接派發 | subagent ~20 tool calls 預算，探索就耗盡 |
| 將 context 嵌入 Agent prompt 而非 Ticket | Prompt 是 ephemeral 載體，agent 失敗後 context 不可重用（PC-040） |

---

## 與現有規則的關係

- `tdd-flow.md` — 階段轉換時 PM 填寫 Context Bundle 為強制動作
- `decision-tree.md` — 派發前檢查 Context Bundle 是否已填寫
- `two-stage-dispatch.md` — 任務 A 產出寫入 Context Bundle
- `claude-code-platform-limits.md` — 背景約束（~20 tool calls、32K output）

---

**Last Updated**: 2026-04-06
**Version**: 2.1.0 - 新增標準 prompt 模板、prompt 長度上限、禁止嵌入 prompt（PC-040, W3-004）
