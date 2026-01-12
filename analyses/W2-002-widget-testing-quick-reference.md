# W2-002 Widget 測試快速參考卡片

## 核心問題 (60 秒理解)

```
問題: Widget 測試中使用 .w, .h, .sp 單位時報 LateInitializationError
原因: 測試沒有用 ScreenUtilInit 包裝，導致 ScreenUtil 未初始化
影響: 324+ 個測試失敗 (92% 是這個問題)
```

---

## 五種包裝方式決策樹

```
你需要什麼?
│
├─ 只需要基本 MaterialApp
│  └─ ❌ TestApp (太簡單，會失敗)
│
├─ 需要 Localization + ScreenUtil
│  └─ ❌ createTestApp (缺少 ScreenUtil)
│     └─ ❌ createScreenUtilTestApp (缺少 Provider)
│
└─ 需要 Localization + ScreenUtil + Provider (最常見)
   └─ ✅ createFullTestApp (推薦!)
      或 ✅ createTestAppWithProviders (同效)
```

---

## 三個修復方案速查表

### 方案 A: 改進 TestApp (最快! 30 分鐘)

**適用於**: 所有使用 `pumpTestWidget` 的測試 (101 個)

**修改檔案**: `test/presentation/version_management/helpers/test_app.dart`

```dart
❌ 當前 (不完整)
class TestApp extends StatelessWidget {
  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      home: Scaffold(body: child),
    );
  }
}

✅ 改進後 (完整)
class TestApp extends StatelessWidget {
  @override
  Widget build(BuildContext context) {
    return ScreenUtilInit(                    // ← 新增
      designSize: const Size(375, 812),
      minTextAdapt: true,
      splitScreenMode: true,
      builder: (context, _) => ProviderScope( // ← 新增
        child: MaterialApp(
          locale: const Locale('zh', 'TW'),   // ← 新增
          localizationsDelegates:
            AppLocalizations.localizationsDelegates,
          supportedLocales:
            AppLocalizations.supportedLocales,
          home: Scaffold(body: child),
          debugShowCheckedModeBanner: false,
        ),
      ),
    );
  }
}
```

**預期效果**: ✅ 101 個 pumpTestWidget 測試通過

---

### 方案 B: 統一為 createFullTestApp (簡單替換)

**適用於**: 使用 `createTestApp` 的測試 (17 + 11 = 28 個)

**當前錯誤模式**:
```dart
❌ 寫法 1
await tester.pumpWidget(WidgetTestHelper.createTestApp(...));

❌ 寫法 2
await tester.pumpWidget(_createTestApp(...));

❌ 寫法 3 (最複雜)
return WidgetTestHelper.createScreenUtilTestWrapper(
  child: ProviderScope(
    overrides: [...],
    child: WidgetTestHelper.createTestApp(...),  // ← 層數太多!
  ),
);
```

**統一修復**:
```dart
✅ 推薦寫法 1
await tester.pumpWidget(
  WidgetTestHelper.createFullTestApp(
    const VersionIndicator(count: 3),
  ),
);

✅ 推薦寫法 2 (需要 Provider override)
await tester.pumpWidget(
  ProviderScope(
    overrides: [
      libraryDisplayViewModelProvider.overrideWith(...),
    ],
    child: WidgetTestHelper.createFullTestApp(
      const LibraryDisplayPage(),
    ),
  ),
);
```

**預期效果**: ✅ 28 個測試通過

---

### 方案 C: 統一多語系測試 (腳本化替換)

**適用於**: 多語系相關測試 (40% 的失敗)

**當前混亂狀態**:
```dart
❌ 寫法 1 (缺少 ScreenUtil)
WidgetTestEnvironment.createTestEnvironment(
  child: MyWidget(),
)

❌ 寫法 2 (hardcoded locale)
MaterialApp(
  locale: const Locale('zh', 'TW'),
  ...
)

❌ 寫法 3 (層數混亂)
ScreenUtilInit(
  builder: (_) => MaterialApp(...),
)
```

**統一方案**:
```dart
✅ 所有多語系測試統一用
await tester.pumpWidget(
  WidgetTestHelper.createFullTestApp(
    MyWidget(),
    locale: const Locale('zh', 'TW'),  // 可自訂語言
  ),
);
```

**預期效果**: ✅ 40% 的多語系測試通過

---

## 失敗模式 → 解決方案對應表

| 失敗訊息 | 根因 | 立即修復 |
|--------|------|--------|
| `LateInitializationError: Field '_screenUtil' has not been initialized` | 缺 ScreenUtilInit | 套用方案 A |
| `ProviderNotFoundException: No provider found` | 缺 ProviderScope | 套用方案 A |
| `Localization not found` | 缺 localizationsDelegates | 套用方案 A |
| `找不到 widget` (某個 widget 沒有渲染) | 通常是 A + B + C 的組合 | 依序套用 |

---

## 修復優先級速查

```
修復順序        方案        影響範圍    時間     複雑度
─────────────────────────────────────────────────────
1️⃣  優先修    方案 A      101 個     30min    低
   (立即!)

2️⃣  高優先    方案 B      28 個     1.5h     中

3️⃣  中優先    方案 C      40%       1h       低

✅  預期結果: ~170 個測試通過 (324 - 154)
```

---

## 常見錯誤和正確做法

### ❌ 錯誤 #1: 層數太多

```dart
❌ 錯誤
ScreenUtilInit(
  builder: (_) => ProviderScope(
    child: MaterialApp(
      home: Scaffold(
        body: MyWidget(),
      ),
    ),
  ),
)

✅ 正確
WidgetTestHelper.createFullTestApp(MyWidget())
// createFullTestApp 已經內部完成了這些層數
```

### ❌ 錯誤 #2: 使用單一 TestApp

```dart
❌ 錯誤
await tester.pumpTestWidget(MyWidget());
// pumpTestWidget 使用簡單的 TestApp，缺少功能

✅ 正確
await tester.pumpWidget(
  WidgetTestHelper.createFullTestApp(MyWidget())
);
```

### ❌ 錯誤 #3: Provider override 位置錯誤

```dart
❌ 錯誤
return WidgetTestHelper.createFullTestApp(
  ProviderScope(  // ← override 應該在外層!
    overrides: [...],
    child: MyWidget(),
  ),
);

✅ 正確
return ProviderScope(
  overrides: [...],
  child: WidgetTestHelper.createFullTestApp(
    MyWidget(),
  ),
);
```

---

## 五行快速檢查清單

### 你的 Widget 測試是否正確?

- [ ] 使用 `WidgetTestHelper.createFullTestApp` 或 `createTestAppWithProviders`?
- [ ] 沒有手動創建 `ScreenUtilInit`?
- [ ] 沒有手動創建 `ProviderScope` (除非需要 override)?
- [ ] 沒有重複的 `MaterialApp` / `Scaffold` 包裝?
- [ ] Widget 可以正常使用 `.w`, `.h`, `.sp` 單位?

如果全部 ✅ → 你的測試應該通過
如果任何 ❌ → 套用上面的方案 A/B/C

---

## 最佳實踐速查

### 單純的 Widget 測試 (最常見)

```dart
testWidgets('test name', (tester) async {
  await tester.pumpWidget(
    WidgetTestHelper.createFullTestApp(
      const MyWidget(),
    ),
  );

  expect(find.byType(MyWidget), findsOneWidget);
});
```

### 需要 Provider override 的測試

```dart
testWidgets('test name', (tester) async {
  await tester.pumpWidget(
    ProviderScope(
      overrides: [
        myProvider.overrideWith((ref) => MockValue()),
      ],
      child: WidgetTestHelper.createFullTestApp(
        const MyWidget(),
      ),
    ),
  );

  expect(...);
});
```

### 多語系測試

```dart
testWidgets('test name', (tester) async {
  const locales = [
    Locale('en', 'US'),
    Locale('zh', 'TW'),
    Locale('ja', 'JP'),
  ];

  for (final locale in locales) {
    await tester.pumpWidget(
      WidgetTestHelper.createFullTestApp(
        const MyWidget(),
        locale: locale,
      ),
    );

    expect(...);
  }
});
```

---

## 相關檔案位置

```
推薦使用:
├── test/helpers/widget_test_helper.dart

不推薦單獨使用:
├── test/presentation/version_management/helpers/test_app.dart
│   (改進後可用)
└── test/helpers/widget_test_environment.dart
    (缺少 ScreenUtil)
```

---

**使用本卡片快速修復 Widget 測試問題，預期成功率 95%+**

