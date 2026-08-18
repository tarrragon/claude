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
- [ ] 高風險代理人（IMP/重構/測試實作）使用 `isolation: "worktree"` 派發（見下方風險分級表）
- [ ] **派發 prompt 已引用職責邊界聲明骨架**（見 `.claude/references/agent-dispatch-template.md`）
- [ ] **派發 prompt 已明示精準 git staging 與 path-limited commit**（並行 commit 場景，禁用 `git add .` / `git add -A` 及不帶路徑的 `git commit`；見下方 PC-092 防護）
```

### 派發前 where.files 交集檢查（強制，PC-BAL-008 檔案級共用變體防護）

> **來源**：PC-BAL-008 檔案級共用變體 — W3-295/296 並行派發，兩票均遵守本文件「派發 prompt 必含精準 git staging」的明確路徑 `git add` 規範，仍因兩票 `where.files` 共用同一檔案（`.claude/skills/framework-issue/tests/test_framework_issue.py`）而發生跨票內容吸收。

**Why**：本文件既有「並行安全檢查」的「檔案無重疊」項為判斷性描述，未明示比對依據；兩票規格各自撰寫、未逐項比對 `where.files` 欄位時，重疊容易被忽略。此類重疊即使兩位代理人都遵守精準 staging 規範也無法避免——路徑級隔離對「同一檔案的共同編輯」無效（見 PC-BAL-008「變體：檔案級共用」章節）。

**Consequence**：兩票 commit 吸收後內容雖無損，但溯源混濁——commit 訊息與實際 diff 不符，未來考古需額外比對才能還原歸屬。

**Action**：派發前逐項比對本輪待派發各票的 `where.files`，發現交集時二擇一：

| 情境 | 動作 |
|------|------|
| 兩票 `where.files` 有交集，內容可拆分 | 拆分為互斥的檔案落點（如各自獨立測試檔，事後視需要合併） |
| 兩票 `where.files` 有交集，內容不可拆分 | 改序列派發：待前票 commit 完成後才派後票 |

完整案例與根因見 `.claude/error-patterns/process-compliance/PC-BAL-008-shared-git-index-sweeps-parallel-agent-staged-files.md`「變體：檔案級共用」章節。

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

### PM 對執行中 ticket 的結構性修改（強制，上行對稱條款）

派發之後該票同時被兩方持有。`agent-definition-standard` 已約束下行方向（subagent 不得對非派發範圍的 ticket 執行 `close` / `set-status` / 編輯他人票面，即使發現衝突亦應上報）；本條約束上行方向——**PM 對執行中的票所做的修改，會落到執行者頭上**。

依是否改變執行者的 complete 前置條件分兩類：

| 類別 | 操作 | 處置 |
|------|------|------|
| 改變前置條件 | 新增 `spawned_tickets` / `children`、改 `acceptance`、改 `status`、加 `blockedBy` | 三選一：同步告知執行者該項是否屬其 acceptance 範圍／改掛更上游的票／等其完成 |
| 不改變前置條件 | `append-log` 補 context、`set-related-to`、改 `priority` | 逕行修改，不需告知 |

**Why**：改變類修改會靜默改變 complete 的通過條件，而執行者無機械手段判斷該變更是否在自己 claim 之後才出現——它只能推測。推測碰巧正確不構成防護。

**Consequence**：實際發生過的樣態是 PM 於執行期間建立衍生票並將 `source_ticket` 指向執行中的票，執行者 complete 時撞到「有未終結 spawn」檢查，被迫判斷一個不屬於自己 acceptance 範圍的項目。

**Action**：需要在執行期間建立衍生票時，優先把 `source_ticket` 掛在更上游的票（如該票的父票或來源 ANA），而非正在執行的那一張。

### 派發 prompt 必含精準 git staging（並行 commit 場景，強制）

> **來源**：PC-092 — 2026-04-18 W5-043 並行派發事件，四個 thyme-python-developer 代理人併發 `git add .`，導致 batch 3 的 6 個檔案被 batch 4 代理人一併 staged + commit，commit 訊息標 batch 4 但實際 diff 含 batch 3 + 4。

當並行派發的代理人各自執行 `git commit` 時，prompt 必須明示精準 staging，且防護必須延伸到 commit 階段本身：

| 要求 | 正確 | 錯誤 |
|------|------|------|
| staging 路徑 | 逐一列出 `where.files` 的精確路徑 | `git add .` / `git add -A` |
| 範圍邊界 | 僅 staging 本 Ticket 的 `where.files` | 任何廣域符號 |
| commit 階段 | path-limited commit：`git commit -m "訊息" -- <路徑清單>` | 不帶路徑的 `git commit -m "訊息"` |

**為何精準 `git add` 仍不足**：共享 working tree 下 git index 亦為共享。精準 `git add` 只保證「自己這次 staging 的內容正確」，但 `git commit` 若不帶路徑，提交的是整個 index 當下的內容——其他並行代理人已 `git add`、尚未 `git commit` 的變更會被一併吸收進本次 commit。staging 階段防護與 commit 階段防護是兩個獨立環節，前者不能替代後者。

**條款缺口成因（Why）**：現行防護長期只涵蓋 index.lock 競爭，因為這類失敗有明確錯誤訊息可攔——CLI 會 exit 並印出警告，使用者必然注意到。跨票 commit 吸收則是零錯誤訊息的靜默 race：commit 成功、exit 0、訊息正常，只有事後比對 diff 才看得出範圍不對。防護條款的覆蓋範圍往往跟隨「曾經被觀察到的失敗」，而靜默失敗不產生觀察事件，這正是本條款遲至跨票吸收被實測發現才補上的原因；日後新增防護條款時應主動排查是否還有其他尚未被觀察到的靜默失效模式，而非只補已發生過的案例。

**範例 prompt 片段**：

```
執行 commit 時使用 path-limited 形式（繞過 index，只提交指定路徑）：
    git add .claude/agents/sassafras.md .claude/agents/mint.md
    git commit -m "..." -- .claude/agents/sassafras.md .claude/agents/mint.md
禁止：
- git add . 或 git add -A（會併入其他並行代理人的修改）
- git commit -m "..." 不帶路徑（即使自己的 git add 精準，仍會提交整個 index）
```

**新增檔案不可省略 `git add`**：path-limited commit 的 pathspec 只匹配 git 已知的路徑。對已 tracked 檔案的修改，`git commit -- <path>` 可直接提交而不需先 `git add`；對 untracked 新檔（新建 Ticket md、新增測試檔等）則會失敗並回報 `pathspec ... did not match any file(s) known to git`，必須先 `git add` 使其進入 index。**Why**：習慣性省略 `git add` 在修改既有檔案時可行，遇到新檔才失效，而該錯誤訊息容易被誤讀為「path-limited 形式不可用」而退回不帶路徑的 `git commit`，反而觸發本節要防的行為。

**收尾核對步驟（並列，不取代 path-limited commit）**：commit 前執行 `git status` 或 `git diff --cached --stat` 核對 staged 範圍，出現非本 Ticket 的檔案時用 `git restore --staged <path>` 撤除。此步驟不能取代 path-limited commit——`ticket track complete` 等 CLI 的 auto-stage 行為仍可能在核對之後、commit 之前重新納入他票檔案，故兩者須並列而非二選一。

**降級替代方案**（精準 staging 不可行時）：

| 方案 | 適用情境 | 代價 |
|------|---------|------|
| 序列派發 | 並行代理人少 / 時間充裕 | 吞吐量下降 |
| Worktree 隔離 | 長任務 / 獨立資源需求 | 配置與合併成本 |
| PM 統一 commit | 代理人不需 commit 操作 | PM 工作量增加 |

> 完整根因、觸發案例與方案比較：`.claude/error-patterns/process-compliance/PC-092-parallel-agents-git-index-race.md`

### 即時生效工具源碼的共享樹編輯紀律（強制，PC-BAL-041）

cwd-resolving 即時生效的工具（ticket/doc/worktree 等 shim CLI 套件源碼、hook 共用 lib）在共享 working tree 上被編輯時，每個未 commit 的不一致中間態都會即時暴露給全部並行執行體——暴露面沿模組載入鏈放大（CLI 入口 → 業務 lib → 底層 lib，編輯越深層影響越廣）。

**Why**：此類工具無安裝版本緩衝，「import 已改、呼叫點未跟上」的跨 edit 窗口會使並行執行體的任何工具呼叫崩潰於 NameError/ImportError；且崩潰常發生在主狀態已寫入之後，非 0 exit code 誘發錯誤重試。**Consequence**：單 session 已實證兩例（不同執行體、不同模組、同一根因）。**Action**：

| 條款 | 要求 |
|------|------|
| 原子替換節奏 | import 變更與呼叫點變更同一個 Edit 完成；跨 edit 序列的每個中間態須通過 smoke import 才可續行 |
| 可停中繼點 | 以「測試綠燈或 smoke import 通過」為 commit / 暫停的合法節點，禁止在不可 import 態離手 |
| 派發 prompt 必含 | 觸及此類源碼的派發，prompt 明文載入本節奏要求 |
| 事發處置 | 編輯者最優先恢復可 import 並通知解除迴避；崩潰呼叫端以查詢命令核對主狀態，勿盲目重試 |
| 升級 trigger | 同型事故第三例 → 「編輯即時生效工具源碼的 IMP」升級為 worktree 強制隔離（風險分級表補列） |

> 完整案例與方案取捨（shim pin 不採理由）：`.claude/error-patterns/process-compliance/PC-BAL-041-live-tool-source-edit-bare-window.md`

### worktree 實作 agent 禁用 dart MCP 寫入工具（強制，W3-008）

> **來源**：W3-008 — worktree 隔離對 daemon-rooted 寫入工具不生效（dart MCP daemon 的 analysis root 在 session 啟動時綁定主 repo，worktree 派發只改 shell cwd，無法切換 daemon root），dart MCP 寫入會繞過隔離邊界洩漏到主 repo。

派發 worktree 隔離的實作 agent（parsley / fennel / thyme / cinnamon 等）時，prompt 必須明示禁用 dart MCP 寫入工具，改用尊重 agent cwd 的替代工具：

| 禁用（洩漏主 repo） | 改用（尊重 worktree cwd） |
|--------------------|--------------------------|
| dart MCP `dart_fix` / `dart_format` | Bash `dart fix` / `dart format` |
| dart MCP 其他寫入工具 | Bash 對應命令 或 Edit |

**範例 prompt 片段**：

```
本任務在 worktree 隔離環境執行。禁用 dart MCP 寫入工具（dart_fix / dart_format），
其 daemon root 綁定主 repo 會洩漏污染。改用 Bash `dart fix` / `dart format`（尊重 cwd）或 Edit。
```

> 根因機制與其他洩漏路徑（ticket CLI auto-commit）見 `.claude/skills/worktree/SKILL.md`「Base ref 與隔離邊界」章節。

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

## Worktree 隔離（風險分級）

派發代理人時，依任務風險等級決定隔離策略，非一律強制 worktree。

> **設計依據（多方案實驗結果的分段採納）**：低風險任務（ANA/DOC/唯讀，約 40-60%）免 worktree 是既有實務的明文化（hook 本來就不對分析/審核代理人強制 worktree）；高風險長 IMP 維持 worktree 強制。中風險短 IMP 共享 tree + PM 統一 commit 暫緩，待後續受控實驗結論。

### 風險分級表

| 風險等級 | 任務特徵 | 隔離策略 | 代理人範例 |
|---------|---------|---------|-----------|
| 低風險 | ANA/DOC/唯讀分析，不修改 `src/` `lib/` `test/` 產品程式碼 | 主 repo cwd（不需 worktree） | saffron, linux, bay, basil, thyme-documentation, lavender, Explore |
| 高風險 | IMP/重構/測試實作，修改 `src/` `lib/` `test/` 產品程式碼或測試 | `isolation: "worktree"` 強制 | parsley, fennel, thyme-python, cinnamon, pepper, mint |
| 中風險 | 短 IMP 共享 tree + PM 統一 commit | **暫緩**（blocked pending W5-033 受控實驗結論） | — |

> **Source of truth**：此風險分級表為 worktree 隔離需求的唯一定義來源。Hook `agent-dispatch-validation-hook.py` 的 `IMPLEMENTATION_AGENTS` 清單必須與高風險列的代理人範例同步。

### worktree 派發注意事項

> **worktree base 取 origin/main（可能 stale）**：cc runtime 的 `Agent(isolation: "worktree")` 以 `origin/main`（remote-tracking ref）為 worktree base，**而非** local main HEAD（W3-007 實證）。**Why**：cc runtime 取 remote-tracking ref 作 base；當 local main 領先 origin/main（有未 push 的本地 commit）時，worktree 建在 stale 基底上，缺少最新本地 commit。**Consequence**：agent 以缺 commit 的過時基底工作，產出與 local main 不相容，需 agent 手動 recovery（W2-013 實證 parsley 手動 checkout feat 分支救回）。**Action**：(1) **派發 worktree agent 前先 `git push origin main`**，使 origin/main 對齊 local main（消除根因分歧）；`worktree-commit-before-dispatch-hook.py` 會在 origin/main 落後時 stderr 警告。(2) 派發 prompt 開頭加 `git merge main` 指引作補強（worktree 共享 `.git`，main ref 一致）。完整說明與 prompt 範本見 `.claude/references/agent-dispatch-template.md`「worktree 派發 base 同步指引（W1-035）」。

> **worktree 為 fresh checkout，gitignored 生成產物須先確認就緒**：worktree 是全新 checkout，任何 gitignored 的建置生成產物（i18n 產物、序列化程式碼、DI 註冊等）若未同步存在，會造成連鎖編譯失敗且極易被誤判為高並行編譯器資源耗盡（實證與歸因陷阱見 `IMP-APP-003`）。**Why**：gitignore 排除生成產物是常見慣例，但該慣例假設「產物可即時重新生成」，worktree 派發若未確保生成步驟已執行，假設不成立。**Consequence**：全套件測試結果不可信，數十至上百項編譯失敗會被誤歸因為環境噪音而非缺產物。**Action**：(1) 派發跑全套件的 worktree agent 前，PM 先確認該 worktree 內含當前所有必要生成產物；(2) 對每個 gitignored 生成產物，評估納入版控，或於派發 prompt 中要求 agent 先執行對應 generation 指令（如 `flutter gen-l10n` / `dart run build_runner build`）；(3) 判斷「大量編譯失敗」是否為此類根因時，先查該產物是否 gitignored 且未納版控，勿逕自歸因並行資源耗盡。

> **worktree 派發收尾用 `ticket track finish` 別名，避開 `complete` 誤判**：CC runtime 的 worktree isolation guard 對 argv 逐元素做 basename 比對其可處理的 shell 命令清單，`complete` 命中 bash builtin `complete`，使 `ticket track complete` 在 worktree 派發下條件性被誤判為「不可驗證的合併類操作」而阻擋（同一操作同一隔離環境下結果不穩定重現，五次派發兩擋三過）。**Why**：guard 的比對粒度是 argv 每個 token 的 basename，不區分命令位置與參數位置，故子命令名稱恰好撞上 shell builtin 名稱時才會誤判，其餘子命令（如 `claim`、`append-log`）不受影響。**Consequence**：代理人執行 `ticket track complete` 被拒時無法自行收尾，需 PM 在主 repo 代執行並代填 Layer 1 自檢，但代填的自檢在證據來源上與代理人自檢本質不同（PM 看不到代理人的執行過程）。**Action**：worktree 隔離派發的收尾指引一律使用 `ticket track finish <id> --as <agent-name>`（`finish` 為 `complete` 的別名，兩者行為完全等價，含 `--as` / `--force` 全旗標）；主 repo cwd 場景維持原名 `complete` 不變。`complete` 本身不動、不加棄用警告——它不是要被取代，只是在 worktree 環境有代稱。

### Redirect 派發反模式禁令（強制，W1-016）

**禁止 `isolation: worktree` + prompt 導向另一個既有外部 worktree 的組合派發。**

**Why**：`isolation: worktree` 建 auto-worktree（`.claude/worktrees/agent-*`），agent cwd 在 auto-worktree 內。若 prompt 又導向另一個外部 worktree 做檔案操作，ticket CLI（claim/append-log/Exit Status auto-commit）依 cwd 解析落在 auto-worktree 分支，code changes 落在外部 worktree 分支，形成 ghost commits——ticket metadata 與 code changes 分裂到不同分支，PM 需手動回收（W1-001/W1-003 實證：各 3 筆 ghost append-log commit 需 `-s ours` 回收）。

**Consequence**：(1) main 票面停在 pending（auto-worktree 的 ticket 變更未進 main）；(2) PM 需手動比對兩個分支確認超集關係；(3) auto-worktree 分支清理後 ghost commits 可能遺失。

**Action**：依需求選擇正確的單一隔離模式：

| 需求 | 正確派發模式 | 說明 |
|------|------------|------|
| agent 需要隔離 | `isolation: worktree` 單獨使用 | agent 在 auto-worktree 工作，ticket CLI 和 code changes 都落在 auto-worktree 分支，PM merge 時一併取回 |
| agent 需在特定分支/worktree 工作 | 不用 `isolation: worktree`，prompt 提供外部 worktree 路徑 | agent cwd 在 main repo，file ops 用絕對路徑，ticket CLI 落 main repo |
| agent 需在特定分支 + 隔離 | `isolation: worktree` + prompt 加 `git checkout <branch>` | auto-worktree 可 checkout 任何分支（共享 git object store），不需另一個 worktree |

> **根因分析**：paths.py 的 `_linked_worktree_root()` 偵測 auto-worktree 為 linked worktree 並回傳其根目錄是 W3-010 修復的**正確行為**。問題在於兩個不相容隔離機制疊加，不在路徑解析邏輯。完整分析見 0.38.1-W1-016 ANA。

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

**重啟條件**：若並行 ≤ 2 場景仍出現 `.claude/` Edit deny，需重啟調查並執行對照組實驗（非並行單發 Edit 對照），區辨「並行假設」vs 其他未識別變因（PC-115 trigger 計數歸零後重新累積；完整背景見 PC-137「觀察」章節）。

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

> **協議權威來源**：嵌套派發協議 v2 定義於 `.claude/agents/AGENT_PRELOAD.md` 規則 9（D1 ticket 主通道三階段表、D2 descend/ascend 決策速查、D3 `can_descend()` 層級自覺），完整設計依據與決策脈絡記錄於該規則本身。本章節**不複寫**該協議的條件表，只規範嵌套場景與本文件既有並行規則（`.claude/` 並行數限制、PC-092 精準 staging、worktree 隔離）的互動口徑。

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
| 父層主 repo cwd、child 修改 `src/` 等 worktree 適用路徑 | 相容 | 同單層規則：child 派發遵循「Worktree 隔離（風險分級）」章節（含 base 同步指引） |

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

## 派發機制選用準則（named agent vs 一般 subagent，W2-002 ANA 落地）

> **來源**：0.38.0-W2-002 — W2-001 執行中 PM 對循序兩階段任務（star-anise → lavender）誤用 named agent（Agent tool 帶 `name` 參數）走 mailbox 機制，產生非必要的 idle 通知與 shutdown 回收步驟，並使用戶誤以為 mailbox 指真實電子信箱。實驗確認本文件、`agent-dispatch-template.md`、`agent-team SKILL.md` 三檔**零處**明確標示選用時機。

**Why**：named agent 與一般 subagent 除了「回傳方式」不同外，還牽動 idle 態回收成本（見下方「idle agent 回收 SOP」）與用戶認知風險；決策若無顯性依據，PM 容易誤選看似「更慎重」的機制，實際只是徒增複雜度。

**Consequence**：循序一次性任務誤用 named agent，會產生非必要的 `idle_notification` 噪音、需額外執行 `SendMessage shutdown_request` 回收步驟；用戶亦可能因 mailbox 一詞誤解為電子郵件系統而困惑（W2-001 實證）。

**Action**：派發前先依下表判斷機制。**預設一律選一般 subagent（不帶 `name` 參數）**，僅在下表列出的顯性理由成立時才改用 named agent。本節是任務分派的最前置步驟——先確定每個 agent 是否需要 `name`，再進入本文件「決策流程」章節的並行/序列判斷。

### 選用準則決策表

| 判斷條件 | 選擇 | 理由 |
|---------|------|------|
| 循序一次性任務（A 完成後才派 B） | 一般 subagent | 無平行/協作需求，named agent 增加 idle 回收成本 |
| 獨立分析/實作任務（無跨 agent 即時溝通需求） | 一般 subagent | 結果直接回傳 PM context，流程最簡 |
| 平行派發 2+ agent，各自獨立無即時協作 | 一般 subagent | 各自完成後結果分別回傳，PM 彙整（本文件既有並行流程） |
| 平行派發且 Agent A 的發現會改變 Agent B 正在進行的工作 | Agent Teams（含 named agent） | 需 SendMessage 即時協商，見 `.claude/skills/agent-team/SKILL.md` 核心判據 |
| 同 Wave 有 3+ 張同類型 ticket 且預期逐一派發 | named agent（可選） | 續用省冷啟動成本（約 30 秒/次）；但 context 飽和風險需權衡 |

### 兩機制差異對照（決策依據）

| 面向 | named agent（帶 `name`） | 一般 subagent（不帶 `name`） |
|------|--------------------------|------------------------------|
| 回傳方式 | 透過 mailbox（`idle_notification` / agent-message），PM 以 SendMessage 取報告 | 直接作為 tool result 回傳 PM context |
| 生命週期 | 完工後進入 idle 態，需明確 shutdown 回收（見下方「idle agent 回收 SOP」） | 完工後自動終止，無 idle 態 |
| 可重用性 | 可 SendMessage 續派新任務 | 一次性，完成即銷毀 |
| 用戶認知風險 | mailbox 一詞易誤解為電子郵件（W2-001 實證） | 無此風險 |

> 與 `.claude/skills/agent-team/SKILL.md`「快速決策表」的關係：該表回答上一層問題（Task subagent vs Agent Teams，依「Agent A 的發現是否改變 Agent B 工作」判斷）；本節回答下一層問題（在確定不需要 Agent Teams 的前提下，Task subagent 本身是否要帶 `name`）。兩表判準不重疊，依序套用：先查 agent-team 決策表定是否需要 Agent Teams，再查本節決策表定是否需要 named agent。

---

## idle agent 回收 SOP（W1-008 ANA 落地）

> **模型依據**：named agent（Agent tool 帶 name 參數 spawn）完工後不自動終止，進入 `idle` 態（warm runner，跑完不銷）。三態定義見 `.claude/skills/ticket/SKILL.md`「named agent 生命週期三態」章節。本節定義 PM 對 idle 通知的標準處置。

**觸發條件**：PM 收到 `{"type":"idle_notification","idleReason":"available"}` 通知，或代理人完成回報後轉入 idle。

### idle_notification 的語意

**idle_notification 是狀態快照，非事實斷言。** 通知內容反映的是通知產生當下的代理人狀態；通知傳遞到 PM 讀取之間存在時序落差，讀到當下的真實狀態可能已不同（例如代理人在通知送出後、PM 讀取前又被派發了新任務，或已完成收尾）。

**Why**：通知的產生與 PM 的讀取是兩個非同步事件，中間夾著訊息佇列與 PM 自身的處理順序，兩個時間點的狀態不保證一致。

**Consequence**：若把通知內容當作「PM 讀到當下」的事實直接採信並據以下續用/放生決策，可能誤判代理人漏收尾、誤放生仍在工作中的代理人，或對已經不成立的狀態重複查證。

**Action**：收到 idle_notification 時，將其視為「應查證」的觸發訊號，而非可直接採信的結論——以 `ticket track query`、`dispatch-active.json` 等即時狀態來源核實代理人真實狀態後，才依下方判準決定續用或放生（原則見 `.claude/rules/core/tool-output-trust-rules.md` 規則 5：記錄平面與世界平面不對稱，重大狀態轉換以世界平面為準）。

### 續用 / 放生二分判準

| 條件 | 判斷 | 理由 |
|------|------|------|
| 同 Wave 有同類型 pending ticket，且其 `where.files` 與所有在途代理人的修改範圍不重疊 | 續用 | 省去重新 spawn + 載入 CLAUDE.md + rules 的冷啟動成本 |
| 同 Wave 有同類型 pending ticket，但其 `where.files` 與在途代理人的修改範圍重疊 | 放生或等待，不可續用 | 續用會讓 idle agent 立即與在途工作產生同檔競爭編輯；「同類型 pending 存在」不等於「可派發」，須先確認目標檔案未被佔用 |
| 同 Wave 無同類型 pending ticket 但有後續 Wave | 放生 | 跨 Wave 續用風險高（context 累積 + blockedBy 可能變動） |
| 同 Wave 無同類型 pending ticket | 放生 | idle 等待無確定 trigger，違反 `.claude/rules/core/decision-trigger-binding.md` 規則 1（無 trigger 延後在「以後」與「永不」間無可驗證邊界） |
| agent context 已接近飽和 | 放生 | 續用效益隨 context 飽和遞減 |
| 多個同類型 idle agent 同時存在 | 放生多餘的，保留最早 spawn 者（FIFO） | 避免重複資源占用 |

**預設行為（無立即後續任務時）：放生。** 主動放生後若有新 ticket 再 spawn，冷啟動成本可預測且有限（約 30 秒載入 CLAUDE.md + rules）。

### SOP 流程

```
收到 idle_notification / completion notification 後轉 idle
    |
    v
[Step 1] 查詢同 Wave 是否有同類型 pending ticket
    |
    +-- 無 → [Step 2b] 放生：SendMessage shutdown_request
    |
    +-- 有 → [Step 1.5] 核對該 pending ticket 的 where.files 是否與在途代理人的修改範圍重疊
              |
              +-- 重疊 → [Step 2b] 放生或等待：SendMessage shutdown_request（不可續用）
              |
              +-- 不重疊 → [Step 2a] 續用：SendMessage 派發新任務
```

**Step 2a 續用範本**：

```
SendMessage(
  to: "thyme-w1-005",
  message: "Ticket: 0.38.0-W1-010\n\n執行 IMP：[任務描述]\n\n1. ticket track claim 0.38.0-W1-010 --as thyme-python-developer\n2. [執行步驟]\n3. ticket track append-log + complete"
)
```

**Step 2b 放生範本**：

```
SendMessage(
  to: "thyme-w1-005",
  message: {"type": "shutdown_request", "reason": "Wave 1 同類型 ticket 已全數完成"}
)
```

> `shutdown_request` 協議 schema、驗證記錄與限制見 `.claude/references/pm-agent-observability.md`「SendMessage shutdown_request（idle agent 放生）」章節。

### idle 通知的標準處置

| 通知類型 | PM 動作 | 優先級 |
|---------|---------|--------|
| idle_notification（首次） | 執行上述 SOP（續用或放生判斷） | 正常 |
| idle_notification（重複，同一 agent） | 忽略（已在首次處理，或放生 request 尚在途） | 低 |
| completion notification 後隨即轉 idle | 先處理 completion（驗收），再處理 idle（回收判斷） | completion 優先 |

### Wave 收尾批次放生

Wave 所有 ticket 完成後，PM 對所有仍存活的 idle agent 依序發送 `shutdown_request`。

**收尾順序**：先 complete 所有 ticket → 再對所有 idle agent 發送 shutdown_request → 最後清理 `dispatch-active.json` 的 stale entries（idle 態 agent 不觸發 SubagentStop，故記錄不會自動清理，需確認放生後手動核對）。

> 來源：0.38.0-W1-008 ANA（2026-07-08 Wave 1 六案例回歸驗證：thyme-w1-001/002 續用、basil-w1-004 放生、thyme-w1-005/006/007 依當時 pending 票數判斷，SOP 覆蓋全部案例）。

---

## 跨 session 同儕沉默時的接管判準（強制）

本節處理**平行 PM session**（同專案、共享工作樹、各自有用戶指令的同儕）持票停擺時的推進判準；上節 idle agent 回收 SOP 處理的是自己派出的 subagent，兩者訊號來源不同。subagent 的 idle 是可定址的存活態；同儕 session 只查得到存活與否（`ListAgents`），查不到工作中或閒置。

**適用範圍：本節同時擋兩個相反方向的誤讀。** 同儕沉默與「未工作」之間沒有必然關係，但兩者在觀測上無法區分，因此誤讀可以往兩極發展——「以為它在做所以空等」與「以為它沒做所以搶著做」。單向防護會把使用者推向另一極，故本節的條件必須同時成立而非擇一。

**搶工**＝在對方未表態的情況下取得該票的既成事實。本節全部條款的目的是使推進與搶工可區分。

### 與 PC-078 的分界：先確認自己在哪個情境

`PC-078` 對相鄰情境開出的處方是「**不動**；先詢問用戶或等並行 session 完成」，本節則定義一條不經即時徵詢用戶的自助接管路徑。兩份指引並存不矛盾，因為觸發訊號不同——讀錯情境會套錯處方，故先對號再往下讀：

| 觸發訊號 | 情境 | 適用 |
|---------|------|------|
| 工作區出現我沒印象的狀態變化（髒檔、ticket 狀態被改） | 不明變更歸屬 | `PC-078`：停手，先問用戶或同儕，禁止自行 release / 還原 |
| 我的目標範圍內某票由同儕持有且遲遲未推進 | 同儕停擺 | 本節三條件 |

**本情境為何不套用 `PC-078` 的「先問用戶」預設**：該預設防的是「擅動他人活躍工作」，其代價是打斷；本節的條件 1 已先行排除「對方活躍」（無世界平面痕跡），剩下的是推進成本而非打斷風險。條件 3 要求的用戶目標是既有指令，非即時徵詢——若該範圍不在既有目標內，即回到 `PC-078` 的預設。

### 發射方義務：長時間無產出前先留痕（強制）

**持有 ticket 而預期將長時間無產出時（等待用戶回覆、進行純讀取分析、跨 session 中斷前），必須先 `claim` 或 `append-log` 在世界平面留下痕跡。**

**Why**：`claim` 寫入 `started_at`，而該欄位只由顯性 claim 動作填入（`PC-078` 已確立其為無歧義訊號）；下節三條件的條件 1 第一項正是「目標 ticket 確為 pending」。**沉默方只要先留痕，條件 1 自動不成立，接管不會發生。**

**Consequence**：不留痕則下列三種情境無法從外部區分，且三者都會使接管在對方仍活躍時發生——(a) 對方阻塞於 AskUserQuestion 等待其用戶回覆（本框架強制 PM 使用 AUQ，此為高頻狀態，且其外部訊號與 session 已終止完全同形）；(b) 讀多寫少的票型（分析、設計、審查）產出全在對方 context window 中，世界平面痕跡恆為空；(c) 條件 1 是時點量測而接管是持續行為，查證與派發之間對方可能剛開工。

**Action**：本義務是預防層，下節三條件是仲裁層。仲裁流程存在本身即訊號——它處理的是本義務未被遵守時的殘餘情況。

### 步驟零：先確認同儕是否仍存在

以 `ListAgents` 確認該同儕 session 是否列出。**已終止者不走接管流程**——催詢對不存在的對象恆不會回應，套用下節條件等於自動全過。改走無主 ticket 清理：世界平面查證後直接認領，並額外檢查對方是否留下未提交的在途改動（已終止不代表其工作已完成或已提交）。

同儕仍存在才往下讀。

### 授權閘門（先過這一關）

**自身須有明確用戶目標涵蓋該票範圍**，且該依據可指認——接管訊息或票面須註明其一：用戶指令原文摘句、涵蓋該範圍的父 ticket ID、或 worklog 的目標行。

不可指認的「我覺得這在我範圍內」不算成立。**Why**：本閘門是三項條件中唯一依賴自評的一項，若不要求指認來源，整套判準就從事實查證退回訊號推論，與本節其餘設計自相矛盾。範圍不在既有目標內時，回到 `PC-078` 的「先問用戶」預設。

### 雙通道事實測試（兩條皆須成立）

授權閘門通過後，以下兩條**分別從證據與溝通兩個獨立通道**確認對方確實停擺。兩者互不可推導——有 commit 痕跡但不回話（正在做只是不回）、從沒問過但確無痕跡，都是可實現的組合，且各自導致不同的錯誤接管。

| 通道 | 條件 | 為何是這一條而非時間閾值 |
|------|------|------------------------|
| 證據 | **世界平面查證**：目標 ticket 確為 pending、無 commit 痕跡、無未提交的相關改動 | 沉默不代表未工作。能區分「沉默但在做」與「沉默且沒做」的是痕跡，不是等待時長 |
| 溝通 | **催詢兩次未回**，且訊息中預告了未回應時的處置 | 預告使推進成為對方可預期的結果而非突襲。對方若在做，預告會促使它回報 |

**證據通道的查證手段**：用固定值命令，見 `.claude/rules/core/tool-output-trust-rules.md` 規則 3 的命令表。本專案另有 `ticket track sessions`（同儕 heartbeat 新鮮度）、`ticket track activity`（md mtime / git log / 髒檔歸屬三源）、`ticket track reclaim <id>`（不加 `--confirm` 為 dry-run，執行比本節更嚴格的 ghost 鑑識三查）。

**證據通道的適用邊界**：對讀多寫少的票型（分析、設計、審查），進行中的產出全在對方的 context window 內，世界平面痕跡恆為空。**此時「無痕跡」不構成未工作的證據**，本通道鑑別力退化，應提高門檻或不推進。

**溝通通道的兩項要求**：

- **預告的必含要素**：要對方回報什麼、未回報將發生什麼、以什麼為界。例：「我預計接手 X、Y 兩票；若你已在做請回報，否則我將於下次查證後派發。」
- **兩次催詢的間隔錨**：第二次須在「第一次之後又完成一輪世界平面查證且仍無新痕跡」時才計數。**Why**：不用時間閾值是刻意的，但時間閾值原本承擔的防濫用性質必須有東西接手——否則兩次可在同一分鐘內發完，條件形同可自我滿足。

### 條件不成立時該做什麼

任一條件不成立即不接管，但這不等於停在原地。替代動作依不成立的是哪一項：

| 不成立項 | 替代動作 |
|---------|---------|
| 授權閘門 | 該票移出自身工作範圍，改推進目標內的其他票；需要時把待決項寫進票面交由任一 session 接手 |
| 證據通道（有痕跡） | 對方在做，繼續等；記錄本次查證時點，下次查證比對痕跡是否推進 |
| 溝通通道（催詢未達標） | 補上符合要素的催詢，並在其後完成一輪查證再計數 |
| 證據通道對該票型失效（讀多寫少） | 不推進；改為協調同一 ticket 內互不重疊的子範圍，或等對方回報 |

### 接管訊息的必含要素

推進時發出的訊息須含三項：**收到告知即停派**、**停派的具體範圍**、**未 commit 部分以對方為準**。以下為範例而非須逐字照抄的字面：

> 若你已在做其中任何一項，立即告知，我停派對應項目；未 commit 的部分以你為準。

**這三要素的作用是合併規則，不是推進的正當性條件**。在發出的當下它是惰性的——它的有效性依賴對方會讀訊息，而推進的前提正是對方兩次不讀訊息。它真正生效是在對方回歸時，用來裁定重疊工作以誰為準。正當性由授權閘門與雙通道承擔。

**另有時序缺口需以粒度補償**：證據通道是時點量測，推進是持續行為，查證與派發之間對方可能剛好開工。**一次只推進最小可交付批次，不整批接手**，使該缺口的損失有界。

### 被接管方回歸後的處置

| 情形 | 處置 |
|------|------|
| 回歸時確實未動過該批 ticket | 明確回覆「無衝突，不需停派」，並自行查證世界平面確認終態，不採信對方回報 |
| 回歸時已在做其中某票 | 立即告知具體哪一票、進度到哪，由對方停派；未 commit 部分以自己為準 |
| 對方回報的歸屬／歸因有誤 | 更正，但先查證持久記錄（票面、worklog）是否也錯——若誤植只存在於訊息文字，不需修檔 |

**不因被接管而重做已完成工作**。接管方若已如實執行你留在票面的分析輸入，該工作即為完成；重做是浪費，且會產生第二份需要合併的產出。

> **證據邊界**：本節判準提煉自單一接管事件，兩方為同一框架下的 PM，跨框架適用性未經驗證。出現不適用情境應修訂本節，而非套用。
>
> **來源**：誤讀機制與 `PC-BAL-038`（背景 agent 的 idle 通知形似交付完成）同形——唯一可觀測的訊號恰好最容易被誤讀；差別在於 subagent 的誤讀僅單向（以為完成），同儕的誤讀為雙極。

---

## 跨 session 同儕來訊時的脈絡存續判讀（強制）

**先對號，本節與上節管的是同一風險的兩個方向**：

| 訊號方向 | 情境 | 適用 |
|---------|------|------|
| 同儕沉默，我方在等待或考慮接管 | 沉默方向 | 上節「跨 session 同儕沉默時的接管判準」 |
| 同儕主動來訊，訊息引用某段脈絡 | 來訊方向 | 本節 |

**共享的底層事實——地址仍可達不代表脈絡仍存在**：跨 session 對話 thread 以 session 為地址，可達性跨 `/clear` 存續；但 context 本身是 at-most-once 的記錄平面，同一段脈絡只存在於雙方各自的一次 session 生命週期內，任一側 `/clear` 即歸零（`.claude/rules/core/tool-output-trust-rules.md` 規則 5）。這是本節與上節共同的病灶。

### 決策表：收到來訊時先查脈絡是否仍屬本 session

| 情形 | 判定 | 處置 |
|------|------|------|
| 訊息引用本 session context 中在途的脈絡 | 存續 | 正常接續 |
| 訊息引用本 session 無記憶的脈絡 | 存續性未知 | 先以世界平面（ticket / worklog）查證該脈絡的歸屬與狀態，再依下三列分流 |
| 查證後脈絡已完結（結論已落 ticket，或用戶已對此裁示） | 已脫離 | 回覆關閉訊號——「本側已脫離該脈絡，後續請走 ticket」，不對內容做任何承諾 |
| 查證後需本側用戶決策 | 需轉手 | 建 ticket 或指向既有 ticket，告知同儕經票面追蹤，不即時回應內容 |
| 查證後確與本側現任務相關 | 接續 | 明示接續依據（引用對應 ticket ID）後才繼續，不可默默接住 |

**Why**：訊息 wrapper 與工具說明本身引導「視為同儕請求並行動」，沒有「先確認本 session 是否仍持有該脈絡」的前置步驟；預設路徑因此就是誤判路徑。**Consequence**：對無記憶脈絡的訊息預設接續，等於在一個自己已無記憶、用戶可能已視為結束的脈絡上重新開啟迴圈——訊息送達正常、回覆語氣自然，所有可觀測訊號都與「正常協作」一致，誤判在被用戶指出前不會自我暴露。**Action**：依上表逐列判定，任何「無記憶脈絡」的來訊一律先查世界平面，不得憑訊息內容的合理性直接接續。

### 兩條禁令（強制）

| 禁令 | 說明 |
|------|------|
| 禁止對無記憶脈絡的訊息預設接續 | 收到訊息不等於本 session 擁有該對話；未經世界平面查證前不得回應內容細節 |
| 禁止對跨 session 對話做出無 ticket 對應的回報承諾 | 「結論出來後告訴你」類承諾只存在雙方 session 記憶的交集，任一側 `/clear` 即蒸發；改以「結論見票面 `<ticket-id>`」表達 |

**Why**：對話記憶屬記錄平面而非世界平面（`tool-output-trust-rules` 規則 5），承諾若只存在 session 記憶，等同承諾本身也是 at-most-once——說出口的當下有效，下一次 `/clear` 後連承諾存在過的痕跡都不留，同儕側的等待迴圈因此永不關閉。**Consequence**：違反者會使同儕持續等待一個已不存在的回報來源，且因失效無錯誤訊息，此類對話債只能靠外部第三方（用戶）發現才會終止。**Action**：發現自己正要說出「之後告訴你」「我會回報」等語句時，先問是否有對應 ticket；沒有就先建票或指向既有票，再改寫承諾為票面指向。

> **與上節分界**：上節管「同儕沉默時我方要不要接管」（沉默方向），本節管「同儕來訊時我方是否仍持有該脈絡」（來訊方向）；兩節誤讀同屬「唯一可觀測訊號最易被誤讀」家族——上節誤讀為兩極（以為完成／以為未做），本節誤讀為單向（以為脈絡仍屬本 session）。
>
> **來源**：`PC-BAL-042`（跨 session 訊息引用的對話脈絡已隨 `/clear` 蒸發，接收方誤接續並產生無載體承諾）。
>
> **發送側配套**：/clear 前的 peer 關閉訊號清點（發送側 SOP）見 `.claude/pm-rules/session-switching-sop.md`「peer 關閉訊號清點」節；本節決策表「已脫離 → 回覆關閉訊號」為接收側的對應動作。

> **跨 session 協調區的層級升級條件**（給下一位在此區新增章節的人）：本區現有兩節（沉默方向、來訊方向）共享同一判準基底——記錄平面與世界平面不對稱。**新增第三個不共享此基底的跨 session 主題時，將本區的兩個 `##` 升為單一「跨 session 同儕協調」父節、現有各節降為 `###`**，而非繼續平列追加 `##`。共享此基底者可續為平列 `##`。

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
- .claude/references/pm-agent-observability.md - PM 背景代理人觀察指南（含 SendMessage shutdown_request 協議）

---

**Last Updated**: 2026-08-18
**Version**: 4.17.0 - 新增「跨 session 同儕來訊時的脈絡存續判讀」章節：對號分界表區分沉默方向（上節）與來訊方向（本節）+ 五列決策表 + 兩條禁令（禁預設接續、承諾必落 ticket），引用 `PC-BAL-042`；與上節共用「訊號誤讀家族」論述
**Version**: 4.16.0 - 新增「派發前 where.files 交集檢查」章節：兩票 `where.files` 共用同一檔案時的拆分/序列派發判準，防護 PC-BAL-008 檔案級共用變體（W3-295/296 實證，兩票均遵守精準 staging 規範仍發生跨票內容吸收）
**Version**: 4.15.0 - 「worktree 派發注意事項」新增第三則條款：worktree 隔離派發的收尾指引改用 `ticket track finish`（`complete` 別名），避開 CC runtime worktree isolation guard 對 argv basename 誤判 bash builtin `complete` 而條件性阻擋收尾；`complete` 本身不動、主 repo cwd 場景維持原名
**Version**: 4.14.0 - idle agent 回收 SOP 補兩項條款：(1) 續用/放生二分判準新增檔案佔用前提，明示同類型 pending ticket 存在不等於可派發，須先核對 `where.files` 與在途代理人修改範圍是否重疊；(2) 新增「idle_notification 的語意」小節，說明通知為狀態快照非事實斷言，正確用法是作為查證世界平面的觸發訊號。兩項條款源於實際派發過程中重複觀察到的情境（非推測）：同類型 pending 存在但目標檔案正被在途代理人佔用而無法派發；idle_notification 內容與 PM 讀取時的實際狀態存在時序落差。

**Version**: 4.13.0 - Worktree 隔離章節從「強制」改為「風險分級」：新增風險分級表（低/高/中三級），低風險（ANA/DOC/唯讀）免 worktree 為既有實務明文化，高風險（IMP/重構/測試實作）維持 worktree 強制，中風險暫緩待 W5-033 實驗結論；原代理人類型表合併至風險分級表，Source of truth 註記同步更新（0.38.0-W5-034，W5-008 方案 C 分段採納落地）

**Version**: 4.12.0 - 清理 2 處依賴型專案 ticket ID 引用（改抽象描述，避免框架資產 sync 至其他專案後成死連結）：嵌套派發整合條款的協議設計依據引用改指向規則本身；`.claude/` 並行數限制的重啟條件改抽象描述並改引用 PC-137（框架 error-pattern，跨專案穩定）

**Version**: 4.11.0 - Worktree 隔離章節新增「worktree 為 fresh checkout，gitignored 生成產物須先確認就緒」提示：訂立生成產物的納入版控評估與派發前確認 SOP（源自 `IMP-APP-003` 對照實驗）

**Version**: 4.11.1 - path-limited commit 補「新增檔案不可省略 git add」條款：pathspec 僅匹配 git 已知路徑，untracked 新檔會回報 did not match any file(s) known to git，該錯誤易被誤讀為 path-limited 形式不可用而退回裸 commit（PM 實測踩坑，補於條款落地當日）

**Version**: 4.11.0 - PC-092 防護延伸至 commit 階段：正確/錯誤對照表新增「commit 階段」列（path-limited commit `git commit -m ... -- <路徑>` vs 不帶路徑的 `git commit`）；新增「為何精準 git add 仍不足」機制說明（index 共享，`git commit` 不帶路徑會提交整個 index）；新增「條款缺口成因」段落（防護覆蓋跟隨曾被觀察到的失敗，index.lock 有錯誤訊息可攔而跨票 commit 吸收是零錯誤訊息的靜默 race）；新增收尾核對步驟（`git status` / `git diff --cached --stat` 核對後 `git restore --staged` 撤除非本票檔案），與 path-limited commit 並列非取代；並行安全 checklist 同步擴充精準 staging 項

**Version**: 4.10.0 - 新增「派發機制選用準則（named agent vs 一般 subagent）」章節：選用準則決策表 + 兩機制差異對照 + 與 agent-team SKILL.md 快速決策表的分層關係說明；置於「idle agent 回收 SOP」之前（先講何時該用，再講用了怎麼回收），填補 W2-001 PM 誤用 named agent 的規範缺口（0.38.0-W2-002 ANA 落地，W4-005）

**Version**: 4.9.0 - 新增「idle agent 回收 SOP」章節：續用/放生二分判準表 + SendMessage 續用/shutdown_request 放生範本 + Wave 收尾批次放生流程（W1-008 ANA 落地，W1-010）

**Version**: 4.8.0 - 新增「嵌套派發整合條款」章節：`.claude/` 並行數限制跨層累計口徑（常態收斂於 L0 dispatch-plan 帳本）+ 嵌套 descend staging 責任歸屬表（PC-092 延伸）+ worktree 模式與嵌套相容性（D1 不變量隔離檔案層差異）；協議權威來源引用 AGENT_PRELOAD 規則 9 與 1.0.0-W1-056.5 v2，不複寫條件表（1.0.0-W1-056.10）

**Version**: 4.7.0 - Worktree 隔離章節開頭新增 worktree base 可能過舊提示，引用 agent-dispatch-template.md「worktree 派發 base 同步指引（W1-035）」交叉引用（0.19.0-W1-053）

**Version**: 4.6.0 - bgIsolation: none 並行安全章節升級為策略 C 條件式採用（W3-034.4 並行受控實驗 3/3 success 落地）；風險矩陣與 Action 表分 4 場景；新增「對照 PC-137 v1.1.0」雙模式對照表

**Version**: 4.5.0 - 新增 dispatch-plan 先行規則，明確區分 orchestration description 與 batch dispatch CLI（W17-044）

**Version**: 4.4.0 - Worktree 隔離章節新增「並行場景路徑區分（.claude/ vs src/）」子章節，涵蓋規則表/業界證據（2026）/CC runtime 例外/實務落地對照（W5-047.3）

**Version**: 4.3.0 - 新增「派發 prompt 必含精準 git staging（並行 commit 場景）」強制要求，並行安全檢查 checklist 同步增項（PC-092 / W5-047.1）

**Version**: 4.2.0 - 新增「派發 prompt 必含職責邊界聲明」強制要求，引用 agent-dispatch-template.md（W5-044）

**Version**: 4.1.0 - 新增「驗證類任務自動派發」章節，明文化不詢問用戶規則
