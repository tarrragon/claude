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

### Horizontal Spacing (use with `.w`)

```dart
UISpacing.xs    // 8.w   - Small horizontal gaps
UISpacing.sm    // 12.w  - Medium-small horizontal gaps
UISpacing.md    // 16.w  - Standard horizontal padding
UISpacing.lg    // 24.w  - Large horizontal gaps
UISpacing.xl    // 32.w  - Extra large horizontal gaps
UISpacing.xxl   // 48.w  - Major horizontal spacing
UISpacing.xxxl  // 64.w  - Maximum horizontal spacing
```

### Vertical Spacing (use with `.h`)

```dart
UISpacing.verticalXs   // 4.h  - Tight vertical gaps
UISpacing.verticalSm   // 8.h  - Small vertical gaps
UISpacing.verticalMd   // 16.h - Standard vertical spacing
UISpacing.verticalLg   // 24.h - Large vertical gaps
UISpacing.verticalXl   // 32.h - Extra large vertical gaps
UISpacing.verticalXxl  // 48.h - Major vertical spacing
```

---

## SizedBox Usage

### Vertical Spacing

```dart
// Before (hardcoded)
SizedBox(height: 16)

// After (configuration)
SizedBox(height: UISpacing.md)
```

### Horizontal Spacing

```dart
// Before (hardcoded)
SizedBox(width: 8)

// After (configuration)
SizedBox(width: UISpacing.xs)
```

### Common Patterns

```dart
// List item spacing
ListView.separated(
  separatorBuilder: (_, __) => SizedBox(height: UISpacing.xs),
  ...
)

// Button row spacing
Row(
  children: [
    ElevatedButton(...),
    SizedBox(width: UISpacing.sm),
    TextButton(...),
  ],
)

// Card content spacing
Column(
  children: [
    Text('Title'),
    SizedBox(height: UISpacing.xs),
    Text('Subtitle'),
    SizedBox(height: UISpacing.md),
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
Padding(padding: EdgeInsets.all(UISpacing.md))
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
    horizontal: UISpacing.md,
    vertical: UISpacing.xs,
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
    left: UISpacing.md,
    top: UISpacing.xs,
    right: UISpacing.md,
    bottom: UISpacing.lg,
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
| `20` | `UISpacing.md` |
| `24` | `UISpacing.lg` |
| `24.0` | `UISpacing.lg` |
| `32` | `UISpacing.xl` |
| `32.0` | `UISpacing.xl` |
| `48` | `UISpacing.xxl` |

### Non-Standard Values

For values not in the standard scale, round to the nearest:

| Hardcoded | Nearest UISpacing |
|-----------|-------------------|
| `6` | `UISpacing.xs` (8) |
| `10` | `UISpacing.sm` (12) or `UISpacing.xs` (8) |
| `14` | `UISpacing.md` (16) or `UISpacing.sm` (12) |
| `18` | `UISpacing.md` (16) |
| `20` | `UISpacing.lg` (24) or `UISpacing.md` (16) |
| `28` | `UISpacing.xl` (32) or `UISpacing.lg` (24) |

---

## Best Practices

1. **Always use UISpacing constants** - Never hardcode pixel values
2. **Prefer standard scale** - Avoid custom spacing values
3. **Use semantic spacing** - `UISpacing.md` for "medium" not specific pixels
4. **Consider responsive** - Use dynamic methods for layout-dependent spacing
5. **Maintain visual rhythm** - Consistent spacing creates better UX
