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

PM 並行派發多個會執行 `git add` + `git commit` 的代理人（或 PM 前台與 subagent 並行）時，因檔案修改與 staging 的時序交錯，共用同一份 git index，可能發生：

1. **檔案被併入錯誤批次**：A 代理人修改的檔案被 B 代理人的 `git add .` 一起 staged，導致 B 的 commit 包含 A 的變更
2. **Commit 訊息與實際邊界不對齊**：commit message 標 batch B，但實際 diff 含 batch A + B
3. **A 代理人 commit 失敗**：`no changes added to commit`（檔案已被 B commit）
4. **PM 裸 commit 掃入 subagent 暫存檔（v3）**：PM 前台跑無 pathspec 的 `git commit`，提交整個 index，把並行 subagent 已 `git add` 但未 commit 的檔案（及 ticket CLI auto-stage 填入的檔案）一併掃進 PM 的 commit

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

### v3 案例（2026-07-05，1.5.0-W5-009 混合派發）

前兩個案例是 **agent → agent** 的 `git add .` 互掃。v3 是 **PM 主線程 → subagent** 的不同 actor / 不同機制變體：

PM 混合派發時，一個 subagent（.5）在共用工作樹修改 `.claude/skills/wrap-decision/` 並 `git add` 該路徑（暫存但尚未 commit）。PM 前台完成 sibling ticket .1 後執行 `ticket track complete`，其 **auto-stage** 又 stage 了 .1 的 ticket md；PM 接著跑**無 pathspec 的裸 `git commit`**，提交的是「整個 index」——連同 .5 已暫存的 `premortem-workflow.md` 一併掃入 commit b7d6d40b4（訊息標 .1 metadata，實際含 .5 的新建檔）。

與 v1/v2 的關鍵差異：
- **actor**：掃入方是 PM 主線程，非另一個 subagent
- **機制**：觸發掃入的不是 `git add -A`，而是**裸 `git commit`（無 pathspec）提交整個已暫存 index**
- **index 汙染源**：ticket CLI 的 `complete` auto-stage 在 PM 未察覺下把檔案填進 index，PM 誤以為 index 只有自己的變更

內容未遺失（.5 工作樹隨後乾淨，檔案都在 feat 分支），但 commit 歸屬錯亂。之後 PM 全面改用精確 pathspec `git commit -- <path>` 後不再發生（.2 起各 commit 邊界乾淨）。

**為何 worktree 隔離無法迴避**：.5 編輯 `.claude/`，而 subagent 無法 Edit worktree 內 `.claude/`（ARCH-015 hardcoded 保護），故只能在主 repo 共用樹跑，方案 C 對此類 ticket 不適用，只剩 pathspec 紀律可靠。

## 根本原因

### 表層原因
代理人使用 `git add .` 或 `git add -A` 等廣域 staging 命令。

### 深層原因
1. **git index 是全 repo 共享狀態**：並行 worker 共用同一份 index
2. **代理人不知道其他並行工作存在**：subagent 不能看到 sibling agent 的 file 寫入
3. **`git add` 不檢查 ownership**：staging 任何 worktree 中的修改檔案
4. **PM 規則只防止「並行修改同檔案」未防「並行 commit 同 repo」**：feedback_parallel_agent_conflict 只覆蓋檔案層衝突
5. **裸 `git commit` 提交整個 index，非只提交自己的檔案（v3）**：commit boundary 由 index 現況決定，不由「意圖提交哪些檔案」決定。ticket CLI 的 `complete` / `append-log` auto-stage 會在 PM 未察覺下把檔案填進 index，使 PM 對 index 內容的心智模型與實際不符——PM 以為「只有我的變更」，實際含 auto-stage + 並行 subagent 已暫存的檔案

## 正確做法

### 方案 A：精準 staging（推薦）
代理人 prompt 明示：
```
git add <精確檔案路徑列表>，禁止使用 git add . / git add -A
```

**PM 主線程變體（v3）**：PM 在 subagent 並行於共用工作樹時，每個 commit 一律用**精確 pathspec 的 partial commit**，不用裸 `git commit`：
```
git commit -m "..." -- <精確路徑>   # 只提交該路徑，無視 index 其他已暫存檔
```
`git commit -- <path>` 只提交指定路徑，繞過 index 現況（含 ticket CLI auto-stage 與並行 subagent 的暫存檔），是 PM 側對應方案 A 的可靠寫法。

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
| PM 前台在 subagent 並行時 commit，是否用精確 pathspec `git commit -- <path>` 而非裸 commit？ | v3 案例：裸 commit + ticket CLI auto-stage 掃入並行 subagent 暫存檔（方案 A PM 變體） |

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
- feedback_pm_bare_commit_sweeps_subagent_staged — v3 案例的 memory（PM 裸 commit 掃入 subagent 暫存檔）
- feedback_pm_edit_during_agent_shared_worktree — 反方向（agent 掃 PM 未 commit 變更）
- PC-155 — auto-stage × worktree 並行編輯 merge conflict（ticket CLI auto-stage 交互的另一失敗面）
- ARCH-015 — subagent 無法 Edit worktree 內 `.claude/`（v3 中 worktree 隔離不適用的根因）

---

**Last Updated**: 2026-07-05
**v3 Source**: 1.5.0-W5-010（補 v3 案例：PM 主線程裸 commit + ticket CLI auto-stage 掃入並行 subagent 暫存檔，commit b7d6d40b4 實證；源 memory feedback_pm_bare_commit_sweeps_subagent_staged / 1.5.0-W5-009 混合派發）
**v2 Source**: 0.19.0-W3-060 commit 13ad538d + 0.19.0-W3-065 ticket（補 v2 案例 + PM PC-068/123 自評學習）
