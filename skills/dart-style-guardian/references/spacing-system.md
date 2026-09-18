# Spacing System Reference

## Design Philosophy

### 4dp Grid System

All spacing in this project follows a **4dp grid system**. This ensures:
- Visual harmony and alignment
- Consistent rhythm across the UI
- Easier responsive scaling

### Spacing Scale

| Name | Value | Common Usage |
|------|-------|--------------|
| `xxs` | 4dp | Tight gaps, icon margins |
| `xs` | 8dp | Small gaps, list item padding |
| `sm` | 12dp | Medium-small gaps |
| `md` | 16dp | Standard padding, card margins |
| `lg` | 24dp | Large gaps, section spacing |
| `xl` | 32dp | Extra large gaps |
| `xxl` | 48dp | Section dividers |
| `xxxl` | 64dp | Major section spacing |

---

## UISpacing Constants

基礎間距常數對應〈Spacing Scale〉的離散階，常數本身不含方向或縮放尾綴：

```dart
UISpacing.xxs   // 4   - Tight gaps, icon margins
UISpacing.xs    // 8   - Small gaps, list item padding
UISpacing.sm    // 12  - Medium-small gaps
UISpacing.md    // 16  - Standard padding, card margins
UISpacing.lg    // 24  - Large gaps, section spacing
UISpacing.xl    // 32  - Extra large gaps
UISpacing.xxl   // 48  - Section dividers
UISpacing.xxxl  // 64  - Major section spacing
```

需要響應式縮放時，由呼叫端依方向外加尾綴：水平（`width`／`horizontal`）加 `.w`，垂直（`height`／`vertical`）加 `.h`——`UISpacing.md.w`、`UISpacing.md.h`。同一階不分水平垂直另立第二組常數（不存在 `UISpacing.verticalMd` 這類命名）。

---

## SizedBox Usage

### Vertical Spacing

```dart
// Before (hardcoded)
SizedBox(height: 16)

// After (configuration)
SizedBox(height: UISpacing.md.h)
```

### Horizontal Spacing

```dart
// Before (hardcoded)
SizedBox(width: 8)

// After (configuration)
SizedBox(width: UISpacing.xs.w)
```

### Common Patterns

```dart
// List item spacing
ListView.separated(
  separatorBuilder: (_, __) => SizedBox(height: UISpacing.xs.h),
  ...
)

// Button row spacing
Row(
  children: [
    ElevatedButton(...),
    SizedBox(width: UISpacing.sm.w),
    TextButton(...),
  ],
)

// Card content spacing
Column(
  children: [
    Text('Title'),
    SizedBox(height: UISpacing.xs.h),
    Text('Subtitle'),
    SizedBox(height: UISpacing.md.h),
    Text('Body content'),
  ],
)
```

---

## EdgeInsets Usage

### All Sides

```dart
// Before
Padding(padding: EdgeInsets.all(16))

// After
Padding(padding: EdgeInsets.all(UISpacing.md.w))
```

### Symmetric

```dart
// Before
Padding(
  padding: EdgeInsets.symmetric(
    horizontal: 16,
    vertical: 8,
  ),
)

// After
Padding(
  padding: EdgeInsets.symmetric(
    horizontal: UISpacing.md.w,
    vertical: UISpacing.xs.h,
  ),
)
```

### Individual Sides

```dart
// Before
Padding(
  padding: EdgeInsets.only(
    left: 16,
    top: 8,
    right: 16,
    bottom: 24,
  ),
)

// After
Padding(
  padding: EdgeInsets.only(
    left: UISpacing.md.w,
    top: UISpacing.xs.h,
    right: UISpacing.md.w,
    bottom: UISpacing.lg.h,
  ),
)
```

---

## Responsive Spacing

### Dynamic Content Padding

```dart
// Use contentPadding for responsive content margins
Container(
  padding: UISpacing.contentPadding(context),
  child: ...,
)
```

### Dynamic Card Margin

```dart
// Use cardMargin for responsive card spacing
Card(
  margin: UISpacing.cardMargin(context),
  child: ...,
)
```

---

## Migration Guide

### Common Replacements

| Hardcoded | UISpacing |
|-----------|-----------|
| `4` | `UISpacing.xxs` |
| `4.0` | `UISpacing.xxs` |
| `8` | `UISpacing.xs` |
| `8.0` | `UISpacing.xs` |
| `12` | `UISpacing.sm` |
| `12.0` | `UISpacing.sm` |
| `16` | `UISpacing.md` |
| `16.0` | `UISpacing.md` |
| `24` | `UISpacing.lg` |
| `24.0` | `UISpacing.lg` |
| `32` | `UISpacing.xl` |
| `32.0` | `UISpacing.xl` |
| `48` | `UISpacing.xxl` |

### Non-Standard Values

值不在〈Spacing Scale〉的八階上時，先判斷這個值從哪裡來，再決定取近似階還是加一階：

| 值的來源 | 處置 |
|---------|------|
| 設計來源（設計稿、元件規範）刻意指定此值 | 不取近似。這是缺 token：停下走 design-system 前置票提案加階，不在元件或頁面內就地寫值（元件庫雙向約束方法論「缺件前置範圍擴充」） |
| 設計畫布實測值，屬產生器輸出、看不出尺度 | 萃取時歸納進離散階，映射記入決策文件（`foundation-design` skill `references/examples.md`〈萃取不等於照抄〉） |
| 既有程式碼已在使用的裸值 | 取近似會改變畫面，屬行為變更：候選階記入決策文件，收斂另開票，驗收含改動前後畫面或特徵測試比對（`foundation-design` skill `references/handoff-mode.md`〈命名與收斂分兩步〉） |
| 無設計來源的新寫程式碼 | 取下表候選。與相鄰兩階距離不等時只列較近的一階；距離相等時兩階並列，兩者皆合規 |

| Hardcoded | Candidate UISpacing |
|-----------|---------------------|
| `6` | `UISpacing.xxs` (4) or `UISpacing.xs` (8) |
| `10` | `UISpacing.xs` (8) or `UISpacing.sm` (12) |
| `14` | `UISpacing.sm` (12) or `UISpacing.md` (16) |
| `18` | `UISpacing.md` (16) |
| `20` | `UISpacing.md` (16) or `UISpacing.lg` (24) |
| `28` | `UISpacing.lg` (24) or `UISpacing.xl` (32) |

---

## Best Practices

1. **Always use UISpacing constants** - Never hardcode pixel values
2. **Prefer standard scale** - Avoid custom spacing values
3. **Use semantic spacing** - `UISpacing.md` for "medium" not specific pixels
4. **Consider responsive** - Use dynamic methods for layout-dependent spacing
5. **Maintain visual rhythm** - Consistent spacing creates better UX
