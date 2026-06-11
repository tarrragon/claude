# 並行派發指南

> **核心哲學**：並行化是主線程的首要考量，不是可選優化。
> 決策第一步不是「這是什麼類型的任務」，而是「這個工作可以讓多少人去做？」

---

## 觸發條件（必須同時滿足）

| 條件 | 說明 |
|------|------|
| 多任務 | 2+ 個待處理任務（同 Wave） |
| 無依賴 | 任務間無先後順序 |
| 無重疊 | 修改檔案無交集 |
| 同階段 | 屬於同一 TDD 階段 |
| 複雜度適合 | 所有任務的認知負擔指數 <= 10（見下方複雜度評估） |

### 複雜度評估（並行適合性）

> **核心原則**：無依賴只是並行的必要條件，不是充分條件。高複雜度任務即使無依賴，也可能不適合並行。

| 維度 | 適合並行 | 不適合並行（降級為序列） |
|------|---------|----------------------|
| 功能職責（SRP） | 各任務聚焦單一獨立功能面 | 任務間有功能職責重疊或依賴 |
| 認知負擔 | 兩個任務的指數均 <= 10 | 任一任務指數 > 10 |
| 驗證需求 | 各自獨立驗證即可 | 需要 PM 專注逐步確認 |
| 風險等級 | P2 以下的常規修改 | P0/P1 的高風險修改 |
| 任務類型 | 同質且機械性（如批量修正） | 涉及設計決策或架構變更 |

**降級判斷**：任一維度判定為「不適合並行」→ 整組降級為序列派發。

**向用戶呈現並行選項時的要求**：AskUserQuestion 的並行選項描述中，應包含各任務的複雜度摘要（如認知負擔指數、修改檔案數），讓用戶有足夠資訊做決策。

---

## 並行安全檢查（強制）

```markdown
- [ ] 檔案所有權已驗證（見 task-splitting.md 策略 6）
- [ ] 檔案無重疊：各任務修改的檔案集合無交集
- [ ] 測試無衝突：各任務的測試可獨立執行
- [ ] 依賴無循環：任務之間無先後依賴關係
- [ ] 資源無競爭：不會同時存取相同外部資源
- [ ] Wave 無跨越：所有任務屬於同一個 Wave
- [ ] 目標檔案路徑在代理人可編輯範圍（見下方路徑權限）
- [ ] 實作代理人使用 `isolation: "worktree"` 派發
- [ ] **派發 prompt 已引用職責邊界聲明骨架**（見 `.claude/references/agent-dispatch-template.md`）
- [ ] **派發 prompt 已明示精準 git staging**（並行 commit 場景，禁用 `git add .` / `git add -A`；見下方 PC-092 防護）
```

### Dispatch-Plan 先行（多任務 / group / spawned 場景）

> **來源**：W17-029 / W17-035 — Linux 類比後的結論是保留單一 ticket / agent / exit status 的生命週期，用 Makefile-like dispatch-plan 描述 orchestration，不新增 batch dispatch CLI。

以下任一情境成立時，PM 必須先在 ticket Problem Analysis 或 Solution 寫 dispatch-plan，再派發 agent：

| 情境 | 要求 |
|------|------|
| 2+ tickets 同輪派發 | 先列 dispatch-plan，確認 files/deps/run mode |
| group ticket coordinator | 先列 children / spawned 的 ticket-agent-files 對照 |
| spawned follow-up | 先列 source ticket、context source、commit policy |
| 並行與序列混合 | 將 `run mode` 分成 `parallel` / `serial` / `blocked` |

dispatch-plan 是 orchestration description，不是 execution automation：

| 項目 | dispatch-plan | batch dispatch CLI |
|------|---------------|--------------------|
| 角色 | 描述多個 job 的依賴、ownership、context source、run mode | 自動批量派發 agent |
| 生命週期 | 保留每張 ticket 的獨立 prompt、commit、Exit Status | 容易弱化 ticket / agent 邊界 |
| 首輪落地 | 強制使用 | 禁止新增 |
| 升級條件 | W17-030 T3 顯示 PM 仍拼單避免派發 | 另建 INV/IMP 評估 |

dispatch-plan 欄位以 `.claude/references/agent-dispatch-template.md` 為準：`ticket` / `agent` / `files` / `deps` / `context source` / `commit policy` / `run mode`。

### 派發 prompt 必含職責邊界聲明（強制）

> **來源**：Ticket 0.18.0-W5-009 / W5-044 — W5-001 session 實證，含職責邊界聲明的派發（pepper/thyme）無越界；缺聲明的派發（sage）出現越界寫測試。

所有派發 prompt（並行或單一）必須於開場引用 `.claude/references/agent-dispatch-template.md` 定義的骨架，包含：

1. `Ticket: {id}` 第一行
2. `## 職責邊界聲明`：列出允許 / 禁止的產出
3. `## 執行`：具體步驟
4. `## 禁止`：跨 Ticket 衝突範圍

並行派發時尤其重要：每個代理人的 prompt 必須明示「禁止修改其他並行 Ticket 的 where.files」以防範圍交叉。

> 完整骨架與填寫要點：`.claude/references/agent-dispatch-template.md`

### 派發 prompt 必含精準 git staging（並行 commit 場景，強制）

> **來源**：PC-092 — 2026-04-18 W5-043 並行派發事件，四個 thyme-python-developer 代理人併發 `git add .`，導致 batch 3 的 6 個檔案被 batch 4 代理人一併 staged + commit，commit 訊息標 batch 4 但實際 diff 含 batch 3 + 4。

當並行派發的代理人各自執行 `git commit` 時，prompt 必須明示精準 staging：

| 要求 | 正確 | 錯誤 |
|------|------|------|
| staging 路徑 | 逐一列出 `where.files` 的精確路徑 | `git add .` / `git add -A` |
| 範圍邊界 | 僅 staging 本 Ticket 的 `where.files` | 任何廣域符號 |

**範例 prompt 片段**：

```
執行 commit 時使用：
    git add .claude/agents/sassafras.md .claude/agents/mint.md
    git commit -m "..."
禁止：git add . 或 git add -A（會併入其他並行代理人的修改）
```

**降級替代方案**（精準 staging 不可行時）：

| 方案 | 適用情境 | 代價 |
|------|---------|------|
| 序列派發 | 並行代理人少 / 時間充裕 | 吞吐量下降 |
| Worktree 隔離 | 長任務 / 獨立資源需求 | 配置與合併成本 |
| PM 統一 commit | 代理人不需 commit 操作 | PM 工作量增加 |

> 完整根因、觸發案例與方案比較：`.claude/error-patterns/process-compliance/PC-092-parallel-agents-git-index-race.md`

### 派發前路徑權限確認

> **來源**：PC-022 — Phase 3b 代理人無法編輯 `.claude/hooks/` 檔案，任務中斷需 PM 手動介入。

| 目標路徑 | 建議執行者 | 原因 |
|---------|-----------|------|
| `lib/`、`test/` | 代理人 | 標準開發路徑 |
| `.claude/skills/`、`.claude/lib/` | 代理人 | 一般可編輯 |
| `.claude/hooks/` | PM 直接或確認權限 | 權限受限路徑 |
| `.claude/rules/` | PM 直接 | PM 允許編輯範圍 |

**處理策略**：全部在可編輯範圍 → 正常派發；部分受限 → 拆分；全部受限 → PM 直接執行。

> 代理人收到派發後應直接嘗試 Edit/Write，被阻擋時上報 PM。可編輯路徑見 decision-tree.md「代理人可編輯路徑對照表」。

---

## 驗證類任務自動派發（強制，不詢問用戶）

> **核心原則**：驗證類任務有明確 SOP（執行指令 → 產出報告 → 寫回 Ticket），PM 直接建子 Ticket 背景派發，**不需要詢問用戶「要派代理人還是自己做」**。

### 識別特徵

Ticket 的 `what` / `how` 含以下任一特徵即屬於驗證類：

| 特徵 | 關鍵詞範例 |
|------|-----------|
| 執行指令並產出報告 | 「執行 X 並產出報告」「跑 Y 後整理結果」 |
| 驗證 AC 實況 | 「驗證 AC 是否達成」「實測 AC 通過率」 |
| 測試/掃描/建置/打包 | 「跑測試」「全量掃描」「建置產物」「打包驗證」 |
| 覆蓋率/通過率統計 | 「測試覆蓋率」「測試通過率」「lint 錯誤數」 |

### 預設行動

| 動作 | 說明 |
|------|------|
| 直接建子 Ticket | 子 Ticket 序號用 `{parent}.{n}` 命名（父子關係標記） |
| 寫 Context Bundle | 父 Ticket 的 Problem Analysis 寫入完整 Context Bundle |
| 背景派發代理人 | `run_in_background: true`，PM 不等結果 |
| PM 立即切換 | 轉去做其他 Ticket 的前置準備（Context Bundle、規格分析等） |
| 收到通知才驗收 | 代理人完成通知到達後再回來驗收 |

### 例外條件（可回頭詢問用戶）

驗證結果會**直接影響派發策略的根本決策**時，才回頭詢問用戶。例如：

| 例外情境 | 說明 |
|---------|------|
| 驗證結果決定 Ticket 是否繼續 | 如「這個 Ticket 還值不值得做」取決於驗證結果 |
| 驗證結果決定版本發布與否 | 如打包驗證失敗可能需要用戶決定是否重排版本 |
| 驗證結果影響其他 Wave 排序 | 根因不明的驗證結果可能需要用戶決策方向 |

**一般情境不適用例外**：AC 實況驗證、覆蓋率統計、lint 掃描等純資料收集型驗證，**不屬於例外**，必須直接派發。

### 與 AskUserQuestion 的關係

`askuserquestion-rules.md` 的通用觸發原則（行為驅動）在此**不觸發**，因為：

- 本規則預設動作是「直接派發」，PM 不向用戶呈現選擇
- 不存在「要不要派代理人？」的二元確認（該問題已由規則預先決定）
- 僅在上述「例外條件」成立時，才進入 AskUserQuestion 流程

> 詳細 SOP 和流程圖：.claude/references/background-dispatch-rules.md（驗證類任務自動派發章節）

---

## 決策流程

```
任務分派 → [強制] 派發前複雜度關卡（認知負擔 <= 10?）
              → 否（> 10）→ 先拆分子任務再重新評估
              → 是（<= 10）→ 是單一任務?
                               → 是 → 標準派發
                               → 否 → 任務間有依賴? → 是 → 依 Wave 序列派發
                                                     → 否 → 複雜度適合並行?
                                                            → 否 → 降級為序列
                                                            → 是 → 並行安全檢查
                                                                   → 通過 → 並行派發
                                                                   → 失敗 → 降級為序列
```

> **派發前複雜度關卡**：所有派發（單一或並行）的前置條件。詳見 decision-tree.md 第負一層。

**複雜度適合並行？** 判斷依據：
1. 所有任務認知負擔指數 <= 10
2. 無 P0/P1 高風險任務
3. 無需 PM 專注逐步確認的任務
4. 無涉及設計決策或架構變更的任務

---

## Worktree 隔離（強制）

所有會修改檔案或執行 git 操作的代理人，必須使用 `Agent(isolation: "worktree")` 派發。

> **worktree base 可能過舊**：cc runtime 以派發瞬間 main HEAD 為 worktree base，不後續同步。**Why**：base 建立後主 repo 新增 commit 不反映到 worktree。**Consequence**：agent 以過時檔案為基礎工作，產出與 main 新增 commit 不相容，需手動整合。**Action**：每次 worktree 派發 prompt 必須在開頭加 `git merge main` 指引，確保 agent 對齊最新 main。完整說明與 prompt 範本見 `.claude/references/agent-dispatch-template.md`「worktree 派發 base 同步指引（W1-035）」。

| 代理人類型 | 需要 worktree |
|-----------|--------------|
| 實作代理人（parsley, fennel, thyme-python） | 強制 |
| 重構代理人（cinnamon） | 強制 |
| 測試/格式代理人（pepper, mint） | 強制 |
| 分析/審核代理人（linux, bay, saffron） | 不需要 |
| 探索代理人（Explore） | 不需要 |

> **Source of truth**：此表格為 worktree 隔離需求的唯一定義來源。Hook `agent-dispatch-validation-hook.py` 的 `IMPLEMENTATION_AGENTS` 清單必須與此表格同步。

### 並行場景路徑區分（`.claude/` vs `src/`）

> **兩個正交維度**：代理人類型（上表）決定是否需要 worktree 的一般規則；target 路徑（本小節）決定 worktree 可否使用的實體限制。**target 路徑限制優先於代理人類型**。

#### 規則表

| Target 路徑 | 派發策略 | 並行 commit 安全模型 |
|-----------|---------|-------------------|
| `src/` / `test/` / `lib/` / `docs/` | worktree 隔離（預設） | 各 worktree 獨立 commit，PM 合併 |
| `.claude/` | 主 repo cwd（CC runtime 限制） | 精準 staging + Hook 偵測（見「派發 prompt 必含精準 git staging」章節） |

#### `src/` 預設 worktree 的業界證據（2026）

AI coding agent 並行工作預設 worktree 隔離已成業界共識：

| 來源 | 立場 |
|------|------|
| Anthropic Claude Code 官方文件 | 推薦 worktree for multi-session workflows |
| Cursor | "Parallel Agents" 功能建立在 worktree 基礎上 |
| Augment Code Intent | 每個 Space 專屬 worktree + branch |
| Upsun 開發者文件（2026 專文） | AI coding agents worktree 用法專題 |
| Worktrunk CLI（2026 初發布） | 專為並行 AI agent 設計的 worktree 管理工具 |
| JetBrains 2026.1 / VS Code 2025.7 | first-class worktree IDE 支援 |

worktree 解決並行 AI agent 的核心問題：shared git index 競爭（見 PC-092）。獨立 worktree 提供獨立 index，並行 commit 互不干擾。

#### `.claude/` 例外（CC runtime 硬編碼保護）

Claude Code runtime 對 subagent 操作 worktree 內 `.claude/` 有硬編碼保護（見 ARCH-015）。實測 v2.1.114：

- **Target 在主 repo 樹內 `.claude/`**：subagent Write/Edit 可成功（無論 cwd 是主 repo 或 worktree）
- **Target 在 worktree 樹內 `.claude/`**：subagent Write/Edit 被拒
- **分界線**：target 路徑是否在主 repo 樹內

因此 `.claude/` 不能用 worktree 隔離並行修改，改用精準 staging + Hook 偵測（PC-092 方案 A）。

#### `.claude/` 修改類並行數限 ≤ 2（W17-177 ANA 落地）

`.claude/` 修改類 ticket（含 hooks、pm-rules、error-patterns、agents、rules、methodologies、skills 等）並行派發數**限 ≤ 2**，禁止 3+ 並行。

**Why**：W17-177 saffron ANA 統計 — 7/7 歷史 deny 案例（W17-097.1-.4 + W17-174.2.1/.3/.4）皆發生於並行派發場景；18/18 非並行 Edit 全部 success。並行派發 + `.claude/` Edit 為新候選假設（中等證據）。

**Consequence**：3+ 並行派發 `.claude/` 修改類 ticket 預期觸發 runtime deny（無 hook stderr，無 hook-logs；診斷成本高）；deny 後需 PM 接手手動 Edit，併行收益被抹除。

**Action**：

| 並行數 | 處理方式 |
|-------|---------|
| 1 | 序列派發，無限制 |
| 2 | 允許並行；確認檔案邊界互斥 |
| 3+ | 拆 batch（每批 ≤ 2）或改序列；緊急情境豁免需在 dispatch-plan 註明並接受 deny 風險 |

**重啟條件**：若 W17-177.1 落地後仍出現並行 ≤ 2 場景的 `.claude/` Edit deny，需執行 W17-177 NeedsContext 的對照組實驗區辨「並行假設」vs 其他變因（PC-115 trigger 計數歸零後重新累積）。

#### 實務落地對照

| 場景 | 派發位置 | 並行 commit 策略 |
|------|---------|----------------|
| 單一代理人改 `src/` | worktree | 代理人自 commit |
| 多代理人並行改 `src/` 不同檔案 | 各自 worktree | 各自 commit，PM 合併 |
| 單一代理人改 `.claude/` | 主 repo cwd | 代理人自 commit |
| 多代理人並行改 `.claude/` 不同檔案 | 主 repo cwd | 精準 staging（禁 `git add .` / `git add -A`），序列化 commit 或 PM 統一 commit |

> 業界證據連結：
> - Augment Code — https://www.augmentcode.com/guides/git-worktrees-parallel-ai-agent-execution
> - Upsun — https://developer.upsun.com/posts/2026/git-worktrees-for-parallel-ai-coding-agents
> - Worktrunk — https://worktrunk.dev/

### bgIsolation: none 並行安全建議（W3-034.4 驗證落地）

Claude Code v2.1.143+ 提供 `worktree.bgIsolation: "none"` 設定，讓 subagent 直接在主 repo working copy 操作（不建 worktree）。W3-034.4 並行受控實驗驗證後，本設定已從「並行情境未驗證」升級為「並行 3 已驗證 success（W3-034.4 3/3）」，但仍受 git index 競爭與並行 5+ 未測限制。 <!-- PC-093-exempt: history:0.19.0-W3-034.4 為實驗驗證歷史錨點 -->

**風險矩陣**：

| 風險類型 | bgIsolation: worktree（預設） | bgIsolation: none |
|---------|-----------------------------|------------------|
| Git index 競爭 | 各自隔離，安全 | **共享 index**，PC-092 風險必然化（需精準 staging 或 PM 統一 commit） |
| `.claude/` 並行 Edit | 限並行 ≤ 2（PC-137 worktree 模式規則） | 並行 3 已驗證 success（W3-034.4）；5+ 未驗證 |
| 殭屍 worktree 累積 | 有，已有 GC hook | 無此問題 |
| 合併成本 | 每次需合併 | 無 |

**目前建議（v0.19.x）**：採策略 C 條件式採用（與 worktree-operations.md 一致）。

**Why**：W3-034.4 並行受控實驗驗證 bgIsolation: none + 並行 3 subagent + `.claude/` Edit 達 3/3 success（PC-137 v1.1.0 落地）。PC-137 並行 ≤ 2 規則僅在 worktree 模式下有效；bgIsolation: none 下未受並行數限制（已驗證至 3）。

**Consequence**：誤外推 worktree 模式並行限制到 bgIsolation: none 會放棄已驗證的並行解鎖；反之誤外推 none 模式解鎖到 worktree 模式則違反 PC-137 規則。模式判別錯誤直接決定派發成敗。

**Action**：

| 場景 | bgIsolation 設定 | 並行限制 |
|------|------------------|---------|
| 單一 subagent + `.claude/` 修改 | none 可選 per-dispatch override | 無並行（W3-034.1 驗證 success） |
| 並行 2 subagent + `.claude/` 修改 | worktree（預設）或 none 皆可 | 允許並行（PC-137 worktree 模式上限 = 2；none 模式同等可用） |
| 並行 3+ subagent + `.claude/` 修改 | **none 必用**（worktree 模式禁止 3+） | 允許並行 Edit；commit 由 PM 統一執行 |
| 全面切換 bgIsolation: none | **暫不採用** | 並行 commit 與 5+ 並行未驗證；對 src/ 失去 worktree 隔離保護。當前正向路徑：採策略 C 條件式採用（per-dispatch override），待出現 5+ 並行需求或 PC-092 共享 index 驗證需求時，建 ANA ticket 對照實驗 |

**未驗證情境（仍受限）**：

| 情境 | 風險 |
|------|------|
| bgIsolation: none + 並行 + 子代理人各自 git add/commit | PC-092 共享 index 競爭未測 |
| bgIsolation: none + 並行 5+ subagent | 更高並行度未測，採並行 ≤ 3 為觀察上限 |

> 上表屬規則檔擴充性說明（依 `.claude/rules/core/decision-trigger-binding.md` 規則 1.5，rules/方法論可述未來考量，不需綁 ticket trigger）。實際出現 5+ 並行需求或需驗證 PC-092 共享 index 行為時，建 ANA ticket 執行對照實驗。

**Git index 競爭警告（bgIsolation: none 下強化）**：

bgIsolation: none 下所有 subagent 共享主 repo git index。並行派發若任一 subagent 執行 `git add` 或 `git commit`，會與其他 subagent 競爭 index.lock，可能造成：

- Index corruption（多個 process 同時寫 index）
- Commit 邊界混亂（git add 範圍超出該 subagent 工作範圍）
- Index.lock 殘留（process 異常結束未釋放）

對應防護：派發 prompt 必含精準 git staging（禁 `git add .` / `git add -A`），或由 PM 統一 commit，見本文件「派發 prompt 必含精準 git staging」章節。

**對照 PC-137 v1.1.0 規則**：

| 並行數 | bgIsolation: worktree | bgIsolation: none |
|-------|----------------------|------------------|
| 1 | 序列派發，無限制 | 序列派發，無限制 |
| 2 | 允許並行（檔案邊界互斥） | 允許並行（檔案邊界互斥） |
| 3+ | 拆 batch（每批 ≤ 2）或改序列 | 允許並行 Edit；commit 由 PM 統一執行 |

PC-137 並行 ≤ 2 規則為 worktree 模式下的觀察結論（W17-097.1-.4 + W17-174.2.1/.3/.4 7/7 deny 證據）；bgIsolation: none 模式並行行為由 W3-034.4 受控實驗驗證為不同模式，並行 ≤ 3 已 success。模式判別應依當前 `.claude/settings.json` 的 `worktree.bgIsolation` 設定值 + per-dispatch override 為準（per-dispatch override 機制由 CC runtime 提供，當前 v0.19.x 採全域 settings + 特定情境派發近似實現）。

**參考**：

- worktree-operations.md「bgIsolation 策略選擇」子節（策略對照表與決策樹）
- PC-092（並行 commit 邊界混亂）
- PC-137 v1.1.0（並行 ≤ 2 規則 + bgIsolation: none 例外章節）

---

## 嵌套派發整合條款（嵌套協議 v2 與並行規則的互動）

> **協議權威來源**：嵌套派發協議 v2 定義於 `.claude/agents/AGENT_PRELOAD.md` 規則 9（D1 ticket 主通道三階段表、D2 descend/ascend 決策速查、D3 `can_descend()` 層級自覺）；完整設計依據見 ticket `1.0.0-W1-056.5` Solution「修訂版協議（v2）」。本章節**不複寫**該協議的條件表，只規範嵌套場景與本文件既有並行規則（`.claude/` 並行數限制、PC-092 精準 staging、worktree 隔離）的互動口徑。

### 嵌套層並行數計算口徑（`.claude/` 限制跨層累計）

**核心規則**：`.claude/` 修改類並行數限制（worktree 模式 ≤ 2，見上方「`.claude/` 修改類並行數限 ≤ 2」章節）以「同一時刻全系統並行操作 `.claude/` 的 agent 總數」計算，**跨層累計**，不依派發層級分開計數。

**Why**：該限制是 runtime deny 行為的觀察結論，runtime 不區分 dispatch 層級——嵌套層 agent 對主 repo `.claude/` 的 Edit 與 PM 直接派發的 agent 在 runtime 眼中等價（W1-056.4 已實證 hook 與 runtime 行為在嵌套層一致生效）。

**Consequence**：若各層獨立計數（L0 派 2 + 嵌套層再派 1 = 實際 3 並行），全系統並行數超過觀察安全上限，預期觸發 runtime deny；deny 無 hook stderr 可診斷，且需 PM 接手手動修復，併行收益被抹除。

**Action**：

| 場景 | 計數與處理 |
|------|-----------|
| 常態（D2 條件表生效） | 嵌套層 descend `.claude/` 寫入類子任務已被 D2 敏感操作條件禁止（AGENT_PRELOAD 規則 9）——常態下嵌套層不新增 `.claude/` 並行數，**計數收斂於 L0：PM 的 dispatch-plan 即全系統並行帳本** |
| 豁免情境（用戶明確授權嵌套層修改 `.claude/`） | descend 方必須在 child ticket 的 Problem Analysis 載明「佔用 1 個 `.claude/` 並行額度」，且 PM dispatch-plan 須預留該額度（總數仍受跨層累計上限約束） |

### 嵌套 descend 的 staging 責任歸屬（PC-092 延伸）

**核心規則**：每層 agent 只 staging 自身 ticket 的 `where.files`（PC-092 精準 staging 要求跨層不變）；descend 方（建 child ticket 的派發層）額外承擔邊界設計與政策傳遞責任。

**Why**：PC-092 的根因是並行 commit 時廣域 staging 把他人變更帶入 commit；嵌套加深後「他人」包含父層 agent 自身——父層與 child 若在同一 working copy（主 repo cwd 或 bgIsolation: none），child 執行 `git add .` 會把父層未 commit 的中間產物一併帶走。

**Consequence**：commit 邊界跨層混雜後，git blame 與 ticket 歸因失效——W1-056.4 實證嵌套層 git 操作可歸因到具體 agent，但歸因正確性以精準 staging 為前提；廣域 staging 會讓歸因結果指向錯誤的 ticket。

**Action**：

| 責任項 | 歸屬 | 說明 |
|--------|------|------|
| child `where.files` 與自身及其他 child 互斥 | descend 方 | 建 child ticket 時設計；並行 descend 另受 D-2 檔案無重疊條件約束 |
| 精準 staging 政策傳遞 | descend 方 | 寫入 child ticket 的 Problem Analysis（D1：staging 政策屬 context，進 ticket 不進 prompt） |
| 執行精準 staging + commit | child agent | 逐一列出自身 `where.files`，禁 `git add .` / `git add -A` |
| descend 前自身中間產物處置 | descend 方 | 先 commit 自身已完成部分再 descend，避免與 child 變更在 working copy 交錯 |

### worktree 模式與嵌套的相容性

**核心不變量**：無論父層與 child 的 isolation 設定為何，**跨層資訊傳遞一律經 ticket（D1），禁止依賴父層 working copy 的未 commit 中間檔案**。此不變量將 worktree 行為差異對協議的影響隔離在檔案層，資訊層不受影響。

| 情境 | 相容性 | 規則 |
|------|--------|------|
| 父層 worktree 內、child 需要父層中間產物 | 條件相容 | 父層必須先 commit 並 merge 回 main（worktree base 以派發瞬間 main HEAD 為準，父層 worktree 內未回 main 的變更對 child 不可見）；無法滿足時禁止 descend，改在本層完成 |
| child 修改 `.claude/` | 受 D2 敏感操作禁止 | `.claude/` 寫入屬敏感操作，嵌套層禁止 descend 此類子任務；ARCH-015 限制（target 必須在主 repo 樹內）跨層不變 |
| 父層主 repo cwd、child 修改 `src/` 等 worktree 適用路徑 | 相容 | 同單層規則：child 派發遵循「Worktree 隔離」章節（含 base 同步指引） |

**嵌套層 worktree 受控驗證**：嵌套層的 worktree 建立行為（base 取點、合併歸屬、GC 回收）尚無受控實驗資料；上表為依單層已知行為與 D1 不變量推導的保守規則。本段屬規則檔擴充性說明（依 `.claude/rules/core/decision-trigger-binding.md` 規則 1.5）：實際出現嵌套層 worktree descend 需求時，建 ANA ticket 執行對照實驗後再放寬。

---

## 並行派發後驗證（強制）

所有並行代理人回報完成後，**必須**執行 `git diff --stat` 驗證實際變更。

```markdown
- [ ] `git diff --stat` 已執行
- [ ] 代理人報告 vs 實際變更已比對
- [ ] 無缺失檔案（或已補派）
```

> 詳細驗證步驟和常見原因：.claude/references/parallel-dispatch-details.md

---

## 相關文件

- .claude/references/agent-dispatch-template.md - 職責邊界聲明骨架（派發 prompt 強制引用）
- .claude/references/parallel-dispatch-details.md - 詳細規則（5W1H 格式、分析任務並行、Agent Teams 場景表、進度追蹤）
- .claude/pm-rules/references/dispatch-routing-framework.md - 派發路由（數量原則、不適用並行、背景派發、跨 Wave 優先級）
- .claude/pm-rules/references/reporting-and-review-standards.md - 回報原則（最小回報、三人組、計數自檢）
- .claude/pm-rules/references/commit-and-phase-responsibility.md - Commit 責任邊界（Phase 分工、代理人自治規則）
- .claude/skills/bulk-evaluate/SKILL.md - 批量評估工具（1:1 派發）
- .claude/skills/parallel-evaluation/SKILL.md - 並行評估工具（多視角掃描）
- .claude/pm-rules/task-splitting.md - 任務拆分指南
- .claude/pm-rules/decision-tree.md - 主線程決策樹（第負一層）
- .claude/skills/agent-team/SKILL.md - Agent Teams 操作指南

---

**Last Updated**: 2026-06-11
**Version**: 4.8.0 - 新增「嵌套派發整合條款」章節：`.claude/` 並行數限制跨層累計口徑（常態收斂於 L0 dispatch-plan 帳本）+ 嵌套 descend staging 責任歸屬表（PC-092 延伸）+ worktree 模式與嵌套相容性（D1 不變量隔離檔案層差異）；協議權威來源引用 AGENT_PRELOAD 規則 9 與 1.0.0-W1-056.5 v2，不複寫條件表（1.0.0-W1-056.10）

**Version**: 4.7.0 - Worktree 隔離章節開頭新增 worktree base 可能過舊提示，引用 agent-dispatch-template.md「worktree 派發 base 同步指引（W1-035）」交叉引用（0.19.0-W1-053）

**Version**: 4.6.0 - bgIsolation: none 並行安全章節升級為策略 C 條件式採用（W3-034.4 並行受控實驗 3/3 success 落地）；風險矩陣與 Action 表分 4 場景；新增「對照 PC-137 v1.1.0」雙模式對照表

**Version**: 4.5.0 - 新增 dispatch-plan 先行規則，明確區分 orchestration description 與 batch dispatch CLI（W17-044）

**Version**: 4.4.0 - Worktree 隔離章節新增「並行場景路徑區分（.claude/ vs src/）」子章節，涵蓋規則表/業界證據（2026）/CC runtime 例外/實務落地對照（W5-047.3）

**Version**: 4.3.0 - 新增「派發 prompt 必含精準 git staging（並行 commit 場景）」強制要求，並行安全檢查 checklist 同步增項（PC-092 / W5-047.1）

**Version**: 4.2.0 - 新增「派發 prompt 必含職責邊界聲明」強制要求，引用 agent-dispatch-template.md（W5-044）

**Version**: 4.1.0 - 新增「驗證類任務自動派發」章節，明文化不詢問用戶規則
