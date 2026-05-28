# Agent Dispatch Template — 職責邊界聲明骨架

> **用途**：PM 派發代理人時，prompt 必含「職責邊界聲明」開場結構，讓代理人在執行前確認任務符合其定義的允許產出範圍，阻擋越界行為。
>
> **實證來源**：
> - W5-001 session（pepper / thyme-A / thyme-B）：派發 prompt 含職責邊界聲明，無越界案例
> - W5-001 sage 越界案例：派發 prompt 缺職責邊界聲明，sage 寫了禁止範圍的 .py 測試
>
> **設計依據**：quality-baseline 規則 6（失敗案例學習原則）— 從實證有效的派發模式固化為強制骨架。

---

## 骨架

派發 prompt 必含以下開場結構：

```
Ticket: {ticket_id}

## 職責邊界聲明

{agent-name} 的 agent 定義為「{agent-description 引文，來自 .claude/agents/{agent}.md frontmatter}」。

**允許的產出**:
- {列出本 ticket 範圍內允許的檔案/動作}

**禁止的產出**:
- {列出本 ticket 範圍外或代理人定義禁止的檔案/動作}

本 prompt 符合職責邊界，請繼續執行。

## 執行

{具體執行步驟、Ticket 指令、引用 Context Bundle}

## 禁止
- {與其他並行 Ticket 衝突的修改範圍}
- {本 Ticket 不應涉及的副作用}
```

---

## 三段式快速填空骨架（W17-048 方案 F）

> **用途**：PM 派發前最常用的中文對話式骨架。把 context 寫入 ticket 後，直接複製以下骨架填三個空格即可派發。prompt 控制在 **10-15 行**，穩過 Hook 30 行上限。

### 骨架（3 段）

```markdown
Ticket: {ticket_id}

## 任務

{一句話動作描述，≤ 40 字}

讀取 ticket：`ticket track full {ticket_id}`
依 Context Bundle 執行流程。遇阻立即停下回報，禁繞過 Hook。
```

### IMP 實戰範例（實作派發）

```markdown
Ticket: 0.18.0-W17-046.1

## 任務

擴充 TICKET_EXEMPT_AGENT_TYPES 白名單 + 補充 Hook 判別準則註解 + 新增測試。

讀取 ticket：`ticket track full 0.18.0-W17-046.1`
依 Problem Analysis 的 Context Bundle 規格實作 + commit + complete。
遇阻立即停下回報，禁繞過 Hook。
```

### ANA 實戰範例（分析派發）

```markdown
Ticket: 0.18.0-W17-043

## 任務

分析 scenario-17 AskUserQuestion 提醒在 append-log 誤觸發根因。

讀取 ticket：`ticket track full 0.18.0-W17-043`
依 acceptance 產出分析報告寫入 Solution，衍生修復 ticket 後 complete。
遇阻即停回報，禁繞過 Hook。
```

### DOC 實戰範例（文件派發）

```markdown
Ticket: 0.18.0-W17-048.3

## 任務

新增 agent-dispatch-template.md「短 prompt 三段式骨架」範例區。

讀取 ticket：`ticket track full 0.18.0-W17-048.3`
依 Context Bundle 設計文件結構，append Solution + commit + complete。
遇阻即停回報。
```

### 填空檢查清單

派發前確認：

- [ ] 第一行為 `Ticket: {id}`（Hook 強制驗證）
- [ ] 含「讀取 ticket」指引（W17-048.2 軟提示檢查）
- [ ] context 已在 ticket 的 Problem Analysis / Context Bundle（不塞 prompt）
- [ ] prompt 總行數 ≤ 15 行（遠低於 30 行硬上限）
- [ ] 動作描述一句話可理解（不堆疊多個動詞）

---

## 短 Prompt Snippets（PC-040 / PC-065）

以下 snippets 是派發時優先使用的短版骨架。完整 context 必須先寫入 Ticket Context Bundle；prompt 只保留 Ticket ID、邊界摘要與執行指令。每個 snippet 第一行固定為 `Ticket: {id}`。

### 單任務

```markdown
Ticket: {id}

{agent-name}: Read ticket md and execute the current acceptance criteria.
Allowed: {allowed files/actions from where.files}
Forbidden: {out-of-scope files/actions}
Use precise staging only: git add {exact files}
If context is insufficient, append NeedsContext and stop.
```

### 並行多任務

```markdown
Ticket: {id}

{agent-name}: Execute only this ticket from the dispatch-plan.
Allowed: {this ticket files/actions}
Forbidden: other parallel tickets' files and git add . / git add -A
Commit policy: {agent commit | PM commit | no commit}
If blocked, report Exit Status without touching sibling scope.
```

### Group Coordinator

```markdown
Ticket: {id}

{agent-name}: Update the group/coordinator ticket only.
Use the dispatch-plan table to track children (功能拆分 / ANA 落地，PC-091 路線)
and spawned tickets (執行中發現獨立技術債，PC-073 殘存範圍).
血緣 vs 衍生語意參考 .claude/skills/ticket/references/field-semantics.md
Do not implement child scope or batch-dispatch agents.
Record blockers, deps, and next runnable ticket IDs.
```

---

## Dispatch-Plan Template

對 2+ ticket、group ticket、spawned follow-up、或任何需要並行/序列混合派發的場景，PM 先在 ticket Problem Analysis 或 Solution 寫入 dispatch-plan。dispatch-plan 是 orchestration description，不是 batch dispatch CLI。

| ticket | agent | files | deps | context source | commit policy | run mode |
|--------|-------|-------|------|----------------|---------------|----------|
| `{id}` | `{agent}` | `{exact files}` | `{none | ids}` | `{Context Bundle | handoff | manual note}` | `{agent commit | PM commit | no commit}` | `{parallel | serial | blocked}` |

欄位要求：

| 欄位 | 內容要求 |
|------|---------|
| `ticket` | 單一 ticket ID；不得把多個 ticket 合成同一列 |
| `agent` | 指定 agent 或 PM 前台 |
| `files` | 精確檔案 ownership；未知時先補 Context Bundle，不派發 |
| `deps` | blockedBy / 前置 ticket；無依賴填 `none` |
| `context source` | agent 應讀取的持久化 context 來源 |
| `commit policy` | 明確 agent 自 commit、PM 統一 commit、或 no commit |
| `run mode` | `parallel`、`serial` 或 `blocked`；不得用 `batch` 表示自動批量執行 |

---

## 填寫要點

| 欄位 | 內容要求 |
|------|---------|
| `{agent-name}` | 代理人名稱（如 `thyme-python-developer`） |
| `{agent-description 引文}` | 從 `.claude/agents/{agent}.md` frontmatter `description` 直接引用 |
| 允許的產出 | 對照代理人可編輯路徑表 + 本 Ticket `where.files` 交集 |
| 禁止的產出 | 並行 Ticket 範圍、代理人定義外的檔案類型、跨 Ticket 動作 |

---

## PM 自做 framework 規則編輯流程

> **用途**：PM 直接編輯 framework 規則檔（`.claude/rules/`、`pm-rules/`、`references/`、`skills/`、`methodologies/`、`agents/`）的標準流程，含 Layer 1 自檢 + Layer 2 委員審查。
>
> **設計依據**：W17-122 ANA Layer C 落地（與 Layer A Hook + Layer B Claim 提示三層協同）。實證來源：W17-060 落地暴露兩個流程缺口（事前未觸發 SKILL + 事後缺 Layer 2 委員），規則 6 條款違反 compositional-writing 原則 3。

### 標準步驟（6 步，跳過項需評估成本）

| 步驟 | 動作 | 跳過此步的成本 vs 執行此步的成本 |
|------|------|----------------------------|
| 1. Read SKILL | claim 後、Edit 前 Read `.claude/skills/compositional-writing/SKILL.md`（與該情境對應的 reference）。同 session 已 Read 過時可省略 | 跳過：違反原則 3 機率高（W17-060 實證），事後 Layer 2 補做約 5-10K token；執行：先讀 SKILL 約 2-3K token 換取首次撰寫品質 |
| 2. 撰寫 | 依 SKILL 原則撰寫，重點：原則 3（機會成本語氣）+ 原則 6 第 3 輪 review（絕對主義詞翻 trade-off） | 規範性文字（template / hook 訊息 / claim 提示）以機會成本示範；事實陳述（描述歷史違規）可保留絕對語氣；兩者明確分區 |
| 3. 派 Layer 2 | 派 `basil-writing-critic` 等獨立委員審查文字品質，明示審「絕對主義 vs 機會成本 / 正向 vs 負向表述」 | 規範性文字場景：PM 自做 Layer 1 + Layer 4 同主體失去獨立性風險高（PC-081），獨立委員約 3-5K token 換取盲區發現（W17-051 多視角審查盲區案例）；事實陳述場景：風險較低，可視範圍決定是否派發 |
| 4. 收報告 | 接收 Layer 2 報告，按 P0/P1/P2 分級判斷修正幅度 | P0 阻擋級值得修正；P1 視成本決定修正或建 follow-up；P2 可建 follow-up 批次處理 |
| 5. 修正 | 依報告修正內容 | 修正幅度大時可選擇性再派一輪委員 |
| 6. commit（建議） | commit msg 含「Layer 2 by [agent-name]」標記，便於後續追蹤 | 缺標記時 commit-msg hook 警告（依 W17-126 落地後生效）；標記讓後人快速判斷 commit 是否經獨立審查 |

### Commit msg 標記規範

```
docs(<ticket-id>): <summary>

<body>

Layer 2 by <agent-name> (audit <agentId 或 ticket ID>)
```

實際範例（取自 W17-060 落地）：
```
docs(0.18.0-W17-060): 新增 ai-communication-rules 規則 6

Layer 2 by basil-writing-critic (agent ad93c61e88f1ff6e8)
```

Layer 2 不適用情境（如 typo 修正、純結構重組）標：
```
Layer 2 不適用 by <理由>
```

上述兩類以外，預設走 Layer 2；模糊場景偏向走 Layer 2 換取盲區發現（事後補做成本高於事前審查）。

### 適用範圍

| 情境 | 走完整 6 步驟的成本對比 | 可省略條件 |
|------|---------------------|----------|
| 新增規則條款 | 完整 6 步驟成本約 10-15K token；省略 Layer 2 風險高（規則條款是後續引用基礎，違規累積成本高） | 規則條款屬內部草案/實驗條款且後續會強制走 Layer 2 收斂時可暫省（草案標記必須明示） |
| 修正既有規則文字 | 完整 6 步驟成本約 8-12K token；視修正範圍與既有規則重要性 | 修正屬純語句通順化（未改規範強度、未改適用邊界）時可省略 |
| 新增 / 修改 SKILL.md 主文 | 完整 6 步驟（SKILL 主文影響面廣） | SKILL 主文無「適用情境/觸發條件/禁止行為」段落變更時可省略 |
| typo 或 link 修正 | 可省略 Layer 2，commit msg 標「Layer 2 不適用 by typo」 | 預設可省略 |
| 純結構重組（不改文字） | 可省略 Layer 2，標「Layer 2 不適用 by 結構重組」 | 預設可省略 |

### 三層協同（W17-122 ANA Solution 落地後生效）

本流程是 W17-122 三層防護的 Layer C（紙本約束）。Layer A（hook 自動偵測）與 Layer B（claim 提示）為事前提醒，本 Layer 為事中規範與事後追蹤的紙本依據：

| 時點 | 機制 | 落地 ticket |
|------|------|-----------|
| 事前 | Hook 偵測 Edit framework 路徑時若無 SKILL 呼叫即警告 | W17-127（未來落地） |
| 事前 | claim 時若 ticket where.files 含 framework 路徑即新增 S 問提示 | W17-125（未來落地） |
| 事中 / 事後 | 本流程 + commit msg 標記規範 | W17-124（本 ticket） |
| 事後追蹤 | commit-msg hook 偵測 framework commit 是否含 Layer 2 標記 | W17-126（未來落地） |

四個 ticket 落地完成後，三層防護完整協同；任一層失效時其他層提供備援。

---

## Layer 1 自檢觸發指引

> **用途**：PM 派發代理人時，在 prompt 末段插入自檢指令，使代理人在 complete 前執行一輪 Layer 1 自律審查。
>
> **設計依據**：W17-061（W17-051 WRAP 選項 B 階段二）— codex 實驗驗證第二步修正成本遠低於第一步生成，Layer 1 是最低成本的品質防護層。

### 觸發條件

| 情境 | 是否插入自檢指令 |
|------|----------------|
| IMP / ANA / DOC ticket（產出包含規則、方法論、長段說明） | 建議插入 |
| 純機械任務（格式修正、路徑替換等） | 可省略 |
| 代理人回報已執行 Layer 1 的情境（同 session 剛跑完） | 可省略 |

### prompt 末段插入範本

在任意派發 prompt 的最後一段，加入以下指令（可選一種）：

**標準版**（適合 IMP/ANA 規則類產出）：

```markdown
完成後 complete 前，依 .claude/references/agent-self-check-template.md 執行 Layer 1 自檢
（A 文字品質 / B 禁用字 / C Schema 結構），發現違規立即修正，結果寫入 Solution ### 自檢結果。
```

**精簡版**（適合小型 DOC 或純文件修正）：

```markdown
commit 前快速掃描禁用字（數據/代碼/默認/文檔/軟件/硬件/信息）和 emoji，確認無誤後 complete。
```

### 為何放末段而非開頭

自檢是「完成後」的動作，放末段對代理人的指令順序更自然：先執行任務，再回頭自檢，符合「生成 → 審查」的認知流程。放開頭會讓代理人在任務未完成時提前分心。

---

## 共用 lib 修復派發提醒（PC-136 強制）

> **用途**：派發共用 lib / predicate / shared utility bug 修復 IMP 時，在 prompt 加註此提醒，使代理人在修復前主動 grep all callers，防止「只修觸發 bug 的單一 caller」反模式。
>
> **設計依據**：PC-136（W17-182 retrospective ANA）— ARCH-020 三次重爆軌跡證實，未 grep all callers 的修復會在數週內從另一處重爆。

### 觸發條件

| 情境 | 是否插入提醒 |
|------|------------|
| IMP 修復共用函式 / predicate / shared utility bug | 強制 |
| ANA 驗證共用函式正確性 | 強制（指向 operational-error-root-cause-methodology.md PC-136 章節） |
| 純單檔內部函式修復（無 caller 散佈） | 可省略 |
| 純機械任務（格式 / 路徑替換） | 可省略 |

### prompt 插入範本

在共用 lib 修復派發 prompt 中，加入以下段落（接在「## 任務」之後）：

```markdown
## 修復前必執行（PC-136）

執行 `grep -rn "<函式名>" .claude/ src/ lib/ tests/` 列出：
- 所有同名實作位置（lib + hook 雙副本可能存在）
- 所有 caller 位置

在 ticket Problem Analysis append 完整清單後再開始修復。修復後對每處逐一確認已同步修正，禁止只修觸發 bug 的單一 caller。

依據：.claude/references/quality-common.md §1.2.6
```

### 為何強制

| 防護層 | 失效模式 |
|-------|---------|
| 代理人自律（quality-common §1.2.6） | 高壓 / 急迫情境下易跳過 grep |
| **派發 prompt 提醒** | **派發時即明示，代理人執行前有檢查依據** |
| ANA 方法論（callees 追蹤） | 屬 ANA 階段，IMP 階段需另有提醒 |

三層協同，prompt 提醒是 IMP 階段的最後防線。

---

## worktree 派發 base 同步指引（W1-035）

> **用途**：派發 `isolation: "worktree"` agent 時，在 prompt 加入 base 同步指引，使 agent 開始工作前先將 worktree merge 至最新 main。
>
> **設計依據**：W1-035 ANA — cc runtime `isolation:worktree` 以派發瞬間 main HEAD 為快照、不後續同步；worktree 共享 git object store，可在 worktree 內直接 merge main 取得最新內容。

### 觸發條件

| 情境 | 是否插入指引 |
|------|------------|
| `isolation: "worktree"` 背景派發 | 強制 |
| 非 worktree 派發（主 repo cwd） | 不需要（無 base 落差問題） |
| 純查詢類 agent（無 ticket create、無檔案寫入） | 可省略（stale base 不影響唯讀操作） |

### prompt 插入範本

在 worktree 派發 prompt 的「## 任務」或「## 執行」段開頭，加入：

```markdown
開始工作前先同步 worktree base：執行 git merge main（worktree 共享 git
object store，可直接 merge），確認本地檔案為最新 main 後再開始工作。
```

### 與派發前 commit gate 的關係

A1（PM 派發前 commit gate，見 `.claude/pm-rules/behavior-loop-details.md`「派發前檢查：worktree base 同步」）與本指引（B1）為互補防護：A1 在派發前縮小 base 初始落差，B1 在 agent 端補平派發後新增的落差。A1 是一次 `git status`、B1 是 prompt 內一行 `git merge` 指引，相對於 base 落差累積後的手動整合成本，兩者投入都小；並用可覆蓋派發前與執行中兩個時間窗。

---

## tests/ 修改派發 SOP（W1-051）

**用途**：派發涉及 tests/ 修改的 agent 前，PM 必須先建立 feat branch，避免代理人在受保護的 main branch 上被 branch-verify-hook 阻擋。

**Why**：`.claude/hooks/branch-verify-hook.py` 的 `exempt_prefixes = [.claude/, docs/, scripts/experiments/]`，tests/ 不在豁免清單。tests/ 與 src/ 是緊耦合對偶——tests/ 變更通常反映「規格變更」需要對應 src/ 變更才完整，允許 tests/ 在 main 上直接修改會增加紅燈直接進 main 的風險，違反 quality-baseline 規則 1。

**Consequence**：跳過此 SOP 會導致代理人 Edit tests/ 第一次嘗試被 hook deny，浪費代理人回合（PC-042 ~20 tool call 上限）；嚴重時代理人 self-imposed early stop 誤判平台不允許（PC-112 同精神）。

**Action**：依下方觸發條件 + 操作步驟執行。

### 觸發條件

| 情境 | 是否需先建 feat branch |
|------|-------------------|
| ticket where.files 含 tests/ 路徑 | 是 |
| 代理人 prompt 含 Edit/Write tests/* | 是 |
| TDD Phase 2 由 PM 前台寫 RED 測試 | 是 |
| 純讀取 tests/（如分析測試結構） | 否 |
| isolation: worktree 派發（cc runtime 自動建 worktree） | 否（worktree 自動隔離） |

### 操作步驟（派發前）

PM 在 main branch 執行：

```bash
git checkout -b feat/<ticket-id>-<short-desc>
```

範例：`feat/0.19.0-W1-081-worklogs-root-dynamic`

命名建議：feat 前綴 + 完整 ticket ID + 簡短描述（kebab-case，3-5 字）。

### 操作步驟（派發後）

1. agent 在 feat branch 上 Edit / 跑測試 / commit
2. PM 接收回報、驗證 acceptance、寫 Phase 4 評估報告
3. PM 切回 main：`git checkout main`
4. Fast-forward merge：`git merge feat/<branch-name> --no-edit`

### 為何不採方案 B（擴大 exempt 加 tests/）

允許 tests/ 在 main 上直接編輯會在以下情境放任紅燈：(1) RED 測試 commit 直接進 main、(2) 測試失敗未及修復即 commit、(3) 多並行 ticket 同時改 tests/ 互相覆蓋。feat branch 隔離強制完整 GREEN 後才 merge，符合品質承諾。

### 為何不採方案 A（強制 worktree）

worktree CLI 目前有 bug（W1-118 偵測：誤報「基礎分支 main 不存在」），在 W1-118 修復前不可依賴。即便 W1-118 修復，git checkout -b 對於小型 ticket（< 1 day）仍是 lower-overhead 的選擇（無需切目錄、無需後續 worktree merge 步驟）。

### 實證（W1-081 session）

PM 試圖直接 Edit tests/unit/scripts/build-version-check.test.js 被 branch-verify-hook 擋下，fallback 到 `git checkout -b feat/0.19.0-W1-081-worklogs-root-dynamic`，完成 Phase 2/3b/4 後 fast-forward merge 回 main，全流程無 friction（5 個 commit fast-forward 整合）。

---

## 適用範圍

| 場景 | 是否強制引用骨架 |
|------|----------------|
| 所有 TDD Phase 派發（Phase 1-4） | 強制 |
| 所有背景代理人派發（`run_in_background: true`） | 強制 |
| ANA / DOC / IMP 各類 Ticket 派發 | 強制 |
| 並行派發（多代理人同時） | 強制（尤其重要，範圍劃分清楚） |
| 探索類代理人（Explore、查詢類） | 選用（無寫入風險時可省略） |

---

## 為何不直接依賴代理人定義？

代理人 frontmatter 已定義職責，但實務證明僅靠代理人端檢查不足夠：

| 防護層 | 失效模式 |
|-------|---------|
| 代理人端 agent 定義 | 代理人可能為滿足 prompt 具體要求而越界 |
| Hook 預檢（branch-verify-hook） | 僅檢查路徑白名單，無法判斷 Ticket 範圍 |
| **Prompt 端職責邊界聲明** | **派發時即明示邊界，代理人執行前有自檢依據** |

三層防護並存，prompt 端聲明是派發時的最後防線。

---

## 與 /goal 的邊界

> **設計依據**：W3-032 ANA 結論方案 D — `/goal` 與 ticket acceptance 運作層級根本不同，不整合、平行存在。

`/goal`（Claude Code v2.1.139+ 的 session 執行工具）與 ticket `acceptance`（本專案品質閘門）看似都在定義「完成條件」，但兩者解決不同問題，**不可互相取代**。

### 層級對照表

| 維度 | `/goal`（session 引導） | `acceptance`（ticket 品質閘門） |
|------|------------------------|--------------------------------|
| 層級 | session-level | ticket-level |
| 持久性 | session 結束即消失 | `.md` 檔持久存在，可 git 追蹤 |
| 定義者 | 用戶即時輸入 | PM 建立 ticket 時定義 |
| 驗證者 | Claude Code evaluator（runtime 自動） | acceptance-gate-hook + CLI（半自動） |
| 核心用途 | execution boundary（何時停止執行） | quality gate（產出是否合格） |
| 可追蹤性 | 無（session 內暫態） | 有（ticket history + git blame） |
| 多條件支援 | 單一 goal | 多條 acceptance 條件 |

### 兩者不可互相取代的原因

- `/goal` 的 evaluator 為 runtime 內部機制，**無法客製化**；`acceptance-gate-hook` 支援 7 個 checker（正則、指令執行、欄位驗證）。
- 若 `/goal` evaluator 認為「完成了」但 `acceptance-gate-hook` 認為「未完成」，agent 會停止但 ticket 無法 complete，產生**死鎖或狀態混淆**。
- `acceptance` 是本專案品質追蹤鏈路（frontmatter → CLI → hook → lifecycle）的核心節點；`/goal` 是輔助執行的工具，不具備此鏈路。

### 允許的搭配使用方式

派發代理人時若需使用 `/goal`，goal 定義應與 ticket acceptance 對齊（方向一致），但 **`/goal` 不取代 acceptance 驗收**：

```markdown
# 允許：方向對齊但不取代
/goal: 完成 ticket 0.19.0-W3-032.1 的所有 acceptance 條件

# ticket acceptance 仍由以下機制負責驗收（不省略）：
ticket track check-acceptance --all 0.19.0-W3-032.1
ticket track complete 0.19.0-W3-032.1
```

---

## 相關文件

- `.claude/pm-rules/parallel-dispatch.md` — 引用本模板為強制骨架
- `.claude/pm-rules/decision-tree.md` — 代理人可編輯路徑對照表
- `.claude/rules/core/quality-baseline.md` — 規則 6 失敗案例學習原則

---

**Last Updated**: 2026-05-26
**Version**: 1.5.0 — 新增「與 /goal 的邊界」章節：層級對照表（7 維度）、不可互相取代原因（含死鎖風險）、允許搭配使用範例（W3-032.1 落地，對應 W3-032 ANA 方案 D）

**Version**: 1.4.0 — 新增「共用 lib 修復派發提醒（PC-136 強制）」章節：觸發條件表、prompt 插入範本、三層協同說明（W17-182.1 落地）

**Version**: 1.3.1 — W17-128 批次落地 W17-124 剩餘 Layer 2 違規修正：(1) P1 #7 適用範圍表新增「可省略條件」欄（5 列分別給條件）；(2) P2 #5 步驟 6 commit 標題加「（建議）」；(3) P2 #6「Layer 2 不適用情境」段落補正向陳述「上述兩類以外預設走 Layer 2，模糊場景偏向走 Layer 2 換取盲區發現」；P2 #8 屬事實陳述（W17-124 basil 報告判定可接受）無修

**Version**: 1.3.0 — 新增「Layer 1 自檢觸發指引」章節（W17-061）：觸發條件表、標準版與精簡版 prompt 末段範本、放末段的設計理由

**Version**: 1.2.1 — 依 W17-124 Layer 2 審查（basil-writing-critic）修正 P1 違規 3 條：(1) 標題「必經步驟」改「標準步驟（6 步，跳過項需評估成本）」；(2) 步驟 1 補同 session 已讀豁免條件；(3) 步驟 3 補規範性文字 vs 事實陳述場景區分。剩餘 P1 #7（適用範圍可省略條件欄）+ 4 條 P2 排入 follow-up

**Version**: 1.2.0 — 新增「PM 自做 framework 規則編輯流程」章節（W17-124 / W17-122 ANA Layer C 落地）：6 步驟標準流程、Commit msg 標記規範、適用範圍對照、三層協同表（與 W17-125/126/127 銜接）。文字以機會成本語氣示範（dogfooding，避免 W17-122 Solution 自身違規重蹈）

**Version**: 1.1.0 — 新增短 prompt snippets 與 dispatch-plan template（W17-044）

**Version**: 1.0.0 — 從 W5-009 方案 2 落地（Ticket 0.18.0-W5-044）
