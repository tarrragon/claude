# PC-010: PM 在 ticket complete 後跳過 Checkpoint 流程

## 基本資訊

- **Pattern ID**: PC-010
- **分類**: 流程合規
- **來源版本**: v0.1.0
- **發現日期**: 2026-03-08
- **風險等級**: 中

## 問題描述

### 症狀

PM 執行 `ticket track complete` 後，直接結束回應，未執行決策樹第七、八層的 Checkpoint 流程。用戶需要主動追問「為什麼沒有觸發下一步」。

### 根因

PM 將 `ticket track complete` 誤當作任務結束點，而非流程的一個節點。完成後應繼續執行：

1. **第七層（complete 前）**：AskUserQuestion #1（驗收方式確認）— 詢問「標準/簡化/先完成後補」
2. **Checkpoint 1**：檢查未提交變更，建議 commit
3. **Checkpoint 1.5**：AskUserQuestion #16（錯誤學習經驗確認）
4. **Checkpoint 2**：查詢同 Wave pending Ticket，依情境路由 AskUserQuestion #11/13

### 影響

- 用戶沒有獲得後續步驟引導
- 未提交變更停留在工作目錄（Checkpoint 1 未執行）
- 未詢問錯誤學習（Checkpoint 1.5 未執行）
- 未確認 Wave 收尾或切換任務（Checkpoint 2 未執行）

## 解決方案

`ticket track complete` 執行成功後，PM 必須立即繼續執行：

```
ticket track complete <id>
    |
    v
[第七層] AskUserQuestion #1（complete 前確認驗收方式，若未確認）
    |
    v
[Checkpoint 1] git status → 有變更 → 建議 /commit-as-prompt
    |
    v
[Checkpoint 1.5] AskUserQuestion #16（錯誤學習確認）
    |
    v
[Checkpoint 2] ticket track list --wave {n} --status pending in_progress
              → 情境 B（有 pending）→ AskUserQuestion #11b
              → 情境 C（無 pending）→ 查全版本 → AskUserQuestion #3a 或 #13
```

## 根本原因（三層分析）

**第一層（設計邊界）**：`COMPLETE_NEXT_STEP_REMINDER` 在 PreToolUse 觸發，與驗收確認混合，PM 注意力在「能否 complete」，對後續提醒注意力低。

**第二層（使用情境）**：`ticket track complete` 成功後無 PostToolUse hook，PM 看到「已完成」訊息後認知上產生完成感，容易停止。

**第三層（說明充分性）**：決策樹第八層規則詳細，但 Checkpoint 1/1.5 缺少執行點的強制提醒，規則與 Hook 觸發點解耦。

## 預防措施

1. **記憶點**：`ticket track complete` 完成後，下一步永遠是 Checkpoint 1（git status），不是結束。
2. **觸發詞**：看到 CLI 輸出「已完成」時，立即問自己：「Checkpoint 1 做了嗎？」
3. **Hook 強化**（全部已完成）：

## 防護完整性確認

**狀態**：所有 Checkpoint 路徑已由 Hook 系統完整覆蓋（2026-03-10 W30 多視角審查確認）

| Checkpoint | 覆蓋 Hook | 狀態 |
|------------|----------|------|
| 第七層（#1 驗收確認） | acceptance-gate-hook（PreToolUse） | 已覆蓋 |
| Checkpoint 1（git status） | post-ticket-complete-checkpoint-hook（PostToolUse） | 已覆蓋 |
| Checkpoint 1.5（#16 錯誤學習） | post-ticket-complete-checkpoint-hook + commit-handoff-hook | 已覆蓋 |
| Checkpoint 2 有 commit 路徑 | commit-handoff-hook（PostToolUse） | 已覆蓋 |
| Checkpoint 2 無 commit 路徑 | post-ticket-complete-checkpoint-hook（補充） | 已覆蓋 |

## 相關錯誤模式

- PC-004: 跳過分析直接修復（同為跳過必要流程步驟的模式）
- PC-009: PM 在 completed ticket 誤用 --context-refresh 旗標
