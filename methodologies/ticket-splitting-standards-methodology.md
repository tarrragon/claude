# Ticket 拆分標準方法論

> ## ⚠️ 棄用警告
>
> **本方法論已被 [🎯 Atomic Ticket 方法論](./atomic-ticket-methodology.md) 取代。**
>
> **核心變更**：
> - ❌ 不再使用時間、行數、檔案數、測試數等**量化指標**判斷拆分
> - ✅ 改用**單一職責原則**（Single Responsibility Principle）作為唯一評估標準
>
> **新的評估方式**：
> 1. **語義檢查**：能用「動詞 + 單一目標」表達嗎？
> 2. **修改原因檢查**：只有一個原因會導致修改嗎？
> 3. **驗收一致性**：所有驗收條件指向同一目標嗎？
> 4. **依賴獨立性**：拆分後不會產生循環依賴嗎？
>
> **請改用**：[🎯 Atomic Ticket 方法論](./atomic-ticket-methodology.md)

---

## 方法論概述（歷史參考）

> **注意**：以下內容為歷史版本，僅供參考。請使用 Atomic Ticket 方法論。

### 為什麼需要 Ticket 拆分標準

**問題背景**:

在大型軟體開發專案中，我們經常面臨以下挑戰：

1. **God Ticket 問題**：單一任務過於龐大，包含數十個檔案修改，跨越多個架構層級
2. **主觀判斷困境**：不同開發者對「任務大小」的理解不同，導致協作效率低
3. **進度追蹤困難**：任務粒度不一致，難以準確評估完成度
4. **風險控制失衡**：大任務失敗影響大，小任務過碎增加管理成本

**傳統拆分方法的問題**:

- ❌ **經驗導向**：依賴個人經驗判斷，缺乏客觀標準
- ❌ **時間估算**：受個人能力和環境影響，難以標準化
- ❌ **模糊描述**：「不要太大」「保持適中」等描述無法執行
- ❌ **後驗調整**：任務執行後才發現過大，增加返工成本

**~~本方法論的創新點~~**（已棄用）:

~~本方法論提供**量化、客觀、可執行**的 Ticket 拆分標準：~~

~~✅ **4 個量化指標**：職責數量、程式碼行數、檔案數量、測試數量~~
~~✅ **複雜度分級**：簡單、中等、複雜、需拆分 4 個明確等級~~
~~✅ **分層拆分策略**：基於 Clean Architecture 的標準化拆分方法~~
~~✅ **決策樹指引**：提供完整的拆分決策流程~~

---

### 適用場景

**核心適用場景**:
- 多人協作開發專案
- 需要精細進度追蹤的敏捷開發
- 採用 Clean Architecture 的軟體專案
- 需要標準化任務管理的團隊

**特別適用情況**:
- **新團隊建立**: 缺乏任務拆分經驗的新團隊
- **大型重構**: 需要將大型任務分解為可控單元
- **遠端協作**: 需要明確任務邊界的分散式團隊
- **品質管控**: 需要在設計階段就控制任務複雜度

---

### 核心目標

1. **標準化任務拆分**：提供統一的拆分標準，消除主觀判斷
2. **控制任務複雜度**：確保每個 Ticket 在可控範圍內
3. **提升協作效率**：明確的任務邊界，減少溝通成本
4. **及早風險管控**：設計階段就識別過大任務，降低執行風險

---

### 與其他方法論的關係

**本方法論的定位**:

```text
Ticket 設計派工方法論 (主方法論)
├── Ticket 拆分標準方法論 ← 你正在閱讀
│   └── 提供量化拆分標準和決策樹
├── Code Smell 品質閘門檢測方法論
│   └── 提供設計階段的品質檢測
├── Ticket 生命週期管理方法論
│   └── 提供 Ticket 執行流程管理
└── 即時 Review 機制方法論
    └── 提供執行過程中的 Review 機制
```

**與相關方法論的整合**:

| 方法論 | 關係 | 整合點 |
|--------|------|--------|
| [Ticket 設計派工方法論]($CLAUDE_PROJECT_DIR/.claude/methodologies/ticket-design-dispatch-methodology.md) | **父方法論** | 本方法論是其第二章的詳細展開 |
| [Clean Architecture 實作方法論]($CLAUDE_PROJECT_DIR/.claude/methodologies/clean-architecture-implementation-methodology.md) | **依賴方法論** | 基於 CA 分層原則設計拆分策略 |
| [層級隔離派工方法論]($CLAUDE_PROJECT_DIR/.claude/methodologies/layered-ticket-methodology.md) | **平行方法論** | 提供層級隔離的派工策略 |
| [TDD 四階段方法論]($CLAUDE_PROJECT_DIR/.claude/methodologies/tdd-four-phases-methodology.md) | **平行方法論** | 測試數量指標基於 TDD 實踐 |

---

## 第一章：量化指標體系

### 1.1 指標 1：職責數量（Responsibilities）⭐ 最優先

**定義**：Ticket 需要完成的獨立職責數量。

**為什麼職責是第一指標**：
- ✅ **最客觀**：不受個人能力影響
- ✅ **最穩定**：不受環境和參考資料影響
- ✅ **最易溝通**：PM 和工程師都能理解
- ✅ **最精確**：直接對應業務需求

#### 職責的精確定義

**什麼算一個職責**：

一個職責 = 一個明確可驗證的功能點或邊界條件

**識別方式**：
- 每個「需要實作的功能點」算一個職責
- 每個「需要驗證的邊界條件」算一個職責
- 每個「需要處理的錯誤情境」算一個職責

**範例說明**：

```markdown
範例任務：實作書籍評分功能

職責識別：
1. 定義 Rating Value Object（數值範圍驗證）      ← 職責 1
2. 定義 Rating Entity（包含評分和評論）         ← 職責 2
3. 實作 IRatingRepository 介面                  ← 職責 3
4. 實作評分儲存邏輯                              ← 職責 4
5. 處理無效評分錯誤                              ← 職責 5
6. 處理資料庫錯誤                                ← 職責 6

總計：6 個職責 → 超過 5 個，必須拆分
```

#### 職責數量標準

| 等級 | 職責數量 | 判定 | 說明 |
|------|---------|------|------|
| **簡單 Ticket** | 1 個 | ✅ 理想 | 單一職責，最易管理 |
| **中等 Ticket** | 2-3 個 | ✅ 可接受 | 少數相關職責，可控範圍 |
| **複雜 Ticket** | 3-5 個 | ⚠️ 需檢查 | 多職責，建議拆分 |
| **必須拆分** | > 5 個 | ❌ 禁止 | 範圍失控，必須拆分 |

**強制規則**：
- ⚠️ **超過 5 個職責 = 必須拆分**，無例外
- ⚠️ **3-5 個職責 = 評估是否可拆分**，優先拆分
- ✅ **1-2 個職責 = 理想狀態**，鼓勵維持

#### 職責識別實例

**實例 1：簡單 Ticket（1 職責）**

```markdown
任務：定義 SelectionManager 介面方法簽名

職責分析：
✅ 職責 1：定義 toggleSelection、clearSelection、getSelectedIds 三個方法簽名

總計：1 個職責
判定：簡單 Ticket ✅
```

**實例 2：中等 Ticket（2-3 職責）**

```markdown
任務：實作 SelectionManager 基礎功能

職責分析：
✅ 職責 1：實作 toggleSelection 方法
✅ 職責 2：實作 clearSelection 方法
✅ 職責 3：實作 ChangeNotifier 通知機制

總計：3 個職責
判定：中等 Ticket ✅（可接受）
```

**實例 3：複雜 Ticket（3-5 職責）- 建議拆分**

```markdown
任務：實作完整的 BookRepository

職責分析：
⚠️ 職責 1：實作 getBookByIsbn CRUD 方法
⚠️ 職責 2：實作 saveBook CRUD 方法
⚠️ 職責 3：實作 Data Mapper 轉換
⚠️ 職責 4：實作錯誤處理
⚠️ 職責 5：實作 Cache 管理

總計：5 個職責
判定：複雜 Ticket ⚠️（建議拆分為 2-3 個 Ticket）
```

**實例 4：必須拆分（> 5 職責）**

```markdown
任務：實作書籍評分完整功能（包含 UI、UseCase、Repository）

職責分析：
❌ 職責 1：定義 Rating Value Object
❌ 職責 2：定義 Rating Entity
❌ 職責 3：建立 RatingWidget UI
❌ 職責 4：實作 RateBookUseCase
❌ 職責 5：定義 IRatingRepository
❌ 職責 6：實作 SQLiteRatingRepository
❌ 職責 7：處理各種異常情境
❌ 職責 8：撰寫完整測試

總計：8 個職責
判定：God Ticket ❌ 必須拆分
```

**拆分建議**：
```markdown
拆分為 4 個 Ticket：
- Ticket 1: 定義 Rating Domain 模型（職責 1, 2）
- Ticket 2: 實作 RatingRepository（職責 5, 6）
- Ticket 3: 實作 RateBookUseCase（職責 4, 7）
- Ticket 4: 實作 RatingWidget UI（職責 3, 8）
```

---

### 1.2 指標 2：程式碼行數（Lines of Code）

**定義**：Ticket 涉及的程式碼修改行數（新增 + 修改 + 刪除）。

**為什麼需要行數指標**：
- ✅ **可量化**：使用 `git diff --stat` 精確統計
- ✅ **可驗證**：執行後可驗證預估準確性
- ✅ **風險指標**：行數越多，出錯風險越高

#### 行數統計標準

**測量方式**：
```bash
# 統計修改行數
git diff --stat

# 範例輸出
lib/domain/entities/book.dart        | 25 +++++++++++++
lib/domain/repositories/i_repo.dart  | 15 ++++++--
test/unit/domain/book_test.dart      | 40 ++++++++++++++++++++
3 files changed, 78 insertions(+), 2 deletions(-)

# 計算方式
總行數 = 新增行數 + 修改行數 + 刪除行數
      = 25 + 15 + 40 = 80 行
```

**計算規則**：
- ✅ 包含新增行數
- ✅ 包含修改行數
- ✅ 包含刪除行數
- ❌ 不包含空行（pure whitespace changes）
- ❌ 不包含純註解行（comment-only changes）

#### 行數標準

| 等級 | 行數範圍 | 判定 | 說明 |
|------|---------|------|------|
| **簡單 Ticket** | < 30 行 | ✅ 理想 | Interface 定義、簡單 Value Object |
| **中等 Ticket** | 30-70 行 | ✅ 可接受 | 中等實作、含測試 |
| **複雜 Ticket** | 70-100 行 | ⚠️ 需檢查 | 複雜實作、多測試案例 |
| **必須拆分** | > 100 行 | ❌ 禁止 | 範圍過大，必須拆分 |

**強制規則**：
- ⚠️ **超過 100 行 = 必須拆分**
- ⚠️ **70-100 行 = 評估是否可拆分**
- ✅ **< 70 行 = 可接受範圍**

#### 行數估算實例

**實例 1：簡單 Ticket（< 30 行）**

```dart
// 任務：定義 IBookRepository 介面
// lib/domain/repositories/i_book_repository.dart

abstract class IBookRepository {
  /// 根據 ISBN 取得書籍
  Future<Book?> getBookByIsbn(String isbn);

  /// 儲存書籍
  Future<void> saveBook(Book book);

  /// 刪除書籍
  Future<void> deleteBook(String isbn);
}

// 預估行數：~20 行（含註解）
// 判定：簡單 Ticket ✅
```

**實例 2：中等 Ticket（30-70 行）**

```dart
// 任務：實作 Rating Value Object
// lib/domain/value_objects/rating.dart + test

// rating.dart (~40 行)
class Rating {
  final int value;

  Rating(this.value) {
    if (value < 1 || value > 5) {
      throw ValidationException.invalidRating(value);
    }
  }

  // ... 其他方法（equals, hashCode, toString）
}

// rating_test.dart (~25 行)
void main() {
  test('建立有效評分', () { ... });
  test('評分過低拋出異常', () { ... });
  test('評分過高拋出異常', () { ... });
}

// 總計：~65 行
// 判定：中等 Ticket ✅
```

**實例 3：複雜 Ticket（70-100 行）- 建議拆分**

```dart
// 任務：實作完整的 BookRepository
// lib/infrastructure/repositories/sqlite_book_repository.dart + test

// repository.dart (~80 行)
class SQLiteBookRepository implements IBookRepository {
  // ... 建構子和欄位定義

  @override
  Future<Book?> getBookByIsbn(String isbn) async {
    // ... SQL 查詢邏輯（~15 行）
    // ... Data Mapper 轉換（~10 行）
    // ... 錯誤處理（~5 行）
  }

  @override
  Future<void> saveBook(Book book) async {
    // ... SQL 插入/更新邏輯（~20 行）
    // ... Data Mapper 轉換（~10 行）
    // ... 錯誤處理（~5 行）
  }

  @override
  Future<void> deleteBook(String isbn) async {
    // ... SQL 刪除邏輯（~10 行）
    // ... 錯誤處理（~5 行）
  }
}

// repository_test.dart (~80 行)
// ... 8 個測試案例

// 總計：~160 行 ❌
// 判定：超過 100 行，必須拆分
```

**拆分建議**：
```markdown
拆分為 3 個 Ticket：
- Ticket 1: 定義 IBookRepository 介面（~20 行）
- Ticket 2: 實作 getBookByIsbn + 測試（~60 行）
- Ticket 3: 實作 saveBook + deleteBook + 測試（~80 行）
```

---

### 1.3 指標 3：涉及檔案數（Files）

**定義**：Ticket 需要修改的檔案數量（不含測試檔案）。

**為什麼需要檔案數指標**：
- ✅ **架構層級指標**：檔案數反映任務的架構範圍
- ✅ **風險管控**：修改越多檔案，影響範圍越大
- ✅ **測試複雜度**：檔案數越多，測試整合越複雜

#### 檔案統計標準

**測量方式**：
```bash
# 統計修改檔案數
git diff --name-only | grep -v '_test\.dart$' | wc -l

# 範例輸出
lib/domain/entities/book.dart
lib/domain/repositories/i_book_repository.dart
lib/infrastructure/repositories/sqlite_book_repository.dart

# 結果：3 個檔案（不含測試）
```

**計算規則**：
- ✅ 包含新建檔案
- ✅ 包含修改檔案
- ✅ 包含刪除檔案
- ❌ 不包含測試檔案（測試檔案另計為「測試數量」指標）
- ❌ 不包含配置檔案（如 pubspec.yaml, analysis_options.yaml）

#### 檔案數標準

| 等級 | 檔案數量 | 判定 | 說明 |
|------|---------|------|------|
| **簡單 Ticket** | 1 個 | ✅ 理想 | 單一檔案修改 |
| **中等 Ticket** | 2-3 個 | ✅ 可接受 | 相關檔案修改 |
| **複雜 Ticket** | 3-5 個 | ⚠️ 需檢查 | 多檔案修改，建議拆分 |
| **必須拆分** | > 5 個 | ❌ 禁止 | 範圍過大，必須拆分 |

**強制規則**：
- ⚠️ **超過 5 個檔案 = 必須拆分**
- ⚠️ **3-5 個檔案 = 評估是否可拆分**
- ✅ **1-2 個檔案 = 理想狀態**

#### 檔案數實例

**實例 1：簡單 Ticket（1 個檔案）**

```markdown
任務：建立 Rating Value Object

涉及檔案：
✅ lib/domain/value_objects/rating.dart

總計：1 個檔案
判定：簡單 Ticket ✅
```

**實例 2：中等 Ticket（2-3 個檔案）**

```markdown
任務：更新 Book Entity 增加評分欄位

涉及檔案：
✅ lib/domain/entities/book.dart         （修改）
✅ lib/domain/value_objects/rating.dart  （新增）

總計：2 個檔案
判定：中等 Ticket ✅
```

**實例 3：複雜 Ticket（3-5 個檔案）- 建議拆分**

```markdown
任務：實作完整的書籍評分功能

涉及檔案：
⚠️ lib/domain/entities/rating.dart
⚠️ lib/domain/entities/book.dart
⚠️ lib/domain/repositories/i_rating_repository.dart
⚠️ lib/infrastructure/repositories/sqlite_rating_repository.dart
⚠️ lib/infrastructure/mappers/rating_mapper.dart

總計：5 個檔案
判定：複雜 Ticket ⚠️（建議拆分）
```

**實例 4：必須拆分（> 5 個檔案）**

```markdown
任務：實作評分功能（含 UI、UseCase、Repository）

涉及檔案：
❌ lib/presentation/widgets/rating_widget.dart
❌ lib/presentation/controllers/rating_controller.dart
❌ lib/application/use_cases/rate_book_use_case.dart
❌ lib/domain/entities/rating.dart
❌ lib/domain/entities/book.dart
❌ lib/domain/repositories/i_rating_repository.dart
❌ lib/infrastructure/repositories/sqlite_rating_repository.dart
❌ lib/infrastructure/mappers/rating_mapper.dart

總計：8 個檔案 ❌
判定：God Ticket，必須拆分
```

**拆分建議**：
```markdown
按 Clean Architecture 分層拆分為 4 個 Ticket：
- Ticket 1: Domain 層（檔案 4, 5, 6）             - 3 個檔案 ✅
- Ticket 2: Infrastructure 層（檔案 7, 8）        - 2 個檔案 ✅
- Ticket 3: Application 層（檔案 3）              - 1 個檔案 ✅
- Ticket 4: Presentation 層（檔案 1, 2）          - 2 個檔案 ✅
```

---

### 1.4 指標 4：測試用例數（Tests）

**定義**：Ticket 對應的測試用例數量。

**為什麼需要測試數量指標**：
- ✅ **品質保證指標**：測試數量反映功能複雜度
- ✅ **執行時間預估**：測試數量影響 TDD 循環時間
- ✅ **維護成本**：過多測試增加維護負擔

#### 測試統計標準

**測量方式**：
```dart
// 計算測試方法數
void main() {
  group('Rating Value Object', () {
    test('建立有效評分', () { ... });           // 測試 1
    test('評分過低拋出異常', () { ... });        // 測試 2
    test('評分過高拋出異常', () { ... });        // 測試 3
    test('相同評分視為相等', () { ... });        // 測試 4
  });
}

// 總計：4 個測試
```

**計算規則**：
- ✅ 每個 `test('...', () {...})` 算一個測試
- ✅ 每個 `testWidgets('...', () {...})` 算一個測試
- ✅ 包含單元測試和整合測試
- ❌ 不包含 `group()` 本身（只是測試組織）

#### 測試數量標準

| 等級 | 測試數量 | 判定 | 說明 |
|------|---------|------|------|
| **簡單 Ticket** | 1-3 個 | ✅ 理想 | 基本功能測試 |
| **中等 Ticket** | 3-6 個 | ✅ 可接受 | 含邊界和異常測試 |
| **複雜 Ticket** | 6-10 個 | ⚠️ 需檢查 | 複雜邏輯，多測試案例 |
| **必須拆分** | > 10 個 | ❌ 禁止 | 測試過多，必須拆分 |

**強制規則**：
- ⚠️ **超過 10 個測試 = 必須拆分**
- ⚠️ **6-10 個測試 = 評估是否可拆分**
- ✅ **1-6 個測試 = 可接受範圍**

#### 測試數量實例

**實例 1：簡單 Ticket（1-3 個測試）**

```dart
// 任務：定義 Rating Value Object

void main() {
  group('Rating Value Object', () {
    test('建立有效評分', () {
      final rating = Rating(4);
      expect(rating.value, 4);
    });

    test('評分過低拋出異常', () {
      expect(() => Rating(0), throwsA(isA<ValidationException>()));
    });

    test('評分過高拋出異常', () {
      expect(() => Rating(6), throwsA(isA<ValidationException>()));
    });
  });
}

// 總計：3 個測試
// 判定：簡單 Ticket ✅
```

**實例 2：中等 Ticket（3-6 個測試）**

```dart
// 任務：實作 BookRepository.getBookByIsbn

void main() {
  group('BookRepository.getBookByIsbn', () {
    test('成功取得存在的書籍', () { ... });          // 測試 1
    test('書籍不存在回傳 null', () { ... });          // 測試 2
    test('無效 ISBN 拋出 ValidationException', () { ... }); // 測試 3
    test('資料庫錯誤拋出 StorageException', () { ... });    // 測試 4
    test('資料庫連線失敗拋出 NetworkException', () { ... }); // 測試 5
  });
}

// 總計：5 個測試
// 判定：中等 Ticket ✅
```

**實例 3：複雜 Ticket（6-10 個測試）- 建議拆分**

```dart
// 任務：實作完整的 BookRepository CRUD

void main() {
  group('BookRepository CRUD', () {
    // getBookByIsbn 測試
    test('取得存在的書籍', () { ... });              // 測試 1
    test('書籍不存在回傳 null', () { ... });         // 測試 2

    // saveBook 測試
    test('新增書籍成功', () { ... });                // 測試 3
    test('更新書籍成功', () { ... });                // 測試 4
    test('儲存時資料庫錯誤', () { ... });            // 測試 5

    // deleteBook 測試
    test('刪除存在的書籍', () { ... });              // 測試 6
    test('刪除不存在的書籍', () { ... });            // 測試 7
    test('刪除時資料庫錯誤', () { ... });            // 測試 8

    // Data Mapper 測試
    test('Entity 轉 DTO 正確', () { ... });          // 測試 9
    test('DTO 轉 Entity 正確', () { ... });          // 測試 10
  });
}

// 總計：10 個測試 ⚠️
// 判定：複雜 Ticket（達上限，建議拆分）
```

**拆分建議**：
```markdown
拆分為 3 個 Ticket：
- Ticket 1: getBookByIsbn + 測試（2 個測試）     ✅
- Ticket 2: saveBook + 測試（3 個測試）          ✅
- Ticket 3: deleteBook + Mapper + 測試（5 個測試）✅
```

---

### 1.5 指標整合評估方法

#### 整合評估原則

**最高等級原則**：
- 取 4 個指標中「最高的複雜度等級」作為最終評估結果
- 任一指標達到「必須拆分」，則整個 Ticket 必須拆分

**評估公式**：

```text
Ticket 複雜度 = max(職責複雜度, 行數複雜度, 檔案數複雜度, 測試數複雜度)

where 複雜度等級：
  簡單 = 1
  中等 = 2
  複雜 = 3
  必須拆分 = 4
```

#### 整合評估實例

**實例 1：所有指標都是簡單 → 簡單 Ticket**

```markdown
任務：定義 Rating Value Object

指標評估：
- 職責數量：1 個職責 → 簡單 ✅
- 程式碼行數：25 行 → 簡單 ✅
- 涉及檔案：1 個檔案 → 簡單 ✅
- 測試用例：3 個測試 → 簡單 ✅

最終判定：簡單 Ticket ✅（最理想狀態）
```

**實例 2：有一個指標是中等 → 中等 Ticket**

```markdown
任務：實作 Rating Value Object

指標評估：
- 職責數量：2 個職責（建立、驗證）→ 中等 ⚠️
- 程式碼行數：45 行 → 中等 ⚠️
- 涉及檔案：1 個檔案 → 簡單 ✅
- 測試用例：5 個測試 → 中等 ⚠️

最終判定：中等 Ticket ⚠️（可接受）
```

**實例 3：有一個指標是複雜 → 複雜 Ticket（建議拆分）**

```markdown
任務：實作 BookRepository.getBookByIsbn

指標評估：
- 職責數量：3 個職責（查詢、轉換、異常處理）→ 複雜 ⚠️⚠️
- 程式碼行數：65 行 → 中等 ⚠️
- 涉及檔案：2 個檔案 → 中等 ⚠️
- 測試用例：6 個測試 → 複雜 ⚠️⚠️

最終判定：複雜 Ticket ⚠️⚠️（建議拆分）
```

**實例 4：有任一指標超標 → 必須拆分**

```markdown
任務：實作完整的書籍評分功能

指標評估：
- 職責數量：8 個職責 → 必須拆分 ❌
- 程式碼行數：180 行 → 必須拆分 ❌
- 涉及檔案：7 個檔案 → 必須拆分 ❌
- 測試用例：15 個測試 → 必須拆分 ❌

最終判定：God Ticket ❌ 必須立即拆分
```

#### 評估決策流程

```text
步驟 1：計算 4 個指標
    ↓
步驟 2：取最高複雜度等級
    ↓
    ├─ 簡單 ✅ → 可直接建立 Ticket
    ├─ 中等 ⚠️ → 可直接建立 Ticket（可選：評估是否拆分為更小 Ticket）
    ├─ 複雜 ⚠️⚠️ → 強烈建議拆分（可選：無法拆分時勉強接受）
    └─ 必須拆分 ❌ → 阻止建立，必須先拆分再重新評估
```

**評估檢查清單**：

```markdown
□ 已計算 4 個指標的值
□ 已確定每個指標的複雜度等級
□ 已取最高複雜度等級作為最終判定
□ 如為「必須拆分」，已執行拆分並重新評估
□ 如為「複雜」，已評估是否可拆分為更小 Ticket
```

---

## 第二章：複雜度評估方法

### 2.1 複雜度等級定義

**4 級複雜度體系**：

| 等級 | 職責 | 行數 | 檔案 | 測試 | 描述 | 處理方式 |
|------|------|------|------|------|------|---------|
| **Level 1: 簡單** | 1 個 | < 30 行 | 1 個 | 1-3 個 | 單一職責，單一檔案 | ✅ 直接建立 Ticket |
| **Level 2: 中等** | 2-3 個 | 30-70 行 | 2-3 個 | 3-6 個 | 少數相關職責，少數檔案 | ✅ 直接建立 Ticket |
| **Level 3: 複雜** | 3-5 個 | 70-100 行 | 3-5 個 | 6-10 個 | 多職責，多檔案 | ⚠️ 建議拆分 |
| **Level 4: 超標** | > 5 個 | > 100 行 | > 5 個 | > 10 個 | 範圍失控 | ❌ 必須拆分 |

**複雜度特徵**：

**Level 1: 簡單**
- ✅ **特徵**: 最小可交付單元，職責明確
- ✅ **適用**: Interface 定義、單一 Value Object、單一方法實作
- ✅ **優點**: 風險低、易測試、易 Review
- ⏱️ **預估時間**: 5-20 分鐘

**Level 2: 中等**
- ✅ **特徵**: 少數相關職責，內聚性高
- ✅ **適用**: 含業務邏輯的 Entity、基礎 Repository 方法
- ⚠️ **注意**: 確保職責相關性，避免職責分散
- ⏱️ **預估時間**: 20-40 分鐘

**Level 3: 複雜**
- ⚠️ **特徵**: 多職責或跨檔案，整合性高
- ⚠️ **適用**: 完整 UseCase、Repository CRUD、複雜業務邏輯
- ⚠️ **風險**: 測試複雜、Review 困難、易出錯
- ⏱️ **預估時間**: 40-60 分鐘
- 💡 **建議**: 優先評估是否可拆分為 Level 1-2

**Level 4: 超標**
- ❌ **特徵**: 任一指標超標，範圍失控
- ❌ **問題**: God Ticket、高風險、難以管理
- ❌ **處理**: 必須拆分，無例外
- 🚫 **禁止**: 禁止建立此等級 Ticket

---

### 2.2 評估流程

**3 步驟評估流程**：

```text
步驟 1: 初步評估（基於任務描述）
    ↓
    計算 4 個指標的預估值
    ↓
步驟 2: 複雜度確認（取最高等級）
    ↓
    取 4 個指標中最高的複雜度等級
    ↓
步驟 3: 拆分決策（基於等級決定）
    ↓
    ├─ Level 1-2 ✅ → 可直接建立 Ticket
    ├─ Level 3 ⚠️ → 評估是否可拆分
    └─ Level 4 ❌ → 必須拆分
```

#### 步驟 1：初步評估

**目標**: 快速估算 4 個指標的值

**評估依據**:
1. 任務描述（What to do）
2. 驗收條件（Acceptance Criteria）
3. 預期步驟（Steps）

**評估方法**:

```markdown
範例任務：實作 Book Entity

步驟 1-1：估算職責數量
- 分析任務描述，列出所有需要完成的功能點
- 功能點 1：定義 Entity 欄位
- 功能點 2：實作 equals/hashCode
- 功能點 3：實作 toString
- 功能點 4：撰寫測試
→ 預估：4 個職責

步驟 1-2：估算程式碼行數
- 根據類似任務經驗估算
- Entity 定義：~30 行
- equals/hashCode：~15 行
- toString：~5 行
- 測試：~40 行
→ 預估：~90 行

步驟 1-3：估算檔案數量
- 列出需要建立/修改的檔案
- lib/domain/entities/book.dart（新增）
- test/unit/domain/entities/book_test.dart（新增）
→ 預估：2 個檔案（1 個生產 + 1 個測試）

步驟 1-4：估算測試數量
- 根據驗收條件估算測試案例
- 測試 Entity 建立
- 測試 equals（相等/不等）
- 測試 hashCode
- 測試 toString
→ 預估：5 個測試
```

#### 步驟 2：複雜度確認

**目標**: 確定最終複雜度等級

**確認方法**:

```text
對應 4 個指標到複雜度等級：

職責數量：4 個 → Level 3（複雜）⚠️⚠️
程式碼行數：90 行 → Level 3（複雜）⚠️⚠️
檔案數量：2 個（1 生產 + 1 測試）→ Level 2（中等）⚠️
測試數量：5 個 → Level 2（中等）⚠️

取最高等級：Level 3（複雜）⚠️⚠️
```

**確認檢查清單**:
```markdown
□ 已計算所有 4 個指標
□ 已對應每個指標到複雜度等級
□ 已確定最高複雜度等級
□ 已記錄評估依據
```

#### 步驟 3：拆分決策

**目標**: 決定是否拆分以及如何拆分

**決策規則**:

```text
Level 1-2 ✅ → 可直接建立 Ticket
    ├─ 無需拆分
    └─ 直接進入 Phase 2（測試設計）

Level 3 ⚠️ → 評估是否可拆分
    ├─ 可拆分為 Level 1-2 → 執行拆分
    └─ 無法拆分 → 勉強接受，加強 Review

Level 4 ❌ → 必須拆分
    ├─ 阻止建立 Ticket
    ├─ 執行拆分（使用第三章拆分策略）
    └─ 重新評估每個拆分後的子 Ticket
```

**Level 3 拆分評估**:

```markdown
範例：實作 Book Entity（Level 3）

拆分評估：
1. 是否可拆分為更小 Ticket？
   → 是，可拆分為兩個 Ticket

2. 如何拆分？
   Ticket A: 定義 Book Entity 欄位和基礎方法
   - 職責：定義欄位 + equals/hashCode
   - 行數：~45 行
   - 檔案：1 個
   - 測試：3 個
   → Level 2（中等）✅

   Ticket B: 補充 Book Entity 完整功能
   - 職責：toString + 完整測試
   - 行數：~45 行
   - 檔案：1 個（修改）
   - 測試：2 個
   → Level 1（簡單）✅

3. 拆分後依賴關係？
   → Ticket B 依賴 Ticket A（B 在 A 完成後執行）

4. 拆分價值評估？
   → ✅ 降低風險：兩個 Level 1-2 比一個 Level 3 更易管理
   → ✅ 易於 Review：分兩次 Review，每次範圍更小
   → ⚠️ 成本：增加一個 Ticket，但風險降低值得

結論：建議拆分
```

**Level 4 拆分處理**:

```markdown
範例：實作完整書籍評分功能（Level 4）

當前狀態：
- 職責：8 個 → Level 4 ❌
- 行數：180 行 → Level 4 ❌
- 檔案：7 個 → Level 4 ❌
- 測試：15 個 → Level 4 ❌

拆分決策：必須拆分（無選項）

拆分方式：使用「基於 Clean Architecture 分層拆分策略」（詳見第三章）
```

---

### 2.3 評估決策樹

**完整決策流程圖**:

```text
[開始評估]
    ↓
[計算 4 個指標]
    ↓
[取最高複雜度等級]
    ↓
    ├─ Level 1（簡單）
    │   ↓
    │   [✅ 可直接建立 Ticket]
    │   ↓
    │   [進入 Phase 2：測試設計]
    │
    ├─ Level 2（中等）
    │   ↓
    │   [✅ 可直接建立 Ticket]
    │   ↓
    │   [（可選）評估是否拆分為更小 Ticket]
    │   ↓
    │   [進入 Phase 2：測試設計]
    │
    ├─ Level 3（複雜）
    │   ↓
    │   [⚠️ 評估是否可拆分]
    │   ↓
    │   ├─ 可拆分？
    │   │   ├─ Yes → [執行拆分]
    │   │   │           ↓
    │   │   │       [重新評估子 Ticket]
    │   │   │           ↓
    │   │   │       [確保所有子 Ticket 為 Level 1-2]
    │   │   │
    │   │   └─ No → [勉強接受]
    │   │              ↓
    │   │          [標記為高風險 Ticket]
    │   │              ↓
    │   │          [加強 Review 機制]
    │   │              ↓
    │   │          [進入 Phase 2]
    │
    └─ Level 4（超標）
        ↓
        [❌ 禁止建立 Ticket]
        ↓
        [阻止進入 Phase 2]
        ↓
        [必須拆分（使用第三章策略）]
        ↓
        [重新評估所有子 Ticket]
        ↓
        [確保所有子 Ticket ≤ Level 3]
```

**決策節點詳細說明**:

**節點 1：Level 3 拆分評估**
```text
問題：此 Ticket 是否可拆分為更小 Ticket？

評估準則：
1. 職責是否可分離？
   - 是否包含多個獨立功能點？
   - 是否可按照 Clean Architecture 分層拆分？

2. 拆分後是否降低複雜度？
   - 拆分後每個子 Ticket 是否 ≤ Level 2？
   - 是否減少單一 Ticket 的風險？

3. 拆分成本是否合理？
   - 增加的管理成本 vs 降低的風險
   - 是否需要額外的整合測試？

決策：
- 滿足 1 且 2 → 建議拆分
- 不滿足 1 或 2，但 3 成本高 → 勉強接受 Level 3
```

**節點 2：Level 4 強制拆分**
```text
Level 4 無需評估，必須拆分

拆分方法（按優先順序）：
1. 優先：按 Clean Architecture 分層拆分（詳見第三章 3.1-3.4）
2. 次之：按職責拆分（每個職責獨立 Ticket）
3. 最後：按檔案拆分（每個檔案獨立 Ticket）

拆分要求：
- 所有子 Ticket 必須 ≤ Level 3
- 建議所有子 Ticket ≤ Level 2
- 理想所有子 Ticket = Level 1

拆分後驗證：
□ 所有子 Ticket 都已重新評估
□ 所有子 Ticket 都 ≤ Level 3
□ 子 Ticket 依賴關係明確
□ 子 Ticket 總和涵蓋原始 Ticket 所有功能
```

---

### 2.4 複雜度評估實例

**完整評估案例**：

#### 案例 1：簡單 Ticket 評估

```markdown
任務：定義 IBookRepository 介面

步驟 1：初步評估
- 職責數量：1 個（定義介面方法簽名）
- 程式碼行數：~20 行
- 涉及檔案：1 個（i_book_repository.dart）
- 測試數量：0 個（Interface 不需測試）

步驟 2：複雜度確認
- 職責：1 個 → Level 1 ✅
- 行數：20 行 → Level 1 ✅
- 檔案：1 個 → Level 1 ✅
- 測試：0 個 → Level 1 ✅
→ 最高等級：Level 1

步驟 3：拆分決策
- Level 1 → ✅ 可直接建立 Ticket
- 無需拆分
- 進入 Phase 2
```

#### 案例 2：中等 Ticket 評估

```markdown
任務：實作 Rating Value Object

步驟 1：初步評估
- 職責數量：2 個（建立 + 驗證）
- 程式碼行數：~50 行（含測試）
- 涉及檔案：1 個（rating.dart）
- 測試數量：5 個

步驟 2：複雜度確認
- 職責：2 個 → Level 2 ⚠️
- 行數：50 行 → Level 2 ⚠️
- 檔案：1 個 → Level 1 ✅
- 測試：5 個 → Level 2 ⚠️
→ 最高等級：Level 2

步驟 3：拆分決策
- Level 2 → ✅ 可直接建立 Ticket
- 評估：可選拆分，但不必要（職責內聚性高）
- 進入 Phase 2
```

#### 案例 3：複雜 Ticket 評估與拆分

```markdown
任務：實作 BookRepository CRUD

步驟 1：初步評估
- 職責數量：5 個（get + save + delete + mapper + 錯誤處理）
- 程式碼行數：~160 行（含測試）
- 涉及檔案：2 個（repository.dart + mapper.dart）
- 測試數量：10 個

步驟 2：複雜度確認
- 職責：5 個 → Level 3 ⚠️⚠️
- 行數：160 行 → Level 4 ❌（超過 100 行）
- 檔案：2 個 → Level 2 ⚠️
- 測試：10 個 → Level 3 ⚠️⚠️
→ 最高等級：Level 4（行數超標）

步驟 3：拆分決策
- Level 4 → ❌ 必須拆分
- 拆分方式：按 CRUD 方法拆分

  Ticket A: 實作 getBookByIsbn
  - 職責：2 個（查詢 + 轉換）
  - 行數：~50 行
  - 檔案：2 個
  - 測試：3 個
  → Level 2 ✅

  Ticket B: 實作 saveBook
  - 職責：2 個（儲存 + 錯誤處理）
  - 行數：~60 行
  - 檔案：1 個（修改 repository.dart）
  - 測試：4 個
  → Level 2 ✅

  Ticket C: 實作 deleteBook
  - 職責：2 個（刪除 + 錯誤處理）
  - 行數：~50 行
  - 檔案：1 個（修改 repository.dart）
  - 測試：3 個
  → Level 2 ✅

結果：拆分為 3 個 Level 2 Ticket ✅
```

#### 案例 4：God Ticket 評估與拆分

```markdown
任務：實作完整書籍評分功能（UI + UseCase + Repository）

步驟 1：初步評估
- 職責數量：8 個（UI + Controller + UseCase + Entity + Repository + Mapper + 測試 + 整合）
- 程式碼行數：~300 行
- 涉及檔案：8 個（跨 4 個架構層級）
- 測試數量：20 個

步驟 2：複雜度確認
- 職責：8 個 → Level 4 ❌
- 行數：300 行 → Level 4 ❌
- 檔案：8 個 → Level 4 ❌
- 測試：20 個 → Level 4 ❌
→ 最高等級：Level 4（所有指標都超標）

步驟 3：拆分決策
- Level 4 → ❌ 必須拆分（God Ticket）
- 拆分方式：使用 Clean Architecture 分層拆分策略

  Ticket 1: Domain 層實作（Layer 5）
  - Rating Entity + Rating Value Object
  - 職責：2 個
  - 行數：~60 行
  - 檔案：2 個
  - 測試：6 個
  → Level 2 ✅

  Ticket 2: Repository 層實作（Layer 4-5 Interface + Infra）
  - IRatingRepository + SQLiteRatingRepository + Mapper
  - 職責：3 個
  - 行數：~90 行
  - 檔案：3 個
  - 測試：8 個
  → Level 3 ⚠️（可接受）

  Ticket 3: UseCase 層實作（Layer 3）
  - RateBookUseCase
  - 職責：2 個
  - 行數：~60 行
  - 檔案：1 個
  - 測試：4 個
  → Level 2 ✅

  Ticket 4: Presentation 層實作（Layer 1-2）
  - RatingWidget + RatingController
  - 職責：2 個
  - 行數：~90 行
  - 檔案：2 個
  - 測試：4 個（Widget 測試）
  → Level 2 ✅

結果：拆分為 4 個 Ticket（3 個 Level 2 + 1 個 Level 3）✅
依賴順序：Ticket 1 → Ticket 2 → Ticket 3 → Ticket 4
```

---

## 第三章：Clean Architecture 分層拆分策略

### 為什麼需要基於架構分層拆分

**架構分層拆分的核心價值**:

1. **單層修改原則**（Single Layer Modification Principle）
   - ✅ 每個 Ticket 專注於單一架構層級
   - ✅ 降低跨層依賴帶來的複雜度
   - ✅ 提升程式碼審查效率

2. **依賴方向一致性**
   - ✅ 遵循 Clean Architecture 依賴規則（內層不依賴外層）
   - ✅ 避免循環依賴
   - ✅ 確保架構穩定性

3. **測試可獨立性**
   - ✅ 每層有明確的測試策略
   - ✅ 可獨立測試不依賴其他層
   - ✅ 簡化 Mock 和 Stub

**本章內容結構**:

```text
3.1 Clean Architecture 五層架構回顧
    └── 快速回顧五層架構和依賴規則
3.2 四種標準拆分策略
    ├── 策略 1: Interface 定義 Ticket
    ├── 策略 2: 具體實作 Ticket
    ├── 策略 3: 測試驗證 Ticket
    └── 策略 4: 整合連接 Ticket
3.3 分層拆分決策指引
    └── 如何選擇合適的拆分策略
3.4 分層拆分實務案例
    └── 完整的書籍評分功能拆分範例
```

---

### 3.1 Clean Architecture 五層架構回顧

**五層架構定義**（引用自 Clean Architecture 實作方法論）:

```text
Layer 1 (UI - 最外層)
├── 職責: 使用者介面元件
├── 路徑: lib/presentation/widgets/, lib/presentation/pages/
├── 依賴: Layer 2 (Behavior)
└── 不依賴: Layer 3-5

Layer 2 (Behavior)
├── 職責: UI 行為控制（State Management）
├── 路徑: lib/presentation/controllers/, lib/presentation/providers/
├── 依賴: Layer 3 (UseCase)
└── 不依賴: Layer 1, 4-5

Layer 3 (UseCase)
├── 職責: 業務用例協調
├── 路徑: lib/application/use_cases/, lib/application/services/
├── 依賴: Layer 4-5 (Domain)
└── 不依賴: Layer 1-2

Layer 4 (Domain Events/Interfaces)
├── 職責: 領域事件和介面定義
├── 路徑: lib/domain/events/, lib/domain/repositories/ (介面)
├── 依賴: Layer 5 (Domain Implementation)
└── 不依賴: Layer 1-3

Layer 5 (Domain Implementation - 最內層)
├── 職責: 領域模型實作和基礎設施
├── 路徑: lib/domain/entities/, lib/domain/value_objects/, lib/infrastructure/
├── 依賴: 無（核心層）
└── 不依賴: 任何層
```

**依賴規則（Dependency Rule）**:

```text
外層 → 內層 ✅ 允許
內層 → 外層 ❌ 禁止

範例：
- Layer 2 (Behavior) → Layer 3 (UseCase) ✅
- Layer 3 (UseCase) → Layer 2 (Behavior) ❌
```

**單層修改原則**:

- ✅ **理想**: 每個 Ticket 只修改單一層級
- ⚠️ **可接受**: Ticket 修改相鄰兩層（如 Interface + Implementation）
- ❌ **禁止**: Ticket 跨越超過 2 層（如 UI → Domain 直接跨越）

---

### 3.2 四種標準拆分策略

#### 策略 1：Interface 定義 Ticket

**定義**: 定義一個介面及其輸入輸出契約。

**適用層級**: 主要用於 Layer 4 (Domain Interfaces)

**職責範圍**:
- ✅ 定義 Interface 簽名
- ✅ 定義輸入參數類型
- ✅ 定義回傳類型
- ✅ 撰寫文檔註解（含業務需求編號）

**禁止包含**:
- ❌ 具體實作邏輯
- ❌ 資料庫操作
- ❌ 業務邏輯

**Ticket 範本**:

```markdown
## Ticket #NNN: 定義 {Interface 名稱} 介面

### 業務需求
[引用業務需求編號，如 REQ-001]

### 目標
建立 `{Interface 名稱}` 介面，定義 {業務功能} 的契約

### 步驟
1. 在 `lib/domain/repositories/` 建立 `{interface_file}.dart`
2. 定義 `{method1}` 方法簽名
3. 定義 `{method2}` 方法簽名
4. 撰寫文檔註解（含需求編號）

### 驗收條件
- [ ] Interface 檔案建立在正確位置
- [ ] 所有方法簽名完整且明確
- [ ] 輸入輸出類型定義清楚
- [ ] 包含完整的文檔註解（含需求編號）
- [ ] dart analyze 0 錯誤
```

**實務範例**:

```markdown
## Ticket #101: 定義 IBookRepository 介面

### 業務需求
REQ-LIB-001: 書籍資料存取功能

### 目標
建立 `IBookRepository` 介面，定義書籍資料存取的契約

### 步驟
1. 在 `lib/domain/repositories/` 建立 `i_book_repository.dart`
2. 定義 `getBookByIsbn` 方法簽名
   ```dart
   /// [REQ-LIB-001.1] 根據 ISBN 查詢書籍
   ///
   /// 參數:
   /// - isbn: 書籍 ISBN 編號
   ///
   /// 回傳:
   /// - Book 物件（存在）或 null（不存在）
   Future<Book?> getBookByIsbn(String isbn);
   ```
3. 定義 `saveBook` 方法簽名
4. 定義 `deleteBook` 方法簽名
5. 撰寫文檔註解

### 驗收條件
- [ ] Interface 檔案建立在 `lib/domain/repositories/`
- [ ] 3 個方法簽名完整且明確
- [ ] 輸入輸出類型定義清楚
- [ ] 包含完整的文檔註解（含需求編號）
- [ ] dart analyze 0 錯誤

### 指標評估
- 職責: 1 個（定義介面）
- 行數: ~25 行
- 檔案: 1 個
- 測試: 0 個（Interface 不需單元測試）
→ Level 1（簡單）✅
```

---

#### 策略 2：具體實作 Ticket

**定義**: 實作一個類別的核心邏輯。

**適用層級**:
- Layer 5 (Domain Implementation): Entity, Value Object
- Layer 5 (Infrastructure): Repository 實作, Service 實作

**職責範圍**:
- ✅ 實作類別邏輯
- ✅ 實現介面方法
- ✅ 處理異常
- ✅ 撰寫單元測試

**禁止包含**:
- ❌ UI 元件
- ❌ 跨層整合（如直接呼叫 UseCase）
- ❌ 測試以外的其他層修改

**Ticket 範本**:

```markdown
## Ticket #NNN: 實作 {類別名稱}

### 業務需求
[引用業務需求編號]

### 目標
實作 `{類別名稱}`，提供 {業務功能} 的具體實現

### 依賴 Ticket
- Ticket #XXX: 定義 {Interface 名稱} 介面（必須先完成）

### 步驟
1. 建立 `{類別名稱}` 類別（實作 `{Interface}`）
2. 實作 `{method1}` 方法
3. 實作 `{method2}` 方法
4. 處理異常情況
5. 撰寫單元測試（正常流程 + 異常處理）
6. 確保所有測試通過

### 驗收條件
- [ ] 實作所有 Interface 方法
- [ ] 異常處理完整
- [ ] 單元測試 100% 通過
- [ ] 測試覆蓋正常流程和異常處理
- [ ] dart analyze 0 錯誤
```

**實務範例**:

```markdown
## Ticket #102: 實作 SQLiteBookRepository

### 業務需求
REQ-LIB-001: 書籍資料存取功能

### 目標
實作 `SQLiteBookRepository`，提供書籍資料的 SQLite 儲存

### 依賴 Ticket
- Ticket #101: 定義 IBookRepository 介面（必須先完成）

### 步驟
1. 在 `lib/infrastructure/repositories/` 建立 `sqlite_book_repository.dart`
2. 實作 `getBookByIsbn` 方法
   - SQL 查詢邏輯
   - Data Mapper 轉換（DTO → Entity）
   - 錯誤處理（Database Exception）
3. 實作 `saveBook` 方法
   - SQL 插入/更新邏輯
   - Data Mapper 轉換（Entity → DTO）
   - 錯誤處理
4. 實作 `deleteBook` 方法
5. 撰寫單元測試
   - 正常流程：CRUD 操作成功
   - 異常處理：資料庫錯誤、資料不存在
6. 確保所有測試通過

### 驗收條件
- [ ] 實作所有 IBookRepository 方法
- [ ] 異常處理完整（DatabaseException, ValidationException）
- [ ] 單元測試 100% 通過（至少 6 個測試案例）
- [ ] dart analyze 0 錯誤

### 指標評估
- 職責: 3 個（CRUD 實作、Mapper、異常處理）
- 行數: ~80 行（含測試）
- 檔案: 1 個
- 測試: 6 個
→ Level 2（中等）✅
```

---

#### 策略 3：測試驗證 Ticket

**定義**: 撰寫一組相關的測試用例，補強現有實作的測試覆蓋率。

**適用時機**:
- 現有實作缺乏完整測試
- 需要補充邊界測試和異常測試
- TDD 紅綠燈循環中的「紅燈」階段

**職責範圍**:
- ✅ 撰寫單元測試
- ✅ 覆蓋正常流程
- ✅ 覆蓋邊界條件
- ✅ 覆蓋異常處理
- ✅ 確保測試通過

**禁止包含**:
- ❌ 修改生產程式碼（除非是修正測試發現的 Bug）
- ❌ 新增功能
- ❌ 重構（測試 Ticket 專注於驗證，不做重構）

**Ticket 範本**:

```markdown
## Ticket #NNN: 撰寫 {功能} 測試

### 業務需求
[引用業務需求編號]

### 目標
撰寫 `{類別名稱}` 的完整測試用例，確保 {業務功能} 正確性

### 依賴 Ticket
- Ticket #XXX: 實作 {類別名稱}（必須先完成）

### 步驟
1. 建立測試檔案 `{class}_test.dart`
2. 撰寫正常流程測試
3. 撰寫邊界條件測試
4. 撰寫異常處理測試
5. 確保所有測試通過

### 驗收條件
- [ ] 測試檔案建立在正確位置
- [ ] 至少 N 個測試用例
- [ ] 覆蓋正常流程、邊界條件和異常處理
- [ ] 所有測試 100% 通過
```

**實務範例**:

```markdown
## Ticket #103: 撰寫 BookRepository 整合測試

### 業務需求
REQ-LIB-001: 書籍資料存取功能

### 目標
撰寫 `BookRepository` 的整合測試，驗證資料庫操作正確性

### 依賴 Ticket
- Ticket #102: 實作 SQLiteBookRepository（必須先完成）

### 步驟
1. 建立測試檔案 `test/integration/repositories/book_repository_test.dart`
2. 撰寫 `getBookByIsbn` 測試
   - 測試 1: 成功取得存在的書籍
   - 測試 2: 書籍不存在回傳 null
   - 測試 3: 無效 ISBN 拋出異常
3. 撰寫 `saveBook` 測試
   - 測試 4: 新增書籍成功
   - 測試 5: 更新現有書籍成功
4. 撰寫 `deleteBook` 測試
   - 測試 6: 刪除存在的書籍
   - 測試 7: 刪除不存在的書籍無異常
5. 確保所有測試通過

### 驗收條件
- [ ] 測試檔案建立在 `test/integration/repositories/`
- [ ] 至少 7 個整合測試案例
- [ ] 覆蓋正常流程和異常處理
- [ ] 所有測試 100% 通過

### 指標評估
- 職責: 1 個（撰寫測試）
- 行數: ~60 行（純測試）
- 檔案: 1 個（測試檔案）
- 測試: 7 個
→ Level 2（中等）✅
```

---

#### 策略 4：整合連接 Ticket

**定義**: 連接兩個模組並驗證整合，實現端到端流程。

**適用時機**:
- 需要連接 Layer 3 (UseCase) 和 Layer 5 (Repository)
- 需要連接 Layer 2 (Controller) 和 Layer 3 (UseCase)
- 完成分層實作後的整合階段

**職責範圍**:
- ✅ 連接 Use Case 和 Repository
- ✅ 實作依賴注入
- ✅ 撰寫整合測試
- ✅ 驗證端到端流程

**禁止包含**:
- ❌ 修改核心業務邏輯（應在具體實作 Ticket 完成）
- ❌ 跨越超過 2 層的整合
- ❌ UI 實作（應獨立為 Presentation 層 Ticket）

**Ticket 範本**:

```markdown
## Ticket #NNN: 整合 {UseCase} 到 {Repository}

### 業務需求
[引用業務需求編號]

### 目標
將 `{Repository}` 整合到 `{UseCase}`，實現 {業務功能} 完整流程

### 依賴 Ticket
- Ticket #XXX: 定義 {Interface}（必須先完成）
- Ticket #YYY: 實作 {Repository}（必須先完成）

### 步驟
1. 修改 `{UseCase}` 注入 `{Interface}`
2. 在 `execute` 方法中呼叫 Repository 方法
3. 處理 Repository 異常
4. 撰寫整合測試驗證端到端流程
5. 確保所有測試通過

### 驗收條件
- [ ] `{UseCase}` 正確注入 `{Interface}`
- [ ] 端到端流程正常運作
- [ ] 整合測試 100% 通過
- [ ] 異常處理完整
```

**實務範例**:

```markdown
## Ticket #104: 整合 BookRepository 到 GetBookUseCase

### 業務需求
REQ-LIB-001: 書籍查詢功能

### 目標
將 `BookRepository` 整合到 `GetBookUseCase`，實現完整書籍查詢流程

### 依賴 Ticket
- Ticket #101: 定義 IBookRepository 介面（必須先完成）
- Ticket #102: 實作 SQLiteBookRepository（必須先完成）

### 步驟
1. 修改 `GetBookInteractor` 注入 `IBookRepository`
   ```dart
   class GetBookInteractor implements GetBookUseCase {
     final IBookRepository _repository;

     GetBookInteractor(this._repository);

     @override
     Future<Book?> execute(String isbn) async {
       // 呼叫 Repository
     }
   }
   ```
2. 在 `execute` 方法中呼叫 `repository.getBookByIsbn`
3. 處理 Repository 異常（ValidationException, StorageException）
4. 撰寫整合測試
   - 測試 1: 成功查詢書籍
   - 測試 2: 書籍不存在
   - 測試 3: Repository 異常處理
5. 確保所有測試通過

### 驗收條件
- [ ] `GetBookInteractor` 正確注入 `IBookRepository`
- [ ] 端到端流程正常運作
- [ ] 整合測試 100% 通過（至少 3 個測試案例）
- [ ] 異常處理完整

### 指標評估
- 職責: 2 個（注入、整合）
- 行數: ~50 行（含測試）
- 檔案: 1 個（修改 UseCase）
- 測試: 3 個
→ Level 2（中等）✅
```

---

### 3.3 分層拆分決策指引

**決策流程圖**:

```text
[分析 Ticket 涉及的架構層級]
    ↓
    ├─ 單層修改？
    │   ├─ Yes → 選擇對應策略
    │   │   ├─ Layer 4 Interface → 策略 1: Interface 定義
    │   │   ├─ Layer 5 Implementation → 策略 2: 具體實作
    │   │   └─ 補充測試 → 策略 3: 測試驗證
    │   │
    │   └─ No → 跨層修改？
    │       ├─ 相鄰兩層整合 → 策略 4: 整合連接
    │       └─ 跨越超過 2 層 → ❌ 必須拆分為多個 Ticket
```

**決策準則**:

**準則 1: 優先單層修改**
```markdown
問題: Ticket 是否只修改單一架構層級？

- ✅ Yes → 選擇策略 1-3（Interface / 實作 / 測試）
- ❌ No → 評估是否可拆分為多個單層 Ticket
```

**準則 2: 相鄰層整合可接受**
```markdown
問題: 是否為相鄰兩層的整合？

範例：
- Layer 3 (UseCase) + Layer 4-5 (Repository) ✅ 可接受
- Layer 2 (Controller) + Layer 3 (UseCase) ✅ 可接受
- Layer 1 (UI) + Layer 5 (Domain) ❌ 禁止（跨越太多層）

決策：
- 相鄰兩層整合 → 策略 4: 整合連接
- 跨越超過 2 層 → 必須拆分為多個 Ticket
```

**準則 3: Interface 先行**
```markdown
原則: Interface 定義必須先於實作

範例拆分順序：
1. Ticket A: 定義 IBookRepository（策略 1）
2. Ticket B: 實作 SQLiteBookRepository（策略 2）
3. Ticket C: 整合到 GetBookUseCase（策略 4）

依賴關係: Ticket C 依賴 B，B 依賴 A
```

**準則 4: 測試獨立或整合**
```markdown
問題: 測試應該獨立 Ticket 還是整合到實作 Ticket？

決策：
- 實作 Ticket < Level 2 → 整合測試到實作 Ticket ✅
- 實作 Ticket = Level 2-3 → 可選擇獨立測試 Ticket
- 測試案例 > 10 個 → 必須獨立測試 Ticket（策略 3）
```

---

### 3.4 分層拆分實務案例

**完整案例：書籍評分功能實作**

#### 原始 God Ticket 分析

```markdown
原始任務: 實作完整書籍評分功能（UI + UseCase + Repository）

指標評估:
- 職責: 8 個
- 行數: ~300 行
- 檔案: 8 個
- 測試: 20 個
→ Level 4（所有指標都超標）❌ 必須拆分
```

#### 分層拆分方案

**拆分為 6 個 Ticket（按 Clean Architecture 分層）**:

---

**Ticket 1: 定義 Rating Domain 模型（Layer 5 - Domain Implementation）**

```markdown
## Ticket #201: 定義 Rating Value Object

### 層級: Layer 5 (Domain Implementation)
### 策略: 策略 2（具體實作）

### 業務需求
REQ-RATING-001: 書籍評分功能

### 目標
建立 `Rating` Value Object，封裝評分規則（1-5 分）

### 步驟
1. 建立 `lib/domain/value_objects/rating.dart`
2. 實作 Rating 類別
   - 建構子驗證（1-5 分）
   - equals / hashCode
   - toString
3. 撰寫單元測試（正常、邊界、異常）
4. 確保測試通過

### 驗收條件
- [ ] Rating 類別實作完整
- [ ] 驗證邏輯正確（1-5 分）
- [ ] 單元測試 100% 通過（至少 5 個測試）
- [ ] dart analyze 0 錯誤

### 指標評估
- 職責: 1 個
- 行數: ~50 行
- 檔案: 1 個
- 測試: 5 個
→ Level 2（中等）✅
```

---

**Ticket 2: 定義 Rating Entity（Layer 5 - Domain Implementation）**

```markdown
## Ticket #202: 定義 Rating Entity

### 層級: Layer 5 (Domain Implementation)
### 策略: 策略 2（具體實作）
### 依賴: Ticket #201（Rating Value Object）

### 業務需求
REQ-RATING-001: 書籍評分功能

### 目標
建立 `Rating` Entity，包含評分和評論資訊

### 步驟
1. 建立 `lib/domain/entities/rating.dart`
2. 實作 Rating Entity
   - 欄位: ratingValue (Rating VO), comment (String), userId, bookIsbn
   - equals / hashCode
3. 撰寫單元測試
4. 確保測試通過

### 驗收條件
- [ ] Rating Entity 實作完整
- [ ] 使用 Rating Value Object
- [ ] 單元測試 100% 通過（至少 3 個測試）
- [ ] dart analyze 0 錯誤

### 指標評估
- 職責: 1 個
- 行數: ~40 行
- 檔案: 1 個
- 測試: 3 個
→ Level 1（簡單）✅
```

---

**Ticket 3: 定義 IRatingRepository 介面（Layer 4 - Domain Interfaces）**

```markdown
## Ticket #203: 定義 IRatingRepository 介面

### 層級: Layer 4 (Domain Interfaces)
### 策略: 策略 1（Interface 定義）

### 業務需求
REQ-RATING-001: 書籍評分功能

### 目標
建立 `IRatingRepository` 介面，定義評分資料存取契約

### 步驟
1. 建立 `lib/domain/repositories/i_rating_repository.dart`
2. 定義 `saveRating` 方法簽名
3. 定義 `getRatingsByBookIsbn` 方法簽名
4. 撰寫文檔註解

### 驗收條件
- [ ] Interface 檔案建立在正確位置
- [ ] 2 個方法簽名完整
- [ ] 文檔註解包含需求編號
- [ ] dart analyze 0 錯誤

### 指標評估
- 職責: 1 個
- 行數: ~20 行
- 檔案: 1 個
- 測試: 0 個
→ Level 1（簡單）✅
```

---

**Ticket 4: 實作 SQLiteRatingRepository（Layer 5 - Infrastructure）**

```markdown
## Ticket #204: 實作 SQLiteRatingRepository

### 層級: Layer 5 (Infrastructure)
### 策略: 策略 2（具體實作）
### 依賴: Ticket #202, #203

### 業務需求
REQ-RATING-001: 書籍評分功能

### 目標
實作 `SQLiteRatingRepository`，提供評分資料的 SQLite 儲存

### 步驟
1. 建立 `lib/infrastructure/repositories/sqlite_rating_repository.dart`
2. 實作 `saveRating` 方法
   - SQL 插入邏輯
   - Data Mapper 轉換
   - 錯誤處理
3. 實作 `getRatingsByBookIsbn` 方法
4. 撰寫單元測試（CRUD + 異常）
5. 確保測試通過

### 驗收條件
- [ ] 實作所有 IRatingRepository 方法
- [ ] 異常處理完整
- [ ] 單元測試 100% 通過（至少 6 個測試）
- [ ] dart analyze 0 錯誤

### 指標評估
- 職責: 3 個（CRUD、Mapper、異常）
- 行數: ~90 行
- 檔案: 1 個
- 測試: 6 個
→ Level 3（複雜）⚠️ 可接受
```

---

**Ticket 5: 實作 RateBookUseCase（Layer 3 - UseCase）**

```markdown
## Ticket #205: 實作 RateBookUseCase

### 層級: Layer 3 (UseCase)
### 策略: 策略 4（整合連接）
### 依賴: Ticket #203, #204

### 業務需求
REQ-RATING-001: 書籍評分功能

### 目標
實作 `RateBookUseCase`，協調書籍評分業務流程

### 步驟
1. 建立 `lib/application/use_cases/rate_book_use_case.dart`
2. 注入 `IRatingRepository`
3. 實作 `execute` 方法
   - 建立 Rating Entity
   - 呼叫 Repository 儲存
   - 處理異常
4. 撰寫整合測試
5. 確保測試通過

### 驗收條件
- [ ] UseCase 正確注入 IRatingRepository
- [ ] 業務流程完整
- [ ] 整合測試 100% 通過（至少 4 個測試）
- [ ] 異常處理完整
- [ ] dart analyze 0 錯誤

### 指標評估
- 職責: 2 個（協調、整合）
- 行數: ~60 行
- 檔案: 1 個
- 測試: 4 個
→ Level 2（中等）✅
```

---

**Ticket 6: 實作 RatingWidget UI（Layer 1-2 - Presentation）**

```markdown
## Ticket #206: 實作 RatingWidget 和 RatingController

### 層級: Layer 1 (UI) + Layer 2 (Behavior)
### 策略: 策略 2 + 策略 4（實作 + 整合）
### 依賴: Ticket #205

### 業務需求
REQ-RATING-001: 書籍評分功能

### 目標
實作評分 UI 元件和行為控制

### 步驟
1. 建立 `lib/presentation/widgets/rating_widget.dart`
2. 實作 RatingWidget（5 星評分 UI）
3. 建立 `lib/presentation/controllers/rating_controller.dart`
4. 實作 RatingController
   - 注入 RateBookUseCase
   - 呼叫 UseCase 評分
   - 狀態管理
5. 撰寫 Widget 測試
6. 確保測試通過

### 驗收條件
- [ ] RatingWidget UI 正確顯示
- [ ] RatingController 正確整合 UseCase
- [ ] Widget 測試 100% 通過（至少 4 個測試）
- [ ] dart analyze 0 錯誤

### 指標評估
- 職責: 2 個（UI、Controller）
- 行數: ~80 行
- 檔案: 2 個
- 測試: 4 個
→ Level 2（中等）✅
```

---

#### 拆分結果總結

**拆分前後對比**:

| 項目 | 拆分前（God Ticket）| 拆分後（6 個 Ticket）|
|------|-------------------|-------------------|
| 職責數量 | 8 個 ❌ | 平均 1.7 個 ✅ |
| 程式碼行數 | ~300 行 ❌ | 平均 57 行 ✅ |
| 檔案數量 | 8 個 ❌ | 平均 1.2 個 ✅ |
| 測試數量 | 20 個 ❌ | 平均 4 個 ✅ |
| 複雜度等級 | Level 4 ❌ | 5 個 Level 1-2 ✅<br>1 個 Level 3 ⚠️ |

**拆分效益**:
- ✅ **風險降低**: 從 1 個高風險任務 → 6 個低風險任務
- ✅ **並行開發**: 可 2-3 人同時開發不同層級
- ✅ **易於 Review**: 每個 PR 範圍小，Review 時間縮短
- ✅ **依賴明確**: 清楚的 Ticket 依賴順序
- ✅ **測試獨立**: 每層可獨立測試，Mock 簡單

**執行順序**:
```text
Phase 1（可並行）:
├─ Ticket #201: Rating Value Object
└─ Ticket #202: Rating Entity （依賴 #201）

Phase 2（可並行）:
├─ Ticket #203: IRatingRepository Interface
└─ Ticket #204: SQLiteRatingRepository （依賴 #202, #203）

Phase 3:
└─ Ticket #205: RateBookUseCase （依賴 #204）

Phase 4:
└─ Ticket #206: RatingWidget UI （依賴 #205）
```

---

## 第四章：Ticket 大小標準與範例

### 4.1 簡單 Ticket 標準與範例（Level 1）

**Level 1 特徵**：
- 職責：1 個明確職責
- 行數：< 30 行
- 檔案：1 個
- 測試：1-3 個

**適用場景**：
- ✅ Interface 定義
- ✅ 單一 Value Object
- ✅ 單一方法實作
- ✅ 簡單配置修改

---

#### 範例 1：定義 IBookRepository 介面

```markdown
## Ticket #1: 定義 IBookRepository 介面

### 層級：Layer 4 (Domain Interfaces)

### 業務需求
REQ-LIB-001: 書籍資料存取功能

### 目標
建立 `IBookRepository` 介面，定義書籍資料存取的契約

### 步驟
1. 在 `lib/domain/repositories/` 建立 `i_book_repository.dart`
2. 定義 `getBookByIsbn(String isbn)` 方法簽名
3. 定義 `saveBook(Book book)` 方法簽名
4. 定義 `deleteBook(String isbn)` 方法簽名
5. 撰寫文檔註解（含需求編號）

### 驗收條件
- [ ] Interface 檔案建立在 `lib/domain/repositories/`
- [ ] 3 個方法簽名完整且明確
- [ ] 輸入輸出類型定義清楚
- [ ] 文檔註解包含需求編號 REQ-LIB-001
- [ ] dart analyze 0 錯誤

### 指標評估
- 職責數量：1 個（定義介面契約）
- 程式碼行數：~20 行
- 涉及檔案：1 個
- 測試用例：0 個（Interface 不需單元測試）
→ Level 1（簡單）✅

### 預估時間
10-15 分鐘
```

---

#### 範例 2：建立 Rating Value Object

```markdown
## Ticket #2: 建立 Rating Value Object

### 層級：Layer 5 (Domain Implementation)

### 業務需求
REQ-RATING-001: 書籍評分功能

### 目標
建立 `Rating` Value Object，封裝評分規則（1-5 分）

### 步驟
1. 在 `lib/domain/value_objects/` 建立 `rating.dart`
2. 實作 Rating 類別
   - 建構子驗證（1-5 分範圍）
   - equals / hashCode
   - toString
3. 撰寫單元測試
   - 測試 1：建立有效評分
   - 測試 2：評分過低拋出異常
   - 測試 3：評分過高拋出異常
4. 確保所有測試通過

### 驗收條件
- [ ] Rating 類別實作完整
- [ ] 驗證邏輯正確（1-5 分）
- [ ] equals / hashCode / toString 實作正確
- [ ] 單元測試 100% 通過（至少 3 個測試）
- [ ] dart analyze 0 錯誤

### 指標評估
- 職責數量：1 個（實作 Value Object）
- 程式碼行數：~25 行（含測試）
- 涉及檔案：1 個
- 測試用例：3 個
→ Level 1（簡單）✅

### 預估時間
15-20 分鐘
```

---

### 4.2 中等 Ticket 標準與範例（Level 2）

**Level 2 特徵**：
- 職責：2-3 個相關職責
- 行數：30-70 行
- 檔案：2-3 個
- 測試：3-6 個

**適用場景**：
- ✅ 含業務邏輯的 Entity
- ✅ 基礎 Repository 方法
- ✅ 簡單 UseCase
- ✅ 單一功能的 Controller

---

#### 範例 3：實作 Book Entity

```markdown
## Ticket #3: 實作 Book Entity

### 層級：Layer 5 (Domain Implementation)

### 業務需求
REQ-LIB-001: 書籍資料模型

### 目標
建立 `Book` Entity，封裝書籍核心資料

### 步驟
1. 在 `lib/domain/entities/` 建立 `book.dart`
2. 定義 Entity 欄位
   - isbn (String, required)
   - title (String, required)
   - author (String, required)
   - publishDate (DateTime, optional)
3. 實作 equals / hashCode（基於 isbn）
4. 實作 toString
5. 撰寫單元測試
   - 測試 1：建立有效 Book
   - 測試 2：equals 正確比較（相同 ISBN）
   - 測試 3：equals 正確比較（不同 ISBN）
   - 測試 4：hashCode 一致性
6. 確保測試通過

### 驗收條件
- [ ] Book Entity 欄位定義完整
- [ ] equals / hashCode 實作正確（基於 isbn）
- [ ] toString 回傳清楚的字串表示
- [ ] 單元測試 100% 通過（至少 4 個測試）
- [ ] dart analyze 0 錯誤

### 指標評估
- 職責數量：3 個（欄位定義、equals/hashCode、toString）
- 程式碼行數：~50 行（含測試）
- 涉及檔案：1 個
- 測試用例：4 個
→ Level 2（中等）✅

### 預估時間
25-35 分鐘
```

---

#### 範例 4：實作 GetBookUseCase

```markdown
## Ticket #4: 實作 GetBookUseCase

### 層級：Layer 3 (UseCase)

### 業務需求
REQ-LIB-001: 查詢書籍功能

### 目標
實作 `GetBookUseCase`，協調書籍查詢業務流程

### 依賴 Ticket
- Ticket #1: 定義 IBookRepository 介面（必須先完成）

### 步驟
1. 在 `lib/application/use_cases/` 建立 `get_book_use_case.dart`
2. 定義 `GetBookUseCase` 介面
3. 實作 `GetBookInteractor`
   - 注入 `IBookRepository`
   - 實作 `execute(String isbn)` 方法
   - 處理 Repository 異常
4. 撰寫單元測試
   - 測試 1：成功查詢書籍
   - 測試 2：書籍不存在回傳 null
   - 測試 3：無效 ISBN 拋出 ValidationException
   - 測試 4：Repository 異常正確處理
5. 確保測試通過

### 驗收條件
- [ ] GetBookInteractor 正確注入 IBookRepository
- [ ] execute 方法實作正確
- [ ] 異常處理完整
- [ ] 單元測試 100% 通過（至少 4 個測試）
- [ ] dart analyze 0 錯誤

### 指標評估
- 職責數量：2 個（業務協調、異常處理）
- 程式碼行數：~55 行（含測試）
- 涉及檔案：1 個
- 測試用例：4 個
→ Level 2（中等）✅

### 預估時間
30-40 分鐘
```

---

### 4.3 複雜 Ticket 標準與範例（Level 3）

**Level 3 特徵**：
- 職責：3-5 個相關職責
- 行數：70-100 行
- 檔案：3-5 個
- 測試：6-10 個

**適用場景**：
- ⚠️ 完整 Repository CRUD
- ⚠️ 複雜 UseCase（含多重驗證）
- ⚠️ 複雜業務邏輯實作

**注意**：Level 3 Ticket 建議優先評估是否可拆分為更小 Ticket

---

#### 範例 5：實作 BookRepository CRUD（建議拆分）

```markdown
## Ticket #5: 實作 SQLiteBookRepository CRUD

### 層級：Layer 5 (Infrastructure)

### 業務需求
REQ-LIB-001: 書籍資料存取功能

### 目標
實作 `SQLiteBookRepository`，提供完整的 CRUD 操作

### 依賴 Ticket
- Ticket #1: 定義 IBookRepository 介面（必須先完成）

### ⚠️ 複雜度警告
此 Ticket 為 Level 3（複雜），建議拆分為 3 個 Level 2 Ticket：
- Ticket A: 實作 getBookByIsbn + 測試
- Ticket B: 實作 saveBook + 測試
- Ticket C: 實作 deleteBook + Data Mapper + 測試

### 步驟（如不拆分）
1. 在 `lib/infrastructure/repositories/` 建立 `sqlite_book_repository.dart`
2. 在 `lib/infrastructure/mappers/` 建立 `book_mapper.dart`
3. 實作 `getBookByIsbn` 方法
   - SQL 查詢邏輯
   - Data Mapper 轉換（DTO → Entity）
   - 錯誤處理
4. 實作 `saveBook` 方法
   - SQL 插入/更新邏輯
   - Data Mapper 轉換（Entity → DTO）
   - 錯誤處理
5. 實作 `deleteBook` 方法
6. 撰寫完整測試
   - getBookByIsbn: 成功、不存在、異常（3 個測試）
   - saveBook: 新增、更新、異常（3 個測試）
   - deleteBook: 成功、不存在、異常（3 個測試）
7. 確保所有測試通過

### 驗收條件
- [ ] 實作所有 IBookRepository 方法
- [ ] Data Mapper 轉換正確
- [ ] 異常處理完整
- [ ] 單元測試 100% 通過（至少 9 個測試）
- [ ] dart analyze 0 錯誤

### 指標評估
- 職責數量：5 個（get、save、delete、mapper、異常處理）
- 程式碼行數：~160 行（含測試）
- 涉及檔案：2 個
- 測試用例：9 個
→ Level 3（複雜）⚠️ 建議拆分

### 預估時間
60-90 分鐘

### 建議拆分方案
拆分為 3 個 Ticket（詳見第五章決策樹）
```

---

### 4.4 必須拆分標準（Level 4）

**Level 4 特徵**：
- 職責：> 5 個
- 行數：> 100 行
- 檔案：> 5 個
- 測試：> 10 個

**處理方式**：
- ❌ **禁止建立 Level 4 Ticket**
- ❌ **必須拆分為多個 Level 1-2 Ticket**
- ⚠️ **拆分後可接受少數 Level 3 Ticket**

---

#### 範例 6：God Ticket 檢測與拆分

```markdown
## ❌ 禁止：實作完整書籍評分功能

### 原始任務描述
實作書籍評分功能，包含 UI、Controller、UseCase、Repository

### God Ticket 檢測結果
- 職責數量：8 個 → Level 4 ❌
- 程式碼行數：~300 行 → Level 4 ❌
- 涉及檔案：8 個 → Level 4 ❌
- 測試用例：20 個 → Level 4 ❌
→ **所有指標都超標，必須拆分**

### 拆分決策
使用「Clean Architecture 分層拆分策略」（詳見第三章 3.4）

拆分為 6 個 Ticket：
1. Ticket #201: Rating Value Object（Level 2）
2. Ticket #202: Rating Entity（Level 1）
3. Ticket #203: IRatingRepository Interface（Level 1）
4. Ticket #204: SQLiteRatingRepository（Level 3）
5. Ticket #205: RateBookUseCase（Level 2）
6. Ticket #206: RatingWidget UI（Level 2）

結果：5 個 Level 1-2 + 1 個 Level 3 ✅ 全部可接受
```

---

### 4.5 Ticket 大小對照表

**快速參考表**：

| Level | 職責 | 行數 | 檔案 | 測試 | 預估時間 | 範例 |
|-------|------|------|------|------|---------|------|
| **1 簡單** | 1 | <30 | 1 | 1-3 | 5-20分鐘 | Interface 定義、簡單 VO |
| **2 中等** | 2-3 | 30-70 | 2-3 | 3-6 | 20-40分鐘 | Entity、基礎 UseCase |
| **3 複雜** | 3-5 | 70-100 | 3-5 | 6-10 | 40-90分鐘 | 完整 Repository CRUD |
| **4 超標** | >5 | >100 | >5 | >10 | N/A | ❌ 禁止建立 |

**決策建議**：
- ✅ Level 1-2：直接建立 Ticket
- ⚠️ Level 3：優先評估是否可拆分
- ❌ Level 4：必須拆分，無例外

---

## 第五章：拆分決策樹

### 5.1 決策樹總覽

**完整決策流程**：

```text
[Ticket 設計階段]
    ↓
[計算 4 個量化指標]
    ↓
[取最高複雜度等級]
    ↓
    ├─ Level 1-2 ✅
    │   ↓
    │   [直接建立 Ticket]
    │   ↓
    │   [進入 Phase 2（測試設計）]
    │
    ├─ Level 3 ⚠️
    │   ↓
    │   [拆分評估決策]
    │   ↓
    │   ├─ 可拆分？
    │   │   ├─ Yes → [執行拆分策略] → [重新評估]
    │   │   └─ No → [勉強接受] → [標記高風險]
    │   ↓
    │   [進入 Phase 2]
    │
    └─ Level 4 ❌
        ↓
        [阻止建立 Ticket]
        ↓
        [執行強制拆分]
        ↓
        [選擇拆分策略]
        ↓
        ├─ 優先：按架構分層拆分
        ├─ 次之：按職責拆分
        └─ 最後：按檔案拆分
        ↓
        [重新評估所有子 Ticket]
        ↓
        [確保所有子 Ticket ≤ Level 3]
        ↓
        [可建立 Ticket]
```

---

### 5.2 Level 3 拆分評估決策

**決策問題**：此 Level 3 Ticket 是否應該拆分？

**評估準則**：

#### 準則 1：職責可分離性

```text
問題：職責是否可獨立分離為多個 Ticket？

評估方法：
1. 列出所有職責
2. 檢查職責之間的依賴關係
3. 判斷是否可獨立完成

範例：
原始任務：實作 BookRepository CRUD
職責分析：
- 職責 1：getBookByIsbn → 可獨立 ✅
- 職責 2：saveBook → 可獨立 ✅（依賴職責 1 的測試模式）
- 職責 3：deleteBook → 可獨立 ✅
- 職責 4：Data Mapper → 可整合到職責 1-3 ⚠️
- 職責 5：異常處理 → 可整合到職責 1-3 ⚠️

結論：可拆分為 3 個 Ticket（每個職責對應 1 個 Ticket）✅
```

#### 準則 2：拆分後複雜度降低

```text
問題：拆分後每個子 Ticket 是否 ≤ Level 2？

評估方法：
對每個拆分後的子 Ticket 重新計算 4 個指標

範例：
原始 Ticket（Level 3）：
- 職責：5 個
- 行數：160 行
- 檔案：2 個
- 測試：9 個

拆分後 Ticket A：getBookByIsbn
- 職責：2 個（查詢 + 轉換）
- 行數：50 行
- 檔案：2 個
- 測試：3 個
→ Level 2 ✅

拆分後 Ticket B：saveBook
- 職責：2 個（儲存 + 異常處理）
- 行數：60 行
- 檔案：1 個（修改）
- 測試：3 個
→ Level 2 ✅

拆分後 Ticket C：deleteBook
- 職責：2 個（刪除 + 異常處理）
- 行數：50 行
- 檔案：1 個（修改）
- 測試：3 個
→ Level 2 ✅

結論：拆分成功，所有子 Ticket 都降為 Level 2 ✅
```

#### 準則 3：拆分成本合理性

```text
問題：拆分帶來的管理成本是否合理？

成本考量：
- ✅ 收益：風險降低、易於 Review、可並行開發
- ⚠️ 成本：增加 Ticket 數量、需要管理依賴關係

決策：
- 拆分收益 > 拆分成本 → 建議拆分
- 拆分收益 ≈ 拆分成本 → 可選擇
- 拆分收益 < 拆分成本 → 不建議拆分

範例：
原始 Ticket：Level 3（複雜 Repository CRUD）
拆分收益：
+ 風險降低：1 個高風險 → 3 個低風險
+ Review 效率：每次 Review 50-60 行 vs 160 行
+ 可並行：3 個 Ticket 可依序快速開發

拆分成本：
- 管理成本：需要管理 3 個 Ticket 依賴
- 整合測試：需要額外的整合測試（但本來就需要）

結論：拆分收益 > 拆分成本，建議拆分 ✅
```

---

### 5.3 Level 4 強制拆分策略

**Level 4 無需評估，必須拆分**

#### 拆分策略優先順序

**策略 1：按 Clean Architecture 分層拆分（優先）**

```text
適用情況：
- Ticket 跨越多個架構層級（Layer 1-5）
- 檔案分布在不同層級目錄
- 涉及 UI、UseCase、Repository 等多層

拆分方法：
1. 按照 Layer 1 → Layer 5 順序分組檔案
2. 每個 Layer 建立獨立 Ticket
3. 相鄰兩層可合併為單一 Ticket（如 Interface + Implementation）

範例（書籍評分功能）：
原始：8 個檔案，跨越 4 層
拆分後：
- Ticket 1: Layer 5 Domain（Rating VO + Entity）
- Ticket 2: Layer 5 + 4 Repository（Interface + Impl）
- Ticket 3: Layer 3 UseCase
- Ticket 4: Layer 1-2 Presentation（UI + Controller）

結果：4 個 Level 1-2 Ticket ✅
```

**策略 2：按職責拆分（次之）**

```text
適用情況：
- 所有檔案在同一層級，但職責過多
- 單一 Repository 包含過多 CRUD 方法
- 單一 UseCase 包含過多業務邏輯

拆分方法：
1. 列出所有職責
2. 每個獨立職責建立 Ticket
3. 相關職責可合併（最多 2-3 個職責）

範例（BookRepository CRUD）：
原始：5 個職責（get + save + delete + mapper + error）
拆分後：
- Ticket A: getBookByIsbn + mapper + error（2-3 職責）
- Ticket B: saveBook + error（2 職責）
- Ticket C: deleteBook + error（2 職責）

結果：3 個 Level 2 Ticket ✅
```

**策略 3：按檔案拆分（最後）**

```text
適用情況：
- 前兩種策略都無法適用
- 檔案之間相對獨立
- 每個檔案本身就是一個完整單元

拆分方法：
1. 每個檔案建立獨立 Ticket
2. 相關檔案可合併（最多 2-3 個檔案）

範例：
原始：7 個檔案
拆分後：
- Ticket 1: file1.dart + file2.dart（相關）
- Ticket 2: file3.dart
- Ticket 3: file4.dart + file5.dart（相關）
- Ticket 4: file6.dart + file7.dart（相關）

結果：4 個 Ticket
```

---

### 5.4 拆分決策檢查清單

**Level 3 拆分評估檢查清單**：

```markdown
□ 已列出所有職責
□ 已評估職責可分離性
□ 已計算拆分後每個子 Ticket 的指標
□ 已確認所有子 Ticket ≤ Level 2
□ 已評估拆分成本 vs 收益
□ 已確定是否拆分的最終決策
```

**Level 4 強制拆分檢查清單**：

```markdown
□ 已識別 Ticket 為 Level 4（任一指標超標）
□ 已選擇拆分策略（分層 / 職責 / 檔案）
□ 已執行拆分（列出所有子 Ticket）
□ 已重新評估所有子 Ticket
□ 已確認所有子 Ticket ≤ Level 3
□ 已標記子 Ticket 依賴關係
□ 已確認子 Ticket 總和涵蓋原始功能
```

---

## 第六章：Ticket 拆分檢查清單

### 6.1 拆分前檢查清單

**階段 1：需求理解**

```markdown
□ 已閱讀完整的業務需求
□ 已理解 Ticket 的業務目標
□ 已確認 Ticket 的驗收條件
□ 已識別所有需要完成的功能點
□ 已確認與其他 Ticket 的依賴關係
```

**階段 2：指標計算**

```markdown
□ 已列出所有職責（功能點 + 邊界條件 + 異常處理）
□ 已估算程式碼行數（參考類似任務）
□ 已列出所有涉及檔案（含新建和修改）
□ 已估算測試用例數（正常 + 邊界 + 異常）
□ 已取最高複雜度等級作為最終評估
```

**階段 3：複雜度確認**

```markdown
□ 已確定 Ticket 的複雜度等級（Level 1-4）
□ 如為 Level 4，已阻止建立並準備拆分
□ 如為 Level 3，已評估是否拆分
□ 如為 Level 1-2，已確認可直接建立
```

---

### 6.2 拆分過程檢查清單

**階段 4：拆分策略選擇**

```markdown
□ 已分析 Ticket 涉及的架構層級
□ 已確定拆分策略（分層 / 職責 / 檔案）
□ 已列出所有拆分後的子 Ticket
□ 已為每個子 Ticket 撰寫初步描述
```

**階段 5：子 Ticket 設計**

```markdown
□ 每個子 Ticket 都有明確的目標
□ 每個子 Ticket 都有清楚的步驟
□ 每個子 Ticket 都有具體的驗收條件
□ 每個子 Ticket 都標記了層級（[Layer X]）
□ 每個子 Ticket 都標記了依賴關係
```

**階段 6：依賴關係確認**

```markdown
□ 已識別所有子 Ticket 之間的依賴
□ 已確保依賴方向符合 Clean Architecture 規則
□ 已標記依賴順序（Phase 1 → Phase 2 → ...）
□ 已確認可並行執行的 Ticket
```

---

### 6.3 拆分後驗證清單

**階段 7：指標重新評估**

```markdown
□ 已重新計算每個子 Ticket 的 4 個指標
□ 已確認所有子 Ticket ≤ Level 3
□ 已確認大多數子 Ticket ≤ Level 2
□ 如有 Level 3 子 Ticket，已評估合理性
```

**階段 8：完整性驗證**

```markdown
□ 所有子 Ticket 功能總和 = 原始 Ticket 功能
□ 沒有遺漏任何功能點
□ 沒有重複的功能實作
□ 所有檔案都被包含在某個子 Ticket 中
□ 所有測試案例都被包含
```

**階段 9：品質檢查**

```markdown
□ 每個子 Ticket 都有業務需求引用
□ 每個子 Ticket 都有指標評估
□ 每個子 Ticket 都有預估時間
□ 每個子 Ticket 的職責明確且不重疊
□ 每個子 Ticket 的標題包含 [Layer X] 標籤
```

---

### 6.4 特殊情況檢查清單

**情況 1：無法拆分的 Level 3 Ticket**

```markdown
□ 已明確記錄為何無法拆分
□ 已標記為「高風險 Ticket」
□ 已安排額外的 Code Review
□ 已增加測試覆蓋率要求（> 90%）
□ 已準備更長的開發時間
```

**情況 2：跨層整合 Ticket**

```markdown
□ 已確認只涉及相鄰兩層（如 Layer 3 + Layer 4-5）
□ 已確認符合依賴規則（外層 → 內層）
□ 已明確標記為「整合 Ticket」
□ 已包含整合測試驗收條件
```

**情況 3：測試獨立 Ticket**

```markdown
□ 已確認生產程式碼已完成（依賴 Ticket）
□ Ticket 只包含測試程式碼
□ 已列出所有測試案例（正常 + 邊界 + 異常）
□ 已確認測試數量在合理範圍（< 10 個）
```

---

## 第七章：實務案例與最佳實踐

### 7.1 完整案例：書籍搜尋功能

**業務需求**：
```markdown
REQ-SEARCH-001: 實作書籍搜尋功能
- 使用者可輸入關鍵字搜尋書籍
- 支援書名、作者、ISBN 搜尋
- 顯示搜尋結果列表
```

---

#### 初步評估：識別為 God Ticket

```markdown
原始任務分析：
實作完整書籍搜尋功能（包含 UI、Controller、UseCase、Repository）

指標計算：
- 職責數量：10 個
  1. SearchBar UI 元件
  2. SearchResultList UI 元件
  3. SearchController 狀態管理
  4. SearchBookUseCase 業務協調
  5. Repository 查詢方法（書名搜尋）
  6. Repository 查詢方法（作者搜尋）
  7. Repository 查詢方法（ISBN 搜尋）
  8. 錯誤處理
  9. 載入狀態處理
  10. 空結果處理

- 程式碼行數：~400 行
- 涉及檔案：10 個
- 測試用例：25 個

複雜度評估：
- 職責：10 個 → Level 4 ❌
- 行數：400 行 → Level 4 ❌
- 檔案：10 個 → Level 4 ❌
- 測試：25 個 → Level 4 ❌

結論：God Ticket ❌ 必須拆分
```

---

#### 拆分策略：Clean Architecture 分層拆分

**第一步：按層級分組檔案**

```text
Layer 5 (Domain + Infrastructure):
- SearchQuery Value Object
- IBookRepository.searchByTitle()
- IBookRepository.searchByAuthor()
- IBookRepository.searchByIsbn()
- SQLiteBookRepository 查詢實作

Layer 3 (UseCase):
- SearchBookUseCase

Layer 2 (Behavior):
- SearchController

Layer 1 (UI):
- SearchBar Widget
- SearchResultList Widget
```

**第二步：設計拆分後的 Ticket**

---

**Ticket 1: 定義 SearchQuery Value Object（Layer 5）**

```markdown
## Ticket #301: 定義 SearchQuery Value Object

### 層級：Layer 5 (Domain Implementation)
### 策略：策略 2（具體實作）

### 業務需求
REQ-SEARCH-001: 書籍搜尋功能

### 目標
建立 `SearchQuery` Value Object，封裝搜尋條件驗證

### 步驟
1. 建立 `lib/domain/value_objects/search_query.dart`
2. 實作 SearchQuery 類別
   - 驗證查詢字串長度（最少 2 個字元）
   - trim() 處理空白
   - equals / hashCode
3. 撰寫單元測試
4. 確保測試通過

### 驗收條件
- [ ] SearchQuery 類別實作完整
- [ ] 驗證邏輯正確（最少 2 字元）
- [ ] 單元測試 100% 通過（至少 4 個測試）
- [ ] dart analyze 0 錯誤

### 指標評估
- 職責：1 個
- 行數：~30 行
- 檔案：1 個
- 測試：4 個
→ Level 1（簡單）✅

### 預估時間
15-20 分鐘
```

---

**Ticket 2: 擴充 IBookRepository 查詢方法（Layer 4）**

```markdown
## Ticket #302: 定義 IBookRepository 搜尋方法

### 層級：Layer 4 (Domain Interfaces)
### 策略：策略 1（Interface 定義）

### 業務需求
REQ-SEARCH-001: 書籍搜尋功能

### 目標
在 `IBookRepository` 介面新增搜尋方法簽名

### 步驟
1. 修改 `lib/domain/repositories/i_book_repository.dart`
2. 新增 `searchByTitle(String query)` 方法簽名
3. 新增 `searchByAuthor(String query)` 方法簽名
4. 新增 `searchByIsbn(String query)` 方法簽名
5. 撰寫文檔註解

### 驗收條件
- [ ] 3 個搜尋方法簽名完整
- [ ] 回傳類型為 `Future<List<Book>>`
- [ ] 文檔註解包含需求編號
- [ ] dart analyze 0 錯誤

### 指標評估
- 職責：1 個（定義介面）
- 行數：~15 行
- 檔案：1 個（修改）
- 測試：0 個
→ Level 1（簡單）✅

### 預估時間
10 分鐘
```

---

**Ticket 3: 實作 BookRepository 搜尋方法（Layer 5）**

```markdown
## Ticket #303: 實作 SQLiteBookRepository 搜尋

### 層級：Layer 5 (Infrastructure)
### 策略：策略 2（具體實作）
### 依賴：Ticket #301, #302

### 業務需求
REQ-SEARCH-001: 書籍搜尋功能

### 目標
實作 `SQLiteBookRepository` 的 3 個搜尋方法

### 步驟
1. 修改 `lib/infrastructure/repositories/sqlite_book_repository.dart`
2. 實作 `searchByTitle` 方法
   - SQL LIKE 查詢
   - Data Mapper 轉換
   - 錯誤處理
3. 實作 `searchByAuthor` 方法
4. 實作 `searchByIsbn` 方法
5. 撰寫單元測試（每個方法 2-3 個測試）
6. 確保測試通過

### 驗收條件
- [ ] 3 個搜尋方法實作完整
- [ ] SQL 查詢使用 LIKE 模糊搜尋
- [ ] 異常處理完整
- [ ] 單元測試 100% 通過（至少 8 個測試）
- [ ] dart analyze 0 錯誤

### 指標評估
- 職責：4 個（3 個搜尋方法 + 異常處理）
- 行數：~95 行
- 檔案：1 個（修改）
- 測試：8 個
→ Level 3（複雜）⚠️ 可接受
（註：3 個搜尋方法邏輯相似，整合實作較有效率）

### 預估時間
60-75 分鐘
```

---

**Ticket 4: 實作 SearchBookUseCase（Layer 3）**

```markdown
## Ticket #304: 實作 SearchBookUseCase

### 層級：Layer 3 (UseCase)
### 策略：策略 4（整合連接）
### 依賴：Ticket #302, #303

### 業務需求
REQ-SEARCH-001: 書籍搜尋功能

### 目標
實作 `SearchBookUseCase`，協調搜尋業務流程

### 步驟
1. 建立 `lib/application/use_cases/search_book_use_case.dart`
2. 注入 `IBookRepository`
3. 實作 `execute(SearchQuery query, SearchType type)` 方法
   - 根據 SearchType 呼叫對應的 Repository 方法
   - 處理空結果
   - 處理異常
4. 撰寫整合測試
5. 確保測試通過

### 驗收條件
- [ ] UseCase 正確注入 IBookRepository
- [ ] 支援 3 種搜尋類型（Title / Author / ISBN）
- [ ] 整合測試 100% 通過（至少 5 個測試）
- [ ] 異常處理完整
- [ ] dart analyze 0 錯誤

### 指標評估
- 職責：2 個（業務協調、異常處理）
- 行數：~65 行
- 檔案：1 個
- 測試：5 個
→ Level 2（中等）✅

### 預估時間
35-45 分鐘
```

---

**Ticket 5: 實作 SearchController（Layer 2）**

```markdown
## Ticket #305: 實作 SearchController

### 層級：Layer 2 (Behavior)
### 策略：策略 4（整合連接）
### 依賴：Ticket #304

### 業務需求
REQ-SEARCH-001: 書籍搜尋功能

### 目標
實作 `SearchController`，管理搜尋狀態

### 步驟
1. 建立 `lib/presentation/controllers/search_controller.dart`
2. 注入 `SearchBookUseCase`
3. 實作狀態管理
   - isLoading（載入中）
   - searchResults（搜尋結果）
   - errorMessage（錯誤訊息）
4. 實作 `search(String query, SearchType type)` 方法
5. 撰寫單元測試
6. 確保測試通過

### 驗收條件
- [ ] SearchController 正確注入 UseCase
- [ ] 狀態管理正確（loading / success / error）
- [ ] 單元測試 100% 通過（至少 5 個測試）
- [ ] dart analyze 0 錯誤

### 指標評估
- 職責：2 個（狀態管理、UseCase 整合）
- 行數：~70 行
- 檔案：1 個
- 測試：5 個
→ Level 2（中等）✅

### 預估時間
40 分鐘
```

---

**Ticket 6: 實作搜尋 UI 元件（Layer 1）**

```markdown
## Ticket #306: 實作 SearchBar 和 SearchResultList

### 層級：Layer 1 (UI)
### 策略：策略 2（具體實作）
### 依賴：Ticket #305

### 業務需求
REQ-SEARCH-001: 書籍搜尋功能

### 目標
實作搜尋介面的 UI 元件

### 步驟
1. 建立 `lib/presentation/widgets/search_bar.dart`
2. 實作 SearchBar Widget
   - TextField 輸入框
   - SearchType 選擇器
   - 搜尋按鈕
3. 建立 `lib/presentation/widgets/search_result_list.dart`
4. 實作 SearchResultList Widget
   - 顯示搜尋結果
   - 載入中狀態
   - 空結果提示
   - 錯誤提示
5. 撰寫 Widget 測試
6. 確保測試通過

### 驗收條件
- [ ] SearchBar UI 正確顯示和互動
- [ ] SearchResultList 正確顯示各種狀態
- [ ] Widget 測試 100% 通過（至少 6 個測試）
- [ ] dart analyze 0 錯誤

### 指標評估
- 職責：2 個（SearchBar、SearchResultList）
- 行數：~90 行
- 檔案：2 個
- 測試：6 個
→ Level 2（中等）✅

### 預估時間
50-60 分鐘
```

---

#### 拆分結果總結

**拆分前後對比**：

| 項目 | 拆分前（God Ticket）| 拆分後（6 個 Ticket）|
|------|-------------------|-------------------|
| 職責數量 | 10 個 ❌ | 平均 1.8 個 ✅ |
| 程式碼行數 | ~400 行 ❌ | 平均 61 行 ✅ |
| 檔案數量 | 10 個 ❌ | 平均 1.2 個 ✅ |
| 測試數量 | 25 個 ❌ | 平均 4.7 個 ✅ |
| 複雜度等級 | Level 4 ❌ | 5 個 Level 1-2 ✅<br>1 個 Level 3 ⚠️ |
| 預估總時間 | N/A（無法估算）| 210-250 分鐘 |

**拆分效益分析**：

1. **風險大幅降低**：
   - 從 1 個無法管理的 God Ticket → 6 個可控 Ticket
   - 單一 Ticket 失敗不影響其他 Ticket

2. **支援並行開發**：
   - Phase 1: Ticket #301, #302 可並行
   - Phase 2: Ticket #303 執行
   - Phase 3: Ticket #304 執行
   - Phase 4: Ticket #305, #306 可部分並行

3. **Review 效率提升**：
   - 每次 Review 平均 61 行（vs 400 行）
   - Review 時間縮短 85%

4. **測試獨立性**：
   - 每層可獨立測試
   - Mock 依賴簡單明確

---

### 7.2 常見錯誤與解決方案

#### 錯誤 1：過度拆分

**問題描述**：
```markdown
將 Level 2（中等）Ticket 拆分為多個 Level 1 Ticket，
反而增加管理成本且沒有實質收益。

範例：
原始 Ticket（Level 2）：實作 Rating Value Object
- 職責：2 個（建立 + 驗證）
- 行數：50 行
- 測試：5 個

過度拆分為 2 個 Ticket：
- Ticket A：實作 Rating 建構子（Level 1，25 行）
- Ticket B：實作 Rating 驗證邏輯（Level 1，25 行）

問題：
- 兩個 Ticket 高度耦合，必須連續執行
- 增加了額外的管理成本
- 沒有實質的風險降低
```

**解決方案**：
```markdown
✅ 保持原始 Level 2 Ticket 不拆分

判斷準則：
- Level 1-2 Ticket 通常不需要拆分
- 只有 Level 3-4 才需要評估拆分
- 拆分後的子 Ticket 應該相對獨立
```

---

#### 錯誤 2：拆分後依賴過於複雜

**問題描述**：
```markdown
拆分方式導致依賴關係過於複雜，
難以理解和管理執行順序。

範例：
拆分為 8 個 Ticket，依賴關係如下：
Ticket 1 → Ticket 2 → Ticket 4
Ticket 1 → Ticket 3 → Ticket 5
Ticket 2 → Ticket 6
Ticket 3 → Ticket 6
Ticket 5 → Ticket 7
Ticket 6 → Ticket 7 → Ticket 8

問題：
- 依賴網絡複雜，難以追蹤
- 執行順序不明確
- 容易遺漏依賴
```

**解決方案**：
```markdown
✅ 使用線性或樹狀依賴結構

優化後的依賴關係：
Phase 1（並行）:
├─ Ticket 1, Ticket 2

Phase 2（並行）:
├─ Ticket 3, Ticket 4（依賴 Phase 1）

Phase 3:
└─ Ticket 5（依賴 Phase 2）

Phase 4:
└─ Ticket 6（依賴 Phase 3）

判斷準則：
- 優先使用 Phase 分組（線性依賴）
- 同 Phase 內的 Ticket 可並行
- 避免跨 Phase 的複雜依賴
```

---

#### 錯誤 3：拆分邊界不清晰

**問題描述**：
```markdown
拆分後的子 Ticket 職責重疊或邊界模糊，
導致實作時不知道該在哪個 Ticket 完成。

範例：
原始：實作完整 BookRepository
拆分後：
- Ticket A：實作 getBookByIsbn
- Ticket B：實作 Data Mapper
- Ticket C：實作異常處理

問題：
- Ticket A 需要 Data Mapper（依賴 Ticket B）
- Ticket A 需要異常處理（依賴 Ticket C）
- 但 Ticket A 應該先完成？
- 邊界模糊，無法獨立完成
```

**解決方案**：
```markdown
✅ 確保每個子 Ticket 可獨立完成

正確拆分：
- Ticket A：實作 getBookByIsbn（含 Mapper + 異常處理）
- Ticket B：實作 saveBook（含 Mapper + 異常處理）
- Ticket C：實作 deleteBook（含異常處理）

判斷準則：
- 每個子 Ticket 應該是「最小可交付單元」
- 避免將共用邏輯獨立為 Ticket
- 共用邏輯應整合到使用它的 Ticket 中
```

---

### 7.3 拆分最佳實踐

#### 實踐 1：優先選擇架構分層拆分

**原則**：
```markdown
當 Ticket 跨越多個架構層級時，
優先按照 Clean Architecture 分層拆分。

優點：
✅ 依賴方向清晰（內層不依賴外層）
✅ 測試策略明確（每層有標準測試方法）
✅ 可並行開發（不同層可由不同開發者負責）
✅ 符合單一職責原則
```

**範例**：
```markdown
原始任務：實作書籍評分功能（跨越 4 層）

❌ 錯誤：按功能模組拆分
- Ticket A：評分輸入功能（UI + Controller + UseCase）
- Ticket B：評分儲存功能（Repository + Mapper）

問題：
- Ticket A 跨越 3 層，依賴關係複雜
- 測試困難（需要 Mock 多層）

✅ 正確：按架構分層拆分
- Ticket 1：Rating Domain 模型（Layer 5）
- Ticket 2：IRatingRepository + Impl（Layer 4-5）
- Ticket 3：RateBookUseCase（Layer 3）
- Ticket 4：RatingController + Widget（Layer 1-2）

優點：
- 每個 Ticket 職責單一
- 依賴方向清楚
- 測試獨立簡單
```

---

#### 實踐 2：保持線性依賴順序

**原則**：
```markdown
優先設計線性或樹狀依賴結構，
避免複雜的網狀依賴關係。

建議結構：
✅ 線性依賴：Ticket 1 → Ticket 2 → Ticket 3 → Ticket 4
✅ 樹狀依賴：
   Ticket 1
   ├─ Ticket 2
   │  └─ Ticket 4
   └─ Ticket 3
      └─ Ticket 5

避免結構：
❌ 網狀依賴：多個交叉依賴，難以追蹤
```

**實施方法**：
```markdown
步驟 1：識別「核心 Ticket」
- Domain 層 Ticket 通常是核心
- 其他層依賴 Domain 層

步驟 2：按照 Clean Architecture 依賴方向排序
- Layer 5 → Layer 4 → Layer 3 → Layer 2 → Layer 1

步驟 3：標記 Phase
- Phase 1：Layer 5（Domain）
- Phase 2：Layer 4-5（Repository）
- Phase 3：Layer 3（UseCase）
- Phase 4：Layer 1-2（Presentation）
```

---

#### 實踐 3：每個 Ticket 包含完整測試

**原則**：
```markdown
每個 Ticket 應該包含對應的測試，
不要將測試獨立為單獨 Ticket（除非測試數量 > 10）。

優點：
✅ TDD 紅綠燈循環完整
✅ 每個 Ticket 交付時就是可測試的
✅ 避免「實作完成但測試缺失」的情況
```

**實施方法**：
```markdown
在 Ticket 驗收條件中明確測試要求：

範例：
## Ticket #X: 實作 Rating Value Object

### 驗收條件
- [ ] Rating 類別實作完整
- [ ] 單元測試 100% 通過（至少 3 個測試）
  - 測試 1：建立有效評分
  - 測試 2：評分過低拋出異常
  - 測試 3：評分過高拋出異常
- [ ] 測試覆蓋率 > 90%
- [ ] dart analyze 0 錯誤

例外情況（測試獨立 Ticket）：
- 測試用例 > 10 個（測試複雜度 Level 4）
- 補充現有程式碼的測試（非新功能）
- 整合測試（跨多層驗證）
```

---

#### 實踐 4：明確標記層級和策略

**原則**：
```markdown
每個 Ticket 標題應包含：
1. [Layer X] 標籤（標示架構層級）
2. 策略類型（Interface / 實作 / 整合）

格式：
## Ticket #NNN: [Layer X] {動詞} {目標}

範例：
✅ 好的標題：
- [Layer 4] 定義 IBookRepository 介面
- [Layer 5] 實作 SQLiteBookRepository
- [Layer 3] 實作 GetBookUseCase

❌ 不好的標題：
- 書籍資料存取功能（沒有層級、目標不明確）
- 實作 Repository（沒有層級、範圍不清楚）
```

**實施方法**：
```markdown
在 Ticket 範本中包含：

### 層級：Layer X (層級名稱)
### 策略：策略 N（策略名稱）

範例：
## Ticket #101: [Layer 4] 定義 IBookRepository 介面

### 層級：Layer 4 (Domain Interfaces)
### 策略：策略 1（Interface 定義）

### 目標
建立 `IBookRepository` 介面，定義書籍資料存取的契約

這樣可以：
✅ 快速識別 Ticket 的架構位置
✅ 理解 Ticket 的目的（定義 / 實作 / 整合）
✅ 追蹤依賴關係（內層 → 外層）
```

---

## 附錄 A：術語表

| 術語 | 英文 | 定義 | 範例 |
|------|------|------|------|
| **職責** | Responsibility | Ticket 需要完成的獨立功能點或邊界條件 | 定義介面、實作方法、處理異常 |
| **複雜度等級** | Complexity Level | 基於 4 個量化指標計算的任務複雜度（Level 1-4） | Level 2（中等）|
| **God Ticket** | God Ticket | 範圍過大、無法管理的任務（Level 4） | 包含 8 個檔案、300 行程式碼的任務 |
| **單層修改原則** | Single Layer Modification | 每個 Ticket 應只修改單一架構層級 | Ticket 只修改 Domain 層 |
| **依賴規則** | Dependency Rule | Clean Architecture 的依賴方向規則（外層→內層） | UseCase 依賴 Repository Interface |
| **最小可交付單元** | Minimum Deliverable Unit | 可獨立完成、測試、交付的最小功能單元 | 實作單一 Value Object |
| **指標整合評估** | Integrated Indicator Assessment | 取 4 個指標中最高的複雜度等級 | max(Level 2, Level 3, Level 1, Level 2) = Level 3 |
| **拆分策略** | Splitting Strategy | 將大任務拆分為小任務的標準方法 | 按架構分層拆分 |
| **Phase** | Phase | 依賴順序的執行階段 | Phase 1（Domain 層）→ Phase 2（Repository 層）|

---

## 附錄 B：拆分決策模板

**模板用途**：用於記錄 Ticket 拆分的決策過程

```markdown
# Ticket 拆分決策記錄

## 基本資訊
- **原始任務**：[任務描述]
- **業務需求**：[需求編號]
- **評估日期**：YYYY-MM-DD
- **評估人員**：[姓名]

## 指標評估

### 職責數量
- **職責列表**：
  1. [職責 1]
  2. [職責 2]
  ...
- **總計**：X 個
- **等級**：Level X

### 程式碼行數
- **預估行數**：X 行
- **依據**：[參考類似任務或經驗估算]
- **等級**：Level X

### 涉及檔案
- **檔案列表**：
  1. [檔案路徑 1]
  2. [檔案路徑 2]
  ...
- **總計**：X 個
- **等級**：Level X

### 測試用例數
- **測試列表**：
  1. [測試案例 1]
  2. [測試案例 2]
  ...
- **總計**：X 個
- **等級**：Level X

## 複雜度結論
- **最高等級**：Level X
- **最終判定**：[簡單 / 中等 / 複雜 / 必須拆分]

## 拆分決策

### 決策結果
- [ ] 不拆分（Level 1-2）
- [ ] 評估拆分（Level 3）
- [ ] 強制拆分（Level 4）

### 拆分原因（如適用）
[說明為什麼需要拆分]

### 拆分策略（如適用）
- [ ] 按架構分層拆分（優先）
- [ ] 按職責拆分（次之）
- [ ] 按檔案拆分（最後）

## 拆分方案（如適用）

### 子 Ticket 列表
1. **Ticket A**：[標題]
   - 層級：Layer X
   - 指標：職責 X、行數 X、檔案 X、測試 X
   - 等級：Level X

2. **Ticket B**：[標題]
   - 層級：Layer X
   - 指標：職責 X、行數 X、檔案 X、測試 X
   - 等級：Level X

### 依賴關係
```text
[依賴關係圖或順序說明]
```

### 執行順序
- Phase 1：[Ticket A, Ticket B]
- Phase 2：[Ticket C]
- ...

## 驗證清單

### 拆分前檢查
- [ ] 已計算所有 4 個指標
- [ ] 已確定複雜度等級
- [ ] 已確定是否拆分

### 拆分後檢查（如適用）
- [ ] 所有子 Ticket 已設計
- [ ] 所有子 Ticket ≤ Level 3
- [ ] 依賴關係明確
- [ ] 功能完整性確認

## 備註
[其他需要記錄的資訊]
```text

---

## 附錄 C：與其他方法論的整合指引

### C.1 與 TDD 四階段方法論整合

**整合點**：
```markdown
本方法論位於 TDD Phase 1（設計階段）

TDD 流程整合：
Phase 1: Ticket 設計
  ↓
  使用本方法論評估 Ticket 複雜度
  ↓
  如為 Level 3-4，執行拆分
  ↓
  所有 Ticket 確認為 Level 1-2
  ↓
Phase 2: 測試設計（sage-test-architect）
  ↓
Phase 3: 實作（pepper → parsley）
  ↓
Phase 4: 重構（cinnamon-refactor-owl）
```

**協作方式**：
- ✅ Phase 1 完成時，所有 Ticket 都應該 ≤ Level 3
- ✅ 理想狀態：所有 Ticket 都是 Level 1-2
- ⚠️ 如有 Level 3 Ticket，應標記為「需要額外 Review」

---

### C.2 與層級隔離派工方法論整合

**整合點**：
```markdown
本方法論提供「拆分標準」
層級隔離派工方法論提供「派工策略」

協作流程：
1. 使用本方法論拆分 Ticket（按架構分層）
2. 使用層級隔離派工方法論決定執行順序
   - 優先派發內層 Ticket（Layer 5）
   - 逐步派發外層 Ticket（Layer 1）
3. 確保依賴順序符合 Clean Architecture 規則
```

**範例**：
```markdown
拆分結果（本方法論）：
- Ticket 1: Layer 5 Domain
- Ticket 2: Layer 4-5 Repository
- Ticket 3: Layer 3 UseCase
- Ticket 4: Layer 1-2 Presentation

派工順序（層級隔離派工方法論）：
Week 1:
  ├─ 派發 Ticket 1（Layer 5）給 Developer A
  ├─ Ticket 1 完成後，派發 Ticket 2（Layer 4-5）給 Developer A

Week 2:
  ├─ Ticket 2 完成後，派發 Ticket 3（Layer 3）給 Developer B
  └─ 可同時派發 Ticket 4（Layer 1-2）給 Developer C（部分並行）
```

---

### C.3 與 Code Smell 品質閘門檢測方法論整合

**整合點**：
```markdown
本方法論在 Ticket 設計階段執行（Design Time）
Code Smell 品質閘門在 Ticket 執行後檢測（Runtime）

協作流程：
設計階段（本方法論）：
  ├─ 計算 4 個指標
  ├─ 評估複雜度等級
  ├─ 決定是否拆分
  └─ 確保 Ticket ≤ Level 3

執行階段（Code Smell 檢測）：
  ├─ C1 檢測：God Ticket（檔案數、層級跨度）
  ├─ C2 檢測：Incomplete Ticket（缺失元素）
  └─ C3 檢測：Ambiguous Responsibility（職責不明）

如果 Code Smell 檢測失敗：
  ├─ C1 失敗 → 返回本方法論重新拆分
  ├─ C2 失敗 → 補充缺失元素
  └─ C3 失敗 → 明確職責定義
```

**防範措施**：
```markdown
如果在設計階段使用本方法論：
✅ C1 God Ticket 失敗率應該降至 0%
✅ C3 Ambiguous Responsibility 失敗率應該降至接近 0%
⚠️ C2 Incomplete Ticket 仍需要 Code Smell 檢測補強
```

---

### C.4 與 Clean Architecture 實作方法論整合

**整合點**：
```markdown
本方法論的「架構分層拆分策略」（第三章）
完全基於 Clean Architecture 實作方法論的五層架構。

依賴關係：
本方法論 → 依賴 Clean Architecture 實作方法論
- 採用相同的五層架構定義
- 遵循相同的依賴規則
- 使用相同的檔案路徑規範
```

**參考章節對應**：
```markdown
本方法論第三章「Clean Architecture 分層拆分策略」
↓ 引用自
Clean Architecture 實作方法論：
- 第一章：五層架構定義
- 第二章：依賴規則
- 第三章：檔案組織規範
```

---

## 總結

### 方法論核心價值

本方法論提供了**量化、客觀、可執行**的 Ticket 拆分標準，解決了傳統拆分方法的主觀性和不一致性問題。

**核心創新點**：
1. ✅ **4 個量化指標體系**：職責數量、程式碼行數、檔案數量、測試數量
2. ✅ **4 級複雜度分類**：簡單、中等、複雜、必須拆分
3. ✅ **完整拆分決策樹**：從評估到拆分的完整流程
4. ✅ **Clean Architecture 整合**：基於架構分層的標準拆分策略

### 使用場景回顧

**適用專案**：
- 多人協作開發專案
- 採用 Clean Architecture 的軟體專案
- 需要標準化任務管理的團隊
- 敏捷開發和精細進度追蹤的專案

**預期效果**：
- ✅ **消除主觀判斷**：所有決策基於量化指標
- ✅ **降低開發風險**：大任務拆分為小任務，風險可控
- ✅ **提升協作效率**：任務邊界清晰，減少溝通成本
- ✅ **支援並行開發**：按架構分層拆分，可多人同時開發

### 快速開始指引

**第一步**：評估 Ticket 複雜度
```markdown
1. 計算 4 個指標（職責、行數、檔案、測試）
2. 取最高複雜度等級
3. 判斷是否需要拆分
```

**第二步**：執行拆分（如需要）
```markdown
1. 選擇拆分策略（優先：架構分層）
2. 設計子 Ticket
3. 重新評估每個子 Ticket
4. 確認所有子 Ticket ≤ Level 3
```

**第三步**：驗證和記錄
```markdown
1. 使用檢查清單驗證（第六章）
2. 記錄決策過程（附錄 B 模板）
3. 進入 TDD Phase 2（測試設計）
```

### 相關方法論引用

完整的 Ticket 設計派工流程請參考：
- [📚 Ticket 設計派工方法論]($CLAUDE_PROJECT_DIR/.claude/methodologies/ticket-design-dispatch-methodology.md) - 主方法論
- [🏗 Clean Architecture 實作方法論]($CLAUDE_PROJECT_DIR/.claude/methodologies/clean-architecture-implementation-methodology.md) - 架構基礎
- [🎯 層級隔離派工方法論]($CLAUDE_PROJECT_DIR/.claude/methodologies/layered-ticket-methodology.md) - 派工策略
- [🔬 TDD 四階段方法論]($CLAUDE_PROJECT_DIR/.claude/methodologies/tdd-four-phases-methodology.md) - 開發流程

---

**文件版本**：v1.0.0
**建立日期**：2025-10-11
**最後更新**：2025-10-11 21:30
**狀態**：✅ 完成
**總字數**：~26,500 tokens

**貢獻者**：
- lavender-interface-designer（Phase 1 需求規劃）
- pepper-test-implementer（Phase 3a 策略規劃）
- 主線程（Phase 3 方法論提煉執行）

**審查狀態**：
- [ ] rosemary-project-manager 審查
- [ ] 整合回主方法論
- [ ] 建立引用連結
