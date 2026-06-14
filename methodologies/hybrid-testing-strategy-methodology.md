# 混合測試策略方法論（30 秒核心）

> **本檔已瘦身（W8-018.2）**：通用測試策略選擇（測試金字塔、測試類型選擇、邊界條件、技術性必檢項目）已在 `/tdd` skill 的 `.claude/skills/tdd/references/phase2-test-design.md`。本檔僅保留本方法論的 distinct 核心：依 Clean Architecture 層級選測試方法的決策樹。需要 GWT 設計、場景覆蓋、測試案例格式時直接讀 phase2-test-design.md。

混合測試策略依 Clean Architecture 層級選擇測試方法：BDD 測業務行為、單元測試測複雜邏輯、整合測試測關鍵流程。核心是「不同架構層用不同測試手段」，避免整合測試做單元測試的工作。

---

## 分層測試決策樹（distinct 核心）

| 層級 | 測試類型 | 覆蓋率要求 | 觸發條件 |
|-----|---------|-----------|---------|
| Layer 1 (UI) | 整合測試（關鍵流程） | 關鍵路徑 100% | 流程失敗影響核心業務 / 多步驟操作 / 涉及金流敏感資料 |
| Layer 2 (Behavior) | 單元測試（複雜轉換） | 邏輯覆蓋率 100% | 含條件判斷 / 計算邏輯 / 多來源資料 / 邏輯超過 10 行 |
| Layer 3 (UseCase) | BDD 測試（所有場景） | 行為場景 100% | 所有業務行為（Given-When-Then） |
| Layer 4 (Interface) | 不測試 | N/A | 由實作層測試 |
| Layer 5 (Domain) | 單元測試（複雜邏輯） | 程式碼+分支 100% | 含業務規則驗證 / 計算 / 狀態轉換 / 不變量檢查 |

**判斷流程**：先定位程式碼屬哪一層，再依該層的觸發條件決定是否需測試及測試類型。Layer 2/5 的「複雜」是觸發單元測試的門檻，不複雜則依賴 UseCase 層 BDD 測試涵蓋。

---

## 路由

| 需求 | 讀這裡 |
|------|--------|
| 測試金字塔、測試類型選擇、GWT 設計、場景覆蓋、邊界條件識別、技術性必檢項目 | `.claude/skills/tdd/references/phase2-test-design.md` |
| BDD Given-When-Then 格式與行為鏈、前置條件驗證 | `.claude/methodologies/bdd-testing-methodology.md` |
| Sociable vs Solitary 測試邊界選擇 | `.claude/methodologies/behavior-first-tdd-methodology.md` |

---

**Last Updated**: 2026-06-13
**Version**: 2.0.0 — W8-018.2 整併瘦身：通用測試策略內容路由至 `/tdd` skill phase2-test-design.md，保留 distinct 的 Clean Architecture 分層決策樹為 30 秒核心 + 路由。歷史完整版見 git log。
