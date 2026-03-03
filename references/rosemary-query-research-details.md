# 查詢 vs 研究邊界規則 - 詳細情境範例

> 來源：rosemary-project-manager Agent 定義
> 參考：.claude/rules/guides/query-vs-research.md

---

## 允許直接執行的查詢

| 查詢類型 | 方式 | 說明 | 範例 |
|---------|------|------|------|
| Ticket 進度查詢 | `/ticket track` | 使用 Ticket 系統命令 | `/ticket track summary` |
| 版本資訊查詢 | Read | 讀取版本工作日誌 | 查詢 `docs/work-logs/v0.31.0/` |
| 待辦事項查詢 | Read | 讀取待辦清單 | 讀取 `docs/todolist.yaml` |
| 代理人定義查詢 | Read | 查閱代理人責任邊界 | 查詢 `.claude/agents/` |
| 專案文件查詢 | Read/Grep/Glob | 搜尋內部文件 | 查詢規則、方法論、設計文件 |
| 進度狀態檢查 | Bash | 執行專案工具查詢 | 運行 `/ticket track` 命令 |

**使用原則**：

- 查詢的目的是瞭解當前狀態和做決策
- 只使用專案內部資源
- 查詢結果直接用於派工和決策

---

## 禁止直接執行的行為（應派發研究代理人）

| 禁止行為 | 為什麼禁止 | 派發代理人 |
|---------|-----------|-----------|
| 查詢外部資源（GitHub、官方網站、API 文件） | 需要深度分析和判斷，超出主線程職責 | oregano-data-miner |
| 使用 WebFetch 或 WebSearch | 屬於外部資源研究，非內部查詢 | oregano-data-miner |
| 分析工具實現細節 | 需要技術專業知識，不是簡單查詢 | oregano-data-miner |
| 對比多個技術方案 | 屬於研究和分析，需要專業評估 | oregano-data-miner 或 saffron-system-analyst |
| 評估第三方依賴可行性 | 需要深度技術分析 | oregano-data-miner 或 saffron-system-analyst |
| 驗證工具相容性 | 需要具體測試，非簡單查詢 | oregano-data-miner 或 sumac-system-engineer |
| 查詢 API 規格詳情 | 屬於深度研究，非內部查詢 | oregano-data-miner |

---

## 情境範例

### 情境 1：需要瞭解現有 Ticket 進度

```markdown
正確做法：
1. 執行 /ticket track summary
2. 查詢相關工作日誌
3. 根據結果決策派工

禁止做法：
- 不使用 WebSearch 查詢外部 Ticket 系統
- 不分析工具實現細節
```

### 情境 2：需要瞭解第三方依賴可行性

```markdown
禁止做法：
1. 直接 WebFetch 官方文件
2. 自行對比多個方案
3. 評估相容性

正確做法：
1. 建立研究 Ticket「評估 X 依賴的可行性」
2. 派發 oregano-data-miner 或 saffron-system-analyst
3. 根據研究報告決策
```

### 情境 3：需要瞭解系統架構問題

```markdown
禁止做法：
- 自行分析架構細節
- 嘗試評估設計方案可行性

正確做法：
1. 建立分析 Ticket「評估 X 架構問題影響」
2. 派發 saffron-system-analyst
3. 根據分析結果決策
```

---

## 邊界判定清單

遇到新的查詢/研究需求時，用此清單判定：

- [ ] 這個資訊在專案內部可以找到嗎？
  - 是 → 允許直接查詢（使用 Read/Grep/Glob）
  - 否 → 繼續判定
- [ ] 這是簡單的資訊查詢還是深度分析？
  - 簡單查詢 → 可以直接執行
  - 深度分析 → 需派發研究代理人
- [ ] 是否涉及專業技術判斷？
  - 否 → 可以直接查詢
  - 是 → 需派發專業代理人
- [ ] 涉及外部資源或工具嗎？
  - 否 → 允許查詢
  - 是 → 需派發研究代理人或專業工程師

**最終判定**：任何不確定的情況，優先派發專業代理人，不自行決定。

---

**Last Updated**: 2026-03-02
**Version**: 1.0.0
**Source**: rosemary-project-manager v2.2.0 查詢 vs 研究邊界規則
