# 掃描規則和鍵名建議

i18n_hardcode_checker 的掃描規則、排除模式和 ARB 鍵名建議邏輯。

## 排除規則

腳本會自動排除以下模式，避免誤判：

| 排除類型 | 說明 | 範例 |
|---------|------|------|
| 註解 | 單行、多行、文檔註解 | `// 這是註解`、`/* 多行 */`、`/// 文檔` |
| import 語句 | package 導入 | `import 'package:...'` |
| package 路徑 | URI 格式 package 引用 | `'package:flutter/...'` |
| ARB 檔案引用 | JSON 鍵值查詢 | `l10n!.keyName` |
| URL | 網址和協定 | `https://...`, `http://...` |
| 生成的檔案 | 自動產出檔案 | `.g.dart`, `generated/...` |
| l10n 目錄 | i18n 資源目錄 | `l10n/` 目錄全跳 |
| 常數字串定義 | 常數和 final 變數 | `const String KEY = '...'` |

## 建議鍵名邏輯

腳本會根據中文內容自動建議 ARB 鍵名，遵循命名規範：

### 基礎對應表

| 中文關鍵字 | 英文對應 | ARB 鍵名範例 |
|-----------|---------|------------|
| 成功 | success | `actionSuccess`, `submitSuccess` |
| 失敗 | failed/failure | `actionFailed`, `connectionFailed` |
| 錯誤 | error | `validationError`, `networkError` |
| 匯入 | import | `importFile`, `importBooks` |
| 匯出 | export | `exportData`, `exportReport` |
| 書籍 | book | `bookTitle`, `bookAuthor` |
| 載入 | loading | `dataLoading`, `pageLoading` |
| 完成 | completed/done | `taskCompleted`, `downloadDone` |
| 確認 | confirm | `confirmAction`, `confirmDelete` |
| 取消 | cancel | `cancelOperation` |
| 提交 | submit | `submitForm`, `submitData` |
| 搜尋 | search | `searchBooks`, `searchUsers` |
| 下一步 | next | `nextStep`, `nextPage` |
| 返回 | back | `backButton`, `goBack` |
| 等待 | waiting | `waitingForSync`, `waitingResponse` |

### 命名規範

鍵名遵循以下規範：

1. **格式**：camelCase（小駝峰）
2. **結構**：`[上下文][動詞/名詞][目標]`
3. **前綴**：可選的上下文前綴（form、button、message、label、tooltip）
4. **長度**：不超過 50 字元

### 範例

| 中文字串 | 上下文 | ARB 鍵名 | 說明 |
|---------|-------|---------|------|
| 確認 | 按鈕 | `confirmButton` | 確認按鈕 |
| 確認刪除 | 對話框 | `confirmDeleteDialog` | 確認刪除的對話框 |
| 載入中 | 狀態提示 | `loadingMessage` | 資料載入中的提示 |
| 網路錯誤 | 錯誤訊息 | `networkErrorMessage` | 網路錯誤的錯誤訊息 |
| 搜尋書籍 | 表單標籤 | `searchBooksLabel` | 搜尋書籍的標籤 |
| 匯出成功 | 成功提示 | `exportSuccessMessage` | 匯出成功的提示 |

## ARB 生成格式

腳本產出的 ARB JSON 格式：

```json
{
  "actionSuccess": {
    "value_zh": "成功",
    "value_en": "[TODO: Success]",
    "description": "From lib/presentation/screens/detail_screen.dart:42"
  },
  "confirmDeleteDialog": {
    "value_zh": "確認刪除",
    "value_en": "[TODO: Confirm Delete]",
    "description": "From lib/presentation/widgets/delete_dialog.dart:15"
  }
}
```

### 欄位說明

| 欄位 | 說明 |
|------|------|
| `value_zh` | 原始中文字串 |
| `value_en` | 英文翻譯佔位符（`[TODO: ...]`），待人工翻譯 |
| `description` | 來源位置，便於追蹤和驗證 |

## 使用批量替換腳本

當新增 ARB 鍵值並執行 `flutter gen-l10n` 後，使用批量替換腳本：

```bash
# 預檢查（dry run）
uv run scripts/i18n_batch_replace.py --target lib/presentation

# 預檢查 + 生成報告
uv run scripts/i18n_batch_replace.py --target lib/presentation --report

# 實際替換
uv run scripts/i18n_batch_replace.py --target lib/presentation --apply
```

腳本會根據已有的 ARB 對應關係，自動替換等級 A 的文字。

## 特殊情況處理

### 帶參數的中文字串

```dart
// 原始程式碼
Text('用戶：$userName')

// 對應 ARB
{
  "userLabel": "用戶：{name}",
  ...
}

// 替換後
Text(l10n.userLabel(name: userName))
```

### 複數形式

```dart
// 原始程式碼
Text('找到 $count 個結果')

// 對應 ARB（需支援 ICU plural）
{
  "searchResults": {
    "value_zh": "{count, plural, one{找到 1 個結果} other{找到 # 個結果}}",
    ...
  }
}
```

### 條件文字

```dart
// 原始程式碼
Text(isLoading ? '載入中...' : '已完成')

// 拆分為兩個 ARB 鍵值
{
  "loadingMessage": "載入中...",
  "completedMessage": "已完成"
}

// 替換後
Text(isLoading ? l10n.loadingMessage : l10n.completedMessage)
```

## 驗證和品質檢查

執行檢查和替換後，進行驗證：

```bash
# 1. 確認替換數量
uv run scripts/i18n_hardcode_checker.py --json | jq '.summary'

# 2. 查看剩餘的硬編碼
uv run scripts/i18n_hardcode_checker.py --report > docs/i18n-remaining.md

# 3. 比較前後變化
# 計算替換率：(原始總數 - 剩餘總數) / 原始總數
```

## 常見的鍵名衝突

| 衝突情況 | 解決方案 |
|---------|---------|
| 多個地方使用相同文字 | 合併為同一個 ARB 鍵值（複用） |
| 相似但不同語境的文字 | 分開建立不同的 ARB 鍵值 |
| 層級不同的相同文字 | 根據層級加入前綴（formConfirm vs buttonConfirm） |
| 地區特定的措辭 | 使用 ARB 地區後綴（en_US, zh_CN） |

## 與其他 i18n 工具整合

### flutter_gen 使用 ARB 鍵名

生成後的 Dart 程式碼：

```dart
// 生成的 l10n.dart
class AppLocalizations {
  String get actionSuccess => _localizedValues['actionSuccess']![locale.languageCode]!;
  String get confirmButton => _localizedValues['confirmButton']![locale.languageCode]!;
  // ...
}
```

### Easy Localization 相容性

若使用 easy_localization 而非 flutter_gen，ARB 鍵名無須更改，但呼叫方式不同：

```dart
// flutter_gen
Text(l10n.actionSuccess)

// easy_localization
Text('actionSuccess'.tr())
```

---

*Last Updated: 2026-03-02*
*Version: 1.0.0*
