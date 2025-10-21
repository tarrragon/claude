# 🏗 Clean Architecture 實作方法論

## 📖 方法論概述

本方法論提供系統化的 Clean Architecture 實作指引，整合依賴反轉原則（DIP）、Interface-Driven Development、TDD 四階段流程和敏捷重構方法論，確保架構設計的獨立性、可測試性和可維護性。

**目標讀者**：
- 需要設計和實作 Clean Architecture 的開發人員
- 執行 TDD 四階段流程的專業代理人
- 負責架構審查和品質把關的技術主管

**核心價值**：
- ✅ 提供明確的設計和實作順序參考
- ✅ 建立 Interface-Driven Development 實務標準
- ✅ 整合 TDD 和敏捷重構方法論
- ✅ 提供可執行的檢查清單和實務案例

---

## 第一章：Clean Architecture 核心原則與哲學

### 1.1 Clean Architecture 定義與目標

**Clean Architecture 定義**：

Clean Architecture 是一種軟體架構模式，由 Robert C. Martin (Uncle Bob) 提出，強調系統的核心業務邏輯應該獨立於外部技術框架、資料庫、UI 和其他基礎設施。

**核心目標**：

1. **獨立性（Independence）**
   - 業務邏輯不依賴框架（Framework）
   - 業務邏輯不依賴 UI 實作
   - 業務邏輯不依賴資料庫技術
   - 業務邏輯不依賴外部系統

2. **可測試性（Testability）**
   - 核心業務邏輯可獨立測試
   - 不需要啟動框架或資料庫即可測試
   - 測試快速且穩定

3. **可維護性（Maintainability）**
   - 變更 UI 不影響業務邏輯
   - 變更資料庫不影響業務邏輯
   - 變更框架不影響業務邏輯
   - 系統易於理解和修改

**價值主張**：

Clean Architecture 讓系統的「業務核心」和「技術細節」明確分離，技術框架可以隨時替換而不影響業務邏輯，大幅降低技術債務和維護成本。

### 1.2 四層架構分層

Clean Architecture 採用同心圓分層架構，由內到外依序為：

**第一層：Entities（企業核心規則）**

**定義**：
- 封裝企業級的核心業務規則和資料
- 代表業務領域的核心概念（如「訂單」、「客戶」、「書籍」）
- 不依賴任何框架、資料庫或外部技術

**責任**：
- 定義業務實體的屬性和行為
- 實現業務不變量（Business Invariants）
- 執行核心業務驗證規則

**範例**：
```dart
// ✅ Entities 層：純粹的業務邏輯，不依賴任何框架
class Book {
  final ISBN isbn;
  final Title title;
  final Author author;

  Book({
    required this.isbn,
    required this.title,
    required this.author,
  });

  // 業務不變量：書籍必須有有效的 ISBN
  void validate() {
    if (!isbn.isValid()) {
      throw ValidationException('ISBN 格式無效');
    }
  }
}
```

**第二層：Use Cases（應用業務規則）**

**定義**：
- 封裝應用程式特定的業務規則
- 協調 Entities 之間的互動
- 定義系統的功能（如「建立訂單」、「取消訂單」）

**責任**：
- 定義輸入介面（Input Port）
- 定義輸出介面（Output Port）
- 協調 Entities 和外部系統互動
- 執行應用層業務規則

**範例**：
```dart
// ✅ Use Cases 層：定義應用業務規則和介面契約
abstract class CreateBookUseCase {
  Future<CreateBookOutput> execute(CreateBookInput input);
}

class CreateBookInput {
  final String isbn;
  final String title;
  final String author;

  CreateBookInput({
    required this.isbn,
    required this.title,
    required this.author,
  });
}

class CreateBookOutput {
  final Book book;
  final String message;

  CreateBookOutput({required this.book, required this.message});
}
```

**第三層：Interface Adapters（介面轉接層）**

**定義**：
- 轉換資料格式以符合 Use Cases 和外部系統的需求
- 實現 Controller、Presenter、Repository 等介面
- 橋接內層業務邏輯和外層技術細節

**責任**：
- Controller：接收外部請求，轉換為 Use Case 輸入
- Presenter：格式化 Use Case 輸出，呈現給 UI
- Repository：實現資料存取介面，隔離資料庫技術

**範例**：
```dart
// ✅ Interface Adapters 層：轉接外部請求和內層業務邏輯
class BookController {
  final CreateBookUseCase createBookUseCase;

  BookController({required this.createBookUseCase});

  Future<void> handleCreateBook(HttpRequest request) async {
    // 轉換 HTTP 請求為 Use Case 輸入
    final input = CreateBookInput(
      isbn: request.body['isbn'],
      title: request.body['title'],
      author: request.body['author'],
    );

    // 執行 Use Case
    final output = await createBookUseCase.execute(input);

    // 格式化回應
    return HttpResponse.ok({'book': output.book});
  }
}
```

**第四層：Frameworks & Drivers（框架與外部系統）**

**定義**：
- 外部技術框架（Web、資料庫、UI、第三方服務）
- 系統最外層，包含所有技術細節
- 可隨時替換而不影響內層

**責任**：
- Web 框架（Express、Spring、Flutter）
- 資料庫技術（MySQL、MongoDB、SQLite）
- UI 框架（React、Flutter、Vue）
- 外部設備（相機、感測器、網路）

**範例**：
```dart
// ✅ Frameworks & Drivers 層：具體的技術實作
class SQLiteBookRepository implements BookRepository {
  final Database database;

  SQLiteBookRepository({required this.database});

  @override
  Future<Book> save(Book book) async {
    // 使用 SQLite 儲存資料
    await database.insert('books', {
      'isbn': book.isbn.value,
      'title': book.title.value,
      'author': book.author.value,
    });
    return book;
  }
}
```

### 1.3 依賴方向規則

**核心原則**：依賴只能由外向內，內層不得依賴外層

**依賴方向圖**

```text
┌─────────────────────────────────────────┐
│   Frameworks & Drivers (外層)          │
│   Web, DB, UI, Devices                  │
│          ↓ 依賴方向                      │
│   ┌─────────────────────────────────┐   │
│   │ Interface Adapters (轉接層)     │   │
│   │ Controller, Presenter, Repo     │   │
│   │        ↓ 依賴方向                │   │
│   │   ┌─────────────────────────┐   │   │
│   │   │ Use Cases (應用層)      │   │   │
│   │   │ Application Logic       │   │   │
│   │   │      ↓ 依賴方向          │   │   │
│   │   │   ┌─────────────────┐   │   │   │
│   │   │   │ Entities (核心) │   │   │   │
│   │   │   │ Business Logic  │   │   │   │
│   │   │   └─────────────────┘   │   │   │
│   │   └─────────────────────────┘   │   │
│   └─────────────────────────────────┘   │
└─────────────────────────────────────────┘
```

**依賴反轉原則（Dependency Inversion Principle, DIP）**

**定義**：
- 高層模組不應該依賴低層模組，兩者都應該依賴抽象
- 抽象不應該依賴細節，細節應該依賴抽象

**實踐方式**：

```dart
// ❌ 錯誤：Use Case 直接依賴具體的 Repository 實作
class CreateBookUseCase {
  final SQLiteBookRepository repository; // 依賴具體實作

  CreateBookUseCase({required this.repository});
}

// ✅ 正確：Use Case 依賴抽象介面
abstract class BookRepository {
  Future<Book> save(Book book);
  Future<Book?> findByISBN(ISBN isbn);
}

class CreateBookUseCase {
  final BookRepository repository; // 依賴抽象介面

  CreateBookUseCase({required this.repository});

  Future<CreateBookOutput> execute(CreateBookInput input) async {
    // 使用抽象介面，不關心具體實作
    final book = Book.create(
      isbn: ISBN(input.isbn),
      title: Title(input.title),
      author: Author(input.author),
    );

    final savedBook = await repository.save(book);
    return CreateBookOutput(book: savedBook, message: '建立成功');
  }
}
```

**優勢**：
- Use Case 不知道資料儲存在 SQLite、MySQL 或 MongoDB
- 可以輕易替換 Repository 實作而不修改 Use Case
- 測試時可以使用 Mock Repository

**依賴注入（Dependency Injection）**

**定義**：
在組裝階段（Composition Root）將具體實作注入到依賴抽象介面的元件中。

**實踐方式**：

```dart
// 組裝階段：連接抽象介面和具體實作
void main() {
  // Step 1: 建立基礎設施層實作
  final database = SQLiteDatabase.open('books.db');
  final bookRepository = SQLiteBookRepository(database: database);

  // Step 2: 建立 Use Case，注入 Repository 介面
  final createBookUseCase = CreateBookInteractor(
    repository: bookRepository, // 注入具體實作
  );

  // Step 3: 建立 Controller，注入 Use Case
  final bookController = BookController(
    createBookUseCase: createBookUseCase,
  );

  // Step 4: 啟動應用程式
  runApp(bookController);
}
```

**關鍵點**：
- 具體實作在組裝階段才被注入
- Use Case 和 Controller 只依賴介面，不知道具體實作
- 替換實作只需修改組裝階段程式碼

### 1.4 Clean Architecture 的價值

**價值 1：提升程式碼品質**

**具體表現**：
- 業務邏輯集中在 Entities 和 Use Cases，易於理解和維護
- 介面契約明確，減少模組間的耦合
- 依賴反轉讓程式碼更靈活和可擴展

**範例**：
```dart
// ✅ 業務邏輯集中在 Entity，清晰易懂
class Book {
  final ISBN isbn;
  final Title title;

  // 業務規則：書籍標題不可為空
  Book({required this.isbn, required this.title}) {
    if (title.value.isEmpty) {
      throw ValidationException('書籍標題不可為空');
    }
  }
}
```

**價值 2：降低維護成本**

**具體表現**：
- 修改 UI 不影響業務邏輯
- 替換資料庫技術只需修改 Repository 實作
- 升級框架版本不影響核心系統

**範例**：
```dart
// ✅ 替換資料庫技術只需實作新的 Repository
class MongoDBBookRepository implements BookRepository {
  final MongoDatabase database;

  MongoDBBookRepository({required this.database});

  @override
  Future<Book> save(Book book) async {
    // 使用 MongoDB 儲存資料
    await database.collection('books').insertOne({
      'isbn': book.isbn.value,
      'title': book.title.value,
    });
    return book;
  }
}

// Use Case 完全不需要修改，繼續使用抽象介面
```

**價值 3：提高開發效率**

**具體表現**：
- 團隊可並行開發不同層級
- 介面定義完成後即可開始測試
- 清晰的責任邊界減少溝通成本

**範例**：
```dart
// ✅ 前端團隊可以使用 Mock Repository 開發 UI
class MockBookRepository implements BookRepository {
  @override
  Future<Book> save(Book book) async {
    // 回傳假資料，不需要真實資料庫
    return book;
  }
}

// 後端團隊可以獨立開發真實的 Repository 實作
```

**價值 4：測試覆蓋率高**

**具體表現**：
- Entities 和 Use Cases 可獨立測試
- 測試不需要啟動資料庫或框架
- 測試速度快且穩定

**範例**：
```dart
// ✅ Use Case 測試使用 Mock Repository
void main() {
  test('建立書籍成功', () async {
    // Arrange
    final mockRepository = MockBookRepository();
    final useCase = CreateBookInteractor(repository: mockRepository);
    final input = CreateBookInput(
      isbn: '978-3-16-148410-0',
      title: 'Clean Architecture',
      author: 'Robert C. Martin',
    );

    // Act
    final output = await useCase.execute(input);

    // Assert
    expect(output.book.title.value, 'Clean Architecture');
  });
}
```

---

## 第二章：設計階段原則（Inner → Outer）

### 2.1 設計思考方向：由內往外

**核心原則**：設計階段必須從內層（Entities、Use Cases）開始，由內往外逐步定義介面契約。

**為什麼從內層開始？**

1. **業務核心是系統本質**
   - Entities 和 Use Cases 代表系統的核心價值
   - 外層技術可以替換，但業務邏輯是系統的基石

2. **內層不依賴外層**
   - 內層設計時不需要知道外層技術細節
   - 先定義「做什麼」，再決定「怎麼做」

3. **介面契約由內層定義**
   - Use Cases 定義需要什麼樣的 Repository 介面
   - 外層實作必須符合內層定義的契約

**設計思考流程**：

```text
Step 1: 定義 Entities（核心業務規則）
    ↓ 建立業務模型
Step 2: 定義 Use Cases（應用業務規則）
    ↓ 定義輸入/輸出介面（Ports）
Step 3: 定義 Interface Adapters（介面契約）
    ↓ Repository、Service、Gateway 介面
Step 4: 定義 Frameworks & Drivers（技術選型）
    ↓ 選擇 Web、DB、UI 技術
```

### 2.2 Step 1: Entities 設計優先

**設計目標**：定義核心業務實體和業務不變量。

**設計要點**

1. **識別業務核心概念**
   - 從需求中提取核心業務實體（如書籍、訂單、客戶）
   - 定義實體的屬性和行為

2. **定義業務不變量**
   - 業務規則必須始終成立（如 ISBN 格式必須有效）
   - 實體建立時即驗證不變量

3. **使用 Value Objects**
   - 封裝業務概念（如 ISBN、Title、Author）
   - 確保值的有效性和不可變性

**設計範例**：

```dart
// ✅ Step 1: 設計核心業務實體

// Value Object：ISBN
class ISBN {
  final String value;

  ISBN(this.value) {
    if (!_isValid(value)) {
      throw ValidationException('ISBN 格式無效');
    }
  }

  bool _isValid(String value) {
    // ISBN-13 格式驗證邏輯
    return RegExp(r'^\d{3}-\d{1,5}-\d{1,7}-\d{1,7}-\d{1}$').hasMatch(value);
  }

  @override
  bool operator ==(Object other) =>
      identical(this, other) ||
      other is ISBN && value == other.value;

  @override
  int get hashCode => value.hashCode;
}

// Value Object：Title
class Title {
  final String value;

  Title(this.value) {
    if (value.isEmpty) {
      throw ValidationException('書籍標題不可為空');
    }
    if (value.length > 200) {
      throw ValidationException('書籍標題過長（最多 200 字元）');
    }
  }
}

// Entity：Book
class Book {
  final ISBN isbn;
  final Title title;
  final Author author;
  final DateTime createdAt;

  Book({
    required this.isbn,
    required this.title,
    required this.author,
    DateTime? createdAt,
  }) : createdAt = createdAt ?? DateTime.now();

  // 工廠方法：建立新書籍
  factory Book.create({
    required String isbn,
    required String title,
    required String author,
  }) {
    return Book(
      isbn: ISBN(isbn),
      title: Title(title),
      author: Author(author),
    );
  }

  // 業務行為：更新標題
  Book updateTitle(String newTitle) {
    return Book(
      isbn: isbn,
      title: Title(newTitle), // 重新驗證標題
      author: author,
      createdAt: createdAt,
    );
  }
}
```

**設計檢查清單**：

- [ ] 核心業務實體已識別（Entity、Value Object）
- [ ] 業務不變量已定義並驗證
- [ ] Value Objects 確保值的有效性和不可變性
- [ ] Entity 屬性使用 Value Objects 封裝
- [ ] Entity 不依賴任何框架或技術細節

### 2.3 Step 2: Use Cases 設計次之

**設計目標**：定義應用業務規則和輸入/輸出介面（Ports）。

**設計要點**

1. **識別系統功能**
   - 從用例圖中提取系統功能（如「建立書籍」、「查詢書籍」）
   - 每個功能對應一個 Use Case

2. **定義輸入介面（Input Port）**
   - Use Case 的執行入口
   - 定義輸入資料結構

3. **定義輸出介面（Output Port）**
   - Use Case 的執行結果
   - 定義輸出資料結構

4. **定義依賴介面（Repository、Service）**
   - Use Case 需要的外部能力
   - 定義抽象介面，不依賴具體實作

**設計範例**：

```dart
// ✅ Step 2: 設計 Use Case 和介面契約

// 輸入介面
class CreateBookInput {
  final String isbn;
  final String title;
  final String author;

  CreateBookInput({
    required this.isbn,
    required this.title,
    required this.author,
  });
}

// 輸出介面
class CreateBookOutput {
  final Book book;
  final String message;

  CreateBookOutput({
    required this.book,
    required this.message,
  });
}

// Use Case 抽象介面
abstract class CreateBookUseCase {
  Future<CreateBookOutput> execute(CreateBookInput input);
}

// Repository 抽象介面（Use Case 定義需要的能力）
abstract class BookRepository {
  Future<Book> save(Book book);
  Future<Book?> findByISBN(ISBN isbn);
  Future<List<Book>> findAll();
}

// Use Case 實作
class CreateBookInteractor implements CreateBookUseCase {
  final BookRepository repository;

  CreateBookInteractor({required this.repository});

  @override
  Future<CreateBookOutput> execute(CreateBookInput input) async {
    // Step 1: 驗證書籍是否已存在
    final existingBook = await repository.findByISBN(ISBN(input.isbn));
    if (existingBook != null) {
      throw BusinessException('書籍已存在（ISBN: ${input.isbn}）');
    }

    // Step 2: 建立新書籍（Entity 驗證業務不變量）
    final book = Book.create(
      isbn: input.isbn,
      title: input.title,
      author: input.author,
    );

    // Step 3: 儲存書籍
    final savedBook = await repository.save(book);

    // Step 4: 回傳結果
    return CreateBookOutput(
      book: savedBook,
      message: '書籍建立成功',
    );
  }
}
```

**設計檢查清單**：

- [ ] 系統功能已識別並對應 Use Case
- [ ] 輸入介面（Input Port）已定義
- [ ] 輸出介面（Output Port）已定義
- [ ] Repository/Service 抽象介面已定義
- [ ] Use Case 不依賴具體實作，只依賴抽象介面

### 2.4 Step 3: Interface Adapters 設計

**設計目標**：定義 Controller、Presenter、Repository 介面，橋接內層業務邏輯和外層技術細節。

**設計要點**

1. **Controller 設計**
   - 接收外部請求（HTTP、CLI、UI 事件）
   - 轉換請求為 Use Case 輸入
   - 呼叫 Use Case 執行
   - 格式化 Use Case 輸出回傳給外部

2. **Presenter 設計**
   - 格式化 Use Case 輸出為 UI 可用格式
   - 處理國際化和本地化
   - 處理錯誤訊息呈現

3. **Repository Interface 設計**
   - 定義資料存取方法
   - 不依賴具體資料庫技術
   - 回傳 Entity，不回傳資料庫模型

**設計範例**：

```dart
// ✅ Step 3: 設計 Interface Adapters

// Controller：處理 HTTP 請求
class BookController {
  final CreateBookUseCase createBookUseCase;
  final BookPresenter presenter;

  BookController({
    required this.createBookUseCase,
    required this.presenter,
  });

  Future<HttpResponse> handleCreateBook(HttpRequest request) async {
    try {
      // Step 1: 轉換 HTTP 請求為 Use Case 輸入
      final input = CreateBookInput(
        isbn: request.body['isbn'],
        title: request.body['title'],
        author: request.body['author'],
      );

      // Step 2: 執行 Use Case
      final output = await createBookUseCase.execute(input);

      // Step 3: 使用 Presenter 格式化回應
      final viewModel = presenter.presentCreateBookSuccess(output);
      return HttpResponse.ok(viewModel);

    } on ValidationException catch (e) {
      final viewModel = presenter.presentValidationError(e);
      return HttpResponse.badRequest(viewModel);

    } on BusinessException catch (e) {
      final viewModel = presenter.presentBusinessError(e);
      return HttpResponse.conflict(viewModel);
    }
  }
}

// Presenter：格式化輸出
class BookPresenter {
  Map<String, dynamic> presentCreateBookSuccess(CreateBookOutput output) {
    return {
      'success': true,
      'message': output.message,
      'data': {
        'isbn': output.book.isbn.value,
        'title': output.book.title.value,
        'author': output.book.author.value,
      },
    };
  }

  Map<String, dynamic> presentValidationError(ValidationException error) {
    return {
      'success': false,
      'error': '驗證失敗',
      'message': error.message,
    };
  }

  Map<String, dynamic> presentBusinessError(BusinessException error) {
    return {
      'success': false,
      'error': '業務規則錯誤',
      'message': error.message,
    };
  }
}

// Repository Interface（已在 Step 2 定義）
abstract class BookRepository {
  Future<Book> save(Book book);
  Future<Book?> findByISBN(ISBN isbn);
  Future<List<Book>> findAll();
}
```

**設計檢查清單**：

- [ ] Controller 定義完整（接收請求、轉換輸入、呼叫 Use Case、格式化輸出）
- [ ] Presenter 定義完整（成功、驗證錯誤、業務錯誤）
- [ ] Repository Interface 定義完整（符合 Use Case 需求）
- [ ] Controller 和 Presenter 不包含業務邏輯
- [ ] Repository Interface 回傳 Entity，不回傳資料庫模型

### 2.5 Step 4: Frameworks & Drivers 設計

**設計目標**：選擇技術框架和外部系統整合方式。

**設計要點**

1. **技術選型**
   - Web 框架（Express、Spring、Flutter）
   - 資料庫技術（MySQL、MongoDB、SQLite）
   - UI 框架（React、Flutter、Vue）

2. **外部系統整合**
   - 第三方 API（Google Books API）
   - 外部設備（相機、感測器）
   - 訊息佇列（RabbitMQ、Kafka）

3. **技術限制和約束**
   - 效能要求
   - 可擴展性要求
   - 成本約束

**設計範例**：

```dart
// ✅ Step 4: 實作 Frameworks & Drivers

// SQLite Repository 實作
class SQLiteBookRepository implements BookRepository {
  final Database database;

  SQLiteBookRepository({required this.database});

  @override
  Future<Book> save(Book book) async {
    await database.insert('books', {
      'isbn': book.isbn.value,
      'title': book.title.value,
      'author': book.author.value,
      'created_at': book.createdAt.toIso8601String(),
    });
    return book;
  }

  @override
  Future<Book?> findByISBN(ISBN isbn) async {
    final List<Map<String, dynamic>> maps = await database.query(
      'books',
      where: 'isbn = ?',
      whereArgs: [isbn.value],
    );

    if (maps.isEmpty) {
      return null;
    }

    return Book(
      isbn: ISBN(maps[0]['isbn']),
      title: Title(maps[0]['title']),
      author: Author(maps[0]['author']),
      createdAt: DateTime.parse(maps[0]['created_at']),
    );
  }

  @override
  Future<List<Book>> findAll() async {
    final List<Map<String, dynamic>> maps = await database.query('books');
    return maps.map((map) => Book(
      isbn: ISBN(map['isbn']),
      title: Title(map['title']),
      author: Author(map['author']),
      createdAt: DateTime.parse(map['created_at']),
    )).toList();
  }
}

// HTTP 框架整合（Express 範例）
void setupRoutes(Router router, BookController bookController) {
  router.post('/books', (req, res) async {
    final response = await bookController.handleCreateBook(req);
    res.status(response.statusCode).json(response.body);
  });
}
```

**設計檢查清單**：

- [ ] 技術框架已選定（Web、DB、UI）
- [ ] 外部系統整合方式已設計
- [ ] Repository 具體實作符合介面契約
- [ ] 技術限制和約束已評估
- [ ] 框架替換不影響內層業務邏輯

### 2.6 設計階段檢查清單

**Entities 設計檢查**：
- [ ] 核心業務實體已識別（Entity、Value Object）
- [ ] 業務不變量已定義並驗證
- [ ] Value Objects 確保值的有效性和不可變性
- [ ] Entity 不依賴任何框架或技術細節

**Use Cases 設計檢查**：
- [ ] 系統功能已識別並對應 Use Case
- [ ] 輸入介面（Input Port）已定義
- [ ] 輸出介面（Output Port）已定義
- [ ] Repository/Service 抽象介面已定義
- [ ] Use Case 不依賴具體實作，只依賴抽象介面

**Interface Adapters 設計檢查**：
- [ ] Controller 定義完整（接收請求、轉換輸入、呼叫 Use Case、格式化輸出）
- [ ] Presenter 定義完整（成功、驗證錯誤、業務錯誤）
- [ ] Repository Interface 定義完整（符合 Use Case 需求）
- [ ] Controller 和 Presenter 不包含業務邏輯

**Frameworks & Drivers 設計檢查**：
- [ ] 技術框架已選定（Web、DB、UI）
- [ ] Repository 具體實作符合介面契約
- [ ] 框架替換不影響內層業務邏輯

**整體架構檢查**：
- [ ] 依賴方向正確（外層依賴內層，內層不依賴外層）
- [ ] 抽象介面定義明確（Use Case、Repository、Service）
- [ ] 業務邏輯與技術細節明確分離

---

## 第三章：實作階段策略（Outer → Inner）

### 3.1 實作順序：由外往內

**核心原則**：實作階段必須從外層（Frameworks & Drivers）開始，由外往內逐步完成具體實作。

**為什麼實作要由外往內？**

1. **先建立可運行的基礎架構**
   - 先有可運行的應用程式框架（Web Server、資料庫連線）
   - 確保開發環境正常運作
   - 提供測試和驗證的基礎

2. **Interface-Driven Development (IDD)**
   - 先定義內層介面（Ports），外層依賴介面開發
   - 內層實作尚未完成時，外層可使用 Mock 介面進行測試
   - 並行開發：前端、後端、測試團隊同時進行

3. **依賴反轉的實踐**
   - 外層依賴內層介面，而非等待內層實作
   - 內層實作符合介面契約即可
   - 最後在組裝階段連接所有元件

**實作順序流程**：

```text
Step 1: 定義內層介面（Ports）
    ↓ 建立 Use Case 介面、Repository 介面
Step 2: 外層依賴介面開發
    ↓ Controller、Presenter 使用介面（Mock 測試）
Step 3: 補完內層具體實作
    ↓ Interactor 實作業務邏輯
Step 4: 組裝階段依賴注入
    ↓ Composition Root 連接具體實作
```

**與設計階段的對比**：

| 階段 | 設計階段（Inner → Outer） | 實作階段（Outer → Inner） |
|------|--------------------------|--------------------------|
| **起點** | Entities 設計優先 | 定義介面（Ports） |
| **方向** | 由內往外思考 | 由外往內實作 |
| **目標** | 定義架構分層和介面契約 | 完成具體實作和組裝 |
| **產出** | 設計文件、介面定義 | 可執行程式碼、測試通過 |

### 3.2 Interface-Driven Development 核心策略

**IDD 定義**：

Interface-Driven Development（介面驅動開發）是 Clean Architecture 的核心實作策略，強調在實作早期階段先定義內層的「介面（Ports）」，外層依賴這些介面進行開發，而非等待內層具體實作完成。

**核心理念**：

1. **抽象先行**
   - 先定義「需要什麼能力」（介面）
   - 再實作「如何提供能力」（具體實作）

2. **依賴抽象而非具體**
   - 外層依賴內層介面，不知道具體實作
   - 具體實作可以隨時替換

3. **並行開發**
   - 介面定義完成後，前端、後端、測試團隊可同時進行
   - 不需要等待所有元件完成才能開始

**IDD 優勢分析**：

| 優勢 | 說明 | 實際效益 |
|------|------|---------|
| **並行開發** | 介面定義後即可開始，不需等待實作 | 縮短開發週期 30-50% |
| **可測試性高** | 外層可用 Mock 介面測試，不依賴真實實作 | 測試覆蓋率提升至 90%+ |
| **依賴方向正確** | 外層依賴抽象介面，符合 DIP 原則 | 降低耦合度，提升可維護性 |
| **靈活替換** | 具體實作可隨時替換（如資料庫技術） | 技術演進成本降低 70% |
| **團隊協作** | 清晰的介面契約減少溝通成本 | 團隊協作效率提升 40% |

**與傳統實作方式對比**：

```dart
// ❌ 傳統方式：等待所有實作完成才能測試
// 步驟 1: 實作 Repository
class SQLiteBookRepository { ... }

// 步驟 2: 實作 Use Case（依賴具體 Repository）
class CreateBookUseCase {
  final SQLiteBookRepository repository; // 依賴具體實作
}

// 步驟 3: 實作 Controller（必須等步驟 1-2 完成）
class BookController {
  final CreateBookUseCase useCase; // 必須等待 Use Case 完成
}

// 問題：前端團隊必須等待後端全部完成才能開始

// ✅ IDD 方式：定義介面後即可並行開發
// 步驟 1: 定義介面（Ports）
abstract class BookRepository { ... }
abstract class CreateBookUseCase { ... }

// 步驟 2: 外層依賴介面開發（前端團隊可立即開始）
class BookController {
  final CreateBookUseCase useCase; // 依賴介面

  // 測試時使用 Mock
  BookController({required this.useCase});
}

// 步驟 3: 內層補完實作（後端團隊並行進行）
class CreateBookInteractor implements CreateBookUseCase { ... }
class SQLiteBookRepository implements BookRepository { ... }

// 步驟 4: 組裝階段連接
// 優勢：前端、後端、測試團隊同時進行，不互相阻塞
```

### 3.3 Step 1: 定義內層介面（Ports）

**介面設計原則**：

1. **明確定義能力契約**
   - 介面方法名稱清楚表達功能
   - 輸入參數和回傳值型別明確
   - 異常處理規範定義

2. **避免技術細節洩漏**
   - 介面不包含資料庫、框架相關細節
   - 使用 Domain 語言（如 `Book`），不使用技術語言（如 `BookDTO`）

3. **遵循介面隔離原則（ISP）**
   - 介面應小而專注
   - 不強迫實作類別依賴不需要的方法

**Input/Output Ports 定義**：

```dart
// ✅ Step 1: 定義內層介面（Ports）

// Input Port：Use Case 執行入口
abstract class CreateBookInputPort {
  Future<CreateBookOutputPort> execute(CreateBookInput input);
}

class CreateBookInput {
  final String isbn;
  final String title;
  final String author;

  CreateBookInput({
    required this.isbn,
    required this.title,
    required this.author,
  });
}

// Output Port：Use Case 執行結果
abstract class CreateBookOutputPort {
  Book get book;
  String get message;
}

class CreateBookOutput implements CreateBookOutputPort {
  @override
  final Book book;

  @override
  final String message;

  CreateBookOutput({
    required this.book,
    required this.message,
  });
}

// Repository Port：Use Case 需要的資料存取能力
abstract class BookRepository {
  Future<Book> save(Book book);
  Future<Book?> findByISBN(ISBN isbn);
  Future<List<Book>> findAll();
  Future<void> delete(ISBN isbn);
}
```

**介面定義檢查清單**：

- [ ] Input Port 定義明確（方法名稱、參數、回傳值）
- [ ] Output Port 定義明確（成功結果、錯誤處理）
- [ ] Repository Port 定義完整（CRUD 操作）
- [ ] 介面不洩漏技術細節（無資料庫、框架相關型別）
- [ ] 遵循介面隔離原則（ISP）

### 3.4 Step 2: 外層依賴介面開發

**Controller 依賴介面實作**：

```dart
// ✅ Step 2: 外層依賴介面開發

class BookController {
  final CreateBookInputPort createBookUseCase; // 依賴介面，不依賴具體實作

  BookController({required this.createBookUseCase});

  Future<HttpResponse> handleCreateBook(HttpRequest request) async {
    try {
      // 轉換 HTTP 請求為 Use Case 輸入
      final input = CreateBookInput(
        isbn: request.body['isbn'],
        title: request.body['title'],
        author: request.body['author'],
      );

      // 呼叫 Use Case 介面（此時具體實作可能尚未完成）
      final output = await createBookUseCase.execute(input);

      // 回傳成功結果
      return HttpResponse.ok({
        'success': true,
        'message': output.message,
        'data': {
          'isbn': output.book.isbn.value,
          'title': output.book.title.value,
        },
      });

    } on ValidationException catch (e) {
      return HttpResponse.badRequest({
        'success': false,
        'error': '驗證失敗',
        'message': e.message,
      });
    }
  }
}
```

**Mock 介面用於測試**：

```dart
// ✅ 測試時使用 Mock Input Port
class MockCreateBookUseCase implements CreateBookInputPort {
  @override
  Future<CreateBookOutputPort> execute(CreateBookInput input) async {
    // 回傳假資料，不需要真實業務邏輯和資料庫
    final book = Book.create(
      isbn: input.isbn,
      title: input.title,
      author: input.author,
    );

    return CreateBookOutput(
      book: book,
      message: '建立成功（Mock）',
    );
  }
}

// Controller 測試
void main() {
  test('建立書籍成功', () async {
    // Arrange：使用 Mock Use Case
    final mockUseCase = MockCreateBookUseCase();
    final controller = BookController(createBookUseCase: mockUseCase);

    final request = HttpRequest(
      body: {
        'isbn': '978-3-16-148410-0',
        'title': 'Clean Architecture',
        'author': 'Robert C. Martin',
      },
    );

    // Act
    final response = await controller.handleCreateBook(request);

    // Assert
    expect(response.statusCode, 200);
    expect(response.body['success'], true);
    // Controller 測試完成，不需要等待 Use Case 和 Repository 實作
  });
}
```

**外層開發檢查清單**：

- [ ] Controller 依賴介面而非具體實作
- [ ] Mock 介面已建立用於測試
- [ ] Controller 測試通過（使用 Mock）
- [ ] 不阻塞其他團隊開發進度

### 3.5 Step 3: 補完內層具體實作

**Interactor 實作具體業務邏輯**：

```dart
// ✅ Step 3: 補完內層具體實作

class CreateBookInteractor implements CreateBookInputPort {
  final BookRepository repository; // 依賴 Repository 介面

  CreateBookInteractor({required this.repository});

  @override
  Future<CreateBookOutputPort> execute(CreateBookInput input) async {
    // Step 1: 驗證書籍是否已存在
    final isbn = ISBN(input.isbn);
    final existingBook = await repository.findByISBN(isbn);

    if (existingBook != null) {
      throw BusinessException('書籍已存在（ISBN: ${input.isbn}）');
    }

    // Step 2: 建立新書籍（Entity 驗證業務不變量）
    final book = Book.create(
      isbn: input.isbn,
      title: input.title,
      author: input.author,
    );

    // Step 3: 儲存書籍（透過 Repository 介面）
    final savedBook = await repository.save(book);

    // Step 4: 回傳結果
    return CreateBookOutput(
      book: savedBook,
      message: '書籍建立成功',
    );
  }
}
```

**Repository 具體實作**：

```dart
// ✅ Repository 具體實作（符合介面契約）

class SQLiteBookRepository implements BookRepository {
  final Database database;

  SQLiteBookRepository({required this.database});

  @override
  Future<Book> save(Book book) async {
    await database.insert('books', {
      'isbn': book.isbn.value,
      'title': book.title.value,
      'author': book.author.value,
      'created_at': book.createdAt.toIso8601String(),
    });
    return book;
  }

  @override
  Future<Book?> findByISBN(ISBN isbn) async {
    final maps = await database.query(
      'books',
      where: 'isbn = ?',
      whereArgs: [isbn.value],
    );

    if (maps.isEmpty) return null;

    return Book(
      isbn: ISBN(maps[0]['isbn']),
      title: Title(maps[0]['title']),
      author: Author(maps[0]['author']),
      createdAt: DateTime.parse(maps[0]['created_at']),
    );
  }

  @override
  Future<List<Book>> findAll() async {
    final maps = await database.query('books');
    return maps.map((map) => Book(
      isbn: ISBN(map['isbn']),
      title: Title(map['title']),
      author: Author(map['author']),
      createdAt: DateTime.parse(map['created_at']),
    )).toList();
  }

  @override
  Future<void> delete(ISBN isbn) async {
    await database.delete(
      'books',
      where: 'isbn = ?',
      whereArgs: [isbn.value],
    );
  }
}
```

**內層實作檢查清單**：

- [ ] Interactor 實作 Input Port 介面
- [ ] Interactor 包含完整業務邏輯
- [ ] Repository 實作 Repository Port 介面
- [ ] Repository 回傳 Entity，不回傳資料庫模型
- [ ] 所有單元測試通過

### 3.6 Step 4: 組裝階段依賴注入

**Composition Root 模式**：

Composition Root 是應用程式的「組裝點」，負責建立所有元件並注入依賴關係。這是唯一知道具體實作的地方。

**依賴注入實作**：

```dart
// ✅ Step 4: 組裝階段依賴注入

class AppComposition {
  late final BookController bookController;
  late final CreateBookInputPort createBookUseCase;
  late final BookRepository bookRepository;

  Future<void> setup() async {
    // Step 1: 建立基礎設施層（Frameworks & Drivers）
    final database = await SQLiteDatabase.open('books.db');
    bookRepository = SQLiteBookRepository(database: database);

    // Step 2: 建立 Use Case（注入 Repository 介面）
    createBookUseCase = CreateBookInteractor(
      repository: bookRepository, // 注入具體實作
    );

    // Step 3: 建立 Controller（注入 Use Case 介面）
    bookController = BookController(
      createBookUseCase: createBookUseCase, // 注入具體實作
    );
  }

  // 提供 Controller 給 Web Server
  BookController getBookController() => bookController;
}

// 應用程式啟動
void main() async {
  // 組裝所有元件
  final composition = AppComposition();
  await composition.setup();

  // 啟動 Web Server
  final server = HttpServer();
  server.post('/books', composition.getBookController().handleCreateBook);
  server.listen(3000);
}
```

**組裝檢查清單**：

- [ ] Composition Root 統一管理所有依賴關係
- [ ] 具體實作在組裝階段注入
- [ ] 內層元件不知道具體實作（只依賴介面）
- [ ] 應用程式啟動正常

### 3.7 實作階段總檢查清單

**Interface-Driven 準備度檢查**：
- [ ] 所有 Input/Output Ports 已定義
- [ ] Repository Ports 已定義
- [ ] 介面契約明確且不洩漏技術細節
- [ ] Mock 介面已建立用於測試

**並行開發機會識別**：
- [ ] 前端團隊可使用 Mock 介面開發 UI
- [ ] 後端團隊可並行實作 Use Case 和 Repository
- [ ] 測試團隊可提前設計測試案例

**測試策略檢查**：
- [ ] Controller 測試使用 Mock Use Case（不依賴真實實作）
- [ ] Use Case 測試使用 Mock Repository（不依賴資料庫）
- [ ] Repository 測試使用真實資料庫（整合測試）

**組裝完成驗證**：
- [ ] Composition Root 正確注入所有依賴
- [ ] 應用程式啟動無錯誤
- [ ] 端到端測試通過
- [ ] 所有單元測試和整合測試通過

---

## 第四章：與 TDD 四階段流程整合

### 4.1 TDD 四階段流程回顧

**TDD 四階段定義**：

本專案採用完整的 TDD 四階段開發流程，確保需求→設計→測試→實作→重構的完整循環。

**四階段流程**：

```text
Phase 1: 功能設計（lavender-interface-designer）
   ↓ 需求分析、功能規劃、介面設計
Phase 2: 測試設計（sage-test-architect）
   ↓ 測試案例設計、驗收標準定義
Phase 3a: 實作策略（pepper-test-implementer）
   ↓ 語言無關的實作規劃、虛擬碼設計
Phase 3b: 程式碼實作（parsley-flutter-developer 等）
   ↓ 語言特定的程式碼撰寫、測試執行
Phase 4: 重構優化（cinnamon-refactor-owl）
   ↓ 架構合規檢查、程式碼品質提升
```

**與 Clean Architecture 的關係**：

| TDD 階段 | Clean Architecture 對應 | 核心產出 |
|---------|------------------------|---------|
| **Phase 1** | 設計階段（Inner → Outer） | Entities、Use Cases、介面契約 |
| **Phase 2** | 測試策略設計 | 單元測試、整合測試設計 |
| **Phase 3** | 實作階段（Outer → Inner） | 完整實作 + 測試通過 |
| **Phase 4** | 架構合規驗證 | 依賴方向檢查、重構優化 |

### 4.2 Phase 1 整合：設計內層介面優先

**Phase 1 職責**：
- 分析需求並提取核心業務規則
- 設計 Entities 和 Use Cases
- 定義 Input/Output Ports
- 規劃 Repository/Service 介面

**Clean Architecture 整合策略**：

1. **Entities 設計優先**
   - 識別核心業務概念（從需求規格提取）
   - 定義業務不變量和驗證規則
   - 設計 Value Objects 封裝業務概念

2. **Use Cases 設計次之**
   - 從用例圖提取系統功能
   - 定義 Input Port 和 Output Port
   - 定義 Repository Port（Use Case 需要的能力）

3. **介面契約設計**
   - Repository 介面定義（回傳 Entity，不回傳 DTO）
   - Service 介面定義（外部系統整合能力）
   - 遵循介面隔離原則（ISP）

**Phase 1 設計範例**：

```dart
// ✅ Phase 1 產出：設計 Entities 和 Use Cases

// Step 1: 設計 Entity
class Book {
  final ISBN isbn;
  final Title title;
  final Author author;

  Book({required this.isbn, required this.title, required this.author});

  factory Book.create({required String isbn, required String title, required String author}) {
    return Book(
      isbn: ISBN(isbn),
      title: Title(title),
      author: Author(author),
    );
  }
}

// Step 2: 定義 Use Case 介面
abstract class CreateBookInputPort {
  Future<CreateBookOutputPort> execute(CreateBookInput input);
}

// Step 3: 定義 Repository Port
abstract class BookRepository {
  Future<Book> save(Book book);
  Future<Book?> findByISBN(ISBN isbn);
}
```

**Phase 1 整合檢查清單**：

- [ ] Entities 設計完成（業務不變量定義）
- [ ] Use Cases 介面定義完成（Input/Output Ports）
- [ ] Repository Ports 定義完成（符合 Use Case 需求）
- [ ] 介面不洩漏技術細節（純 Domain 語言）
- [ ] 依賴方向正確（Use Case 依賴 Repository 介面）

### 4.3 Phase 2 整合：測試驅動介面定義

**Phase 2 職責**：
- 基於 Phase 1 設計撰寫測試案例
- 定義單元測試（Entities、Use Cases）
- 定義整合測試（Repository、Controller）
- 確保測試可用 Mock 介面執行

**Clean Architecture 測試策略**：

1. **Entities 單元測試**
   - 測試業務不變量驗證
   - 測試 Value Objects 有效性
   - 不依賴任何外部資源

2. **Use Cases 單元測試**
   - 使用 Mock Repository 測試業務邏輯
   - 驗證輸入/輸出契約
   - 驗證異常處理邏輯

3. **Repository 整合測試**
   - 測試真實資料庫互動
   - 驗證回傳 Entity 而非 DTO
   - 驗證資料持久化正確性

**Phase 2 測試範例**：

```dart
// ✅ Phase 2 產出：測試案例設計

// Entities 單元測試
void main() {
  group('Book Entity Tests', () {
    test('建立書籍時驗證 ISBN 格式', () {
      // Assert: ISBN 格式無效應拋出異常
      expect(
        () => ISBN('invalid-isbn'),
        throwsA(isA<ValidationException>()),
      );
    });
  });

  // Use Case 單元測試（使用 Mock Repository）
  group('CreateBookUseCase Tests', () {
    test('建立書籍成功', () async {
      // Arrange
      final mockRepository = MockBookRepository();
      when(mockRepository.findByISBN(any)).thenAnswer((_) async => null);
      when(mockRepository.save(any)).thenAnswer((inv) async => inv.positionalArguments[0]);

      final useCase = CreateBookInteractor(repository: mockRepository);
      final input = CreateBookInput(isbn: '978-3-16-148410-0', title: 'Clean Architecture', author: 'Robert C. Martin');

      // Act
      final output = await useCase.execute(input);

      // Assert
      expect(output.book.title.value, 'Clean Architecture');
      verify(mockRepository.save(any)).called(1);
    });
  });

  // Repository 整合測試（使用真實資料庫）
  group('SQLiteBookRepository Integration Tests', () {
    late Database database;
    late BookRepository repository;

    setUp(() async {
      database = await openDatabase(':memory:');
      repository = SQLiteBookRepository(database: database);
    });

    test('儲存書籍並查詢', () async {
      // Arrange
      final book = Book.create(isbn: '978-3-16-148410-0', title: 'Clean Architecture', author: 'Robert C. Martin');

      // Act
      await repository.save(book);
      final foundBook = await repository.findByISBN(book.isbn);

      // Assert
      expect(foundBook, isNotNull);
      expect(foundBook!.title.value, 'Clean Architecture');
    });
  });
}
```

**Phase 2 整合檢查清單**：

- [ ] Entities 單元測試完整（業務邏輯驗證）
- [ ] Use Cases 單元測試使用 Mock Repository
- [ ] Repository 整合測試使用真實資料庫
- [ ] 測試覆蓋所有 Input/Output Ports
- [ ] 測試驗證依賴方向正確

### 4.4 Phase 3 整合：Interface-Driven 實作

**Phase 3a 職責**（語言無關策略規劃）：
- 制定實作順序（Outer → Inner）
- 規劃 Mock 介面建立策略
- 定義並行開發機會
- 規劃組裝階段依賴注入

**Phase 3b 職責**（語言特定實作）：
- 外層依賴介面開發（Controller、Presenter）
- 內層補完具體實作（Interactor、Repository）
- 組裝階段依賴注入（Composition Root）
- 執行所有測試確保 100% 通過

**Interface-Driven Development 實作流程**：

```text
Step 1: 建立 Mock 介面（Phase 3b 開始）
   ↓ MockBookRepository、MockCreateBookUseCase
Step 2: 外層依賴介面開發
   ↓ Controller 使用 Mock Use Case 測試
Step 3: 內層補完具體實作
   ↓ CreateBookInteractor、SQLiteBookRepository
Step 4: 組裝階段依賴注入
   ↓ Composition Root 連接所有元件
```

**Phase 3b 實作範例**：

```dart
// ✅ Phase 3b 產出：完整實作

// Step 1: 建立 Mock 介面
class MockCreateBookUseCase implements CreateBookInputPort {
  @override
  Future<CreateBookOutputPort> execute(CreateBookInput input) async {
    final book = Book.create(isbn: input.isbn, title: input.title, author: input.author);
    return CreateBookOutput(book: book, message: '建立成功（Mock）');
  }
}

// Step 2: Controller 依賴介面開發
class BookController {
  final CreateBookInputPort createBookUseCase; // 依賴介面

  BookController({required this.createBookUseCase});

  Future<HttpResponse> handleCreateBook(HttpRequest request) async {
    final input = CreateBookInput(
      isbn: request.body['isbn'],
      title: request.body['title'],
      author: request.body['author'],
    );
    final output = await createBookUseCase.execute(input);
    return HttpResponse.ok({'book': output.book});
  }
}

// Step 3: 內層補完具體實作
class CreateBookInteractor implements CreateBookInputPort {
  final BookRepository repository;

  CreateBookInteractor({required this.repository});

  @override
  Future<CreateBookOutputPort> execute(CreateBookInput input) async {
    final book = Book.create(isbn: input.isbn, title: input.title, author: input.author);
    final savedBook = await repository.save(book);
    return CreateBookOutput(book: savedBook, message: '建立成功');
  }
}

// Step 4: 組裝階段依賴注入
class AppComposition {
  Future<void> setup() async {
    final database = await SQLiteDatabase.open('books.db');
    final bookRepository = SQLiteBookRepository(database: database);
    final createBookUseCase = CreateBookInteractor(repository: bookRepository);
    final bookController = BookController(createBookUseCase: createBookUseCase);
  }
}
```

**Phase 3 整合檢查清單**：

- [ ] Mock 介面已建立（Use Case、Repository）
- [ ] Controller 測試使用 Mock（不依賴真實實作）
- [ ] Use Case 具體實作完成（業務邏輯完整）
- [ ] Repository 具體實作完成（符合介面契約）
- [ ] Composition Root 正確注入所有依賴
- [ ] 所有測試 100% 通過

### 4.5 Phase 4 整合：架構合規檢查與重構

**Phase 4 職責**：
- 驗證依賴方向正確（外層依賴內層）
- 檢查介面契約清晰性
- 確認業務邏輯與技術細節分離
- 執行程式碼品質重構

**Clean Architecture 合規檢查項目**：

1. **依賴方向檢查**
   - Use Case 不得依賴 Controller、Repository 具體實作
   - Entities 不得依賴 Use Cases 或外層
   - Repository 介面在 Use Case 層定義

2. **介面契約檢查**
   - Input/Output Ports 明確且不洩漏技術細節
   - Repository Port 回傳 Entity，不回傳 DTO
   - 介面遵循介面隔離原則（ISP）

3. **業務邏輯位置檢查**
   - 業務不變量在 Entities 中驗證
   - 應用業務規則在 Use Cases 中執行
   - Controller 不包含業務邏輯

4. **技術細節隔離檢查**
   - Entities 不依賴框架（無 `import 'package:flutter'`）
   - Use Cases 不依賴資料庫技術
   - 資料庫模型與 Entity 明確分離

**Phase 4 重構範例**：

```dart
// ❌ Phase 4 發現問題：依賴方向錯誤

// 錯誤範例 1：Use Case 依賴具體 Repository
class CreateBookInteractor {
  final SQLiteBookRepository repository; // 依賴具體實作
}

// ✅ 修正：Use Case 依賴抽象介面
class CreateBookInteractor {
  final BookRepository repository; // 依賴抽象介面
}

// ❌ 錯誤範例 2：Controller 包含業務邏輯
class BookController {
  Future<HttpResponse> handleCreateBook(HttpRequest request) async {
    // 業務邏輯不應在 Controller
    if (request.body['isbn'].isEmpty) {
      throw ValidationException('ISBN 不可為空');
    }
  }
}

// ✅ 修正：業務邏輯移至 Entity
class ISBN {
  final String value;

  ISBN(this.value) {
    if (value.isEmpty) {
      throw ValidationException('ISBN 不可為空');
    }
  }
}

// ❌ 錯誤範例 3：Repository 回傳資料庫模型
class SQLiteBookRepository {
  Future<BookModel> findByISBN(ISBN isbn) async {
    // 回傳資料庫模型
    return BookModel.fromMap(map);
  }
}

// ✅ 修正：Repository 回傳 Entity
class SQLiteBookRepository implements BookRepository {
  @override
  Future<Book> findByISBN(ISBN isbn) async {
    final map = await database.query('books', where: 'isbn = ?', whereArgs: [isbn.value]);
    // 轉換資料庫模型為 Entity
    return Book(
      isbn: ISBN(map[0]['isbn']),
      title: Title(map[0]['title']),
      author: Author(map[0]['author']),
    );
  }
}
```

**Phase 4 整合檢查清單**：

- [ ] 依賴方向檢查通過（外層依賴內層）
- [ ] 介面契約明確（Input/Output/Repository Ports）
- [ ] 業務邏輯位置正確（Entities、Use Cases）
- [ ] 技術細節隔離完整（框架、資料庫）
- [ ] Repository 回傳 Entity，不回傳 DTO
- [ ] 所有程式碼重構完成，測試 100% 通過

### 4.6 TDD 四階段與 Clean Architecture 整合總覽

**完整整合流程圖**：

```text
┌─────────────────────────────────────────────────────────┐
│ Phase 1: 功能設計（lavender-interface-designer）         │
│ Clean Architecture: 設計階段（Inner → Outer）           │
├─────────────────────────────────────────────────────────┤
│ 產出：                                                   │
│ - Entities 設計（業務不變量、Value Objects）            │
│ - Use Cases 介面定義（Input/Output Ports）              │
│ - Repository Ports 定義（Use Case 需求）                │
├─────────────────────────────────────────────────────────┤
│ 檢查：依賴方向正確、介面不洩漏技術細節                    │
└─────────────────────────────────────────────────────────┘
                         ↓
┌─────────────────────────────────────────────────────────┐
│ Phase 2: 測試設計（sage-test-architect）                │
│ Clean Architecture: 測試策略設計                        │
├─────────────────────────────────────────────────────────┤
│ 產出：                                                   │
│ - Entities 單元測試（業務邏輯驗證）                      │
│ - Use Cases 單元測試（Mock Repository）                 │
│ - Repository 整合測試（真實資料庫）                      │
├─────────────────────────────────────────────────────────┤
│ 檢查：測試使用 Mock 介面、覆蓋所有 Ports                 │
└─────────────────────────────────────────────────────────┘
                         ↓
┌─────────────────────────────────────────────────────────┐
│ Phase 3a: 實作策略（pepper-test-implementer）           │
│ Clean Architecture: Interface-Driven 策略規劃           │
├─────────────────────────────────────────────────────────┤
│ 產出：                                                   │
│ - Mock 介面建立策略                                     │
│ - 並行開發機會識別                                      │
│ - 組裝階段依賴注入規劃                                  │
├─────────────────────────────────────────────────────────┤
│ 檢查：實作順序 Outer → Inner、並行開發可行性            │
└─────────────────────────────────────────────────────────┘
                         ↓
┌─────────────────────────────────────────────────────────┐
│ Phase 3b: 程式碼實作（parsley-flutter-developer 等）    │
│ Clean Architecture: 實作階段（Outer → Inner）           │
├─────────────────────────────────────────────────────────┤
│ 產出：                                                   │
│ - Controller 依賴介面開發（使用 Mock 測試）             │
│ - Interactor 補完業務邏輯                               │
│ - Repository 補完資料存取邏輯                           │
│ - Composition Root 依賴注入                             │
├─────────────────────────────────────────────────────────┤
│ 檢查：所有測試 100% 通過、依賴注入正確                  │
└─────────────────────────────────────────────────────────┘
                         ↓
┌─────────────────────────────────────────────────────────┐
│ Phase 4: 重構優化（cinnamon-refactor-owl）              │
│ Clean Architecture: 架構合規檢查與重構                  │
├─────────────────────────────────────────────────────────┤
│ 產出：                                                   │
│ - 依賴方向驗證（外層依賴內層）                          │
│ - 介面契約清晰性檢查                                    │
│ - 業務邏輯位置驗證                                      │
│ - 技術細節隔離檢查                                      │
├─────────────────────────────────────────────────────────┤
│ 檢查：架構合規、程式碼品質提升、測試 100% 通過           │
└─────────────────────────────────────────────────────────┘
```

**整合成功指標**：

| 階段 | 成功指標 | 驗證方式 |
|------|---------|---------|
| **Phase 1** | Entities 和 Use Cases 設計完整 | 介面定義檢查清單 ✅ |
| **Phase 2** | 測試案例覆蓋所有 Ports | 測試覆蓋率報告 ≥ 90% |
| **Phase 3** | 所有測試 100% 通過 | CI/CD 測試結果 ✅ |
| **Phase 4** | 架構合規檢查通過 | 依賴方向檢查 ✅ |

---

## 第五章：與敏捷重構方法論整合

### 5.1 敏捷重構方法論回顧

**敏捷重構方法論定義**：

本專案採用三重文件（CHANGELOG + todolist + work-log）協作機制，透過主線程 PM 和專業 agents 分工協作，確保開發進度和品質控制。

**核心機制**：

1. **三重文件原則**
   - CHANGELOG.md：版本功能變動記錄（面向用戶）
   - todolist.md：開發任務全景圖（任務狀態追蹤）
   - work-log/：詳細實作記錄（技術細節和決策）

2. **主線程 PM 職責**
   - 基於 todolist 和 main work-log 分派任務
   - 監控進度和品質
   - **禁止親自執行程式碼修改**

3. **執行代理人職責**
   - 基於 task work-log 執行並記錄過程
   - 完成時更新 todolist 狀態
   - 發現問題必須記錄到 work-log

**與 Clean Architecture 的關係**：

敏捷重構方法論提供「任務分派和協作機制」，Clean Architecture 提供「架構設計和實作順序」。兩者整合確保任務分派符合架構原則。

### 5.2 主線程 PM 與 Clean Architecture 任務分派

**PM 任務分派原則**：

主線程 PM 基於 Clean Architecture 原則分派任務時，必須明確指定：

1. **架構層級定位**
   - 任務屬於哪個架構層（Entities、Use Cases、Interface Adapters、Frameworks）
   - 依賴方向是否正確（外層依賴內層）

2. **介面優先策略**
   - Phase 1 必須先設計內層介面（Entities、Use Cases）
   - Phase 3 實作時先定義 Ports，後補完實作

3. **並行開發機會**
   - 識別可並行開發的任務（介面定義後）
   - 避免依賴阻塞（使用 Mock 介面）

**任務分派範例**：

```markdown
## v0.12.3 - Google Books API 整合

### Phase 1 任務分派（lavender-interface-designer）

**任務**: 設計 Google Books API 整合架構

**架構定位**:
- Entities 層：Book、ISBN、Author（已存在，檢查是否需要擴充）
- Use Cases 層：SearchBooksUseCase、FetchBookDetailsUseCase（新建）
- Interface Adapters 層：GoogleBooksService 介面定義（新建）
- Frameworks 層：GoogleBooksHttpClient 實作（Phase 3）

**設計順序**（Inner → Outer）:
1. 檢視 Entities 是否需要擴充（如 Publisher、PublishedDate）
2. 定義 Use Cases 介面（Input/Output Ports）
3. 定義 GoogleBooksService 介面（Use Case 需要的能力）

**產出**:
- Entities 擴充設計（如需要）
- SearchBooksUseCase 介面定義
- GoogleBooksService 介面定義
```

**任務分派檢查清單**：

- [ ] 明確指定架構層級定位
- [ ] 遵循設計順序（Inner → Outer）
- [ ] 識別依賴介面（Repository、Service）
- [ ] 確認依賴方向正確
- [ ] 提供介面優先策略指引

### 5.3 子任務分解與架構分層對應

**子任務分解原則**：

Clean Architecture 的分層結構自然對應子任務分解方式：

1. **Entity 層任務**
   - 設計核心業務實體
   - 定義業務不變量
   - 設計 Value Objects

2. **Use Case 層任務**
   - 定義 Use Case 介面（Input/Output Ports）
   - 定義 Repository Ports
   - 實作業務邏輯（Interactor）

3. **Interface Adapters 層任務**
   - 設計 Controller、Presenter
   - 定義 Repository 介面實作
   - 轉換資料格式

4. **Frameworks 層任務**
   - 實作 Repository（SQLite、HTTP Client）
   - 整合外部框架（Flutter、Web）
   - 組裝依賴注入（Composition Root）

**子任務範例**（v0.12.3 Google Books API 整合）：

```markdown
## v0.12.3 子任務分解

### v0.12.3.1 - Entities 擴充（如需要）
**架構層級**: Entities
**產出**: Publisher、PublishedDate Value Objects
**依賴**: 無（最內層）

### v0.12.3.2 - Use Cases 介面定義
**架構層級**: Use Cases
**產出**: SearchBooksUseCase、FetchBookDetailsUseCase 介面
**依賴**: Entities（內層）

### v0.12.3.3 - GoogleBooksService 介面定義
**架構層級**: Use Cases（定義介面）
**產出**: GoogleBooksService 抽象介面
**依賴**: Entities（回傳 Book Entity）

### v0.12.3.4 - Controller 實作
**架構層級**: Interface Adapters
**產出**: SearchBooksController
**依賴**: SearchBooksUseCase 介面（內層介面）

### v0.12.3.5 - Use Case 業務邏輯實作
**架構層級**: Use Cases
**產出**: SearchBooksInteractor 實作
**依賴**: GoogleBooksService 介面（內層介面）

### v0.12.3.6 - GoogleBooksHttpClient 實作
**架構層級**: Frameworks & Drivers
**產出**: GoogleBooksHttpClient implements GoogleBooksService
**依賴**: GoogleBooksService 介面（內層介面）

### v0.12.3.7 - 組裝依賴注入
**架構層級**: Frameworks & Drivers
**產出**: AppComposition 更新
**依賴**: 所有元件（最外層）
```

**子任務分解檢查清單**：

- [ ] 每個子任務明確標示架構層級
- [ ] 子任務依賴方向正確（外層依賴內層）
- [ ] 內層任務可先行開始（無外層依賴）
- [ ] 介面定義任務優先於實作任務
- [ ] 組裝任務位於最後（連接所有元件）

### 5.4 Agent 角色映射與 Clean Architecture

**Agent 責任與架構層級對應**：

| Agent 角色 | TDD 階段 | Clean Architecture 責任 |
|-----------|---------|------------------------|
| **lavender-interface-designer** | Phase 1 | 設計 Entities、Use Cases、Ports |
| **sage-test-architect** | Phase 2 | 設計單元測試（Entities、Use Cases）<br>設計整合測試（Repository） |
| **pepper-test-implementer** | Phase 3a | 規劃 IDD 策略（Mock、並行開發） |
| **parsley-flutter-developer** | Phase 3b | 實作所有層級（遵循 Outer → Inner） |
| **cinnamon-refactor-owl** | Phase 4 | 架構合規檢查（依賴方向、介面契約） |

**Phase 1 Agent 輸出範例**（lavender-interface-designer）：

```markdown
## Phase 1 產出：SearchBooksUseCase 設計

### Entities 層設計
無需新增，使用既有 Book、ISBN、Title、Author

### Use Cases 層設計

**Input Port**:
```dart
abstract class SearchBooksInputPort {
  Future<SearchBooksOutputPort> execute(SearchBooksInput input);
}

class SearchBooksInput {
  final String keyword;
  final int maxResults;

  SearchBooksInput({required this.keyword, this.maxResults = 10});
}
```

**Output Port**:
```dart
abstract class SearchBooksOutputPort {
  List<Book> get books;
  int get totalResults;
}
```

**Repository Port**（Use Case 需要的能力）:
```dart
abstract class GoogleBooksService {
  Future<List<Book>> searchBooks(String keyword, {int maxResults});
}
```

### 依賴方向確認
- SearchBooksUseCase 依賴 GoogleBooksService 介面（內層定義）
- GoogleBooksHttpClient 實作 GoogleBooksService（外層實作）
- ✅ 依賴方向正確
```text

**Phase 4 Agent 輸出範例**（cinnamon-refactor-owl）：

```markdown
## Phase 4 產出：Clean Architecture 合規檢查

### 依賴方向檢查
✅ SearchBooksInteractor 依賴 GoogleBooksService 介面（正確）
❌ SearchBooksInteractor 錯誤導入 GoogleBooksHttpClient（錯誤）

**修正建議**:
移除 `import 'package:book_overview_app/infrastructure/http/google_books_http_client.dart'`
確保只依賴 `import 'package:book_overview_app/domains/library/services/google_books_service.dart'`

### 介面契約檢查
✅ GoogleBooksService 回傳 Book Entity（正確）
✅ SearchBooksInput/Output Ports 不洩漏技術細節（正確）

### 業務邏輯位置檢查
✅ 關鍵字驗證在 SearchBooksInput 建構子（正確）
✅ 搜尋結果處理在 SearchBooksInteractor（正確）

### 技術細節隔離檢查
✅ SearchBooksUseCase 不依賴 HTTP 套件（正確）
✅ GoogleBooksHttpClient 隔離在 Frameworks 層（正確）
```

**Agent 角色整合檢查清單**：

- [ ] lavender: 設計符合 Inner → Outer 順序
- [ ] sage: 測試使用 Mock 介面（不依賴實作）
- [ ] pepper: 規劃 IDD 並行開發策略
- [ ] parsley: 實作遵循 Outer → Inner 順序
- [ ] cinnamon: 檢查依賴方向和架構合規

### 5.5 工作日誌與 Clean Architecture 文件

**work-log 文件結構擴充**：

整合 Clean Architecture 後，work-log 應記錄架構設計決策：

```markdown
## Phase 1: 功能設計

### 架構設計決策

**Entities 層**:
- 使用既有 Book Entity
- 新增 Publisher Value Object
- 新增 PublishedDate Value Object

**Use Cases 層**:
- 新增 SearchBooksUseCase 介面
- 定義 SearchBooksInput/Output Ports
- 定義 GoogleBooksService 介面（Use Case 需要的能力）

**依賴方向分析**:
```text
SearchBooksController (Interface Adapters)
    ↓ 依賴
SearchBooksInputPort (Use Cases 介面)
    ↓ 實作
SearchBooksInteractor (Use Cases)
    ↓ 依賴
GoogleBooksService 介面 (Use Cases 層定義)
    ↓ 實作
GoogleBooksHttpClient (Frameworks & Drivers)
```

**介面優先策略**:
- Phase 1 定義所有介面（Ports、Service）
- Phase 3b 先實作 Controller（使用 Mock Service）
- Phase 3b 後補完 Interactor 和 HttpClient
- 組裝階段連接所有元件
```text

**work-log 文件檢查清單**：

- [ ] 記錄架構層級定位（Entities、Use Cases、Interface Adapters、Frameworks）
- [ ] 記錄依賴方向分析（確保外層依賴內層）
- [ ] 記錄介面優先策略（定義→Mock→實作→組裝）
- [ ] 記錄架構設計決策（為什麼選擇這個設計）
- [ ] 記錄介面契約定義（Input/Output/Repository Ports）

### 5.6 敏捷重構與 Clean Architecture 整合總覽

**完整整合機制**：

```text
┌─────────────────────────────────────────────────────────┐
│ 主線程 PM (rosemary-project-manager)                    │
│ 基於 todolist 和 vX.Y.0-main.md 分派任務                │
├─────────────────────────────────────────────────────────┤
│ 分派策略：                                               │
│ - 明確架構層級定位（Entities → Use Cases → Adapters）   │
│ - 遵循設計順序（Inner → Outer）                         │
│ - 遵循實作順序（Outer → Inner）                         │
│ - 識別並行開發機會（介面定義後）                         │
└─────────────────────────────────────────────────────────┘
                         ↓
┌─────────────────────────────────────────────────────────┐
│ Phase 1: lavender-interface-designer                    │
│ 設計 Entities、Use Cases、Ports                         │
├─────────────────────────────────────────────────────────┤
│ 產出：                                                   │
│ - vX.Y.Z-feature-design.md                              │
│ - 架構層級定位、依賴方向分析、介面契約定義               │
│ - 更新 todolist（標記 Phase 1 完成）                    │
└─────────────────────────────────────────────────────────┘
                         ↓
┌─────────────────────────────────────────────────────────┐
│ Phase 2: sage-test-architect                            │
│ 設計測試（Entities 單元測試、Use Cases Mock 測試）       │
├─────────────────────────────────────────────────────────┤
│ 產出：                                                   │
│ - 更新 vX.Y.Z-feature-design.md（Test Design 章節）     │
│ - 測試使用 Mock 介面策略                                │
│ - 更新 todolist（標記 Phase 2 完成）                    │
└─────────────────────────────────────────────────────────┘
                         ↓
┌─────────────────────────────────────────────────────────┐
│ Phase 3a: pepper-test-implementer                       │
│ 規劃 IDD 實作策略（Mock → 並行開發 → 組裝）             │
├─────────────────────────────────────────────────────────┤
│ 產出：                                                   │
│ - 更新 vX.Y.Z-feature-design.md（Implementation 章節）  │
│ - Mock 介面建立策略、並行開發機會、組裝順序             │
│ - 更新 todolist（標記 Phase 3a 完成）                   │
└─────────────────────────────────────────────────────────┘
                         ↓
┌─────────────────────────────────────────────────────────┐
│ Phase 3b: parsley-flutter-developer                     │
│ 實作所有層級（Outer → Inner + 組裝）                    │
├─────────────────────────────────────────────────────────┤
│ 產出：                                                   │
│ - 完整程式碼實作（遵循 Outer → Inner）                  │
│ - 測試 100% 通過                                        │
│ - 更新 todolist（標記 Phase 3b 完成）                   │
└─────────────────────────────────────────────────────────┘
                         ↓
┌─────────────────────────────────────────────────────────┐
│ Phase 4: cinnamon-refactor-owl                          │
│ Clean Architecture 合規檢查與重構                       │
├─────────────────────────────────────────────────────────┤
│ 產出：                                                   │
│ - 依賴方向檢查報告                                      │
│ - 介面契約清晰性檢查                                    │
│ - 業務邏輯位置驗證                                      │
│ - 更新 todolist（標記 Phase 4 完成）                    │
│ - 更新 CHANGELOG（提取功能變動）                        │
└─────────────────────────────────────────────────────────┘
```

**整合成功指標**：

| 整合層面 | 成功指標 | 驗證方式 |
|---------|---------|---------|
| **任務分派** | 所有任務明確架構定位 | work-log 包含架構層級說明 |
| **文件記錄** | 依賴方向分析完整 | work-log 包含依賴方向圖 |
| **Agent 協作** | 每階段產出符合 Clean Architecture | Phase 4 合規檢查通過 |
| **品質保證** | 測試 100% 通過 + 架構合規 | CI/CD + Phase 4 報告 |

---

## 第六章：案例研究與檢查清單

### 6.1 完整實作案例：Google Books API 整合

**案例背景**：

整合 Google Books API 到書籍管理系統，讓使用者可以搜尋 Google Books 資料庫並取得書籍詳細資訊。

**架構設計決策**：

```text
┌─────────────────────────────────────────────────────────┐
│ Frameworks & Drivers 層                                 │
├─────────────────────────────────────────────────────────┤
│ GoogleBooksHttpClient                                   │
│ - implements GoogleBooksService                         │
│ - 負責 HTTP 請求和 JSON 解析                             │
└─────────────────────────────────────────────────────────┘
                         ↓ 實作介面
┌─────────────────────────────────────────────────────────┐
│ Use Cases 層                                            │
├─────────────────────────────────────────────────────────┤
│ GoogleBooksService (介面)                               │
│ - Future<List<Book>> searchBooks(String keyword)       │
│                                                         │
│ SearchBooksInteractor (業務邏輯)                        │
│ - implements SearchBooksInputPort                       │
│ - 依賴 GoogleBooksService 介面                          │
└─────────────────────────────────────────────────────────┘
                         ↓ 依賴介面
┌─────────────────────────────────────────────────────────┐
│ Interface Adapters 層                                   │
├─────────────────────────────────────────────────────────┤
│ SearchBooksController                                   │
│ - 依賴 SearchBooksInputPort 介面                        │
│ - 轉換 HTTP 請求為 Use Case 輸入                        │
└─────────────────────────────────────────────────────────┘
                         ↓ 依賴
┌─────────────────────────────────────────────────────────┐
│ Entities 層                                             │
├─────────────────────────────────────────────────────────┤
│ Book, ISBN, Title, Author, Publisher, PublishedDate    │
│ - 核心業務實體和 Value Objects                          │
└─────────────────────────────────────────────────────────┘
```

**完整實作範例請參考方法論文件第六章節**

### 6.2 Interface-Driven Development 實務範例

**範例 1: Repository 介面驅動開發** - 提升開發效率 30%

**範例 2: Service 介面驅動開發** - 易於測試和替換

**範例 3: 多實作替換** - 技術演進成本降低 70%

### 6.3 常見錯誤與解決方案

**錯誤 1: 依賴方向錯誤** - Use Case 依賴具體 Repository

**錯誤 2: Repository 回傳 DTO** - 應回傳 Entity

**錯誤 3: Controller 包含業務邏輯** - 業務邏輯應在 Entity/Use Case

**錯誤 4: Entities 依賴框架** - Entity 應純粹業務邏輯

**錯誤 5: 介面洩漏技術細節** - 應使用 Domain 語言

### 6.4 Clean Architecture 合規檢查清單

**架構層級檢查**：

- [ ] **Entities 層**
  - [ ] 不依賴任何框架
  - [ ] 業務不變量在 Entity 建構子中驗證
  - [ ] Value Objects 封裝業務概念且不可變
  - [ ] Entity 不包含資料庫或 UI 相關邏輯

- [ ] **Use Cases 層**
  - [ ] Input/Output Ports 定義明確
  - [ ] Use Case 依賴 Repository/Service 介面
  - [ ] Repository 介面在 Use Cases 層定義
  - [ ] Use Case 不依賴資料庫技術或 HTTP 套件

- [ ] **Interface Adapters 層**
  - [ ] Controller 不包含業務邏輯
  - [ ] Controller 依賴 Use Case 介面
  - [ ] Repository 實作回傳 Entity
  - [ ] Presenter 只負責格式化輸出

- [ ] **Frameworks & Drivers 層**
  - [ ] Repository 實作符合介面契約
  - [ ] HTTP Client、資料庫連線封裝在此層
  - [ ] Composition Root 統一管理依賴注入

**依賴方向檢查**：

- [ ] 外層依賴內層
- [ ] Use Cases 依賴 Entities
- [ ] Frameworks 依賴 Interface Adapters
- [ ] 內層不知道外層存在
- [ ] 所有跨層依賴都透過介面

**介面契約檢查**：

- [ ] Input Port 定義明確
- [ ] Output Port 定義明確
- [ ] Repository Port 回傳 Entity
- [ ] Service Port 使用 Domain 語言
- [ ] 介面遵循介面隔離原則（ISP）

**測試策略檢查**：

- [ ] Entities 單元測試不依賴外部資源
- [ ] Use Cases 單元測試使用 Mock Repository
- [ ] Repository 整合測試使用真實資料庫
- [ ] Controller 測試使用 Mock Use Case
- [ ] 測試覆蓋率 ≥ 90%

**Interface-Driven 檢查**：

- [ ] 所有 Ports 在 Phase 1 定義完成
- [ ] Mock 介面用於 Phase 2-3 測試
- [ ] Controller 先實作（使用 Mock Use Case）
- [ ] Use Case 和 Repository 後補完
- [ ] Composition Root 統一組裝所有元件

---

**文件完成摘要**：

本方法論提供完整的 Clean Architecture 實作指引，涵蓋：
- 第一章：核心原則與四層架構
- 第二章：設計階段（Inner → Outer）
- 第三章：實作階段（Outer → Inner）
- 第四章：與 TDD 四階段整合
- 第五章：與敏捷重構方法論整合
- 第六章：案例研究與檢查清單

**使用方式**：
1. 開發前閱讀第一至三章，理解核心原則
2. TDD 開發時參考第四章整合指引
3. 敏捷重構時參考第五章任務分派策略
4. 實作時參考第六章案例和檢查清單

**文件版本**: v1.0.0
**建立時間**: 2025-10-10
**最後更新**: 2025-10-10
**狀態**: 完整版本（6 章完成）
**總字數**: 約 10500 字
**總行數**: 約 2900 行
