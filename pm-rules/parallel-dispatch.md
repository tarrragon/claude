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
| 同主題 | 所有任務屬同一主題（見下方「主題層前置」）；跨主題任務不並行派發 |

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

## 主題層前置（強制）

**Why**：並行安全檢查回答的是「同時寫會不會撞」，回答不了「這些是否為同一件事」。兩者正交且時常反向——同主題的票因觸及同一批檔案而互斥，能並行的票往往正因為彼此不是同一件事。以檔案交集為唯一選票判準，等於用並行度取代主題作為工作單位。

**Consequence**：缺此層時，一輪派發會同時開啟數個不相干主題，每個推進一小段。任一主題都不收斂，而每次接手都要重建全部主題的 context。

**Action**：派發前先選定主題，再於該主題內套用上方五項觸發條件與複雜度五維度，不另立平行標準。

### 主題持有

一個 session 一次只持有一個主題。取主題前先查佔用狀態（主題清單視圖提供各主題的 in_progress 佔用與持有 session 的 lease 狀態）；已由 FRESH session 持有的主題不取。

### 主題與 Wave 的優先關係

主題優先於 Wave。主題跨 Wave 時以主題為單位推進，不因 Wave 邊界中斷；Wave 僅作為主題內的排序輸入。

**Why**：Wave 是批次容量的劃分，主題是語意的劃分。以 Wave 為單位切換，會使同一主題的票散落於多個 session，每次接手重建同一份 context。

### 主題內的兩條分流路徑

| 情境 | 路徑 |
|------|------|
| 主題內待辦全數滿足上方五項觸發條件，且複雜度五維度均判定適合 | 平行派發 |
| 任一觸發條件或任一複雜度維度不滿足 | 序列處理，並以 handoff 將 context 交接至主題內的優先項（`ticket handoff --from-ticket-id <來源> --next <主題內優先項>`） |

判準完全沿用上方既有條文，本節不新增平行標準——主題層決定「做哪一組」，既有五條件與五維度決定「這組能不能同時做」。

### topic 與 group ticket 的語彙區別

| 語彙 | 指涉 | 載體 |
|------|------|------|
| topic（主題） | 跨票的語意歸屬，一張票屬於零個或一個主題 | ticket_id 到主題的映射檔 |
| group ticket | 具 children 的父票，其 children 為結構上的子任務 | ticket frontmatter 的 `children` / `parent_id` |

兩者正交：同一主題的票可分屬不同 group ticket，同一 group ticket 的 children 亦可分屬不同主題。文件中提及「群組」時須指明何者，避免同詞異義。

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
- [ ] 高風險代理人（IMP/重構/測試實作）使用 `isolation: "worktree"` 派發（見 `.claude/references/parallel-dispatch-worktree-details.md` 風險分級表）
- [ ] **派發 prompt 已依權威骨架執行、未重述 ticket 已載欄位**（見 `.claude/references/agent-dispatch-template.md`「骨架（權威版）」與「prompt 不重述 ticket 已載欄位」節）
- [ ] **派發 prompt 已使用 `.claude/references/agent-dispatch-template.md`「精準 staging 制式句」固定措辭**（並行 commit 場景，逐字複製不自行改寫；見下方 PC-092 防護）
```

### 派發前 where.files 交集檢查（強制，PC-BAL-008 檔案級共用變體防護）

> **來源**：PC-BAL-008 檔案級共用變體 — 並行派發時，兩票均遵守本文件「派發 prompt 必含精準 git staging」的明確路徑 `git add` 規範，仍因兩票 `where.files` 共用同一檔案而發生跨票內容吸收。同型事件於 2026-08-18 再現於 PM 前台工作場景：PM 前台改寫本檔案尚未 commit 期間，另一 session 派發的代理人以同檔為標的執行 commit，將前台在途改動一併吸收——顯示原條款「僅比對本輪待派發各票」的範圍未涵蓋 PM 前台自身在途工作，是此次未攔截的根因之一（完整案例見 PC-BAL-008「變體：檔案級共用」章節）。

**Why**：本文件既有「並行安全檢查」的「檔案無重疊」項為判斷性描述，未明示比對依據；兩票規格各自撰寫、未逐項人工比對 `where.files` 欄位時，重疊容易被忽略，且人工比對天然只涵蓋「當下正在準備派發的這幾票」，看不到已在進行中、未在本輪派發清單內的其他票（含 PM 前台自身正在編輯但尚未 commit 的工作）。此類重疊即使兩位代理人都遵守精準 staging 規範也無法避免——路徑級隔離對「同一檔案的共同編輯」無效（見 PC-BAL-008「變體：檔案級共用」章節）。

**Consequence**：兩票 commit 吸收後內容雖無損，但溯源混濁——commit 訊息與實際 diff 不符，未來考古需額外比對才能還原歸屬；範圍未涵蓋 PM 前台在途工作時，前台正在編輯的章節可能被另一 session 的派發代理人整段吸收提交，前台已寫入但未 commit 的內容（如版本記錄編號）也隨之被錯票占用。

**Action**：派發前必須執行 `ticket track conflicts`（`--version` 可省略，預設掃描全部 active 版本），禁止改回人工逐項比對——該指令已內建 `pending`/`in_progress` 兩兩交集判定與 impl→test 擴張啟發式，覆蓋範圍與判定準確度均高於人工比對：

```bash
ticket track conflicts
```

比對範圍為**當前所有 `pending`/`in_progress` 票**，不限本輪待派發各票；PM 前台自身在途工作（尚未 commit 的框架檔案編輯）比照代理人在途工作，同樣須先以 ticket 認領登記 `where.files`（見 `.claude/rules/core/pm-role.md` PM 可寫路徑範圍），使其可被本檢查涵蓋。前置提醒：`where.files` 若含目錄級宣告會被 `create`/`set-where` 發出 WARNING（PC-BAL-040），先修正為精確路徑再執行本檢查，避免目錄級宣告造成過度序列化誤判。

只需確認**本輪待派發的特定幾票**是否互撞時，改用針對性查詢，免人工在全量輸出裡逐行找：

```bash
ticket track conflicts --among <id1>,<id2>,...   # 僅比對指定票組彼此之間
ticket track conflicts --for <id>                # 列出該票與其他 pending/in_progress 票的全部衝突對
```

兩者預設隱藏純目錄層級宣告命中（噪音來源，如票面填 `.claude/hooks/` 會與該目錄下任何檔案宣告配對），需 `--include-heuristic` 才顯示；全量模式（不帶 `--for`/`--among`）行為不受影響。

輸出 exit code 1（偵測到衝突）時，逐組交集依下表二擇一：

| 情境 | 動作 |
|------|------|
| 兩票 `where.files` 有交集，內容可拆分 | 拆分為互斥的檔案落點（如各自獨立測試檔，事後視需要合併） |
| 兩票 `where.files` 有交集，內容不可拆分 | 改序列派發：待前票 commit 完成後才派後票 |

exit code 0（無衝突）時方可依原計畫並行派發。指令用法、判定規則、`[heuristic]` 標記語意見 `.claude/skills/ticket/references/track-command.md`「track conflicts 子命令」；完整案例與根因見 `.claude/error-patterns/process-compliance/PC-BAL-008-shared-git-index-sweeps-parallel-agent-staged-files.md`「變體：檔案級共用」章節。

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

### 派發 prompt 依權威骨架執行、不重述 ticket 已載欄位（強制）

> **來源**：一次代理人越界事件的實證比對（明示邊界的派發無越界，缺聲明的派發出現越界）確立「派發時明示邊界可防越界」；後續一輪骨架收斂分析發現「逐項複製 `where.files` 為允許/禁止清單」的實作方式正是派發 prompt 重述比例離散的根因之一，邊界防護改由讀取 ticket 指引傳遞，不再要求 prompt 逐項複製。

所有派發 prompt（並行或單一）必須依 `.claude/references/agent-dispatch-template.md`「骨架（權威版）」開場，並遵守同檔「prompt 不重述 ticket 已載欄位」節的正面清單：

1. `Ticket: {id}` 第一行
2. 讀取指引：`ticket track full {id}`
3. `claim {id} --as {agent_name}` 認領行
4. 一句話任務描述 + 依 Context Bundle 執行的指標句（禁逐字複製 `how.strategy` / `acceptance` / `where.files` 內容）

並行派發時，範圍限制一律以指標句表達（「範圍限定於本 ticket `where.files`，不得觸碰其他並行 Ticket 檔案」），不逐項列舉允許/禁止清單。

> 完整骨架、變體與填寫要點：`.claude/references/agent-dispatch-template.md`

### PM 建立衍生票掛載執行中 ticket（已工具化，非文件條款）

`ticket create --source-ticket` 於 source 狀態為 `in_progress` 時已自動印出 WARNING，並建議改掛其上游（附 `--parent` 建議，若 source 有 parent_id）；命中時機在建票當下，早於執行者 complete 時才撞到「有未終結 spawn」檢查。本條款的存在理由已從「提醒 PM 記得告知執行者」轉為「說明工具的既有行為」——告知義務原依賴 PM 記憶，現由工具在建票路徑上強制顯示。

**Action**：PM 建立衍生票時依提示改掛更上游的票（如該票的父票或來源 ANA），而非正在執行的那一張。其餘「PM 對執行中票的結構性修改」情境不需專門條款：改 `acceptance` 見 `.claude/error-patterns/process-compliance/PC-BAL-034-injected-context-supersedes-existing-acceptance.md`（PM 補注入 context 覆蓋既有 acceptance 的漂移模式）；改 `status` / 加 `blockedBy` 屬異常操作，非常態流程，不需要告知規則。

### 派發 prompt 必含精準 git staging（並行 commit 場景，強制）

> **來源**：PC-092 — 2026-04-18 W5-043 並行派發事件，四個 thyme-python-developer 代理人併發 `git add .`，導致 batch 3 的 6 個檔案被 batch 4 代理人一併 staged + commit，commit 訊息標 batch 4 但實際 diff 含 batch 3 + 4。

當並行派發的代理人各自執行 `git commit` 時，prompt 必須明示精準 staging，且防護必須延伸到 commit 階段本身：

| 要求 | 正確 | 錯誤 |
|------|------|------|
| staging 路徑 | 逐一列出 `where.files` 的精確路徑 | `git add .` / `git add -A` |
| 範圍邊界 | 僅 staging 本 Ticket 的 `where.files` | 任何廣域符號 |
| commit 階段 | 精確 `git add` → `git diff --cached --name-only` 核對 → 裸 `git commit`（不帶 pathspec / `--only` / `-o` / `-a`）；高競爭路徑改用隔離索引（`GIT_INDEX_FILE` + plumbing，見 `bash-tool-usage-rules.md` 規則七與 details「隔離索引提交」） | `git commit -m "訊息" -- <路徑>`（pathspec 形式：丟棄既有 index、以 working tree 內容重建，會吸入他人同路徑未 stage 的編輯）；`git add .` 後裸 commit |

**為何精準 `git add` 仍不足**：共享 working tree 下 git index 亦為共享。精準 `git add` 只保證「自己這次 staging 的內容正確」，但 `git commit` 若不帶路徑，提交的是整個 index 當下的內容——其他並行代理人已 `git add`、尚未 `git commit` 的變更會被一併吸收進本次 commit。staging 階段防護與 commit 階段防護是兩個獨立環節，前者不能替代後者。

**條款缺口成因（Why）**：現行防護長期只涵蓋 index.lock 競爭，因為這類失敗有明確錯誤訊息可攔——CLI 會 exit 並印出警告，使用者必然注意到。跨票 commit 吸收則是零錯誤訊息的靜默 race：commit 成功、exit 0、訊息正常，只有事後比對 diff 才看得出範圍不對。防護條款的覆蓋範圍往往跟隨「曾經被觀察到的失敗」，而靜默失敗不產生觀察事件，這正是本條款遲至跨票吸收被實測發現才補上的原因；日後新增防護條款時應主動排查是否還有其他尚未被觀察到的靜默失效模式，而非只補已發生過的案例。

**範例 prompt 片段**（示範上述原則的具體套用；實際派發直接複製 `.claude/references/agent-dispatch-template.md`「精準 staging 制式句」的固定措辭，不需自行改寫）：

```
    git add .claude/agents/sassafras.md .claude/agents/mint.md
    git diff --cached --name-only   # 只能含上列兩檔；多出者 git restore --staged <path>
    git commit -m "..."             # 裸 commit；禁 -- <paths> / --only / -o / -a
禁止：
- git add . 或 git add -A（併入其他並行代理人的修改）
- git commit -m "..." -- <paths>（pathspec 形式丟棄 index、吸入他人同路徑未 stage 編輯，規則七）
被掃入時：停手、記錄 SHA 與檔案清單、上報 PM；禁 revert / reset --soft / amend / 反向套用。
```

> **歷史註記**：本段 4.11.0–4.24.0 曾以 path-limited commit（`git commit -- <paths>`）為主防護，後經實測推翻（pathspec 形式對同一路徑上他人未 stage 的編輯無隔離，且丟棄既有 index），由 `bash-tool-usage-rules.md` 規則七明文禁止。現行兩層制：一般代理人派發採「精確 add + 核對 + 裸 commit」；PM 收尾、ticket CLI 等高競爭路徑採隔離索引（完整性三要件見 `bash-tool-usage-details.md`）。

**新增檔案同樣需精確 `git add`**：untracked 新檔（新建 Ticket md、新增測試檔等）不會出現在 `git diff --cached`，漏 add 即漏提交；裸 commit 前的核對步驟以 `git status --porcelain` 一併確認無本票 untracked 殘留。

**核對步驟的邊界**：`git diff --cached --name-only` 核對與裸 commit 之間仍有 TOCTOU 窗口（PC-BAL-008 實證五）——`ticket track complete` 的 auto-stage 或他票 `git add` 可在其間塞入檔案。一般派發接受此殘餘風險並以「被掃入即停手上報、禁還原」收尾；不可接受殘餘風險的路徑（PM 收尾、CLI 自動提交）改用隔離索引，且檔案清單不得取自共用 index（三要件第一條）。

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

> **完整規則**：`.claude/references/parallel-dispatch-worktree-details.md`（按需讀取，含風險分級表、worktree 派發注意事項、Redirect 派發反模式禁令、並行場景路徑區分、bgIsolation: none 並行安全建議）。

---

## 嵌套派發整合條款（嵌套協議 v2 與並行規則的互動）

> **協議權威來源**：嵌套派發協議 v2 定義於 `.claude/agents/AGENT_PRELOAD.md` 規則 9（D1 ticket 主通道三階段表、D2 descend/ascend 決策速查、D3 `can_descend()` 層級自覺），完整設計依據與決策脈絡記錄於該規則本身。本章節**不複寫**該協議的條件表，只規範嵌套場景與本文件既有並行規則（`.claude/` 並行數限制、PC-092 精準 staging、worktree 隔離）的互動口徑。

### 嵌套層並行數計算口徑（`.claude/` 限制跨層累計）

**核心規則**：`.claude/` 修改類並行數限制（worktree 模式 ≤ 2，見 `.claude/references/parallel-dispatch-worktree-details.md`「`.claude/` 修改類並行數限 ≤ 2」章節）以「同一時刻全系統並行操作 `.claude/` 的 agent 總數」計算，**跨層累計**，不依派發層級分開計數。

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

> **完整規則**：`.claude/references/parallel-dispatch-agent-lifecycle-details.md`（按需讀取，含選用準則決策表、兩機制差異對照，以及下方「idle agent 回收 SOP」的完整內容）。

---

## idle agent 回收 SOP（W1-008 ANA 落地）

> **完整規則**：`.claude/references/parallel-dispatch-agent-lifecycle-details.md`（按需讀取，含 idle_notification 語意、續用/放生二分判準、主題聚焦維度、SOP 流程、範本）。本節處理**票已 completed** 但 teammate 仍 idle 的回收；票仍 `in_progress` 時改走下一節。

---

## in_progress 票 teammate idle 逾時判準（強制）

> **與上節分野**：上節處理票已 `completed` 但 teammate 仍 idle 的回收；本節處理票仍 `in_progress`、teammate idle、且無任何後續產出的停滯偵測——訊號來源不同，兩節判準不互通，需分開查核。

**Why**：`in_progress` 票的代理人若以背景模式啟動長測試（如全套件 baseline）後轉入 idle 等待，PM 側唯一可能收到的訊號是 `idle_notification`，其內容常為進度說明而非完成回報，且該通知僅在 spawn 時明確要求過才會送達；沒有要求時 PM 對這類停滯完全無感知。實測案例：某代理人以背景模式跑完全套件 baseline 後依規則不輪詢進入 idle，票面停在 `in_progress`、分支零 commit、工作區零修改，持續約 10 小時直到用戶主動指出才被發現，期間 PM 收到的訊號皆不指向停滯。

**Consequence**：不設逾時判準，`in_progress` 票的停滯只能靠用戶主動察覺；PM 側缺乏任何主動偵測機制，任務進度長期不動也不會觸發介入，重派或喚醒的時機完全交給運氣。

**Action**（判準與處置）：

| 判準 | 說明 |
|------|------|
| 逾時門檻 | 該票 `in_progress`，對應 teammate idle 超過 30 分鐘，且期間無新 commit、無票面 append-log |
| 查核方式 | 對照該票 `where.files` 檢查 `git log --oneline -1 -- <files>`；`ticket track full <id>` 查最後一筆 append-log 時間戳 |
| 一級處置 | `SendMessage` 喚醒，附具體下一步指令（如「背景任務已完成，請前景確認結果並繼續」） |
| 二級處置 | 喚醒後仍無回應或無新產出，`TaskStop` 後依現有派發流程重派 |

自動化偵測（掃描 dispatch 記錄、主動提醒而非等 PM 巡查）超出本節範圍，屬獨立的防護類 hook 實作，另立追蹤票處理。

---

## 跨 session 實驗器材的自我標示與存活期治理（強制）

> **完整規則**：`.claude/references/parallel-dispatch-experiment-details.md`（按需讀取，含器材定義、明示型/盲測型分兩型判準、檔名與首行雙軌標示、票面登記與存活期治理、讀者側處置、收尾強制處置）。

---

## 跨 session 同儕沉默時的接管判準（強制）

> **完整規則**：`.claude/references/cross-session-coordination-details.md`（按需讀取，含 Why/Consequence/Action 全文、發射方義務、接管訊息範例、來源引註）。本節僅保留判準表與速查路由。

本節處理平行 PM session（同專案、共享工作樹、各自有用戶指令的同儕）持票停擺時的推進判準，與 idle agent 回收 SOP（處理自己派出的 subagent）訊號來源不同——同儕 session 只查得到存活與否，查不到工作中或閒置。條件須**同時成立**而非擇一，防的是「以為它在做所以空等」與「以為它沒做所以搶著做」兩個相反方向的誤讀。**搶工**＝在對方未表態下取得該票的既成事實。

**先對號**：工作區出現無印象的狀態變化（不明變更歸屬）→ `PC-078`（停手，先問）；目標範圍內某票由同儕持有且遲遲未推進（同儕停擺）→ 本節三條件。

**發射方義務（強制）**：持有 ticket 預期長時間無產出時，必須先 `claim` 或 `append-log` 留痕——沉默方只要先留痕，下方條件 1 自動不成立，接管不會發生。

三條件（授權閘門先過，再雙通道）：

| 條件 | 判準 |
|------|------|
| 0. 同儕仍存在 | `ListAgents` 確認。已終止者不走接管流程，改走無主 ticket 清理 |
| 1. 授權閘門 | 自身有明確用戶目標涵蓋該票範圍，且依據可指認（用戶指令摘句 / 父 ticket ID / worklog 目標行） |
| 2. 證據通道 | 世界平面查證：目標 ticket 確為 pending、無 commit 痕跡、無未提交改動（讀多寫少票型此通道鑑別力退化） |
| 3. 溝通通道 | 催詢兩次未回，且訊息預告未回應時的處置；第二次須在完成一輪世界平面查證後才計數 |

任一條件不成立時的替代動作、接管訊息必含三要素（收到告知即停派/具體範圍/未 commit 以對方為準）、被接管方回歸後的處置表：見完整規則。

---

## 跨 session 同儕來訊時的脈絡存續判讀（強制）

> **完整規則**：`.claude/references/cross-session-coordination-details.md`（按需讀取）。

管上節相反方向：同儕主動來訊、訊息引用某段脈絡時，先查脈絡是否仍屬本 session——跨 session 對話 thread 以 session 為地址可達性跨 `/clear` 存續，但 context 是 at-most-once 記錄平面，任一側 `/clear` 即歸零（`tool-output-trust-rules.md` 規則 5）。

| 情形 | 處置 |
|------|------|
| 訊息引用本 session 在途脈絡 | 正常接續 |
| 無記憶脈絡，查證後已完結 | 回覆關閉訊號，不對內容承諾 |
| 無記憶脈絡，查證後需用戶決策 | 建 ticket 或指向既有 ticket，經票面追蹤 |
| 無記憶脈絡，查證後確與現任務相關 | 明示接續依據（ticket ID）後才繼續 |

兩條禁令：禁止對無記憶脈絡的訊息預設接續（未經世界平面查證前不得回應內容細節）；禁止對跨 session 對話做無 ticket 對應的回報承諾（改以「結論見票面 `<ticket-id>`」表達）。

> **本區外移時機與偵測承擔者**：本檔（`parallel-dispatch.md`）整檔行數達 PM 規則類檔案臨界值時，由 `file-size-guardian-hook.py`（`.claude/hooks/file-size-guardian-hook.py`）偵測並列入超標清單，偵測承擔者與量測單位皆為整檔。本兩節已外移完整內容至 references/，此處為速查 stub；若未來新增內容使本節篇幅回升，適用同一整區外移判準（兩節共享判準基底，外移須整區為單位）。

---

## 相關文件

- .claude/references/agent-dispatch-template.md - 派發 prompt 權威骨架與情境變體（強制引用）
- .claude/references/parallel-dispatch-details.md - 詳細規則（5W1H 格式、分析任務並行、Agent Teams 場景表、進度追蹤）
- .claude/references/cross-session-coordination-details.md - 跨 session 協調區完整規則（同儕沉默接管判準、來訊脈絡存續判讀，外移自本檔）
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

**Last Updated**: 2026-08-26
**Version**: 4.31.0 - 「跨 session 同儕沉默時的接管判準」與「跨 session 同儕來訊時的脈絡存續判讀」兩節整區外移至新建 `.claude/references/cross-session-coordination-details.md`，主文改留判準表與速查 stub（兩 H2 標題保留以維持既有錨點——`PC-076`、`tool-output-trust-rules.md`、`session-switching-sop.md` 皆以標題文字引用本兩節，不隨外移改變）；本區行數由 137 降至約 40 行；「本區外移時機與偵測承擔者」條文更新為完成式，補「未來篇幅回升時適用同一整區外移判準」一句
**Version**: 4.30.0 - 「本區外移閾值」條文改寫為「本區外移時機與偵測承擔者」：原「協調區達 200 行」為區塊級條件，但實際偵測機制 `file-size-guardian-hook.py` 只量測整檔行數，兩者粒度不符，依 decision-trigger-binding 規則 2.5「自指維護閾值須指名偵測承擔者且粒度相符」判準不合格。改為以整檔臨界值為條件（與該 hook 量測單位一致），指名該 hook 為偵測承擔者，外移動作仍以協調區整區為單位（觸發整檔瘦身時優先外移此語意自足段落）
**Version**: 4.29.0 - 移除前一版本新增的「競態窗口維度」小節與 SOP 流程圖 Step 1 對應查詢條件，還原為新增前原文。移除理由：該小節前提經查證不成立，非設計方向變更——`assigned` 欄位在程式碼中僅由 `claim` 路徑（含批次 claim）寫入 `true`，且與 `status` 轉為 `in_progress` 在同一區塊原子完成；派發動作本身不寫入 `assigned`，故不存在「`status` 仍為 `pending` 但 `assigned` 已為 `true`」的窗口期，該小節所述機制不存在於現行程式碼。既有五列判準與主題聚焦維度小節不受影響，文字未變更
**Version**: 4.27.0 - 「idle agent 回收 SOP」新增「主題聚焦維度」小節：續用/放生二分判準表補一組並列適用的主題維度列（同 Wave 同類型 pending 但跨主題時放生為預設），SOP 流程圖新增 Step 1.7 主題比對分支；定義「當前 session 持有的主題」查詢方式（依序：session-switching-sop 宣告值 → topic-assignments 對照 → 未歸屬即不擋）並註明與 session-switching-sop.md 起訖階段宣告機制的分工邊界。既有判準列文字不變，僅新增維度（現場實例：某代理人完工轉 idle 後，同 Wave 同類型 pending ticket 存在但分屬不同主題，原判準表無法推導放生結論）
**Version**: 4.26.0 - 「bgIsolation: none 並行安全建議」章節同步 PC-137 v1.2.0：並行已驗證上限由 3 擴大至 5（未測門檻由 5+ 提升至 6+）；`git add`/`commit` 共享 index 情境由「未測」改列四項實測觀察（index.lock 可重試、跨票 staged 污染頻繁、三步驟串接致誤提交、隔離索引 CAS 為高衝突解），結論不因此收緊並行數；新增「模式判別方法」段指向 PC-137「如何判別自己處於哪個模式」章節
**Version**: 4.25.0 - 「並行安全的 git commit 紀律」段移除 path-limited commit 主防護（規則七已禁 pathspec 形式），改為兩層制：一般派發「精確 add + 核對 + 裸 commit + 掃入即停手」，高競爭路徑隔離索引（三要件）；舊做法保留為歷史註記
**Version**: 4.24.0 - 「派發前 where.files 交集檢查」章節改寫：強制動作由人工逐項比對改為執行 `ticket track conflicts` CLI（內建 pending/in_progress 兩兩交集判定 + impl→test 擴張啟發式，覆蓋範圍與準確度均高於人工比對）；比對範圍由「本輪待派發各票」明文擴大為「當前所有 pending/in_progress 票，含 PM 前台自身在途工作」，並要求 PM 前台編輯框架檔案前同樣以 ticket 登記 where.files 使其可被涵蓋；來源段補一則 2026-08-18 PM 前台 vs 派發代理人跨 session 疊寫實證（PC-BAL-008 章節記錄詳情）
**Version**: 4.23.0 - 條件三與存活期治理改引用 CLI（`ticket track register-artifact` / `resolve-artifact` / `list-artifacts`）：規範原僅要求「登記三項」但格式自由發揮，收尾者需人工掃描 Solution 章節；CLI 化後登記為固定 schema（EXP-N 自動編號）、輸出可複製的首行 header 文字、`--status kept` 強制要求 `--successor`（CLI 層面阻止漏處置，非僅文件提醒），文件條款退為說明層（opinionated-default-design 主張 1 的信號落地）
**Version**: 4.22.0 - 實驗器材章節依三視角審查（品味 / 文字 / 一致性）改寫：新增「器材分兩型」（明示型適用全條款可跨 session；盲測型免檔名標示但限同一 session 收尾，因標示本身會改變被觀測方行為）、新增「讀者側處置」小節取代原條件二末段與適用範圍節的重複授權（原兩處對「發現者可否移除」給出相反指示）、存活期治理的偵測改為 `git status --untracked=all` 過濾 `experiment-` 前綴的獨立掃描（原設計只比對票面登記，漏登記者永不被偵測）、條件三登記位置定為 Solution 單一章節、刪除多餘的外移閾值豁免宣告（該區範圍定義已排除本節，兩套定義並存會在章節順序調整時給出相反答案）
**Version**: 4.21.0 - 並行安全檢查清單「派發 prompt 已明示精準 git staging 與 path-limited commit」項改為引用 `agent-dispatch-template.md`「精準 staging 制式句」固定措辭，消除各自手抄造成的措辭變異來源；「派發 prompt 必含精準 git staging」節的「範例 prompt 片段」補一句指向同一制式句（示範性質保留，複製貼上以制式句為準）
**Version**: 4.20.0 - 新增「跨 session 實驗器材的自我標示與存活期治理（強制）」章節：檔名 + 首行 header 雙軌標示格式、器材須維持 untracked（`git add` 改變被觀測對象／`.gitignore` 切斷觀測管道）、票面登記路徑與存活期、收尾時擇一處置（移除或指名接手 ticket）；反例採未標示 sentinel 遭同一 PM 三度誤判的實測樣態。本節不計入跨 session 協調區的外移閾值
**Version**: 4.19.0 - 「派發 prompt 必含職責邊界聲明（強制）」章節改寫為「派發 prompt 依權威骨架執行、不重述 ticket 已載欄位（強制）」：`agent-dispatch-template.md` 骨架收斂為單一權威版後，本節同步不再要求 prompt 逐項複製 `where.files` 為允許/禁止清單，改引用權威骨架的四項開場結構與「prompt 不重述 ticket 已載欄位」正面清單；並行安全檢查 checklist 與「相關文件」條目同步更新措辭
**Version**: 4.18.0 - 「兩機制差異對照」回傳方式列補強：明示 named agent 純文字完工輸出結構性不送達 PM（idle_notification 不攜帶文字，不索回即零送達，非機率性遺失），並路由 PC-BAL-038「區辨因子」章節取樣實證（named 純文字 0/6、SendMessage 索回 6/6、unnamed 3/3）；一般 subagent 欄同步註明完工通知含 result 欄位文字直達。評估結論：既有「PM 以 SendMessage 取報告」已含索回步驟宣告，不另立新章節，僅補強語氣與實證路由
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
