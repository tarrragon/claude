# Color System Reference

## Design Philosophy

### Three-Color System

This project uses a **Flat Design 2.0** approach with a **monochrome color system**:

- **Primary (90%)**: Blue - main interactive elements, branding
- **Positive (5%)**: Green - success states, confirmations
- **Negative (5%)**: Orange - warnings, errors, destructive actions

**Important**: Red is NOT used in this project. All error/warning states use Orange.

---

## 顏色歸類判準（primary／positive／negative 判不出來時）

分類依據是**元件本身的功能類型**，不是它所屬操作的業務後果——上方〈Three-Color System〉逐項列出的是元件功能（「success states, confirmations」屬 positive；「warnings, errors, destructive actions」屬 negative），功能類型不因觸發它的前置操作是否具破壞性而改變。

【輸入】

```
情境：刪除按鈕觸發刪除動作；刪除完成後顯示「已刪除」提示訊息
```

【產出】

```
形態：決策表

元件                    | 分類     | 理由
------------------------|----------|------------------------------------------------
刪除按鈕（觸發刪除動作） | negative | 元件本身是「destructive actions」（negative 分類項）
「已刪除」完成提示       | positive | 元件本身是「confirmations」（positive 分類項），
                                      不因其對應操作具破壞性而改判
```

【驗證】

```
檢驗問句
Q 分類依據是元件本身的功能類型，還是它所屬操作的業務後果？
  預期：元件本身的功能類型（〈Three-Color System〉逐項列出的是功能，非後果）
Q 「已刪除」提示是否因跟隨一個破壞性操作而改判 negative？
  預期：否——confirmations 已明列於 positive，功能類型不因前置操作改變
```

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

## Theme 與 Token 判準（第 4 項「Prefer theme colors」與「一律用 token」的交界）

`SKILL.md`〈Key Files〉已定義 Theme 是「組裝 tokens 為 ThemeData 的入口」——Theme 的值來自 token，兩者不是互斥的兩套系統，判準是「Flutter 內建語意插槽是否已覆蓋這個 token 語意」。對應的內建語意插槽存在時用主題插槽，不存在時用 token。無法確定某語意是否有內建插槽時，查閱當前框架版本的 ColorScheme／TextTheme 官方欄位清單再判定，不憑記憶。

【輸入】

```
規則：Theme 由 token 組裝而成（SKILL.md〈Key Files〉「Theme」列）
情境：程式需要設定按鈕文字顏色為主要品牌色
```

【產出】

```
形態：決策表

情境                                    | 判定           | 理由
------------------------------------------|----------------|--------------------------------------------
內建主題插槽已覆蓋這個顏色語意             | 採用主題提供的對應插槽 | 主題由 token 組裝，兩者值一致，優先用內建插槽減少樣板碼
內建主題插槽未覆蓋這個顏色語意（如細分色階、專案自訂語意） | 直接採用元件庫顏色 token | 主題沒有這個語意插槽，繞過 token 會失去單一事實來源
```

【驗證】

```
檢驗問句
（本則驗證問句經非撰寫者兩輪複核仍無法由引文逐詞推出，已刪除；判定依據見本節判準段方向句）
```

附註（本專案語法查表，非三段鏈式範例本身；用途是讓讀者比對自己手上的 Dart 程式碼，不承載本判準的判定依據）：

```dart
// 內建主題插槽已覆蓋（ColorScheme.primary 對應 token 的 primary）
Theme.of(context).colorScheme.primary

// 內建主題插槽未覆蓋（token 的 positive／negative 無對應標準欄位）
UIColors.positive
```
