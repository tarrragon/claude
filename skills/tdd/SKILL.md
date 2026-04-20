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

**粒度原則**：Use Case → 行為單元 → 測試 → 實作，每一層的拆分由上一層決定。單一 Ticket 目標 3-7 分鐘完成。詳見 `references/task-granularity-rules.md`。

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

初始化一個新功能的 TDD 流程。

**執行前 Read**：`references/phase0/rules.md`

> **框架整合**：在 Ticket 的 `tdd_stage` 欄位記錄當前 Phase。遷移任務豁免標記跳過的 Phase。

---

## `/tdd next` - 推進到下一個 Phase

在當前 Phase 完成後，確認轉換條件並推進。

**執行前 Read**：當前 Phase 對應的 `references/phase{N}/rules.md`（查看「轉換條件」章節）

> **框架整合**：使用 `scripts/phase_complete.py` 執行 Phase Contract 驗證，確認產出符合要求後執行 `/ticket track complete {id}` 標記完成。Phase 1/2/3a 由執行者自行 commit。

---

## `/tdd split` - Phase 1 SOLID 拆分分析

在 Phase 1 設計階段，使用 SOLID 原則分析功能需求，產出拆分建議。

**執行前 Read**：`references/phase1/rules.md`（「SOLID 拆分進階工具與範本」章節）

CLI 工具位於 `scripts/tdd-phase1-split.py`。

> **框架整合**：使用 `/ticket create --parent {parent_id}` 建立子 Ticket，以 `blockedBy` 標記依賴。

---

## `/tdd status` - 查看當前進度

確認目前所在 TDD 階段、完成情況、下一步行動。

---

## `/tdd phase4-exempt` - Phase 4 豁免評估

Phase 3b 完成後，評估是否符合 Phase 4 豁免條件（跳過 4a/4c，直接執行 4b）。

**執行前 Read**：`references/phase4/rules.md`（「Phase 4 豁免評估」章節）

> **框架整合**：Phase 4a 使用 `/parallel-evaluation B`，Phase 4c 使用 `/parallel-evaluation A`。

---

## 3b 拆分評估（Phase 3a 完成後強制執行）

Phase 3a 策略文件完成後，評估 Phase 3b 是否需要拆分為多個並行子任務。

**執行前 Read**：`references/phase3/rules.md`（「3b 拆分評估」章節）及 `.claude/pm-rules/tdd-flow.md`

> **框架整合**：拆分時建立子任務，指定修改檔案清單（`where.files`），確保無交集，並行派發。

---

## Layer 1 / Layer 2 設計原則

本 SKILL 的所有內容分為兩層，確保核心 TDD 知識可跨專案複用：

| 層次 | 內容 | 可攜性 |
|------|------|--------|
| Layer 1 | Phase 定義、階段轉換條件、SOLID 檢查、BDD/GWT、品質基準、豁免規則、任務類型豁免 | 通用，任何專案可直接使用 |
| Layer 2 | Ticket 系統、Agent 派發、Hook 自動化、決策樹路由、Commit 管理角色 | 本框架特定，以 blockquote (`>`) 標記 |

### Layer 1 禁止引用

在 `references/phase{N}/rules.md` 的非 blockquote 區域，禁止出現：

| 禁止項 | 替代方式 |
|--------|---------|
| `/ticket` CLI（如 `/ticket create`） | 「任務系統」「狀態管理」 |
| 具體代理人名稱（lavender/parsley/sage 等） | 「設計者」「實作者」「測試者」 |
| `.claude/hooks/` 系統 | 「驗證機制」「檢查點」 |
| `decision-tree` 路由 | 「階段轉換」「路由決策」 |
| `/parallel-evaluation` 工具 | 「多維度分析」「交叉審查」 |
| 本專案路徑（`.claude/`、`docs/`） | 「規則目錄」「工作目錄」 |
| Wave、Patch 概念 | 「執行批次」「版本」 |

### Layer 2 整合點

Layer 2 內容以 blockquote 標記，提供本框架的具體實現方式：

| 整合點 | Layer 1 描述 | Layer 2 實現 |
|--------|-------------|-------------|
| 任務管理 | 「任務轉換條件」 | `/ticket track complete` |
| 角色派發 | 「Phase 1 由設計者執行」 | 「派發給 lavender-interface-designer」 |
| 自治提交 | 「完成後自行提交」 | `feat({id}): Phase X - {摘要}` |
| 多視角分析 | 「多維度交叉審查」 | `/parallel-evaluation` |

---

## 案例集

真實案例記錄 TDD 各階段踩過的坑，供設計和審查時參考：

| 案例 | 對應 Phase | 主要教訓 |
|------|-----------|---------|
| [跨模組共用策略缺失](references/cases/cross-module-shared-strategy-gaps.md) | Phase 1 | 規格未標注跨模組驗證重複、ID 碰撞、欄位映射缺失、零日誌 |
| [測試資料與可觀測性盲點](references/cases/test-data-and-observability-blind-spots.md) | Phase 2 | 測試資料殘留 v1 欄位碰巧通過、catch 區塊零日誌未測 |
| [印表機測試覆蓋深度不足](references/cases/printer-test-coverage-depth-failure.md) | Phase 2 | 28 個測試全過但 4 個 Bug 上線，路徑深度不足、try-catch 吞錯誤 |
| [並行實作重複與 Lint](references/cases/parallel-impl-duplication-and-lint.md) | Phase 3 | 並行 worktree 各自實作驗證框架、dead import、版本號硬編碼 |
| [多視角審查發現總結](references/cases/multi-perspective-review-findings-v0170.md) | Phase 4 | 完整審查報告：規格盲點 36%、測試盲點 27%、實作品質 36% |
| [Chrome Storage API 效能延遲](references/cases/storage-api-performance-latency.md) | Phase 1 | 規格應定義效能目標數值，批次參數屬規格範疇 |
| [批次寫入失敗處理策略](references/cases/storage-write-failure-handling.md) | Phase 1 | 回滾/孤立/預防中止三策略選擇，規格須定義失敗策略 |
| [私有方法測試覆蓋缺口](references/cases/private-method-test-coverage-gap.md) | Phase 2 | 合併邏輯和快取鍵的私有方法無獨立斷言，邊界條件未覆蓋 |
| [異常路徑測試覆蓋缺口](references/cases/error-path-test-coverage-gap.md) | Phase 2 | 180 錯誤碼中 49% 生產路徑未測，引用 != 測試 |
| [Phase 4 豁免判斷邊界](references/cases/phase4-exemption-doc-task.md) | Phase 4 | DOC 標籤不等於低風險，豁免條件應改為 AND 邏輯 |
| [SA 審查 Tag-based Book Model](references/cases/sa-review-tag-based-book-model.md) | Phase 0 | 跨 3 子域變更必須 Phase 0，重複實作只能在系統層級識別 |

---

## 相關資源

- TDD 流程規則：`.claude/pm-rules/tdd-flow.md`
- 任務拆分指南：`.claude/rules/guides/task-splitting.md`
- 並行派發指南：`.claude/rules/guides/parallel-dispatch.md`
- 認知負擔原則：`.claude/rules/core/cognitive-load.md`

---

**Last Updated**: 2026-04-04
**Version**: 2.0.0 - 全面重整：消滅孤立文件、統一 scripts/、集中 cases、子命令加入 Read 指示
**Specialization**: TDD 全流程指導（Phase 0-4）
