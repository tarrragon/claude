---
id: PC-GPD-065
title: /clear 後以 repo 最近活動推定自身身份，接手了另一條線的票
category: process-compliance
severity: medium
status: active
created: 2026-10-31
related:
- PC-BAL-073
- PC-166
- PC-BAL-042
---

# PC-GPD-065：/clear 後以 repo 最近活動推定自身身份

## 基本資訊

- **Pattern ID**: PC-GPD-065
- **分類**: process-compliance（多 session 協作的身份判定）
- **風險等級**: 中
- **關聯**: [[PC-BAL-073]]（以專案名索引行為；本模式是自身方向的同型錯誤：把別人的活動當成自己的）、[[PC-166]] 規則 5（記錄平面不是 ground truth）、[[PC-BAL-042]]（跨 session 訊息誤續舊線）

## 症狀

多個 session 並行時，某個 session 在 `/clear` 後收到「繼續」。它沒有查自己的 session 名稱和協調票上屬於自己的佇列，而是從 repo 最近的活動推定自己是誰：git log 最後一筆是哪張票、票面 `who.current` 寫誰。推定成立後，它認領並實作另一條線建立的票，回報也署那條線的名字。

實例（2026-10-31）：一條線的 `/clear`＋「繼續」本身就是用戶在做 clear 實測，該線佇列只剩「clear 實測（用戶）→ 收線」。它看到 git log 最後一筆是另一條線剛建的子票，票面 `who.current` 寫「<另一條線>（本 session）」，便以那條線的身份 claim、實作、合併、complete，並以其名義回報主控。主控從訊息來源 socket 對不上才發現。

## 根因

- **Why**：`/clear` 後 context 清空，唯一的身份線索在 context 之外（session 狀態檔、協調票佇列行），不主動查就沒有。repo 的最近活動是並行各線共用的，最新一筆屬於哪條線與本 session 無關。`who.current` 的「（本 session）」是寫入者視角的相對指稱，被其他 session 讀到時指向的是寫入者，不是讀者。
- **Consequence**：

| 層級 | 影響 |
|------|------|
| 工作歸屬 | 接手別人的票；原持有者以為票還在自己手上，可能重複實作或發生衝突 |
| 自己的佇列 | 原本該做的事（實例中是配合用戶實測後收線）被擱置，且 /clear 本身是實測這件事沒被辨認 |
| 回報 | 以他人名義回報，主控的協調紀錄被誤導；需靠訊息來源等外部線索才能發現 |
| 票面紀錄 | who.current、complete 的 `--as` 都記成錯的執行者 |

## 解決方案

- **Action**：`/clear` 或 `/compact` 後要接續工作前，先查世界平面的身份，再查自己的佇列：

| 步驟 | 做法 |
|------|------|
| 1. 查自己是誰 | 以本 session 的 sessionId 比對 `~/.claude/sessions/*.json` 取得名稱（或用看板／`line_status`） |
| 2. 查自己的佇列 | 以名稱找協調票上自己的現行佇列行，依該行決定下一步 |
| 3. 不用的線索 | git log 最近一筆、票面 `who.current` 的相對指稱（「本 session」）、`runqueue` 排序：這些都是全 repo 共用的，不指出「我」 |

事後發現已誤接手時：改 who.current 為實際執行者、在票面寫更正、回報主控；已合併且經主控核可的產出不撤回（品質基線規則 6，產出無害）。

## 預防措施

- 票面 `who.current` 避免寫「本 session」這類相對指稱，改寫線號加名稱。
- 可評估以 SessionStart（source=clear／compact）hook 注入本 session 名稱與現行佇列行，讓身份線索不依賴 AI 主動查。

## 關聯 Ticket

- 本專案 2026-10-31 恢復開工通知送出紀錄檔子票（被誤接手；票面 Completion Info〈執行者更正〉）
