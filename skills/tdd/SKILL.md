---
name: tdd
description: "TDD 全流程指導工具。Use for: (1) 開始新功能的 TDD 流程（Phase 0-4）, (2) 推進到下一個 TDD 階段, (3) Phase 1 SOLID 原則驅動功能拆分分析, (4) 查看當前 TDD 進度和階段狀態, (5) 評估是否需要 Phase 4 重構以及 3b 拆分評估。Use when: 開始新功能開發、進入任何 TDD Phase、需要 SOLID 拆分指導、需要確認當前所在 TDD 階段、需要做 Phase 4 豁免判斷時。"
---

# /tdd - TDD 全流程指導工具

統一的 TDD 流程入口，涵蓋 Phase 0（架構審查）到 Phase 4（重構評估）的完整指導。

---

## 核心理念

TDD 的價值不只是「測試先寫」，而是**強迫你在實作前想清楚**：

- Phase 0：系統一致性確認（避免重複造輪子）
- Phase 1：功能設計和 SOLID 拆分（設計決策優於實作決策）
- Phase 2：行為規格化（Given-When-Then 驅動實作邊界）
- Phase 3：實作執行（按規格不走彎路）
- Phase 4：品質反思（發現設計債務）

**設計原則**：Layer 1 內容為通用 TDD 知識，任何專案均可直接使用。Layer 2 為框架整合點，以 blockquote 標記。

---

## 子命令總覽

| 子命令 | 用途 | 適用時機 |
|--------|------|---------|
| `/tdd start` | 開始新 TDD 流程 | 新功能需求進入開發 |
| `/tdd next` | 推進到下一個 Phase | 當前 Phase 完成後 |
| `/tdd split` | Phase 1 SOLID 拆分分析 | Phase 1 設計階段需要拆分功能 |
| `/tdd status` | 查看當前進度和階段 | 確認目前所在 Phase 和轉換條件 |
| `/tdd phase4-exempt` | 評估 Phase 4 豁免條件 | Phase 3b 完成後決定是否豁免 4a/4c |

---

## `/tdd start` - 開始新 TDD 流程

初始化一個新功能的 TDD 流程。詳細規則見 `references/portable-design-boundary.md`。

> **框架整合**：在 Ticket 的 `tdd_stage` 欄位記錄當前 Phase。遷移任務豁免標記跳過的 Phase。

---

## `/tdd next` - 推進到下一個 Phase

在當前 Phase 完成後，確認轉換條件並推進。轉換條件詳見各 Phase reference 檔案。

> **框架整合**：執行 `/ticket track complete {id}` 標記完成。Phase 1/2/3a 由執行者自行 commit。

---

## `/tdd split` - Phase 1 SOLID 拆分分析

在 Phase 1 設計階段，使用 SOLID 原則分析功能需求，產出拆分建議。詳細方法論見 `references/phase1-split-methodology.md`。

> **框架整合**：使用 `/ticket create --parent {parent_id}` 建立子 Ticket，以 `blockedBy` 標記依賴。

---

## `/tdd status` - 查看當前進度

確認目前所在 TDD 階段、完成情況、下一步行動。

---

## `/tdd phase4-exempt` - Phase 4 豁免評估

Phase 3b 完成後，評估是否符合 Phase 4 豁免條件（跳過 4a/4c，直接執行 4b）。詳見 `references/phase4-refactor.md`。

> **框架整合**：Phase 4a 使用 `/parallel-evaluation B`，Phase 4c 使用 `/parallel-evaluation A`。

---

## 3b 拆分評估（Phase 3a 完成後強制執行）

Phase 3a 策略文件完成後，評估 Phase 3b 是否需要拆分為多個並行子任務。拆分規則見 `.claude/pm-rules/tdd-flow.md`。

> **框架整合**：拆分時建立子任務，指定修改檔案清單（`where.files`），確保無交集，並行派發。

---

## Phase 參考資料

| Phase | 詳細指引 |
|-------|---------|
| Phase 0 SA 前置審查 | `references/phase0-sa-review.md` |
| Phase 1 功能設計 | `references/phase1-design.md` |
| Phase 1 SOLID 拆分方法論 | `references/phase1-split-methodology.md`（CLI 工具、版本分配、報告範本） |
| Phase 2 測試設計 | `references/phase2-test-design.md` |
| Phase 3 實作 | `references/phase3-implementation.md` |
| Phase 4 重構 | `references/phase4-refactor.md` |
| 可攜式設計邊界 | `references/portable-design-boundary.md` |

---

## Layer 1 / Layer 2 設計原則

| 層次 | 內容 | 可攜性 |
|------|------|--------|
| Layer 1 | Phase 定義、SOLID 檢查、BDD/GWT、品質基準、豁免規則 | 通用，任何專案可直接使用 |
| Layer 2 | Ticket 系統、Agent 派發、Hook 自動化、決策樹路由 | 本框架特定，以 blockquote 標記 |

**Layer 1 禁止引用**：`/ticket` CLI、具體代理人名稱（lavender/parsley 等）、`.claude/hooks/` 系統、`decision-tree` 路由、`/parallel-evaluation` 工具、Wave/Patch 概念。

---

## 相關資源

- TDD 流程規則：`.claude/pm-rules/tdd-flow.md`
- 任務拆分指南：`.claude/rules/guides/task-splitting.md`
- 並行派發指南：`.claude/rules/guides/parallel-dispatch.md`
- 認知負擔原則：`.claude/rules/core/cognitive-load.md`

---

**Last Updated**: 2026-03-12
**Version**: 1.1.0 - 整合 tdd-phase1-split 內容：新增 phase1-split-methodology.md 和 CLI 腳本（0.1.0-W44-001.6）
**Specialization**: TDD 全流程指導（Phase 0-4）
