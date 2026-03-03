# FLUTTER.md - Flutter 專案開發規範

本文件包含 Flutter/Dart 專案的語言特定開發規範。
通用開發規範請參考專案根目錄的 CLAUDE.md。

---

## 專案類型識別

**適用專案**: Flutter 應用程式
**自動識別**: 存在 `pubspec.yaml` 檔案
**執行代理人**: parsley-flutter-developer（Phase 3b 程式碼實作）

### Flutter 專案基本資訊
- **開發語言**: Dart
- **編譯工具**: Flutter SDK
- **測試框架**: Flutter Test / Dart Test
- **目標平台**: 依專案需求（macOS / Windows / Linux / Android / iOS / Web）
- **專案識別**: `pubspec.yaml`, `.dart` 檔案, `lib/` 目錄

---

## 開發工具鏈

### 測試指令

```bash
# 重要：統一使用 flutter test，避免 dart:ui 類型問題

# 執行所有測試
flutter test

# 執行特定測試檔案
flutter test test/path/to/specific_test.dart

# 執行測試並產生覆蓋率報告
flutter test --coverage

# 執行整合測試
flutter test integration_test/
```

### 測試執行規範（重要）

**強制要求**: 所有測試必須透過 **flutter test** 執行，**禁用 dart test**

**正確方式**:
```bash
# 正確 - 統一使用 flutter test 避免 UI 類型問題
flutter test test/path/to/specific_test.dart
flutter test test/widget/

# 正確 - 執行整合測試
flutter test integration_test/app_test.dart
```

**錯誤方式**:
```bash
# 錯誤 - 使用 dart test 會導致 dart:ui 類型缺失問題
dart test test/unit/

# 錯誤 - 使用 npm/jest（此專案是 Flutter 不是 Node.js）
npm test
npx jest test/
node test/
```

### MCP run_tests 使用限制（重要）

**問題描述**: `mcp__dart__run_tests` 在執行全部測試時會卡住超過 20 分鐘，但 `flutter test` 直接執行約 85 秒完成。

**根本原因**: MCP run_tests 在處理大量測試輸出時存在效能問題（實驗性功能）。

**強制規範**:
```bash
# 嚴格禁止 - 會卡住超過 20 分鐘
mcp__dart__run_tests (不指定 paths)

# 正確 - 指定測試子目錄，限制輸出量
mcp__dart__run_tests(roots: [{"root": "file:///path", "paths": ["test/domains/"]}])
mcp__dart__run_tests(roots: [{"root": "file:///path", "paths": ["test/unit/core/"]}])

# 推薦 - 使用 Bash 執行全量測試（最穩定）
flutter test --reporter compact
./.claude/hooks/test-summary.sh
```

**MCP run_tests 適用場景**:
| 場景 | 是否適用 | 說明 |
|------|---------|------|
| 單一測試檔案 | 適用 | 輸出量小，可正常完成 |
| 單一測試目錄 (paths) | 適用 | 如 `test/domains/`、`test/unit/core/` |
| 全部測試（無 paths）| 禁止 | 會卡住，改用 `flutter test` |

**相關文件**:
- [Dart MCP Server 官方文檔](https://docs.flutter.dev/ai/mcp-server)
- MCP 是實驗性功能，可能存在未知問題

### 全量測試執行規範（Context 保護機制）

**問題背景**: `flutter test` 完整輸出超過 4.6MB (33,000+ 行)，會耗盡對話 context，導致無法確認測試結果。

**嚴格禁止行為**:
```bash
# 嚴格禁止 - 輸出超過 4MB，會耗盡 context
flutter test
flutter test test/

# 禁止 - 整個測試目錄也會產生大量輸出
flutter test test/unit/
flutter test test/widget/
```

**正確的全量測試方式**:
```bash
# 使用摘要腳本執行全量測試（輸出 < 50KB）
./.claude/hooks/test-summary.sh

# 使用摘要腳本執行特定目錄測試
./.claude/hooks/test-summary.sh test/unit/presentation/

# 執行單一測試檔案（輸出較小，可直接執行）
flutter test test/path/to/specific_test.dart

# 使用 Dart MCP 工具執行單檔案測試
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
name: {app_name}
description: {app_description}
version: 1.0.0+1

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

## 專案結構

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

## Flutter 特定程式碼品質標準

### Widget 命名規範

- 所有 Widget 類別名稱使用 **PascalCase**
- **Stateless Widget**: `BookListWidget`, `LoadingIndicatorWidget`
- **Stateful Widget**: `BookDetailPage` + `_BookDetailPageState`
- **自訂 Widget**: 清楚描述用途（如 `EnrichmentProgressWidget`）

### State 管理模式（MVVM ViewModel）

本專案採用 **MVVM + Riverpod** 模式。

#### ViewModel 職責

| 職責 | 說明 |
|-----|------|
| Domain → UI 轉換 | 將 Domain 模型轉為 UI 格式 |
| UI 狀態管理 | 管理 Widget 狀態和互動邏輯 |
| Provider 定義 | 定義 Riverpod Provider |
| UI 專用計算 | 顏色、圖標、格式化文字 |

#### ViewModel 命名規範

- **格式**：`[Feature]ViewModel`
- **位置**：`lib/presentation/[feature]/[feature]_viewmodel.dart`
- **範例**：`EnrichmentProgressViewModel`, `LibraryDisplayViewModel`

#### ViewModel 結構範本

```dart
class EnrichmentProgressViewModel {
  // Domain 來源
  final EnrichmentProgress domainProgress;

  // UI 專用計算屬性
  String get displayStatus => _mapStatus();
  Color get progressColor => _mapColor();
  bool get canRetry => domainProgress.isComplete && failedBooks.isNotEmpty;
}

// Provider 定義
final enrichmentProgressViewModelProvider =
  StreamProvider.family<EnrichmentProgressViewModel, String>((ref, id) {...});
```

#### ViewModel 禁止事項

- 禁止 Widget 程式碼（放在 Extension）
- 禁止直接依賴 BuildContext
- 禁止業務邏輯（放在 Domain Service）

#### ViewModel 檢查清單

- [ ] 檔案位置正確（`lib/presentation/[feature]/`）
- [ ] 命名符合 `[Feature]ViewModel` 格式
- [ ] 只包含 Domain→UI 轉換，無業務邏輯
- [ ] Provider 已定義
- [ ] Widget 程式碼在 Extension 中

### ViewModel 層使用者訊息規範

**核心原則**：ViewModel 不可硬編碼使用者訊息字串。

#### 使用者訊息的三個合法來源

| 來源 | 用途 | 範例 |
|------|------|------|
| **i18n 系統** | 靜態訊息，多語言支援 | `context.l10n!.invalidFileFormat` |
| **ErrorHandler 轉換** | 動態錯誤碼對應 | `ErrorHandler.getUserMessage(exception)` |
| **Exception.message** | 僅限系統異常透傳 | `catch (e) => e.toString()` |

#### 正確做法

```dart
// 使用 i18n 系統
state = state.copyWith(errorMessage: context.l10n!.invalidFileFormat);

// 使用 ErrorHandler 轉換 ErrorCode
state = state.copyWith(
  errorMessage: ErrorHandler.getUserMessage(exception),
);

// 系統異常透傳（僅限未知異常）
catch (e) {
  state = state.copyWith(errorMessage: e.toString());
}
```

#### 錯誤做法

```dart
// 硬編碼使用者訊息
state = state.copyWith(errorMessage: 'Invalid file format');  // i18n 違規
state = state.copyWith(errorMessage: '網路連線失敗');          // i18n 違規
state = state.copyWith(errorMessage: 'Error: ${error.code}'); // 應使用 ErrorHandler
```

#### 分層責任

| 層級 | 責任 | 訊息格式 |
|------|------|----------|
| **Domain/Service** | 拋出 Exception + ErrorCode | 技術錯誤碼 |
| **ViewModel** | 將 ErrorCode 轉換為 i18n 訊息 | 使用者友善訊息 |
| **UI** | 顯示 ViewModel 提供的訊息 | 直接使用 |

#### 檢查清單

- [ ] ViewModel 無硬編碼使用者訊息字串
- [ ] 錯誤訊息使用 i18n 或 ErrorHandler
- [ ] 只有未知異常使用 `e.toString()`

**相關規範**：`.claude/skills/style-guardian/SKILL.md`

### Flutter 測試最佳實踐

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

## parsley-flutter-developer 使用指引

### 角色定位

**parsley-flutter-developer 是 Flutter/Dart 專案的 Phase 3b 程式碼實作執行者**

### 核心職責

- 接收 pepper-test-implementer 的實作策略（虛擬碼、流程圖）
- 將策略轉換為 Flutter/Dart 程式碼
- 遵循 FLUTTER.md 的語言特定規範
- 執行測試確保綠燈（100% 通過率）
- 處理 Flutter/Dart 特定問題

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
- 實作策略完整（虛擬碼、流程圖、架構決策）
- 資料流程清楚
- 錯誤處理策略明確

**交接給 Phase 4**:
- 所有 Phase 2 測試案例通過（綠燈，100%）
- Flutter 程式碼符合 FLUTTER.md 品質標準
- 實作完整記錄到工作日誌

---

## Flutter 專項文件體系

### Flutter 關鍵檔案

- `pubspec.yaml` - Flutter 套件依賴管理
- `analysis_options.yaml` - Dart 靜態分析規則

### Flutter 社群資源

- [Flutter 官方文件](https://flutter.dev/docs)
- [Dart 語言指南](https://dart.dev/guides)
- [Effective Dart](https://dart.dev/guides/language/effective-dart)
- [Flutter Widget 目錄](https://flutter.dev/docs/development/ui/widgets)
- [Flutter 測試文件](https://flutter.dev/docs/testing)

---

## 相關文件連結

**通用開發規範**: 請參考專案根目錄的 CLAUDE.md
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

*最後更新: 2026-03-04*
*版本: 2.0.0 - 泛化為通用 Flutter 模板，移除專案特定引用（0.2.0-W1-002）*
