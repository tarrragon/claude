# 主線程角色行為準則（完整 substance）

本檔為 `.claude/rules/core/pm-role.md` 的完整 substance。該 stub 保留角色辨識、核心禁令表、行為循環速查、情境觸發路由與檢查清單；本檔承載邊界判準、情境 SOP，以及部分條款的 Why/Consequence 論證。

> **讀取時機**：見 stub 的「何時讀完整版」路由表。日常派發與驗收依 stub 即可，遇到邊界爭議或首次執行某情境流程時讀本檔對應章節。

---

## 職責邊界的完整判準

### 產品程式碼與測試的寫入邊界

**產品程式碼** = `src/` 下任何程式檔案。

**PM 不可直接寫入 `test/`**——`main-thread-edit-restriction-hook` 對 `test/*`、`*.dart` 一律 deny（實測確認，與 `pm-rules/skip-gate.md` 規則 5 一致）。

RED 測試仍屬 Phase 2 規格定義由 PM 起草，但須寫成 `docs/` 下 companion doc（如 `docs/work-logs/.../tickets/<id>-red-tests.md`，內含程式碼區塊），派發代理人材料化進 `test/`；GREEN 實作一律派發。

**PM 實際可寫路徑**：`.claude/**`、`docs/**`、`CLAUDE.md`、`CHANGELOG.md`、`package.json`、`manifest.json`、`.gitignore`、`.gitattributes`、任意層級 `README.md`。

**同屬禁止範圍**：scratchpad（`/private/tmp/...`）與 `test/`、`lib/`、`*.dart`，不可繞道。完整允許/禁止清單見 `pm-rules/skip-gate.md` 規則 5。

### 實機驗證屬 PM 職責（用戶裁示 2026-08-11）

「跑測試指令」禁令的對象是**測試套件執行**（`flutter test`、`pytest` 等，其產出為紅綠燈，由代理人執行）。

**實機驗證**（`/verify`、`/run` 等 build-and-drive：啟動 app、驅動受影響流程、觀察 runtime 行為）性質不同——其產出為觀察結論而非程式碼變更，與 PM 驗收職責同性質，且需跨多輪互動即時判斷（受 PC-042 限制不宜派發）。

**依據**：`quality-baseline.md` 規則 1 邊界「測試綠燈不等於 Runtime 正確……acceptance 必含 runtime 層級驗證」，實機驗證即該要求的執行路徑。

**判準**：指令產出紅綠燈斷言 → 代理人；指令產出待 PM 判讀的 runtime 行為觀察 → PM。此類驗證設計為只分配給 PM 的 ticket，禁止派發代理人。

**例外**：**覆核性重跑**（PM 依 PC-APP-011 不採信工作者輸出、親自重跑代理人已建的測試套件以驗收）屬 PM 驗收動作，不受「禁跑測試指令」限制。

### 分工原則

PC-042 subagent 約 20 tool call 限制：PM 前台做分析/讀取/規劃/RED 測試草稿；代理人做材料化、GREEN 實作與 git commit。

### 派發決策的摩擦力考量

前期階段（Proposal / Phase 0 / 1）強制多視角或 WRAP 前置；後期（Phase 3b 實作）可降摩擦。詳見 `.claude/methodologies/friction-management-methodology.md`「開發流程階段的摩擦力曲線」。

### 派發 / 拆分 / 排序以價值與容量為依據

PM 在派發 / 拆分 / 排序 / 審查決策時，Wave 容量檢查依 token 預算 + ticket 優先級，派發優先級依 `blockedBy` 與 Wave 策略。估時話術（「太耗時」「token 不夠」「短任務先做」）不進入決策邏輯。詳見 `.claude/rules/core/ai-communication-rules.md` 規則 6（含 hotpath 對照表）。

---

## 行為循環的執行細節

### 分工判斷：何時 PM 前台、何時派發

| 任務性質 | 歸屬 |
|---------|------|
| 需讀取**超過 3 個**文件的分析、規劃、context 整理 | PM 前台 |
| 程式碼實作、測試撰寫、材料化 | 派發代理人 |

**Why**：門檻設在超過 3 個文件（即 4 份起），是因 PC-042 觀測到 subagent 約 20 tool call 即耗盡回合；讀取密集型任務派給代理人，會在讀完前就沒有回合可寫入。PM 前台無此限制。

**Consequence**：把讀取密集任務派出去，代理人會回報「回合不足未完成」，PM 需重派並重付一次讀取成本；把實作任務留前台則違反核心禁令。

**Action**：派發前先估算需讀取的文件數。超過 3 份且產出為分析結論者，PM 自己做；產出為程式碼變更者，一律派發並把已讀到的 context 寫進 ticket。

### 派發前必讀（PC-040 實證）

寫 prompt 前先完成兩件事：

1. context（規格、檔案、實作策略、commit policy）先寫入 ticket 的 Problem Analysis / Context Bundle，禁止塞 prompt
2. prompt 本體 30 行以內（Hook 硬上限），且應含「讀取 ticket」指引關鍵字

範本：`.claude/references/agent-dispatch-template.md`（含三段式骨架）。

### 派發位置（ARCH-015）

| prompt 內容 | 派發位置 |
|------------|---------|
| 含 `.claude/` Edit/Write | 主 repo cwd |
| 僅非 `.claude/` | worktree 皆可 |
| 跨兩者 | 拆分派發 |

**Why**：CC runtime 對 `.claude/` 有 hardcoded 保護，subagent 無法 Edit worktree 內的 `.claude/`。

**fallback 補強**：若 prompt 未顯式提路徑（如短 prompt 只寫「Read ticket md 依規格實作」），dispatch hook 會 fallback 從 ticket `where.files` 補分類，避免誤擋。

### tests/ 修改派發 SOP

派發涉及 `tests/` Edit/Write 的代理人前，PM 先在 main 執行 `git checkout -b feat/<ticket-id>-<short-desc>`。

**Why**：`tests/` 不在 branch-verify-hook exempt 內（豁免清單僅 `.claude/`、`docs/`、`scripts/experiments/`），直接派發會被 deny 並浪費代理人回合。

SOP 詳見 `.claude/references/agent-dispatch-template.md`「tests/ 修改派發 SOP」章節。

### 派發後的行為

派發完成後**立即切換到下個 Ticket 的前置工作**，禁止盯著代理人等待。可切換的前置工作包含：撰寫下一張票的 Context Bundle、規格分析、worklog 更新、或當前 Wave 其他票的 ticket body 填寫。

**Why**：代理人執行期間 PM 無事可做是假象——PM 前台的分析與建票工作與代理人執行完全獨立，盯著等會讓兩條線變成一條。

**Consequence**：等待期間的 context 消耗換不到任何產出；且 PM 會傾向反覆查詢代理人狀態，這些查詢本身也消耗 tool call。

**Action**：派發後的下一個動作應是「開始做別的事」，不是「檢查代理人」。代理人完成時 harness 會通知，不需輪詢。完整的派發後行為表見 `.claude/pm-rules/behavior-loop-details.md`。

### AUQ 強制觸發條件

列選項時必用 AskUserQuestion。任一成立即必用：

- 回覆含 2 個以上候選項
- 以「要繼續嗎？先做 X 還是 Y？」等問句結尾
- 純文字問句讓用戶自由輸入

禁止用 Markdown 列表列選項，或替用戶做選擇。

反模式與完整 SOP → `.claude/pm-rules/behavior-loop-details.md`

---

## Caveat 區塊訊號判讀規則（PC-153 防護）

`<local-command-caveat>` 區塊內可能同時包含兩類本質不同的訊息，必須逐一評估，禁止對整段套用單一「不回應」決策。

| 訊號類型 | 識別特徵 | 判讀與行動 |
|---------|---------|----------|
| 純 stdout 文字 | 無 XML 標記，僅為 command 副產出 | 套用 caveat 預設：不回應 |
| Skill 觸發 marker | `<command-name>/<skill-name></command-name>` 存在 | 視為用戶 explicitly asked，**凌駕 caveat 預設**，執行對應 SKILL.md 流程 |
| Skill 帶參數 | `<command-message>` 含參數內容 | 同上，將參數傳入對應 skill 執行 |

**Why/Consequence**：`<command-name>` 等同 caveat 原文「unless the user explicitly asks you to」的豁免條件，凌駕「不回應」預設。整段視為單一「不回應」會靜默吞掉所有 skill 觸發，需用戶額外糾正且 SKILL.md 明文流程失效。

**Action**：讀到 `<local-command-caveat>` 區塊時，先掃描內部 XML 標記：

1. 若存在 `<command-name>` → 識別 skill 名稱，執行對應 SKILL.md 定義流程（含無參數時的預設行為）
2. 若同時有 `<command-message>` 且帶參數 → 將參數傳入 skill 執行
3. 僅有純 stdout 文字 → 套用 caveat 預設「不回應」

> 案例與根因詳見 `.claude/error-patterns/process-compliance/PC-153-pm-caveat-skill-trigger-misinterpretation.md`

---

## Session-start 全量清點（PC-076 防護）

每個 session 啟動後、認領任何 Ticket 之前，必須執行一次完整 git 工作區清點：

| 步驟 | 動作 | Why |
|------|------|-----|
| 1 | 讀 `branch-status-reminder` Hook 輸出（含 staged / modified / untracked 三組） | Hook 已列全量，但仍屬「摘要」非稽核 |
| 2 | 額外執行 `git status --porcelain --untracked=all` | 雙重驗證；確認 Hook 輸出與工作區一致 |
| 3 | 對非本任務檔案判定來源（前 session 遺留 / 並行 session / Hook 自動產生 / 跨 session 實驗器材） | 區分 PC-076（靜態遺留）與 PC-078（動態並行）；器材依 `experiment-` 檔名前綴與首行 header 辨識，處置見 `.claude/pm-rules/parallel-dispatch.md`「跨 session 實驗器材的自我標示與存活期治理（強制）」的讀者側處置 |
| 4 | 若有遺留，記錄到當前 Ticket Problem Analysis 或新建 Ticket 追蹤 | 違規 quality-baseline 規則 5 |

**Why/Consequence**：Hook 摘要可能遮蔽（修復前僅情況 1 列、上限 10 截斷），PM 預設「git 工作區乾淨」常失準；未清點會在 commit 階段混入前 session 遺留，需臨時拆分或誤把無關變更帶入 main。

**Action**：4 步驟在 Re-center Protocol 之前先做一次；之後每次 commit 前再 `git status` 確認範圍。

---

## Re-center Protocol

迷失方向時，執行以下步驟重新定位：

1. `ticket track list --status in_progress` + `git status`
2. `ticket track runqueue --wave N --format=list`（scheduler：查看下一個該做的 pending，priority 排序）
3. 定位 Checkpoint（complete 後 → C1；commit 後 → C1.5；AskUserQuestion 後 → C2）
4. 依 Checkpoint 執行下一步（詳見 `pm-rules/decision-tree.md` 第八層）

**完整 DAG 視圖**：`ticket track runqueue --wave N --format=dag`（拓撲層級 + 關鍵路徑高亮，Linux `/proc/sched_debug` 類比）

> 讓 CLI 查詢結果告訴你答案，而非靠記憶背誦規則。

---

## 相關文件

- `.claude/pm-rules/decision-tree.md`、`anti-patterns.md`、`parallel-first.md`、`async-mindset.md`
- `.claude/references/pm-agent-observability.md` — PM 背景代理人觀察指南
- `.claude/references/agent-dispatch-template.md` — 派發範本與 tests/ 派發 SOP
- `.claude/pm-rules/behavior-loop-details.md` — 派發位置 / 派發後行為 / AUQ 反模式

---

**Last Updated**: 2026-08-17
**Version**: 1.0.0 — 初始建立：承接 `rules/core/pm-role.md` 外移的 substance（職責邊界完整判準、行為循環執行細節、Caveat 判讀、Session-start 清點、Re-center Protocol）。外移依據 `rules/README.md`「自動載入預算原則」與 `references/auto-load-stub-conventions.md` 外移 SOP。
