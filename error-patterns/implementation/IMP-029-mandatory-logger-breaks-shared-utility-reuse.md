---
id: IMP-029
title: 強制 logger 參數導致函式提取至共用模組後介面不一致
category: implementation
severity: medium
created: 2026-03-09
related_tickets:
  - 0.1.0-W22-024
---

# IMP-029：強制 logger 參數導致函式提取至共用模組後介面不一致

## 症狀

從單一 hook 提取函式至 hook_utils.py（共用模組）時，原函式的 `logger` 參數設計為必填（因為 hook 環境下永遠有 logger）。提取後若維持必填設計，呼叫者（如單元測試、無 logger 環境的腳本）必須傳入假 logger，造成使用障礙。若改為選填（`logger = None`），又與同模組其他函式的介面風格不一致。

## 根因

Hook 內部函式的 logger 屬於「環境依賴」（所在 hook 永遠有 logger），但共用模組函式的 logger 屬於「可選觀測工具」（呼叫者不一定有 logger）。提取函式時若未重新思考參數設計，直接搬移會繼承不適合共用場景的介面假設。

## 發現情境

W22-024 將 `_parse_ticket_date()` 和 `check_error_patterns_changed()` 從 `acceptance-gate-hook.py` 提取至 `hook_utils.py` 時，原函式的 `logger` 為必填位置參數。提取後改為 `logger: ... = None` 選填，並在每個 logger 呼叫前加 `if logger:` 保護，才能讓函式在無 logger 環境下安全運作。

## 解決方案

提取函式至共用模組時，對 logger 參數執行以下設計審查：

```python
# 錯誤：直接搬移，維持必填設計
def parse_ticket_date(value, logger) -> Optional[datetime]:  # logger 必填
    logger.debug("...")  # 無 logger 時 AttributeError

# 正確：改為選填，加 if logger 保護
def parse_ticket_date(value, logger=None) -> Optional[datetime]:
    if logger:
        logger.debug("...")
```

## 預防措施

提取函式至共用模組的 checklist 新增項目：

1. 原函式是否依賴呼叫環境的隱式依賴（logger、context、config）？
2. 這些依賴在共用模組中是否仍然普遍存在？
3. 若否 → 改為選填參數並加保護，或拆分為「有 logger」和「無 logger」兩個版本。

## 影響範圍

- 函式提取至共用模組（如 hook_utils.py、lib/utils.py）的場景
- 單元測試需要在無 logger 環境下測試共用函式的場景
