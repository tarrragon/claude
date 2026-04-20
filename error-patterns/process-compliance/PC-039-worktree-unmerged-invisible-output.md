# PC-039: 代理人回報完成但主倉庫看不到變更（Worktree/Feature 分支未合併）

## 症狀

- 代理人回報完成（task-notification 顯示成功）
- PM 在主倉庫檢查 `git status` 或 `git log` 看不到變更
- PM 誤判代理人未完成工作，重複派發或手動重做

## 根因

代理人在 worktree 或 feature 分支中工作並 commit，但 PM 只看 main 分支的 `git status`，看不到其他分支上的 commit。

**行為模式（兩種場景）**：

**場景 A - Worktree 分支**：
1. PM 派發代理人到 worktree（`isolation: "worktree"`）
2. 代理人完成工作並 commit 在 worktree 分支上
3. PM 在主倉庫檢查 `git status` -> 看不到變更
4. PM 誤判為「代理人未完成」，重複派發

**場景 B - Feature 分支**：
1. PM 或代理人建立了 feature 分支（如 `feat/0.17.3-W2-001-consolidate-808080`）
2. 代理人在 feature 分支上 commit 了變更
3. PM 回到 main 分支檢查 `git status` -> 看不到變更（因為在另一個分支）
4. PM 誤判為「代理人未完成」，不必要地重新派發
5. 原始 feature 分支 commit 被遺忘，浪費工作成果

## 解決方案

**PM 在檢查代理人產出前，必須先確認所有分支狀態：**

```bash
# 1. 確認當前位置
pwd && git branch --show-current

# 2. 列出所有 worktree
git worktree list

# 3. 列出所有 feature 分支
git branch | grep feat/

# 4. 檢查分支是否有未合併 commit
git log main..{branch} --oneline

# 5. 合併分支回 main
git checkout main && git merge {branch} --no-edit

# 6. 然後再檢查產出
```

## 預防措施

1. **agent-commit-verification-hook.py**（PostToolUse:Agent）已增強：
   - Agent 完成後同時檢查「未 commit」、「worktree 未合併」和「feature 分支未合併」
   - CWD 還原提醒改為條件化（只在 worktree 代理人時顯示）
   - 新增「PM 立即動作」摘要，整合所有狀態為一個清晰的下一步清單
   
2. **worktree-merge-reminder-hook.py**（PostToolUse:Bash）作為第二道防線：
   - ticket complete 時再次檢查 worktree 合併狀態

3. **PM 行為規範**（pm-rules/agent-failure-sop.md 失敗判斷前置步驟）：
   - 判斷代理人是否失敗前，必須先執行分支檢查
   - 禁止只看 `git status` 就判定代理人失敗

## 診斷檢查清單

當「代理人回報完成但看不到變更」時：

- [ ] `pwd && git branch --show-current` 確認當前分支是 main？
- [ ] `git worktree list` 是否有非 main 的 worktree？
- [ ] `git branch | grep feat/` 是否有 feature 分支？
- [ ] `git log main..{branch} --oneline` 是否有 commit？
- [ ] 代理人的 task-notification 是否顯示了 commit hash？
- [ ] 該 commit hash 是否在其他分支上而非 main？

## 實際案例

**案例（2026-04-09）**：代理人在 `feat/0.17.3-W2-001-consolidate-808080` 分支上成功 commit 了 5 個檔案的修改，但 PM 在 main 上執行 `git status` 看不到變更，誤判代理人失敗並重新派發，浪費了一次代理人執行。

**案例（2026-04-10）**：同樣的錯誤再次發生。代理人在 feature 分支上完成了 CSS 修改，PM 又誤判為失敗。

## 關聯

- **相關模式**: PC-019（worktree merge 狀態遺失）、PC-024（代理人跳過 commit）
- **防護 Hook**: agent-commit-verification-hook.py, worktree-merge-reminder-hook.py
- **PM 規則**: .claude/pm-rules/agent-failure-sop.md（代理人失敗判斷前置步驟）

---

**發現日期**: 2026-04-05
**更新日期**: 2026-04-10（擴展覆蓋 feature 分支場景）
**嚴重程度**: P1（導致重複工作和時間浪費）
