# 主線程決策樹

本文件定義主線程（rosemary-project-manager）的完整決策流程，是規則系統的核心。

> **核心原則**：所有任務入口都從這裡開始，其他規則都是它的支撐或延伸。
>
> **管理哲學**：主管的價值不在於解決問題的速度，而在於讓團隊的人力發揮到極致。
> 詳見：.claude/skills/manager/SKILL.md
>
> **適用對象**：本文件的行為限制（禁止直接查詢、禁止直接修復等）僅適用於 rosemary-project-manager（主線程）。被派發的 subagent 開發代理人應依據自身職責定義執行任務，不受主線程行為限制。

---

## 決策流程總覽（二元樹結構）

```
接收訊息
    |
    v
[Skill 匹配層] 已註冊 Skill 觸發條件匹配?
    |
    +-- 是（明確指令/關鍵字/Hook 提示）→ 使用 Skill tool 執行
    |
    +─── 否 → 繼續決策樹
    |
    v
[第負一層] 並行化評估（最高優先）
    |
    v
[強制] 派發前複雜度關卡（Dispatch Complexity Gate）
    → 評估認知負擔指數（變數數 + 分支數 + 巢狀深度 + 依賴數）
    |
    +-- 指數 <= 10 → 繼續（進入並行化判斷）
    |
    +-- 指數 > 10 → [強制] 先拆分子任務再派發（AskUserQuestion #6）
    |                禁止整包派發給單一代理人
    |                → 拆分後每個子任務重新通過本關卡
    |
    v
可並行拆分? ─是→ 複雜度適合並行?（詳見 parallel-dispatch.md 複雜度評估章節）
    |                      |
    |                      +─ 否 → [序列派發]
    |                      |
    |                      +─ 是 → Agent A 的發現會改變 Agent B?
    |                               |
    |                               +─ 否 → [並行派發 Task subagent]
    |                               |
    |                               +─ 是 → 3-4x 成本合理?
    |                                        |
    |                                        +─ 是 → [Agent Teams 派發]（/agent-team）
    |                                        +─ 否 → [Task subagent + PM 中轉]
    |
    +─── 否 → 主線程必須親自處理? ─是→ [僅限：用戶溝通、最終決策]
    |                             |       ↓
    |                             |  [強制] 用戶決策使用 AskUserQuestion
    |                             |
    |                             └─否→ [必須派發給代理人]
    |
    v
[第零層] 明確性檢查
    |
    +-- 包含明確錯誤關鍵字? ─是→ [第六層] 事件回應流程
    |
    +─── 否 → 包含不確定性詞彙? ─是→ [確認機制]
    |                            |
    |                            └─否→ 複雜需求? ─是→ [確認機制]
    |                                      |
    |                                      └─否→ [第一層]
```

> 視覺化 Mermaid 圖表：.claude/references/decision-tree-diagrams.md

---

## Skill 匹配層（最高優先）

Skill 是預建的專用工具，優先於代理人派發。

| 優先級 | 匹配方式 | 範例 |
|--------|---------|------|
| 1 | 明確指令 (`/skill-name`) | `/ticket track summary` |
| 2 | Skill description 中的觸發關鍵字 | 「確認待辦的 ticket」→ ticket Skill |
| 3 | Hook `[SKILL 提示]` 輸出 | Hook 建議使用某 Skill |

無 Skill 匹配 → 進入第負一層。

---

## 第負一層：並行化評估

> **核心原則**：決策第一步不是「這是什麼類型的任務」，而是「這個工作可以讓多少人去做？」

### 派發前複雜度關卡（Dispatch Complexity Gate，強制）

> **來源**：0.1.1-W15-004 — W15-001 派發時，PM 將認知負擔 > 10 的整包任務直接派發給單一代理人，未先拆分。

**任何派發（單一或並行）前，PM 必須先評估目標任務的認知負擔指數。**

| 認知負擔指數 | 判定 | 行動 |
|-------------|------|------|
| <= 10 | 通過 | 繼續進入並行化判斷 |
| > 10 | 阻塞 | 先拆分子任務再派發（AskUserQuestion #6） |

**評估方式**：`認知負擔指數 = 變數數 + 分支數 + 巢狀深度 + 依賴數`（詳見 cognitive-load.md）

**快速判斷指標**（任一超標即視為 > 10）：

| 指標 | 閾值 | 超標行動 |
|------|------|---------|
| 修改檔案數 | > 5 | 必須拆分 |
| 跨架構層級數 | > 2 | 必須拆分 |
| 依賴模組數 | > 3 | 必須拆分 |

**禁止行為**：

| 禁止 | 說明 |
|------|------|
| 整包派發認知負擔 > 10 的任務給單一代理人 | 必須先拆分為子任務 |
| 跳過評估直接派發 | 每次派發前都必須通過本關卡 |

**拆分後重新評估**：拆分產生的每個子任務必須重新通過本關卡（指數 <= 10），確保遞迴拆分至可管理粒度。

### 並行化判斷

接收到任務後，主線程必須先問自己：
1. **這個任務可以拆成幾個獨立部分？**
2. **拆分後的部分有依賴關係嗎？**
3. **哪些可以同時開始？**
4. **我需要親自處理的部分是什麼？**（應該極少）

**主線程允許親自處理**：用戶溝通、任務拆分設計、Ticket 建立和指派、閱讀報告和最終決策、驗收結果。其餘一律派發代理人。

**Subagent 禁止事項**：Subagent 遇到多方案選擇或路由決策時，**禁止**直接向用戶呈現選擇（禁止使用 AskUserQuestion），必須在產出物中標記「需 PM 決策」後回報主線程，由 PM 中轉。詳見：.claude/pm-rules/askuserquestion-rules.md（使用對象限制章節）

**派發方式判斷**：「Agent A 的發現會改變 Agent B 正在進行的工作嗎？」

| 判斷結果 | 路由 |
|---------|------|
| 否（各自獨立） | Task subagent 並行派發 |
| 是（需即時互動）且成本合理 | Agent Teams 派發 |
| 是 但成本不合理 | Task subagent + PM 中轉 |

### 派發模式選擇規則

派發代理人時，**預設使用背景模式**（`run_in_background: true`）。完整的派發模式表格、例外場景和背景派發後跟蹤規則：

> 詳見：.claude/pm-rules/parallel-dispatch.md（派發模式：預設背景章節）
> AskUserQuestion 強制使用規則：.claude/pm-rules/askuserquestion-rules.md

---

## 第零層：明確性檢查

> 當定義不明確時，應該往上詢問確認，而非強行做出判斷。
>
> **工具要求**：向用戶呈現選項供選擇時，必須使用 AskUserQuestion 工具，禁止文字提問。

| 情境 | 觸發條件 | 確認目標 |
|------|---------|---------|
| 不確定性詞彙 | 包含「好像」「可能」「似乎」等 | 確認問題性質 |
| 複雜需求 | 觸發 3+ 代理人 | 確認 use case 和優先級 |
| 模糊需求 | 無法用「動詞+目標」描述 | 確認具體需求 |

---

## 第一層：訊息類型判斷

| 訊息類型 | 識別關鍵字 |
|---------|-----------|
| 問題 | "怎麼樣"、"進度"、"為什麼"、"如何"、"是什麼"、"?" |
| 命令 | "實作"、"建立"、"修復"、"處理"、"執行"、"開始"、"測試"、"驗證"、"調整" |

---

## 第二層：問題處理流程

> 所有查詢都應派發代理人，主線程禁止直接執行查詢命令、WebFetch、WebSearch。

| 問題類型 | 路由 |
|---------|------|
| Ticket/版本進度查詢 | → Explore agent |
| 外部資源 | → oregano-data-miner |
| 架構/設計諮詢 | → system-analyst / system-designer |
| 環境/安全/效能 | → system-engineer / security-reviewer / ginger |

**SKILL 提示強制採納**：當 Hook 輸出 `[SKILL 提示]` 時，**必須**使用建議的 SKILL 指令。

> 完整派發對照表：.claude/pm-rules/query-vs-research.md

---

## 第二層半：基於檔案類型的派發規則

| 檔案類型 | 派發代理人 |
|---------|-----------|
| `.claude/hooks/*.py` 新增/設計 | basil-hook-architect |
| `.claude/hooks/*.py` 優化/修正 | thyme-python-developer |
| `*.py`（其他） | thyme-python-developer |
| `*.dart`（lib/ 或 test/） | parsley-flutter-developer |
| `.md`（.claude/rules/ 或 docs/） | 主線程允許編輯 |

> Hook 派發原則：「Hook 該怎麼運作」→ basil；「Hook 程式碼該怎麼寫」→ thyme
> IMP-003 防護：.claude/error-patterns/implementation/IMP-003-refactoring-scope-regression.md

### 代理人可編輯路徑對照表（Source of Truth）

> **派發即授權**：PM 派發任務時已驗證路徑權限。subagent 被派發後應放心執行，無需預先評估風險。被阻擋時上報 PM 即可。
>
> **唯一來源**：本表是代理人路徑權限的唯一定義。其他檔案（skip-gate.md、agent 定義等）引用本表，不自行維護路徑清單。

| 代理人 | 可編輯路徑（glob） | 說明 |
|--------|-------------------|------|
| thyme-python-developer | `.claude/hooks/*.py`、`.claude/skills/**/*.py`、`.claude/lib/*.py` | Hook 優化/修正、Skill 程式碼、共用程式庫 |
| parsley-flutter-developer | `ui/lib/**/*.dart`、`ui/test/**/*.dart`、`ui/pubspec.yaml` | Flutter 應用程式碼和測試 |
| basil-hook-architect | `.claude/hooks/*.py`、`.claude/lib/*.py` | Hook 新增/設計、共用程式庫設計 |
| fennel-go-developer | `server/**/*.go` | Go 後端程式碼 |
| sage-test-architect | `ui/test/**/*.dart` | 測試設計（不修改實作碼） |

---

## 第三層：命令處理流程

```
是命令
    |
    v
是開發/修改命令? ─是→ [Level 2] Hook 系統驗證 Ticket
               |
               └─否→ 是除錯命令? ─是→ [強制] 派發 incident-responder
                                |
                                └─否→ 其他命令類型 (ignore)
```

| 判斷條件 | 路由 |
|---------|------|
| 開發命令（實作/建立/新增/重構） | Hook 驗證 Ticket → 行為分類（IMP/TST/ADJ/ANA） |
| 安全相關（auth/token/permission） | → 強制派發 security-reviewer |
| 除錯命令（test failed/crash/bug） | → 強制派發 incident-responder |
| **執行中發現技術債/問題/回歸/超範圍需求** | → **[強制] 立即 `/ticket create`，不詢問，不中斷主線** |

---

## 第三層半：執行中額外發現規則（技術債/問題/超範圍需求）

> 當 PM 或 Agent 在 Ticket 執行過程中發現任何需要追蹤的問題時，適用本規則。

**核心規則：發現即建立，不詢問確認**

- 發現了需要追蹤的問題嗎？→ 是 → **直接 /ticket create**
- 要不要處理、優先級高不高 → 這是後續 acceptance-auditor 審核的職責，不是此刻的決策點

### 子任務 vs 獨立 Ticket 判斷

| 判斷條件 | 建立方式 | 範例 |
|---------|---------|------|
| 因執行當前 Ticket 而產生（因果關係） | 子任務（`/ticket create --parent {current_id}`） | 實作中發現需要先重構某模組 |
| 與當前 Ticket 相同功能模組 | 子任務 | 同一個 feature 的額外驗收條件 |
| 獨立問題、不同模組 | 獨立 Ticket | 發現另一個模組的 bug |
| 跨版本的技術債 | 獨立 Ticket（歸入 todolist） | 長期架構改善 |

> 識別條件、強制處理流程、禁止行為清單：.claude/pm-rules/plan-to-ticket-flow.md（「執行中額外發現」章節）

---

## 第四層：Ticket 執行流程

```
[Ticket 驗證通過]
    |
    v
是「繼續任務鏈」類請求? ─是→ [強制] 並行可行性分析 → 主動建議並行
    |
    └─否→ pending? → creation_accepted?
          |           ─否→ [強制] 並行審核（acceptance-auditor + system-analyst）
          |                → 通過後設定 creation_accepted: true
          |           ─是→ claim → 階段判斷
          in_progress? → 繼續執行
          completed? → [AskUserQuestion] 後續步驟選擇
          blocked? → 升級 PM
```

**建立後審核檢查（強制）**：pending Ticket 認領前必須 `creation_accepted: true`，否則強制並行派發 acceptance-auditor + system-analyst 審核。豁免：已審核父 Ticket 的子任務。

**Wave 邊界檢查（強制）**：當用戶指定「繼續 Wx」時，**必須**只處理該 Wave 的任務，禁止跨 Wave 執行。

**Handoff 方向選擇（AskUserQuestion）**：當 handoff 有多個可能方向時，**必須**使用 AskUserQuestion 讓使用者選擇。

> Ticket 生命週期：.claude/pm-rules/ticket-lifecycle.md
> 並行派發規則：.claude/pm-rules/parallel-dispatch.md

---

## 第五層：TDD 階段判斷

| 階段 | 代理人 | 進入條件 |
|------|-------|---------|
| SA 前置審查 | system-analyst | 新功能/架構變更 |
| Phase 1 | lavender-interface-designer | SA 通過 |
| Phase 2 | sage-test-architect | Phase 1 完成 |
| Phase 3a | pepper-test-implementer | Phase 2 完成 |
| Phase 3b | parsley-flutter-developer | Phase 3a 完成 |
| Phase 4a | /parallel-evaluation B（多視角重構分析） | Phase 3b 完成（標準流程） |
| Phase 4b | cinnamon-refactor-owl（依 4a 報告執行） | Phase 4a 完成（或豁免時直接進入） |
| Phase 4c | /parallel-evaluation A（多視角再審核） | Phase 4b 完成（標準流程） |

> TDD 完整流程：.claude/pm-rules/tdd-flow.md

> **Agent Registry 關係**（v0.1.2 規劃）：上方 TDD 階段代理人對應表是**決策規則**（本文件是決策引擎）。未來 Agent Registry（`.claude/agents/registry.yaml`）將作為**能力資料層**，提供機器可讀的代理人能力查詢和派發驗證，但不取代本文件的決策邏輯。架構分工：decision-tree（判斷需要什麼能力）→ registry（查詢誰有這個能力）→ Hook（驗證選定的 Agent 符合）。詳見：docs/work-logs/v0.1.1/tickets/0.1.1-W14-001-analysis.md（附錄：已確認設計決策）

---

## 第六層：事件回應流程

```
錯誤/失敗發生
    |
    v
是工具/CLI 本身報錯? ─是→ [CLI 調查流程] --help → 字面解讀 → 比對狀態 → 歸因
    |                       → 語法問題 → 修正後重試
    |                       → 確認非語法問題 → 進入下方邏輯錯誤流程
    |
    +─── 否（程式碼/邏輯錯誤）→ [強制] /pre-fix-eval → 派發 incident-responder
                                → 建立 Ticket → 對應代理人修復
```

> CLI 調查流程詳見：.claude/pm-rules/incident-response.md（CLI/工具失敗調查步驟）
> 錯誤分類和派發對應表：.claude/pm-rules/incident-response.md

---

## 第七層：完成判斷流程

**ANA Ticket 結論轉化檢查（強制）**：ANA 類型 Ticket 完成前，必須確認分析結論已轉化為後續 Ticket。

> **來源**：PC-017 — ANA Ticket 完成時分析結論未轉化為後續 Ticket，導致分析成果無法落地。

**驗收方式確認（AskUserQuestion）**：complete 前必須確認驗收方式（標準/簡化/先完成後補）。

**主動勾選驗收條件（強制）**：確認驗收方式後、執行 complete 前，PM **必須**主動勾選驗收條件，禁止依賴 CLI 擋回才補勾。

```
任務執行完成
    |
    v
Ticket type == ANA?
    |
    +-- 是 → [強制] 確認分析結論已轉化為 Ticket
    |         → children 或 spawned_tickets 非空?
    |           +-- 是 → 繼續標準完成流程
    |           +-- 否 → 建立修復+防護 Ticket 後再繼續
    |
    +-- 否 → 繼續標準完成流程
    |
    v
Step 1: 確認驗收方式（AskUserQuestion #1）
    |
    v
Step 2: 逐條確認驗收條件已滿足
    |
    v
Step 3: ticket track check-acceptance <id>
    |
    v
Step 4: ticket track complete <id>
```

**ANA 結論轉化規則**：

| 檢查項 | 說明 |
|--------|------|
| children 非空 | ANA Ticket 已建立子任務（修復/防護等） |
| spawned_tickets 非空 | ANA Ticket 已衍生獨立 Ticket |
| 任一滿足即通過 | 至少有一個後續 Ticket 追蹤分析結論 |
| 均為空 | **阻塞完成**：必須先建立後續 Ticket（修復+防護）再繼續 |

**下一步選擇（AskUserQuestion）**：有多個後續 Ticket 可選時，必須讓使用者選擇。

> 驗收流程詳細規則：.claude/pm-rules/ticket-lifecycle.md（Complete 前主動勾選驗收條件章節）

---

## 第八層：完成後路由（Commit-Evaluate-Handoff 循環）

任務或階段完成後的統一路由機制（Checkpoint 0 → 1 → 1.5 → 2 → 3 → 4）。

**核心判斷規則**：

| Checkpoint | 判斷條件 | 路由 |
|------------|---------|------|
| 0 建立後 Handoff | 可並行派發? | 是 → 留在 session 並行派發；否 → commit + handoff |
| 1 變更狀態 | 有未提交變更? | 是 → commit；無 → 跳至 Checkpoint 3 |
| 1.5 錯誤學習 | commit 成功後 | AskUserQuestion #16 |
| 1.8 合併回 main | 在開發分支上? | 是 → merge --no-ff → main → 刪除開發分支；否 → 跳過 |
| 2 情境評估 | [強制查詢] ticket track list | 情境 D/A/B/C（見下方） |
| 3 後續路由 | 任務類型 | AskUserQuestion #13 |
| 4 parallel-evaluation | 階段完成後 | AskUserQuestion #14 |

**Checkpoint 2 情境評估（強制先查詢再路由，禁止依賴記憶）**：

| 情境 | 條件 | 路由 |
|------|------|------|
| D（優先） | ticket 含 tdd_phase 欄位 | D1: Phase 1/2 → 全自動下一 Phase；D1a: Phase 3a → 3b 拆分評估（見 tdd-flow.md）後派發 3b；D2: Phase 3b → [自動檢查豁免條件] → 符合豁免 → 全自動 4b / 不符合 → #13（選擇 4a 或 4b）；D3a: 4a → 全自動 4b；D3b: 4b 標準 → 全自動 4c / 豁免 → /tech-debt-capture + #13；D3c: 4c → /tech-debt-capture + #13 |
| A（#11a） | ticket 仍 in_progress | Context 刷新 Handoff |
| B（#11b） | ticket completed + 同 Wave 有 pending | 任務切換 Handoff |
| C | ticket completed + 同 Wave 無 pending | [強制] /parallel-evaluation Wave 審查（必須包含 linux 常駐審查委員，見 parallel-dispatch.md 多視角審查固定三人組）→ C1: 有其他 Wave → #3a；C2: 全完成 → [強制] 版本收尾技術債整理（見 version-progression.md）→ /version-release check + #13 |

**與現有層級的銜接**：第四層（建立完成）→ Checkpoint 0；第五層（Phase 完成）→ Checkpoint 1；第六層（incident 完成）→ Checkpoint 3；第七層（complete）→ Checkpoint 1

**Handoff 強制動作**：PM **必須**執行 `/ticket handoff`，**禁止**手動建立交接文件。前須 `ticket handoff --status` 確認無殘留。

**Resume 後接手（Checkpoint R）**：resume 後先確認範圍再 claim，不直接開始實作。

> Checkpoint 0-4 完整流程、情境子規則、Checkpoint R 詳細步驟：.claude/references/decision-tree-checkpoint-details.md
> AskUserQuestion 場景 11-17：.claude/pm-rules/askuserquestion-rules.md
> 模板：.claude/references/ticket-askuserquestion-templates.md

---

## 代理人觸發優先級

```
Level 2: Hook 系統驗證（命令入口，最早觸發）
Level 1: incident-responder（錯誤/失敗最高優先）
Level 2: system-analyst（架構審查）
Level 3: security-reviewer（安全審查）
Level 4: 其他專業代理人（DBA, SE, SD, ginger 等）
Level 5: TDD 階段代理人 + thyme-python-developer
```

| 觸發組合 | 處理方式 |
|---------|---------|
| 錯誤 + 任何 | incident-responder 先處理 |
| SA + security | SA 先審查架構 |
| 多個專業代理人 | SA 協調或分解為多 Ticket |

---

## 派發記錄要求

所有 Ticket 必須包含 `decision_tree_path` 欄位（entry_point、final_decision、rationale）。

---

## 強制執行命令

| 情境 | 強制命令 |
|------|---------|
| 錯誤/失敗發生 | `/pre-fix-eval` |
| Phase 4 完成 | `/tech-debt-capture` |
| 版本發布前 | `/version-release check` |
| 用戶決策確認 | AskUserQuestion（17 個場景，詳見 askuserquestion-rules.md） |
| Commit 後 | AskUserQuestion #16（錯誤學習）→ #11（Handoff 確認） |
| 流程省略偵測 | AskUserQuestion #12（省略確認） |
| **執行中發現技術債/問題/回歸/超範圍需求** | **`/ticket create` 建立 pending Ticket（立即，不詢問，不延後）** |
| **ANA Ticket 完成前** | **確認 children 或 spawned_tickets 非空（PC-017）** |
| **派發代理人前** | **派發前複雜度關卡：認知負擔指數 > 10 必須先拆分（W15-004）** |

---

## 違規處理

| 違規行為 | 處理方式 |
|---------|---------|
| 跳過 incident-responder 直接修復 | 停止，回滾，重新走流程 |
| 未建立 Ticket 就開始實作 | 停止，先建立 Ticket |
| 跳過 SA 前置審查（新功能） | 停止，派發 SA |
| 跳過 Phase 4 | 強制執行 Phase 4 |
| 計畫執行中發現額外需求未立即建立 Ticket | 補建 Ticket，記錄遺漏原因 |
| ANA Ticket 完成時無後續 Ticket（PC-017） | 阻塞完成，先建立修復+防護 Ticket |
| **跳過複雜度關卡直接派發** | **停止派發，執行認知負擔評估，超標則先拆分** |

---

## 相關文件

- .claude/pm-rules/parallel-dispatch.md - 並行派發指南（場景表、安全檢查）
- .claude/pm-rules/tdd-flow.md - TDD 流程
- .claude/pm-rules/incident-response.md - 事件回應流程（錯誤分類表）
- .claude/pm-rules/ticket-lifecycle.md - Ticket 生命週期（驗收流程）
- .claude/pm-rules/skip-gate.md - Skip-gate 防護
- @.claude/pm-rules/askuserquestion-rules.md - AskUserQuestion 強制使用規則
- .claude/references/decision-tree-checkpoint-details.md - 第八層 Checkpoint 詳細流程（情境 A/B/C/D、#11a/11b、Handoff 說明）

---

**Last Updated**: 2026-03-23
**Version**: 7.33.0 - 情境 C Wave 審查補充 linux 常駐審查委員要求（多視角固定三人組）
