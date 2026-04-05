# PC-039: 代理人回報完成但主倉庫看不到變更（Worktree 未合併）

## 症狀

- 代理人回報完成（task-notification 顯示成功）
- PM 在主倉庫檢查 `git status` 或 `git log` 看不到變更
- PM 誤判代理人未完成工作，重複派發或手動重做

## 根因

代理人在 worktree（隔離分支）中工作並 commit，但 PM 忘記合併 worktree 分支回 main。主倉庫自然看不到 worktree 分支上的 commit。

**行為模式**：
1. PM 派發代理人到 worktree（`isolation: "worktree"` 或手動建立的 worktree）
2. 代理人完成工作並 commit 在 worktree 分支上
3. PM 回到主倉庫檢查，只看 main 分支 → 看不到變更
4. PM 誤判為「代理人未完成」，重複派發或手動重做
5. 原始 worktree commit 長期未合併，浪費工作成果

## 解決方案

**PM 在檢查代理人產出前，必須先確認 worktree 狀態：**

```bash
# 1. 列出所有 worktree
git worktree list

# 2. 檢查 worktree 分支是否有未合併 commit
git log main..feat/xxx --oneline

# 3. 合併 worktree 分支回 main
git merge feat/xxx --no-edit

# 4. 然後再檢查產出
```

## 預防措施

1. **agent-commit-verification-hook.py**（PostToolUse:Agent）已增強：
   - Agent 完成後同時檢查「未 commit」和「worktree 未合併」
   - 輸出合併提醒到 additionalContext
   
2. **worktree-merge-reminder-hook.py**（PostToolUse:Bash）作為第二道防線：
   - ticket complete 時再次檢查 worktree 合併狀態

3. **PM 行為規範**：
   - 代理人回報完成 → 先合併 worktree → 才驗證產出
   - 不要在未合併的情況下判斷代理人是否完成

## 診斷檢查清單

當「代理人回報完成但看不到變更」時：

- [ ] `git worktree list` 是否有非 main 的 worktree？
- [ ] `git log main..{branch} --oneline` 是否有 commit？
- [ ] 代理人的 task-notification 是否顯示了 commit hash？
- [ ] 該 commit hash 是否在 worktree 分支上而非 main？

## 關聯

- **Ticket**: 0.17.2-W2-018
- **相關模式**: PC-019（worktree merge 狀態遺失）、PC-024（代理人跳過 commit）
- **防護 Hook**: agent-commit-verification-hook.py, worktree-merge-reminder-hook.py

---

**發現日期**: 2026-04-05
**嚴重程度**: P1（導致重複工作和時間浪費）
