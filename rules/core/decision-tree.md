# 主線程決策樹

本文件定義主線程（rosemary-project-manager）的完整決策流程，是規則系統的核心。

> **核心原則**：所有任務入口都從這裡開始，其他規則都是它的支撐或延伸。
>
> **管理哲學**：主管的價值不在於解決問題的速度，而在於讓團隊的人力發揮到極致。
> 詳見：.claude/skills/manager/SKILL.md

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
    +-- 可並行拆分? ─是→ Agent A 的發現會改變 Agent B 正在進行的工作?
    |                      |
    |                      +─ 否 → [並行派發 Task subagent]
    |                      |
    |                      +─ 是 → 3-4x 成本合理?
    |                               |
    |                               +─ 是 → [Agent Teams 派發]（/agent-team）
    |                               +─ 否 → [Task subagent + PM 中轉]
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

接收到任務後，主線程必須先問自己：
1. **這個任務可以拆成幾個獨立部分？**
2. **拆分後的部分有依賴關係嗎？**
3. **哪些可以同時開始？**
4. **我需要親自處理的部分是什麼？**（應該極少）

**主線程允許親自處理**：用戶溝通、任務拆分設計、Ticket 建立和指派、閱讀報告和最終決策、驗收結果。其餘一律派發代理人。

**派發方式判斷**：「Agent A 的發現會改變 Agent B 正在進行的工作嗎？」

| 判斷結果 | 路由 |
|---------|------|
| 否（各自獨立） | Task subagent 並行派發 |
| 是（需即時互動）且成本合理 | Agent Teams 派發 |
| 是 但成本不合理 | Task subagent + PM 中轉 |

> 場景表和詳細規則：.claude/rules/guides/parallel-dispatch.md
> AskUserQuestion 強制使用規則：.claude/rules/core/askuserquestion-rules.md

---

## 第零層：明確性檢查

> 當定義不明確時，應該往上詢問確認，而非強行做出判斷。

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

> 完整派發對照表：.claude/rules/guides/query-vs-research.md

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
| **計畫執行中發現超範圍需求** | → **[強制] 立即 `/ticket create`，不中斷主線** |

---

## 第三層半：Plan Mode 執行中額外發現規則

> 當 PM 或 Agent 在計畫執行中發現超出原計畫範圍的需求時，適用本規則。

**識別條件**：超出當前 Ticket scope 的延伸工作、未在原計畫中涵蓋的設計缺口

**強制動作**：

```
發現超範圍需求（執行中）
    |
    v
[強制] 立即 /ticket create → 建立 pending Ticket
    |
    v
繼續執行當前計畫主線（不中斷、不延後）
```

| 禁止行為 | 說明 |
|---------|------|
| 忽視不建 Ticket | 額外發現必須立即追蹤 |
| 中斷主線去處理額外發現 | 先建 Ticket，完成當前任務後再執行 |
| 口頭回報取代 Ticket | 必須有可追蹤的 Ticket 記錄 |
| 等計畫完成後補建 | 必須**立即**建立 |

> 詳細觸發條件和流程：.claude/rules/flows/plan-to-ticket-flow.md（「執行中額外發現」章節）

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

**建立後審核檢查（強制）**：pending Ticket 認領前必須 `creation_accepted: true`，否則強制並行派發 acceptance-auditor + system-analyst 審核。豁免：DOC 類型或已審核父 Ticket 的子任務。

**Wave 邊界檢查（強制）**：當用戶指定「繼續 Wx」時，**必須**只處理該 Wave 的任務，禁止跨 Wave 執行。

**Handoff 方向選擇（AskUserQuestion）**：當 handoff 有多個可能方向時，**必須**使用 AskUserQuestion 讓使用者選擇。

> Ticket 生命週期：.claude/rules/flows/ticket-lifecycle.md
> 並行派發規則：.claude/rules/guides/parallel-dispatch.md

---

## 第五層：TDD 階段判斷

| 階段 | 代理人 | 進入條件 |
|------|-------|---------|
| SA 前置審查 | system-analyst | 新功能/架構變更 |
| Phase 1 | lavender-interface-designer | SA 通過 |
| Phase 2 | sage-test-architect | Phase 1 完成 |
| Phase 3a | pepper-test-implementer | Phase 2 完成 |
| Phase 3b | parsley-flutter-developer | Phase 3a 完成 |
| Phase 4 | cinnamon-refactor-owl | Phase 3b 完成 |

> TDD 完整流程：.claude/rules/flows/tdd-flow.md

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

> CLI 調查流程詳見：.claude/rules/flows/incident-response.md（CLI/工具失敗調查步驟）
> 錯誤分類和派發對應表：.claude/rules/flows/incident-response.md

---

## 第七層：完成判斷流程

**驗收方式確認（AskUserQuestion）**：complete 前必須確認驗收方式（標準/簡化/先完成後補）。

**下一步選擇（AskUserQuestion）**：有多個後續 Ticket 可選時，必須讓使用者選擇。

> Ticket 生命週期和驗收流程：.claude/rules/flows/ticket-lifecycle.md

---

## 第八層：完成後路由（Commit-Evaluate-Handoff 循環）

任務或階段完成後的統一路由機制，確保每個完成點都有明確的確認。

```
任務/階段完成
    |
    v
[Checkpoint 0] 建立後 Handoff 判斷（Ticket 建立/拆分完成後適用）
    |
    +-- 建立了子任務或獨立 Ticket，且可並行派發?
    |   （條件：creation_accepted + 檔案無重疊 + 敘述完善 + 符合並行安全條件）
    |   → 留在當前 session → 並行派發代理人 → 進入 Checkpoint 1
    |
    +-- 建立了子任務且不可並行派發?
    |   → commit → handoff → 新 session 逐一處理子任務
    |
    +-- 建立了獨立 Ticket（非子任務，不可並行）?
    |   → commit → handoff → 新 session 認領執行
    |
    +-- 非建立/拆分場景（執行完成、Phase 完成等）?
        → 跳過，進入 Checkpoint 1
    |
    v
[Checkpoint 1] 變更狀態檢查
    |
    +-- git status 有未提交變更?
    |   |
    |   +-- 是 + 批量變更 → AskUserQuestion #15（備份確認）
    |   +-- 是 → 建議 commit（/commit-as-prompt）
    |   +-- 否 → [Checkpoint 3]
    |
    v
[Checkpoint 1.5] 錯誤學習經驗確認（AskUserQuestion #16）
    |
    +-- 記錄 → 執行 /error-pattern add → 可能產生新 commit → 回到 Checkpoint 1.5
    +-- 無需記錄 / 稍後記錄 → 繼續
    |
    v
[Checkpoint 2] Commit 後情境評估（每次 commit 後，PM 必須先查詢再選擇路由）
    |
    +-- [強制查詢] ticket track list --wave W{n} --status pending,in_progress
    |   → 取得數據後再評估，禁止依賴記憶判斷
    |
    +-- [前置分流] 當前 commit 屬於 TDD Phase 完成?
    |   識別：PM 工作流為 TDD 模式，已完成 ticket 含 tdd_phase 欄位
    |
    +-- [情境 D] TDD Phase 完成路由（優先於情境 A/B/C）
    |   |
    |   +-- [D1] Phase 1/2/3a 完成 → 全自動，無分岔
    |   |       → 直接派發下一 Phase 代理人，無需 AskUserQuestion
    |   |       Phase 1→2: sage-test-architect（Phase 2 測試設計）
    |   |       Phase 2→3a: pepper-test-implementer（Phase 3a 策略規劃）
    |   |       Phase 3a→3b: parsley-flutter-developer（Phase 3b 實作）
    |   |
    |   +-- [D2] Phase 3b 完成 → AskUserQuestion #13（Phase 3b 路由確認）
    |   |       +-- /parallel-evaluation A → 程式碼審查後進 Phase 4（Recommended）
    |   |       +-- 直接進入 Phase 4（派發 cinnamon-refactor-owl）
    |   |       +-- 先 commit 再決定
    |   |
    |   +-- [D3] Phase 4 完成 → [強制] /tech-debt-capture
    |           → 不可跳過，必須優先於 Wave 收尾判斷
    |           → /tech-debt-capture 完成後 AskUserQuestion #13（Phase 4 + tech-debt 路由）
    |           → commit 後回到情境 B/C 評估
    |
    +-- [情境 A] 查詢結果有自己的 ticket 仍 in_progress
    |   目的：Context 刷新（新 session 繼續同一 ticket）
    |   → AskUserQuestion #11a
    |   +-- Handoff (Context 刷新) → [強制] /ticket handoff → 結束 context
    |   +-- 繼續在此 session → [Checkpoint 3]
    |
    +-- [情境 B] ticket 已 completed + 同 Wave 有 pending 任務
    |   目的：任務切換（切換到下一個 ticket）
    |   → AskUserQuestion #11b
    |   +-- Handoff 到 {next_ticket_id} → [強制] /ticket handoff → 結束 context
    |   +-- 此 session 繼續 {next_ticket_id} → 直接 claim → [Checkpoint 3]
    |   +-- 查看所有待處理任務再決定 → 列出任務 → [Checkpoint 3]
    |
    +-- [情境 C] ticket 已 completed + 同 Wave 無待處理任務（Wave 完成）
        → [再次查詢] ticket track list --status pending（查詢版本其他 Wave）
        |
        +-- [情境 C1] 版本有其他 Wave 的 pending 任務
        |   → AskUserQuestion #3a（Wave 收尾 + 開始下一 Wave）
        |
        +-- [情境 C2] 版本無任何待處理任務（版本全部完成）
            → [強制] /version-release check
            → AskUserQuestion #13（版本推進確認）
    |
    v
[Checkpoint 3] 後續任務路由（AskUserQuestion #13）
    |
    +-- 分析完成 → 實作 or /parallel-evaluation F
    +-- 規劃完成 → /parallel-evaluation C/G or TDD
    +-- Phase 3b 完成 → /parallel-evaluation A or Phase 4
    +-- Phase 4 完成 → /tech-debt-capture → 收尾
    +-- 規則/Skill 變更 → /parallel-evaluation G
    +-- 無後續 → 場景 3（Wave 收尾）
    |
    v
[Checkpoint 4] parallel-evaluation 觸發（AskUserQuestion #14）
    |
    +-- 執行 → /parallel-evaluation 情境 X → 回到 Checkpoint 1
    +-- 跳過 → AskUserQuestion #12（省略確認）→ 進入下一步
```

**與現有層級的銜接**：

| 現有出口 | 進入第八層入口 |
|---------|-------------|
| 第四層 Ticket 建立/拆分完成 | Checkpoint 0（建立後 Handoff 判斷） |
| 第五層 Phase 3b/4 完成 | Checkpoint 1 |
| 第六層 incident 分析完成 | Checkpoint 3 |
| 第七層 Ticket complete | 既有場景 2 → Checkpoint 1 |
| SA 審查完成 | Checkpoint 3 |

**Checkpoint 2 情境評估規則**：每次 commit 後 PM **必須**先執行強制查詢再評估情境，禁止依賴記憶判斷。

- **強制查詢**：`ticket track list --wave W{n} --status pending,in_progress`（取得數據後再選路由）
- **情境 D**（TDD Phase 完成，識別依據：ticket 含 tdd_phase 欄位，**優先於 A/B/C**）：
  - D1（Phase 1/2/3a）→ 全自動直接進入下一 Phase，無 AskUserQuestion
  - D2（Phase 3b）→ AskUserQuestion #13（/parallel-evaluation A 或直接 Phase 4）
  - D3（Phase 4）→ [強制] /tech-debt-capture → AskUserQuestion #13（tech-debt 後路由）→ commit 後情境 B/C
- **情境 A**（查詢結果有 in_progress ticket）→ AskUserQuestion #11a（Context 刷新），新 session 繼續同一 ticket
- **情境 B**（ticket completed + 同 Wave 有 pending 任務）→ AskUserQuestion #11b（任務切換），切換到下一個 ticket
- **情境 C**（ticket completed + 同 Wave 無待處理任務）→ 再次查詢版本全狀態 → 分為 C1 或 C2
- **情境 C1**（版本有其他 Wave pending）→ AskUserQuestion #3a（Wave 收尾 + 開始下一 Wave）
- **情境 C2**（版本無任何 pending）→ [強制] /version-release check → AskUserQuestion #13

**Handoff 強制動作**：選擇任何 Handoff 選項後，PM **必須**執行 `/ticket handoff` 建立標準 `pending/*.json` 檔案，**禁止**手動建立 `.claude/handoff/*.md` 交接文件。`/ticket handoff` 會自動判斷下一步方向（父/子/兄弟），確保 `resume --list` 在下一個 session 能正確偵測待恢復任務。

**流程省略防護（AskUserQuestion #12）**：主線程輸出含省略意圖關鍵字時，process-skip-guard-hook 自動偵測並提醒確認。

> AskUserQuestion 場景 11-17 詳見：.claude/rules/core/askuserquestion-rules.md
> 模板詳見：.claude/references/ticket-askuserquestion-templates.md

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
| **計畫執行中發現超範圍需求** | **`/ticket create` 建立 pending Ticket（立即，不延後）** |

---

## 違規處理

| 違規行為 | 處理方式 |
|---------|---------|
| 跳過 incident-responder 直接修復 | 停止，回滾，重新走流程 |
| 未建立 Ticket 就開始實作 | 停止，先建立 Ticket |
| 跳過 SA 前置審查（新功能） | 停止，派發 SA |
| 跳過 Phase 4 | 強制執行 Phase 4 |
| 計畫執行中發現額外需求未立即建立 Ticket | 補建 Ticket，記錄遺漏原因 |

---

## 相關文件

- .claude/rules/guides/parallel-dispatch.md - 並行派發指南（場景表、安全檢查）
- .claude/rules/flows/tdd-flow.md - TDD 流程
- .claude/rules/flows/incident-response.md - 事件回應流程（錯誤分類表）
- .claude/rules/flows/ticket-lifecycle.md - Ticket 生命週期（驗收流程）
- .claude/rules/forbidden/skip-gate.md - Skip-gate 防護
- @.claude/rules/core/askuserquestion-rules.md - AskUserQuestion 強制使用規則

---

**Last Updated**: 2026-03-05
**Version**: 7.8.0 - 第六層新增工具失敗 vs 邏輯失敗分流（PC-003）
