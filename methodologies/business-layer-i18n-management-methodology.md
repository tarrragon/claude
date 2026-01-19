# 分層 i18n 管理方法論

## 核心概念

i18n（國際化）訊息的管理遵循分層架構原則：**每層有明確的 i18n 責任，Domain 層不知道 UI 呈現方式**。

**關鍵原則**：
- 單一職責：每層只處理自己的 i18n 責任
- 關注點分離：Domain 層使用技術語言，ViewModel 層轉換為使用者語言
- 禁止硬編碼：所有使用者可見訊息必須來自合法來源

---

## 分層責任

### Domain/Service 層

**職責**：處理業務邏輯，回傳技術性結果或錯誤碼。

**規則**：
- 使用 `ErrorCode` 枚舉或技術異常
- **禁止**使用 i18n 或任何使用者訊息字串
- 回傳可被上層轉換的結構化資料

**範例**：

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

**職責**：將 Domain 層結果轉換為 UI 可顯示的狀態，包含使用者友善訊息。

**規則**：
- 將 `ErrorCode` 轉換為 i18n 訊息
- **禁止**硬編碼使用者訊息字串
- 使用三個合法訊息來源

**三個合法訊息來源**：

| 來源 | 使用場景 | 範例 |
|------|---------|------|
| **i18n 系統** | 靜態訊息，多語言支援 | `context.l10n!.invalidFileFormat` |
| **ErrorHandler** | 統一錯誤處理 | `ErrorHandler.getMessage(errorCode)` |
| **Domain 回傳** | 動態訊息（伺服器回傳） | `apiResponse.message` |

**範例**：

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

**職責**：顯示 ViewModel 提供的狀態和訊息。

**規則**：
- 直接使用 ViewModel 提供的訊息
- **禁止**自行組裝或轉換訊息
- **禁止**硬編碼使用者訊息字串

**範例**：

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

## 錯誤訊息流程

```text
[Domain/Service 層]
        |
        | 回傳 ErrorCode 或技術異常
        v
[ViewModel 層]
        |
        | 使用 ErrorHandler 或 i18n 轉換為使用者訊息
        v
[UI 層]
        |
        | 直接顯示訊息
        v
[使用者看到友善訊息]
```

**完整流程範例**：

```text
1. Repository 捕獲 TimeoutException
2. Repository 回傳 Result.failure(BookErrorCode.networkTimeout)
3. ViewModel 接收 errorCode
4. ViewModel 呼叫 ErrorHandler.getMessage(errorCode)
5. ErrorHandler 查詢 i18n：l10n.networkTimeout → "網路連線逾時，請稍後再試"
6. ViewModel 更新 state.errorMessage
7. UI 顯示 state.errorMessage
```

---

## 參數化訊息處理

當訊息需要動態參數時，在 ViewModel 層組裝。

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

## 反模式

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

**為什麼是錯的**：
- 違反關注點分離
- 無法支援多語言
- Domain 層耦合到 UI 呈現

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

**為什麼是錯的**：
- 無法支援多語言
- 訊息散落在程式碼各處，難以維護
- 違反 i18n 規範

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

**為什麼是錯的**：
- UI 層應該只負責呈現，不負責邏輯
- 訊息邏輯應集中在 ViewModel 層
- 增加 UI 層複雜度

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

**為什麼是錯的**：
- Domain 層耦合到 Flutter 框架
- 難以測試
- 違反分層架構

---

## 執行步驟

1. **確認層級**：判斷目前程式碼屬於哪一層
2. **選擇訊息來源**：Domain 用 ErrorCode，ViewModel 用 i18n/ErrorHandler
3. **實作轉換**：在 ViewModel 層完成 ErrorCode 到訊息的轉換
4. **驗證 UI**：確認 UI 只顯示 ViewModel 提供的訊息

---

## 檢查清單

### Domain/Service 層

- [ ] 使用 ErrorCode 枚舉而非訊息字串
- [ ] 無 i18n 相關 import
- [ ] 無硬編碼使用者訊息
- [ ] 無 BuildContext 依賴

### ViewModel 層

- [ ] 所有使用者訊息來自三個合法來源
- [ ] 無硬編碼使用者訊息字串
- [ ] ErrorCode 轉換邏輯集中（ErrorHandler）
- [ ] 參數化訊息在此層組裝

### UI 層

- [ ] 直接使用 ViewModel 提供的訊息
- [ ] 無自行組裝訊息邏輯
- [ ] 無硬編碼使用者訊息字串
- [ ] 無 ErrorCode 判斷邏輯

### 整體架構

- [ ] i18n 訊息轉換只發生在 ViewModel 層
- [ ] Domain 層與 UI 呈現完全解耦
- [ ] ErrorHandler 集中管理錯誤訊息轉換

---

## Reference

### 專案規範

- [FLUTTER.md - ViewModel 層使用者訊息規範](../../FLUTTER.md#viewmodel-層使用者訊息規範) - ViewModel 禁止事項和檢查清單
- [錯誤修復和重構方法論](./error-fix-refactor-methodology.md) - 錯誤處理原則

### 相關方法論

- [行為優先 TDD 方法論](./behavior-first-tdd-methodology.md) - 測試設計原則
- [程式碼自然語言化撰寫方法論](./natural-language-programming-methodology.md) - 命名規範
