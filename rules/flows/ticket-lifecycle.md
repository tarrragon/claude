# Ticket 生命週期流程

> 操作指南：.claude/skills/ticket/SKILL.md
> AskUserQuestion 規則：.claude/rules/core/askuserquestion-rules.md

---

## 狀態定義

```
pending → claim → in_progress → complete → completed
                                    ↑ release → blocked → 升級 PM
```

| 狀態 | 允許操作 |
|------|---------|
| pending | claim |
| in_progress | complete, release |
| completed | - |
| blocked | claim（重新認領） |

---

## 階段-標準流程總覽

| 階段 | 強制規則 | AskUserQuestion |
|------|---------|----------------|
| **建立** | 必須用 `/ticket create`，禁止直接寫 .md | 任務拆分確認（認知 > 10） |
| **建立後** | 強制並行審核：acceptance-auditor（品質）+ system-analyst（設計）→ creation_accepted: true | - |
| **認領** | 阻塞依賴檢查 | - |
| **執行** | 錯誤強制派發 incident-responder；日誌必填 | - |
| **驗收** | acceptance-gate-hook 檢查 | **驗收方式確認**（標準/簡化/先完成後補） |
| **完成** | 驗收通過後執行 `/ticket track complete`；complete 後處理 #17（錯誤學習） | **後續步驟選擇** |
| **收尾** | PM 主動告知變更狀態 + 查詢待處理 | **Wave 收尾確認** |

> 各階段詳細規則：.claude/references/ticket-lifecycle-phases.md

---

## Ticket 建立強制規則

| 規則 | 說明 |
|------|------|
| 必須使用命令 | `/ticket create` |
| 唯一存放路徑 | `docs/work-logs/v{version}/tickets/` |
| 子任務建立 | `/ticket create --parent {parent_id}` |
| 任務層級判斷 | 因執行現有 Ticket 產生 → 子任務；獨立問題 → 新任務鏈 |

---

## 建立後強制審核流程

Ticket 建立後、認領前，強制並行派發多代理人審核。

### 觸發條件

- Ticket 建立完成（`/ticket create` 執行成功）
- `creation_accepted` 為 false（預設）

### 審核內容

| 審核者 | 面向 | 檢查項目 |
|--------|------|---------|
| acceptance-auditor | 品質 | 驗收條件 4V 合規、where.files 完整性、數字正確性 |
| system-analyst | 設計 | 設計合理性、重複實作檢查、範圍適當性 |

### 審核流程

```
/ticket create → creation_accepted: false
    |
    v
[強制] 並行派發 acceptance-auditor + system-analyst
    |
    v
彙整結果 → 通過（無高/中缺陷）→ creation_accepted: true → 可認領
         → 未通過 → 修正 → 重新審核
```

### 判定標準

| 缺陷等級 | 判定 | 處理 |
|---------|------|------|
| 無/僅低缺陷 | 通過 | creation_accepted: true |
| 中缺陷 | 不通過 | PM 修正後重新審核或確認 |
| 高缺陷 | 不通過 | 必須修正後重新審核 |

### 豁免條件

| 條件 | 說明 |
|------|------|
| DOC 類型（任務範圍單純） | 純文件更新，可跳過 |
| 已審核父 Ticket 的子任務 | 範圍已確認，可跳過 |

> 來源：PC-002 錯誤模式 — Ticket 建立後未經審核直接派發

---

## 驗收流程

| 任務類型 | 驗收深度 |
|---------|---------|
| IMP/ADJ/TDD Phase/複雜/安全 | 完整驗收（acceptance-auditor） |
| DOC/簡單（任務範圍單純） | 簡化驗收 |

---

## 完成階段錯誤學習驗證

`ticket track complete` 執行前，acceptance-gate-hook（PreToolUse）會自動檢查執行期間是否有新增 error-pattern，並輸出場景 #17 提醒。

### 執行時序（重要：先 complete，後處理 #17）

```
[1] 用戶執行: ticket track complete X
    ↓
[2] acceptance-gate-hook 觸發（PreToolUse）
    |
    ├── [阻擋] 子任務未完成 → 阻止執行（exit 2）
    |
    ├── [有新增 error-pattern] → 輸出 #17 提醒（非阻擋，exit 0）
    |
    └── [正常情況] → 輸出 #1 驗收確認提醒（非阻擋，exit 0）
    ↓
[3] ticket track complete X 執行（in_progress → completed）
    ↓
[4] PM 根據 hook 輸出，complete 後執行對應動作
    +-- [若有 #17 提醒] → AskUserQuestion #17 → 選擇後處理
    +-- [場景 #1/#2] → AskUserQuestion #1 → 確認驗收方式 → AskUserQuestion #2 → 路由下一步
```

**死鎖防護：complete 必須先執行，#17 在 complete 後處理**

> **問題根源**：error-pattern 檔案在 #17 處理後不會自動移除。若 PM 先處理 #17 再執行 complete，下一次執行 complete 時 hook 仍會觸發 #17 提醒，造成無限循環無法完成。

| 行為 | 結果 |
|------|------|
| 看到 #17 提醒 → 先處理 → 再執行 complete | 死鎖：hook 持續觸發 #17，complete 永遠等待 |
| 看到 #17 提醒 → 直接執行 complete → 完成後處理 #17 | 正確：non-blocking，一次完成 |

### AskUserQuestion #17 觸發條件

| 條件 | 說明 |
|------|------|
| 有新增 error-pattern | ticket 執行期間 `.claude/error-patterns/` 下有新增或修改的檔案 |
| 無新增 error-pattern | 跳過 #17，正常完成 |

### #17 選項

| 選項 | 說明 |
|------|------|
| 建立改進 Ticket（Recommended） | 為新增的 error-pattern 建立修復/防護 Ticket |
| 已有對應 Ticket | error-pattern 相關修復已在現有 Ticket 中 |
| 延後處理 | 記錄到 todolist.yaml，後續版本排程 |

> 場景定義詳見：.claude/rules/core/askuserquestion-rules.md（場景 #17）

---

## 相關文件

- .claude/references/ticket-lifecycle-phases.md - 各階段詳細規則
- .claude/skills/ticket/references/ticket-lifecycle-details.md - 格式和 Hook 技術細節
- .claude/rules/core/decision-tree.md - 主線程決策樹
- .claude/rules/flows/incident-response.md - 事件回應流程

---

**Last Updated**: 2026-03-09
**Version**: 5.3.0 - 修復完成階段時序：釐清 #1/#17 執行順序，新增死鎖防護說明（W22-009）
