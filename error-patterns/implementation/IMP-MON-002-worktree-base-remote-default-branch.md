---
id: IMP-MON-002
title: CC worktree 隔離以遠端預設分支為 base（session 啟動快取），非 origin/main
type: implementation
severity: high
status: active
source: 0.2.0 v0.2.0 GREEN wave worktree 派發實證
related:
  - ARCH-003
  - parallel-dispatch
---

# IMP-MON-002: Worktree Base 是遠端預設分支（非 origin/main）

## 摘要

CC runtime 的 worktree 隔離（`isolation: "worktree"`）建立 worktree 時，base 是**遠端預設分支**（`origin/HEAD` 指向的分支），且該值在 **session 啟動時快取**（環境區塊「Main branch」），session 中途改 git/gh ref 不會更新。worktree hook 訊息宣稱「base = origin/main」與實際不符。當遠端預設分支不是工作主線（如本案誤設為只有 scaffold 的 `feat/initial-scaffold`）時，所有 implementation agent 的 worktree 落在缺前置的舊 commit，只能 NeedsContext。

## 症狀

| 症狀 | 觀察點 |
|------|--------|
| worktree agent 回報 base 缺 collector/、空 tickets/、無前置檔 | Exit Status NeedsContext，head=scaffold commit |
| `git push origin main` 後 worktree 仍落在舊 commit | 改 origin/main 無效 |
| `git symbolic-ref refs/remotes/origin/HEAD` 指向非主線分支 | 遠端預設分支誤設 |
| 環境區塊「Main branch (PRs): X」X 非 main | session 啟動快取值 |

## 根因

worktree base 取自 CC harness 對「main 分支」的判定 = 遠端預設分支，於 session 啟動解析並快取。git/gh ref 的 mid-session 變更不會回寫該快取。本案根因是 repo 預設分支被設為 `feat/initial-scaffold`（scaffold only），實際開發在 `main`。

## 防護

1. 派發 implementation worktree agent 前，確認**遠端預設分支** = 工作主線：`git symbolic-ref refs/remotes/origin/HEAD` 與 `gh repo view --json defaultBranchRef`。
2. 永久修：`gh repo edit --default-branch main` + `git remote set-head origin main`（下 session 生效）。
3. **本 session 即時解鎖**（快取值無法刷新時）：把遠端預設分支快進到主線內容（`git branch -f <default> main && git push origin <default>`），worktree base 即含全部前置。
4. 每次 merge 後 push main 並同步遠端預設分支，維持 worktree base 最新。
5. worktree hook 訊息的「base = origin/main」是錯誤假設，勿據以排錯。

## 來源

0.2.0 v0.2.0 GREEN wave（3 輪 worktree 失敗後定位）。專案 memory `worktree-base-is-remote-default-branch` 升級（0.2.0-W4-005）。
