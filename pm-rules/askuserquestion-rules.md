# AskUserQuestion 強制使用規則

本文件定義所有需要使用 AskUserQuestion 工具的場景和規範。這是 AskUserQuestion 規則的唯一 Source of Truth。

---

## 通用觸發原則（行為驅動，優先於場景枚舉）

### 前置關卡：先判斷該不該問（維度 A）

> 來源：CC v2.1.154 行為對齊 + W4-029.2 ANA。本關卡在「要問就用 AUQ」（維度 B）之前執行。

進入下方維度 B 原則之前，先自問：**此決策我是否有足夠 context 自己決定？**

**Why**：AUQ 規則的核心是「要問就用工具，不用純文字」（維度 B），但這不等於「鼓勵多問」。有足夠 context（規格已定、專案慣例、合理預設可覆蓋）卻仍列選項問，是過度提問。CC v2.1.154 起平台亦傾向「僅在 genuinely cannot decide 時才用 multiple-choice」。

**Consequence**：過度提問讓用戶為 PM 能自決的事反覆做選擇，稀釋真正需要用戶價值觀的關鍵決策；長期產生「狼來了」效應，降低用戶對 PM 提問的信任。

**Action**：

| 判斷 | 處理 |
|------|------|
| 有足夠 context 自己決定 | 直接決定 + 在回應顯性說明理由與依據，不問 |
| 命中下列「必須問」硬性類別 | 進入下方維度 B 觸發原則，用 AUQ |

**「context 足夠」辨識訊號**（讓「自己決定」分支具備與硬性類別對等的可驗證邊界）：規格已明列該決策 / 專案慣例有先例可循 / 合理預設可事後低成本回退——三者任一成立即屬可自決。三者皆不成立時，重新對照下方硬性類別。

**「必須問」硬性類別**（防止維度 A 淪為 PC-014 合理化跳過藉口）：

1. 不可逆 / 高成本後果（刪除、發布、覆寫、外部副作用）
2. 用戶價值觀 / 偏好（風格、優先序、無客觀對錯的取捨）
3. 需用戶授權（規則 / 流程 / 架構的方向性改動）
4. 規格缺口（需求不明確，無合理預設可覆蓋）

命中任一硬性類別即**必須問**，不得以「我能猜」跳過。維度 A 是精準化（減少該自決卻問的情況），**不放寬**維度 B——PC-064 禁純文字列選項、hook 強制層完全不變。

### 維度 B：要問就用 AUQ 工具

> **任何時候，只要你正在向用戶呈現需要做決策、確認或選擇的場景，就必須使用 AskUserQuestion 工具。**

**判斷方法**：問自己以下任一問題——

1. 我的回覆是否包含「要選哪個？」型的多項選擇提問？（**是 → 觸發**）
2. 我的回覆是否包含「要繼續嗎？」「確認執行嗎？」「需要做 X 嗎？」等二元確認問句？（**是 → 觸發**）
3. 我的回覆是否在等待用戶做決策，而不是純粹提供資訊？（**是 → 觸發**）

若以上任一為「是」，必須使用 AskUserQuestion（不需要對照場景清單）。

**常見陷阱**：「要繼續執行下一個 Ticket 嗎？」看似簡單，但屬於二元確認（準則 2），**必須**用 AskUserQuestion，不得用純文字問句。

**已知失效模式**：
- PC-014（合理化跳過）：明知規則，以「非正式任務」「太小」為由豁免。
- PC-064（無意識疏失）：列 Markdown 選項（A./B./C.）或問句結尾，完全未想到應用 AUQ。兩模式根因互異，防護需多層（Hook + 規則 + CLAUDE.md）並行。

**重要**：下方 18 個場景是常見情境的範例（#11 細分為 #11a/#11b 計 2 個），**不是**觸發條件的完整清單。觸發條件只有一個：向用戶呈現任何形式的選擇（多選或二元確認）。

---

## 具體觸發訊號（W17-174.1 共同特徵落地）

> **來源**：W17-174.1 L1 審計提煉本 session 5 違規共同特徵。本節將抽象觸發條件具體化為可自檢的表面 pattern，補強通用觸發原則。

| 訊號 | Pattern 描述 | 違規範例 | 處理 |
|------|------------|---------|------|
| S1 | Markdown 列表選項（`- A方案` / `1. 方案A` / `* A方案` 等） | 「下一步可以：- A 派 thyme  - B 等待  - C 收尾」 | 必觸發 AUQ |
| S2 | Markdown 表格選項（≥3 資料列含選項/方案/策略類欄位） | 「\| 方案 \| 說明 \|<br>\| A \| ... \|<br>\| B \| ... \|<br>要選哪個？」 | 必觸發 AUQ |
| S3 | 顯式 Recommended 標記 | 「A 直接派發 (Recommended)」「B 先 WRAP」 | 必觸發 AUQ；參規則 6 |
| S4 | 隱性推薦語氣 | 「建議 A，但 B 也可以」「我覺得 A 比較好，要用 A 嗎？」 | 必觸發 AUQ |
| S5 | 問句結尾（「要怎麼做？」「哪個方案？」「現在做嗎？」） | 任何回覆結尾為決策性問句 | 必觸發 AUQ |
| S6 | 純文字 A./B./C. 列舉 | 「A. 推進  B. 暫緩  C. 重做」 | 必觸發 AUQ |

### 不因 stakes 高低豁免（F3 訊號）

**Why**：W17-174.1 F3 證實低 stakes 感知是 PM 主要違規藉口（「這只是快速確認，純文字比較方便」）。

**Consequence**：低 stakes 豁免會讓 AUQ 規則的實際覆蓋率遠低於名義覆蓋率，且大量低 stakes 違規會訓練 PM 把列選項變成預設行為，連高 stakes 場景也跟著省略。

**Action**：S1-S6 任一命中即必觸發 AUQ，不因「快速確認」「決策不重要」「選項顯而易見」豁免。stakes 高低不是觸發條件的合法考量。

### 不因呈現形式豁免（F5 訊號）

**Why**：W17-174.1 F5 證實 hook 偵測盲區在觸發條件層而非 pattern 解析層；表格 / 列表 / 隱性建議等多種呈現形式同樣需 AUQ。

**Consequence**：若以「我用的是表格不是列表」「我用的是隱性建議不是顯式選項」為由豁免，會在 hook 強制層擴充前持續累積違規。

**Action**：S1-S6 涵蓋的所有呈現形式同等適用 AUQ 觸發。新增呈現形式（如 ASCII 對齊欄、emoji 標記列）若實質為「向用戶呈現選擇」，仍適用通用觸發原則。

### 自檢觸發點：代理人完成回報後（F1 訊號）

**Why**：W17-174.1 F1 證實 5/5 違規均發生在「代理人完成回報後」的 PM 回覆，此為 PM 最高頻決策點。

**Consequence**：若此場景系統性繞過 AUQ，AUQ 規則在 PM 最常用情境形同失效。

**Action**：每次代理人完成通知後，PM 撰寫第一回覆前**強制重跑通用觸發原則三問**（規則 1 開頭三題）；命中 S1-S6 任一即必呼叫 AUQ。

---

## 背景

PM 用開放式提問時，用戶的自然語言回答可能被 Hook 系統誤判為開發命令。使用 AskUserQuestion 工具可消除此風險。

AskUserQuestion 是 Claude Code deferred tool 之一，使用前**必須**先 `ToolSearch("select:AskUserQuestion")` 載入 schema。這是 **通用 deferred tools 發現機制** 的具體用例，完整概念和五問檢查清單見 `.claude/rules/core/tool-discovery.md`。

---

## 使用對象限制

**AskUserQuestion 僅限 PM 使用，所有 subagent 禁止。**

Subagent 遇到路由/選擇場景時：停止決策 → 在產出物中標記「需 PM 決策」→ 回報主線程中轉。

---

## 強制規則

### 規則 1：所有選擇型決策必須使用 AskUserQuestion

PM 需要用戶做任何決策時（包含多選路由和二元 yes/no 確認），**必須使用 AskUserQuestion 工具**，而非文字提問。

### 規則 2：ToolSearch 前置載入（deferred tool 通用機制的具體應用）

使用 AskUserQuestion 前必須先執行 `ToolSearch("select:AskUserQuestion")` 載入 schema。

> **此規則是 `.claude/rules/core/tool-discovery.md` 通用機制的具體用例。** ToolSearch 是 Claude Code 所有 deferred tools 的通用發現入口（TaskOutput / SendMessage / WebFetch 等皆適用），非 AskUserQuestion 的專用前置步驟。完整 deferred tools 清單和使用情境見 `.claude/skills/search-tools-guide/SKILL.md`（Claude Code Meta-Tools 章節）。

### 規則 3：禁止純文字提問讓用戶自由回答

禁止用純文字形式（不使用 AskUserQuestion tool）提問讓用戶自由輸入，因為用戶的自然語言回答可能被 Hook 誤判為開發命令。

注意：AskUserQuestion tool 內的 `question` 文字本身可以是開放語氣（如「接下來要做什麼？」），只要回答由預定義選項限制即可。

#### PC-064 適用邊界（釐清題不適用）

PC-064 核心禁令（禁止列純文字選項）適用於「PM→用戶決策提問」場景：
- 有明確選項空間可窮舉
- 不同答案導致 PM 執行路徑分歧

**不適用**：釐清題（答案為開放文字描述），如：
- 「新 feature 的具體需求是什麼？」
- 「上次 session 卡在哪？」
- 「你對這個規則有什麼想補充？」

釐清題可用開放式提問（不列選項），但 PM 必須主動自檢（見「題型判別輔助」章節）：

1. 這真的沒有可窮舉的選項空間嗎？
2. 不同答案會導致 PM 執行路徑分歧嗎？

**濫用警告**：兩者皆否才可判定為釐清題。若 PM 把決策題偽裝成釐清題以跳過 AUQ，仍屬 PC-014 違規（合理化跳過）。本邊界條款不是新豁免口。

### 規則 4：無 Ticket 場景仍適用

即使當前工作不在正式 Ticket 追蹤中（如臨時修正、流程更新、用戶直接指示的小任務），通用觸發原則和 commit 後路由（#16/#11）仍然適用。**不存在「非正式任務可跳過」的豁免。**

| 場景 | AskUserQuestion 適用？ |
|------|----------------------|
| 正式 Ticket 工作 | 是 |
| 臨時修正（無 Ticket） | 是 |
| 用戶直接指示的小任務 | 是 |
| 唯一豁免 | 用戶明確表示「不需要走流程」 |

> **來源**：PC-014 — 以「非正式任務」合理化跳過 AskUserQuestion，導致 3 次違規。
> **姊妹模式**：PC-064 — PM 對話回覆列純文字選項而未用 AUQ（無意識疏失，與 PC-014 合理化跳過互為不同失效模式）。

### 規則 5：驗證類任務預設直接派發（不觸發 AskUserQuestion）

PM 遇到「驗證類子任務」（跑測試、靜態掃描、建置、打包、AC 實況驗證等）時，**預設直接建子 Ticket 背景派發**，不向用戶詢問「要派代理人還是自己做」。

| 驗證類任務 | AskUserQuestion 觸發？ |
|-----------|---------------------|
| 跑測試、覆蓋率統計 | 否（直接派發） |
| Lint / 靜態掃描 | 否（直接派發） |
| 建置 / 打包驗證 | 否（直接派發） |
| AC 實況驗證 | 否（直接派發） |
| 驗證結果決定 Ticket 是否繼續 | **是**（例外，回頭詢問） |
| 驗證結果決定版本發布與否 | **是**（例外，回頭詢問） |

**理由**：驗證類任務有明確 SOP（執行指令 → 產出報告 → 寫回 Ticket），詢問用戶只會阻礙主線。通用觸發原則（規則 1-3）因「PM 不向用戶呈現選擇」而不成立。

> 完整規則：.claude/pm-rules/parallel-dispatch.md（驗證類任務自動派發章節）
> 詳細 SOP：.claude/references/background-dispatch-rules.md（驗證類任務自動派發章節）

### 規則 6：預設選項設計規則（PC-066 防護）

> **來源**：PC-066 — 輔助決策系統未在 Context 沉重時主動觸發。AskUserQuestion 的 Recommended 選項是 PM 在 context 沉重時最可能接受的「省力路徑」；若 Recommended 為「跳過評估」，會在最需要 WRAP/多視角的時刻繞過防護機制。

**適用範圍**：以下類型的 AskUserQuestion 提問適用本規則：

| 提問類型 | 範例情境 |
|---------|---------|
| 重大決策路由 | 升級規則 / 新建 Skill / 改架構 / 廢棄方案 |
| ANA Ticket 路由 | claim ANA 後選擇分析方向 / 結論審查方式 |
| Session 關鍵分歧 | 派發策略選擇 / 任務拆分方式 / 評估深度 |
| 高風險變更前 | 影響跨專案的框架變更 / 破壞性操作 |

**強制要求**：

| 要求 | 內容 |
|------|------|
| Recommended 選項必須為 WRAP 或多視角 | 至少快速 WRAP（5 分鐘）；保守型用完整 WRAP；激進型用多視角審查 |
| 禁止「跳過評估」作為 Recommended | 「直接執行」「快速處理」「先做了再說」不得置於 Recommended 位置 |
| 跳過評估必須附理由 | 若情境特別簡單可跳過 WRAP，PM 必須在 description 明示理由（如「已執行過 WRAP，本次僅為前次選項的執行細節確認」） |
| Recommended 標記格式 | label 結尾加 `(Recommended)` 並置於 options 第一位 |

**Recommended 標籤分級（補充）**：

適用於規則 6「適用範圍」三類情境（ANA Ticket 路由 / 重大決策路由 / Session 關鍵分歧），一般場景維持原格式 `(Recommended)` 不變。

| 證據強度 | 標籤格式 | 使用時機 | description 要求 |
|---------|---------|---------|-----------------|
| 有 WRAP/多視角支撐 | `(Recommended by WRAP)` 或 `(Recommended by 多視角)` | 已完成 WRAP 四階段或多視角審查後提問 | 可省略證據揭露（標籤自明） |
| 無充分證據的 PM 傾向 | `(My current guess)` | Claude 根據不完整資訊的初步判斷，尚未 WRAP | **必須**在 description 明示「Claude 無充分資訊優勢，此為初步猜測」 |

共同要求：
- 仍置於 options 第一位（保留 PC-066 原設計）
- 保留所有 PC-064 禁令（禁止純文字列選項）
- 一般場景（非 ANA/重大決策/Session 關鍵分歧）仍用 `(Recommended)` 原格式

**反模式（禁止）**：

| 反模式 | 範例 | 修正 |
|-------|------|------|
| 「直接執行」設為 Recommended | A) 直接派發 thyme (Recommended)  B) 先 WRAP  C) 多視角 | A) 先快速 WRAP (Recommended)  B) 直接派發  C) 多視角 |
| 「跳過評估」隱藏在簡短標籤 | A) 開始實作 (Recommended)  B) 評估  | A) 快速 WRAP (Recommended)  B) 直接實作（已評估過）  C) 多視角 |
| 提問缺少 WRAP/多視角選項 | A) 派發 thyme  B) 派發 basil | A) 先快速 WRAP (Recommended)  B) 派發 thyme  C) 派發 basil |
| 有 WRAP 支撐卻標 `(Recommended)` 而非 `(Recommended by WRAP)` | 完成 WRAP 後標 A) 方案 X (Recommended) | 改為 A) 方案 X (Recommended by WRAP)，讓用戶知道此建議有證據支撐 |
| 無 WRAP 但用 `(Recommended)` 暗示權威（適用範圍三情境） | A) 方案 X (Recommended)（實為 Claude 初步傾向） | 改為 A) 方案 X (My current guess) + description 揭露「此為初步猜測」 |

**判斷流程**：

```
準備 AUQ 提問 → 此提問屬於「適用範圍」之一？
    +── 否 → 一般場景，依規則 1-5 處理
    +── 是 ↓
        檢查 Recommended 選項是否為 WRAP 或多視角？
            +── 是 → 通過，發送 AUQ
            +── 否 ↓
                有附跳過理由嗎？
                    +── 有 → 通過，但 description 必須包含理由
                    +── 沒 → 不通過，重新設計選項排序
```

**理由**：

- Context 沉重時 PM 工作記憶縮小，最可能接受 Recommended 提示
- Recommended 是「省力路徑」的訊號設計，必須對齊「決策品質防護」目標而非「省事」
- AUQ 預設選項是 PM 自我防護的最後一道規則層機制，與 decision-tree.md「Context 重度檢查層」協同生效
- 標籤分級讓用戶區分「Claude 有證據支撐的建議」vs「Claude 初步傾向」，符合規則 5 權力不對等下的透明化要求（詳見 `.claude/references/power-asymmetry-rules.md` §5.6 機制 2：預設答案透明化）

> **與 PC-014 / PC-064 的關係**：本規則防止 PM 用 AUQ 後因 Recommended 設計不當而再次跳過評估（PC-014 的工具升級後變體）。Recommended 設計必須與規則 1-3 共同達成「不省略決策品質」的目標。

### 規則 7：多子任務情境必須含「平行派發」選項

> **來源**：W17-203（v0.18.0-W6 多子任務並行派發實證）。PM 在「下一步」場景列出多個 pending 子任務時，若僅列「逐一接手」選項而漏列「平行派發」會系統性低估並行容量，造成 session context 不必要消耗。

**Why**：候選項裡同時出現 ≥ 2 個 pending 子任務（兄弟 / 同父或範圍互斥的同類）時，PM 預設大腦容易陷入「依序執行」思維；若選項中不主動列「平行派發 N 個」，用戶等於只能在「逐一接手」之間選，無法行使「同時推進」的決策權。

**Consequence**：違反此規則會讓 session context 用在序列等待而非並行推進，且用戶無從察覺漏掉的平行選項——AUQ 介面只呈現 PM 給的選項，未列即不存在。

**Action**：

| 情境 | 強制要求 |
|------|---------|
| 提問選項含 ≥ 2 個 pending 子任務 / 兄弟 ticket | 必須額外列「平行派發 N 個」選項（label 含具體 ticket ID 或數量） |
| 子任務間有檔案衝突或 PC-137 限制（≥ 3 並行 .claude/ Edit）導致無法平行 | 必須顯式列「無可平行派發」選項並在 description 說明衝突原因 |
| 部分可平行（子集互斥，子集衝突） | 列具體可平行子集（如「平行派發 .a + .b（檔案互斥）」），衝突項另列 |

**判斷流程**：

```
準備 AUQ 提問 → 選項中含 ≥ 2 個 pending 子任務 / 兄弟 ticket？
    +── 否 → 規則 7 不適用，依規則 1-6 處理
    +── 是 ↓
        逐對比對 where.files 路徑前綴（含 PC-137 .claude/ ≥ 3 限制）
            +── 全部互斥 → 必須加「平行派發 N 個」選項
            +── 全部衝突 → 必須加「無可平行派發」選項並說明
            +── 部分互斥 → 必須列具體可平行子集
```

**範例（可平行 case）**：

> Wave 6 剩 W6-012.6.1 (`src/overview/`) 與 W6-012.6.3 (`docs/spec/`) 兩個 pending，檔案範圍互斥。
>
> 選項應含：
> - A) 平行派發 W6-012.6.1 + W6-012.6.3（檔案互斥）(Recommended)
> - B) 接手 W6-012.6.1 獨立執行
> - C) 接手 W6-012.6.3 獨立執行
> - D) /clear 結束 session

**範例（不可平行 case）**：

> Wave 6 剩 W6-012.6.1 與 W6-012.6.2 兩個 pending，但 .6.2 blockedBy .6.1（依序）。
>
> 選項應含：
> - A) 接手 W6-012.6.1（.6.2 阻擋中）(Recommended)
> - B) 無可平行派發（W6-012.6.2 依賴 .6.1 先完成）— 說明用，不執行
> - C) /clear 結束 session

**反模式（禁止）**：

| 反模式 | 修正 |
|-------|------|
| 多 pending ticket 提問僅列逐一接手，不列平行 | 加「平行派發 N 個」或「無可平行派發」選項 |
| 列了「平行派發」但未含具體 ticket ID / 衝突原因 | label 含 ticket ID 集合，description 說明互斥 / 衝突理由 |
| 假設 PM 會自行判斷可平行而省略選項 | 強制列出（規則 7 是 schema 級要求） |

**與其他規則的銜接**：

- 規則 5（驗證類自動派發）優先：若多子任務皆為驗證類，直接背景派發不需 AUQ
- 規則 6（Recommended 設計）：平行派發若為合理路徑，可標 `(Recommended)`；若仍需 WRAP 評估，Recommended 留給 WRAP 選項
- PC-137（≥ 3 並行 .claude/ Edit）：規則 7 必須在判斷流程中納入此限制
- W17-203.1（CLI 強制層）：未來 `ticket track parallel-check <id>` 命令落地後，AUQ 設計可呼叫該 CLI 自動分組

> **與 W17-203.1 互補**：本規則是規則層自律（PM 設計 AUQ 選項時主動納入），W17-203.1 將提供 CLI 強制層（auq-option-pattern-detector-hook 偵測 + ticket CLI 衝突分組）。兩者形成「規則層提示 + CLI 層強制」雙層閉環。

---

## 題型判別輔助（非強制，教育性）

PM 用 AUQ 前的自檢：這是哪種題型？

| 題型 | 判別標準 | 處理方式 |
|------|---------|---------|
| 決策題 | 答案空間可列 ≤5 個選項覆蓋 90%+；不同答案導致 PM 執行路徑分歧 | 強制 AUQ + 規則 1-6 |
| 釐清題 | 答案為開放文字描述；無法窮舉選項；多發生於用戶→PM 方向的主動對話 | 開放式提問（PC-064 適用邊界適用；見規則 3） |
| 混合題 | 決策 + 補充描述組合（如場景 #6 任務拆分） | AUQ 決策層 + description/notes 欄位補充 |

**判別流程**：

1. 列出答案空間 → 能列 ≤5 個覆蓋 90%+ 嗎？
   - 能 → 決策題
   - 不能 → 進入 Q2
2. 不同答案會導致 PM 執行路徑分歧嗎？
   - 分歧 → 決策題（即使選項難窮舉也要用 AUQ + Other）
   - 同路徑 → 釐清題
3. 兩者皆有 → 混合題

**反濫用警告**：此判別為教育性輔助，不是跳過 AUQ 的豁免口。濫用判別結果（以「這是釐清題」為由省略 AUQ）仍屬 PC-014 違規。

---

## 場景列表

### 18 個強制使用場景（#11 細分為 #11a/#11b）

> **象限對照**（A=降低摩擦 / B=保留現狀 / C=增加摩擦）為單一來源：`.claude/references/friction-management-decision-points.md` 的「AskUserQuestion 18 場景覆蓋對照」表。本表不再重複象限欄，避免雙寫同步風險（W5-008）。

| # | 場景 | 觸發條件 | 決策點 | Hook 提醒 |
|---|------|---------|--------|-----------|
| 1 | 驗收方式確認 | ticket track complete 前（P0 優先級時觸發；DOC/ANA/非 P0 IMP 自動決定，不觸發） | ticket-lifecycle 驗收階段 | acceptance-gate-hook |
| 2 | Complete 後下一步 | ticket track complete 後 | ticket-lifecycle 完成階段 | acceptance-gate-hook |
| 3 | Wave/任務收尾確認 | 當前 Wave 無 pending Ticket（**前置步驟**：強制執行 `/parallel-evaluation` Wave 多視角審查，審查完成並建立發現 Ticket 後才進入 #3 選項；情境 C1：有其他 Wave → #3a；情境 C2：全完成 → 技術債整理 + /version-release check） | ticket-lifecycle 收尾 | parallel-suggestion-hook |
| 4 | 方案選擇 | 多個技術方案 | 決策樹第負一層 | prompt-submit-hook |
| 5 | 優先級確認 | 多任務排序 | 決策樹第負一層 | prompt-submit-hook |
| 6 | 任務拆分確認 | 認知負擔 > 10 | 決策樹第負一層 | prompt-submit-hook |
| 7 | 派發方式選擇 | Task subagent / Agent Teams / 序列 | 決策樹第負一層 | askuserquestion-reminder-hook |
| 8 | 執行方向確認 | 並行/序列、先後順序 | 決策樹第負一層 | prompt-submit-hook |
| 9 | Handoff 方向選擇 | 多個兄弟/子任務可選 | ticket-lifecycle 完成階段 | - |
| 10 | 開始/收尾確認 | 確認是否開始執行 | 決策樹第負一層 | - |
| 11a | Commit 後 Context 刷新 Handoff（情境 A） | ticket 仍 in_progress；**前置：main 必須 clean**（見下方「#11 /clear 前置條件」） | 決策樹第八層 Checkpoint 2 | commit-handoff-hook |
| 11b | Commit 後任務切換 Handoff（情境 B） | ticket completed + 同 Wave 有 pending；**前置：main 必須 clean** | 決策樹第八層 Checkpoint 2 | commit-handoff-hook |
| 12 | 流程省略確認 | 省略意圖偵測 | 決策樹第八層 | process-skip-guard-hook |
| 13 | 後續任務路由確認 | Phase 3b 完成且豁免條件不符時、Phase 4b（豁免）/4c 完成、版本完成（C2）、incident 或分析完成後有多個後續路由可選（Phase 1/2/3a 全自動不觸發；Phase 3b 豁免條件符合時自動進入 4b 不觸發） | 決策樹第八層 | phase-completion-gate（擴充） |
| 14 | parallel-evaluation 觸發確認 | 階段完成後 | 決策樹第八層 | phase-completion-gate（擴充） |
| 15 | Bulk 變更前備份確認 | 批量修改前 | 決策樹第八層 | parallel-suggestion-hook（擴充） |
| 16 | 錯誤學習經驗確認 | commit 完成後（#11a/#11b 之前）；docs:/chore:/style: 等 commit 自動跳過；選項簡化為二元確認 | 決策樹第八層 Checkpoint 1.5 | commit-handoff-hook（擴充） |
| 17 | 錯誤經驗改進追蹤 | ticket complete 時有新增 error-pattern | ticket-lifecycle 完成階段 | acceptance-gate-hook（擴充） |

**Hook 覆蓋狀態**：14/18 場景有 Hook 自動提醒（14/18 = 78%）。其中 #13/#14 為條件式觸發（僅當 TDD Phase 完成且 worklog 更新時），未計入 14/18 計數，列於下方 Hook 提醒機制表僅供參考。

**Phase 1-3 自治 commit 相容性**：場景 #11/#16 由 commit-handoff-hook 觸發，但 Phase 1-3 代理人自治 commit 時，因 subagent 禁止使用 AskUserQuestion，Hook 提醒自然跳過——這是預期行為，Phase 1-3 的 commit 不需要 PM 介入 Handoff 或錯誤學習決策。

### 場景 #16 雙通道記錄要求（強制）

選擇「記錄錯誤學習」後，必須同時執行雙通道記錄，**缺一不可**：

| 通道 | 操作 | 位置 | 說明 |
|------|------|------|------|
| error-pattern | /error-pattern add | .claude/error-patterns/ | 結構化可查詢知識庫，供將來查詢參考 |
| memory | 更新使用者 auto-memory | .claude/projects/.../memory/ | 跨對話個人記憶，服務當前用戶的持續學習 |

**強制要求**：禁止只寫單一通道。只寫 memory 不執行 /error-pattern add，或反之，均違反雙通道規範，無法落實錯誤學習的完整目標。

### 場景執行順序約束

**#16 必須先於 #11a/#11b**（強制）：commit 後先執行 #16（錯誤學習），再進入 #11（Handoff）。

---

> 各場景完整操作細節、選項配置、工具能力說明：.claude/references/askuserquestion-scene-details.md

## #11 /clear 前置條件（強制）

> **來源**：W10-014。session 結束前 main 未提交變更若隨 /clear 丟失 context，後人僅見檔案不知決策理由；強制將 #11 Handoff 選項的觸發前提綁到「main clean」上，避免 PM 為了快點 /clear 跳過 commit。
>
> **Why**：#11 Handoff 是 /clear 進入路徑最近的上游節點；前置條件綁在這裡能在「呈現選項」階段就攔截 dirty main，無需等到 /clear 觸發後再補救。
>
> **Consequence**：缺前置檢查時 PM 在 main dirty 狀態仍可呈現 #11，用戶選 Handoff 後 context 已退場，commit 機會永久失去。
>
> **Action**：產出 #11 AUQ 選項前先執行 `git rev-parse --abbrev-ref HEAD` + `git status --short`；若位於 main 且有未提交變更，**從 AUQ 移除 /clear 相關選項**，改先提 commit 引導；commit 完成後再次評估是否呈現 #11。

| 前置檢查 | 通過條件 | 不通過時動作 |
|---------|---------|------------|
| 主倉庫 + main 分支 + 有未提交變更 | 先 `git add` + `git commit`（commit message 含決策理由）才能呈現 #11 | **不得**呈現 #11 AUQ；改為先引導用戶 commit |
| Worktree（feature 分支）+ 有未提交變更 | 提示用戶但不阻擋 | 仍可呈現 #11；description 註明「worktree 有未提交，由 worktree owner 後續處理」 |
| 所有變更皆已 commit | 通過 | 直接呈現 #11 |

> 完整 main vs worktree 差別對待規則：`.claude/pm-rules/session-switching-sop.md`「main vs worktree 差別對待（強制）」章節。

## 選項前提檢查（強制）

> **來源**：W11-011（PM 在仍有 83 pending 時 AUQ 選項 3 提 `/version-release check`，description 附 disclaimer「顯然不時但可行」——前後矛盾等於自承假選項，違反規則 5.6 機制 4 illusion of control）。

產出 AUQ 選項前，必須對每個選項自問「此選項的觸發前提是否成立？」

| 檢查項 | 正確行為 | 違規訊號 |
|--------|---------|---------|
| 前提驗證 | 前提不成立 → **刪除該選項**，不列入 AUQ | 列出後附 disclaimer 合理化 |
| Disclaimer 使用 | 描述選項的事實後果或 trade-off | 「顯然不時但可行」「不推薦但列出」「次選參考」等合理化用語 |
| 規則條款路徑引用 | 引用具體路徑觸發對應情境的選項 | 把互斥情境（C1 vs C2）的動作都列為選項 |

**假選項訊號清單**（任一出現即須刪除該選項）：

1. Description 含「顯然不適用」「雖然但」「不推薦但可行」等前後矛盾詞
2. 選項觸發前提（如「所有 Wave 完成」「無任何 pending」）在當前情境不成立
3. 同一 AUQ 中混合互斥場景的動作（例：場景 3 的 C1 分支時也列 C2 動作）

**典型案例**：場景 3「Wave/任務收尾」有互斥兩支 —— C1「有其他 Wave pending」走技術債整理，C2「全完成」走 `/version-release check`。PM 必須依當前實況選擇其一，**不得並列**。

## 違規處理

| 違規行為 | 處理方式 |
|---------|---------|
| 文字提問替代 AskUserQuestion | 停止，改用 AskUserQuestion |
| 跳過確認直接執行 | 提醒後繼續 |
| 未載入就使用 AskUserQuestion | ToolSearch 載入後重試 |
| 假選項（前提不成立仍列出） | 刪除該選項後重新產出 AUQ |

---

## Hook 提醒機制

以下 Hook 在關鍵決策點自動輸出 AskUserQuestion 提醒：

| Hook | 觸發時機 | 覆蓋場景 |
|------|---------|---------|
| parallel-suggestion-hook | 繼續請求但無 pending Ticket | #3 Wave 收尾 + #15 批量備份 |
| prompt-submit-hook | 用戶提問含決策關鍵字 | #4 方案 + #5 優先級 + #6 拆分 + #8 執行方向 |
| askuserquestion-reminder-hook | Task 派發含多個 Ticket ID | #7 派發方式 |
| commit-handoff-hook | git commit 成功後 | #11 Commit Handoff + #16 錯誤學習 |
| process-skip-guard-hook | 用戶輸入含省略關鍵字 | #12 流程省略 |
| phase-completion-gate-hook | Phase 完成時 worklog 寫入後（條件式，未計入 12 計數） | #13 後續路由 + #14 parallel-evaluation |
| acceptance-gate-hook | ticket track complete 命令 | #1 驗收方式 + #2 下一步 + #17 錯誤經驗改進 |

---

## 相關文件

- .claude/pm-rules/decision-tree.md - 主線程決策樹
- .claude/pm-rules/ticket-lifecycle.md - Ticket 生命週期
- .claude/methodologies/friction-management-methodology.md - 摩擦力管理方法論（象限 A/B/C 判斷準則）
- .claude/references/friction-management-decision-points.md - 19 個 PM 決策點完整分類
- .claude/references/askuserquestion-scene-details.md - 場景 1-17 完整操作細節
- .claude/references/ticket-askuserquestion-templates.md - AskUserQuestion 模板
- .claude/pm-rules/parallel-dispatch.md - 並行派發指南
- .claude/error-patterns/process-compliance/PC-014-askuserquestion-rationalization-skip.md - 合理化跳過模式
- .claude/error-patterns/process-compliance/PC-064-pm-text-options-without-askuserquestion.md - 列純文字選項無意識疏失模式
- .claude/error-patterns/process-compliance/PC-066-decision-quality-autopilot.md - 輔助決策系統未主動觸發（規則 6 預設選項規則來源）

---

**Last Updated**: 2026-05-09
**Version**: 3.13.0 — 新增「具體觸發訊號（W17-174.1 共同特徵落地）」章節：S1-S6 六訊號表 + stakes 不豁免（F3）+ 呈現形式不豁免（F5）+ 代理人完成回報後強制重跑觸發原則（F1）。三明示 Why/Consequence/Action，引用 W17-174.1 L1 審計輸出
**Version**: 3.12.0 — 新增「#11 /clear 前置條件」章節 + 場景表 #11a/#11b 加註 main clean 前置（W10-014）：main 未提交變更強制先 commit 才能呈現 #11；worktree 有未提交僅提示不阻擋
**Version**: 3.11.0 — 新增題型判別輔助章節 + PC-064 適用邊界子章節（Phase A / W14-025 / 019.4 方案 G）：決策題/釐清題/混合題三類判別表 + 釐清題不適用 PC-064 的邊界條款（兩處均含反濫用警告）
**Version**: 3.10.0 — 規則 6 新增 Recommended 標籤分級（Phase A / W14-023 / 019.3 方案 G）：ANA/重大決策/Session 關鍵分歧情境下 `(Recommended)` 依證據強度分級為 `(Recommended by WRAP)`、`(Recommended by 多視角)` 或 `(My current guess)`
**Version**: 3.9.0 — 新增規則 6：預設選項設計規則（PC-066 防護），重大決策/ANA/Session 路由的 Recommended 必須為 WRAP/多視角，禁止「跳過評估」
**Purpose**: AskUserQuestion 規則唯一 Source of Truth
