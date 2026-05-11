# PC-130: 規範性文字 dogfooding 違規（內容禁止絕對主義，形式採用絕對主義）

## 錯誤症狀

撰寫「禁止 X」「推崇 Y」類規範性文字時，作者自身使用 X 語氣或未體現 Y 語氣，造成內容主張與形式表現的元層矛盾。典型表現：

1. **規則 6 教推崇機會成本語氣，自身用「必須 / 一律 / 嚴禁」絕對命令詞**：W17-060 案例
2. **三層防護章節主張 dogfooding，Solution 自身違反所提出的 dogfooding**：W17-122 ANA 案例
3. **PC error-pattern 的「防護」段使用絕對主義禁令，未對照其推崇的價值/容量/邊界語言**：常見於壓力下撰寫的 PC
4. **Methodology 文件的「強制規則」章節未交代邊界與例外**：讓讀者誤解為適用所有情境

讀者複製文字的形式（絕對語氣）時，內容主張（機會成本框架）反而失效——形式覆蓋內容。

## 根因分析

### 表層原因：規範性文字的權威需求引導絕對主義

撰寫規則時 LLM 預設選擇「必須 / 禁止 / 強制」絕對命令詞，認為這樣才有約束力。**Why**: 命令式句型在訓練語料中與「規則」類別高度共現；改用機會成本語氣需主動消耗 token 重構句型。**Consequence**: 規範性文字產出的預設語氣即絕對主義，與 ai-communication-rules.md 規則 6 / compositional-writing 原則 3 主張的「以價值 / 容量 / 邊界為依據」相悖。**Action**: 撰寫規範性文字時主動執行語氣自審；避免在第一次產出就追求精準，採二次審查補修策略（document-writing-style.md「最高優先原則」）。

### 深層原因：內容焦點遮蔽形式自審

作者注意力集中於「禁止 X」的精準定義，工作記憶用於確保語意涵蓋與邊界劃分；形式層（自身語氣）被擠出注意焦點。**Why**: 內容定義的認知負荷高（需考慮邊界、例外、跨規則一致性），剩餘注意力不足以同時監控形式。**Consequence**: 內容越精準的規範性段落越容易出現 dogfooding 違規，因為作者越投入內容焦點，越無法分神看自己的語氣。**Action**: 把形式自審外移到獨立步驟（Layer 2 委員 / 二次審查清單），不依賴作者在內容撰寫過程中同時自審。

### 第三層原因：與 PC-066 共振——壓力下偏向限制性反應

Context 沉重時規範性文字撰寫尤其易違規，這是 PC-066「限制性反應在書面文字場域的延伸」。**Why**: PC-066 描述 PM 在壓力下偏向「禁止 X / 規避 X」的限制性解法；規範性文字撰寫本身即「定義禁令」，與限制性反應同向。**Consequence**: 兩個機制疊加放大絕對主義輸出傾向；高 context session 中的規則撰寫風險最高。**Action**: framework 路徑的 Edit 觸發 SKILL trigger（W17-125）讓 compositional-writing 原則在 claim 階段就進入 PM 工作記憶；事中 Layer 2 委員審查（W17-124）作為形式自審外包機制。

## 案例庫

| 案例 | Ticket | 違規 | 修復成本 |
|------|--------|------|---------|
| 1 | W17-060（`ai-communication-rules.md` 規則 6） | basil 審查 P0 1 + P1 6（規則內容禁止絕對主義，形式多處「必須 / 禁止」） | W17-124 v1.2.1 + W17-128 兩輪修正 |
| 2 | W17-122 ANA Solution（三層防護章節） | basil 審查 P0 1 + P1 6（Solution 主張 dogfooding，自身違反 dogfooding） | W17-124 / W17-128 / W17-129 三 ticket 結案 |

兩案例 P0 各 1 條暗示存在系統性閾值（非偶發單次失誤）；修復成本平均 2-3 個 follow-up ticket，事後補做累積成本顯著高於事前一次定義防護。

### 案例 1：W17-060 規則 6 文字 dogfooding 違規

PM 撰寫「禁止以估時為決策依據」規則，主張改用「價值 / 容量 / 優先級」語言。

- 違規模式：規則內文使用「必須」「一律」「嚴禁」絕對命令詞共 6 處
- **Consequence**: basil-writing-critic Layer 2 審查標 P0 1 條 + P1 6 條；讀者複製形式（絕對語氣）會抵消內容主張的機會成本框架
- **Action**（已落地）: W17-124 v1.2.1 將首段命令式改為條件式描述；W17-128 補完 hotpath 對照表的語氣對齊

### 案例 2：W17-122 ANA Solution dogfooding 違規

PM 撰寫三層防護方案，主張「framework 編輯觸發 compositional-writing skill」以防止規範性文字 dogfooding。

- 違規模式：Solution 自身採用絕對主義句型（「PM 必須 / 一律執行 / 嚴禁跳過」），與所提出的 dogfooding 防護自相矛盾
- **Consequence**: 元層悖論——分析「為何規則語氣失準」的 Solution 自己語氣也失準；三層防護方案落地前就被自身的形式違規證實「事前防護不足」假設
- **Action**（已落地）: W17-124 / W17-128 / W17-129 三 ticket 修正 Solution 文字 + 落地三層防護機制

## 防護措施（已分散落地，本 PC 為統合錨點）

| 層 | 機制 | 落地 ticket |
|----|------|-----------|
| 事前 | claim 時若 ticket where.files 含 framework 路徑 + type=IMP，提示 Read compositional-writing SKILL | W17-125 |
| 事中 | PM 自做 framework 規則編輯 6 步驟流程（含 Layer 2 委員審查） | W17-124 |
| 事後 | commit msg 標 `Layer 2 by [agent-name]` 或 `N/A by [理由]` | W17-126（待落地） |
| 偵測 | framework-rule-edit-skill-trigger-hook 偵測 Edit framework 路徑時若無 SKILL Read 即提醒 | W17-127 |

四層機制非並聯複述，分別覆蓋不同節點：claim（事前）/ 編輯流程（事中）/ commit（事後）/ Hook 訊號（偵測）。Single source of truth 為 compositional-writing SKILL；本 PC 與四個 ticket 引用 SKILL，不複述其原則。

## 與 PC-066 邊界對照

PC-130 是 PC-066 在「書面規範性文字產出」場域的延伸，兩者共振但範疇可分離。

| 維度 | PC-066 decision-quality-autopilot | PC-130 prescriptive-text-dogfooding-violation |
|------|-----------------------------------|----------------------------------------------|
| 場景 | 決策框架選擇（限制性 vs 探索性） | 書面規範性文字撰寫（規則 / methodology / PC / SKILL 主文） |
| 觸發條件 | context 沉重時 PM 主動決策 | Edit framework 路徑 + 撰寫規範性段落 |
| 違規形式 | 採限制性解法（禁止 X / 規避 X）而非探索性解法（找正確工具做 X） | 內容主張機會成本，形式採絕對主義（內容形式不對齊） |
| 防護機制 | Hook 偵測「無法 / 禁止」關鍵字 → 觸發 WRAP；CLI claim 三問 | claim 時 SKILL trigger（W17-125）+ Layer 2 委員（W17-124）+ commit 標記（W17-126） |
| 上下位關係 | **上位機制**（壓力下偏限制性反應的根本機制） | **下位延伸**（書面文字場域的具體表現） |
| 互補關係 | PC-066 防止決策語氣失準 | PC-130 防止規範性文字語氣失準（同根因，不同產出層） |

**判別準則**：
- 處理「PM 該不該採取 X 行動」的決策過程 → PC-066
- 處理「規範性文字本身的語氣形式」 → PC-130
- 兩者在 context 沉重時同時觸發概率高，建議交叉引用而非合併

## 自我檢查清單

撰寫規範性文字（rules / methodologies / PC / SKILL 主文 / pm-rules）時自問：

- [ ] 我的規範性段落內容是否主張機會成本 / 價值 / 容量 / 邊界語言？
- [ ] 我的規範性段落形式是否與內容主張對齊（無「必須 / 一律 / 嚴禁」與內容相悖）？
- [ ] 我是否已執行二次審查（document-writing-style.md「最高優先原則」）？
- [ ] 若處於 context 沉重 session，我是否已派 Layer 2 委員（basil-writing-critic）審查形式？

> 觸發條件與 SKILL 原則的權威來源為 `.claude/skills/compositional-writing/SKILL.md`，本檔不複述。

## 關聯

- **上位機制**：PC-066 decision-quality-autopilot（壓力下限制性反應的根本機制；本 PC 為其書面文字場域延伸）
- **相關模式**：PC-111 pm-narrative-fabrication（書面論述品質，事實層；本 PC 為語氣層）
- **相關模式**：PC-093 yagni-deferred-decision（決策延後反模式，與本 PC 同屬規範性文字撰寫風險）
- **相關 Skill**：`.claude/skills/compositional-writing/SKILL.md`（書寫原則的權威來源）
- **相關規則**：`.claude/rules/core/document-writing-style.md`（二次審查原則）
- **相關規則**：`.claude/rules/core/ai-communication-rules.md` 規則 6（價值 / 容量 / 優先級語言，本 PC 案例 1 來源）
- **相關 Agent**：`.claude/agents/basil-writing-critic.md`（Layer 2 委員審查角色）
- **相關 Hook**：framework-rule-edit-skill-trigger-hook（W17-127 待實作）

---

**Created**: 2026-05-05
**Last Updated**: 2026-05-05
**Category**: process-compliance
**Severity**: P2（不直接導致功能缺陷；間接累積規則品質負債，事後補做成本顯著）
**Key Lesson**: 規範性文字的內容主張與形式表現可能背離。**Why**: 撰寫規則時注意力集中於內容精準度，形式自審被擠出工作記憶；命令式句型又與訓練語料中的「規則」類別高度共現，預設語氣即絕對主義。**Consequence**: 讀者複製形式（絕對語氣）時內容主張（機會成本框架）反而失效；形式覆蓋內容，元層悖論。**Action**: 形式自審外移到獨立步驟（Layer 2 委員 / 二次審查清單），不依賴作者在內容撰寫過程中同時自審；framework 路徑編輯透過 SKILL trigger 在 claim 階段就讓原則進入工作記憶。

**Meta Lesson**: 本 PC 自身的撰寫即為一次 dogfooding 測試——若本檔案使用「必須 / 一律 / 嚴禁」絕對命令詞，即重現所描述的違規模式。**Why**: PC 撰寫者也是規範性文字撰寫者，同樣受根因 1-3 影響。**Consequence**: 本 PC 通過二次審查與形式自審後落地；若後續修訂出現絕對主義語氣，視為 PC-130 案例 3 加入案例庫。**Action**: 修訂本檔時保留交叉引用（PC-066 上位 / compositional-writing SKILL 權威），形式語氣對齊內容主張的機會成本框架。
