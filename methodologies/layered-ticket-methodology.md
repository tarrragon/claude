# 層級隔離派工方法論

> **定位**：定義 Clean Architecture 五層劃分標準與單層修改原則，指導 Ticket 拆分與從外而內實作順序。受眾為 PM（拆 Ticket）、開發人員（執行單層修改）、架構師（設計審查）、Code Reviewer（檢查層級隔離）。30 秒複習清單；完整 code 範例與案例見 Reference 段。

**適用範圍**：所有遵循 Clean Architecture 的專案。

> **與 Atomic Ticket 的關係**：本方法論管「層級維度」（一個 Ticket 只改一個架構層），[Atomic Ticket 方法論](./atomic-ticket-methodology.md) 管「職責維度」（一個 Action + 一個 Target），兩者互補。Ticket 拆分的核心依據仍是單一職責原則，本文件的量化指標僅供參考。

---

## 30 秒核心

| 原則 | 一句話定義 |
|------|-----------|
| 五層劃分 | 業務邏輯切成 UI / Behavior / UseCase / Domain Interface / Domain 五層，每層變更原因單一 |
| 單層修改 | 一個 Ticket 只修改單一架構層級，變更原因單一且明確（對應 SRP） |
| 從外而內 | 實作順序 Layer 1 → 5，影響範圍與回滾成本遞增，先驗證影響小的層 |
| 依賴倒置 | 外層依賴內層的抽象介面，內層不依賴外層，所有依賴通過介面（DIP） |
| 粒度標準 | 1-3 檔（最多 5）、50-200 行（最多 300）、單層、2-8 小時、測試覆蓋率 100% |

---

## 五層架構定義

> code-smell-checklist 等引用方依賴本節（2.2 五層、2.3 依賴方向）。

| 層級 | 名稱 | 職責 | Flutter 對應 | 變更原因 |
|------|------|------|-------------|---------|
| Layer 1 | UI / Presentation | 視覺呈現、樣式、UI 狀態 | Widget、build()、Theme | 視覺設計變更 |
| Layer 2 | Application / Behavior | 事件處理、UI 邏輯、輸入驗證、Domain→ViewModel 轉換、UseCase 協調 | Controller、ViewModel、Presenter、Bloc/Cubit | 互動流程或事件處理變更 |
| Layer 3 | UseCase | 業務流程編排、跨 Domain 資料整合、事件發布 | UseCase、execute() | 業務流程或編排邏輯變更 |
| Layer 4 | Domain Events / Interfaces | 介面契約、事件定義、DTO 定義 | abstract class 介面、Event、DTO | 契約定義或事件結構變更 |
| Layer 5 | Domain Implementation | 核心業務規則、Entity、Value Object、Domain Service | Entity、Value Object、Domain Service | 核心業務規則變更 |

**依賴方向**（2.3）：Layer 1 → 2 → 3 → 4，Layer 5 實作 Layer 4 介面。外層依賴內層，內層不依賴外層；Layer 3 只依賴 Layer 4 抽象介面，不依賴 Layer 5 具體實作；所有依賴通過介面（DIP）。

**Infrastructure 層不納入五層討論**：資料持久化、第三方 API、技術基礎設施（Repository 實作、API Client、EventBus 實作）由技術驅動變更，與五層的需求驅動變更模式不同，通常是獨立技術 Ticket。

**判斷程式碼屬於哪一層（決策樹）**：依序問——渲染 UI 元素？→ Layer 1；處理 UI 事件或轉換資料給 UI？→ Layer 2；協調多個 Domain Service 或編排業務流程？→ Layer 3；定義介面契約或事件結構？→ Layer 4；實作核心業務規則或定義 Entity？→ Layer 5；皆否 → Infrastructure。決策卡住時改問「變更原因是什麼」：視覺/互動/業務流程/契約/業務規則分別對應 Layer 1-5；仍無法判斷代表職責不單一，需拆分。

---

## 單層修改原則

> code-smell-checklist 引用本節（3.1）作為 Shotgun Surgery 等 Code Smell 的判準。

**定義**：一個 Ticket 的所有程式碼變更集中在同一 Clean Architecture 層級，變更原因單一（SRP），測試範圍限定該層級。

**判斷檢查清單**：

- [ ] 所有程式碼修改都在同一架構層級？
- [ ] 變更原因單一且明確？
- [ ] 測試範圍限定該層級（不需啟動其他層）？
- [ ] 可獨立驗收，不依賴其他層級完成？

**違反的常見模式**：

| 模式 | 問題 | 解法 |
|------|------|------|
| Shotgun Surgery | 一個小變更需同時改多層 | 引入 DTO / Adapter 隔離層級依賴 |
| Feature Envy | 一層過度依賴另一層的內部細節（UI 直存 Domain 欄位） | 引入 ViewModel / Presenter 轉換 |
| Divergent Change | 不同原因的變更集中在同一類別（Controller 同時負責列表與詳情） | 按職責拆分類別 |

---

## 從外而內實作順序

**順序**：UI → Behavior → UseCase → Domain Events → Domain。從最小影響範圍開始逐步深入核心。

**為什麼**：影響範圍與回滾成本隨層級遞增（Layer 1 改 UI 風險低、回滾極低；Layer 5 改業務規則風險高、回滾極高）。先實作影響小的層快速驗證需求，及早發現需求偏差，調整成本低；每層完成後立即測試（Layer 1 Widget 測試 / Layer 2 行為測試 / Layer 3 UseCase 測試 / Layer 4 介面測試 / Layer 5 Domain 測試）。

**特殊場景需替代策略**：

| 場景 | 策略 | 理由 |
|------|------|------|
| 架構遷移 | Interface-First（先定 Layer 4 介面） | 外層修改依賴內層介面穩定，大爆炸重構風險高 |
| 安全性修復 | 從內而外（Core-First） | 安全問題必須從核心修復，業務正確性優先於 UI |
| 緊急 Bug Fix | 依 Bug 根因所在層決定 | UI Bug 從外而內，Domain Bug 從內而外 |
| 第三方套件升級 | 依套件依賴位置決定 | Infrastructure 用則技術驅動，影響 Domain Interface 則 Interface-First |

---

## Ticket 粒度標準

> code-smell-checklist 引用本節（5.2）量化指標。

| 指標 | 標準值 | 容許上限 |
|------|--------|---------|
| 修改檔案數 | 1-3 個 | 5 個（超過需拆分） |
| 程式碼行數 | 50-200 行 | 300 行（含測試） |
| 修改層級 | 1 層 | 嚴格單層 |
| 開發時間 | 2-8 小時 | 1 天 |
| 測試覆蓋率 | 100% | 不容許低於 100% |

**超標處理**：檔案數 > 5 → 分析依賴關係強制拆分；行數 > 300 → 先檢查重複邏輯可否提取，否則按子功能拆分；時間 > 1 天 → 重新評估複雜度與依賴後拆分為多個半天 Ticket。粒度過小（如改 1 行）則合併為同層級、同變更原因的較大 Ticket。

**拆分維度優先序**：按架構層級拆分（優先）→ 按功能模組 → 按變更原因 → 按依賴關係（標記先後順序）。

---

## 檢查清單

**單層修改**：所有修改在同一層級？變更原因單一？測試範圍限定該層級？

**Ticket 設計**：符合粒度標準（1-5 檔）？有明確驗收條件？可獨立測試驗收？

**依賴方向**：外層依賴內層？內層不依賴外層？透過介面隔離？

---

## Reference

完整 code 範例（各層 Dart 實作、錯誤處理三階段、Interface-First 五步驟）與實踐案例（新功能 / 重構 / 架構遷移）已隨本次整併移除（屬完整流程細節，非 30 秒核心）；需要時依下列相關方法論查閱：

- [層級檢查機制](./layered-architecture-quality-checking.md) - 檔案路徑分析法、測試範圍分析法、違規模式識別
- [Atomic Ticket 方法論](./atomic-ticket-methodology.md) - 單一職責設計原則
- [敏捷重構方法論](./agile-refactor-methodology.md) - Agent 分工協作模式
- [TDD 四階段流程](./tdd-collaboration-flow.md) - 開發流程整合
