# IMP-027: 跨境界 Library-Hook 邏輯重複

## 基本資訊

- **Pattern ID**: IMP-027
- **分類**: 程式碼實作
- **來源版本**: v0.1.0
- **發現日期**: 2026-03-08
- **風險等級**: 低
- **關聯 Ticket**: 0.1.0-W21-001

## 問題描述

### 症狀

兩個邏輯幾乎相同的函式分別存在於：
1. Python 套件的 library 模組（如 `project_init/lib/hook_verifier.py`）
2. 獨立 hook 腳本（如 `.claude/hooks/hook-completeness-check.py`）

因為兩者的 import 境界不同，開發者傾向在各自的上下文中獨立實作，導致 70-80% 的邏輯重複且各自維護。

細微差異逐漸累積（例如：預設排除清單不同、logger 參數有無），增加未來維護成本和行為不一致的風險。

### 根因

新增 library 模組時，開發者只看同一套件內的現有模組，沒有橫向掃描不同位置（hooks 目錄）是否有相同邏輯。反之亦然。

**具體案例（W21-001）**：

`hook_verifier.py` 和 `hook-completeness-check.py` 同時實作了：

```python
# 兩個檔案都各自定義了這 5 個函式
_load_json_file()        # vs  load_json_file()
_get_exclude_patterns()  # vs  get_exclude_patterns()
_should_exclude_file()   # vs  should_exclude_file()
_scan_hooks_directory()  # vs  scan_hooks_directory()
_extract_registered_hooks() # vs extract_registered_hooks()
```

差異只在命名慣例（私有 vs 公開）和預設排除清單的細微不同。

## 解決方案

### 方案：提取到 library，hook 透過 sys.path 匯入

1. 在 library 目錄建立共享模組（如 `lib/hook_checker.py`）
2. Library 模組改為從共享模組 import
3. 獨立 hook 腳本透過 `sys.path.insert` 插入 library 套件路徑後 import

```python
# hook-completeness-check.py 的 import 模式
_HOOKS_DIR = Path(__file__).parent
_CLAUDE_DIR = _HOOKS_DIR.parent
_PROJECT_INIT_DIR = _CLAUDE_DIR / "skills" / "project-init"

sys.path.insert(0, str(_HOOKS_DIR))
sys.path.insert(0, str(_PROJECT_INIT_DIR))

from hook_utils import setup_hook_logging, run_hook_safely
from project_init.lib.hook_checker import (
    extract_registered_hooks,
    get_exclude_patterns,
    load_json_file,
    scan_hooks_directory,
    should_exclude_file,
)
```

## 防護措施

### 設計新 library 模組前的橫向掃描

新增 library 模組（尤其涉及 hook 系統相關邏輯）時，先執行：

```bash
grep -rn "def 函式名" .claude/hooks/
grep -rn "json.load" .claude/hooks/
grep -rn "settings.get.*hooks" .claude/hooks/
```

確認 hooks 目錄是否有相似實作。

### 程式碼審查檢查項

- [ ] 新 library 模組的核心邏輯是否已在 `.claude/hooks/` 某個 hook 中存在？
- [ ] 新 hook 的核心邏輯是否已在 library 模組中存在？
- [ ] 若兩者都有，是否已建立共享模組並讓兩端 import？

### 識別信號

- 兩個函式做相同的事但名稱有微小差異（有無底線前綴）
- 相同的 JSON 解析邏輯分散在 library 和 hook 中
- 相同的目錄掃描邏輯分散在兩個不同境界

## 與既有模式的關係

| 模式 | 關係 |
|------|------|
| IMP-001（散落重複程式碼） | 本模式是 IMP-001 的跨境界變體：重複不在同一上下文，在不同 import 境界之間 |
| IMP-022（內聯導入工具重複） | IMP-022 是 hook 內部重複 hook_utils；本模式是 library ↔ hook 跨境界重複 |
