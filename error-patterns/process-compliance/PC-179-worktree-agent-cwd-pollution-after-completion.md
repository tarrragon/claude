# PC-179: worktree agent 完成後主線程 cwd 污染致 merge 誤判

## 摘要

`isolation: "worktree"` 的實作代理人完成後，主線程 Bash 工具的工作目錄（cwd）會被帶入該 worktree 子目錄（`<repo>/.claude/worktrees/agent-<id>/`），而非停留在主 repo root。後續主線程在此污染 cwd 執行 `git merge <worktree-branch>`，因當前分支已是 worktree branch 本身，變成「對自己 merge」→ 回報 `Already up to date`，但主 repo 的 main 實際**未整合** worktree 的 commit。根因是 worktree agent 結束後主線程 cwd 未自動還原，PM 預設「cwd 仍在主 repo root」的假設失準。修正方向：merge 前先 `pwd` + `git worktree list` 確認 cwd，被污染時用絕對路徑還原（`cd /絕對/repo/root && git merge`）再操作。

## 症狀

- worktree agent 完成後，主線程 `git merge <worktree-branch>` 矛盾回報 `Already up to date`，但 `git branch --contains <commit>` 不含 main
- `git worktree list` 顯示主 repo 在 `[main]`，但同一 cwd 下 `git branch --show-current` 回 `worktree-agent-<id>`
- `pwd` 落在 `.claude/worktrees/agent-<id>/` 而非主 repo root
- 誤判「worktree 工作已合併」，實際 main 未整合，若未察覺會在後續 push 時遺漏 worktree commit

## 根因（worktree agent 結束後 cwd 未還原）

worktree agent 在自己的 worktree 工作目錄執行所有操作。agent 結束後，主線程繼承的 Bash cwd 指向該 worktree path（task-notification 的 `worktreePath` 欄位即是該目錄）。

| 環節 | 預期 | 實際 |
|------|------|------|
| agent 結束後主線程 cwd | 主 repo root | worktree 子目錄 |
| `git merge <worktree-branch>` 的當前分支 | main | worktree-agent branch（cwd 在 worktree 內） |
| merge 語意 | main ← worktree（fast-forward） | worktree branch ← 自己（already up to date） |

PM 預設「派發前 cwd 在主 repo root，派發後仍在」，但 worktree 隔離機制在 agent 結束後將主線程 cwd 留在 worktree。此假設失準與 `git merge` 對「當前分支 = 被 merge 分支」回報 already up to date 的正常行為共振，產生「工作已合併」的假象。

## 案例：W8-035.1 移除孤兒 widget 後 merge 誤判（2026-06-08）

PM 派發 parsley（isolation:worktree）執行 W8-035.1（移除 12 孤兒 widget 檔）。agent 完成後 PM 在主線程執行 `git merge worktree-agent-<id> --no-edit`，回報 `Already up to date`。但稍早 `git log main..worktree-agent-<id>` 明確顯示 worktree branch 領先 main 2 個 commit，`git branch --contains` 也確認 main 不含這些 commit——矛盾。

逐步診斷揭露 cwd 污染：

```bash
git worktree list                 # 主 repo 顯示 [main] 7aac7c60
git branch --show-current         # 回 worktree-agent-<id>（非 main！）
pwd                               # /repo/.claude/worktrees/agent-<id>（cwd 在 worktree 內）
```

確認後用絕對路徑還原並真正 merge：

```bash
cd /絕對/repo/root && git merge worktree-agent-<id> --no-edit
# → Updating 7aac7c60..f8e6f726  Fast-forward（這次才真正整合）
```

緩解因子：PM 在 merge 回報 already up to date 與先前 `git log main..worktree` 顯示有 commit 的矛盾下，未盲信 already up to date，逐步診斷（worktree list + branch --show-current + pwd）定位 cwd 污染，未造成 main 遺漏整合。屬 near-miss。

## 防護

| 步驟 | 動作 | 目的 |
|------|------|------|
| 1 | worktree agent 完成後、merge 前，先 `pwd` + `git worktree list` 確認 cwd | 偵測 cwd 是否被帶入 worktree 子目錄 |
| 2 | `git merge` 回報 already up to date 時，交叉驗證 `git branch --contains <commit>` 是否含 main | 區分「真已合併」vs「對自己 merge 假象」 |
| 3 | cwd 被污染 → 絕對路徑還原 `cd /絕對/repo/root && git merge`（規則一污染補救場景） | 在正確的主 repo / main 分支執行 merge |
| 4 | 整合後 `git worktree remove <path>` + `git branch -d <worktree-branch>` 清理 | 移除已合併的 worktree，避免殘留 |

**Why**：worktree agent 結束後主線程 cwd 不自動還原，是 harness 行為而非可從 code 推導的事實，PM 必須主動驗證而非假設。

**Consequence**：未驗證直接 merge 會因「對自己 merge」誤判工作已整合，main 實際遺漏 worktree commit，後續 push 同步殘缺，且 already up to date 訊息本身會強化錯誤假設。

**Action**：worktree agent 完成驗收後、執行任何依賴 cwd 的 git 寫入（merge / commit / push）前，先 `pwd` 確認；被污染則絕對路徑還原。

## 相關

- `.claude/error-patterns/implementation/IMP-008-bash-working-directory-pollution.md` — cwd 污染的一般形式（cd 持久改變）
- `.claude/rules/core/bash-tool-usage-rules.md` 規則一 — cwd 污染補救（絕對路徑還原）
- memory `project_worktree_cwd_pollution.md`（雙通道）+ `project_harness_worktree_forks_origin_main.md` — worktree fork base = origin/main 的姊妹陷阱

---

**Last Updated**: 2026-06-08 | **Source**: 0.31.1-W8-035.1 worktree merge near-miss
