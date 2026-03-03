# TDD 含 SA 前置審查流程

本文件定義包含 SA（System Analyst）前置審查的完整 TDD 開發流程。

---

## 流程總覽

```
新功能需求
    |
    v
[Phase 0] SA 前置審查 → [system-analyst](../agents/system-analyst.md)
    |
    +-- 審查通過 --> 進入 TDD 流程
    +-- 審查不通過 --> 補充前置作業 --> 重新審查
    |
    v
[Phase 1] 功能設計 → [lavender-interface-designer](../agents/lavender-interface-designer.md)
    |
    v
[Phase 2] 測試設計 → [sage-test-architect](../agents/sage-test-architect.md)
    |
    v
[Phase 3a] 策略規劃 → [pepper-test-implementer](../agents/pepper-test-implementer.md)
    |
    v
[Phase 3b] 實作執行 → [parsley-flutter-developer](../agents/parsley-flutter-developer.md)
    |
    v
[Phase 4] 重構優化 → [cinnamon-refactor-owl](../agents/cinnamon-refactor-owl.md)
    |
    v
完成 → 提交
```

---

## Phase 0：SA 前置審查

### 觸發條件

| 條件 | 需要 SA 審查 |
|------|-------------|
| 新功能需求 | 是 |
| 架構變更 | 是 |
| 影響 3+ 模組 | 是 |
| 小型修改/Bug 修復 | 否 |

### 審查內容

1. **系統一致性檢查** - 與現有架構是否一致、遵循設計原則、無命名衝突
2. **重複實作檢查** - 無類似功能、無可重用元件、無重複造輪子
3. **需求文件完整性** - 需求書有記錄、用例有定義、驗收標準明確

### 審查結論

| 結論 | 下一步 |
|------|-------|
| 通過 | 進入 Phase 1 |
| 需補充 | 完成補充後重新審查 |
| 不建議 | 升級到 PM 決定 |

> 詳細規格：@.claude/agents/system-analyst.md

---

## Phase 1-4：標準 TDD 流程

### Phase 1：功能設計

**代理人**：@.claude/agents/lavender-interface-designer.md

**產出**：功能規格文件、API 介面定義、驗收標準

### Phase 2：測試設計

**代理人**：@.claude/agents/sage-test-architect.md

**產出**：測試案例清單、Given-When-Then 規格、測試檔案結構

### Phase 3a：策略規劃

**代理人**：@.claude/agents/pepper-test-implementer.md

**產出**：實作策略文件、虛擬碼設計、技術債務評估

### Phase 3b：實作執行

**代理人**：@.claude/agents/parsley-flutter-developer.md

**產出**：可執行程式碼、通過的測試、程式碼品質報告

### Phase 4：重構優化

**代理人**：@.claude/agents/cinnamon-refactor-owl.md

**產出**：重構後程式碼、品質改善報告、技術債務記錄

---

## 階段轉換規則

### 轉換條件

| 從 | 到 | 條件 |
|----|----|----|
| Phase 0 | Phase 1 | SA 審查通過 |
| Phase 1 | Phase 2 | 功能規格完成 |
| Phase 2 | Phase 3a | 測試案例設計完成 |
| Phase 3a | Phase 3b | 策略文件完成 |
| Phase 3b | Phase 4 | 測試全部通過 |
| Phase 4 | 完成 | 重構評估完成 |

### 轉換動作

每次階段轉換時：

1. 執行 `/ticket track complete {id}`
2. 更新工作日誌
3. 派發下一階段代理人

---

## 異常處理

### 情況 1：測試失敗

```
Phase 3b 測試失敗
    |
    v
[強制] 派發 incident-responder
    |
    v
建立錯誤 Ticket
    |
    v
根據分析派發對應代理人
```

> 詳細流程：@.claude/rules/flows/incident-response.md

### 情況 2：SA 審查發現問題

建立補充 Ticket → 完成補充後重新審查

### 情況 3：需要跨階段修改

建立 Ticket 記錄問題 → 完成當前階段後回到對應階段

---

## 工作日誌記錄

每個階段完成時，更新工作日誌：

```markdown
## Phase X: [階段名稱]

### 執行資訊
- **代理人**: [代理人名稱]
- **開始時間**: [時間]
- **完成時間**: [時間]

### 產出物
- [產出1]
- [產出2]
```

---

## 相關文件

- @.claude/rules/core/decision-tree.md - 主線程決策樹
- @.claude/rules/core/quality-baseline.md - 品質基線（Phase 4 不可跳過）

---

**Last Updated**: 2026-01-23
**Version**: 2.0.0
