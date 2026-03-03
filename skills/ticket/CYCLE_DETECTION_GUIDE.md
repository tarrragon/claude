# 循環依賴檢測指南

## 概述

循環依賴檢測機制是 Ticket 系統中的一項核心安全功能，用於防止任務之間的循環依賴導致系統死鎖。

### 什麼是循環依賴？

循環依賴是指 Ticket 之間形成的環形依賴關係，例如：

```
A 被 B 阻塞
B 被 C 阻塞
C 被 A 阻塞
```

在這種情況下，沒有任何 Ticket 可以完成，因為每個都在等待另一個完成。

### 檢測演算法

循環檢測使用深度優先搜尋（DFS）演算法：

- **時間複雜度**：O(V + E)，其中 V 為 Ticket 數，E 為依賴數
- **空間複雜度**：O(V)，用於遞迴棧和訪問追蹤
- **保證**：必定能偵測出所有環

## 核心功能

### 1. `CycleDetector.has_cycle()`

檢測從特定 Ticket 開始的依賴圖中是否存在環。

**使用範例**：

```python
from ticket_system.lib.cycle_detector import CycleDetector

def get_deps(ticket_id: str) -> list[str]:
    deps = {
        "A": ["B"],
        "B": ["C"],
        "C": ["A"]
    }
    return deps.get(ticket_id, [])

has_cycle, cycle_path = CycleDetector.has_cycle("A", get_deps)
# 輸出：(True, ['A', 'B', 'C', 'A'])
```

**返回值**：

- `(False, None)`：無環
- `(True, cycle_path)`：有環，返回環的完整路徑

### 2. `CycleDetector.detect_cycles_in_all_tickets()`

掃描所有 Ticket 中的所有循環依賴。

**使用範例**：

```python
from ticket_system.lib.cycle_detector import CycleDetector

tickets = [
    {"id": "A", "blockedBy": ["B"]},
    {"id": "B", "blockedBy": ["C"]},
    {"id": "C", "blockedBy": ["A"]}
]

cycles = CycleDetector.detect_cycles_in_all_tickets(tickets)
# 輸出：[("A", ["A", "B", "C", "A"])]
```

**返回值**：環的清單，格式為 `(起始 Ticket ID, 環路清單)`

### 3. `CycleDetector.validate_blocked_by()`

驗證設定新的 blockedBy 依賴是否會產生循環。

**使用範例**：

```python
from ticket_system.lib.cycle_detector import CycleDetector

tickets = [
    {"id": "B", "blockedBy": ["C"]},
    {"id": "C", "blockedBy": ["A"]}
]

# 嘗試設定 A -> B（會產生 A -> B -> C -> A）
valid, error_msg, cycle_path = CycleDetector.validate_blocked_by(
    "A", ["B"], tickets
)
# 輸出：
# valid = False
# error_msg = "設定依賴會產生循環：A → B → C → A"
# cycle_path = ["A", "B", "C", "A"]
```

**返回值**：

- `(True, None, None)`：驗證通過，無循環
- `(False, error_msg, cycle_path)`：驗證失敗，返回錯誤訊息和環路

### 4. `validate_blocked_by()` （在 ticket_validator 中）

在 Ticket 驗證器中整合的循環檢測。

**使用範例**：

```python
from ticket_system.lib.ticket_validator import validate_blocked_by

tickets = [...]  # 現有 Ticket 清單
valid, msg, path = validate_blocked_by("A", ["B"], tickets)

if not valid:
    print(f"錯誤：{msg}")
    print(f"環路：{' → '.join(path)}")
```

## 支援的依賴格式

系統支援多種 `blockedBy` 欄位格式：

### 列表格式（推薦）

```yaml
blockedBy:
  - "B"
  - "C"
```

### 逗號分隔字串

```yaml
blockedBy: "B,C"
```

### 空依賴

```yaml
blockedBy: []
# 或
blockedBy:
```

## 測試覆蓋

完整的測試套件位於 `tests/test_cycle_detector.py`，包含 34 個測試案例：

### 測試分類

| 類別       | 測試數 | 說明                                        |
| ---------- | ------ | ------------------------------------------- |
| 基本環檢測 | 10     | 無環、自我依賴、二節點、三節點、複雜 DAG 等 |
| 全面掃描   | 8      | 單一環、多個環、邊界情況、特殊格式          |
| 驗證功能   | 8      | 有效依賴、無效依賴、更新現有 Ticket 等      |
| 環路路徑   | 3      | 路徑完整性、路徑格式、訊息格式              |
| 邊界情況   | 5      | 重複依賴、空字串、None、長路徑等            |

### 執行測試

```bash
# 執行所有循環檢測測試
cd .claude/skills/ticket
uv run pytest tests/test_cycle_detector.py -v

# 執行特定測試類別
uv run pytest tests/test_cycle_detector.py::TestHasCycle -v

# 執行所有測試（包含其他模組）
uv run pytest tests/ -v
```

## 設計特點

### 1. 純函數式設計

所有函式都是純函式（無副作用）：

- 不修改輸入參數
- 不依賴全域狀態
- 結果完全由輸入決定

### 2. 錯誤容易性

系統能優雅地處理各種邊界情況：

```python
# 直接自我依賴
has_cycle, path = CycleDetector.has_cycle("A", get_deps)
# 若 A 的依賴包含 A，會正確檢測

# 空字串依賴
def get_deps(tid):
    return ["B", ""]  # 包含空字串

has_cycle, path = CycleDetector.has_cycle("A", get_deps)
# 會忽略空字串，正確處理

# None 值
def get_deps(tid):
    return ["B", None]

# 會安全處理 None
```

### 3. 詳細的錯誤訊息

循環檢測返回的錯誤訊息包含完整的環路路徑，便於除錯：

```
"設定依賴會產生循環：A → B → C → A"
```

### 4. 高性能

- **單次檢測**：O(V + E) 時間
- **全面掃描**：全部 Ticket 的 O(V + E)
- **記憶體**：O(V) 空間

## 整合點

### 1. Ticket 建立時驗證

在建立新 Ticket 時，如果指定了 `blockedBy` 欄位，應進行循環檢測：

```python
# 從 ticket_validator 呼叫
valid, msg, path = validate_blocked_by(
    ticket_id="0.31.0-W4-002",
    blocked_by=["0.31.0-W4-001"],
    all_tickets=existing_tickets
)

if not valid:
    raise ValueError(msg)
```

### 2. Ticket 更新時驗證

更新 Ticket 的 `blockedBy` 欄位時，應進行循環檢測：

```python
# 變更依賴關係時檢測
valid, msg, path = validate_blocked_by(
    ticket_id="0.31.0-W4-001",
    blocked_by=["0.31.0-W4-002"],  # 新的依賴
    all_tickets=existing_tickets
)
```

### 3. 查詢系統中的所有環

掃描系統中所有 Ticket 的所有循環依賴：

```python
from ticket_system.lib.cycle_detector import CycleDetector
from ticket_system.lib.ticket_loader import list_tickets

tickets = list_tickets("0.31.0")
cycles = CycleDetector.detect_cycles_in_all_tickets(tickets)

if cycles:
    print("發現循環依賴！")
    for start_id, cycle_path in cycles:
        print(f"  {' → '.join(cycle_path)}")
```

## 常見問題

### Q1：如果依賴有重複會怎樣？

A：系統會正確處理重複依賴：

```python
blockedBy: ["B", "B"]  # 重複依賴

# 會被視為單一依賴 B，不會影響循環檢測
```

### Q2：系統支援哪些最大環大小？

A：理論上沒有限制，實際受系統記憶體限制。測試中已驗證 26 節點的環能正確檢測。

### Q3：部分依賴無效會怎樣？

A：系統會忽略無效的依賴（如 None、空字串），只檢測有效的依賴。

### Q4：如何避免循環依賴？

A：最佳實踐：

- 在設定 `blockedBy` 時總是進行驗證
- 使用拓撲排序規劃依賴結構
- 定期掃描系統中的所有環

## 效能建議

### 1. 批量驗證

若需要驗證多個新 Ticket，建議批量進行：

```python
# 推薦：建立臨時清單，一次驗證全部
temp_tickets = existing_tickets + new_tickets
cycles = CycleDetector.detect_cycles_in_all_tickets(temp_tickets)

if cycles:
    # 處理錯誤
    pass
```

### 2. 緩存依賴圖

若依賴圖頻繁被查詢，可考慮緩存：

```python
# 建立依賴表：Ticket ID → 依賴清單
dependency_map = {
    t["id"]: t.get("blockedBy", [])
    for t in tickets
}

# 使用緩存版本
has_cycle, path = CycleDetector.has_cycle(
    "A",
    lambda tid: dependency_map.get(tid, [])
)
```

## 相關文件

- [Ticket 驗證規範](ticket_system/lib/ticket_validator.py) - 驗證器實作
- [Ticket 系統說明書](README.md) - Ticket 系統整體說明
- [測試檔案](tests/test_cycle_detector.py) - 完整的測試案例

## 變更日誌

### v1.0.0 (2026-02-04)

- 初始發布
- 實作 CycleDetector 類別
- 整合到 ticket_validator
- 完整測試覆蓋（34 個測試案例）
- 支援多種依賴格式
- 詳細的錯誤訊息

如有問題，請參考專案文件：

- [Ticket 系統 Skill 文件](.claude/skills/ticket/SKILL.md)
- [專案規則](.claude/rules/README.md)
