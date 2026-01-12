# Internationalization (i18n) Guidelines

## Overview

This project supports **10 languages** and uses Flutter's built-in localization system. All user-facing text must be internationalized.

### Supported Languages

| Code | Language | Primary Markets |
|------|----------|-----------------|
| `en` | English | Global |
| `en_US` | English (US) | United States |
| `zh_TW` | Traditional Chinese | Taiwan, Hong Kong |
| `zh_CN` | Simplified Chinese | Mainland China |
| `zh` | Chinese (fallback) | General Chinese |
| `es` | Spanish | Spain, Latin America |
| `fr` | French | France, Canada |
| `hi` | Hindi | India |
| `ja` | Japanese | Japan |
| `ko` | Korean | South Korea |

---

## File Structure

### ARB Files Location

```
lib/l10n/
├── app_en.arb      # English (base)
├── app_en_US.arb   # English (US)
├── app_zh_TW.arb   # Traditional Chinese
├── app_zh_CN.arb   # Simplified Chinese
├── app_zh.arb      # Chinese (fallback)
├── app_es.arb      # Spanish
├── app_fr.arb      # French
├── app_hi.arb      # Hindi
├── app_ja.arb      # Japanese
└── app_ko.arb      # Korean
```

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

## Validation Tools

### Check i18n Keys

```bash
# Using make command
make check-i18n

# Using script directly
dart scripts/check_i18n_keys.dart

# Using shell script
./scripts/check_i18n.sh
```

### Run i18n Tests

```bash
# Using make command
make test-i18n

# Using flutter test
flutter test test/widget/localization/
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

```dart
// Violation
throw Exception('An error occurred');
showError('Failed to load');

// Fix
throw Exception(context.l10n!.genericError);
showError(context.l10n!.loadError);
```

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

1. **Technical identifiers** - Error codes, keys
2. **Brand names** - "Flutter", "Google Books"
3. **Formatting characters** - `/`, `-`, `:`
4. **Numbers and units** - When culture-independent

```dart
// These are OK without i18n
Text('ISBN: $isbn')  // Technical identifier
Text('Flutter')      // Brand name
Text('v1.0.0')       // Version number
```

---

## Best Practices

1. **Never hardcode user-facing text** - Always use l10n
2. **Provide context in @descriptions** - Helps translators
3. **Use semantic key names** - `errorMessage` not `error1`
4. **Test all languages** - Verify translations work correctly
5. **Handle long text** - Some languages expand 30%+
6. **Consider RTL** - Arabic, Hebrew support if needed
7. **Use plural forms** - Different languages have different plural rules
