# Worktree 操作流程 SOP

本文件定義 PM 使用 worktree 隔離派發代理人時的標準操作流程。

> **來源**：PC-019 — Worktree 合併流程中 Ticket 狀態遺失。

---

## 核心原則

> **先 commit 再派發**：main 上的任何修改必須在派發 worktree agent 前 commit，防止 stash/checkout 操作導致變更丟失。

---

## 適用範圍與強制規則

| 情境 | 強制規則 |
|------|---------|
| 人工隔離 session | 使用 `claude --worktree <path>` 或 `claude -w <path>` 前，main 必須 clean 且 ticket 狀態已 commit |
| 背景實作 subagent | 非 `.claude/` 寫入任務預設使用 `isolation: worktree` |
| 大型或範圍明確任務 | 可設定 `worktree.sparsePaths`，但必須包含 source、test、fixture、ticket 文件 |
| worktree 生命週期觀測 | `WorktreeCreate` / `WorktreeRemove` event 只能用於記錄、提醒與檢查，不可取代 PM 合併判斷 |
| stale worktree | 清理前必須檢查未提交變更、未合併 commit、base 落後距離與可保留 diff |
| `.claude/` Edit/Write | 不使用 worktree subagent，依 ARCH-015 改由主 repo cwd 處理 |

---

## Claude Code Worktree 能力入口

### 入口選擇

| 情境 | 使用方式 | 備註 |
|------|---------|------|
| PM 要在獨立 worktree 開新互動 session | `claude --worktree <path>` 或 `claude -w <path>` | 適合長時間人工驗證或跨分支操作 |
| PM 派發背景 subagent 實作非 `.claude/` 檔案 | `isolation: worktree` | 預設選擇；避免 shared git index 競爭 |
| 只讀審查、ANA、DOC 前台修改 | 不需要 worktree | 依 command-routing 的分工路由處理 |
| `.claude/` Edit/Write | 主 repo cwd，不用 worktree | ARCH-015 強制限制 |

### CLI worktree session

使用 `--worktree` / `-w` 前仍必須先讓主 repo 乾淨：

```bash
git status --short
git add <files>
git commit -m "<message>"
claude --worktree ../book-overview-feature
```

短旗標等價：

```bash
claude -w ../book-overview-feature
```

**使用規則**：

- `--worktree` / `-w` 是 PM 人工 session 隔離入口，不取代 git 狀態檢查。
- 啟動前 main 必須 clean；若 ticket 狀態剛被 claim 或更新，先 commit。
- 啟動後立即確認 `pwd && git branch --show-current`，避免後續 git 操作落在錯誤分支。
- 結束前仍要跑本 SOP 的合併與清理流程。

### Subagent isolation frontmatter

背景實作代理人需要隔離時，派發設定必須明示 worktree：

```yaml
isolation: worktree
```

派發 prompt 應同時包含：

```text
Ticket: <ticket-id>
Scope: src/foo.py, tests/test_foo.py
Isolation: worktree
Do not edit .claude/ paths.
Commit your changes on the worktree branch before reporting completion.
```

**使用規則**：

- `src/`、`tests/`、`docs/` 等非 `.claude/` 實作任務可用 `isolation: worktree`。
- prompt 含 `.claude/` Edit/Write 時，不派 worktree subagent；改由 PM 前台或主 repo 流程處理。
- 若 ticket 是剛建立或剛更新，除 commit 外，prompt 必須附 ticket 絕對路徑，避免 IMP-066 的「worktree 看不到新 ticket」問題。
- agent 回報完成後，不可只看主 repo `git status`；先查 `git worktree list` 和 `git log main..{branch}`。

### `worktree.sparsePaths`

大型或檔案所有權明確的任務可設定 sparse checkout 範圍，讓 worktree 只暴露必要路徑：

```yaml
worktree:
  sparsePaths:
    - src/content/
    - tests/unit/content/
    - <ticket-file-path>
```

**使用規則**：

- sparsePaths 必須包含 agent 需要讀寫的 source、test、fixture、ticket 文件。
- 若 agent 需要讀框架規則，可加只讀參考路徑；但不要把 `.claude/` Edit/Write 放進 worktree 任務。
- 不確定依賴範圍時，不要過度稀疏；寧可先派較完整 worktree，再用 ownership 限制 prompt。
- 合併前用 `git -C <worktree> status --short` 和 `git -C <worktree> diff --stat main...HEAD` 確認 sparse checkout 沒漏掉必要產物。

### Worktree Hook events

`WorktreeCreate` / `WorktreeRemove` Hook events 用於觀測生命週期，不取代 PM 的人工合併判斷。

| Event | 建議用途 | 不可用途 |
|-------|---------|---------|
| `WorktreeCreate` | 記錄 branch、path、ticket、base commit；提示 stale base 檢查 | 不可視為任務已可安全開始 |
| `WorktreeRemove` | 記錄清理完成；檢查是否仍有未合併 commit | 不可自動丟棄未審查產出 |

Hook 實作應至少記錄：

```text
ticket_id, worktree_path, branch, base_commit, created_at, removed_at
```

**防護邊界**：

- Hook 可提醒 stale base、未合併 commit、殘留 worktree。
- Hook 不應在沒有 PM 明確決策時自動刪除含未合併 commit 的 worktree。
- Hook 提醒與 Checkpoint 1.9 要一致：ticket complete 前仍需 PM 主動檢查 worktree。

---

## Worktree 狀態檢查觸發點（強制，來源 PC-039）

> **原則**：任何決策點之前，先確認 worktree 是否乾淨。代理人產出在 worktree 分支上，不合併就不可見。

| 觸發時機 | 檢查內容 | 防護機制 |
|---------|---------|---------|
| **Agent 完成後**（最重要） | worktree 未合併 commit | agent-commit-verification-hook（自動提醒）+ PM 主動合併 |
| **ticket complete 前** | 所有 worktree 合併狀態 | worktree-merge-reminder-hook（自動提醒）+ Checkpoint 1.9 |
| **切換 Ticket 前** | 殘留 worktree | PM 主動執行 `git worktree list` |
| **handoff/session 結束前** | 所有 worktree + 未提交 | PM 主動檢查 |
| **push 前** | 確認所有 worktree 已合併 | worktree-branch-check-hook（自動提醒） |

**PM 強制動作**（每個觸發點都必須執行）：

```bash
# 1. 列出 worktree
git worktree list

# 2. 檢查未合併 commit
git log main..{branch} --oneline

# 3. 合併（如有）
git merge {branch} --no-edit

# 4. 清理
git worktree remove {path}
git branch -d {branch}
```

---

## 三階段標準流程

### 階段 1：派發前（Pre-dispatch）

| 步驟 | 動作 | 原因 |
|------|------|------|
| 1 | 完成 Ticket 狀態更新（5W1H、claim、accept-creation） | 確保 Ticket 資訊完整 |
| 2 | `git add` + `git commit` main 上的變更 | **強制**，防止 stash 丟失（PC-019） |
| 3 | 確認 `git status` 為 clean | 確保無殘留未提交變更 |
| 4 | 決定 `--worktree` / `-w` session 或 `Agent(isolation: "worktree")` | 依人工 session 或背景 subagent 選入口 |
| 5 | 若任務範圍明確，設定 `worktree.sparsePaths` | 降低大型 worktree 污染與 checkout 成本 |

**禁止**：main 上有未提交變更時派發 worktree agent。

### 階段 2：合併時（Post-agent）

| 步驟 | 動作 | 原因 |
|------|------|------|
| 1 | 確認工作目錄：`pwd && git branch --show-current` | Agent 可能污染 shell CWD |
| 2 | 若不在 main：`git checkout main`（不要 stash） | 回到 main 分支 |
| 3 | 查看 worktree 變更：`git -C .claude/worktrees/agent-{id} status --short` | 確認產出物 |
| 4 | 用 `cp` 從 worktree 提取檔案到 main | **推薦方式**，避免 merge 衝突 |
| 5 | 在 main 上跑測試確認 | 驗證產出物在 main 正常運作 |
| 6 | `git add` + `git commit` | 提交合併後的變更 |

**提取方式選擇**：

| 方式 | 適用場景 | 風險 |
|------|---------|------|
| `cp`（推薦） | 新增檔案、覆蓋已知檔案 | 低 |
| `git merge` | 大量變更、需保留 commit 歷史 | 中（可能衝突） |
| `git cherry-pick` | 需要特定 commit | 中 |

### 階段 3：清理後（Cleanup）

| 步驟 | 動作 | 原因 |
|------|------|------|
| 1 | 確認產出物已在 main 上且測試通過 | 清理前驗證 |
| 2 | `git worktree remove .claude/worktrees/agent-{id} --force` | 移除 worktree |
| 3 | `git branch -D worktree-agent-{id}` | 刪除對應分支 |
| 4 | 確認 `git worktree list` 無殘留 | 驗證清理完成 |

**批量清理**：

```bash
# 移除所有 agent worktree
git worktree list | grep "agent-" | awk '{print $1}' | while read wt; do
  git worktree remove "$wt" --force 2>/dev/null
done

# 刪除所有 worktree 分支
git branch | grep "worktree-agent-" | xargs git branch -D 2>/dev/null
```

---

## Shell 工作目錄保護

| 問題 | 原因 | 防護 |
|------|------|------|
| Agent 完成後 CWD 在 worktree 路徑 | Agent 工具可能改變 shell 狀態 | 每次 Agent 完成後執行 `pwd && git branch --show-current` |
| `git status` 顯示錯誤分支的狀態 | CWD 在 feature 分支 | 確認在 main 後才執行 git 操作 |
| `git stash` 後 `stash drop` 丟失變更 | main 上有未提交變更 | **禁止**：先 commit 再派發（階段 1 步驟 2） |

---

## 並行 Worktree 注意事項

| 場景 | 處理方式 |
|------|---------|
| 兩個 agent 修改不同檔案 | 安全，依序 `cp` 即可 |
| 兩個 agent 修改相同檔案 | 禁止，派發前確認檔案所有權互斥 |
| Agent A 依賴 Agent B 的產出 | 序列派發，不可並行 |

---

## Stale Worktree 清理

> 來源：PC-036、PC-039。

stale worktree 是「仍存在但基底過舊、已合併、或無人負責」的 worktree。清理前必須先判斷是否含有可用產出。

### 判斷流程

| 步驟 | 命令 | 判斷 |
|------|------|------|
| 1 | `git worktree list` | 找出 `.claude/worktrees/agent-*` |
| 2 | `git -C <path> status --short` | 有未提交變更則不可直接刪 |
| 3 | `git log main..<branch> --oneline` | 有未合併 commit 則先審查 |
| 4 | `git log <branch>..main --oneline | wc -l` | 落後太多時視為 stale base |
| 5 | `git diff --stat main...<branch>` | 判斷是否還有可搬回 main 的產出 |

### 清理決策

| 狀態 | 動作 |
|------|------|
| 無未提交、無未合併 commit | 可移除 worktree 並刪 branch |
| 有未提交變更 | 先審查；需要保留則 commit 或複製到 main |
| 有未合併 commit，且基底不舊 | merge 或 cherry-pick 後再清理 |
| 有未合併 commit，但基底過舊 | 優先 diff/cherry-pick 有價值片段；避免直接 merge 造成 revert |
| 無法判斷價值 | 建 ticket 或記錄決策，不做靜默刪除 |

### 安全清理命令

```bash
git worktree remove .claude/worktrees/agent-{id}
git branch -d worktree-agent-{id}
```

只有在已確認產出無需保留、且有明確決策紀錄時，才使用 `--force` / `-D`。

---

## .claude/ 路徑限制（強制，來源 ARCH-015）

> **核心規則**：**`.claude/` 變更不在 worktree 進行**。subagent 對 worktree 內 `.claude/` 路徑的 Edit/Write 會被 CC runtime hardcoded 拒絕，無法繞過。

### 派發位置決策

派發 subagent 前判斷 prompt 是否提及 `.claude/` 路徑修改：

| Prompt 內容 | 派發位置 | 執行者 |
|------------|---------|-------|
| 含 `.claude/` 路徑 Edit/Write | **主 repo cwd**（不進 worktree） | PM 前台 或 主 repo subagent |
| 僅含非 `.claude/` 路徑（src/、tests/、docs/） | worktree 或主 repo 皆可 | worktree subagent |
| 跨 `.claude/` 與其他路徑 | **拆分為兩次派發** | .claude/ 主 repo + 其他 worktree |

### 為何此限制不可繞過

實證（5 受控實驗）：

| 嘗試的繞過方式 | 結果 |
|--------------|------|
| subagent frontmatter `permissionMode: bypassPermissions` | 無效 |
| settings.json `additionalDirectories` 絕對路徑 | 無效 |
| settings.json `additionalDirectories` glob pattern | 無效 |
| Agent 工具 `mode: "acceptEdits"` 參數 | 無效 |
| `--add-dir` 啟動參數 / `/add-dir` runtime 命令 | PM 無法執行（無對應 deferred tool） |

**不要繼續嘗試上述任何方式。** CC runtime 對 `.claude/` 有 hardcoded 寫入保護，僅允許主 session cwd 內的 `.claude/`。詳見 ARCH-015。

### Read 操作不受限制

subagent 在任何 cwd 都可 Read worktree 內的 `.claude/` 檔案。可用於：
- subagent 比對 worktree 與主 repo 的 `.claude/` 差異
- subagent 讀取 worktree 內框架規則作為決策依據

僅 Edit/Write 受限。

---

## 檢查清單

### 派發前
- [ ] main 上 `git status` 為 clean？
- [ ] Ticket 狀態已更新且 committed？
- [ ] 已選擇 `--worktree` / `-w` 人工 session 或 `isolation: worktree` subagent？
- [ ] 若使用 `worktree.sparsePaths`，是否包含 source / tests / fixtures / ticket？
- [ ] Agent prompt 包含 `Ticket: {id}`？
- [ ] 若 prompt 提及 `.claude/` 路徑 Edit/Write，cwd 為**主 repo**（非 worktree）？（ARCH-015）

### 合併時
- [ ] `pwd && git branch --show-current` 確認在 main？
- [ ] `git worktree list` 檢查 worktree 產出物？
- [ ] `git branch | grep feat/` 檢查 feature 分支產出物？
- [ ] 若 branch 落後 main 很多，先按 stale worktree 流程評估，不直接 merge？
- [ ] 合併到 main 後測試通過？

### 清理後
- [ ] 產出物已 commit 到 main？
- [ ] Worktree 和分支已刪除？
- [ ] `WorktreeRemove` 事件或等效紀錄已可追溯？

---

## 手動修復前檢查清單

> **來源**：PM 在背景代理人執行時自行修復同一 Ticket 的歷史事件。

在手動修復任何問題前，**必須先確認無背景代理人正在處理**：

| 步驟 | 動作 | 命令 |
|------|------|------|
| 1 | 檢查 active dispatch | `cat .claude/dispatch-active.json` |
| 2 | 檢查 worktree 分支 | `git worktree list` |
| 3 | 確認無衝突 | 目標檔案不在任何 active dispatch 的 files 清單中 |

**自動防護**：
- `active-dispatch-tracker-hook.py`（PostToolUse:Agent）自動清理完成的派發記錄
- `main-thread-edit-restriction-hook.py` 會在 PM 編輯已派發檔案時發出 WARNING

**如果發現衝突**：
1. 等待背景代理人完成
2. 合併代理人產出物
3. 在代理人產出物基礎上繼續修復

**禁止**：在背景代理人執行中直接修復同一檔案。

---

## 相關文件

- .claude/error-patterns/process-compliance/PC-019-worktree-merge-state-loss.md
- .claude/error-patterns/process-compliance/PC-036-worktree-stale-base-commit-invalid-work.md
- .claude/error-patterns/process-compliance/PC-039-worktree-unmerged-invisible-output.md
- .claude/error-patterns/architecture/ARCH-015-subagent-claude-dir-hardcoded-protection.md
- .claude/error-patterns/implementation/IMP-066-subagent-worktree-ticket-cli-invisible.md
- .claude/pm-rules/parallel-dispatch.md - 並行派發規則
- .claude/pm-rules/command-routing.md - DOC/ANA/IMP/TST 分工路由
- .claude/pm-rules/decision-tree.md - Checkpoint 1.9 Worktree 合併
- .claude/rules/core/bash-tool-usage-rules.md - 禁止 cd 污染

---

**Last Updated**: 2026-04-21
**Version**: 2.2.0 - 補充 CC worktree 入口、sparsePaths、Hook events 與 stale cleanup
