# MVVM ViewModel 開發方法論

## 🎯 5W1H 決策記錄

**Who**: lavender-interface-designer、pepper-test-implementer 協作開發
**What**: 建立完整的 ViewModel 開發規範，確保 MVVM 架構一致性
**When**: 每次開發新功能的 UI 層時強制遵循
**Where**: `lib/presentation/[feature]/[feature]_viewmodel.dart`
**Why**: 解決 MVVM 架構執行不足問題（當前覆蓋率僅 13%）
**How**: 透過標準化的 ViewModel 結構、Mapper 模式、Provider 整合模式

---

## 📚 核心概念

### ViewModel 定位

**ViewModel 是 MVVM 架構的核心層**，負責：

1. **Domain → UI 轉換**：將 Domain 模型轉為 UI 需要的格式
2. **UI 狀態管理**：管理 Widget 狀態和互動邏輯
3. **Provider 定義**：定義 Riverpod Provider 供 Widget 使用
4. **UI 專用計算邏輯**：提供顏色、圖標、格式化文字等 UI 屬性

### MVVM 分層原則

```text
┌─────────────────────────────────────────┐
│ Presentation Layer (UI 層)              │
├─────────────────────────────────────────┤
│ Widget (Page/Extensions)                │
│ - 純 UI 組裝，無業務邏輯                 │
│ - 使用 ViewModel Provider 取得資料       │
│ - 顯示 ViewModel 提供的 UI 屬性          │
├─────────────────────────────────────────┤
│ ViewModel                               │
│ - Domain → UI 轉換                       │
│ - UI 狀態管理                            │
│ - UI 專用計算邏輯                        │
│ - Provider 定義                          │
├─────────────────────────────────────────┤
│ Mapper                                  │
│ - Domain 模型 → ViewModel 轉換邏輯       │
├─────────────────────────────────────────┤
│ Domain Layer (領域層)                    │
│ - 業務邏輯                               │
│ - Domain 模型                            │
│ - Domain 服務                            │
└─────────────────────────────────────────┘
```

---

## 🏗 ViewModel 命名規範

### 命名格式

**格式**：`[Feature]ViewModel`

**範例**：
- `EnrichmentProgressViewModel` - 補充進度顯示
- `ChromeExtensionImportViewModel` - Chrome Extension 匯入
- `LibraryDisplayViewModel` - 書庫展示
- `AdvancedSearchViewModel` - 進階搜尋

### 檔案位置

**標準路徑**：`lib/presentation/[feature]/[feature]_viewmodel.dart`

**範例**：
```text
lib/presentation/
├── import/
│   └── chrome_extension_import_viewmodel.dart
├── library/
│   ├── library_viewmodel.dart
│   └── library_display_page.dart
└── search/
    └── advanced_search_viewmodel.dart
```

---

## 📋 ViewModel 職責定義

### ✅ 包含的職責

#### 1. Domain → UI 轉換

將 Domain 模型轉換為 UI 需要的格式：

```dart
/// Domain 來源
final EnrichmentProgress domainProgress;

/// UI 專用欄位（計算屬性）
String get displayStatus => _mapStatus();
IconData get statusIcon => _mapIcon();
Color get progressColor => _mapColor();
```

#### 2. UI 狀態管理

管理 Widget 需要的狀態：

```dart
class EnrichmentProgressViewModel {
  // 狀態欄位
  final EnrichmentProgress domainProgress;
  final List<Book> failedBooks;

  // UI 控制狀態
  bool get showFailedBooks => failedBooks.isNotEmpty;
  bool get canRetry => domainProgress.isComplete && failedBooks.isNotEmpty;
}
```

#### 3. Provider 定義

定義 Riverpod Provider 供 Widget 使用：

```dart
final enrichmentProgressViewModelProvider =
  StreamProvider.family<EnrichmentProgressViewModel, String>(
    (ref, operationId) {
      // Provider 邏輯
    },
  );
```

#### 4. UI 專用計算邏輯

提供 UI 需要的格式化資料：

```dart
/// 格式化的摘要文字
String get summaryText =>
  '已處理 ${domainProgress.processedBooks}/${domainProgress.totalBooks} 本';

/// 進度顏色（根據狀態決定）
Color get progressColor {
  if (domainProgress.failedEnrichments > 0) return Colors.orange;
  if (domainProgress.isComplete) return Colors.green;
  return Colors.blue;
}
```

### ❌ 不包含的內容

#### 1. Widget 程式碼

```dart
// ❌ 錯誤：ViewModel 中包含 Widget
class EnrichmentProgressViewModel {
  Widget buildProgressBar() {  // 違規
    return LinearProgressIndicator(...);
  }
}

// ✅ 正確：Widget 在 Extension 中
extension EnrichmentProgressWidgets on Widget {
  Widget enrichmentProgressBar(EnrichmentProgressViewModel vm) {
    return LinearProgressIndicator(
      value: vm.domainProgress.percentageComplete / 100,
      color: vm.progressColor,
    );
  }
}
```

#### 2. 直接依賴 Flutter 框架（除 ChangeNotifier）

```dart
// ❌ 錯誤：依賴 Flutter Material
import 'package:flutter/material.dart';

class MyViewModel {
  BuildContext? context;  // 違規
}

// ✅ 正確：使用 Dart 原生類型
class MyViewModel {
  Color progressColor;  // 可以使用 Color（來自 dart:ui）
  IconData statusIcon;  // 可以使用 IconData
}
```

#### 3. 業務邏輯

```dart
// ❌ 錯誤：在 ViewModel 中執行業務邏輯
class EnrichmentProgressViewModel {
  Future<void> enrichBook(Book book) {
    // 呼叫 API、驗證資料、儲存到資料庫
    // 這些是 Domain 層的職責
  }
}

// ✅ 正確：業務邏輯在 Domain Service
class IBookInfoEnrichmentService {
  Future<EnrichedBookInfo> enrichBookInfo(Book book);
}

// ViewModel 只負責狀態管理
class EnrichmentProgressViewModel {
  final EnrichmentProgress domainProgress;
  // 不包含業務邏輯
}
```

---

## 🔧 ViewModel 結構範本

### 基本結構

```dart
/// UI 層專用的 [Feature] 顯示模型
///
/// 職責：
/// - 將 Domain 模型轉換為 UI 需要的格式
/// - 提供 UI 專用的計算屬性
/// - 管理 UI 狀態
///
/// 需求：[需求編號]
class [Feature]ViewModel {
  // =============================================================================
  // Domain 來源（不可變）
  // =============================================================================

  /// Domain 模型來源
  final [DomainModel] domainModel;

  /// 額外的 Domain 資料（如失敗清單）
  final List<[Entity]> additionalData;

  // =============================================================================
  // UI 專用欄位（計算屬性）
  // =============================================================================

  /// 狀態顯示文字
  String get displayStatus => _mapStatus();

  /// 狀態圖標
  IconData get statusIcon => _mapIcon();

  /// 進度顏色
  Color get progressColor => _mapColor();

  /// 摘要文字
  String get summaryText => _formatSummary();

  // =============================================================================
  // 建構子
  // =============================================================================

  const [Feature]ViewModel({
    required this.domainModel,
    this.additionalData = const [],
  });

  // =============================================================================
  // Domain → UI 轉換方法（私有）
  // =============================================================================

  /// 對應狀態到顯示文字
  String _mapStatus() {
    // 轉換邏輯
  }

  /// 對應狀態到圖標
  IconData _mapIcon() {
    // 轉換邏輯
  }

  /// 對應狀態到顏色
  Color _mapColor() {
    // 轉換邏輯
  }

  /// 格式化摘要文字
  String _formatSummary() {
    // 格式化邏輯
  }
}
```

### 完整範例：EnrichmentProgressViewModel

```dart
import 'package:flutter/material.dart';
import 'package:book_overview_app/domains/import/value_objects/enrichment_progress.dart';
import 'package:book_overview_app/domains/library/entities/book.dart';

/// UI 層專用的補充進度顯示模型
///
/// 職責：
/// - 將 EnrichmentProgress Domain 模型轉為 UI 格式
/// - 提供進度顏色、圖標、文字等 UI 屬性
/// - 管理失敗書籍清單的顯示
///
/// 需求：UC-01.Enrichment.Progress
class EnrichmentProgressViewModel {
  // =============================================================================
  // Domain 來源
  // =============================================================================

  /// Domain 進度模型
  final EnrichmentProgress domainProgress;

  /// 失敗補充的書籍清單
  final List<Book> failedBooks;

  // =============================================================================
  // UI 專用欄位（計算屬性）
  // =============================================================================

  /// 狀態顯示文字
  ///
  /// 對應規則：
  /// - processedBooks == 0 → "準備中"
  /// - processedBooks > 0 && !isComplete → "補充中"
  /// - isComplete → "已完成"
  String get displayStatus {
    if (domainProgress.isComplete) return '已完成';
    if (domainProgress.processedBooks == 0) return '準備中';
    return '補充中';
  }

  /// 狀態圖標
  ///
  /// 對應規則：
  /// - 準備中 → Icons.pending
  /// - 補充中 → Icons.sync
  /// - 已完成 → Icons.check_circle
  IconData get statusIcon {
    if (domainProgress.isComplete) return Icons.check_circle;
    if (domainProgress.processedBooks == 0) return Icons.pending;
    return Icons.sync;
  }

  /// 進度顏色
  ///
  /// 對應規則：
  /// - 有失敗 → 橘色警告
  /// - 已完成 → 綠色成功
  /// - 進行中 → 藍色
  Color get progressColor {
    if (domainProgress.failedEnrichments > 0) return Colors.orange;
    if (domainProgress.isComplete) return Colors.green;
    return Colors.blue;
  }

  /// 摘要文字
  ///
  /// 格式：「已處理 X/Y 本（成功 A，失敗 B）」
  String get summaryText {
    final processed = domainProgress.processedBooks;
    final total = domainProgress.totalBooks;
    final success = domainProgress.successfulEnrichments;
    final failed = domainProgress.failedEnrichments;

    if (failed > 0) {
      return '已處理 $processed/$total 本（成功 $success，失敗 $failed）';
    }
    return '已處理 $processed/$total 本';
  }

  /// 失敗書籍摘要清單
  ///
  /// 提供簡化的書籍資訊供 UI 顯示
  List<BookSummary> get failedBooksSummary {
    return failedBooks.map((book) => BookSummary.fromBook(book)).toList();
  }

  /// 進度百分比（直接使用 Domain 計算）
  double get progressPercentage => domainProgress.percentageComplete;

  /// 當前處理書名（如果有）
  String? get currentBookTitle => domainProgress.currentBook?.title.value;

  /// 是否顯示失敗清單
  bool get showFailedBooks => failedBooks.isNotEmpty;

  /// 是否可以重試
  bool get canRetry => domainProgress.isComplete && failedBooks.isNotEmpty;

  // =============================================================================
  // 建構子
  // =============================================================================

  const EnrichmentProgressViewModel({
    required this.domainProgress,
    this.failedBooks = const [],
  });
}

/// 書籍摘要（UI 專用簡化資料）
class BookSummary {
  final String id;
  final String title;
  final String author;

  const BookSummary({
    required this.id,
    required this.title,
    required this.author,
  });

  factory BookSummary.fromBook(Book book) {
    return BookSummary(
      id: book.id.value,
      title: book.title.value,
      author: book.author.value,
    );
  }
}
```

---

## 🔄 Mapper 模式

### Mapper 職責

**Mapper 負責 Domain 模型 → ViewModel 的轉換邏輯**。

### Mapper 結構

```dart
/// Domain [DomainModel] → UI ViewModel 轉換器
///
/// 職責：
/// - 將 Domain 模型轉換為 ViewModel
/// - 整合多個 Domain 資料來源
/// - 處理轉換過程中的資料格式化
class [Feature]Mapper {
  /// 轉換 Domain 模型為 ViewModel
  static [Feature]ViewModel toViewModel(
    [DomainModel] domainModel,
    // 額外的 Domain 資料來源
  ) {
    return [Feature]ViewModel(
      domainModel: domainModel,
      // 額外欄位轉換
    );
  }

  /// 批量轉換
  static List<[Feature]ViewModel> toViewModelList(
    List<[DomainModel]> domainModels,
  ) {
    return domainModels.map((model) => toViewModel(model)).toList();
  }
}
```

### 完整範例：EnrichmentProgressMapper

```dart
import 'package:book_overview_app/domains/import/value_objects/enrichment_progress.dart';
import 'package:book_overview_app/domains/library/entities/book.dart';
import 'package:book_overview_app/presentation/import/enrichment_progress_viewmodel.dart';

/// Domain EnrichmentProgress → UI ViewModel 轉換器
///
/// 職責：
/// - 整合 EnrichmentProgress 和失敗書籍清單
/// - 轉換為 UI 層需要的 ViewModel 格式
class EnrichmentProgressMapper {
  /// 轉換 Domain 進度模型為 ViewModel
  ///
  /// 參數：
  /// - [progress]: Domain 進度模型
  /// - [failedBooks]: 失敗補充的書籍清單（從 Service 取得）
  ///
  /// 回傳：UI 層專用的 ViewModel
  static EnrichmentProgressViewModel toViewModel(
    EnrichmentProgress progress,
    List<Book> failedBooks,
  ) {
    return EnrichmentProgressViewModel(
      domainProgress: progress,
      failedBooks: failedBooks,
    );
  }

  /// 批量轉換（如果需要顯示多個進度）
  static List<EnrichmentProgressViewModel> toViewModelList(
    List<EnrichmentProgress> progressList,
    Map<String, List<Book>> failedBooksMap,
  ) {
    return progressList.map((progress) {
      // 假設每個 progress 有唯一 ID
      final failedBooks = failedBooksMap[progress.hashCode.toString()] ?? [];
      return toViewModel(progress, failedBooks);
    }).toList();
  }
}
```

---

## 🔌 Provider 整合模式

### StreamProvider 整合

**當 Domain 資料是 Stream 時使用 StreamProvider**。

```dart
/// ViewModel StreamProvider 定義
///
/// 職責：
/// - 整合多個 Domain Provider
/// - 使用 Mapper 轉換為 ViewModel
/// - 提供給 Widget 使用
final enrichmentProgressViewModelProvider =
  StreamProvider.family<EnrichmentProgressViewModel, String>(
    (ref, operationId) {
      // 1. 監聽 Domain Progress Stream
      final domainProgressStream = ref.watch(
        enrichmentProgressProvider(operationId)
      );

      // 2. 監聽失敗書籍 Stream
      final failedBooksStream = ref.watch(
        failedBooksProvider(operationId)
      );

      // 3. 合併 Stream 並轉換為 ViewModel
      return Rx.combineLatest2(
        domainProgressStream,
        failedBooksStream,
        (EnrichmentProgress progress, List<Book> failedBooks) {
          return EnrichmentProgressMapper.toViewModel(
            progress,
            failedBooks,
          );
        },
      );
    },
  );
```

### StateProvider 整合

**當 ViewModel 需要狀態管理時使用 Notifier**。

```dart
/// ViewModel State 定義
class LibraryDisplayState {
  final DisplayMode displayMode;
  final List<LibraryBookModel> books;
  final Set<String> selectedBookIds;

  const LibraryDisplayState({
    this.displayMode = DisplayMode.simple,
    this.books = const [],
    this.selectedBookIds = const {},
  });

  LibraryDisplayState copyWith({
    DisplayMode? displayMode,
    List<LibraryBookModel>? books,
    Set<String>? selectedBookIds,
  }) {
    return LibraryDisplayState(
      displayMode: displayMode ?? this.displayMode,
      books: books ?? this.books,
      selectedBookIds: selectedBookIds ?? this.selectedBookIds,
    );
  }
}

/// ViewModel Notifier
class LibraryDisplayViewModel extends Notifier<LibraryDisplayState> {
  @override
  LibraryDisplayState build() {
    return const LibraryDisplayState();
  }

  /// 切換顯示模式
  void toggleDisplayMode() {
    final newMode = state.displayMode == DisplayMode.simple
        ? DisplayMode.management
        : DisplayMode.simple;
    state = state.copyWith(displayMode: newMode);
  }

  /// 選擇書籍
  void toggleBookSelection(String bookId) {
    final selectedIds = Set<String>.from(state.selectedBookIds);
    if (selectedIds.contains(bookId)) {
      selectedIds.remove(bookId);
    } else {
      selectedIds.add(bookId);
    }
    state = state.copyWith(selectedBookIds: selectedIds);
  }
}

/// Provider 定義
final libraryDisplayViewModelProvider =
  NotifierProvider<LibraryDisplayViewModel, LibraryDisplayState>(
    LibraryDisplayViewModel.new,
  );
```

---

## 🧪 Widget 使用方式

### StreamProvider 使用

```dart
class EnrichmentProgressWidget extends ConsumerWidget {
  final String operationId;

  const EnrichmentProgressWidget({
    required this.operationId,
    super.key,
  });

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final viewModelAsync = ref.watch(
      enrichmentProgressViewModelProvider(operationId)
    );

    return viewModelAsync.when(
      data: (viewModel) => _buildProgressContent(viewModel),
      loading: () => const CircularProgressIndicator(),
      error: (error, stack) => ErrorWidget(error),
    );
  }

  Widget _buildProgressContent(EnrichmentProgressViewModel vm) {
    return Column(
      children: [
        // 使用 ViewModel 的 UI 屬性
        Icon(vm.statusIcon, color: vm.progressColor),
        Text(vm.displayStatus),
        LinearProgressIndicator(
          value: vm.progressPercentage / 100,
          color: vm.progressColor,
        ),
        Text(vm.summaryText),

        // 失敗清單
        if (vm.showFailedBooks)
          _buildFailedBooksList(vm.failedBooksSummary),
      ],
    );
  }
}
```

### StateProvider 使用

```dart
class LibraryDisplayPage extends ConsumerWidget {
  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final state = ref.watch(libraryDisplayViewModelProvider);
    final viewModel = ref.read(libraryDisplayViewModelProvider.notifier);

    return Scaffold(
      appBar: AppBar(
        title: Text('書庫'),
        actions: [
          IconButton(
            icon: Icon(Icons.view_list),
            onPressed: viewModel.toggleDisplayMode,
          ),
        ],
      ),
      body: ListView.builder(
        itemCount: state.books.length,
        itemBuilder: (context, index) {
          final book = state.books[index];
          final isSelected = state.selectedBookIds.contains(book.id);

          return ListTile(
            title: Text(book.title),
            selected: isSelected,
            onTap: () => viewModel.toggleBookSelection(book.id),
          );
        },
      ),
    );
  }
}
```

---

## ✅ 測試要求

### 單元測試覆蓋率

**每個 ViewModel 必須有單元測試，覆蓋率 ≥ 90%**。

### 測試項目

1. **Domain → UI 轉換邏輯**
2. **UI 專用計算邏輯**
3. **狀態管理邏輯**（如果是 Notifier）
4. **邊界條件和錯誤處理**

### 測試範例

```dart
import 'package:flutter_test/flutter_test.dart';
import 'package:book_overview_app/domains/import/value_objects/enrichment_progress.dart';
import 'package:book_overview_app/presentation/import/enrichment_progress_viewmodel.dart';
import 'package:book_overview_app/presentation/import/enrichment_progress_mapper.dart';

void main() {
  group('EnrichmentProgressViewModel', () {
    group('displayStatus', () {
      test('準備中 - processedBooks == 0', () {
        // Arrange
        final progress = EnrichmentProgress.initial(10);
        final vm = EnrichmentProgressMapper.toViewModel(progress, []);

        // Act & Assert
        expect(vm.displayStatus, '準備中');
      });

      test('補充中 - processedBooks > 0 且未完成', () {
        // Arrange
        final progress = EnrichmentProgress(
          totalBooks: 10,
          processedBooks: 5,
          successfulEnrichments: 5,
          failedEnrichments: 0,
        );
        final vm = EnrichmentProgressMapper.toViewModel(progress, []);

        // Act & Assert
        expect(vm.displayStatus, '補充中');
      });

      test('已完成 - processedBooks == totalBooks', () {
        // Arrange
        final progress = EnrichmentProgress(
          totalBooks: 10,
          processedBooks: 10,
          successfulEnrichments: 10,
          failedEnrichments: 0,
        );
        final vm = EnrichmentProgressMapper.toViewModel(progress, []);

        // Act & Assert
        expect(vm.displayStatus, '已完成');
      });
    });

    group('statusIcon', () {
      test('準備中 - Icons.pending', () {
        final progress = EnrichmentProgress.initial(10);
        final vm = EnrichmentProgressMapper.toViewModel(progress, []);

        expect(vm.statusIcon, Icons.pending);
      });

      test('補充中 - Icons.sync', () {
        final progress = EnrichmentProgress(
          totalBooks: 10,
          processedBooks: 5,
          successfulEnrichments: 5,
          failedEnrichments: 0,
        );
        final vm = EnrichmentProgressMapper.toViewModel(progress, []);

        expect(vm.statusIcon, Icons.sync);
      });

      test('已完成 - Icons.check_circle', () {
        final progress = EnrichmentProgress(
          totalBooks: 10,
          processedBooks: 10,
          successfulEnrichments: 10,
          failedEnrichments: 0,
        );
        final vm = EnrichmentProgressMapper.toViewModel(progress, []);

        expect(vm.statusIcon, Icons.check_circle);
      });
    });

    group('progressColor', () {
      test('有失敗 - Colors.orange', () {
        final progress = EnrichmentProgress(
          totalBooks: 10,
          processedBooks: 10,
          successfulEnrichments: 8,
          failedEnrichments: 2,
        );
        final vm = EnrichmentProgressMapper.toViewModel(progress, []);

        expect(vm.progressColor, Colors.orange);
      });

      test('已完成無失敗 - Colors.green', () {
        final progress = EnrichmentProgress(
          totalBooks: 10,
          processedBooks: 10,
          successfulEnrichments: 10,
          failedEnrichments: 0,
        );
        final vm = EnrichmentProgressMapper.toViewModel(progress, []);

        expect(vm.progressColor, Colors.green);
      });

      test('進行中 - Colors.blue', () {
        final progress = EnrichmentProgress(
          totalBooks: 10,
          processedBooks: 5,
          successfulEnrichments: 5,
          failedEnrichments: 0,
        );
        final vm = EnrichmentProgressMapper.toViewModel(progress, []);

        expect(vm.progressColor, Colors.blue);
      });
    });

    group('summaryText', () {
      test('無失敗 - 顯示處理進度', () {
        final progress = EnrichmentProgress(
          totalBooks: 10,
          processedBooks: 5,
          successfulEnrichments: 5,
          failedEnrichments: 0,
        );
        final vm = EnrichmentProgressMapper.toViewModel(progress, []);

        expect(vm.summaryText, '已處理 5/10 本');
      });

      test('有失敗 - 顯示成功和失敗數', () {
        final progress = EnrichmentProgress(
          totalBooks: 10,
          processedBooks: 10,
          successfulEnrichments: 8,
          failedEnrichments: 2,
        );
        final vm = EnrichmentProgressMapper.toViewModel(progress, []);

        expect(vm.summaryText, '已處理 10/10 本（成功 8，失敗 2）');
      });
    });
  });
}
```

---

## 📊 ViewModel 開發檢查清單

### Phase 1: 設計階段

- [ ] 確認 Domain 模型已完成
- [ ] 定義 ViewModel 需要的 UI 屬性
- [ ] 設計 Domain → UI 轉換邏輯
- [ ] 規劃 Mapper 結構
- [ ] 定義 Provider 整合方式

### Phase 2: 實作階段

- [ ] 建立 ViewModel 類別和欄位
- [ ] 實作 UI 專用計算屬性
- [ ] 實作 Mapper 轉換方法
- [ ] 定義 Provider
- [ ] 撰寫完整註解（包含需求編號）

### Phase 3: 測試階段

- [ ] 撰寫 ViewModel 單元測試
- [ ] 測試所有計算屬性
- [ ] 測試 Mapper 轉換邏輯
- [ ] 測試邊界條件
- [ ] 達成 90% 以上覆蓋率

### Phase 4: 整合階段

- [ ] Widget 整合 ViewModel Provider
- [ ] 驗證 UI 正確顯示
- [ ] 執行 Widget 測試
- [ ] Code Review 確認符合規範

---

## 🚨 常見問題和最佳實踐

### Q1: ViewModel 可以包含 StatefulWidget 的狀態嗎？

**A**: 不可以。ViewModel 應該是純資料模型，不包含 Widget 生命週期邏輯。

```dart
// ❌ 錯誤
class MyViewModel extends StatefulWidget { }

// ✅ 正確
class MyViewModel {
  final MyDomainModel domainModel;
  // 純資料模型
}
```

### Q2: 如何處理複雜的 UI 狀態？

**A**: 使用 Notifier 管理狀態，定義 State 類別。

```dart
// ✅ 正確
class MyState {
  final DisplayMode mode;
  final List<Item> items;
  final Set<String> selectedIds;

  MyState copyWith({...}) { }
}

class MyViewModel extends Notifier<MyState> { }
```

### Q3: ViewModel 可以呼叫 Domain Service 嗎？

**A**: 可以，但建議透過 Provider 整合而非直接呼叫。

```dart
// ✅ 推薦：透過 Provider 整合
final myViewModelProvider = Provider((ref) {
  final domainData = ref.watch(domainServiceProvider);
  return MyMapper.toViewModel(domainData);
});

// ⚠️ 可接受但不推薦：直接呼叫
class MyViewModel {
  final MyDomainService service;

  Future<void> fetchData() async {
    final data = await service.getData();
    // ...
  }
}
```

### Q4: 多個 Domain 模型如何整合到一個 ViewModel？

**A**: 在 Mapper 中整合多個來源。

```dart
class MyMapper {
  static MyViewModel toViewModel(
    DomainModel1 model1,
    DomainModel2 model2,
    List<Entity> entities,
  ) {
    return MyViewModel(
      field1: model1.value,
      field2: model2.value,
      items: entities.map(_mapEntity).toList(),
    );
  }
}
```

---

## 📚 參考文件

- **專案規範**: `docs/ui_design_specification.md` - MVVM 架構規格
- **既有範例**: `lib/presentation/library/library_viewmodel.dart`
- **既有範例**: `lib/presentation/viewmodels/advanced_search_viewmodel.dart`
- **Domain 模型**: `lib/domains/import/value_objects/enrichment_progress.dart`

---

**最後更新**: 2025-10-08
**版本**: 1.0.0
**狀態**: ✅ 規範建立完成
