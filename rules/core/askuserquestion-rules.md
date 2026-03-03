# AskUserQuestion 強制使用規則

本文件定義所有需要使用 AskUserQuestion 工具的場景和規範。這是 AskUserQuestion 規則的唯一 Source of Truth。

---

## 背景

### 為什麼需要 AskUserQuestion

PM 用開放式提問（如「要並行處理嗎？」）時，用戶的自然語言回答可能被 Hook 系統誤判為開發命令（觸發 command-entrance-gate-hook）。使用 Claude Code 原生的 AskUserQuestion 工具可消除此風險。

### AskUserQuestion 是 Deferred Tool

AskUserQuestion 是 deferred tool，使用前**必須**先載入：

```
ToolSearch("select:AskUserQuestion")
```

載入後即可直接呼叫。每個 Hook 提醒訊息都包含此提示。

---

## 強制規則

### 規則 1：決策確認必須使用 AskUserQuestion

PM 需要用戶確認決策時，**必須使用 AskUserQuestion 工具**，而非文字提問。

### 規則 2：ToolSearch 前置載入

使用 AskUserQuestion 前必須先執行 `ToolSearch("select:AskUserQuestion")` 載入。

### 規則 3：禁止文字提問替代

禁止使用開放式文字問句讓用戶自由回答可能觸發 Hook 的詞彙。

---

## 場景列表

### 15 個強制使用場景

| # | 場景 | 觸發條件 | 決策點 | Hook 提醒 |
|---|------|---------|--------|-----------|
| 1 | 驗收方式確認 | ticket track complete 前 | ticket-lifecycle 驗收階段 | acceptance-gate-hook |
| 2 | Complete 後下一步 | ticket track complete 後 | ticket-lifecycle 完成階段 | acceptance-gate-hook |
| 3 | Wave/任務收尾確認 | Wave 無 pending Ticket | ticket-lifecycle 收尾 | parallel-suggestion-hook |
| 4 | 方案選擇 | 多個技術方案 | 決策樹第負一層 | prompt-submit-hook |
| 5 | 優先級確認 | 多任務排序 | 決策樹第負一層 | prompt-submit-hook |
| 6 | 任務拆分確認 | 認知負擔 > 10 | 決策樹第負一層 | prompt-submit-hook |
| 7 | 派發方式選擇 | Task subagent / Agent Teams / 序列 | 決策樹第負一層 | askuserquestion-reminder-hook |
| 8 | 執行方向確認 | 並行/序列、先後順序 | 決策樹第負一層 | - |
| 9 | Handoff 方向選擇 | 多個兄弟/子任務可選 | ticket-lifecycle 完成階段 | - |
| 10 | 開始/收尾確認 | 確認是否開始執行 | 決策樹第負一層 | - |
| 11 | Commit 後情境感知 Handoff | git commit 後依情境路由（11a/11b，或轉 #3） | 決策樹第八層 | commit-handoff-hook |
| 12 | 流程省略確認 | 省略意圖偵測 | 決策樹第八層 | process-skip-guard-hook |
| 13 | 後續任務路由確認 | 任務完成後 | 決策樹第八層 | phase-completion-gate（擴充） |
| 14 | parallel-evaluation 觸發確認 | 階段完成後 | 決策樹第八層 | phase-completion-gate（擴充） |
| 15 | Bulk 變更前備份確認 | 批量修改前 | 決策樹第八層 | parallel-suggestion-hook（擴充） |

**Hook 覆蓋狀態**：10/15 場景有 Hook 自動提醒（從 7/10 提升到 10/15 = 67%）。

### AskUserQuestion 工具能力

- 2-4 個選項，帶標籤和描述
- 單選（`multiSelect: false`）或多選（`multiSelect: true`）
- 自動提供「Other」選項供自由輸入
- markdown 預覽（方案比較時使用）

---

## 場景詳細說明

### 場景 1-2：驗收方式確認 + Complete 後下一步

**觸發**：`ticket track complete` 命令

**驗收方式確認選項**：

| 選項 | 說明 |
|------|------|
| 標準驗收（Recommended） | 派發 acceptance-auditor 執行完整驗收 |
| 簡化驗收 | DOC 類型或認知負擔 < 5 的任務 |
| 先完成後補驗收 | P0 緊急任務，24 小時內補驗收 |

**Complete 後下一步選項**（動態生成）：

| 選項 | 說明 |
|------|------|
| 開始 {Ticket-ID} - {標題} | 阻塞已解除或同 Wave pending 的 Ticket |
| Handoff 到父任務 | 任務鏈完成，返回父任務 |
| 結束當前 Wave | 所有任務已完成 |

### 場景 3：Wave/任務收尾確認

**觸發**：Checkpoint 2 情境 C（同 Wave 無待處理任務，需判斷版本狀態）

**收尾前步驟**（必須先執行）：
1. 列出本次修改的檔案清單
2. 告知 git 未提交狀態

**#3a：Wave 收尾 + 有下一個 Wave**

**觸發條件**：情境 C1（版本有其他 Wave 的 pending 任務）

**選項**：

| 選項 | 說明 |
|------|------|
| 開始 Wave X+1（{n} 個待處理任務）（Recommended） | 直接進入下一個 Wave |
| Handoff，下一 session 開始 Wave X+1 | 結束 context，下個 session 繼續 |
| 先提交變更再決定 | git commit 後重新確認 |

**#3b：版本收尾（無任何待處理任務）**

**觸發條件**：情境 C2（版本無任何 pending 任務）

**選項**：

| 選項 | 說明 |
|------|------|
| /version-release check 確認前置條件（Recommended） | 執行版本推進前置檢查 |
| 查看版本摘要（ticket track summary） | 確認全部任務已完成 |
| 延後版本推進 | 稍後再執行版本推進 |

### 場景 4-6：方案選擇 / 優先級確認 / 任務拆分確認

**觸發**：用戶提問包含方案選擇、優先級確認、任務拆分相關關鍵字

**任務拆分選項**：

| 選項 | 說明 |
|------|------|
| 需要拆分 | 認知負擔 > 10，進入拆分流程 |
| 不需拆分 | 直接派發執行 |
| 需要進一步評估 | 派發 SA 分析 |

### 場景 7：派發方式選擇

**觸發**：多任務派發（Task prompt 包含 2+ 個 Ticket ID）

**選項**：

| 選項 | 說明 |
|------|------|
| Task subagent | 各 Agent 獨立完成，不互相影響 |
| Agent Teams | Agent A 的發現會改變 Agent B 的工作 |
| 序列派發 | 有依賴關係，需按順序執行 |

### 場景 8-10：執行方向 / Handoff 方向 / 開始收尾

這 3 個場景目前無 Hook 自動提醒，依賴 PM 遵循本規則文件。

### 場景 11：Commit 後情境感知 Handoff

**觸發**：每次 `git commit` 成功後（PostToolUse/Bash Hook 偵測）

**路由邏輯**（PM 必須先評估再選擇子場景）：

| 情境 | 條件 | 路由 |
|------|------|------|
| A：Context 刷新 | ticket 仍 in_progress | #11a |
| B：任務切換 | ticket 已 completed + 有關聯待處理任務 | #11b |
| C：Wave 收尾 | ticket 已 completed + 無關聯待處理任務 | 跳至 #3，不使用 #11 |

**#11a：Context 刷新 Handoff**（情境 A — ticket 仍 in_progress）

```
question: "此 ticket 仍在進行中。要刷新 context 並在新 session 繼續嗎？"
```

| 選項 | 說明 |
|------|------|
| Handoff (Context 刷新)（Recommended） | 在新 session 以乾淨 context 繼續同一 ticket |
| 繼續在此 session 工作 | 留在當前 context 繼續 |

**#11b：任務切換 Handoff**（情境 B — ticket 已 completed，有關聯任務）

```
question: "Ticket 已完成。切換到下一個任務嗎？"
```

| 選項 | 說明 |
|------|------|
| Handoff 到 {next_ticket_id} - {title}（Recommended） | 在新 session 切換到下一個 ticket |
| 在此 session 繼續 {next_ticket_id} | 直接 claim，留在當前 context |
| 查看所有待處理任務後決定 | 列出後讓用戶選擇 |

**Handoff 後強制動作**：選擇任何 Handoff 選項後，PM **必須**執行 `/ticket handoff` 建立標準 `pending/*.json` 檔案。**禁止**手動建立 `.claude/handoff/*.md` 交接文件。這確保下一個 session 的 `resume --list` 能正確偵測待恢復任務。

### 場景 12：流程省略確認

**觸發**：Hook 偵測到主線程輸出含省略意圖關鍵字

**偵測的 6 類省略行為**：

| 類別 | 偵測關鍵字 |
|------|-----------|
| SKIP_AGENT_DISPATCH | 「不需要派發」「自行處理」「不用代理人」 |
| SKIP_ACCEPTANCE | 「跳過驗收」「不需要驗收」「省略驗收」 |
| SKIP_TDD_PHASE | 「跳過 Phase」「省略 Phase」「不需要 Phase」 |
| SKIP_PARALLEL_EVAL | 「跳過審核」「不需要評估」「跳過 parallel」 |
| SKIP_SA_REVIEW | 「不需要 SA」「跳過 SA」「不做架構審查」 |
| SKIP_PHASE4 | 「跳過 Phase 4」「不需要重構」「省略重構」 |

**選項**：

| 選項 | 說明 |
|------|------|
| 不省略，執行完整流程（Recommended） | 遵循標準流程 |
| 確認省略 | 用戶明確同意省略 |
| 簡化執行 | 精簡版本 |

### 場景 13：後續任務路由確認

**觸發**：分析/規劃/修改/TDD Phase 3b 或 Phase 4 tech-debt 後完成，有多個後續路由可選

> **TDD Phase 路由說明**：
> - Phase 1/2/3a 完成由**情境 D1 全自動**處理（直接派發下一 Phase 代理人，不走 AskUserQuestion）
> - Phase 3b 完成由**情境 D2** 觸發此場景（task_type: Phase 3b 完成）
> - Phase 4 完成由**情境 D3 強制** /tech-debt-capture 後觸發此場景（task_type: Phase 4 + tech-debt 完成）

**動態選項**（依 task_type 變化）：

| task_type | 選項 1 | 選項 2 | 選項 3 |
|-----------|--------|--------|--------|
| 分析完成 | 進入實作（建立 Ticket） | /parallel-evaluation F（結論審查） | 先 commit 再決定 |
| 規劃完成 | /parallel-evaluation C/G（審核） | 直接進入 TDD Phase 1 | 先 commit 再決定 |
| Phase 3b 完成 | /parallel-evaluation A（程式碼審查，Recommended）→ 後進 Phase 4 | 直接進入 Phase 4（派發 cinnamon-refactor-owl） | 先 commit 再決定 |
| Phase 4 + tech-debt 完成 | commit 並查看 Wave 狀態（Recommended） | Handoff，下個 session 繼續 Wave 路由 | 查看所有待處理 Ticket |
| incident 分析完成 | /parallel-evaluation F（結論審查） | 直接建立修復 Ticket | 先 commit 再決定 |
| Wave 完成（有下一 Wave） | 開始 Wave X+1（列出任務） | Handoff 到 Wave X+1 | 先 commit 再決定 |
| 版本完成（無待處理任務） | /version-release check | 查看 ticket track summary | 延後版本推進 |

### 場景 14：parallel-evaluation 觸發確認

**觸發**：TDD 階段完成或任務完成後，系統建議可用 parallel-evaluation

**對應情境**：

| TDD 階段/事件 | 建議情境 | 視角 |
|--------------|---------|------|
| Phase 3b 完成 | A（程式碼審查） | Reuse, Quality, Efficiency |
| Phase 4 開始前 | B（重構評估） | Redundancy, Coupling, Complexity |
| SA 審查完成 | C（架構評估） | Consistency, Impact, Simplicity |
| 規則/Skill 變更 | G（系統設計） | Consistency, Completeness, CogLoad |
| incident 分析 | F（結論審查） | Evidence, Alternatives, Scope |

**選項**：

| 選項 | 說明 |
|------|------|
| 執行 /parallel-evaluation 情境 X（Recommended） | 啟動多視角掃描 |
| 跳過，直接進入下一步 | 觸發場景 12 省略確認 |
| 執行其他情境 | 選擇不同的 parallel-evaluation 情境 |

### 場景 15：Bulk 變更前備份確認

**觸發**：即將進行大批量修改前（偵測到多檔案修改意圖）

**選項**：

| 選項 | 說明 |
|------|------|
| 先 commit 備份（Recommended） | 建立回退點 |
| 直接開始 | 不備份 |
| 查看變更範圍 | 確認後再決定 |

---

## 違規處理

| 違規行為 | 處理方式 |
|---------|---------|
| 文字提問替代 AskUserQuestion | 停止，改用 AskUserQuestion |
| 跳過確認直接執行 | 提醒後繼續 |
| 未載入就使用 AskUserQuestion | ToolSearch 載入後重試 |

---

## Hook 提醒機制

以下 Hook 在關鍵決策點自動輸出 AskUserQuestion 提醒：

| Hook | 觸發時機 | 覆蓋場景 |
|------|---------|---------|
| acceptance-gate-hook | ticket track complete 命令 | #1 驗收方式 + #2 下一步 |
| parallel-suggestion-hook | 繼續請求但無 pending Ticket | #3 Wave 收尾 + #15 批量備份 |
| prompt-submit-hook | 用戶提問含決策關鍵字 | #4 方案 + #5 優先級 + #6 拆分 |
| askuserquestion-reminder-hook | Task 派發含多個 Ticket ID | #7 派發方式 |
| commit-handoff-hook | git commit 成功後 | #11 Commit Handoff |
| process-skip-guard-hook | 用戶輸入含省略關鍵字 | #12 流程省略 |
| phase-completion-gate-hook | Phase 完成偵測後 | #13 後續路由 + #14 parallel-evaluation |

---

## 相關文件

- .claude/rules/core/decision-tree.md - 主線程決策樹
- .claude/rules/flows/ticket-lifecycle.md - Ticket 生命週期
- .claude/references/ticket-askuserquestion-templates.md - AskUserQuestion 模板
- .claude/rules/guides/parallel-dispatch.md - 並行派發指南

---

**Last Updated**: 2026-03-03
**Version**: 2.2.0 - 場景 #13 新增 TDD Phase 路由說明（情境 D1/D2/D3）+ Phase 3b/4 選項更新
**Purpose**: AskUserQuestion 規則唯一 Source of Truth
