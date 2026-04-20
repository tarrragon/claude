---
id: IMP-064
title: 函式體 local re-import 遮蔽 unittest.mock.patch
category: implementation
severity: high
first_seen: 2026-04-17
related_patterns:
- PC-068
- IMP-005
---

# IMP-064: 函式體 local re-import 遮蔽 unittest.mock.patch

## 症狀

使用 `unittest.mock.patch("module.name", ...)` 攔截模組層匯入的符號時，mock 完全失效。函式執行時取到真實符號而非 mock，導致測試讀取真實 I/O / 資料庫 / 檔案系統，產出與 fixture 不一致的結果。

典型錯誤訊號：
- `assert "[INFO]" in output` 失敗，實際輸出 `[WARNING]`（因為 mock ticket age 9 天被繞過，讀到真實 ticket age 14 天）
- patch 的 assertion 顯示 `mock.call_count == 0`
- 單獨跑函式正常，但跑測試「彷彿 patch 沒生效」

## 根因

模組頂層已匯入某符號（`from x.y import foo`）後，函式體內又重複匯入同名符號（防禦性 re-import 或 copy-paste 汙染），Python 作用域規則會建立**新的 function-local binding**，遮蔽 module-level binding。

```python
# module.py
from x.y import foo  # line 24 — module-level binding

def do_work(arg):
    # 函式體內 local import → 建立新 local binding 遮蔽 module-level
    from x.y import foo
    return foo(arg)

# test.py
from unittest.mock import patch

@patch("module.foo")  # 只攔截 module.foo（module-level 名稱），攔不到函式內的 local 名稱
def test_do_work(mock_foo):
    module.do_work("x")
    mock_foo.assert_called_once()  # 失敗：do_work 拿到真實 foo，不是 mock_foo
```

`unittest.mock.patch` 只能修改模組屬性字典，無法攔截函式作用域內的 local import。

## 常見誘因

1. **肌肉記憶防禦 import**：寫新 block 時為怕「import 失敗」順手再 import 一次，沒意識到 module-level 已經有。
2. **Copy-paste 汙染**：把其他模組的程式碼塊貼過來，帶著對方的 local import。
3. **錯誤的作用域信念**：以為 try/except 包覆的 import 需要局部化才能「降級」（實際上 module-level import 失敗會直接讓模組無法載入，根本到不了 try）。

## 為何 Quality 視角容易放行

靜態審查（linter / 類型檢查）對重複 import 只會給 warning 或完全無訊息。Code review 肉眼也容易忽略（兩個 import 同名符號，看起來「沒差」）。只有測試執行時觸發 mock 失效才暴露。

## 偵測方法

### 1. 主動掃描

```bash
# 對專案內所有 .py 檔案：搜尋函式體內（縮排 4+ 空格）的 import
grep -rn "^    from\|^        from" src/ tests/ --include="*.py" | \
  grep -v "__init__\|conftest"
```

針對每個命中：檢查是否 module-level 已匯入同名符號。

### 2. Mock 測試未生效的排查流程

1. 把 `@patch("module.symbol")` 換成 `print(module.symbol)` 確認 patch target 存在
2. 在函式內加 `print(id(symbol))` 比對是否為 mock 物件 id
3. 搜尋函式內 `from ...` 或 `import ...` 是否建立 local binding

## 防護措施

### 1. 模組頂層統一 import

所有函式共用的符號一律 module-level import。只有在以下情境才允許 local import：

| 情境 | 理由 |
|------|------|
| 循環依賴破解 | module-level 會造成 ImportError |
| Optional dependency 降級 | try/except 允許 import 失敗走 fallback |
| 測試/除錯專用（僅開發路徑） | 避免生產 import 開銷 |

否則一律 module-level。

### 2. Pylint/Ruff 規則啟用

- **Pylint**：`reimported (W0404)` 警告
- **Ruff**：`F811 redefined-while-unused` + `PLW0406 import-self`

CI 至少把這類 warning 升為 error。

### 3. 新增 mock-evading import 測試

對於涉及 I/O 或副作用的模組，寫測試驗證 mock 實際被調用：

```python
@patch("module.load_data")
def test_mock_actually_used(mock_load):
    mock_load.return_value = {"fake": True}
    result = module.process()
    mock_load.assert_called_once()  # 若失敗 = local re-import 嫌疑
```

### 4. 程式碼審查清單

審查任何 diff 時，若看到函式體內 `from ...` import：

- [ ] module-level 是否已匯入同名符號？
- [ ] 若已匯入，為何不共用？（循環依賴？可選依賴？無正當理由則刪除）
- [ ] 若是新增的 local import，是否會破壞下游測試的 mock 攔截？

## 自我檢查清單

撰寫/修改 Python 模組時：

- [ ] 函式體內的 `from ... import ...` 有明確正當理由嗎？
- [ ] module-level 匯入和 local import 沒有同名遮蔽？
- [ ] 使用 `unittest.mock.patch` 時，patch target 是函式實際使用的 binding？
- [ ] 測試有斷言 mock 被調用（`assert_called_*`）以捕獲 local re-import 繞過？

## 範例案例

| 日期 | 專案 | 事件 | 觸發檔案 |
|------|------|------|---------|
| 2026-04-17 | ticket system | `execute_claim` 內 local re-import `load_ticket` 使 test_ac_drift_regression 2 fails（WARNING/14 天 vs INFO/9 天） | lifecycle.py 函式體 |

## 相關模式

- **PC-068**：既有 utility 調用時未驗證邊界（家族上位模式，本案的根因之一是沒確認 load_ticket 的 import 邊界）
- **IMP-005**：不完整 import 遷移（遷移後遺留 local import 沒清理）

## 驗證清單

- [x] 替換 file path 為通用描述後仍有意義：跨專案可重現
- [x] 任何 Python 專案使用 mock.patch + 有 local re-import 習慣都可能中
- [x] 偵測方法可工具化（grep + pylint/ruff 規則）
- [x] 防護措施有明確落地路徑
