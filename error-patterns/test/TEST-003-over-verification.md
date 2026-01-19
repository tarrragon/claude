# TEST-003: 過度驗證超出責任

## 基本資訊

- **Pattern ID**: TEST-003
- **分類**: 測試設計
- **來源版本**: v0.6.2
- **發現日期**: 2025-01-13
- **風險等級**: 中

## 問題描述

### 症狀

測試跨越多個組件的責任，導致：
- 測試難以維護
- 測試失敗原因難以定位
- 組件修改會破壞不相關的測試

```dart
// Import Widget 測試
test('should complete import flow', () async {
  // 執行匯入...

  // 驗證 Import Widget 責任範圍內的項目（正確）
  expect(find.textContaining('成功匯入'), findsOneWidget);

  // 驗證 Library Widget 責任範圍的項目（錯誤）
  expect(find.byKey(const Key('library_simple_mode')), findsOneWidget);
  expect(find.text('大腦不滿足'), findsOneWidget);
  expect(find.byKey(const Key('platform_icon_readmoo')), findsAtLeastNWidgets(2));

  // 驗證背景服務責任範圍的項目（錯誤）
  expect(find.byKey(const Key('api_loading_indicator')), findsAtLeastNWidgets(1));
});
```

### 根本原因 (5 Why 分析)

1. Why 1: Import Widget 測試驗證了 Library Widget 的行為
2. Why 2: 測試設計時沒有明確區分組件責任
3. Why 3: 想要「順便」驗證更多功能
4. Why 4: 認為整合測試應該驗證所有相關功能
5. Why 5: **測試責任邊界不清晰，混淆了「整合」與「什麼都測」**

## 解決方案

### 正確做法

每個測試只驗證其直接責任範圍：

```dart
// Import Widget 測試
test('should complete import flow', () async {
  // 執行匯入...

  // 只驗證 Import Widget 直接責任的項目
  expect(
    find.textContaining('成功匯入'),
    findsOneWidget,
    reason: '完成後應顯示成功訊息',
  );

  // 驗證資料層（透過 Mock 或 Repository）
  final importedBooks = await mockServices.databaseService.getAllBooks();
  expect(importedBooks.length, equals(5), reason: '應匯入 5 本書籍');
});

// Library Widget 測試（獨立測試）
test('should display imported books', () async {
  // 預先設定資料庫有書籍
  await setupBooksInDatabase(5);

  // 驗證 Library Widget 的顯示
  expect(find.byKey(const Key('library_simple_mode')), findsOneWidget);
  expect(find.text('大腦不滿足'), findsOneWidget);
});
```

### 錯誤做法 (避免)

```dart
// 錯誤：在一個測試中驗證多個組件
test('should complete import and show in library', () async {
  await performImport();

  // 驗證 Import Widget（正確）
  expect(find.textContaining('成功'), findsOneWidget);

  // 驗證 Library Widget（越界）
  expect(find.byKey(const Key('library_view')), findsOneWidget);

  // 驗證 Search Widget（越界）
  expect(find.byKey(const Key('search_results')), findsWidgets);

  // 驗證 Background Service（越界）
  expect(mockApiService.callCount, greaterThan(0));
});
```

## 責任邊界判斷

| 組件 | 責任範圍 |
|------|---------|
| Import Widget | 檔案選擇、驗證、匯入進度、成功/失敗訊息 |
| Library Widget | 書籍列表顯示、平台圖標、模式切換 |
| Search Widget | 搜尋輸入、結果顯示 |
| Background Service | API 呼叫、資料豐富化 |

## 檢查清單

在撰寫測試時，確認：

- [ ] 測試名稱是否準確反映測試範圍？
- [ ] 驗證項目是否都在測試目標的直接責任內？
- [ ] 是否可以將某些驗證移到其他測試？
- [ ] 測試失敗時，能否立即確定問題組件？

## 相關資源

- 工作日誌: `docs/work-logs/v0.6.2-chrome-extension-import-tdd-phase2-test-design.md`
- 行為優先 TDD 方法論: `.claude/methodologies/behavior-first-tdd-methodology.md`
- Sociable Unit Tests 概念

## 標籤

`#測試` `#責任邊界` `#整合測試` `#組件測試` `#測試設計`
