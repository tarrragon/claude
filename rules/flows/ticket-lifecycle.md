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

`ticket track complete` 執行前，acceptance-gate-hook 會自動檢查是否有新增 error-pattern，並輸出場景 #17 提醒。

**強制時序**：先執行 complete，後處理 #17（避免死鎖）。

| 條件 | 處理 |
|------|------|
| 有新增 error-pattern | complete 後執行 AskUserQuestion #17 |
| 無新增 error-pattern | 跳過 #17，正常完成 |

> 執行時序詳細說明和死鎖防護：.claude/references/ticket-lifecycle-phases.md（完成階段錯誤學習驗證章節）
> 場景定義：.claude/rules/core/askuserquestion-rules.md（場景 #17）

---

## 相關文件

- .claude/references/ticket-lifecycle-phases.md - 各階段詳細規則
- .claude/skills/ticket/references/ticket-lifecycle-details.md - 格式和 Hook 技術細節
- .claude/rules/core/decision-tree.md - 主線程決策樹
- .claude/rules/flows/incident-response.md - 事件回應流程

---

**Last Updated**: 2026-03-11
**Version**: 5.5.0 - 移除建立後審核的 DOC 類型豁免條件（0.1.0-W37-001）
