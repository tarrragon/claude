# Agent Dispatch Template

> **用途**：PM 派發代理人時使用的權威 prompt 骨架，以及情境變體（並行 / 唯讀探針 / 嵌套派發等）速查集合。單一權威骨架見下方「## 骨架（權威版）」；骨架的禁重述規則見「## prompt 不重述 ticket 已載欄位（強制）」。
>
> **分檔**：收尾政策、測試入口政策、worktree 派發政策、PM 自做規則編輯、情境變體各自在同目錄的 `agent-dispatch-closeout.md`、`agent-dispatch-testing.md`、`agent-dispatch-worktree.md`、`agent-dispatch-pm-edit.md`、`agent-dispatch-variants.md`；本檔對被移走的段標保留同名標題加一行路由，〈段標〉引用不需改寫。
>
> **收斂緣由**：本文件曾同時提供三套對「prompt 是否應複製 ticket 欄位」給出相反答案的骨架——舊版「職責邊界聲明骨架」要求逐項複製 `where.files` 至「允許的產出」/「禁止的產出」清單、「三段式快速填空骨架」（W17-048 方案 F）僅用指標零重述、「短 Prompt Snippets」（PC-040/PC-065）的 `Allowed:`/`Forbidden:` 亦要求複製 `where.files`。三者並存使 PM 選任一皆合規，抽樣量測顯示派發 prompt 重述比例在樣本間離散（15%-62%，單一樣本達 55% 字元量），也使任何「prompt 與 ticket 重疊度」檢查機制必然誤報 template-compliant 的 prompt。本次收斂：三段式骨架升格為單一權威版；短 Prompt Snippets 改寫為權威版的情境變體，不再要求複製 `where.files`；舊版職責邊界聲明骨架的防越界意圖併入權威版，改用指標式表達（見下方「歷史脈絡」段）。

---

### 歷史脈絡：職責邊界聲明骨架（已併入權威版）

初版骨架源自一次代理人越界事件的實證比對：含「允許的產出」/「禁止的產出」明示清單的派發無越界，缺此聲明的派發越界寫了禁止範圍的測試。該實證確立「派發時明示邊界可防越界」本身成立，但其實作方式（要求 prompt 逐項複製 `where.files` 為允許/禁止清單）正是後續骨架收斂分析定位的重述根因之一。

**現行處置**：邊界防護改由「讀取 ticket 指引」傳遞——agent 依權威版骨架第一步讀取 `ticket track full {ticket_id}` 取得 `where.files` 正本，prompt 不再複製副本；高越界風險情境（如並行多任務，見「短 Prompt Snippets」變體）另以指標句（「範圍限定於本 ticket `where.files`，不得觸碰其他並行 Ticket 檔案」）取代逐項複製清單，防越界意圖不變、複製動作移除。

---

## 骨架（權威版）

> **用途**：PM 派發前最常用的中文對話式骨架（原稱「三段式快速填空骨架」，W17-048 方案 F）。把 context 寫入 ticket 後，直接複製以下骨架填三個空格即可派發。骨架本體（`SKELETON_TEMPLATE_NORMAL`，不含 commit 制式句）約 10 行（含一條固定句：測試與其結果為後續步驟前置的命令一律前景執行，`run_in_background` 僅限真正可並行的旁路任務）；`--commit-policy agent`（預設）另附精準 staging 短版指標句（3 行，26 行全文改冪等寫入票的「### Commit 規範」章節，見下方「精準 staging 制式句」節），最長組合 22 行（hook 提醒、worktree 搜尋句、測試入口、紅燈句全疊加；參數化守衛量測，留至少 8 行給 PM 填寫）。agent-prompt-length-guard 的 Layer 1 硬上限（30 行）**無任何豁免**——模板關鍵字只影響 Layer 2 軟提示（10-30 行缺關鍵字時的提示），不影響 Layer 1 判定；骨架實際行數與硬上限的綁定測試見 `.claude/hooks/tests/test_agent_prompt_length_guard_hook.py`。

> **機制選擇前置（0.38.0-W2-002 ANA 落地）**：呼叫 `Agent(...)` 時**預設不帶 `name` 參數**（一般 subagent）。僅當任務符合「平行派發且 Agent A 的發現會改變 Agent B 正在進行的工作」（改用 Agent Teams）或「同 Wave 有 3+ 張同類型 ticket 且預期逐一派發」（named agent 可選續用）時才加 `name`。循序一次性任務、獨立分析/實作任務一律不帶 `name`。完整選用準則決策表見 `.claude/pm-rules/parallel-dispatch.md`「派發機制選用準則」章節。
>
> **帶 `name` 的代價（W3-182 實證）**：背景 named agent 的最終回覆文字**不送達主線程**，PM 只收到 `idle_notification`。唯讀型 named agent 因此既不能落檔也無 final message，產出必然遺失，除非 prompt 明寫「以 `SendMessage({to: "main"})` 送出報告本體」。此代價使「順手給個名字方便定址」成為實質的通道變更，不是命名偏好。重派也不解決此代價——若未修正 prompt，新執行體會複製同一失效，三次觀測見 `PC-BAL-038`。通道對照見下方「交付通道速查」維度二。

> **實戰範例為歷史記錄，複製請以本節骨架為準**：下方 IMP/ANA/DOC 三則範例為過去實際派發的逐字記錄，不隨骨架後續修訂回溯改寫；派發時複製對象是「骨架（3 段）」本身，不是任一則範例。

### 骨架（3 段）

> **CLI 為單一權威**：骨架文字的權威來源是 `ticket_system/lib/dispatch_skeleton.py` 的 `SKELETON_TEMPLATE_NORMAL` / `SKELETON_TEMPLATE_REVIEW` 常數（命令實作僅 import 使用，非定義處），本節不再逐字複製維護副本，改以指令產生：
>
> ```bash
> ticket track dispatch {ticket_id} --as {agent_name}
> ```
>
> 提醒：worktree 不隔離票務寫入，實驗請用獨立 clone 或 tmp_path（詳見 `.claude/error-patterns/process-compliance/PC-GPD-030-worktree-not-isolated-for-ticket-cli-writes.md`）。
>
> 派發位置由 `--isolation {worktree,none}` 指定：`worktree` 變體的收尾句為 `ticket track commit`（於 worktree 路徑，只提交產品檔；票面由主 repo CLI 寫入並自動提交，worktree 內的票面副本是舊版本，`ticket track commit --worktree` 遇到票面會拒絕）後止步並回報 PM，complete 由 PM 於合併後在主 checkout 執行（權威為 `CLOSING_BY_ISOLATION`；見下方〈worktree 派發收尾指引：complete 由 PM 於合併後執行〉）；未帶且 where.files 含非豁免路徑時 stderr 警告。`--kind review` 骨架首行固定為 `Dispatch-Mode: readonly`（`SKELETON_TEMPLATE_REVIEW`），第二行起為 `Ticket: {id}`。需落票約束時加 `--note "..."`（寫入票的「派發日誌」章節）；審查派發改 `--kind review`（輸出不含認領/收尾的審查骨架，改用審查標的/視角/裁決問題/回報格式四欄）。兩個變體的收尾句皆要求 Solution 含 `### 自檢結果與 Phase 4 評估`（acceptance-gate 依此檢查，缺則 complete 被擋）。指令輸出即可直接複製貼入 `Agent(...)` prompt。同步保護（`.claude/hooks/tests/test_agent_prompt_length_guard_hook.py`）涵蓋兩個獨立維度，缺一不足：(1) 骨架常數是否仍命中 length-guard hook 的模板關鍵字（僅影響 Layer 2 軟提示）；(2) 骨架**實際組裝後的行數**（含 `--commit-policy agent` 短版指標句、觸及 hooks 目錄票的額外提醒）是否仍 <= PROMPT_LINE_LIMIT（Layer 1 硬上限，無豁免）——(2) 是骨架曾實際成長至 39-48 行、逐字貼入被 Layer 1 阻擋兩次後才補上的維度，任一維度漂移即測試失敗。

> **紅燈實跑行由 CLI 條件式加入**：票 type 為 IMP 且 acceptance 含測試字樣或 E1／E2 時，骨架多一行「修改產品碼前先實跑新增測試，於 Test Results 貼紅燈輸出摘要；未實跑者須標為推論」（權威為 `dispatch_skeleton.py` 的 `RED_RUN_LINE` 與 `requires_red_run`），DOC／ANA 與無測試 acceptance 的 IMP 骨架不變；PM 不需再手寫此句。

> **閘門逐檔檢查由 CLI 條件式併入收尾句**：checkout 根有合併閘門宣告（`.claude/project-integration/merge-gate.yaml`）時，若 where.files 落在帶 `changed_files` 的套件範圍內，該套件命令與命中檔會插進收尾句的 commit 之前，寫成「提交前跑閘門逐檔檢查（結束碼須為 0）：…」。這類套件只檢查本次改動檔，代理人在本機就能重現。如果沒有轉成本機要求，紅燈要到合併閘門才會出現，多佔一輪閘門名額。插進既有句子而不新增行，因為最長骨架已達 PM 填寫空間的上限。沒有宣告或沒有命中時，骨架不變。權威為 `dispatch_skeleton.py` 的 `GATE_CHECK_CLAUSE` 與 `gate_check_commands`，細節見 ticket skill `references/track-command-dispatch.md`〈閘門逐檔檢查併入收尾句〉；PM 不需再手寫格式檢查句。

> **claim 行必帶 `--as {agent_name}`**（派發身份前移，W5-005 F1a）：dispatch hook 已在派發時對無主票綁定 who.current，此行是 agent 端對稱綁定與 hook 失效 fallback；缺 `--as` 的裸 claim 不寫 who.current，收尾 `complete --as` 會因身份不符需 set-who 繞道。

> **停手上報而非定義優先序**：在只讀得到 prompt 與正本兩份文本的條件下，agent 無可靠判別依據——故不定義三方優先序表，交由 PM 裁決；裁決回票面方式見「衝突裁決回票面（PM 端）」節。

> **Edit/Write 被非專案來源拒絕時同理停手，不得改用 Bash 繞過**：被 harness auto mode classifier、permissionMode 或 OS 權限拒絕（非專案 hook）時，agent 應停手於 ticket NeedsContext 記錄並回報 PM，禁止改用 Bash 內嵌腳本（`python3 -c` / `sed` / heredoc 重寫）完成同一修改；判準見 `.claude/rules/core/tool-selection.md` 規則二。

### IMP 實戰範例（實作派發）

```markdown
Ticket: 0.18.0-W17-046.1

## 任務

擴充 TICKET_EXEMPT_AGENT_TYPES 白名單 + 補充 Hook 判別準則註解 + 新增測試。

讀取 ticket：`ticket track full 0.18.0-W17-046.1`
認領：`ticket track claim 0.18.0-W17-046.1 --as thyme-python-developer`
依 Problem Analysis 的 Context Bundle 規格實作 + commit + complete。
遇阻立即停下回報，禁繞過 Hook。
```

### ANA 實戰範例（分析派發）

```markdown
Ticket: 0.18.0-W17-043

## 任務

分析 scenario-17 AskUserQuestion 提醒在 append-log 誤觸發根因。

讀取 ticket：`ticket track full 0.18.0-W17-043`
認領：`ticket track claim 0.18.0-W17-043 --as saffron-system-analyst`
依 acceptance 產出分析報告寫入 Solution，衍生修復 ticket 後 complete。
遇阻即停回報，禁繞過 Hook。
```

### DOC 實戰範例（文件派發）

```markdown
Ticket: 0.18.0-W17-048.3

## 任務

新增 agent-dispatch-template.md「短 prompt 三段式骨架」範例區。

讀取 ticket：`ticket track full 0.18.0-W17-048.3`
認領：`ticket track claim 0.18.0-W17-048.3 --as thyme-documentation-integrator`
依 Context Bundle 設計文件結構，append Solution + commit + complete。
遇阻即停回報。
```

### 文件票實查約束句（PC-BAL-007）

**觸發條件**：文件票（DOC ticket）的產出涉及持久化型態、schema 結構、或元件接線現況的陳述（如 domain-map §3 資料契約引用欄、SPEC 資料契約文件、任何描述「某表/某元件是否已實作/已接線」的段落）。

**Why/Consequence**：並行文件票各自涉及同一底層事實時，未實查的一方會轉述舊文件或憑推論下斷言，且各自 acceptance 不驗證對方涵蓋的事實範圍，誤述只在 PM 合併期交叉比對才暴露（實證：PC-BAL-007，W10-006 誤述 loan domain 為「無獨立持久化」，同時段 W10-003 實查確認為實表）。

**Action**：prompt 必須含以下句子（可併入任務段或獨立一行）：

```
陳述持久化/schema/接線現況前必須實查（讀 DDL / grep CREATE TABLE / ls migration），
禁止轉述既有描述或推論；無法實查則標註「待 {來源票 id} 定案」（PC-BAL-007）。
```

### 既有失敗歸因約束句（PC-BAL-022）

**觸發條件**：派發任務涉及執行測試 / 建置 / lint 等可能產生失敗結果的驗收動作。

**Why/Consequence**：宣稱失敗為「既有」「與本次變更無關」若只憑因果核對（失敗檔案是否落在本次改動範圍內），無法排除環境造成的新失敗——兩者回答不同問題，此判準已在同一 session 內復發三次（PC-BAL-022）。

**Action**：prompt 必須含以下句子（可併入任務段或獨立一行）：

```
宣稱測試/建置失敗為既有狀況前，必須在乾淨 baseline 重跑同一命令並在回報中附上對照結果
（環境、命令、通過/失敗數）。無 baseline 對照的既有宣稱視為未查證（PC-BAL-022）。
```

### 測試入口

> 已移至 `agent-dispatch-testing.md`〈測試入口〉。

### 全套件由合併閘門執行，代理人只跑相關測試檔（TEST-BAL-006）

> 已移至 `agent-dispatch-testing.md`〈全套件由合併閘門執行，代理人只跑相關測試檔（TEST-BAL-006）〉。

### 派發裁示不留未定義行為約束句（PC-GPD-026）

**觸發條件**：裁示句（PM／用戶對 prompt 或 ticket 的補充指示）出現「補 X」「並補 Y」「加上 Z 的處理」句型，其中 X／Y／Z 是一個決策點的名稱而非可直接落筆的具體內容。

**Why/Consequence**：這種句子在句法上是完整的祈使句，執行者依表面文字判斷「已裁示」，會自行填入具體內容並套用就近先例，未觸發停手回報——因為裁示句本身留白，不是 prompt 與正本衝突，既有「停手上報而非定義優先序」機制未覆蓋此訊號形態。發明的答案一旦寫入正文並標上版號即取得裁決的外觀權威，下游代理人會照單全收；若發明內容恰與同文件既有先例相反（如「是否計入既有分類/總數」這類會被交叉比對的二元決策），矛盾要等事後審查才浮現，需另開稽核與簽核才能收斂（PC-GPD-026）。

**Action**：裁示句凡指名一個決策點卻未給內容時，二選一——寫出行為本身的具體內容（含是否計入既有分類/總數等下游計算屬性），或明寫「此處未定，執行者遇到時停手回報」；不得讓「指名但不給內容」的句子維持看似完整的外觀。執行者收到此類句子且該決策會影響既有分類、計數或與其他規則產生互斥/相容關係時，填空前先搜尋同文件是否有同形先例，決定與先例不同時須在改文中明寫差異與理由，不能悄悄給出相反答案；判斷不了是否屬此類留白時，比照「停手上報而非定義優先序」處理。

| 反例（指名空白，不給內容） | 正例（給內容，或明寫未定） |
|------|------|
| 「§2 進入條件改為已選定判定，**並補未選定時的呈現**」——只指名需要新增呈現，未寫呈現內容，也未寫是否計入狀態總數 | 「§2 進入條件改為已選定判定，未選定時顯示『請先選擇一項』提示且**不進入步驟表**；比照既有『未選節點』先例**計入狀態總數**」，或「§2 進入條件改為已選定判定；未選定時的呈現**尚未裁決，執行者遇到時停手回報**，不得自行決定是否計入狀態總數」 |

### 終止長時間測試後驗證子程序已退出約束句

> 已移至 `agent-dispatch-testing.md`〈終止長時間測試後驗證子程序已退出約束句〉。

### 填空檢查清單

派發前確認：

- [ ] 第一行為 `Ticket: {id}`（Hook 強制驗證）
- [ ] 含「讀取 ticket」指引（W17-048.2 軟提示檢查）
- [ ] 含 `claim {id} --as {agent_name}` 認領行（派發身份前移；agent 端對稱綁定，見骨架下方說明）
- [ ] context 已在 ticket 的 Problem Analysis / Context Bundle（不塞 prompt）
- [ ] prompt 總行數 ≤ 30 行硬上限（無豁免）；`ticket track dispatch --commit-policy agent` 預設輸出約 21-30 行屬正常範圍，非異常
- [ ] 動作描述一句話可理解（不堆疊多個動詞）
- [ ] 交付通道已確認（L3/L2: append-log+commit / L1: append-log+/tmp / L0: final message 後 PM 立即落檔）
- [ ] 文件票涉及持久化/schema/接線現況陳述時，已含實查約束句（PC-BAL-007，見上節）
- [ ] 防護類 ticket 的產生路徑盤點表已存在於 `how.strategy` / Solution（建票時產出，此處僅確認存在，格式見 `ticket-body-schema.md` 同名節；PC-BAL-035）
- [ ] 派發對象為 `.claude/` 框架檔案修改時，代理人受 `.claude/rules/core/document-format-rules.md`「引用穩定性規則」約束（禁依賴型 ticket 引用，該層已實測確認每次派發都會注入），無需 prompt 額外重複；AGENT_PRELOAD 規則 12 僅供代理人主動 Read 時參考，不構成無需重複的依據（`.claude/agents/*.md` 主文 `@-import` 已實測不會展開為內容）
- [ ] 派發任務涉及測試/建置驗收時，已含既有失敗歸因約束句（PC-BAL-022，見上節）
- [ ] 派發任務的測試段已改為「全套件由合併閘門執行，代理人只跑相關測試檔」並含局部執行回報句（命令引用〈測試入口〉；TEST-BAL-006，見 `agent-dispatch-testing.md`）；僅任務明確要求代理人跑全套件時，才改用無路徑指令（含 `-rfE`）與對帳格式（命令原文 + `--collect-only -q` 全量數 + 執行數 = 全量 - deselected + FAILED / ERROR 行不被 tail、grep 過濾）
- [ ] 裁示句是否有「補 X」「並補 Y」型句型只指名決策點、未給具體內容？若有，已補齊內容或已明寫「此處未定，停手回報」（PC-GPD-026，見上節）
- [ ] 派發的代理人會跑長時間或背景測試時，已含終止後 pgrep 驗證約束句（見 `agent-dispatch-testing.md`〈終止長時間測試後驗證子程序已退出約束句〉，含 ps 確認命中身分與等待改等已知 PID 兩句）

---

## prompt 不重述 ticket 已載欄位（強制）

> **依據**：一輪骨架收斂分析（實驗量測 + 補充實證，方法為逐單元 5-gram 覆蓋率比對 + 母體抽樣）。派發 prompt 只承載「ticket 尚未持有、且無法由 agent 讀 ticket 後自行推導」的內容；`how.strategy` / `acceptance` 等 ticket 正本內容一律改用指標句（例：「依 Context Bundle 執行」「依 acceptance 逐項驗收」），不逐字複製或改寫貼入 prompt。

### prompt 專屬欄位正面清單

以下六類為權威版骨架已涵蓋、且判定為不可下放的必要內容（補充實證：`.claude/agents/*.md` 主文以 `@` import 寫入 AGENT_PRELOAD 但未展開為代理人可見內容，實測多數代理人直接違反其讀取禁令、僅少數代理人主動用過驗收查核指令——prompt 是這些指令對代理人的**唯一有效載體**，故讀取指引、claim 行、收尾協議判定為必要而非可下放樣板）：

| 欄位 | 內容 | 不可下放理由 |
|------|------|-------------|
| ticket ID | `Ticket: {ticket_id}` 首行 | 先有 prompt 才有 agent 讀 ticket，且為 dispatch hook 解析錨點 |
| 讀取指引 | `ticket track full {ticket_id}` | AGENT_PRELOAD 未展開注入，prompt 是唯一有效傳遞路徑 |
| claim 行 | `ticket track claim {ticket_id} --as {agent_name}` | 同上；agent 端無從得知須主動 claim |
| 收尾協議 | set-acceptance / body 填寫 / complete 三命令與 `--as` 全覆蓋 | 同上；抄錯會與框架正本歧異且無仲裁規則（實測已發生一次漂移，見下方 Why） |
| 本次 commit 歸屬 | 誰 commit（agent / PM / 不 commit） | 取決於派發當下並行狀況，建票時不可知 |
| agent 能力衝突的臨時調整 | 如派發對象工具受限時的臨時變通 | 需「ticket 需求 x agent 能力」的即時判斷，無既有載體可承擔 |

### 禁止重述的內容

`how.strategy`、`acceptance` 條目、`where.files` 逐項清單一律不得複製或改寫貼入 prompt——agent 已被讀取指引要求讀 ticket 取得正本，重述形成第二份人工維護副本，副本與正本歧異時現行規則未定義以何者為準。摘要式指標句（例：「依 how.strategy 的行為三分實作」）不算重述，逐字或改寫超過一句話的核心約束算重述。

**Why**：實測已發生一次漂移——某派發 prompt 的收尾協議寫 `set-acceptance` 未帶 `--as`，與 AGENT_PRELOAD 的 `--as` 全覆蓋要求矛盾，agent 逐字依 prompt 執行並在 identity-guard usage log 留下 warn 記錄，污染 `--as` 轉強制裁決所依賴的資料。母體量測（全文 prompt 抽樣）顯示重述比例中位數為 0%（多數樣本零重述），證明零重述可行且為母體常態；本節把此常態固化為規則，防止離群樣本（單一樣本重述達 55% 字元量）再現。

**Consequence**：不遵守本節，prompt 與 ticket 正本再度分裂為兩份人工維護副本，重蹈上述漂移事故。

**Action**：派發前檢查 prompt 是否只含上表六類內容 + 骨架固定樣板（讀取指引/claim 行為 hook 軟提示要求，跨派發恆定不計入重述判定）；含 `how.strategy`/`acceptance` 逐字或改寫內容時改為指標句。

---

## 短 Prompt Snippets（PC-040 / PC-065，權威版的情境變體）

以下 snippets 是「骨架（權威版）」在特定情境（單任務極簡形式 / 並行多任務 / group coordinator / L0 唯讀型）的變體寫法，不是另一套獨立骨架。完整 context 必須先寫入 Ticket Context Bundle；prompt 只保留 Ticket ID、範圍指標（指向 `where.files`，不逐項複製，見上節）與執行指令。每個 snippet 第一行固定為 `Ticket: {id}`。

### 精準 staging 制式句（權威版，PC-092 / PC-BAL-008）

**單一權威已改為 CLI**：制式句文字的權威副本是 `.claude/skills/ticket/ticket_system/lib/dispatch_skeleton.py` 的 `STAGING_PHRASE_AGENT`（全文）與 `STAGING_PHRASE_AGENT_PROMPT`（骨架用短版指標句，命令實作僅 import 使用，非定義處），本文件不再手動維護逐字副本。取得方式：

```
ticket track dispatch <ticket_id> --as <agent_name> --commit-policy agent
```

`--commit-policy agent`（預設）於骨架末尾附上 `STAGING_PHRASE_AGENT_PROMPT` 短版指標句（3 行，逐句保留 dispatch-staging-phrase-guard-hook 判定所需的 Category A/B/C 正面片語），並**冪等寫入/更新**該票「## Problem Analysis」下「### Commit 規範」子節為 `STAGING_PHRASE_AGENT` 全文——骨架瘦身落地：26 行全文若逐字嵌入骨架會使骨架超出 agent-prompt-length-guard 的 30 行硬上限（PC-040 實測 39-48 行兩次被 Layer 1 阻擋），改為骨架只留短版指標句 + 指向 ticket 固定章節，代理人 `ticket track full <ticket_id>` 即可讀到全文。`--commit-policy pm` / `--commit-policy none` 分別輸出一行對應說明（PM 統一 commit / 本次派發不涉及 commit），不寫入 Commit 規範章節。主路徑為 `ticket track commit`（隔離索引提交 where.files 子集，全程不觸碰共用 index，從工具層消除 PC-092/PC-BAL-008 兩類根因）；裸 `git add` + `git commit` 降為 fallback，僅於新命令失敗或不可用時使用，措辭仍涵蓋三類獨立根因，缺一不足：precise `git add`（防 PC-092，廣域 `git add .` / `git add -A` 併入其他並行代理人尚未 commit 的變更）；`git diff --cached --name-only` 核對 + `git restore --staged`（防 PC-BAL-008，他人已 stage 在共用 index 的內容會被動吸收——即使 `git add` 精準，仍可能在收尾前才發現 index 裡混入非本票內容）；禁 pathspec / `--only` / `-o` 裸 commit（防丟棄既有 index、誤吸他人未 stage 的編輯，`.claude/rules/core/bash-tool-usage-rules.md` 規則七）。

以下為 `--commit-policy agent` 骨架末尾附加的短版指標句示意（如與 CLI 實際輸出不一致，以 CLI 為準）：

```
Commit: `ticket track commit <ticket-id> -m "..." -- {exact files}` (isolated index, precise staging; linked worktree: add `--worktree <abs-path>`). Scope/criteria rejection: no fallback, stop & report PM. Swept-in content: forbid revert/reset/amend, stop & report.
Environmental failure: re-run first; if it persists, fallback `git add {exact files}` -> `git diff --cached --name-only` to verify -> verified bare commit, no pathspec (forbid `-- <paths>` / `--only` / `-o` / `-a` / `git add .` / `git add -A`).
Full text: this ticket's "### Commit 規範" section (`ticket track full <ticket-id>`).
```

以下為冪等寫入該票「### Commit 規範」子節的全文示意（`STAGING_PHRASE_AGENT`，如與 CLI 實際輸出不一致，以 CLI 為準）：

```
Recommended: commit via isolated index (files must be a subset of this
ticket's where.files; never touches the shared index):
  ticket track commit <ticket-id> -m "..." -- {exact files}
In a linked worktree (files changed under a worktree dir, not the main repo):
add `--worktree <abs-worktree-path>` to the command above.
Fallback (not recommended; only if `ticket track commit` hits an environmental
failure that persists after re-running it, or is unavailable. Scope/criteria
rejections must NOT use fallback: stop and report to PM) — use precise staging + verified bare commit only (no pathspec):
  git add {exact files}
  git diff --cached --name-only   # confirm index contains ONLY {exact files}
  git commit -m "..."             # bare commit; no -- <paths> / --only / -o / -a
Forbidden: git add . / git add -A; git commit -- <paths> / --only / -o / -a
  (pathspec-style commit discards the index and rebuilds it from working-tree
   content for the given paths — it silently absorbs unstaged edits other
   sessions may have on the same path, not just already-staged ones)
Before fallback commit: git diff --cached --name-only to check staged scope; git restore --staged <path> for any non-owned file
If bare `git commit` fallback is DENYed by bare-commit-guard-hook (another
dispatch active), stop and escalate to PM; never switch to pathspec /
--only / -o / -a to get around it.
If a commit is later found to have swept in out-of-scope content (e.g. a
peer session's staged changes):
Forbidden recovery actions: git revert; git reset --soft; git commit
--amend; any "reverse apply"/reapply of the diff. None of these may be
used to undo or rewrite the commit.
The ONLY permitted actions are: stop, record the commit SHA and file
list in the ticket, report to PM.
Reason: swept-in content is diff-indistinguishable from a peer's
legitimate concurrent write in the same window, so any of the forbidden
actions above would also undo the peer's legitimate work.
```

### 單任務

> 已移至 `agent-dispatch-variants.md`〈單任務〉。

### 並行多任務

> 已移至 `agent-dispatch-variants.md`〈並行多任務〉。

### Group Coordinator

> 已移至 `agent-dispatch-variants.md`〈Group Coordinator〉。

### L0 唯讀型（Plan type）

> 已移至 `agent-dispatch-variants.md`〈L0 唯讀型（Plan type）〉。

## 交付通道速查（W5-005.12）

> 已移至 `agent-dispatch-variants.md`〈交付通道速查（W5-005.12）〉。

---

## 唯讀探針派發 SOP（PC-V1-002 防護）

> 已移至 `agent-dispatch-variants.md`〈唯讀探針派發 SOP（PC-V1-002 防護）〉。

---

## Dispatch-Plan Template

> 已移至 `agent-dispatch-variants.md`〈Dispatch-Plan Template〉。

---

## 嵌套派發（descend）派發端指引

> 已移至 `agent-dispatch-variants.md`〈嵌套派發（descend）派發端指引〉。

---

## append-log 收尾持久化驗證

> 已移至 `agent-dispatch-closeout.md`〈append-log 收尾持久化驗證〉。

---

## 衝突裁決回票面（PM 端）

> 已移至 `agent-dispatch-closeout.md`〈衝突裁決回票面（PM 端）〉。

---

## PM 自做 framework 規則編輯流程

> 已移至 `agent-dispatch-pm-edit.md`〈PM 自做 framework 規則編輯流程〉。

---

## Layer 1 自檢觸發指引

> 已移至 `agent-dispatch-pm-edit.md`〈Layer 1 自檢觸發指引〉。

---

## 共用 lib 修復派發提醒（PC-136 強制）

> 已移至 `agent-dispatch-pm-edit.md`〈共用 lib 修復派發提醒（PC-136 強制）〉。

---

## 唯讀派發豁免 worktree 強制（0.2.1-W3-269，框架 issue 36）

> 已移至 `agent-dispatch-worktree.md`〈唯讀派發豁免 worktree 強制（0.2.1-W3-269，框架 issue 36）〉。

---

## worktree 派發 base 同步指引（W1-035）

> 已移至 `agent-dispatch-worktree.md`〈worktree 派發 base 同步指引（W1-035）〉。

### worktree 派發收尾指引：complete 由 PM 於合併後執行

> 已移至 `agent-dispatch-worktree.md`〈worktree 派發收尾指引：complete 由 PM 於合併後執行〉。

---

## tests/ 修改派發 SOP（W1-051）

> 已移至 `agent-dispatch-testing.md`〈tests/ 修改派發 SOP（W1-051）〉。

---

## worktree 快照過舊防護（W2-007）

> 已移至 `agent-dispatch-worktree.md`〈worktree 快照過舊防護（W2-007）〉。

### 阻塞回報後：重派新 agent 優先於 SendMessage 恢復

> 已移至 `agent-dispatch-worktree.md`〈阻塞回報後：重派新 agent 優先於 SendMessage 恢復〉。

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

> **備用第四層：`Tool(param:value)` 權限語法（CC 2.1.178+）**。permission rules 可比對工具輸入參數，如 `Agent(model:opus)` 阻擋特定模型的 subagent 派發。**現況不啟用**：本專案派發 incident 根因均為職責邊界模糊（hook 層已覆蓋），無「模型/參數錯誤派發」案例，無痛點的預防規則是維護負債且無法驗證正確性。**啟用條件（絆腳索）**：出現「代理人以錯誤模型/參數被派發且 hook 層未攔截」的實際 incident 時，以該案例寫出可驗證的規則（評估紀錄見 1.5.0-W5-001.5）。

---

## 與 /goal 的邊界

> **設計依據**：`/goal` 與 ticket acceptance 運作層級根本不同（設計決策方案 D），不整合、平行存在。

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

# ticket acceptance 仍由以下機制負責驗收（不省略；--as 為身份申報，見「收尾 --as 全覆蓋與建票 who 對齊」章節）：
ticket track check-acceptance --all 0.19.0-W3-032.1 --as <agent-name>
ticket track complete 0.19.0-W3-032.1 --as <agent-name>
```

---

## 收尾 --as 全覆蓋與建票 who 對齊（W1-049 裁決前置）

> 已移至 `agent-dispatch-closeout.md`〈收尾 --as 全覆蓋與建票 who 對齊（W1-049 裁決前置）〉。

---

## 收尾義務標準段（W2-003）

> 已移至 `agent-dispatch-closeout.md`〈收尾義務標準段（W2-003）〉。

### 4. Solution 自檢結果子章節義務（W2-008）

> 已移至 `agent-dispatch-closeout.md`〈4. Solution 自檢結果子章節義務（W2-008）〉。

---

## 相關文件

- `.claude/pm-rules/parallel-dispatch.md` — 引用本模板為強制骨架；「派發機制選用準則」章節定義 named agent vs 一般 subagent 選用時機
- `.claude/skills/agent-team/SKILL.md` — Task subagent vs Agent Teams 快速決策表（上一層判斷）
- `.claude/pm-rules/decision-tree.md` — 代理人可編輯路徑對照表
- `.claude/rules/core/quality-baseline.md` — 規則 6 失敗案例學習原則

---

**Last Updated**: 2026-10-31
**Version**: 1.50.0 — 〈骨架（3 段）〉在紅燈實跑行說明後補「閘門逐檔檢查由 CLI 條件式併入收尾句」一段：合併閘門宣告中帶 `changed_files` 的套件，依 where.files 推出的命令插進收尾句的 commit 之前，權威為 `GATE_CHECK_CLAUSE`／`gate_check_commands`（CLI 行為變更的同 commit 文件同步）。
**Version**: 1.49.0 — 骨架同步壓縮：模板去分隔空行、短版指標句改 3 行（示意區塊逐字對應 `STAGING_PHRASE_AGENT_PROMPT`）、hook 提醒壓為 2 行、worktree 骨架新增「改行為前以改動物字面 grep 所有測試目錄（範圍見 agent-dispatch-testing.md〈相關測試檔怎麼找〉），需改的測試檔不在 where.files 內即停手回報」一句，骨架不另列目錄清單（`WORKTREE_SIBLING_TEST_LINE`）；最長組合 34 行降為 22 行，參數化守衛涵蓋全部變體。
**Version**: 1.48.0 — `agent-dispatch-testing.md`〈全套件由合併閘門執行，代理人只跑相關測試檔〉補〈相關測試檔怎麼找〉：以被改動物的字面（hook 檔名、模組名、參數的 dest 與旗標名、改動前的輸出字面）grep 所有測試目錄，命中幾個套件就各以該套件入口跑一次；寫明只憑目錄或檔名挑選會漏的兩類（同名檔分處兩套件、以被改參數作旁路的使用端）與間接執行的盲區。兩類各有一次合併閘門紅燈實例。
**Version**: 1.47.0 — 〈骨架（3 段）〉補一句路由：IMP 票 acceptance 含測試或 E1／E2 時，CLI 骨架條件式加入「修改產品碼前先實跑紅燈並貼輸出摘要」一行，權威在 `dispatch_skeleton.py`。
**Version**: 1.46.0 — `agent-dispatch-testing.md`〈測試入口〉佔位符由 `<root>`（專案根）改為 `<checkout>`（執行測試所在 checkout 的根，linked worktree 內為該 worktree 路徑），並補單檔或相關測試檔的指令示例。原定義在 worktree 內會被代入主倉庫路徑，改跑主倉庫的程式碼而 worktree 內的修改未被測到，結果照樣綠燈；新寫法與 hooks conftest 缺依賴時提示的指令字面一致。
**Version**: 1.45.0 — 〈全套件回報規格（TEST-BAL-006）〉改寫為〈全套件由合併閘門執行，代理人只跑相關測試檔〉：測試命令引用〈測試入口〉，局部執行須明寫；驗收方合併前只驗相關測試檔，complete 時讀合併閘門結束行；原對帳格式保留為「任務明確要求代理人跑全套件」例外情境與核對全套件回報之用。「填空檢查清單」對應列同步。
**Version**: 1.44.0 — 〈worktree 派發收尾指引〉由「用 finish 別名避開 complete 誤判」改寫為「complete 由 PM 於合併後執行」：隔離代理人止於 worktree commit，PM 以 set-who 後 complete 收尾且不代填自檢；開頭骨架說明句同步（用戶裁決，2026-10-14）
**Version**: 1.43.0 — 〈終止長時間測試後驗證子程序已退出約束句〉制式句開頭補兩行：測試逾時一律經 `run-with-timeout.py` 啟動、禁用 `timeout`／`alarm` 加 `exec`／背景 `sleep` 後 `kill` 單一 PID 與 `pkill`／`killall`；並新增「逾時須經包裝腳本」三明示段（逾時當下無終止動作可觸發自檢，殘留只能在啟動方式上預防；清理改用 `orphan-test-procs.py`）
**Last Updated**: 2026-10-08
**Version**: 1.42.1 — 〈阻塞回報後：重派新 agent 優先於 SendMessage 恢復〉二次審查修正：段首補原則句與「標題沿用初版情境名」說明；Action 與判準表末列對「兩個訊號都取不到」統一為直接重派（刪去與 git worktree list 同源、無增量的 ls 後援）；補兩訊號不一致時以 git worktree list 為準
**Version**: 1.42.0 — 〈阻塞回報後：重派新 agent 優先於 SendMessage 恢復〉射程由快照過舊擴為所有恢復與續用路徑（審查退回、補料後恢復、idle 續用、超時催促）：補前提事實（無變更 worktree 於完成通知送達時清除，恢復後落回主 repo）與兩個判斷訊號（完成通知 worktreePath 欄位、worktree list 比對 agent id），判準為 worktree 不在則重派；不新增「無變更一律不恢復」禁令
**Last Updated**: 2026-10-07
**Version**: 1.41.0 — 「append-log 收尾持久化驗證」Action 新增 worktree 守衛拒收多行參數時分次 append、不得壓成單行的條文：主條文為派發 prompt 明示此條，附通用偵測指令與 PC-GPD-003 引用

**Last Updated**: 2026-10-06
**Version**: 1.40.0 — 「全套件回報規格（TEST-BAL-006）」指令改為 `uv run pytest -q -rfE`，回報規格補第 4 項：有 failed 或 error 時附完整 FAILED / ERROR 行，不得被 tail、grep、grep -v 過濾；只看尾段時先 tee 留全量日誌再取尾段。動機：回報須保留失敗項與錯誤項的 nodeid，驗收方才能不重跑就定位；`-rfE` 讓摘要區固定列出兩類 nodeid（`-r` 取代預設 reportchars，單寫 `-rf` 會漏 ERROR 行）；遺失主因是 tail 行數不足或 grep 過濾。審查後修正（同版未發佈，版號沿用）：初稿誤用 `-rf` 並誤述「缺 -r 時只剩計數」，已更正。「填空檢查清單」對應列同步。
**Last Updated**: 2026-10-02
**Version**: 1.39.0 — 「既有失敗歸因約束句」後新增「全套件回報規格（TEST-BAL-006）」子節：全套件一律用無路徑指令 `(cd <pkg> && uv run pytest -q)`，回報附命令原文、`--collect-only -q` 全量數，對帳公式執行數 = 全量 - deselected，涵蓋 `N tests collected` 與 `N/M tests collected (K deselected)` 兩種摘要格式；「填空檢查清單」同步補一列。文字提醒已兩次失效，本節讓回報可對帳，與 conftest 外掛的執行當下提示互補。
**Version**: 1.38.0 — 「終止長時間測試後驗證子程序已退出約束句」補兩句：pgrep 命中時以 `ps -o command= -p <pid>` 確認命中的是測試程序本身（macOS pgrep 只排除自身與祖先，會比對到命令列含同字串的其他 shell）；需要等待程序結束時等已知 PID（`kill -0`），不以 `pgrep -f` 樣式作迴圈條件。新增 Why/Consequence 段：兩個 `until ! pgrep -f` 等待迴圈互相比對而永久空等的反例。
**Version**: 1.37.0 — 「派發裁示不留未定義行為約束句」後新增「終止長時間測試後驗證子程序已退出約束句」子節：觸發條件（派發會跑長時間或背景測試的代理人）+ Why/Consequence（終止的是自己的 shell，執行器長駐子程序不一定隨之結束，後果由並行代理人承擔）+ 句型（`pgrep -f <worktree 絕對路徑>` 驗證並附輸出）。
**Version**: 1.36.0 — 〈tests/ 修改派發 SOP〉加註已被 `.claude/pm-rules/parallel-dispatch.md`〈禁止在共用主工作樹切換或建立分支（強制）〉取代，改路由至〈派發位置判準（強制）〉；push-first 與 finish 兩節內容不變，由該判準表引用（框架 issue 101）。
**Version**: 1.35.0 — 「既有失敗歸因約束句（PC-BAL-022）」後新增「派發裁示不留未定義行為約束句（PC-GPD-026）」子節：觸發條件（裁示句「補 X」型句型只指名決策點、未給具體內容）+ Why/Consequence（執行者填空後外觀取得裁決權威，與既有先例矛盾要等事後審查才浮現）+ 正反例對照表；「填空檢查清單」同步補一列。實證來源：一次規格回寫派發裁示留白「並補未選定時的呈現」未寫內容，執行者自行決定「不另計狀態」與同規格既有先例（另一過渡行為被提升為一級狀態）矛盾，另建 `PC-GPD-026` 記錄。

**Last Updated**: 2026-09-08
**Version**: 1.34.0 — 讓號並補記本地兩項變更：其一，「元件票／畫面票的票型專屬必含項」句內「十一欄位投影」改「元件契約欄位表投影」，同步 `component-contract-design` 方法論欄位表計數去數字化；其二，「Solution 自檢結果子章節義務」節後補一句路由，指向該 skill〈派發語言〉表格的「派發 prompt 必含」列，該列僅回指本檔、不複製內容。兩項原標 1.33.1 與 1.33.0，與上游同日獨立標記的 1.33.0 撞號；兩側內容皆在本檔，本地兩項合併讓號至本版。
**Version**: 1.33.0 — 「Dispatch-Plan Template」欄位要求表 `commit policy` 列改寫：與上節「精準 staging 制式句」（`ticket track commit` 為主路徑）同步，消解檔內矛盾（該列原僅寫精確 add 三步，與上節相反）；精確 add 降為該命令失敗或不可用時的 fallback。
**Last Updated**: 2026-09-02
**Version**: 1.32.0 — 「骨架（權威版）」段「停手上報而非定義優先序」後新增一行提醒：Edit/Write 被非專案來源（harness auto mode classifier、permissionMode、OS 權限）拒絕時同理停手回報 NeedsContext，禁改用 Bash 內嵌腳本繞過，引用 `tool-selection.md` 規則二；不動 `track_dispatch.py` 骨架常數

**Last Updated**: 2026-09-01
**Version**: 1.31.0 — 骨架瘦身落地修正兩處失準敘述：(1)「骨架（權威版）」用途段刪「prompt 控制在 10-15 行，穩過 Hook 30 行上限」（`--commit-policy agent` 預設下實測 39-48 行、被 Layer 1 硬上限阻擋兩次），改為精確描述骨架本體 + 短版指標句的行數構成與硬上限無豁免的事實；(2)「同步保護」句由「只驗模板關鍵字同步」改為明示涵蓋關鍵字同步（Layer 2）與骨架實際行數（Layer 1，新增）兩個獨立維度，避免讀者誤以為 hook 對骨架有豁免。「精準 staging 制式句」節同步改寫：`STAGING_PHRASE_AGENT` 26 行全文不再直接嵌入骨架，改冪等寫入票的「### Commit 規範」子節；骨架末尾改附 `STAGING_PHRASE_AGENT_PROMPT` 短版指標句（約 6 行，逐句保留 Category A/B/C 判定所需片語）。

**Last Updated**: 2026-08-27
**Version**: 1.30.0 — 「文件票實查約束句（PC-BAL-007）」後新增「既有失敗歸因約束句（PC-BAL-022）」子節：觸發條件（涉及測試/建置/lint 驗收動作）+ Why/Consequence（因果核對不足以排除環境造成的新失敗，同一 session 內復發三次）+ prompt 逐字制式句（宣稱既有前須附 baseline 對照結果）；「填空檢查清單」同步補一列。修的是送達路徑——PC-BAL-022 原文正確且準確預測本次復發，內容不動。
**Version**: 1.29.0 — 「精準 staging 制式句」與其兩個逐字引用 snippet（單任務／並行多任務）改寫：path-limited commit（`git commit -m "..." -- <paths>`）改為精確 `git add` + `git diff --cached --name-only` 核對 + 裸 `git commit`（不帶 pathspec / `--only` / `-o` / `-a`）；`--only`/`-o` 與 `-- <paths>` 語意相同，皆丟棄既有 index 改取 working tree 全文，會吸入他人未 stage 的編輯，故一併禁用（`.claude/rules/core/bash-tool-usage-rules.md` 規則七）；新增「若裸 commit 被 bare-commit-guard-hook DENY，停手回報，不得改用 DENY 訊息建議的 pathspec 寫法」提醒；Dispatch-Plan Template `commit policy` 欄位同步改寫。歷史 1.26.0/1.7.0 版說明的 path-limited 寫法為當時記錄，不回溯改寫。
**Version**: 1.28.0 — 依 Layer 2 審查（basil-writing-critic）修正仲裁行為條文落地內容：P0（阻擋級）「衝突裁決回票面」節補可執行 Action（`append-log` 指令 + 裁決最小欄位表 + section 依 type 路由 `ticket-body-schema.md`）；P1（4 項）同節資訊優先序改原則前置、移除無錨新造詞「凌駕註記」改就地定義、骨架下方 blockquote 收斂重複動作描述僅留 Why + 路由、`tool-output-trust-rules.md` 衍生情境標題由位置編號改語意標題並補邊界段來源；P2（3 項）骨架 code block「感知」改「發現」並壓縮句長、停手上報 blockquote 改條件式表述、骨架段補「實戰範例為歷史記錄」提醒
**Version**: 1.27.0 — 落地仲裁行為條文兩處：(1) 骨架（權威版）code block 補「感知 prompt 與正本衝突時停手上報 NeedsContext、不自行選邊」制式句，並補一則 Why 說明「prompt 誤寫與 PM 正當客製在 token 層同形，agent 無判定能力」；(2) 新增「衝突裁決回票面（PM 端）」章節，明示裁決以 append-log 寫回票面，不得只存在於重發 prompt 或對話。三處實戰範例（IMP/ANA/DOC）為歷史實際派發記錄不回溯改寫，僅骨架權威版更新
**Version**: 1.26.0 — 「短 Prompt Snippets」新增「精準 staging 制式句（權威版，PC-092 / PC-BAL-008）」子節：抽出「單任務」「並行多任務」既有雛形為單一固定四行措辭（path-limited commit + `git status`/`git restore --staged` 核對），兩 snippet 改為逐字引用；「單任務」補回原缺的 Forbidden + Before-commit 兩行（PC-BAL-008 缺口：僅防主動 add 過多，未防他人已 stage 內容被動吸收）；消除措辭變異來源，parallel-dispatch.md 檢查清單同步改引用（見該檔 Version 記錄）
**Version**: 1.25.0 — 骨架收斂為單一權威版：標題移除「職責邊界聲明骨架」副標；舊版「職責邊界聲明骨架」（要求逐項複製 `where.files` 為允許/禁止清單）併入權威版並改為「歷史脈絡」段，防越界意圖改用指標式表達；「三段式快速填空骨架」升格為「## 骨架（權威版）」；「短 Prompt Snippets」改述為權威版情境變體，`Allowed:`/`Forbidden:` 逐項複製 `where.files` 的寫法改為 `Scope:` 指標句；新增「## prompt 不重述 ticket 已載欄位（強制）」章節，含 prompt 專屬欄位正面清單（六類）與禁止重述內容判準；移除僅對應舊骨架欄位（`{agent-description 引文}`／允許禁止產出）的孤兒「## 填寫要點」章節，消除死引用。收斂緣由：三套骨架對「是否複製 ticket 欄位」給出相反答案，是派發 prompt 重述比例離散的直接來源
**Version**: 1.24.0 — 「帶 `name` 的代價」段補一句直接引用 `PC-BAL-038`（重派複製失效的三次觀測），使 named-agent 章節與 L0 Fallback SOP 兩處皆能路由到觀測證據，非「更完整說明」（PC-BAL-038 已收斂為觀測記錄，模板才是權威載體）
**Version**: 1.23.0 — 「交付通道速查」併回 `PC-BAL-038` 的增量觀測：Why 補 idle 訊號反轉機制（正常關聯斷裂但訊號仍送達，最易誤讀為成功）；L0 Fallback SOP 新增第 5 步（重派前若未修正 prompt，新執行體複製同一失效）。`PC-BAL-038` 同步收斂為觀測記錄，根因改判為本檔既有條款未送達派發者 context（`PC-BAL-043` delivery gap 實例）
**Version**: 1.22.0 — 「收尾義務標準段」章節新增「建票血緣回填義務」小節：執行中建票禁止裸 `create` 只標 `--related-to`，須帶 `--source-ticket` 或改走 `add-spawn-request`（兩通道由 CLI 自動回填血緣欄位），並補判準速查表；四塊改五塊
**Version**: 1.21.0 — 「填空檢查清單」中「代理人受 AGENT_PRELOAD 規則 12 約束無需 prompt 重複」一項改述：三探針實測證實 `.claude/agents/*.md` 主文 `@-import` 不展開為內容，改指向已實測確認每次派發都會注入的 `document-format-rules.md`「引用穩定性規則」
**Version**: 1.20.0 — 「填空檢查清單」新增一列：防護類 ticket 的產生路徑盤點表存在性確認（盤點表於建票時產出並寫入 how.strategy / Solution，本清單僅確認其存在，格式權威在 ticket-body-schema 同名節；PC-BAL-035）
**Version**: 1.19.0 — 新增「唯讀派發豁免 worktree 強制（0.2.1-W3-269，框架 issue 36）」章節：prompt 首行 `Dispatch-Mode: readonly` 聲明速查 + 骨架範例 + 禁止情境 + 適用情境速查表 + 與 review mode 的 OR 關係；完整判準權威來源指向 `.claude/pm-rules/worktree-operations.md`「唯讀派發豁免 worktree 強制」節，避免雙處維護漂移
**Version**: 1.18.0 — 「worktree 派發 base 同步指引」章節新增「環境前置欄位（0.2.1-W3-274，框架 issue 46）」小節：worktree 為 git 層隔離，gitignore 排除的建置狀態不隨之而來，補派發模板「環境前置」選填欄位與填寫指引；框架層不寫任何專案專屬命令字面，指向 consumer 專案層文件；與 worktree SKILL「worktree 不含的狀態」節交叉引用
**Version**: 1.17.0 — 「worktree 派發 base 同步指引」章節新增「worktree 派發收尾指引：用 finish 別名避開 complete 誤判」小節：CC runtime worktree isolation guard 對 argv basename 誤判 bash builtin `complete` 而條件性阻擋，收尾指令改用別名 `ticket track finish`（與 complete 行為完全等價），含正確/錯誤指令範例對照
**Version**: 1.16.0 — 「交付通道速查」拆為兩個維度：維度一沿用既有 agent 能力三列，新增維度二派發形態（有無 `name`）——背景 named agent 的 final message 不送達主線程，唯一通道為 `SendMessage({to: "main"})`；明示兩維度交會處（唯讀 + named）為零通道組合。「機制選擇前置」補帶 `name` 的 Consequence（原僅有 Action，讀者無從評估違反成本）。L0 Fallback SOP 增第 4 步：久無回報先要求以 SendMessage 重送再判定失聯，`idle_notification` 不是未執行的證據（`PC-BAL-015`）。實證為 0.2.1-W3-174 的 Layer 2 派發（0.2.1-W3-182）
**Version**: 1.15.0 — 「與派發前 commit gate 的關係」章節新增「派發前 origin 同步驗證（PC-154 前置 1 延伸）」小節：worktree base 可能反映 origin/main 而非本機 HEAD，補派發前 `git push origin main` 驗證步驟，與 PC-154 前置 1 交叉引用（memory 搬遷落地，0.2.1-W3-085）
**Version**: 1.14.0 — 「填空檢查清單」新增一項：派發 `.claude/` 框架檔案修改時，代理人已受 AGENT_PRELOAD 規則 12（禁依賴型 ticket 引用）約束，prompt 不需重複交代（0.2.1-W3-093）
**Version**: 1.13.0 — 「唯讀探針派發 SOP」章節新增「parallel-evaluation 常駐審查委員免 Ticket ID 派發」條目：`basil-writing-critic` / `linux` 已列入 `TICKET_EXEMPT_AGENT_TYPES`（0.2.1-W3-010 落地），派發時直接走優先序 1，禁止借用他人 pending ticket ID 湊格式要求（PC-V1-002 案例變體二防護，0.2.1-W3-011）
**Version**: 1.12.0 — 「三段式快速填空骨架」章節新增「機制選擇前置」提示：預設呼叫 `Agent(...)` 不帶 `name` 參數，例外情境（Agent Teams / 同 Wave 續用）指向 `parallel-dispatch.md`「派發機制選用準則」章節；相關文件補交叉引用

**Version**: 1.11.0 — 「收尾義務標準段」章節擴充：新增「Solution 自檢結果子章節義務」項，收尾四塊改為含此項；實測發現 warning 被大量忽略（受眾/時點雙錯），為擴充依據
**Version**: 1.10.0 — 新增「收尾義務標準段（W2-003）」章節：set-acceptance 指令範例（--all-check / --check index 兩型）+ ticket body 填寫義務（Solution/Test Results/Exit Status）+「回覆勾選不算數，frontmatter 才是 SOT」明示提醒；引用 0.4.1-W1-001 摩擦 F3（0.4.0 W2-002/003 回覆勾選未動 frontmatter 二度擋 complete，prompt 明示後四票收斂）為 source
**Version**: 1.9.0 — 新增「worktree 快照過舊防護（W2-007）」章節：session 中途新 commit 後的派發，prompt 第 0 步強制 merge main + ls/grep 驗證目標檔案存在；阻塞回報後重派新 agent 優先於 SendMessage 恢復（無變更 worktree 被平台自動回收，恢復時 cwd 靜默 fallback 主 repo）；引用 0.3.6-W2-007 為 source
**Version**: 1.8.0 — 新增「收尾 --as 全覆蓋與建票 who 對齊」章節（W1-049 首輪裁決前置）：收尾三命令一律帶 --as、PM 建子票必帶 --who（繼承 parent who 為 false positive deny 誤傷源）、agent deny 時禁繞過須回報；/goal 章節收尾範例同步補 --as
**Version**: 1.8.0 — 派發身份前移（W5-005 F1a）：三段式骨架與三個實戰範例、嵌套 child prompt 範例均補 `claim {id} --as {agent_name}` 認領行；填空檢查清單新增對應核對項；骨架下方補 Why 說明（dispatch hook 綁定為第一道，claim --as 為 agent 端對稱綁定與 fallback）

**Version**: 1.7.0 — 新增「嵌套派發（descend）派發端指引」章節：descend 條件速查（派發端動作對照）+ dispatch-plan 嵌套欄位（parent / depth-can_descend）+ child prompt 三段式範例；協議 SSOT 引用 AGENT_PRELOAD 規則 9，深度上限數值不在本檔重複定義（嵌套派發協議 S2 落地）

**Version**: 1.7.0 — commit policy 骨架同步 PC-092 commit 階段防護：單任務與並行多任務短 prompt snippet 補 path-limited commit 形式（`git commit -m "..." -- <paths>`）與收尾 `git status` 核對步驟；dispatch-plan template `commit policy` 欄位說明補 path-limited 形式指引，交叉引用 parallel-dispatch.md PC-092 防護章節

**Version**: 1.6.0 — worktree 派發 base 同步指引（W1-035）章節新增「cc runtime worktree base 選擇邏輯（實證歸納）」與「三方案評估與選定理由」（選定方案 B，0.19.0-W1-053）

**Version**: 1.5.0 — 新增「與 /goal 的邊界」章節：層級對照表（7 維度）、不可互相取代原因（含死鎖風險）、允許搭配使用範例（W3-032.1 落地，對應 W3-032 ANA 方案 D）

**Version**: 1.4.0 — 新增「共用 lib 修復派發提醒（PC-136 強制）」章節：觸發條件表、prompt 插入範本、三層協同說明（W17-182.1 落地）

**Version**: 1.3.1 — W17-128 批次落地 W17-124 剩餘 Layer 2 違規修正：(1) P1 #7 適用範圍表新增「可省略條件」欄（5 列分別給條件）；(2) P2 #5 步驟 6 commit 標題加「（建議）」；(3) P2 #6「Layer 2 不適用情境」段落補正向陳述「上述兩類以外預設走 Layer 2，模糊場景偏向走 Layer 2 換取盲區發現」；P2 #8 屬事實陳述（W17-124 basil 報告判定可接受）無修

**Version**: 1.3.0 — 新增「Layer 1 自檢觸發指引」章節（W17-061）：觸發條件表、標準版與精簡版 prompt 末段範本、放末段的設計理由

**Version**: 1.3.0（同號第二落地——與上條為兩次獨立變更誤用同一版號；保留原號以對應 W1-046 等歷史引用，整序見 W1-080） — 新增「唯讀探針派發 SOP」章節（PC-V1-002 防護）：白名單型優先 + 三禁約束範本，固化「引用 ≠ 指派」原則（探針越權勾選 acceptance + complete 事件落地）

**Version**: 1.2.1 — 依 W17-124 Layer 2 審查（basil-writing-critic）修正 P1 違規 3 條：(1) 標題「必經步驟」改「標準步驟（6 步，跳過項需評估成本）」；(2) 步驟 1 補同 session 已讀豁免條件；(3) 步驟 3 補規範性文字 vs 事實陳述場景區分。剩餘 P1 #7（適用範圍可省略條件欄）+ 4 條 P2 排入 follow-up

**Version**: 1.2.0 — 新增「PM 自做 framework 規則編輯流程」章節（W17-124 / W17-122 ANA Layer C 落地）：6 步驟標準流程、Commit msg 標記規範、適用範圍對照、三層協同表（與 W17-125/126/127 銜接）。文字以機會成本語氣示範（dogfooding，避免 W17-122 Solution 自身違規重蹈）

**Version**: 1.1.0 — 新增短 prompt snippets 與 dispatch-plan template（W17-044）

**Version**: 1.0.0 — 初版建立代理人派發職責邊界聲明骨架（W5-044 落地，源 W5-009 方案 2）
