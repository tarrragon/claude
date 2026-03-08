# Dart/Flutter 品質規則

本文件為 Dart/Flutter 語言的品質規則補充。通用規則見 quality-common.md。

> **適用代理人**：parsley-flutter-developer

---

## 1. Package 導入

```dart
// 正確：package 格式
import 'package:book_overview_app/domains/library/entities/book.dart';

// 錯誤：相對路徑
import '../entities/book.dart';
```

- 100% 使用 `package:book_overview_app/` 格式
- 禁用 `as` 別名，重構命名解決衝突
- 測試檔案同樣使用 package 格式

> 完整方法論：.claude/methodologies/package-import-methodology.md

---

## 2. 常數集中管理（強制）

> **核心原則**：程式碼中禁止任何硬編碼數值或字串，所有常數集中在 `lib/core/constants/` 管理。

```
ui/lib/core/constants/
├── app_constants.dart      # 全域常數（Panel 數量上限等）
├── duration_constants.dart # 時間常數（重連間隔、心跳等）
└── style_constants.dart    # 樣式數值常數
```

正確做法：

```dart
if (panels.length > AppConstants.maxSplitPanels)
Future.delayed(DurationConstants.reconnectInitialDelay)
```

錯誤做法（魔法數字/字串）：

```dart
if (panels.length > 4)
Future.delayed(Duration(seconds: 1))
```

---

## 3. i18n 多語系管理（強制）

> **核心原則**：UI 中禁止任何硬編碼顯示文字，所有使用者可見字串透過 ARB/l10n 系統。

```
ui/lib/l10n/
├── app_en.arb      # 英文（預設）
└── app_zh_TW.arb   # 繁體中文
```

正確做法：

```dart
Text(context.l10n.sessionListTitle)
Text(context.l10n.connectionStatusConnected)
```

錯誤做法：

```dart
Text('Session List')
Text('Connected')
```

**適用範圍**：Widget 文字、錯誤提示、按鈕標籤、狀態文字

**例外**：開發者 log、測試斷言、技術標識符（package name 等）

---

## 4. i18n 管理 — ViewModel 層

**ViewModel 層三個合法訊息來源**：

| 來源 | 用途 | 範例 |
|------|------|------|
| i18n 系統 | 靜態訊息 | `context.l10n!.invalidFileFormat` |
| ErrorHandler | 錯誤碼對應 | `ErrorHandler.getUserMessage(exception)` |
| Exception.message | 僅限系統異常透傳 | `catch (e) => e.toString()` |

**分層責任**：

| 層級 | 責任 | 禁止 |
|------|------|------|
| Domain/Service | 拋出 Exception + ErrorCode | 使用 i18n、硬編碼訊息 |
| ViewModel | ErrorCode → i18n 訊息 | 硬編碼使用者訊息 |
| UI | 顯示 ViewModel 提供的訊息 | 自行組裝訊息 |

> 完整方法論：.claude/methodologies/business-layer-i18n-management-methodology.md

---

## 5. 錯誤處理

正確做法（使用預編譯錯誤）：

```dart
throw CommonErrors.titleRequired;
throw BusinessException.duplicate(book.isbn);
```

錯誤做法（字串拋出）：

```dart
throw 'Title is required';
throw Exception('Book already exists');
```

---

## 6. Lint 規則

由 `analysis_options.yaml` 強制執行：

| 規則 | 說明 |
|------|------|
| `avoid_print: true` | 使用 AppLogger/TestLogger |
| `prefer_single_quotes: true` | 統一使用單引號 |
| `prefer_const_constructors: true` | 優先使用 const |
| `prefer_final_locals: true` | 區域變數優先 final |

---

## 7. Dart/Flutter 品質檢查清單

（在通用清單基礎上追加）

- [ ] 100% package 格式導入
- [ ] 所有常數集中在 `lib/core/constants/`，無魔法數字
- [ ] UI 文字全部透過 l10n，無硬編碼顯示文字
- [ ] ViewModel 無硬編碼使用者訊息
- [ ] 錯誤使用預編譯 Exception
- [ ] `dart analyze` 0 issues
- [ ] 測試 100% 通過

---

## 相關文件

- .claude/rules/core/quality-common.md - 通用品質基線
- .claude/methodologies/package-import-methodology.md - 導入路徑方法論
- .claude/methodologies/business-layer-i18n-management-methodology.md - i18n 方法論

---

**Last Updated**: 2026-03-08
**Version**: 1.0.0 - 從 implementation-quality.md 拆分（W13-007）
