# 程式碼註解撰寫方法論

## 註解的本質

### 註解不是什麼

註解不是：

- **程式碼解釋器**：不解釋程式在做什麼
- **API 文件**：不描述函式的使用方法
- **實作說明**：不說明技術選擇理由
- **TODO 列表**：不記錄未完成工作

### 註解是什麼

註解是：

- **需求保護器**：防止維護時破壞原始需求
- **設計意圖記錄**：保存業務邏輯的設計考量
- **維護指引**：為未來修改者提供約束條件
- **需求上下文**：建立程式碼與需求規格的連結

## 第一原則：程式碼自說明

### 語意化命名要求

程式碼本身必須完全可讀：

#### 函式命名標準

```dart
// ❌ 錯誤：需要註解才能理解
void process(Book book) {
  // 檢查書籍狀態並更新進度
}

// ✅ 正確：函式名稱完全說明行為
void updateReadingProgressWhenStatusChanges(Book book) {
  // 需求：UC-005 閱讀進度管理
  // 當使用者標記書籍為「閱讀中」時，自動設定進度為 0%
  // 當使用者標記為「已完成」時，自動設定進度為 100%
  // 約束：不可覆蓋使用者手動設定的進度值
}
```

#### 變數命名標準

```dart
// ❌ 錯誤：需要註解解釋變數內容
final data = book.getInfo();

// ✅ 正確：變數名稱完全說明內容
final enrichedBookMetadata = book.getMetadataWithEnrichment();
```

### 自說明程式碼的驗證標準

程式碼達到自說明標準的判斷：

- 移除所有註解後，仍能理解程式邏輯 → 合格
- 需要猜測變數含義或函式行為 → 重新命名
- 無法確定程式碼目的 → 拆分函式

## 第二原則：註解記錄需求脈絡

### 需求連結標準

每個業務邏輯註解必須包含：

#### 需求編號引用

```dart
/// 需求：UC-003.2 書籍分類管理
/// 使用者可以為書籍設定多個標籤進行分類
/// 約束：標籤名稱不可重複，最多 10 個標籤
void addTagToBook(BookId bookId, Tag tag) {
  // 實作...
}
```

#### 業務規則說明

```dart
/// 需求：BR-001 書籍狀態轉換規則
/// 書籍狀態變更順序：初始 → 資訊補充中 → 資訊補充完成 → 可用
/// 約束：不可跳過中間狀態，不可逆向轉換
/// 例外：管理員可以直接設定為任何狀態
BookStatus transitionBookStatus(BookStatus current, BookStatus target) {
  // 實作...
}
```

#### 設計決策記錄

```dart
/// 需求：NFR-002 效能需求
/// 書庫載入時間不可超過 2 秒
/// 設計決策：採用懶載入 + 分頁載入策略
/// 影響：首次載入只載入 20 本書，滾動時動態載入
List<Book> loadLibraryWithPagination(int page, int pageSize) {
  // 實作...
}
```

### 註解內容的必要元素

每個業務邏輯註解必須包含：

1. **需求來源**：UC-編號或 BR-編號
2. **業務描述**：使用者故事或業務規則
3. **約束條件**：限制和邊界條件
4. **影響範圍**：修改此邏輯會影響哪些功能

## 第三原則：維護指引的明確性

### 修改約束標準

註解必須明確告知維護者：

#### 禁止修改的邏輯

```dart
/// 需求：UC-001.3 書籍唯一性檢查
/// 同一書庫內不可有相同 ISBN 的書籍
/// 警告：此邏輯關聯到資料一致性，修改前必須檢查：
/// - 書籍匯入流程 (ImportBookService)
/// - 書籍合併功能 (BookMergeService)
/// - 資料庫索引設計 (book_isbn_unique_index)
bool isDuplicateBook(String isbn, LibraryId libraryId) {
  // 實作...
}
```

#### 擴展要求的邏輯

```dart
/// 需求：UC-004 書籍搜尋功能
/// 支援書名、作者、標籤的模糊搜尋
/// 擴展指引：新增搜尋條件時必須：
/// 1. 更新 SearchCriteria 值物件
/// 2. 修改索引策略以維持效能
/// 3. 更新搜尋測試案例涵蓋新條件
List<Book> searchBooks(SearchCriteria criteria) {
  // 實作...
}
```

### 相依性警告標準

```dart
/// 需求：UC-006 借閱管理
/// 計算書籍歸還到期日
/// 相依性警告：此邏輯與以下模組緊密耦合
/// - LoanReminderService（提醒計算）
/// - OverdueBookDetector（逾期偵測）
/// - LibraryStatistics（統計計算）
/// 修改歸還期限計算會影響上述所有模組
DateTime calculateDueDate(DateTime loanDate, int loanPeriodDays) {
  // 實作...
}
```

## 第四原則：註解的結構標準

### 標準註解格式

```dart
/// 需求：[需求編號] [簡短描述]
/// [詳細業務描述，說明使用者需求]
/// 約束：[限制條件和邊界規則]
/// [維護指引：修改須知、相依性警告、擴展要求]
[函式簽名]
```

### 複雜業務邏輯的註解範例

```dart
/// 需求：UC-007.1 閱讀統計分析
/// 計算使用者的閱讀速度和預估剩餘時間
/// 約束：只統計狀態為「閱讀中」的書籍，頁數必須大於 0
/// 計算邏輯：(已讀頁數 / 實際閱讀時間) = 閱讀速度（頁/小時）
/// 維護指引：修改計算公式會影響：
/// - 閱讀目標設定功能
/// - 個人化推薦系統
/// - 學習分析報表
/// 相依模組：ReadingProgressTracker, BookMetadata, UserPreferences
ReadingSpeed calculateReadingSpeed(
  ReadingProgress progress,
  BookMetadata metadata,
  Duration actualReadingTime
) {
  // 實作...
}
```

## 禁止的註解模式

### 程式碼重述與技術實作細節描述（違反 DRY 原則）

#### ❌ 禁止：直接重述程式碼行為

```dart
// ❌ 禁止：重述程式碼
// 設定書籍標題
book.setTitle(newTitle);

// ❌ 禁止：描述技術實作細節
// 使用 Map 快速查找避免 O(n) 複雜度
final bookMap = books.asMap();
```

#### ❌ 禁止：描述 UI 技術實作細節

```dart
/// ❌ 錯誤：重複描述程式碼內容
/// BookListItem - 書庫列表項目 Widget
///
/// 視覺設計：
/// - 陰影刻痕變化（凸起→凹陷）              ← 直接描述程式碼實作
/// - 無背景色變化（保持純白）                ← 可以從程式碼看出
/// - 無邊框、無選中指示器（極簡設計）        ← 程式碼已說明
/// - AnimatedContainer 200ms 過渡動畫       ← 重複程式碼參數
///
/// 觸覺回饋：
/// - 選擇時：HapticFeedback.selectionClick()  ← 重複程式碼呼叫
/// - 取消選擇：HapticFeedback.lightImpact()   ← 重複程式碼呼叫
class BookListItem extends StatelessWidget {
  // ...
}
```

**問題分析**：

- ❌ 描述「200ms」、「陰影凸起→凹陷」等技術細節 → 程式碼已經說明
- ❌ 列舉 `HapticFeedback.selectionClick()` 等 API 呼叫 → 完全重複程式碼
- ❌ 沒有說明「為什麼」這樣設計 → 缺少需求和設計決策依據

#### ✅ 正確：記錄設計決策和需求脈絡

```dart
/// 【需求來源】UC-05: 雙模式書庫展示切換 - 書籍選擇互動
/// 【規格文件】docs/ui_design_specification.md#book-selection-feedback
/// 【設計決策】採用方案C-1基礎版 - 極簡視覺回饋設計
/// 【為什麼選擇陰影刻痕變化】
/// - 不影響文字可讀性：避免背景色干擾閱讀體驗
/// - 符合無障礙設計：不依賴顏色作為唯一視覺提示
/// 【為什麼選擇差異化觸覺回饋】
/// - 選中 vs 取消必須有不同的觸覺回饋類型
/// - selectionClick 提供明確的「確認」感受
/// - lightImpact 提供輕微的「狀態變更」提示
/// 【修改約束】
/// - 觸覺回饋時機不可調換（與使用者預期一致）
/// - 陰影變化動畫時長需保持 < 250ms（符合 Material Design 規範）
/// 【維護警告】
/// - 此 Widget 被 3 個書庫頁面使用
/// - 修改視覺回饋會影響整體使用者體驗一致性
class BookListItem extends StatelessWidget {
  // ...
}
```

**正確註解特徵**：
- ✅ 說明「為什麼」選擇陰影變化（使用者調研數據）
- ✅ 說明「為什麼」差異化觸覺回饋（使用者預期）
- ✅ 記錄設計約束（Material Design 規範）
- ✅ 提供維護警告（影響範圍）
- ❌ 不重複程式碼內容（200ms、HapticFeedback API）

### 模糊的業務描述

```dart
// ❌ 禁止：模糊的業務描述
// 處理書籍相關邏輯
void handleBook(Book book) {}

// ❌ 禁止：缺乏約束的需求描述
// 讓使用者管理書籍
void manageBook(Book book) {}
```

### 過時的註解

```dart
// ❌ 禁止：過時且未更新的註解
// TODO: 之後要加入 ISBN 驗證
// 注意：此函式目前只支援簡單驗證
// （實際上已經有完整的 ISBN 驗證了）
bool validateBookData(BookData data) {
  return isbnValidator.validate(data.isbn) &&
         titleValidator.validate(data.title);
}
```

## 註解品質驗證標準

### 可執行性測試

對每個註解檢查：

1. 維護者能理解業務需求嗎？
2. 修改約束是否明確？
3. 需求來源可以追溯嗎？
4. 影響範圍是否完整？

### 必要性測試

檢查註解是否必要：

- 移除註解後，是否會遺失業務脈絡？ → 必要
- 移除註解後，仍能理解程式邏輯？ → 檢查是否為重述
- 註解內容是否過時？ → 更新或刪除

### 完整性檢查清單

每個業務邏輯註解必須包含：

- [ ] 需求編號或業務規則編號
- [ ] 清晰的業務描述
- [ ] 明確的約束條件
- [ ] 維護指引或修改警告
- [ ] 相依性說明（如適用）

## 與程式碼審查的整合

### Code Review 檢查點

審查時必須確認：

1. **新增業務邏輯** → 必須有需求註解
2. **修改現有邏輯** → 註解是否需要更新
3. **重構程式碼** → 註解的需求脈絡是否保持
4. **刪除程式碼** → 相關註解是否一併移除

### 註解覆蓋率要求

- 業務邏輯函式 → 100% 需要需求註解
- 純技術函式（utility） → 不需要業務註解
- 值物件建構器 → 需要約束條件註解
- 領域模型方法 → 需要業務規則註解

## 第五原則：事件驅動架構註解標準

### 事件處理函式識別

事件處理函式特徵：
- 函式名稱包含 `handle*`, `on*`, `process*`, `emit*`, `dispatch*`
- 回傳類型為 `Future<>`, `Stream<>`, `OperationResult<>`
- 位於 UseCase 或 Domain 層

### 事件處理函式註解範例

```dart
/// 【需求來源】UC-01: Chrome Extension 匯入書籍資料
/// 【規格文件】docs/app-requirements-spec.md#chrome-extension-import
/// 【設計方案】方案C-1基礎版 (v0.12.7 Phase 1)
/// 【工作日誌】docs/work-logs/v0.12.7.md - 方案研究和設計決策
/// 【事件類型】BookAdded 事件處理
/// 【修改約束】修改時需確保事件流完整性，避免影響上游訂閱者
/// 【維護警告】此函式被 3 個 UseCase 依賴，修改前需檢查影響範圍
Future<void> handleBookAdded(BookAddedEvent event) async {
  // 實作...
}
```

### 輔助函式豁免規則

以下函式類型可豁免詳細註解：
- 私有前置處理函式（`_isValid*`, `_format*`, `_prepare*`）
- 私有資料轉換函式（`_convert*`, `_transform*`, `_parse*`）
- 私有驗證函式（`_validate*`, `_check*`, `_extract*`）

**理由**：這些函式不包含業務邏輯，僅負責技術性資料處理。

## 第六原則：Widget 獨立性註解標準

### 獨立 Widget 識別

獨立 Widget 特徵：
- 非私有命名（不以 `_` 開頭）
- 繼承自 `StatefulWidget`, `ConsumerWidget`, `StreamBuilder`, `FutureBuilder`
- 具備獨立狀態管理能力

### 獨立 Widget 註解範例

```dart
/// 【需求來源】UC-05: 雙模式書庫展示切換
/// 【規格文件】docs/ui_design_specification.md#book-list-item
/// 【設計方案】方案C-1基礎版 - 陰影刻痕變化 + 觸覺回饋
/// 【工作日誌】docs/work-logs/v0.12.7.md - UI 互動設計
/// 【Widget 類型】獨立狀態管理 Widget
/// 【修改約束】此 Widget 具備獨立狀態，下層刷新不觸發上層重建
/// 【維護警告】修改前需確認子 Widget 依賴關係
class BookListItem extends StatefulWidget {
  // 實作...
}
```

### 依賴型 Widget 豁免規則

以下 Widget 類型可豁免詳細註解：
- 私有 StatelessWidget（如 `_BookTitleText`, `_ProgressBar`）
- 完全依賴上層狀態的子組件
- 純展示型組件（無獨立狀態管理）

**理由**：這些 Widget 僅負責展示上層傳遞的資料，不包含獨立的業務邏輯。

## 第七原則：工作日誌追溯標準

### 工作日誌連結格式

註解必須包含工作日誌追溯資訊：

```dart
/// 【工作日誌】docs/work-logs/v0.12.7.md - 方案C-1基礎版設計
```

**追溯資訊包含**：
- 工作日誌檔案路徑
- 設計方案名稱或 Phase 階段
- 關鍵決策記錄

### 規格文件連結格式

註解必須包含規格文件連結：

```dart
/// 【規格文件】docs/app-requirements-spec.md#section-name
/// 【規格文件】docs/event-driven-architecture-design.md#event-flow
```

**規格文件類型**：
- `app-requirements-spec.md` - 功能需求規格
- `event-driven-architecture-design.md` - 事件驅動架構規範
- `ui_design_specification.md` - UI 設計規格
- `app-use-cases.md` - 用例說明文件

## Comment Quality Assurance Hook

本專案提供自動化註解品質檢查 Hook：

**Hook 位置**: `.claude/hooks/comment-qa-hook.py`

**檢查功能**：
- 自動識別事件處理函式和獨立 Widget
- 智慧豁免輔助函式和依賴型 Widget
- 生成符合標準的註解框架建議
- 追溯工作日誌和規格文件

**觸發時機**: PostToolUse Hook (Edit/Write 完成後)

**報告位置**: `.claude/hook-logs/comment-qa/reports/`

## 結論

註解不是程式碼的解釋員，而是需求的守護者。它們的存在是為了讓未來的維護者能夠：

- 理解程式碼背後的業務需求
- 避免破壞原始設計意圖
- 正確地擴展和修改功能
- 追溯需求來源和設計決策
- 理解事件驅動架構的事件流
- 識別 Widget 的獨立性和依賴關係

這是需求保護機制，確保每次修改都能追溯原始意圖，而非純粹的文書工作。
