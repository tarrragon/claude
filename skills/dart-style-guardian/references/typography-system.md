# Typography System Reference

## Design Philosophy

### Font Family

This project uses a Chinese-optimized font stack:

```dart
Primary:  'PingFang SC'
Fallback: 'Microsoft YaHei'
```

### Type Scale

The typography system follows a modular scale for visual hierarchy:

| Category | Size | Usage |
|----------|------|-------|
| Headline | 24-32 | Page titles, major headings |
| Title | 16-20 | Section titles, card headers |
| Body | 12-16 | Main content, descriptions |
| Caption | 10-12 | Labels, hints, metadata |

---

## UIFontSizes Constants

### Headlines

```dart
UIFontSizes.headline1  // 32.rsp - Major page titles
UIFontSizes.headline2  // 28.rsp - Secondary page titles
UIFontSizes.headline3  // 24.rsp - Section headings
UIFontSizes.headline4  // 20.rsp - Subsection headings
```

### Titles

```dart
UIFontSizes.titleLarge   // 20.rsp - Card titles, dialog headers
UIFontSizes.titleMedium  // 18.rsp - List item titles
UIFontSizes.titleSmall   // 16.rsp - Small titles
```

### Body Text

```dart
UIFontSizes.bodyLarge   // 16.rsp - Important body text
UIFontSizes.bodyMedium  // 14.rsp - Standard body text
UIFontSizes.bodySmall   // 12.rsp - Secondary text
```

### Other

```dart
UIFontSizes.button    // 14.rsp - Button labels
UIFontSizes.caption   // 12.rsp - Captions, hints
UIFontSizes.overline  // 10.rsp - Labels, tags
```

---

## Font Weights

### UITypography Weights

```dart
UITypography.light     // FontWeight.w300
UITypography.regular   // FontWeight.w400
UITypography.medium    // FontWeight.w500
UITypography.semiBold  // FontWeight.w600
UITypography.bold      // FontWeight.w700
```

### Usage Guidelines

| Weight | Usage |
|--------|-------|
| `light` | Large decorative text |
| `regular` | Body text, descriptions |
| `medium` | Emphasis, interactive elements |
| `semiBold` | Titles, headings |
| `bold` | Strong emphasis, alerts |

---

## Line Heights

### UITypography Line Heights

```dart
UITypography.lineHeightTight    // 1.2 - Headings, tight layouts
UITypography.lineHeightNormal   // 1.4 - Body text, paragraphs
UITypography.lineHeightRelaxed  // 1.6 - Long-form content
```

---

## 字級判準：headline 與 title 同值時如何選

`headline4`（20.rsp）與 `titleLarge`（20.rsp）數值相同但用途不同——〈UIFontSizes Constants〉的定義註解已分別標「Subsection headings」與「Card titles, dialog headers」，數值相同不代表語意相同。依上方〈Headlines〉與〈Titles〉區塊的定義註解：頁面內的階層子節標題對映 `headline4`（「Subsection headings」）；卡片或對話框等容器元件內的標題對映 `titleLarge`（「Card titles, dialog headers」）。

【輸入】

```
定義註解：
  headline4  // 20.rsp - Subsection headings
  titleLarge // 20.rsp - Card titles, dialog headers
情境：畫面上有一段文字，字級寫死為 20
```

【產出】

```
形態：決策表

情境                                    | 判定       | 理由
------------------------------------------|------------|------------------------------
文字是文件層級的子節標題（頁面內的階層標題） | headline4  | 定義註解「Subsection headings」
文字是卡片或對話框內的標題（元件情境內）     | titleLarge | 定義註解「Card titles, dialog headers」
```

【驗證】

```
檢驗問句
Q 該文字是否位於某個容器元件（卡片／對話框）內、作為該容器的標題？
  預期：是 → titleLarge；否，是頁面文件階層的子標題 → headline4
Q 兩個 token 是否因數值相同（皆 20.rsp）而可互換？
  預期：否——定義註解已區分文件階層與元件情境兩種語意，數值相同不代表語意相同
```

---

## TextStyle Examples

### Page Title

```dart
TextStyle(
  fontSize: UIFontSizes.headline1,
  fontWeight: UITypography.bold,
  height: UITypography.lineHeightTight,
  color: UIColors.onSurfaceLight,
)
```

### Section Header

```dart
TextStyle(
  fontSize: UIFontSizes.titleLarge,
  fontWeight: UITypography.semiBold,
  height: UITypography.lineHeightTight,
  color: UIColors.onSurfaceLight,
)
```

### Body Text

```dart
TextStyle(
  fontSize: UIFontSizes.bodyMedium,
  fontWeight: UITypography.regular,
  height: UITypography.lineHeightNormal,
  color: UIColors.onSurfaceLight,
)
```

### Caption

```dart
TextStyle(
  fontSize: UIFontSizes.caption,
  fontWeight: UITypography.regular,
  height: UITypography.lineHeightNormal,
  color: UIColors.onSurfaceMuted,
)
```

### Button Label

```dart
TextStyle(
  fontSize: UIFontSizes.button,
  fontWeight: UITypography.medium,
  height: UITypography.lineHeightTight,
)
```

---

## Responsive Typography

### The `.rsp` Suffix

All UIFontSizes use the `.rsp` (responsive scale pixel) suffix for automatic scaling:

```dart
// Definition in UIFontSizes
static double get bodyMedium => 14.rsp;  // Automatically scales

// Usage (no need to add .rsp again)
TextStyle(fontSize: UIFontSizes.bodyMedium)
```

### Manual Responsive Text

When using custom sizes (not recommended), apply `.rsp`:

```dart
// Correct
TextStyle(fontSize: 14.rsp)

// Incorrect
TextStyle(fontSize: 14)  // Won't scale
TextStyle(fontSize: 14.sp)  // Wrong suffix
```

---

## Migration Guide

### Common Replacements

| Hardcoded | UIFontSizes |
|-----------|-------------|
| `fontSize: 10` | `UIFontSizes.overline` |
| `fontSize: 12` | `UIFontSizes.bodySmall` |
| `fontSize: 14` | `UIFontSizes.bodyMedium` |
| `fontSize: 16` | `UIFontSizes.bodyLarge` |
| `fontSize: 18` | `UIFontSizes.titleMedium` |
| `fontSize: 20` | `UIFontSizes.titleLarge` |
| `fontSize: 24` | `UIFontSizes.headline3` |
| `fontSize: 28` | `UIFontSizes.headline2` |
| `fontSize: 32` | `UIFontSizes.headline1` |

### Non-Standard Values

字級不在〈Type Scale〉離散階上時，先判斷這個值從哪裡來，再決定取近似階還是加一階：

| 值的來源 | 處置 |
|---------|------|
| 設計來源（設計稿、元件規範）刻意指定此值 | 不取近似。這是缺 token：停下走 design-system 前置票提案加階，不在元件或頁面內就地寫值（元件庫雙向約束方法論「缺件前置範圍擴充」） |
| 設計畫布實測值，屬產生器輸出、看不出尺度 | 萃取時歸納進離散階，映射記入決策文件（`foundation-design` skill `references/examples.md`〈萃取不等於照抄〉） |
| 既有程式碼已在使用的裸值 | 取近似會改變畫面（文字大小視覺變動），屬行為變更：候選階記入決策文件，收斂另開票，驗收含改動前後畫面或特徵測試比對（`foundation-design` skill `references/handoff-mode.md`〈命名與收斂分兩步〉） |
| 無設計來源的新寫程式碼 | 取下表候選。與相鄰兩階距離不等時只列較近的一階；距離相等時兩階並列，兩者皆合規 |

| Hardcoded | Candidate UIFontSizes |
|-----------|------------------------|
| `fontSize: 11` | `UIFontSizes.overline` (10) or `UIFontSizes.bodySmall` (12) |
| `fontSize: 13` | `UIFontSizes.bodySmall` (12) or `UIFontSizes.bodyMedium` (14) |
| `fontSize: 15` | `UIFontSizes.bodyMedium` (14) or `UIFontSizes.bodyLarge` (16) |
| `fontSize: 17` | `UIFontSizes.bodyLarge` (16) or `UIFontSizes.titleMedium` (18) |
| `fontSize: 19` | `UIFontSizes.titleMedium` (18) or `UIFontSizes.titleLarge` (20) |

### Weight Replacements

| Hardcoded | UITypography |
|-----------|--------------|
| `FontWeight.w300` | `UITypography.light` |
| `FontWeight.w400` | `UITypography.regular` |
| `FontWeight.w500` | `UITypography.medium` |
| `FontWeight.w600` | `UITypography.semiBold` |
| `FontWeight.w700` | `UITypography.bold` |

---

## Best Practices

1. **Use semantic names** - `UIFontSizes.bodyMedium` not `14.rsp`
2. **Avoid hardcoded sizes** - All font sizes should use UIFontSizes
3. **Maintain hierarchy** - Headlines > Titles > Body > Captions
4. **Consider readability** - Minimum 12.rsp for body text
5. **Test on devices** - Verify scaling works correctly
6. **Use theme when available** - `Theme.of(context).textTheme` for consistency；Theme 與 token 該用哪一個的判準見 `color-system.md`〈Theme 與 Token 判準〉，字級語意同適用（不重複列一份決策表）
