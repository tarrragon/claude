# AskUserQuestion 強制使用規則

本文件定義所有需要使用 AskUserQuestion 工具的場景和規範。這是 AskUserQuestion 規則的唯一 Source of Truth。

---

## 通用觸發原則（行為驅動，優先於場景枚舉）

> **任何時候，只要你正在向用戶呈現需要做決策、確認或選擇的場景，就必須使用 AskUserQuestion 工具。**

**判斷方法**：問自己以下任一問題——

1. 我的回覆是否包含「要選哪個？」型的多項選擇提問？（**是 → 觸發**）
2. 我的回覆是否包含「要繼續嗎？」「確認執行嗎？」「需要做 X 嗎？」等二元確認問句？（**是 → 觸發**）
3. 我的回覆是否在等待用戶做決策，而不是純粹提供資訊？（**是 → 觸發**）

若以上任一為「是」，必須使用 AskUserQuestion（不需要對照場景清單）。

**常見陷阱**：「要繼續執行下一個 Ticket 嗎？」看似簡單，但屬於二元確認（準則 2），**必須**用 AskUserQuestion，不得用純文字問句。

**重要**：下方 17 個場景是常見情境的範例，**不是**觸發條件的完整清單。觸發條件只有一個：向用戶呈現任何形式的選擇（多選或二元確認）。

---

## 背景

PM 用開放式提問時，用戶的自然語言回答可能被 Hook 系統誤判為開發命令。使用 AskUserQuestion 工具可消除此風險。

AskUserQuestion 是 deferred tool，使用前**必須**先 `ToolSearch("select:AskUserQuestion")` 載入。

---

## 使用對象限制

**AskUserQuestion 僅限 PM 使用，所有 subagent 禁止。**

Subagent 遇到路由/選擇場景時：停止決策 → 在產出物中標記「需 PM 決策」→ 回報主線程中轉。

---

## 強制規則

### 規則 1：所有選擇型決策必須使用 AskUserQuestion

PM 需要用戶做任何決策時（包含多選路由和二元 yes/no 確認），**必須使用 AskUserQuestion 工具**，而非文字提問。

### 規則 2：ToolSearch 前置載入

使用 AskUserQuestion 前必須先執行 `ToolSearch("select:AskUserQuestion")` 載入。

### 規則 3：禁止純文字提問讓用戶自由回答

禁止用純文字形式（不使用 AskUserQuestion tool）提問讓用戶自由輸入，因為用戶的自然語言回答可能被 Hook 誤判為開發命令。

注意：AskUserQuestion tool 內的 `question` 文字本身可以是開放語氣（如「接下來要做什麼？」），只要回答由預定義選項限制即可。

---

## 場景列表

### 18 個強制使用場景（#11 細分為 #11a/#11b）

| # | 場景 | 觸發條件 | 決策點 | Hook 提醒 |
|---|------|---------|--------|-----------|
| 1 | 驗收方式確認 | ticket track complete 前（P0 優先級時觸發；DOC/ANA/非 P0 IMP 自動決定，不觸發） | ticket-lifecycle 驗收階段 | acceptance-gate-hook |
| 2 | Complete 後下一步 | ticket track complete 後 | ticket-lifecycle 完成階段 | acceptance-gate-hook |
| 3 | Wave/任務收尾確認 | 當前 Wave 無 pending Ticket（前置：強制 /parallel-evaluation Wave 審查；情境 C1：有其他 Wave → #3a；情境 C2：全完成 → 技術債整理 + /version-release check） | ticket-lifecycle 收尾 | parallel-suggestion-hook |
| 4 | 方案選擇 | 多個技術方案 | 決策樹第負一層 | prompt-submit-hook |
| 5 | 優先級確認 | 多任務排序 | 決策樹第負一層 | prompt-submit-hook |
| 6 | 任務拆分確認 | 認知負擔 > 10 | 決策樹第負一層 | prompt-submit-hook |
| 7 | 派發方式選擇 | Task subagent / Agent Teams / 序列 | 決策樹第負一層 | askuserquestion-reminder-hook |
| 8 | 執行方向確認 | 並行/序列、先後順序 | 決策樹第負一層 | prompt-submit-hook |
| 9 | Handoff 方向選擇 | 多個兄弟/子任務可選 | ticket-lifecycle 完成階段 | - |
| 10 | 開始/收尾確認 | 確認是否開始執行 | 決策樹第負一層 | - |
| 11a | Commit 後 Context 刷新 Handoff（情境 A） | ticket 仍 in_progress | 決策樹第八層 Checkpoint 2 | commit-handoff-hook |
| 11b | Commit 後任務切換 Handoff（情境 B） | ticket completed + 同 Wave 有 pending | 決策樹第八層 Checkpoint 2 | commit-handoff-hook |
| 12 | 流程省略確認 | 省略意圖偵測 | 決策樹第八層 | process-skip-guard-hook |
| 13 | 後續任務路由確認 | Phase 3b 完成且豁免條件不符時、Phase 4b（豁免）/4c 完成、版本完成（C2）、incident 或分析完成後有多個後續路由可選（Phase 1/2/3a 全自動不觸發；Phase 3b 豁免條件符合時自動進入 4b 不觸發） | 決策樹第八層 | phase-completion-gate（擴充） |
| 14 | parallel-evaluation 觸發確認 | 階段完成後 | 決策樹第八層 | phase-completion-gate（擴充） |
| 15 | Bulk 變更前備份確認 | 批量修改前 | 決策樹第八層 | parallel-suggestion-hook（擴充） |
| 16 | 錯誤學習經驗確認 | commit 完成後（#11a/#11b 之前）；docs:/chore:/style: 等 commit 自動跳過；選項簡化為二元確認 | 決策樹第八層 Checkpoint 1.5 | commit-handoff-hook（擴充） |
| 17 | 錯誤經驗改進追蹤 | ticket complete 時有新增 error-pattern | ticket-lifecycle 完成階段 | acceptance-gate-hook（擴充） |

**Hook 覆蓋狀態**：14/18 場景有 Hook 自動提醒（14/18 = 78%）。其中 #13/#14 為條件式觸發（僅當 TDD Phase 完成且 worklog 更新時），未計入 14/18 計數，列於下方 Hook 提醒機制表僅供參考。

**Phase 1-3 自治 commit 相容性**：場景 #11/#16 由 commit-handoff-hook 觸發，但 Phase 1-3 代理人自治 commit 時，因 subagent 禁止使用 AskUserQuestion，Hook 提醒自然跳過——這是預期行為，Phase 1-3 的 commit 不需要 PM 介入 Handoff 或錯誤學習決策。

### 場景執行順序約束

**#16 必須先於 #11a/#11b**（強制）：commit 後先執行 #16（錯誤學習），再進入 #11（Handoff）。

---

> 各場景完整操作細節、選項配置、工具能力說明：.claude/references/askuserquestion-scene-details.md

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
| parallel-suggestion-hook | 繼續請求但無 pending Ticket | #3 Wave 收尾 + #15 批量備份 |
| prompt-submit-hook | 用戶提問含決策關鍵字 | #4 方案 + #5 優先級 + #6 拆分 + #8 執行方向 |
| askuserquestion-reminder-hook | Task 派發含多個 Ticket ID | #7 派發方式 |
| commit-handoff-hook | git commit 成功後 | #11 Commit Handoff + #16 錯誤學習 |
| process-skip-guard-hook | 用戶輸入含省略關鍵字 | #12 流程省略 |
| phase-completion-gate-hook | Phase 完成時 worklog 寫入後（條件式，未計入 12 計數） | #13 後續路由 + #14 parallel-evaluation |
| acceptance-gate-hook | ticket track complete 命令 | #1 驗收方式 + #2 下一步 + #17 錯誤經驗改進 |

---

## 相關文件

- .claude/rules/core/decision-tree.md - 主線程決策樹
- .claude/rules/flows/ticket-lifecycle.md - Ticket 生命週期
- .claude/references/askuserquestion-scene-details.md - 場景 1-17 完整操作細節
- .claude/references/ticket-askuserquestion-templates.md - AskUserQuestion 模板
- .claude/rules/guides/parallel-dispatch.md - 並行派發指南

---

**Last Updated**: 2026-03-13
**Version**: 3.4.0 - 同步 W43-W47 規則：D2 自動豁免閘門、Phase 1-3 自治 commit 相容性、Hook 覆蓋數 14/18（0.1.0-W48-003）
**Purpose**: AskUserQuestion 規則唯一 Source of Truth
