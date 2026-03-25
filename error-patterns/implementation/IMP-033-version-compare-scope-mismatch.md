# IMP-033: 版本比對時 source 掃描範圍與 installed 不對齊

## 基本資訊

- **Pattern ID**: IMP-033
- **分類**: 實作
- **來源版本**: v0.1.1
- **發現日期**: 2026-03-14
- **風險等級**: 中

## 問題描述

### 症狀

`project-init check` 始終報告所有自製套件為 `[OUTDATED]`，即使剛執行 `uv tool install . --force --reinstall` 重新安裝，仍然顯示需要更新。SHA256 hash 永遠不匹配。

### 根本原因 (5 Why 分析)

1. Why 1: `compare_versions()` 計算的 source hash 與 installed hash 不同
2. Why 2: source 掃描整個 skill 目錄（含 `tests/`、scripts 等），installed 只有模組子目錄
3. Why 3: source 檔案的相對路徑包含模組前綴（如 `mermaid_ascii/__init__.py`），installed 直接從模組根開始（如 `__init__.py`）
4. Why 4: `scan_custom_packages()` 將 `source_path` 設為 skill 根目錄，而非模組子目錄
5. Why 5: **根本原因**：source 和 installed 的比較基準點（根目錄）不同，導致掃描範圍和路徑結構都不對齊

**具體差異範例**：
```
Source（掃描 .claude/skills/mermaid-ascii/）:
  mermaid_ascii/__init__.py          <- 含模組前綴
  mermaid_ascii/mermaid_ascii_renderer.py
  tests/__init__.py                  <- 額外的測試檔案
  tests/test_mermaid_ascii_renderer.py

Installed（掃描 site-packages/mermaid_ascii/）:
  __init__.py                        <- 無前綴
  mermaid_ascii_renderer.py
```

## 解決方案

### 正確做法

在 `compare_versions()` 中，當 source_dir 是 skill 根目錄（含 `pyproject.toml`）時，自動定位到與 installed_dir 同名的模組子目錄：

```python
effective_source = source_dir
if (source_dir / "pyproject.toml").exists():
    module_subdir = source_dir / installed_dir.name
    if module_subdir.exists() and module_subdir.is_dir():
        effective_source = module_subdir

source_hashes = _compute_file_hashes(effective_source)
```

### 錯誤做法 (避免)

```python
# 直接用 skill 根目錄掃描，範圍不對齊
source_hashes = _compute_file_hashes(source_dir)  # source_dir = .claude/skills/xxx/
installed_hashes = _compute_file_hashes(installed_dir)  # installed_dir = site-packages/xxx_module/
```

## 防護建議

- 比較兩個目錄的檔案集合時，先驗證掃描範圍是否對齊（檔案數量、相對路徑結構）
- 考慮在比對結果中輸出差異檔案清單（debug 模式），便於快速定位不匹配原因
- hash 不匹配時記錄具體的差異檔案，而非只報告「需要重新安裝」

## 相關資源

- `.claude/skills/project-init/project_init/lib/package_manager.py` - 修正的比對邏輯
- IMP-017 - 全局 CLI 未隨原始碼修復更新（相關但不同：IMP-017 是安裝動作問題，本 pattern 是比對邏輯問題）

## 標籤

`#hash比對` `#路徑對齊` `#掃描範圍` `#誤報`
