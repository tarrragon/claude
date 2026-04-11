# 決策樹 — 完成 Domain

> 本文件從 decision-tree.md 按 DDD domain 邊界拆分。
> 路由入口：.claude/pm-rules/decision-tree.md
> 來源：0.17.2-W3-007.1

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
    +-- 是 → [強制] children/spawned_tickets 非空?
    |           +-- 否 → 建立後續 Ticket
    |           +-- 是 → AC 覆蓋率 100%?（PC-041）→ 是:繼續 / 否:補充
    +-- 否 → 繼續
    |
    v
確認驗收方式 → 勾選 AC → check-acceptance → complete
```

**ANA 結論轉化規則**：

| 檢查項 | 說明 |
|--------|------|
| children 非空 | ANA Ticket 已建立子任務（修復/防護等） |
| spawned_tickets 非空 | ANA Ticket 已衍生獨立 Ticket |
| 任一滿足即通過存在性 | 至少有一個後續 Ticket 追蹤分析結論 |
| 均為空 | **阻塞完成**：必須先建立後續 Ticket（修復+防護）再繼續 |
| **AC 覆蓋率 100%** | **後續 Ticket AC 合集必須 1:1 覆蓋 ANA Solution 所有修改項（PC-041）** |

**AC 完整性驗證**：列出 ANA Solution 修改項 → 逐項對照後續 Ticket AC → 每項必須 1:1 覆蓋。背景代理人結果需合併後再驗證。

> 驗收流程詳細規則：.claude/pm-rules/ticket-lifecycle.md

---

## 第八層：完成後路由（Commit-Evaluate-Handoff 循環）

任務或階段完成後的統一路由機制（Checkpoint 0 → 1 → 1.5 → 2 → 3 → 4）。

**核心判斷規則**：

| Checkpoint | 判斷條件 | 路由 |
|------------|---------|------|
| 0 建立後 Handoff | 可並行派發? | 是 → 留在 session 並行派發；否 → commit + handoff |
| 0.5 進度更新 | **[強制]** 階段轉換時 | `ticket track append-log` 更新 |
| 1 變更狀態 | 有未提交變更? | 是 → commit；無 → 跳至 1.5 |
| 1.5 錯誤學習 | commit 成功後 | AskUserQuestion #16 |
| 1.8 合併回 main | 在開發分支上? | 是 → merge --no-ff → main → 刪除開發分支；否 → 跳過 |
| 1.85 代理人清點 | `dispatch-active.json` 為空? | 否 → **阻塞**：仍有代理人在執行，禁止繼續；是 → 通過 |
| 1.9 Worktree 合併 | `git worktree list` 有非 main worktree? | 有未合併 commit → 合併 + 清理；無 → 跳過 |
| 2 情境評估 | [強制查詢] ticket track list | 情境 D/A/B/C（見下方） |
| 3 後續路由 | 任務類型 | AskUserQuestion #13 |
| 4 parallel-evaluation | 階段完成後 | AskUserQuestion #14 |

**Checkpoint 2 情境評估（強制先查詢再路由，禁止依賴記憶）**：

| 情境 | 條件 | 路由 |
|------|------|------|
| D（優先） | ticket 含 tdd_phase 欄位 | → **tdd-completion-routing.md**（7 個子場景獨立展開） |
| A（#11a） | ticket 仍 in_progress | Context 刷新 Handoff |
| B（#11b） | ticket completed + 同 Wave 有 pending | 任務切換 Handoff |
| C | ticket completed + 同 Wave 無 pending | [強制] /parallel-evaluation Wave 審查（含 linux 常駐委員）→ C1: 有其他 Wave → #3a；C2: 全完成 → 版本收尾 → /version-release check + #13 |

**Checkpoint 1.85 代理人清點（強制，PC-050）**：

所有代理人完成前，禁止進入後續 Checkpoint。

```bash
cat .claude/dispatch-active.json | python3 -c "
import json, sys
d = json.load(sys.stdin)
if d:
    print('[BLOCK] 仍有 {} 個代理人在執行：'.format(len(d)))
    for x in d:
        print('  - {}'.format(x.get('agent_description', '?')))
    print('禁止繼續。等待所有代理人完成通知。')
else:
    print('[PASS] 無活躍派發，可繼續。')
"
```

| 結果 | 行動 |
|------|------|
| 有活躍派發 | **阻塞**：等待完成通知，不做任何 commit/merge/complete |
| 無活躍派發 | 通過，進入 Checkpoint 1.9 |

> 來源：PC-050 — PM 在代理人仍在工作時誤判完成

**Checkpoint 1.9 Worktree 合併（強制，PC-039）**：

`git worktree list` → 有非 main worktree → 合併 + 清理；無 → 跳過。

> 完整流程和觸發時機：.claude/pm-rules/worktree-operations.md

**背景代理人結果合併（ANA 完成前，強制，PC-041）**：ANA 完成前必須確認所有背景代理人已完成，合併分析結果到 Solution 後再建立執行 Ticket。禁止背景代理人未完成就建 Ticket。

**Checkpoint 0.5 PM 進度更新（強制，對稱代理人 W15-001）**：

PM 在 4 個時機必須 `ticket track append-log`：認領後（確認範圍）→ 分析完成（決策+下一步）→ 修正完成（摘要）→ 完成前（Solution 記錄）。禁止 complete 時才一次性補寫。若跳過中間時機，complete 前必須補寫遺漏的進度記錄。

**與現有層級的銜接**：第四層（建立完成）→ Checkpoint 0；第五層（Phase 完成）→ Checkpoint 1；第六層（incident 完成）→ Checkpoint 3；第七層（complete）→ Checkpoint 1

**Handoff 強制動作**：PM **必須**執行 `/ticket handoff`，**禁止**手動建立交接文件。前須 `ticket handoff --status` 確認無殘留。

**Resume 後接手（Checkpoint R）**：resume 後先確認範圍再 claim，不直接開始實作。

> Checkpoint 0-4 完整流程、情境子規則、Checkpoint R 詳細步驟：.claude/references/decision-tree-checkpoint-details.md
> AskUserQuestion 場景 11-17：.claude/pm-rules/askuserquestion-rules.md
> 模板：.claude/references/ticket-askuserquestion-templates.md

---

**Last Updated**: 2026-04-09
**Version**: 2.0.0 - 情境 D 拆分至 tdd-completion-routing.md + Worktree/ANA 流程精簡（W9-001）
