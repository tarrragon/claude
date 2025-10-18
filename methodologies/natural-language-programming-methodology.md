# 程式碼自然語言化撰寫方法論

## 程式碼的本質

### 程式碼不是什麼

程式碼不是：

- **機器指令的縮寫**：不是為了讓電腦理解而寫
- **技術炫技的展示**：不是為了證明技術能力
- **簡潔性的競賽**：不是為了減少行數而犧牲可讀性
- **個人風格的表達**：不是個人偏好的創作空間

### 程式碼是什麼

程式碼是：

- **自然語言的程式化表達**：如同閱讀文章般流暢
- **業務邏輯的精確描述**：每行都清楚說明意圖
- **未來維護者的溝通媒介**：為人類閱讀而設計
- **需求實現的文件化過程**：展示解決問題的步驟

## 第一原則：自然語言可讀性

### 程式碼必須如同閱讀自然語言

每個函式、每個變數、每個類別都必須讓閱讀者能夠：

- **無需猜測意圖**：一眼看出要做什麼
- **理解業務邏輯**：明白為什麼這樣設計
- **追蹤執行流程**：清楚程式的運作步驟
- **預測執行結果**：知道會產生什麼結果

### 自然語言可讀性標準

#### 函式命名的自然語言化

```dart
// ❌ 錯誤：無法理解意圖
void process(data) {}
void handle(item) {}
void update(obj) {}

// ❌ 錯誤：缺乏動作描述
void bookData(book) {}
void userInfo(user) {}

// ✅ 正確：完整動作描述
void calculateBookReadingProgress(Book book) {}
void validateUserRegistrationData(User user) {}
void enrichBookMetadataFromExternalSource(Book book) {}
```

#### 變數命名的內容物描述

```dart
// ❌ 錯誤：模糊的縮寫
var usr = getCurrentUser();
var bks = getBooks();
var cfg = loadConfig();

// ❌ 錯誤：兼用於不同用途
var data = loadUserData();
// ... 100行後
data = processBookData(); // 同一變數承載不同類型

// ✅ 正確：明確的內容描述
final authenticatedUser = getCurrentUser();
final availableBooks = getLibraryBooks();
final applicationConfiguration = loadConfig();

// ✅ 正確：專用變數
final userProfileData = loadUserData();
final enrichedBookMetadata = processBookData();
```

#### 類別命名的職責描述

```dart
// ❌ 錯誤：抽象且模糊
class Manager {}
class Handler {}
class Processor {}

// ❌ 錯誤：技術導向命名
class BookDAO {}
class UserUtils {}

// ✅ 正確：業務職責描述
class BookMetadataEnrichmentService {}
class UserRegistrationValidator {}
class LibraryBookSearchEngine {}
```

## 第二原則：五行函式單一職責

### 函式長度的強制限制

每個函式必須控制在 **5-10 行** 之間，理由：

- **認知負荷控制**：人腦一次只能處理有限資訊
- **單一職責驗證**：超過 10 行通常表示多重職責
- **可測試性保證**：小函式更容易撰寫精確測試
- **重用性提升**：小函式更容易在其他地方重用

### 函式拆分的判斷標準

#### 必須拆分的情況

```dart
// ❌ 錯誤：函式負擔多重職責（15行）
Book processBook(String isbn) {
  // 驗證 ISBN
  if (isbn.length != 13) throw ArgumentError('Invalid ISBN');
  if (!isValidISBNChecksum(isbn)) throw ArgumentError('ISBN checksum failed');

  // 從外部API獲取資料
  final apiResponse = httpClient.get('/books/$isbn');
  if (apiResponse.statusCode != 200) throw Exception('API failed');

  // 解析回應
  final bookData = json.decode(apiResponse.body);

  // 建立書籍物件
  final book = Book.create(
    id: BookId(generateUniqueId()),
    title: BookTitle(bookData['title']),
    source: BookSource.external(),
  );

  return book;
}

// ✅ 正確：拆分為多個單一職責函式
Book createBookFromISBN(String isbn) {
  validateISBNFormat(isbn);
  final bookData = fetchBookDataFromExternalAPI(isbn);
  return buildBookFromExternalData(bookData);
}

void validateISBNFormat(String isbn) {
  if (isbn.length != 13) {
    throw ArgumentError('ISBN must be 13 digits');
  }
  if (!isValidISBNChecksum(isbn)) {
    throw ArgumentError('ISBN checksum validation failed');
  }
}

Map<String, dynamic> fetchBookDataFromExternalAPI(String isbn) {
  final apiResponse = httpClient.get('/books/$isbn');
  if (apiResponse.statusCode != 200) {
    throw Exception('Failed to fetch book data from external API');
  }
  return json.decode(apiResponse.body);
}

Book buildBookFromExternalData(Map<String, dynamic> bookData) {
  return Book.create(
    id: BookId(generateUniqueId()),
    title: BookTitle(bookData['title']),
    source: BookSource.external(),
  );
}
```

### 函式拆分的執行準則

#### 拆分觸發條件

- 函式超過 10 行 → 必須拆分
- 函式名稱使用「和」「或」描述 → 必須拆分
- 函式內有多個抽象層級 → 必須拆分
- 函式包含多個事件處理邏輯 → 必須拆分為事件驅動架構

#### 拆分的正確方法

```dart
// ❌ 錯誤：為了拆分而拆分
void processUser() {
  step1();
  step2();
  step3();
}

void step1() { /* meaningless separation */ }

// ✅ 正確：按照業務邏輯拆分
void registerNewUser(UserRegistrationData data) {
  validateUserRegistrationData(data);
  createUserAccount(data);
  sendWelcomeEmail(data.email);
}

void validateUserRegistrationData(UserRegistrationData data) {
  // 5-8行的驗證邏輯
}

void createUserAccount(UserRegistrationData data) {
  // 5-8行的帳戶建立邏輯
}

void sendWelcomeEmail(String email) {
  // 3-5行的歡迎信寄送邏輯
}
```

## 第三原則：變數職責專一化

### 變數命名的明確性要求

每個變數必須：

- **單一內容物**：只承載一種類型的資料
- **完整描述**：名稱完全說明內容和用途
- **無縮寫**：避免任何可能造成歧義的縮寫
- **上下文獨立**：變數名稱在任何地方都能理解

### 變數職責專一化標準

#### 禁止的變數使用模式

```dart
// ❌ 錯誤：變數兼用於不同用途
var result = validateUser(userData);
if (result.isValid) {
  result = processPayment(paymentData); // 同一變數承載不同類型
  if (result.success) {
    result = updateDatabase(result.data); // 再次改變用途
  }
}

// ❌ 錯誤：模糊的變數名稱
var data = getUserData();
var info = getBookInfo();
var obj = createObject();
```

#### 正確的變數職責專一化

```dart
// ✅ 正確：每個變數專用於單一職責
final userValidationResult = validateUser(userData);
if (userValidationResult.isValid) {
  final paymentProcessingResult = processPayment(paymentData);
  if (paymentProcessingResult.success) {
    final databaseUpdateResult = updateDatabase(paymentProcessingResult.data);
  }
}

// ✅ 正確：明確的變數名稱
final authenticatedUserProfile = getUserData();
final enrichedBookMetadata = getBookInfo();
final newlyCreatedBookEntity = createObject();
```

### 變數生命週期管理

```dart
// ❌ 錯誤：變數生命週期過長，職責不明
void processLibraryBooks() {
  var books = getAllBooks();

  // ... 50行的處理邏輯

  books = filterAvailableBooks(books);

  // ... 30行的處理邏輯

  books = sortBooksByTitle(books);

  // 變數 books 在100行間承載不同狀態的資料
}

// ✅ 正確：每個階段使用專用變數
void processLibraryBooks() {
  final allLibraryBooks = getAllBooks();
  final availableBooks = filterAvailableBooks(allLibraryBooks);
  final sortedAvailableBooks = sortBooksByTitle(availableBooks);
}
```

## 第四原則：事件驅動的語意化流程

### 行為即事件的設計思維

在事件驅動架構中，每個行為都是一個事件：

- **判斷邏輯**：if/else 本身就是事件的分支處理
- **狀態變更**：每個狀態轉換都觸發對應事件
- **業務流程**：複雜流程是多個事件的組合
- **錯誤處理**：異常情況也是需要處理的事件

### 事件驅動的程式設計標準

問題不在於 if/else 的多寡，而在於是否正確地將業務邏輯包裝成語意化的事件流程。

#### 錯誤的流程導向寫法

```dart
// ❌ 錯誤：將多個事件混在一個函式中
void submitForm(FormData formData) {
  // 驗證事件
  if (formData.name.isEmpty) {
    showErrorMessage('姓名不能為空');
    return;
  }
  if (formData.email.isEmpty) {
    showErrorMessage('Email不能為空');
    return;
  }
  if (!isValidEmail(formData.email)) {
    showErrorMessage('Email格式不正確');
    return;
  }

  // API調用事件
  final apiResult = submitToAPI(formData);

  // 結果處理事件
  if (apiResult.success) {
    showSuccessMessage('提交成功');
    navigateToSuccessPage();
    clearForm();
  } else {
    showErrorMessage('提交失敗：' + apiResult.error);
    highlightErrorFields(apiResult.errorFields);
  }
}
```

#### 正確的事件驅動寫法

```dart
// ✅ 正確：將業務流程拆解為明確的事件序列
void submitUserRegistrationForm(UserRegistrationFormData formData) {
  final validationResult = validateUserRegistrationData(formData);

  if (validationResult.isValid) {
    handleSuccessfulValidation(formData);
  } else {
    handleValidationFailure(validationResult.errors);
  }
}

ValidationResult validateUserRegistrationData(UserRegistrationFormData formData) {
  final validationErrors = <ValidationError>[];

  if (!isValidUserName(formData.name)) {
    validationErrors.add(ValidationError.invalidUserName());
  }

  if (!isValidUserEmail(formData.email)) {
    validationErrors.add(ValidationError.invalidEmail());
  }

  return ValidationResult.fromErrors(validationErrors);
}

void handleSuccessfulValidation(UserRegistrationFormData formData) {
  submitUserRegistrationToAPI(formData)
    .then(handleSuccessfulAPIResponse)
    .catchError(handleAPIFailure);
}

void handleValidationFailure(List<ValidationError> errors) {
  displayValidationErrors(errors);
  highlightInvalidFormFields(errors);
}

void handleSuccessfulAPIResponse(APIResponse response) {
  displaySuccessMessage('用戶註冊成功');
  navigateToWelcomePage();
  clearRegistrationForm();
}

void handleAPIFailure(APIError error) {
  displayErrorMessage('Registration failed: ${error.userFriendlyMessage}');
  logErrorForDebugging(error);
}
```

### 事件組合的語意化表達

#### 複雜業務流程的事件分解

```dart
// ❌ 錯誤：將整個借書流程寫在一個函式中
void borrowBook(String userId, String bookId) {
  final user = getUserById(userId);
  if (user == null) {
    showError('用戶不存在');
    return;
  }

  final book = getBookById(bookId);
  if (book == null) {
    showError('書籍不存在');
    return;
  }

  if (book.status != BookStatus.available) {
    showError('書籍不可借閱');
    return;
  }

  if (user.borrowedBooks.length >= user.maxBorrowLimit) {
    showError('已達借閱上限');
    return;
  }

  // 執行借書
  book.status = BookStatus.borrowed;
  book.borrower = user;
  book.borrowDate = DateTime.now();
  book.dueDate = DateTime.now().add(Duration(days: 14));

  user.borrowedBooks.add(book);

  saveBook(book);
  saveUser(user);

  sendBorrowConfirmationEmail(user, book);
  showSuccess('借書成功');
}

// ✅ 正確：分解為清晰的事件驅動流程
void initiateBorrowBookProcess(String userId, String bookId) {
  final borrowRequest = BorrowRequest.create(userId, bookId);

  validateBorrowRequest(borrowRequest)
    .then(executeBorrowTransaction)
    .then(handleSuccessfulBorrow)
    .catchError(handleBorrowFailure);
}

Future<ValidatedBorrowRequest> validateBorrowRequest(BorrowRequest request) async {
  await validateUserEligibilityForBorrowing(request.userId);
  await validateBookAvailabilityForBorrowing(request.bookId);
  await validateUserBorrowingLimits(request.userId);

  return ValidatedBorrowRequest.fromRequest(request);
}

Future<BorrowTransaction> executeBorrowTransaction(ValidatedBorrowRequest validatedRequest) async {
  final borrowTransaction = createBorrowTransaction(validatedRequest);
  await updateBookStatusToBorrowed(borrowTransaction);
  await updateUserBorrowingRecord(borrowTransaction);
  await persistBorrowTransaction(borrowTransaction);

  return borrowTransaction;
}

void handleSuccessfulBorrow(BorrowTransaction transaction) {
  sendBorrowConfirmationEmail(transaction);
  displayBorrowSuccessMessage(transaction);
  updateLibraryInterface();
}

void handleBorrowFailure(BorrowError error) {
  displayUserFriendlyErrorMessage(error);
  logBorrowFailureForAnalysis(error);
}
```

### 語意化事件命名標準

#### 事件動作的命名原則

```dart
// ❌ 錯誤：技術導向的命名
void processData() {}
void handleEvent() {}
void executeAction() {}

// ✅ 正確：業務事件導向的命名
void validateUserAccountRegistration() {}
void executeBookBorrowingTransaction() {}
void handlePaymentFailureNotification() {}
```

#### 事件結果的命名原則

```dart
// ❌ 錯誤：模糊的結果處理
void onSuccess() {}
void onError() {}
void onComplete() {}

// ✅ 正確：明確的事件結果處理
void handleSuccessfulUserAuthentication() {}
void handleBookSearchTimeoutError() {}
void handlePaymentTransactionCompletion() {}
```

### 事件驅動重構的檢查標準

#### 重構檢查問題

每個包含 if/else 的函式都必須回答：

1. **這個判斷是否代表不同的事件？**
   - 是 → 拆分為獨立的事件處理函式
   - 否 → 檢查是否為單一事件的不同處理路徑

2. **函式是否處理了多個業務事件？**
   - 是 → 必須拆分為事件序列
   - 否 → 檢查函式命名是否正確反映事件意圖

3. **事件的語意是否明確？**
   - 否 → 重新命名函式以反映真實的業務事件
   - 是 → 檢查事件組合是否符合業務邏輯

#### 事件驅動重構範例

```dart
// 重構前：混淆的責任
void updateBookStatus(Book book, String newStatus) {
  if (newStatus == 'available') {
    book.status = BookStatus.available;
    book.borrower = null;
    book.returnDate = DateTime.now();
    updateSearchIndex(book);
    notifyWaitingUsers(book);
  } else if (newStatus == 'borrowed') {
    book.status = BookStatus.borrowed;
    book.borrowDate = DateTime.now();
    book.dueDate = calculateDueDate();
    sendBorrowConfirmation(book);
  } else if (newStatus == 'maintenance') {
    book.status = BookStatus.maintenance;
    removeFromSearchIndex(book);
    notifyMaintenanceTeam(book);
  }
}

// 重構後：明確的事件處理
void handleBookReturnEvent(Book book) {
  executeBookReturn(book);
  notifyBookBecameAvailable(book);
}

void handleBookBorrowEvent(Book book, User borrower) {
  executeBookBorrow(book, borrower);
  confirmBorrowingToUser(book, borrower);
}

void handleBookMaintenanceEvent(Book book) {
  markBookForMaintenance(book);
  notifyMaintenanceRequired(book);
}
```

## 第五原則：可讀性優於簡潔性

### 明確性勝過簡潔性

程式碼的價值排序：

1. **正確性** → 程式必須正確執行
2. **可讀性** → 人類必須能理解
3. **可維護性** → 未來必須能修改
4. **簡潔性** → 最後才考慮程式長度

### 拒絕為簡潔犧牲明確性

#### 錯誤的簡潔性追求

```dart
// ❌ 錯誤：為了簡潔犧牲可讀性
books.where((b) => b.s == 'a' && b.p > 100).map((b) => b.t).toList();

// ❌ 錯誤：過度簡化的命名
void proc(d) => d.map((x) => x.val).reduce((a, b) => a + b);
```

#### 正確的明確性表達

```dart
// ✅ 正確：完全明確的業務邏輯
final availableBooksWithMoreThan100Pages = allBooks
    .where((book) => book.status == BookStatus.available)
    .where((book) => book.pageCount > 100)
    .toList();

final bookTitlesForDisplay = availableBooksWithMoreThan100Pages
    .map((book) => book.title.value)
    .toList();

// ✅ 正確：明確的計算意圖
int calculateTotalPagesFromBookList(List<Book> books) {
  final pageNumbers = books.map((book) => book.pageCount);
  return pageNumbers.reduce((totalPages, currentBookPages) =>
      totalPages + currentBookPages);
}
```

## 函式設計的實用準則

### 函式職責設計標準

每個函式必須通過「電梯測試」：

- **30秒內能說明**：在電梯裡用30秒說完這個函式做什麼
- **單一動詞描述**：函式名稱只包含一個主要動詞
- **無複合邏輯**：不處理多個不相關的業務規則
- **預測性執行**：從名稱就能預測執行結果

### 函式設計範例

#### 複雜業務邏輯的正確拆分

```dart
// ❌ 錯誤：函式負擔過多職責（25行）
Book enrichBookWithFullInformation(String isbn) {
  // ISBN驗證
  if (!isValidISBN(isbn)) throw ArgumentError('Invalid ISBN');

  // 檢查是否已存在
  final existingBook = findBookByISBN(isbn);
  if (existingBook != null) return existingBook;

  // 從多個外部源獲取資料
  final googleBooksData = fetchFromGoogleBooks(isbn);
  final openLibraryData = fetchFromOpenLibrary(isbn);
  final worldCatData = fetchFromWorldCat(isbn);

  // 合併資料
  final mergedData = mergeBookDataFromMultipleSources(
    googleBooksData, openLibraryData, worldCatData);

  // 建立書籍
  final book = createBookFromMergedData(mergedData);

  // 儲存到資料庫
  saveBookToDatabase(book);

  // 更新搜尋索引
  updateSearchIndex(book);

  return book;
}

// ✅ 正確：按照業務邏輯清晰拆分
Book enrichBookWithFullInformation(String isbn) {
  validateISBNForEnrichment(isbn);
  final existingBook = checkIfBookAlreadyExists(isbn);
  if (existingBook != null) return existingBook;

  final enrichedBook = createBookFromMultipleExternalSources(isbn);
  persistNewlyEnrichedBook(enrichedBook);
  return enrichedBook;
}

void validateISBNForEnrichment(String isbn) {
  if (!isValidISBN(isbn)) {
    throw ArgumentError('Cannot enrich book with invalid ISBN: $isbn');
  }
}

Book? checkIfBookAlreadyExists(String isbn) {
  return findBookByISBN(isbn);
}

Book createBookFromMultipleExternalSources(String isbn) {
  final multipleSourceData = gatherBookDataFromAllExternalSources(isbn);
  final mergedBookData = mergeBookDataFromMultipleSources(multipleSourceData);
  return createBookFromMergedData(mergedBookData);
}

void persistNewlyEnrichedBook(Book enrichedBook) {
  saveBookToDatabase(enrichedBook);
  updateSearchIndex(enrichedBook);
}
```

## 第六原則：Widget 獨立性與註解標準

### Widget 獨立性的核心概念

在 Flutter 開發中，Widget 的獨立性決定了程式碼的可維護性和註解需求：

- **獨立 Widget**：下層 Widget 刷新不觸發上層 Widget 重建
- **依賴 Widget**：完全依賴上層 Widget 傳入的資料，無獨立狀態

### Widget 獨立性判斷標準

#### 獨立 Widget 特徵（需要完整註解）

```dart
// ✅ 獨立 Widget - 有自己的狀態管理
class BookListItem extends StatefulWidget {
  /// 【需求來源】UC-05: 雙模式書庫展示切換
  /// 【規格文件】docs/ui_design_specification.md#book-list-item
  /// 【設計方案】方案C-1基礎版 (v0.12.7 Phase 2)
  /// 【工作日誌】docs/work-logs/v0.12.7.md - UI 互動設計
  /// 【Widget 類型】獨立狀態管理 Widget (StatefulWidget)
  /// 【修改約束】此 Widget 具備獨立狀態，下層刷新不觸發上層重建
  /// 【維護警告】修改前需確認子 Widget 依賴關係和狀態傳遞

  final Book book;
  final ValueChanged<Book>? onTap;

  const BookListItem({
    required this.book,
    this.onTap,
    super.key,
  });

  @override
  State<BookListItem> createState() => _BookListItemState();
}

// ✅ 獨立 Widget - 使用 ConsumerWidget 訂閱狀態
class EnrichmentProgressWidget extends ConsumerWidget {
  /// 【需求來源】UC-01: Chrome Extension 匯入書籍資料
  /// 【規格文件】docs/ui_design_specification.md#enrichment-progress
  /// 【設計方案】方案C-1基礎版 (v0.12.4 Phase 2)
  /// 【工作日誌】docs/work-logs/v0.12.4.md - 進度顯示 Widget 設計
  /// 【Widget 類型】獨立狀態管理 Widget (ConsumerWidget)
  /// 【修改約束】此 Widget 獨立訂閱 EnrichmentProgressProvider
  /// 【維護警告】修改時需確保 Provider 依賴正確，避免影響狀態更新

  const EnrichmentProgressWidget({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final progress = ref.watch(enrichmentProgressProvider);
    // ...
  }
}
```

**獨立 Widget 識別規則**：
1. **繼承自**: `StatefulWidget`, `ConsumerWidget`, `StreamBuilder`, `FutureBuilder`
2. **命名特徵**: 非私有（不以 `_` 開頭）
3. **職責特徵**: 有獨立的狀態管理或訂閱機制

#### 依賴 Widget 特徵（可省略詳細註解）

```dart
// ❌ 依賴 Widget - 無獨立狀態，依賴上層傳入資料
class _BookTitleText extends StatelessWidget {
  // 簡單註解即可，上層 BookListItem 已有完整說明
  final String title;
  final TextStyle? style;

  const _BookTitleText({
    required this.title,
    this.style,
  });

  @override
  Widget build(BuildContext context) {
    return Text(
      title,
      style: style ?? Theme.of(context).textTheme.titleMedium,
      maxLines: 2,
      overflow: TextOverflow.ellipsis,
    );
  }
}

// ❌ 依賴 Widget - 純展示元件
class _ProgressBar extends StatelessWidget {
  final double progress;
  final Color? color;

  const _ProgressBar({
    required this.progress,
    this.color,
  });

  @override
  Widget build(BuildContext context) {
    return LinearProgressIndicator(
      value: progress,
      backgroundColor: Colors.grey[300],
      valueColor: AlwaysStoppedAnimation<Color>(
        color ?? Theme.of(context).primaryColor,
      ),
    );
  }
}
```

**依賴 Widget 識別規則**：
1. **繼承自**: `StatelessWidget`
2. **命名特徵**: 私有（以 `_` 開頭）
3. **職責特徵**: 純展示，完全依賴傳入參數，無獨立狀態

### Widget 設計的最佳實踐

#### 獨立 Widget 設計標準

```dart
// ✅ 正確：獨立 Widget 完整封裝狀態和行為
class BookSelectionPanel extends StatefulWidget {
  /// 【需求來源】UC-05: 雙模式書庫展示切換
  /// 【Widget 類型】獨立狀態管理 Widget
  /// 【職責】管理多本書籍的選取狀態，支援單選和多選模式

  final List<Book> books;
  final SelectionMode mode;
  final ValueChanged<List<Book>>? onSelectionChanged;

  const BookSelectionPanel({
    required this.books,
    this.mode = SelectionMode.single,
    this.onSelectionChanged,
    super.key,
  });

  @override
  State<BookSelectionPanel> createState() => _BookSelectionPanelState();
}

class _BookSelectionPanelState extends State<BookSelectionPanel> {
  final Set<String> _selectedBookIds = {};

  void _handleBookTap(Book book) {
    setState(() {
      if (widget.mode == SelectionMode.single) {
        _selectedBookIds.clear();
      }

      if (_selectedBookIds.contains(book.id.value)) {
        _selectedBookIds.remove(book.id.value);
      } else {
        _selectedBookIds.add(book.id.value);
      }
    });

    widget.onSelectionChanged?.call(_getSelectedBooks());
  }

  List<Book> _getSelectedBooks() {
    return widget.books
        .where((book) => _selectedBookIds.contains(book.id.value))
        .toList();
  }

  @override
  Widget build(BuildContext context) {
    return ListView.builder(
      itemCount: widget.books.length,
      itemBuilder: (context, index) {
        final book = widget.books[index];
        final isSelected = _selectedBookIds.contains(book.id.value);

        return _BookSelectionItem(
          book: book,
          isSelected: isSelected,
          onTap: () => _handleBookTap(book),
        );
      },
    );
  }
}

// ❌ 依賴 Widget - 無需詳細註解
class _BookSelectionItem extends StatelessWidget {
  final Book book;
  final bool isSelected;
  final VoidCallback onTap;

  const _BookSelectionItem({
    required this.book,
    required this.isSelected,
    required this.onTap,
  });

  @override
  Widget build(BuildContext context) {
    return ListTile(
      title: Text(book.title.value),
      trailing: isSelected
          ? const Icon(Icons.check_circle, color: Colors.blue)
          : const Icon(Icons.circle_outlined),
      onTap: onTap,
    );
  }
}
```

### Widget 註解標準總結

#### 必須完整註解的 Widget

1. **StatefulWidget** - 有獨立狀態管理
2. **ConsumerWidget** - 使用 Riverpod 訂閱狀態
3. **StreamBuilder** - 監聽 Stream 事件
4. **FutureBuilder** - 處理異步資料
5. **非私有命名的主要 Widget** - 對外公開的 UI 元件

#### 可省略詳細註解的 Widget

1. **私有 StatelessWidget** - 依賴上層傳入資料
2. **純展示元件** - 無業務邏輯
3. **輔助 Widget** - 上層 Widget 已有完整說明

### Widget 獨立性設計檢查清單

- [ ] 此 Widget 是否有獨立的狀態管理？
- [ ] 下層 Widget 刷新是否會觸發上層重建？
- [ ] Widget 是否訂閱了外部狀態（Provider/Stream）？
- [ ] Widget 命名是否清楚表達獨立性（非私有 vs 私有）？
- [ ] 獨立 Widget 是否有完整的需求追溯註解？
- [ ] 依賴 Widget 是否正確標記為私有（`_` 開頭）？

## 驗證標準與檢查清單

### 自然語言化程式碼檢查清單

#### 命名檢查

- [ ] 函式名稱是否以動詞開頭？
- [ ] 變數名稱是否完整描述內容？
- [ ] 類別名稱是否說明職責？
- [ ] 所有名稱是否無縮寫？
- [ ] 名稱是否在任何上下文都能理解？

#### 函式長度檢查

- [ ] 每個函式是否在10行以內？
- [ ] 函式是否只負責單一職責？
- [ ] 函式名稱是否能30秒內說明完畢？
- [ ] 函式是否無複合邏輯？

#### 事件驅動架構檢查

- [ ] 包含 if/else 的函式是否正確分解為事件處理？
- [ ] 每個判斷分支是否代表明確的業務事件？
- [ ] 函式名稱是否反映真實的業務事件？
- [ ] 複雜流程是否拆分為事件序列？
- [ ] 錯誤處理是否也視為需要處理的事件？

#### 變數職責檢查

- [ ] 每個變數是否只承載一種類型資料？
- [ ] 變數是否在整個生命週期保持同一職責？
- [ ] 變數名稱是否完全描述用途？
- [ ] 沒有為了重用而混用變數？

#### 可讀性檢查

- [ ] 程式碼是否如同閱讀自然語言？
- [ ] 不需要註解就能理解程式邏輯？
- [ ] 業務邏輯是否直觀明確？
- [ ] 執行流程是否容易追蹤？

### 品質驗證測試

#### 陌生人測試

讓完全不熟悉專案的工程師閱讀程式碼：

- 5分鐘內能理解主要邏輯 → 合格
- 需要解釋才能理解 → 重寫
- 無法理解業務目的 → 重新設計

#### 自然語言轉換測試

將程式碼翻譯成自然語言：

- 翻譯流暢自然 → 合格
- 翻譯生硬難懂 → 改善命名
- 無法翻譯 → 重新設計

#### 未來維護者測試

假設6個月後要修改這段程式碼：

- 能快速定位要修改的地方 → 合格
- 需要重新理解邏輯 → 改善結構
- 不敢修改怕破壞功能 → 重新設計

## 反模式：常見的撰寫錯誤

### 技術導向命名

```dart
// ❌ 錯誤：技術實作導向
class BookRepository {}
class UserDAO {}
class PaymentProcessor {}

// ✅ 正確：業務行為導向
class BookLibrarySearchEngine {}
class UserAccountManager {}
class PaymentTransactionHandler {}
```

### 過度簡化

```dart
// ❌ 錯誤：犧牲明確性的簡化
void proc(d) => save(transform(validate(d)));

// ✅ 正確：明確的業務流程
void processUserRegistration(UserRegistrationData data) {
  final validatedData = validateUserRegistrationData(data);
  final transformedData = transformToUserAccount(validatedData);
  saveUserAccountToDatabase(transformedData);
}
```

### 職責混淆

```dart
// ❌ 錯誤：單一函式處理多種職責
void handleUserAction(String action, dynamic data) {
  if (action == 'login') {
    // 登入邏輯
  } else if (action == 'register') {
    // 註冊邏輯
  } else if (action == 'logout') {
    // 登出邏輯
  }
}

// ✅ 正確：每個職責獨立函式
void handleUserLogin(LoginData loginData) {
  // 專門處理登入
}

void handleUserRegistration(RegistrationData registrationData) {
  // 專門處理註冊
}

void handleUserLogout(LogoutData logoutData) {
  // 專門處理登出
}
```

## 結論

程式碼不是寫給電腦看的，而是寫給人類讀的。電腦只是執行的工具，人類才是維護和擴展的主體。

**每一行程式碼都是一句話，每個函式都是一個段落，每個類別都是一個章節。**

好的程式碼應該像一本好書一樣，讓讀者能夠：
- 理解作者的意圖
- 跟隨思考的邏輯
- 預測故事的發展
- 在需要時修改情節

這是溝通原則，確保程式碼能被任何維護者理解和擴展。
