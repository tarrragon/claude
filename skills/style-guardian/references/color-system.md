# Color System Reference

## Design Philosophy

### Three-Color System

This project uses a **Flat Design 2.0** approach with a **monochrome color system**:

- **Primary (90%)**: Blue - main interactive elements, branding
- **Positive (5%)**: Green - success states, confirmations
- **Negative (5%)**: Orange - warnings, errors, destructive actions

**Important**: Red is NOT used in this project. All error/warning states use Orange.

---

## Primary Color Palette (Blue)

### Color Scale

| Name | Hex | RGB | Usage |
|------|-----|-----|-------|
| `primaryLightest` | #E3F2FD | rgb(227, 242, 253) | Background blocks, hover states |
| `primaryLight` | #BBDEFB | rgb(187, 222, 251) | Secondary backgrounds, borders |
| `primaryMedium` | #64B5F6 | rgb(100, 181, 246) | Interactive elements, icons |
| `primary` | #2196F3 | rgb(33, 150, 243) | Primary buttons, links |
| `primaryDark` | #1976D2 | rgb(25, 118, 210) | Selected states, active elements |
| `primaryDarkest` | #0D47A1 | rgb(13, 71, 161) | Emphasis text, headers |

### Usage Examples

```dart
// Primary button
ElevatedButton(
  style: ElevatedButton.styleFrom(
    backgroundColor: UIColors.primary,
    foregroundColor: UIColors.surfaceLight,
  ),
  onPressed: () {},
  child: Text('Submit'),
)

// Selected item background
Container(
  color: UIColors.primaryLightest,
  child: ListTile(...),
)

// Accent text
Text(
  'Important',
  style: TextStyle(color: UIColors.primaryDark),
)
```

---

## Positive Color Palette (Green)

### Color Scale

| Name | Hex | RGB | Usage |
|------|-----|-----|-------|
| `positiveLight` | #C8E6C9 | rgb(200, 230, 201) | Success backgrounds |
| `positive` | #4CAF50 | rgb(76, 175, 80) | Success icons, buttons |
| `positiveDark` | #388E3C | rgb(56, 142, 60) | Success emphasis |

### Aliases

```dart
UIColors.success = UIColors.positive
UIColors.successLight = UIColors.positiveLight
UIColors.successDark = UIColors.positiveDark
```

### Usage Examples

```dart
// Success toast
showToast(
  message: 'Saved successfully',
  backgroundColor: UIColors.positive,
)

// Success badge
Container(
  decoration: BoxDecoration(
    color: UIColors.positiveLight,
    borderRadius: BorderRadius.circular(UIBorderRadius.sm),
  ),
  child: Icon(Icons.check, color: UIColors.positiveDark),
)
```

---

## Negative Color Palette (Orange)

### Color Scale

| Name | Hex | RGB | Usage |
|------|-----|-----|-------|
| `negativeLight` | #FFE0B2 | rgb(255, 224, 178) | Warning backgrounds |
| `negative` | #FF9800 | rgb(255, 152, 0) | Warning icons, buttons |
| `negativeDark` | #F57C00 | rgb(245, 124, 0) | Warning emphasis |

### Aliases

```dart
UIColors.warning = UIColors.negative
UIColors.error = UIColors.negative  // No red in this project
UIColors.warningLight = UIColors.negativeLight
UIColors.errorLight = UIColors.negativeLight
```

### Usage Examples

```dart
// Error message
Text(
  'Invalid input',
  style: TextStyle(color: UIColors.negative),
)

// Delete button
TextButton(
  style: TextButton.styleFrom(
    foregroundColor: UIColors.negative,
  ),
  onPressed: () {},
  child: Text('Delete'),
)
```

---

## Neutral Colors

### Surface Colors

| Name | Hex | Usage |
|------|-----|-------|
| `surfaceLight` | #FFFFFF | Card backgrounds, dialogs |
| `backgroundLight` | #FAFAFA | Page backgrounds |
| `onSurfaceLight` | #424242 | Primary text |
| `onSurfaceMuted` | #757575 | Secondary text |

### Dark Theme Colors

| Name | Hex | Usage |
|------|-----|-------|
| `backgroundDark` | #0A0E13 | Dark page backgrounds |
| `onBackgroundDark` | #E3F2FD | Text on dark backgrounds |

---

## Shadow Colors

Shadows use the primary blue color with varying opacity:

| Name | Color | Usage |
|------|-------|-------|
| `shadowLight` | #2196F3 @ 8% | Subtle elevation |
| `shadowMedium` | #2196F3 @ 12% | Standard elevation |
| `shadowStrong` | #2196F3 @ 16% | High elevation |

### Divider Colors

| Name | Color | Usage |
|------|-------|-------|
| `dividerSubtle` | #2196F3 @ 6% | Subtle separation |
| `dividerNormal` | #2196F3 @ 10% | Standard separation |
| `dividerStrong` | #2196F3 @ 14% | Strong separation |

---

## Migration Guide

### From Material Colors

| Material | UIColors |
|----------|----------|
| `Colors.blue` | `UIColors.primary` |
| `Colors.blue[50]` | `UIColors.primaryLightest` |
| `Colors.blue[100]` | `UIColors.primaryLight` |
| `Colors.blue[300]` | `UIColors.primaryMedium` |
| `Colors.blue[700]` | `UIColors.primaryDark` |
| `Colors.blue[900]` | `UIColors.primaryDarkest` |
| `Colors.green` | `UIColors.positive` |
| `Colors.orange` | `UIColors.negative` |
| `Colors.red` | `UIColors.negative` |
| `Colors.white` | `UIColors.surfaceLight` |
| `Colors.grey[50]` | `UIColors.backgroundLight` |
| `Colors.grey[600]` | `UIColors.onSurfaceMuted` |

### From Hex Colors

| Hex | UIColors |
|-----|----------|
| `Color(0xFF2196F3)` | `UIColors.primary` |
| `Color(0xFF1976D2)` | `UIColors.primaryDark` |
| `Color(0xFF4CAF50)` | `UIColors.positive` |
| `Color(0xFF388E3C)` | `UIColors.positiveDark` |
| `Color(0xFFFF9800)` | `UIColors.negative` |
| `Color(0xFFF57C00)` | `UIColors.negativeDark` |

---

## Best Practices

1. **Never use `Colors.red`** - Use `UIColors.negative` instead
2. **Avoid opacity modifiers** - Use pre-defined color variants
3. **Use semantic names** - `UIColors.positive` not `UIColors.green`
4. **Prefer theme colors** - Use `Theme.of(context).colorScheme` when available
5. **Test dark mode** - Ensure colors work in both themes
