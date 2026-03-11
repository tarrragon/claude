# TDD 含 SA 前置審查流程

本文件定義包含 SA（System Analyst）前置審查的完整 TDD 開發流程。

---

## 流程總覽

```
新功能需求
    |
    v
[Phase 0] SA 前置審查 → [saffron-system-analyst](../../agents/saffron-system-analyst.md)
    |
    +-- 審查通過 --> 進入 TDD 流程
    +-- 審查不通過 --> 補充前置作業 --> 重新審查
    |
    v
[Phase 1] 功能設計 → [lavender-interface-designer](../../agents/lavender-interface-designer.md)
    |
    v
[Phase 2] 測試設計 → [sage-test-architect](../../agents/sage-test-architect.md)
    |
    v
[Phase 3a] 策略規劃 → [pepper-test-implementer](../../agents/pepper-test-implementer.md)
    |
    v
[Phase 3b] 實作執行 → [parsley-flutter-developer](../../agents/parsley-flutter-developer.md)
    |
    v
[Phase 4a] 多視角分析 → /parallel-evaluation B（Redundancy/Coupling/Complexity）
    |
    v（豁免時直接跳至 Phase 4b）
[Phase 4b] 重構執行 → [cinnamon-refactor-owl](../../agents/cinnamon-refactor-owl.md)
    |
    v（豁免時跳過 Phase 4c，直接執行 /tech-debt-capture → 完成）
[Phase 4c] 多視角再審核 → /parallel-evaluation A（Reuse/Quality/Efficiency）
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

> 詳細規格：@.claude/agents/saffron-system-analyst.md

---

## 任務類型豁免規則

並非所有任務都需要完整 TDD（Phase 0-4）。遷移/轉換類任務適用簡化流程。

**識別標準**（任一符合即視為遷移任務）：

- 主要工作是「轉換」而非「建立新業務邏輯」
- 輸出可完全由輸入推導（無新業務規則）
- 現有測試或驗證步驟已足夠確認正確性

**禁止行為**：

| 禁止 | 說明 |
|------|------|
| 以「遷移任務」跳過結果驗證 | 驗證是遷移任務不可省略的步驟 |
| 無 dry-run 或備份直接執行不可回滾的遷移 | 須先備份或執行 dry-run |
| 將有新業務邏輯的任務誤判為遷移 | 遷移是純轉換，有新邏輯則走完整 TDD |

> 遷移任務範例、TDD Phase 豁免表、簡化流程：.claude/references/tdd-flow-details.md（任務類型豁免規則章節）

---

## Phase 1-4：標準 TDD 流程

| Phase | 代理人 | 產出 |
|-------|-------|------|
| Phase 1 功能設計 | lavender-interface-designer | 功能規格、API 定義、驗收標準 |
| Phase 2 測試設計 | sage-test-architect | 測試案例、GWT 規格、檔案結構 |
| Phase 3a 策略規劃 | pepper-test-implementer | 策略文件、虛擬碼、債務評估 |
| Phase 3b 實作執行 | parsley-flutter-developer | 程式碼、通過測試、品質報告 |
| Phase 4a 多視角分析 | /parallel-evaluation B | 重構分析報告 |
| Phase 4b 重構執行 | cinnamon-refactor-owl | 重構程式碼、債務記錄 |
| Phase 4c 多視角再審核 | /parallel-evaluation A | 審核報告 |

**Phase 4 豁免條件（可簡化為單步驟，直接 Phase 4b，跳過 4a/4c）**：

| 豁免情況 | 說明 |
|---------|------|
| 小型修改（修改 <= 2 個檔案） | 影響範圍有限，多視角成本大於收益 |
| DOC 類型任務 | 純文件更新，不涉及程式碼品質 |
| 任務範圍單純（單一模組、修改目的明確） | 低複雜度任務，cinnamon 單視角已足夠 |

> 各 Phase 詳細描述和代理人連結：.claude/references/tdd-flow-details.md（Phase 1-4 章節）

---

## 階段轉換規則

### 轉換條件

| 從 | 到 | 條件 |
|----|----|----|
| Phase 0 | Phase 1 | SA 審查通過 |
| Phase 1 | Phase 2 | 功能規格完成 |
| Phase 2 | Phase 3a | 測試案例設計完成 |
| Phase 3a | Phase 3b | 策略文件完成 |
| Phase 3b | Phase 4a | 測試全部通過（標準流程）；直接到 Phase 4b（豁免條件） |
| Phase 4a | Phase 4b | 多視角分析報告完成 |
| Phase 4b | Phase 4c | 重構執行完成（標準流程）；/tech-debt-capture → 完成（豁免條件） |
| Phase 4c | 完成 | 多視角再審核報告完成 |

### 轉換動作

每次階段轉換時：

1. 執行 `/ticket track complete {id}`
2. 更新工作日誌
3. 派發下一階段代理人

---

## 異常處理

| 情況 | 處理方式 |
|------|---------|
| 測試失敗 | 強制派發 incident-responder → 建立 Ticket → 對應代理人修復 |
| SA 審查發現問題 | 建立補充 Ticket → 完成後重新審查 |
| 需要跨階段修改 | 建立 Ticket → 完成當前階段後回到對應階段 |

> 異常處理詳細流程和工作日誌模板：.claude/references/tdd-flow-details.md（異常處理章節）
> 事件回應流程：.claude/rules/flows/incident-response.md

---

## 相關文件

- .claude/references/tdd-flow-details.md - 豁免規則詳細、Phase 詳細描述、異常處理、日誌模板
- @.claude/rules/core/decision-tree.md - 主線程決策樹
- @.claude/rules/core/quality-baseline.md - 品質基線（Phase 4 不可跳過）

---

**Last Updated**: 2026-03-11
**Version**: 2.4.0 - 操作指引提取至 references/tdd-flow-details.md（W35-001.7）
