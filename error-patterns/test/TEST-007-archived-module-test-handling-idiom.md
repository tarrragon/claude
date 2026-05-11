---
id: TEST-007
title: Archived 模組的測試檔處理 idiom（pytestmark.skip + try/except import 雙層保護）
category: test
severity: low
created: 2026-05-11
related:
 - W17-190
 - W17-192
---

# TEST-007: Archived 模組的測試檔處理 idiom

> **性質**：本文為「正向實作 idiom」非「錯誤模式」，記錄於 error-patterns/test 是為了在 grep 「archived」「stale module」時可被搜尋到。

## 適用情境

模組從活躍位置（如 `.claude/hooks/agent_dispatch_analytics.py`）搬到 archive 目錄（`.claude/hooks/archived/`），但測試檔仍在原 `tests/` 目錄。pytest collection 會撞 `ModuleNotFoundError`，需明確聲明「測試保留但暫時 skip」狀態。

| 條件 | 說明 |
|------|------|
| 模組被搬到 `archived/` 目錄 | deprecation 過渡期，模組保留但不再維護 |
| 測試檔仍存在原 tests/ 位置 | 未一併刪除，作為未來恢復參考 |
| 直接 import 該模組 | pytest collection 撞 `ModuleNotFoundError` |
| 模組無其他活躍 import | 確認真正 dormant，非暫時錯置 |

## 反模式對照

| 反模式 | 為何不適合 |
|-------|----------|
| 刪除整個測試檔 | 失去未來恢復的參考；後人不知曾有過這些測試 |
| 修 import 指向 archived/ 目錄 | 復活 archived 模組的測試 → 維護負擔；模組已 archive 表示不再投資 |
| 整檔註解掉測試程式碼 | 失去 pytest 統計可見性；後人 grep 困難 |
| 把測試也搬到 archived/ | 違反 tests/ 目錄結構慣例；pytest 預設不掃描 archived/ |

## 推薦 idiom

```python
import pytest

# WAVE-XXX：<module_name> 模組已移至 .claude/hooks/archived/，
# 整檔 skip 以避免 collection error。恢復條件：模組重新啟用時，
# 移除 pytestmark 並修正 import path。
# 相關 ticket: <source ANA / IMP ticket>
pytestmark = pytest.mark.skip(
    reason="<module_name> 模組已 archived（WAVE-XXX）；測試保留作為未來恢復參考"
)

# 模組層 import 用 try/except 包住，避免 ModuleNotFoundError 阻擋 pytest collection。
# pytestmark.skip 會阻止測試實際執行，故 import 失敗不影響行為。
try:
    from <module_name> import (  # type: ignore[import-not-found]
        ClassA, ClassB, ...
    )
except ImportError:
    # 模組已 archived，符合預期；pytestmark.skip 將阻止測試實際執行
    pass
```

### 雙層保護機制

1. **`pytestmark = pytest.mark.skip(...)`**：module-level marker，阻止所有測試實際執行
2. **`try/except ImportError`**：保護 module-level import，避免 `ModuleNotFoundError` 在 pytest collection 階段就 fail（pytestmark 在 collection 後才生效）

缺一層都會出問題：
- 只用 pytestmark → import 仍在 module 載入時 fail，collection error
- 只用 try/except → 測試會被 collect 並執行，但 fixtures/functions 變成 undefined name

## 案例

### W17-190 / W17-192（2026-05-11）

`agent_dispatch_analytics.py` 被搬到 `.claude/hooks/archived/`，但 `tests/test_analytics.py` 仍在原位置。W17-190 ANA Reality Test 發現 pytest collection 撞 `ModuleNotFoundError: No module named 'agent_dispatch_analytics'`，影響 `npm run test:hooks` 統計準確性。

W17-192 採此 idiom 後：

- 2167 tests collected（含 22 個 test_analytics 測試 skip）
- 0 collection error
- skip 訊息明示 ticket 引用：`W17-192`
- pre-existing test failures 不受影響

## 恢復路徑

若 archived 模組重新啟用：

1. 將模組搬回原位置（或保留在 archived/ 並修 sys.path）
2. 移除測試檔的 `pytestmark = pytest.mark.skip(...)`
3. 移除測試檔的 `try/except` 包裝，恢復為直接 `import`
4. 執行測試套件確認所有測試仍綠（若有 break，依個案修補）
5. 更新測試檔註解，移除 archived 標記

## 相關規則 / 文件

- pytest 官方文件：[pytestmark](https://docs.pytest.org/en/stable/how-to/skipping.html#skip-all-test-functions-of-a-class-or-module)
- W17-190 ANA：Reality Test 發現此 stale bug
- W17-192 IMP：本 idiom 的首次落地案例

## 預估影響

- 觸發頻率：每次有模組 archive 但測試保留時都應採用
- 認知負擔：低（標準 pytest idiom + 註解模板）
- 維護成本：近零（archived 模組 bug 不影響 skip 測試）
