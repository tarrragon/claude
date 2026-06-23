---
id: PC-MON-001
title: 並行 worktree 代理人 commit 交叉混入
severity: medium
frequency: first-occurrence
affected_components:
  - parallel-dispatch
  - worktree-isolation
  - agent-commit
first_seen: "2026-06-23"
resolved: false
---

# PC-MON-001: 並行 worktree 代理人 commit 交叉混入

## 症狀

多個代理人以 `isolation: "worktree"` 並行派發，各自修改不同模組（無檔案交集）。完成後 commit 歷史顯示：

- commit 內容交叉混入——A 代理人的 commit 包含 B 代理人的檔案
- commit 訊息與實際內容不符
- 線性歷史無分支——所有 commit 在同一分支上，無 merge commit

## 根因

CC runtime 的 `isolation: "worktree"` 建立獨立工作目錄但多個 worktree 可能共用同一個分支 ref。多個 worktree 的 `git add + commit` 競爭同一個分支的 HEAD，導致先完成的代理人 commit 帶入其他代理人的未 staged 檔案。

**Why**：git worktree 機制中，多個 worktree checkout 同一分支時共用 ref，`git add .` + `git commit` 不是原子操作，併發執行產生 race condition。

**Consequence**：commit 歸屬不正確（`git blame` / `git log --follow` 失真），但檔案內容完整不遺失。

**觸發條件**：主 repo 不在 main 分支 + 多個 worktree agent 同時 git commit。

## 防護措施

### 派發前（PM 操作）

| 措施 | 動作 | Why |
|------|------|-----|
| 確保主 repo 在 main | 派發前 `git checkout main` | 避免代理人 worktree 共用 feature 分支 |
| 先 push 到 origin | `git push origin main` | worktree base 為最新 main |
| prompt 指定獨立分支 | 加 `git checkout -b feat/<ticket-id>` | 每個代理人在獨立分支，消除 ref 競爭 |

### Prompt 範例

```
完成後先建立獨立分支再 commit：
  git checkout -b feat/<ticket-id>
  git add <specific-files>
  git commit -m "..."
```

### 合併收尾

每個代理人的分支獨立 merge 到 main，逐一驗證。

## 案例

### 2026-06-23 W3-012.2/012.3/013/014/015 並行派發

5 個 fennel-go-developer agent 各修改不同 collector 模組。主 repo 在 `feat/W3-013` 分支。

| Commit | 標記 | 實際包含 |
|--------|------|---------|
| 3c741fb | W3-012.3 協議 | config + rule + protocol（3 個模組混入） |
| 07a690c | W3-012.2 Ingest | sqlite storage 檔案 |
| f7534fc | W3-014 SQLite | query handler 檔案 |
| 518cc96 | W3-012.2 Ingest | 正確（只有 ingest） |
| 3dc0235 | W3-015 Config | 只有 ticket md（程式碼已在 3c741fb） |

功能不受影響，全專案 `go test ./...` 結果正確（58 FAIL 紅燈）。

## 相關

- PC-078：動態並行 session working tree 污染
- W3-007：worktree base 取 origin/main 而非 local main
- W3-008：worktree 隔離對 daemon-rooted 工具不生效
- `.claude/pm-rules/parallel-dispatch.md`：並行派發規則

## 防護驗證結果

W3-016 單一代理人 worktree 派發驗證：

| 檢查項 | 結果 |
|--------|------|
| CC runtime 自動建立獨立分支 | `feat/0.1.0-W3-016-integration-tests` |
| commit 內容無交叉混入 | 只有 4 個整合測試檔 |
| commit 訊息與內容一致 | 正確 |

**結論**：單一代理人的 worktree 隔離完全正確。交叉混入只在多代理人同時派發且共用分支 ref 時發生。下次多代理人並行派發時，需確保主 repo 在 main + 已 push origin，讓 CC runtime 為每個代理人建立獨立分支。

---

**Created**: 2026-06-23
**Updated**: 2026-06-23
**Source**: W3-012.2/012.3/013/014/015 並行派發實測 + W3-016 單一派發驗證
