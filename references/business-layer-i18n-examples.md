# 分層 i18n 管理：完整程式碼範例

> **用途**：本檔為 `.claude/methodologies/business-layer-i18n-management-methodology.md` 的衛星參考檔，存放三層責任（Domain/Service、ViewModel、UI）的完整程式碼範例、參數化訊息的完整範例，以及四個反模式的正反程式碼對照。需要照抄某一層的實作骨架、或需要對照具體反模式程式碼理解違規時按需讀取。
>
> **核心方法論（分層責任概念 + 錯誤訊息流程 + 反模式概念 + 檢查清單，30 秒核心）**：`.claude/methodologies/business-layer-i18n-management-methodology.md`（需回顧分層責任定義、三個合法訊息來源、錯誤訊息流程或檢查清單時讀）

---

## 三層責任完整程式碼範例

對應主檔「分層責任」節（各層的職責定義與規則）。本節提供每一層的完整實作骨架。

### Domain/Service 層

回傳技術性結果或錯誤碼，禁止使用 i18n 或任何使用者訊息字串。

```dart
// Domain 層錯誤定義
enum BookErrorCode {
  notFound,
  invalidIsbn,
  networkTimeout,
  serverError,
}

// Service 層回傳錯誤碼
class BookRepository {
  Future<Result<Book, BookErrorCode>> fetchBook(String id) async {
    try {
      final response = await api.getBook(id);
      return Result.success(Book.fromJson(response));
    } on NotFoundException {
      return Result.failure(BookErrorCode.notFound);
    } on TimeoutException {
      return Result.failure(BookErrorCode.networkTimeout);
    }
  }
}
```

### ViewModel 層

將 `ErrorCode` 轉換為 i18n 訊息（三個合法訊息來源見主檔），禁止硬編碼使用者訊息字串。

```dart
class BookDetailViewModel extends StateNotifier<BookDetailState> {
  BookDetailViewModel(this._repository) : super(BookDetailState.initial());

  final BookRepository _repository;

  Future<void> loadBook(String id) async {
    state = state.copyWith(isLoading: true);

    final result = await _repository.fetchBook(id);

    result.when(
      success: (book) {
        state = state.copyWith(
          isLoading: false,
          book: book,
        );
      },
      failure: (errorCode) {
        // 使用 ErrorHandler 轉換錯誤碼為 i18n 訊息
        final message = ErrorHandler.getMessage(errorCode);
        state = state.copyWith(
          isLoading: false,
          errorMessage: message,
        );
      },
    );
  }
}

// ErrorHandler 實作
class ErrorHandler {
  static String getMessage(BookErrorCode code, {required AppLocalizations l10n}) {
    switch (code) {
      case BookErrorCode.notFound:
        return l10n.bookNotFound;
      case BookErrorCode.invalidIsbn:
        return l10n.invalidIsbn;
      case BookErrorCode.networkTimeout:
        return l10n.networkTimeout;
      case BookErrorCode.serverError:
        return l10n.serverError;
    }
  }
}
```

### UI 層

直接顯示 ViewModel 提供的訊息，禁止自行組裝或轉換訊息。

```dart
class BookDetailScreen extends ConsumerWidget {
  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final state = ref.watch(bookDetailViewModelProvider);

    if (state.isLoading) {
      return const CircularProgressIndicator();
    }

    if (state.errorMessage != null) {
      // 直接顯示 ViewModel 提供的訊息，不自行處理
      return ErrorDisplay(message: state.errorMessage!);
    }

    return BookDetailContent(book: state.book!);
  }
}
```

---

## 參數化訊息完整範例

對應主檔「參數化訊息處理」節。當訊息需要動態參數時，在 ViewModel 層組裝。

**i18n 定義（ARB 檔案）**：

```json
{
  "bookNotFoundWithId": "找不到書籍（ID: {bookId}）",
  "@bookNotFoundWithId": {
    "placeholders": {
      "bookId": {
        "type": "String"
      }
    }
  }
}
```

**ViewModel 使用**：

```dart
// ViewModel 層組裝參數化訊息
final message = l10n.bookNotFoundWithId(bookId);
state = state.copyWith(errorMessage: message);
```

**禁止做法**：

```dart
// 禁止：在 UI 層組裝
Text('找不到書籍（ID: ${state.bookId}）');  // 硬編碼違規

// 禁止：在 Domain 層組裝
throw Exception('Book not found: $id');  // Domain 不應產生使用者訊息
```

---

## 四反模式正反程式碼對照

對應主檔「反模式」節（4 反模式標題 + 為什麼是錯的）。本節提供每個反模式的完整錯誤程式碼。

### 反模式一：Domain 層包含使用者訊息

```dart
// 錯誤：Domain 層不應該知道使用者訊息
class BookRepository {
  Future<Result<Book, String>> fetchBook(String id) async {
    try {
      // ...
    } catch (e) {
      return Result.failure('找不到這本書');  // 錯誤！
    }
  }
}
```

**為什麼是錯的**：違反關注點分離；無法支援多語言；Domain 層耦合到 UI 呈現。

### 反模式二：ViewModel 硬編碼訊息

```dart
// 錯誤：ViewModel 不應硬編碼訊息
class BookViewModel {
  void handleError(BookErrorCode code) {
    switch (code) {
      case BookErrorCode.notFound:
        state = state.copyWith(errorMessage: '找不到書籍');  // 錯誤！
        break;
    }
  }
}
```

**為什麼是錯的**：無法支援多語言；訊息散落在程式碼各處，難以維護；違反 i18n 規範。

### 反模式三：UI 層自行組裝訊息

```dart
// 錯誤：UI 層不應自行組裝訊息
class BookScreen extends StatelessWidget {
  @override
  Widget build(BuildContext context) {
    if (state.hasError) {
      // 錯誤！UI 不應自行決定訊息內容
      return Text(state.errorCode == BookErrorCode.notFound
          ? '找不到書籍'
          : '發生錯誤');
    }
  }
}
```

**為什麼是錯的**：UI 層應該只負責呈現，不負責邏輯；訊息邏輯應集中在 ViewModel 層；增加 UI 層複雜度。

### 反模式四：跨層傳遞 Context

```dart
// 錯誤：不應將 BuildContext 傳到 Domain 層
class BookRepository {
  Future<void> fetchBook(String id, BuildContext context) async {
    // 錯誤！Domain 層不應依賴 Flutter Context
    final l10n = AppLocalizations.of(context);
  }
}
```

**為什麼是錯的**：Domain 層耦合到 Flutter 框架；難以測試；違反分層架構。

---

**Last Updated**: 2026-06-14
**Version**: 1.0.0 - 從 business-layer-i18n-management-methodology.md 外移：三層責任完整程式碼範例 + 參數化訊息完整範例 + 四反模式正反程式碼對照（W8-020.10 方法論瘦身校準）
