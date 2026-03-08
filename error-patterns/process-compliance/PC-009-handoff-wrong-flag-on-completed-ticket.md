# PC-009: PM 在 completed ticket 誤用 --context-refresh 旗標

## 基本資訊

- **Pattern ID**: PC-009
- **分類**: 流程合規
- **來源版本**: v0.1.0
- **發現日期**: 2026-03-07
- **風險等級**: 中
- **來源 Ticket**: 0.1.0-W11-005

## 問題描述

### 症狀

PM 在 Ticket 完成（status: completed）後，執行 handoff 時使用 `--context-refresh` 旗標：

```bash
ticket handoff 0.1.0-W11-001 --context-refresh
```

CLI 回傳錯誤：

```
Ticket 0.1.0-W11-001 無法執行 handoff
當前狀態：completed
需要狀態（context-refresh）：in_progress
```

### 根因

PM 誤解了 `--context-refresh` 的用途：
- `--context-refresh`：僅適用 `in_progress` 狀態，代表「同一任務尚未完成，需要在新 session 以乾淨 context 繼續」
- completed 狀態的 ticket 應直接使用普通 handoff（不加旗標或指定方向旗標）

原因是 AskUserQuestion #11a（Context 刷新 Handoff）的選項說明未區分「此選項對應哪個 ticket 狀態」，導致 PM 在 completed ticket 上也選擇 context-refresh 路由。

### 影響

- handoff 執行失敗，session 無法正常結束
- PM 誤以為 CLI 有 bug，反而花時間診斷

## 解決方案

對 completed ticket 執行 handoff，不加 `--context-refresh`：

```bash
# 切換到下一個任務（兄弟任務）
ticket handoff <id> --to-sibling <next_id>

# 返回父任務
ticket handoff <id> --to-parent

# 讓 CLI 自動判斷方向
ticket handoff <id>
```

## 預防措施

1. **文件防護**（已完成，W11-005）：
   - `workflow-handoff.md` 新增狀態-命令映射規則
   - `handoff-command.md` 新增按 Ticket 狀態選擇命令表和禁止行為
   - `askuserquestion-rules.md` #11a 新增警告：「禁止在 completed ticket 使用此旗標」；#11b 補充正確 CLI 命令

2. **決策記憶點**：
   - `--context-refresh` = 「我還沒做完，換個新環境繼續」→ 只用於 in_progress
   - 不加旗標 = 「我做完了，交棒給下一個任務」→ 用於 completed

## 相關錯誤模式

- PC-005: CLI 失敗時假設歸因（未查閱語法就猜測原因）
