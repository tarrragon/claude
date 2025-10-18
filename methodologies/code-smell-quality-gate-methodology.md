# Code Smell 品質閘門檢測方法論

> **版本**: v1.0.0
> **建立日期**: 2025-01-11
> **狀態**: ✅ 完成
> **來源**: 提煉自《Ticket 設計派工方法論》第二章 2.4 節

---

## 📋 方法論概述

### 為什麼需要設計階段的品質閘門

**傳統品質檢測的局限性**:

傳統的品質檢測通常在「實作完成後」執行，這導致：
- **修正成本高**: 程式碼已經寫好，需要大幅重構
- **時間浪費**: 發現設計問題時可能已經花費數小時實作
- **心理抵抗**: 開發者不願意重構已完成的程式碼
- **品質妥協**: 為了趕進度，選擇「局部修正」而非「根本解決」

**設計階段品質檢測的優勢**:

在 Ticket 設計階段執行品質檢測，可以：
- **及早發現**: 在程式碼未寫之前就發現設計問題
- **低修正成本**: 只需要調整 Ticket 內容，無需重構程式碼（**修正成本降低 80%**）
- **預防性**: 預防問題進入實作階段，減少返工時間
- **品質導向**: 強制確保每個 Ticket 都符合品質標準

**效益對比**:

| 維度 | 實作後檢測 | 設計階段檢測 |
|------|----------|------------|
| **檢測時機** | Phase 3 實作完成後 | Phase 1 設計完成後 |
| **修正成本** | 高（需要重構程式碼） | 低（只需調整 Ticket） |
| **修正時間** | 2-4 小時 | 10-20 分鐘 |
| **心理抵抗** | 高（已完成的程式碼） | 低（尚未實作） |
| **品質保證** | 事後補救 | 事前預防 |

### 適用場景

本方法論適用於以下場景：

1. **TDD Phase 1 完成時**:
   - lavender-interface-designer 完成 Ticket 設計
   - 準備提交給 PM 審查前
   - 執行品質閘門檢測確保 Ticket 品質

2. **Ticket 修訂時**:
   - PM 要求修改 Ticket 內容時
   - 重新執行檢測確保修訂後仍符合標準

3. **專案啟動階段**:
   - 建立 Ticket 設計標準
   - 培訓團隊理解品質閘門概念

4. **品質審查時**:
   - PM 審查 Ticket 設計品質
   - 使用檢測報告作為審查依據

### 核心目標

**三大品質目標**:

1. **防止 God Ticket**（C1 檢測）
   - 確保每個 Ticket 的範圍合理
   - 檔案數量 ≤ 10、層級跨度 ≤ 2、預估工時 ≤ 16h
   - 符合「單層修改原則」和 Clean Architecture 設計理念

2. **確保 Ticket 完整性**（C2 檢測）
   - 確保 Ticket 包含必要元素
   - 驗收條件、測試規劃、工作日誌、參考文件四要素齊全
   - 開發者可以明確理解需求和驗收標準

3. **明確責任歸屬**（C3 檢測）
   - 確保 Ticket 的層級和職責清晰
   - 層級標示、職責描述、檔案範圍、驗收限定四要素明確
   - 避免跨層級職責模糊

**兩大流程目標**:

1. **強制阻斷機制**: 任何 Ticket 未通過檢測，禁止進入 Phase 2
2. **完整記錄機制**: 所有檢測過程和修正過程都記錄到工作日誌

### 創新點：從實作品質檢測到設計品質檢測

**傳統方法**（實作後檢測）:
```text
Ticket 設計 → Phase 2 測試設計 → Phase 3 實作 → 發現問題 ❌
                                              ↓
                                         返工重構（成本高）
```

**本方法論**（設計階段檢測）:
```text
Ticket 設計 → 品質閘門檢測 ✅ → Phase 2 測試設計 → Phase 3 實作 → 無問題 ✅
            ↑     ↓
            └ 修正（成本低）
```

**創新點**:
1. **時間前移**: 將品質檢測從 Phase 3 後移到 Phase 1 後
2. **成本降低**: 修正只需調整文字，不需重構程式碼
3. **預防導向**: 預防問題進入實作階段
4. **標準化**: 提供統一的檢測標準，避免主觀判斷

### 與其他方法論的關係

本方法論與以下方法論整合使用：

1. **《Ticket 設計派工方法論》**（主方法論）
   - 本方法論是主方法論第二章 2.4 節的獨立提煉
   - 定義品質閘門在 TDD 四階段中的位置

2. **《Ticket 拆分標準方法論》**（平行方法論）
   - C1 檢測使用拆分標準方法論的量化指標
   - 檢測失敗時引用拆分策略執行拆分

3. **《層級隔離派工方法論》**（基礎方法論）
   - C1 和 C3 檢測依賴層級隔離原則
   - 使用五層架構判斷層級跨度

4. **《敏捷重構方法論》**（流程方法論）
   - 檢測過程遵循三重文件原則
   - 工作日誌記錄檢測過程和修正決策

---

## 第一章：品質閘門檢測體系

### 1.1 三層檢測標準（C1/C2/C3）

**品質閘門檢測體系由三個檢測標準組成**:

#### C1. God Ticket 檢測（複雜度警告）

**檢測目標**: 防止單一 Ticket 範圍過大，確保符合「單層修改原則」

**檢測指標**:
- **檔案數量**: ≤ 10 個
- **層級跨度**: ≤ 2 層
- **預估工時**: ≤ 16 小時

**判定邏輯**: **任一指標超標 = God Ticket**（必須拆分）

**失敗處理**: 執行拆分策略（按層級/按職責/按功能模組）

---

#### C2. Incomplete Ticket 檢測（架構完整性）

**檢測目標**: 確保 Ticket 包含必要元素，開發者可以明確理解需求

**檢測指標**:
- **驗收條件**: 至少 3 個可驗證的驗收項目
- **測試規劃**: 明確測試檔案路徑和測試項目
- **工作日誌規劃**: 定義工作日誌檔案名稱
- **參考文件**: 至少 1 個有效的文件連結

**判定邏輯**: **任一元素缺失 = Incomplete Ticket**（必須補充）

**失敗處理**: 補充缺失的必要元素

---

#### C3. Ambiguous Responsibility 檢測（責任明確性）

**檢測目標**: 確保 Ticket 的層級和職責清晰，避免職責模糊

**檢測指標**:
- **層級標示**: 標題包含 `[Layer X]` 標籤
- **職責描述**: 目標章節明確定義單一職責
- **檔案範圍**: 步驟章節明確列出檔案路徑
- **驗收限定**: 驗收條件限定在該層級

**判定邏輯**: **任一元素缺失 = Ambiguous Responsibility**（必須重新定義）

**失敗處理**: 執行重新定義流程（明確層級、重新定義職責、明確檔案範圍、限定驗收條件）

### 1.2 檢測標準分級制度

**三級檢測分級**:

| 級別 | 檢測標準 | 通過標準 | 失敗處理 | 阻斷等級 |
|------|---------|---------|---------|---------|
| **Level 1** | **C1 God Ticket** | 檔案 ≤10、層級 ≤2、工時 ≤16h | 執行拆分策略 | 🔴 強制阻斷 |
| **Level 2** | **C3 Ambiguous** | 4 個必要元素齊全 | 重新定義職責 | 🔴 強制阻斷 |
| **Level 3** | **C2 Incomplete** | 4 個必要元素齊全 | 補充缺失元素 | 🔴 強制阻斷 |

**檢測順序**: C1 → C3 → C2

**順序理由**:
1. **C1 優先**: 如果是 God Ticket，拆分後會產生多個新 Ticket，需要重新檢測
2. **C3 其次**: 職責明確後，才能準確補充驗收條件和測試規劃
3. **C2 最後**: 在職責明確的基礎上，補充完整元素

### 1.3 檢測觸發時機

**三個關鍵檢測時機**:

#### 時機 1: Ticket 撰寫完成後（最重要）

```text
lavender-interface-designer 完成 Ticket 清單
  ↓
所有 Ticket 的內容都已撰寫完成
  ↓
【立即執行品質閘門檢測】
  ├─ 對每個 Ticket 執行 C1/C2/C3 檢測
  ├─ 記錄檢測結果到工作日誌
  └─ 生成品質閘門報告
```

**檢測範圍**: 所有新建立的 Ticket

**執行者**: lavender-interface-designer

**輸出**: 品質閘門檢測報告（記錄到工作日誌）

---

#### 時機 2: 分派執行前（門檻檢查）

```text
PM 審查 Ticket 設計
  ↓
確認品質閘門檢測報告
  ├─ 所有 Ticket 通過檢測 ✅ → PM 批准 → 分派執行
  └─ 有 Ticket 未通過 ❌ → 要求修正 → 重新檢測
```

**檢測範圍**: 待分派的 Ticket

**執行者**: PM（檢查報告）+ lavender-interface-designer（執行檢測）

**輸出**: PM 批准決策

---

#### 時機 3: PM 審查時（品質依據）

```text
PM 審查 Ticket 品質
  ↓
品質閘門檢測報告是重要參考依據
  ├─ 檢查檢測是否完整執行
  ├─ 檢查修正過程是否合理
  └─ 檢查最終檢測結果
```

**檢測範圍**: 所有提交審查的 Ticket

**執行者**: PM

**輸出**: 品質評估和改善建議

### 1.4 品質閘門決策流程

**完整決策流程圖**:

```text
Phase 1: 功能設計（lavender-interface-designer）
  ↓
Ticket 清單撰寫完成
  ↓
┌─────────────────────────────────────┐
│   品質閘門檢測開始                    │
│   （lavender-interface-designer）    │
└─────────────────────────────────────┘
  ↓
對每個 Ticket 執行檢測（按順序）
  ↓
┌─────────────────────────────────────┐
│ 【檢測 1】C1. God Ticket 檢測        │
│                                     │
│ 檢查指標:                            │
│  - 檔案數量 ≤ 10？                   │
│  - 層級跨度 ≤ 2？                    │
│  - 預估工時 ≤ 16h？                  │
│                                     │
│ 組合邏輯: 任一項目超標 = God Ticket   │
└─────────────────────────────────────┘
  ↓
  ├─ 通過 ✅ → 繼續檢測 C3
  └─ 失敗 ❌ → 執行拆分 → 重新檢測 C1
  ↓
┌─────────────────────────────────────┐
│ 【檢測 2】C3. Ambiguous              │
│           Responsibility 檢測         │
│                                     │
│ 檢查要素:                            │
│  - 有層級標示 [Layer X]？            │
│  - 職責描述明確？                    │
│  - 檔案範圍明確？                    │
│  - 驗收條件限定在該層？              │
└─────────────────────────────────────┘
  ↓
  ├─ 通過 ✅ → 繼續檢測 C2
  └─ 失敗 ❌ → 重新定義職責 → 重新檢測 C3
  ↓
┌─────────────────────────────────────┐
│ 【檢測 3】C2. Incomplete Ticket 檢測 │
│                                     │
│ 檢查要素:                            │
│  - 有驗收條件章節？                  │
│  - 有測試規劃？                      │
│  - 有工作日誌規劃？                  │
│  - 有參考文件連結？                  │
└─────────────────────────────────────┘
  ↓
  ├─ 通過 ✅ → 完成檢測
  └─ 失敗 ❌ → 補充元素 → 重新檢測 C2
  ↓
所有 Ticket 都通過 C1/C2/C3？
  ├─ Yes ✅ → 生成品質閘門報告
  │           ↓
  │        提交給 PM 審查
  │           ↓
  │        PM 批准 → 分派給開發者執行（Phase 2）
  │
  └─ No ❌  → 阻止進入 Phase 2
              ├─ 記錄檢測失敗原因到工作日誌
              ├─ 執行修正（拆分/補充/重新定義）
              └─ 重新檢測（直到通過）
```

**阻斷機制**:
- **強制阻斷**: 任何 Ticket 未通過 C1/C2/C3 檢測，**禁止進入 Phase 2**
- **修正優先**: 發現問題後**立即修正**，不延後處理
- **完整記錄**: 所有檢測過程和修正過程都記錄到工作日誌

**品質閘門價值**:

| 價值維度 | 說明 | 效益 |
|---------|------|------|
| **及早發現** | 設計階段就能發現 Code Smell | 修正成本降低 80% |
| **標準化** | 提供統一的檢測標準 | 避免主觀判斷 |
| **可追溯** | 完整的檢測記錄 | 提升品質可見性 |
| **預防性** | 預防問題進入實作階段 | 減少返工時間 |

---

## 第二章：C1 複雜度警告檢測

### 2.1 檢測標準（God Ticket 判定）

**C1 檢測的核心使命**: 防止單一 Ticket 範圍過大，確保符合「單層修改原則」和 Clean Architecture 設計理念。

**量化檢測指標**:

| 指標 | 良好設計 | 需要檢查 | God Ticket（必須拆分） |
|------|---------|---------|----------------------|
| **檔案數量** | 1-3 個 ✅ | 4-6 個 ⚠️ | **> 10 個** ❌ |
| **層級跨度** | 1 層 ✅ | 2 層 ⚠️ | **> 2 層** ❌ |
| **預估工時** | 2-4 小時 ✅ | 4-8 小時 ⚠️ | **> 16 小時** ❌ |

**組合邏輯**（關鍵判定規則）:

```text
判斷標準：任一項目超標 = God Ticket（需要拆分）

範例：
- 檔案數 = 8 個（未超標）、層級跨度 = 3 層（超標） → God Ticket ❌
- 檔案數 = 12 個（超標）、層級跨度 = 1 層（未超標） → God Ticket ❌
- 檔案數 = 5 個（未超標）、層級跨度 = 2 層（未超標）、工時 = 20 小時（超標） → God Ticket ❌

只要有任何一個指標超標，就判定為 God Ticket，必須拆分。
```

**為什麼採用「任一指標超標」邏輯**:

- **檔案數量超標** → 職責過於複雜，測試和維護困難
- **層級跨度超標** → 違反 Clean Architecture 分層原則，耦合度高
- **預估工時超標** → 風險過高，難以在合理時間內完成和驗證

### 2.2 檢測方法（四步驟檢測流程）

#### 步驟 1: 列出 Ticket 涉及的檔案清單

從 Ticket 的「步驟」章節中提取所有檔案路徑。

**範例 Ticket 步驟**:

```markdown
1. 建立 Rating Value Object（`lib/domain/value_objects/rating_value.dart`）
2. 建立 Rating Entity（`lib/domain/entities/rating.dart`）
3. 更新 Book Entity（`lib/domain/entities/book.dart`）
4. 定義 IRatingRepository（`lib/domain/repositories/i_rating_repository.dart`）
...
```

**提取檔案清單**:
- `lib/domain/value_objects/rating_value.dart`
- `lib/domain/entities/rating.dart`
- `lib/domain/entities/book.dart`
- `lib/domain/repositories/i_rating_repository.dart`
- ...

#### 步驟 2: 計算檔案數量

```text
統計檔案數量（不包含測試檔案）：
  ├─ 1-3 個 → 良好設計 ✅
  ├─ 4-6 個 → 需要檢查 ⚠️（評估是否可拆分）
  ├─ 7-10 個 → 建議拆分 ⚠️
  └─ > 10 個 → God Ticket ❌（強制拆分）
```

#### 步驟 3: 判斷層級跨度

使用《層級隔離派工方法論》第 6.2 節「檔案路徑分析法」判斷每個檔案所屬層級。

**檔案路徑 → 層級對應規則**:

```text
Layer 1（UI）:
- lib/presentation/widgets/
- lib/presentation/pages/

Layer 2（Behavior）:
- lib/presentation/controllers/
- lib/presentation/providers/
- lib/presentation/view_models/

Layer 3（UseCase）:
- lib/application/use_cases/
- lib/application/services/

Layer 4（Domain Events/Interfaces）:
- lib/domain/events/
- lib/domain/repositories/ (介面)
- lib/domain/services/ (介面)

Layer 5（Domain Implementation）:
- lib/domain/entities/
- lib/domain/value_objects/
- lib/infrastructure/repositories/ (實作)
- lib/infrastructure/services/ (實作)
```

**計算層級跨度**:

```text
範例：
檔案清單：
- lib/presentation/widgets/rating_widget.dart → Layer 1
- lib/presentation/controllers/rating_controller.dart → Layer 2
- lib/application/use_cases/rate_book_use_case.dart → Layer 3
- lib/domain/entities/rating.dart → Layer 5

層級跨度 = max(5) - min(1) = 4 層 ❌ → God Ticket
```

**判斷標準**:

```text
  ├─ 1 層（單層修改）→ 良好設計 ✅
  ├─ 2 層（Facade 整合）→ 需要檢查 ⚠️（可能可接受）
  └─ > 2 層（跨多層修改）→ God Ticket ❌（強制拆分）
```

#### 步驟 4: 評估預估工時

根據 Ticket 的「步驟」章節複雜度評估工時。

**評估依據**:

```text
1. 步驟數量：
   ├─ < 10 項 → 簡單任務（2-4 小時）
   ├─ 10-20 項 → 中等任務（4-8 小時）
   └─ > 20 項 → 複雜任務（> 8 小時）

2. 步驟複雜度：
   ├─ 單純檔案建立或方法定義 → 簡單（x1.0 係數）
   ├─ 包含邏輯實作和測試 → 中等（x1.5 係數）
   └─ 包含多層整合和異常處理 → 複雜（x2.0 係數）

3. 計算公式：
   預估工時 = 步驟數量 × 平均每步驟時間 × 複雜度係數

範例：
- 15 個步驟 × 30 分鐘 × 1.5 係數 = 11.25 小時 ⚠️
- 25 個步驟 × 30 分鐘 × 2.0 係數 = 25 小時 ❌ → God Ticket
```

**判斷標準**:

```text
  ├─ 2-4 小時 → 良好設計 ✅
  ├─ 4-8 小時 → 需要檢查 ⚠️
  ├─ 8-16 小時 → 建議拆分 ⚠️
  └─ > 16 小時 → God Ticket ❌（強制拆分）
```

### 2.3 檢測失敗處理（拆分策略決策樹）

**檢測失敗處理流程**:

```text
God Ticket 檢測失敗 → 執行拆分策略

步驟 1: 選擇拆分策略
  優先策略: 按層級拆分（引用《層級隔離派工方法論》第 3.1 節單層修改原則）
  次要策略: 按職責拆分
  最終策略: 按功能模組拆分

步驟 2: 執行拆分（引用《Ticket 拆分標準方法論》第 5.4 節拆分指引）
  範例：14 個檔案、4 層 → 拆分為 6 個 Ticket（每層級 1 個）

步驟 3: 重新檢測
  對拆分後的每個 Ticket 重新執行 C1 檢測
  確保所有 Ticket 都通過標準
```

**拆分策略決策樹**:

```text
God Ticket 拆分決策：

檔案數量 > 10 或 層級跨度 > 2？
  └─ Yes → 按層級拆分（優先）
            ├─ Layer 5: Domain 層 Ticket
            ├─ Layer 4: Domain 介面層 Ticket
            ├─ Layer 3: UseCase 層 Ticket
            ├─ Layer 2: Behavior 層 Ticket
            └─ Layer 1: UI 層 Ticket

預估工時 > 16 小時？
  └─ Yes → 按職責拆分（次要）
            ├─ 職責 1: 資料建模 Ticket
            ├─ 職責 2: 業務邏輯 Ticket
            ├─ 職責 3: 介面整合 Ticket
            └─ 職責 4: UI 呈現 Ticket

職責數量 > 5？
  └─ Yes → 按功能模組拆分（最終）
            ├─ 模組 A: 核心功能 Ticket
            ├─ 模組 B: 輔助功能 Ticket
            └─ 模組 C: 整合驗證 Ticket
```

### 2.4 C1 檢測實例（完整流程）

#### 原始 Ticket（違反 C1 標準）

```markdown
## Ticket: 新增「書籍評分」完整功能

### 背景
根據 UC-03 需求，需要新增書籍評分功能。

### 目標
實作書籍評分的完整功能，包含 UI、邏輯、資料儲存。

### 步驟
1. 建立 Rating Value Object（`lib/domain/value_objects/rating_value.dart`）
2. 建立 Rating Entity（`lib/domain/entities/rating.dart`）
3. 更新 Book Entity（`lib/domain/entities/book.dart`）
4. 定義 IRatingRepository（`lib/domain/repositories/i_rating_repository.dart`）
5. 實作 RatingRepositoryImpl（`lib/infrastructure/repositories/rating_repository_impl.dart`）
6. 建立 Rating 資料表（`lib/infrastructure/database/rating_table.dart`）
7. 定義 RateBookUseCase 介面（`lib/application/use_cases/i_rate_book_use_case.dart`）
8. 實作 RateBookUseCase（`lib/application/use_cases/rate_book_use_case.dart`）
9. 定義 GetBookRatingUseCase 介面（`lib/application/use_cases/i_get_book_rating_use_case.dart`）
10. 實作 GetBookRatingUseCase（`lib/application/use_cases/get_book_rating_use_case.dart`）
11. 更新 BookDetailController（`lib/presentation/controllers/book_detail_controller.dart`）
12. 建立 RatingController（`lib/presentation/controllers/rating_controller.dart`）
13. 建立 RatingWidget（`lib/presentation/widgets/rating_widget.dart`）
14. 更新 BookDetailWidget（`lib/presentation/widgets/book_detail_widget.dart`）
15. 撰寫測試
```

#### C1 檢測執行

```text
步驟 1: 列出檔案清單
  檔案數量 = 14 個

步驟 2: 計算檔案數量
  14 個 > 10 個 → God Ticket ❌

步驟 3: 判斷層級跨度
  檔案層級分布：
  - Layer 5: rating_value.dart, rating.dart, book.dart (3 個)
  - Layer 5: rating_repository_impl.dart, rating_table.dart (2 個)
  - Layer 4: i_rating_repository.dart (1 個)
  - Layer 3: i_rate_book_use_case.dart, rate_book_use_case.dart (2 個)
  - Layer 3: i_get_book_rating_use_case.dart, get_book_rating_use_case.dart (2 個)
  - Layer 2: book_detail_controller.dart, rating_controller.dart (2 個)
  - Layer 1: rating_widget.dart, book_detail_widget.dart (2 個)

  層級跨度 = 5 - 1 = 4 層 ❌ → God Ticket

步驟 4: 評估預估工時
  步驟數量 = 15 項
  複雜度 = 包含多層整合（x2.0 係數）
  預估工時 = 15 × 30 分鐘 × 2.0 = 15 小時 ⚠️

結論: 檔案數量和層級跨度都超標 → God Ticket ❌（必須拆分）
```

#### 拆分策略執行

```text
選擇策略: 按層級拆分（優先策略）

拆分結果（6 個 Ticket）:

Ticket 1 [Layer 5]: Rating Domain 模型
  - rating_value.dart
  - rating.dart
  - book.dart（新增 rating 欄位）

Ticket 2 [Layer 5 + 4]: Rating Repository
  - i_rating_repository.dart（介面）
  - rating_repository_impl.dart（實作）
  - rating_table.dart（資料表）

Ticket 3 [Layer 3]: RateBook UseCase
  - i_rate_book_use_case.dart（介面）
  - rate_book_use_case.dart（實作）

Ticket 4 [Layer 3]: GetBookRating UseCase
  - i_get_book_rating_use_case.dart（介面）
  - get_book_rating_use_case.dart（實作）

Ticket 5 [Layer 2]: Rating Controller 整合
  - book_detail_controller.dart（更新）
  - rating_controller.dart（新建）

Ticket 6 [Layer 1]: Rating UI 元件
  - rating_widget.dart（新建）
  - book_detail_widget.dart（更新）
```

#### 拆分後重新檢測

```text
Ticket 1 [Layer 5]: Rating Domain 模型
  檔案數量: 3 個 ✅
  層級跨度: 1 層 ✅
  預估工時: 3 小時 ✅
  結論: 通過 ✅

Ticket 2 [Layer 5 + 4]: Rating Repository
  檔案數量: 3 個 ✅
  層級跨度: 2 層 ⚠️（Repository 介面和實作可接受）
  預估工時: 4 小時 ✅
  結論: 通過 ✅

Ticket 3 [Layer 3]: RateBook UseCase
  檔案數量: 2 個 ✅
  層級跨度: 1 層 ✅
  預估工時: 3 小時 ✅
  結論: 通過 ✅

Ticket 4 [Layer 3]: GetBookRating UseCase
  檔案數量: 2 個 ✅
  層級跨度: 1 層 ✅
  預估工時: 2.5 小時 ✅
  結論: 通過 ✅

Ticket 5 [Layer 2]: Rating Controller 整合
  檔案數量: 2 個 ✅
  層級跨度: 1 層 ✅
  預估工時: 3 小時 ✅
  結論: 通過 ✅

Ticket 6 [Layer 1]: Rating UI 元件
  檔案數量: 2 個 ✅
  層級跨度: 1 層 ✅
  預估工時: 4 小時 ✅
  結論: 通過 ✅

最終結論: 所有 Ticket 都通過 C1 檢測 ✅
```

#### 改善效果

| 維度 | 原始 Ticket | 拆分後（6 個 Ticket） | 改善 |
|------|-----------|-------------------|------|
| **檔案數量** | 14 個 ❌ | 2-3 個/Ticket ✅ | 符合標準 |
| **層級跨度** | 4 層 ❌ | 1-2 層/Ticket ✅ | 符合單層修改原則 |
| **預估工時** | 15 小時 ⚠️ | 2.5-4 小時/Ticket ✅ | 可在半天內完成 |
| **可並行性** | 無法並行 | 6 個 Ticket 可同時開發 | 縮短總開發時間 |
| **測試粒度** | 整體測試困難 | 每層獨立測試 | 提升測試可靠性 |
| **風險控制** | 高風險 | 低風險 | 易於驗證和回溯 |

---

## 第三章：C2 架構完整性檢測（Incomplete Ticket 檢測）

### 3.1 Incomplete Ticket 判定標準

**C2 檢測的核心使命**: 確保 Ticket 包含必要元素，開發者可以明確理解需求、驗收標準和測試方法。

**Incomplete Ticket 定義**:

Incomplete Ticket 是指 Ticket 內容缺失關鍵元素，導致：
- 開發者無法明確理解需求
- 驗收標準不清楚或無法量化
- 測試方法不明確
- 缺乏設計決策的依據文件

**四要素檢測標準**:

| 元素 | 檢查內容 | 通過標準 | 重要性 |
|------|---------|---------|--------|
| **驗收條件** | 是否有「### 驗收條件」章節 | 至少 3 個可驗證的驗收項目 | 🔴 必要 |
| **測試規劃** | 步驟中是否包含測試 | 明確列出測試檔案和測試項目 | 🔴 必要 |
| **工作日誌規劃** | 是否規劃工作日誌檔案 | 明確工作日誌檔案名稱和記錄內容 | 🔴 必要 |
| **參考文件** | 是否連結需求規格或設計文件 | 至少 1 個有效的文件連結 | 🔴 必要 |

**判定邏輯**: **任一元素缺失 = Incomplete Ticket**（必須補充）

### 3.2 四要素檢查方法

#### 要素 1: 驗收條件完整性

**檢查流程**:

```text
掃描 Ticket 內容
  ↓
檢查是否包含「### 驗收條件」章節？
  ├─ Yes → 檢查驗收項目數量
  │         ├─ ≥ 3 個 → 通過 ✅
  │         └─ < 3 個 → 失敗 ❌（驗收條件不足）
  │
  └─ No → 失敗 ❌（缺少驗收條件章節）

驗收條件品質檢查：
  ├─ 是否可量化驗證？（避免模糊描述）
  ├─ 是否限定在該層級？（不跨層級驗收）
  └─ 是否涵蓋功能性、品質性、整合性？
```

**合格範例**:
```markdown
### 驗收條件
- [ ] `IBookRepository` 介面檔案建立在 `lib/domains/library/repositories/`
- [ ] `getBookByIsbn(String isbn)` 方法簽名完整且明確
- [ ] 方法包含完整的文檔註解（參數、回傳值、異常）
- [ ] dart analyze 0 錯誤
- [ ] 測試覆蓋率 > 80%
- [ ] 不破壞既有功能（回歸測試通過）
```

**不合格範例**:
```markdown
### 驗收條件
- [ ] 功能可以正常運作
- [ ] 程式碼品質良好
```
❌ 問題：驗收條件過於模糊，無法量化驗證

#### 要素 2: 測試規劃完整性

**檢查流程**:

```text
掃描「步驟」章節
  ↓
檢查是否包含測試相關步驟？
  ├─ Yes → 檢查測試內容
  │         ├─ 有測試檔案路徑 ✅
  │         ├─ 有測試項目清單 ✅
  │         ├─ 有測試覆蓋率要求 ✅
  │         └─ 通過 ✅
  │
  └─ No → 失敗 ❌（缺少測試規劃）

測試規劃品質檢查：
  ├─ 是否包含單元測試？
  ├─ 是否包含整合測試？（如需要）
  └─ 是否定義測試覆蓋率標準？
```

**合格範例**:
```markdown
### 步驟
4. 撰寫 `test/domain/repositories/book_repository_test.dart` 單元測試
   - 測試 `getBookByIsbn` 正常流程（書籍存在）
   - 測試書籍不存在異常處理
   - 測試 ISBN 格式錯誤異常處理
   - 測試網路錯誤異常處理
5. 確保測試覆蓋率 > 80%
```

**不合格範例**:
```markdown
### 步驟
4. 撰寫測試
```
❌ 問題：沒有明確測試檔案路徑和測試項目

#### 要素 3: 工作日誌規劃

**檢查流程**:

```text
掃描 Ticket 內容
  ↓
檢查是否包含「### 工作日誌」章節？
  ├─ Yes → 檢查檔案名稱
  │         ├─ 符合命名規範 ✅
  │         │   格式: docs/work-logs/vX.Y.Z-feature-name.md
  │         └─ 通過 ✅
  │
  └─ No → 失敗 ❌（缺少工作日誌規劃）

命名規範檢查：
  ├─ 是否包含版本號？
  ├─ 是否描述性命名？
  └─ 是否在 docs/work-logs/ 目錄下？
```

**合格範例**:
```markdown
### 工作日誌
檔案名稱: `docs/work-logs/v0.12.8-book-repository-interface.md`

記錄內容:
- Ticket 執行過程
- 設計決策和理由
- 遇到的問題和解決方法
- 測試結果和覆蓋率報告
```

**不合格範例**:
```markdown
（沒有工作日誌規劃）
```
❌ 問題：缺少工作日誌章節

#### 要素 4: 參考文件連結

**檢查流程**:

```text
掃描 Ticket 內容
  ↓
檢查是否包含「### 參考文件」章節？
  ├─ Yes → 檢查連結有效性
  │         ├─ 至少 1 個連結 ✅
  │         ├─ 連結格式正確 ✅
  │         └─ 連結內容相關 ✅
  │
  └─ No → 失敗 ❌（缺少參考文件）

連結品質檢查：
  ├─ 是否連結需求規格？（建議）
  ├─ 是否連結設計文件？（建議）
  └─ 是否連結相關 Ticket？（如有依賴）
```

**合格範例**:
```markdown
### 參考文件
- `docs/app-requirements-spec.md` #UC-01 書籍查詢功能
- `docs/work-logs/v0.12.7-design-decisions.md` #決策1 Repository 設計模式
- `.claude/methodologies/layered-ticket-methodology.md` 層級隔離原則
```

**不合格範例**:
```markdown
（沒有參考文件章節）
```
❌ 問題：缺少參考文件章節

### 3.3 完整性修正流程

**缺失項目 1: 沒有驗收條件**

修正步驟:
```text
1. 新增「### 驗收條件」章節
2. 撰寫 3-6 個可量化驗收項目
3. 涵蓋三個維度:
   - 功能性驗收（檔案位置、方法簽名、程式邏輯）
   - 品質性驗收（dart analyze、測試覆蓋率、文檔）
   - 整合性驗收（整合測試、不破壞既有功能）
```

**缺失項目 2: 沒有測試規劃**

修正步驟:
```text
1. 在「### 步驟」章節新增測試步驟
2. 明確列出測試檔案路徑
3. 列出測試項目清單（正常流程 + 異常處理）
4. 定義測試覆蓋率要求（建議 > 80%）
```

**缺失項目 3: 沒有工作日誌規劃**

修正步驟:
```text
1. 新增「### 工作日誌」章節
2. 定義工作日誌檔案名稱
   格式: docs/work-logs/vX.Y.Z-feature-name.md
3. 說明記錄內容範圍
```

**缺失項目 4: 沒有參考文件**

修正步驟:
```text
1. 新增「### 參考文件」章節
2. 連結需求規格（必要）
3. 連結設計文件（建議）
4. 連結相關 Ticket（如有依賴）
```

### 3.4 C2 檢測實例（完整流程）

**檢測範例**:

```text
Ticket #1: [Layer 5] 定義 IBookRepository 介面
  ↓
執行 C2. Incomplete Ticket 檢測
  ↓
【步驟 1】檢查驗收條件
  ├─ 有「### 驗收條件」章節 ✅
  ├─ 驗收項目數量: 6 個 ✅
  ├─ 驗收條件可量化 ✅
  └─ 通過 ✅
  ↓
【步驟 2】檢查測試規劃
  ├─ 步驟 4 包含測試 ✅
  ├─ 測試檔案路徑明確 ✅
  ├─ 測試項目完整 ✅
  └─ 通過 ✅
  ↓
【步驟 3】檢查工作日誌規劃
  ├─ 有「### 工作日誌」章節 ✅
  ├─ 檔案名稱符合規範 ✅
  └─ 通過 ✅
  ↓
【步驟 4】檢查參考文件
  ├─ 有「### 參考文件」章節 ✅
  ├─ 連結數量: 3 個 ✅
  ├─ 連結格式正確 ✅
  └─ 通過 ✅
  ↓
C2 檢測結論: 通過 ✅
```

**修正前後對比**:

| 維度 | 修正前 | 修正後 | 改善 |
|------|--------|--------|------|
| **驗收條件** | 缺失 ❌ | 6 個可量化項目 ✅ | 明確驗收標準 |
| **測試規劃** | 模糊描述 ❌ | 完整測試路徑和項目 ✅ | 測試可執行 |
| **工作日誌** | 缺失 ❌ | 明確檔案和內容範圍 ✅ | 過程可追溯 |
| **參考文件** | 缺失 ❌ | 3 個有效連結 ✅ | 需求可查證 |
| **開發可行性** | 低 | 高 | 開發者可獨立執行 |

---

## 第四章：C3 責任明確性檢測（Ambiguous Responsibility 檢測）

### 4.1 Ambiguous Responsibility 判定標準

**C3 檢測的核心使命**: 確保 Ticket 的層級和職責清晰，避免職責模糊導致跨層級耦合和設計混亂。

**Ambiguous Responsibility 定義**:

Ambiguous Responsibility 是指 Ticket 的職責定義模糊，導致：
- 無法判斷 Ticket 屬於哪一層級
- 職責範圍不清楚（做什麼、不做什麼）
- 影響的檔案範圍不明確
- 驗收條件跨越多個層級

**四要素檢測標準**:

| 要素 | 檢查內容 | 通過標準 | 重要性 |
|------|---------|---------|--------|
| **層級標示** | 標題是否包含 `[Layer X]` 標籤 | 明確標示所屬層級（Layer 1-5） | 🔴 必要 |
| **職責描述** | 目標章節是否明確定義職責 | 明確說明「做什麼」和「責任範圍」 | 🔴 必要 |
| **檔案範圍** | 步驟章節是否明確列出檔案 | 具體列出檔案路徑，不使用模糊描述 | 🔴 必要 |
| **驗收限定** | 驗收條件是否限定在該層級 | 只驗證該層級的職責，不跨層驗收 | 🔴 必要 |

**判定邏輯**: **任一要素缺失 = Ambiguous Responsibility**（必須重新定義）

### 4.2 四要素檢查方法

#### 要素 1: 層級標示檢查

**檢查流程**:

```text
檢查 Ticket 標題
  ↓
是否包含 [Layer X] 標籤？
  ├─ Yes → 檢查標籤正確性
  │         ├─ Layer 1-5 有效 ✅
  │         └─ 通過 ✅
  │
  └─ No → 失敗 ❌（缺少層級標示）

層級標籤檢查：
  ├─ [Layer 1] - UI 層（Widget/Page）
  ├─ [Layer 2] - Behavior 層（Controller/Provider）
  ├─ [Layer 3] - UseCase 層（業務邏輯）
  ├─ [Layer 4] - Domain Events/Interfaces 層
  └─ [Layer 5] - Domain Implementation 層（Entity/Repository）
```

**合格範例**:
```markdown
## Ticket: [Layer 2] 實作書籍詳情 Controller 事件處理
```
✅ 明確標示屬於 Layer 2（Behavior 層）

**不合格範例**:
```markdown
## Ticket: 實作書籍詳情功能
```
❌ 缺少層級標示，無法判斷屬於哪一層

#### 要素 2: 職責描述明確性

**檢查流程**:

```text
檢查「### 目標」章節
  ↓
是否明確定義職責？
  ├─ Yes → 檢查職責清晰度
  │         ├─ 明確說明「做什麼」 ✅
  │         ├─ 明確說明「責任範圍」 ✅
  │         ├─ 明確說明「不做什麼」 ✅
  │         └─ 通過 ✅
  │
  └─ No → 失敗 ❌（職責定義模糊）

職責清晰度檢查：
  ├─ 職責是否限定在單一層級？
  ├─ 是否清楚描述輸入和輸出？
  └─ 是否明確職責邊界？
```

**合格範例**:
```markdown
### 目標
實作 BookDetailController 的 loadBookDetail 方法，
負責接收使用者的「查看書籍詳情」事件並呼叫 GetBookDetailUseCase。

職責範圍：
- 接收使用者事件（如按鈕點擊）
- 呼叫 GetBookDetailUseCase 獲取書籍資料
- 將 UseCase 回傳的資料傳遞給 UI
- 不包含業務邏輯實作（業務邏輯在 UseCase 層）
```
✅ 明確定義職責範圍和邊界

**不合格範例**:
```markdown
### 目標
實作書籍詳情功能，讓使用者可以查看書籍的完整資訊。
```
❌ 職責定義模糊：
- "書籍詳情功能"範圍太廣（UI? 邏輯? 資料？）
- 沒有明確說明職責範圍和邊界

#### 要素 3: 檔案範圍明確性

**檢查流程**:

```text
檢查「### 步驟」章節
  ↓
是否明確列出檔案路徑？
  ├─ Yes → 檢查檔案路徑
  │         ├─ 完整路徑（非模糊描述） ✅
  │         ├─ 檔案都屬於同一層級 ✅
  │         └─ 通過 ✅
  │
  └─ No → 失敗 ❌（檔案範圍模糊）

檔案路徑品質檢查：
  ├─ 是否使用具體檔案路徑？
  ├─ 是否避免模糊描述（如"相關檔案"）？
  └─ 檔案是否都屬於同一層級？
```

**合格範例**:
```markdown
### 步驟
1. 修改 `lib/presentation/controllers/book_detail_controller.dart`
2. 新增 `loadBookDetail(String isbn)` 方法
3. 注入 `IGetBookDetailUseCase` 依賴
4. 撰寫單元測試
```
✅ 明確列出具體檔案路徑

**不合格範例**:
```markdown
### 步驟
1. 修改相關檔案
2. 實作查詢邏輯
3. 更新 UI 顯示
```
❌ 檔案範圍模糊：
- "相關檔案"沒有具體說明
- 沒有明確的檔案路徑

#### 要素 4: 驗收條件限定性

**檢查流程**:

```text
檢查「### 驗收條件」章節
  ↓
驗收條件是否限定在該層級？
  ├─ Yes → 檢查驗收項目
  │         ├─ 只驗證該層級職責 ✅
  │         ├─ 不包含其他層級驗收 ✅
  │         └─ 通過 ✅
  │
  └─ No → 失敗 ❌（驗收未限定）

驗收限定性檢查：
  ├─ 是否只驗證該層級的輸入輸出？
  ├─ 是否避免驗證其他層級的功能？
  └─ 是否符合單一職責原則？
```

**合格範例（Layer 2 Controller）**:
```markdown
### 驗收條件
- [ ] BookDetailController.loadBookDetail() 方法建立在正確位置
- [ ] 正確注入 IGetBookDetailUseCase 依賴
- [ ] loadBookDetail() 正確呼叫 useCase.execute()
- [ ] 正確處理 OperationResult（success/failure）
- [ ] 事件處理邏輯正確（不包含業務邏輯）
- [ ] 單元測試覆蓋率 > 80%
```
✅ 驗收條件限定在 Layer 2（Controller 層）：
- 只驗證 Controller 的事件處理
- 不驗證 UI 顯示（Layer 1）
- 不驗證業務邏輯（Layer 3）

**不合格範例**:
```markdown
### 驗收條件
- [ ] 使用者可以看到書籍詳情
- [ ] 資料正確顯示
- [ ] 功能正常運作
```
❌ 驗收未限定在單一層級：
- "使用者可以看到"是 UI 層（Layer 1）驗收
- "功能正常運作"涵蓋所有層級

### 4.3 明確化重新定義流程

**C3 檢測失敗處理流程**:

```text
C3 檢測失敗 → 執行重新定義步驟

步驟 1: 明確層級定位
  使用《層級隔離派工方法論》檔案路徑分析法判斷層級
  在標題加上 [Layer X] 標籤

步驟 2: 重新定義職責
  基於該層級的職責範圍重寫目標章節
  明確說明「做什麼」「責任範圍」「不做什麼」

步驟 3: 明確檔案範圍
  列出具體的檔案路徑（避免籠統描述）
  確保檔案都屬於同一層級

步驟 4: 限定驗收條件
  驗收條件只驗證該層級的職責
  移除跨層級的驗收項目

步驟 5: 重新檢測
  確認所有 4 個必要元素都已明確
```

**重新定義決策樹**:

```text
發現 Ambiguous Responsibility
  ↓
【步驟 1】明確層級定位
  ↓
分析 Ticket 內容 → 判斷主要職責
  ├─ UI 顯示和互動 → Layer 1（UI）
  ├─ 事件處理和狀態管理 → Layer 2（Behavior）
  ├─ 業務邏輯和流程控制 → Layer 3（UseCase）
  ├─ 領域事件和介面定義 → Layer 4（Interfaces）
  └─ 領域模型和資料存取 → Layer 5（Domain）
  ↓
更新標題 → 加上 [Layer X] 標籤
  ↓
【步驟 2】重新定義職責
  ↓
基於該層級職責範圍重寫目標：
  - 明確輸入來源（上一層 or 外部）
  - 明確處理內容（該層職責）
  - 明確輸出目標（下一層 or 結果）
  - 明確職責邊界（不做什麼）
  ↓
【步驟 3】明確檔案範圍
  ↓
列出具體檔案路徑 → 確認都屬於同一層級
  ↓
【步驟 4】限定驗收條件
  ↓
只驗證該層級職責 → 移除跨層驗收
  ↓
【步驟 5】重新檢測 C3
```

### 4.4 C3 檢測實例（完整流程）

#### 原始 Ticket（違反 C3 標準）

```markdown
## Ticket: 實作書籍詳情功能

### 背景
根據 UC-02 需求，需要實作書籍詳情功能。

### 目標
實作書籍詳情功能，讓使用者可以查看書籍的完整資訊。

### 步驟
1. 修改相關檔案
2. 實作查詢邏輯
3. 更新 UI 顯示

### 驗收條件
- [ ] 使用者可以看到書籍詳情
- [ ] 資料正確顯示
- [ ] 功能正常運作
```

#### C3 檢測執行

```text
步驟 1: 檢查層級標示
  標題: "實作書籍詳情功能"
  結果: 沒有 [Layer X] 標籤 ❌
  問題: 無法判斷屬於哪一層級

步驟 2: 檢查職責描述
  目標: "實作書籍詳情功能，讓使用者可以查看書籍的完整資訊"
  結果: 職責定義模糊 ❌
  問題:
  - "書籍詳情功能"範圍太廣（UI? 邏輯? 資料？）
  - 沒有明確說明職責範圍

步驟 3: 檢查檔案範圍
  步驟: "修改相關檔案"
  結果: 檔案範圍模糊 ❌
  問題:
  - "相關檔案"沒有具體說明
  - 沒有明確的檔案路徑

步驟 4: 檢查驗收限定
  驗收條件: "使用者可以看到書籍詳情"、"功能正常運作"
  結果: 驗收未限定在單一層級 ❌
  問題:
  - "使用者可以看到"是 UI 層驗收
  - "功能正常運作"涵蓋所有層級

結論: Ambiguous Responsibility ❌（必須重新定義）
```

#### 重新定義執行

```text
步驟 1: 明確層級定位
  分析 Ticket 內容 → 主要涉及 Controller 事件處理
  判斷層級 → Layer 2（Behavior）
  更新標題 → 加上 [Layer 2] 標籤

步驟 2: 重新定義職責
  重寫目標章節：
  - 明確說明「接收使用者事件」
  - 明確說明「呼叫 UseCase」
  - 明確說明「不包含業務邏輯」

步驟 3: 明確檔案範圍
  列出具體檔案路徑：
  - lib/presentation/controllers/book_detail_controller.dart

步驟 4: 限定驗收條件
  只驗證 Layer 2 的職責：
  - Controller 方法建立
  - 依賴注入正確
  - UseCase 呼叫正確
  - 事件處理邏輯正確
```

#### 修正後 Ticket（符合 C3 標準）

```markdown
## Ticket: [Layer 2] 實作書籍詳情 Controller 事件處理

### 背景
根據 UC-02 需求，需要實作 BookDetailController 的事件處理邏輯。

### 目標
實作 BookDetailController 的 loadBookDetail 方法，
負責接收使用者的「查看書籍詳情」事件並呼叫 GetBookDetailUseCase。

職責範圍：
- 接收使用者事件（如按鈕點擊）
- 呼叫 GetBookDetailUseCase 獲取書籍資料
- 將 UseCase 回傳的資料傳遞給 UI
- 不包含業務邏輯實作（業務邏輯在 UseCase 層）

### 步驟
1. 修改 `lib/presentation/controllers/book_detail_controller.dart`
2. 新增 `loadBookDetail(String isbn)` 方法
3. 注入 `IGetBookDetailUseCase` 依賴
4. 實作事件處理邏輯：
   - 呼叫 `useCase.execute(isbn)`
   - 處理回傳的 `OperationResult<Book>`
   - 更新 Controller 狀態（loading/success/error）
5. 撰寫單元測試

### 驗收條件
- [ ] BookDetailController.loadBookDetail() 方法建立在正確位置
- [ ] 正確注入 IGetBookDetailUseCase 依賴
- [ ] loadBookDetail() 正確呼叫 useCase.execute()
- [ ] 正確處理 OperationResult（success/failure）
- [ ] 事件處理邏輯正確（不包含業務邏輯）
- [ ] 單元測試覆蓋率 > 80%
- [ ] dart analyze 0 錯誤

### 依賴 Ticket
- Ticket #3: 定義 IGetBookDetailUseCase 介面（必須先完成）

### 參考文件
- docs/app-requirements-spec.md #UC-02
- docs/work-logs/v0.12.8-design-decisions.md #決策2
```

#### 修正後重新檢測

```text
步驟 1: 檢查層級標示
  標題: "[Layer 2] 實作書籍詳情 Controller 事件處理"
  結果: 有 [Layer 2] 標籤 ✅

步驟 2: 檢查職責描述
  目標: 明確定義職責範圍和邊界
  結果: 職責定義明確 ✅
  - 明確說明「接收事件」「呼叫 UseCase」
  - 明確說明「不包含業務邏輯」

步驟 3: 檢查檔案範圍
  步驟: 明確列出檔案路徑
  結果: 檔案範圍明確 ✅
  - `lib/presentation/controllers/book_detail_controller.dart`

步驟 4: 檢查驗收限定
  驗收條件: 限定在 Layer 2 職責
  結果: 驗收限定正確 ✅
  - 只驗證 Controller 層的職責
  - 不包含 UI 或業務邏輯驗收

結論: 通過 C3 檢測 ✅
```

#### 改善效果

| 維度 | 原始 Ticket | 修正後 Ticket | 改善 |
|------|-----------|-------------|------|
| **層級標示** | 無 ❌ | [Layer 2] ✅ | 明確定位 |
| **職責描述** | 模糊 ❌ | 明確定義範圍和邊界 ✅ | 職責清晰 |
| **檔案範圍** | "相關檔案" ❌ | 具體檔案路徑 ✅ | 影響範圍明確 |
| **驗收限定** | 跨層級 ❌ | 限定在 Layer 2 ✅ | 驗收標準清晰 |
| **可執行性** | 低 ❌ | 高 ✅ | 開發者可直接執行 |
| **職責清晰度** | 30% | 95% | 避免跨層級耦合 |

---

## 第五章：自動化檢測工具

### 5.1 自動化檢測目標

**品質閘門自動化的核心目標**:

在 v0.12.G.4「代理人和 Hook 機制調整」中,規劃將品質閘門檢測自動化,以實現:

1. **減少人工檢測工作量**
   - lavender-interface-designer 不需要手動執行所有檢測
   - 自動化腳本提供檢測結果,lavender 只需確認和處理

2. **提升檢測一致性**
   - 避免人工檢測的主觀判斷差異
   - 統一檢測標準和判定邏輯

3. **即時反饋 Ticket 品質問題**
   - Ticket 儲存時立即執行檢測
   - 立即發現問題,縮短修正週期

4. **支援 lavender-interface-designer 執行檢測**
   - 提供明確的檢測報告
   - 自動生成修正建議

**自動化範圍和限制**:

| 檢測項目 | 可自動化程度 | 自動化方法 | 需要人工判斷 |
|---------|-------------|-----------|-------------|
| **C1 檔案數量** | 100% ✅ | 掃描步驟章節,提取檔案路徑,計算數量 | 無 |
| **C1 層級跨度** | 100% ✅ | 使用檔案路徑分析法判斷層級 | 無 |
| **C1 預估工時** | 60% ⚠️ | 根據步驟數量估算（< 10 步 = 2-4h）| 複雜度需人工確認 |
| **C2 驗收條件** | 100% ✅ | 檢查章節存在性、驗收項目數量 | 無 |
| **C2 測試規劃** | 80% ⚠️ | 檢查測試檔案和關鍵字 | 測試完整性需人工確認 |
| **C2 工作日誌** | 100% ✅ | 檢查章節存在性、檔案名稱格式 | 無 |
| **C2 參考文件** | 100% ✅ | 檢查章節存在性、連結數量 | 無 |
| **C3 層級標示** | 100% ✅ | 正則匹配 `\[Layer \d+\]` | 無 |
| **C3 職責描述** | 50% ⚠️ | 檢查字數、關鍵字 | 明確性需人工確認 |
| **C3 檔案範圍** | 100% ✅ | 檢查具體檔案路徑 | 無 |
| **C3 驗收限定** | 70% ⚠️ | 提取驗收條件的類別名稱 | 層級一致性需人工確認 |

**自動化信心度等級**:

```text
高信心度（≥ 90%）:
  - C1 檔案數量、C1 層級跨度
  - C2 驗收條件、C2 工作日誌、C2 參考文件
  - C3 層級標示、C3 檔案範圍
  → 可直接使用自動化結果

中信心度（60-89%）:
  - C1 預估工時
  - C2 測試規劃
  - C3 驗收限定
  → 自動化提供初步判斷,人工確認

低信心度（< 60%）:
  - C3 職責描述
  → 自動化提供參考,人工判斷為主
```

### 5.2 Python 檢測腳本設計

#### C1 God Ticket 自動化檢測腳本

**腳本功能**: 自動檢測 Ticket 是否為 God Ticket

**檢測邏輯**:

```python
def check_god_ticket_automated(ticket_content: str) -> dict:
    """
    自動化檢測 God Ticket

    參數:
        ticket_content: Ticket 的 Markdown 內容

    回傳格式:
    {
        "file_count": int,              # 檔案數量
        "layer_span": int,              # 層級跨度
        "estimated_hours": int,         # 預估工時
        "is_god_ticket": bool,          # 是否為 God Ticket
        "confidence": float,            # 信心度 (0.0-1.0)
        "reasons": list                 # 超標項目清單
    }
    """
    # 1. 提取檔案路徑（從步驟章節）
    file_paths = extract_file_paths(ticket_content)
    file_count = len(file_paths)

    # 2. 判斷層級跨度（使用檔案路徑分析法）
    layers = [determine_layer(path) for path in file_paths]
    layer_span = max(layers) - min(layers) + 1 if layers else 0

    # 3. 預估工時（簡化估算）
    step_count = count_steps(ticket_content)
    estimated_hours = estimate_hours_by_steps(step_count)

    # 4. 判斷是否為 God Ticket（任一項目超標）
    reasons = []
    if file_count > 10:
        reasons.append(f"檔案數量超標: {file_count} > 10")
    if layer_span > 2:
        reasons.append(f"層級跨度超標: {layer_span} > 2")
    if estimated_hours > 16:
        reasons.append(f"預估工時超標: {estimated_hours}h > 16h")

    is_god_ticket = len(reasons) > 0

    # 5. 計算信心度
    # 檔案數量和層級跨度是 100% 信心度
    # 預估工時信心度較低（60%）
    confidence = 0.9 if file_count > 0 else 0.6

    return {
        "file_count": file_count,
        "layer_span": layer_span,
        "estimated_hours": estimated_hours,
        "is_god_ticket": is_god_ticket,
        "confidence": confidence,
        "reasons": reasons
    }

def extract_file_paths(ticket_content: str) -> list:
    """
    從 Ticket 內容提取檔案路徑

    邏輯:
    - 掃描「### 步驟」章節
    - 使用正則匹配 `lib/**/*.dart` 格式
    - 去除測試檔案（test/**/*.dart）
    """
    import re

    # 提取步驟章節
    steps_section = extract_section(ticket_content, "### 步驟")

    # 正則匹配檔案路徑
    file_pattern = r'`(lib/[^`]+\.dart)`'
    file_paths = re.findall(file_pattern, steps_section)

    # 去除重複
    return list(set(file_paths))

def determine_layer(file_path: str) -> int:
    """
    判斷檔案所屬層級

    使用《層級隔離派工方法論》第 6.2 節檔案路徑分析法
    """
    layer_mapping = {
        'lib/presentation/widgets/': 1,
        'lib/presentation/pages/': 1,
        'lib/presentation/controllers/': 2,
        'lib/presentation/providers/': 2,
        'lib/presentation/view_models/': 2,
        'lib/application/use_cases/': 3,
        'lib/application/services/': 3,
        'lib/domain/events/': 4,
        'lib/domain/repositories/': 4,  # 介面
        'lib/domain/entities/': 5,
        'lib/domain/value_objects/': 5,
        'lib/infrastructure/repositories/': 5,  # 實作
        'lib/infrastructure/services/': 5,
    }

    for prefix, layer in layer_mapping.items():
        if file_path.startswith(prefix):
            return layer

    return 0  # 無法判斷

def estimate_hours_by_steps(step_count: int) -> int:
    """
    根據步驟數量估算工時

    簡化估算公式:
    - < 10 步: 2-4 小時 → 平均 3 小時
    - 10-20 步: 4-8 小時 → 平均 6 小時
    - > 20 步: > 8 小時 → 按 0.5 小時/步驟計算
    """
    if step_count < 10:
        return 3
    elif step_count <= 20:
        return 6
    else:
        return int(step_count * 0.5)
```

#### C2 Incomplete Ticket 自動化檢測腳本

**腳本功能**: 自動檢測 Ticket 是否缺失必要元素

**檢測邏輯**:

```python
def check_incomplete_ticket_automated(ticket_content: str) -> dict:
    """
    自動化檢測 Incomplete Ticket

    回傳格式:
    {
        "has_acceptance_criteria": bool,    # 是否有驗收條件
        "acceptance_count": int,            # 驗收項目數量
        "has_test_plan": bool,              # 是否有測試規劃
        "test_files": list,                 # 測試檔案清單
        "has_work_log": bool,               # 是否有工作日誌規劃
        "work_log_file": str,               # 工作日誌檔案名稱
        "has_references": bool,             # 是否有參考文件
        "reference_count": int,             # 參考文件數量
        "is_incomplete": bool,              # 是否為 Incomplete Ticket
        "missing_elements": list            # 缺失元素清單
    }
    """
    # 1. 檢查驗收條件
    has_acceptance = has_section(ticket_content, "### 驗收條件")
    acceptance_count = count_acceptance_items(ticket_content)

    # 2. 檢查測試規劃
    has_test_plan = has_test_keywords(ticket_content)
    test_files = extract_test_files(ticket_content)

    # 3. 檢查工作日誌
    has_work_log = has_section(ticket_content, "### 工作日誌")
    work_log_file = extract_work_log_file(ticket_content)

    # 4. 檢查參考文件
    has_references = has_section(ticket_content, "### 參考文件")
    reference_count = count_references(ticket_content)

    # 5. 判斷缺失元素
    missing_elements = []
    if not has_acceptance or acceptance_count < 3:
        missing_elements.append("驗收條件不足（< 3 個）")
    if not has_test_plan or len(test_files) == 0:
        missing_elements.append("測試規劃不明確")
    if not has_work_log or not work_log_file:
        missing_elements.append("工作日誌規劃缺失")
    if not has_references or reference_count < 1:
        missing_elements.append("參考文件不足（< 1 個）")

    # 6. 判斷是否為 Incomplete Ticket
    is_incomplete = len(missing_elements) > 0

    return {
        "has_acceptance_criteria": has_acceptance,
        "acceptance_count": acceptance_count,
        "has_test_plan": has_test_plan,
        "test_files": test_files,
        "has_work_log": has_work_log,
        "work_log_file": work_log_file,
        "has_references": has_references,
        "reference_count": reference_count,
        "is_incomplete": is_incomplete,
        "missing_elements": missing_elements
    }

def has_section(ticket_content: str, section_header: str) -> bool:
    """檢查 Ticket 是否包含特定章節"""
    return section_header in ticket_content

def count_acceptance_items(ticket_content: str) -> int:
    """計算驗收條件項目數量"""
    import re

    # 提取驗收條件章節
    acceptance_section = extract_section(ticket_content, "### 驗收條件")

    # 正則匹配 checkbox 項目
    pattern = r'- \[ \]'
    return len(re.findall(pattern, acceptance_section))

def has_test_keywords(ticket_content: str) -> bool:
    """檢查是否包含測試相關關鍵字"""
    test_keywords = ['測試', 'test', '單元測試', '整合測試', '覆蓋率']
    return any(keyword in ticket_content for keyword in test_keywords)

def extract_test_files(ticket_content: str) -> list:
    """提取測試檔案路徑"""
    import re

    # 正則匹配測試檔案路徑
    pattern = r'`(test/[^`]+\.dart)`'
    return re.findall(pattern, ticket_content)
```

#### C3 Ambiguous Responsibility 自動化檢測腳本

**腳本功能**: 自動檢測 Ticket 職責是否明確

**檢測邏輯**:

```python
def check_ambiguous_responsibility_automated(ticket_content: str) -> dict:
    """
    自動化檢測 Ambiguous Responsibility

    回傳格式:
    {
        "has_layer_tag": bool,                  # 是否有層級標示
        "layer_number": int,                    # 層級編號
        "has_clear_responsibility": bool,       # 職責描述是否明確
        "responsibility_length": int,           # 職責描述字數
        "has_file_paths": bool,                 # 是否有檔案路徑
        "file_count": int,                      # 檔案數量
        "acceptance_limited_to_layer": bool,    # 驗收是否限定在該層
        "is_ambiguous": bool,                   # 是否職責模糊
        "confidence": float,                    # 信心度
        "missing_elements": list                # 缺失元素清單
    }
    """
    # 1. 檢查層級標示
    has_layer_tag, layer_number = extract_layer_tag(ticket_content)

    # 2. 檢查職責描述（簡化檢查）
    responsibility = extract_responsibility(ticket_content)
    has_clear_responsibility = len(responsibility) > 20

    # 3. 檢查檔案範圍
    file_paths = extract_file_paths(ticket_content)
    has_file_paths = len(file_paths) > 0

    # 4. 檢查驗收限定（需要層級判斷）
    acceptance_items = extract_acceptance_items(ticket_content)
    acceptance_layers = [
        determine_layer_from_acceptance(item)
        for item in acceptance_items
    ]

    # 判斷驗收條件是否限定在單一層級
    acceptance_limited = (
        all(layer == layer_number for layer in acceptance_layers)
        if layer_number > 0 else False
    )

    # 5. 判斷缺失元素
    missing_elements = []
    if not has_layer_tag:
        missing_elements.append("缺少層級標示 [Layer X]")
    if not has_clear_responsibility:
        missing_elements.append("職責描述不明確（字數 < 20）")
    if not has_file_paths:
        missing_elements.append("檔案範圍未明確列出")
    if not acceptance_limited:
        missing_elements.append("驗收條件未限定在該層級")

    # 6. 判斷是否為 Ambiguous Responsibility
    is_ambiguous = len(missing_elements) > 0

    # 7. 計算信心度（職責描述需人工確認）
    confidence = 0.7 if has_clear_responsibility else 0.5

    return {
        "has_layer_tag": has_layer_tag,
        "layer_number": layer_number,
        "has_clear_responsibility": has_clear_responsibility,
        "responsibility_length": len(responsibility),
        "has_file_paths": has_file_paths,
        "file_count": len(file_paths),
        "acceptance_limited_to_layer": acceptance_limited,
        "is_ambiguous": is_ambiguous,
        "confidence": confidence,
        "missing_elements": missing_elements
    }

def extract_layer_tag(ticket_content: str) -> tuple:
    """
    提取層級標示

    回傳: (是否有標示, 層級編號)
    """
    import re

    # 正則匹配 [Layer X]
    pattern = r'\[Layer (\d+)\]'
    match = re.search(pattern, ticket_content)

    if match:
        return (True, int(match.group(1)))
    else:
        return (False, 0)

def extract_responsibility(ticket_content: str) -> str:
    """提取職責描述（從目標章節）"""
    return extract_section(ticket_content, "### 目標")
```

### 5.3 Hook 系統整合與檢測報告生成

#### Hook 觸發時機和整合方式

**觸發時機**: Ticket 檔案修改時（PostEdit Hook）

**整合方式**:

```python
# Hook 配置: .claude/settings.local.json
{
  "hooks": {
    "PostToolUse": [
      {
        "matcher": "Write|Edit",
        "hooks": [
          {
            "type": "command",
            "command": "$CLAUDE_PROJECT_DIR/.claude/hooks/ticket-quality-gate-hook.py"
          }
        ]
      }
    ]
  }
}
```

**Hook 主函式設計**:

```python
def ticket_quality_gate_hook(ticket_file_path: str) -> dict:
    """
    Ticket 品質閘門 Hook

    執行時機:
    - Ticket 檔案儲存時（Write/Edit）
    - lavender-interface-designer 提交工作日誌時

    回傳格式:
    {
        "passed": bool,                 # 是否通過
        "c1_result": dict,              # C1 檢測結果
        "c2_result": dict,              # C2 檢測結果
        "c3_result": dict,              # C3 檢測結果
        "suggestions": list,            # 修正建議
        "blocking_issues": list         # 阻斷問題（需立即修正）
    }
    """
    # 1. 讀取 Ticket 內容
    ticket_content = read_ticket_file(ticket_file_path)

    # 2. 執行自動化檢測（按順序：C1 → C3 → C2）
    c1_result = check_god_ticket_automated(ticket_content)
    c3_result = check_ambiguous_responsibility_automated(ticket_content)
    c2_result = check_incomplete_ticket_automated(ticket_content)

    # 3. 判斷是否通過
    passed = not (
        c1_result["is_god_ticket"] or
        c2_result["is_incomplete"] or
        c3_result["is_ambiguous"]
    )

    # 4. 生成修正建議
    suggestions = generate_suggestions(c1_result, c2_result, c3_result)

    # 5. 生成阻斷問題（需要立即修正）
    blocking_issues = []

    if c1_result["is_god_ticket"]:
        blocking_issues.append({
            "type": "C1 God Ticket",
            "message": (
                f"檔案數={c1_result['file_count']}, "
                f"層級跨度={c1_result['layer_span']}, "
                f"工時={c1_result['estimated_hours']}h"
            ),
            "reasons": c1_result["reasons"]
        })

    if c2_result["is_incomplete"]:
        blocking_issues.append({
            "type": "C2 Incomplete Ticket",
            "message": "缺少必要元素",
            "missing": c2_result["missing_elements"]
        })

    if c3_result["is_ambiguous"]:
        blocking_issues.append({
            "type": "C3 Ambiguous Responsibility",
            "message": "職責不明確",
            "missing": c3_result["missing_elements"]
        })

    # 6. 生成檢測報告
    report = {
        "passed": passed,
        "c1_result": c1_result,
        "c2_result": c2_result,
        "c3_result": c3_result,
        "suggestions": suggestions,
        "blocking_issues": blocking_issues
    }

    # 7. 記錄到日誌
    log_detection_result(ticket_file_path, report)

    return report

def generate_suggestions(c1_result, c2_result, c3_result) -> list:
    """
    生成修正建議

    根據檢測結果提供具體的修正建議
    """
    suggestions = []

    # C1 修正建議
    if c1_result["is_god_ticket"]:
        if c1_result["file_count"] > 10:
            suggestions.append(
                "【C1 拆分建議】檔案數量超標，建議按層級拆分為多個 Ticket"
            )
        if c1_result["layer_span"] > 2:
            suggestions.append(
                "【C1 拆分建議】層級跨度超標，建議按 Clean Architecture 分層拆分"
            )
        if c1_result["estimated_hours"] > 16:
            suggestions.append(
                "【C1 拆分建議】預估工時超標，建議按職責或功能模組拆分"
            )

    # C2 修正建議
    if c2_result["is_incomplete"]:
        for missing in c2_result["missing_elements"]:
            if "驗收條件" in missing:
                suggestions.append(
                    "【C2 補充建議】新增「### 驗收條件」章節，至少包含 3 個可量化項目"
                )
            if "測試規劃" in missing:
                suggestions.append(
                    "【C2 補充建議】在步驟中明確測試檔案路徑和測試項目"
                )
            if "工作日誌" in missing:
                suggestions.append(
                    "【C2 補充建議】新增「### 工作日誌」章節，定義檔案名稱"
                )
            if "參考文件" in missing:
                suggestions.append(
                    "【C2 補充建議】新增「### 參考文件」章節，連結需求規格"
                )

    # C3 修正建議
    if c3_result["is_ambiguous"]:
        for missing in c3_result["missing_elements"]:
            if "層級標示" in missing:
                suggestions.append(
                    "【C3 修正建議】在標題加上 [Layer X] 標籤"
                )
            if "職責描述" in missing:
                suggestions.append(
                    "【C3 修正建議】重寫目標章節，明確說明職責範圍和邊界"
                )
            if "檔案範圍" in missing:
                suggestions.append(
                    "【C3 修正建議】在步驟中列出具體檔案路徑"
                )
            if "驗收條件" in missing:
                suggestions.append(
                    "【C3 修正建議】驗收條件限定在該層級，移除跨層級驗收項目"
                )

    return suggestions
```

#### 檢測報告格式

**文字報告格式**:

```text
=== Ticket 品質閘門檢測報告 ===

Ticket: docs/work-logs/v0.12.8-book-repository-interface.md
檢測時間: 2025-10-11 21:50

【C1. God Ticket 檢測】
  檔案數量: 3 個 ✅
  層級跨度: 1 層 ✅
  預估工時: 4 小時 ✅
  結論: 通過 ✅

【C3. Ambiguous Responsibility 檢測】
  層級標示: [Layer 5] ✅
  職責描述: 明確（45 字） ✅
  檔案範圍: 明確（3 個檔案） ✅
  驗收限定: 限定在 Layer 5 ✅
  結論: 通過 ✅

【C2. Incomplete Ticket 檢測】
  驗收條件: 6 個項目 ✅
  測試規劃: 明確（1 個測試檔案） ✅
  工作日誌: 明確 ✅
  參考文件: 3 個連結 ✅
  結論: 通過 ✅

【最終結論】
✅ 通過品質閘門檢測，可進入 Phase 2

==========================================
```

**JSON 報告格式** (供後續分析使用):

```json
{
  "ticket_path": "docs/work-logs/v0.12.8-book-repository-interface.md",
  "detection_time": "2025-10-11T21:50:00",
  "passed": true,
  "c1_result": {
    "file_count": 3,
    "layer_span": 1,
    "estimated_hours": 4,
    "is_god_ticket": false,
    "confidence": 0.9,
    "reasons": []
  },
  "c2_result": {
    "has_acceptance_criteria": true,
    "acceptance_count": 6,
    "has_test_plan": true,
    "test_files": ["test/domain/repositories/book_repository_test.dart"],
    "has_work_log": true,
    "work_log_file": "docs/work-logs/v0.12.8-book-repository-interface.md",
    "has_references": true,
    "reference_count": 3,
    "is_incomplete": false,
    "missing_elements": []
  },
  "c3_result": {
    "has_layer_tag": true,
    "layer_number": 5,
    "has_clear_responsibility": true,
    "responsibility_length": 45,
    "has_file_paths": true,
    "file_count": 3,
    "acceptance_limited_to_layer": true,
    "is_ambiguous": false,
    "confidence": 0.7,
    "missing_elements": []
  },
  "suggestions": [],
  "blocking_issues": []
}
```

#### v0.12.G.4 實作準備清單

為了完整實作自動化檢測工具,需要完成以下準備工作:

- [ ] **基礎函式庫**:
  - [ ] 實作檔案路徑提取函式 (`extract_file_paths`)
  - [ ] 實作層級判斷函式 (`determine_layer`)
  - [ ] 實作章節提取函式 (`extract_section`)
  - [ ] 實作步驟數量計算函式 (`count_steps`)
  - [ ] 實作工時估算函式 (`estimate_hours_by_steps`)

- [ ] **C1 檢測函式**:
  - [ ] 實作 `check_god_ticket_automated` 主函式
  - [ ] 實作檔案數量計算邏輯
  - [ ] 實作層級跨度判斷邏輯
  - [ ] 實作預估工時計算邏輯

- [ ] **C2 檢測函式**:
  - [ ] 實作 `check_incomplete_ticket_automated` 主函式
  - [ ] 實作驗收條件檢查函式 (`has_section`, `count_acceptance_items`)
  - [ ] 實作測試規劃檢查函式 (`has_test_keywords`, `extract_test_files`)
  - [ ] 實作工作日誌檢查函式
  - [ ] 實作參考文件檢查函式 (`count_references`)

- [ ] **C3 檢測函式**:
  - [ ] 實作 `check_ambiguous_responsibility_automated` 主函式
  - [ ] 實作層級標示提取函式 (`extract_layer_tag`)
  - [ ] 實作職責描述提取函式 (`extract_responsibility`)
  - [ ] 實作驗收條件層級判斷函式 (`determine_layer_from_acceptance`)

- [ ] **Hook 整合**:
  - [ ] 實作 `ticket_quality_gate_hook` 主函式
  - [ ] 實作修正建議生成器 (`generate_suggestions`)
  - [ ] 實作檢測報告生成器 (文字和 JSON 格式)
  - [ ] 實作檢測結果日誌機制 (`log_detection_result`)
  - [ ] 配置 Hook 到 `.claude/settings.local.json`

- [ ] **測試與驗證**:
  - [ ] 撰寫單元測試（模擬 Ticket 檔案）
  - [ ] 測試 C1/C2/C3 檢測函式的正確性
  - [ ] 測試 Hook 整合和觸發機制
  - [ ] 驗證檢測報告格式和內容

---

## 第六章：品質閘門決策矩陣

### 6.1 決策矩陣設計原理

**三維檢測體系**:

品質閘門採用三維檢測體系，每個維度對應一個 Code Smell 類型：

```text
決策矩陣三維體系：

維度 1: C1 - God Ticket（複雜度警告）
    ├─ 檔案數量檢測
    ├─ 層級跨度檢測
    └─ 預估工時檢測

維度 2: C2 - Incomplete Ticket（架構完整性）
    ├─ 驗收條件檢測
    ├─ 測試規劃檢測
    ├─ 工作日誌檢測
    └─ 參考文件檢測

維度 3: C3 - Ambiguous Responsibility（責任明確性）
    ├─ 層級標示檢測
    ├─ 職責描述檢測
    ├─ 檔案範圍檢測
    └─ 驗收限定檢測
```

**判定級別定義**:

品質閘門使用三級判定機制：

| 判定級別 | 符號 | 定義 | 後續行動 |
|---------|-----|------|---------|
| **通過 (Pass)** | ✅ | 所有檢測項目符合標準 | 繼續下一個檢測或提交審查 |
| **警告 (Warning)** | ⚠️ | 檢測項目接近閾值，建議優化 | 可繼續執行，但建議改善 |
| **阻止 (Block)** | ❌ | 檢測項目不符合標準 | 強制修正，阻止進入 Phase 2 |

**決策矩陣邏輯**:

```text
決策流程（針對單一 Ticket）：

【檢測 1】C1 檢測
  ├─ 通過 ✅ → 繼續【檢測 2】
  ├─ 警告 ⚠️ → 記錄警告，繼續【檢測 2】
  └─ 阻止 ❌ → 執行拆分修正，重新檢測

【檢測 2】C3 檢測
  ├─ 通過 ✅ → 繼續【檢測 3】
  └─ 阻止 ❌ → 重新定義職責，重新檢測

【檢測 3】C2 檢測
  ├─ 通過 ✅ → 標記 Ticket 為「通過品質閘門」
  └─ 阻止 ❌ → 補充遺漏項目，重新檢測

所有檢測通過
  ↓
提交給 PM 審查
  ↓
分派給開發者執行（進入 Phase 2）
```

**檢測順序原則**:

品質閘門按照 **C1 → C3 → C2** 的順序執行，原因如下：

| 執行順序 | 檢測項目 | 原因 |
|---------|---------|------|
| **第一順位：C1** | God Ticket 檢測 | 複雜度問題必須先解決，避免後續檢測浪費時間 |
| **第二順位：C3** | Ambiguous Responsibility 檢測 | 職責明確後才能判斷完整性要求 |
| **第三順位：C2** | Incomplete Ticket 檢測 | 完整性檢測依賴明確的職責定義 |

### 6.2 判定規則詳細規範

#### 6.2.1 C1 God Ticket 判定規則

**三項指標判定標準**:

| 指標 | 通過 ✅ | 警告 ⚠️ | 阻止 ❌ |
|------|--------|--------|--------|
| **檔案數量** | 1-3 個 | 4-6 個 | > 10 個 |
| **層級跨度** | 1 層 | 2 層 | > 2 層 |
| **預估工時** | 2-4 小時 | 4-8 小時 | > 16 小時 |

**組合判定邏輯**:

```python
def judge_c1_god_ticket(file_count, layer_span, estimated_hours):
    """
    C1 判定邏輯：任一項目超過「阻止」閾值 → 阻止 ❌

    回傳: ("pass" | "warning" | "block", reasons)
    """
    reasons = []

    # 檢查是否有任何項目超過「阻止」閾值
    if file_count > 10:
        return ("block", ["檔案數量超標: {file_count} > 10"])
    if layer_span > 2:
        return ("block", ["層級跨度超標: {layer_span} > 2"])
    if estimated_hours > 16:
        return ("block", ["預估工時超標: {estimated_hours}h > 16h"])

    # 檢查是否有任何項目在「警告」範圍
    if 4 <= file_count <= 6:
        reasons.append(f"檔案數量接近上限: {file_count} 個")
    if layer_span == 2:
        reasons.append(f"層級跨度達到上限: {layer_span} 層")
    if 4 <= estimated_hours <= 8:
        reasons.append(f"預估工時接近上限: {estimated_hours}h")

    # 如果有警告項目，回傳警告
    if reasons:
        return ("warning", reasons)

    # 所有項目都在「通過」範圍
    return ("pass", [])
```

**判定範例**:

```text
範例 1: 阻止 ❌
- 檔案數量: 8 個（未超標）
- 層級跨度: 3 層（超標）
- 預估工時: 12 小時（未超標）
→ 判定: 阻止 ❌（任一超標即阻止）
→ 原因: 層級跨度超標: 3 > 2

範例 2: 警告 ⚠️
- 檔案數量: 5 個（警告範圍）
- 層級跨度: 2 層（警告範圍）
- 預估工時: 6 小時（警告範圍）
→ 判定: 警告 ⚠️
→ 原因: 檔案數量、層級跨度、工時均接近上限

範例 3: 通過 ✅
- 檔案數量: 2 個
- 層級跨度: 1 層
- 預估工時: 4 小時
→ 判定: 通過 ✅
```

#### 6.2.2 C2 Incomplete Ticket 判定規則

**四要素必要性檢測**:

| 要素 | 通過 ✅ | 阻止 ❌ |
|------|--------|--------|
| **驗收條件** | 存在且 ≥ 3 個 | 缺失或 < 3 個 |
| **測試規劃** | 明確列出測試檔案和項目 | 缺失或不明確 |
| **工作日誌規劃** | 明確檔案名稱和記錄內容 | 缺失 |
| **參考文件** | 至少 1 個有效連結 | 缺失 |

**判定邏輯**:

```python
def judge_c2_incomplete_ticket(
    has_acceptance, acceptance_count,
    has_test_plan,
    has_work_log,
    has_references, reference_count
):
    """
    C2 判定邏輯：任一要素缺失 → 阻止 ❌

    C2 採用二元判定（只有通過/阻止，沒有警告）

    回傳: ("pass" | "block", missing_elements)
    """
    missing_elements = []

    # 檢查驗收條件
    if not has_acceptance:
        missing_elements.append("缺少「驗收條件」章節")
    elif acceptance_count < 3:
        missing_elements.append(f"驗收條件不足: {acceptance_count} < 3")

    # 檢查測試規劃
    if not has_test_plan:
        missing_elements.append("缺少測試規劃（步驟中無測試相關內容）")

    # 檢查工作日誌
    if not has_work_log:
        missing_elements.append("缺少工作日誌規劃")

    # 檢查參考文件
    if not has_references:
        missing_elements.append("缺少參考文件章節")
    elif reference_count == 0:
        missing_elements.append("參考文件章節為空")

    # 如果有任何缺失，回傳阻止
    if missing_elements:
        return ("block", missing_elements)

    # 所有要素完整
    return ("pass", [])
```

**判定範例**:

```text
範例 1: 阻止 ❌（多項缺失）
- 驗收條件: 缺失
- 測試規劃: 存在
- 工作日誌: 缺失
- 參考文件: 存在
→ 判定: 阻止 ❌
→ 原因:
  - 缺少「驗收條件」章節
  - 缺少工作日誌規劃

範例 2: 阻止 ❌（驗收條件不足）
- 驗收條件: 存在但只有 2 個
- 測試規劃: 存在
- 工作日誌: 存在
- 參考文件: 存在
→ 判定: 阻止 ❌
→ 原因: 驗收條件不足: 2 < 3

範例 3: 通過 ✅
- 驗收條件: 存在且有 5 個
- 測試規劃: 存在
- 工作日誌: 存在
- 參考文件: 存在（2 個連結）
→ 判定: 通過 ✅
```

#### 6.2.3 C3 Ambiguous Responsibility 判定規則

**四要素明確性檢測**:

| 要素 | 通過 ✅ | 阻止 ❌ |
|------|--------|--------|
| **層級標示** | 標題包含 `[Layer X]` | 標題缺少層級標示 |
| **職責描述** | 目標章節明確定義單一職責 | 職責模糊或跨層級 |
| **檔案範圍** | 步驟章節明確列出檔案路徑 | 檔案範圍籠統或模糊 |
| **驗收限定** | 驗收條件限定在該層級 | 驗收條件跨層級 |

**判定邏輯**:

```python
def judge_c3_ambiguous_responsibility(
    has_layer_tag,
    has_clear_responsibility,
    has_specific_files,
    acceptance_limited_to_layer
):
    """
    C3 判定邏輯：任一要素不明確 → 阻止 ❌

    C3 採用二元判定（只有通過/阻止，沒有警告）

    回傳: ("pass" | "block", ambiguous_elements)
    """
    ambiguous_elements = []

    # 檢查層級標示
    if not has_layer_tag:
        ambiguous_elements.append("標題缺少 [Layer X] 層級標示")

    # 檢查職責描述
    if not has_clear_responsibility:
        ambiguous_elements.append("目標章節職責定義不明確")

    # 檢查檔案範圍
    if not has_specific_files:
        ambiguous_elements.append("步驟章節檔案範圍模糊（如「相關檔案」）")

    # 檢查驗收限定
    if not acceptance_limited_to_layer:
        ambiguous_elements.append("驗收條件未限定在單一層級")

    # 如果有任何不明確，回傳阻止
    if ambiguous_elements:
        return ("block", ambiguous_elements)

    # 所有要素明確
    return ("pass", [])
```

**判定範例**:

```text
範例 1: 阻止 ❌（缺少層級標示）
- 層級標示: 缺失
- 職責描述: 明確
- 檔案範圍: 明確
- 驗收限定: 符合
→ 判定: 阻止 ❌
→ 原因: 標題缺少 [Layer X] 層級標示

範例 2: 阻止 ❌（多項不明確）
- 層級標示: 存在 [Layer 2]
- 職責描述: 模糊（「實作書籍詳情功能」）
- 檔案範圍: 模糊（「修改相關檔案」）
- 驗收限定: 跨層級（包含 UI 和資料驗收）
→ 判定: 阻止 ❌
→ 原因:
  - 目標章節職責定義不明確
  - 步驟章節檔案範圍模糊
  - 驗收條件未限定在單一層級

範例 3: 通過 ✅
- 層級標示: [Layer 2]
- 職責描述: 明確（實作 BookDetailController.loadBookDetail 方法）
- 檔案範圍: 明確（lib/presentation/controllers/book_detail_controller.dart）
- 驗收限定: 限定在 Layer 2（Controller 層）
→ 判定: 通過 ✅
```

### 6.3 組合決策流程與阻斷機制

#### 6.3.1 完整決策流程

**Ticket 品質閘門完整檢測流程**:

```text
【開始】Ticket 設計完成
  ↓
【檢測 1】C1. God Ticket 檢測
  ├─ 檢測項目:
  │   ├─ 檔案數量
  │   ├─ 層級跨度
  │   └─ 預估工時
  │
  ├─ 判定結果:
  │   ├─ 通過 ✅ → 繼續【檢測 2】
  │   ├─ 警告 ⚠️ → 記錄警告，繼續【檢測 2】
  │   └─ 阻止 ❌ → 執行拆分修正
  │                 ├─ 按層級拆分
  │                 ├─ 按職責拆分
  │                 └─ 按 TDD 階段拆分
  │                 ↓
  │                 重新執行【檢測 1】
  ↓
【檢測 2】C3. Ambiguous Responsibility 檢測
  ├─ 檢測項目:
  │   ├─ 層級標示
  │   ├─ 職責描述
  │   ├─ 檔案範圍
  │   └─ 驗收限定
  │
  ├─ 判定結果:
  │   ├─ 通過 ✅ → 繼續【檢測 3】
  │   └─ 阻止 ❌ → 重新定義職責
  │                 ├─ 加入層級標示
  │                 ├─ 重寫目標章節
  │                 ├─ 明確檔案範圍
  │                 └─ 限定驗收條件
  │                 ↓
  │                 重新執行【檢測 2】
  ↓
【檢測 3】C2. Incomplete Ticket 檢測
  ├─ 檢測項目:
  │   ├─ 驗收條件
  │   ├─ 測試規劃
  │   ├─ 工作日誌
  │   └─ 參考文件
  │
  ├─ 判定結果:
  │   ├─ 通過 ✅ → 繼續【提交審查】
  │   └─ 阻止 ❌ → 補充遺漏項目
  │                 ├─ 補充驗收條件
  │                 ├─ 補充測試規劃
  │                 ├─ 補充工作日誌規劃
  │                 └─ 補充參考文件連結
  │                 ↓
  │                 重新執行【檢測 3】
  ↓
【提交審查】所有 Ticket 檢測完成
  ├─ 所有 Ticket 都通過 C1/C2/C3？
  │   ├─ Yes ✅ → 提交給 PM 審查
  │   └─ No ❌  → 修正未通過的 Ticket
  │                ↓
  │                重新執行對應檢測
  ↓
【PM 審查】檢查品質閘門報告
  ├─ 檢查項目:
  │   ├─ 報告完整性
  │   ├─ 檢測結果正確性
  │   ├─ 修正記錄完整性
  │   ├─ Ticket 數量合理性
  │   └─ 依賴關係正確性
  │
  ├─ 審查結果:
  │   ├─ 批准 ✅ → 分派給開發者執行（進入 Phase 2）
  │   └─ 拒絕 ❌ → 要求重新設計或調整
  │                 ↓
  │                 lavender 修正後重新提交
  ↓
【結束】品質閘門通過，開始實作
```

#### 6.3.2 阻斷機制詳細說明

**強制阻斷原則**:

| 阻斷條件 | 阻斷時機 | 解除條件 |
|---------|---------|---------|
| **C1 阻止判定** | 任一指標超過閾值（> 10 個檔案 / > 2 層 / > 16h） | Ticket 拆分後重新檢測通過 |
| **C2 阻止判定** | 任一要素缺失（驗收條件/測試/工作日誌/參考文件） | 補充遺漏項目後重新檢測通過 |
| **C3 阻止判定** | 任一要素不明確（層級/職責/檔案/驗收） | 重新定義職責後重新檢測通過 |
| **PM 拒絕** | PM 審查發現問題（報告不完整/結果不正確/數量不合理） | 根據 PM 要求修正後重新提交 |

**阻斷處理流程**:

```text
檢測失敗（阻止 ❌）
  ↓
【步驟 1】記錄失敗原因到工作日誌
  - 記錄檢測項目
  - 記錄失敗原因
  - 記錄時間戳記
  ↓
【步驟 2】根據失敗類型選擇修正方法
  ├─ C1 失敗 → 執行 Ticket 拆分
  │             ├─ 按層級拆分（優先）
  │             ├─ 按職責拆分（次要）
  │             └─ 按 TDD 階段拆分（特殊）
  │
  ├─ C3 失敗 → 重新定義職責
  │             ├─ 確認主要職責層級
  │             ├─ 加入層級標示 [Layer X]
  │             ├─ 限定職責範圍
  │             └─ 明確列出檔案
  │
  └─ C2 失敗 → 補充遺漏項目
                ├─ 補充驗收條件
                ├─ 補充測試規劃
                ├─ 補充工作日誌規劃
                └─ 補充參考文件連結
  ↓
【步驟 3】修正完成，記錄修正內容
  - 記錄修正方法
  - 記錄修正前後對比
  - 記錄決策理由
  ↓
【步驟 4】重新執行失敗的檢測項目
  ├─ 通過 ✅ → 繼續下一個檢測
  └─ 失敗 ❌ → 再次修正（回到步驟 1）
```

#### 6.3.3 警告處理機制

**警告級別處理原則**:

C1 檢測中的「警告 ⚠️」級別處理方式：

```text
【警告處理】C1 警告判定
  ├─ 不阻止進入 Phase 2
  ├─ 建議優化但不強制
  └─ 記錄警告到工作日誌
      ↓
【建議行動】
  - 警告 1: 檔案數量 4-6 個 → 建議檢查是否可進一步拆分
  - 警告 2: 層級跨度 2 層 → 建議檢查是否符合「單層修改原則」
  - 警告 3: 預估工時 4-8 小時 → 建議檢查步驟是否過於複雜
      ↓
【工作日誌記錄範例】
  **C1 檢測結果**: 警告 ⚠️
  - 檔案數量: 5 個（接近上限）
  - 層級跨度: 2 層（達到上限）
  - 預估工時: 6 小時

  **建議**:
  - 考慮是否可進一步拆分為兩個 Ticket
  - 如決定不拆分，需說明理由

  **決策**: 不拆分
  **理由**: 這 5 個檔案都屬於同一個 Feature，必須一起修改才能確保一致性
      ↓
【繼續執行】繼續 C3 檢測
```

**警告級別價值**:

| 價值 | 說明 |
|------|------|
| **提供彈性** | 不是所有「接近閾值」的情況都需要拆分 |
| **鼓勵思考** | 提醒設計者思考是否可以優化 |
| **保留決策權** | 設計者可以根據實際情況判斷是否拆分 |
| **記錄依據** | 要求設計者說明不拆分的理由 |

---

## 第七章：實務案例與最佳實踐

### 7.1 完整案例：書籍查詢功能品質閘門檢測

**案例背景**:

v0.12.8 版本需要實作書籍查詢功能。設計階段建立了 2 個 Ticket：
- Ticket #1: [Layer 5] 定義 Book Entity
- Ticket #2: [Layer 3/5] 實作書籍查詢功能（原始設計）

以下展示完整的品質閘門檢測流程和修正過程。

---

#### 案例 1: 標準 Ticket 檢測（Ticket #1）

**Ticket 標題**: [Layer 5] 定義 Book Entity

**檢測時間**: 2025-10-11

**C1. God Ticket 檢測**:
```text
【檢測項目】
檔案數量: 2 個（book.dart + isbn.dart）
層級跨度: 1 層（Layer 5）
預估工時: 4 小時

【判定邏輯】
- 檔案數量: 2 個 < 10 個 → 通過 ✅
- 層級跨度: 1 層 ≤ 2 層 → 通過 ✅
- 預估工時: 4h < 16h → 通過 ✅

【檢測結論】
C1 檢測結果: 通過 ✅
```

**C3. Ambiguous Responsibility 檢測**:
```text
【檢測項目】
層級標示: [Layer 5] 存在 ✅
職責描述: 「定義 Book Entity 和 ISBN Value Object」明確 ✅
檔案範圍: 明確列出 2 個檔案路徑 ✅
驗收限定: 限定在 Domain 層（Layer 5）✅

【判定邏輯】
- 層級標示: 存在 [Layer 5] → 通過 ✅
- 職責描述: 單一且明確 → 通過 ✅
- 檔案範圍: 具體路徑明確 → 通過 ✅
- 驗收限定: 限定在單一層級 → 通過 ✅

【檢測結論】
C3 檢測結果: 通過 ✅
```

**C2. Incomplete Ticket 檢測**:
```text
【檢測項目】
驗收條件: 6 個驗收項目 ✅
測試規劃: 包含測試步驟和覆蓋率要求 ✅
工作日誌: 規劃檔案名稱（v0.12.8-ticket-001.md）✅
參考文件: 連結需求規格和設計文件 ✅

【判定邏輯】
- 驗收條件: 6 個 ≥ 3 個 → 通過 ✅
- 測試規劃: 明確測試檔案和項目 → 通過 ✅
- 工作日誌: 明確檔案名稱 → 通過 ✅
- 參考文件: 2 個連結 ≥ 1 個 → 通過 ✅

【檢測結論】
C2 檢測結果: 通過 ✅
```

**最終結論**:
- Ticket #1 通過品質閘門 ✅
- 可分派給開發者執行

---

#### 案例 2: God Ticket 檢測與拆分（Ticket #2）

**Ticket 標題（原始）**: [Layer 3/5] 實作書籍查詢功能

**檢測時間**: 2025-10-11

**C1. God Ticket 檢測（第一次）**:
```text
【檢測項目】
檔案數量: 15 個
層級跨度: 3 層（跨 Layer 1/2/3/5）
預估工時: 24 小時

【判定邏輯】
- 檔案數量: 15 > 10 → 阻止 ❌
- 層級跨度: 3 > 2 → 阻止 ❌
- 預估工時: 24h > 16h → 阻止 ❌

【檢測結論】
C1 檢測結果: 阻止 ❌（3 個指標都超標）
```

**修正行動：按層級拆分**

根據 C1 檢測失敗，執行拆分修正：

**拆分策略**: 按 Clean Architecture 層級拆分為 4 個 Ticket

```text
原始 Ticket #2
  ↓
【拆分策略】按層級拆分
  ↓
Ticket #2a: [Layer 5] 定義 Book Entity（2 個檔案、4h）
Ticket #2b: [Layer 3] 實作 GetBookUseCase（3 個檔案、6h）
Ticket #2c: [Layer 2] 實作 BookController（2 個檔案、4h）
Ticket #2d: [Layer 1] 實作 BookListWidget（3 個檔案、5h）
  ↓
【拆分結果】
總檔案數: 10 個（原 15 個）
層級跨度: 4 個 Ticket 各為 1 層
總工時: 19 小時（4+6+4+5）
```

**拆分後重新檢測**:

**Ticket #2a 檢測**:
```text
C1: 通過 ✅（2 個檔案、1 層、4h）
C3: 通過 ✅（職責明確：定義 Domain Entity）
C2: 通過 ✅（4 項必要元素齊全）
```

**Ticket #2b 檢測**:
```text
C1: 通過 ✅（3 個檔案、1 層、6h）
C3: 通過 ✅（職責明確：實作業務邏輯）
C2: 通過 ✅（4 項必要元素齊全）
```

**Ticket #2c 檢測**:
```text
C1: 通過 ✅（2 個檔案、1 層、4h）
C3: 通過 ✅（職責明確：實作事件處理）
C2: 通過 ✅（4 項必要元素齊全）
```

**Ticket #2d 檢測**:
```text
C1: 通過 ✅（3 個檔案、1 層、5h）
C3: 通過 ✅（職責明確：實作 UI 元件）
C2: 通過 ✅（4 項必要元素齊全）
```

**最終結論**:
- 原 Ticket #2 拆分為 4 個 Ticket
- 所有拆分後 Ticket 都通過品質閘門 ✅
- 可分派給開發者執行

---

#### PM 審查報告

**審查日期**: 2025-10-11
**審查 Ticket 清單**: v0.12.8 書籍查詢功能（5 個 Ticket）

**品質閘門檢測確認**:
- ✅ Ticket #1: 通過 C1/C2/C3 檢測
- ✅ Ticket #2a: 通過 C1/C2/C3 檢測（拆分後）
- ✅ Ticket #2b: 通過 C1/C2/C3 檢測（拆分後）
- ✅ Ticket #2c: 通過 C1/C2/C3 檢測（拆分後）
- ✅ Ticket #2d: 通過 C1/C2/C3 檢測（拆分後）

**拆分合理性評估**:
```text
原 Ticket 數量: 2 個（1 個正常 + 1 個 God Ticket）
拆分後數量: 5 個
評估: 合理 ✅

理由:
- God Ticket 按層級拆分為 4 個
- 符合「單層修改原則」
- 每個 Ticket 職責單一明確
- Ticket 數量在合理範圍（< 10 個）
```

**依賴關係檢查**:
```text
依賴順序: Ticket #1 → #2a → #2b → #2c → #2d
評估: 正確 ✅

理由:
- 遵循架構層級順序（L5 → L3 → L2 → L1）
- 符合依賴規則（外層依賴內層）
- 可並行開發（#1 和 #2a 相同層級，可同時進行）
```

**審查結論**:
- ✅ 批准 Ticket 清單
- ✅ 可分派給開發者執行（進入 Phase 2）

---

### 7.2 品質閘門最佳實踐

基於實務案例和方法論完整執行經驗，總結以下最佳實踐：

#### 實踐 1: 設計階段強制檢測

**原則**: 所有 Ticket 必須在 Phase 1（設計階段）完成品質閘門檢測

**為什麼重要**:
```text
設計階段檢測 vs 實作後檢測

修正成本對比：
- 設計階段修正: 5-10 分鐘（重新設計 Ticket）
- 實作後修正: 2-4 小時（重構已完成程式碼）
- 成本比: 1:20（80% 成本節省）

品質影響對比：
- 設計階段: 架構清晰，職責明確
- 實作後: 架構債務累積，重構風險高
```

**執行方法**:
1. lavender-interface-designer 設計 Ticket 後立即執行 C1/C2/C3 檢測
2. 任何檢測失敗必須立即修正，不延後到實作階段
3. PM 審查時確認所有 Ticket 都有品質閘門檢測記錄

#### 實踐 2: C1 → C3 → C2 檢測順序

**原則**: 按照 C1 → C3 → C2 的順序執行檢測

**為什麼這個順序**:
```text
檢測順序的邏輯依賴：

C1 檢測失敗 → 必須拆分 Ticket
  ↓ (拆分後職責可能變化)
C3 檢測失敗 → 重新定義職責
  ↓ (職責明確後才能確定需要哪些要素)
C2 檢測失敗 → 補充遺漏項目
  ↓
所有檢測通過
```

**錯誤範例**:
```text
❌ 錯誤順序: C2 → C1 → C3

問題:
1. 先執行 C2，補充驗收條件和測試規劃
2. 後執行 C1，發現 God Ticket 需要拆分
3. 拆分後之前補充的驗收條件和測試規劃都失效
4. 需要重新執行 C2 → 浪費時間

✅ 正確順序: C1 → C3 → C2

好處:
1. C1 先拆分，確保 Ticket 規模合理
2. C3 重新定義職責，確保職責明確
3. C2 最後補充要素，一次到位
```

#### 實踐 3: 警告級別彈性處理

**原則**: C1 警告級別不阻止進入 Phase 2，但需要記錄決策理由

**為什麼需要彈性**:
```text
警告級別存在的原因：

並非所有「接近閾值」的情況都需要拆分

範例 1：Feature 一致性
- 5 個檔案都屬於同一個 UI 元件
- 拆分會破壞一致性
- 決策：保持不拆分 ✅

範例 2：技術限制
- 2 層修改是最小可行方案
- 無法進一步拆分
- 決策：保持 2 層 ✅

範例 3：效率考量
- 6 小時工時剛好符合開發者工作節奏
- 拆分反而降低效率
- 決策：保持不拆分 ✅
```

**執行方法**:
1. C1 檢測產生警告時，不阻止進入 Phase 2
2. 要求設計者說明「為什麼不拆分」的理由
3. 理由記錄到工作日誌（可追溯決策）
4. PM 審查時確認理由合理

#### 實踐 4: 自動化檢測優先，人工檢測補充

**原則**: 能自動化的檢測項目使用 Hook 系統，人工只判斷自動化無法處理的項目

**自動化檢測項目**（信心度 ≥ 90%）:
```text
C1 檢測：
- ✅ 檔案數量（100% 自動化）
- ✅ 層級跨度（100% 自動化）
- ⚠️ 預估工時（60% 自動化，需人工確認複雜度）

C2 檢測：
- ✅ 驗收條件存在性（100% 自動化）
- ✅ 驗收條件數量（100% 自動化）
- ✅ 測試規劃存在性（80% 自動化）
- ✅ 工作日誌規劃（100% 自動化）
- ✅ 參考文件存在性（100% 自動化）

C3 檢測：
- ✅ 層級標示存在性（100% 自動化）
- ⚠️ 職責描述明確性（50% 自動化，需人工判斷）
- ✅ 檔案範圍具體性（100% 自動化）
- ⚠️ 驗收限定正確性（70% 自動化，需人工確認）
```

**執行方法**:
1. 配置 PostEdit Hook 在 Ticket 檔案儲存時自動執行檢測
2. Hook 產生檢測報告（文字 + JSON 格式）
3. 人工只檢查自動化信心度 < 90% 的項目
4. 自動化檢測結果記錄到工作日誌

#### 實踐 5: 完整檢測記錄可追溯

**原則**: 所有檢測過程和修正過程都記錄到工作日誌

**記錄範例**:
```markdown
## Code Smell 品質閘門檢測

### Ticket #2: [Layer 3/5] 實作書籍查詢功能

#### 檢測記錄（2025-10-11 10:30）

**C1. God Ticket 檢測（第一次）**:
- 檔案數量: 15 個 ❌（超標）
- 層級跨度: 3 層 ❌（超標）
- 預估工時: 24 小時 ❌（超標）
- 結論: 失敗 ❌

#### 修正記錄（2025-10-11 10:45）

**修正方法**: 按層級拆分為 4 個 Ticket
- Ticket #2a: [Layer 5] 定義 Book Entity
- Ticket #2b: [Layer 3] 實作 GetBookUseCase
- Ticket #2c: [Layer 2] 實作 BookController
- Ticket #2d: [Layer 1] 實作 BookListWidget

**拆分理由**:
原始 Ticket 跨越 3 個層級（L5/L3/L2/L1），違反「單層修改原則」
按層級拆分可確保每個 Ticket 職責單一且層級明確

#### 檢測記錄（2025-10-11 11:00）

**Ticket #2a-2d 重新檢測**:
- ✅ Ticket #2a: 通過 C1/C2/C3 檢測
- ✅ Ticket #2b: 通過 C1/C2/C3 檢測
- ✅ Ticket #2c: 通過 C1/C2/C3 檢測
- ✅ Ticket #2d: 通過 C1/C2/C3 檢測

**最終結論**: 拆分成功，所有 Ticket 通過品質閘門 ✅
```

**記錄價值**:
1. **可追溯性**: 清楚記錄修正過程和決策理由
2. **學習價值**: 團隊可以從修正過程學習最佳實踐
3. **審查依據**: PM 審查時有完整的檢測記錄
4. **改善依據**: 分析檢測失敗模式，持續改善設計品質

#### 實踐 6: PM 審查聚焦品質閘門報告

**原則**: PM 審查時優先檢查品質閘門報告，確保檢測標準執行

**PM 審查清單**:
```text
【檢查 1】報告完整性
- [ ] 所有 Ticket 都有 C1/C2/C3 檢測記錄
- [ ] 檢測時間合理（在設計完成後立即執行）
- [ ] 檢測結果格式正確

【檢查 2】檢測結果正確性
- [ ] 所有 Ticket 都標記為「通過 ✅」
- [ ] 如有失敗記錄，必須有修正過程
- [ ] 修正後必須重新檢測並通過

【檢查 3】修正記錄完整性
- [ ] 檢測失敗的 Ticket 是否記錄修正過程
- [ ] 修正方法是否合理（拆分/補充/重新定義）
- [ ] 修正理由是否充分

【檢查 4】Ticket 數量合理性
- [ ] 拆分後 Ticket 數量在 1-10 個範圍
- [ ] 無過度拆分（< 1 個）
- [ ] 無過度合併（> 10 個）

【檢查 5】依賴關係正確性
- [ ] Ticket 依賴順序符合架構層級
- [ ] 依賴關係明確標示
- [ ] 無循環依賴
```

**審查決策**:
- 所有檢查通過 → 批准 Ticket 清單，分派給開發者
- 任一檢查失敗 → 要求 lavender 修正後重新提交

---

## 附錄

### 附錄 A：術語表

**品質閘門 (Quality Gate)**:
設計階段的品質檢測機制，在 Ticket 分派給開發者前執行，確保 Ticket 設計品質符合標準。

**God Ticket**:
單一 Ticket 修改過多檔案和層級，範圍失控，違反「單層修改原則」的 Ticket。

**Incomplete Ticket**:
Ticket 內容缺失關鍵元素（驗收條件/測試規劃/工作日誌/參考文件），導致開發者無法明確理解需求或驗收標準的 Ticket。

**Ambiguous Responsibility**:
Ticket 的職責定義不明確，無法判斷屬於哪一層級，違反「層級明確原則」的 Ticket。

**C1 檢測**:
複雜度警告檢測，檢查 Ticket 是否為 God Ticket（檔案數量/層級跨度/預估工時）。

**C2 檢測**:
架構完整性檢測，檢查 Ticket 是否缺失必要元素（驗收條件/測試規劃/工作日誌/參考文件）。

**C3 檢測**:
責任明確性檢測，檢查 Ticket 是否職責明確（層級標示/職責描述/檔案範圍/驗收限定）。

**通過 (Pass)**:
所有檢測項目符合標準，可繼續下一個檢測或提交審查。

**警告 (Warning)**:
檢測項目接近閾值，建議優化但不強制，可繼續執行。

**阻止 (Block)**:
檢測項目不符合標準，強制修正，阻止進入 Phase 2。

**單層修改原則**:
每個 Ticket 只修改單一層級（Layer）的檔案，避免跨層級修改導致職責混亂。

**層級標示**:
Ticket 標題中的 `[Layer X]` 標籤，明確標示 Ticket 屬於哪個架構層級。

**Clean Architecture 五層架構**:
- Layer 1: Presentation（UI）
- Layer 2: Behavior（Controller/Provider）
- Layer 3: Use Case（業務邏輯）
- Layer 4: Domain Events/Interfaces
- Layer 5: Domain（Entity/Repository）

---

### 附錄 B：檢測標準速查表

#### C1 God Ticket 檢測標準

| 指標 | 通過 ✅ | 警告 ⚠️ | 阻止 ❌ |
|------|--------|--------|--------|
| **檔案數量** | 1-3 個 | 4-6 個 | > 10 個 |
| **層級跨度** | 1 層 | 2 層 | > 2 層 |
| **預估工時** | 2-4h | 4-8h | > 16h |

**判定邏輯**: 任一指標超過「阻止」閾值 → 阻止 ❌

---

#### C2 Incomplete Ticket 檢測標準

| 要素 | 通過 ✅ | 阻止 ❌ |
|------|--------|--------|
| **驗收條件** | 存在且 ≥ 3 個 | 缺失或 < 3 個 |
| **測試規劃** | 明確列出測試檔案和項目 | 缺失或不明確 |
| **工作日誌規劃** | 明確檔案名稱和記錄內容 | 缺失 |
| **參考文件** | 至少 1 個有效連結 | 缺失 |

**判定邏輯**: 任一要素缺失 → 阻止 ❌

---

#### C3 Ambiguous Responsibility 檢測標準

| 要素 | 通過 ✅ | 阻止 ❌ |
|------|--------|--------|
| **層級標示** | 標題包含 `[Layer X]` | 標題缺少層級標示 |
| **職責描述** | 目標章節明確定義單一職責 | 職責模糊或跨層級 |
| **檔案範圍** | 步驟章節明確列出檔案路徑 | 檔案範圍籠統或模糊 |
| **驗收限定** | 驗收條件限定在該層級 | 驗收條件跨層級 |

**判定邏輯**: 任一要素不明確 → 阻止 ❌

---

### 附錄 C：與其他方法論的整合指引

#### 與《Ticket 設計派工方法論》整合

**關係定位**:
- **包含關係**: Code Smell 品質閘門檢測是 Ticket 設計派工方法論的第 2.4 節
- **整合點**: Phase 1（設計階段）完成 Ticket 後立即執行品質閘門檢測

**整合流程**:
```text
Phase 1（設計階段）
  ↓
lavender-interface-designer 設計 Ticket
  ↓
【品質閘門檢測】執行 C1/C2/C3 檢測 ← 本方法論
  ├─ 通過 → 提交給 PM 審查
  └─ 失敗 → 修正後重新檢測
  ↓
PM 審查批准
  ↓
分派給開發者執行（進入 Phase 2）
```

**引用方式**:
- 設計 Ticket 時參考《Ticket 設計派工方法論》
- 品質檢測時參考《Code Smell 品質閘門檢測方法論》

---

#### 與《Ticket 拆分標準方法論》整合

**關係定位**:
- **依賴關係**: C1 檢測失敗時需要執行 Ticket 拆分，拆分標準來自《Ticket 拆分標準方法論》
- **整合點**: C1 檢測失敗處理流程

**整合流程**:
```text
C1 檢測失敗（God Ticket）
  ↓
【拆分決策】參考《Ticket 拆分標準方法論》 ← 引用點
  ├─ 按層級拆分（策略 1）
  ├─ 按職責拆分（策略 2）
  ├─ 按 TDD 階段拆分（策略 3）
  └─ 按技術棧拆分（策略 4）
  ↓
拆分後重新執行 C1 檢測
  ├─ 通過 → 繼續 C3 檢測
  └─ 失敗 → 再次拆分
```

**引用方式**:
- C1 檢測確認複雜度問題
- 拆分策略參考《Ticket 拆分標準方法論》第三章

---

#### 與《敏捷重構方法論》整合

**關係定位**:
- **橫向關係**: 品質閘門檢測在 Phase 1，敏捷重構在 Phase 4
- **整合點**: 工作日誌記錄和三重文件原則

**整合流程**:
```text
Phase 1（設計階段）
  ↓
品質閘門檢測 ← 本方法論
  ├─ 檢測記錄寫入 vX.Y.Z-phase1-design.md
  └─ 修正記錄寫入工作日誌
  ↓
Phase 2-3（測試與實作）
  ↓
Phase 4（重構階段）
  ↓
敏捷重構 ← 參考《敏捷重構方法論》
  ├─ 重構記錄寫入 vX.Y.Z-phase4-refactor.md
  └─ 更新三重文件（CHANGELOG/todolist/work-log）
```

**引用方式**:
- 工作日誌記錄格式參考《敏捷重構方法論 - 三層進度管理》
- 檢測記錄納入工作日誌的 Phase 1 記錄

---

#### 與《Hook 系統方法論》整合

**關係定位**:
- **技術依賴**: 自動化檢測依賴 Hook 系統執行
- **整合點**: PostEdit Hook 觸發品質閘門檢測

**整合流程**:
```text
開發者儲存 Ticket 檔案（Write/Edit）
  ↓
【PostEdit Hook 觸發】
  ↓
執行 ticket_quality_gate_hook.py ← 本方法論第五章
  ├─ C1 自動化檢測
  ├─ C2 自動化檢測
  └─ C3 自動化檢測
  ↓
生成檢測報告
  ├─ 文字報告（給開發者閱讀）
  └─ JSON 報告（給工具解析）
  ↓
記錄到 .claude/hook-logs/quality-gate-reports/
```

**引用方式**:
- Hook 配置參考《Hook 系統方法論 - PostEdit Hook 設計》
- Python 腳本開發參考《Hook 系統方法論 - UV Single-File Pattern》

---

**完整引用網絡**:
```text
Code Smell 品質閘門檢測方法論（本方法論）
  ↑ 被引用
Ticket 設計派工方法論（主方法論）
  ↓ 引用
  ├─ Ticket 拆分標準方法論（C1 失敗處理）
  ├─ 敏捷重構方法論（工作日誌記錄）
  ├─ Hook 系統方法論（自動化檢測）
  └─ Clean Architecture 實作方法論（架構原則）
```

---

## 總結

### 方法論價值

**Code Smell 品質閘門檢測方法論**實現了「設計階段品質保證」的創新實踐：

1. **及早發現問題**: 在設計階段（Phase 1）即發現並修正 Code Smell，修正成本降低 80%
2. **標準化檢測**: 提供明確的 C1/C2/C3 檢測標準，避免主觀判斷
3. **自動化支援**: 高自動化程度（C1: 80%, C2: 90%, C3: 70%），減少人工檢測工作量
4. **完整記錄**: 所有檢測過程和修正過程都記錄到工作日誌，可追溯決策
5. **阻斷機制**: 強制修正，確保 Ticket 品質符合標準才能進入實作階段

### 核心創新

**從「實作品質檢測」到「設計品質檢測」**：
```text
傳統方法：
設計 → 實作 → 測試 → 發現問題 → 重構修正
                              ↑
                         修正成本高

本方法論：
設計 → 品質閘門檢測 → 發現問題 → 修正設計 → 實作
              ↑                      ↑
         及早發現              修正成本低
```

### 適用場景

**最適合採用的專案**:
- 採用 Clean Architecture 的專案（明確的分層架構）
- 實行 TDD 四階段方法論的團隊
- 需要控制技術債務的長期專案
- 多人協作需要標準化品質控制的團隊

**不適合採用的場景**:
- 快速原型開發（過度的品質控制會降低速度）
- 一次性專案（投入產出比不划算）
- 單人開發且經驗豐富（自我管理能力強）

### 持續改善

**方法論本身需要持續改善**:
1. **自動化程度提升**: 持續提升自動化檢測的信心度
2. **檢測標準調整**: 根據專案實際情況調整閾值
3. **案例累積**: 持續補充實務案例，提升參考價值
4. **工具整合**: 與 IDE、CI/CD 等工具深度整合

---

**最後更新**: 2025-10-11 22:05
**方法論版本**: v1.0
**狀態**: 完整版本
**檔案規模**: ~12,700 tokens
**完成度**: 100% ✅
