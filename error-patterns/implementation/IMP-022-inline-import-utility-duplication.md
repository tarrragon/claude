# IMP-022: 內聯 __import__ 重複實作共用邏輯

## 基本資訊

- **Pattern ID**: IMP-022
- **分類**: 程式碼實作
- **來源版本**: v0.1.0
- **發現日期**: 2026-03-06
- **風險等級**: 低
- **關聯 Ticket**: 0.1.0-W2-006

## 問題描述

### 症狀

多個模組使用 `__import__("module")` 內聯導入，各自重複實作相同的工具函式，而該函式已存在於共用 utility 模組中。

### 根因

開發者在撰寫新 hook 時，為了「自給自足」或不確定共用模組是否有對應功能，選擇在本地重新實作，使用 `__import__` 避免在檔案頂部添加 import。

### 具體案例

**5 個 hook 重複實作 `get_project_root()`**：

```python
# 錯誤：每個 hook 各自內聯實作
def get_project_root():
    try:
        result = __import__("subprocess").run(
            ["git", "rev-parse", "--show-toplevel"],
            capture_output=True, text=True, check=True
        )
        return Path(result.stdout.strip())
    except Exception:
        return Path.cwd()
```

而 `hook_utils.py` 已有 `_find_project_root()` 函式做完全相同的事。

**影響的 hook**：
- handoff-cleanup-hook.py
- handoff-prompt-reminder-hook.py
- handoff-reminder-hook.py
- handoff-auto-resume-stop-hook.py
- tech-debt-reminder.py

```python
# 正確：使用共用模組
from hook_utils import get_project_root

project_root = get_project_root()
```

## 解決方案

1. 將共用邏輯提升到 utility 模組的公開 API
2. 所有消費端統一使用共用模組的函式
3. 新增 hook 時先檢查 hook_utils 是否已有對應功能

## 防護措施

### 程式碼審查檢查項

- [ ] 新 hook 是否使用 `__import__()` 內聯導入？
- [ ] 新 hook 的邏輯是否已存在於 hook_utils？
- [ ] 如果 hook_utils 沒有，是否應該先新增到 hook_utils？

### 識別關鍵字

```python
# 警告信號
__import__("subprocess")  # 內聯導入通常意味著重複實作
__import__("json")        # 同上
```

## 與既有模式的關係

| 模式 | 關係 |
|------|------|
| IMP-001（散落重複程式碼） | 本模式是 IMP-001 在 Hook 系統的具體表現 |
| IMP-003（作用域迴歸） | 相關但不同：IMP-003 是重構時的作用域問題 |
