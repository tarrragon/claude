---
id: PC-BAL-008
title: 同 repo 並行 agent 共用 git index，commit 掃入他人已 staged 檔案
severity: medium
category: process-compliance
related: [PC-BAL-007]
created: 2026-07-26
---

# PC-BAL-008: 同 repo 並行 agent 共用 git index，commit 掃入他人已 staged 檔案

## 症狀

- 並行派發多個 agent 到同一非 worktree repo（各自負責不同檔案，路徑零交集）
- 某方執行 `git add <自己的檔案> && git commit -m "<自己的訊息>"`，commit 卻包含他方的檔案
- commit 訊息與內容不符：標題宣稱 A 票的工作，`git show --stat` 顯示的卻是 B 票的檔案
- 內容本身無遺失也無錯誤，但 commit 歷史的可追溯性受損——後續考古會把 B 票的變更歸因到 A 票

## 根因

`git commit` 提交的是**整個 index**，不是「本次 `git add` 的檔案」。同一 repo 的所有行程共用一份 `.git/index`：

- agent A 完成工作、`git add` 自己的檔案後尚未 commit（或正在寫 ticket body）
- agent B（或 PM）此時執行 `git add <B 的檔案> && git commit`，index 中 A 已 staged 的檔案一併進入該 commit
- 兩者路徑零交集也無法避免——衝突發生在 index 這個共用狀態，不在檔案內容

「檔案路徑零交集即可安全並行」這個判準只對**工作區內容衝突**成立，對 **index 競態**不成立。

## 解決方案

- **git worktree 隔離**：需要各自 commit 的並行 agent 應分配獨立 worktree（`git worktree add`），各自擁有獨立 index
- **或改為單一 commit 者**：並行 agent 只改檔案不 commit，由 PM 在全部完成後統一分票 commit（`git add <路徑> && git commit` 逐票執行，中間無並行寫入）
- **或 pathspec commit**：`git commit <路徑...>` 只提交指定路徑（繞過 index 全量提交），但對已 staged 的他人檔案仍需注意

## 預防措施

- 派發前判斷：本批 agent 是否各自需要 commit？需要 → 用 worktree；不需要 → prompt 明確要求「只改檔案不 commit，由 PM 收尾」
- 已發生時不改寫歷史：內容正確的前提下，rebase 重寫會破壞 ticket body 已引用的 commit SHA；改為在兩票的 Solution 各記一筆「commit 落地備註」交叉指認
- Commit 後驗證：`git show --stat HEAD` 確認涵蓋檔案與預期一致，不以 `git add` 的參數為準

## 關聯

- PC-BAL-007（並行文件票未交叉驗證的事實漂移）：同屬並行派發的副作用家族；該模式風險在**內容**，本模式風險在**版控狀態**
- 實證：flutter_balance 0.2.1-W3-003 / W3-005（2026-07-26），commit `73e4ea3` 標題為 W3-005 收尾、內容全為 W3-003 檔案；W3-005 的原始碼變更早已由其 agent 自行 commit。內容無遺失，僅訊息與內容不符，兩票已交叉記錄
