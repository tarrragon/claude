---
name: provider-architecture
description: "Riverpod Provider 架構設計規範 - 確保正確的依賴注入、介面隔離和測試可行性"
---

# Provider Architecture Skill

Riverpod Provider 架構設計規範 - 確保正確的依賴注入、介面隔離和測試可行性。

## 使用方法

要查詢 Provider 架構設計指南，輸入：

```text
/provider-architecture
```

---

## 核心設計原則

### 問題的本質

ref 問題的根源不只是 Provider 定義方式，而是**直接操作狀態**而非**透過介面提供語意化方法**。

### 三大設計原則

#### 1. 介面隔離原則

對內和對外使用不同的接口：

| 接口類型 | 暴露對象 | 範例方法 |
|---------|---------|---------|
| **對外（Widget 層）** | 語意化方法 | `selectFile()`, `startImport()`, `reset()` |
| **對內（ViewModel）** | 私有方法 | `_updateProgress()`, `_handleError()` |

**程式碼範例**：

```dart
class ChromeExtensionImportViewModel extends Notifier<ChromeExtensionImportState> {
  // === 對外語意化方法（Widget 層呼叫）===
  Future<void> selectFile() async { ... }
  Future<void> startImport() async { ... }
  void reset() { ... }
  void retry() { ... }

  // === 對內私有方法（狀態操作封裝）===
  void _updateProgress(double progress) { ... }
  void _handleError(AppException error) { ... }
}
```

#### 2. 語意化操作原則

不直接操作狀態，而是透過有意義的方法名稱：

```dart
// 錯誤：直接操作狀態
ref.read(provider.notifier).state = newState;

// 正確：透過語意化方法
ref.read(provider.notifier).selectFile();
```

#### 3. 依賴注入透過介面原則

服務透過 Provider 注入，不硬編碼實例：

```dart
// 錯誤：ViewModel 直接依賴具體實作
class MyViewModel {
  final _bookService = BookService();  // 硬編碼，無法測試替換
}

// 正確：透過 Provider 注入
class MyViewModel extends Notifier<MyState> {
  late final BookService _bookService;  // 延遲初始化

  @override
  MyState build() {
    // 在 build() 中透過 ref.read() 取得服務
    // 這些服務可以在測試中被 override
    _bookService = ref.read(bookServiceProvider);
    return MyState.initial();
  }
}
```

---

## 標準 ViewModel 模式

### 完整範例

```dart
/// ChromeExtensionImportViewModel
///
/// 職責：管理 Chrome Extension 資料匯入流程的狀態
///
/// 設計原則：
/// - 服務透過 Provider 注入（支援測試替換）
/// - 對外只暴露語意化方法
/// - 狀態操作封裝在內部
class ChromeExtensionImportViewModel extends Notifier<ChromeExtensionImportState> {
  // === 透過 Provider 注入的服務 ===
  late final BookService _bookService;
  late final FileService _fileService;
  late final JsonValidationService _jsonValidationService;

  @override
  ChromeExtensionImportState build() {
    // 在 build() 中透過 ref.read() 取得服務
    _bookService = ref.read(bookServiceProvider);
    _fileService = ref.read(fileServiceProvider);
    _jsonValidationService = ref.read(jsonValidationServiceProvider);
    return const ChromeExtensionImportState();
  }

  // === 對外語意化方法 ===

  /// 選擇要匯入的 JSON 檔案
  Future<void> selectFile() async {
    final file = await _fileService.pickJsonFile();
    if (file != null) {
      state = state.copyWith(selectedFile: file);
      await _validateFile(file);
    }
  }

  /// 開始執行匯入
  Future<void> startImport() async {
    _updateProgress(0.0);
    try {
      final books = await _processImport();
      await _bookService.saveBooks(books);
      _updateProgress(1.0);
    } catch (e) {
      _handleError(e as AppException);
    }
  }

  /// 重設狀態
  void reset() {
    state = const ChromeExtensionImportState();
  }

  /// 重試上次操作
  void retry() {
    if (state.selectedFile != null) {
      startImport();
    }
  }

  // === 對內私有方法 ===

  void _updateProgress(double progress) {
    state = state.copyWith(progress: progress);
  }

  void _handleError(AppException error) {
    state = state.copyWith(error: error);
  }

  Future<void> _validateFile(File file) async { ... }
  Future<List<Book>> _processImport() async { ... }
}
```

### Provider 定義

```dart
/// Provider 定義
///
/// 使用 .new 簡化寫法，讓 Notifier 在 build() 中自行取得依賴
final chromeExtensionImportViewModelProvider =
    NotifierProvider<ChromeExtensionImportViewModel, ChromeExtensionImportState>(
  ChromeExtensionImportViewModel.new,
);
```

---

## 測試最佳實踐

### Provider Override 機制

在測試中透過 `ProviderScope.overrides` 注入 Mock 服務：

```dart
testWidgets('完整匯入流程', (tester) async {
  // 1. 建立共享的 Mock 服務實例
  final mockBookService = MockBookService();
  final mockFileService = MockFileServiceForImport();
  final mockJsonValidationService = MockJsonValidationService();

  // 2. 透過語意化方法配置 Mock 行為
  mockFileService.setPickResult(tempJsonFile);

  // 3. 使用 ProviderScope.overrides 注入 Mock
  await tester.pumpWidget(
    ProviderScope(
      overrides: [
        bookServiceProvider.overrideWithValue(mockBookService),
        fileServiceProvider.overrideWithValue(mockFileService),
        jsonValidationServiceProvider.overrideWithValue(mockJsonValidationService),
      ],
      child: MaterialApp(
        home: const ChromeExtensionImportWidget(),
      ),
    ),
  );

  // 4. 測試透過 UI 互動驗證行為
  await tester.tap(find.byKey(const Key('import_data_button')));
  await tester.pumpAndSettle();
  expect(find.text('成功匯入 5 本書籍'), findsOneWidget);
});
```

### Mock 服務設計原則

Mock 服務也應提供語意化方法：

```dart
class MockFileServiceForImport implements FileService {
  File? _pickResult;

  /// 設定檔案選取結果（語意化方法）
  void setPickResult(File? file) {
    _pickResult = file;
  }

  @override
  Future<File?> pickJsonFile() async => _pickResult;
}
```

---

## 禁止行為

### 1. 直接操作 `.state`

```dart
// 錯誤
ref.read(provider.notifier).state = newState;

// 正確
ref.read(provider.notifier).updateSomething(value);
```

### 2. 在建構函式中硬編碼服務實例

```dart
// 錯誤
class MyViewModel {
  final _service = ConcreteService();  // 硬編碼
}

// 正確
class MyViewModel extends Notifier<MyState> {
  late final AbstractService _service;

  @override
  MyState build() {
    _service = ref.read(serviceProvider);
    return MyState.initial();
  }
}
```

### 3. 使用 `ref.watch()` 在非 build 方法中

```dart
// 錯誤：在普通方法中使用 watch
void someMethod() {
  final service = ref.watch(serviceProvider);  // 會導致不必要的重建
}

// 正確：在 build() 中使用 watch，其他地方用 read
@override
MyState build() {
  final reactiveData = ref.watch(someDataProvider);  // OK：響應式資料
  _service = ref.read(serviceProvider);  // OK：服務實例
  return MyState(data: reactiveData);
}

void someMethod() {
  final service = ref.read(serviceProvider);  // OK：一次性讀取
}
```

---

## 專案參考範例

已使用此模式的 ViewModel：

| 檔案 | 行數 | 說明 |
|------|------|------|
| `lib/presentation/viewmodels/advanced_search_viewmodel.dart` | 149-151 | 搜尋功能 ViewModel |
| `lib/presentation/library/library_viewmodel.dart` | 84-94 | 圖書館主頁 ViewModel |
| `lib/presentation/import/chrome_extension_import_view_model.dart` | - | 匯入功能 ViewModel |

---

## 檢查清單

### ViewModel 設計檢查

- [ ] 服務是否透過 `late final` 聲明？
- [ ] 服務是否在 `build()` 中透過 `ref.read()` 取得？
- [ ] 對外方法是否都是語意化的（動詞開頭）？
- [ ] 狀態操作是否都封裝在私有方法中？

### Provider 定義檢查

- [ ] 是否使用 `.new` 簡化寫法？
- [ ] 是否避免在建構函式中傳入依賴？

### 測試設計檢查

- [ ] 是否使用 `ProviderScope.overrides` 注入 Mock？
- [ ] Mock 服務是否提供語意化配置方法？
- [ ] 是否透過 UI 互動驗證行為（而非檢查內部狀態）？

---

## 相關資源

### 方法論

- [敏捷重構方法論](.claude/methodologies/agile-refactor-methodology.md)
- [TDD 四階段流程](.claude/rules/flows/tdd-flow.md)

### Tickets

- `0.25.1-W2-002`: Provider Override 機制實作
- `0.25.1-W2-003`: AppButton Flexible Widget 修復

### 錯誤模式

- `TM-007`: 測試期望與實作行為不符

---

*建立日期：2026-01-13*
*來源：UC-01 整合測試修復過程中的經驗總結*
