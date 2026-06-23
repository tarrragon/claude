# 行為優先 TDD 方法論（30 秒核心）

> **本檔已瘦身（W8-018.2）**：路徑驅動測試、Bug 遮蔽模式、try-catch 測試策略、Fake/Mock 設計原則、測試自我檢查清單已完整收錄於 `/tdd` skill 的 `.claude/skills/tdd/references/phase2-test-design.md`（「測試實戰教訓」「從呼叫路徑出發」「try-catch 設計原則」「Fake/Mock 設計原則」「檢查清單」）。本檔僅保留 30 秒核心 + 本方法論的 distinct 內容（Sociable vs Solitary 選擇與前置條件關係）。需要實戰教訓六個坑的完整案例時直接讀 phase2-test-design.md。

測試耦合到行為（Module API），而非結構（Class Methods）。重構時測試保持穩定，因為測試只透過 Public API 互動，不知道內部有哪些類別。

---

## Sociable vs Solitary 選擇（distinct 核心）

| 類型 | Unit 定義 | Mock 範圍 | 適用 |
|------|----------|----------|------|
| Sociable（推薦） | Module（1 或多個類別） | 只 Mock 外部依賴（DB / 檔案系統 / 外部服務） | 業務應用、CRUD / Web API |
| Solitary（特殊情況） | Class | Mock 所有協作者 | 數學演算法、加密系統 |

**核心主張**：優先 Sociable，使用真實 Domain Entities；只在數學演算法/加密系統才用 Solitary。Solitary 測試脆弱、維護成本高。

**重構安全性驗證**：改變內部邏輯 / 調整類別結構 / 重新命名內部方法 → 測試應不變。全部「測試不變」= Sociable（正確）；任何「測試需改」= Solitary（重新設計）。

### Sociable 與前置條件驗證的關係

Sociable Unit Tests 的「使用真實 Domain Entities」原則，使前置條件驗證有實際意義——「按鈕存在」是真實渲染的結果，而非 Mock 的預設值。

| 測試類型 | 前置條件來源 | 前置條件可驗性 |
|---------|------------|--------------|
| Sociable（真實物件） | 透過真實 Domain Entity 建立，狀態真實可驗 | 高（前置條件即真實業務狀態） |
| Solitary（Mock 一切） | Mock 物件回傳預設值，狀態是假設的 | 低（前置條件只是測試假設） |

**禁止模式**：直接假設 Mock 會回傳正確值而不驗證 Mock 設定是否正確。

### Sociable 行為推演檢查清單

- [ ] 測試的前置狀態是透過真實物件建立的，而非 Mock 硬編碼
- [ ] Mock 的回傳值符合真實業務邏輯（不是任意假值）
- [ ] 每個 Given 步驟有對應的驗證斷言
- [ ] 行為觸發（When）只呼叫 Module Public API，不呼叫內部方法
- [ ] 結果確認（Then）驗證的是可觀察輸出，不是 Mock 被呼叫的次數

---

## 路由

| 需求 | 讀這裡 |
|------|--------|
| 路徑驅動測試、Bug 遮蔽模式、整合測試 vs 單元測試分工 | `.claude/skills/tdd/references/phase2-test-design.md`「測試實戰教訓」「從呼叫路徑出發」 |
| try-catch 測試策略、Fake/Mock 設計原則、測試自我檢查清單 | `.claude/skills/tdd/references/phase2-test-design.md`「try-catch 設計原則」「Fake/Mock 設計原則」「檢查清單」 |
| Sociable vs Solitary 完整選擇框架、重構安全性驗證、BDD→單元拆分判準 | `.claude/skills/tdd/references/bdd-behavior-testing.md` |
| Given-When-Then 格式與前置條件驗證 | `.claude/methodologies/bdd-testing-methodology.md` |
| 分層測試決策樹（完整版） | `.claude/skills/tdd/references/layered-test-strategy.md` |

### 外部文獻

- Kent Beck,《Test Driven Development By Example》
- Martin Fowler,《Refactoring》
- Google,《Software Engineering at Google》

---

**Last Updated**: 2026-06-13
**Version**: 2.0.0 — W8-018.2 整併瘦身：路徑驅動測試 / try-catch / Fake-Mock / 自我檢查清單路由至 `/tdd` skill phase2-test-design.md（內容已完整收錄），保留 30 秒核心 + distinct 的 Sociable vs Solitary 選擇與前置條件關係。歷史 1.3.0 完整版見 git log。
