---
id: PC-163
title: PM-worktree ticket md 偏離 — PM 在 main repo 跑 ticket CLI 與 agent 在 worktree 作業導致雙邊不同步
category: process-compliance
severity: medium
status: resolved
created: 2026-05-27
related:
- ARCH-015
- PC-076
- PC-078
---

# PC-163: PM-worktree ticket md 偏離

## 狀態附記（2026-09-03，已解決）：根本原因已由 get_ticket_state_root() 消除

**現況**：本 PC 的核心前提——「ticket CLI 依 cwd 的 git working tree 決定操作對象」（見下方「Why」）——已於 2026-09-02 隨 `get_ticket_state_root()`（`.claude/skills/ticket/ticket_system/lib/paths.py`）新增而不再成立。該函式讓 `claim` / `append-log` / `complete` / `set-acceptance` 等 ticket 狀態操作（經 `get_tickets_dir()` -> `get_ticket_path()` 呼叫鏈，覆蓋 `lifecycle.py` 全部生命週期命令）在偵測到 linked worktree 場景時一律回推**主倉庫**根目錄，與呼叫端 cwd 無關；`complete()` 收尾的 ticket md auto-commit 同樣錨定主倉庫（`lifecycle.py` 對應段落）。PM（main repo cwd）與 agent（worktree cwd）執行 ticket CLI 時，兩者寫入的是同一份主倉庫檔案，不再各自持有一份會分裂的 working tree 副本。

**為何在建立當下（2026-05-27）成立**：當時 ticket CLI 的路徑解析全域委派 `get_project_root()`（純 cwd-based git working tree 解析），ticket 狀態操作與程式碼提交共用同一套解析邏輯，未區分兩者。PM 與 agent 若處於不同 cwd（main repo vs worktree），ticket CLI 會分別作用於各自 working tree 內的 ticket md 副本，因而產生本 PC 下方「觸發案例」記載的分裂與人工 reconcile 需求——此為 W1-096 案例的真實情境，非誤判。

**對下方內容的影響**：

| 段落 | 現況 |
|------|------|
| 「Why」「Consequence」「Action」（開頭三段） | 前提已不成立，僅作歷史記載保留 |
| Approach A（PM cd 到 worktree） | 失效——寫入位置已與 cwd 無關，cd 與否不再影響結果 |
| Approach B（派發前 commit 進 worktree base） | 失效——同上，該補救對象（cwd 決定寫入位置）已不存在 |
| Approach C（ticket CLI 增加 worktree 偵測，長期解） | 已達成，但達成方式非原設想的「偵測並警告 PM」，而是更徹底的「讓寫入位置與 cwd 無關」，故不需額外偵測/警告邏輯 |
| 防護措施三層 | 全數失效，見上 |
| 邊界與例外 | 不受影響（該表描述「本 PC 何時不適用」，與根因是否過期無關） |

**Action**：後續讀者遇本 PC 時，不再依循 Approach A/B/C 的 mitigation 建議；改讀 `get_ticket_state_root()` docstring（`.claude/skills/ticket/ticket_system/lib/paths.py`）與 `.claude/skills/worktree/SKILL.md` / `.claude/skills/ticket/SKILL.md`（2026-09 已補入現行設計說明：程式碼提交走 worktree 分支、ticket 狀態統一寫入主倉庫）理解現行架構。**邊界**：本附記僅涵蓋 ticket 狀態讀寫；`ticket track commit`（程式碼提交）仍維持 worktree 感知（`resolve_project_cwd()`），不受影響，此部分本非本 PC 原始範圍。

---

當 PM 在 main repo cwd 執行 `ticket track claim` / `ticket track append-log` 等命令，同時 agent 在 worktree cwd 作業並修改 ticket md 時，兩邊的 working tree 對同一 ticket md 持有不同的 uncommitted 變更，需 PM 在 agent 完成後手動 reconcile（合併 frontmatter 更新 + body 填充 + 派發期 ephemeral context 的去留決策），merge 才能順利進行。

**Why**：ticket CLI 依 cwd 的 git working tree 決定操作對象，但 PM 與 agent 的 cwd 預設分屬不同 git 樹（main repo vs worktree branch），兩邊變更不會自動同步。

**Consequence**：未在 agent 完成後 reconcile 即 merge 會 git conflict 或一邊 silent 覆寫另一邊；若 PM 未察覺，最壞情況是 agent 完成的 body 填充被 PM 的 frontmatter 更新覆寫，導致 ticket md 缺失 Test Results / Solution 等必填章節。

**Action**：依下方「正確做法」分流，預設採 Approach A（PM cd 到 worktree 後再做 ticket CLI 操作）。

## 觸發案例

### W1-096 案例（2026-05-27）

**時序**：

1. PM `worktree create 0.19.0-W1-096` 建立 worktree（path: `book_overview_v1-0.19.0-W1-096`，branch: `feat/0.19.0-W1-096`），此時 worktree 的 ticket md 為原始 `status: pending` 狀態
2. PM 在 **main repo cwd** 執行 `ticket track claim 0.19.0-W1-096` → main repo 的 ticket md 被更新（`status: in_progress` + `started_at` + `assigned: true`），但變更未 commit，且 worktree 的 ticket md 完全沒看到此更新
3. PM 在 **main repo cwd** 執行 `ticket track append-log` 兩次（Problem Analysis 寫 WRAP 三問、Solution 寫派發執行指引）→ 兩個 PM 派發期 ephemeral context 寫入 main repo's working tree
4. PM 派發 thyme-extension-engineer 到背景，**agent 在 worktree cwd 作業**
5. Agent 修復 3 檔程式碼，commit 到 `feat/0.19.0-W1-096`，再修改 **worktree 的** ticket md 填寫 Problem Analysis / Solution / Test Results / Completion Info（基於原始 pending 狀態，沒看到 PM 的 WRAP / dispatch 指引）
6. Agent 因 API 529 中斷，未 commit ticket md，未 complete
7. PM 接手發現：
   - main repo 的 ticket md：`status: in_progress` + WRAP + dispatch 指引（uncommitted）
   - worktree 的 ticket md：`status: pending` + agent 的 body 深度填充（uncommitted）
   - 同一檔的兩個 working tree 持有**互不重疊但 frontmatter 衝突**的變更

**Reconcile 過程**：

1. 編輯 worktree 的 ticket md 同步 frontmatter（`status: in_progress` + `started_at` + `assigned: true`）
2. 決定 PM 的 WRAP / dispatch 指引去留（本案例選擇捨棄，因屬派發期 ephemeral context；agent 的 body 為主要產出）
3. Commit worktree 的 ticket md
4. `check-acceptance --all` + `complete`（從 worktree cwd 執行）
5. 在 main repo `git checkout --` 捨棄 main repo 的 uncommitted 變更
6. `git merge feat/0.19.0-W1-096` fast-forward
7. `git worktree remove` + `git branch -d` 清理

額外成本：6 個額外 Bash 操作 + 認知負擔（決定 ephemeral context 去留 + 確認沒誤覆寫 agent 產出）。

## 根本原因

### 表層原因

| 原因 | 說明 |
|------|------|
| ticket CLI 依 cwd | `ticket track *` 命令依 `git rev-parse --show-toplevel` 決定 working tree，不會偵測「此 ticket 是否有 active worktree」 |
| PM 預設在 main repo cwd | PM 派發後通常停留 main repo 繼續做其他工作（worklog / 後續 ticket prep），不會主動 cd 到 worktree |
| Agent 預設在 worktree cwd | Worktree skill 與 dispatch policy 鼓勵 agent 在 worktree 作業以隔離分支 |

### 深層原因

| 維度 | 說明 |
|------|------|
| Worktree skill 與 ticket CLI 未整合 | `worktree create` 不會自動把後續 ticket CLI 重導向 worktree，兩個 skill 各自獨立 |
| 派發指引未強制 PM cd | `.claude/references/agent-dispatch-template.md` 與 dispatch 流程沒提醒 PM「派發後若要再對 ticket md 操作，必須 cd 到 worktree」 |
| Frontmatter 與 body 變更難自動 merge | ticket md 是純文字，frontmatter（YAML）與 body（Markdown）跨變更不能 git auto-merge 區段 |

**橋接**：表層原因可由 Approach A（PM cd 到 worktree）規避，零工程成本；深層原因（CLI 未偵測 worktree、文件純文字易衝突）需 Approach C 系統性改造 ticket CLI 才能根除。Approach B 為過渡補救方案。

## 正確做法

### Approach A：PM 派發後 cd 到 worktree（推薦）（歷史，已失效，見文首「狀態附記」）

| 時機 | 動作 |
|------|------|
| 派發 agent 前 | 在 **main repo cwd** 做 worktree create / claim / append-log（避免 worktree 才剛建立尚未 claim 即衝突） |
| 派發 agent 後 | **立即** cd 到 worktree cwd，後續所有 ticket CLI 操作從 worktree 執行 |
| Agent 完成後 | 從 worktree cwd 執行 check-acceptance + complete，避免 main repo 的 working tree 留下殘留 |

**Why**：worktree 是 ticket 的權威工作場；agent 已產出 commit 在 feat 分支，PM 在同一 working tree 操作才能避免分叉。

**Consequence**：減少 reconcile 步驟到 0（worktree 內所有 ticket md 變更都已在同一 branch，merge 即可）。

**Action**：dispatch SOP 加註「派發後立即 cd worktree」或建 PM cwd-switch helper。

### Approach B：派發前完成所有 PM 變更並 commit 進 worktree base（補救型）（歷史，已失效，見文首「狀態附記」）

| 動作 | 何時 |
|------|------|
| PM 在 main repo 跑 claim/append-log | 派發前 |
| PM commit 此變更進 main | 派發前 |
| 派發後 worktree 已基於 main 含此變更（fresh worktree）或執行 `git pull origin main` rebase | Worktree 已建立才補變更時 |

**Why**：讓 worktree 的 ticket md 起點就含 PM 的 frontmatter 更新與 ephemeral context，agent 在其上 append 不會偏離。

**Consequence**：PM 流程多一個 commit 步驟（claim/append-log 的小變更需 commit 進 main 或 feat），破壞 ticket md frontmatter 更新通常與 complete 一起 commit 的慣例。

**Action**：僅在 Approach A 不可行（如 worktree 已存在且 PM 已寫了 main repo 的變更）時採用。

### Approach C：ticket CLI 增加 worktree 偵測（長期解）（已達成，達成方式見文首「狀態附記」）

| 動作 | 何時 |
|------|------|
| ticket CLI claim/append-log 偵測「此 ticket 有 active worktree」並提示 PM cd | 命令啟動時 |
| 偵測到 PM 在 main repo cwd 操作有 worktree 的 ticket，警告或自動 -C 切換到 worktree | 命令啟動時 |

**Why**：自動防護優於人工自律。

**Consequence**：需修改 ticket CLI 並加 worktree 偵測邏輯，工作量較大。

**Action**：列為 follow-up ANA ticket，評估成本效益後決定是否實作。

## 防護措施（歷史，三層全數失效，見文首「狀態附記」）

### 第一層：派發 SOP 提醒（短期）

**適用條件**：尚未實作任何 hook 偵測前的立即生效防護。零工程成本，但依賴 PM 自律，覆蓋率視 PM 警覺性而定。

PM 派發 agent 後立即 cd 到 worktree，後續 ticket CLI 操作均在 worktree cwd 執行；只有 worktree 不存在時才在 main repo 操作。

### 第二層：建 ticket-cwd-check hook（中期）

**適用條件**：第一層覆蓋率不足（PM 自律失效案例累積 ≥ 3 次）時引入。中等工程成本，但事後警告而非事前阻擋。

PostToolUse:Bash 偵測「`ticket track (claim|append-log|complete)` 在 main repo cwd 執行 + 該 ticket 有 active worktree」時警告。Hook 事件選 PostToolUse 而非 PreToolUse，因偵測邏輯需先讀 ticket frontmatter 與 git worktree list，預先阻擋會打斷 PM 工作流；事後警告便於 PM 立即補做 reconcile。

### 第三層：ticket CLI 整合 worktree 偵測（長期，Approach C）

**適用條件**：第二層警告轉化為阻擋失效（PM 忽略警告繼續操作的案例累積）時引入。最高工程成本，需修改 ticket CLI 核心邏輯，建議由獨立 ANA ticket 評估設計與工作量。

如上節 Approach C 所述，需獨立 ANA ticket 評估。

## 邊界與例外

| 情境 | 適用 |
|------|------|
| 短任務未開 worktree | 不適用（直接在 main repo 操作） |
| DOC ticket 純文件更新 | 可不開 worktree（直接 main repo commit），不觸發本 PC |
| 多 agent 並行（W17-203.1 parallel-check） | 每個 ticket 都有獨立 worktree，本 PC 各自獨立適用 |
| Agent 完成 + complete 全程順利 | 不觸發本 PC（agent 自己處理 ticket md commit） |

**邊界判定原則**：本 PC 觸發前提是「PM 與 agent 對同一 ticket md 並行作業於不同 working tree」。任一條件不成立即不適用——單一 cwd 操作（無 worktree 或全程同 cwd）、agent 自主完成全部 ticket md 變更（PM 無 append-log）、ticket md 變更全部在 agent commit 前 reconcile 完畢，均屬安全情境。多 agent 並行情境下，每對「PM cwd × agent worktree」獨立判定。

## 相關

| 參考 | 關聯 |
|------|------|
| ARCH-015 | `.claude/` 修改的派發位置決策（dispatch-position vs worktree base） |
| PC-076 | Session-start 全量清點（跨 session 殘留變更追蹤） |
| PC-078 | 並行 session ticket 誤判（多 cwd 同時操作 ticket 系統的相關場景） |
| memory `worktree-agent-issues` | 既有 4 個 worktree-agent 議題（本 PC 為第 5 個維度補充） |

---

**Last Updated**: 2026-09-03
**Version**: 1.2.0 — status 改為 resolved，文首新增「狀態附記」：根本原因（ticket CLI 依 cwd 決定操作對象）已由 get_ticket_state_root() 統一回推主倉庫消除，Approach A/B 失效、Approach C 已達成（達成方式與原設想不同）、防護措施三層失效；各對應段落標題補歷史標記，內容保留不刪
**Version**: 1.1.0 — Layer 2 by basil-writing-critic 審查補強：表格後橋接說明（根本原因 / 邊界與例外）+ 防護措施三層各補適用條件
**Version**: 1.0.0 — 初始建立，源 W1-096 reconcile 案例
