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

## Action（防護 SOP）

### 偏好方案：PM 在 merge 前處理 staged 變更

```bash
# 1. merge 前確認 main 工作區
git status --porcelain --untracked=all

# 2. 若有 staged 同名 ticket md，先單獨 commit
git commit -m "chore(<ticket-id>): metadata sync post-completion"

# 3. merge worktree
git merge --no-ff worktree-agent-<id> -m "merge: ..."
```

此方式 staged commit 與 worktree commit 各成獨立節點，merge 演算法能識別兩者為時序兩點，自動 fast-forward 或安全 3-way merge。

### Fallback：衝突發生時採 worktree SSOT

```bash
git checkout --theirs docs/work-logs/.../<ticket-id>.md
git add docs/work-logs/.../<ticket-id>.md
git commit -m "merge: ... (resolve conflict 採 worktree 版)"
```

**為何 worktree 是 SSOT**：subagent 在 worktree 完成的 ticket md 包含完整 Test Results、Solution、Completion Info、Exit Status——main 的 auto-stage 通常只覆蓋 frontmatter status / completed_at / acceptance 局部欄位。worktree 版含更多資訊，且 main 端的 frontmatter 變更最終也會在 worktree 內被 complete 流程寫入。

## 與其他 pattern 的關係

| Pattern | 關係 |
|---------|------|
| PC-154（worktree 派發兩前置） | 兩者皆為 worktree 工作流問題；PC-154 在派發**前**、PC-155 在合併**後** |
| W11-035（complete auto-stage 機制） | PC-155 是該機制的副作用；W11-035 不該關閉，但 PM 需理解其與 worktree 並行的時序 |
| `feedback_worktree_merge_after_agent` | feedback 強調「立即合併」，PC-155 補充「合併前先處理 staged」 |

## 案例

**0.19.0-W1-048.2（2026-05-23）**：

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

## 防護升級展望

長期方向：

1. auto-stage hook 可偵測「同名 ticket md 已被 worktree 修改」並跳過 staging
2. ticket complete CLI 可在 worktree 模式下傳 `--skip-main-stage` flag，由 PM merge 時統一處理

目前以 PM SOP（先處理 staged，再 merge）為主。
