# TEST-002: 測試流程不完整

## 基本資訊

- **Pattern ID**: TEST-002
- **分類**: 測試設計
- **來源版本**: v0.6.2
- **發現日期**: 2025-01-13
- **風險等級**: 高

## 問題描述

### 症狀

測試邏輯看似完整，但測試永遠無法完成或驗證失敗：

```dart
// 測試流程
// 1. 點擊選擇檔案按鈕
await tester.tap(find.byKey(const Key('import_data_button')));
await tester.pumpAndSettle();

// 2. 等待匯入完成（永遠不會發生）
await waitForImportComplete();
```

### 根本原因 (5 Why 分析)

1. Why 1: 測試等待匯入完成，但匯入從未開始
2. Why 2: 只點擊了「選擇檔案」按鈕，沒有點擊「開始匯入」按鈕
3. Why 3: 測試設計時忽略了 UI 的兩步驟流程
4. Why 4: 假設選擇檔案後會自動開始匯入
5. Why 5: **假設某個步驟會自動發生，未完整追蹤使用者流程**

## 解決方案

### 正確做法

完整覆蓋使用者流程：

```dart
// 1. 點擊選擇檔案按鈕
final selectFileButton = find.byKey(const Key('import_data_button'));
await tester.tap(selectFileButton);
await tester.pumpAndSettle(const Duration(seconds: 2));

// 2. 等待匯入按鈕出現（檔案驗證完成）
await tester.pumpAndSettle(const Duration(seconds: 2));

// 3. 點擊開始匯入按鈕（這是關鍵步驟）
final startImportButton = find.widgetWithText(
  ElevatedButton,
  '開始匯入',
);
expect(startImportButton, findsOneWidget,
    reason: '檔案驗證通過後應顯示開始匯入按鈕');

await tester.tap(startImportButton);
await tester.pumpAndSettle(const Duration(seconds: 1));

// 4. 等待匯入完成
await waitForImportComplete();
```

### 錯誤做法 (避免)

```dart
// 錯誤：假設選擇檔案後會自動匯入
await tester.tap(find.byKey(const Key('import_data_button')));
await waitForImportComplete(); // 永遠不會完成

// 錯誤：跳過中間步驟
await selectFile();
await verifyImportResult(); // 匯入從未開始
```

## 檢查清單

在撰寫整合測試時，確認：

- [ ] 是否完整模擬了使用者的操作流程？
- [ ] 每個 UI 互動是否都明確觸發？
- [ ] 是否有「隱藏步驟」被假設會自動發生？
- [ ] 流程中的每個狀態轉換是否都被驗證？

## 流程驗證方法

1. **手動操作一次**: 在模擬器中手動執行一次完整流程
2. **記錄每個點擊**: 列出每個按鈕、輸入框的互動
3. **檢查狀態轉換**: 確認每個狀態變化都有對應的測試步驟
4. **加入等待點**: 在每個步驟後加入適當的等待

## 相關資源

- 工作日誌: `docs/work-logs/v0.6.2-chrome-extension-import-tdd-phase2-test-design.md`
- 測試設計反模式: `.claude/test-design-antipatterns.md`

## 標籤

`#測試` `#流程完整性` `#整合測試` `#使用者流程` `#UI測試`
