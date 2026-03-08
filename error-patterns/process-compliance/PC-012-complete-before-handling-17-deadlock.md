# PC-012: Complete 流程死鎖（#17 事前處理陷阱）

## 基本資訊

- **Pattern ID**: PC-012
- **分類**: 流程合規
- **來源版本**: v0.1.0
- **發現日期**: 2026-03-09
- **風險等級**: 中
- **來源 Ticket**: 0.1.0-W22-009

## 問題描述

### 症狀

PM 執行 `ticket track complete X` 時，acceptance-gate-hook 輸出場景 #17 提醒（有新增 error-pattern）。PM 誤以為必須先處理 #17 才能執行 complete，於是：

1. PM 處理 #17（建立改進 Ticket 或記錄 todolist）
2. PM 再次執行 `ticket track complete X`
3. hook 再次觸發 #17（error-pattern 檔案仍存在）
4. 循環，complete 永遠無法完成

### 根本原因

acceptance-gate-hook 的 #17 判斷邏輯基於：
```
error-pattern 檔案的 mtime > ticket.created 時間
```

**關鍵事實**：處理 #17（建立 fix ticket、記錄 todolist）不會移除 error-pattern 檔案。
因此每次執行 complete，hook 都會重新觸發 #17 提醒，造成無限循環。

### 觸發情境

- PM 在執行期間有新增 `.claude/error-patterns/` 下的檔案
- PM 在看到 #17 提醒後嘗試「先解決再 complete」

## 正確做法

**acceptance-gate-hook 對 #17 是非阻擋的（exit 0）**，complete 必須先執行：

```
[1] 看到 #17 提醒
    ↓
[2] 直接執行 ticket track complete X（hook 允許，non-blocking）
    ↓
[3] ticket 狀態變為 completed
    ↓
[4] 執行 AskUserQuestion #17，選擇處理方式
```

| 行為 | 結果 |
|------|------|
| 看到 #17 → 先處理 → 再 complete | 死鎖：每次 complete 都觸發 #17 |
| 看到 #17 → 直接 complete → 完成後處理 | 正確：一次完成 |

## 預防措施

1. **文件**：ticket-lifecycle.md v5.3.0 已新增「死鎖防護」說明，明確標示 hook 為非阻擋
2. **記憶**：看到 #17 提醒 = 提示 complete 後要做 AskUserQuestion #17，不是要求先處理
3. **判斷**：若 hook exit code 為 0（輸出 `"permissionDecision": "allow"`），complete 永遠允許執行

## 相關文件

- `.claude/rules/flows/ticket-lifecycle.md` - 完成階段時序說明（v5.3.0 修復）
- `.claude/rules/core/askuserquestion-rules.md` - 場景 #17 定義
- `.claude/hooks/acceptance-gate-hook.py` - hook 實作（exit code 邏輯）
