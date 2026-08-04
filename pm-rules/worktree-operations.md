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
| 背景實作 subagent | 非 `.claude/` 寫入任務預設使用 `isolation: worktree`；唯讀規劃/分析派發可豁免，見下方「唯讀派發豁免 worktree 強制」節 |
| 大型或範圍明確任務 | 可設定 `worktree.sparsePaths`，但必須包含 source、test、fixture、ticket 文件 |
| worktree 生命週期觀測 | `WorktreeCreate` / `WorktreeRemove` event 只能用於記錄、提醒與檢查，不可取代 PM 合併判斷 |
| stale worktree | 清理前必須檢查未提交變更、未合併 commit、base 落後距離與可保留 diff |
| `.claude/` Edit/Write | 不使用 worktree subagent，依 ARCH-015 改由主 repo cwd 處理 |

---

## 唯讀派發豁免 worktree 強制（0.2.1-W3-269，框架 issue 36）

> **用途**：PM 派發實作代理人執行**唯讀規劃/分析階段**（如 TDD Phase 3a 只讀不寫）時，若明確宣告唯讀，可豁免上方「適用範圍與強制規則」表列的 worktree 強制，不需為純唯讀工作先建立/切換 worktree。
>
> **命名說明**：本節提及的三個 hook（`agent-dispatch-validation-hook.py`、`worktree-pre-dispatch-branch-drift-hook.py`、`worktree-commit-before-dispatch-hook.py`）與本文件「Worktree 狀態檢查觸發點」表的 Guard A/B 是不同語境的獨立命名，本節不沿用該表字母代號，避免與 Guard A（`worktree-remove-deliverable-check-hook`，remove 前交付物驗證，與本節主題無關）混淆；其中 `worktree-pre-dispatch-branch-drift-hook.py` 恰為該表的 Guard B，其餘兩個 hook 未在該表出現。

**Why**：worktree 隔離的目的是防止並行寫入互相覆蓋（見「核心原則」），唯讀階段不產生寫入衝突，強制 worktree 隔離對此類派發只有成本沒有收益——consumer 被迫先合併 feat 分支才能派發，對純唯讀階段成本過高（框架 issue 36）。

**Consequence**：未使用本豁免時，唯讀派發仍會被 `agent-dispatch-validation-hook.py` 判定為未使用 worktree 而阻擋，PM 需額外走一次不必要的 worktree 建立流程才能派發純讀取任務。

**Action — 聲明方式**：prompt **首行**（strip 後第一行）逐字寫：

```
Dispatch-Mode: readonly
```

三條件 AND 判準（`_is_dispatch_mode_readonly_prompt`，`.claude/skills/ticket/hooks/agent-dispatch-validation-hook.py`）：(1) 必須是首行，非文中任意位置 (2) 以 `Dispatch-Mode:` 固定前綴開頭 (3) 值（冒號後 strip）大小寫不敏感等於 `readonly`。三條件缺一即不豁免，維持現行 worktree 強制阻擋。

**適用判準（何謂唯讀階段）**：只讀不寫的規劃/分析工作，代表情境如 TDD Phase 3a（實作策略規劃，產出虛擬碼/流程圖但不動實際程式碼）、唯讀審查、純分析報告。判斷依據是**該次派發是否會產生任何檔案寫入**，不是代理人的一般職責定義——同一代理人這次派發若確實會寫入檔案，即不得宣告本豁免。

**反例（不可使用本豁免的情境）**：

| 情境 | 說明 |
|------|------|
| 任何會寫入檔案的派發 | 即使只是小改，只要有 Edit/Write 就不得宣告 `Dispatch-Mode: readonly`——宣告後 hook 即放行不建 worktree，寫入會直接落在派發當下的 cwd，可能污染主 repo 或既有 worktree |
| 外部 `.claude/`（非本專案）路徑 | 不受本豁免影響——外部 `.claude/` 路徑在判斷序列最前一律阻擋（runtime 必拒），先於本豁免判斷 |
| 值非 `readonly`（如 `Dispatch-Mode: review`） | 三條件不符，不豁免 |
| 非首行宣告（如夾在 prompt 中段） | 三條件不符，不豁免 |
| Agent 工具 `dispatch_mode` 結構化參數 | **無效**——探針實測確認 CC runtime 組 PreToolUse hook payload 時剝離 Agent tool_input 的自訂欄位，唯一有效聲明方式是 prompt 首行文字（0.2.1-W3-269 Problem Analysis 附 hook log 證據） |

**與 review mode 的關係**：與既有 W10-084 審查模式豁免（prompt 全文含「審查/review/掃描/scan/評估/evaluate」等關鍵字）為 **OR 關係**——任一命中即豁免 worktree 強制，兩者判斷邏輯互相獨立、互不取代。差異：review mode 是全文關鍵字比對，本豁免是首行固定格式協議（結構化精確比對，非關鍵字掃描），issue 36 明文要求後者形式以避免關鍵字比對法的誤判風險。

**其餘兩道檢查無需另外處理**：`worktree-pre-dispatch-branch-drift-hook.py`（即本文件「Worktree 狀態檢查觸發點」表的 Guard B）與 `.claude/skills/worktree/hooks/worktree-commit-before-dispatch-hook.py` 皆以 `isolation == "worktree"` 為觸發前提；本豁免路徑不設定該欄位，兩者的跳過條件自然生效，不需額外設定。

**派發 prompt 骨架速查**：見 `.claude/references/agent-dispatch-template.md`「唯讀派發豁免 worktree 強制」節。

---

## Claude Code Worktree 能力入口

### 入口選擇

| 情境 | 使用方式 | 備註 |
|------|---------|------|
| PM 要在獨立 worktree 開新互動 session | `claude --worktree <path>` 或 `claude -w <path>` | 適合長時間人工驗證或跨分支操作 |
| PM 派發背景 subagent 實作非 `.claude/` 檔案 | `isolation: worktree` | 預設選擇；避免 shared git index 競爭 |
| 只讀審查、ANA、DOC 前台修改 | 不需要 worktree | 依 command-routing 的分工路由處理 |
| `.claude/` Edit/Write | 主 repo cwd，不用 worktree | ARCH-015 強制限制 |

### bgIsolation 策略選擇

Claude Code v2.1.143+ 提供 `worktree.bgIsolation` 設定，控制 background sessions（subagent）是否使用 worktree 隔離。

| 設定值 | 行為 | 適用情境 |
|--------|------|---------|
| `"worktree"`（預設） | subagent 自動建立 worktree 隔離 | 並行 src/ 修改、需 git index 隔離 |
| `"none"` | subagent 直接在主 repo working copy 操作 | 條件式採用，需評估並行 git index 競爭風險 |

**策略對照表**：

| 策略 | 設定 | 收益 | 風險 |
|------|------|------|------|
| A. 維持 worktree（短期推薦） | 不設定（預設） | 並行 git index 隔離；既有規則 / hook 不需修改 | 殭屍 worktree 累積（已有 GC hook 緩解） |
| B. 全面 none | bgIsolation: none | 消除合併成本；可能解鎖 subagent .claude/ Edit | 並行 git index 競爭；PC-092 風險必然化 |
| C. 條件式（長期目標） | 不改預設；特定任務 per-dispatch override | 兼顧上述兩者優勢 | 需 per-dispatch override 可行性確認；規則複雜度增加 |

**受控實驗結論摘要**：

| 假設 | 內容 | 驗證結果 |
|------|------|---------|
| A | deny 綁定 subagent cwd（worktree cwd ≠ 主 repo cwd 時觸發） | **成立**（單一 subagent + bgIsolation: none + .claude/ Edit → success） |
| B | deny 綁定 subagent 身份（任何 subagent 對 .claude/ Edit 均受限） | **否證** |

**實驗範圍限制**：僅驗證單一 subagent。並行 3+ subagent 情境（PC-137 真正關注場景）由後續並行受控實驗驗證。 <!-- PC-093-exempt: history:0.19.0-W3-034.1 W3-034.4 為實驗驗證歷史錨點 -->

**目前建議（v0.19.x）**：採策略 C（條件式採用），W3-034.4 並行受控實驗驗證落地。 <!-- PC-093-exempt: history:0.19.0-W3-034.4 為實驗驗證歷史錨點 -->

**Why**：W3-034.4 並行受控實驗（bgIsolation: none + 並行 3 subagent + `.claude/` Edit）取得 3/3 success（PC-137 v1.1.0 落地）；單一 subagent 場景另由 W3-034.1 驗證 success。bgIsolation: none 模式下並行 `.claude/` Edit 已具備可控證據，不需繼續停留在策略 A 的全面 worktree 短期建議。

**Consequence**：未升級會讓 `.claude/` 並行修改場景持續受策略 A 的並行 ≤ 2 限制（PC-137 worktree 模式規則），無法利用 bgIsolation: none 已驗證的並行解鎖；同時與 PC-137 v1.1.0「bgIsolation: none 例外」章節脫節，造成讀者誤外推。

**Action**：

| 派發情境 | bgIsolation 設定 | 理由 |
|---------|------------------|------|
| 涉及 src/ / tests/ 並行 subagent | worktree（預設） | 保留 git index 隔離，避免 PC-092 風險；業界並行 AI agent 標準 |
| 單一 subagent + `.claude/` Edit | none 可選 per-dispatch override | W3-034.1 驗證 success；ARCH-015 主 repo cwd 規則仍適用 |
| 並行 3+ subagent + `.claude/` Edit | **none 必用**（worktree 模式並行 ≤ 2 禁止 3+） | W3-034.4 驗證 success；commit 由 PM 統一執行避免 PC-092 |
| 跨 `.claude/` + src/ 混合修改 | 拆兩次派發（`.claude/` 用 none，src/ 用 worktree） | ARCH-015 + bgIsolation 衝突避免 |
| 全面切換 bgIsolation: none | **暫不採用** | 並行 commit 與 5+ 並行未驗證；對 src/ 失去 worktree 隔離保護。當前正向路徑：採策略 C 條件式採用（per-dispatch override），待 5+ 並行需求或 PC-092 共享 index 驗證需求出現時，建 ANA ticket 對照實驗 |

**未驗證情境（仍受限）**：

| 情境 | 風險 |
|------|------|
| bgIsolation: none + 並行 + 子代理人各自 git add/commit | PC-092 共享 index 競爭未測 |
| bgIsolation: none + 並行 5+ subagent | 更高並行度未測，採並行 ≤ 3 為觀察上限 |

> 上表屬規則檔擴充性說明（依 `.claude/rules/core/decision-trigger-binding.md` 規則 1.5，rules/方法論可述未來考量，不需綁 ticket trigger）。實際出現 5+ 並行需求或需驗證 PC-092 共享 index 行為時，建 ANA ticket 執行對照實驗。

**不採策略 B 的理由**：全面 bgIsolation: none 對 src/ 並行修改場景失去 git index 隔離保護（PC-092 風險必然化）；策略 C 保留 worktree 為預設，僅在 `.claude/` 場景 per-dispatch override 為 none，兼顧兩者優勢。

**參考**：

- ARCH-015（`.claude/` Edit 邊界 — 本文件下方「.claude/ 路徑限制」章節）
- PC-137 v1.1.0（並行 ≤ 2 規則 + bgIsolation: none 例外章節）
- PC-092（並行 commit 邊界混亂）

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

**實作 agent commit 紀律（強制，來源 1.2.0-W1-028 事故一）**：派發 worktree 實作 agent 的 prompt 必須明示「回報完成前，先 `git add <where.files> && git commit` 產品碼進 worktree 分支；ticket CLI 只 commit metadata，不代為 commit 產品碼」。PM 收到回報後用階段 2/3 的 `git log main..{branch}` + Guard A 驗證交付物確已 commit。完整論證（為何 ticket CLI 不 commit 產品碼、與 PC-024 push 禁令的邊界）見 `.claude/agents/AGENT_PRELOAD.md` 規則 6「worktree 隔離派發時必須 commit 產品碼進 worktree 分支」。

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
| **派發 worktree 前**（Guard B） | 主 repo HEAD 是否漂移離開 main | worktree-pre-dispatch-branch-drift-hook（阻擋 exit 2） |
| **Agent 完成後**（最重要） | worktree 未合併 commit | agent-commit-verification-hook（自動提醒）+ PM 主動合併 |
| **ticket complete 前** | 所有 worktree 合併狀態 | worktree-merge-reminder-hook（自動提醒）+ Checkpoint 1.9 |
| **worktree remove 前**（Guard A / Guard C） | 分支是否有未 merge 進 main 的交付物（Guard A）+ target worktree 是否已 clean（Guard C） | worktree-remove-deliverable-check-hook（阻擋 exit 2）+ PM 固定值驗證硬規則 |
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

#### Guard B 前置：派發前確認主 repo 未漂移（來源 1.2.0-W1-028 事故二）

> **Why**：cwd 污染後主 repo HEAD 可能漂移到 feat 分支（如 `feat/<ticket>-...`）。在漂移基底上派發 worktree，後續 `git -C <main> merge` 會落在誤切分支而非 main，`push` 顯示 up-to-date 但 `git log main` 查無交付物，工作落錯位置難以察覺。
> **Consequence**：交付物 merge 進 feat 分支而非 main，PM 誤以為已完成，實際 main 無變更。
> **Action**：每次 worktree 派發前，用世界平面固定值確認主 repo 分支：

```bash
git -C <project-root> branch --show-current   # 必須回 main/master
```

非 main/master 時，先 `git checkout main` 校正再派發。`worktree-pre-dispatch-branch-drift-hook` 在 `isolation: worktree` 派發時自動檢查並阻擋漂移（exit 2）。

**禁止**：用 cwd-relative 查詢（裸 `git status`、`git branch`）推斷主 repo 狀態——cwd 在 worktree 內時會回 worktree 分支狀態，騙過判斷（tool-output-trust 規則 3：關鍵事實一律用固定值/明示 ref）。

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
| `git checkout <ref> -- <paths>` | 跨 phase 傳遞（刻意不落 main，見下方「多階段串接派發」節） | 低（僅取程式碼路徑，不取 ticket md） |

### 階段 3：清理後（Cleanup）

| 步驟 | 動作 | 原因 |
|------|------|------|
| 1 | **Guard A：用固定值驗證 ticket 交付物確在 main**（見下） | **強制**，防 1.2.0-W1-028 事故一資料遺失 |
| 2 | 確認產出物已在 main 上且測試通過 | 清理前驗證 |
| 3 | `git worktree remove .claude/worktrees/agent-{id} --force` | 移除 worktree |
| 4 | `git branch -D worktree-agent-{id}` | 刪除對應分支 |
| 5 | 確認 `git worktree list` 無殘留 | 驗證清理完成 |

#### Guard A：remove 前必須驗證交付物已落地 main（PM 硬規則，來源 1.2.0-W1-028 事故一）

> **Why**：實作 agent 在 worktree 建檔+測試通過但只 ticket CLI auto-commit metadata、未 git commit 產品碼時，PM merge 僅得 metadata（merge stat「1 file changed」是紅旗）。此時 `worktree remove --force` 會永久刪除未提交工作樹，`git fsck` 無 unreachable，產品碼無法復原。
> **Consequence**：ticket 交付物（產品碼）永久遺失，需重做整個 ticket。
> **Action**：`git worktree remove` 前，對每個 `where.files` 用世界平面固定值（非 cwd-relative 推斷）確認確在 main：

```bash
# 擇一，皆以 main ref 為準（固定值，tool-output-trust 規則 3）
git show main:<where.files> | head        # 有內容才代表已落地
git ls-tree -r main --name-only | grep <file>   # 命中才代表已落地
```

任一交付物在 main 查無內容 → **禁止 remove**，先 merge/cherry-pick 該 worktree 分支。

**自動防護**：`worktree-remove-deliverable-check-hook`（PreToolUse:Bash）偵測 `git worktree remove`，若該 worktree 分支有未 merge 進 main 的 commit（`git log main..<branch>` 觸及檔案）→ 阻擋（exit 2）。`--force` 不繞過此檢查（檢查在 hook 層，先於 git 執行）。

#### Guard C：remove 前必須確認 target worktree working tree 已 clean（PM 硬規則，來源 0.2.1-W3-280，issue 46 症狀四）

> **命名說明**：本節代號原為「Guard B」，因與 `worktree-pre-dispatch-branch-drift-hook`（本文件「Worktree 狀態檢查觸發點」表已分配的 Guard B，派發前主 repo 分支漂移檢查）撞號，於 0.2.1-W3-285 改名為 Guard C，避免同一字母指向兩個語意無關的 hook。

> **Why**：merge 完成後 Guard A 即放行，但 worktree working tree 內未提交的修改（已追蹤或未追蹤）不在 commit 歷史中，`remove --force` 會使其永久遺失。這是 1.2.0-W1-028 事故一在「merge 已完成」路徑下的變體（issue 46 症狀四）。
> **Consequence**：代理人寫入但未 commit 的內容（或殘留的未追蹤檔案）在 remove 時被靜默丟棄，`git fsck` 無 unreachable 可查，遺失不可逆。
> **Action**：`git worktree remove` 前，對每個目標 worktree 用固定值確認 working tree 已 clean：

```bash
git -C <path> status --porcelain   # 無輸出即代表 clean，可安全 remove
```

非空時依情況擇一處理：保留變更則 `git -C <path> add <paths> && git -C <path> commit -m "<message>" -- <paths>` 後 `git merge <branch> --no-edit`；確認可捨棄則 `git -C <path> restore .` + `git -C <path> clean -fd .`。處理完成後重跑上方 status 命令確認為空，再執行 remove。

**自動防護**：`worktree-remove-deliverable-check-hook`（PreToolUse:Bash）在 Guard A 放行後，額外檢查 target worktree 的 `git status --porcelain`，非空即阻擋（exit 2），依未追蹤/已追蹤分組列出將遺失的內容並附上述逐字修復命令。`--force` 不繞過此檢查。

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

## 多階段串接派發（Feat 分支累積器）

> **適用情境**：完整 TDD 跨多個 agent 接力（如 sage 寫 RED → pepper 定策略 → parsley 寫 GREEN → cinnamon 修），且 harness `isolation: worktree` 使每個 agent 的 worktree 都 base 在 origin/main。上方三階段標準流程假設「單一 agent、產出立即落 main」；本節補充的是「N 個 agent 依序接力、main 須全程恆綠」情境，既有單 agent 流程不受影響。

**Why**：把中間產出（如尚未通過的 RED 測試）直接 merge 進 main 會使 main 出現紅燈，違反 quality-baseline 規則 1（main 恆綠）。

**Consequence**：不採用分支累積器、每個 phase 產出都直接 merge 進 main，會讓 main 在跨 agent 交接期間反覆紅綠，且難以回溯是哪個 phase 造成當前失敗。

**Action**（四步驟）：

| 步驟 | 動作 | Why |
|------|------|-----|
| 1 | 首個 phase（如 sage 的 RED 測試）產出推上 **feat 分支**（非 main），PM `git push origin feat/<ticket>-<phase>` | 隔離未完成產出，main 不受影響 |
| 2 | 下游 phase（如 parsley GREEN）的 worktree base origin/main，用 `git checkout origin/feat/<ticket>-<prev-phase> -- <paths>` 只取程式碼路徑、不 merge 分支；完成後 push 為新 feat 分支供下一 phase 接手 | 只取程式碼繞開 ticket md 分歧，見下方說明 |
| 3 | 全鏈完成、main 外測試通過後，PM 在 main 上 `git checkout <final-branch> -- <code-paths>` 並一次 commit（不 merge） | ticket md 由 PM 在 main 統一更新，不隨程式碼一併帶入 |
| 4 | worktree 清理前先 `git merge -s ours <branches> --no-edit` | 見下方「與 Guard A 的銜接」 |

**為何用 checkout-paths 而非 merge**：各 phase 代理人都會用 `ticket track append-log` 把執行紀錄寫入自己分支上的 ticket md，若用 `git merge` 落地會在 ticket md 上產生衝突（每分支版本不同）。checkout-paths 只取程式碼路徑（如 `lib/`、`test/`），繞開 ticket md 的分支間分歧；ticket md 內容由 PM 在 main 上統一維護。

**與 Guard A 的銜接**：checkout-paths 落地只複製檔案內容，不會使 feat 分支的 commit 進入 main 的祖先鏈，`git log main..<branch>` 仍會顯示該分支有「未落地」的 commit，觸發本文件階段 3 Guard A 與 `worktree-remove-deliverable-check-hook` 阻擋 remove。`git merge -s ours <branches> --no-edit` 只建立一個標記已合併的 merge commit（tree 內容維持 main 現狀不變、程式碼不受影響），使該 hook 判定通過後才能安全 remove worktree 與刪除 feat 分支。

**與階段 2「提取方式選擇」的關係**：本節是該表第四列 `git checkout <ref> -- <paths>` 的展開說明，適用於跨 phase 傳遞、刻意不落 main 的情境；`cp` / `git merge` / `git cherry-pick` 三法仍是單 agent 產出立即落 main 的預設選擇，不受本節影響。

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

### 邊界註記：claude agents dashboard 的自動 commit/push/PR（CC 2.1.198+）

CC 2.1.198 起，**從 `claude agents` dashboard 啟動的背景 session** 在 worktree 完成程式碼工作後會自動 commit、push 並開 draft PR，不再停下詢問。**Why**：本框架派發模式為 PM session 內 Agent tool 派發，不經 dashboard，此行為不觸發；但若未來改用 dashboard 派發程式碼工作，draft PR 會未經 PM 驗收 gate 出現在 GitHub（外部化動作）。**Action**：改用 dashboard 派發前必先重新評估此項；絆腳索——GitHub 出現 PM 未發起的 draft PR 時立即重新評估（評估紀錄見 1.5.0-W5-001.4）。

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
- [ ] **Guard B：`git -C <project-root> branch --show-current` 確認主 repo 在 main/master（未漂移）？**
- [ ] 已選擇 `--worktree` / `-w` 人工 session 或 `isolation: worktree` subagent？
- [ ] 若使用 `worktree.sparsePaths`，是否包含 source / tests / fixtures / ticket？
- [ ] Agent prompt 包含 `Ticket: {id}` + **commit 紀律提示（回報前 commit 產品碼進 worktree 分支）**？
- [ ] 若 prompt 提及 `.claude/` 路徑 Edit/Write，cwd 為**主 repo**（非 worktree）？（ARCH-015）

### 合併時
- [ ] `pwd && git branch --show-current` 確認在 main？
- [ ] `git worktree list` 檢查 worktree 產出物？
- [ ] `git branch | grep feat/` 檢查 feature 分支產出物？
- [ ] 若 branch 落後 main 很多，先按 stale worktree 流程評估，不直接 merge？
- [ ] 合併到 main 後測試通過？

### 清理後
- [ ] **Guard A：每個 `where.files` 已用 `git show main:<file>` / `git ls-tree -r main` 固定值驗證確在 main？**
- [ ] **Guard C：目標 worktree `git -C <path> status --porcelain` 已確認為空（clean）？**
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
- .claude/rules/core/tool-output-trust-rules.md - 規則 3：關鍵事實用固定值驗證（Guard A/B 信任層依據）
- .claude/skills/worktree/hooks/worktree-remove-deliverable-check-hook.py - Guard A / Guard C 強制層
- .claude/skills/worktree/hooks/worktree-pre-dispatch-branch-drift-hook.py - Guard B 強制層
- .claude/skills/ticket/hooks/agent-dispatch-validation-hook.py - 「唯讀派發豁免 worktree 強制」判準強制層（`_is_dispatch_mode_readonly_prompt`）
- .claude/skills/worktree/hooks/worktree-commit-before-dispatch-hook.py - 「唯讀派發豁免 worktree 強制」節提及，isolation != "worktree" 自然跳過
- .claude/references/agent-dispatch-template.md - 唯讀派發 prompt 骨架速查、worktree 環境前置欄位

---

**Last Updated**: 2026-08-04
**Version**: 2.7.0 - 修正 worktree-remove-deliverable-check-hook 的 BLOCK_MESSAGE_DIRTY 內部代號「Guard B」與本文件既有 Guard B（worktree-pre-dispatch-branch-drift-hook，派發前分支漂移）撞號：改名 Guard C 並於階段 3 新增獨立章節、同步觸發點表與清理後檢查清單；merge-reminder-hook 的 dirty 分支清理建議改為 commit 後 merge 再 remove 的導向，不再指向會被 Guard C 阻擋的 `remove --force`（0.2.1-W3-285，承接 0.2.1-W3-282 同型問題殘留）
**Version**: 2.6.0 - 新增「唯讀派發豁免 worktree 強制（0.2.1-W3-269，框架 issue 36）」節：TDD Phase 3a 等唯讀規劃/分析派發可用 prompt 首行 `Dispatch-Mode: readonly` 豁免 worktree 強制，含三條件 AND 判準、適用判準、反例表、與 review mode 的 OR 關係；「適用範圍與強制規則」表補豁免指引；派發 prompt 骨架速查另見 `agent-dispatch-template.md`（0.2.1-W3-270，接續 0.2.1-W3-269 落地）
**Version**: 2.5.0 - 新增「多階段串接派發（Feat 分支累積器）」節：跨 agent TDD phase 接力（RED→GREEN 跨多個 worktree agent）時保 main 全程恆綠的機制，含 checkout-paths 取代 merge 的理由與 Guard A 銜接說明；階段 2「提取方式選擇」表補第四列 `git checkout <ref> -- <paths>`（0.2.1-W3-095，落地自 memory multi-phase-tdd-branch-flow.md）

**Version**: 2.4.0 - 落地 1.2.0-W1-028 兩守護：Guard A（階段 3 remove 前固定值驗證交付物在 main + remove-deliverable-check-hook 強制層 + 實作 agent commit 紀律）防未提交碼遺失；Guard B（階段 1 派發前主 repo 分支漂移檢查 + pre-dispatch-branch-drift-hook 強制層）防 cwd 污染致 merge 落錯處；觸發點表與派發前/清理後檢查清單同步補列

**Version**: 2.3.0 - 「目前建議」章節升級為策略 C 條件式採用（W3-034.4 並行受控實驗 3/3 success 落地）；新增 Action 表分 5 場景對應 bgIsolation 設定 + 未驗證情境表 + 不採策略 B 理由

**Version**: 2.2.0 - 補充 CC worktree 入口、sparsePaths、Hook events 與 stale cleanup
