# PC-111: PM 論述編造技術機制 + 根因淺層歸因

**Category**: process-compliance
**Severity**: High
**Status**: Protected (methodology-backed) material-traced (R5 追溯 W17-078.1) — W17-075 WRAP 深度分析後升級，防護機制整合至 `.claude/methodologies/pm-judgment-interference-map.md` v1.0.0；W17-078.1 素材溯源追溯後升級 R5
**Created**: 2026-04-24
**Source**: 2026-04-24 session W17-072/074 並行派發事件 — PM 用「兩個 thyme working memory 混淆」編造機制支撐分工決策；被用戶糾正後第一反應歸因為「我判斷錯誤 / 過度臆測」，被用戶二次糾正「任何時候都不應該把問題歸納為你的判斷錯誤或者過度臆測」。
**Updated**: 2026-04-24 — W17-078.1 素材溯源：R1「AI 合理化傾向」改寫為「素材存在但層級誤置」；新增 R5「素材跨層誤推」；觸發案例補素材溯源鏈

---

## 症狀（雙層）

### Layer A：論述編造技術機制

PM 做決策（分工、拆分、派發、風險評估）後，論述中使用「聽起來專業」的技術術語包裝決策：

| 事件情境 | 事實句型（對） | 被編造的機制句型（錯） |
|---------|--------------|--------------------|
| 派發 basil + thyme 而非兩 thyme | 「basil hook 設計職責 vs thyme lib 優化職責，memory feedback 已有分工記錄」 | 「兩個 thyme 並發會 working memory 混淆」 |
| 拆分建議 | 「cognitive-load.md 閾值 X；本任務 Y 超標 Z%」 | 「會造成認知負擔累積」 |
| 並行可行性 | 「檔案範圍不重疊：A 改 X/ B 改 Y」 | 「可能 race condition」 |
| 決策速度 | 「此決策可依 decision-tree 第 N 層直接判定」 | 「直覺告訴我應該 A」（反之亦可：事實包裝為直覺） |

決策結果**通常是對的**，但論述的技術機制**實際不存在於系統層面**（沒對應規則、API、memory feedback、檔案路徑可引用）。

### Layer B：根因歸因淺層化

當用戶糾正 Layer A 的論述錯誤時，PM 第一反應將根因歸納為**自我品質問題**：

- 「我判斷錯誤」
- 「我過度臆測」
- 「我想得太快」
- 「我應該先查再說」

這類歸因的共通特徵：主詞是「我」（屬性歸因），沒有指向**論述生成機制**（結構歸因）。看起來像承認錯誤，實際無可操作性——下次仍會犯，因為沒改變任何生成流程。

## 根因（機制層）

### R1：素材存在但層級誤置（原「AI 合理化傾向」，W17-078.1 改寫）

LLM 輸出論述時，通常**確實有素材**作為推論起點，並非憑空捏造。問題在於：素材所屬的抽象層級（如 git index 競爭、agent 各看局部）被提升到更高層次（如「working memory 混淆」），造成論述聽起來合理但機制描述失準。

與 R5 的細分關係：
- **R1** 描述的是「有素材但層級提升後失真」的廣義現象
- **R5** 描述的是具體機制——哪些素材、如何跨層、產生什麼誤推

**Why**：素材層和機制層的抽象鴻溝在輸出時不可見，論述流暢性會自動橋接。**Consequence**：讀者收到「技術性包裝」後無從追溯，防護自檢（Q1-Q3）找不到素材來源。**Action**：觸發警戒術語時執行 R5 素材溯源（見防護 A），確認素材所在抽象層級後再決定是否可用。

### R2：自信度校準失效

使用技術術語時未觸發「這個機制寫在哪？我可以引用哪個規則/API/文件/memory？」的自檢問句。結果：無事實依據的機制描述被以「科學性」包裝輸出。

### R3：事實句型 vs 機制句型分層意識缺失

兩種句型的對比：

| 句型類型 | 範例 | 支撐需求 |
|---------|------|---------|
| **事實句型** | 「basil 職責是 hook 設計（來源：agent definition + memory feedback X）」 | 可引用的檔案/規則/memory |
| **機制句型** | 「兩個 thyme 會 working memory 混淆」 | 實際系統機制（規則、API、runtime 行為） |

機制句型**聽起來更專業**，PM 下意識偏好使用。但機制句型需要實際機制支撐；無支撐就要回退到事實句型。

### R4：自責式歸因遮蔽真因

「我判斷錯誤 / 過度臆測」是**屬性歸因**——把根因放在「PM 品質」這個黑盒。它有三個問題：

1. **無可操作性**：下次該如何避免？答不出來。
2. **遮蔽機制根因**：真正該挖的是「論述生成機制為何會選機制句型」。
3. **違反 quality-baseline 規則 6**：失敗案例學習原則要求「提煉教訓固化為規則」，而不是情緒性自責。

### R5：素材跨層誤推（W17-078.1 新增）

**定義**：PM 論述編造的具體機制——存在真實素材，但素材所屬的抽象層級（實作層 / 工具層）被提升至更高抽象層（認知層 / 架構層），導致論述「有素材可追溯但機制描述失準」。

**運作機制**：

| 素材層（實際存在） | 提升動作 | 誤推至的抽象層 | 誤推產生的論述 |
|------------------|---------|--------------|--------------|
| 實作層：並行 thyme git index 競爭（PC-092 git race） | 跨層提升 | 認知層：working memory | 「兩個 thyme 並發會 working memory 混淆」 |
| 工具層：subagent 各看局部 transcript（feedback_parallel_agent_arbitration） | 跨層提升 | 認知層：working memory | 「各 thyme 的 working memory 不共享」 |
| 協作層：agent-team SKILL 的 Team 共享 state 設計 | 跨層提升 | 架構層：記憶體共用 | 「同 agent 類型共用 working memory 資源」 |

**W17-072/074 實例（跨層誤推路徑）**：

```
素材 A：PC-092 — 並行 thyme 對同一檔案的 git index.lock 競爭（實作層）
素材 B：feedback_parallel_agent_arbitration — subagent 各看局部 transcript（工具層）
素材 C：agent-team SKILL — Team 模式下 shared state 設計（協作層）
       ↓  跨層提升（未標注）
論述輸出：「兩個 thyme 並發會 working memory 混淆」（認知層）
       ↑  此層無對應文件、規則或 API 支撐
```

**為何跨層不可見**：素材與論述之間的抽象鴻溝在流暢的句子中消失；Q1-Q3 自檢（「這個機制寫在哪？」）仍能找到素材，但素材本身是對的，只是層級錯了，讓自檢無法有效攔截。

**與 R1 的細分**：R1 描述廣義現象（素材存在但失真）；R5 描述具體路徑（哪三素材、如何提升、最終誤推到哪一層）。R5 是 R1 的機制解剖版，讓防護從「找有無引用」下挖至「確認引用的抽象層級是否匹配」。

## 防護（可操作）

### 防護 A：決策論述前的句型檢查

陳述「技術機制」前自問三問：

| 檢查項 | 問題 | 不通過的處置 |
|-------|------|------------|
| Q1：機制來源 | 這個機制寫在哪個規則/文件/API/memory？ | 無引用→改事實句型 |
| Q2：引用可驗證性 | 我能說出具體的檔案路徑或規則 ID 嗎？ | 說不出→改事實句型 |
| Q3：與事實句型的等價性 | 改成「我選 X 因為 Y 職責/條款/案例」會不會同樣完整？ | 會→用事實句型，不用機制句型 |
| Q4（R5 補充）：素材抽象層級 | 找到的引用素材，它的層級（實作/工具/協作/認知/架構）和我描述的層級一致嗎？ | 層級不符→在事實句型中明示原始層級，禁止提升 |

**警戒術語清單**（出現即檢查 Q1-Q3）：

- `working memory`、`context pollution`、`race condition`
- `認知負擔累積`（泛用版，需指向 cognitive-load.md 具體閾值）
- `attention pool 污染`（需指向 PC-072/W12-002 等具體事件）
- 任何「可能會 / 傾向於 / 容易導致」的預測性機制描述

### 防護 B：被糾正時的分層挖因

禁止第一反應的自責歸因。必須分層回答：

| 層 | 問題 | 產出 |
|----|------|------|
| 1. 決策層 | 決策本身錯了嗎？ | 通常「決策對，論述錯」——先明示這個分離 |
| 2. 論述層 | 哪個句型出問題？用了哪個警戒術語？ | 具體引用論述原文的問題句 |
| 3. 生成機制層 | 為什麼我的論述生成會選那個句型？ | 機制性回答（R1-R4 任一或組合）|
| 4. 防護層 | 下次具體自檢機制是什麼？ | 可執行清單（不是「我下次小心」）|

**禁用句型對照**：

| 禁用 | 替代 |
|------|------|
| 「我判斷錯誤」 | 「我在 X 情境下輸出了 Y 論述，該論述包含無事實支撐的機制 Z」 |
| 「我過度臆測」 | 「我跳過了 Q1-Q3 自檢，直接輸出機制句型」 |
| 「我承認錯誤」 | 「決策層對、論述層錯；生成機制層的根因是 R1/R2/R3；防護是 XXX」 |
| 「我應該先查再說」 | 「此類論述必須附引用；無引用就改事實句型」 |

### 防護 C：回饋閉環

每次觸發 PC-111 情境（輸出警戒術語或被糾正為淺層歸因）後：

1. 即時修正論述（加引用或改事實句型）
2. 更新 memory feedback（記錄觸發情境與自檢結果）
3. 累積 3 次以上同類觸發 → 升級為方法論或新規則

## 與其他規則的關係

| 規則 | 關係 |
|------|------|
| `quality-baseline.md` 規則 6（失敗案例學習原則） | PC-111 是此規則的具體執行範例：流程瑕疵不回退決策（W17-072/074 派發結果保留），提煉機制為規則 |
| `ai-communication-rules.md` 規則 5（權力不對等下的對話品質） | 「Claude 自信度校準」是主體性保護的一部分；PC-111 處理的是「自信度校準失效」 |
| `document-writing-style.md`（正面陳述原則） | 「禁用『不要』改用『必須』」的同構：「禁用『我判斷錯』改用『我在 X 情境下用 Y 論述模式』」 |
| PC-066（決策品質 autopilot） | 同宗——都是 PM 跳過自檢直接輸出的問題。PC-066 關注「決策本身未經 WRAP」，PC-111 關注「論述生成未經事實驗證」 |
| PC-072（AUQ charset contamination） | 互補——PC-072 是「PM token pool 被簡體字污染」，PC-111 是「PM 論述被機制句型污染」，兩者都是論述層污染 |

## 觸發案例

### 案例 1：W17-072/074 並行派發論述（2026-04-24 初次觸發）

**情境**：PM 準備派發 W17-072（IMP-2）+ W17-074（validator bug），用戶問「不重疊就併發」。

**PM 輸出（錯）**：「無重疊，可安全並行。派發 thyme-python-developer（W17-072）+ thyme-python-developer（W17-074）——但同 agent 類型並發會造成 working memory 混淆。改派 basil-hook-architect（W17-072）+ thyme-python-developer（W17-074）。」

**用戶糾正**：「剛剛提到這個問題，可以詳細解釋嗎？」

**PM 二次錯誤**：「這個論述我是錯的」「我的判斷錯誤 / 過度臆測」。

**用戶二次糾正**：「任何時候都不應該把問題歸納為你的判斷錯誤或者過度臆測，你找到了問題，但是對於分析問題產生的原因太過輕易下判斷」。

**正確論述**（事後修正）：
- 決策層：派 basil + thyme 是對的（職責匹配）
- 論述層：用了「working memory 混淆」警戒術語，無事實引用
- 機制層：R1（素材存在但層級誤置）+ R2（自信度校準失效）+ R3（機制句型偏好）+ R5（素材跨層誤推）
- 防護：Q1-Q4 自檢 + 警戒術語清單

### 素材溯源鏈（W17-078.1 補充）

W17-072/074 事件的「working memory 混淆」論述，素材溯源結果如下：

**三個原始素材**：

| 素材 ID | 所在層級 | 素材內容 | 誤推路徑 |
|--------|---------|---------|---------|
| PC-092（feedback_git_index_lock_prevention） | 實作層 — git 操作 | 並行 thyme 對同一 git index.lock 競爭，commit 串接導致 index 鎖死 | git index 競爭 → 「working memory 競爭」（實作層→認知層跨越） |
| feedback_parallel_agent_arbitration | 工具層 — transcript 存取 | 並行 subagent 各看局部 transcript，結論互斥時需 PM 實證仲裁 | 各看局部 → 「working memory 不共享」（工具層→認知層跨越） |
| agent-team SKILL（Team 共享 state 設計） | 協作層 — agent 協作 | Agent Team 模式下 shared state 允許成員讀寫共用變數 | shared state 設計 → 「同類型 agent 共用 working memory」（協作層→認知層跨越） |

**跨層誤推路徑圖**：

```
實作層  PC-092 git index race ─────────────┐
工具層  parallel_agent_arbitration ────────┼──→ 論述：「working memory 混淆」（認知層）
協作層  agent-team SKILL shared state ──────┘       ↑ 此層無支撐文件
```

**素材本身正確**，錯誤在「三素材均屬系統底層」卻被提升至「PM 認知 working memory」層描述，形成聽起來合理但無文件支撐的論述。正確使用方式：保留素材本身的層級（「並行 thyme 有 git index 競爭風險，見 PC-092；subagent 各看局部 transcript，需 PM 仲裁」），不跨層轉譯。

## 抽象層級分析（W17-080 backfill 示範）

> 本章節為 README 模板「抽象層級分析」必填章節的撰寫示範。R5 跨層誤推案例完整展現「症狀層 → 根因層」的層級錯位。

| 欄位 | 內容 |
|------|------|
| 症狀層級 | 認知層 / 架構層（PM 論述描述「working memory 混淆」「PM 注意力資源稀缺」等認知 / 架構機制） |
| 根因層級 | 實作層（PC-092 git index）+ 工具層（subagent transcript）+ 協作層（agent-team shared state） |
| 跨層路徑 | 實作 / 工具 / 協作層 → 認知 / 架構層（向上 2-3 層，無支撐文件） |
| 防護層級 | 工具層（防護 A Q4 句型檢查）+ 協作層（PM 自檢清單）+ 架構層（pm-judgment-interference-map methodology 13 因子地圖） |
| 跨層警示 | 本 PC 素材若被引用，禁止再從「實作層 git 機制」提升至「認知層 working memory」；任何跨層論述必須先補對應抽象層的支撐文件，禁止用流暢句型自動橋接 |

## 撰寫側設計要求（W17-079 撰寫側延伸）

讀者自檢（防護 A Q4）只能在閱讀時觸發；R5 防護的長期落地需要**撰寫端的結構性引導**。下列要求作用於 SKILL / PC / 方法論的撰寫者：

| 要求 | 落地位置 |
|------|---------|
| 新建 PC 必填「抽象層級分析」5 欄位表格 | `.claude/error-patterns/README.md` 模板（W17-080 已落地） |
| compositional-writing 原則 3 顯性化「層級貼合」 | `.claude/skills/compositional-writing/SKILL.md` 原則 3 標題與粗體層級標記行（W17-081 已落地） |
| 既有 PC 追溯補欄（按需 backfill） | 延後執行，3 個月觀察 README 模板與原則 3 升級效果後決定（pending ticket，待 W17-079 Worth-It Filter C 觸發時建立） |
| Lint hook 偵測跨層誤推 | 延後評估，需 D / B' 觀察期累積證據（W17-079 Worth-It Filter F） |

## 相關文件

- `.claude/rules/core/quality-baseline.md` 規則 6 — 失敗案例學習原則（提煉機制不回退、不自責）
- `.claude/rules/core/ai-communication-rules.md` 規則 5 — 權力不對等下的自信度校準
- `.claude/rules/core/document-writing-style.md` — 正面陳述原則、二次審查強制執行
- `.claude/error-patterns/process-compliance/PC-066-decision-quality-autopilot.md` — 同宗：決策自檢缺失
- `.claude/methodologies/pm-judgment-interference-map.md` — 13 因子 × 6 層 PM 判斷干擾地圖；本 PC 對應層 1 論述生成 + 層 2 歸因；R5 對應因子 1.4（素材錯置抽象層級，W17-078.2 新增）
- Memory `feedback_pm_narrative_fabrication_and_shallow_attribution.md` — 本 PC 的 memory feedback 對應
- `docs/work-logs/v0.18.0/tickets/0.18.0-W17-078.md` — 父 Ticket：強化 PC-111 + methodology 新增 R5 整體規劃
- `docs/work-logs/v0.18.0/tickets/0.18.0-W17-075.md` — 上游 WRAP ANA：13 因子地圖產出、素材溯源起點

---

**Last Updated**: 2026-04-27
**Version**: 1.3.0 — backfill「抽象層級分析」5 欄位表格作為 README 模板示範；新增「撰寫側設計要求」章節呼應 W17-079 撰寫側延伸（W17-080 落地）
**Version**: 1.2.0 — R1 改寫為「素材存在但層級誤置」；新增 R5「素材跨層誤推」（定義、運作機制、三素材溯源鏈）；觸發案例補素材溯源鏈小節；防護 A 新增 Q4 抽象層級檢查；相關文件補 methodology + W17-078 + W17-075（W17-078.1 落地）
**Version**: 1.1.0 — Status 升 Protected；指向 `pm-judgment-interference-map.md` methodology；本 PC 對應地圖層 1 因子 1.1-1.3（R1-R3）+ 層 2 因子 2.1（R4）
**Version**: 1.0.0 — 初版；雙層症狀（論述編造 + 淺層歸因）與四層根因（R1-R4）
