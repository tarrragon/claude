# 分層測試策略：依架構層級選測試方法

## 目的

依架構層級選擇測試方法的決策指引。不同層的程式碼性質不同（UI 是互動流程、UseCase 是業務行為、Domain 是規則邏輯），統一測試手法會造成過度測試或覆蓋不足。不依架構分層制定策略，重構時大量測試壞掉（測太細）或上線後出 bug（測太粗）。依本文五層分工表和判斷流程，為每層選擇適合的測試方法。

---

## 五層測試分工表

| Layer | 測試類型 | 覆蓋率要求 | 觸發條件（何時寫測試） | 跳過條件（何時不測） |
|-------|---------|-----------|---------------------|-------------------|
| 1 UI/Presentation | 整合測試 | 關鍵流程 100% | 流程失敗影響核心業務、多步驟操作、涉及金流/敏感資料 | 靜態展示頁面、簡單列表 |
| 2 Application/Behavior | 條件單元測試 | 複雜邏輯 100% | 轉換含條件判斷、計算邏輯、多來源資料、邏輯 >10 行 | 簡單 DTO 欄位直接映射（由 UseCase 層間接覆蓋） |
| 3 UseCase | BDD 測試 | 行為場景 100% | 所有業務場景，無例外 | 無（必測層） |
| 4 Interface | 不測試 | 0% | — | 介面只定義合約，無可測試行為 |
| 5 Domain Implementation | 單元測試 | 分支 100% | 業務規則驗證、計算邏輯、狀態轉換、不變量檢查 | 純資料容器 Entity |

UseCase 層每個 UseCase 至少涵蓋：1 個正常流程 + 2 個異常流程 + 3 個邊界條件。只 Mock 外層依賴，使用真實 Domain Entity。

---

## 判斷流程

先定位程式碼所屬層級（目錄結構反映架構層級），再問該層一個問題：

1. **UI 層**：這是關鍵互動流程嗎？→ 是：寫整合測試（必須覆蓋操作行為——tap→navigate / submit→callback / error→fallback，不只覆蓋元件存在性） / 否：跳過，讓人工測試覆蓋
2. **Behavior 層**：這裡有複雜轉換邏輯嗎？→ 是：寫條件單元測試 / 否：跳過，讓 UseCase 層間接覆蓋
3. **UseCase 層**：直接寫 BDD 測試，不問
4. **Interface 層**：不測試，不問
5. **Domain 層**：這裡有複雜業務規則嗎？→ 是：寫單元測試 / 否：跳過，純資料容器由上層覆蓋

---

## 覆蓋率語意

覆蓋率數字背後有實際語意，不是為報告好看：

| 層級 | 覆蓋率指標 | 語意 |
|------|-----------|------|
| UseCase | 行為場景覆蓋率 100% | 所有業務場景都有測試（非程式碼行數百分比） |
| Domain | 分支覆蓋率 100% | 每個分支代表一個業務決策，都必須驗證 |
| 整體新增程式碼 | 80% 以上 | 扣除跳過層（Interface、簡單映射、純資料容器）後的合理基線 |

---

## 測試穩定性原則

測試因業務改變而失敗，代表測試在保護業務正確性——這很好。測試因重構內部實作而大量失敗，代表測試耦合了實作細節——這是設計問題。

| 層級 | 穩定性預期 | 說明 |
|------|-----------|------|
| UseCase BDD | 高 | 關注行為，重構內部邏輯只要業務行為不變，測試不需動 |
| Domain 單元 | 高 | 只有規則本身改變才需更新 |
| Behavior 條件 | 中 | 只測複雜轉換邏輯，重構簡單映射不影響測試 |
| UI 整合 | 低 | UI 變動頻繁，只測關鍵流程以控制維護成本 |

---

## 技術性必檢項目

不分層級都要納入的基礎驗證，容易被忽略但上線後常出問題：

- **Null 值和空集合**：輸入為 null / 空陣列 / 空字串時的行為
- **邊界值**：零、負數、最大值、溢位
- **異常處理**：網路錯誤、儲存失敗、逾時
- **資料驗證**：格式、範圍、必填欄位

---

## 與 monitor 專案的對應

monitor 專案非典型 Clean Architecture（monorepo 含多語言 SDK + collector），五層對應需適配：

| 五層 | monitor 對應元件 | 測試方法 |
|------|-----------------|---------|
| UseCase | collector handler（接收+驗證+儲存+查詢）、各 SDK 的 flush/batch 邏輯 | BDD 測試（GWT 場景） |
| Domain | schema validator、event 建構邏輯、query 篩選邏輯 | 單元測試（分支覆蓋 100%） |
| Behavior | SDK 的 event→JSON 序列化、collector 的 response 格式轉換 | 條件單元測試（有複雜邏輯時） |
| Interface | `schema/event.schema.json`（契約定義） | 不測試（由 protocol integration 驗證契約實現） |
| Transport | SDK↔collector HTTP 通訊層 | 見 `protocol-integration-testing.md`（Mock 從結構上無法驗證協議契約） |

---

## 檢查清單

測試設計時確認：

- [ ] 已定位程式碼所屬架構層級？
- [ ] 已依判斷流程決定測試方法（而非預設全部單元測試）？
- [ ] UseCase 層每個場景至少 1 正常 + 2 異常 + 3 邊界？
- [ ] UseCase 層只 Mock 外層依賴、使用真實 Domain Entity？
- [ ] Domain 層複雜規則分支覆蓋率 100%？
- [ ] 技術性必檢項目（Null / 邊界 / 異常 / 驗證）已納入？
- [ ] 跳過的層級確認由上層間接覆蓋？

---

## 相關文件

- `references/phase2-test-design.md` — Phase 2 測試設計指引（通用三層金字塔，本文是五層展開的 refinement）
- `references/doc-handoff.md` — doc→TDD 銜接（UC 場景的整合/單元分工判準）
- `references/bdd-behavior-testing.md` — BDD 行為測試深度指引（Sociable/Solitary、分層 Mock）
- `references/protocol-integration-testing.md` — Protocol integration 三層策略（Mock 遮蔽機制）
- `.claude/methodologies/hybrid-testing-strategy-methodology.md` — 方法論 stub（30 秒核心）

---

**Last Updated**: 2026-06-22
**Version**: 1.0.0 — 從 blog hybrid-testing-strategy-methodology 提煉，整合 monitor 專案對應
**Source**: `~/Projects/blog/content/record/hybrid-testing-strategy-methodology.md`
