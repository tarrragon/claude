# TDD 流程詳細說明

本文件包含 TDD 流程的豁免規則詳細、各 Phase 描述、異常處理流程和工作日誌模板。

> 精簡版（常駐載入）：.claude/rules/flows/tdd-flow.md

---

## 任務類型豁免規則 — 遷移/轉換類任務

**定義**：將現有資料、ID、格式或介面從一種狀態機械性轉換為另一種狀態的任務。

**典型範例**：

| 任務 | 說明 |
|------|------|
| `ticket migrate` | Ticket ID 格式遷移 |
| 資料庫 schema 遷移 | 欄位重命名、資料格式轉換 |
| API 版本遷移 | v1 → v2 介面對應轉換 |
| handoff 格式遷移 | MD → JSON 格式轉換 |
| 命名規則批量重新命名 | 統一命名規範 |

**適用流程（簡化）**：

| 步驟 | 要求 | 說明 |
|------|------|------|
| 前置確認 | 必要 | 確認來源狀態、目標格式、回滾方案 |
| 執行遷移 | 必要 | 依遷移腳本或步驟執行 |
| 驗證結果 | 必要 | 執行現有測試 + 確認遷移完整性 |

**TDD Phase 豁免表**：

| Phase | 標準任務 | 遷移任務 |
|-------|---------|---------|
| Phase 0（SA 審查） | 新功能/架構變更時必要 | 豁免（除非影響 3+ 模組架構） |
| Phase 1（功能設計） | 必要 | 豁免（遷移規格已明確） |
| Phase 2（測試設計） | 必要 | 豁免（使用既有測試驗證） |
| Phase 3a（策略規劃） | 必要 | 簡化為「執行計畫說明」 |
| Phase 3b（實作執行） | 必要 | 必要（執行遷移） |
| Phase 4（重構評估） | 必要 | 豁免 |

---

## Phase 1-4 詳細描述

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

### Phase 4：重構優化（三步驟）

Phase 4 分為三個子步驟，取代原本由 cinnamon-refactor-owl 單一視角包辦分析+執行的做法。

#### Phase 4a：多視角分析

**代理人**：`/parallel-evaluation` Skill（情境 B — 重構評估，視角：Redundancy/Coupling/Complexity）

**產出**：重構分析報告（什麼應該重構、什麼不該重構、優先順序建議）

#### Phase 4b：重構執行

**代理人**：@.claude/agents/cinnamon-refactor-owl.md

**前置條件**：Phase 4a 分析報告完成（報告作為輸入）

**產出**：重構後程式碼、品質改善說明、技術債務初步記錄

#### Phase 4c：多視角再審核

**代理人**：`/parallel-evaluation` Skill（情境 A — 程式碼審查，視角：Reuse/Quality/Efficiency）

**前置條件**：Phase 4b 重構完成

**產出**：審核報告（重構是否達到預期品質目標）

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

> 詳細流程：.claude/rules/flows/incident-response.md

### 情況 2：SA 審查發現問題

建立補充 Ticket → 完成補充後重新審查

### 情況 3：需要跨階段修改

建立 Ticket 記錄問題 → 完成當前階段後回到對應階段

---

## 工作日誌記錄模板

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

- .claude/rules/flows/tdd-flow.md - 精簡版（常駐）
- .claude/rules/core/decision-tree.md - 主線程決策樹
- .claude/rules/core/quality-baseline.md - 品質基線

---

**Last Updated**: 2026-03-11
**Version**: 1.0.0 - 從 tdd-flow.md v2.3.0 提取豁免規則詳細、Phase 描述、異常處理、日誌模板（W35-001.7）
