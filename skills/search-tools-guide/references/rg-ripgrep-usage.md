# rg (ripgrep) 詳細用法

> **定位**：本檔為 `search-tools-guide` 主檔「rg (ripgrep) - 日常主力搜尋」節的完整版，收錄安裝方式、rg 與內建 Grep 的完整功能對照、常用指令速查、語言/框架範例與概念性搜尋技巧。
>
> **何時讀本檔**：已決定要用 bash 直接呼叫 rg（而非內建 Grep）、需要查特定 flag 語法、或要用多 Pattern 組合改善概念搜尋召回率時。一般搜尋用內建 Grep 即可，不需要讀本檔。
>
> **同目錄**：無。本節內容單獨外移，`search-tools-guide/references/` 下無其他 rg 相關檔案。
>
> 溯源：v5.2.0 拆分自 `SKILL.md`「rg (ripgrep) - 日常主力搜尋」節（體量收斂：全檔 6,723 tokens 超出 5,000 門檻 1.34 倍）。

---

## 核心概念

**ripgrep** 是基於 Rust 的高效能正則搜尋工具，是 Claude Code 內建 Grep 的底層引擎。

**效能特性**：使用有限自動機和 SIMD 最佳化、lock-free 並行目錄遍歷，比 GNU grep 快約 33 倍（Linux kernel 搜尋基準）。預設自動遵守 `.gitignore` 規則。

## 安裝

```bash
# macOS
brew install ripgrep

# Linux (Debian/Ubuntu)
sudo apt-get install ripgrep

# 通用（需要 Rust）
cargo install ripgrep
```

## rg vs 內建 Grep

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

## 常用指令速查

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

## 語言/框架專案範例（以 Flutter/Dart 為例，其他語言類似）

```bash
# Widget 定義（Flutter）
rg -t dart "class\s+\w+\s+extends\s+(Stateless|Stateful)Widget"

# Provider 使用（Flutter）
rg -t dart "Provider\.(of|watch|read)" lib/

# 測試案例（Dart）
rg -t dart "test(Widgets)?\(" test/

# TODO 和 FIXME（Dart，可替換為其他語言的 type filter 如 -t js/py/go）
rg -t dart "(TODO|FIXME|HACK)" lib/

# Ticket 狀態（與語言無關）
rg "status:\s*(pending|in_progress)" docs/work-logs/
```

## 概念性搜尋技巧

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
