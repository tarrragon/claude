# 方法論體系導覽

> **方法論 = 30 秒可複習的明確判斷標準與操作清單**

本目錄包含 52 個方法論檔案，依功能家族分組導覽如下。各方法論遵循 `framework-meta-methodology` 定義：30 秒可複習（< 1 頁），提供明確判斷標準供 AI 執行。

---

## 1. TDD & 測試家族

| 方法論 | 用途 |
|--------|------|
| [behavior-first-tdd-methodology](./behavior-first-tdd-methodology.md) | TDD 痛點根源與 Sociable Unit Tests 理論基礎 |
| [bdd-testing-methodology](./bdd-testing-methodology.md) | Given-When-Then 格式規範與 Clean Architecture 整合 |
| [hybrid-testing-strategy-methodology](./hybrid-testing-strategy-methodology.md) | 分層測試決策樹（Layer 1-5）與量化覆蓋率指標 |
| [tdd-collaboration-flow](./tdd-collaboration-flow.md) | TDD 四階段流程（Phase 0-4）與代理人派發規範 |
| [tdd-ticket-integration-methodology](./tdd-ticket-integration-methodology.md) | TDD 與 Ticket 生命週期整合 |
| [three-phase-reflection-methodology](./three-phase-reflection-methodology.md) | 測試失敗三階段反思（隔離問題、重現最小案例、根因分析）|
| [test-assertion-design-methodology](./test-assertion-design-methodology.md) | 斷言設計判斷框架（flaky 與設計品質問題識別）|
| [legacy-code-test-rebuild-methodology](./legacy-code-test-rebuild-methodology.md) | 遺留程式碼測試重建策略 |

---

## 2. Ticket 管理家族

| 方法論 | 用途 |
|--------|------|
| [atomic-ticket-methodology](./atomic-ticket-methodology.md) | Atomic Ticket 設計原則（單一責任、可驗收、獨立）|
| [ticket-design-dispatch-methodology](./ticket-design-dispatch-methodology.md) | Ticket 設計與派發決策樹 |
| [layered-ticket-methodology](./layered-ticket-methodology.md) | Layered Ticket 設計方法論 |
| [group-ticket-design-methodology](./group-ticket-design-methodology.md) | Group Ticket 設計與拆分策略 |
| [ticket-lifecycle-management-methodology](./ticket-lifecycle-management-methodology.md) | Ticket 生命週期管理（create → complete）|
| [csv-ticket-tracking-methodology](./csv-ticket-tracking-methodology.md) | CSV Ticket 追蹤機制（已廢棄，改用 ticket CLI）|
| [frontmatter-ticket-tracking-methodology](./frontmatter-ticket-tracking-methodology.md) | Frontmatter Ticket 追蹤機制 |
| [acceptance-criteria-methodology](./acceptance-criteria-methodology.md) | 驗收條件設計原則（SMART 原則、可勾選）|
| [handoff-design-principle-methodology](./handoff-design-principle-methodology.md) | 任務交接設計原則（純指針，禁含任務描述）|

---

## 3. Hook 系統家族

| 方法論 | 用途 |
|--------|------|
| [hook-system-methodology](./hook-system-methodology.md) | Hook 系統架構與設計原則 |
| [rule-layer-ssot-before-hook-layer-methodology](./rule-layer-ssot-before-hook-layer-methodology.md) | 規則層 SSOT 優先於 Hook 層原則 |

---

## 4. 品質與架構家族

| 方法論 | 用途 |
|--------|------|
| [cognitive-load-design-methodology](./cognitive-load-design-methodology.md) | 認知負擔設計原則（降低閱讀者負擔）|
| [natural-language-programming-methodology](./natural-language-programming-methodology.md) | 自然語言程式設計（讓程式碼像文章）|
| [clean-architecture-implementation-methodology](./clean-architecture-implementation-methodology.md) | Clean Architecture 實作方法論（分層依賴倒置）|
| [layered-architecture-quality-checking](./layered-architecture-quality-checking.md) | 分層架構品質檢查清單 |
| [comment-writing-methodology](./comment-writing-methodology.md) | 註解撰寫原則（業務情境聚焦、抽象層級貼合）|
| [code-smell-quality-gate-methodology](./code-smell-quality-gate-methodology.md) | Code Smell 品質閘門（識別與修復）|
| [design-driven-refactoring-methodology](./design-driven-refactoring-methodology.md) | 設計驅動重構方法論 |
| [agile-refactor-methodology](./agile-refactor-methodology.md) | 敏捷重構方法論（增量式改善）|
| [error-fix-refactor-methodology](./error-fix-refactor-methodology.md) | 錯誤修復重構方法論 |
| [package-import-methodology](./package-import-methodology.md) | 套件 import 管理方法論 |

---

## 5. 流程與協作家族

| 方法論 | 用途 |
|--------|------|
| [5w1h-self-awareness-methodology](./5w1h-self-awareness-methodology.md) | 5W1H 自我感知方法論（任務明確性檢查）|
| [claude-self-check-methodology](./claude-self-check-methodology.md) | Claude 自我檢查方法論（回應前品質確認）|
| [friction-management-methodology](./friction-management-methodology.md) | 摩擦力管理方法論（開發流程階段摩擦力曲線）|
| [migration-methodology](./migration-methodology.md) | 資料遷移方法論 |
| [business-layer-i18n-management-methodology](./business-layer-i18n-management-methodology.md) | 業務層 i18n 管理方法論 |
| [lsp-first-development-methodology](./lsp-first-development-methodology.md) | LSP 優先開發方法論 |
| [instant-review-mechanism-methodology](./instant-review-mechanism-methodology.md) | 即時審查機制方法論 |

---

## 6. 分析與反思家族

| 方法論 | 用途 |
|--------|------|
| [systematic-debugging-methodology](./systematic-debugging-methodology.md) | 系統化除錯方法論（問題隔離與根因分析）|
| [operational-error-root-cause-methodology](./operational-error-root-cause-methodology.md) | 營運錯誤根因分析方法論 |
| [parallel-evaluation-methodology](./parallel-evaluation-methodology.md) | 多視角並行評估方法論（三人組審查）|
| [problem-awareness-evaluation-methodology](./problem-awareness-evaluation-methodology.md) | 問題意識評估方法論 |
| [three-phase-reflection-methodology](./three-phase-reflection-methodology.md) | 三階段反思方法論（根因反思、不回退、教訓提煉）|
| [agent-failure-debugging-sop](./agent-failure-debugging-sop.md) | Agent 失敗除錯 SOP |
| [pm-judgment-interference-map](./pm-judgment-interference-map.md) | PM 判斷干擾地圖（決策盲點識別）|

---

## 7. 框架與元方法論

| 方法論 | 用途 |
|--------|------|
| [framework-meta-methodology](./framework-meta-methodology.md) | 框架元方法論（30 秒標準定義）|
| [knowledge-carrier-allocation-methodology](./knowledge-carrier-allocation-methodology.md) | 知識載體責任分配（rules/agents/skills/methodologies 邊界）|
| [methodology-writing-methodology](./methodology-writing-methodology.md) | 方法論撰寫方法論（格式與品質標準）|
| [methodology-rewriting-methodology](./methodology-rewriting-methodology.md) | 方法論改寫方法論 |
| [five-document-system-methodology](./five-document-system-methodology.md) | 五文件系統方法論（worklog/ticket/CHANGELOG/todolist/error-patterns）|
| [worklog-writing-methodology](./worklog-writing-methodology.md) | 工作日誌撰寫方法論 |
| [error-pattern-numbering-methodology](./error-pattern-numbering-methodology.md) | Error Pattern 編號方法論 |

---

## 8. 其他專門方法論

| 方法論 | 用途 |
|--------|------|
| [personalized-consultation-methodology](./personalized-consultation-methodology.md) | 個人化諮詢方法論（AI 諮詢倫理，識別/分級/誠實三層機制）|
| [suggestion-tracking-methodology](./suggestion-tracking-methodology.md) | 建議追蹤方法論 |

---

## 使用指引

### 新手路徑

1. **理解品質基線** → `cognitive-load-design-methodology`（所有設計的終極目標）
2. **學習 TDD 流程** → `tdd-collaboration-flow`（四階段流程）→ `behavior-first-tdd-methodology`（理論基礎）
3. **學習 Ticket 管理** → `atomic-ticket-methodology`（設計原則）→ `ticket-lifecycle-management-methodology`（生命週期）
4. **理解架構原則** → `clean-architecture-implementation-methodology`（分層依賴倒置）

### 快速查找

| 需求場景 | 參考方法論 |
|---------|-----------|
| 撰寫測試 | `bdd-testing-methodology` → Given-When-Then 規範 |
| 判斷測試類型 | `hybrid-testing-strategy-methodology` → 決策樹 |
| 設計 Ticket | `atomic-ticket-methodology` + `ticket-design-dispatch-methodology` |
| 任務拆分 | `layered-ticket-methodology` + `group-ticket-design-methodology` |
| 除錯問題 | `systematic-debugging-methodology` + `operational-error-root-cause-methodology` |
| Code Review | `parallel-evaluation-methodology` → 多視角審查 |
| 重構評估 | `design-driven-refactoring-methodology` + `agile-refactor-methodology` |
| 撰寫註解 | `comment-writing-methodology` + `natural-language-programming-methodology` |
| Hook 設計 | `hook-system-methodology` + `rule-layer-ssot-before-hook-layer-methodology` |
| 方法論撰寫 | `methodology-writing-methodology` + `framework-meta-methodology` |

---

## 核心原則

### 方法論 = 30 秒可複習的明確判斷標準

- **不是**：完整流程說明、程式碼範例、決策表格（這些屬 skill reference）
- **是**：明確判斷標準、操作清單、快速參考表

**Why**：方法論聚焦判斷標準（< 1 頁可複習），skill reference 承載完整流程與範例（按需載入）。**Consequence**：混淆兩者會導致方法論膨脹為多頁文件失去快速參考價值。**Action**：寫方法論時問「這段是判斷依據還是執行細節」，後者移至對應 skill。

### 認知負擔最小化

所有設計原則的終極目標：降低閱讀者的認知負擔。參考 `cognitive-load-design-methodology`。

**Consequence**：認知負擔過載使閱讀者需同時追蹤 > 7 個概念（Miller's Law），導致理解錯誤與維護成本上升。**Action**：設計時依 cognitive-load-design-methodology 量化標準（函式 ≤ 15 行 / 參數 ≤ 3 / 巢狀深度 ≤ 3）自我檢查。

### 行為驅動測試

測試應耦合到行為而非結構。重構時測試不應破裂。參考 `behavior-first-tdd-methodology`。

**Why**：行為（對外可見功能）比結構（內部實作）穩定；測試耦合到行為使重構時測試不需修改。**Consequence**：耦合到結構（如測試 private 方法）會使每次重構需同步改測試，增加重構成本並降低測試對重構的保護。

---

**Last Updated**: 2026-06-15
**Version**: 2.1.0 — Layer 2 審查修正（補充 3 處三明示：方法論定義 / 認知負擔 / 行為驅動測試的 Why/Consequence/Action）
**Maintained by**: thyme-documentation-integrator
