# AskUserQuestion 場景 1-17 詳細說明

本文件為 `.claude/rules/core/askuserquestion-rules.md` 的 reference，包含各場景的完整操作細節。

---

## 場景 1-2：驗收方式確認 + Complete 後下一步

**觸發**：`ticket track complete` 命令

### #1 自動決定規則（減少觸發）

acceptance-gate-hook 讀取 Ticket 的 `type` 和 `priority` 欄位，依下表自動決定驗收方式：

| 條件 | 自動選擇 | 是否觸發 #1 提醒 |
|------|---------|----------------|
| type = DOC | 簡化驗收 | 否（自動，不需確認） |
| type = ANA | 簡化驗收 | 否（自動，不需確認） |
| priority = P0 | 顯示 2 選項供選擇 | 是（2 選項） |
| 其他（IMP/ADJ/TST + 非 P0） | 標準驗收 | 否（自動，不需確認） |
| type 未知 | 標準驗收 | 否（保守預設） |

**觸發時機**：僅 priority = P0 的 Ticket 才觸發 #1 AskUserQuestion。

**驗收方式確認選項**（P0 限定）：

| 選項 | 說明 |
|------|------|
| 標準驗收（Recommended） | 派發 acceptance-auditor 執行完整驗收 |
| 先完成後補驗收 | P0 緊急任務，24 小時內補驗收 |

**Complete 後下一步選項**（動態生成）：

| 選項 | 說明 |
|------|------|
| 開始 {Ticket-ID} - {標題} | 阻塞已解除或同 Wave pending 的 Ticket |
| Handoff 到父任務 | 任務鏈完成，返回父任務 |
| 結束當前 Wave | 所有任務已完成 |

---

## 場景 3：Wave/任務收尾確認

**觸發**：Checkpoint 2 情境 C（同 Wave 無待處理任務，需判斷版本狀態）

**收尾前步驟**（必須先執行）：
1. 執行 /parallel-evaluation 對本 Wave 成果進行多視角審查（Recommended）
2. 列出本次修改的檔案清單
3. 告知 git 未提交狀態

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

**前置步驟**（必須先執行）：
1. [強制] 檢查 todolist.yaml 未排程技術債
2. 有需要建立的技術債 → `/ticket batch-create` 批量建立（歸入下一版本）
3. 技術債整理完成後，進入選項

> 技術債整理流程詳見：.claude/pm-rules/version-progression.md（版本收尾技術債整理流程章節）

**選項**：

| 選項 | 說明 |
|------|------|
| /version-release check 確認前置條件（Recommended） | 執行版本推進前置檢查 |
| 查看版本摘要（ticket track summary） | 確認全部任務已完成 |
| 延後版本推進 | 稍後再執行版本推進 |

---

## 場景 4-6：方案選擇 / 優先級確認 / 任務拆分確認

**觸發**：用戶提問包含方案選擇、優先級確認、任務拆分相關關鍵字

**任務拆分選項**：

| 選項 | 說明 |
|------|------|
| 需要拆分 | 認知負擔 > 10，進入拆分流程 |
| 不需拆分 | 直接派發執行 |
| 需要進一步評估 | 派發 SA 分析 |

---

## 場景 7：派發方式選擇

**觸發**：多任務派發（Task prompt 包含 2+ 個 Ticket ID）

**選項**：

| 選項 | 說明 |
|------|------|
| Task subagent | 各 Agent 獨立完成，不互相影響 |
| Agent Teams | Agent A 的發現會改變 Agent B 的工作 |
| 序列派發 | 有依賴關係，需按順序執行 |

---

## 場景 8-10：執行方向 / Handoff 方向 / 開始收尾

場景 #8 由 prompt-submit-hook 偵測執行順序相關關鍵字（「先做」「順序」「先後」「並行還是序列」等）自動提醒。場景 #9 和 #10 目前無 Hook 自動提醒，依賴 PM 遵循本規則文件。

---

## 場景 11：Commit 後情境感知 Handoff

**觸發**：每次 `git commit` 成功後（PostToolUse/Bash Hook 偵測）

> **Phase 1-3 自治 commit 不觸發**：Phase 1/2/3a 代理人自行 commit 時，因 subagent 禁止使用 AskUserQuestion，commit-handoff-hook 的 #11/#16 提醒自然跳過。這是預期行為——Phase 1-3 不需要 PM 介入 Handoff 決策。

**路由邏輯**（PM 必須先評估再選擇子場景）：

| 情境 | 條件 | 路由 |
|------|------|------|
| A：Context 刷新 | ticket 仍 in_progress | #11a |
| B：任務切換 | ticket 已 completed + 有關聯待處理任務 | #11b |
| C1：Wave 收尾（有下一 Wave） | ticket 已 completed + 無關聯待處理任務 + 版本仍有其他 Wave pending | 先執行 /parallel-evaluation 本 Wave 多視角審查 (Recommended) → 審查完成後跳至 #3，不使用 #11 |
| C2：版本完成 | ticket 已 completed + 無關聯待處理任務 + 版本無任何待處理任務 | 先執行 /parallel-evaluation 本 Wave 多視角審查 (Recommended) → 審查完成後跳至 #13（強制 /version-release check），不使用 #11 |

**#16 → #11 執行順序**

commit 成功後，PM 必須先執行 #16（錯誤學習經驗確認），再進入 #11（Handoff/路由確認）：

```
commit 成功
    ↓
[Checkpoint 1.5] AskUserQuestion #16（錯誤學習經驗確認）
    ↓
[Checkpoint 2] AskUserQuestion #11（Handoff/路由確認）
```

**#11 核心原則：Handoff first（PC-009）**

> Context 是有限資源。每次 Ticket 完成後的 handoff 是保護下一個任務思考品質的方式。
> **Handoff 永遠是第一選項且標記 (Recommended)；繼續在此 session 工作是例外，不是預設。**

**#11 共通規則：完成摘要 + /clear 選項**

所有 #11 子場景的 AskUserQuestion 必須：

1. **在 question 中包含本次 session 的完成摘要**（已完成的 Checkpoint 項目）
2. **提供 `/clear` 選項**（清空 session，不建立 handoff）
3. **Handoff 選項為第一位且標記 (Recommended)**，繼續在此 session 工作選項排後

**完成摘要格式**（嵌入 question 文字中）：

```
本次 session 已完成：
- [已完成項目 1]
- [已完成項目 2]
- commit: {commit hash} {commit message}
```

PM 應根據 session 實際執行內容動態組裝摘要，讓用戶在做決策前了解「到這裡為止做了什麼」。

---

**#11a：Context 刷新 Handoff**（情境 A — ticket 仍 in_progress）

```
question: "{完成摘要}\n\n此 ticket 仍在進行中。接下來要？"
```

| 選項 | 說明 |
|------|------|
| Handoff (Context 刷新)（Recommended） | 在新 session 以乾淨 context 繼續同一 ticket |
| 繼續在此 session 工作 | 留在當前 context 繼續 |
| /clear 結束 session | 清空對話，不建立 handoff 檔案 |

**#11a 對應 CLI 命令**（用戶確認後執行）：

```bash
ticket handoff <id> --context-refresh
```

> 注意：`--context-refresh` 僅適用 `in_progress` 狀態。**禁止**在 `completed` ticket 使用此旗標。

**#11b：任務切換 Handoff**（情境 B — ticket 已 completed，有關聯任務）

```
question: "{完成摘要}\n\nTicket 已完成。切換到下一個任務嗎？"
```

| 選項 | 說明 |
|------|------|
| Handoff 到 {next_ticket_id} - {title}（Recommended） | 在新 session 切換到下一個 ticket |
| 在此 session 繼續 {next_ticket_id} | 直接 claim，留在當前 context |
| 查看所有待處理任務後決定 | 列出後讓用戶選擇 |
| /clear 結束 session | 清空對話，不建立 handoff 檔案 |

**#11b 對應 CLI 命令**（用戶確認後執行）：

```bash
# 切換到兄弟任務
ticket handoff <id> --to-sibling <next_ticket_id>

# 或返回父任務
ticket handoff <id> --to-parent

# 或讓 CLI 自動判斷方向（completed 狀態不加旗標）
ticket handoff <id>
```

> 注意：ticket 已 `completed`，**不需要也不可以**使用 `--context-refresh`。

**Handoff 後強制動作**：選擇任何 Handoff 選項後，PM **必須**執行 `/ticket handoff` 建立標準 `pending/*.json` 檔案。**禁止**手動建立 `.claude/handoff/*.md` 交接文件。這確保下一個 session 的 `resume --list` 能正確偵測待恢復任務。

---

## 場景 12：流程省略確認

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

---

## 場景 13：後續任務路由確認

**觸發**：分析/規劃/修改/TDD Phase 3b 或 Phase 4 tech-debt 後完成，有多個後續路由可選

> **TDD Phase 路由說明**：
> - Phase 1/2/3a 完成由**情境 D1 全自動**處理（代理人自治 commit + complete，直接派發下一 Phase，不走 AskUserQuestion）
> - Phase 3b 完成由**情境 D2** 處理：PM 先自動檢查豁免條件（<=2 檔案/DOC/單純）→ 符合豁免時**全自動進入 Phase 4b**（不觸發 #13）；不符合時觸發此場景讓用戶選擇 Phase 4a 或 4b
> - Phase 4 完成由**情境 D3 強制** /tech-debt-capture 後觸發此場景（task_type: Phase 4 + tech-debt 完成）

**動態選項**（依 task_type 變化）：

| task_type | 選項 1 | 選項 2 | 選項 3 |
|-----------|--------|--------|--------|
| 分析完成 | 進入實作（建立 Ticket） | /parallel-evaluation F（結論審查） | 先 commit 再決定 |
| 規劃完成 | /parallel-evaluation C/G（審核） | 直接進入 TDD Phase 1 | 先 commit 再決定 |
| Phase 3b 完成 | 進入 Phase 4a（/parallel-evaluation B 多視角重構分析，Recommended） | 直接進入 Phase 4b（豁免：<=2 檔案/DOC 類型/任務範圍單純） | 先 commit 再決定 |
| Phase 4c + tech-debt 完成 | commit 並查看 Wave 狀態（Recommended） | Handoff，下個 session 繼續 Wave 路由 | 查看所有待處理 Ticket |
| incident 分析完成 | /parallel-evaluation F（結論審查） | 直接建立修復 Ticket | 先 commit 再決定 |
| Wave 完成（有下一 Wave） | 開始 Wave X+1（列出任務） | Handoff 到 Wave X+1 | 先 commit 再決定 |
| 版本完成（無待處理任務） | /version-release check | 查看 ticket track summary | 延後版本推進 |

---

## 場景 14：parallel-evaluation 觸發確認

**觸發**：TDD 階段完成或任務完成後，系統建議可用 parallel-evaluation

**對應情境**：

| TDD 階段/事件 | 建議情境 | 視角 |
|--------------|---------|------|
| Phase 3b 完成（→ Phase 4a） | B（重構評估） | Redundancy, Coupling, Complexity |
| Phase 4b 完成（→ Phase 4c） | A（程式碼審查） | Reuse, Quality, Efficiency |
| SA 審查完成 | C（架構評估） | Consistency, Impact, Simplicity |
| 規則/Skill 變更 | G（系統設計） | Consistency, Completeness, CogLoad |
| incident 分析 | F（結論審查） | Evidence, Alternatives, Scope |

**選項**：

| 選項 | 說明 |
|------|------|
| 執行 /parallel-evaluation 情境 X（Recommended） | 啟動多視角掃描 |
| 跳過，直接進入下一步 | 觸發場景 12 省略確認 |
| 執行其他情境 | 選擇不同的 parallel-evaluation 情境 |

---

## 場景 15：Bulk 變更前備份確認

**觸發**：即將進行大批量修改前（偵測到多檔案修改意圖）

**選項**：

| 選項 | 說明 |
|------|------|
| 先 commit 備份（Recommended） | 建立回退點 |
| 直接開始 | 不備份 |
| 查看變更範圍 | 確認後再決定 |

---

## 場景 16：錯誤學習經驗確認

**觸發**：每次 git commit 成功後，在進入 #11 Handoff 確認之前

**觸發時機**：Checkpoint 1.5（commit 成功 → #16 → #11）

### #16 commit message 語義過濾（減少觸發）

commit-handoff-hook 解析 commit message 前綴，依下表決定是否觸發 #16：

| commit message 前綴 | #16 行為 | 說明 |
|--------------------|---------|------|
| `docs:`, `chore:`, `style:`, `refactor:`, `test:` | 自動跳過 | 純文件/格式/重構 commit，錯誤學習機會低 |
| `fix:`, `bug:`, `patch:` | 強制觸發 | 錯誤修復 commit，錯誤學習機會高 |
| 其他（`feat:`, 無前綴等） | 觸發二元確認 | 標準流程 |

### #16 簡化為二元確認

**question 格式**：

```
本次 commit 是否有需要記錄的錯誤學習經驗？
（例如：踩到的坑、發現的反模式、設計決策教訓）
```

**選項**（二元）：

| 選項 | 說明 |
|------|------|
| 無（Recommended） | 本次 commit 無特殊錯誤經驗 |
| 有，執行 /error-pattern add | 記錄本次發現的模式 |

**選擇「有」後的流程**：

```
選擇「有，執行 /error-pattern add」
    ↓
執行 /error-pattern add
    ↓
記錄完成（可能產生新 commit）
    ↓
回到 Checkpoint 1.5（再次確認是否有更多經驗要記錄）
    ↓
選擇「無」→ 進入 #11
```

---

## 場景 17：錯誤經驗改進追蹤

**觸發**：`ticket track complete` 時，檢查本 ticket 執行期間是否有新增 error-pattern

**檢查方式**：比對 ticket created 時間 vs error-pattern 檔案 mtime

**question 格式**：

```
本 ticket 執行期間新增了 {N} 個錯誤學習經驗：
- {pattern_id}: {pattern_title}
- ...

這些錯誤經驗是否需要建立改進 Ticket 來修復根因或加強防護？
```

**選項**：

| 選項 | 說明 |
|------|------|
| 建立改進 Ticket（Recommended） | 為新增的 error-pattern 建立修復/防護 Ticket |
| 已有對應 Ticket | error-pattern 相關修復已在現有 Ticket 中 |
| 延後處理 | 記錄到 todolist.yaml，後續版本排程 |

**選擇「建立改進 Ticket」後的流程**：

```
選擇「建立改進 Ticket」
    ↓
為每個需要改進的 error-pattern 執行 /ticket create
    ↓
改進 Ticket 建立完成
    ↓
繼續原有的 complete 後流程
```

---

## 相關文件

- .claude/rules/core/askuserquestion-rules.md - AskUserQuestion 規則主檔（Source of Truth）
- .claude/references/ticket-askuserquestion-templates.md - AskUserQuestion 模板

---

**Last Updated**: 2026-03-13
**Version**: 1.2.0 - 同步 W43-W47 規則：#8 Hook 覆蓋、D2 自動豁免、Phase 1-3 自治 commit 相容性（0.1.0-W48-003）
