# 任務鏈索引使用指南

## 概述

任務鏈索引是為了優化 Ticket 父子關係查詢性能而建立的功能。在沒有索引時，查詢某個任務的所有子任務需要遍歷整個列表（O(n) 複雜度）。使用索引後，查詢時間優化到 O(1)。

## 核心類別：TicketChainIndex

### 初始化和建立索引

```python
from ticket_system.lib import TicketChainIndex, list_tickets

# 方法 1：手動建立索引
tickets = list_tickets("0.31.0")
index = TicketChainIndex()
index.build_from_tickets(tickets)

# 方法 2：自動取得快取索引
from ticket_system.lib import get_chain_index
index = get_chain_index("0.31.0")
```

## API 介面

### 查詢直接子任務

**方法**：`get_children(parent_id: str) -> List[str]`

返回直接子任務 ID 列表。

```python
# 取得 0.31.0-W4-001 的所有直接子任務
children = index.get_children("0.31.0-W4-001")
print(children)
# 輸出：['0.31.0-W4-001.1', '0.31.0-W4-001.2']

# 查詢不存在的任務返回空列表
children = index.get_children("999")
print(children)
# 輸出：[]
```

### 查詢所有後代任務

**方法**：`get_descendants(root_id: str) -> List[str]`

返回所有後代任務 ID 列表（包含根任務本身），採用深度優先搜尋順序。

```python
# 取得 0.31.0-W4-001 的所有後代
descendants = index.get_descendants("0.31.0-W4-001")
print(descendants)
# 輸出：['0.31.0-W4-001', '0.31.0-W4-001.1', '0.31.0-W4-001.1.1', '0.31.0-W4-001.2']
```

**注意**：此方法只針對根任務有效（即 parent_id 為空的任務）。子任務呼叫此方法會返回空列表。

### 檢查是否有子任務

**方法**：`has_children(parent_id: str) -> bool`

快速檢查是否有至少一個子任務。

```python
# 檢查任務是否有子任務
if index.has_children("0.31.0-W4-001"):
    print("此任務有子任務")
else:
    print("此任務無子任務")
```

### 取得子任務數量

**方法**：`get_child_count(parent_id: str) -> int`

返回直接子任務的數量。

```python
# 取得 0.31.0-W4-001 的子任務數量
count = index.get_child_count("0.31.0-W4-001")
print(f"子任務數量：{count}")
```

### 取得後代任務數量

**方法**：`get_descendant_count(root_id: str) -> int`

返回所有後代任務的數量（包含根任務本身）。

```python
# 取得 0.31.0-W4-001 的所有後代數量
count = index.get_descendant_count("0.31.0-W4-001")
print(f"後代數量：{count}")
```

## 索引結構

### parent_index

類型：`defaultdict[str, list[str]]`

鍵：父任務 ID
值：直接子任務 ID 列表

用於快速查詢直接子任務。

```python
# 檢查索引結構
print(index.parent_index)
# 輸出：defaultdict(<class 'list'>, {
#     '0.31.0-W4-001': ['0.31.0-W4-001.1', '0.31.0-W4-001.2'],
#     '0.31.0-W4-001.1': ['0.31.0-W4-001.1.1']
# })
```

### root_index

類型：`defaultdict[str, list[str]]`

鍵：根任務 ID（parent_id 為空）
值：所有後代任務 ID 列表（包含根任務本身）

用於快速查詢任務樹的全部節點。

```python
# 檢查索引結構
print(index.root_index)
# 輸出：defaultdict(<class 'list'>, {
#     '0.31.0-W4-001': ['0.31.0-W4-001', '0.31.0-W4-001.1', '0.31.0-W4-001.1.1', '0.31.0-W4-001.2'],
#     '0.31.0-W4-002': ['0.31.0-W4-002', '0.31.0-W4-002.1']
# })
```

## 使用場景

### 場景 1：遍歷任務樹

```python
def print_task_tree(index, root_id, indent=0):
    """遞迴列印任務樹"""
    prefix = "  " * indent
    print(f"{prefix}{root_id}")

    # 取得所有直接子任務
    children = index.get_children(root_id)
    for child_id in children:
        print_task_tree(index, child_id, indent + 1)

# 從根任務開始列印整個樹
print_task_tree(index, "0.31.0-W4-001")
```

### 場景 2：計算任務樹的規模

```python
# 統計每個根任務的規模
for root_id in index.root_index.keys():
    descendant_count = index.get_descendant_count(root_id)
    print(f"{root_id} 包含 {descendant_count} 個任務")
```

### 場景 3：檢查特定任務的完成狀況

```python
from ticket_system.lib import load_ticket

def check_completion_status(index, version, root_id):
    """檢查任務樹的完成狀況"""
    descendants = index.get_descendants(root_id)
    completed = 0
    total = len(descendants)

    for ticket_id in descendants:
        ticket = load_ticket(version, ticket_id)
        if ticket and ticket.get("status") == "completed":
            completed += 1

    completion_rate = (completed / total * 100) if total > 0 else 0
    print(f"{root_id} 完成度：{completed}/{total} ({completion_rate:.1f}%)")

check_completion_status(index, "0.31.0", "0.31.0-W4-001")
```

## 效能考量

### 建立索引的複雜度

- 時間複雜度：O(n + m)
  - n = Ticket 數量
  - m = 父子關係邊數

- 空間複雜度：O(n)

### 查詢複雜度

| 操作 | 複雜度 | 說明 |
|------|--------|------|
| `get_children()` | O(1) | 直接字典查詢 |
| `has_children()` | O(1) | 直接字典查詢 |
| `get_child_count()` | O(1) | 列表長度計算 |
| `get_descendants()` | O(1) | 直接字典查詢 |
| `get_descendant_count()` | O(1) | 列表長度計算 |

### 快取機制

`get_chain_index()` 函式使用模組層級的快取，避免重複建立索引：

```python
# 第一次呼叫：建立索引並快取
index1 = get_chain_index("0.31.0")  # 耗時 ~10-20ms

# 第二次呼叫：返回快取
index2 = get_chain_index("0.31.0")  # 耗時 <1ms

# 不同版本：各自快取
index3 = get_chain_index("0.32.0")  # 為新版本建立新索引
```

## 邊界情況處理

### 無效 Ticket ID

```python
# 查詢不存在的 ID 返回空結果
children = index.get_children("nonexistent_id")  # 返回 []
has_children = index.has_children("nonexistent_id")  # 返回 False
```

### 混合格式子任務

索引支援兩種子任務格式：

```python
tickets = [
    {
        "id": "001",
        "chain": {},
        "children": [
            "001.1",  # 字串格式
            {"id": "001.2", "status": "pending"},  # 字典格式
        ]
    }
]

index.build_from_tickets(tickets)
children = index.get_children("001")
# 返回：['001.1', '001.2']
```

### 無效格式跳過

```python
tickets = [
    {
        "id": "001",
        "chain": {},
        "children": [
            "001.1",
            123,  # 無效型別，會被跳過
            None,  # 無效值，會被跳過
            {"id": "001.2"},  # 有效
        ]
    }
]

index.build_from_tickets(tickets)
children = index.get_children("001")
# 返回：['001.1', '001.2']，無效項目被忽略
```

## 測試覆蓋

完整的測試套件位於 `tests/test_ticket_chain_index.py`，包含：

- 索引建立：空列表、單一任務、多級層級、多個根任務
- 查詢操作：直接子任務、所有後代、計數
- 邊界情況：無效輸入、混合格式、重建索引
- 效能驗證：大規模資料集

執行測試：

```bash
cd .claude/skills/ticket
uv run pytest tests/test_ticket_chain_index.py -v
```

## 相關文件

- [ticket_chain_index.py](ticket_system/lib/ticket_chain_index.py) - 索引實作
- [test_ticket_chain_index.py](tests/test_ticket_chain_index.py) - 完整測試
