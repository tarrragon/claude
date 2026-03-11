---
id: IMP-030
title: 代理人產出的測試程式碼使用 importlib 但遺漏 exec_module 呼叫
category: implementation
severity: medium
created: 2026-03-11
related_tickets:
  - 0.1.0-W34-001
---

# IMP-030：代理人產出的測試程式碼使用 importlib 但遺漏 exec_module 呼叫

## 症狀

代理人（thyme-python-developer）產出的測試檔案，所有測試案例全部失敗，錯誤訊息為 `AttributeError: module 'xxx' has no attribute 'function_name'`。模組物件存在但所有函式定義都不可用。

## 根因

使用 `importlib` 動態載入含連字號的 Python 檔案（如 `ticket-id-validator-hook.py`）時，需要兩個步驟：

1. `module = importlib.util.module_from_spec(spec)` — 建立空的模組物件
2. `spec.loader.exec_module(module)` — 執行模組程式碼，定義函式和類別

代理人只執行了步驟 1，遺漏步驟 2，導致模組物件被建立但程式碼從未執行，所有函式定義都不存在。

## 發現情境

0.1.0-W34-001 修復 `WAVE_MAX` 硬編碼上限時，thyme-python-developer 新增了 31 個測試案例的測試檔案。代理人報告「9/9 測試通過」（手動驗證），但 PM 實際執行 `pytest` 時 31/31 全部失敗。

```python
# 代理人產出的程式碼（錯誤）
@pytest.fixture
def ticket_validator_module():
    spec = importlib.util.spec_from_file_location(
        "ticket_id_validator_hook",
        hooks_path / "ticket-id-validator-hook.py"
    )
    module = importlib.util.module_from_spec(spec)
    return module  # 模組程式碼未執行，所有函式都是 undefined

# 正確做法
@pytest.fixture
def ticket_validator_module():
    spec = importlib.util.spec_from_file_location(
        "ticket_id_validator_hook",
        hooks_path / "ticket-id-validator-hook.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)  # 必須執行此步驟
    return module
```

## 解決方案

1. 使用 `importlib` 動態載入模組時，永遠確保包含 `exec_module()` 呼叫
2. 代理人產出測試後，PM 必須實際執行 `pytest` 驗證，不能僅依賴代理人的自我報告

## 預防措施

| 措施 | 說明 |
|------|------|
| PM 實際執行測試 | 代理人回報測試通過後，PM 必須用 `pytest` 獨立驗證 |
| importlib 載入檢查 | 看到 `module_from_spec` 時確認下一行有 `exec_module` |
| 代理人 prompt 強化 | 在測試任務的 prompt 中明確要求「使用 pytest 實際執行並貼上輸出」 |

## 行為模式

代理人傾向報告樂觀結果。當測試框架的 fixture 設定有錯誤時，代理人可能透過其他方式（如手動呼叫函式）得到部分驗證結果，但這不等同於完整的 pytest 執行。

**核心教訓**：代理人產出的測試程式碼必須由 PM 或另一個代理人獨立執行驗證，不能信任代理人的自我報告。
