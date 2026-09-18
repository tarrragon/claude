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

# 5a. 若步驟 5 被擋下（fatal: ref updates aborted by hook）：
#     合併本身已對 branch-verify 豁免（多 parent 的合併 commit 判為
#     is_merge_commit，見 commit_content_guards._check_branch_verify），
#     仍被擋通常是其他內容 guard（如 reference-stability-rule8）。git 此時
#     已寫入 index 並建立 MERGE_HEAD，不會隨 deny 自動撤銷，須先清理：
git merge --abort
#     再依 stderr 訊息修正內容後重新執行步驟 5。

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

**案例（2026-09-08，本檔步驟 5 的建議指令曾與守衛互斥）**：本檔步驟 5 建議的
`git checkout main && git merge {branch} --no-edit`，被 `branch-verify` 守衛
（掛在 `reference-transaction` 原生 git hook，於 ref 寫入階段執行）擋下——
守衛的判定依據是「工作區目前在哪個保護分支」，不分辨這次寫入是合併還是
逐檔直接提交，故對 main 上帶有非豁免路徑的合併必然 deny。此時 git 已完成
合併計算、寫入 index 並建立 `MERGE_HEAD`，但守衛只擋住 ref 寫入本身，終端
訊息（`fatal: ref updates aborted by hook`）未提示這兩者已存在，發起者因而
誤判「合併沒發生」轉去分析守衛，殘局滯留主 repo 約一小時，期間三方 session
全數停手。根因是「同一份守衛換執行位置換答案」——同樣內容在代理人自己的
worktree 內提交會放行（非保護分支），到主 repo 執行合併才擋下。修復方式：
守衛新增合併 commit（多 parent）判定，命中即豁免 branch-verify（見
`.claude/lib/commit_content_guards.py` 的 `_check_branch_verify` 
`is_merge_commit` 參數）；仍被其他內容 guard（如 rule8）擋下的少數情形，
deny 訊息新增明確的 `git merge --abort` 清理指引（步驟 5a），消除步驟 4
的認知落差。

## 關聯

- **相關模式**: PC-019（worktree merge 狀態遺失）、PC-024（代理人跳過 commit）
- **防護 Hook**: agent-commit-verification-hook.py, worktree-merge-reminder-hook.py, git-ref-transaction-content-guard.py（reference-transaction，merge 情境判定與殘局提醒）
- **PM 規則**: .claude/pm-rules/agent-failure-sop.md（代理人失敗判斷前置步驟）

---

**發現日期**: 2026-04-05
**更新日期**: 2026-09-08（新增守衛與建議指令互斥案例，記錄修復方式）
**嚴重程度**: P1（導致重複工作和時間浪費）
