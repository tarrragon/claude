# 本專案 WRAP 案例集

記錄本專案中觸發 WRAP 補強或暴露 WRAP 缺口的實戰案例。每個案例包含：情境、疏失行為、根因、WRAP 觀察、衍生防護。

> 案例編號對應 `docs/work-logs/` 與 `.claude/error-patterns/` 的正式紀錄。本文件為集中索引與教訓摘要；詳細過程見各自的正式紀錄。

---

## PC-051：WRAP 建立動機案例

**發生時間**：v0.17.x 初期
**情境**：PM 在代理人派發連續失敗後，將失敗歸因於「代理人能力不足」，導致不斷更換代理人而非檢討派發方式。
**疏失行為**：未擴增選項、未實境檢驗、未考慮機會成本。
**根因**：決策深度不足 — 在沒有任何框架引導下，直覺歸因到最表面的原因。
**WRAP 觀察**：用 WRAP 重跑後系統性發現 3 層問題 — Hook JSON 格式、觸發頻率、PM 判斷偏誤。單純「換人」完全脫靶。
**衍生防護**：WRAP skill 建立，作為決策品質的系統性補強。

---

## PC-063：偽 Widen 案例（W5-031 脫靶）

**發生時間**：v0.17.4 W5-031
**情境**：PM 在 Widen Options 階段列出 4 個候選方案（A/B/C/D），每個看似不同做法。
**疏失行為**：4 個候選方案全部基於同一假設根因「版本字面值問題」。重現實驗後發現真正的根因是其他（方案 F/H 命中）。
**根因**：Widen 在「實作手段」層級多元（哨兵值 vs gitignore vs hook），但在「假設根因」層級單一 — 全部接受同一個未驗證的根因假設。
**WRAP 觀察**：Widen 出多個方案 ≠ 真正擴增了選項空間。選項必須在「假設根因」層級多元，而不只是「實作手段」層級多元。
**脫靶率**：4/4（100%）。
**衍生防護**：SKILL 與 `pseudo-widen-guard.md` 的「偽 Widen vs 真 Widen」章節 — 強制三層質疑（質疑根因/質疑問題框架/質疑場景）+ Reality Test 閘門。

---

## PC-066：決策品質自動駕駛

**發生時間**：v0.18.0 早期
**情境**：PM 在多個決策節點直接採用預設方案，未觸發 WRAP。
**疏失行為**：
- 觸發條件被視為「如果我想不起來才做」而非「符合條件就做」
- 清單漂移：SKILL 與 pm-rules 各自重複觸發條件，版本不同步
- DRY 違反：同一清單在多處維護，改一處忘改其他處
**根因**：WRAP 原本設計成「PM 主動召喚」，沒有強制觸發機制；且 SKILL 未被標為「觸發條件權威來源」，導致複製散落。
**衍生防護**：
- `wrap-triggers.yaml` 作為機器可讀觸發條件的單一來源
- `wrap-decision-tripwire-hook.py` 自動觸發
- pm-rules（如 `decision-tree.md`）改為「指向權威來源，不複述清單」

---

## PC-067：ANA Plan 執行未審查

**情境**：ANA 類型 Ticket 的 plan 階段結束後直接執行，未用 WRAP 檢視 plan 品質。
**疏失行為**：ANA 分析品質依賴 plan 正確性，但 plan 本身未被 Reality Test 過。
**衍生防護**：ANA Ticket claim 時必須跑完整 WRAP（含 R 階段），不能只跑簡化三問。CLI 的 `ClaimWrapMessages.ANA_EXTRA_BODY` 強制提示。

---

## PC-071：個人化建議的資料充足度盲點

**發生時間**：2026-04-16
**情境類型**：AI 諮詢對話 — 羽球選拍建議
**詳細紀錄**：`.claude/error-patterns/process-compliance/PC-071-advice-without-personal-context.md`

### 對話序列

1. **第 1 輪（資訊查詢）**：使用者問「羽球初階/中階/高階拍的差異？」→ AI 給完整三階段對比表。合理。
2. **第 2 輪（諮詢模式但 AI 誤判）**：使用者補充「我是雙打新手，只有十幾年前國中小體育課打過羽球」→ AI 再給具體型號推薦（Yonex Nanoflare 001 Feel 等）、G5 握把、22-24 磅。**此輪起疏失**。
3. **第 3 輪（使用者質疑）**：「你沒問我身高、體重、性別，這是系統判斷不需要還是決策疏失？」

### AI 的隱藏假設

| 行為 | 隱藏假設 |
|------|---------|
| 直接給球拍型號推薦 | 假設使用者是「20-30 歲亞洲成年男性」 |
| 推薦握把 G5 | 假設手掌大小是亞洲成人平均值 |
| 推薦線磅 22-24 磅 | 假設握力中等 |
| 推薦 NT$2,000-3,000 價位 | 假設預算中等 |
| 推薦 Yonex/Victor | 假設使用者在台灣方便買到 |

**矛盾點**：AI 在同一份回答中明列「性別、年齡、舊傷、體能」會改變建議，卻沒問當事人任何一項。

### 應問卻沒問的 13 個關鍵變數

身高、體重、性別、慣用手、年齡、有無舊傷、手掌大小、握力、預算、所在地區、球友程度、每週頻率、是否計畫上教練課。

### 五個根因

1. **預設「回答問題」而非「釐清需求」** — 把決策諮詢當資訊查詢處理
2. **用「群體統計」替代「個體確認」** — 「新手通常」「亞洲成人手掌」的濫用
3. **急於展示專業知識** — 給完整表格看似專業，實為知識炫耀
4. **WRAP 分析時也沒補救** — R 階段質疑了羽球知識假設，卻沒質疑最根本的「我知道用戶是誰」假設
5. **使用者體驗的慣性** — AI 潛意識為了對話流暢犧牲準確度

### 對 WRAP 框架的結構性影響

**原版 WRAP 缺口**：錨點確認檢查的是「核心目標」，不檢查「資訊充足度」。導致 WRAP 可以在「不知道當事人是誰」的狀態下完整跑完整套流程 — 所有擴增的選項、檢驗的假設、評估的機會成本，全部建立在群體平均值上。

**修補**：錨點後加入 **Step 0 資料充足度閘門**。在進入 W 之前強制回答：
1. 這是資訊查詢還是決策諮詢？
2. 決策諮詢 → 我手上有當事人的關鍵變數嗎？
3. 沒有 → 停下來問，不要直接進 W。

### 衍生防護

- SKILL 的 Step 0 資料充足度檢查（通用原理版）
- `personalized-advice.md` 的本專案三層機制（識別/分級/誠實）
- `pm-rules/personalized-advice-rules.md` 的完整規則實作

---

## W5-031：W10-009 前導 — Hook 自動觸發需求

**情境**：PM 在 WRAP 觸發條件符合時仍忘記主動執行，事後反省發現自律不足是失敗主因（60% 發生率）。
**衍生防護**：`wrap-decision-tripwire-hook.py` 實作（W10-009 完成），監測連續失敗、限制性關鍵字、ANA claim 三訊號自動提醒。

---

## W10-009：WRAP Hook 實作

**情境**：Hook 實作完成，S1/S2/S3 三訊號上線。
**設計約束**（W10-052）：禁止在 Hook Python 程式碼中硬編碼 triggers/keywords/thresholds — 機器可讀來源為 `wrap-triggers.yaml`，Hook 動態讀取。
**S4-S8**：列為未來擴充 follow-up（期限型、偏離型、回退型、嘗試型、資料充足度強制型）。

---

## W10-027：Atomic Ticket Claim Checkpoint

**情境**：每次 ticket claim 若跑完整 WRAP（15-30 分鐘）會累積成儀式負擔；但完全不跑又讓「預設選項未評估」成為常態。
**設計**：取出 W/A/P 三個核心品質閘門，形成 1-2 分鐘的「簡化 WRAP 三問（Claim 版）」。R 階段留給 ANA 類型和已升級情境。
**衍生檔案**：`simplified-three-questions.md`、CLI 的 `ClaimWrapMessages` 類別。

---

## W10-028：CLI 文案 Source of Truth

**情境**：簡化三問在三個位置出現（CLI/SKILL/reference），若無明確 source of truth 會互相漂移。
**決策**：CLI 的 `ClaimWrapMessages` 類別為 Source of Truth；SKILL 與 reference 的文字必須與 CLI 輸出逐字一致。
**維護責任**：
- CLI 層 → ticket skill
- 規則層（原 SKILL，現 `simplified-three-questions.md`） → wrap-decision skill
- 實作層範例（原 `claim-quick-wrap.md`，已併入） → wrap-decision skill

---

## W10-052：Hook 觸發條件 DRY 約束

**情境**：原 Hook Python 中硬編碼關鍵字列表，YAML 新增關鍵字時 Hook 沒同步。
**決策**：Hook 必須從 `wrap-triggers.yaml` 動態讀 keywords/thresholds/failure_detection。禁止硬編碼。
**衍生**：`triggers-alignment.md` 說明 YAML ↔ SKILL ↔ Hook 三者的同步責任。

---

## W10-056.3：Hook 失敗判定一致性

**情境**：S1（連續失敗偵測）的「失敗」定義原本在 Hook Python 中判定，與 YAML 描述不一致。
**決策**：YAML 新增 `failure_detection` 欄位（keywords + structured_statuses），Hook 讀 YAML 判定。CE-4+R2 約束。

---

## W10-064：來源核對防 LLM 清單幻覺

**情境**：claude-code-guide agent 回報「Claude Code 支援 18+ hook events」，列出清單包含 `SubagentStart`、`TaskCompleted` 等項目。
**實況**：多項為幻覺。透過本機 hook-spec 檔 + Context7 雙重核對識破幻覺；但 `SubagentStop` 的 input schema 細節（agent_id/agent_type/agent_transcript_path/last_assistant_message）卻完全正確。
**觀察**：
- 列清單時 LLM 最易幻覺（「補齊看起來合理的項目」）
- 單項深入問細節（input schema、欄位語意）LLM 較難幻覺
- 即使官方 guide agent 也會幻覺清單
**衍生防護**：Reality Test 對清單類答案強制**逐項對 source 核對**。見 `source-verification.md`。

---

## W10-075：個人化諮詢偏誤分析

**情境**：PC-071 事件後的系統性分析。
**產出**：
- `personalized-advice.md` 本專案落地
- SKILL 新增 Step 0 章節（W10-075.3）
- `pm-rules/personalized-advice-rules.md` 三層機制

---

## W14-019：規則 5 設計 — 多輪迭代查詢方法論實證

**情境**：用戶提出「洗車距離 50 公尺，開車還是走路？」邏輯題揭露 ai-communication-rules.md 缺少「receiver 端前提查驗」對偶。設計過程實證了多輪迭代查詢 + 反向驗證的有效性。

**四輪查詢執行統計**：

| 輪次 | 名稱 | 搜尋數 | 新洞察數 | 累積 | 關鍵突破 |
|-----|------|-------|---------|------|---------|
| 1 | 發散型 | 8 | A-F (6) | 6 | Calibrated Questions 雙面性、Confirmshaming 對應 |
| 2 | 具體化 | 8 | G-L (6) | 12 | Lifton 8 條件、MI OARS、Anthropic 自承權力不對等 |
| 3 | 精準化 | 8 | M-S (7) | 19 | Anthropic sycophancy 自證、DarkBench 30-61% |
| 4 | **反向驗證** | 8 | U-BB (8) | **27** | **規則 5 是 paternalism 悖論揭露** |

**關鍵介入點**（用戶補充作為盲點發現器）：

| 時機 | 介入內容 | 引發效應 |
|-----|---------|---------|
| 第 1 輪後 | 補充警方/談判/師長 4 例 | 暴露 PM narrow framing → 第 2 輪轉向「權力結構」 |
| 建 ticket 時 | 覆蓋 v0.20.0 推薦選 v0.18.0 | 暴露 pm-quality-baseline 規則 6 漏洞 → 衍生 W14-020 |
| 第 3 輪後 | 指出「這不是對錯題」也是強勢框架 | 規則 5 機制 4 元層次升級（從「禁止暗示」改為「主動暴露」） |
| 第 4 輪 | 要求做反向搜尋 | 揭露規則 5 是 paternalism 核心悖論 |

**衍生產出**：

- W14-020（補強 pm-quality-baseline 規則 6「框架 ticket 必須放當前 active 版本」）
- W14-019.1（本 ticket：提煉四輪方法論擴充 WRAP skill）
- `references/iterative-research.md`：多輪迭代查詢方法論
- `references/anti-paternalism.md`：悖論識別 + 自我暴露偏好實踐

**對 WRAP 的擴充**（v2.1.0）：

- W 階段：新增「多輪迭代查詢」章節
- R 階段：新增「反向驗證範本」章節（8 種反向類型）
- A 階段：新增「悖論識別檢查清單」（4 條件 benevolent paternalism 測試）
- P 階段：新增「自我暴露偏好實踐」（不標 Recommended、暴露推理鏈）

**核心啟示**：

1. 多輪迭代搜尋確實累積洞察（每輪平均 6-8 個新洞察）
2. 第 4 輪反向驗證的洞察數最高（8 個）且質量最尖銳——**反向輪不是「補充」是「主軸」**
3. 用戶補充是設計者盲點的最強發現器
4. 規則設計過程本身可能複製它要禁止的模式（自我參照悖論）

---

**Last Updated**: 2026-04-17
**Version**: 1.1.0 — 新增 W14-019 規則 5 設計案例（多輪迭代查詢方法論實證）
