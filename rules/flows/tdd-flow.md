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

並非所有任務都需要完整 TDD（Phase 0-4）。以下任務類型適用簡化流程。

### 遷移/轉換類任務（Migration/Conversion）

**定義**：將現有資料、ID、格式或介面從一種狀態機械性轉換為另一種狀態的任務。

**典型範例**：

| 任務 | 說明 |
|------|------|
| `ticket migrate` | Ticket ID 格式遷移 |
| 資料庫 schema 遷移 | 欄位重命名、資料格式轉換 |
| API 版本遷移 | v1 → v2 介面對應轉換 |
| handoff 格式遷移 | MD → JSON 格式轉換 |
| 命名規則批量重新命名 | 統一命名規範 |

**識別標準**（任一符合即視為遷移任務）：

- 主要工作是「轉換」而非「建立新業務邏輯」
- 輸出可完全由輸入推導（無新業務規則）
- 現有測試或驗證步驟已足夠確認正確性

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

**禁止行為**：

| 禁止 | 說明 |
|------|------|
| 以「遷移任務」跳過結果驗證 | 驗證是遷移任務不可省略的步驟 |
| 無 dry-run 或備份直接執行不可回滾的遷移 | 須先備份或執行 dry-run |
| 將有新業務邏輯的任務誤判為遷移 | 遷移是純轉換，有新邏輯則走完整 TDD |

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

**豁免條件（可簡化為單步驟，直接 Phase 4b，跳過 4a/4c）**：

| 豁免情況 | 說明 |
|---------|------|
| 小型修改（修改 <= 2 個檔案） | 影響範圍有限，多視角成本大於收益 |
| DOC 類型任務 | 純文件更新，不涉及程式碼品質 |
| 任務範圍單純（單一模組、修改目的明確） | 低複雜度任務，cinnamon 單視角已足夠 |

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

**Last Updated**: 2026-03-08
**Version**: 2.3.0 - 修正 Phase 4b 豁免路由：「直接到完成」→「/tech-debt-capture → 完成」，與 checkpoint-details 統一（0.1.0-W22-004）
