---
id: PC-092
title: 並行代理人 git index 競爭導致 commit 邊界與訊息不對齊
category: process-compliance
severity: medium
status: active
created: 2026-04-18
related:
- PC-091
- IMP-046
---

# PC-092: 並行代理人 git index 競爭導致 commit 邊界與訊息不對齊

## 問題描述

PM 並行派發多個會執行 `git add` + `git commit` 的代理人時，因檔案修改與 staging 的時序交錯，可能發生：

1. **檔案被併入錯誤批次**：A 代理人修改的檔案被 B 代理人的 `git add .` 一起 staged，導致 B 的 commit 包含 A 的變更
2. **Commit 訊息與實際邊界不對齊**：commit message 標 batch B，但實際 diff 含 batch A + B
3. **A 代理人 commit 失敗**：`no changes added to commit`（檔案已被 B commit）

工作內容**不會遺失**（仍在 git 歷史中），但 commit 邊界混亂，後續溯源/revert 困難。

## 觸發案例

**事件**（2026-04-18，W5-043.3 + W5-043.4 並行派發）：

PM 並行派發 4 個 thyme-python-developer 子代理人：
- W5-030.1 修改 thyme-extension-engineer.md
- W5-043.2 修改 7 個 agent
- W5-043.3 修改 6 個 agent
- W5-043.4 修改 6 個 agent

W5-043.4 代理人（先完成）執行 `git add .` 時，把 W5-043.3 已寫入但尚未 commit 的 6 個檔案一併 staged 並 commit 為 8e5b05e4（訊息標 batch 4，實際含 batch 3 + batch 4 共 12 個檔案）。

W5-043.3 代理人後續嘗試 commit 時，看到 `no changes added to commit`，回報「commit race」。

## 根本原因

### 表層原因
代理人使用 `git add .` 或 `git add -A` 等廣域 staging 命令。

### 深層原因
1. **git index 是全 repo 共享狀態**：並行 worker 共用同一份 index
2. **代理人不知道其他並行工作存在**：subagent 不能看到 sibling agent 的 file 寫入
3. **`git add` 不檢查 ownership**：staging 任何 worktree 中的修改檔案
4. **PM 規則只防止「並行修改同檔案」未防「並行 commit 同 repo」**：feedback_parallel_agent_conflict 只覆蓋檔案層衝突

## 正確做法

### 方案 A：精準 staging（推薦）
代理人 prompt 明示：
```
git add <精確檔案路徑列表>，禁止使用 git add . / git add -A
```

### 方案 B：序列化 commit（低風險高摩擦）
PM 不並行派發會 commit 的代理人，改為序列。

### 方案 C：worktree 隔離（適合長任務）
為每個並行代理人建立獨立 worktree，互不干擾。

### 方案 D：PM 統一 commit
代理人不執行 commit，僅修改檔案，回報後 PM 統一逐 ticket commit。

## 補救措施（觸發案例）

本案例選擇接受混合 commit：
- 內容正確（所有檔案在 git 歷史中）
- ticket 全 complete（驗收結果不變）
- commit 訊息與實際邊界不對齊（後人查 8e5b05e4 看到 batch 4 訊息但含 batch 3 變更，需透過 ticket complete log 還原邊界）

可選清理（未做）：`git revert` + 重 commit 切分，但會擾動 main branch 歷史。

## 預防措施

### 派發前檢查清單
- [ ] 並行派發的代理人是否都會執行 git commit？
- [ ] 若是，prompt 是否明示「git add 精確檔案路徑，禁止 git add ./-A」？
- [ ] 若工作量大，考慮選方案 D（PM 統一 commit）避免 race

### 規則 / Hook 建議
- 在 `.claude/rules/core/parallel-dispatch-rules.md` 或 pm-rules 加入 PC-092 防護
- agent-dispatch-validation Hook 偵測：若 prompt 含「git add .」「git add -A」且為並行派發場景 → 警告

## 相關規則 / 經驗

- IMP-046 — Git index.lock 競爭條件（hook 與 commit 競爭）
- PC-091 — ANA 落地 Ticket 血緣關係
- feedback_parallel_agent_conflict — 並行代理人修改同檔案會衝突
- feedback_git_index_lock — Hook/Agent 的 git 操作與 commit 競爭

---

**Last Updated**: 2026-04-18
