# 派發機制選用與 idle agent 回收詳細規則

> **定位**：本檔為 `.claude/pm-rules/parallel-dispatch.md`「派發機制選用準則」與「idle agent 回收 SOP」兩章節的完整 substance。主文保留兩章節標題為 stub 並路由至本檔，內容原樣搬移未經改寫。
> **外移紀錄**：2026-09-01 外移（熱點檔案叢集拆分，依既有叢集邊界分析定案的叢集 C）。

---

<!-- rule8-exempt: relocation:自 .claude/pm-rules/parallel-dispatch.md 逐字搬移 -->
## 派發機制選用準則（named agent vs 一般 subagent，W2-002 ANA 落地）

<!-- rule8-exempt: relocation:自 .claude/pm-rules/parallel-dispatch.md 逐字搬移 -->
> **來源**：0.38.0-W2-002 — W2-001 執行中 PM 對循序兩階段任務（star-anise → lavender）誤用 named agent（Agent tool 帶 `name` 參數）走 mailbox 機制，產生非必要的 idle 通知與 shutdown 回收步驟，並使用戶誤以為 mailbox 指真實電子信箱。實驗確認本文件、`agent-dispatch-template.md`、`agent-team SKILL.md` 三檔**零處**明確標示選用時機。

**Why**：named agent 與一般 subagent 除了「回傳方式」不同外，還牽動 idle 態回收成本（見下方「idle agent 回收 SOP」）與用戶認知風險；決策若無顯性依據，PM 容易誤選看似「更慎重」的機制，實際只是徒增複雜度。

<!-- rule8-exempt: relocation:自 .claude/pm-rules/parallel-dispatch.md 逐字搬移 -->
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
| 回傳方式 | 透過 mailbox（`idle_notification` / agent-message），PM 以 SendMessage 取報告。**純文字完工輸出結構性不送達 PM——idle_notification 不攜帶文字，不索回即零送達，非機率性遺失**（取樣實證與決策指引見 PC-BAL-038「區辨因子」章節） | 直接作為 tool result 回傳 PM context（完工通知含 result 欄位，文字直達） |
| 生命週期 | 完工後進入 idle 態，需明確 shutdown 回收（見下方「idle agent 回收 SOP」） | 完工後自動終止，無 idle 態 |
| 可重用性 | 可 SendMessage 續派新任務 | 一次性，完成即銷毀 |
| 用戶認知風險 | mailbox 一詞易誤解為電子郵件（W2-001 實證） | 無此風險 <!-- rule8-exempt: relocation:自 .claude/pm-rules/parallel-dispatch.md 逐字搬移 --> |

> 與 `.claude/skills/agent-team/SKILL.md`「快速決策表」的關係：該表回答上一層問題（Task subagent vs Agent Teams，依「Agent A 的發現是否改變 Agent B 工作」判斷）；本節回答下一層問題（在確定不需要 Agent Teams 的前提下，Task subagent 本身是否要帶 `name`）。兩表判準不重疊，依序套用：先查 agent-team 決策表定是否需要 Agent Teams，再查本節決策表定是否需要 named agent。

---

<!-- rule8-exempt: relocation:自 .claude/pm-rules/parallel-dispatch.md 逐字搬移 -->
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

### 主題聚焦維度（idle agent 續用判準）

上方判準表的既有列（Wave / type / 檔案重疊 / context 飽和 / 重複 idle agent）對「主題」全部失明——「同 Wave 同類型 pending ticket 存在」不代表「該票與當前 session 持有的主題（見上方「主題層前置」「主題持有」小節）相符」。以下新增列與既有列**並列適用（AND 關係）**：任一列指向放生即放生，唯有全部列都指向續用才續用；既有列的文字與判斷不因本節而改變。

| 條件 | 判斷 | 理由 |
|------|------|------|
| 同 Wave 有同類型 pending ticket，且其主題與當前 session 持有的主題相符，或 session 未持有明確主題 | 續用（仍受既有列如檔案重疊、context 飽和等條件約束） | 主題相符時續用不影響 session 焦點，回退既有判準列決定 |
| 同 Wave 有同類型 pending ticket，但其主題與當前 session 持有的主題不同（跨主題） | 放生（預設） | 續用會使 session 同時混雜不相干主題的變更脈絡，違反「主題層前置」一節「一個 session 一次只持有一個主題」的設計目標；「同類型」不等於「同主題」，Wave/type 兩維度對主題本身無鑑別力 |

**現場實例**（觸發本節的具體情境）：某代理人完成任務後轉 idle，PM 依原判準表 Step 1 查得同 Wave 有多張同類型 pending 任務，結果為「續用」；但這些 pending 任務分屬「規則引用清理」「Hook 測試覆蓋」等與當前 session 持有主題不同的主題，續用會使 session 從當前主題發散。原判準表對此無法給出「不可續用」的結論——這正是本節新增列所補的缺口。

**何謂「當前 session 持有的主題」與如何查詢**

Why：判準要能被執行，「session 持有的主題」須是可查證的定義，不能停留在 PM 自行感覺是否發散。

Consequence：若無明確查詢方式，PM 各自解讀「持有的主題」，本節新增列形同虛設，續用/放生決策仍落回自由心證，與新增本節的目的相悖。

Action：依序判定，命中即停止：

1. `.claude/pm-rules/session-switching-sop.md` 若已建立 session 起始時宣告持有主題的機制，以宣告值為準（截至本節定案時該機制尚未建立；建立後以其宣告介面為準，不需改動本節其餘判準）。
2. 未宣告時，以本 session 當前在途或最近完成 ticket 的主題作為代理判準：`grep "^<ticket-id>" docs/work-logs/topic-assignments.txt` 或 `ticket track board --group-by topic` 查得該 ticket 與待續用 pending ticket 各自的主題，兩者字串相符即為「主題相符」。
3. 兩張票的主題皆查無（未歸屬）時，視為「session 未持有明確主題」，本節不擋，回退既有判準列。

> **與 session 起訖階段主題宣告的分工邊界**：`.claude/pm-rules/session-switching-sop.md` 涵蓋 session **起訖**——開始時宣告持有主題、收尾時審視主題並改派（該機制截至本節定案時尚待建立）。本節（`parallel-dispatch.md`）涵蓋 session **中途**——idle agent 續用/放生的決策點。兩檔案不同、時機不同，非重複；但皆涉及「主題聚焦」，故上方步驟 1 優先採用 `session-switching-sop.md` 的宣告值，未宣告時才退回步驟 2-3 的 proxy 判準，避免兩份文件對同一決策給出不同指引。本節條文不依賴 `session-switching-sop.md` 的宣告機制即可獨立運作（步驟 2-3 為自足 fallback）。

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
              +-- 不重疊 → [Step 1.7] 核對該 pending ticket 的主題是否與當前 session 持有的主題相符（見上方「主題聚焦維度」）
                        |
                        +-- 不符（跨主題）→ [Step 2b] 放生（預設）：續用會使 session 從持有主題發散
                        |
                        +-- 相符，或 session 未持有明確主題 → [Step 2a] 續用：SendMessage 派發新任務
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

### 跨 session 殘留回收（SessionStart 掃描觸發層）

上方「idle agent 回收 SOP」的判準假設 PM 對通知範圍內的 idle agent 有觀察
與回收能力（ListAgents 可見、TaskStop 可停）。實測顯示這個假設只對**本
session 自有**的 idle agent 成立——ListAgents 只列本 session 自有
teammate，不列他 session 所屬者；對他 session 所屬者執行 TaskStop 一律
回報找不到該 task。故除 idle_notification（僅在 spawn 時要求過才會送達）
外，跨 session 殘留的 idle agent 沒有任何主動提醒管道，SOP 本身即使判準
完整也無從被觸發。

**觸發層**：`session-registry-start-hook.py` 於每次 SessionStart 唯讀掃描
`dispatch-active.json` 中 `turn_ended_at` 已設定的 entry（回合已結束的
候選，非「ListAgents 判定為 idle」——後者對跨 session 族群無鑑別力），
交叉比對 `pm-registry.json` 判定歸屬，輸出報告區塊。掃描不呼叫
ListAgents / TaskStop，也不修改任何狀態檔——這兩個互動式工具只有收到
報告的 PM/代理人對話迴圈能存取，掃描只能交叉比對持久化狀態並產出建議。

**歸屬三分 + 孤兒兩級**：

| 歸屬 | 判定依據 | PM 應執行的動作 |
|------|---------|----------------|
| 本 session 自有 | entry 的 `session_id` 等於當前 session | 依上方續用/放生 SOP，以 ListAgents 讀取 Teammates 區塊內的列（非區塊存在性）確認狀態後決定 |
| 他 session 所屬（仍存活） | `session_id` 不等於當前 session，且該 session 存在於 `pm-registry.json` 的 `sessions` 中且 `is_fresh(heartbeat_ts)` 為真 | 向該 session 發出回收請求 |
| 確定孤兒 | `session_id` 不存在於 `pm-registry.json` 的 `sessions` 中（已 SessionEnd graceful release） | 記錄為框架限制，無 session 可回收 |
| 疑似孤兒 | `session_id` 存在於 registry 但 `is_fresh()` 為假（heartbeat 逾 30 分鐘） | 先確認該 session 是否異常終止，暫不視為確定孤兒 |

**接收方須自行驗證歸屬（強制）**：實測「請求方發訊息、擁有者 session 執行
TaskStop」的路徑成立，但其前提是執行方已知該代理人屬於自己（其代理人
清單直接列出）。回收請求的接收方須以自身代理人清單驗證該名稱確實屬於
自己後才執行，不採信請求方提供的歸屬資訊——停錯的後果是終止他人仍在
使用的代理人。此要求已落在掃描的回報範本中（每筆跨 session 候選的處置
文字皆含此句），非僅記於個別 ticket 的 Solution 章節。與
`.claude/rules/core/tool-output-trust-rules.md` 規則 5「不採信對方回報，
查世界平面」一致。

**措辭要求**：回報不得暗示目標「已失效」「無效」「可刪除」。停止不是
終態——對已停止代理人發送訊息會帶完整 transcript 恢復它，故掃描語意為
「釋放被佔用的執行體」而非「清除已死之物」。

**已知限制**：擁有者 session 已結束時（確定孤兒），底層執行體是否仍在
執行未經驗證——本框架目前沒有查詢或回收路徑，這是資訊缺口而非「已確認
清除」，回報措辭需反映此不確定性。

### Wave 收尾批次放生

Wave 所有 ticket 完成後，PM 對所有仍存活的 idle agent 依序發送 `shutdown_request`。

**收尾順序**：先 complete 所有 ticket → 再對所有 idle agent 發送 shutdown_request → 最後清理 `dispatch-active.json` 的 stale entries（idle 態 agent 不觸發 SubagentStop，故記錄不會自動清理，需確認放生後手動核對）。

<!-- rule8-exempt: relocation:自 .claude/pm-rules/parallel-dispatch.md 逐字搬移 -->
> 來源：0.38.0-W1-008 ANA（2026-07-08 Wave 1 六案例回歸驗證：thyme-w1-001/002 續用、basil-w1-004 放生、thyme-w1-005/006/007 依當時 pending 票數判斷，SOP 覆蓋全部案例）。

---

**Last Updated**: 2026-09-03
**Version**: 1.1.0 — 新增「跨 session 殘留回收（SessionStart 掃描觸發層）」小節：補上 idle agent 回收 SOP 缺少的觸發層（`session-registry-start-hook.py` 唯讀掃描 `dispatch-active.json` + `pm-registry.json`），含歸屬三分（自有／他 session 存活／孤兒）+ 孤兒兩級判準表、接收方驗證歸屬強制要求、措辭可逆性要求。
**Version**: 1.0.0 — 從 `.claude/pm-rules/parallel-dispatch.md`「派發機制選用準則」與「idle agent 回收 SOP」兩章節整段外移（熱點檔案叢集拆分），內容未經改寫，僅位置搬移。
