---
id: PC-155
title: ticket complete auto-stage 與 worktree append-log 並行編輯同一 ticket md 造成 merge conflict
category: process-compliance
severity: low
source_case: 0.19.0-W1-048.2
created: 2026-05-23
---

# PC-155: auto-stage × worktree 並行編輯同檔造成 merge conflict

## 症狀

PM 完成 `git merge --no-ff worktree-agent-<id>` 命令後遭遇衝突，受影響檔案為 ticket md：

```
Auto-merging docs/work-logs/v*/v*.*/v*.*.*/tickets/<id>.md
CONFLICT (content): Merge conflict in docs/work-logs/v*/v*.*/v*.*.*/tickets/<id>.md
Automatic merge failed; fix conflicts and then commit the result.
```

額外訊號：

- PM 在 merge 前看到 `git status` 中含 `M  docs/work-logs/.../<id>.md`（已 staged）並 commit 進 main
- 同時 worktree 內 subagent 完成 ticket 流程含 `append-log Test Results` / `append-log Solution` / `complete` 的 metadata sync
- 兩端的 ticket md 變更時序重疊但獨立 commit

## Why

- **main 端**：`ticket track complete` 的 auto-stage hook 將 main repo 內的 ticket md 加入 staging（W11-035 行為）；PM 隨後 `git commit -am` 把 staged 變更落地。這個變更通常是 cinnamon agent complete metadata sync 的副本（路徑被 hook 同時管控）。
- **worktree 端**：subagent 在 complete 流程中 `append-log` 多次寫入 ticket md，且 complete 自身寫入 frontmatter status / completed_at 等欄位。worktree 累積多個 commit。
- merge 時：兩條 commit 鏈在 ticket md 同行區段（frontmatter status / log section）有不同寫入，git ort 策略無法自動推斷哪一份是「最新意圖」。

## Consequence

- merge 卡住，需手動解衝突
- 若 PM 不熟悉 ticket md 結構，可能誤採 main 的 partial metadata 而遺失 worktree 完整 Test Results / Solution
- Session 多一輪 tool call 處理衝突

## 兩種觸發變體

| 變體 | main/feature 端觸發源 | 時序 |
|------|----------------------|------|
| A：auto-stage | `ticket complete` 的 auto-stage hook 把 ticket md 加入 staging，PM commit | merge 後（complete 階段） |
| B：PM append-log | PM 派發前 `append-log` 寫 Problem Analysis / Context Bundle，auto-commit 落地 | 派發前（context 準備階段） |

兩者本質相同：main/feature branch 與 worktree 各自 commit 同一 ticket md。差異在於變體 B 的 PM 寫入（Problem Analysis / Context Bundle）可能**不在 worktree 版本中**（worktree 從 `origin/main` fork，不含 PM 的 local commits），`--theirs` 會丟失 PM 分析內容。

## Action（防護 SOP）

### 預防方案（推薦）：PM append-log 後 push origin 再派發

```bash
# 1. PM 寫入 Context Bundle
ticket track append-log <id> --section "Problem Analysis" "..."
ticket track append-log <id> --section "Context Bundle" "..."

# 2. push origin 確保 worktree fork 包含 PM 寫入
git push origin <branch>

# 3. 派發 worktree agent（worktree 從 origin fork，包含 PM commits）
```

**Why**：worktree 從 `origin/main`（或 `origin/<branch>`）fork，PM 的 local commits 未 push 則 worktree 不可見。先 push 使 fork 點在 PM append-log commits 之後，worktree agent 的後續 append-log 是追加而非分叉，merge 可 ff 或無衝突 3-way。

### 偏好方案（變體 A）：PM 在 merge 前處理 staged 變更

```bash
# 1. merge 前確認 main 工作區
git status --porcelain --untracked=all

# 2. 若有 staged 同名 ticket md，先單獨 commit
git commit -m "chore(<ticket-id>): metadata sync post-completion"

# 3. merge worktree
git merge --no-ff worktree-agent-<id> -m "merge: ..."
```

此方式 staged commit 與 worktree commit 各成獨立節點，merge 演算法能識別兩者為時序兩點，自動 fast-forward 或安全 3-way merge。

### Fallback：衝突發生時的解法

| 變體 | 解衝突策略 | 原因 |
|------|-----------|------|
| A（auto-stage） | `git checkout --theirs <ticket.md>` | worktree 版是 SSOT（含完整 Test Results / Solution / Completion Info） |
| B（PM append-log） | 手動 merge 或先確認 theirs 是否包含 PM 分析 | worktree 版可能缺 PM 的 Problem Analysis / Context Bundle |

**變體 A 為何 worktree 是 SSOT**：subagent 在 worktree 完成的 ticket md 包含完整 Test Results、Solution、Completion Info、Exit Status——main 的 auto-stage 通常只覆蓋 frontmatter status / completed_at / acceptance 局部欄位。worktree 版含更多資訊，且 main 端的 frontmatter 變更最終也會在 worktree 內被 complete 流程寫入。

**變體 B 注意**：若 PM 未 push 即派發，worktree agent 的 `claim` 也會 auto-commit ticket md（寫 frontmatter status/started_at），從 fork 點開始與 PM 的 append-log commits 分叉。此時 `--theirs` 會丟失 PM 的 Problem Analysis / Context Bundle。需手動確認或改用預防方案。

## 與其他 pattern 的關係

| Pattern | 關係 |
|---------|------|
| PC-154（worktree 派發兩前置） | 兩者皆為 worktree 工作流問題；PC-154 在派發**前**、PC-155 在合併**後** |
| W11-035（complete auto-stage 機制） | PC-155 是該機制的副作用；W11-035 不該關閉，但 PM 需理解其與 worktree 並行的時序 |
| `feedback_worktree_merge_after_agent` | feedback 強調「立即合併」，PC-155 補充「合併前先處理 staged」 |

## 案例

### 案例 1（變體 A）：0.19.0-W1-048.2（2026-05-23）

```
1. PM 派發 thyme-extension-engineer to worktree
2. subagent 完成：append-log Test Results + Solution + ticket complete（metadata sync）
3. main 端 auto-stage hook 把 docs/.../0.19.0-W1-048.2.md 加入 staging
4. PM `git commit -am "chore(...): main repo metadata sync (auto-stage)"` 落地該 staged 變更
5. PM `git merge --no-ff worktree-agent-<id>` → conflict
6. PM 採 fallback：git checkout --theirs <ticket.md> 解決
```

時序圖：

```
main:     ... ─── A (PM auto-stage commit) ─── M (merge attempt → conflict)
worktree:        ╲─── W1 (refactor) ─── W2 (ticket md append) ─── W3 (complete metadata)
                                                                    ↑
                                              W3 與 A 各自寫 ticket md frontmatter / log
```

### 案例 2（變體 B）：0.32.0-W3-030（2026-06-17）

```
1. PM 建 feature branch，執行 append-log Problem Analysis + Context Bundle（auto-commit 兩筆）
2. PM push origin feature branch
3. PM 派發 parsley to worktree（worktree 從 origin/main fork，不含 PM 的 append-log commits）
4. subagent 完成：claim（auto-commit）+ refactor commit + append-log Test Results + complete
5. PM merge worktree branch → conflict（ticket md 兩端各自寫入不同章節）
6. PM 採 git checkout --theirs 解決（此案例 worktree agent claim 後重新 append-log 了 Context Bundle，theirs 包含完整資訊）
```

時序圖：

```
feature:  ... ─── P1 (PM append-log PA) ─── P2 (PM append-log CB) ─── M (merge → conflict)
                   ↑ origin/main fork 點在此之前
worktree:    ╲─── W1 (claim) ─── W2 (refactor) ─── W3 (append-log TR) ─── W4 (complete)
```

**根因**：PM push 了 feature branch 但 worktree 從 `origin/main` fork（非 `origin/feature`），PM 的 P1/P2 commits 不在 worktree 祖先鏈上。

## 防護升級展望

長期方向：

1. auto-stage hook 可偵測「同名 ticket md 已被 worktree 修改」並跳過 staging
2. ticket complete CLI 可在 worktree 模式下傳 `--skip-main-stage` flag，由 PM merge 時統一處理
3. worktree 派發 hook 可偵測「ticket md 有 local uncommitted/unpushed append-log commits」並警告 PM 先 push

目前以 PM SOP（append-log 後 push origin 再派發 + 衝突時依變體選解法）為主。

---

**Last Updated**: 2026-06-17 | **Version**: 1.1.0 — 新增變體 B（PM append-log auto-commit 觸發）、預防方案（push origin 再派發）、案例 2（0.32.0-W3-030）、Fallback 變體對照表
