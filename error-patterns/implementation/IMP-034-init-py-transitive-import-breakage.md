# IMP-034: __init__.py 全量 import 導致 transitive 依賴斷裂

## 錯誤摘要

| 項目 | 說明 |
|------|------|
| **分類** | Implementation |
| **嚴重性** | 中（影響 SessionStart 體驗，非功能阻塞） |
| **發現版本** | v0.1.0 |
| **相關 Ticket** | 0.1.0-W52-002 |

## 症狀

- `ModuleNotFoundError: No module named 'yaml'` 執行 hook 時
- hook-health-monitor 報告 `[FAIL]`（日誌長時間未更新）
- SessionStart 顯示 `hook error`

## 根因分析

**行為模式**：`__init__.py` 採用全量 import（eagerly import 所有子模組），導致任何消費者 import 該 package 的任意模組時，被迫載入所有子模組的依賴。

**具體案例**：

```
hook-completeness-check.py（只需要 hook_checker）
    → from project_init.lib.hook_checker import ...
    → Python 先載入 project_init/lib/__init__.py
    → __init__.py 全量 import 包含 onboard_checker
    → onboard_checker 依賴 PyYAML
    → 系統 Python 無 PyYAML → ModuleNotFoundError
```

**觸發條件**：

1. 模組 A 使用受限的 Python 環境（系統 Python，無第三方套件）
2. 模組 A 只需要 package X 的子模組 Y
3. package X 的 `__init__.py` 全量 import 包含子模組 Z
4. 子模組 Z 依賴第三方套件（不在受限環境中）
5. import chain 斷裂：A → X.__init__ → Z → 缺少的第三方套件

## 為什麼難以偵測

- hook 本身的直接依賴（hook_checker）不需要 PyYAML
- 只有 `__init__.py` 的間接 import 觸發問題
- 錯誤在 `__init__.py` 被修改時（新增子模組 import）才出現，不在 hook 修改時
- 修改 `__init__.py` 的人不知道有消費者使用受限 Python 環境

## 解決方案

**方案 A（推薦）：統一執行環境**

將所有 hook 改為 `uv run --script` + PEP 723 header，宣告所需依賴。這樣 uv 自動管理依賴，不受系統 Python 限制。

```python
#!/usr/bin/env -S uv run --quiet --script
# /// script
# requires-python = ">=3.11"
# dependencies = ["pyyaml"]
# ///
```

**方案 B：lazy import**

將 `__init__.py` 的全量 import 改為按需 import，但這增加了 package 使用複雜度。

## 預防措施

| 措施 | 說明 |
|------|------|
| Hook 統一使用 uv run | 所有 hook 應使用 PEP 723 宣告依賴，避免依賴系統 Python |
| `__init__.py` 審查 | 修改 `__init__.py` 新增 import 時，檢查是否有消費者使用受限環境 |
| hook-health-monitor | 已有的監控機制能偵測 hook 長時間未執行（閾值 48h） |

## 檢查清單

修改 `__init__.py` 時：

- [ ] 新增的 import 是否引入新的第三方依賴？
- [ ] 該 package 的消費者是否有使用受限 Python 環境的？
- [ ] 是否所有消費者都能取得新引入的依賴？

新增 hook 時：

- [ ] 使用 `uv run --script` + PEP 723（非 `python3`）？
- [ ] PEP 723 dependencies 是否涵蓋所有 transitive 依賴？

---

**Last Updated**: 2026-03-17
**Version**: 1.0.0
