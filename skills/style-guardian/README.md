# Style Guardian - Quick Reference

## Purpose

Prevent hardcoded styles and text in the codebase. Ensure consistent use of:
- UIColors (color system)
- UISpacing (spacing system)
- UIFontSizes (typography system)
- UIBorderRadius (border radius system)
- context.l10n (internationalization)

## Quick Start

```dart
// Required import
import 'package:book_overview_app/core/ui/ui_config.dart';
```

## Common Replacements

### Colors

| Before | After |
|--------|-------|
| `Colors.blue` | `UIColors.primary` |
| `Colors.green` | `UIColors.positive` |
| `Colors.orange` | `UIColors.negative` |
| `Colors.white` | `UIColors.surfaceLight` |
| `Colors.grey[50]` | `UIColors.backgroundLight` |

### Spacing (4dp grid)

| Before | After |
|--------|-------|
| `4` | `UISpacing.xxs` |
| `8` | `UISpacing.xs` |
| `12` | `UISpacing.sm` |
| `16` | `UISpacing.md` |
| `24` | `UISpacing.lg` |
| `32` | `UISpacing.xl` |

### Font Sizes

| Before | After |
|--------|-------|
| `10` | `UIFontSizes.overline` |
| `12` | `UIFontSizes.bodySmall` |
| `14` | `UIFontSizes.bodyMedium` |
| `16` | `UIFontSizes.bodyLarge` |
| `20` | `UIFontSizes.titleLarge` |

### Border Radius

| Before | After |
|--------|-------|
| `4` | `UIBorderRadius.xs` |
| `8` | `UIBorderRadius.sm` |
| `12` | `UIBorderRadius.md` |
| `16` | `UIBorderRadius.lg` |

### Text (i18n)

| Before | After |
|--------|-------|
| `'My Library'` | `context.l10n!.libraryTitle` |
| `'Settings'` | `context.l10n!.settingsTitle` |
| `'Error'` | `context.l10n!.errorMessage` |

## Design Principles

1. **Flat Design 2.0** - Subtle shadows, no borders
2. **Monochrome System** - 90% blue, 5% green (success), 5% orange (warning)
3. **4dp Grid** - All spacing multiples of 4
4. **Responsive** - Use `.w`, `.h`, `.rsp` suffixes

## Run Detection

```bash
# Scan project
uv run .claude/skills/style-guardian/scripts/style_checker.py scan lib/

# Generate report
uv run .claude/skills/style-guardian/scripts/style_checker.py report
```

## Full Documentation

See [SKILL.md](./SKILL.md) for complete reference.
