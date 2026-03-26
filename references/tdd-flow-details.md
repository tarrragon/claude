# TDD 流程詳細說明

本文件包含 TDD 流程的豁免規則詳細、各 Phase 描述、異常處理流程和工作日誌模板。

> 精簡版（常駐載入）：.claude/pm-rules/tdd-flow.md

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

## 3b 拆分評估 — 詳細說明

Phase 3a 策略文件完成後，PM 在派發 Phase 3b 前必須進行拆分可行性評估。

### 評估流程

```
Phase 3a 策略文件完成
    |
    v
PM 閱讀策略文件，提取以下資訊：
  - Phase 2 定義的 GWT scenario group（測試群組）
  - 各測試群組對應的修改檔案
  - 實作順序和依賴關係
    |
    v
任一拆分閾值觸發? （測試群組 > 1 且無交叉依賴、認知 > 10、跨層 > 2、context > 20K）
    |
    +-- 否（豁免）→ 直接派發單一 parsley 執行 Phase 3b
    |
    +-- 是 → 拆分流程
        |
        v
    依 Phase 2 的 GWT scenario group 建立子任務
    （每個子任務 = 「通過特定測試群組」）
        |
        v
    PM 使用 phase3b-prompt-template.md 提取必要資訊
    （API 簽名 + 測試案例 + 相關常數）
        |
        v
    每個子任務指定 where.files（無交集）
        |
        v
    並行安全檢查（parallel-dispatch.md）
        |
        v
    並行派發 parsley（每個子任務一個代理人，背景模式）
```

### 拆分粒度

**拆分單位是 Phase 2 的 GWT scenario group（測試群組），非模組或檔案。**

| 拆分方式 | 適用場景 | 對應 task-splitting.md 策略 |
|---------|---------|--------------------------|
| 按測試群組（推薦） | Phase 3b 實作拆分 | 策略 7 |
| 按架構層 | 跨 domain/service/UI 層 | 策略 1 |
| 按功能模組 | 涉及多個獨立模組 | 策略 2 |

### 範例

**場景**：Phase 2 定義了 3 個 GWT scenario group：TC-01~TC-13（連線管理）、TC-14~TC-16,TC-18~TC-34（事件推送+心跳+分頁）。

**評估**：
- 測試群組數 = 2（無交叉依賴，觸發拆分）
- 預估 context：各子任務 < 20K tokens

**拆分結果**：
- 子任務 A：通過 TC-01~TC-13（連線管理）
- 子任務 B：通過 TC-14~TC-16,TC-18~TC-34（事件推送+心跳）
- PM 使用 prompt 模板提取 API 簽名 + 測試案例
- 並行派發兩個 parsley 代理人

### 與現有規則的一致性

| 規則 | 關係 |
|------|------|
| task-splitting.md | 拆分閾值和策略來自此文件（策略 7：按測試群組） |
| parallel-dispatch.md | 並行安全檢查和派發規則來自此文件 |
| phase3b-prompt-template.md | PM 派發時的資訊提取模板 |
| decision-tree.md 第負一層 | 並行化評估原則的 TDD 具體實踐 |

---

## Phase 1-3 代理人自治執行規範

> **來源**：0.1.0-W43-003 — 減少 PM 中轉開銷，Phase 1-3 代理人自行管理 Ticket 和 commit。

### 自治範圍

| 職責 | Phase 1/2/3a（自治） | Phase 3b+（PM 管理） |
|------|---------------------|---------------------|
| 更新 Ticket Execution Log | 代理人自行 | 代理人自行 |
| git commit | 代理人自行 | PM 收到回報後執行 |
| git push | 禁止 | PM 統一執行 |
| 下一階段派發 | PM（收到成功通知後全自動） | PM（依決策樹路由） |
| 錯誤處理 | 回報失敗 + 原因，PM 派發 incident-responder | 同左 |

### 代理人自治執行清單

Phase 1/2/3a 代理人完成工作後，依序執行：

```
1. 確認產出物完整（功能規格/測試案例/策略文件）
2. ticket track append-log {id} --section "Solution" "產出物描述"
3. git add {相關檔案}
4. git commit -m "feat({ticket-id}): Phase X 完成 - {摘要}"
5. ticket track complete {id}
6. 回報主線程：「Phase X 完成，Ticket {id} 已更新」
```

### 回報格式

**成功回報**（回傳給主線程的訊息）：

```
Phase X 完成。Ticket {id} 已更新並 commit。
```

**失敗回報**：

```
Phase X 失敗。原因：{簡述}。建議：派發 incident-responder 分析。
```

**禁止回報**：完整分析報告、逐步實作過程、程式碼片段。這些內容寫入 Ticket Execution Log。

### PM 收到回報後的動作（全自動，決策樹情境 D1）

PM 收到 Phase 1/2/3a 的成功回報後，**全自動派發下一 Phase**（不需要 AskUserQuestion）：

| 收到 | 下一步 |
|------|-------|
| Phase 1 完成 | 自動派發 Phase 2（sage-test-architect） |
| Phase 2 完成 | 自動派發 Phase 3a（pepper-test-implementer） |
| Phase 3a 完成 | 進入 3b 拆分評估（PM 評估，見 tdd-flow.md） |

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

> 詳細流程：.claude/pm-rules/incident-response.md

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

- .claude/pm-rules/tdd-flow.md - 精簡版（常駐）
- .claude/rules/core/decision-tree.md - 主線程決策樹
- .claude/rules/core/quality-baseline.md - 品質基線

---

**Last Updated**: 2026-03-12
**Version**: 1.2.0 - 新增 Phase 1-3 代理人自治執行規範章節（0.1.0-W43-003）
