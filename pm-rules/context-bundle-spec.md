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

## 認領時 Context 驗證

PM 認領 Ticket 後、填寫 Context Bundle 前，必須先完成 Context 驗證：

| 驗證項 | 動作 | 失敗時處理 |
|-------|------|-----------|
| 目標檔案存在 | glob/ls 確認 where.files 路徑 | 關閉 Ticket 或修正 where.files |
| 前提假設成立 | 確認架構/依賴/API 未變更 | 更新 Ticket 描述或重新評估 |
| 跨專案關聯性 | 確認範疇正確、無重疊 Ticket | 關閉/遷移/合併重疊 Ticket |

> **來源**：歷史經驗——曾有 Ticket 的目標檔案不存在於當前 codebase，浪費認領後的分析時間。

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

## 代理人中間進度更新

> **目標**：PM 查 Ticket 即可知道代理人進度，不需要查代理人 output。只有異常（失敗/阻塞）時才需要 PM-代理人直接溝通。

### 更新時機

代理人在以下時機執行 `ticket track append-log` 更新 Ticket：

| 時機 | 更新內容 | 範例 |
|------|---------|------|
| 開始工作 | 確認已讀取 Context Bundle | `開始執行，已讀取 Context Bundle` |
| 關鍵階段完成 | 階段結果 + 下一步 | `測試通過 5/5，開始實作第二個函式` |
| 遇到阻塞 | 阻塞原因 + 需要什麼 | `缺少 X 模組的 API 簽名，需 PM 補充` |
| 任務完成 | 完成摘要（見上節） | 完整的 Phase N 完成摘要 |

### 標準 Agent Prompt 模板（含中間更新）

```
Ticket: {ticket_id}
任務: {ticket title}
Ticket 路徑: docs/work-logs/v{version}/tickets/{ticket_id}.md

請 Read Ticket 取得完整 Context Bundle 和驗收條件。

進度更新規範：
- 開始時：ticket track append-log {ticket_id} "開始執行，已讀取 Context Bundle"
- 關鍵階段完成時：ticket track append-log {ticket_id} "階段摘要"
- 完成時：更新 Solution 和 Test Results 區段
```

### PM 行為

| PM 想知道進度時 | 正確做法 | 禁止做法 |
|---------------|---------|---------|
| 查詢單一 Ticket | `ticket track query {id}` 看 log | 用 SendMessage 問代理人 |
| 查詢全局進度 | `ticket track snapshot` | 逐一檢查每個代理人的 output |
| 代理人阻塞 | 代理人已更新 Ticket，PM 看到後補充資訊 | 定時輪詢代理人狀態 |

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

**Last Updated**: 2026-04-08
**Version**: 2.2.0 - 新增代理人中間進度更新規範
