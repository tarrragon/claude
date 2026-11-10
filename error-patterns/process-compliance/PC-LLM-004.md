---
id: PC-LLM-004
title: "補證據的寫入與受閘門管制的命令串在同一個 Bash 呼叫，閘門看到的是寫入前的狀態而擋下整條命令"
severity: low
category: process-compliance
related: [PC-GPD-003]
created: 2026-11-10
---

# PC-LLM-004: 補證據的寫入與受閘門管制的命令串在同一個 Bash 呼叫，閘門看到的是寫入前的狀態而擋下整條命令

## 基本資訊

| 項目 | 內容 |
|------|------|
| 風險等級 | 低 |
| 分類 | process-compliance（PreToolUse 閘門的評估時點） |
| 來源版本 | 3.1.0 |
| 首次觀測 | 2026-11-10 |

## 症狀

ticket complete 被 acceptance gate 擋下，訊息指出缺 liveness 與失敗語意證據。執行者把兩筆 `ticket track append-log`（補證據）與 `ticket track complete` 串成同一個 Bash 命令重送，閘門以完全相同的缺項訊息再擋一次，兩筆 append-log 也都沒有執行。拆成兩次呼叫（先 append-log，再 complete）後即通過。

同一 session 內出現兩次：第一次 complete 與 Test Results 的 append-log 串接；第二次則是補證據的 append-log 與 complete 串接。

## 根因

**PreToolUse 閘門在整條 Bash 命令執行前評估一次**。閘門從命令文字辨識出 `complete`，接著讀取當下磁碟上的票面判定證據是否齊全；同一命令中排在前面的 append-log 尚未執行，閘門看到的永遠是補寫前的狀態。擋下時整條命令都不執行，前段的寫入也一併丟失。

擋下訊息只說「缺少某項」，不說「評估發生在命令執行前」。執行者容易把第二次擋下讀成「補的證據內容不合格」，進而改寫證據文字重試，問題卻在命令的切分方式。

## 解決方案

把「讓閘門條件成立的寫入」與「受閘門管制的命令」拆成兩次 Bash 呼叫：

1. 先執行 append-log、set-where 等補件寫入，確認結束碼與 `[verify]` 輸出。
2. 再單獨執行 `ticket track complete`。

## 預防措施

- 送出受 PreToolUse 閘門管制的命令（`complete`、`claim`、`git commit` 等）時，若同一命令裡有寫入能改變閘門判定，一律拆開。
- 閘門擋下後重送前，先確認上一條命令中的寫入是否真的執行過（例如 `grep -c` 票面上的新段落），不要直接改寫證據內容。
- 工具層改善方向：閘門偵測到同一命令內有前置寫入時，在擋下訊息加一行「本閘門在命令執行前評估，前段寫入未執行，請拆成兩次呼叫」。
