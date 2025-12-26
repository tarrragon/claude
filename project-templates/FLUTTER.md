# FLUTTER.md - Flutter 專案開發規範

本文件包含 Flutter/Dart 專案的語言特定開發規範。
通用開發規範請參考 [`CLAUDE.md`](./CLAUDE.md)。

---

## 🚨 專案類型識別

**當前專案**: Flutter 移動應用程式
**自動識別**: 存在 `pubspec.yaml` 檔案
**執行代理人**: parsley-flutter-developer（Phase 3b 程式碼實作）

### 📱 當前專案：書庫管理 Flutter APP
- **專案類型**: Flutter 移動應用程式
- **開發語言**: Dart
- **編譯工具**: Flutter SDK
- **測試框架**: Flutter Test / Dart Test
- **目標平台**: Android (Google Play Store) / iOS (Apple App Store)
- **專案識別**: `pubspec.yaml`, `.dart` 檔案, `lib/` 目錄

---

## 🔧 開發工具鏈

### 測試指令

```bash
# 🚨 重要：統一使用 flutter test，避免 dart:ui 類型問題

# 執行所有測試
flutter test

# 執行特定測試檔案
flutter test test/unit/library/library_domain_test.dart

# 執行測試並產生覆蓋率報告
flutter test --coverage

# 執行整合測試
flutter test integration_test/

# 執行診斷測試
flutter test test/diagnostic_test.dart
```

### ⚠️ 測試執行規範（重要）

**強制要求**: 所有測試必須透過 **flutter test** 執行，**禁用 dart test**

**正確方式**:
```bash
# ✅ 正確 - 統一使用 flutter test 避免 UI 類型問題
flutter test test/unit/library/library_domain_test.dart
flutter test test/widget/

# ✅ 正確 - 執行整合測試
flutter test integration_test/app_test.dart
```

**錯誤方式**:
```bash
# ❌ 錯誤 - 使用 dart test 會導致 dart:ui 類型缺失問題
dart test test/unit/

# ❌ 錯誤 - 使用 npm/jest（此專案是 Flutter 不是 Node.js）
npm test
npx jest test/
node test/
```

### 🚨 全量測試執行規範（Context 保護機制）

**問題背景**: `flutter test` 完整輸出超過 4.6MB (33,000+ 行)，會耗盡對話 context，導致無法確認測試結果。

**嚴格禁止行為**:
```bash
# ❌ 嚴格禁止 - 輸出超過 4MB，會耗盡 context
flutter test
flutter test test/

# ❌ 禁止 - 整個測試目錄也會產生大量輸出
flutter test test/unit/
flutter test test/widget/
```

**正確的全量測試方式**:
```bash
# ✅ 使用摘要腳本執行全量測試（輸出 < 50KB）
./.claude/hooks/test-summary.sh

# ✅ 使用摘要腳本執行特定目錄測試
./.claude/hooks/test-summary.sh test/unit/presentation/

# ✅ 執行單一測試檔案（輸出較小，可直接執行）
flutter test test/unit/core/errors/common_errors_test.dart

# ✅ 使用 Dart MCP 工具執行單檔案測試
mcp__dart__run_tests (指定單一檔案)
```

**摘要腳本輸出格式**:
```text
=== 測試摘要 ===
總數: 1065 | 通過: 1045 | 失敗: 20 | 跳過: 0
執行時間: 45.2s

=== 失敗測試 (20) ===
1. test/unit/xxx_test.dart: 測試名稱
   錯誤: Expected: ... Actual: ...
```

**適用對象**: 所有代理人和主線程在執行測試時必須遵循此規範。

### 建置指令

```bash
# 安裝依賴項
flutter pub get

# 開發版本建置（Android）
flutter build apk --debug

# 生產版本建置（Android）
flutter build apk --release
flutter build appbundle --release  # Play Store 上架用

# iOS 建置
flutter build ios --release

# 程式碼生成（JSON 序列化等）
dart run build_runner build

# 清理建置產物
flutter clean
```

### 程式碼品質指令

```bash
# 執行 Dart 程式碼分析
dart analyze

# 執行 Flutter 程式碼檢查
flutter analyze

# 格式化程式碼
dart format .

# 清理依賴快取
flutter clean && flutter pub get
```

### 依賴管理

**Flutter 使用 `pubspec.yaml` 管理套件依賴**:

```yaml
# pubspec.yaml 範例
name: book_overview_app
description: 書庫管理 Flutter APP
version: 0.12.6+1

environment:
  sdk: ">=3.0.0 <4.0.0"

dependencies:
  flutter:
    sdk: flutter
  provider: ^6.0.0  # 狀態管理

dev_dependencies:
  flutter_test:
    sdk: flutter
  flutter_lints: ^2.0.0  # Lint 規則
```

---

## 📦 專案結構

### 標準目錄結構

```text
project-root/
├── lib/                    # Dart 原始碼目錄
│   ├── main.dart          # 應用程式進入點
│   ├── core/              # 核心功能（錯誤處理、工具類）
│   ├── domains/           # Domain 層（實體、Value Objects、服務）
│   ├── use_cases/         # Use Case 層（業務邏輯編排）
│   ├── presentation/      # Presentation 層（UI、ViewModel）
│   └── infrastructure/    # Infrastructure 層（Repository 實作、API 客戶端）
├── test/                  # 測試檔案目錄
│   ├── unit/             # 單元測試
│   ├── widget/           # Widget 測試
│   └── integration/      # 整合測試
├── integration_test/      # E2E 測試
├── pubspec.yaml          # 套件管理和專案配置
└── analysis_options.yaml # Dart 分析器配置
```

### 關鍵檔案說明

- **pubspec.yaml**: Flutter 專案的依賴管理和配置檔案
- **lib/main.dart**: 應用程式進入點，執行 `runApp()`
- **test/**: 所有測試檔案目錄，鏡像 `lib/` 結構
- **analysis_options.yaml**: Dart 靜態分析規則配置

---

## 🎨 Flutter 特定程式碼品質標準

### Widget 命名規範

- 所有 Widget 類別名稱使用 **PascalCase**
- **Stateless Widget**: `BookListWidget`, `LoadingIndicatorWidget`
- **Stateful Widget**: `BookDetailPage` + `_BookDetailPageState`
- **自訂 Widget**: 清楚描述用途（如 `EnrichmentProgressWidget`）

### State 管理模式

本專案採用 **Provider + ViewModel** 模式：

```dart
// ViewModel 定義
class BookListViewModel extends ChangeNotifier {
  // State 和業務邏輯
  List<Book> _books = [];

  List<Book> get books => _books;

  Future<void> loadBooks() async {
    _books = await bookRepository.getAll();
    notifyListeners();
  }
}

// Provider 註冊
ChangeNotifierProvider(
  create: (_) => BookListViewModel(),
  child: BookListPage(),
)
```

### Flutter 測試最佳實踐

詳細指南請參考：[`test/TESTING_GUIDELINES.md`](./test/TESTING_GUIDELINES.md)

**Widget 測試要點**:
- 使用 `WidgetTester` 進行 Widget 測試
- 使用 `pumpWidget()` 渲染 Widget
- 使用 `find.byType()`, `find.text()` 定位元素
- 使用 `expect()` 驗證 UI 狀態

**Mock 策略**:
- Domain 層使用 Mockito 產生 Mock
- Repository 使用介面定義，測試時注入 Mock 實作

### Dart 語言特定規範

- **導入路徑**: 使用 `package:` 開頭的絕對路徑導入
- **禁用相對路徑**: 不允許 `../../../` 相對路徑導入
- **命名規範**: 所有類別、函式、變數名稱必須正確傳達意義
- **語言標準**: 遵循 [Effective Dart](https://dart.dev/guides/language/effective-dart) 規範

---

## 🤖 parsley-flutter-developer 使用指引

### 角色定位

**parsley-flutter-developer 是 Flutter/Dart 專案的 Phase 3b 程式碼實作執行者**

### 核心職責

- ✅ 接收 pepper-test-implementer 的實作策略（虛擬碼、流程圖）
- ✅ 將策略轉換為 Flutter/Dart 程式碼
- ✅ 遵循 FLUTTER.md 的語言特定規範
- ✅ 執行測試確保綠燈（100% 通過率）
- ✅ 處理 Flutter/Dart 特定問題

### 輸入來源

- **Phase 3a 產出**: pepper 的實作策略（語言無關）
- **語言規範**: FLUTTER.md（本文件）
- **測試規格**: Phase 2 測試案例

### 執行流程

1. **閱讀實作策略**: pepper 的虛擬碼、流程圖、架構決策
2. **轉換為程式碼**: 將虛擬碼轉換為 Flutter/Dart 程式碼
3. **執行測試驗證**: 運行 `flutter test` 確保綠燈
4. **處理 Flutter 問題**: 解決 Widget 生命週期、State 管理等
5. **記錄實作結果**: 在工作日誌中記錄實作和問題

### 技能專精

- **Flutter Widget 開發**: Stateless/Stateful Widget、自訂 Widget
- **Dart 語言特性**: async/await、Stream、Future、Extension
- **Flutter 測試框架**: WidgetTester、Mockito、Integration Test
- **Flutter 專案結構**: Clean Architecture 在 Flutter 中的實現
- **狀態管理**: Provider、ChangeNotifier、ViewModel 模式

### 交接檢查點

**從 Phase 3a 接收**:
- ✅ 實作策略完整（虛擬碼、流程圖、架構決策）
- ✅ 資料流程清楚
- ✅ 錯誤處理策略明確

**交接給 Phase 4**:
- ✅ 所有 Phase 2 測試案例通過（綠燈，100%）
- ✅ Flutter 程式碼符合 FLUTTER.md 品質標準
- ✅ 實作完整記錄到工作日誌

---

## 📚 Flutter 專項文件體系

### Flutter 特定文件

- [`test/TESTING_GUIDELINES.md`](./test/TESTING_GUIDELINES.md) - Widget 測試指導原則
- [`docs/ui_design_specification.md`](./docs/ui_design_specification.md) - UI 設計規格書（包含 Flutter Widget 規範）
- `pubspec.yaml` - Flutter 套件依賴管理
- `analysis_options.yaml` - Dart 靜態分析規則

### Flutter 社群資源

- [Flutter 官方文件](https://flutter.dev/docs)
- [Dart 語言指南](https://dart.dev/guides)
- [Effective Dart](https://dart.dev/guides/language/effective-dart)
- [Flutter Widget 目錄](https://flutter.dev/docs/development/ui/widgets)
- [Flutter 測試文件](https://flutter.dev/docs/testing)

### 專案特定 Flutter 規範

- [事件驅動架構在 Flutter 中的實現](./docs/event-driven-architecture-design.md)
- [Domain 轉換層設計](./docs/domain-transformation-layer-design.md)
- [JSON 序列化規範](./docs/json-serialization-specification.md)
- [Value Objects 序列化目錄](./docs/value-objects-serialization-catalog.md)

---

## 🔗 相關文件連結

**通用開發規範**: 請參考 [`CLAUDE.md`](./CLAUDE.md)
- TDD 四階段流程
- 5W1H 決策框架
- Hook 系統機制
- 敏捷重構方法論
- 文件管理規範

**通用代理人**: 可跨語言/框架重用
- lavender-interface-designer (Phase 1 功能設計)
- sage-test-architect (Phase 2 測試設計)
- pepper-test-implementer (Phase 3a 策略規劃)
- cinnamon-refactor-owl (Phase 4 重構評估)
- rosemary-project-manager (PM 統籌)

---

*最後更新: 2025-10-09*
*版本: 1.0.0*
*專案類型: Flutter 移動應用程式*
