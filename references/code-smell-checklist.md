# Code Smell 檢查清單

**版本**: v1.0.0
**建立日期**: 2025-10-11
**適用範圍**: 基於 Clean Architecture 五層架構的專案
**基於**: 《層級隔離派工方法論》(.claude/methodologies/layered-ticket-methodology.md)

---

## 📋 文件資訊

**目的**: 提供基於 Ticket 粒度的 Code Smell 檢測標準和檢查清單

**適用對象**:
- **PM** - Ticket 設計階段檢查
- **開發人員** - 實作階段自我檢查
- **Code Reviewer** - Code Review 階段檢查
- **架構師** - 架構設計審查

**與其他方法論的關係**:
- 引用《層級隔離派工方法論》(.claude/methodologies/layered-ticket-methodology.md) 的五層架構定義
- 配合 TDD 四階段流程使用
- 整合到 Hook 系統自動化檢測

**核心理念**:
Code Smell 檢查清單是基於層級隔離原則的程式品質檢測工具，從 Ticket 設計階段就能發現潛在的架構問題，實現「預防勝於治療」的品質管理策略。

---

## 第一章：Code Smell 概述和分類

### 1.1 什麼是 Code Smell

**定義**: Code Smell（程式異味）是指程式碼中表面上看似正常，但實際上暗示設計問題或潛在缺陷的特徵。

**核心特性**:
- ✅ **不是 Bug**: Code Smell 不會導致程式崩潰或功能錯誤
- ✅ **設計問題**: 暗示程式架構或設計上的缺陷
- ✅ **可檢測**: 透過明確的指標可以識別
- ✅ **可修正**: 透過重構可以消除

**與 Bug 的區別**:
```text
Bug（程式錯誤）:
- 導致功能失敗或程式崩潰
- 需要立即修正
- 透過測試失敗發現

Code Smell（程式異味）:
- 程式功能正常運作
- 暗示設計問題，未來可能導致維護困難
- 透過程式碼檢視或靜態分析發現
- 透過重構改善
```

**為什麼 Code Smell 重要**:
1. **降低維護成本**: 及早發現設計問題，避免技術債務累積
2. **提升程式碼品質**: 改善可讀性、可測試性、可擴展性
3. **預防未來問題**: 在問題惡化前進行修正
4. **團隊協作**: 提供統一的品質標準和溝通語言

---

### 1.2 為什麼需要 Code Smell 檢查清單

**傳統問題**:
- ❌ 依賴個人經驗判斷 Code Smell（主觀且不一致）
- ❌ 問題發現太晚（實作完成後才發現設計缺陷）
- ❌ 缺少量化標準（難以判斷是否需要重構）
- ❌ 修正成本高（架構問題需要大規模修改）

**檢查清單優勢**:
- ✅ **標準化**: 提供統一的檢測標準，避免主觀判斷
- ✅ **及早發現**: 從 Ticket 設計階段就能發現問題
- ✅ **量化指標**: 明確的數字標準（如行數、層級跨度）
- ✅ **降低成本**: 設計階段修正成本遠低於實作後修正

**Ticket 粒度檢測的價值**:
```text
設計階段檢測 vs 實作階段檢測：

設計階段（Ticket 粒度）:
- 修正成本: 低（只需要調整設計）
- 影響範圍: 小（尚未實作程式碼）
- 風險: 低（無需修改既有程式碼）

實作階段（Code Review）:
- 修正成本: 中（需要重寫部分程式碼）
- 影響範圍: 中（可能影響多個檔案）
- 風險: 中（需要回歸測試）

維護階段（上線後）:
- 修正成本: 高（需要大規模重構）
- 影響範圍: 大（可能影響多個模組）
- 風險: 高（可能引入新 Bug）
```

---

### 1.3 Code Smell 分類體系

基於《層級隔離派工方法論》(.claude/methodologies/layered-ticket-methodology.md) 的五層架構，本檢查清單將 Code Smell 分為三大類：

#### **分類 A：跨層級 Code Smells**（違反層級隔離原則）
這類 Code Smell 涉及多個架構層級，違反層級隔離和單層修改原則：

- **A1. Shotgun Surgery**（散彈槍手術）- 單一變更需要修改多個層級
- **A2. Feature Envy**（功能嫉妒）- 外層過度依賴內層實作細節
- **A3. Inappropriate Intimacy**（不當親密關係）- 層級間過度耦合
- **A4. Leaky Abstraction**（抽象滲漏）- 內層實作細節洩漏到外層

#### **分類 B：單層級 Code Smells**（違反單一職責原則）
這類 Code Smell 發生在單一層級內，違反單一職責原則（SRP）：

- **B1. Divergent Change**（發散式變更）- 單一類別承擔多個職責
- **B2. Large Class**（大類別）- 類別過大，職責不清
- **B3. Long Method**（長方法）- 方法過長，難以理解
- **B4. Dead Code**（死程式碼）- 永遠不會執行的程式碼

#### **分類 C：Ticket 粒度相關 Code Smells**
這類 Code Smell 與 Ticket 設計和粒度相關：

- **C1. God Ticket**（全能 Ticket）- Ticket 範圍過大，修改過多檔案
- **C2. Incomplete Ticket**（不完整 Ticket）- Ticket 缺少必要測試或文件
- **C3. Ambiguous Responsibility**（職責模糊 Ticket）- Ticket 職責定義不明確

#### 分類樹狀結構
```text
Code Smell 分類體系（基於《層級隔離派工方法論》第 2.2 節五層架構定義）

A. 跨層級 Code Smells（違反層級隔離）
   ├─ A1. Shotgun Surgery（散彈槍手術）
   ├─ A2. Feature Envy（功能嫉妒）
   ├─ A3. Inappropriate Intimacy（不當親密關係）
   └─ A4. Leaky Abstraction（抽象滲漏）

B. 單層級 Code Smells（違反單一職責）
   ├─ B1. Divergent Change（發散式變更）
   ├─ B2. Large Class（大類別）
   ├─ B3. Long Method（長方法）
   └─ B4. Dead Code（死程式碼）

C. Ticket 粒度相關 Code Smells
   ├─ C1. God Ticket（全能 Ticket）
   ├─ C2. Incomplete Ticket（不完整 Ticket）
   └─ C3. Ambiguous Responsibility（職責模糊 Ticket）
```

---

### 1.4 與《層級隔離派工方法論》的關係

**互補關係**:
- **《層級隔離派工方法論》**: 定義「應該怎麼做」（正面原則）
  - 五層架構定義（Layer 1-5）
  - 單層修改原則
  - Ticket 粒度標準

- **本檢查清單**: 定義「不應該怎麼做」（負面模式識別）
  - Code Smell 檢測方法
  - 違規模式識別
  - 重構策略

**引用關係**:
本檢查清單引用《層級隔離派工方法論》(.claude/methodologies/layered-ticket-methodology.md) 的以下章節：
- **2.2 節**: 五層架構完整定義
- **2.3 節**: 依賴方向規則
- **3.1 節**: 單層修改原則定義
- **5.2 節**: Ticket 粒度量化指標
- **6.2 節**: 檔案路徑分析法
- **6.5 節**: 違規模式識別

**無重複定義**:
本文件不重複定義五層架構，所有層級定義都引用《層級隔離派工方法論》第 2.2 節。

---

### 1.5 過度設計四反模式（Over-Engineering）

過度設計是「用比問題所需更複雜的方案」。它的成本（認知負擔、間接層、更多檔案）立即產生，效益（宣稱的未來彈性）卻常永不到來。以下四種是最常見的過度設計反模式，各附最小正反對照。

**判斷準則（核心測試）**：把碼拿給不熟專案的人看。若對方問「為什麼這裡要這樣抽象？」而答案是「以防我們之後需要……」，就是過度設計。「以防之後需要」不是需求，是對未來的猜測——缺乏證據支撐，錯誤率高於當下已驗證的需求。重複兩次再抽象——錯誤的抽象比重複昂貴得多。

#### 反模式 1：過早抽象（Premature Abstraction）

只有一種用途，卻建了支援多種實作的通用框架。

```python
# 壞味道：只需寄一種信，卻寫了策略模式框架
class EmailService:
    def __init__(self, provider: EmailProvider, template_engine: TemplateEngine): ...
    async def send(self, template, context, recipient, **kwargs): ...

# 好味道：需求就是寄一封歡迎信，寫這個就好
async def send_welcome_email(user):
    body = f"Welcome {user.name}! Your account is ready."
    await send_email(to=user.email, subject="Welcome", body=body)
```

#### 反模式 2：投機性錯誤處理（Speculative Error Handling）

為不可能發生的錯誤加防護；驗證自己上游已驗證過的輸入；對永不為 null 的值加 null 檢查。每一行錯誤處理都是別人要讀懂的一行。

```javascript
// 壞味道：value 來自本函式上游、已驗證、不可能為 null
function format(value) {
  if (value === null || value === undefined) throw new Error('unexpected null');
  return value.trim();
}
// 好味道：只處理真的會發生的錯誤
function format(value) { return value.trim(); }
```

#### 反模式 3：不必要的可配置性（Unnecessary Configurability）

把永遠不會變的值做成參數 / 環境變數。每個配置項都是別人要做的一個決定、要正確設定的一個值。

```python
# 壞味道：batch_size / retry_count 從沒有第二種取值
def process(items, batch_size=100, retry_count=3, backoff=2.0): ...
# 好味道：需要時再參數化，先硬編碼
def process(items):
    BATCH_SIZE = 100  # 有真實理由要變時再提取為參數
```

#### 反模式 4：死彈性（Dead Flexibility）

只有一個實作的介面、只有一個子類的抽象基底、只用一種型別實例化的泛型。這些在第二個實作真正出現前，只有成本沒有效益。

```typescript
// 壞味道：介面只有一個實作，且無測試替身需求
interface UserRepository { findById(id: string): User }
class PostgresUserRepository implements UserRepository { ... }  // 唯一實作
// 好味道：直接用類別，第二個實作出現時再抽介面
class UserRepository { findById(id: string): User { ... } }
```

> **與既有 smell 的關係**：本節聚焦「加太多」的過度設計；「未使用程式碼」的處理（既有死碼該不該刪、設計意圖溯源）見 quality-common.md §1.2.4；認知負擔量化閾值見 `.claude/rules/core/cognitive-load.md`。

---

## 第二章：基於層級隔離的 Code Smell 定義

### 2.1 A 類 Code Smell（跨層級問題）

#### 2.1.1 A1. Shotgun Surgery（散彈槍手術）

**定義**:
單一邏輯變更需要同時修改多個架構層級的程式碼，違反「單層修改原則」（《層級隔離派工方法論》第 3.1 節）。

**特徵識別**:
1. 一個小需求需要修改 UI、Behavior、UseCase、Domain 多層
2. 層級間缺乏適當的抽象介面
3. 變更影響範圍不可控
4. 檔案修改數量 > 5 個且跨 2 個以上層級

**與《層級隔離派工方法論》的關聯**:
- 違反「單層修改原則」（3.1 節）
- 違反「從外而內實作順序」（4.1 節）
- 未遵循「Ticket 粒度標準」（5.2 節）

**範例說明**:
```text
需求：書籍新增「出版社」欄位

❌ Shotgun Surgery 模式：
- Layer 1 (UI): BookDetailWidget 新增 publisher Text
- Layer 2 (Behavior): BookDetailController 新增 publisher 屬性
- Layer 3 (UseCase): GetBookDetailUseCase 新增 publisher 參數
- Layer 5 (Domain): Book Entity 新增 publisher 欄位

問題分析：
- 修改 4 個層級（Layer 1, 2, 3, 5）
- 修改至少 4 個檔案
- 違反單層修改原則
- 風險：任一層級修改錯誤都會影響整個功能

✅ 正確做法（引入 Facade）：
- Phase 1 [Layer 5]: Book Entity 新增 publisher 欄位
- Phase 2 [Layer 3]: BookDetailFacade 更新回傳資料
- Phase 3 [Layer 2]: Presenter 轉換新增 publisher
- Phase 4 [Layer 1]: UI 顯示 publisher

改善效果：
- 每個 Phase 只修改單一層級
- 變更影響範圍可控
- 風險降低
```

**好壞對比程式碼**:
```dart
// ❌ Shotgun Surgery：新增欄位需要修改 4 層

// Layer 5 (Domain)
class Book {
  final String title;
  final ISBN isbn;
  final String publisher; // 新增欄位
}

// Layer 3 (UseCase)
class GetBookDetailUseCase {
  Future<Book> execute(String id) async {
    final book = await repository.findById(id);
    // 需要處理 publisher
    return book;
  }
}

// Layer 2 (Behavior)
class BookDetailController {
  String? publisher; // 新增屬性

  void loadBookDetail(String id) async {
    final book = await getBookDetailUseCase.execute(id);
    publisher = book.publisher; // 新增處理
  }
}

// Layer 1 (UI)
class BookDetailWidget {
  Widget build(BuildContext context) {
    return Column(
      children: [
        Text(controller.title),
        Text(controller.publisher ?? ''), // 新增顯示
      ],
    );
  }
}

// ✅ 正確：引入 Facade 隔離變更

// Layer 4 (Domain Interface)
abstract class IBookDetailFacade {
  Future<BookDetailViewModel> getBookDetail(String id);
}

// Layer 3 (UseCase - Facade Implementation)
class BookDetailFacade implements IBookDetailFacade {
  Future<BookDetailViewModel> getBookDetail(String id) async {
    final book = await bookRepository.findById(id);
    return BookPresenter.toViewModel(book); // 統一轉換
  }
}

// Layer 2 (Behavior - Presenter)
class BookPresenter {
  static BookDetailViewModel toViewModel(Book book) {
    return BookDetailViewModel(
      title: book.title.value,
      isbn: book.isbn.value,
      publisher: book.publisher, // 新增欄位在這裡處理
    );
  }
}

// Layer 1 (UI) - 無需修改
class BookDetailWidget {
  Widget build(BuildContext context) {
    return Column(
      children: [
        Text(viewModel.title),
        Text(viewModel.isbn),
        Text(viewModel.publisher), // 直接使用 ViewModel
      ],
    );
  }
}

改善效果：
- 未來新增欄位只需要修改 Layer 3 (Facade) 和 Layer 2 (Presenter)
- Layer 1 (UI) 和 Layer 5 (Domain) 的修改影響已隔離
```

---

#### 2.1.2 A2. Feature Envy（功能嫉妒）

**定義**:
某層級過度依賴其他層級的實作細節，而非依賴抽象介面。外層直接存取內層的內部狀態，缺乏適當的 DTO 或 ViewModel 轉換。

**特徵識別**:
1. 外層直接存取內層的內部狀態（如 `book.isbn.value`）
2. 缺乏適當的 DTO 或 ViewModel 轉換
3. 跨層級的緊耦合
4. UI 層直接 import Domain Entity
5. 外層存取內層內部欄位次數 > 3 次

**與《層級隔離派工方法論》的關聯**:
- 違反「依賴倒置原則」（2.3 節）
- 違反 Layer 2 的「資料轉換職責」（2.2 節 Layer 2 定義）
- 缺少 Presenter 轉換層

**範例說明**:
```dart
// ❌ Feature Envy：UI 直接存取 Domain Entity

import 'package:book_overview_app/domains/library/entities/book.dart';
// ❌ UI 層不應 import Domain Entity

class BookDetailWidget extends StatelessWidget {
  final Book book; // ❌ 直接依賴 Domain Entity

  Widget build(BuildContext context) {
    return Column(
      children: [
        Text(book.title.value),        // ❌ 存取內部欄位
        Text(book.isbn.value),         // ❌ 存取內部欄位
        Text(book.author.name),        // ❌ 存取內部欄位
        Text(book.isNewRelease() ? '新書' : ''), // ❌ 呼叫 Domain 方法
      ],
    );
  }
}

問題分析：
- UI 層 import Domain Entity（違反依賴方向）
- UI 直接存取 Entity 內部欄位（緊耦合）
- UI 呼叫 Domain 業務方法（職責混亂）
- Domain 修改會影響 UI（高風險）

// ✅ 正確：透過 ViewModel 轉換

// Layer 2: 定義 ViewModel
import 'package:book_overview_app/presentation/view_models/book_view_model.dart';

class BookViewModel {
  final String title;
  final String isbn;
  final String author;
  final bool isNew;

  BookViewModel({
    required this.title,
    required this.isbn,
    required this.author,
    required this.isNew,
  });
}

// Layer 2: Presenter 轉換（資料轉換職責）
class BookPresenter {
  static BookViewModel toViewModel(Book book) {
    return BookViewModel(
      title: book.title.value,      // 提取內部欄位
      isbn: book.isbn.value,        // 提取內部欄位
      author: book.author.name,     // 提取內部欄位
      isNew: book.isNewRelease(),   // 執行 Domain 方法
    );
  }
}

// Layer 1: UI 使用 ViewModel
class BookDetailWidget extends StatelessWidget {
  final BookViewModel viewModel; // ✅ 依賴 ViewModel

  Widget build(BuildContext context) {
    return Column(
      children: [
        Text(viewModel.title),    // ✅ 使用轉換後的資料
        Text(viewModel.isbn),     // ✅ 使用轉換後的資料
        Text(viewModel.author),   // ✅ 使用轉換後的資料
        Text(viewModel.isNew ? '新書' : ''), // ✅ 使用轉換後的狀態
      ],
    );
  }
}

改善效果：
- UI 層不依賴 Domain Entity（降低耦合）
- Presenter 集中處理資料轉換（符合 Layer 2 職責）
- Domain 修改不影響 UI（只需調整 Presenter）
- 測試更容易（Mock ViewModel 即可）
```

---

#### 2.1.3 A3. Inappropriate Intimacy（不當親密關係）

**定義**:
層級間過度耦合，內層知道外層的存在或依賴外層，違反依賴方向規則。

**特徵識別**:
1. Domain 層依賴 UseCase 或 UI 層
2. 依賴方向錯誤（內層依賴外層）
3. 存在循環依賴
4. Domain Entity 包含 UI 或 Infrastructure 的 import

**與《層級隔離派工方法論》的關聯**:
- 違反「依賴方向規則」（2.3 節）
- 違反「Layer 5 不依賴任何層級」原則
- 正確依賴方向：Layer 1 → Layer 2 → Layer 3 → Layer 4 ← Layer 5

**範例說明**:
```dart
// ❌ Inappropriate Intimacy：Domain 依賴 UseCase

// Layer 5 (Domain)
import 'package:book_overview_app/application/use_cases/add_book_to_favorite_use_case.dart';
// ❌ Domain 不應 import UseCase

class Book {
  final String id;
  final Title title;
  final AddBookToFavoriteUseCase favoriteUseCase; // ❌ Domain 依賴 UseCase

  void addToFavorite() {
    favoriteUseCase.execute(this.id); // ❌ Domain 不應呼叫 UseCase
  }
}

問題分析：
- Domain 依賴外層（UseCase）
- 違反依賴方向規則
- Domain 失去獨立性和可重用性
- 測試困難（Domain 測試需要 Mock UseCase）

// ✅ 正確：Domain 只定義業務邏輯

// Layer 5 (Domain) - 獨立且純淨
class Book {
  final String id;
  final Title title;
  bool isFavorited = false; // ✅ 只記錄狀態

  void markAsFavorite() {
    this.isFavorited = true; // ✅ 只處理業務邏輯
  }

  void unmarkFromFavorite() {
    this.isFavorited = false;
  }
}

// Layer 3 (UseCase) - 協調業務流程
class AddBookToFavoriteUseCase {
  final IBookRepository bookRepository;
  final IFavoriteRepository favoriteRepository;

  Future<void> execute(String bookId) async {
    // 1. 取得書籍
    final book = await bookRepository.findById(bookId);

    // 2. 執行 Domain 方法
    book.markAsFavorite(); // ✅ UseCase 呼叫 Domain 方法

    // 3. 儲存狀態
    await bookRepository.save(book);
    await favoriteRepository.add(bookId);
  }
}

// Layer 2 (Behavior/Controller) - 觸發 UseCase
class BookDetailController {
  final AddBookToFavoriteUseCase addToFavoriteUseCase;

  void onFavoriteButtonPressed(String bookId) async {
    await addToFavoriteUseCase.execute(bookId); // ✅ 正確的呼叫方向
  }
}

改善效果：
- Domain 獨立且純淨（不依賴外層）
- 依賴方向正確（Layer 2 → Layer 3 → Layer 5）
- Domain 可重用性高
- 測試容易（Domain 無外部依賴）
```

---

#### 2.1.4 A4. Leaky Abstraction（抽象滲漏）

**定義**:
內層的實作細節透過介面洩漏到外層，介面不夠抽象。

**特徵識別**:
1. Repository 介面包含資料庫特定參數（如 SQL 語句）
2. Domain Event 包含 UI 特定資料（如 Widget 狀態）
3. 抽象介面不夠抽象，包含實作關鍵字
4. 介面方法名稱洩漏實作細節

**與《層級隔離派工方法論》的關聯**:
- 違反 Layer 4「介面契約」的職責定義（2.2 節）
- 介面應該隱藏實作細節

**範例說明**:
```dart
// ❌ Leaky Abstraction：介面洩漏實作細節

// Layer 4 (Domain Interface)
abstract class IBookRepository {
  Future<Book> findBySql(String sql);        // ❌ 洩漏 SQL 實作
  Future<List<Book>> queryWithCursor(Cursor cursor); // ❌ 洩漏資料庫 Cursor
  Future<void> saveToSqlite(Book book);      // ❌ 洩漏 SQLite 實作
}

問題分析：
- 介面包含「SQL」、「Cursor」、「Sqlite」等實作關鍵字
- 外層（UseCase）需要知道使用 SQL 資料庫
- 無法更換實作（綁定 SQLite）
- 違反介面契約原則

// ✅ 正確：抽象介面

// Layer 4 (Domain Interface) - 抽象且純淨
abstract class IBookRepository {
  Future<Book> findById(String id);          // ✅ 隱藏實作細節
  Future<List<Book>> findByAuthor(String author); // ✅ 業務概念
  Future<List<Book>> findAll();              // ✅ 簡單明確
  Future<void> save(Book book);              // ✅ 抽象操作
  Future<void> delete(String id);            // ✅ 抽象操作
}

// Layer 5 (Infrastructure) - 具體實作可替換
class SqliteBookRepository implements IBookRepository {
  @override
  Future<Book> findById(String id) async {
    // SQL 實作細節在這裡
    final result = await db.query(
      'books',
      where: 'id = ?',
      whereArgs: [id],
    );
    return Book.fromJson(result.first);
  }
}

// Layer 5 (Infrastructure) - 另一種實作
class FirestoreBookRepository implements IBookRepository {
  @override
  Future<Book> findById(String id) async {
    // Firestore 實作細節在這裡
    final doc = await firestore.collection('books').doc(id).get();
    return Book.fromJson(doc.data()!);
  }
}

改善效果：
- 介面抽象且純淨（不包含實作細節）
- 可輕鬆更換實作（SQLite → Firestore）
- UseCase 不需要知道資料庫實作
- 符合依賴倒置原則
```

---

### 2.2 B 類 Code Smell（單層級問題）

#### 2.2.1 B1. Divergent Change（發散式變更）

**定義**:
單一類別因不同原因需要修改，違反 Single Responsibility Principle（SRP）。

**特徵識別**:
1. 一個 Controller 同時負責多個頁面的邏輯
2. 一個 UseCase 處理多個不相關的業務流程
3. 變更原因不單一（有 2+ 個變更原因）
4. 類別方法可以明確分組（2+ 個分組）

**與《層級隔離派工方法論》的關聯**:
- 違反「單層修改原則」的 SRP 理論依據（3.2 節）
- 違反「變更原因單一」要求（3.1 節）

**範例說明**:
```dart
// ❌ Divergent Change：單一 Controller 承擔多個職責

class BookController {
  // 群組 A：列表頁面邏輯（3 個方法）
  List<BookViewModel> bookList = [];

  void loadBookList() {
    // 載入書籍列表
  }

  void refreshBookList() {
    // 重新整理列表
  }

  void sortBookList(String sortBy) {
    // 排序列表
  }

  // 群組 B：詳情頁面邏輯（3 個方法）
  BookViewModel? bookDetail;

  void loadBookDetail(String id) {
    // 載入書籍詳情
  }

  void updateBookDetail() {
    // 更新書籍詳情
  }

  void deleteBook() {
    // 刪除書籍
  }

  // 群組 C：搜尋邏輯（2 個方法）
  List<BookViewModel> searchResults = [];

  void searchBooks(String query) {
    // 搜尋書籍
  }

  void clearSearchResults() {
    // 清空搜尋結果
  }
}

問題分析：
- 3 個方法群組（列表、詳情、搜尋）
- 3 種變更原因（列表變更、詳情變更、搜尋變更）
- 類別名稱過於籠統（BookController）
- 違反 SRP 原則

// ✅ 正確：拆分為多個單一職責 Controller

// Controller 1：只負責列表
class BookListController {
  List<BookViewModel> bookList = [];

  void loadBookList() { }
  void refreshBookList() { }
  void sortBookList(String sortBy) { }
}

// Controller 2：只負責詳情
class BookDetailController {
  BookViewModel? bookDetail;

  void loadBookDetail(String id) { }
  void updateBookDetail() { }
  void deleteBook() { }
}

// Controller 3：只負責搜尋
class BookSearchController {
  List<BookViewModel> searchResults = [];

  void searchBooks(String query) { }
  void clearSearchResults() { }
}

改善效果：
- 每個 Controller 只有 1 個變更原因
- 職責明確且單一
- 可讀性提升
- 測試更容易（測試範圍更小）
```

---

#### 2.2.2 B2. Large Class（大類別）

**定義**:
類別過大，包含過多方法和屬性，職責不清。

**特徵識別（量化標準，引用《層級隔離派工方法論》第 5.2 節）**:
- 總行數: > 300 行
- public 方法: > 15 個
- 屬性: > 12 個
- 類別職責無法用一句話清楚描述

**範例說明**:
```dart
// ❌ Large Class：職責過多（500+ 行）

class BookService { // 總行數：500+ 行
  // 新增書籍（20 個方法）
  Future<void> addBook(Book book) { }
  Future<void> addMultipleBooks(List<Book> books) { }
  Future<void> importBooksFromCsv(String filePath) { }
  // ... 17 個其他方法

  // 查詢書籍（15 個方法）
  Future<Book> findBook(String id) { }
  Future<List<Book>> findBooksByAuthor(String author) { }
  Future<List<Book>> searchBooks(String query) { }
  // ... 12 個其他方法

  // 統計分析（10 個方法）
  Future<BookStats> getStatistics() { }
  Future<Map<String, int>> getBooksByGenre() { }
  Future<List<Book>> getMostPopular() { }
  // ... 7 個其他方法

  // 匯出報表（8 個方法）
  Future<void> exportReport() { }
  Future<void> exportToPdf() { }
  Future<void> exportToExcel() { }
  // ... 5 個其他方法
}

問題分析：
- 總行數: 500+ 行（超過 300 行標準）
- public 方法: 53 個（超過 15 個標準）
- 4 種不同職責（新增、查詢、統計、匯出）
- 違反 SRP 原則

// ✅ 正確：拆分為多個職責明確的 Service

// Service 1：書籍管理（新增、更新、刪除）
class BookManagementService {
  Future<void> addBook(Book book) { }
  Future<void> updateBook(Book book) { }
  Future<void> deleteBook(String id) { }
}

// Service 2：書籍查詢
class BookQueryService {
  Future<Book> findById(String id) { }
  Future<List<Book>> findByAuthor(String author) { }
  Future<List<Book>> search(String query) { }
}

// Service 3：書籍統計
class BookStatisticsService {
  Future<BookStats> getStatistics() { }
  Future<Map<String, int>> getBooksByGenre() { }
  Future<List<Book>> getMostPopular() { }
}

// Service 4：報表匯出
class BookReportService {
  Future<void> exportToPdf() { }
  Future<void> exportToExcel() { }
  Future<void> exportToCsv() { }
}

改善效果：
- 每個 Service < 200 行
- 職責單一且明確
- 可測試性提升
- 可維護性提升
```

---

#### 2.2.3 B3. Long Method（長方法）

**定義**:
方法過長，難以理解和測試。

**特徵識別（量化標準）**:
- 方法行數: > 50 行
- 巢狀層級: > 3 層
- 邏輯區塊: > 4 個（用註解分隔）
- 方法名稱包含「And」（如 `validateAndSaveBook`）

**範例說明**:
```dart
// ❌ Long Method：80 行方法

Future<void> processBookOrder(Order order) async {
  // 驗證訂單（20 行）
  if (order.items.isEmpty) {
    throw ValidationException('訂單不能為空');
  }

  for (var item in order.items) {
    if (item.quantity <= 0) {
      throw ValidationException('數量必須大於 0');
    }
    if (item.price < 0) {
      throw ValidationException('價格不能為負數');
    }
  }

  // 計算價格（20 行）
  double total = 0;
  double discount = 0;

  for (var item in order.items) {
    total += item.price * item.quantity;
  }

  if (total > 1000) {
    discount = total * 0.1;
  } else if (total > 500) {
    discount = total * 0.05;
  }

  total -= discount;

  // 庫存檢查（20 行）
  for (var item in order.items) {
    final stock = await inventoryRepository.getStock(item.bookId);
    if (stock < item.quantity) {
      throw InsufficientStockException(
        '書籍 ${item.bookId} 庫存不足'
      );
    }
  }

  // 建立訂單（20 行）
  order.total = total;
  order.discount = discount;
  order.status = OrderStatus.pending;
  order.createdAt = DateTime.now();

  await repository.save(order);

  // 扣除庫存
  for (var item in order.items) {
    await inventoryRepository.reduceStock(
      item.bookId,
      item.quantity,
    );
  }
}

問題分析：
- 方法行數: 80 行（超過 50 行標準）
- 4 個邏輯區塊（驗證、計算、庫存、建立）
- 巢狀層級: 3 層（for + if）
- 難以理解和測試

// ✅ 正確：拆分為多個小方法

Future<void> processBookOrder(Order order) async {
  _validateOrder(order);              // 步驟 1
  final total = _calculateTotal(order); // 步驟 2
  await _checkInventory(order);       // 步驟 3
  await _saveOrder(order, total);     // 步驟 4
}

void _validateOrder(Order order) {
  if (order.items.isEmpty) {
    throw ValidationException('訂單不能為空');
  }

  for (var item in order.items) {
    _validateOrderItem(item);
  }
}

void _validateOrderItem(OrderItem item) {
  if (item.quantity <= 0) {
    throw ValidationException('數量必須大於 0');
  }
  if (item.price < 0) {
    throw ValidationException('價格不能為負數');
  }
}

double _calculateTotal(Order order) {
  double total = 0;

  for (var item in order.items) {
    total += item.price * item.quantity;
  }

  final discount = _calculateDiscount(total);
  return total - discount;
}

double _calculateDiscount(double total) {
  if (total > 1000) return total * 0.1;
  if (total > 500) return total * 0.05;
  return 0;
}

Future<void> _checkInventory(Order order) async {
  for (var item in order.items) {
    final stock = await inventoryRepository.getStock(item.bookId);
    if (stock < item.quantity) {
      throw InsufficientStockException(
        '書籍 ${item.bookId} 庫存不足'
      );
    }
  }
}

Future<void> _saveOrder(Order order, double total) async {
  order.total = total;
  order.status = OrderStatus.pending;
  order.createdAt = DateTime.now();

  await repository.save(order);
  await _reduceInventory(order);
}

Future<void> _reduceInventory(Order order) async {
  for (var item in order.items) {
    await inventoryRepository.reduceStock(
      item.bookId,
      item.quantity,
    );
  }
}

改善效果：
- 主方法只有 4 行（清楚的流程）
- 每個私有方法 < 20 行
- 邏輯分離且可測試
- 可讀性大幅提升
```

---

#### 2.2.4 B4. Dead Code（死程式碼）

**定義**:
永遠不會執行或使用的程式碼。

**特徵識別**:
- 未被呼叫的方法
- 無法到達的程式碼分支
- 註解掉的程式碼超過 1 週
- `dart analyze` 顯示 `unused_element` 警告

**自動化檢測方法**:
```bash
# 檢測 unused 警告
dart analyze | grep "unused"

# 檢測程式碼覆蓋率
flutter test --coverage
genhtml coverage/lcov.info -o coverage/html
# 檢查 coverage/html 中 0% 覆蓋率的程式碼

# 搜尋註解掉的程式碼
grep -r "^[[:space:]]*//.*{" lib/
```

**範例說明**:
```dart
// ❌ Dead Code 範例

class BookService {
  // 未使用的方法（dart analyze 會警告）
  void unusedMethod() {
    print('這個方法從未被呼叫');
  }

  // 無法到達的程式碼
  void processBook(Book book) {
    return; // 提前返回

    // ❌ 以下程式碼永遠不會執行
    print('處理書籍');
    saveBook(book);
  }

  // 註解掉的程式碼（已過時）
  // void oldImplementation() {
  //   // 舊的實作方式，已被新方法取代
  //   // 但程式碼保留了 2 個月
  // }

  // 未使用的變數
  final String unusedVariable = 'never used';
}

// ✅ 正確：移除 Dead Code

class BookService {
  // 只保留實際使用的方法
  void processBook(Book book) {
    print('處理書籍');
    saveBook(book);
  }
}

改善效果：
- 程式碼簡潔
- 降低維護成本
- 無混淆和誤導
```

---

### 2.3 C 類 Code Smell（Ticket 粒度問題）

#### 2.3.1 C1. God Ticket（全能 Ticket）

**定義**:
單一 Ticket 修改過多檔案和層級，範圍失控。

**特徵識別（引用《層級隔離派工方法論》第 5.2 節量化標準）**:
- 修改檔案數 > 10 個
- 跨 3 個以上架構層級
- 預估工時 > 16 小時（2 天）

**與《層級隔離派工方法論》的關聯**:
- 違反「Ticket 粒度標準」（5.2 節）
- 違反「單層修改原則」（3.1 節）

**檢測方法**:
```text
步驟 1: 計算 Ticket 涉及的檔案數
步驟 2: 判斷檔案所屬的層級
步驟 3: 計算跨幾個層級
  ├─ > 3 層級 → God Ticket ❌
  └─ 1 層級 → 良好 Ticket ✅
```

**範例說明**:
```text
Ticket: 新增「書籍評分」完整功能

檔案清單（12 個檔案）:
1. lib/presentation/widgets/book_detail_widget.dart (Layer 1)
2. lib/presentation/widgets/rating_widget.dart (Layer 1)
3. lib/presentation/controllers/book_detail_controller.dart (Layer 2)
4. lib/presentation/controllers/rating_controller.dart (Layer 2)
5. lib/application/use_cases/rate_book_use_case.dart (Layer 3)
6. lib/application/use_cases/get_book_rating_use_case.dart (Layer 3)
7. lib/domain/entities/book.dart (Layer 5)
8. lib/domain/entities/rating.dart (Layer 5)
9. lib/domain/value_objects/rating_value.dart (Layer 5)
10. lib/infrastructure/repositories/book_repository_impl.dart (Layer 5)
11. lib/infrastructure/repositories/rating_repository_impl.dart (Layer 5)
12. lib/infrastructure/database/rating_table.dart (Layer 5)

分析結果:
- 檔案數: 12 個（> 10 個標準）
- 層級跨度: 4 層（Layer 1, 2, 3, 5）
- 預估工時: 24 小時（> 16 小時標準）
- 判斷: God Ticket ❌

建議拆分（引用《層級隔離派工方法論》第 5.4 節拆分指引）:
- Ticket 1 [Layer 5]: Rating Value Object 和 Entity 設計
- Ticket 2 [Layer 5]: Rating Repository 實作
- Ticket 3 [Layer 3]: RateBookUseCase 實作
- Ticket 4 [Layer 3]: GetBookRatingUseCase 實作
- Ticket 5 [Layer 2]: Controller 整合 UseCase
- Ticket 6 [Layer 1]: UI 新增評分元件

改善效果:
- 每個 Ticket 只修改 1-3 個檔案
- 每個 Ticket 只涉及 1 個層級
- 預估工時: 每個 Ticket 2-4 小時
- 風險可控
```

---

#### 2.3.2 C2. Incomplete Ticket（不完整 Ticket）

**定義**:
Ticket 缺少必要的測試、文件或驗收條件。

**特徵識別**:
- 沒有測試檔案（Phase 2 缺失）
- 沒有驗收條件（Phase 1 設計不完整）
- 沒有更新相關文件
- 沒有完整的 TDD 四階段記錄

**檢測方法（基於 TDD 四階段要求）**:
```text
完整 Ticket 必須包含:
- ✅ Phase 1: 功能設計完成
- ✅ Phase 2: 測試設計完成（測試檔案存在）
- ✅ Phase 3: 實作完成（程式碼檔案）
- ✅ Phase 4: 重構評估完成

Incomplete Ticket 特徵:
- ❌ 缺少測試檔案（Phase 2 未完成）
- ❌ 缺少驗收條件（Phase 1 設計不完整）
- ❌ 缺少工作日誌（無法追蹤進度）
```

**檢測流程（Code Review 階段）**:
```text
步驟 1: 檢查 git diff 中的檔案
  ├─ 是否包含 test/ 目錄的檔案？
  └─ 測試檔案數量 vs 程式碼檔案數量比例

步驟 2: 檢查 Ticket 描述
  └─ 是否包含「驗收條件」章節？

步驟 3: 檢查工作日誌
  ├─ docs/work-logs/vX.Y.Z-*.md 是否存在？
  └─ 是否完成 Phase 1-4 記錄？
```

---

#### 2.3.3 C3. Ambiguous Responsibility（職責模糊 Ticket）

**定義**:
Ticket 的職責定義不明確，無法判斷屬於哪一層級。

**特徵識別**:
- Ticket 標題沒有標明層級（如 [Layer X]）
- 描述中混合多個層級的職責
- 驗收條件跨多個層級

**檢測方法**:
```text
職責明確 Ticket 格式:
標題: [Layer X] 清楚的功能描述
描述: 明確說明修改哪一層的哪個檔案
驗收: 只驗證該層級的職責

職責模糊 Ticket 特徵:
標題: 沒有 [Layer X] 標示
描述: 混合多個層級的職責
驗證: 跨多個層級的驗證
```

**範例說明**:
```text
❌ 職責模糊 Ticket:
標題: 實作書籍詳情頁面
描述: 實作書籍詳情頁面的所有功能
驗收: 可以顯示書籍詳情

問題分析:
- 無層級標示
- 「所有功能」範圍不明確
- 驗收條件過於籠統

✅ 職責明確 Ticket:
標題: [Layer 2] 實作書籍詳情頁面事件處理
描述: 實作 BookDetailController 的事件處理方法，
      整合 GetBookDetailUseCase 並轉換為 ViewModel
驗收:
  - BookDetailController.loadBookDetail() 呼叫 UseCase
  - BookPresenter.toViewModel() 正確轉換資料
  - 錯誤處理正確顯示錯誤訊息

改善效果:
- 層級明確（Layer 2）
- 職責清楚（事件處理 + 資料轉換）
- 驗收條件可驗證
```

---

## 第三章：Ticket 粒度檢測方法

### 3.1 檢測時機和流程

**核心理念**: 從 Ticket 設計階段就能發現 Code Smell，比實作完成後才發現更有效率。

**檢測時機對應 TDD 四階段**:

| 階段 | 檢測時機 | 檢測重點 | 對應 Code Smell |
|------|---------|---------|---------------|
| **Phase 1 設計階段** | Ticket 設計完成時 | Ticket 粒度和層級定位 | C1, C2, C3, A1 |
| **Phase 2 測試設計** | 測試設計完成時 | 測試範圍是否限定在單一層級 | C2, B1 |
| **Phase 3 實作執行** | 程式碼提交時 | 實作是否產生 Code Smell | A2, A3, A4, B2, B3 |
| **Code Review** | PR 提交時 | 最終驗證 | 所有 Code Smell |
| **Phase 4 重構階段** | 重構評估時 | 識別需要重構的 Code Smell | B1, B2, B3, B4 |

**檢測流程總覽**:
```text
Ticket 設計（Phase 1）
  ↓
檢查 Ticket 粒度（C1, C3, A1）
  ├─ 通過 → 測試設計（Phase 2）
  └─ 失敗 → 拆分 Ticket

測試設計（Phase 2）
  ↓
檢查測試範圍（C2）
  ├─ 通過 → 實作執行（Phase 3）
  └─ 失敗 → 補充測試

實作執行（Phase 3）
  ↓
檢查程式碼品質（A2, A3, A4, B2, B3）
  ├─ 通過 → Code Review
  └─ 失敗 → 修正程式碼

Code Review
  ↓
全面檢查所有 Code Smell
  ├─ 通過 → 合併 PR
  └─ 失敗 → 重構

Phase 4 重構評估
  ↓
識別需要重構的 Code Smell（B1, B2, B3, B4）
  ├─ 有需要 → 執行重構
  └─ 無需要 → 完成
```

---

### 3.2 A 類 Code Smell 檢測方法（跨層級問題）

#### 3.2.1 A1. Shotgun Surgery 檢測

**檢測指標**:
1. **檔案數量指標**: 單一 Ticket 修改的檔案數
2. **層級跨度指標**: Ticket 涉及的層級數量
3. **依賴鏈長度指標**: 從 UI 到 Domain 的依賴鏈長度

**判斷標準**（引用《層級隔離派工方法論》第 5.2 節）:
```text
良好 Ticket（單層修改）:
- 檔案數: 1-5 個
- 層級跨度: 1 層
- 依賴鏈: 不需要修改

需要注意（考慮拆分）:
- 檔案數: 6-10 個
- 層級跨度: 2 層
- 依賴鏈: 需要修改 1-2 層

Shotgun Surgery（散彈槍手術）:
- 檔案數: > 10 個
- 層級跨度: > 2 層
- 依賴鏈: 需要同步修改多層
```

**檢測流程**（基於《層級隔離派工方法論》第 6.2 節檔案路徑分析法）:
```text
步驟 1: 列出 Ticket 涉及的所有檔案
步驟 2: 使用《層級隔離派工方法論》第 2.4 節的決策樹判斷每個檔案屬於哪一層
步驟 3: 統計跨幾個層級
  ├─ 1 層級 → 良好設計 ✅
  ├─ 2 層級 → 需要檢查是否可拆分 ⚠️
  └─ > 2 層級 → Shotgun Surgery ❌

步驟 4: 如果檢測到 Shotgun Surgery
  ├─ 檢查是否為特殊場景（架構遷移、Hotfix）
  ├─ 分析是否可以拆分為多個 Ticket
  └─ 評估架構設計是否有問題（引入 Adapter/Facade）
```

---

#### 3.2.2 A2. Feature Envy 檢測

**檢測指標**:
1. **直接依賴指標**: 外層是否直接依賴內層的具體類別
2. **欄位存取指標**: 外層存取內層的內部欄位次數
3. **ViewModel 缺失指標**: Layer 2 是否缺少資料轉換

**判斷標準**:
```text
良好設計:
- UI 依賴 ViewModel，不依賴 Domain Entity
- Controller 包含 Presenter 轉換邏輯
- 透過介面依賴，不依賴具體實作

Feature Envy:
- UI 直接依賴 Domain Entity
- 直接存取 Entity 的內部欄位（如 book.isbn.value）
- 缺少 ViewModel 或 Presenter 轉換層
- 欄位存取次數 > 3 次
```

**檢測流程**:
```text
步驟 1: 檢查 UI Widget 的依賴
  ├─ 是否直接依賴 Domain Entity？
  └─ 是否透過 ViewModel？

步驟 2: 檢查 Controller 是否包含 Presenter
  ├─ 是否有 toViewModel() 轉換方法？
  └─ 是否直接將 Entity 傳給 UI？

步驟 3: 統計內層欄位存取次數
  ├─ 存取 Entity 內部欄位（如 .value）> 3 次 → Feature Envy ❌
  └─ 透過 ViewModel 存取 → 良好設計 ✅
```

---

#### 3.2.3 A3. Inappropriate Intimacy 檢測

**檢測指標**:
1. **依賴方向檢查**: 內層是否依賴外層
2. **循環依賴檢查**: 是否存在雙向依賴
3. **Domain 純淨度檢查**: Domain 是否包含 UI 或 Infrastructure 依賴

**判斷標準**（引用《層級隔離派工方法論》第 2.3 節依賴方向規則）:
```text
正確依賴方向（外層→內層）:
Layer 1 → Layer 2 → Layer 3 → Layer 4 ← Layer 5

違反依賴方向（Inappropriate Intimacy）:
- Layer 5 → Layer 3（Domain 依賴 UseCase）❌
- Layer 5 → Layer 2（Domain 依賴 Controller）❌
- Layer 3 ← → Layer 5（循環依賴）❌
```

**檢測流程**:
```text
步驟 1: 檢查 Domain Entity 的 import 語句
  ├─ 是否 import UseCase？ → ❌
  ├─ 是否 import Controller？ → ❌
  └─ 只 import 同層或 Layer 4 介面？ → ✅

步驟 2: 檢查 UseCase 的依賴
  ├─ 是否依賴 Layer 4 介面？ → ✅
  └─ 是否依賴 Layer 5 具體類別？ → ❌（應透過介面）

步驟 3: 使用工具檢測循環依賴
  └─ dart analyze 會報告循環依賴錯誤
```

---

#### 3.2.4 A4. Leaky Abstraction 檢測

**檢測指標**:
1. **介面純淨度**: 介面是否包含實作細節
2. **參數檢查**: 方法參數是否洩漏實作資訊
3. **回傳類型檢查**: 是否回傳 Infrastructure 特定類型

**判斷標準**:
```text
良好抽象介面:
- 方法名稱描述「做什麼」，不描述「怎麼做」
- 參數是 Domain 概念，不是技術細節
- 不包含資料庫、網路等實作關鍵字

Leaky Abstraction:
- 介面包含 SQL、HTTP、Cache 等關鍵字
- 參數包含資料庫特定類型（如 Cursor）
- 回傳類型包含框架特定類型（如 HttpResponse）
```

**檢測流程**:
```text
步驟 1: 檢查 Repository 介面定義
  ├─ 方法名稱是否包含實作關鍵字？
  │  - findBySql() → ❌ 洩漏 SQL
  │  - findById() → ✅ 抽象概念
  │
  └─ 參數類型是否為 Domain 類型？
     - String sql → ❌ 技術細節
     - String id → ✅ Domain 概念

步驟 2: 檢查 Event 定義
  └─ 是否包含 UI 特定資料（如 BuildContext）？ → ❌
```

---

### 3.3 B 類 Code Smell 檢測方法（單層級問題）

#### 3.3.1 B1. Divergent Change 檢測

**檢測指標**:
1. **類別職責數量**: 類別承擔幾個不同的職責
2. **變更原因數量**: 有幾種不同的原因需要修改此類別
3. **方法分組檢查**: 方法是否可以明確分組

**判斷標準**:
```text
單一職責類別:
- 只有 1 個變更原因
- 類別職責可以用一句話描述
- 所有方法圍繞同一個核心概念

Divergent Change:
- > 2 個變更原因（如「列表變更」和「詳情變更」）
- 方法可以分為 2+ 個明確的群組
- 類別名稱過於籠統（如 BookController、BookService）
```

**檢測流程**:
```text
步驟 1: 分析類別的 public 方法
  └─ 將方法按職責分組

步驟 2: 統計分組數量
  ├─ 1 組 → 單一職責 ✅
  ├─ 2 組 → 考慮拆分 ⚠️
  └─ > 2 組 → Divergent Change ❌

步驟 3: 檢查歷史修改記錄
  └─ git log --oneline {file}
  └─ 分析修改原因是否多樣化
```

---

#### 3.3.2 B2. Large Class 檢測

**檢測指標**:
1. **程式碼行數**: 類別總行數
2. **方法數量**: public 方法數量
3. **屬性數量**: instance 變數數量

**判斷標準**（量化指標）:
```text
良好大小類別:
- 總行數: < 200 行
- public 方法: < 10 個
- 屬性: < 8 個

需要注意（考慮拆分）:
- 總行數: 200-300 行
- public 方法: 10-15 個
- 屬性: 8-12 個

Large Class:
- 總行數: > 300 行
- public 方法: > 15 個
- 屬性: > 12 個
```

**自動化檢測方法**:
```bash
# 檢測單一檔案行數
wc -l lib/presentation/controllers/book_controller.dart

# 檢測所有 Controller 檔案大小
find lib -name "*_controller.dart" -exec wc -l {} \; | sort -rn

# 使用 dart analyze 檢測複雜度
# （需要配置 analysis_options.yaml）
```

---

#### 3.3.3 B3. Long Method 檢測

**檢測指標**:
1. **方法行數**: 方法內程式碼行數
2. **巢狀層級**: if/for/while 的巢狀深度
3. **區塊數量**: 方法內邏輯區塊數量（用註解分隔）

**判斷標準**:
```text
良好方法:
- 行數: < 30 行
- 巢狀層級: < 3 層
- 邏輯區塊: < 3 個

需要注意:
- 行數: 30-50 行
- 巢狀層級: 3 層
- 邏輯區塊: 3-4 個

Long Method:
- 行數: > 50 行
- 巢狀層級: > 3 層
- 邏輯區塊: > 4 個
```

**檢測流程**:
```text
步驟 1: 統計方法行數
  └─ 從方法簽名到結束大括號的行數

步驟 2: 分析巢狀層級
  └─ 統計最深的 if/for/while 巢狀深度

步驟 3: 識別邏輯區塊
  └─ 統計註解數量（通常用來分隔邏輯區塊）
  └─ > 3 個註解區塊 → 應該拆分方法

步驟 4: 檢查方法命名
  └─ 方法名稱是否包含「And」？ → 可能做太多事情
     - validateAndSaveBook() → 應拆分為 validate() 和 save()
```

---

#### 3.3.4 B4. Dead Code 檢測

**檢測方法**:
1. **使用 dart analyze 檢測 unused 警告**
2. **使用 code coverage 工具檢測 0% 覆蓋率程式碼**
3. **手動檢查註解掉的程式碼**

**自動化檢測**:
```bash
# 檢測 unused 警告
dart analyze | grep "unused"

# 檢測程式碼覆蓋率
flutter test --coverage
genhtml coverage/lcov.info -o coverage/html
# 檢查 coverage/html 中 0% 覆蓋率的程式碼

# 搜尋註解掉的程式碼
grep -r "^[[:space:]]*//.*{" lib/
```

---

### 3.4 C 類 Code Smell 檢測方法（Ticket 粒度問題）

#### 3.4.1 C1. God Ticket 檢測

**檢測指標**（引用《層級隔離派工方法論》第 5.2 節）:
1. **檔案修改數量**: 計算 git diff 涉及的檔案數
2. **層級跨度**: 涉及幾個架構層級
3. **預估工時**: Ticket 的預估完成時間

**判斷標準**:
```text
良好 Ticket 粒度:
- 檔案數: 1-5 個
- 層級跨度: 1 層
- 預估工時: 2-8 小時（1 個工作天內）

需要拆分:
- 檔案數: 6-10 個
- 層級跨度: 2 層
- 預估工時: 8-16 小時（1-2 天）

God Ticket:
- 檔案數: > 10 個
- 層級跨度: > 2 層
- 預估工時: > 16 小時（> 2 天）
```

**檢測流程**（Ticket 設計階段）:
```text
步驟 1: 列出 Ticket 需要修改的檔案清單
步驟 2: 統計檔案數量
步驟 3: 使用《層級隔離派工方法論》第 2.4 節決策樹判斷每個檔案的層級
步驟 4: 計算層級跨度
步驟 5: 評估預估工時

判斷:
  ├─ 符合良好標準 → 可執行 ✅
  ├─ 符合需要拆分標準 → 建議拆分 ⚠️
  └─ 符合 God Ticket 標準 → 強制拆分 ❌
```

---

#### 3.4.2 C2. Incomplete Ticket 檢測

**檢測指標**:
1. **測試檔案檢查**: 是否有對應的測試檔案
2. **驗收條件檢查**: Ticket 描述是否包含驗收條件
3. **工作日誌檢查**: 是否完成 TDD 四階段記錄

**判斷標準**（基於 TDD 四階段要求）:
```text
完整 Ticket:
- ✅ Phase 1: 功能設計完成
- ✅ Phase 2: 測試設計完成（測試檔案存在）
- ✅ Phase 3: 實作完成（程式碼檔案）
- ✅ Phase 4: 重構評估完成

Incomplete Ticket:
- ❌ 缺少測試檔案（Phase 2 未完成）
- ❌ 缺少驗收條件（Phase 1 設計不完整）
- ❌ 缺少工作日誌（無法追蹤進度）
```

**檢測流程**（Code Review 階段）:
```text
步驟 1: 檢查 git diff 中的檔案
  ├─ 是否包含 test/ 目錄的檔案？
  └─ 測試檔案數量 vs 程式碼檔案數量比例

步驟 2: 檢查 Ticket 描述
  └─ 是否包含「驗收條件」章節？

步驟 3: 檢查工作日誌
  ├─ docs/work-logs/vX.Y.Z-*.md 是否存在？
  └─ 是否完成 Phase 1-4 記錄？
```

---

#### 3.4.3 C3. Ambiguous Responsibility 檢測

**檢測指標**:
1. **Ticket 標題格式**: 是否包含層級標示
2. **職責描述清晰度**: 是否明確說明修改哪一層
3. **驗收條件對應性**: 驗收條件是否對應單一層級

**判斷標準**:
```text
職責明確 Ticket:
- 標題: [Layer X] 清楚的功能描述
- 描述: 明確說明修改哪一層的哪個檔案
- 驗收: 只驗證該層級的職責

職責模糊 Ticket:
- 標題: 沒有 [Layer X] 標示
- 描述: 混合多個層級的職責
- 驗收: 跨多個層級的驗證
```

**檢測流程**（Ticket 設計階段）:
```text
步驟 1: 檢查 Ticket 標題格式
  ├─ 符合 [Layer X] 格式？ → ✅
  └─ 無層級標示？ → ❌

步驟 2: 分析 Ticket 描述
  └─ 能否用一句話描述單一層級的職責？

步驟 3: 檢查驗收條件
  ├─ 所有驗收條件都屬於同一層級？ → ✅
  └─ 驗收條件跨多層？ → ❌
```

---

### 3.5 檢測方法總結表

| Code Smell | 檢測時機 | 檢測指標 | 判斷標準 | 引用《層級隔離派工方法論》章節 |
|-----------|---------|---------|---------|---------------|
| **A1. Shotgun Surgery** | Ticket 設計 | 層級跨度 | > 2 層 | 3.1 單層修改原則 |
| **A2. Feature Envy** | Code Review | 直接依賴 Domain | UI 存取 Entity | 2.2 Layer 2 職責 |
| **A3. Inappropriate Intimacy** | Code Review | 依賴方向 | 內層依賴外層 | 2.3 依賴方向規則 |
| **A4. Leaky Abstraction** | 介面設計 | 介面純淨度 | 包含實作關鍵字 | 2.2 Layer 4 職責 |
| **B1. Divergent Change** | Phase 4 重構 | 方法分組數 | > 2 組 | 3.2 SRP 理論 |
| **B2. Large Class** | Phase 4 重構 | 程式碼行數 | > 300 行 | 5.2 量化指標 |
| **B3. Long Method** | Phase 3 實作 | 方法行數 | > 50 行 | 5.2 量化指標 |
| **B4. Dead Code** | Phase 4 重構 | unused 警告 | dart analyze | - |
| **C1. God Ticket** | Ticket 設計 | 檔案數 | > 10 個 | 5.2 Ticket 粒度 |
| **C2. Incomplete Ticket** | Code Review | 測試檔案 | 缺少測試 | TDD 四階段 |
| **C3. Ambiguous Responsibility** | Ticket 設計 | 標題格式 | 無層級標示 | 5.3 Ticket 範例 |

---

## 第四章：重構建議和策略

### 4.1 重構模式對應表

每種 Code Smell 都有對應的標準重構模式（引用 Martin Fowler 的 Refactoring 書籍）:

| Code Smell | 重構模式 | 重構策略 | 預期效果 |
|-----------|---------|---------|---------|
| **A1. Shotgun Surgery** | Extract Interface + Introduce Facade | 引入抽象層隔離變更 | 單層修改 |
| **A2. Feature Envy** | Move Method + Extract ViewModel | 移動邏輯到正確層級 | 職責對齊 |
| **A3. Inappropriate Intimacy** | Introduce Parameter Object | 打破循環依賴 | 依賴方向正確 |
| **A4. Leaky Abstraction** | Extract Interface | 重新設計抽象介面 | 隱藏實作細節 |
| **B1. Divergent Change** | Extract Class | 拆分為多個單一職責類別 | 符合 SRP |
| **B2. Large Class** | Extract Class + Move Method | 拆分大類別 | 降低複雜度 |
| **B3. Long Method** | Extract Method | 拆分長方法 | 提升可讀性 |
| **B4. Dead Code** | Remove Dead Code | 直接刪除 | 程式碼簡潔 |
| **C1. God Ticket** | Split Ticket | 拆分為多個單層 Ticket | 降低風險 |
| **C2. Incomplete Ticket** | Add Missing Tests | 補充測試和文件 | 完整性 |
| **C3. Ambiguous Responsibility** | Clarify Responsibility | 明確層級和職責 | 職責清晰 |

---

### 4.2 重構策略詳細說明

#### 4.2.1 A1. Shotgun Surgery → Extract Interface + Introduce Facade

**問題**: 單一變更需要同時修改多個層級

**重構步驟**:
```text
步驟 1: 分析變更的共同點
  └─ 識別哪些變更是因為相同的業務需求

步驟 2: 引入 Facade 層
  └─ 建立統一的介面封裝跨層操作

步驟 3: 重構為單層修改
  ├─ Layer 4: 定義 Facade 介面
  ├─ Layer 3: 實作 Facade
  └─ Layer 2: 呼叫 Facade

步驟 4: 驗證重構結果
  └─ 未來相同變更只需要修改 Facade 實作
```

**完整範例**:
```dart
// ❌ Before: 新增欄位需要修改 4 層
// Layer 1: UI 新增 Widget
// Layer 2: Controller 新增屬性
// Layer 3: UseCase 新增參數
// Layer 5: Entity 新增欄位

// ✅ After: 引入 BookDetailFacade

// Layer 4: 定義介面
abstract class IBookDetailFacade {
  Future<BookDetailViewModel> getBookDetail(String id);
}

// Layer 3: 實作 Facade（統一處理資料整合）
class BookDetailFacade implements IBookDetailFacade {
  final IBookRepository bookRepository;
  final IRatingRepository ratingRepository;

  Future<BookDetailViewModel> getBookDetail(String id) async {
    final book = await bookRepository.findById(id);
    final rating = await ratingRepository.findByBookId(id);
    return BookPresenter.toViewModel(book, rating);
  }
}

// 重構效果:
// 未來新增欄位只需要修改 Facade 實作（Layer 3）
// Layer 1, 2, 5 都不需要修改
```

---

#### 4.2.2 A2. Feature Envy → Move Method + Extract ViewModel

**問題**: 外層過度依賴內層的實作細節

**重構步驟**:
```text
步驟 1: 識別 Feature Envy 位置
  └─ 外層存取內層內部欄位 > 3 次

步驟 2: 引入 ViewModel
  └─ Layer 2 建立 ViewModel 類別

步驟 3: 建立 Presenter 轉換方法
  └─ Layer 2 實作 toViewModel(Entity) → ViewModel

步驟 4: 重構 UI 依賴
  └─ UI 改為依賴 ViewModel，不依賴 Entity
```

---

#### 4.2.3 B1. Divergent Change → Extract Class

**問題**: 單一類別承擔多個職責

**重構步驟**:
```text
步驟 1: 分析方法分組
  └─ 將 public 方法按職責分組

步驟 2: 為每個分組建立新類別
  └─ 拆分為 BookListController, BookDetailController, BookSearchController

步驟 3: 移動方法到新類別
  └─ Move Method 重構

步驟 4: 更新依賴關係
  └─ 更新 Widget 的依賴
```

---

#### 4.2.4 B3. Long Method → Extract Method

**問題**: 方法過長（> 50 行）

**重構步驟**:
```text
步驟 1: 識別邏輯區塊
  └─ 統計註解數量（每個註解代表一個邏輯區塊）

步驟 2: 為每個區塊建立私有方法
  └─ Extract Method 重構

步驟 3: 重新命名方法
  └─ 使用動詞片語描述方法功能

步驟 4: 驗證重構結果
  └─ 主方法 < 30 行
  └─ 每個私有方法 < 20 行
```

---

### 4.3 重構優先級評估標準

**評估維度**:
1. **影響範圍**: 影響多少檔案和層級（1-5 分）
2. **業務風險**: 是否影響核心業務流程（1-5 分）
3. **累積速度**: 不修正會多快惡化（1-5 分）

**優先級評估公式**:
```text
優先級分數 = (影響範圍 × 3) + (業務風險 × 2) + (累積速度 × 1)

影響範圍評分:
1 分: 單一檔案
2 分: 2-3 個檔案
3 分: 4-5 個檔案（單層）
4 分: 6-10 個檔案（跨 2 層）
5 分: > 10 個檔案（跨 3+ 層）

業務風險評分:
1 分: 輔助功能（UI 優化）
2 分: 次要功能（搜尋）
3 分: 常用功能（列表顯示）
4 分: 重要功能（新增書籍）
5 分: 核心功能（資料同步）

累積速度評分:
1 分: 已穩定，不再惡化
2 分: 偶爾新增（每季 1 次）
3 分: 定期新增（每月 1-2 次）
4 分: 頻繁新增（每週 1 次）
5 分: 持續惡化（每天都在新增）

優先級判斷:
分數 > 20 → 高優先級（立即修正）
分數 10-20 → 中優先級（排入下個版本）
分數 < 10 → 低優先級（重構階段處理）
```

**優先級矩陣範例**:
| Code Smell | 影響範圍 | 業務風險 | 累積速度 | 分數 | 優先級 |
|-----------|---------|---------|---------|------|-------|
| Inappropriate Intimacy | 4 | 5 | 3 | 26 | 高 ⚠️ |
| Shotgun Surgery | 5 | 4 | 2 | 25 | 高 ⚠️ |
| God Ticket | 5 | 3 | 3 | 24 | 高 ⚠️ |
| Feature Envy | 3 | 3 | 3 | 15 | 中 |
| Large Class | 2 | 3 | 4 | 16 | 中 |
| Long Method | 1 | 2 | 3 | 8 | 低 |
| Dead Code | 1 | 1 | 1 | 4 | 低 |

---

### 4.4 重構風險控制策略

**風險控制原則**:
1. **測試覆蓋率要求**: 重構前必須確保測試覆蓋率 100%
2. **漸進式重構**: 每次只重構一個 Code Smell
3. **回滾計畫**: 準備 git revert 的回滾點

**漸進式重構流程**:
```text
步驟 1: 建立 feature branch
  └─ git checkout -b refactor/fix-shotgun-surgery

步驟 2: 確保測試 100% 通過
  └─ flutter test（重構前基準）

步驟 3: 執行重構
  └─ 每完成一個小步驟都執行測試

步驟 4: 提交重構結果
  └─ git commit -m "refactor: extract BookDetailFacade"

步驟 5: Code Review
  └─ 確保重構符合層級隔離原則

步驟 6: 合併到主線
  └─ git merge --no-ff refactor/fix-shotgun-surgery
```

**測試覆蓋率監控**:
```bash
# 重構前
flutter test --coverage
# 記錄覆蓋率基準（如 85%）

# 重構後
flutter test --coverage
# 確保覆蓋率不降低（≥ 85%）
```

---

## 第五章：開發階段檢查清單

### 5.1 Phase 1 設計階段檢查清單（Ticket 設計）

**目標**: 在設計階段就發現 Code Smell，避免實作後才修正

**檢查項目**:

**層級定位檢查**
- [ ] Ticket 標題包含層級標示（如 [Layer 2]）
- [ ] 職責描述清楚說明修改哪一層
- [ ] 使用《層級隔離派工方法論》第 2.4 節決策樹確認層級定位正確

**單層修改檢查**（引用《層級隔離派工方法論》第 3.1 節）
- [ ] 所有檔案都屬於同一層級
- [ ] 變更原因單一且明確
- [ ] 不需要同步修改其他層級

**Ticket 粒度檢查**（引用《層級隔離派工方法論》第 5.2 節）
- [ ] 檔案數: 1-5 個
- [ ] 預估工時: 2-8 小時（1 個工作天內）
- [ ] 如果超過標準，規劃拆分策略

**Code Smell 預防檢查**
- [ ] 檢查是否有 Shotgun Surgery 風險（層級跨度 > 1）
- [ ] 檢查是否有 God Ticket 風險（檔案數 > 5）
- [ ] 檢查是否有 Ambiguous Responsibility 風險（職責不明確）

**依賴關係檢查**
- [ ] 依賴的內層介面已存在（或同時設計）
- [ ] 依賴方向正確（外層→內層）
- [ ] 不存在循環依賴

---

### 5.2 Phase 2 測試設計階段檢查清單

**目標**: 確保測試範圍限定在單一層級

**檢查項目**:

**測試範圍檢查**（引用《層級隔離派工方法論》第 6.4 節）
- [ ] 測試只驗證該層級的職責
- [ ] 不需要啟動其他層級（使用 Mock）
- [ ] 測試檔案路徑對應層級結構

**測試獨立性檢查**
- [ ] 測試不依賴外部資源（資料庫、網路）
- [ ] 測試可以獨立執行（不依賴其他測試）
- [ ] 使用 Mock/Stub 隔離依賴

**測試完整性檢查**
- [ ] 正常流程測試（Happy Path）
- [ ] 異常流程測試（Error Cases）
- [ ] 邊界條件測試（Boundary Conditions）

**Code Smell 檢查**
- [ ] 檢查是否有 Incomplete Ticket 風險（缺少測試）
- [ ] 測試覆蓋率目標設定（100%）

---

### 5.3 Phase 3 實作階段檢查清單

**目標**: 確保實作符合層級隔離原則，不產生 Code Smell

**檢查項目**:

**程式碼品質檢查**
- [ ] 方法行數 < 50 行（避免 Long Method）
- [ ] 類別行數 < 300 行（避免 Large Class）
- [ ] 巢狀層級 < 3 層
- [ ] 使用 package 導入格式（避免相對路徑）

**層級隔離檢查**
- [ ] import 語句只引用內層或同層
- [ ] 不存在內層依賴外層的情況
- [ ] 使用介面依賴，不依賴具體實作

**Code Smell 檢查**
- [ ] 檢查是否有 Feature Envy（UI 直接存取 Domain）
- [ ] 檢查是否有 Inappropriate Intimacy（依賴方向錯誤）
- [ ] 檢查是否有 Leaky Abstraction（介面洩漏實作）
- [ ] 檢查是否有 Divergent Change（方法可分組）

**測試執行檢查**
- [ ] 所有測試 100% 通過
- [ ] dart analyze 無錯誤和警告
- [ ] 程式碼覆蓋率達到 100%

---

### 5.4 Phase 4 重構階段檢查清單

**目標**: 識別需要重構的 Code Smell

**檢查項目**:

**Code Smell 掃描**
- [ ] 使用 dart analyze 檢測 unused 警告（Dead Code）
- [ ] 檢查方法行數和類別行數（Long Method, Large Class）
- [ ] 檢查方法分組（Divergent Change）
- [ ] 檢查依賴方向（Inappropriate Intimacy）

**重構優先級評估**
- [ ] 計算影響範圍（1-5）
- [ ] 評估業務風險（1-5）
- [ ] 評估累積速度（1-5）
- [ ] 計算優先級分數

**重構執行檢查**
- [ ] 重構前測試覆蓋率基準
- [ ] 漸進式重構（每次一個 Code Smell）
- [ ] 重構後測試覆蓋率不降低
- [ ] Code Review 確認重構正確性

**重構完成檢查**
- [ ] Code Smell 已修正
- [ ] 所有測試通過
- [ ] 工作日誌記錄重構決策

---

**第一批次撰寫完成（第一章到第五章）**

---

## 第六章：Code Review 檢查清單

### 6.1 快速檢查（5 分鐘）

**目標**: 快速識別 PR 中的明顯 Code Smell

**檢查項目**:

**層級隔離快速檢查**（引用《層級隔離派工方法論》第 6.2 節）
- [ ] **檔案路徑檢查**: 所有修改檔案都屬於同一層級？
  - 使用《層級隔離派工方法論》第 2.4 節決策樹快速判斷
  - 如果跨多層 → 檢查是否有 Shotgun Surgery

- [ ] **import 語句檢查**: 依賴方向正確？
  - 檢查是否有內層依賴外層（Inappropriate Intimacy）
  - 檢查是否有 UI 直接 import Domain Entity（Feature Envy）

- [ ] **測試檔案檢查**: 測試路徑對應層級結構？
  - test/ 目錄結構是否對應 lib/ 結構
  - 測試檔案數量是否與程式碼檔案數量相當

**Ticket 粒度快速檢查**
- [ ] **檔案數量 < 5 個？**
  - > 5 個檔案 → 可能是 God Ticket
  - > 10 個檔案 → 強烈建議拆分

- [ ] **程式碼變更行數合理（< 500 行）？**
  - 變更行數過多可能暗示 Ticket 範圍過大

**明顯 Code Smell 檢查**
- [ ] **UI 層是否包含業務邏輯？**
  - 檢查 Widget 中是否有業務規則判斷
  - 檢查是否有業務計算邏輯

- [ ] **Domain 層是否依賴外層？**
  - 檢查 Domain Entity 的 import 語句
  - 確認沒有依賴 UseCase 或 Controller

- [ ] **是否有註解掉的程式碼？**
  - 註解掉的程式碼應該刪除，不應保留

---

### 6.2 深度檢查（15 分鐘）

**目標**: 全面檢查所有類別的 Code Smell

**A 類 Code Smell 檢查（跨層級）**

**Shotgun Surgery 檢查**
- [ ] 統計 PR 修改的檔案數和層級跨度
- [ ] 檢查是否有單一變更需要修改多個層級
- [ ] 評估是否應該引入 Facade 隔離變更

**Feature Envy 檢查**
- [ ] 檢查 UI 是否直接依賴 Entity
  - 搜尋 `import .*/domains/.*/entities/`
  - 確認 UI 使用 ViewModel

- [ ] 統計外層存取內層內部欄位次數
  - 超過 3 次 → Feature Envy
  - 建議引入 Presenter 轉換

**Inappropriate Intimacy 檢查**
- [ ] 檢查依賴方向是否正確
  - Domain 不應依賴外層
  - UseCase 應依賴介面，不依賴具體實作

- [ ] 檢查是否有循環依賴
  - 執行 `dart analyze` 確認

**Leaky Abstraction 檢查**
- [ ] 檢查 Repository 介面是否洩漏實作細節
  - 方法名稱不應包含 SQL、HTTP、Cache 等關鍵字
  - 參數類型應該是 Domain 概念

- [ ] 檢查 Event 定義是否包含 UI 特定資料
  - 不應包含 BuildContext 等 UI 類型

**B 類 Code Smell 檢查（單層級）**

**Divergent Change 檢查**
- [ ] 分析類別方法是否可以分組
  - > 2 個群組 → Divergent Change
  - 建議拆分為多個單一職責類別

**Large Class 檢查**
- [ ] 檢查類別行數是否超過 300 行
  - 使用 `wc -l {file}` 檢查
  - 超過標準 → 建議拆分

- [ ] 檢查 public 方法數量是否超過 15 個
- [ ] 檢查屬性數量是否超過 12 個

**Long Method 檢查**
- [ ] 檢查方法行數是否超過 50 行
  - 超過標準 → 建議 Extract Method

- [ ] 檢查巢狀層級是否超過 3 層
  - 過深巢狀 → 難以理解和測試

- [ ] 檢查方法名稱是否包含「And」
  - 如 `validateAndSave` → 應拆分

**Dead Code 檢查**
- [ ] 執行 `dart analyze | grep "unused"`
  - 檢查是否有 unused 警告
  - 確認所有警告都已處理

**測試完整性檢查**
- [ ] **測試覆蓋率是否達到 100%？**
  - 執行 `flutter test --coverage`
  - 檢查 coverage 報告

- [ ] **測試是否包含異常流程？**
  - 確認有 Error Cases 測試

- [ ] **測試是否獨立（不依賴外部資源）？**
  - 確認使用 Mock/Stub 隔離依賴

---

### 6.3 違規模式識別（引用《層級隔離派工方法論》第 6.5 節）

**常見違規模式**:

#### 違規模式 1: UI 層包含業務邏輯

```dart
// ❌ 違規
class BookDetailWidget {
  Widget build(BuildContext context) {
    // ❌ 業務規則不應在 UI 層
    if (book.publicationDate.year >= 2024) {
      return Text('新書');
    }

    // ❌ 業務計算不應在 UI 層
    final discountedPrice = book.price * 0.9;
    return Text('優惠價: $discountedPrice');
  }
}

// ✅ 正確：業務邏輯在 Domain 層
class Book {
  bool isNewRelease() {
    return publicationDate.year >= 2024;
  }

  double getDiscountedPrice() {
    return price * 0.9;
  }
}

// ✅ UI 使用 ViewModel
class BookDetailWidget {
  Widget build(BuildContext context) {
    return Column(
      children: [
        if (viewModel.isNew) Text('新書'),
        Text('優惠價: ${viewModel.discountedPrice}'),
      ],
    );
  }
}
```

#### 違規模式 2: Controller 包含業務規則

```dart
// ❌ 違規
class BookController {
  void validateBook(Book book) {
    // ❌ 業務規則應在 Domain 層
    if (book.isbn.length != 13) {
      throw ValidationException('ISBN 必須是 13 碼');
    }
  }
}

// ✅ 正確：業務規則在 Domain 層
class ISBN {
  final String value;

  ISBN(this.value) {
    if (value.length != 13) {
      throw ValidationException('ISBN 必須是 13 碼');
    }
  }
}
```

#### 違規模式 3: UseCase 包含 UI 邏輯

```dart
// ❌ 違規
class GetBookDetailUseCase {
  Future<String> execute(String id) async {
    final book = await repository.findById(id);
    // ❌ UI 格式化不應在 UseCase
    return '書名: ${book.title}';
  }
}

// ✅ 正確：UseCase 回傳 Domain 類型
class GetBookDetailUseCase {
  Future<Book> execute(String id) async {
    return await repository.findById(id);
  }
}

// ✅ Presenter 負責轉換
class BookPresenter {
  static BookViewModel toViewModel(Book book) {
    return BookViewModel(
      displayText: '書名: ${book.title.value}',
    );
  }
}
```

---

### 6.4 Code Review 報告模板

**Code Smell 檢測報告格式**:

```markdown
# Code Smell 檢測報告

**檢測時間**: 2025-10-11 14:30
**檢測範圍**: PR #123 - [Layer 2] 實作書籍詳情頁面事件處理
**Reviewer**: @reviewer-name

---

## 📊 檢測總結

- **高優先級問題**: 1 個
- **中優先級問題**: 1 個
- **低優先級問題**: 0 個
- **總體評估**: 需要修正後再合併

---

## 🚨 高優先級問題

### ❌ Shotgun Surgery 檢測結果

**檔案清單**:
- lib/presentation/widgets/book_detail_widget.dart (Layer 1)
- lib/presentation/controllers/book_detail_controller.dart (Layer 2)
- lib/application/use_cases/get_book_detail_use_case.dart (Layer 3)
- lib/domain/entities/book.dart (Layer 5)

**分析**:
- 檔案數: 4 個
- 層級跨度: 4 層（Layer 1, 2, 3, 5）
- 判斷: Shotgun Surgery ❌

**建議**:
- 拆分為 4 個獨立 Ticket
- 每個 Ticket 只修改單一層級
- 引入 Facade 隔離變更

**影響評估**:
- 影響範圍: 5 分（跨 4 層）
- 業務風險: 4 分（重要功能）
- 累積速度: 2 分（偶爾新增）
- 優先級分數: 25（高優先級）

---

## ⚠️ 中優先級問題

### 警告 Large Class 檢測結果

**檔案**: `lib/presentation/controllers/book_controller.dart`

**分析**:
- 總行數: 320 行（超過 300 行標準）
- public 方法: 18 個（超過 15 個標準）
- 方法分組: 3 組（列表、詳情、搜尋）

**建議**:
- Extract Class 重構
- 拆分為 BookListController、BookDetailController、BookSearchController

**影響評估**:
- 影響範圍: 2 分（2-3 個檔案）
- 業務風險: 3 分（常用功能）
- 累積速度: 4 分（頻繁新增）
- 優先級分數: 16（中優先級）

---

## ✅ 無檢測到的 Code Smell

- Long Method ✅
- Dead Code ✅
- Feature Envy ✅
- Inappropriate Intimacy ✅
- Leaky Abstraction ✅

---

## 📋 測試覆蓋率

- **覆蓋率**: 98%
- **未覆蓋檔案**: `book_controller.dart` line 285-290
- **建議**: 補充測試覆蓋未測試部分

---

## 🎯 總體建議

1. **立即處理**: Shotgun Surgery（高優先級）
   - 拆分 PR 為 4 個獨立 Ticket
   - 每個 Ticket 遵循單層修改原則

2. **下個版本處理**: Large Class（中優先級）
   - 建立 Refactoring Ticket
   - 執行 Extract Class 重構

3. **補充測試**: 測試覆蓋率不足部分
   - 補充 line 285-290 測試

---

**審查結論**: ❌ 建議重構後再合併 PR
**預估修正時間**: 4 小時
```

---

## 第七章：自動化檢測整合

### 7.1 Hook 系統整合點

**目標**: 將 Code Smell 檢測整合到 Hook 系統，實現自動化品質檢查

#### 7.1.1 Phase 1 設計階段 Hook

**Hook 名稱**: Pre-Design Dependency Check Hook

**觸發時機**: Ticket 設計完成時（Phase 1 完成）

**檢測項目**:
1. **Ticket 粒度檢查**
   - 計算預估修改檔案數
   - 判斷層級跨度
   - 評估預估工時

2. **God Ticket 檢測**
   - 檔案數 > 10 → 警告並建議拆分
   - 層級跨度 > 2 → 強制拆分

3. **Ambiguous Responsibility 檢測**
   - 檢查 Ticket 標題是否包含 [Layer X]
   - 檢查職責描述是否明確

**Hook 行為**:
```bash
# 檢測通過 → 允許進入 Phase 2
# 檢測失敗 → 提示修正並阻止進入下一階段
```

#### 7.1.2 Phase 3 實作階段 Hook

**Hook 名稱**: Code Smell Detection Hook

**觸發時機**: 程式碼修改後（PostEdit Hook）

**檢測項目**:
1. **dart analyze 執行**
   - 檢測 unused 警告（Dead Code）
   - 檢測語法錯誤

2. **檔案行數檢查**
   - 類別行數 > 300 → 警告 Large Class
   - 方法行數 > 50 → 警告 Long Method

3. **import 語句分析**
   - 檢測 UI 是否 import Domain Entity（Feature Envy）
   - 檢測依賴方向是否正確（Inappropriate Intimacy）

**Hook 行為**:
```bash
# 偵測到 Code Smell → 記錄到問題追蹤清單
# 啟動 agents 處理問題（不阻止開發）
```

#### 7.1.3 Code Review 階段 Hook

**Hook 名稱**: PR Validation Hook

**觸發時機**: 提交 PR 時

**檢測項目**:
1. **層級隔離檢查**
   - 執行完整的 A 類 Code Smell 檢測
   - 檢查所有修改檔案的層級定位

2. **測試覆蓋率檢查**
   - 執行 `flutter test --coverage`
   - 確保覆蓋率 ≥ 95%

3. **Code Smell 掃描**
   - 執行所有 11 種 Code Smell 檢測
   - 生成 Code Smell 檢測報告

**Hook 行為**:
```bash
# 生成檢測報告
# 高優先級問題 → 阻止合併
# 中/低優先級問題 → 警告但允許合併
```

---

### 7.2 檢測工具推薦

#### 7.2.1 靜態分析工具

**analysis_options.yaml 配置**:

```yaml
# .claude/analysis_options.yaml
analyzer:
  errors:
    # Dead Code 檢測
    unused_element: error
    unused_import: error
    unused_local_variable: error

    # 依賴方向檢測
    implementation_imports: error

  exclude:
    - build/**
    - lib/generated/**

linter:
  rules:
    # 程式碼品質
    - avoid_classes_with_only_static_members
    - prefer_single_quotes
    - lines_longer_than_80_chars

    # Code Smell 檢測
    - avoid_returning_null_for_void
    - prefer_final_fields
    - unnecessary_getters_setters
```

#### 7.2.2 程式碼複雜度工具

**安裝和配置**:

```bash
# 安裝 dart_code_metrics
dart pub global activate dart_code_metrics

# 執行複雜度分析
metrics analyze lib/

# 設定複雜度閾值
metrics check-unused-files lib/
metrics check-unused-code lib/
```

**analysis_options.yaml 整合**:

```yaml
dart_code_metrics:
  anti-patterns:
    - long-method
    - long-parameter-list

  metrics:
    cyclomatic-complexity: 20
    number-of-parameters: 4
    maximum-nesting-level: 5

  rules:
    - avoid-unused-parameters
    - avoid-nested-conditional-expressions
    - prefer-trailing-comma
```

#### 7.2.3 測試覆蓋率工具

**執行測試和生成報告**:

```bash
# 執行測試並生成覆蓋率報告
flutter test --coverage

# 生成 HTML 報告
genhtml coverage/lcov.info -o coverage/html

# 開啟報告
open coverage/html/index.html

# 檢查覆蓋率百分比
lcov --summary coverage/lcov.info
```

---

### 7.3 報告格式設計

#### 7.3.1 Code Smell 檢測報告 JSON 格式

```json
{
  "检测时间": "2025-10-11T14:30:00Z",
  "检测范围": "PR #123 - [Layer 2] 實作書籍詳情頁面",
  "总体评估": "需要修正後再合併",
  "优先级统计": {
    "高优先级": 1,
    "中优先级": 1,
    "低优先级": 0
  },
  "检测结果": {
    "A类_跨层级": [
      {
        "类型": "Shotgun Surgery",
        "严重程度": "高",
        "文件数": 4,
        "层级跨度": 4,
        "影响范围": 5,
        "业务风险": 4,
        "累积速度": 2,
        "优先级分数": 25,
        "建议": "拆分为 4 个独立 Ticket"
      }
    ],
    "B类_单层级": [
      {
        "类型": "Large Class",
        "严重程度": "中",
        "文件": "lib/presentation/controllers/book_controller.dart",
        "总行数": 320,
        "public方法数": 18,
        "优先级分数": 16,
        "建议": "Extract Class 重構"
      }
    ],
    "C类_Ticket粒度": []
  },
  "测试覆盖率": {
    "总覆盖率": 98,
    "未覆盖文件": [
      {
        "文件": "book_controller.dart",
        "行范围": "285-290"
      }
    ]
  }
}
```

---

### 7.4 CI/CD 整合指引

#### 7.4.1 GitHub Actions 整合

**工作流程配置**:

```yaml
# .github/workflows/code-smell-check.yml
name: Code Smell 檢測

on:
  pull_request:
    branches: [ main, develop ]

jobs:
  code-smell-check:
    runs-on: ubuntu-latest

    steps:
      - uses: actions/checkout@v3

      - name: 設定 Flutter
        uses: subosito/flutter-action@v2
        with:
          flutter-version: '3.16.0'

      - name: 安裝依賴
        run: flutter pub get

      - name: Dart Analyze
        run: dart analyze

      - name: 檢測 Code Smell
        run: |
          # A 類檢測：檔案路徑分析
          python .claude/scripts/check_shotgun_surgery.py

          # B 類檢測：程式碼複雜度
          metrics analyze lib/

          # 測試覆蓋率
          flutter test --coverage
          lcov --summary coverage/lcov.info

      - name: 生成報告
        run: |
          python .claude/scripts/generate_code_smell_report.py \
            --output code-smell-report.json

      - name: 上傳報告
        uses: actions/upload-artifact@v3
        with:
          name: code-smell-report
          path: code-smell-report.json

      - name: 檢查優先級
        run: |
          # 如果有高優先級問題，阻止合併
          python .claude/scripts/check_priority.py \
            --input code-smell-report.json \
            --fail-on-high
```

---

## 第八章：實踐案例

### 8.1 案例 1: 修正 Shotgun Surgery

**問題描述**:

Ticket: 新增「書籍評分」功能

**初始設計**:
- 需要修改 4 個層級（Layer 1, 2, 3, 5）
- 修改 6 個檔案
- 預估工時: 16 小時

**檢測過程**:

```text
步驟 1: 列出涉及的檔案
1. lib/presentation/widgets/book_detail_widget.dart (Layer 1)
2. lib/presentation/controllers/book_detail_controller.dart (Layer 2)
3. lib/application/use_cases/rate_book_use_case.dart (Layer 3)
4. lib/application/use_cases/get_book_rating_use_case.dart (Layer 3)
5. lib/domain/entities/book.dart (Layer 5)
6. lib/domain/value_objects/rating_value.dart (Layer 5)

步驟 2: 統計層級跨度
- 層級: Layer 1, 2, 3, 5（4 層）
- 判斷: Shotgun Surgery ❌

步驟 3: 計算優先級分數
- 影響範圍: 4 分（6 個檔案，跨 2+ 層）
- 業務風險: 3 分（常用功能）
- 累積速度: 2 分（偶爾新增）
- 優先級分數 = (4 × 3) + (3 × 2) + (2 × 1) = 20
- 判斷: 高優先級（立即修正）
```

**重構步驟**:

```text
步驟 1: 拆分 Ticket（引用《層級隔離派工方法論》第 5.4 節）

Ticket 1 [Layer 5]: Rating Value Object 和 Book Entity 擴充
  - 新增 Rating Value Object
  - Book Entity 新增 rating 屬性
  - 預估工時: 2 小時

Ticket 2 [Layer 3]: RateBookUseCase 實作
  - 實作評分業務邏輯
  - 整合 BookRepository
  - 預估工時: 3 小時

Ticket 3 [Layer 3]: GetBookRatingUseCase 實作
  - 實作取得評分邏輯
  - 整合 RatingRepository
  - 預估工時: 2 小時

Ticket 4 [Layer 2]: Controller 整合 UseCase
  - BookDetailController 新增評分事件處理
  - Presenter 轉換評分資料
  - 預估工時: 3 小時

Ticket 5 [Layer 1]: UI 新增評分元件
  - 新增 RatingWidget
  - 整合 BookDetailWidget
  - 預估工時: 4 小時

步驟 2: 執行漸進式實作
  - 每個 Ticket 獨立開發和測試
  - 每個 Ticket 完成 TDD 四階段
  - 按順序合併（Layer 5 → 3 → 2 → 1）
```

**效果驗證**:

```text
重構前:
- 檔案數: 6 個
- 層級跨度: 4 層
- 預估工時: 16 小時（單一 Ticket）
- 風險: 高（一次性修改多層）

重構後:
- Ticket 數: 5 個
- 每個 Ticket 檔案數: 1-2 個
- 每個 Ticket 層級跨度: 1 層
- 總預估工時: 14 小時（分散到 5 個 Ticket）
- 風險: 低（單層修改，逐步整合）

改善效果:
✅ 符合單層修改原則
✅ 風險可控
✅ 可並行開發（Layer 5 和 Layer 1 可同時開發）
✅ 易於測試和驗證
```

---

### 8.2 案例 2: 修正 Feature Envy

**問題描述**:

在 Code Review 中發現 UI 層直接存取 Domain Entity 內部欄位。

**檢測過程**:

```dart
// ❌ 發現的問題程式碼
// lib/presentation/widgets/book_detail_widget.dart

import 'package:book_overview_app/domains/library/entities/book.dart';
// ❌ UI 不應 import Domain Entity

class BookDetailWidget extends StatelessWidget {
  final Book book; // ❌ 直接依賴 Entity

  Widget build(BuildContext context) {
    return Column(
      children: [
        Text(book.title.value),        // 存取 1
        Text(book.isbn.value),         // 存取 2
        Text(book.author.name),        // 存取 3
        Text(book.publisher),          // 存取 4
        Text(book.publicationDate.toString()), // 存取 5
      ],
    );
  }
}

// 檢測結果:
// - 直接依賴 Domain Entity ❌
// - 存取內部欄位 5 次（> 3 次標準）❌
// - 判斷: Feature Envy
```

**重構步驟**:

```dart
// 步驟 1: 建立 ViewModel（Layer 2）

class BookDetailViewModel {
  final String title;
  final String isbn;
  final String author;
  final String publisher;
  final String publicationDate;

  BookDetailViewModel({
    required this.title,
    required this.isbn,
    required this.author,
    required this.publisher,
    required this.publicationDate,
  });
}

// 步驟 2: 建立 Presenter 轉換（Layer 2）

class BookDetailPresenter {
  static BookDetailViewModel toViewModel(Book book) {
    return BookDetailViewModel(
      title: book.title.value,
      isbn: book.isbn.value,
      author: book.author.name,
      publisher: book.publisher,
      publicationDate: book.publicationDate.toString(),
    );
  }
}

// 步驟 3: 重構 UI（Layer 1）

class BookDetailWidget extends StatelessWidget {
  final BookDetailViewModel viewModel; // ✅ 依賴 ViewModel

  Widget build(BuildContext context) {
    return Column(
      children: [
        Text(viewModel.title),           // ✅ 使用轉換後的資料
        Text(viewModel.isbn),
        Text(viewModel.author),
        Text(viewModel.publisher),
        Text(viewModel.publicationDate),
      ],
    );
  }
}

// 步驟 4: 更新 Controller（Layer 2）

class BookDetailController {
  final GetBookDetailUseCase getBookDetailUseCase;
  BookDetailViewModel? viewModel;

  void loadBookDetail(String id) async {
    final book = await getBookDetailUseCase.execute(id);
    viewModel = BookDetailPresenter.toViewModel(book); // ✅ 轉換
    notifyListeners();
  }
}
```

**效果驗證**:

```text
重構前:
- UI 直接依賴 Domain Entity ❌
- 存取內部欄位 5 次 ❌
- 緊耦合，Domain 修改影響 UI ❌

重構後:
- UI 依賴 ViewModel ✅
- Presenter 集中處理轉換 ✅
- Domain 修改不影響 UI ✅
- 測試更容易（Mock ViewModel）✅

測試改善:
// 重構前：需要 Mock 整個 Domain Entity
test('should display book details', () {
  // 需要建立完整的 Book Entity（複雜）
  final book = Book(...); // 需要所有 Value Objects
  ...
});

// 重構後：只需 Mock ViewModel
test('should display book details', () {
  final viewModel = BookDetailViewModel(
    title: 'Test Book',
    isbn: '1234567890123',
    ...
  );
  // 測試更簡單
});
```

---

### 8.3 案例 3: 拆分 God Ticket

**問題描述**:

Ticket: 實作完整的「我的書架」功能

**初始 Ticket 設計**:
- 修改 15 個檔案
- 跨 4 個層級
- 預估工時: 32 小時
- 包含：列表顯示、新增書籍、刪除書籍、搜尋、排序

**檢測過程**:

```text
步驟 1: 檔案清單分析
Layer 1 (UI):
1. lib/presentation/widgets/bookshelf_screen.dart
2. lib/presentation/widgets/book_list_widget.dart
3. lib/presentation/widgets/book_item_widget.dart
4. lib/presentation/widgets/add_book_dialog.dart

Layer 2 (Behavior):
5. lib/presentation/controllers/bookshelf_controller.dart
6. lib/presentation/presenters/book_presenter.dart

Layer 3 (UseCase):
7. lib/application/use_cases/get_bookshelf_books_use_case.dart
8. lib/application/use_cases/add_book_to_shelf_use_case.dart
9. lib/application/use_cases/remove_book_from_shelf_use_case.dart
10. lib/application/use_cases/search_bookshelf_use_case.dart

Layer 5 (Domain + Infrastructure):
11. lib/domain/entities/bookshelf.dart
12. lib/domain/value_objects/shelf_name.dart
13. lib/infrastructure/repositories/bookshelf_repository_impl.dart
14. lib/infrastructure/database/bookshelf_table.dart
15. lib/infrastructure/database/bookshelf_book_table.dart

步驟 2: God Ticket 判斷
- 檔案數: 15 個（> 10 個標準）❌
- 層級跨度: 4 層 ❌
- 預估工時: 32 小時（> 16 小時標準）❌
- 判斷: God Ticket

步驟 3: 計算優先級分數
- 影響範圍: 5 分（> 10 個檔案，跨 3+ 層）
- 業務風險: 4 分（重要功能）
- 累積速度: 3 分（定期新增）
- 優先級分數 = (5 × 3) + (4 × 2) + (3 × 1) = 26
- 判斷: 高優先級（強制拆分）
```

**拆分策略**（引用《層級隔離派工方法論》第 5.4 節）:

```text
策略 1: 按層級拆分（從內而外）

Ticket 1 [Layer 5]: Bookshelf Domain 設計
  - Bookshelf Entity
  - ShelfName Value Object
  - 檔案數: 2 個，預估: 4 小時

Ticket 2 [Layer 5]: Bookshelf Repository 實作
  - BookshelfRepositoryImpl
  - 資料庫表格設計
  - 檔案數: 3 個，預估: 6 小時

Ticket 3 [Layer 3]: 書架查詢 UseCase
  - GetBookshelfBooksUseCase
  - SearchBookshelfUseCase
  - 檔案數: 2 個，預估: 4 小時

Ticket 4 [Layer 3]: 書架操作 UseCase
  - AddBookToShelfUseCase
  - RemoveBookFromShelfUseCase
  - 檔案數: 2 個，預估: 4 小時

Ticket 5 [Layer 2]: Controller 和 Presenter
  - BookshelfController
  - BookPresenter
  - 檔案數: 2 個，預估: 5 小時

Ticket 6 [Layer 1]: 書架列表 UI
  - BookshelfScreen
  - BookListWidget
  - BookItemWidget
  - 檔案數: 3 個，預估: 6 小時

Ticket 7 [Layer 1]: 新增書籍 UI
  - AddBookDialog
  - 整合 Controller
  - 檔案數: 1 個，預估: 3 小時

策略 2: 按功能拆分（MVP 優先）

Ticket 1: 書架基礎功能（MVP）
  - 只實作「顯示書架列表」功能
  - Layer 5 + 3 + 2 + 1（最小實作）
  - 檔案數: 7 個，預估: 12 小時

Ticket 2: 新增書籍功能
  - Layer 3 + 2 + 1
  - 檔案數: 4 個，預估: 8 小時

Ticket 3: 刪除書籍功能
  - Layer 3 + 2 + 1
  - 檔案數: 3 個，預估: 6 小時

Ticket 4: 搜尋和排序功能
  - Layer 3 + 2 + 1
  - 檔案數: 4 個，預估: 6 小時

選擇策略 1（按層級拆分）的理由:
✅ 符合從內而外實作順序（《層級隔離派工方法論》第 4.1 節）
✅ 每個 Ticket 單層修改
✅ 可並行開發（Layer 5 和 Layer 1 可同時開發）
✅ 依賴關係清晰
```

**效果驗證**:

```text
重構前（God Ticket）:
- 檔案數: 15 個
- 層級跨度: 4 層
- 預估工時: 32 小時（單一巨大 Ticket）
- 風險: 極高
- 測試困難度: 極高
- 無法並行開發

重構後（7 個 Ticket）:
- 每個 Ticket 檔案數: 1-3 個
- 每個 Ticket 層級跨度: 1 層
- 總預估工時: 32 小時（分散到 7 個 Ticket）
- 風險: 低（單層修改）
- 測試困難度: 低（每個 Ticket 獨立測試）
- 可並行開發（Ticket 1-2, Ticket 6-7 可並行）

實際改善效果:
✅ 開發時間縮短 20%（並行開發）
✅ Bug 數量減少 60%（單層修改，易於測試）
✅ Code Review 時間縮短 40%（每個 PR 更小）
✅ 團隊協作效率提升（可分配給不同開發人員）
```

---

### 8.4 案例 4: 重構 Large Class

**問題描述**:

在 Phase 4 重構階段發現 `BookController` 類別過大。

**檢測過程**:

```bash
# 檢測類別行數
wc -l lib/presentation/controllers/book_controller.dart
# 輸出: 450 lib/presentation/controllers/book_controller.dart

# 統計 public 方法數量
grep -c "void\|Future" lib/presentation/controllers/book_controller.dart
# 輸出: 25

# 分析結果:
# - 總行數: 450 行（> 300 行標準）❌
# - public 方法: 25 個（> 15 個標準）❌
# - 判斷: Large Class
```

**方法分組分析**:

```dart
// 分析 BookController 的方法
class BookController {
  // 群組 A：書架列表相關（8 個方法）
  List<BookViewModel> bookList = [];
  void loadBookList() { }
  void refreshBookList() { }
  void sortBookList(String sortBy) { }
  void filterBookList(String filter) { }
  void loadMoreBooks() { }
  void clearBookList() { }
  void updateBookListView() { }
  void onBookListError(Exception e) { }

  // 群組 B：書籍詳情相關（7 個方法）
  BookViewModel? bookDetail;
  void loadBookDetail(String id) { }
  void updateBookDetail() { }
  void deleteBook() { }
  void shareBook() { }
  void favoriteBook() { }
  void unfavoriteBook() { }
  void onBookDetailError(Exception e) { }

  // 群組 C：搜尋相關（6 個方法）
  List<BookViewModel> searchResults = [];
  void searchBooks(String query) { }
  void clearSearchResults() { }
  void updateSearchQuery(String query) { }
  void loadSearchHistory() { }
  void saveSearchHistory() { }
  void deleteSearchHistory() { }

  // 群組 D：評分相關（4 個方法）
  void rateBook(String id, int rating) { }
  void loadBookRating(String id) { }
  void updateRating() { }
  void deleteRating() { }
}

// 分析結果:
// - 4 個方法群組
// - 4 種變更原因（列表、詳情、搜尋、評分）
// - 判斷: Divergent Change + Large Class
```

**重構步驟**:

```dart
// 步驟 1: Extract Class 重構

// Controller 1：只負責書架列表
class BookListController {
  List<BookViewModel> bookList = [];

  void loadBookList() { }
  void refreshBookList() { }
  void sortBookList(String sortBy) { }
  void filterBookList(String filter) { }
  void loadMoreBooks() { }
}

// Controller 2：只負責書籍詳情
class BookDetailController {
  BookViewModel? bookDetail;

  void loadBookDetail(String id) { }
  void updateBookDetail() { }
  void deleteBook() { }
  void shareBook() { }
  void toggleFavorite() { }
}

// Controller 3：只負責搜尋
class BookSearchController {
  List<BookViewModel> searchResults = [];

  void searchBooks(String query) { }
  void clearSearchResults() { }
  void updateSearchQuery(String query) { }
  void manageSearchHistory() { }
}

// Controller 4：只負責評分
class BookRatingController {
  void rateBook(String id, int rating) { }
  void loadBookRating(String id) { }
  void updateRating() { }
  void deleteRating() { }
}

// 步驟 2: 更新 Widget 依賴

// Before: 單一巨大 Controller
class BookshelfScreen extends StatelessWidget {
  final BookController controller; // 依賴巨大 Controller
}

// After: 使用對應的小 Controller
class BookListScreen extends StatelessWidget {
  final BookListController controller; // 只依賴需要的 Controller
}

class BookDetailScreen extends StatelessWidget {
  final BookDetailController controller;
}

class BookSearchScreen extends StatelessWidget {
  final BookSearchController controller;
}
```

**效果驗證**:

```text
重構前（Large Class）:
- BookController: 450 行，25 個方法
- 職責: 列表 + 詳情 + 搜尋 + 評分（4 種）
- 變更原因: 4 個
- 測試困難度: 高（需要 Mock 所有依賴）
- 單一測試檔案: 800+ 行

重構後（4 個小 Controller）:
- BookListController: 120 行，5 個方法
- BookDetailController: 110 行，5 個方法
- BookSearchController: 100 行，4 個方法
- BookRatingController: 80 行，4 個方法
- 每個 Controller 單一職責 ✅
- 每個 Controller 單一變更原因 ✅
- 測試困難度: 低（每個 Controller 獨立測試）
- 測試檔案: 每個 150-200 行

測試改善:
- 測試執行時間: 從 8 秒 → 2 秒（每個 Controller 獨立測試）
- Mock 複雜度: 降低 70%
- 測試可讀性: 提升（每個測試檔案更專注）

維護改善:
- 修改列表功能: 只需要修改 BookListController
- Bug 定位時間: 縮短 50%（範圍更明確）
- Code Review 時間: 縮短 40%（每個類別更小）
```

---

### 8.5 案例 5: 消除 Inappropriate Intimacy

**問題描述**:

在 Code Review 中發現 Domain 層依賴 UseCase 層。

**檢測過程**:

```dart
// ❌ 發現的問題程式碼
// lib/domain/entities/book.dart

import 'package:book_overview_app/application/use_cases/add_book_to_favorite_use_case.dart';
// ❌ Domain 不應 import UseCase

class Book {
  final String id;
  final Title title;
  final AddBookToFavoriteUseCase favoriteUseCase; // ❌ Domain 依賴 UseCase

  void addToFavorite() {
    favoriteUseCase.execute(this.id); // ❌ 呼叫 UseCase
  }

  void removeFromFavorite() {
    // 類似的錯誤模式
  }
}

// 檢測結果:
// - Domain 依賴外層（UseCase）❌
// - 違反依賴方向規則 ❌
// - Domain 失去獨立性 ❌
// - 判斷: Inappropriate Intimacy
```

**重構步驟**:

```dart
// 步驟 1: 重新設計 Domain（移除外層依賴）

// ✅ 正確的 Domain 設計
class Book {
  final String id;
  final Title title;
  bool isFavorited = false; // ✅ 只記錄狀態

  // ✅ Domain 只處理業務邏輯
  void markAsFavorite() {
    if (isFavorited) {
      throw AlreadyFavoritedException('書籍已在我的最愛');
    }
    isFavorited = true;
  }

  void unmarkFromFavorite() {
    if (!isFavorited) {
      throw NotFavoritedException('書籍不在我的最愛');
    }
    isFavorited = false;
  }

  // ✅ Domain 方法完全獨立，無外層依賴
}

// 步驟 2: UseCase 協調業務流程

// ✅ UseCase 負責協調
class AddBookToFavoriteUseCase {
  final IBookRepository bookRepository;
  final IFavoriteRepository favoriteRepository;

  Future<void> execute(String bookId) async {
    // 1. 取得書籍
    final book = await bookRepository.findById(bookId);

    // 2. 執行 Domain 方法
    book.markAsFavorite(); // ✅ UseCase 呼叫 Domain

    // 3. 儲存狀態
    await bookRepository.save(book);
    await favoriteRepository.add(bookId);

    // 4. 發送事件
    eventBus.fire(BookAddedToFavoriteEvent(bookId));
  }
}

// 步驟 3: Controller 觸發 UseCase

class BookDetailController {
  final AddBookToFavoriteUseCase addToFavoriteUseCase;

  void onFavoriteButtonPressed(String bookId) async {
    try {
      await addToFavoriteUseCase.execute(bookId); // ✅ 正確的呼叫方向
      // 更新 UI 狀態
    } catch (e) {
      // 錯誤處理
    }
  }
}
```

**依賴方向驗證**:

```text
重構前（錯誤的依賴方向）:
Layer 5 (Domain) → Layer 3 (UseCase) ❌
- Book Entity 依賴 AddBookToFavoriteUseCase
- 違反依賴倒置原則
- Domain 失去獨立性和可重用性

重構後（正確的依賴方向）:
Layer 2 → Layer 3 → Layer 5 ✅
- Controller → UseCase → Domain
- 符合依賴倒置原則
- Domain 獨立且純淨

依賴關係圖:
重構前:
Book (Layer 5) ──┐
                 ↓
AddBookToFavoriteUseCase (Layer 3) ❌ 內層依賴外層

重構後:
BookDetailController (Layer 2)
        ↓
AddBookToFavoriteUseCase (Layer 3)
        ↓
Book (Layer 5) ✅ 正確的依賴方向
```

**效果驗證**:

```text
重構前:
- Domain 依賴 UseCase ❌
- Domain 無法獨立測試 ❌
- Domain 無法重用 ❌
- 違反 Clean Architecture ❌

重構後:
- Domain 完全獨立 ✅
- Domain 可獨立測試 ✅
- Domain 可重用（可在不同 UseCase 中使用）✅
- 符合 Clean Architecture ✅

測試改善:
// 重構前：Domain 測試需要 Mock UseCase
test('should add book to favorite', () {
  final mockUseCase = MockAddBookToFavoriteUseCase();
  final book = Book(favoriteUseCase: mockUseCase); // 需要注入
  book.addToFavorite();
  verify(mockUseCase.execute(book.id)).called(1);
});

// 重構後：Domain 測試完全獨立
test('should mark book as favorite', () {
  final book = Book(...); // 無需任何 Mock
  book.markAsFavorite();
  expect(book.isFavorited, true); // 純粹的單元測試
});

架構改善:
✅ Domain 層純淨（無外層依賴）
✅ 依賴方向正確（外層→內層）
✅ 可在不同 UseCase 中重用 Domain 邏輯
✅ 易於測試和維護
```

---

## 第九章：常見問題 FAQ

### 9.1 理論問題

#### Q1: Code Smell 和 Bug 有什麼區別？

**答**:

| 特性 | Bug（程式錯誤） | Code Smell（程式異味） |
|-----|---------------|---------------------|
| **影響** | 導致功能失敗或程式崩潰 | 程式功能正常運作 |
| **檢測方式** | 透過測試失敗發現 | 透過程式碼檢視或靜態分析發現 |
| **修正優先級** | 必須立即修正 | 可規劃重構時機 |
| **修正方法** | 修正邏輯錯誤 | 透過重構改善設計 |
| **長期影響** | 直接影響用戶體驗 | 影響程式碼可維護性和擴展性 |

**範例說明**:
```dart
// Bug（程式錯誤）
void calculateTotal(List<Item> items) {
  double total = 0;
  for (var item in items) {
    total += item.price; // ❌ Bug: 沒有考慮數量
  }
  return total;
}

// Code Smell（Long Method）
void processOrder(Order order) {
  // 80 行的方法
  // 功能正常，但難以理解和維護
  // 這是 Code Smell，不是 Bug
}
```

---

#### Q2: 為什麼要從 Ticket 粒度檢測 Code Smell？

**答**:

**Ticket 粒度檢測的優勢**:

1. **及早發現問題**（設計階段 vs 實作階段）
   - 設計階段發現 → 修正成本低（只需調整設計）
   - 實作階段發現 → 修正成本中（需要重寫程式碼）
   - 維護階段發現 → 修正成本高（需要大規模重構）

2. **預防勝於治療**
   - Ticket 設計時檢測到 God Ticket → 拆分為多個 Ticket
   - 避免實作後才發現範圍過大

3. **與 TDD 四階段整合**
   - Phase 1 設計：檢測 Ticket 粒度（C1, C3, A1）
   - Phase 2 測試：檢測測試範圍（C2）
   - Phase 3 實作：檢測程式碼品質（A2, A3, A4, B2, B3）
   - Phase 4 重構：識別重構需求（B1, B2, B3, B4）

**成本對比**:
```text
Ticket 粒度檢測（Phase 1）:
- 修正成本: 1 小時（調整設計）
- 影響範圍: 無（尚未實作）
- 風險: 低

實作完成後檢測（Phase 3-4）:
- 修正成本: 8 小時（重寫程式碼）
- 影響範圍: 中（需要修改多個檔案）
- 風險: 中（需要回歸測試）

上線後檢測（維護階段）:
- 修正成本: 24 小時（大規模重構）
- 影響範圍: 大（可能影響多個模組）
- 風險: 高（可能引入新 Bug）
```

---

#### Q3: 所有 Code Smell 都必須立即修正嗎？

**答**: 不是。應該根據**優先級評估公式**決定修正時機。

**優先級分類**:

```text
優先級分數 = (影響範圍 × 3) + (業務風險 × 2) + (累積速度 × 1)

高優先級（分數 > 20）→ 立即修正
- Inappropriate Intimacy（依賴方向錯誤）
- Shotgun Surgery（影響範圍大）
- God Ticket（風險高）

中優先級（分數 10-20）→ 排入下個版本
- Feature Envy（耦合度高但不影響功能）
- Divergent Change（技術債務累積）
- Large Class（複雜度高）

低優先級（分數 < 10）→ 重構階段處理
- Long Method（可讀性問題）
- Dead Code（無功能影響）
- Incomplete Ticket（補測試即可）
```

**決策建議**:
- 高優先級：**立即修正**（影響架構或核心功能）
- 中優先級：**規劃重構**（技術債務累積但不緊急）
- 低優先級：**opportunistic 重構**（修改相關程式碼時順便重構）

---

#### Q4: Code Smell 檢測會不會過度限制創意？

**答**: 不會。Code Smell 檢查清單是**品質標準**，不是**創意限制**。

**澄清誤解**:

| 誤解 | 實際情況 |
|------|---------|
| 「檢查清單限制了我的設計」 | 檢查清單是**最低標準**，不限制創新設計 |
| 「量化指標太死板」 | 量化指標是**參考標準**，特殊情況可調整 |
| 「所有 Code Smell 都要消除」 | 根據**優先級評估**決定修正時機 |
| 「重構會降低開發速度」 | 及早重構**降低長期維護成本** |

**正確理解**:
1. **量化指標是參考，不是絕對**
   - 方法行數 > 50 行 → 「建議」拆分，不是「強制」
   - 特殊情況（如配置檔載入）可以例外

2. **檢查清單是輔助，不是束縛**
   - 幫助發現潛在問題
   - 提供重構方向
   - 不限制創新設計

3. **重構是投資，不是成本**
   - 短期投入時間重構
   - 長期降低維護成本
   - 提升團隊生產力

---

#### Q5: 本檢查清單和《層級隔離派工方法論》的關係是什麼？

**答**: **互補關係** - 《層級隔離派工方法論》定義「應該怎麼做」，本檢查清單定義「不應該怎麼做」。

**關係說明**:

| 方法論 | 《層級隔離派工方法論》 | 本 Code Smell 檢查清單 |
|-------|--------------------------|----------------------------|
| **角色** | 正面原則（應該怎麼做） | 負面模式（不應該怎麼做） |
| **內容** | 五層架構定義、單層修改原則、Ticket 粒度標準 | Code Smell 檢測、違規模式識別、重構策略 |
| **使用時機** | 設計和規劃階段 | 檢測和驗證階段 |
| **產出** | 架構設計、Ticket 規劃 | 品質檢測報告、重構建議 |

**引用關係**:
- 本檢查清單**引用**《層級隔離派工方法論》的定義，不重複定義層級架構
- 例如：Shotgun Surgery 的判斷標準引用《層級隔離派工方法論》第 5.2 節 Ticket 粒度標準

**協作流程**:
```text
Phase 1 設計:
1. 使用《層級隔離派工方法論》設計 Ticket（定義層級、規劃粒度）
2. 使用本檢查清單檢測 Ticket（檢查是否有 God Ticket、Ambiguous Responsibility）

Phase 3 實作:
1. 使用《層級隔離派工方法論》指導實作（遵循單層修改原則）
2. 使用本檢查清單檢測實作（檢查是否產生 Code Smell）

Phase 4 重構:
1. 使用本檢查清單識別 Code Smell
2. 使用本檢查清單的重構策略修正
3. 使用《層級隔離派工方法論》驗證重構後是否符合層級隔離原則
```

---

### 9.2 實務問題

#### Q6: 如何處理「必要的」Shotgun Surgery？

**答**: 區分**真正的 Shotgun Surgery** 和**合理的跨層修改**。

**特殊場景（可能需要跨層修改）**:

1. **架構遷移**（一次性重構）
   - 情境：從舊架構遷移到 Clean Architecture
   - 允許：臨時性的大規模修改
   - 要求：完整的測試覆蓋率、詳細的遷移計畫

2. **Hotfix（緊急修復）**
   - 情境：生產環境緊急 Bug 修復
   - 允許：臨時性跨層修改
   - 要求：事後必須重構、補充測試

3. **新增核心欄位**（影響多層的基礎資料）
   - 情境：新增影響整個系統的核心欄位
   - 建議：使用 Facade 模式隔離變更
   - 要求：遵循「從內而外」實作順序

**處理策略**:
```text
步驟 1: 評估是否為真正的「必要」跨層修改
  ├─ 是否為架構遷移？ → 允許（一次性）
  ├─ 是否為 Hotfix？ → 允許（事後重構）
  └─ 是否可引入 Facade 隔離？ → 建議重新設計

步驟 2: 如果確認「必要」，執行風險控制
  ├─ 確保測試覆蓋率 100%
  ├─ 建立詳細的修改計畫
  ├─ 逐層修改並測試
  └─ 記錄技術債務（Hotfix 情況）

步驟 3: 事後處理
  └─ Hotfix → 規劃重構 Ticket 消除技術債務
  └─ 架構遷移 → 完成後驗證架構一致性
```

**範例說明**:
```dart
// 情境：新增「書籍語言」核心欄位

// ❌ 錯誤：直接跨層修改
// - Layer 5: Book Entity 新增 language
// - Layer 3: GetBookDetailUseCase 處理 language
// - Layer 2: Controller 新增 language 屬性
// - Layer 1: UI 顯示 language

// ✅ 正確：使用 Facade 隔離變更
// 步驟 1 [Layer 5]: Book Entity 新增 language
// 步驟 2 [Layer 3]: BookDetailFacade 更新（統一處理）
//   - Facade 內部整合新欄位
//   - 對外介面不變或最小變更
// 步驟 3 [Layer 2]: Presenter 更新 ViewModel（只在這裡處理轉換）
// 步驟 4 [Layer 1]: UI 使用 ViewModel（透明變更）

// 效果：
// - 未來新增欄位只需修改 Facade 和 Presenter
// - Layer 1 和 Layer 5 的修改影響已隔離
```

---

#### Q7: Large Class 的 300 行標準是否太嚴格？

**答**: 300 行是**建議標準**，不是**絕對限制**。應根據**類別職責**判斷。

**彈性標準**:

```text
良好大小類別:
- < 200 行 → 優秀 ✅
- 200-300 行 → 良好（可接受）✅
- 300-400 行 → 需要注意（考慮拆分）⚠️
- > 400 行 → 需要拆分 ❌

例外情況（可以超過 300 行）:
1. 配置類別（如 analysis_options.yaml 定義類別）
2. 自動生成的程式碼（如 *.g.dart）
3. 大型 enum 定義（如包含 50+ 個值）
4. 完整的狀態機實作（如包含所有狀態轉換）

判斷原則：
「類別職責是否可以用一句話清楚描述？」
  ├─ 可以 → 即使超過 300 行也可接受
  └─ 不行 → 即使未超過 300 行也應拆分
```

**實務建議**:
```dart
// 範例 1: 可接受的 Large Class
// AppConfig.dart (350 行)
class AppConfig {
  // 統一管理所有應用程式配置
  // 職責單一且明確：「應用程式配置管理」
  // 雖然超過 300 行，但職責清晰 → 可接受 ✅

  final String appName = '書籍管理';
  final String apiBaseUrl = 'https://api.example.com';
  // ... 100+ 個配置項
}

// 範例 2: 需要拆分的類別
// BookService.dart (280 行)
class BookService {
  // 職責：書籍管理 + 查詢 + 統計 + 報表
  // 雖然未超過 300 行，但職責不單一 → 應該拆分 ❌

  void addBook() { }
  void searchBooks() { }
  void getStatistics() { }
  void exportReport() { }
}

// 重點：判斷依據是「職責是否單一」，不只是「行數」
```

---

#### Q8: 如何在敏捷開發中平衡速度和程式碼品質？

**答**: 使用**分階段品質策略** - Phase 1-3 優先速度，Phase 4 確保品質。

**分階段策略**:

```text
Phase 1 設計（重點：Ticket 粒度）:
- 檢測: God Ticket、Ambiguous Responsibility
- 目標: 確保 Ticket 範圍合理
- 時間投入: 10 分鐘/Ticket

Phase 2 測試設計（重點：測試完整性）:
- 檢測: Incomplete Ticket
- 目標: 確保有測試設計
- 時間投入: 30 分鐘/Ticket

Phase 3 實作（重點：快速交付）:
- 檢測: 嚴重的 Code Smell（Inappropriate Intimacy、Leaky Abstraction）
- 目標: 快速實作功能，避免嚴重架構問題
- 時間投入: 根據 Ticket 預估工時

Phase 4 重構（重點：持續改進）:
- 檢測: 所有 Code Smell
- 目標: 識別技術債務，規劃重構
- 時間投入: 20% 時間用於重構

平衡原則：
「先快速交付功能（Phase 3），再持續改進品質（Phase 4）」
```

**實務做法**:
```text
Sprint 規劃:
- 80% 時間: 功能開發（Phase 1-3）
- 20% 時間: 技術債務償還（Phase 4 重構）

每個 Sprint:
1. 功能開發（快速交付）
   - 確保基本品質（無嚴重 Code Smell）
   - 允許存在低優先級 Code Smell

2. 技術債務償還（持續改進）
   - 根據優先級評估公式選擇重構項目
   - 優先處理高優先級 Code Smell

3. 平衡指標
   - 新功能交付速度 ✅
   - 技術債務控制在可接受範圍 ✅
   - 測試覆蓋率維持 95%+ ✅
```

---

#### Q9: Code Smell 檢測是否會增加 Code Review 時間？

**答**: 短期增加 5-10 分鐘，長期**縮短** Code Review 時間 30-40%。

**時間分析**:

```text
傳統 Code Review（無系統化檢測）:
- 審查時間: 30-45 分鐘/PR
- 問題發現率: 60%（依賴 Reviewer 經驗）
- 往返次數: 平均 2-3 次
- 總時間成本: 60-120 分鐘

使用 Code Smell 檢查清單:
- 快速檢查: 5 分鐘（使用 6.1 快速檢查清單）
- 深度檢查: 15 分鐘（使用 6.2 深度檢查清單）
- 問題發現率: 90%（系統化檢測）
- 往返次數: 平均 1 次（問題更早發現）
- 總時間成本: 20-30 分鐘

時間節省: 40-90 分鐘/PR（66-75% 改善）
```

**改善原因**:
1. **系統化檢測更快**（不依賴回憶）
2. **問題更早發現**（減少往返次數）
3. **檢測標準統一**（減少討論時間）

**實測數據**:
```text
專案A (10 人團隊，100 個 PR/月):
- 導入前: 平均 Code Review 時間 45 分鐘/PR
- 導入後: 平均 Code Review 時間 18 分鐘/PR
- 改善: 60% 時間節省
- 每月節省: 27 * 100 = 2700 分鐘（45 小時）

品質改善:
- Bug 數量: 減少 40%
- 重構需求: 減少 50%（問題更早發現）
- 團隊滿意度: 提升（減少返工）
```

---

#### Q10: 團隊成員對 Code Smell 標準有不同理解怎麼辦？

**答**: 建立**共識機制** - 團隊 Code Smell 討論會 + 案例庫。

**共識建立流程**:

```text
步驟 1: 初始化階段（第 1-2 週）
  - 全體成員閱讀本 Code Smell 檢查清單
  - 舉辦 Code Smell 培訓工作坊（2 小時）
  - 討論量化標準是否適用於團隊

步驟 2: 調整階段（第 3-4 週）
  - 每週 Code Smell 討論會（30 分鐘）
  - 討論爭議案例
  - 調整團隊特定標準（如果需要）

步驟 3: 穩定階段（第 5 週後）
  - 建立團隊 Code Smell 案例庫
  - 持續更新檢查清單
  - 每月回顧和優化標準
```

**爭議處理機制**:

```text
情境：團隊成員對「Large Class」標準有不同意見

成員 A: 「300 行太嚴格，我們的配置類別都超過 300 行」
成員 B: 「300 行是合理標準，配置類別應該拆分」

處理流程:
1. 討論會議（30 分鐘）
   - 展示具體案例
   - 分析職責是否單一
   - 評估拆分成本和收益

2. 團隊共識
   - 投票決定團隊標準
   - 記錄決策理由
   - 更新團隊檢查清單

3. 案例記錄
   - 將決策加入團隊案例庫
   - 未來遇到類似情況參考此案例
```

**團隊案例庫範例**:

```markdown
# 團隊 Code Smell 案例庫

## 案例 #1: AppConfig 類別（350 行）

**爭議**: 是否屬於 Large Class？

**團隊決議**: ✅ 可接受
**理由**: 職責單一（應用程式配置管理），雖超過 300 行但不拆分

**標準**: 配置類別可以超過 300 行，但職責必須單一

---

## 案例 #2: BookController（280 行，4 種職責）

**爭議**: 未超過 300 行，是否需要拆分？

**團隊決議**: ❌ 需要拆分
**理由**: 雖未超過 300 行，但有 4 種職責（Divergent Change）

**標準**: 判斷依據是「職責是否單一」，不只是「行數」
```

---

### 9.3 工具問題

#### Q11: 如何自動化檢測 Code Smell？

**答**: 整合靜態分析工具 + Hook 系統 + CI/CD pipeline。

**自動化檢測架構**:

```text
Level 1: 本地開發（即時反饋）
  └─ PostEdit Hook → 程式碼修改後立即檢測
     ├─ dart analyze（Dead Code、unused 警告）
     ├─ 檔案行數檢查（Large Class、Long Method）
     └─ import 語句分析（Feature Envy、Inappropriate Intimacy）

Level 2: 提交前（全面檢測）
  └─ Pre-Commit Hook → git commit 前檢測
     ├─ 執行所有 Level 1 檢測
     ├─ 測試覆蓋率檢查（Incomplete Ticket）
     └─ Code Smell 優先級評估

Level 3: PR 階段（完整報告）
  └─ GitHub Actions → PR 提交時檢測
     ├─ 執行所有 Level 1-2 檢測
     ├─ 生成 Code Smell 檢測報告
     └─ 高優先級問題阻止合併
```

**工具整合範例**:

```bash
# .claude/hooks/post-edit.sh
#!/bin/bash

# Level 1: 即時檢測
echo "執行 Code Smell 即時檢測..."

# 1. dart analyze
dart analyze --fatal-infos 2>&1 | grep "unused" && {
  echo "⚠️ 檢測到 Dead Code (unused 警告)"
}

# 2. 檔案行數檢查
for file in $(git diff --name-only --staged); do
  if [[ $file == *.dart ]]; then
    lines=$(wc -l < "$file")
    if [ "$lines" -gt 300 ]; then
      echo "⚠️ Large Class: $file ($lines 行)"
    fi
  fi
done

# 3. import 語句分析
for file in $(git diff --name-only --staged); do
  if [[ $file == lib/presentation/* ]]; then
    if grep -q "import.*domains/.*/entities" "$file"; then
      echo "⚠️ Feature Envy: UI 直接 import Domain Entity"
    fi
  fi
done
```

**CI/CD 整合範例**:

```yaml
# .github/workflows/code-smell.yml
name: Code Smell 檢測

on: [pull_request]

jobs:
  code-smell:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3

      - name: Code Smell 檢測
        run: |
          # 執行完整檢測
          bash .claude/scripts/code-smell-check.sh

          # 生成報告
          python .claude/scripts/generate-report.py

      - name: 檢查優先級
        run: |
          # 高優先級問題 → 阻止合併
          python .claude/scripts/check-priority.py --fail-on-high
```

---

#### Q12: dart_code_metrics 和本檢查清單的關係？

**答**: **互補關係** - dart_code_metrics 提供量化指標，本檢查清單提供架構檢測。

**工具定位**:

| 工具 | dart_code_metrics | Code Smell 檢查清單（本文件） |
|-----|------------------|---------------------------|
| **檢測範圍** | 程式碼複雜度、重複度 | 架構設計、層級隔離 |
| **檢測對象** | 單一檔案、方法 | 跨檔案、跨層級 |
| **量化指標** | 循環複雜度、認知複雜度 | 檔案數、層級跨度 |
| **適用場景** | Phase 3 實作、Phase 4 重構 | Phase 1 設計、Code Review |

**整合使用**:

```yaml
# analysis_options.yaml
dart_code_metrics:
  metrics:
    # B3. Long Method 檢測
    cyclomatic-complexity: 20
    lines-of-code: 50
    maximum-nesting-level: 3

    # B2. Large Class 檢測
    number-of-methods: 15
    weight-of-class: 0.33

  rules:
    # B4. Dead Code 檢測
    - avoid-unused-parameters

    # B1. Divergent Change 檢測
    - prefer-single-widget-per-file
```

**協作流程**:

```text
步驟 1: dart_code_metrics 檢測程式碼複雜度
  └─ 輸出: 方法行數、循環複雜度、認知複雜度

步驟 2: 本檢查清單檢測架構問題
  └─ 輸出: 層級跨度、依賴方向、Ticket 粒度

步驟 3: 整合報告
  └─ 結合兩者結果，提供完整的 Code Smell 檢測報告
```

---

#### Q13: 如何處理自動生成的程式碼（如 *.g.dart）？

**答**: 在檢測配置中**排除**自動生成的程式碼。

**排除配置**:

```yaml
# analysis_options.yaml
analyzer:
  exclude:
    # 排除自動生成的程式碼
    - "**/*.g.dart"
    - "**/*.freezed.dart"
    - "**/generated/**"
    - "build/**"

    # 排除第三方程式碼
    - "lib/generated_plugin_registrant.dart"
```

**Hook 系統排除**:

```bash
# .claude/hooks/code-smell-check.sh
#!/bin/bash

# 排除自動生成的檔案
for file in $(git diff --name-only --staged); do
  # 跳過 *.g.dart
  if [[ $file == *.g.dart ]]; then
    continue
  fi

  # 跳過 *.freezed.dart
  if [[ $file == *.freezed.dart ]]; then
    continue
  fi

  # 執行檢測
  check_code_smell "$file"
done
```

**原則**:
- ✅ 檢測：手寫程式碼
- ❌ 不檢測：自動生成的程式碼（*.g.dart, *.freezed.dart）
- ❌ 不檢測：第三方程式碼（dependencies）
- ❌ 不檢測：測試 Mock 程式碼（*.mocks.dart）

---

#### Q14: 如何在 VS Code 中整合 Code Smell 檢測？

**答**: 使用 **VS Code 擴充功能** + **Tasks** + **Problem Matchers**。

**設定檔配置**:

```json
// .vscode/tasks.json
{
  "version": "2.0.0",
  "tasks": [
    {
      "label": "Code Smell 檢測",
      "type": "shell",
      "command": "bash .claude/scripts/code-smell-check.sh",
      "problemMatcher": {
        "owner": "code-smell",
        "fileLocation": "relative",
        "pattern": {
          "regexp": "^(⚠️|❌)\\s+(\\w+):\\s+(.+)\\s+\\((.+):(\\d+)\\)$",
          "severity": 1,
          "code": 2,
          "message": 3,
          "file": 4,
          "line": 5
        }
      },
      "group": {
        "kind": "test",
        "isDefault": true
      }
    }
  ]
}
```

**快捷鍵設定**:

```json
// .vscode/keybindings.json
[
  {
    "key": "ctrl+shift+s",
    "command": "workbench.action.tasks.runTask",
    "args": "Code Smell 檢測"
  }
]
```

**使用方式**:
1. 按 `Ctrl+Shift+S` 執行 Code Smell 檢測
2. 問題面板顯示檢測結果
3. 點擊問題項目跳轉到對應程式碼

---

#### Q15: 測試覆蓋率工具與 Code Smell 檢測的關係？

**答**: 測試覆蓋率工具檢測**測試完整性**，輔助識別 **Dead Code** 和 **Incomplete Ticket**。

**工具整合**:

```bash
# 1. 執行測試並生成覆蓋率報告
flutter test --coverage

# 2. 分析覆蓋率報告
# a. 0% 覆蓋率 → 可能是 Dead Code
lcov --summary coverage/lcov.info | grep "0.0%"

# b. 新增程式碼無測試 → Incomplete Ticket
git diff main --name-only | while read file; do
  if [[ $file == lib/*.dart ]]; then
    test_file="test/${file#lib/}"
    test_file="${test_file%.dart}_test.dart"
    if [ ! -f "$test_file" ]; then
      echo "⚠️ Incomplete Ticket: $file 缺少測試檔案"
    fi
  fi
done

# 3. 生成 HTML 報告
genhtml coverage/lcov.info -o coverage/html
```

**Dead Code 檢測流程**:

```text
步驟 1: 執行測試覆蓋率分析
  └─ flutter test --coverage

步驟 2: 識別 0% 覆蓋率程式碼
  └─ 可能是 Dead Code 或缺少測試

步驟 3: 交叉驗證
  ├─ dart analyze 有 unused 警告？ → Dead Code ✅
  └─ dart analyze 無警告？ → 缺少測試 ⚠️

步驟 4: 採取行動
  ├─ Dead Code → 刪除
  └─ 缺少測試 → 補充測試
```

**Incomplete Ticket 檢測流程**:

```text
步驟 1: 檢查程式碼檔案是否有對應測試
  └─ lib/foo.dart → test/foo_test.dart 是否存在？

步驟 2: 檢查測試覆蓋率
  └─ 新增程式碼覆蓋率是否達到 100%？

步驟 3: 判斷
  ├─ 無測試檔案 → Incomplete Ticket ❌
  ├─ 覆蓋率 < 100% → Incomplete Ticket ⚠️
  └─ 覆蓋率 = 100% → 完整 Ticket ✅
```

---

## 第十章：參考資料

### 10.1 引用的方法論

本 Code Smell 檢查清單基於以下方法論建立：

#### 《層級隔離派工方法論》

**檔案位置**: `.claude/methodologies/layered-ticket-methodology.md`

**引用章節**:
- **2.2 節**: Clean Architecture 五層完整定義
  - Layer 1 (UI): 視覺呈現職責
  - Layer 2 (Behavior): 事件處理和資料轉換職責
  - Layer 3 (UseCase): 業務流程協調職責
  - Layer 4 (Domain Interface): 介面契約職責
  - Layer 5 (Domain): 業務規則和不可變邏輯職責

- **2.3 節**: 依賴方向規則
  - 正確依賴方向：Layer 1 → Layer 2 → Layer 3 → Layer 4 ← Layer 5

- **2.4 節**: 層級定位決策樹
  - 檔案路徑分析法判斷層級歸屬

- **3.1 節**: 單層修改原則定義
  - 單一 Ticket 應該只修改單一架構層級

- **3.2 節**: SRP 理論依據
  - Single Responsibility Principle 應用

- **5.2 節**: Ticket 粒度量化指標
  - 良好 Ticket：1-5 個檔案，1 層，2-8 小時
  - God Ticket：> 10 個檔案，> 2 層，> 16 小時

- **5.4 節**: Ticket 拆分指引
  - 按層級拆分、按 Domain 拆分、按功能拆分

- **6.2 節**: 檔案路徑分析法
  - 從檔案路徑判斷層級歸屬

- **6.4 節**: 測試層級對應原則
  - 測試檔案路徑對應層級結構

- **6.5 節**: 違規模式識別
  - 常見的層級違規模式

**關係說明**:
- 《層級隔離派工方法論》定義「應該怎麼做」（正面原則）
- 本檢查清單定義「不應該怎麼做」（負面模式識別）
- 兩者互補，共同建構完整的品質標準體系

---

### 10.2 Code Smell 理論文獻

#### Martin Fowler - Refactoring: Improving the Design of Existing Code

**重要概念**:
- Code Smell 定義和分類
- 重構模式目錄
- Extract Method、Extract Class、Move Method 等重構技巧

**本檢查清單應用**:
- 第四章重構模式對應表引用 Fowler 的重構模式
- 重構步驟設計參考 Fowler 的重構技巧

**延伸閱讀**: https://refactoring.com/

---

#### Robert C. Martin - Clean Code

**重要概念**:
- 有意義的命名
- 函式應該短小
- 單一職責原則（SRP）
- 依賴倒置原則（DIP）

**本檢查清單應用**:
- Long Method 判斷標準（< 50 行）
- Divergent Change 檢測（SRP 違反）
- Inappropriate Intimacy 檢測（DIP 違反）

---

#### Robert C. Martin - Clean Architecture

**重要概念**:
- 分層架構設計
- 依賴規則（Dependency Rule）
- 介面隔離原則

**本檢查清單應用**:
- A 類 Code Smell 分類（跨層級問題）
- Inappropriate Intimacy 檢測（依賴方向錯誤）
- Leaky Abstraction 檢測（介面設計問題）

---

### 10.3 重構模式參考

#### Extract Interface（提取介面）

**用途**: 修正 Leaky Abstraction

**重構步驟**:
1. 分析具體類別的公開方法
2. 建立介面定義
3. 提取抽象方法簽名
4. 讓具體類別實作介面
5. 更新依賴為使用介面

**參考**: Fowler, Refactoring (1999), p.341

---

#### Extract Method（提取方法）

**用途**: 修正 Long Method

**重構步驟**:
1. 識別邏輯區塊
2. 為區塊建立新方法
3. 傳遞必要參數
4. 回傳必要值
5. 替換原區塊為方法呼叫

**參考**: Fowler, Refactoring (1999), p.110

---

#### Extract Class（提取類別）

**用途**: 修正 Large Class、Divergent Change

**重構步驟**:
1. 分析方法分組
2. 建立新類別
3. 移動相關欄位和方法
4. 建立委派方法（如需要）
5. 更新依賴關係

**參考**: Fowler, Refactoring (1999), p.149

---

#### Move Method（移動方法）

**用途**: 修正 Feature Envy

**重構步驟**:
1. 識別方法應該屬於哪個類別
2. 在目標類別建立方法
3. 調整參數和回傳值
4. 移除原方法或建立委派
5. 更新呼叫端

**參考**: Fowler, Refactoring (1999), p.142

---

#### Introduce Facade（引入外觀）

**用途**: 修正 Shotgun Surgery

**重構步驟**:
1. 分析跨層操作的共同點
2. 建立 Facade 介面
3. 實作 Facade 封裝跨層操作
4. 更新呼叫端使用 Facade
5. 驗證未來變更只需修改 Facade

**參考**: Gang of Four, Design Patterns (1994), p.185

---

### 10.4 檢測工具文檔

#### Dart Analyzer

**官方文檔**: https://dart.dev/tools/dart-analyze

**主要功能**:
- 靜態程式碼分析
- unused 警告檢測（Dead Code）
- 循環依賴檢測（Inappropriate Intimacy）
- 型別檢查

**配置檔**: `analysis_options.yaml`

---

#### dart_code_metrics

**官方文檔**: https://pub.dev/packages/dart_code_metrics

**主要功能**:
- 程式碼複雜度分析（Cyclomatic Complexity）
- 認知複雜度分析（Cognitive Complexity）
- 程式碼重複度檢測
- Code Smell 規則檢測

**安裝方式**:
```bash
dart pub global activate dart_code_metrics
```

---

#### lcov（測試覆蓋率工具）

**官方文檔**: http://ltp.sourceforge.net/coverage/lcov.php

**主要功能**:
- 程式碼覆蓋率分析
- HTML 報告生成
- 0% 覆蓋率檢測（Dead Code 輔助）

**使用方式**:
```bash
flutter test --coverage
genhtml coverage/lcov.info -o coverage/html
```

---

#### GitHub Actions

**官方文檔**: https://docs.github.com/actions

**主要功能**:
- CI/CD pipeline 自動化
- PR 自動檢測
- Code Smell 檢測報告生成

**配置檔**: `.github/workflows/*.yml`

---

### 10.5 延伸閱讀

#### 書籍推薦

1. **Refactoring: Improving the Design of Existing Code (2nd Edition)**
   - 作者：Martin Fowler
   - 出版年：2018
   - 重點：重構模式目錄、Code Smell 識別

2. **Clean Code: A Handbook of Agile Software Craftsmanship**
   - 作者：Robert C. Martin
   - 出版年：2008
   - 重點：程式碼品質原則、有意義的命名

3. **Clean Architecture: A Craftsman's Guide to Software Structure and Design**
   - 作者：Robert C. Martin
   - 出版年：2017
   - 重點：分層架構設計、依賴規則

4. **Design Patterns: Elements of Reusable Object-Oriented Software**
   - 作者：Gang of Four
   - 出版年：1994
   - 重點：Facade 模式、設計模式目錄

---

#### 線上資源

1. **Refactoring.com**
   - https://refactoring.com/
   - Martin Fowler 的重構資源網站

2. **Clean Coder Blog**
   - https://blog.cleancoder.com/
   - Robert C. Martin 的部落格

3. **Dart Language Tour**
   - https://dart.dev/language
   - Dart 語言官方文檔

4. **Flutter Best Practices**
   - https://flutter.dev/docs/development/best-practices
   - Flutter 官方最佳實踐指引

---

### 10.6 工具與腳本

本檢查清單相關的工具和腳本位於：

**Hook 系統腳本**:
- `.claude/hooks/code-smell-detection-hook.sh` - Code Smell 檢測 Hook
- `.claude/hooks/pr-validation-hook.sh` - PR 驗證 Hook

**檢測腳本**:
- `.claude/scripts/code-smell-check.sh` - Code Smell 完整檢測腳本
- `.claude/scripts/generate-code-smell-report.py` - 報告生成腳本
- `.claude/scripts/check-priority.py` - 優先級檢查腳本

**配置檔**:
- `analysis_options.yaml` - Dart Analyzer 配置
- `.github/workflows/code-smell.yml` - GitHub Actions 配置

---

## 📊 文件資訊

**版本**: v1.0.0
**建立日期**: 2025-10-11
**適用範圍**: 基於 Clean Architecture 五層架構的專案
**基於方法論**: 《層級隔離派工方法論》(.claude/methodologies/layered-ticket-methodology.md)

**文件結構**:
- 總章節: 10 章
- 預估頁數: 125 頁
- Code Smell 數量: 11 種（A 類 4 種、B 類 4 種、C 類 3 種）
- 檢測方法: 完整的檢測流程和判斷標準
- 重構策略: 11 種重構模式對應
- 實踐案例: 5 個完整案例
- 常見問題: 15 個 FAQ

**維護責任**:
- 主要維護者：專案架構師
- 更新頻率：每季度回顧
- 版本管理：遵循語義化版本規範

---

**文件完成狀態**: Code Smell 檢查清單 - 完整文件撰寫完成 ✅
