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

### v1 案例（2026-04-18，W5-043.3 + W5-043.4）

PM 並行派發 4 個 thyme-python-developer 子代理人：
- W5-030.1 修改 thyme-extension-engineer.md
- W5-043.2 修改 7 個 agent
- W5-043.3 修改 6 個 agent
- W5-043.4 修改 6 個 agent

W5-043.4 代理人（先完成）執行 `git add .` 時，把 W5-043.3 已寫入但尚未 commit 的 6 個檔案一併 staged 並 commit 為 8e5b05e4（訊息標 batch 4，實際含 batch 3 + batch 4 共 12 個檔案）。

W5-043.3 代理人後續嘗試 commit 時，看到 `no changes added to commit`，回報「commit race」。

### v2 案例（2026-05-26，W3-060 + W3-061）

PM 並行派發 2 個 thyme-python-developer 子代理人：
- W3-060 修改 `.claude/rules/core/quality-baseline.md` + `.claude/rules/core/pm-role.md` + `.claude/pm-rules/pm-quality-baseline.md`
- W3-061 修改 `.claude/error-patterns/process-compliance/PC-160-*.md` + `.claude/error-patterns/process-compliance/PC-061-*.md`

派發 prompt **已含**「禁止觸碰 .claude/error-patterns/」與「禁止觸碰 .claude/rules/」職責邊界聲明（per PC-092 v1 教訓），但**未含**「git add 顯式路徑、禁止 git add . / -A」staging 紀律明示。

W3-060 thyme（先完成）執行 `git add -A` 類行為，連帶 stage 並 commit W3-061 已寫入但未 stage 的 PC-160/PC-061，commit 13ad538d 含 7 檔（訊息標 W3-060，實際含 W3-060 主檔 3 + W3-061 主檔 2 + 兩個 ticket md）。

W3-061 thyme 後續執行 metadata sync commit 83149fc4 僅含 ticket metadata 變更（無主檔，因主檔已被連帶 commit）。

雙 ticket acceptance 全勾、內容正確，但：
- commit 13ad538d 的 commit message 與實際 diff 邊界不一致
- W3-061 的主要工作 git blame 會歸屬到 W3-060 ticket ID
- v1 教訓已寫入 parallel-dispatch.md L90「派發 prompt 必含精準 git staging」，但 W3-060/061 派發 prompt 未引用該段

**雙重失職**：
1. PM 失職 — 派發 prompt 未含 PC-092 v1 已固化的 staging 紀律明示（規則理解 ≠ 規則遵守，PC-123 家族）
2. Agent 失職 — agent-definition-standard 未強制 agent 在並行情境查詢 sibling 工作前 `git status` 預檢

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

| 檢查項 | 為何 |
|--------|------|
| 並行派發的代理人是否都會執行 git commit？ | 串接 commit + Hook 競爭 index.lock；並行 commit 撞 staging 範圍 |
| 若是，prompt 是否明示「git add 精確檔案路徑，禁止 git add ./-A」？ | v1 + v2 兩次案例都因缺此明示觸發 |
| 若工作量大，考慮選方案 D（PM 統一 commit）避免 race | v2 案例僅 2 個並行也撞到，並行數低不代表免疫 |
| 派發 prompt 是否引用 PC-092 與 parallel-dispatch.md L90 staging 紀律段？ | v2 案例 prompt 含職責邊界但漏 staging 紀律，證明分項引用是必要的 |
| 是否預期 agent 先 `git status` 預檢 working tree 才 git add？ | 防 agent 在 sibling 已 modified 未 stage 時誤判 staging 範圍 |

### 規則 / Hook 建議

- `.claude/pm-rules/parallel-dispatch.md` L90「派發 prompt 必含精準 git staging」段已固化，但 PM 派發時需主動將該段引用納入 prompt（v2 案例證明被動引用無效）
- 派發前 hook 建議：偵測 prompt 含 git commit 指令但不含「git add <顯式路徑>」+ 為並行派發場景時警告（強化現有 parallel-dispatch-verification-hook）
- agent-dispatch-template.md 「git staging 範例」段建議列為必填，dispatch-validate 偵測缺失

## 相關規則 / 經驗

- IMP-046 — Git index.lock 競爭條件（hook 與 commit 競爭）
- PC-091 — ANA 落地 Ticket 血緣關係
- PC-068 — ANA 規劃新建資產前必須 grep 既有同職責資產（v2 案例中 PM 自己違反，原本要建 PC-162 重複造輪子）
- PC-123 — 規則記載 ≠ 規則遵守（v2 案例核心：規則已存在但未被引用）
- feedback_parallel_agent_conflict — 並行代理人修改同檔案會衝突
- feedback_git_index_lock — Hook/Agent 的 git 操作與 commit 競爭

---

**Last Updated**: 2026-05-26
**v2 Source**: 0.19.0-W3-060 commit 13ad538d + 0.19.0-W3-065 ticket（補 v2 案例 + PM PC-068/123 自評學習）
