# TEST-005: Mock 錯誤 import 路徑導致真實副作用

## 分類

測試（Test）

## 症狀

測試使用 `unittest.mock.patch` 替換某個函式，但 patch 未生效：

- Mock 統計（`assert_called_once`、`call_count`）正常通過
- 但真實函式仍被呼叫，產生實際檔案系統 I/O、網路請求、資料庫寫入等副作用
- 測試執行後 repo 出現 untracked 檔案、資料庫殘留、外部系統狀態改變

## 根因：Python import binding 機制

當模組 B 執行 `from module_a import func_a`：

1. Python 在 `module_b.func_a` 建立對 `func_a` 物件的**本地 binding**
2. 此後 `module_b` 內呼叫的 `func_a`，查找的是 `module_b.func_a`，**不是** `module_a.func_a`

因此：

| patch 目標 | 是否生效 |
|-----------|---------|
| `patch('module_a.func_a')` | 不生效（module_b 的 binding 未被替換） |
| `patch('module_b.func_a')` | 生效（替換 module_b 內的呼叫位置） |

## 識別條件

同時滿足以下三項時高度懷疑為 TEST-005：

1. 測試通過（assert 未失敗）但產生意料外的副作用（寫檔、修改資料）
2. 被測模組使用 `from X import Y` 而非 `import X`
3. patch 路徑指向 `X.Y`（原始定義處）而非 `被測模組.Y`（呼叫位置）

## 實際案例

### 案例 1：ticket_system 測試污染

**發生情境**：`test_track_relations.py` 在 repo 根每次跑測試都產生 `docs/work-logs/v0/v0.31/` untracked 檔案。

**問題程式碼**：

```python
# ticket_system/commands/track_relations.py
from ticket_system.lib.ticket_loader import save_ticket  # 本地 binding

def execute_add_child(args, version):
    ...
    save_ticket(ticket, path)  # 呼叫的是 track_relations.save_ticket
```

```python
# tests/test_track_relations.py（錯誤）
with patch('ticket_system.lib.ticket_loader.save_ticket'):  # patch 不生效
    result = execute_add_child(args, "0.31.0")
    # 真實 save_ticket 仍被呼叫，寫入真實 repo 路徑
```

**修正**：patch 呼叫方的 namespace。

```python
with patch('ticket_system.commands.track_relations.save_ticket'):  # 正確
    result = execute_add_child(args, "0.31.0")
```

### 案例 2：測試完全漏 mock

`execute_batch_complete` 等函式呼叫 `save_ticket`，某些測試完全沒有 patch 任何 save_ticket，真實 I/O 執行。

**修正**：所有呼叫會觸發 I/O 的測試都必須 patch 呼叫方 namespace 的 save_ticket。

## 正確做法

### 規則 1：patch 呼叫位置，非定義位置

```python
# 被測模組: module_b.py
from module_a import func_a

def business_logic():
    return func_a()

# 測試：
patch('module_b.func_a')      # 正確
patch('module_a.func_a')      # 錯誤（除非 module_b 用 `import module_a` 再 `module_a.func_a()`）
```

### 規則 2：session 級 guard 阻止靜默污染

在 `conftest.py` 新增 session autouse fixture，比對測試前後 repo 關鍵目錄的變化，若有新增則 raise AssertionError。這能讓「patch 錯路徑」的錯誤立即可見，而不是靜默污染。

```python
@pytest.fixture(scope="session", autouse=True)
def _assert_no_repo_pollution():
    project_root = Path(__file__).resolve().parents[N]  # N 依 conftest 位置
    target = project_root / "docs" / "work-logs" / "v0"
    before = set(target.iterdir()) if target.exists() else set()
    yield
    after = set(target.iterdir()) if target.exists() else set()
    new_dirs = after - before
    if new_dirs:
        raise AssertionError(f"Test pollution detected: {new_dirs}")
```

### 規則 3：Code review 檢查清單

審查測試時檢視每個 `patch(...)`：

- [ ] 被測模組是用 `from X import Y` 還是 `import X`？
- [ ] patch 路徑是指向定義位置（`X.Y`）還是呼叫位置（被測模組.Y`）？
- [ ] 被 mock 的函式是否有 I/O 副作用（寫檔、網路、DB）？
- [ ] 若未 mock 或 mock 錯路徑，會產生哪些可觀測副作用？

## 防護措施

1. **架構層**：session autouse fixture 監控 repo 污染（參考 `tests/conftest.py`）
2. **測試層**：撰寫測試時一律 patch 呼叫方 namespace
3. **CR 層**：review 新測試時檢查 patch 路徑是否對應被測模組的呼叫位置
4. **CI 層**：`git status` 在測試後不應有 untracked 檔案（可在 CI pipeline 加 check）

## 關聯

- TEST-004（Mock Path Invalidation After Wrapper Refactor）— 相同根因，不同觸發情境（重構後 binding 改變）
- IMP-011（Incomplete Format Matching）— 類似「假設 vs 實際」的盲點模式

---

**建立日期**: 2026-04-13
**來源**: 0.18.0-W5-031 ANA 根因分析 + 0.18.0-W5-032 執行驗證
**Version**: 1.0.0
