# 實作品質標準

本文件定義所有實作類代理人（parsley、thyme、cinnamon 等）必須遵循的程式碼品質基線。

> **核心原則**：品質規則只寫一次，所有實作代理人統一引用本文件。
>
> **適用範圍**：所有會產出或修改程式碼的代理人。

---

## 1. 通用規則（所有語言適用）

### 1.1 命名規範

> **原則**：名稱本身就是文件，讓閱讀者不需要額外資訊。

#### 變數命名

| 規則 | 正確 | 錯誤 |
|------|------|------|
| 描述「這是什麼」 | `valid_user` | `user_after_validation` |
| 布林以 is/has/can 開頭 | `is_active`, `has_permission` | `active`, `permission` |
| 集合使用複數 | `users` | `user_list` |
| 禁止模糊詞 | `discountAmount` | `data`, `temp`, `flag`, `info` |

#### 函式命名

| 規則 | 正確 | 錯誤 |
|------|------|------|
| 動詞開頭 | `validate_input()` | `input()` |
| 描述「做什麼」 | `calculate_sum()` | `process()`, `handle()`, `do()` |
| 對稱命名 | `open_` / `close_` | `open_` / `end_` |

#### 類別命名

| 規則 | 正確 | 錯誤 |
|------|------|------|
| 描述業務責任 | `BookMetadataEnrichmentService` | `Manager`, `Helper` |
| 名詞 | `SearchQuery` | `DoSearch` |

#### 禁止的命名模式

| 模式 | 問題 | 替代 |
|------|------|------|
| 匈牙利命名法 | `strName`, `intCount` | `name`, `count` |
| 無意義前綴 | `theUser`, `aBook` | `user`, `book` |
| 過度縮寫 | `usrMgr` | `userManager` |
| 數字後綴 | `user1`, `user2` | `primaryUser`, `secondaryUser` |

---

### 1.2 函式設計

| 指標 | 理想值 | 上限 | 超過時 |
|------|-------|------|--------|
| 函式長度 | 5-10 行 | 30 行 | 必須拆分 |
| 參數數量 | 1-2 個 | 3 個 | 考慮封裝為物件 |
| 巢狀深度 | 1-2 層 | 3 層 | 使用 Guard Clause |
| 區域變數 | 2-3 個 | 5 個 | 考慮拆分 |

**單一責任判斷**：如果描述函式需要「和」或「或」→ 必須拆分。

**Guard Clause 優先**：

```
# 錯誤：深層巢狀
if user:
    if user.is_admin:
        if has_permission:
            do_something()

# 正確：提前返回
if not user: return
if not user.is_admin: return
if not has_permission: return
do_something()
```

---

### 1.2.1 作用域變更防護（重構時強制）

> **來源**：IMP-003 — 變數從全域移入函式內部後，引用該變數的其他函式產生 NameError。
>
> **觸發時機**：任何涉及「變數作用域變更」的重構（全域→區域、模組級→函式內、類別屬性→方法參數）。

**強制檢查清單**（修改作用域前必須完成）：

| 步驟 | 動作 | 驗證方式 |
|------|------|---------|
| 1 | 列出所有引用該變數的函式 | `grep` 或 AST 分析 |
| 2 | 每個函式確認：透過參數接收？還是依賴全域？ | 逐一檢查函式簽名 |
| 3 | 依賴全域的函式必須新增參數 | 修改函式簽名 |
| 4 | 所有呼叫端必須傳遞新參數 | 修改所有 call site |

**驗證優先級**：

| 驗證方式 | 可偵測作用域問題 | 推薦度 |
|---------|----------------|-------|
| AST 分析 | 是 | 最佳 |
| 實際執行 | 是 | 推薦 |
| py_compile | 否（只驗語法） | 不足 |

**禁止行為**：

| 禁止行為 | 原因 |
|---------|------|
| 只移動變數定義，不檢查引用 | 產生 NameError |
| 僅用 py_compile 驗證 | 無法偵測作用域問題 |
| 把變數改回全域以「修復」 | 違反重構目標 |

> 完整錯誤模式：.claude/error-patterns/implementation/IMP-003-refactoring-scope-regression.md

---

### 1.3 常數管理（禁止硬編碼）

> **核心原則**：所有非程式邏輯本身的字面值都必須提取為具名常數。

#### 1.3.1 禁止硬編碼字串

| 類型 | 錯誤 | 正確 |
|------|------|------|
| 使用者訊息 | `print("找不到檔案")` | `print(Messages.FILE_NOT_FOUND)` |
| 錯誤訊息 | `raise Exception("無效格式")` | `raise InvalidFormatError()` |
| 格式字串 | `f"版本: {v}"` | `f"{Labels.VERSION}: {v}"` |
| 提示文字 | `"請輸入名稱"` | `Prompts.ENTER_NAME` |

**訊息常數的組織方式**：

```
# 每個模組有對應的 messages 檔案
module/
  commands/
    create.py            # 使用 CreateMessages
    track.py             # 使用 TrackMessages
  lib/
    messages.py          # 共用訊息
    commands_messages.py  # 命令專用訊息
```

**允許的例外**：

| 例外 | 原因 |
|------|------|
| 日誌訊息（Logger/print） | 供開發者閱讀，非使用者介面 |
| 測試斷言字串 | 測試專用，不面向使用者 |
| 程式碼內部的技術標識 | 如 key name、format pattern |

#### 1.3.2 禁止魔法數字

| 錯誤 | 正確 | 說明 |
|------|------|------|
| `line[9:]` | `line[len(PREFIX):]` | 用 len() 動態計算 |
| `sleep(3)` | `sleep(RETRY_DELAY_SECONDS)` | 具名常數 |
| `if count > 50:` | `if count > MAX_ITEMS:` | 具名常數加註解 |
| `range(5)` | `range(MAX_RETRIES)` | 具名常數 |

**常數定義位置**：

| 作用域 | 定義位置 |
|-------|---------|
| 單一函式內使用 | 函式頂部區域常數 |
| 單一檔案多處使用 | 檔案頂部模組常數 |
| 跨模組共用 | 獨立常數檔案（constants.py / constants.dart） |

#### 1.3.3 配置與程式碼分離

| 問題 | 若答「是」 | 放置位置 |
|------|-----------|---------|
| 會隨環境改變？ | 是 | YAML/ENV 配置 |
| 非工程師可能修改？ | 是 | YAML 配置 |
| 是業務規則？ | 是 | 常數檔 + 註解 |
| 與程式邏輯緊密耦合？ | 是 | 程式碼內常數 |

---

### 1.4 DRY 原則

> **Every piece of knowledge must have a single, unambiguous, authoritative representation within a system.**

| 重複類型 | 範例 | 處理方式 |
|---------|------|---------|
| 完全相同 | 複製貼上的程式碼 | 提取到共用模組 |
| 結構相同 | 相似但參數不同 | 提取並參數化 |
| 概念相同 | 同目的不同實作 | 統一介面 |

**量化標準**：程式碼重複率 < 10%

---

### 1.5 認知負擔閾值

```
認知負擔指數 = 變數數 + 分支數 + 巢狀深度 + 依賴數
```

| 指數 | 評估 | 行動 |
|------|------|------|
| 1-5 | 優良 | 維持 |
| 6-10 | 可接受 | 考慮優化 |
| 11-15 | 需重構 | 建立重構 Ticket |
| > 15 | 必須重構 | 立即處理 |

> 詳細閾值：.claude/rules/core/cognitive-load.md

---

### 1.6 註解標準

> **原則**：註解記錄需求和設計意圖，不解釋程式碼做什麼。

**註解是**：需求保護器、設計意圖記錄、維護指引
**註解不是**：程式碼翻譯、API 說明、TODO 清單

**標準格式**：

```
/// 需求：[UC/BR-xxx] [簡短描述]
/// [詳細業務描述]
/// 約束：[限制條件和邊界規則]
/// [維護指引：修改須知、相依性警告]
```

**覆蓋要求**：

| 程式碼類型 | 需要需求註解 |
|-----------|------------|
| 業務邏輯函式 | 是（100%） |
| 純技術工具函式 | 否 |
| 值物件建構式 | 是（約束條件） |
| Domain 模型方法 | 是（業務規則） |

**禁止的註解**：

| 類型 | 範例 | 原因 |
|------|------|------|
| 程式碼翻譯 | `// 將計數器加 1` | 程式碼已自明 |
| 技術實作描述 | `// 用 Map 做快速查找` | 程式碼已自明 |
| 過時的 TODO | `// TODO: 之後加驗證` | 應建 Ticket 追蹤 |

> 完整方法論：.claude/methodologies/comment-writing-methodology.md

---

## 2. Dart/Flutter 補充規則

> 本節僅列出 Dart/Flutter 的**差異規則**，通用規則見第 1 節。

### 2.1 Package 導入

```dart
// 正確：package 格式
import 'package:book_overview_app/domains/library/entities/book.dart';

// 錯誤：相對路徑
import '../entities/book.dart';
```

- 100% 使用 `package:book_overview_app/` 格式
- 禁用 `as` 別名，重構命名解決衝突
- 測試檔案同樣使用 package 格式

> 完整方法論：.claude/methodologies/package-import-methodology.md

### 2.2 i18n 管理

**ViewModel 層三個合法訊息來源**：

| 來源 | 用途 | 範例 |
|------|------|------|
| i18n 系統 | 靜態訊息 | `context.l10n!.invalidFileFormat` |
| ErrorHandler | 錯誤碼對應 | `ErrorHandler.getUserMessage(exception)` |
| Exception.message | 僅限系統異常透傳 | `catch (e) => e.toString()` |

**分層責任**：

| 層級 | 責任 | 禁止 |
|------|------|------|
| Domain/Service | 拋出 Exception + ErrorCode | 使用 i18n、硬編碼訊息 |
| ViewModel | ErrorCode → i18n 訊息 | 硬編碼使用者訊息 |
| UI | 顯示 ViewModel 提供的訊息 | 自行組裝訊息 |

> 完整方法論：.claude/methodologies/business-layer-i18n-management-methodology.md

### 2.3 錯誤處理

```dart
// 正確：使用預編譯錯誤
throw CommonErrors.titleRequired;
throw BusinessException.duplicate(book.isbn);

// 錯誤：字串拋出
throw 'Title is required';
throw Exception('Book already exists');
```

### 2.4 Lint 規則

由 `analysis_options.yaml` 強制執行：

| 規則 | 說明 |
|------|------|
| `avoid_print: true` | 使用 AppLogger/TestLogger |
| `prefer_single_quotes: true` | 統一使用單引號 |
| `prefer_const_constructors: true` | 優先使用 const |
| `prefer_final_locals: true` | 區域變數優先 final |

---

## 3. Python 補充規則

> 本節僅列出 Python 的**差異規則**，通用規則見第 1 節。

### 3.1 風格與型別

- 遵循 PEP 8 風格
- 所有公開函式必須有完整的型別標註
- 公開函式必須有文件字串（docstring）

### 3.2 執行方式

- **必須**使用 UV 執行：`uv run pytest ...`、`uv run python script.py`
- 禁止直接使用 `python3` 或 `pip`（除非 UV 不可用）

> 詳細規則：.claude/rules/core/python-execution.md

### 3.3 訊息常數管理

Python 模組的硬編碼字串必須提取到專用 messages 模組：

```python
# 正確：集中管理
class CreateMessages:
    SUCCESS = "Ticket {ticket_id} 建立成功"
    MISSING_TITLE = "缺少必填欄位：title"

# 使用
print(CreateMessages.SUCCESS.format(ticket_id=tid))

# 錯誤：散落各處
print(f"Ticket {tid} 建立成功")
```

**命名規範**：

| 常數類型 | 命名規則 | 範例 |
|---------|---------|------|
| 訊息常數 | 大寫蛇形 | `FILE_NOT_FOUND` |
| Messages 類別 | PascalCase + Messages | `CreateMessages` |
| 格式化 | 使用 `format()` 佔位符 | `"{name} 已完成"` |

### 3.4 魔法數字消除

Python 特有的處理方式：

| 方法 | 適用場景 | 範例 |
|------|---------|------|
| `len()` | 字串前綴長度 | `line[len(PREFIX):]` |
| `removeprefix()` | Python 3.9+ | `line.removeprefix(PREFIX)` |
| `IntEnum` | 相關常數群組 | `class Limits(IntEnum)` |

---

## 4. 統一品質檢查清單

### 4.1 所有語言通用

#### 命名

- [ ] 函式以動詞開頭
- [ ] 變數完整描述內容，無縮寫
- [ ] 布林變數以 is/has/can 開頭
- [ ] 類別描述業務責任
- [ ] 無模糊詞（data, info, temp, flag）

#### 結構

- [ ] 函式長度 <= 30 行（理想 5-10 行）
- [ ] 巢狀深度 <= 3 層
- [ ] 參數數量 <= 3
- [ ] 認知負擔指數 < 10
- [ ] 作用域變更已完成影響範圍分析（1.2.1）

#### 常數管理

- [ ] 無硬編碼使用者訊息（提取為常數）
- [ ] 無魔法數字（使用具名常數）
- [ ] 配置與程式碼分離
- [ ] 無重複程式碼（DRY，重複率 < 10%）

#### 註解

- [ ] 業務邏輯函式有需求編號註解
- [ ] 無程式碼翻譯式註解
- [ ] 複雜邏輯有維護指引

### 4.2 Dart/Flutter 追加

- [ ] 100% package 格式導入
- [ ] ViewModel 無硬編碼使用者訊息
- [ ] 錯誤使用預編譯 Exception
- [ ] `dart analyze` 0 issues
- [ ] 測試 100% 通過

### 4.3 Python 追加

- [ ] 使用 UV 執行
- [ ] 型別標註完整
- [ ] 公開函式有 docstring
- [ ] 訊息提取到 Messages 類別

---

## 5. 代理人引用規則

| 代理人 | 必須遵循的章節 |
|--------|-------------|
| parsley-flutter-developer | 第 1 節 + 第 2 節 + 第 4.1 節 + 第 4.2 節 |
| thyme-python-developer | 第 1 節 + 第 3 節 + 第 4.1 節 + 第 4.3 節 |
| cinnamon-refactor-owl | 第 1 節全部（作為重構評估基線） |
| basil-hook-architect | 第 1 節 + 第 3 節（Hook 為 Python） |

---

## 相關文件

- .claude/rules/core/cognitive-load.md - 認知負擔詳細閾值
- .claude/rules/core/quality-baseline.md - 流程品質基線（測試、Phase 4）
- .claude/methodologies/natural-language-programming-methodology.md - 命名方法論
- .claude/methodologies/comment-writing-methodology.md - 註解方法論
- .claude/methodologies/business-layer-i18n-management-methodology.md - i18n 方法論
- .claude/methodologies/package-import-methodology.md - 導入路徑方法論
- .claude/error-patterns/implementation/IMP-001-scattered-duplicate-code.md - 重複程式碼模式
- .claude/error-patterns/implementation/IMP-002-magic-numbers.md - 魔法數字模式
- .claude/error-patterns/implementation/IMP-003-refactoring-scope-regression.md - 作用域迴歸模式

---

**Last Updated**: 2026-02-26
**Version**: 1.1.0 - 新增 1.2.1 作用域變更防護（W25-004）
