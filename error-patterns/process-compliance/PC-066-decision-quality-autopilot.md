# PC-066: 輔助決策系統未在 Context 沉重時主動觸發

## 錯誤症狀

PM 在 context 沉重的 session 中做出本可透過 WRAP/多視角避免的錯誤決策。典型表現：

1. **連續失敗仍重複嘗試**：同一問題修改 2+ 次失敗，PM 繼續調整核心程式碼，未停下執行 WRAP
2. **宣告「做不到」採限制性解法**：PM 輸出「無法」「禁止」「CLI 不支援」前未先窮盡 WRAP 的「擴增選項」階段
3. **ANA Ticket 跳過分析框架**：claim ANA Ticket 後直接寫 Solution，未執行錨點確認與選項擴增
4. **重大決策未經多視角審查**：升級規則、新建 Skill、改架構等影響跨專案的決策，產出後未派發三人組審查
5. **元層悖論**：PM 在分析「為何不主動用輔助系統」的 ANA Ticket 中，自己也未用輔助系統

## 根因分析

### 表層原因：依賴 PM 自律的觸發機制

WRAP 與 multi-perspective 兩套輔助系統的觸發點為「PM 主動回想與選擇」。**Why**: 兩套系統未綁定任何自動偵測 Hook 或 CLI 強制節點，觸發責任完全落在 PM 工作記憶。**Consequence**: Context 使用率 > 60% 時 PM 工作記憶縮小，無法同時持有「該用 WRAP」與「任務本身」兩個併發目標，於是預設行為退化為「直接結案」。**Action**: 將觸發責任從 PM 自律遷移至 Hook + CLI 強制節點（見措施 1 / 6）；新建輔助系統時禁止只設計「PM 自律觸發」單一路徑。

### 深層原因：自律機制在高壓下的系統性失效

| 階段 | 系統狀態 | PM 實測行為 |
|------|---------|---------|
| Context 輕（< 30% 使用） | 工作記憶充足 | 能主動回想 WRAP 觸發條件（觀測命中率 ~80%） |
| Context 中（30-60%） | 工作記憶部分擠壓 | 依賴規則/Skill 引導才會用（命中率 ~50%） |
| Context 重（> 60%） | 工作記憶嚴重縮小 | 直接「快速判斷完結案」，跳過所有引導（命中率 ~20%，本檔案例 1-4 統計） |

**Why**（自律與壓力場景負相關）: PM 最需要輔助系統的時刻（高 context、連續失敗、被困住）正是工作記憶最不足以主動回想規則的時刻。**Consequence**: 仰賴 PM 自律的設計在最關鍵場景失效，等同「規則對需要它的人不可達」。**Action**: 設計輔助系統時先問「此觸發條件能否在 PM 工作記憶縮小時仍被觸發？」；不能 → 必須加 Hook 或 CLI 強制節點（單點強制，不複述）。

### 次要原因：限制性解法是 context 沉重時的預設反應

Context 沉重時 PM 的預設反應為「禁止 X」「規避 X」「防護 X」（限制性解法），而非「找正確工具做 X」（探索性解法）。**Why**: 限制性解法計算成本低（只需寫禁令），探索性解法需執行 W 階段擴增選項（成本高）。**Consequence**: 限制性規則寫入後遮蔽既有正確工具的能力（案例 1：禁止讀 transcript 規則寫入後，TaskOutput deferred tool 被忽視一整段時間）。**Action**: PM 輸出「無法 / 禁止 / 規避」前必先觸發 WRAP W 階段；由措施 1 Hook 偵測關鍵字強制提示，不再仰賴 PM 自律。

### 第三層原因：輔助系統觸發條件靜態化

WRAP skill description 列出 7 種觸發條件（連續失敗、被困住、ANA Ticket 等），條件形式為靜態文字描述。**Why**: 靜態文字需 PM 執行「回想條件 → 匹配情境 → 決定觸發」三步路徑。**Consequence**: 三步路徑任一步在 context 沉重時斷裂（最常見斷在第一步「回想條件」），靜態觸發條件等於失效。**Action**: 機器可讀觸發條件落在 `.claude/config/wrap-triggers.yaml`（措施 1 Hook 動態讀取）；靜態文字僅作為 PM 人工 fallback 對照（措施 4），不再作為主要觸發路徑。

## 實際案例

### 案例 1：宣告 transcript「無法可靠讀取」

PM 處理代理人觀察問題時，連續修改錯誤模式規則多次後，宣稱「PM 無法可靠讀取 transcript」並規則化「禁止讀取」。

- WRAP 符合條件：「被困住（宣稱做不到）」明確觸發；實際未觸發 WRAP，採限制性解法
- **Consequence**: 次日另一場 ANA 發現 deferred tool（TaskOutput）早已可用，限制性規則必須調整為「TaskOutput 安全使用範本」；限制性規則存在期間遮蔽正確工具
- **Action**（防護觸發）: 措施 1 Hook 偵測「無法 / 禁止 / 不支援」關鍵字 → 強制提示 WRAP；輸出該類詞彙前先執行 W 階段（爬梯子法檢查 deferred tools / 既有 API）

### 案例 2：Hook error 三次錯誤假設修改

session 持續排查 hook 異常，已修改核心 hook 工具 2 次皆失敗。PM 第三次繼續修改（先假設 exit code、再假設 stderr、再假設空 stdout）。

- WRAP 符合條件：「連續失敗 2+ 次」明確觸發；實際未觸發 WRAP，第三次後才搜社群發現是 CLI 已知 bug
- **Consequence**: 三次修改全部回退，誤改核心程式碼累積技術債
- **Action**（防護觸發）: 措施 1 Hook 透過 ticket release/reclaim 計數偵測連續失敗 ≥ 2 → 強制提示；同問題第二次失敗即停下執行 R 階段（基本率搜尋：本問題在社群是否已知 bug）

### 案例 3：原則建立反覆只寫 memory 不升級框架

PM 多次在 session 末尾建立跨專案適用的原則，將其寫入 feedback memory 但未升級為 `.claude/` 框架規則。

- WRAP 符合條件：「重大決策（原則建立影響跨專案）」明確觸發；實際未觸發 WRAP，多筆 memory 未升級
- **Consequence**: 跨專案原則延遲惠及其他專案；新專案 sync `.claude/` 後無法繼承這些原則
- **Action**（防護觸發）: quality-baseline 規則 7（Memory 升級評估，PC-061）強制每次寫 memory 後評估是否升級框架；本檔案例補入該規則的觸發樣本

### 案例 4：分析「為何不主動用 WRAP」的 ANA 自己也未用 WRAP

PM 接連執行兩個關於「PM 系統性盲點」的 ANA Ticket，第二個 ANA 直接進入 Solution 撰寫，未執行錨點確認與選項擴增。

- WRAP 符合條件：「ANA Ticket 分析過程（強制快速 WRAP）」明確觸發；實際未觸發 WRAP
- **Consequence**: 元層悖論——分析「為何不用輔助系統」的任務本身未用輔助系統，等同證實「自律觸發無效」假設
- **Action**（防護觸發）: 措施 6 CLI claim 對所有 ticket（含 ANA）強制顯示簡化 WRAP 三問；ANA Ticket claim 後在執行 Solution 前必填 W/A/P 三問入 Problem Analysis 段

## 防護措施（單點強制 + fallback 結構）

### 設計原則：強制觸發只在一個節點

**Why**: 同一觸發條件複述在多處（規則 + Skill + 持續層）會導致漂移——三處文字不同步時，PM 不知哪份權威。**Consequence**: 初版設計（規則層 + Skill 層 + 持續層三處複述）被多視角審查（linux 視角）指出為 DRY 違反，修訂前若已落地將累積三份不同步的觸發條件清單。**Action**: 強制觸發收斂在 single source of truth（Hook 動態讀 YAML）；其他位置只引用不複述；新增防護機制設計時先檢查「此條件是否已在他處定義？」

### 措施 1：decision-quality-guard-hook（強制節點，唯一強制觸發點，W10-009 追蹤）

`.claude/hooks/decision-quality-guard-hook.py`（待落地）為唯一自動強制觸發節點。偵測訊號：

- 連續失敗 ≥ 2 次（透過 ticket release/reclaim 計數）
- PM 輸出「做不到 / 無法 / 禁止」關鍵字（透過 UserPromptSubmit 正則）
- ANA Ticket claim（透過 PostToolUse 偵測 `ticket track claim`）

觸發後輸出 stderr 強制提示，節流：同訊號 10 分鐘內不重複。

> **觸發條件權威來源**：
> - 機器可讀（Hook 動態讀取）：`.claude/config/wrap-triggers.yaml`
> - 本專案對應表：`.claude/skills/wrap-decision/references/project-integration/triggers-alignment.md`
> - 通用原理（抽象類別）：`.claude/skills/wrap-decision/SKILL.md`「觸發條件」章節
>
> Hook 實作以 YAML 為 single source of truth，不在 Python 硬編碼。

### 措施 2：wrap-decision SKILL description 擴充（Skill matching 層）

`.claude/skills/wrap-decision/SKILL.md` description 擴充觸發關鍵字（做不到 / 無法 / 禁止 / 升級 / 重構 / 改架構 / 連續失敗 2+ / 高 context），讓 Skill matching 自動命中觸發場景。

> **權威清單仍在 SKILL 主文「觸發條件」章節**，description 為摘要關鍵字以提高 matching 命中率。

### 措施 3：parallel-evaluation SKILL description 補充（Skill matching 層）

`.claude/skills/parallel-evaluation/SKILL.md` description 補充 Use when 時機（Phase 3b 完成 / Phase 4 前 / 重大架構決策前 / ANA Ticket 結論審查 / 任何分析報告產出後），讓重大決策後的多視角審查能被 Skill matching 自動觸發。

### 措施 4：decision-tree.md Context 重度檢查層（人工 fallback）

`.claude/pm-rules/decision-tree.md` 派發閘門前新增「Context 重度檢查層」入口章節。**不複述觸發條件**，僅引用 wrap-decision SKILL 為權威來源。本層為 PM 主觀決策的 fallback——當 Hook 偵測不到的場景（如 PM 對非關鍵字的限制性思考）由 PM 自律觸發。

### 措施 5：AskUserQuestion 預設選項規則（路由層）

`.claude/pm-rules/askuserquestion-rules.md` 新增規則 6「預設選項設計規則」：

- 重大決策、ANA Ticket 路由、Session 關鍵分歧的 AUQ 提問，Recommended 選項必須為 WRAP 或多視角
- **禁止「跳過評估」「快速處理」作為 Recommended**

> 此規則獨立於上述強制節點，是 AUQ 工具升級後的新變體防護（PC-014 / PC-064 的工具升級延伸），與 WRAP 觸發機制無衝突。

### 措施 6：CLI claim 簡化 WRAP 三問（已落地）

`ticket track claim` 對所有 ticket 強制顯示簡化 WRAP 三問（W/A/P）。此為 ticket 認領節點的內建強制，與措施 1 Hook 互補但不重複（claim 是事件邊界，Hook 是訊號邊界）。

## 結構說明

| 節點 | 強制性 | 角色 |
|------|-------|------|
| Hook（措施 1） | 強制 | 唯一自動強制節點，覆蓋訊號偵測場景 |
| CLI claim（措施 6） | 強制 | 唯一事件邊界強制節點，覆蓋 ticket 認領場景 |
| Skill matching（措施 2/3） | 引導 | 提高 PM 主動使用 wrap-decision/parallel-evaluation 的命中率 |
| decision-tree fallback（措施 4） | 人工 | Hook 與 CLI 都無法偵測的 PM 主觀場景由 PM 自律觸發 |
| AUQ 規則 6（措施 5） | 設計約束 | 預設選項不得引導用戶跳過評估，與其他措施正交 |

**反設計**：本結構**避免**「規則層 + Skill 層 + 持續層」三處複述觸發條件的初版設計（W10-008 多視角審查發現 DRY 違反）。觸發條件 single source of truth = wrap-decision SKILL；其他位置只引用不複述。

> **與 PC-060/PC-061 的關係**：三 ANA 暴露同樣的結構問題（原則正確但執行落差），但**防護方式因領域差異而不同**：PC-060 是工具發現規則化（tool-discovery rule）、PC-061 是 memory 升級評估規則化（quality-baseline 規則 7）、PC-066 是決策觸發 Hook 化（W10-009）。**三者沒有可重用的「三層元架構」**，將其抽象為通用結構是錯誤的概念升維。

## 自我檢查清單

PM 在重大決策節點自問（Hook 強制節點之外的人工 fallback）：

- [ ] 我是否處於 wrap-decision SKILL「觸發條件」章節列出的任一情境？
- [ ] 我是否在輸出「無法 / 禁止 / 規避」前先執行了 WRAP 的 W 階段？
- [ ] 我的 AUQ 提問 Recommended 選項是否為「跳過評估」？（若是，必須改為 WRAP 或補充跳過理由）

> 觸發條件清單以 wrap-decision SKILL 為唯一權威來源，本檔案不複述。

## 關聯

- **相關模式**：PC-060（Meta-tool 發現未窮盡，「規則正確但未執行」結構）
- **相關模式**：PC-061（Memory 升級未評估，「原則建立後執行斷裂」結構）
- **相關模式**：PC-014（AskUserQuestion 合理化跳過，本模式「Recommended 不得跳過評估」的成因）
- **相關模式**：PC-050 模式 D（PM 在代理人仍在工作時誤判完成/失敗，焦慮性檢查的下游症狀）
- **相關 Skill**：`.claude/skills/wrap-decision/SKILL.md`（WRAP 框架通用原理）
- **本專案整合**：`.claude/skills/wrap-decision/references/project-integration/`（觸發條件對應、案例、Hook 設計）
- **相關 Skill**：`.claude/skills/parallel-evaluation/SKILL.md`（多視角審查本體）
- **相關規則**：`.claude/pm-rules/decision-tree.md`（Context 重度檢查層）
- **相關規則**：`.claude/pm-rules/askuserquestion-rules.md`（預設選項規則）
- **相關 Hook**：`decision-quality-guard-hook.py`（自動偵測層，待實作）

---

**Created**: 2026-04-15
**Last Updated**: 2026-04-15（多視角審查後修訂：拆除「三層防護元架構」抽象，採用單點強制 + fallback 結構）
**Category**: process-compliance
**Severity**: P1（直接導致決策品質下降，元層上抑制其他防護機制生效）
**Key Lesson**: 自律機制在 context 沉重時系統性失效。**Why**: PM 最需要輔助系統的時刻也是工作記憶最不足以主動觸發規則的時刻（自律與壓力負相關）。**Consequence**: 仰賴 PM 自律的設計在最關鍵場景失效；多層複寫同一條件會讓概念在多處漂移而非加強防護。**Action**: 將強制觸發收斂到單一節點（Hook + CLI claim）；其他位置只引用觸發條件而不複述；設計新防護前先問「此觸發點能否在 PM 工作記憶縮小時仍生效？」。

**Meta Lesson**: 本錯誤模式自身的初版設計即犯了它要修正的錯誤。**Why**: 初版「規則 + Skill + 持續層三處複寫」被包裝為「三層防護元架構」，看似系統化，實質是同概念多處複述。**Consequence**: 若未經多視角審查就落地，會在框架內植入新的 DRY 違反，並且因為被命名為「架構」而難以推翻。**Action**: 設計元架構前必經多視角審查（至少一視角偵測 DRY / 複述）；發現「同概念在 N 處出現」時必先驗證是否可收斂為「single source of truth + N 處引用」。
