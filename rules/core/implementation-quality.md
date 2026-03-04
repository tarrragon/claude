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

**認知層 — 理解設計意圖（來源: IMP-013）**

在執行影響範圍分析之前，先質疑設計意圖：

| 步驟 | 質疑問題 | 判斷依據 |
|------|---------|---------|
| 1 | 這個參數/變數在舊版中是否被正確使用？ | 檢查實際呼叫和引用 |
| 2 | 如果舊版也未使用，原始設計意圖是什麼？ | git log / git blame / docstring |
| 3 | 在新設計中，這個參數應該在哪裡被使用？ | 需求文件 / 設計規格 |

**判斷結果**：
- 設計意圖已實現 → 繼續下方影響範圍分析
- 設計意圖未實現 → 補上實作，而非盲目沿用或移除
- 確認不再需要 → 移除並記錄原因到工作日誌

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

### 1.2.2 欄位格式溯源（修復時強制）

> **來源**：IMP-011 — 修復函式讀取 `direction` 欄位時，假設為簡單字串（`"to-sibling"`），但生產者實際輸出 `"to-sibling:target_id"`。精確匹配失敗，修復無效。
>
> **觸發時機**：任何修復程式碼中**讀取現有欄位/資料**來做判斷的場景。

**強制檢查清單**（寫修復程式碼前必須完成）：

| 步驟 | 動作 | 驗證方式 |
|------|------|---------|
| 1 | 列出修復程式碼讀取的所有欄位 | 程式碼審閱 |
| 2 | 找到每個欄位的**生產者**（寫入端函式） | `grep` 搜尋賦值位置 |
| 3 | 確認欄位的**完整格式**（所有變體） | 閱讀生產者程式碼 |
| 4 | 在程式碼註解中記錄格式規格 | 文件字串 |
| 5 | 測試案例覆蓋所有格式變體 | 測試每個變體 |

**正確做法**：

```python
def should_preserve(direction: str) -> bool:
    """判斷是否保留。

    direction 格式（來源：handoff.py._resolve_direction_from_args）：
    - "to-parent"（無後綴）
    - "to-sibling:{target_id}"（帶目標 ID）
    - "context-refresh"（非任務鏈）
    """
    # 使用前綴匹配，容許後綴變化
    direction_type = direction.split(":")[0]
    return direction_type in {"to-sibling", "to-parent", "to-child"}
```

**錯誤做法**：

```python
# 錯誤：基於假設使用精確匹配，未查閱生產者
def should_preserve(direction: str) -> bool:
    return direction in {"to-sibling", "to-parent", "to-child"}
    # "to-sibling:0.31.1-W3-002" 不在 set 中 → False
```

**禁止行為**：

| 禁止行為 | 原因 |
|---------|------|
| 基於欄位名稱假設格式 | 實際格式可能含後綴、前綴、分隔符 |
| 只看消費端推測格式 | 必須查閱生產端確認 |
| 測試只用「理想化」格式 | 必須從生產端取得真實格式做測試 |

> 完整錯誤模式：.claude/error-patterns/implementation/IMP-011-incomplete-format-matching.md

---

### 1.2.3 破壞性操作設計防護（自動刪除/清理/GC 時強制）

> **來源**：IMP-010 — GC 只檢查來源 Ticket 的 `status`，未考慮 handoff 的 `direction`，導致有效的 pending JSON 被誤刪。ARCH-002 — Plugin 解除安裝只清理部分儲存層，殘留的 `known_marketplaces.json` 觸發自動重新 clone。
>
> **觸發時機**：任何涉及**自動刪除、GC、快取清理、資料清除**的程式碼設計或修改。

**強制設計檢查清單**（寫破壞性操作程式碼前必須完成）：

| 步驟 | 問題 | 來源 |
|------|------|------|
| 1 | 刪除條件依賴的狀態值，在所有上下文中語義是否一致？ | IMP-010 |
| 2 | 是否需要額外欄位（上下文）才能做出正確的刪除決策？ | IMP-010 |
| 3 | 清理操作是否覆蓋所有儲存層（快取、註冊、目錄、配置）？ | ARCH-002 |
| 4 | 不確定時，預設行為是保留還是刪除？（必須為保留） | IMP-010 |

**正確做法**：

```python
# 正確：結合上下文欄位做刪除決策，不確定時保留
if is_ticket_completed(project_root, ticket_id, logger):
    direction = handoff_data.get("direction", "")
    direction_type = direction.split(":")[0]
    if direction_type in ("to-sibling", "to-parent", "to-child"):
        # 任務鏈 handoff，completed 是預期狀態，保留
        logger.info(f"保留 {direction_type} handoff: {ticket_id}")
        continue
    # 非任務鏈類型，completed 表示 stale，可清理
    file_path.unlink()
```

**錯誤做法**：

```python
# 錯誤：只檢查單一狀態值，不考慮上下文
if is_ticket_completed(project_root, ticket_id, logger):
    file_path.unlink()  # 一律刪除 → 誤刪有效的 handoff
```

**禁止行為**：

| 禁止行為 | 原因 |
|---------|------|
| 只依賴單一狀態值做刪除決策 | 同一狀態在不同上下文可能有不同語義（IMP-010） |
| 清理只處理部分儲存層 | 殘留的註冊/配置會觸發重建（ARCH-002） |
| 預設行為為刪除 | 破壞性操作應保守，不確定時必須保留 |

> 完整錯誤模式：.claude/error-patterns/implementation/IMP-010-gc-state-semantic-conflict.md
> 完整錯誤模式：.claude/error-patterns/architecture/ARCH-002-incomplete-cleanup.md

---

### 1.2.4 未使用程式碼處理（Phase 4 重構時強制）

> **來源**：IMP-013 — 重構時發現 unused code，應先質疑設計意圖而非盲目移除。
>
> **觸發時機**：Phase 4 重構評估中發現未使用的參數、變數、函式或類別時。

**強制檢查清單**（發現 unused code 時必須完成）：

| 步驟 | 動作 | 驗證方式 |
|------|------|---------|
| 1 | 追溯原始目的：這段程式碼為什麼存在？ | git log / git blame / docstring |
| 2 | 判斷類型：是「曾經有用但不再需要」還是「設計意圖未實現」？ | 對照需求文件和設計規格 |
| 3 | 如果是未實現的設計意圖 → 補上實作 | 建立 Ticket 追蹤 |
| 4 | 如果確認不再需要 → 移除並記錄原因 | 工作日誌記錄移除理由 |

**禁止行為**：

| 禁止行為 | 原因 |
|---------|------|
| 直接刪除 unused code 不記錄理由 | 設計意圖永遠消失 |
| 只依賴 linter 報告而不人工審查 | 無法區分「不再需要」與「未實現」兩種情況 |
| 重構時將「未使用」等同於「多餘」 | 可能是尚未完成的設計，移除會讓需求被遺忘 |

**核心教訓**：

> Unused code is a question, not an answer.
> 未使用的程式碼是一個待回答的問題（「為什麼存在？」），而不是一個已知的答案（「應該移除」）。

> 完整錯誤模式：.claude/error-patterns/implementation/IMP-013-refactoring-design-intent-blindness.md

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

### 2.2 常數集中管理（強制）

> **核心原則**：程式碼中禁止任何硬編碼數值或字串，所有常數集中在 `lib/core/constants/` 管理。

```
ui/lib/core/constants/
├── app_constants.dart      # 全域常數（Panel 數量上限等）
├── duration_constants.dart # 時間常數（重連間隔、心跳等）
└── style_constants.dart    # 樣式數值常數
```

```dart
// ✅ 正確
if (panels.length > AppConstants.maxSplitPanels)
Future.delayed(DurationConstants.reconnectInitialDelay)

// ❌ 錯誤：魔法數字/字串
if (panels.length > 4)
Future.delayed(Duration(seconds: 1))
```

### 2.3 i18n 多語系管理（強制）

> **核心原則**：UI 中禁止任何硬編碼顯示文字，所有使用者可見字串透過 ARB/l10n 系統。

```
ui/lib/l10n/
├── app_en.arb      # 英文（預設）
└── app_zh_TW.arb   # 繁體中文
```

```dart
// ✅ 正確
Text(context.l10n.sessionListTitle)
Text(context.l10n.connectionStatusConnected)

// ❌ 錯誤
Text('Session List')
Text('Connected')
```

**適用範圍**：Widget 文字、錯誤提示、按鈕標籤、狀態文字
**例外**：開發者 log、測試斷言、技術標識符（package name 等）

### 2.4 i18n 管理

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

## 3. Go 補充規則

> 本節僅列出 Go 的**差異規則**，通用規則見第 1 節。
> 適用版本：**Go 1.21+**（使用 `log/slog` 標準庫）

### 3.1 命名慣例（Effective Go）

| 類型 | 規則 | 正確 | 錯誤 |
|------|------|------|------|
| 套件名稱 | 小寫單詞，不用下劃線 | `parser`, `watcher` | `jsonlParser`, `file_watcher` |
| 導出名稱 | MixedCaps | `SessionEvent`, `ParseLine` | `session_event`, `parse_line` |
| 未導出名稱 | mixedCaps | `sessionID`, `parseRawLine` | `session_id`, `parse_raw_line` |
| 方法 | 不加 Get 前綴 | `Owner()` | `GetOwner()` |
| 介面（單方法） | 方法名 + `-er` | `Reader`, `Parser` | `IParser`, `ParserInterface` |
| 接收者 | 1-2 字母縮寫 | `(p *Parser)` | `(this *Parser)` |
| 錯誤變數 | `err` 或 `ErrXxx` | `ErrSessionNotFound` | `sessionError` |

**禁止**：蛇形命名、冗餘包名重複、縮寫（`usrMgr`）、模糊詞（`data`, `info`）

### 3.2 常數集中管理（強制）

每個 package 必須有 `constants.go` 集中定義所有常數，**程式碼中禁止硬編碼數值或字串**。

```go
// constants.go
type SessionStatus int

const (
    SessionStatusActive SessionStatus = iota
    SessionStatusIdle
    SessionStatusCompleted
)

const (
    DefaultPort            = 8765
    ActiveThresholdSeconds = 120
    MaxHistoryLines        = 1000
    HeartbeatIntervalSecs  = 30
)
```

**禁止行為**：

| 禁止 | 正確做法 |
|------|---------|
| `port := 8765` | `port := DefaultPort` |
| `time.Sleep(30 * time.Second)` | `time.Sleep(HeartbeatIntervalSecs * time.Second)` |
| `if count > 1000` | `if count > MaxHistoryLines` |

### 3.3 字串集中管理與多語系（強制）

所有字串統一在 `messages/` 目錄管理，**程式碼中禁止硬編碼任何字串**。

```
server/messages/
├── log_messages.go    # 開發者 log 訊息（英文常數）
├── api_messages.go    # API 錯誤碼（Client 可見）
├── cli_messages.go    # CLI 提示訊息
└── i18n/              # 使用者可見文字（多語系）
    ├── en.json
    └── zh-TW.json
```

```go
// ✅ 正確：使用常數
logger.Info(messages.LogNewSessionFile, "sessionID", id)
return WSResponse{Error: messages.ErrCodeSessionNotFound}

// ❌ 錯誤：硬編碼字串
logger.Info("new session detected", "id", id)
return WSResponse{Error: "session not found"}
```

Client 可見的錯誤使用**錯誤碼**（如 `"SESSION_NOT_FOUND"`），由 Client 側負責本地化顯示。

### 3.4 結構化日誌（log/slog，強制）

```go
// 初始化（main.go）
logger := slog.New(slog.NewJSONHandler(os.Stderr, &slog.HandlerOptions{
    Level: slog.LevelDebug,
}))

// 每條 log 必須包含 "layer" 欄位（UC-011 格式變動偵測）
logger.Warn(messages.LogUnknownField,
    "layer", "jsonl_parser",
    "field", unknownKey,
    "hint", messages.LogFormatChangeHint)
```

### 3.5 錯誤處理

```go
// ✅ Sentinel error（可比較）
var ErrSessionNotFound = errors.New("session not found")

// ✅ 自訂錯誤類型（含上下文）
type ParseError struct {
    SessionID string
    Cause     error
}
func (e *ParseError) Error() string { return fmt.Sprintf("parse session %s: %v", e.SessionID, e.Cause) }
func (e *ParseError) Unwrap() error { return e.Cause }

// ✅ 保留上下文
return fmt.Errorf("read file %s: %w", path, err)

// ❌ 丟棄上下文
return errors.New("read failed")
```

**禁止 `_ = err` 丟棄錯誤**，必須處理或明確在註解說明理由。

### 3.6 執行方式

- 所有 Go 指令必須在 `server/` 子目錄下執行，使用子 shell 避免 cd 污染：
  ```bash
  (cd server && go test ./...)
  (cd server && go vet ./...)
  (cd server && go build ./...)
  ```
- 禁止直接 `cd server`（污染 shell 工作目錄）

> 詳細規則：.claude/rules/core/bash-tool-usage-rules.md

---

## 5. Python 補充規則

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

## 6. 統一品質檢查清單

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

## 7. 代理人引用規則

| 代理人 | 必須遵循的章節 |
|--------|-------------|
| parsley-flutter-developer | 第 1 節 + 第 2 節 + 第 6.1 節 + 第 6.2 節 |
| fennel-go-developer | 第 1 節 + 第 3 節 + 第 6.1 節 + 第 6.4 節（新增） |
| thyme-python-developer | 第 1 節 + 第 5 節 + 第 6.1 節 + 第 6.3 節 |
| cinnamon-refactor-owl | 第 1 節全部（作為重構評估基線） |
| basil-hook-architect | 第 1 節 + 第 5 節（Hook 為 Python） |

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
- .claude/error-patterns/implementation/IMP-011-incomplete-format-matching.md - 格式假設錯誤模式

---

**Last Updated**: 2026-03-05
**Version**: 1.4.0 - 新增第 3 節 Go 規範（命名/常數/i18n/slog/錯誤處理）；第 2 節補充 Dart 常數和 i18n 管理；章節重新編號 3→4 Python、4→6 清單、5→7 代理人引用
