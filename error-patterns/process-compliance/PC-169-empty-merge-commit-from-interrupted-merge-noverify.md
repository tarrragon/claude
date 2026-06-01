---
id: PC-169
title: Merge 中斷後以 --no-verify commit 產生 empty merge commit 丟失工作
category: process-compliance
severity: high
status: active
created: 2026-06-01
---

# PC-169：Merge 中斷後以 --no-verify commit 產生 empty merge commit 丟失工作

## 症狀

PM 並行派發多個 isolation:worktree agent 後依序 merge 三個 worktree branch 回 main，其中某個 merge 報「Unable to write index. Automatic merge failed」，PM 觀察 `git status` 顯示「All conflicts fixed but you are still merging」+ unstaged 變更，誤判 merge 已部分完成，用 `git commit -F .git/MERGE_MSG --no-verify` 補上 merge commit。後續 `npm run lint` 暴露原本應被該 worktree 刪除的程式碼仍存在；git show <merge> 對 parent-1 (main) 為空 diff，對 parent-2 (worktree) 顯示反向 diff（merge commit 等同於採用 main 版本，完全忽略 worktree 變更）。

**核心識別訊號**：

| 訊號 | 說明 |
|------|------|
| `git diff <merge>~..<merge>` 對 worktree branch 修改的檔案為空 | merge 採 ours (main) 版本，theirs (worktree) 工作丟失 |
| Merge commit message 含 `# Conflicts:` 字樣但 conflict list 為空 | git 將中斷狀態包裝成「無 conflict 的 merge commit」 |
| Working tree 在 merge 報錯後有 unstaged 變更但 index 為空 | merge 解析寫到 working tree 而非 index，commit 只記錄空變化 |

## 根因

### 1. Merge 中斷的 working tree / index 不一致

ort merge 嘗試寫入 index 失敗（成因可能為 hook 干擾、I/O 競爭、或被 caller 中止），但 ort 已將部分合併結果寫到 working tree。git 進入「merge in progress」狀態（`.git/MERGE_HEAD` 存在），但 index 不含 merge 解析結果。

### 2. Git status 文字誤導

`git status` 顯示「All conflicts fixed but you are still merging. (use "git commit" to conclude merge)」。這句話被 PM 解讀為「已自動解 conflict、commit 即可完成」，實際語意是「沒有 unmerged 條目」（git ls-files -u 為空），但**沒說 index 已含 merge 結果**。

### 3. `git commit -F .git/MERGE_MSG` 使用空 index

merge state 下 `git commit` 用：
- **Tree**：當前 index 的內容
- **Parent #1**：HEAD
- **Parent #2**：MERGE_HEAD

當 index 為空（未含 merge 解析結果），產生的 merge commit 樹 = HEAD 樹 = ours 版本。Git 仍記錄 MERGE_HEAD 作為 parent-2 維持血緣鏈，但 **theirs 的所有變更被丟棄**。

### 4. `--no-verify` 預防性使用降低警示

PM 為避免 pre-commit hook 再次失敗用了 `--no-verify`，繞過了 lint-staged 或其他可能識別異常的閘門。即使 merge commit 本身不通常觸發 pre-commit hook（merge 是 commit 動作但 staged files 由 index 決定，此時 index 空），`--no-verify` 仍是個誤導訊號讓 PM 跳過正常驗證流程。

## 案例

**情境**：0.19.0-W4-024 三並行子任務（W4-024.1/.2/.3）派發 3 個 isolation:worktree agent 完成後 PM 依序 merge 回 main。

**事件鏈**：
1. W4-024.1 merge 成功（ort strategy，正常合併）
2. W4-024.2 merge 成功（ort，src 4 個檔合併無 conflict）
3. W4-024.3 merge 報「Unable to write index. Automatic merge failed」
4. PM `git status` 看到「All conflicts fixed but you are still merging」+ unstaged W4-024.2.md（殘留物，與 W4-024.3 無關）
5. PM `git commit -F .git/MERGE_MSG --no-verify` → 產生 commit 6086caab
6. PM 後續 `npm run lint` 暴露 W4-024.3 應刪除的 3 處 unused vars 仍在
7. 診斷：`git diff <merge>~..<merge> -- tests/e2e/browser/` 為空（採 ours 版本），W4-024.3 整個工作丟失
8. 修復：`git cherry-pick a555d751 5e7c3317`（W4-024.3 worktree 兩個 commit）補回變更

## Why

並行派發 worktree 是高頻 PM 操作（W17-203 模式 / askuserquestion-rules 規則 7），merge 中斷時 PM 沒有快速可信指標識別 index 是否完整。`--no-verify` 預防性使用是常見反模式（W17-XXX feedback memory），與 merge state 結合會產生靜默工作丟失。

## Consequence

| 影響 | 嚴重度 |
|------|-------|
| Agent 工作丟失（src/tests 修改 + ticket md frontmatter 狀態） | 高 |
| Acceptance 通過但 main 上 lint 失敗 | 高 — false positive 完成狀態 |
| 發現困難 — 只有額外驗證才能察覺 | 高 — PM 容易誤判 W4-024 Coordinator 已可 complete |
| 補救成本 — cherry-pick 帶來重複 commit 鏈 | 中 |

## Action

### Layer 1：PM 自律

| 場景 | 必要動作 |
|------|---------|
| Merge 報「Unable to write index」或任何寫 index 錯誤 | **禁止直接 commit 完成**，先 `git merge --abort` 重試或診斷成因 |
| `git status` 顯示「All conflicts fixed but you are still merging」 | 額外執行 `git diff --staged --stat` 確認 index 含預期變更；空 index 表示 merge 解析丟失 |
| 準備使用 `--no-verify` | 自問「為何 hook 會失敗？這不是繞過的理由」；merge commit 不應需要 `--no-verify`（pre-commit 對 staged files，merge 通常無 staged） |
| 三方 worktree merge 完成後 | **強制驗證**：`git diff <merge>~..<merge> -- <worktree changed files>` 應有預期 diff；對 parent-1 為空表示工作丟失 |

### Layer 2：診斷流程

merge 後驗證範本：

```bash
# 對每個 worktree merge commit 驗證
for branch in worktree-agent-X1 worktree-agent-X2; do
  merge_sha=$(git log --merges --grep="$branch" -1 --format=%H)
  echo "=== verifying $branch (merge $merge_sha) ==="
  # 對 parent-1 (main 側) 為空 = 採 ours，theirs 丟失
  git diff "$merge_sha~1..$merge_sha" --stat | head -10
done
```

### Layer 3：Hook 強制層（建議實作）

| Hook | 偵測 | 行為 |
|------|------|------|
| post-merge-empty-diff-check | merge commit 對 parent-1 diff 為空 | warning 提示「可能採 ours 丟失 theirs，請驗證」 |
| pre-commit-with-merge-head | `.git/MERGE_HEAD` 存在 + index 為空 + 用戶 commit | block 並提示「Empty index in merge state — 確認 merge 解析完整」 |

## 防護建議

| 場景 | 預防 |
|------|------|
| Merge 報錯 | `git merge --abort` 重試而非強行 commit |
| 並行派發 worktree 完成後 | merge 完成後跑相關 acceptance（lint / test）驗證 |
| `--no-verify` 使用 | 視為**紅旗訊號**，每次使用前必須能說出具體 hook 行為 |
| Working tree 殘留 unstaged 變更 | 在 merge 前 stash 並完成 merge 後再 unstash，避免狀態混淆 |

## 相關規則 / 模式

- `.claude/rules/core/bash-tool-usage-rules.md` 規則 3：禁止串接多個 git 寫入操作（與本 PC 互補：本 PC 處理單一 merge 失敗的處理錯誤）
- `CLAUDE.md` `--no-verify` 緊急豁免邊界（合規邊界基線）
- memory `feedback_git_index_lock`（IMP-046 git index.lock 競爭模式 — 可能成因之一）
- memory `feedback_premature_agent_verification`（並行 agent 完成後驗證模式）

## 識別清單

每次 merge 後自問：

- [ ] Merge 命令是否回報任何寫 index 錯誤？
- [ ] `git status` 是否顯示「you are still merging」？若是，是否真的有 staged 變更？
- [ ] 是否使用 `--no-verify`？若是，是否能說出具體理由（不是「為了讓 commit 通過」）？
- [ ] Merge 完成後是否跑相關驗證（lint / test）確認預期變更已合入？
- [ ] `git diff <merge>~1..<merge>` 對 worktree 修改的檔案是否含預期 diff？

---

**Source**: 0.19.0-W4-024 多任務並行派發 W4-024.3 worktree merge bug 事件（2026-06-01）。
