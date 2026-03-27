# PC-032: 版本 Ticket 全數完成後跳過版本發布流程

## 症狀

v0.2.0 全部 128 個 Ticket 完成後，PM 直接詢問「要處理 v0.2.1 嗎」，跳過版本發布流程（version-release check / tag / CHANGELOG）。用戶必須手動提醒「0.2.0 已完成應該執行正式推進版本流程」。

## 根因

PM 在「版本無 pending Ticket」情境下，直接跳到下一版本的任務選擇，未將「版本發布」視為版本完成的必要步驟。決策樹的情境 C（無任何 pending）應路由到 `/version-release check`，但 PM 跳過了這一步。

## 行為模式

PM 傾向「繼續做下一件事」而非「收尾當前階段」。版本完成是一個隱性里程碑，沒有明確的 Hook 或 Ticket 觸發發布流程，導致 PM 依賴記憶而非系統提示。

## 解決方案

當所有 Ticket 完成且無 pending/in_progress 時，PM 必須：

1. 執行 `/version-release check --version X.Y.Z` 確認發布前置條件
2. 根據檢查結果決定：通過 → 執行發布流程；失敗 → 修正阻塞項
3. 完成發布後才能開始下一版本的工作

## 防護措施

- commit 後的情境 C2 流程明確要求執行 `/version-release check`
- askuserquestion-rules.md 場景 #13 定義了版本發布確認流程
- PM 應遵循：全部完成 → version-release check → 發布 → 下一版本

## 相關 Ticket

- 0.2.0-W8-001（發現時的 session）

## 發現日期

2026-03-27
