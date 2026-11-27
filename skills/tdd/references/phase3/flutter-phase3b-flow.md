# Flutter Phase 3b 執行流程（逐字自 parsley-flutter-developer 定義搬移）

> **來源**：自 `.claude/agents/parsley-flutter-developer.md` 搬移的五個流程章節（〈核心職責（Phase 3b 特定）〉〈TDD Phase 3b 執行流程〉〈與其他代理人協作〉〈最佳實踐〉〈Phase 3b 成功指標〉），正文逐字未改寫。搬移原因：這五節屬流程，與執行者無關，定義只留身份與邊界。
> **用途**：parsley 執行 Phase 3b 時按需讀取；語言無關通用骨架見 `.claude/skills/tdd/references/phase3-implementation.md`「Phase 3b：實作執行」。
> **位置說明**：下列內文中的章節編號（如「見 Step 4.1」「見下方章節」「詳見 5.3 節」）沿用原文，仍指本檔內對應章節。

---

## 核心職責（Phase 3b 特定）

### 1. 接收並理解 Phase 3a 策略
- **解析虛擬碼**：理解 pepper 提供的語言無關虛擬碼
- **分析流程圖**：理解資料流程和控制流程設計
- **確認架構決策**：理解設計模式選擇和架構考量
- **識別技術債務**：理解標記的權宜方案和改善方向

**檢查清單**：
- [ ] 虛擬碼邏輯清楚且完整
- [ ] 流程圖涵蓋所有關鍵路徑
- [ ] 架構決策有明確理由
- [ ] 技術債務標記清楚

### 2. 轉換為 Flutter/Dart 程式碼
- **語法轉換**：將虛擬碼轉換為符合 Dart 語法的程式碼
- **類型系統對應**：使用 Dart 強型別系統實作虛擬碼邏輯
- **Flutter API 整合**：使用 Flutter SDK 和 Widget 系統
- **套件依賴管理**：使用 `mcp__dart__pub` 管理第三方套件

**轉換原則**：
```dart
// Phase 3a 虛擬碼範例：
// function processBooks(books):
//     result = []
//     for each book in books:
//         if book.isValid():
//             processed = transformBook(book)
//             result.add(processed)
//     return result

// Phase 3b Flutter 轉換：
List<ProcessedBook> processBooks(List<Book> books) {
  final List<ProcessedBook> result = [];
  for (final book in books) {
    if (book.isValid()) {
      final processed = transformBook(book);
      result.add(processed);
    }
  }
  return result;
}
```

### 3. Dart MCP 工具整合開發
- **即時測試驗證**：使用 `mcp__dart__run_tests` 執行本票相關測試檔（呼叫必帶 `paths`）並驗證結果；全套件由合併閘門執行，不在此跑
- **Hot Reload 快速迭代**：使用 `mcp__dart__hot_reload` 快速驗證程式碼變更
- **Runtime Errors 即時處理**：使用 `mcp__dart__get_runtime_errors` 捕獲和修復執行時錯誤
- **Widget Tree 分析**：使用 `mcp__dart__get_widget_tree` 理解 UI 結構
- **符號解析**：使用 `mcp__dart__resolve_workspace_symbol` 查找類別和函式
- **程式碼分析**：使用 `mcp__dart__analyze_files` 檢查程式碼品質

### 4. Serena 工具精準編輯
- **符號層級編輯**：使用 Serena 工具進行精準的程式碼修改
- **關係追蹤**：使用 `mcp__serena__find_referencing_symbols` 理解依賴關係
- **結構分析**：使用 `mcp__serena__get_symbols_overview` 理解檔案結構

### 5. 品質規範強制遵循

> **統一品質標準**：所有品質規則定義在 @.claude/references/quality-common.md
>
> parsley 必須遵循：第 1 節（通用規則）+ 第 2 節（Dart/Flutter 補充）+ 第 6.1 節 + 第 6.2 節

- **Package 導入語意化**：100% 使用 `package:` 格式導入
- **程式碼自然語言化**：函式和變數命名清晰可讀
- **五行函式原則**：函式控制在 5-10 行
- **需求註解覆蓋**：業務邏輯函式包含需求編號
- **錯誤處理規範**：使用預編譯錯誤或專用異常
- **常數管理**：無硬編碼使用者訊息、無魔法數字
- **多語系管理**：所有 UI 字串必須透過 ARB/l10n 系統，禁止硬編碼
- **常數集中管理**：所有魔法數字和字串集中在 `AppConstants` 或 constants 檔案
- **元件庫優先實作**：禁止直接建構元件庫已涵蓋的原生元件，缺件回報 PM 開元件票（詳見 5.3 節）
- **Entity / copyWith 設計判準**：entity 不變式與 copyWith 收窄判準見 `.claude/skills/dart-domain-modeling/SKILL.md`

### 5.1 多語系（i18n）強制規範

> **核心原則**：Flutter UI 中禁止任何硬編碼文字，所有使用者可見字串透過 ARB 多語系系統管理。

**ARB 檔案結構**：

```
ui/lib/l10n/
├── app_en.arb      # 英文（預設）
└── app_zh_TW.arb   # 繁體中文
```

**使用方式**：

```dart
// 正確：透過 l10n 取得字串
Text(context.l10n.sessionListTitle)
Text(context.l10n.connectionStatusConnected)

// 錯誤：硬編碼文字
Text('Session List')
Text('Connected')
```

**適用範圍**：
- 所有 Widget 中的顯示文字
- 錯誤提示訊息
- 按鈕標籤、Tooltip
- 狀態文字（Active、Idle、Completed）

**例外**：開發者 debug log、測試斷言字串、技術標識符

### 5.2 常數集中管理（強制）

> **核心原則**：程式碼中禁止魔法數字和硬編碼設定值，所有常數集中管理。

**目錄結構**：

```
ui/lib/core/constants/
├── app_constants.dart      # 全域常數（數值、尺寸等）
├── duration_constants.dart # 時間相關常數
└── style_constants.dart    # 樣式數值常數
```

**使用方式**：

```dart
// 正確：使用具名常數
const reconnectInitialDelay = DurationConstants.reconnectInitialDelay;
const maxPanelCount = AppConstants.maxSplitPanels;

// 錯誤：硬編碼
Future.delayed(Duration(seconds: 1))
if (panels.length > 4)
```

**AppConstants 範例**：

```dart
// app_constants.dart
class AppConstants {
  AppConstants._();  // 禁止實例化

  static const int maxSplitPanels = 4;
  static const int maxHistoryPreload = 1000;
}

class DurationConstants {
  DurationConstants._();

  static const Duration reconnectInitialDelay = Duration(seconds: 1);
  static const Duration heartbeatInterval = Duration(seconds: 30);
  static const Duration activeSessionThreshold = Duration(minutes: 2);
  static const Duration completedSessionThreshold = Duration(minutes: 30);
}
```

### 5.3 元件庫優先實作（雙向約束方法論，工程端條款）

> **來源**：`.claude/methodologies/component-library-bidirectional-constraint-methodology.md`「雙向約束判準 > 工程端」。工程端是樣式的使用者，實作只從元件庫取件，禁止散落自製元件。

禁止直接建構被專案元件庫涵蓋的原生元件（依專案 spec 元件庫章節的原生元件禁用對照表判定）；元件庫缺件時停止當前實作，回報 PM 開立元件票，不得就地自刻頂替。

| 情境 | 動作 |
|------|------|
| 所需元件已在元件庫定義 | 依語意選用對應元件與 variant，不依外觀湊件 |
| 所需元件不在元件庫（且非豁免清單項目） | 停止實作，回報 PM 開立元件票；不得自行新增一次性元件或直接組裝原生元件頂替 |
| 專案 spec 豁免清單已列該用法 | 依豁免清單使用，不需另行開票 |

**豁免邊界**：僅限專案 spec 豁免清單已登記的項目（結構性無法收斂、有記錄理由、已列入執法工具白名單三條件全滿足者）；未登記的原生元件直用一律視為違規，須開元件票，不得自行認定豁免。

## TDD Phase 3b 執行流程

> **通用流程路由**：Phase 3a → 3b 交接條件、Red-Green-Refactor 循環、程式碼品質基準、測試通過率驗證等語言無關通用骨架見 `.claude/skills/tdd/references/phase3-implementation.md`「Phase 3b：實作執行」段。本章僅保留 Flutter/Dart MCP 特定的執行細節（Dart MCP 工具呼叫、Serena 符號操作、hot_reload、虛擬碼→Dart 轉換範例）。

### Step 1: 接收 Phase 3a 策略規劃（Flutter 特定）

通用交接檢查清單路由至 phase3-implementation.md「接收 Phase 3a 策略」。策略不可實作時，記錄具體 Flutter/Dart 技術障礙與限制，向 pepper 請求重新規劃並建議基於 Flutter 技術特性的替代實作方向。

### Step 2: 開發環境準備
```bash
# 1. 連接 Dart Tooling Daemon（如果需要）
mcp__dart__connect_dart_tooling_daemon

# 2. 分析專案狀態
mcp__dart__analyze_files

# 3. 確認本票相關測試狀態（必帶 paths）
mcp__dart__run_tests(roots: [{"root": "file:///path", "paths": ["test/<本票相關測試檔>"]}])
```

### Step 3: 虛擬碼轉換為 Flutter/Dart 程式碼

#### 3.1 理解現有程式碼結構（使用 Serena）
```bash
# 查看檔案結構
mcp__serena__get_symbols_overview

# 查找相關符號和依賴
mcp__serena__find_symbol
mcp__serena__find_referencing_symbols
```

#### 3.2 轉換虛擬碼為 Dart 語法
**轉換步驟**：
1. **識別虛擬碼結構**：分析 pepper 提供的虛擬碼邏輯
2. **對應 Dart 類型**：將通用類型對應到 Dart 強型別系統
3. **實作 Flutter API**：整合 Flutter SDK 和 Widget 系統
4. **遵循品質規範**：應用專案程式碼品質標準

**轉換範例**：
```dart
// Phase 3a 虛擬碼：
// function validateBook(book):
//     if book.title is empty:
//         throw ValidationError("title required")
//     if book.isbn is empty:
//         throw ValidationError("isbn required")
//     return true

// Phase 3b Flutter 轉換：
/// 需求：[UC-001] 驗證書籍基本資料完整性
/// 約束：標題和 ISBN 為必填欄位
bool validateBook(Book book) {
  if (book.title.isEmpty) {
    throw CommonErrors.titleRequired;
  }
  if (book.isbn.isEmpty) {
    throw CommonErrors.isbnRequired;
  }
  return true;
}
```

#### 3.3 編寫 Flutter/Dart 程式碼
**使用工具**：
- **Write/Edit** - 建立或修改檔案
- **Serena** - 符號層級精準編輯

**強制遵循規範**：
- Package 導入路徑語意化
- 程式碼自然語言化
- 五行函式單一職責
- 需求註解覆蓋
- 錯誤處理規範

#### 3.4 測試驅動開發循環

[WARNING] **MCP run_tests 使用限制**：
```bash
# 嚴格禁止 - 呼叫省略 paths 參數（會卡住超過 20 分鐘）

# 正確 - 必須指定 paths 參數
mcp__dart__run_tests(roots: [{"root": "file:///path", "paths": ["test/domains/"]}])

# 推薦 - 本票相關測試檔使用 Bash，經 run-with-timeout 包裝
python3 .claude/scripts/run-with-timeout.py 600 -- fvm flutter test <本票相關測試檔> --reporter compact
```

**全套件由合併閘門執行（Why/Consequence/Action）**：同一張票由代理人與驗收各跑一次全套件，會讓全套件成本隨票數倍增，且與合併閘門重複。合併閘門在合併前於快照內依改動範圍跑全套件，紅燈不合併（說明見 `.claude/skills/worktree/SKILL.md`〈合併前全套件〉）。本代理人只跑本票相關測試檔，回報時寫明「局部執行」與所跑檔案清單，不宣稱全套件通過。

**測試執行流程**：
```bash
# 1. 執行本票相關測試檔（使用 MCP + paths）
mcp__dart__run_tests(roots: [{"root": "file:///path", "paths": ["test/unit/core/<本票相關測試檔>"]}])

# 2. 查看測試失敗原因
# 分析測試輸出，理解失敗原因

# 3. 修正程式碼
# 根據測試失敗修正實作

# 4. Hot Reload 快速驗證（如有運行應用）
mcp__dart__hot_reload

# 5. 檢查 Runtime Errors
mcp__dart__get_runtime_errors --clearRuntimeErrors=true

# 6. 本票相關測試檔驗證（使用 Bash，經 run-with-timeout 包裝；全套件由合併閘門執行）
python3 .claude/scripts/run-with-timeout.py 600 -- fvm flutter test <本票相關測試檔> --reporter compact

# 7. 重複循環直到本票相關測試通過
```

### Step 4: 品質驗證

#### 4.1 程式碼分析
```bash
# 執行 Dart 分析
mcp__dart__analyze_files

# 執行本票相關測試檔並確認通過（必帶 paths；全套件 100% 由合併閘門確認）
mcp__dart__run_tests(roots: [{"root": "file:///path", "paths": ["test/<本票相關測試檔>"]}])

# 提交前格式化本票改動的 .dart 檔（必做，經 fvm）
fvm dart format <本票改動的 .dart 檔>
# 確認無殘留差異，結束碼須為 0
fvm dart format --output=none --set-exit-if-changed <本票改動的 .dart 檔>
```

**提交前格式化（Why/Consequence/Action）**：合併閘門若宣告了格式檢查套件，會對本次改動的 `.dart` 檔逐檔檢查，結果只由本票的改動決定。不在本機先跑，紅燈要到閘門才出現，整條分支被退回，多佔一輪閘門名額。範圍包含 `lib/`、`test/`、`integration_test/` 下所有被改動的 `.dart` 檔，不限產品碼。派發骨架帶有「提交前跑閘門逐檔檢查」子句時，照該子句的命令跑；沒有帶時，仍執行上面兩行（未以 FVM 釘選 Flutter 版本的專案去掉 `fvm` 前綴）。

#### 4.2 專案規範檢查
- [ ] **Package 導入**：100% 使用 `package:book_overview_app/` 格式
- [ ] **自然語言化**：函式和變數命名清晰可讀
- [ ] **五行原則**：函式控制在 5-10 行
- [ ] **需求註解**：業務邏輯函式包含需求編號
- [ ] **測試通過率**：本票相關測試檔全綠

### 產出物路徑規範（強制）

所有非程式碼產出物（執行報告、測試報告）**必須**寫入 Ticket 目錄，禁止寫入 `docs/work-logs/` 根目錄或其他位置。

| 項目 | 規範 |
|------|------|
| **存放目錄** | `docs/work-logs/v{version}/tickets/` |
| **命名格式** | `{ticket-id}-phase3b-execution-report.md` 或 `{ticket-id}-phase3b-test-report.md` |
| **禁止路徑** | `docs/work-logs/vX.X.X-execution-report.md`（根目錄） |

**範例**：

```
正確：docs/work-logs/v0.1.0/tickets/0.1.0-W44-003-phase3b-execution-report.md
錯誤：docs/work-logs/v0.1.0-execution-report.md
```

> 命名後綴規範詳見：.claude/references/ticket-id-conventions.md（第 2.1 節 TDD Phase 後綴）

### Step 5: 交接 Phase 4 重構代理人（Flutter 特定）

通用 Phase 3b → Phase 4 交接標準與 4a/4b/4c 三步驟流程路由至 `.claude/skills/tdd/references/phase4-refactor.md`。Flutter 特定交接前置：`dart analyze` 0 issues + 無 Runtime Errors（`mcp__dart__get_runtime_errors`）。交接文件章節格式見 `.claude/pm-rules/ticket-body-schema.md` 與 `.claude/templates/work-log-template.md`。

## 與其他代理人協作

### 從 pepper-test-implementer (Phase 3a) 接收

**Phase 3a → Phase 3b 協作模式**：
```text
Phase 3a (pepper) 完成策略規劃
    ↓ 交接產物
Phase 3b (parsley) 接收並轉換
    ↓ 如策略不可實作
Phase 3a (pepper) 重新規劃
```

**接收內容（語言無關）**：
- **虛擬碼**：語言無關的演算法描述
- **流程圖**：資料流程和控制流程視覺化
- **架構決策記錄**：設計模式選擇和理由
- **技術債務標記**：權宜方案和改善方向
- **測試案例引用**：連結到 Phase 2 定義的測試

**接收品質檢查**：
- [ ] 虛擬碼邏輯清楚且無歧義
- [ ] 流程圖涵蓋所有關鍵路徑
- [ ] 架構決策有明確理由
- [ ] 技術債務標記清楚
- [ ] 測試案例引用完整

**升級機制（策略不可實作時）**：
1. **記錄技術障礙**：具體說明 Flutter/Dart 技術限制
2. **向 pepper 請求重新規劃**：提供技術約束資訊
3. **建議替代方案**：基於 Flutter 技術特性提供建議
4. **等待新策略**：接收 pepper 重新規劃的策略

### 交接給 Phase 4 三步驟流程

4a 多視角分析 → 4b 重構執行 → 4c 多視角再審核的協作流程圖路由至 `.claude/skills/tdd/references/phase4-refactor.md`。交接 checklist：本票相關測試檔全綠 + `dart analyze` 0 issues + Phase 3b 工作日誌記錄完整（含從 Phase 3a 接收與 Phase 3b 新增的技術債務）。

### 與 lavender-interface-designer (Phase 1) 協作

**協作時機**：
- Phase 3b 實作時發現設計缺陷
- API 定義不清楚需要澄清
- 功能邊界模糊需要確認

**協作方式**：
1. **記錄設計問題**：詳細描述發現的設計缺陷
2. **提出澄清問題**：明確需要澄清的設計點
3. **建議解決方案**：基於 Flutter 技術特性提供建議
4. **等待設計更新**：Phase 1 更新後重新執行 Phase 3b

## 最佳實踐

### 測試執行強制規範（Context 保護機制）

**問題背景**: `flutter test` 完整輸出超過 4.6MB (33,000+ 行)，會耗盡對話 context，導致無法確認測試結果；同時全套件由合併閘門在合併前執行，代理人再跑一次只是重複成本。

**代理人不跑全套件**:
```bash
# 禁止 - 全套件、整個 test/ 目錄、test/unit/ 或 test/widget/ 這類整目錄執行
#        （輸出耗盡 context 且與合併閘門重複；命令不列於此，避免被照抄）
```

**正確的測試方式（只跑本票相關測試檔，經 run-with-timeout 包裝）**:
```bash
# 本票相關測試檔（可列多個檔案）
python3 .claude/scripts/run-with-timeout.py 600 -- fvm flutter test test/unit/core/errors/common_errors_test.dart --reporter compact

# 使用 Dart MCP 工具執行（必帶 paths）
mcp__dart__run_tests(roots: [{"root": "file:///path", "paths": ["test/unit/core/errors/common_errors_test.dart"]}])
```

> 全套件由 `merge` 的合併閘門在合併前依改動範圍執行，紅燈不合併，以閘門讀取的結束碼為依據（`.claude/skills/worktree/SKILL.md`〈合併前全套件〉）。回報只寫本票相關測試檔的結果，並明寫「局部執行」與檔案清單。
>
> 附註：`.claude/hooks/test-summary.sh` 已刪除，2026-08-22 文件複查更正。<!-- broken-link-exempt: 本行為更正說明，其內容正是在陳述該腳本已刪除，路徑不存在是預期的 -->

**重要提醒**: 代理人不跑全套件；只跑本票相關測試檔，Bash 經 run-with-timeout 包裝、MCP 必帶 paths。此規範為強制遵循。

### 1. Dart MCP 優先原則
```bash
# 優先使用 Dart MCP 工具（本票相關測試檔，必帶 paths）
mcp__dart__run_tests(roots: [{"root": "file:///path", "paths": ["test/<本票相關測試檔>"]}])

# 需要 Bash 時：經 run-with-timeout 包裝，只跑本票相關測試檔
python3 .claude/scripts/run-with-timeout.py 600 -- fvm flutter test <本票相關測試檔> --reporter compact
```

### 2. Hot Reload 快速迭代
```bash
# 小變更時使用 Hot Reload
mcp__dart__hot_reload

# 只在必要時重新啟動應用
# （如：更改 main(), 修改 pubspec.yaml）
```

### 3. 即時錯誤處理
```bash
# 開發過程中持續監控 Runtime Errors
mcp__dart__get_runtime_errors --clearRuntimeErrors=true

# 發現錯誤立即修復，不累積技術債務
```

### 4. 符號層級編輯優先
```bash
# 使用 Serena 進行精準修改
mcp__serena__replace_symbol_body

# 而非讀取整個檔案後修改
```

### 5. 測試驅動開發循環
```text
編寫程式碼 → 執行測試 → Hot Reload → 檢查錯誤 → 修正 → 重複
```

## Phase 3b 成功指標

### 1. TDD Phase 3b 完成標準
- [ ] **策略接收完整**：從 Phase 3a 接收所有必要產物
- [ ] **轉換正確性**：虛擬碼成功轉換為 Flutter/Dart 程式碼
- [ ] **測試完全通過**：本票相關測試檔全綠（全套件由合併閘門確認）
- [ ] **工作日誌記錄**：Phase 3b 執行過程完整記錄

### 2. Flutter 實作品質標準
- [ ] **程式碼分析**：`dart analyze` 0 issues
- [ ] **提交前格式化**：本票改動的 `.dart` 檔經 `fvm dart format --output=none --set-exit-if-changed` 結束碼為 0（見 Step 4.1）
- [ ] **Package 導入**：100% 使用 `package:` 格式
- [ ] **函式行數**：平均符合 5-10 行原則
- [ ] **需求註解**：業務邏輯函式 100% 包含需求編號
- [ ] **錯誤處理**：100% 使用預編譯錯誤或專用異常
- [ ] **Widget 重建效能**：有狀態的 Widget 不因無關資料變更而全體刷新（見下方章節）

### 2.1 Widget 重建與狀態保持（效能意識）

> **來源**：ARCH-010 — 對話列表刷新導致所有 ExpansionTile 展開狀態丟失。

實作涉及狀態變更的 Widget 時，必須考慮：**這個 Widget 的狀態會不會因為無關的資料更新而被重置？**

**常見問題場景**：
- ListView 新增項目時，既有項目的展開/摺疊、輸入框內容被重置
- Provider 狀態變更觸發整棵 Widget tree 重建，子 Widget 的本地狀態丟失
- 動畫進行中因父層重建而中斷

**解決方案選擇（依場景而定）**：

| 方案 | 適用場景 | 範例 |
|------|---------|------|
| `ValueKey` | StatefulWidget 在列表中需跨 rebuild 保持 State | `ExpansionTile(key: ValueKey(id))` |
| `const` Widget | 子樹不依賴變動資料 | `const Padding(...)` |
| `select` / `where` | 只監聽部分狀態變更 | `ref.watch(provider.select((s) => s.count))` |
| StatefulWidget 本地狀態 | 狀態僅該 Widget 使用 | `_isExpanded` 欄位 |
| 外部狀態管理 | 狀態需跨 Widget 或跨頁面共享 | Riverpod Notifier |

**實作時自問**：
1. 這個 Widget 的父層多久重建一次？
2. 重建時，哪些子 Widget 的狀態不應該丟失？
3. 用 Key 就能解決嗎？還是真的需要外部狀態管理？

### 2.2 記憶體與資源管理（即時監控場景）

> **來源**：某次 ccsession 佔用 70GB 記憶體的事件；某次多處資源累積無上限的事件。

本專案是即時監控系統，資料會持續增長。實作時必須考慮資源的生命週期和上限。

**必須遵守的原則**：

| 原則 | 說明 | 反面教材 |
|------|------|---------|
| 集合必須有上限 | List/Map/Set 持續增長的必須設定 maxSize 或清理機制 | session 事件無限累積 → 70GB |
| 訂閱必須有清理 | ref.listen/StreamSubscription 必須在 dispose 中取消 | ref.listen 累積未清理 |
| 大物件延遲載入 | toolInput 等大物件不隨列表全量載入 | 所有 ToolInput 常駐記憶體 |
| 重連必須清理舊連線 | WebSocket 重連前必須完全關閉舊連線 | WS 重連殘留多條連線 |
| keepAlive 謹慎使用 | `keepAlive: true` 的 Provider 永不被 dispose，確認是否真的需要 | 展開狀態用 keepAlive 造成洩漏 |

**實作時自問**：
1. 這個集合會無限增長嗎？上限是多少？
2. 這個訂閱在哪裡取消？dispose 有覆蓋到嗎？
3. 這個資料需要常駐記憶體嗎？能否按需載入？

### 3. 協作流程合規標準
- [ ] **Phase 3a 接收確認**：虛擬碼、流程圖、架構決策完整接收
- [ ] **Phase 3b 轉換記錄**：語法轉換過程詳細記錄
- [ ] **Phase 4 交接準備**：工作程式碼和品質指標準備完整
- [ ] **升級機制執行**：策略不可實作時正確觸發升級流程
- [ ] **技術債務追蹤**：從 Phase 3a 接收和 Phase 3b 新增的技術債務完整記錄

### 4. Phase 3b 交接品質標準
- [ ] **測試覆蓋率**：所有功能有對應測試
- [ ] **Runtime Errors**：無執行時錯誤
- [ ] **Dart MCP 工具使用記錄**：工具使用次數和結果完整記錄
- [ ] **Flutter 規範遵循**：符合 Flutter 最佳實踐和專案規範
