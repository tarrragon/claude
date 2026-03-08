# TEST-004: 重構引入 Wrapper 函式後 Mock Patch 路徑失效

## 基本資訊

- **Pattern ID**: TEST-004
- **分類**: 測試設計 / Python Mock
- **來源版本**: v0.1.0
- **發現日期**: 2026-03-06
- **風險等級**: 高

## 問題描述

### 症狀

重構後測試開始失敗，錯誤訊息顯示「Ticket 找不到」或「欄位不存在」，但票券明明存在於測試 fixture。

```
[Error] 0.31.0-W4-001 無 'when' 欄位
[Error] 0.31.0-W4-001 無 Acceptance Criteria 區段
[Warning] 0.31.0-W4-001 尚未被接手，無法釋放
```

測試中明明設定了 mock：

```python
with patch('ticket_system.lib.ticket_loader.load_ticket') as mock_load:
    mock_load.return_value = {"id": "0.31.0-W4-001", "status": "in_progress", ...}
    result = execute_command(args, version)
    assert result == 0  # FAIL: result == 1
```

### 根本原因 (5 Why 分析)

1. Why 1: mock 無法攔截 `load_ticket` 呼叫，命令讀取到真實的空票券資料（或找不到票券）
2. Why 2: 命令不再直接呼叫 `load_ticket`，而是呼叫 `ticket_ops.load_and_validate_ticket()`
3. Why 3: `ticket_ops.py` 使用 `from ticket_system.lib.ticket_loader import load_ticket` 建立了模組內的獨立引用
4. Why 4: `patch('ticket_system.lib.ticket_loader.load_ticket')` 只修改了 `ticket_loader` 模組的屬性，不影響 `ticket_ops` 已建立的引用
5. Why 5: Python 的 `from X import Y` 會在目標模組的命名空間複製引用，patch 原始位置無法影響已複製的引用

### Python Mock 核心原則

> **Patch where it's USED, not where it's DEFINED.**

```python
# module_a.py
def get_data():
    return "real data"

# module_b.py
from module_a import get_data  # 建立獨立引用

def do_work():
    return get_data()  # 使用 module_b 的引用，不是 module_a 的

# 測試中：
# 錯誤：patch 了定義位置，module_b 的引用不受影響
with patch('module_a.get_data') as mock:
    ...

# 正確：patch 使用位置
with patch('module_b.get_data') as mock:
    ...
```

## 觸發條件

重構將命令模組改為透過 **wrapper 函式**（如 `ticket_ops.load_and_validate_ticket`）呼叫底層函式，但測試的 mock patch 路徑仍指向底層函式的定義模組。

**高風險重構場景**：
- 提取共用 utility 函式（本 Ticket 的情況）
- 在 Repository pattern 中新增抽象層
- 引入 Facade 模式包裝多個底層呼叫

## 解決方案

### 方案 A：更新 Mock 路徑（推薦）

將 mock 路徑從定義位置改為使用位置：

```python
# 修改前
with patch('ticket_system.lib.ticket_loader.load_ticket') as mock_load:
    mock_load.return_value = mock_ticket

# 修改後（patch wrapper 模組中的引用）
with patch('ticket_system.lib.ticket_ops.load_ticket') as mock_load:
    mock_load.return_value = mock_ticket
```

### 方案 B：直接 Mock Wrapper 函式（更激進，更穩定）

不 mock 底層函式，直接 mock wrapper：

```python
with patch('ticket_system.commands.lifecycle.load_and_validate_ticket') as mock_load:
    mock_load.return_value = (mock_ticket, None)   # 成功情況
    # mock_load.return_value = (None, "not found")  # 失敗情況
```

優點：未來 wrapper 內部實作改變，測試不受影響。

### 方案 C：修改 Wrapper 使用 Module-level Import（避免問題根源）

在 wrapper 函式中動態 import（每次呼叫時重新查找屬性）：

```python
# ticket_ops.py
def load_and_validate_ticket(version, ticket_id, auto_print_error=True):
    from ticket_system.lib import ticket_loader  # module-level import，不是 from...import
    ticket = ticket_loader.load_ticket(version, ticket_id)
    ...
```

這樣 `patch('ticket_system.lib.ticket_loader.load_ticket')` 就能正確攔截。

## 預防措施

### 重構時的 Mock 路徑清單

任何引入新 wrapper 函式的重構完成後，**必須檢查**：

1. 執行測試，記錄新增的失敗
2. 對每個新增失敗，確認是否為 mock 路徑問題（錯誤訊息與 mock 行為不符）
3. 更新 mock 路徑為 wrapper 模組路徑

### 測試設計原則

**儘量 mock 最高層的函式**（接近命令邏輯的層次），而不是底層工具函式。這樣可以：
- 降低未來重構對測試的衝擊
- 讓測試更清晰表達業務意圖

## 相關 Ticket

- **發現**: 0.1.0-W2-012（重構 Ticket 驗證邏輯統一提取）
- **修復**: 0.1.0-W2-026（修復 W2-012 重構後 mock 路徑失效）

## 教訓

重構完成後，**即使功能正確，也需要立即執行全量測試並與重構前基準比較**，確保沒有引入新的測試失敗。若有新失敗，優先檢查 mock patch 路徑是否需要更新。

`test_count_before == test_count_after` 是重構品質的最低基準線。
