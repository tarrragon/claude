# 決策樹 — TDD 完成路由（情境 D）

> Checkpoint 2 情境 D 的完整路由。當 Ticket 含 tdd_phase 欄位時觸發。
>
> 路由入口：.claude/pm-rules/completion-checkpoint-rules.md（Checkpoint 2 情境評估）
> 來源：多視角審查後拆分

---

## 觸發條件

Checkpoint 2 情境評估時，ticket 含 `tdd_phase` 欄位 → 優先進入本路由（優先於情境 A/B/C）。

---

## TDD Phase 完成後路由表

| 子情境 | 當前 Phase | 路由 | 說明 |
|--------|-----------|------|------|
| D1 | Phase 1 或 Phase 2 | 全自動進入下一 Phase | 無需 AskUserQuestion |
| D1a | Phase 3a | 3b 拆分評估（見 tdd-flow.md）→ 派發 3b | 評估後再派發 |
| D2 | Phase 3b | 檢查豁免條件（見下方）→ 符合：全自動 4b / 不符合：AskUserQuestion #13 選擇 4a 或 4b | 豁免判斷是關鍵分支 |
| D3a | Phase 4a | 全自動進入 4b | 4a 分析完成後直接執行重構 |
| D3b | Phase 4b（標準流程） | 全自動進入 4c | 重構完成後進入再審核 |
| D3b' | Phase 4b（豁免流程） | /tech-debt-capture → AskUserQuestion #13 | 豁免時跳過 4c |
| D3c | Phase 4c | /tech-debt-capture → AskUserQuestion #13 | 再審核完成，進入後續路由 |

---

## Phase 3b → Phase 4 豁免條件

> 完整豁免規則：.claude/pm-rules/tdd-flow.md

**最小必要判斷標準**（PM 可在此處獨立判斷）：

| 條件 | 滿足時 |
|------|-------|
| 修改行數 < 30 行 | 豁免 4a，直接進入 4b |
| 無新增公開 API | 豁免 4a |
| 僅修改既有函式內部邏輯 | 豁免 4a |
| 新增模組或跨模組修改 | 不豁免，需 4a 多視角分析 |

豁免時：Phase 3b → 直接 4b → /tech-debt-capture → AskUserQuestion #13
不豁免：Phase 3b → AskUserQuestion #13（選擇 4a 或 4b）

---

## 相關文件

- .claude/pm-rules/completion-checkpoint-rules.md - Checkpoint 2 情境評估（入口）
- .claude/pm-rules/tdd-flow.md - TDD 完整流程（豁免規則詳細版）
- .claude/pm-rules/askuserquestion-rules.md - AskUserQuestion 場景 #13

---

**Last Updated**: 2026-04-09
**Version**: 1.0.0 - 從 completion-checkpoint-rules.md 拆分（多視角審查後修正）
