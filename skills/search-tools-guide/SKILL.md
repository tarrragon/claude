---
name: search-tools-guide
description: "搜尋工具使用指南。用於：(1) 選擇正確的搜尋工具, (2) rg 精確文字搜尋, (3) LSP/Serena 符號搜尋, (4) 工具安裝與故障排除"
---

# 搜尋工具指南

---

## 工具總覽與選擇

本專案的搜尋工具經過 W8-008~012 比較測試驗證，各有明確定位。

### 工具定位

| 工具 | 類型 | 定位 | 獨佔能力 |
|------|------|------|---------|
| **Grep (rg)** | 文字（正則） | 日常主力搜尋 | 正則搜尋、PCRE2、壓縮檔、多編碼、分頁、統計 |
| **WebSearch** | 網頁搜尋 | 唯一網頁搜尋工具 | 技術文件查詢、API 用法、版本資訊 |
| **Grep+Glob+Read** | 多步組合 | 多步驟研究預設方案 | 架構追蹤、程式碼路徑分析 |
| **Serena / LSP** | 語意（符號感知） | Dart 符號分析專用 | 符號定義/引用追蹤、重構、型別資訊 |
| **Dart MCP** | 語意（Dart 專用） | Dart 開發工具 | `analyze_files`、`dart_format`、`dart_fix` |
| **內建 Glob** | 檔名模式 | 檔案定位 | 按名稱找檔案 |

### 選擇決策樹

```
搜尋需求
    |
    v
需要搜尋什麼？
    |
    +-- 符號定義/引用/重構 --> Serena / LSP / Dart MCP
    |
    +-- 網頁資訊（技術文件、API、版本） --> WebSearch
    |
    +-- 跨檔案架構追蹤 --> Grep + Glob + Read 組合
    |   例：追蹤 Ticket 系統從 create 到 complete 的完整路徑
    |
    +-- 精確文字/正則模式 --> Grep（優先）或 rg（進階）
    |   例：`class\s+\w+\s+extends\s+StatelessWidget`
    |
    +-- 按檔名找檔案 --> 內建 Glob
        例：`**/*.dart`
```

### 什麼時候用什麼

| 場景 | 首選工具 | 備選 | 範例 |
|------|---------|------|------|
| 找某個類別定義 | Serena `find_symbol` | `rg "class ClassName"` | 找 BookRepository |
| 找某個方法的所有呼叫 | Serena `find_referencing_symbols` | `rg "\.methodName\("` | 找 fetchBooks 引用 |
| 找精確字串 | Grep / rg -F | - | 找 hardcoded 值 |
| 找正則模式 | Grep | rg（進階場景） | 找 import 模式 |
| PCRE2 (lookaround) | rg -P | 無替代 | 進階正則 |
| 搜尋壓縮檔 | rg -z | 無替代 | 搜尋 .gz |
| 查看符號型別 | Dart MCP `hover` | Serena `find_symbol` | 確認回傳型別 |
| 靜態分析 | Dart MCP `analyze_files` | 無替代 | 找 lint 問題 |
| 找檔案路徑 | 內建 Glob | rg -l | 找 *.test.dart |
| 技術文件查詢 | WebSearch | - | Flutter API、套件文件 |
| 跨檔案架構理解 | Glob + Grep + Read | - | 追蹤完整程式碼路徑 |

---

## rg (ripgrep) - 日常主力搜尋

### 核心概念

**ripgrep** 是基於 Rust 的高效能正則搜尋工具，是 Claude Code 內建 Grep 的底層引擎。

**效能特性**：使用有限自動機和 SIMD 最佳化、lock-free 並行目錄遍歷，比 GNU grep 快約 33 倍（Linux kernel 搜尋基準）。預設自動遵守 `.gitignore` 規則。

### 安裝

```bash
# macOS
brew install ripgrep

# Linux (Debian/Ubuntu)
sudo apt-get install ripgrep

# 通用（需要 Rust）
cargo install ripgrep
```

### rg vs 內建 Grep

| 功能 | 內建 Grep | rg (Bash) |
|------|----------|-----------|
| 基本正則搜尋 | 支援 | 支援 |
| 檔案類型過濾 | `glob` 參數 | `-t` / `-T` 參數 |
| 上下文顯示 | `-A` / `-B` / `-C` | `-A` / `-B` / `-C` |
| PCRE2 正則 | 不支援 | `-P` 支援 |
| 壓縮檔搜尋 | 不支援 | `-z` 支援（brotli, bzip2, gzip, lz4, xz, zstd） |
| 替換預覽 | 不支援 | `-r` 支援 |
| JSON 輸出 | 不支援 | `--json` 支援 |
| 排序控制 | 不支援 | `--sort` 支援 |
| 多編碼 | 不支援 | `-E` 支援（UTF-16, Latin-1, GBK, EUC-JP, Shift_JIS） |
| Preprocessor | 不支援 | `--pre` 支援（可搜尋 PDF 等） |
| 混合正則引擎 | 不支援 | `--auto-hybrid-regex` 自動切換 |

**結論**：一般搜尋用內建 Grep 即可，需要進階功能時用 rg。

### 常用指令速查

```bash
# 基本搜尋
rg "pattern" lib/              # 搜尋特定目錄
rg -i "pattern"                # 大小寫不敏感
rg -w "className"              # 全字匹配
rg -F "exact.string"           # 固定字串（非正則）

# 輸出控制
rg -l "pattern"                # 僅顯示檔案名稱
rg -c "pattern"                # 僅顯示計數
rg -C 3 "pattern"              # 前後各 3 行上下文
rg -m 5 "pattern"              # 限制最大匹配數

# 檔案類型過濾
rg -t dart "pattern"           # 僅搜尋 Dart
rg -t py "pattern"             # 僅搜尋 Python
rg -g "*.dart" "pattern"       # glob 過濾
rg -g "!*.test.dart" "pattern" # 排除模式

# 正則表達式
rg "class\s+\w+\s+extends"     # 基本正則
rg -P "(?<=class\s)\w+"        # PCRE2 (lookaround)
rg -U "class.*\{[\s\S]*?\}"    # 多行匹配

# 進階功能（rg 獨佔）
rg -z "pattern" archive.gz     # 搜尋壓縮檔
rg -E utf-16 "pattern"         # 搜尋非 UTF-8 編碼檔案
rg --pre cat "pattern"         # 使用 preprocessor（可搜尋 PDF 等）
rg --hidden "pattern"          # 搜尋隱藏檔案
rg --no-ignore "pattern"       # 搜尋 gitignore 忽略的檔案

# 替換預覽
rg "oldName" -r "newName"      # 不修改檔案，僅預覽
```

### Flutter / Dart 專案範例

```bash
# Widget 定義
rg -t dart "class\s+\w+\s+extends\s+(Stateless|Stateful)Widget"

# Provider 使用
rg -t dart "Provider\.(of|watch|read)" lib/

# 測試案例
rg -t dart "test(Widgets)?\(" test/

# TODO 和 FIXME
rg -t dart "(TODO|FIXME|HACK)" lib/

# Ticket 狀態
rg "status:\s*(pending|in_progress)" docs/work-logs/
```

### 概念性搜尋技巧（W8-010 結論）

rg 的主要弱點是同義詞覆蓋（召回率 ~79-87%），可透過多 Pattern 組合改善：

```bash
# 錯誤處理（基本 + 同義詞擴展）
rg "catch|try|error|exception|throw" lib/           # 基本
rg "failure|recover|fallback|retry|graceful" lib/    # 同義詞擴展

# 狀態管理（基本 + 生命週期概念）
rg "status|state|pending|in_progress|completed" lib/ # 基本
rg "lifecycle|transition|workflow|progress|phase" lib/ # 擴展

# 資料流向（基本 + 資料操作概念）
rg "parse|validate|save|store|write" lib/            # 基本
rg "transform|convert|persist|repository|serialize" lib/ # 擴展
```

**降噪技巧**：排除 l10n 和 import 噪音

```bash
rg "error" lib/ --glob '!lib/l10n/' --glob '!*.g.dart'
```

---

## Serena / LSP / Dart MCP - 符號導航與程式碼理解

### 核心概念

**Serena**、**LSP** 和 **Dart MCP** 提供語意感知的程式碼導航，理解符號定義、引用關係和型別系統。這是唯一能做到精確重構的工具類別。

### 重要限制（W8-011 結論）

**Serena 的 LSP 符號分析僅對 Dart 有效**。對 Python 檔案（如 ticket_system），`find_symbol` 會回傳空結果。Python 程式碼搜尋應使用 Grep。

### Serena 工具

| 工具 | 用途 | 使用場景 |
|------|------|---------|
| `find_symbol` | 搜尋符號定義 | 找類別、方法、變數定義（僅 Dart） |
| `find_referencing_symbols` | 搜尋引用 | 找某個符號的所有使用處 |
| `get_symbols_overview` | 檔案符號總覽 | 瞭解檔案結構（不需讀全檔） |
| `rename_symbol` | 重命名符號 | 安全重構（自動更新所有引用） |
| `replace_symbol_body` | 替換符號定義 | 精確修改函式/類別實作 |
| `insert_before/after_symbol` | 插入程式碼 | 在符號前後新增內容 |
| `search_for_pattern` | 模式搜尋 | 靈活的正則搜尋（類似 rg） |

### Dart MCP 工具

| 工具 | 用途 | 使用場景 |
|------|------|---------|
| `hover` | 型別和文件資訊 | 查看符號的完整型別簽章 |
| `resolve_workspace_symbol` | 跨檔案符號搜尋 | 在整個工作區找符號 |
| `signature_help` | 函式簽章提示 | 查看參數定義和說明 |
| `analyze_files` | 靜態分析 | 找 lint 問題、型別錯誤 |
| `dart_format` | 格式化程式碼 | 自動排版 |
| `dart_fix` | 自動修復 | 套用 lint 建議的修正 |

### Serena search_for_pattern vs Grep（W8-012 結論）

**日常搜尋無法用 Serena 完全取代 rg。** 差異如下：

| 維度 | Grep (rg) | Serena search_for_pattern |
|------|-----------|--------------------------|
| 速度 | 即時（< 1 秒） | 1-5 秒，大範圍可能溢出 |
| 輸出格式 | 簡潔行格式，三種模式 | JSON，較冗長 |
| 大小寫處理 | 原生 `-i` flag | 需 regex `(?i)` |
| 分頁 | `head_limit` + `offset` | 無（溢出時需縮小範圍） |
| 計數 | `output_mode: count` | 無 |
| 跨行搜尋 | 需 `multiline: true` | 預設支援 |
| 程式碼過濾 | `--type dart` | `restrict_search_to_code_files` |

**Serena search_for_pattern 僅在以下場景使用**：
- 搜尋後接續語意操作（find_symbol、replace_symbol_body）
- 需要嚴格只搜尋程式碼檔案
- 需要跨行匹配

### 適用場景

| 適合（獨佔優勢） | 不適合 |
|-----------------|-------|
| 重構前找所有引用（精確） | 搜尋註解或字串內容 |
| 理解類別繼承和實作關係 | 搜尋非 Dart 程式碼檔案 |
| 安全重命名（自動更新引用） | 模糊概念搜尋 |
| 查看符號完整型別資訊 | 跨專案搜尋 |
| 靜態分析和自動修復 | 效能分析 |

---

## WebSearch - 網頁搜尋（W8-008 結論）

### 核心特性

WebSearch 是 Claude Code 內建的網頁搜尋工具，零配置、穩定可用。

| 特性 | 說明 |
|------|------|
| 回應速度 | ~3 秒 |
| 英文查詢品質 | 4-5/5（API 用法、技術文件表現優秀） |
| 中文在地化品質 | 2-3/5（可能混入簡體中文或英文結果） |
| 整合度 | 原生整合到對話，自動提供結構化摘要和來源連結 |

### 中文查詢建議

- 搭配英文關鍵字提升搜尋精確度
- 注意搜尋結果可能混入簡體中文來源
- 重要的在地化資訊建議交叉驗證

---

## 多步驟研究方案（W8-009 結論）

### Grep + Glob + Read 組合

多步驟程式碼架構研究的預設方案，無需任何外部依賴。

**實測結果**（W8-009）：
- 追蹤 Ticket 系統生命週期（8 個核心檔案）：~45 秒，完整度 5/5
- 追蹤 Hook 驗證邏輯（831 行 Python）：~20 秒，完整度 5/5

### 標準研究流程

```
步驟 1: Glob 定位相關檔案
    例：Glob **/*ticket*.py

步驟 2: Grep 搜尋關鍵字
    例：Grep "ticket.*create|lifecycle"

步驟 3: Read 深度閱讀核心檔案
    例：Read ticket.py -> 理解入口和分發

步驟 4: 重複步驟 2-3 追蹤呼叫鏈
    例：Grep "TicketLifecycle" -> Read lifecycle.py
```

---

## 環境檢查與故障排除

### 安裝狀態檢查

```bash
rg --version
```

### rg 常見問題

| 問題 | 原因 | 解決 |
|------|------|------|
| command not found | 未安裝 | `brew install ripgrep` |
| 搜尋結果不完整 | .gitignore 排除 | `rg --no-ignore "pattern"` |
| PCRE2 不可用 | 編譯時未啟用 | `cargo install ripgrep --features pcre2` |

---

## W8 比較測試報告索引

本指南的工具定位和建議基於以下比較測試報告：

| 報告 | 比較項目 | 核心結論 |
|------|---------|---------|
| W8-008 | WebSearch 網頁搜尋效果 | WebSearch 是唯一推薦的網頁搜尋工具 |
| W8-009 | 多步驟研究效果 | Grep+Glob+Read 組合是預設選擇 |
| W8-010 | 語意搜尋 vs 文字搜尋 | rg 精確度 ~90-94%，同義詞弱點可用多 Pattern 改善 |
| W8-011 | Serena 結構化導航 | Serena LSP 僅對 Dart 有效，Grep 步驟數更少 |
| W8-012 | rg vs Serena search_for_pattern | 日常搜尋無法用 Serena 取代 rg |

報告位置：`docs/work-logs/v0.31.0/tickets/`（0.31.0-W8-008.md 至 0.31.0-W8-012.md，各為獨立檔案）

---

**Last Updated**: 2026-02-06
**Version**: 4.0.0 - 移除 mgrep，整合 W8 比較測試結論
