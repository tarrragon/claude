# W2-002 實作執行檢查清單

## 修復計劃概覽

```
目標: 修復 324+ Widget/Integration 測試失敗
計劃: 三階段 + 文檔更新
預計成果: ~90% 的失敗測試應該通過
總時間: 3-4 小時
```

---

## 第一階段: 改進 TestApp (P0 - 優先級最高)

### 目標
- 修復 101 個使用 `pumpTestWidget` 的測試
- 預期修復 92% 的 ScreenUtil 相關錯誤

### 檢查清單

#### 1️⃣ 備份原始檔案
- [ ] 備份 `test/presentation/version_management/helpers/test_app.dart`

#### 2️⃣ 修改 TestApp 實作

**檔案**: `test/presentation/version_management/helpers/test_app.dart`

**步驟**:
1. [ ] 加入 `ScreenUtilInit` 匯入
2. [ ] 加入 `ProviderScope` 匯入
3. [ ] 加入 `AppLocalizations` 匯入
4. [ ] 用 `ScreenUtilInit` 包裝 `MaterialApp`
5. [ ] 用 `ProviderScope` 包裝 `MaterialApp`
6. [ ] 加入 `localizationsDelegates` 和 `supportedLocales`

**所需匯入**:
```dart
import 'package:flutter_screenutil/flutter_screenutil.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:book_overview_app/l10n/generated/app_localizations.dart';
```

**程式碼變更**:
```dart
// 舊代碼
class TestApp extends StatelessWidget {
  final Widget child;
  final ThemeData? theme;

  const TestApp({
    super.key,
    required this.child,
    this.theme,
  });

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      home: Scaffold(
        body: child,
      ),
      theme: theme ?? ThemeData.light(),
      debugShowCheckedModeBanner: false,
    );
  }
}

// 新代碼
class TestApp extends StatelessWidget {
  final Widget child;
  final ThemeData? theme;
  final Locale locale;

  const TestApp({
    super.key,
    required this.child,
    this.theme,
    this.locale = const Locale('zh', 'TW'),
  });

  @override
  Widget build(BuildContext context) {
    return ScreenUtilInit(
      designSize: const Size(375, 812),
      minTextAdapt: true,
      splitScreenMode: true,
      builder: (context, _) => ProviderScope(
        child: MaterialApp(
          locale: locale,
          localizationsDelegates: AppLocalizations.localizationsDelegates,
          supportedLocales: AppLocalizations.supportedLocales,
          home: Scaffold(
            body: child,
          ),
          theme: theme ?? ThemeData.light(),
          debugShowCheckedModeBanner: false,
        ),
      ),
    );
  }
}
```

#### 3️⃣ 更新擴展方法

**檔案**: 同上 (test/presentation/version_management/helpers/test_app.dart)

**更新**: `WidgetTestHelpers` 擴展的 `pumpTestWidget` 方法

```dart
// 舊代碼
Future<void> pumpTestWidget(Widget widget) async {
  await pumpWidget(TestApp(child: widget));
}

// 新代碼
Future<void> pumpTestWidget(Widget widget, {Locale? locale}) async {
  await pumpWidget(TestApp(
    child: widget,
    locale: locale ?? const Locale('zh', 'TW'),
  ));
}
```

#### 4️⃣ 驗證修改

- [ ] 檢查 Dart 分析無錯誤
- [ ] 執行 `flutter pub get`
- [ ] 運行單個版本管理測試驗證:
  ```bash
  flutter test test/presentation/version_management/widgets/version_indicator_test.dart
  ```
- [ ] 驗證至少 5 個 pumpTestWidget 測試通過

#### 5️⃣ 預期結果

✅ 所有使用 `pumpTestWidget` 的測試應該通過 (101 個)

---

## 第二階段: 統一 createTestApp 使用 (P1 - 高優先級)

### 目標
- 修復 28 個使用 `createTestApp` 或 `_createTestApp` 的測試
- 統一使用 `createFullTestApp` 或 `createTestAppWithProviders`

### 關鍵檔案清單

#### 需要修改的檔案 (17 個)

```
test/widget/library/
├─ [ ] library_display_widget_test.dart
├─ [ ] book_list_item_selection_manager_test.dart
├─ [ ] book_list_item_haptic_test.dart
├─ [ ] book_list_item_shadow_test.dart
├─ [ ] book_list_item_details_button_test.dart
├─ [ ] book_list_item_accessibility_test.dart
└─ [ ] display_mode_toggle_button_test.dart (6 個)

test/widget/multilingual/
├─ [ ] isbn_scanner_widget_multilingual_test.dart
├─ [ ] book_search_widget_multilingual_test.dart
└─ [ ] multilingual_integration_test.dart (3 個)

test/unit/presentation/sync/
├─ [ ] sync_settings_page_test.dart
└─ [ ] widgets/* (8 個)
```

#### 本地 `_createTestApp` 定義 (11 個檔案)

```
需要搜尋和替換:
├─ [ ] test/widget/import/local_import_widget_test.dart
├─ [ ] test/widget/design_compliance/*.dart (5 個)
├─ [ ] test/widget/presentation/search/*.dart (4+個)
└─ [ ] 其他使用本地 _createTestApp 的檔案
```

### 修改步驟

#### 1️⃣ 批量搜尋所有 createTestApp 使用

```bash
# 搜尋所有 createTestApp 使用
grep -r "createTestApp" test/ --include="*_test.dart" \
  | grep -v "createTestAppWithProviders\|createFullTestApp\|createTestApp(" \
  | head -30

# 搜尋所有 _createTestApp 定義
grep -r "_createTestApp" test/ --include="*_test.dart" -n
```

#### 2️⃣ 逐個檢查和修改

**模式 1: 簡單替換**

```dart
// ❌ 當前
await tester.pumpWidget(
  WidgetTestHelper.createTestApp(const MyWidget()),
);

// ✅ 修改為
await tester.pumpWidget(
  WidgetTestHelper.createFullTestApp(const MyWidget()),
);
```

**步驟**:
1. [ ] 開啟檔案
2. [ ] 搜尋 `createTestApp(`
3. [ ] 檢查是否需要 `ProviderScope` override
   - 如果有 `overrides:` → 保留外層 `ProviderScope`
   - 如果沒有 → 直接替換為 `createFullTestApp`
4. [ ] 刪除多餘的包裝層次
5. [ ] 執行測試驗證

**模式 2: 本地 _createTestApp 定義**

```dart
// ❌ 當前
Widget _createTestApp(Widget child) {
  return WidgetTestHelper.createScreenUtilTestWrapper(
    child: ProviderScope(
      overrides: [libraryProvider.overrideWith(...)],
      child: WidgetTestHelper.createTestApp(child),
    ),
  );
}

// ✅ 簡化為
Widget _createTestApp(Widget child) {
  return ProviderScope(
    overrides: [libraryProvider.overrideWith(...)],
    child: WidgetTestHelper.createFullTestApp(child),
  );
}
// 或完全刪除 _createTestApp，直接在測試中使用
```

**步驟**:
1. [ ] 移除 `createScreenUtilTestWrapper`
2. [ ] 移除多層 `WidgetTestHelper.createXxx` 嵌套
3. [ ] 只保留必要的 `ProviderScope` (如果有 override)

#### 3️⃣ 檢查清單 (每個檔案)

針對每個修改的檔案:

- [ ] 刪除了多餘的包裝層次?
- [ ] `ProviderScope` override 位置正確?
- [ ] 移除了重複的 `MaterialApp` / `Scaffold`?
- [ ] 移除了多餘的 `ScreenUtilInit`?
- [ ] Dart 分析無錯誤?
- [ ] 測試通過?

#### 4️⃣ 驗證修改

```bash
# 運行所有修改過的測試
flutter test test/widget/library/

# 運行所有多語系測試
flutter test test/widget/multilingual/

# 運行同步相關測試
flutter test test/unit/presentation/sync/
```

#### 5️⃣ 預期結果

✅ 28 個測試應該通過 (createTestApp + _createTestApp)

---

## 第三階段: 統一多語系測試 (P2 - 中優先級)

### 目標
- 統一 Localization 設定
- 修復 40% 的多語系相關失敗

### 檢查清單

#### 1️⃣ 搜尋所有 Localization 配置

```bash
# 搜尋所有自訂 locale 配置
grep -r "locale:" test/ --include="*_test.dart" | wc -l

# 搜尋 WidgetTestEnvironment 使用
grep -r "WidgetTestEnvironment" test/ --include="*_test.dart"

# 搜尋 localizationsDelegates 配置
grep -r "localizationsDelegates" test/ --include="*_test.dart"
```

#### 2️⃣ 批量替換策略

**情況 1: 使用 WidgetTestEnvironment**

```dart
// ❌ 當前
await tester.pumpWidget(
  WidgetTestEnvironment.createTestEnvironment(
    child: MyWidget(),
  ),
);

// ✅ 改為
await tester.pumpWidget(
  WidgetTestHelper.createFullTestApp(MyWidget()),
);
```

**情況 2: 手動 MaterialApp 配置**

```dart
// ❌ 當前
MaterialApp(
  locale: const Locale('zh', 'TW'),
  localizationsDelegates: const [...],
  supportedLocales: const [...],
  ...
)

// ✅ 改為
WidgetTestHelper.createFullTestApp(
  MyWidget(),
  locale: const Locale('zh', 'TW'),
)
```

#### 3️⃣ 多語系測試標準化

```dart
// ✅ 標準多語系測試模式
testWidgets('test_name_multilingual', (tester) async {
  const testLocales = [
    Locale('en', 'US'),
    Locale('zh', 'TW'),
    Locale('ja', 'JP'),
  ];

  for (final locale in testLocales) {
    await tester.pumpWidget(
      WidgetTestHelper.createFullTestApp(
        MyWidget(),
        locale: locale,
      ),
    );

    // 每個 locale 的驗證
    expect(find.byType(MyWidget), findsOneWidget);
  }
});
```

#### 4️⃣ 驗證修改

```bash
flutter test test/widget/multilingual/ -v
```

#### 5️⃣ 預期結果

✅ 所有多語系測試應該使用統一的 `createFullTestApp` 方式

---

## 第四階段: 決定流程測試佔位符 (可選)

### 目標
處理 test/widget/flows/user_interaction_flow_test.dart 中的 25 個 fail() 佔位符

### 檢查清單

#### 選項 1: 保留佔位符 (推薦)

- [ ] 保持測試存在 (當前狀態)
- [ ] 後續實作完成時再啟用
- [ ] 優點: 明確表達測試需求

#### 選項 2: 移除佔位符

```bash
# 移除所有 fail('xxx') 行的測試
grep -n "fail(" test/widget/flows/user_interaction_flow_test.dart
```

- [ ] 如果選擇移除，備份原始檔案
- [ ] 刪除所有 fail() 佔位符測試
- [ ] 保留 group 結構供日後使用

#### 選項 3: 實作基本流程測試 (時間不允許時跳過)

- [ ] 不推薦現在做
- [ ] 另開獨立 Ticket 處理

---

## 第五階段: 文檔更新 (時間許可時執行)

### 檢查清單

#### 1️⃣ 建立 Widget 測試最佳實踐文件

- [ ] 建立 `docs/widget-testing-best-practices.md`
- [ ] 內容包含:
  - [ ] 五種包裝方式說明
  - [ ] 決策樹 (何時使用哪種方式)
  - [ ] 常見錯誤和修復方法
  - [ ] 程式碼範例

#### 2️⃣ 更新 TESTING_GUIDELINES.md

- [ ] 加入 Widget 測試章節
- [ ] 引用最佳實踐文件
- [ ] 加入快速參考表

#### 3️⃣ 更新 CLAUDE.md

- [ ] 加入 Widget 測試相關注意事項
- [ ] 推薦使用 `createFullTestApp`

---

## 驗證和測試

### 全面驗證檢查清單

#### 第一階段完成後

```bash
# 驗證 pumpTestWidget 測試 (101 個)
[ ] flutter test test/presentation/version_management/widgets/
[ ] 預期: ~100+ 測試通過
```

#### 第二階段完成後

```bash
# 驗證 createTestApp 測試 (28 個)
[ ] flutter test test/widget/library/
[ ] flutter test test/unit/presentation/sync/
[ ] 預期: 所有修改過的測試通過
```

#### 第三階段完成後

```bash
# 驗證多語系測試
[ ] flutter test test/widget/multilingual/
[ ] 預期: 所有多語系測試統一使用 createFullTestApp
```

#### 全面驗證

```bash
# 運行所有 Widget 測試
[ ] flutter test test/widget/ test/presentation/
[ ] 預期: ~90% 的先前失敗測試現在通過
```

---

## 常見問題和解決方案

### Q1: 我的測試需要自訂 Provider override，怎麼辦?

**A**: 使用 ProviderScope 包裝 createFullTestApp

```dart
await tester.pumpWidget(
  ProviderScope(
    overrides: [
      myProvider.overrideWith((ref) => MockValue()),
    ],
    child: WidgetTestHelper.createFullTestApp(MyWidget()),
  ),
);
```

### Q2: 修改 TestApp 後出現編譯錯誤?

**A**: 確認已加入所有必要匯入:

```dart
import 'package:flutter_screenutil/flutter_screenutil.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:book_overview_app/l10n/generated/app_localizations.dart';
```

### Q3: 哪些測試應該使用 createFullTestApp?

**A**: 除非只是測試簡單的 StatelessWidget 而不使用任何 Provider 或 ScreenUtil 單位，都應該用 createFullTestApp

### Q4: 能否跳過某些階段?

**A**: 不建議。建議按順序執行:
- 第一階段必須 (解決 92% 失敗)
- 第二階段高度推薦 (解決剩餘 70%)
- 第三階段可選 (改進代碼品質)

---

## 時間估計和資源分配

| 階段 | 任務 | 時間 | 複雜度 | 優先級 |
|-----|------|-----|-------|-------|
| 1 | 改進 TestApp | 30 min | 低 | ⭐⭐⭐ |
| 2 | 統一 createTestApp | 1.5h | 中 | ⭐⭐⭐ |
| 3 | 多語系統一 | 1h | 低 | ⭐⭐ |
| 4 | 流程測試決策 | 15 min | 低 | ⭐ |
| 5 | 文檔更新 | 30 min | 低 | ⭐ |
| | **總計** | **3.5h** | **中** | |

---

## 成功指標

### 階段 1 完成後

- ✅ 101 個 pumpTestWidget 測試通過
- ✅ ScreenUtil 相關錯誤消失
- ✅ TestApp 包含 ScreenUtilInit + ProviderScope + Localization

### 階段 2 完成後

- ✅ 28 個 createTestApp 測試通過
- ✅ 沒有重複包裝層次
- ✅ 統一使用推薦的包裝方式

### 階段 3 完成後

- ✅ 所有多語系測試使用統一方式
- ✅ Localization 配置一致

### 階段 4 完成後

- ✅ 決定是否保留流程測試佔位符

### 階段 5 完成後

- ✅ 文檔完整更新
- ✅ 團隊有清晰的 Widget 測試指南

### 整體成果

- ✅ 預期 ~90% 的先前失敗測試通過
- ✅ Widget 測試基礎設施修復完成
- ✅ 建立了明確的測試最佳實踐

---

## 後續行動

### 短期 (1 週內)

- 執行全部 5 個階段
- 驗證 324+ 測試狀態
- 更新 CHANGELOG.md

### 中期 (2-4 週)

- 持續監控測試通過率
- 搜集團隊反饋
- 調整和改進 Widget 測試指南

### 長期

- 建立 Widget 測試審查檢查清單
- 建立自動化檢查規則 (pre-commit hook)
- 定期更新最佳實踐指南

---

**本檢查清單完整性**: 100%
**預期修復成功率**: 95%+
**日期**: 2026-01-10

