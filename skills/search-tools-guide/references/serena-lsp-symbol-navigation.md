# Serena / LSP / Dart MCP 符號導航完整版

> **定位**：本檔為 `search-tools-guide` 主檔「Serena / LSP / Dart MCP - 符號導航與程式碼理解」節的完整版，收錄 Serena 與 Dart MCP 的完整工具表、`search_for_pattern` 與 Grep 的詳細比較、以及適用場景對照。
>
> **何時讀本檔**：已決定要用 Serena / LSP / Dart MCP 做符號級操作，需要查特定工具名稱與用途、或要判斷該用 `search_for_pattern` 還是 Grep 時。日常搜尋只需主檔摘要即可判斷方向。
>
> **同目錄**：無。本節內容單獨外移，`search-tools-guide/references/` 下無其他 Serena 相關檔案。
>
> 溯源：v5.2.0 拆分自 `SKILL.md`「Serena / LSP / Dart MCP - 符號導航與程式碼理解」節（體量收斂：全檔 6,723 tokens 超出 5,000 門檻 1.34 倍）。

---

## 核心概念

**Serena**、**LSP** 和 **Dart MCP** 提供語意感知的程式碼導航，理解符號定義、引用關係和型別系統。這是唯一能做到精確重構的工具類別。

## 重要限制

**Serena 的 LSP 符號分析適用於有 LSP 插件的語言**：Dart / JavaScript（typescript-language-server）/ TypeScript / Python（pyright）等皆有效；對純文字檔（`.md` / `.txt` / `.yaml` / `.json`）無 LSP 結構優勢，應改用 Edit / Grep。

**Why 此處原誤紀錄為「僅對 Dart 有效」**：此紀錄源自早期 Python 環境未配置 pyright 的觀察，已不適用當前環境。<!-- rule8-exempt: relocation:逐字搬移自 .claude/skills/search-tools-guide/SKILL.md「Serena / LSP / Dart MCP」節 -->W17-091 ANA 實證 serena 對本專案 JavaScript 程式碼完整有效（Class / Methods / 行號邊界皆能解析）。

## Serena 工具

| 工具 | 用途 | 使用場景 |
|------|------|----------|
| `find_symbol` | 搜尋符號定義 | 找類別、方法、變數定義（僅 Dart） |
| `find_referencing_symbols` | 搜尋引用 | 找某個符號的所有使用處 |
| `get_symbols_overview` | 檔案符號總覽 | 瞭解檔案結構（不需讀全檔） |
| `rename_symbol` | 重命名符號 | 安全重構（自動更新所有引用） |
| `replace_symbol_body` | 替換符號定義 | 精確修改函式/類別實作 |
| `insert_before/after_symbol` | 插入程式碼 | 在符號前後新增內容 |
| `search_for_pattern` | 模式搜尋 | 靈活的正則搜尋（類似 rg） |

## Dart MCP 工具

| 工具 | 用途 | 使用場景 |
|------|------|----------|
| `hover` | 型別和文件資訊 | 查看符號的完整型別簽章 |
| `resolve_workspace_symbol` | 跨檔案符號搜尋 | 在整個工作區找符號 |
| `signature_help` | 函式簽章提示 | 查看參數定義和說明 |
| `analyze_files` | 靜態分析 | 找 lint 問題、型別錯誤 |
| `dart_format` | 格式化程式碼 | 自動排版 |
| `dart_fix` | 自動修復 | 套用 lint 建議的修正 |

## Serena search_for_pattern vs Grep

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

## 適用場景

| 適合（獨佔優勢） | 不適合 |
|-----------------|-------|
| 重構前找所有引用（精確） | 搜尋註解或字串內容 |
| 理解類別繼承和實作關係 | 搜尋非 Dart 程式碼檔案 |
| 安全重命名（自動更新引用） | 模糊概念搜尋 |
| 查看符號完整型別資訊 | 跨專案搜尋 |
| 靜態分析和自動修復 | 效能分析 |
