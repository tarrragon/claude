# TEST-001: 錯誤的等待機制

## 基本資訊

- **Pattern ID**: TEST-001
- **分類**: 測試設計
- **來源版本**: v0.6.2
- **發現日期**: 2025-01-13
- **風險等級**: 高

## 問題描述

### 症狀

整合測試永遠等待超時，即使邏輯看似正確：

```dart
// 測試等待這個條件
await TestEnvironmentSetup.waitUntil(
  () => mockServices.progressNotificationService.latestProgress == 1.0,
  timeout: const Duration(seconds: 15),
);
```

測試永遠無法通過，因為條件永遠不會滿足。

### 根本原因 (5 Why 分析)

1. Why 1: 測試等待 `progressNotificationService.latestProgress == 1.0`
2. Why 2: 但 ViewModel 使用 `state.importProgress` 管理進度
3. Why 3: ViewModel 從不直接更新 `progressNotificationService`
4. Why 4: 測試設計時假設 Mock 服務會被更新
5. Why 5: **混淆了「實際狀態管理方式」與「假設的狀態管理方式」**

## 解決方案

### 正確做法

使用 UI 可觀察的行為作為等待條件：

```dart
// 正確：等待 UI 文字出現
await TestEnvironmentSetup.waitUntil(
  () {
    final successMessages = find.textContaining('成功匯入');
    return successMessages.evaluate().isNotEmpty;
  },
  timeout: const Duration(seconds: 15),
  reason: '匯入應在 15 秒內完成',
);
```

### 錯誤做法 (避免)

```dart
// 錯誤：等待 Mock 服務的內部狀態
await TestEnvironmentSetup.waitUntil(
  () => mockServices.progressNotificationService.latestProgress == 1.0,
  timeout: const Duration(seconds: 15),
);

// 錯誤：等待不會被更新的狀態
await TestEnvironmentSetup.waitUntil(
  () => mockService.someInternalState == expectedValue,
  timeout: const Duration(seconds: 15),
);
```

## 檢查清單

在撰寫測試等待條件時，確認：

- [ ] 等待的狀態是否真的會被測試目標更新？
- [ ] 是否可以用 UI 可觀察的行為替代？
- [ ] Mock 服務是否正確連接到被測試的元件？

## 相關 Ticket

| Ticket ID | 狀態 | 說明 |
|-----------|------|------|
| 0.25.1-W1-001 | pending | 修復 UC-01 替代流程測試等待機制 |

## 相關資源

- 工作日誌: `docs/work-logs/v0.6.2-chrome-extension-import-tdd-phase2-test-design.md`
- 行為優先 TDD 方法論: `.claude/methodologies/behavior-first-tdd-methodology.md`
- Ticket: `docs/work-logs/v0.25.1/tickets/0.25.1-W1-001.md`

## 標籤

`#測試` `#等待機制` `#Mock` `#整合測試` `#狀態管理`
