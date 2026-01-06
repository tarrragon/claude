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

## 案例 5：網路斷線導致測試卡住（真實案例 2024/12）

**問題**：網路斷線時 flutter test 卡在 "Resolving dependencies..."，等待 pub.dev DNS 解析超時。

### 問題現象

```bash
$ flutter test

┌─────────────────────────────────────────────────────────┐
│ A new version of Flutter is available!                  │
│                                                         │
│ To update to the latest version, run "flutter upgrade". │
└─────────────────────────────────────────────────────────┘
Resolving dependencies...
Downloading packages...
=== Done ===
ClientException with SocketException: Failed host lookup: 'pub.dev' (OS Error: nodename nor servname provided, or not known, errno = 8), uri=https://pub.dev/api/packages/dio/advisories
Failed to update packages.

# 測試卡住不動...
```

### 根本原因

- 網路斷線或 DNS 解析失敗
- `flutter test` 需要連接 pub.dev 確認套件更新
- DNS 查詢失敗後，測試程序無法正常進行

### 診斷方式

```bash
# 檢查網路連線
ping -c 1 pub.dev

# 如果失敗，會看到類似：
# ping: cannot resolve pub.dev: Unknown host
```

### 修復方案

1. 確認網路連線正常
2. 重新執行測試
3. 考慮使用 `--offline` 模式（如果套件已在本地快取）：
   ```bash
   flutter test --offline
   ```

**教訓**：
- 測試卡住時，先檢查網路連線
- 這類問題無法透過程式碼修復，是環境問題

---

## 案例 6：testWidgets 中 Future.delayed 永不完成（真實案例 2024/12）

**問題**：事件測試使用 `testWidgets` 但實際上不需要 Widget 環境，導致 `Future.delayed` 永遠不會完成。

### 錯誤的實作

```dart
// ❌ 錯誤：使用 testWidgets 但不需要 Widget 環境
// 來源：search_to_library_events_test.dart

testWidgets('進行中搜尋應自動取消後重新搜尋', (tester) async {
  // 模擬搜尋耗時
  mockSearchBookUseCase.setDelay(const Duration(milliseconds: 200));

  // 發起搜尋
  await presenter.search('test');

  // 等待事件
  await Future.delayed(const Duration(milliseconds: 50));  // ⚠️ 永遠不會完成！

  // 驗證事件序列
  expect(events.length, 3);
});
```

### 問題分析

1. **testWidgets 使用虛擬時鐘**：Flutter 的 widget 測試框架使用虛擬時間
2. **Future.delayed 需要 pump**：在虛擬時間環境中，`Future.delayed` 需要 `tester.pump()` 來推進時間
3. **不需要 Widget 環境**：這個測試只驗證事件邏輯，不需要 Widget 樹

### 正確的實作

```dart
// ✅ 正確：改用 test()，因為不需要 Widget 環境

test('進行中搜尋應自動取消後重新搜尋', () async {
  // 模擬搜尋耗時
  mockSearchBookUseCase.setDelay(const Duration(milliseconds: 200));

  // 發起搜尋
  await presenter.search('test');

  // 等待事件 - 在真實時間環境中正常工作
  await Future.delayed(const Duration(milliseconds: 50));

  // 驗證事件序列
  expect(events.length, 3);
});
```

### 替代方案（如果需要 Widget 環境）

```dart
// ✅ 替代方案：使用 testWidgets + pump

testWidgets('進行中搜尋應自動取消後重新搜尋', (tester) async {
  mockSearchBookUseCase.setDelay(const Duration(milliseconds: 200));

  await presenter.search('test');

  // 使用 pump 推進虛擬時間
  await tester.pump(const Duration(milliseconds: 50));

  expect(events.length, 3);
});
```

### 判斷標準

| 情境 | 使用方式 |
|-----|---------|
| 純邏輯測試（事件、狀態） | 使用 `test()` |
| 需要 Widget 樹 | 使用 `testWidgets()` + `pump()` |
| 需要渲染驗證 | 使用 `testWidgets()` + `pumpAndSettle()` |

**教訓**：
- 選擇正確的測試類型很重要
- `testWidgets` 不是 `test` 的升級版，它有特殊的時間行為
- 純邏輯測試應該使用 `test()`

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
