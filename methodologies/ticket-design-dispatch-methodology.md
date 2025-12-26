# Ticket 設計派工方法論

## 方法論概述

本方法論提供完整的 Ticket 設計和派工機制，解決大型開發任務的協作效率問題，特別是工作日誌臃腫和實作偏差風險。

**適用場景**：
- 多人協作開發
- 大型功能模組開發
- 需要精細進度追蹤的專案
- 需要即時 review 機制的團隊

**核心目標**：
- 建立量化的 Ticket 拆分標準
- 定義完整的 Ticket 生命週期
- 建立即時 Review 機制
- 避免工作日誌臃腫

**方法論版本**：v2.0.0（精簡版 + 引用網絡）

**重要說明**：本檔案為主方法論的精簡版本，提供核心概念和整體框架。詳細的標準、流程、檢查清單和實務範例請參考以下獨立方法論文件：

- **🎯 [Atomic Ticket 方法論](./atomic-ticket-methodology.md)** - **單一職責原則**、四大評估方式、拆分範例（**核心參考**）
- **📊 [CSV Ticket 追蹤方法論](./csv-ticket-tracking-methodology.md)** - 狀態追蹤機制
- **♻️ [Ticket 生命週期管理方法論](./ticket-lifecycle-management-methodology.md)** - 生命週期、狀態轉換、工作流程
- **✅ [即時 Review 機制方法論](./instant-review-mechanism-methodology.md)** - Review 觸發、檢查清單、偏差糾正

> **⚠️ 重要提醒**：Ticket 設計必須遵循 **Atomic Ticket 方法論** 的單一職責原則。禁止使用時間、行數、檔案數等量化指標判斷拆分，只用「單一職責四大檢查」評估。

---

## 第一章：Ticket 機制核心原則

### 1.1 Ticket vs 工作日誌的定位差異

**Ticket 定義**：

Ticket 是「最小可交付單元」（Minimal Deliverable Unit），代表一個可以獨立完成、驗收和追蹤的最小任務單位。

**核心特徵**：
- **獨立性**：可以獨立執行和驗收
- **原子性**：不可再分割為更小的可交付單元
- **可驗證性**：有明確的完成標準
- **單一職責**：一個 Action + 一個 Target

**工作日誌定義**：

工作日誌是記錄整個開發過程的完整文檔，包含設計決策、實作細節、問題分析和解決方案。

**核心特徵**：
- **完整性**：記錄所有決策和過程
- **追溯性**：提供歷史記錄和演進軌跡
- **知識傳承**：為後續開發者提供上下文

**定位差異總結**：

| 維度 | Ticket | 工作日誌 |
|------|--------|---------|
| **範圍** | 單一具體任務 | 整個功能模組或版本 |
| **粒度** | 最小可交付單元（單一職責或少數相關職責） | 完整開發週期（數天到數週） |
| **目的** | 任務執行和驗收 | 知識記錄和傳承 |
| **更新頻率** | 執行中持續更新 | 階段性更新 |
| **文件大小** | 100-200 行 | 500-6000 行 |
| **適用場景** | 協作開發、進度追蹤 | 決策記錄、技術傳承 |

**互補關係**：

Ticket 和工作日誌不是替代關係，而是互補關係：
- **Ticket** 負責「執行層面」：將大任務拆分為可管理的小單元
- **工作日誌** 負責「記錄層面」：記錄決策過程和演進軌跡
- **主版本日誌** 負責「總覽層面」：提供任務總覽和 Ticket 索引

### 1.2 Ticket 機制的三大目標

#### 目標 1：可追溯性（Traceability）

**定義**：每個 Ticket 都有明確的來源和目標，可以追溯到需求、設計文件或問題報告。

**實現方式**：
- Ticket 必須包含「參考文件」欄位，連結到需求規格或設計文件
- Ticket 必須包含「背景」欄位，說明為什麼需要這個 Ticket
- 主版本日誌維護完整的 Ticket 索引

**範例**：
```markdown
### 參考文件
- v0.12.7-design-decisions.md #決策1
- docs/app-requirements-spec.md #UC-01

### 背景
根據 UC-01 需求，需要建立書籍資訊豐富化服務的介面契約
```

**效益**：
- 開發者清楚知道「為什麼」要做這個任務
- PM 可以追蹤每個 Ticket 的需求來源
- 後續維護者可以理解設計意圖

#### 目標 2：可驗收性（Verifiability）

**定義**：每個 Ticket 都有明確、可驗證的完成標準，避免主觀判斷。

**實現方式**：
- Ticket 必須包含「驗收條件」欄位，列出所有可驗證的條件
- 驗收條件必須是客觀可檢查的（檔案存在、測試通過、功能運作）
- Review 時逐項檢查驗收條件

**範例**：
```markdown
### 驗收條件
- [ ] 介面檔案建立在 `lib/domains/import/services/` 目錄
- [ ] `enrichBook` 方法簽名完整且明確
- [ ] 輸入輸出類型定義清楚
- [ ] 包含完整的文檔註解
- [ ] dart analyze 0 錯誤
```

**效益**：
- 避免「看起來完成了」但實際未達標準
- 提供明確的驗收依據
- 減少 review 時的主觀爭議

#### 目標 3：可協作性（Collaborability）

**定義**：多個開發者可以並行執行不同的 Ticket，互不阻塞。

**實現方式**：
- Ticket 拆分時考慮依賴關係，最小化依賴
- 明確標註 Ticket 間的依賴關係（必須先完成 / 可並行）
- 使用 Interface-Driven 開發，內層未完成也可開發外層

**範例**：
```markdown
### 依賴 Ticket
- Ticket #1: 定義 IBookInfoEnrichmentService 介面（必須先完成）
- Ticket #3: 撰寫 EnrichmentProgress 測試（可並行）
```

**效益**：
- 多人可同時開發不同模組
- 減少等待時間
- 提升開發效率

### 1.3 基於 Clean Architecture 的 Ticket 設計哲學

#### Clean Architecture 核心原則回顧

**依賴方向規則**：
- 外層依賴內層，內層不依賴外層
- 所有依賴都指向內層（Domain）

**分層定義**：
- **Entities（Domain）**：核心業務邏輯
- **Use Cases（Application）**：應用業務規則
- **Interface Adapters（Presentation/Infrastructure）**：轉接層
- **Frameworks & Drivers（External）**：外部實作

#### Ticket 設計對應 Clean Architecture

**原則 1：Interface 定義優先於具體實作**

每個功能模組的開發順序：
1. **先定義 Interface**（Ticket 類型：Interface 定義）
2. **再實作具體邏輯**（Ticket 類型：具體實作）

**範例**：
```text
Ticket #1: 定義 IBookRepository 介面
    ↓
Ticket #2: 實作 SQLiteBookRepository（依賴 #1）
```

**好處**：
- 外層可依賴 Interface 先行開發（使用 Mock）
- 內層實作延後，不阻塞外層開發
- 符合 Dependency Inversion Principle

**原則 2：測試驅動 Ticket 拆分**

每個實作 Ticket 都應該有對應的測試 Ticket：
1. **Interface 定義 Ticket** → 定義契約
2. **測試撰寫 Ticket** → 驗證契約
3. **具體實作 Ticket** → 實現契約
4. **整合驗證 Ticket** → 確認整合

**範例**：
```text
Ticket #1: 定義 IBookRepository 介面
    ↓
Ticket #2: 撰寫 BookRepository 測試
    ↓
Ticket #3: 實作 SQLiteBookRepository
    ↓
Ticket #4: 整合測試驗證
```

**好處**：
- 測試先行，確保需求清晰
- 實作以測試為目標，不過度設計
- 整合驗證確保模組間正確協作

**原則 3：分層拆分 Ticket**

基於 Clean Architecture 分層，將任務拆分為不同層次的 Ticket：

**Domain 層 Ticket**：
- 定義 Entity
- 定義 Value Object
- 定義 Domain Event
- 定義 Repository Interface

**Application 層 Ticket**：
- 定義 Use Case Interface
- 實作 Use Case Interactor
- 定義 Input/Output Port

**Infrastructure 層 Ticket**：
- 實作 Repository
- 實作 External Service
- 實作 Database Mapper

**Presentation 層 Ticket**：
- 實作 Controller/Presenter
- 實作 ViewModel
- 實作 UI Component

**好處**：
- 職責清晰，不跨層混合
- 符合 Clean Architecture 分層原則
- 易於並行開發

### 1.4 Ticket 機制與 TDD 四階段的關係

#### TDD 四階段回顧

- **Phase 1**：功能設計（設計 Interface、規劃架構）
- **Phase 2**：測試設計（撰寫測試案例）
- **Phase 3**：實作執行（實作功能、通過測試）
- **Phase 4**：重構優化（改善品質、消除技術債務）

#### Ticket 與 TDD 階段對應

**Phase 1 產出的 Ticket**：

Phase 1 設計階段產出「Interface 定義 Ticket」：
- 定義 Domain Interface
- 定義 Use Case Interface
- 定義 Input/Output Port

**特徵**：
- 無具體實作，只有介面簽名
- 明確定義輸入輸出
- 建立契約規範

**Phase 2 產出的 Ticket**：

Phase 2 測試設計階段產出「測試撰寫 Ticket」：
- 撰寫 Entity 測試
- 撰寫 Use Case 測試
- 撰寫 Repository 測試

**特徵**：
- 測試先行，定義預期行為
- 覆蓋所有 Interface 方法
- 包含正常流程和異常處理

**Phase 3 產出的 Ticket**：

Phase 3 實作階段產出「具體實作 Ticket」：
- 實作 Entity 邏輯
- 實作 Use Case Interactor
- 實作 Repository

**特徵**：
- 以測試通過為目標
- 最小可行實作
- 100% 測試通過

**Phase 4 產出的 Ticket**：

Phase 4 重構階段產出「品質改善 Ticket」：
- 重構複雜邏輯
- 消除程式異味
- 改善錯誤處理

**特徵**：
- 保持測試通過
- 改善程式品質
- 不新增功能

#### Ticket 機制支援 TDD 流程

**支援 1：明確的階段產出**

每個 TDD Phase 都產出對應的 Ticket 類型，職責清晰。

**支援 2：可並行執行**

Phase 1 完成後，多個開發者可並行執行 Phase 2-3 的不同 Ticket。

**支援 3：即時 Review**

每完成一個 Ticket 觸發 review，確保品質。

---

## 第二章：Ticket 拆分標準（單一職責原則）

**本章概述**：

本章定義基於**單一職責原則**的 Ticket 拆分標準，確保每個 Ticket 維持「最小可交付單元」的原則。詳細的設計原則和評估方式，請參考：

**🎯 [Atomic Ticket 方法論](./atomic-ticket-methodology.md)**（核心參考）

### 單一職責四大檢查（核心評估方式）

> **⚠️ 重要**：禁止使用時間、行數、檔案數、測試數等量化指標判斷是否需要拆分。只用以下四大檢查評估：

1. **語義檢查**：能用「動詞 + 單一目標」表達嗎？
2. **修改原因檢查**：只有一個原因會導致修改嗎？
3. **驗收一致性**：所有驗收條件指向同一目標嗎？
4. **依賴獨立性**：拆分後不會產生循環依賴嗎？

### 拆分決策流程摘要

```text
檢查 Ticket 是否符合單一職責
    ↓
通過四大檢查？
    ├─ 是 → 保持不變，可執行
    └─ 否 → 分析違反哪項檢查
        ├─ 語義檢查失敗？ → 拆分為多個獨立目標
        ├─ 修改原因過多？ → 依修改原因拆分
        ├─ 驗收不一致？ → 依驗收條件分組
        └─ 存在循環依賴？ → 重新設計依賴關係
```

### 完整內容引用

詳細的拆分標準請查閱：

- **[🎯 Atomic Ticket 方法論](./atomic-ticket-methodology.md)** - 單一職責原則和四大檢查（**核心參考**）

---

## 第三章：Ticket 生命週期管理（精簡版）

**本章概述**：

本章定義 Ticket 從建立到關閉的完整生命週期，包含狀態轉換、工作流程和文件管理。完整的生命週期定義、狀態轉換規則、準備度檢查清單和工作流程圖，請參考：

**♻️ [Ticket 生命週期管理方法論](./ticket-lifecycle-management-methodology.md)**（~28,500 tokens，完整論述）

### 生命週期狀態摘要

**7 種生命週期狀態**：

1. **Draft（草稿）** - Ticket 初步建立，細節待完善
2. **Ready（準備就緒）** - 通過準備度檢查，可派工
3. **In Progress（進行中）** - 開發者執行中
4. **Review（審查中）** - 提交 Review，等待審查結果
5. **Blocked（阻塞）** - 遇到阻塞問題，暫時無法繼續
6. **Closed（已關閉）** - Review 通過，正式完成
7. **Cancelled（已取消）** - 不再執行，標記原因

### 工作流程摘要

```text
Draft → 完善細節 → Ready → 派工 → In Progress
    ↓                            ↓
Review ← 提交審查              Blocked?
    ↓                            ↓
通過？                        解除阻塞
    ├─ 是 → Closed              ↓
    └─ 否 → 建立修正 Ticket → In Progress
```

### 完整內容引用

詳細的生命週期管理包含以下完整內容（請查閱獨立方法論文件）：

- **3.1 Ticket 生命週期定義** - 7 種狀態的詳細定義和轉換條件
- **3.2 Ticket 狀態轉換規則** - 完整的狀態轉換圖和轉換邏輯
- **3.3 Ticket 準備度檢查** - 10 項檢查清單和不足處理流程
- **3.4 Ticket 派工與執行流程** - 完整的派工流程和執行指引
- **3.5 Ticket 文件記錄規範** - 文件結構、記錄內容和模板
- **附錄 A：Ticket 狀態快速參考**
- **附錄 B：Ticket 模板範例集**

---

## 第四章：即時 Review 機制（精簡版）

**本章概述**：

本章建立即時 Review 機制，在每個 Ticket 完成時立即觸發 Review，避免傳統 Review 的滯後問題。完整的 Review 觸發機制、16 項檢查清單、偏差糾正流程和實務案例，請參考：

**✅ [即時 Review 機制方法論](./instant-review-mechanism-methodology.md)**（~24,000 tokens，完整論述）

### 即時 Review 核心原則摘要

**與傳統 Review 的差異**：

| 維度 | 傳統 Review | 即時 Review |
|------|------------|------------|
| **時機** | 所有任務完成後 | 每個 Ticket 完成時 |
| **範圍** | 整個版本所有程式碼 | 單一 Ticket 相關程式碼 |
| **修正成本** | 高（可能需大幅重構） | 低（問題剛發生，容易修正） |
| **反饋週期** | 數天到數週 | 數小時內 |

### Review 觸發時機摘要

**三大觸發條件**：

1. **Ticket 標記為「已完成」** - 開發者自評完成
2. **所有驗收條件通過** - 客觀檢查完成
3. **Ticket 工作日誌已更新** - 記錄完成

### 16 項檢查清單摘要

**四大類別**：

1. **功能正確性（4 項）** - 功能實現、驗收條件、邊界情況、錯誤處理
2. **架構合規性（4 項）** - Clean Architecture、依賴方向、Interface-Driven、架構債務
3. **測試通過率（4 項）** - 單元測試、整合測試、測試覆蓋率、跳過測試
4. **文檔同步性（4 項）** - Ticket 日誌、設計決策、API 文檔、README

### 完整內容引用

詳細的即時 Review 機制包含以下完整內容（請查閱獨立方法論文件）：

- **第一章：即時 Review 核心原則** - 傳統問題分析、即時 Review 優勢
- **第二章：Review 觸發時機與機制** - 觸發條件、Reviewer 分配、時限控制
- **第三章：Review 檢查項目詳解** - 16 項檢查清單的完整說明和範例
- **第四章：偏差糾正流程** - 5 Why 分析、修正 Ticket 建立、持續改善
- **第五章：Review 記錄與追蹤** - 記錄格式、統計追蹤、品質度量
- **第六章：即時 Review 最佳實踐** - 完整案例研究、常見問題解決

---

## 第五章：文件管理策略（精簡版）

**本章概述**：

本章定義 Ticket 機制下的三層文件結構，確保文件組織清晰且易於維護。

### 三層文件結構

**第一層：主版本日誌（vX.Y.Z-main.md）**

**職責**：
- 版本總覽和目標說明
- Ticket 索引（所有 Ticket 的導航）
- 設計決策索引（重要決策的索引）
- 版本總結和經驗教訓

**大小控制**：約 500-1000 行

**第二層：Ticket 工作日誌（vX.Y.Z-ticket-NNN.md）**

**職責**：
- 單一 Ticket 的執行記錄
- 實作細節和程式碼片段
- Review 結果和問題處理
- 完成標記和交付產出

**大小控制**：約 100-200 行 / Ticket

**第三層：設計決策日誌（vX.Y.Z-design-decisions.md）**

**職責**：
- 設計決策的完整記錄
- 決策演進過程（初版、修正版、最終版）
- 廢棄決策的標記和原因
- 設計決策的影響分析

**大小控制**：約 300-500 行

### 文件索引機制

**主版本日誌的 Ticket 索引範例**：

```markdown
## Ticket 索引

### Domain 層
- Ticket #1: 定義 IBookRepository 介面 → [詳細](v0.12.7-ticket-001.md) ✅
- Ticket #2: 定義 IEnrichmentStrategy 介面 → [詳細](v0.12.7-ticket-002.md) ✅

### Application 層
- Ticket #4: 定義 EnrichBookUseCase 介面 → [詳細](v0.12.7-ticket-004.md) 🔄
- Ticket #5: 實作 EnrichBookInteractor → [詳細](v0.12.7-ticket-005.md) 📝

### Infrastructure 層
- Ticket #6: 實作 GoogleBooksStrategy → [詳細](v0.12.7-ticket-006.md) ⏸️
```

**狀態圖示**：
- ✅ 已完成並通過 Review
- 🔄 進行中
- 📝 草稿階段
- ⏸️ 阻塞中
- ❌ 已取消

### 文件更新時機

**Ticket 建立時**：
- 建立 Ticket 工作日誌
- 更新主版本日誌索引
- 如有新設計決策，更新設計決策日誌

**Ticket 執行中**：
- 持續更新 Ticket 工作日誌
- 記錄實作過程和決策調整

**Ticket 完成後**：
- 完成 Ticket 工作日誌
- 更新主版本日誌索引狀態
- 更新設計決策日誌（如有調整）
- 更新 todolist.md 任務狀態

---

## 第六章：與敏捷重構和 TDD 的整合

### 6.1 Ticket 機制與三重文件原則的關係

#### 三重文件原則回顧

本專案採用三重文件原則（CHANGELOG + todolist + work-log）進行全方位進度管理：

**1. CHANGELOG.md**：
- 面向用戶的版本功能描述
- 只記錄「做了什麼」，不記錄「怎麼做」

**2. todolist.md**：
- 記錄整個開發過程所有待處理任務
- 任務狀態追蹤（待執行/進行中/已完成）

**3. work-log/**：
- 完整的技術實作細節和決策過程
- TDD 四階段進度追蹤

#### Ticket 機制如何融入三重文件

**Ticket 機制定位**：

Ticket 機制是「work-log 層」的細化管理工具：
- **work-log 主版本日誌** = Ticket 索引 + 版本總覽
- **work-log Ticket 日誌** = 單一 Ticket 的執行記錄
- **work-log 設計決策日誌** = 設計迭代過程記錄

**整合關係**：

```text
CHANGELOG.md（版本功能描述）
    ↑ 提取功能變動
work-log/vX.Y.Z-main.md（主版本日誌）
    ↓ Ticket 索引
work-log/vX.Y.Z-ticket-NNN.md（Ticket 日誌）
    ↑ 完成狀態
todolist.md（任務狀態追蹤）
```

**協作流程**：

1. **PM 規劃階段**：
   - 在 `todolist.md` 建立任務項目
   - 在 `vX.Y.Z-main.md` 規劃 Ticket 索引

2. **開發執行階段**：
   - 建立 `vX.Y.Z-ticket-NNN.md` Ticket 日誌
   - 執行 Ticket，記錄過程
   - 完成後更新 `todolist.md` 狀態

3. **版本發布階段**：
   - 從 `vX.Y.Z-main.md` 提取功能變動
   - 更新 `CHANGELOG.md` 版本說明

### 6.2 Ticket 與 TDD 四階段的對應關係

#### TDD 四階段與 Ticket 類型對應

**Phase 1（功能設計）→ Interface 定義 Ticket**：

Phase 1 產出的設計決策 → 轉化為 Interface 定義 Ticket：
```text
Phase 1 產出：
- IBookRepository 介面設計
- IBookInfoEnrichmentService 介面設計

↓ 轉化為 Ticket

Ticket #1: 定義 IBookRepository 介面
Ticket #2: 定義 IBookInfoEnrichmentService 介面
```

**Phase 2（測試設計）→ 測試撰寫 Ticket**：

Phase 2 產出的測試設計 → 轉化為測試撰寫 Ticket：
```text
Phase 2 產出：
- BookRepository 測試用例設計
- BookInfoEnrichmentService 測試用例設計

↓ 轉化為 Ticket

Ticket #3: 撰寫 BookRepository 測試
Ticket #4: 撰寫 BookInfoEnrichmentService 測試
```

**Phase 3（實作執行）→ 具體實作 Ticket + 整合 Ticket**：

Phase 3 產出的實作 → 拆分為具體實作和整合 Ticket：
```text
Phase 3 產出：
- SQLiteBookRepository 實作
- GoogleBooksEnrichmentService 實作
- 整合到 Use Case

↓ 轉化為 Ticket

Ticket #5: 實作 SQLiteBookRepository
Ticket #6: 實作 GoogleBooksEnrichmentService
Ticket #7: 整合到 GetBookUseCase
```

**Phase 4（重構優化）→ 重構 Ticket**：

Phase 4 發現的重構需求 → 建立重構 Ticket：
```text
Phase 4 發現：
- BookRepository 邏輯複雜，需要拆分
- EnrichmentService 錯誤處理不完整

↓ 轉化為 Ticket

Ticket #8: 重構 BookRepository，拆分 CRUD 邏輯
Ticket #9: 補充 EnrichmentService 錯誤處理
```

#### TDD 階段完成標準與 Ticket 關係

**Phase 1 完成標準**：
- 所有 Interface 定義 Ticket 建立並標記為「待執行」
- 設計決策日誌記錄完整

**Phase 2 完成標準**：
- 所有測試撰寫 Ticket 建立並標記為「待執行」
- 測試覆蓋所有 Interface 方法

**Phase 3 完成標準**：
- 所有具體實作 Ticket 完成並通過 review
- 所有整合 Ticket 完成並通過測試
- 測試 100% 通過

**Phase 4 完成標準**：
- 所有重構 Ticket 完成並通過 review
- 程式碼品質達標，無技術債務

### 6.3 Ticket 派工前的準備度檢查

#### 準備度檢查清單

在建立和派工 Ticket 前，必須檢查以下準備度：

**設計準備度**（4 項）：
- [ ] 相關設計決策已完成且標記為「最終決策」
- [ ] Interface 定義已完成（如適用）
- [ ] 設計決策日誌已更新
- [ ] 沒有未解決的設計問題

**依賴準備度**（3 項）：
- [ ] 依賴的 Ticket 已完成
- [ ] 依賴的 Interface 已定義
- [ ] 依賴的測試已撰寫（如適用）

**資源準備度**（3 項）：
- [ ] 開發者已理解 Ticket 目標
- [ ] 開發環境已準備就緒
- [ ] 相關文檔已閱讀

**品質準備度**（2 項）：
- [ ] 驗收條件明確且可驗證
- [ ] Review 機制已建立

#### 準備度不足的處理

**發現準備度不足時**：

```text
Ticket 派工前檢查
    ↓
準備度檢查
    ├─ 通過 → 派工執行
    └─ 不通過 → 暫停派工
        ↓
    分析缺失項目
        ├─ 設計不完整 → 補充設計決策
        ├─ 依賴未完成 → 等待依賴 Ticket
        └─ 資源不足 → 準備環境和文檔
        ↓
    重新檢查準備度
```

### 6.4 Ticket 完成後的文件更新

#### 更新流程

每完成一個 Ticket，必須更新以下文件：

**步驟 1：更新 Ticket 工作日誌**

在 `vX.Y.Z-ticket-NNN.md` 記錄：
- 執行過程
- Review 結果
- 遇到的問題和解決方案

**步驟 2：更新主版本日誌**

在 `vX.Y.Z-main.md` 更新：
- Ticket 索引（標記為已完成）
- 如有新的設計決策，更新設計決策索引

**步驟 3：更新 todolist**

在 `todolist.md` 更新：
- 標記對應任務為「已完成」
- 如發現新任務，新增到待辦清單

**步驟 4：更新設計決策日誌（如適用）**

在 `vX.Y.Z-design-decisions.md` 更新：
- 如有設計調整，記錄新的決策版本
- 如廢棄舊決策，標記廢棄原因

### 6.5 整合檢查清單

**Ticket 建立檢查**（4 項）：
- [ ] Ticket 來自 TDD Phase 1-4 的產出
- [ ] Ticket 類型符合 Clean Architecture 分層
- [ ] Ticket 已連結到設計決策日誌
- [ ] Ticket 準備度檢查通過

**Ticket 執行檢查**（4 項）：
- [ ] 執行過程記錄到 Ticket 日誌
- [ ] 完成後更新主版本日誌索引
- [ ] 完成後更新 todolist 狀態
- [ ] 如有設計調整，更新設計決策日誌

**文件同步檢查**（4 項）：
- [ ] Ticket 日誌大小控制在 100-200 行
- [ ] 主版本日誌索引保持最新
- [ ] 設計決策狀態正確標記
- [ ] todolist 任務狀態與實際一致

---

## 第七章：實務案例和模板（精簡版）

### 7.1 典型案例：v0.12.7 工作日誌臃腫問題

**問題描述**：
- 工作日誌臃腫至 6000 行
- 開發者搜尋資訊困難
- 協作衝突頻繁

**解決方案**：
採用 Ticket 機制，將單一 6000 行日誌拆分為：
- 主版本日誌（800 行）+ Ticket 索引
- 12 個 Ticket 日誌（每個 100-200 行）
- 設計決策日誌（400 行）

**效益**：
- 檔案大小縮減 70%（6000 → 約 2000 行總量）
- 資訊查找時間減少 80%
- 協作衝突減少 90%

### 7.2 Ticket 模板

#### Ticket 工作日誌模板

```markdown
# Ticket #N: [動詞] [目標]

## 基本資訊
- **Ticket ID**: #N
- **類型**: [Interface 定義 / 測試撰寫 / 具體實作 / 整合 / 重構]
- **所屬版本**: vX.Y.Z
- **建立日期**: YYYY-MM-DD
- **預估工時**: X 小時
- **實際工時**: Y 小時

## 參考文件
- vX.Y.Z-design-decisions.md #決策N
- docs/app-requirements-spec.md #UC-XX

## 背景
[說明為什麼需要這個 Ticket]

## 目標
[明確說明這個 Ticket 要達成什麼]

## 驗收條件
- [ ] 條件 1
- [ ] 條件 2
- [ ] 條件 3

## 依賴 Ticket
- Ticket #X: [描述]（必須先完成）
- Ticket #Y: [描述]（可並行）

## 實作記錄

### [日期] 實作過程
[記錄實作細節、程式碼片段、遇到的問題]

## Review 結果

### Review 通過標準檢查
- [ ] 功能正確性（4 項）
- [ ] 架構合規性（4 項）
- [ ] 測試通過率（4 項）
- [ ] 文檔同步性（4 項）

### Review 結果
- **Reviewer**: [姓名]
- **Review 日期**: YYYY-MM-DD
- **結果**: ✅ 通過 / ❌ 需修正
- **建議**: [Review 建議]

## 完成標記
- **完成日期**: YYYY-MM-DD
- **狀態**: Closed
- **產出**: [列出交付的檔案或功能]
```

#### 主版本日誌模板

```markdown
# vX.Y.Z 主版本日誌

## 快速導航
- [版本目標](#版本目標)
- [Ticket 索引](#ticket索引)
- [設計決策索引](#設計決策索引)
- [版本總結](#版本總結)

## 版本目標

### 功能目標
[列出這個版本要完成的主要功能]

### 品質目標
[列出這個版本的品質標準]

## Ticket 索引

### Domain 層
- Ticket #1: [描述] → [詳細](vX.Y.Z-ticket-001.md) ✅
- Ticket #2: [描述] → [詳細](vX.Y.Z-ticket-002.md) 🔄

### Application 層
- Ticket #4: [描述] → [詳細](vX.Y.Z-ticket-004.md) 📝

### Infrastructure 層
- Ticket #6: [描述] → [詳細](vX.Y.Z-ticket-006.md) ⏸️

### 測試
- Ticket #10: [描述] → [詳細](vX.Y.Z-ticket-010.md) ✅

## 設計決策索引

### 決策 1: [決策標題]
- **狀態**: 最終決策 / 進行中 / 已廢棄
- **提出日期**: YYYY-MM-DD
- **詳細**: [連結到設計決策日誌]

## 版本總結

### 完成統計
- 總 Ticket 數: X
- 完成 Ticket 數: Y
- 程式碼行數: Z 行
- 測試覆蓋率: W%

### 經驗教訓
[記錄本版本的經驗教訓]
```

### 7.3 實務檢查清單

**Ticket 建立前檢查**（5 項）：
- [ ] 是否超過量化指標？需要拆分？
- [ ] 是否有明確的驗收條件？
- [ ] 是否標註依賴 Ticket？
- [ ] 是否連結到設計決策？
- [ ] 是否通過準備度檢查？

**Ticket 執行中檢查**（4 項）：
- [ ] 是否持續更新 Ticket 日誌？
- [ ] 遇到問題是否記錄解決方案？
- [ ] 是否遵循 TDD 流程？
- [ ] 是否符合 Clean Architecture？

**Ticket 完成後檢查**（6 項）：
- [ ] 是否所有驗收條件通過？
- [ ] 是否更新主版本日誌索引？
- [ ] 是否更新 todolist 狀態？
- [ ] 是否更新設計決策日誌？
- [ ] 是否通過 16 項 Review 檢查？
- [ ] 是否記錄經驗教訓？

---

## 方法論總結

### 核心價值

本方法論通過 Ticket 機制解決大型開發任務的以下核心問題：

1. **工作日誌臃腫** - 三層文件結構，控制檔案大小
2. **協作效率低** - 並行執行 Ticket，提升團隊效率
3. **品質風險高** - 即時 Review 機制，及早發現問題
4. **知識傳承難** - 完整的文件索引和記錄機制

### 方法論應用建議

**小型專案**（1-2 人）：
- 可簡化使用，減少文件層級
- 重點使用量化拆分標準
- 保留即時 Review 機制

**中型專案**（3-5 人）：
- 完整採用三層文件結構
- 嚴格執行準備度檢查
- 建立完整的 Ticket 索引

**大型專案**（6+ 人）：
- 加強 Ticket 依賴管理
- 建立專職 Reviewer 角色
- 使用專案管理工具整合

### 與其他方法論的整合

本方法論與以下專案方法論緊密整合：

- **[敏捷重構方法論](../agile-refactor-methodology.md)** - 三重文件原則、代理人協作
- **[TDD 協作開發流程](../tdd-collaboration-flow.md)** - 四階段流程、測試驅動
- **[5W1H 自覺決策方法論](../5w1h-self-awareness-methodology.md)** - 決策品質確保

### 持續改善

**本方法論持續演進**：
- 收集實務反饋
- 優化量化指標
- 補充新的案例
- 改善工具整合

**版本歷史**：
- v1.0.0（2025-10-10）：初版，包含完整內容（48,438 tokens）
- v2.0.0（2025-10-11）：精簡版，建立引用網絡（~15,000 tokens）

**反饋與改進**：歡迎提供實務經驗和改進建議，持續完善本方法論。

---

**文件結束**
