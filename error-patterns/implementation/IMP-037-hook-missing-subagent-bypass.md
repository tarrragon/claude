# IMP-037: PreToolUse Hook 缺少 subagent 環境檢查導致誤攔截

## 錯誤摘要

| 項目 | 說明 |
|------|------|
| **分類** | Implementation |
| **嚴重性** | 中（subagent 任務失敗，需重新派發） |
| **發現版本** | v0.1.2 |
| **相關 Ticket** | 0.1.2-W6-005 |

## 症狀

- subagent（如 thyme-python-developer）嘗試 Edit/Write 時被 Hook 阻止
- agent 收到「主線程禁止直接編輯程式碼檔案」的錯誤訊息
- agent 誤以為規則不允許自己編輯，轉而建立 Ticket 而非修改檔案
- 同一任務需要多次派發才能完成

## 根因分析

**行為模式**：`main-thread-edit-restriction-hook.py` 設計為限制主線程（PM）直接編輯程式碼，但未加入 `is_subagent_environment()` 檢查，對所有呼叫者（主線程和 subagent）無差別生效。

**設計意圖 vs 實作差距**：

```
skip-gate.md 設計意圖：
  「本文件的限制規則僅適用於 rosemary-project-manager（主線程）。
   subagent 開發代理人不受『主線程禁止』類規則約束。」

Hook 實作：
  對所有 Edit/Write 呼叫執行相同的路徑檢查 → 違反設計意圖
```

**對比**：專案中已有 12 個 Hook 正確使用 `is_subagent_environment()` 跳過 subagent，此 Hook 是遺漏。

## 解決方案

在 Hook 的 `main()` 函式中，工具類型檢查之後、路徑權限檢查之前，加入 subagent 早期跳過：

```python
from hook_utils import ..., is_subagent_environment

# 在 main() 中：
if is_subagent_environment(input_data):
    logger.info(f"subagent 環境（agent_id={input_data.get('agent_id')}），跳過編輯限制")
    result = generate_hook_output(True, "subagent 不受主線程編輯限制")
    print(json.dumps(result, ensure_ascii=False))
    return EXIT_ALLOW
```

## 防護措施

### Hook 類型區分（強制）

開發 Hook 前必須先分類，不同類型有不同的 subagent 處理要求：

| Hook 類型 | 定義 | subagent bypass | 範例 |
|-----------|------|-----------------|------|
| **限制類** | 阻擋操作（exit 1 或 `"decision": "block"`） | **必須加入** | main-thread-edit-restriction、branch-verify |
| **檢查類** | 只提示不阻擋（exit 0，輸出 WARNING） | 通常不需要 | ticket-id-validator、output-style-check |
| **引導類** | 輸出建議或提醒（exit 0，輸出 INFO） | 視情況 | askuserquestion-reminder、commit-handoff |

### 限制類 Hook 必備程式碼模板

```python
import json
import sys
from hook_utils import is_subagent_environment

EXIT_ALLOW = 0
EXIT_BLOCK = 1

def generate_hook_output(is_allowed: bool, reason: str) -> dict:
    """限制類 Hook 的標準輸出格式。"""
    return {"decision": "allow" if is_allowed else "block", "reason": reason}

def main():
    input_data = json.loads(sys.stdin.read())

    # [強制] 限制類 Hook 必須在早期跳過 subagent
    if is_subagent_environment(input_data):
        result = generate_hook_output(True, "subagent 不受此限制")
        print(json.dumps(result, ensure_ascii=False))
        return EXIT_ALLOW

    # ... 主線程限制邏輯 ...
```

### 新 Hook 開發檢查清單

撰寫任何 PreToolUse Hook 時，必須確認：

- [ ] Hook 是限制類、檢查類還是引導類？（見上方分類表）
- [ ] 限制類 Hook 是否已 import `is_subagent_environment`？
- [ ] 限制類 Hook 是否在早期（工具類型檢查之後、業務邏輯之前）加入 subagent 跳過？
- [ ] 錯誤訊息是否會誤導 subagent 改變行為？（如「禁止編輯」可能讓 subagent 放棄嘗試）

### 判斷標準

| 場景 | 需要 subagent 跳過？ |
|------|---------------------|
| 限制主線程編輯範圍（skip-gate） | 是 |
| AskUserQuestion 提醒 | 是（subagent 禁止使用 AskUserQuestion） |
| 通用品質檢查（如路徑格式驗證） | 否（對所有呼叫者適用） |
| Ticket 存在性驗證 | 視情況（subagent 可能不需要） |

## 相關文件

- .claude/rules/forbidden/skip-gate.md（主線程限制設計意圖）
- .claude/hooks/hook_utils/hook_io.py（is_subagent_environment 定義）
- .claude/error-patterns/process-compliance/PC-022-subagent-permission-denied-hook-edit.md（相關事件）

---

**Last Updated**: 2026-03-23
**Version**: 1.0.0
