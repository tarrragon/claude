# Async Cleanup Patterns - 異步資源清理模式參考

本文檔包含從專案中提取的真實案例，展示正確和錯誤的異步資源管理模式。

## 案例 1：book_query_service_test.dart

**問題**：測試啟動 10 秒延遲查詢，但只等待 10ms 就結束，且沒有 tearDown 清理。

### 錯誤的實作

```dart
// ❌ 錯誤：沒有 tearDown 清理
setUp(() {
  mockApiService = MockBookInfoApiService();
  bookQueryService = BookQueryService(apiService: mockApiService);
});

test('應該能取消進行中的查詢', () async {
  // 安排一個 10 秒延遲的查詢
  when(mockApiService.queryByIsbn('9781234567890'))
      .thenAnswer((_) async {
    await Future.delayed(const Duration(seconds: 10));
    return sampleBookData;
  });

  // 啟動查詢但只等待 10ms
  unawaited(bookQueryService.queryByIsbn('9781234567890'));
  await Future.delayed(const Duration(milliseconds: 10));

  // 測試結束，但 Future 還在運行！
  // 這會導致測試框架等待 10 秒
});
```

### 正確的實作

```dart
// ✅ 正確：添加 tearDown 清理
setUp(() {
  mockApiService = MockBookInfoApiService();
  bookQueryService = BookQueryService(apiService: mockApiService);
});

tearDown(() {
  // 清理所有未完成的查詢，避免測試卡住
  bookQueryService.clearAllQueries();
});

test('應該能取消進行中的查詢', () async {
  // 縮短延遲為 200ms（足夠測試邏輯但不阻塞）
  when(mockApiService.queryByIsbn('9781234567890'))
      .thenAnswer((_) async {
    await Future.delayed(const Duration(milliseconds: 200));
    return sampleBookData;
  });

  unawaited(bookQueryService.queryByIsbn('9781234567890'));
  await Future.delayed(const Duration(milliseconds: 10));

  bookQueryService.cancelQuery('9781234567890');
  // tearDown 會確保清理任何殘留的查詢
});
```

**修復要點**：
1. 添加 `tearDown` 調用 `clearAllQueries()`
2. 將 10 秒延遲縮短為 200ms

---

## 案例 2：batch_enrich_view_model_behavior_test.dart

**問題**：Mock 設置了慢速模式但沒有在 tearDown 中重置，導致影響後續測試。

### 錯誤的實作

```dart
// ❌ 錯誤：沒有重置 Mock 慢速模式
setUp(() {
  mockSearchViewModel = MockSearchBookViewModelForBatch();
  mockBookRepository = MockBookRepository();
  mockBatchEnrichBooksUseCase = MockBatchEnrichBooksUseCase();
});

test('Test 5: 取消批次 - processing → cancelled', () async {
  // 設定 Mock 為慢速執行
  mockSearchViewModel.setSlowSearch(true);
  mockBookRepository.setSlowQuery(true);
  mockBatchEnrichBooksUseCase.setFastExecution(false);

  // ... 測試邏輯 ...

  // 測試結束但沒有重置，影響後續測試
});
```

### 正確的實作

```dart
// ✅ 正確：在 tearDown 中重置所有 Mock 設置
setUp(() {
  mockSearchViewModel = MockSearchBookViewModelForBatch();
  mockBookRepository = MockBookRepository();
  mockBatchEnrichBooksUseCase = MockBatchEnrichBooksUseCase();
});

tearDown(() {
  // 重置所有 Mock 的慢速模式設置，避免影響後續測試
  mockSearchViewModel.setSlowSearch(false);
  mockBookRepository.setSlowQuery(false);
  mockBatchEnrichBooksUseCase.setFastExecution(true);
  container.dispose();
});

test('Test 5: 取消批次 - processing → cancelled', () async {
  mockSearchViewModel.setSlowSearch(true);
  mockBookRepository.setSlowQuery(true);
  mockBatchEnrichBooksUseCase.setFastExecution(false);

  // ... 測試邏輯 ...

  // tearDown 會自動重置
});
```

**修復要點**：
1. 在 `tearDown` 中重置所有 Mock 的慢速模式設置
2. 調用 `container.dispose()` 清理資源

---

## 案例 3：performance_monitor.dart

**問題**：Timer.periodic 沒有在 dispose 中取消。

### 錯誤的實作

```dart
// ❌ 錯誤：Timer 沒有保存引用，無法取消
class PerformanceMonitor {
  void startMemoryMonitoring({Duration interval = const Duration(milliseconds: 500)}) {
    // Timer 沒有保存引用
    Timer.periodic(interval, (_) {
      _captureMemorySnapshot();
    });
  }

  void dispose() {
    // 無法取消 Timer！
  }
}
```

### 正確的實作

```dart
// ✅ 正確：保存 Timer 引用並在 dispose 中取消
class PerformanceMonitor {
  Timer? _memoryMonitorTimer;
  Timer? _frameRateMonitorTimer;

  void startMemoryMonitoring({Duration interval = const Duration(milliseconds: 500)}) {
    _stopMemoryMonitoring();  // 先停止之前的
    _memoryMonitorTimer = Timer.periodic(interval, (_) {
      _captureMemorySnapshot();
    });
  }

  void _stopMemoryMonitoring() {
    _memoryMonitorTimer?.cancel();
    _memoryMonitorTimer = null;
  }

  void dispose() {
    _stopMemoryMonitoring();
    _stopFrameRateMonitoring();
  }
}
```

**修復要點**：
1. 保存 Timer 引用到實例變數
2. 提供 `_stopXxx()` 方法
3. 在 `dispose()` 中調用所有停止方法

---

## 案例 4：mock_services.dart StreamController

**問題**：StreamController 沒有在 dispose 中關閉。

### 錯誤的實作

```dart
// ❌ 錯誤：StreamController 沒有 dispose 方法
class MockBookEnrichmentService implements IBookInfoEnrichmentService {
  final StreamController<EnrichmentProgress> _progressController =
      StreamController<EnrichmentProgress>.broadcast();

  @override
  Stream<EnrichmentProgress> enrichmentProgressStream() {
    return _progressController.stream;
  }

  // 沒有 dispose 方法！
}
```

### 正確的實作

```dart
// ✅ 正確：添加 dispose 方法關閉 StreamController
class MockBookEnrichmentService implements IBookInfoEnrichmentService {
  final StreamController<EnrichmentProgress> _progressController =
      StreamController<EnrichmentProgress>.broadcast();

  @override
  Stream<EnrichmentProgress> enrichmentProgressStream() {
    return _progressController.stream;
  }

  void dispose() {
    _progressController.close();
  }
}

// 在測試中使用
tearDown(() {
  mockBookEnrichmentService.dispose();
});
```

**修復要點**：
1. 為包含 StreamController 的類添加 `dispose()` 方法
2. 在 `dispose()` 中調用 `controller.close()`
3. 在測試的 `tearDown` 中調用 `dispose()`

---

## 最佳實踐總結

### 1. 始終添加 tearDown

每個測試 group 都應該有對應的 `tearDown`：

```dart
group('MyService Tests', () {
  late MyService service;

  setUp(() {
    service = MyService();
  });

  tearDown(() {
    service.dispose();  // 或其他清理方法
  });

  // 測試...
});
```

### 2. 縮短測試延遲

測試中的延遲應該盡可能短：

| 用途 | 建議延遲 |
|-----|---------|
| 驗證取消邏輯 | 100-200ms |
| 驗證超時邏輯 | 比超時設定長 50-100ms |
| 驗證異步順序 | 10-50ms |

### 3. Mock 類應實作 dispose

所有使用 Timer、StreamController 或其他異步資源的 Mock 類都應該：

1. 保存資源引用
2. 提供 `dispose()` 方法
3. 在 `dispose()` 中清理所有資源

### 4. 檢查清單

撰寫測試時，確認：

- [ ] 每個 group 都有 `tearDown`
- [ ] 長延遲已縮短或有清理機制
- [ ] Timer.periodic 有對應的 `cancel()`
- [ ] StreamController 有對應的 `close()`
- [ ] Mock 慢速模式在 tearDown 中重置
