# Internationalization (i18n) Guidelines

## Overview

本 skill 為跨專案共用資產，支援語系數量與清單依各專案的 `l10n.yaml` 與實際 ARB 檔案為準，不在此列舉——寫死一份語系清單，其他專案讀到的就是一份與己身設定不符的清單。所有使用者可見文字必須經 Flutter 內建 localization 系統國際化。

**下方範例統一以 `context.l10n!.keyName` 示範存取語法，此為示意寫法之一。** 實際存取子形態（`AppLocalizations.of(context).keyName` 或專案自建 extension）以 `.claude/config/dart-style-guardian.json`〈i18n.accessor〉與專案 `l10n.yaml` 為準，套用前先確認本專案慣例（見 `SKILL.md`〈Internationalization〉）。

---

## File Structure

ARB 檔案位置與語系清單因專案而異，不在此列出實際路徑——實際位置讀專案的 `l10n.yaml`（`arb-dir` 欄位）。以下為 `l10n.yaml` 的通用設定範例（非本專案語系清單）：

### Configuration

In `pubspec.yaml`:

```yaml
flutter:
  generate: true

dependencies:
  flutter_localizations:
    sdk: flutter
  intl: ^0.20.2
```

In `l10n.yaml`:

```yaml
arb-dir: lib/l10n
template-arb-file: app_en.arb
output-localization-file: app_localizations.dart
```

---

## Usage Patterns

### Basic Text

```dart
// Correct
Text(context.l10n!.libraryTitle)

// Incorrect
Text('My Library')
```

### Parameterized Text

ARB definition:
```json
{
  "selectedCount": "{count} of {total} selected",
  "@selectedCount": {
    "placeholders": {
      "count": {"type": "int"},
      "total": {"type": "int"}
    }
  }
}
```

Usage:
```dart
// Correct
Text(context.l10n!.selectedCount(count, total))

// Incorrect
Text('$count of $total selected')
```

### Plural Forms

ARB definition:
```json
{
  "itemCount": "{count, plural, =0{No items} =1{1 item} other{{count} items}}",
  "@itemCount": {
    "placeholders": {
      "count": {"type": "int"}
    }
  }
}
```

Usage:
```dart
Text(context.l10n!.itemCount(items.length))
```

### Select/Gender Forms

ARB definition:
```json
{
  "greeting": "{gender, select, male{Hello Mr.} female{Hello Ms.} other{Hello}}",
  "@greeting": {
    "placeholders": {
      "gender": {"type": "String"}
    }
  }
}
```

---

## Adding New Translations

### Step 1: Add to Base ARB

Edit `lib/l10n/app_en.arb`:

```json
{
  "newFeatureTitle": "New Feature",
  "@newFeatureTitle": {
    "description": "Title for the new feature page"
  }
}
```

### Step 2: Add to Other Languages

Edit each language file (e.g., `app_zh_TW.arb`):

```json
{
  "newFeatureTitle": "新功能"
}
```

### Step 3: Generate Code

```bash
flutter gen-l10n
```

### Step 4: Use in Code

```dart
Text(context.l10n!.newFeatureTitle)
```

---

## Common Patterns

### AppBar Title

```dart
AppBar(
  title: Text(context.l10n!.settingsTitle),
)
```

### Button Labels

```dart
ElevatedButton(
  onPressed: () {},
  child: Text(context.l10n!.saveButton),
)
```

### Error Messages

```dart
ScaffoldMessenger.of(context).showSnackBar(
  SnackBar(content: Text(context.l10n!.errorMessage)),
);
```

### Dialog Content

```dart
AlertDialog(
  title: Text(context.l10n!.confirmDeleteTitle),
  content: Text(context.l10n!.confirmDeleteMessage),
  actions: [
    TextButton(
      onPressed: () => Navigator.pop(context),
      child: Text(context.l10n!.cancelButton),
    ),
    TextButton(
      onPressed: () => deleteItem(),
      child: Text(context.l10n!.deleteButton),
    ),
  ],
)
```

### Empty States

```dart
if (items.isEmpty)
  Center(
    child: Column(
      children: [
        Icon(Icons.inbox_outlined),
        Text(context.l10n!.emptyLibraryTitle),
        Text(context.l10n!.emptyLibraryMessage),
      ],
    ),
  )
```

---

## Common Violations

### Violation 1: Hardcoded UI Text

```dart
// Violation
Text('My Library')
AppBar(title: Text('Settings'))

// Fix
Text(context.l10n!.libraryTitle)
AppBar(title: Text(context.l10n!.settingsTitle))
```

### Violation 2: Hardcoded Error Messages

錯誤訊息的翻譯只發生在持有 `BuildContext`（或等價 localization 存取）的呈現層。拋出例外或回傳錯誤的位置（Repository／UseCase／ViewModel 等非 widget 層）通常不持有 context，不可在該處呼叫 `context.l10n!`；改丟未翻譯的錯誤碼或例外型別，交由呈現層以 `ErrorHandler` 轉譯（分層規則呼應 `SKILL.md`〈Violation 6〉）。

```dart
// Violation
throw Exception('An error occurred');
showError('Failed to load');

// Fix（非 widget 層：只丟錯誤碼，不在此處翻譯）
throw AppException(AppErrorCode.generic);
showError(AppErrorCode.loadFailed);

// Fix（呈現層：持有 context，在此處轉譯後才顯示）
Text(ErrorHandler.getUserMessage(context, errorCode))
```

此處丟出的錯誤碼本身屬〈Exceptions〉的技術識別符，不進 ARB；豁免只到錯誤碼值為止，顯示給使用者的訊息仍須轉譯（交界見〈判準：錯誤碼與使用者可見錯誤訊息的交界〉）。

### Violation 3: String Interpolation

```dart
// Violation
Text('${user.name} has ${user.books} books')

// Fix (use parameterized translation)
Text(context.l10n!.userBookCount(user.name, user.books))
```

### Violation 4: Hardcoded Hints/Labels

```dart
// Violation
TextField(
  hintText: 'Enter your name',
  decoration: InputDecoration(labelText: 'Name'),
)

// Fix
TextField(
  hintText: context.l10n!.nameHint,
  decoration: InputDecoration(labelText: context.l10n!.nameLabel),
)
```

---

## Exceptions

Some strings may NOT need i18n:

1. **Technical identifiers** - Error codes, keys（僅指識別符值本身：層間傳遞、寫入日誌、作為查表鍵；錯誤碼要讓使用者看到時，見〈判準：錯誤碼與使用者可見錯誤訊息的交界〉）
2. **Brand names** - "Flutter"
3. **Formatting characters** - `/`, `-`, `:`
4. **Numbers and units** - When culture-independent

標籤與識別符／數值組合出現時（如「標籤：值」），僅數值本身列入本豁免；標籤文字仍是使用者可見文字，需依〈Violation 3: String Interpolation〉的參數化翻譯方式處理，不得以字串插值直接拼接整句。

```dart
// These are OK without i18n（無標籤、無插值、值本身文化無關）
Text('Flutter')      // Brand name
Text('v1.0.0')       // Version number

// Violation（標籤與數值以字串插值直接拼接，整句誤判為豁免）
Text('ISBN: $isbn')

// Fix（標籤走 l10n 參數化翻譯；數值本身豁免不需要 i18n）
Text(context.l10n!.isbnLabel(isbn))
// ARB: "isbnLabel": "ISBN: {isbn}"
```

### 判準：標籤＋識別符組合時如何分割（culture-independent 的判定）

【輸入】

```
Exceptions 清單：技術識別符／品牌／格式字元／文化無關的數字單位免 i18n
規則：標籤與識別符組合時，僅數值本身豁免，標籤文字依 Violation 3 走參數化翻譯
情境：畫面需顯示「ISBN: 9789571234567」
```

【產出】

```
形態：決策表

片段                  | 是否豁免 | 理由
------------------------|----------|--------------------------------
「ISBN:」標籤          | 否       | 使用者可見文字，非識別符本身
「9789571234567」數值  | 是       | 技術識別符，文化無關（顯示形式不隨語系改變）
組合方式                | —        | 走 l10n 參數化翻譯（Violation 3 模式），不得字串插值直接拼接
```

【驗證】

```
檢驗問句
Q 整句「ISBN: 9789571234567」是否整體豁免 i18n？
  預期：否——只有數值片段豁免，標籤仍需翻譯
```

### 判準：錯誤碼與使用者可見錯誤訊息的交界

錯誤碼豁免的對象是識別符值本身：在層間傳遞（`throw AppException(AppErrorCode.loadFailed)`）、寫入日誌、作為 `ErrorHandler` 查表的鍵，都不進 ARB。使用者可見的錯誤訊息不在豁免範圍內，依〈Violation 2: Hardcoded Error Messages〉由呈現層轉譯後顯示。**錯誤碼不得取代訊息單獨顯示**，因為呈現層跳過轉譯就等於把未翻譯的內部值交給使用者。需要讓使用者看到錯誤碼（例如回報問題用的參考編號）時，錯誤碼必須跟在轉譯後的訊息旁，組合方式依〈Exceptions〉清單後「標籤與識別符／數值組合出現時」一段，照〈Violation 3: String Interpolation〉走參數化翻譯，只有錯誤碼值本身豁免。

```dart
// Violation（呈現層把錯誤碼當訊息直接顯示）
Text(state.errorCode.name)

// Fix（呈現層轉譯後顯示）
Text(ErrorHandler.getUserMessage(context, state.errorCode))

// Fix（需附參考編號：訊息轉譯，錯誤碼值以參數帶入）
Text(context.l10n!.errorWithReference(
  ErrorHandler.getUserMessage(context, state.errorCode),
  state.errorCode.name,
))
// ARB: "errorWithReference": "{message}（錯誤代碼：{code}）"
```

片段                         | 是否豁免 | 理由
-----------------------------|----------|------------------------------------------
層間傳遞的錯誤碼             | 是       | 技術識別符值，不對使用者顯示
呈現層只顯示錯誤碼、沒有訊息 | 否       | 使用者可見錯誤訊息被錯誤碼取代，違反〈Violation 2〉的呈現層轉譯
訊息旁附帶的錯誤碼值         | 是       | 識別符值本身；外圍文字走參數化翻譯

---

## Best Practices

1. **Never hardcode user-facing text** - Always use l10n
2. **Provide context in @descriptions** - Helps translators
3. **Use semantic key names** - `errorMessage` not `error1`
4. **Test all languages** - Verify translations work correctly
5. **Handle long text** - Some languages expand 30%+
6. **Consider RTL** - Arabic, Hebrew support if needed
7. **Use plural forms** - Different languages have different plural rules
