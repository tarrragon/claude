# Plan-to-Ticket 轉換流程

Plan Mode 產出到 Atomic Ticket 的轉換流程。

---

## 8 步驟流程

1. **解析 Plan 檔案** - 提取功能名稱、步驟、修改檔案
2. **識別任務項目** - 原子性檢查、分類（IMP/ADJ/ANA/DOC）
3. **評估複雜度** - 認知負擔指數，決定是否拆分
4. **映射 TDD 階段** - 新功能→完整 TDD，小修改→簡化，純文件→DOC
5. **識別依賴關係** - 資料、架構、TDD 依賴，標記 blockedBy
6. **並行分組** - 無依賴同階段任務分組到同一 Wave
7. **產生 Tickets** - `/ticket create` 建立符合格式的 Atomic Ticket
8. **驗證輸出** - 確認所有 Ticket 符合規範

---

## 觸發條件

| 條件 | 強制性 |
|------|--------|
| `.claude/plans/` 下有已核准 Plan | 必須 |
| 用戶已確認（Plan Mode 退出） | 必須 |
| 目標版本和 Wave 已確定 | 必須 |

**不觸發**：Plan 未核准、純研究型 Plan、已有對應 Ticket

---

## 執行中額外發現（強制流程）

> **核心原則**：計畫執行中發現的超範圍需求必須立即建立 Ticket，不可忽視，不可中斷主線。

### 什麼算「額外發現」

| 情況 | 是否觸發 |
|------|---------|
| 執行 Ticket 時發現相關模組需同步更新 | 是 |
| Agent 分析時識別出計畫未涵蓋的需求 | 是 |
| 實作中發現設計缺口（規則/流程/文件） | 是 |
| 超出當前 Ticket scope 的延伸工作 | 是 |
| 計畫內的子步驟細分 | 否 |
| 已在原計畫 Ticket 驗收條件中的工作 | 否 |

### 強制處理流程

```
計畫執行中發現超範圍需求
    |
    v
[強制] 立即執行 /ticket create 建立 pending Ticket
    |
    v
新 Ticket 歸入當前版本（Wave 依複雜度決定）
    |
    v
繼續執行當前計畫主線（不中斷）
    |
    v
當前 Ticket 完成後 → 處理新建的 pending Ticket
```

### 禁止行為

| 禁止 | 說明 |
|------|------|
| 忽視不建立 Ticket | 額外發現必須立即追蹤 |
| 中斷主線去處理額外發現 | 先建 Ticket，完成當前任務後再執行 |
| 僅口頭回報不建 Ticket | 必須有可追蹤的 Ticket 記錄 |
| 等計畫完成後再補建 Ticket | 必須**立即**建立 |

---

## 相關文件

- .claude/references/plan-to-ticket-mapping-details.md - 映射規則、依賴分析、並行分組
- .claude/references/plan-to-ticket-details.md - 驗證清單、報告格式
- .claude/rules/flows/ticket-lifecycle.md - Ticket 生命週期
- .claude/rules/flows/tdd-flow.md - TDD 流程
- .claude/rules/core/cognitive-load.md - 認知負擔評估

---

**Last Updated**: 2026-03-03
**Version**: 3.1.0 - 新增「執行中額外發現」強制流程（W30-002）
