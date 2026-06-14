# 問題覺察與評估方法論：範例、Hook 程式碼與實戰案例

> **用途**：本檔為 `.claude/methodologies/problem-awareness-evaluation-methodology.md` 的衛星參考檔，存放三大核心原則的完整正反範例、Hook 系統整合程式碼，以及完整實戰案例分析。需要對照具體範例落實全局分析、需要實作 Hook 檢查邏輯，或需要研讀完整案例時按需讀取。
>
> **核心方法論（三大原則定義 + 問題分類決策樹 + 決策執行流程 + 檢查清單）**：`.claude/methodologies/problem-awareness-evaluation-methodology.md`（需回顧原則定義、決策樹判斷標準或檢查清單時讀）

---

## 原則 1 範例：全局分析優先

### 正確的全局分析（v0.12.9 實際案例）

**情境**：測試引用了不存在的事件類別。

```markdown
## 全局分析過程

### 步驟 1: 完整範圍識別
- 測試檔案分析：3 個整合測試檔案
- 事件使用情況：已存在 5 個 Import 事件，缺失 7 個事件類別
- 影響範圍：
  - import_flow_integration_test.dart - 使用已存在事件（可修復）
  - enrichment_flow_integration_test.dart - 需要 6 個 Enrichment 事件
  - error_handling_integration_test.dart - 需要 2 個 Error 事件

### 步驟 2: 根因分析
- 根本原因：Phase 1 設計時規劃了完整事件系統
- 實際狀態：v0.12.5-A 只實作了基本 Import 事件
- 問題本質：未完成實作，非設計缺陷

### 步驟 3: 全局影響評估
- 架構影響：事件系統不完整，影響跨層級整合測試
- 功能影響：Enrichment 和 Error 處理流程無法測試
- 測試影響：2/3 的整合測試無法執行

### 步驟 4: 連鎖問題識別
- 依賴關係：Enrichment 事件依賴 Import 事件完成
- 隱藏問題：可能還有其他模組也需要這些事件
```

**修復策略**（基於全局分析）：

```markdown
## 完整策略規劃

### 階段 1: 建立所有缺失事件（先完成架構）
Ticket 1: 建立 Enrichment 事件系統（6 個事件類別）
Ticket 2: 建立 Error 事件系統（2 個事件類別）

### 階段 2: 修復所有測試（統一修復）
Ticket 3: 修復 import_flow_integration_test.dart
Ticket 4: 修復 enrichment_flow_integration_test.dart
Ticket 5: 修復 error_handling_integration_test.dart

### 階段 3: 驗證整合完整性
Ticket 6: 執行所有整合測試確保 100% 通過
```

### 錯誤的分批思維（避免）

```markdown
## 錯誤的決策過程

選項 A: 分階段修復（推薦）
1. 立即修復 import_flow_integration_test.dart 的參數問題（5-10分鐘）
2. 建立缺失事件 然後修復其他測試（20-30分鐘）
3. 執行測試驗證 確保所有修復正確

選項 B: 先建立所有缺失事件，再統一修復
選項 C: 調整測試設計，移除對缺失事件的依賴
```

**錯誤原因**：

- 未進行完整全局分析就提供選項
- 推薦「分階段修復」導致局部優化
- 以「快速」作為決策依據而非「正確」
- 沒有先建立完整策略就開始執行

---

## 原則 2 範例：策略規劃先行

### 正確的策略規劃

```markdown
## 完整策略：v0.12.9 事件系統補完

### 全局問題清單（來自全局分析）
1. 缺少 6 個 Enrichment 事件類別
2. 缺少 2 個 Error 事件類別
3. 3 個測試檔案引用問題
4. 事件系統架構不完整

### 解決策略設計

#### 策略 1: 先完成架構（事件系統）
- 理由：架構完整才能進行功能實作
- Ticket 1.1: 建立 EnrichmentStartedEvent
- Ticket 1.2: 建立 EnrichmentCompletedEvent
- Ticket 1.3: 建立 EnrichmentErrorEvent
- Ticket 1.4: 建立 BatchEnrichmentStartedEvent
- Ticket 1.5: 建立 BatchEnrichmentProgressUpdatedEvent
- Ticket 1.6: 建立 BatchEnrichmentCompletedEvent
- Ticket 1.7: 建立 ImportErrorEvent
- Ticket 1.8: 建立通用 ErrorEvent（如需要）

#### 策略 2: 統一修復測試
- 理由：事件系統完成後才能正確修復引用
- Ticket 2.1: 修復 import_flow_integration_test.dart
- Ticket 2.2: 修復 enrichment_flow_integration_test.dart
- Ticket 2.3: 修復 error_handling_integration_test.dart

#### 策略 3: 驗證整合完整性
- Ticket 3.1: 執行所有整合測試
- Ticket 3.2: 驗證事件系統完整性
- Ticket 3.3: 更新文件記錄新增事件

### Ticket 依賴關係
- Ticket 1.1-1.8 可並行執行（獨立事件類別）
- Ticket 2.1-2.3 依賴 Ticket 1.1-1.8 完成
- Ticket 3.1-3.3 依賴 Ticket 2.1-2.3 完成

### 執行優先序
1. 高優先：Ticket 1.1-1.8（架構基礎）
2. 中優先：Ticket 2.1-2.3（功能修復）
3. 低優先：Ticket 3.1-3.3（驗證和文件）
```

### 錯誤的策略規劃

```markdown
## 不完整的策略（避免）

### 階段 1: 先修復簡單的
- 修復 import_flow 測試（因為快速）

### 階段 2: 再處理複雜的
- 建立缺失事件
- 修復其他測試

### 階段 3: 最後驗證
- 執行測試
```

**錯誤原因**：

- 以「簡單/複雜」作為優先序而非「架構/功能」
- 策略不完整，缺少明確的 Ticket 設計
- 依賴關係不明確
- 可能導致重複修改（先修測試 -> 建立事件 -> 再修測試）

---

## 原則 3 範例：設計問題立即停止

### 正確的設計問題判斷

**情境 1：模組引用錯誤**

```markdown
## 問題：Layer 3 UseCase 直接引用 Layer 1 Widget

### 根因分析
- 問題本質：違反 Clean Architecture 分層原則
- 問題類型：設計問題（架構缺陷）
- 影響範圍：破壞依賴倒置原則，產生架構債務

### 處理決策
- 判斷：設計問題
- 行動：立即停止功能開發
- 修正方案：
  1. 重新設計 UseCase 的輸入輸出
  2. 使用 DTO 或 ViewModel 取代 Widget 引用
  3. 確保依賴方向正確（內層 <- 外層）

### 修正後繼續
- 架構恢復合理性
- 繼續原定功能開發
```

**情境 2：事件類別缺失**

```markdown
## 問題：測試引用不存在的 EnrichmentStartedEvent

### 根因分析
- 問題本質：Phase 1 設計了事件但 Phase 3 未實作
- 問題類型：實作問題（未完成實作）
- 影響範圍：測試無法執行，但架構設計正確

### 處理決策
- 判斷：實作問題（非設計缺陷）
- 行動：按計劃修復（全局分析 -> 策略規劃 -> 執行）
- 修正方案：
  1. 完成缺失的事件類別實作
  2. 修復測試引用
  3. 驗證整合完整性
```

### 錯誤的設計問題判斷

```markdown
## 錯誤情境：混淆設計問題和實作問題

### 問題：Layer 3 UseCase 直接引用 Layer 1 Widget

錯誤判斷：「這是實作問題，只要調整引用就好」
- 理由錯誤：未識別架構違反
- 後果：產生架構債務，長期維護困難

正確判斷：「這是設計問題，必須修正架構」
- 理由正確：違反分層原則
- 行動：立即停止 -> 修正設計 -> 繼續
```

---

## Hook 系統整合

### Hook 觸發時機

- **PreToolUse(TodoWrite)**: 檢查 Ticket 是否經過全局分析
- **UserPromptSubmit**: 檢查決策建議是否基於完整策略
- **發現多選項決策**: 要求提供全局分析依據

### 檢查機制

```python
# 核心檢查邏輯
def check_problem_awareness(decision_content):
    # 檢查 1: 是否進行全局分析
    if has_multiple_related_issues(decision_content):
        if not has_global_analysis(decision_content):
            return {"decision": "block",
                   "reason": "發現多個相關問題，必須先進行全局分析"}

    # 檢查 2: 是否建立完整策略
    if has_solution_options(decision_content):
        if not has_complete_strategy(decision_content):
            return {"decision": "block",
                   "reason": "必須先建立完整策略，不允許基於速度推薦分批處理"}

    # 檢查 3: 是否識別設計問題
    if has_architecture_violation(decision_content):
        if not has_immediate_stop_action(decision_content):
            return {"decision": "block",
                   "reason": "發現設計問題，必須立即停止功能開發並修正設計"}

    # 檢查 4: 是否有分批思維語言
    if has_batch_thinking_language(decision_content):
        return {"decision": "block",
               "reason": "發現分批思維，必須先完成全局分析和策略規劃"}

    return {"decision": "allow"}

# 分批思維語言檢測
def has_batch_thinking_language(content):
    batch_thinking_patterns = [
        "分階段修復", "先做簡單的", "快速修復",
        "立即修復.*再處理", "先修復.*然後",
        "階段性處理", "逐步修復", "分批處理"
    ]
    return any(pattern in content for pattern in batch_thinking_patterns)
```

### 修復機制

發現違反問題覺察原則時的處理流程：

1. **阻止操作**：立即停止 Ticket 建立或決策執行
2. **要求全局分析**：明確指出缺少的分析步驟
3. **要求完整策略**：必須設計所有 Ticket 再執行
4. **再次驗證**：確認符合三大原則

---

## 實戰案例分析

### 案例 1: v0.12.9 事件系統問題（完整示範）

**問題發現**：

```markdown
測試執行失敗，發現以下問題：
- import_flow_integration_test.dart 使用錯誤的事件參數
- enrichment_flow_integration_test.dart 引用不存在的事件
- error_handling_integration_test.dart 引用不存在的事件
```

**錯誤的決策過程（分批思維）**：

```markdown
主線程推薦：

選項 A: 分階段修復（推薦）
1. 立即修復 import_flow 測試參數問題（5-10分鐘）
2. 建立缺失事件然後修復其他測試（20-30分鐘）
3. 執行測試驗證

推薦理由：快速見效，分批處理
```

**問題分析**：

- 未進行全局分析就提供選項
- 以「快速」作為推薦依據
- 分批處理導致可能重複修改測試
- 未識別這是「未完成實作」而非「參數錯誤」

**正確的決策過程（全局分析 -> 策略規劃）**：

**步驟 1: 全局分析**

```markdown
## 完整範圍識別
- 已存在事件：5 個 Import 事件（ImportStartedEvent, ImportProgressUpdatedEvent, etc.）
- 缺失事件：7 個事件類別
  - Enrichment 事件：6 個
  - Error 事件：2 個
- 影響範圍：
  - import_flow: 只需參數修正
  - enrichment_flow: 需要 6 個新事件
  - error_handling: 需要 2 個新事件

## 根因分析
- 根本原因：Phase 1 規劃了完整事件系統
- 實際狀態：v0.12.5-A 只實作基本 Import 事件
- 問題本質：未完成實作，非設計缺陷

## 問題分類
- 判斷：實作問題（未完成實作）
- 非設計問題：事件系統架構設計正確
- 處理方向：補完實作而非修正設計
```

**步驟 2: 策略規劃**

```markdown
## 完整策略

### 階段 1: 建立所有缺失事件（架構完整性優先）
Ticket 1.1: 建立 EnrichmentStartedEvent
Ticket 1.2: 建立 EnrichmentCompletedEvent
Ticket 1.3: 建立 EnrichmentErrorEvent
Ticket 1.4: 建立 BatchEnrichmentStartedEvent
Ticket 1.5: 建立 BatchEnrichmentProgressUpdatedEvent
Ticket 1.6: 建立 BatchEnrichmentCompletedEvent
Ticket 1.7: 建立 ImportErrorEvent
Ticket 1.8: 建立通用 ErrorEvent（如需要）

### 階段 2: 統一修復所有測試
Ticket 2.1: 修復 import_flow_integration_test.dart
Ticket 2.2: 修復 enrichment_flow_integration_test.dart
Ticket 2.3: 修復 error_handling_integration_test.dart

### 階段 3: 驗證整合完整性
Ticket 3.1: 執行所有整合測試確保 100% 通過
Ticket 3.2: 驗證事件系統完整性
Ticket 3.3: 更新文件記錄

## Ticket 依賴關係
- Ticket 1.1-1.8 可並行執行
- Ticket 2.1-2.3 依賴 1.1-1.8 完成
- Ticket 3.1-3.3 依賴 2.1-2.3 完成

## 執行優先序
1. 高優先：Ticket 1.1-1.8（架構基礎）
2. 中優先：Ticket 2.1-2.3（功能修復）
3. 低優先：Ticket 3.1-3.3（驗證）
```

**步驟 3: 系統執行**

```markdown
按 Ticket 順序執行：
1. 分派 Ticket 1.1-1.8 給 parsley-flutter-developer
2. 驗證事件類別完成
3. 分派 Ticket 2.1-2.3 給 parsley-flutter-developer
4. 驗證測試修復完成
5. 執行 Ticket 3.1-3.3 整體驗證
```

**成果對比**：

| 指標 | 錯誤做法（分批思維） | 正確做法（全局分析） |
|-----|------------------|------------------|
| **完整性** | 可能遺漏問題 | 涵蓋所有問題 |
| **效率** | 可能重複修改 | 一次到位 |
| **品質** | 局部優化 | 系統性解決 |
| **架構** | 可能產生債務 | 架構完整 |

### 案例 2: Layer 引用錯誤（設計問題立即停止）

**問題發現**：

```markdown
UseCase (Layer 3) 直接引用 Widget (Layer 1)
```

**錯誤的判斷**：

```markdown
「這只是引用問題，調整一下就好」
-> 繼續開發其他功能
```

**正確的判斷**：

```markdown
## 設計問題識別
- 問題本質：違反 Clean Architecture 分層原則
- 問題類型：設計問題（架構缺陷）
- 影響範圍：破壞依賴倒置，產生架構債務

## 立即停止決策
- 判斷：設計問題
- 行動：立即停止所有功能開發
- 修正方案：
  1. 重新設計 UseCase 輸入輸出
  2. 建立 DTO 或 ViewModel
  3. 修正依賴方向

## 修正後繼續
- 架構恢復合理
- 繼續原定開發
```

---

**Last Updated**: 2026-06-14
**Version**: 1.0.0 - 從 problem-awareness-evaluation-methodology.md 外移（W8-020.3 方法論瘦身校準）：三大原則完整正反範例 + Hook 系統整合程式碼 + 實戰案例分析（案例 1 v0.12.9 事件系統 + 案例 2 Layer 引用錯誤），emoji 全數清理為純文字
