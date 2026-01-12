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
| `fontSize: 11` | `UIFontSizes.overline` |
| `fontSize: 12` | `UIFontSizes.bodySmall` |
| `fontSize: 13` | `UIFontSizes.bodySmall` |
| `fontSize: 14` | `UIFontSizes.bodyMedium` |
| `fontSize: 15` | `UIFontSizes.bodyMedium` |
| `fontSize: 16` | `UIFontSizes.bodyLarge` |
| `fontSize: 17` | `UIFontSizes.bodyLarge` |
| `fontSize: 18` | `UIFontSizes.titleMedium` |
| `fontSize: 19` | `UIFontSizes.titleMedium` |
| `fontSize: 20` | `UIFontSizes.titleLarge` |
| `fontSize: 24` | `UIFontSizes.headline3` |
| `fontSize: 28` | `UIFontSizes.headline2` |
| `fontSize: 32` | `UIFontSizes.headline1` |

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
6. **Use theme when available** - `Theme.of(context).textTheme` for consistency
