---
name: dart-style-guardian
description: "Style Guardian - Unified Design System Enforcement Tool. Use for: (1) Preventing hardcoded styles (colors, spacing, typography), (2) Preventing hardcoded text (i18n violations), (3) Guiding unified configuration usage, (4) Detecting and fixing style violations"
---

# Style Guardian - Unified Design System Enforcement

> 元件層約束原則（禁自製元件、豁免三條件、白名單治理、WARNING 升阻擋判準）見 `.claude/methodologies/component-library-bidirectional-constraint-methodology.md`；本 skill 為其「工具執法」層的專案實作。

## Core Principles

### Design Philosophy: Flat Design 2.0 + Monochrome System

| Principle | Description | Source |
|-----------|-------------|--------|
| Minimalism | Clean, uncluttered layouts | Flat Design |
| 2D Styling | Simple, flat shapes without 3D effects | Flat Design |
| Subtle Shadows | Shadows hint at interactivity (Flat 2.0) | Material Design |
| Monochrome | Primarily use different saturations of blue | Project Design Spec |
| Three-Color System | Blue (primary) + Green (positive) + Orange (negative) | Project Design Spec |

### Key Files

檔案位置因專案而異，故以角色描述而非路徑列出——寫死某專案的路徑，其他專案讀到的就是一份指向不存在檔案的清單。實際位置見 `.claude/config/dart-style-guardian.json` 的 `tokens` 欄位所指的類別，以及專案的 `l10n.yaml`。

| Role | 內容 |
|------|------|
| Design system tokens | 顏色、間距、字級、圓角的 SSOT；掃描器據此判定何謂「已使用 token」 |
| Theme | 組裝 tokens 為 ThemeData 的入口 |
| Localization 設定 | `l10n.yaml` 決定 ARB 位置與存取子形態 |
| UI 設計規格 | 設計稿與元件規範文件（如有） |

---

## Color System

### Primary Color (Blue, 90% usage)

| Hardcoded | UIColors | Purpose | Hex |
|-----------|----------|---------|-----|
| `Colors.blue` | `UIColors.primary` | Primary buttons | #2196F3 |
| `Color(0xFF2196F3)` | `UIColors.primary` | Primary buttons | #2196F3 |
| `Colors.blue[50]` | `UIColors.primaryLightest` | Background blocks | #E3F2FD |
| `Colors.blue[100]` | `UIColors.primaryLight` | Secondary blocks | #BBDEFB |
| `Colors.blue[300]` | `UIColors.primaryMedium` | Interactive elements | #64B5F6 |
| `Colors.blue[700]` | `UIColors.primaryDark` | Selected states | #1976D2 |
| `Colors.blue[900]` | `UIColors.primaryDarkest` | Emphasis text | #0D47A1 |

### Positive Color (Green, 5% usage)

| Hardcoded | UIColors | Purpose |
|-----------|----------|---------|
| `Colors.green` | `UIColors.positive` | Success, confirmation |
| `Colors.green[100]` | `UIColors.positiveLight` | Success backgrounds |
| `Colors.green[700]` | `UIColors.positiveDark` | Success emphasis |

### Negative Color (Orange, 5% usage)

| Hardcoded | UIColors | Purpose |
|-----------|----------|---------|
| `Colors.orange` | `UIColors.negative` | Warning, error |
| `Colors.amber` | `UIColors.negative` | Warning, caution |
| `Colors.red` | `UIColors.negative` | **Project does NOT use red** |

### Background Colors

| Hardcoded | UIColors | Purpose |
|-----------|----------|---------|
| `Colors.white` | `UIColors.surfaceLight` | Card backgrounds |
| `Colors.grey[50]` | `UIColors.backgroundLight` | Page backgrounds |
| `Colors.grey[600]` | `UIColors.onSurfaceMuted` | Muted text |

---

## Spacing System (4dp Grid)

### SizedBox Spacing

| Hardcoded | UISpacing | Responsive |
|-----------|-----------|------------|
| `SizedBox(height: 4)` | `SizedBox(height: UISpacing.xxs)` | `.h` suffix |
| `SizedBox(height: 8)` | `SizedBox(height: UISpacing.xs)` | `.h` suffix |
| `SizedBox(height: 12)` | `SizedBox(height: UISpacing.sm)` | `.h` suffix |
| `SizedBox(height: 16)` | `SizedBox(height: UISpacing.md)` | `.h` suffix |
| `SizedBox(height: 24)` | `SizedBox(height: UISpacing.lg)` | `.h` suffix |
| `SizedBox(height: 32)` | `SizedBox(height: UISpacing.xl)` | `.h` suffix |
| `SizedBox(width: 8)` | `SizedBox(width: UISpacing.xs)` | `.w` suffix |

### EdgeInsets Padding

| Hardcoded | UISpacing |
|-----------|-----------|
| `EdgeInsets.all(4)` | `EdgeInsets.all(UISpacing.xxs)` |
| `EdgeInsets.all(8)` | `EdgeInsets.all(UISpacing.xs)` |
| `EdgeInsets.all(16)` | `EdgeInsets.all(UISpacing.md)` |
| `EdgeInsets.symmetric(horizontal: 16)` | `EdgeInsets.symmetric(horizontal: UISpacing.md)` |
| `EdgeInsets.symmetric(vertical: 8)` | `EdgeInsets.symmetric(vertical: UISpacing.xs)` |

---

## Typography System

### Font Sizes

| Hardcoded | UIFontSizes | Purpose |
|-----------|-------------|---------|
| `fontSize: 10` | `UIFontSizes.overline` | Overline text |
| `fontSize: 12` | `UIFontSizes.bodySmall` | Small body text |
| `fontSize: 14` | `UIFontSizes.bodyMedium` | Standard body text |
| `fontSize: 16` | `UIFontSizes.bodyLarge` | Large body text |
| `fontSize: 18` | `UIFontSizes.titleMedium` | Medium titles |
| `fontSize: 20` | `UIFontSizes.titleLarge` | Large titles |
| `fontSize: 24` | `UIFontSizes.headline3` | Headlines |

### Responsive Font Sizes

Use `.rsp` suffix for responsive scaling:

```dart
// Correct
TextStyle(fontSize: UIFontSizes.bodyMedium)  // Already includes .rsp

// Incorrect
TextStyle(fontSize: 14)
TextStyle(fontSize: 14.sp)  // Manual scaling
```

---

## Border Radius System

| Hardcoded | UIBorderRadius |
|-----------|----------------|
| `BorderRadius.circular(4)` | `BorderRadius.circular(UIBorderRadius.xs)` |
| `BorderRadius.circular(8)` | `BorderRadius.circular(UIBorderRadius.sm)` |
| `BorderRadius.circular(12)` | `BorderRadius.circular(UIBorderRadius.md)` |
| `BorderRadius.circular(16)` | `BorderRadius.circular(UIBorderRadius.lg)` |
| `BorderRadius.circular(20)` | `BorderRadius.circular(UIBorderRadius.xl)` |
| `BorderRadius.circular(999)` | `BorderRadius.circular(UIBorderRadius.circular)` |

---

## Internationalization (i18n)

所有使用者可見文字必須取自 ARB 產生的 localization 類別，禁止硬編碼字串。存取方式依專案的 `l10n.yaml` 設定而定，常見兩種：`AppLocalizations.of(context).keyName`（`nullable-getter: false`）或 `context.l10n!.keyName`（專案自建 extension）。動手前先讀專案的 `l10n.yaml` 與既有呼叫點確認慣例，勿沿用他專案的寫法。

---

## Common Violations and Fixes

### Violation 1: Hardcoded Colors

```dart
// Violation
Container(color: Colors.blue)
Container(color: Color(0xFF2196F3))

// Fix
Container(color: UIColors.primary)
```

### Violation 2: Hardcoded Spacing

```dart
// Violation
SizedBox(height: 16)
Padding(padding: EdgeInsets.all(8))

// Fix
SizedBox(height: UISpacing.md)
Padding(padding: EdgeInsets.all(UISpacing.xs))
```

### Violation 3: Hardcoded Font Size

```dart
// Violation
TextStyle(fontSize: 14)

// Fix
TextStyle(fontSize: UIFontSizes.bodyMedium)
```

### Violation 4: Hardcoded Border Radius

```dart
// Violation
BorderRadius.circular(8)

// Fix
BorderRadius.circular(UIBorderRadius.sm)
```

### Violation 5: Hardcoded Text

使用者可見文字直接寫在 widget 內，未取自 ARB。`style_checker.py scan` 以 `[i18n]` 標記回報這類違規；修正方式是把字串移入 ARB 檔並改以 localization 類別存取（存取語法見上方 Internationalization 節）。

### Violation 6: ViewModel Hardcoded User Messages

**Scope**: `lib/presentation/**/viewmodel.dart`, `lib/presentation/**_viewmodel.dart`

**Detection Pattern**: String literals assigned to error/message state properties

```dart
// Violation - Hardcoded user messages in ViewModel
state = state.copyWith(errorMessage: 'Invalid file format');
state = state.copyWith(errorMessage: '網路連線失敗');
_errorMessage = 'Something went wrong';

// Fix - Use i18n or ErrorHandler
state = state.copyWith(errorMessage: context.l10n!.invalidFileFormat);
state = state.copyWith(errorMessage: ErrorHandler.getUserMessage(exception));
```

**Allowed Exceptions**:
- `e.toString()` for unknown system exceptions
- String interpolation with i18n: `context.l10n!.errorWithCode(code)`

**Related**（Flutter 專案適用）: ViewModel 層使用者訊息規範見專案根目錄 `FLUTTER.md`（僅 Flutter 專案存在；非 Flutter 專案略過 Violation 6）

---

## Project Calibration

偵測規則本身跨專案通用（硬編碼的顏色、間距、字級一律該進 design system），但**替代方案的名字是專案專屬的**。校準檔告訴掃描器本專案的詞彙：

`.claude/config/dart-style-guardian.json`

```json
{
  "tokens": {
    "color": "AppPalette",
    "spacing": "AppSpacing",
    "font_size": "AppTypography",
    "border_radius": "AppRadius"
  },
  "i18n": {
    "accessor": "AppLocalizations.of(context).keyName",
    "compliance_pattern": "AppLocalizations\\.of\\("
  },
  "exempt_markers": ["magic-exempt", "i18n-exempt"]
}
```

| 欄位 | 作用 |
|------|------|
| `tokens.*` | 修正建議指名的類別；同時作為「此行已合規」的判定依據 |
| `i18n.accessor` | i18n 建議中顯示的存取語法 |
| `i18n.compliance_pattern` | 判定該行已使用 localization 的正則 |
| `exempt_markers` | 行內註解含此標記即豁免，並計入報告的 exempt 計數 |

**缺此檔時**：掃描器仍偵測硬編碼，但建議改為描述性敘述（「改用專案 design system 的 color token」），並在 stderr 提示。這是刻意的——指名某套命名等於斷言它是對的，而讀者照著不存在的類別動手會寫出編譯不過的程式碼。

**豁免的可見性**：被標記豁免的行不列為違規，但計數會出現在報告（`Exempt (marked in source): N`）。靜默略過的行與掃描器看不見的行無法區分，讀者也就無從判斷標記是否真的生效。

**單一規則來源**：PostEdit hook（`.claude/hooks/dart-style-guardian-hook.py`）匯入 `style_checker` 的規則與校準，不另維護一份。兩套規則各自演化的結果是 hook 與 skill 給出互相矛盾的建議。

---

## Detection Script Usage

### Manual Scan

```bash
# Scan entire project
uv run .claude/skills/dart-style-guardian/scripts/style_checker.py scan lib/

# Scan specific directory
uv run .claude/skills/dart-style-guardian/scripts/style_checker.py scan lib/presentation/

# Generate report
uv run .claude/skills/dart-style-guardian/scripts/style_checker.py report
```

### Hook Integration

The style checker is integrated into PostEdit Hook:
- Automatically scans edited files in `lib/presentation/`
- Reports violations in hook output
- Suggests fixes based on this guide

---

## Related Documentation

### Project Files

同上節，以角色而非路徑指涉：design system token 定義、theme 組裝入口、`l10n.yaml` 與其指向的 ARB、設計規格文件。要知道本專案的實際位置，讀 `.claude/config/dart-style-guardian.json` 與 `l10n.yaml`，或直接搜尋 token 類別名的定義處。

### Reference Files (in this SKILL)
- [Color System Reference](./references/color-system.md)
- [Spacing System Reference](./references/spacing-system.md)
- [Typography System Reference](./references/typography-system.md)

### External Resources
- [Flat Design Explained - MasterClass](https://www.masterclass.com/articles/flat-design-explained)
- [Best Practices for Flat Design - Usersnap](https://usersnap.com/blog/flat-design/)
- [Material Design 3 Color System](https://m3.material.io/styles/color/overview)

---

## Quick Reference Card

### Import Statement

```dart
import 'package:book_overview_app/core/ui/ui_config.dart';
```

### Common Replacements

| Type | Hardcoded | Configuration |
|------|-----------|---------------|
| **Color** | `Colors.blue` | `UIColors.primary` |
| **Success** | `Colors.green` | `UIColors.positive` |
| **Warning** | `Colors.orange` | `UIColors.negative` |
| **Spacing** | `16` | `UISpacing.md` |
| **Font** | `14` | `UIFontSizes.bodyMedium` |
| **Radius** | `8` | `UIBorderRadius.sm` |
| **Text** | `'My Library'` | `context.l10n!.libraryTitle` |

### Responsive Suffixes

| Suffix | Purpose | Example |
|--------|---------|---------|
| `.w` | Width scaling | `16.w` |
| `.h` | Height scaling | `16.h` |
| `.rsp` | Font scaling | `14.rsp` |
| `.r` | Radius scaling | `8.r` |

---

**Last Updated**: 2026-03-02
**Version**: 1.0.0
