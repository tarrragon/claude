# PC-005: CLI 失敗時基於假設歸因

---

## 分類資訊

| 項目 | 值 |
|------|------|
| 編號 | PC-005 |
| 類別 | process-compliance |
| 來源版本 | v0.1.0 |
| 發現日期 | 2026-03-05 |
| 風險等級 | 中 |
| 來源 | `ticket handoff` 失敗時基於假設歸因，未調查實際語法，導致繞過標準流程 |

### 症狀

1. CLI 工具報錯（非零退出碼）
2. PM 未查閱 `--help`，直接基於「聽起來合理」的假設判斷原因
3. 基於錯誤假設採取行動（如繞過標準工具流程、手動建檔等）
4. 實際原因可能只是語法錯誤或參數格式不正確

### 根本原因（5 Why 分析）

1. Why 1：PM 看到錯誤訊息後直接推測原因
2. Why 2：未執行 `--help` 確認工具的實際語法和參數格式
3. Why 3：將熟悉的概念（如資料結構）投射到不熟悉的介面（CLI 參數）
4. Why 4：缺乏「CLI 失敗時先查語法」的強制流程
5. Why 5：根本原因：**跳過調查步驟，基於假設直接行動**

---

## 解決方案

### CLI/工具失敗調查步驟（強制）

CLI 或內部工具報錯時，禁止假設歸因，必須依序調查：

```
工具報錯
    |
    v
[Step 1] 查語法：執行 --help 或查閱 SKILL.md 確認完整語法
    |
    v
[Step 2] 字面解讀：錯誤訊息的字面意義是什麼？
    |
    v
[Step 3] 比對狀態：實際資料狀態是否符合工具預期？
    |
    v
[Step 4] 歸因：排除語法和參數問題後，才考慮邏輯層原因
```

---

## 預防措施

### 已實作

| 措施 | 說明 | 位置 |
|------|------|------|
| incident-response 調查步驟 | 第六層新增工具失敗 vs 邏輯失敗分流 | .claude/rules/flows/incident-response.md |
| decision-tree 分流 | 第六層區分 CLI 報錯和邏輯錯誤 | .claude/rules/core/decision-tree.md |
| PostToolUse Hook | Bash 非零退出碼時自動提醒查 --help | .claude/hooks/cli-failure-help-reminder-hook.py |

### 待實作

（無）

---

## 行為模式分析

此模式屬於「假設驅動行動」類型：

- **錯誤訊息被重新詮釋**而非字面理解
- **熟悉的心智模型**覆蓋了實際介面資訊
- **省略調查步驟**直接跳到結論
- **行動基於假設**而非證據

### 相關錯誤模式

| 模式 | 關係 |
|------|------|
| IMP-019 | 子類型 — 資料結構投射到 CLI 介面的具體案例 |
| PC-003 | 同為靜默問題類型，但 PC-003 是資訊不完整，PC-005 是調查不完整 |

---

## 相關文件

- 0.1.0-W2-004 - PostToolUse Hook 防護（待處理）
- .claude/rules/flows/incident-response.md - CLI/工具失敗調查步驟
- .claude/error-patterns/implementation/IMP-019-data-structure-to-cli-projection.md - 具體案例
