---
id: IMP-V1-005
title: index.lock 競爭下 fast-forward 移動 HEAD 但 index 寫入失敗，後續 commit 靜默刪除剛合併的檔案
category: implementation
severity: high
created: 2026-07-03
source_ticket: 0.4.0-W1-002
---

# IMP-V1-005: Fast-forward 移動 HEAD 但 index 過時，後續 commit 靜默刪檔

## 症狀

`git merge <branch>` 輸出「error: Unable to write index. Automatic merge failed」，看似 merge 完全失敗；但稍後 `git merge` 同分支回報「Already up to date」、`git merge-base --is-ancestor` 確認分支已是 main 祖先——而分支引入的檔案卻不在 main tree（`git ls-tree -r main | grep` 命中 0）。無任何 git 錯誤或 conflict 提示指向檔案遺失。

## 根因

三個條件疊加：

1. **並行 session 的 index.lock 競爭**：同 repo 另一 session 恰在 merge 執行期間持有 index.lock。
2. **fast-forward 的非原子性**：merge 判定可 FF 後先移動 HEAD ref，再寫 index/working tree；HEAD 更新成功、index 寫入因 lock 失敗，留下「HEAD 已在新 commit、index 仍是舊 tree」的分裂狀態。
3. **後續 commit 以 index 為準**：下一個 `git add <特定檔> && git commit` 只更新被 add 的路徑，其餘 tree 內容沿用過時 index——相對於新 HEAD（含被合併檔案），該 commit 等效**刪除**了所有 FF 帶入的檔案，且 `git status` 事前不顯示任何異常（status 比對的也是同一份過時 index）。

**具體案例（0.4.0-W1-002）**：合併 worktree 分支（postgres 測試骨架 2 檔）時 FF + index 寫入失敗；接著 commit W1-008 的 ticket md，該 commit 對 parent 的 diff 含 `postgres.go | 121 ------` 與 `postgres_test.go | 473 ------`。

## 偵測

**固定值矛盾對**：`git merge-base --is-ancestor <branch> main` 為真 AND `git ls-tree -r main --name-only | grep <交付檔>` 命中 0 → 即為本 pattern，非「分支沒合到」。

## 解決方案

**當下修復**：`git checkout <原始 commit> -- <路徑>` 從分支原 commit 做 tree 層還原，獨立 commit 記錄事故因果（本案 e61a422）。

## 防護措施

1. **merge 後必驗交付物落地**：合併 worktree 分支後，以 `git ls-tree -r main --name-only | grep <where.files 關鍵檔>` 固定值確認，不以 merge exit code 或「Already up to date」為準（tool-output-trust 規則 3 的 merge 特化）。
2. **「Unable to write index」視為分裂狀態警報**：看到此訊息不可當「merge 沒發生」，必須立即 `git log --oneline -1` 對照 HEAD 是否已前移；已前移則先 `git reset`（重建 index 對齊 HEAD）再繼續任何 commit。
3. **index.lock 競爭場景意識**：同 repo 多 session 並行（本專案常態）時，merge/commit 前後的 lock 錯誤都應觸發「狀態一致性檢查」而非單純重試（與 IMP-046 / PC-139 互補：它們處理 lock 的成因與歸因，本 pattern 處理 lock 造成的靜默資料層後果）。

## 關聯

- IMP-046（git index lock race condition）——lock 競爭本身
- PC-139（index lock 來源誤歸因）——lock 歸因
- `.claude/rules/core/tool-output-trust-rules.md` 規則 3——固定值交叉驗證（本 pattern 的偵測手段）
