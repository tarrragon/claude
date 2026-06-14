# Ticket 設計派工方法論

**版本**：v3.0.0（30 秒核心 + 引用網絡）

> **30 秒核心**：Ticket 是「最小可交付單元」，與工作日誌互補（Ticket 管執行層面、worklog 管記錄層面）。設計遵循三大目標——可追溯性、可驗收性、可協作性。拆分標準是 Atomic Ticket 的單一職責四大檢查（禁用量化指標）。執行中積極派發子 Ticket 建立任務鏈，不追求單一 Ticket 完成所有任務。

本方法論提供 Ticket 設計與派工的核心框架。詳細標準分散在以下獨立方法論（本檔只保留核心概念 + 路由，避免重複）：

| 主題 | 權威文件 |
|------|---------|
| 單一職責原則、四大評估、拆分範例、任務鏈、子任務建立 | `.claude/methodologies/atomic-ticket-methodology.md`（核心參考） |
| 生命週期、狀態轉換、準備度檢查、父 complete 前置 | `.claude/methodologies/ticket-lifecycle-management-methodology.md` |
| 狀態追蹤機制（frontmatter 即唯一事實源） | `.claude/methodologies/frontmatter-ticket-tracking-methodology.md` |
| 即時 Review 觸發、檢查清單、偏差糾正 | `.claude/methodologies/instant-review-mechanism-methodology.md` |
| 層級拆分（一個架構層一個 Ticket） | `.claude/methodologies/layered-ticket-methodology.md` |

> **重要提醒**：Ticket 設計必須遵循 Atomic Ticket 的單一職責原則。禁止使用時間、行數、檔案數等量化指標判斷拆分，只用「單一職責四大檢查」評估。

---

## 第一章：Ticket 機制核心原則

### 1.1 Ticket vs 工作日誌的定位差異

**Ticket** 是「最小可交付單元」（Minimal Deliverable Unit）：可獨立完成、驗收、追蹤的最小任務單位。特徵：獨立性、原子性、可驗證性、單一職責。

**工作日誌** 記錄整個開發過程：設計決策、實作細節、問題分析、解決方案。特徵：完整性、追溯性、知識傳承。

| 維度 | Ticket | 工作日誌 |
|------|--------|----------|
| 範圍 | 單一具體任務 | 整個功能模組或版本 |
| 粒度 | 最小可交付單元（單一職責） | 完整開發週期（數天到數週） |
| 目的 | 任務執行和驗收 | 知識記錄和傳承 |
| 更新頻率 | 執行中持續更新 | 階段性更新 |
| 文件大小 | 100-200 行 | 500-6000 行 |

**互補關係**（非替代）：Ticket 負責執行層面（拆分大任務為可管理小單元）、工作日誌負責記錄層面（決策過程與演進軌跡）、主版本日誌負責總覽層面（任務總覽與 Ticket 索引）。

### 1.2 Ticket 機制的三大目標

| 目標 | 定義 | 實現方式 |
|------|------|---------|
| 可追溯性 | 每個 Ticket 有明確來源和目標，可追溯到需求/設計/問題報告 | Ticket 含「參考文件」「背景」欄位連結需求；主版本日誌維護完整索引 |
| 可驗收性 | 每個 Ticket 有明確、可驗證的完成標準，避免主觀判斷 | Ticket 含「驗收條件」欄位，條件須客觀可檢查（檔案存在、測試通過、功能運作） |
| 可協作性 | 多開發者可並行執行不同 Ticket，互不阻塞 | 拆分時最小化依賴、明確標註依賴關係、Interface-Driven 開發 |

> 驗收條件設計的完整規範見 `.claude/methodologies/acceptance-criteria-methodology.md`。

### 1.3 基於 Clean Architecture 的設計哲學

Ticket 設計對應 Clean Architecture 三原則：

| 原則 | 內容 | 範例 |
|------|------|------|
| 1. Interface 優先 | 先定義 Interface（契約），再實作具體邏輯 | `Ticket #1 定義 IBookRepository` → `Ticket #2 實作 SQLiteBookRepository（依賴 #1）` |
| 2. 測試驅動拆分 | 每個實作 Ticket 有對應測試 Ticket | Interface 定義 → 測試撰寫 → 具體實作 → 整合驗證 |
| 3. 分層拆分 | 依 Clean Architecture 分層拆 Ticket（職責清晰不跨層） | Domain（Entity/VO/Repository Interface）、Application（Use Case）、Infrastructure（Repository 實作）、Presentation（Controller/ViewModel） |

好處：外層可依賴 Interface 先行（用 Mock）、內層實作延後不阻塞外層、符合 Dependency Inversion；易於並行開發。

### 1.4 Ticket 機制與 TDD 四階段的關係

每個 TDD Phase 產出對應的 Ticket 類型，職責清晰：

| Phase | 產出 Ticket 類型 | 特徵 |
|-------|----------------|------|
| Phase 1（功能設計） | Interface 定義 Ticket | 無具體實作，只有介面簽名與輸入輸出契約 |
| Phase 2（測試設計） | 測試撰寫 Ticket | 測試先行，覆蓋所有 Interface 方法，含正常與異常 |
| Phase 3（實作執行） | 具體實作 + 整合 Ticket | 以測試通過為目標，最小可行實作，100% 通過 |
| Phase 4（重構優化） | 品質改善 Ticket | 保持測試通過，改善品質，不新增功能 |

Ticket 機制支援 TDD：明確的階段產出、Phase 1 後可並行執行 Phase 2-3、每完成一個 Ticket 觸發即時 review。

> TDD 四階段與 Ticket 的完整對應（含 Phase 完成標準、派工準備度檢查、完成後文件更新流程）見 `.claude/methodologies/tdd-ticket-integration-methodology.md` 與 `.claude/tdd-collaboration-flow.md`。

---

## 第二章：Ticket 拆分標準（單一職責原則）

拆分標準完全遵循 Atomic Ticket 的單一職責四大檢查（**完整定義與範例見 `.claude/methodologies/atomic-ticket-methodology.md`**）：

1. **語義檢查**：能用「動詞 + 單一目標」表達嗎？
2. **修改原因檢查**：只有一個原因會導致修改嗎？
3. **驗收一致性**：所有驗收條件指向同一目標嗎？
4. **依賴獨立性**：拆分後不會產生循環依賴嗎？

拆分決策摘要：通過四大檢查 → 保持不變可執行；否則分析違反哪項——語義失敗則拆為多個獨立目標、修改原因過多則依原因拆、驗收不一致則依條件分組、有循環依賴則重新設計依賴關係。

> **禁止**：使用時間、行數、檔案數、測試數等量化指標判斷拆分。

---

## 第三章：生命週期與即時 Review（路由）

Ticket 生命週期（7 狀態：Draft → Ready → In Progress → Review → Blocked → Closed/Cancelled）、狀態轉換規則、準備度檢查清單、即時 Review 觸發機制與 16 項檢查清單，皆為獨立方法論的完整論述，本檔不重複：

| 主題 | 權威文件 |
|------|---------|
| 生命週期定義、狀態轉換、準備度檢查、派工流程 | `.claude/methodologies/ticket-lifecycle-management-methodology.md` |
| 即時 Review 觸發、16 項檢查清單、偏差糾正、Review 記錄 | `.claude/methodologies/instant-review-mechanism-methodology.md` |

**即時 Review 核心理念**：每個 Ticket 完成時立即觸發 Review（非所有任務完成後），範圍限單一 Ticket 相關程式碼，問題剛發生容易修正，反饋週期數小時內。

---

## 第四章：文件管理策略

Ticket 機制下的三層文件結構：

| 層級 | 文件 | 職責 | 大小控制 |
|------|------|------|---------|
| 第一層 | 主版本日誌 | 版本總覽、Ticket 索引、設計決策索引、版本總結 | 約 500-1000 行 |
| 第二層 | Ticket 工作日誌 | 單一 Ticket 執行記錄、實作細節、Review 結果 | 約 100-200 行/Ticket |
| 第三層 | 設計決策日誌 | 設計決策完整記錄、決策演進、廢棄標記、影響分析 | 約 300-500 行 |

**文件更新時機**：Ticket 建立時（建工作日誌 + 更新主版本索引 + 新決策更新決策日誌）、執行中（持續更新工作日誌）、完成後（完成工作日誌 + 更新主版本索引狀態 + 更新 todolist + 調整決策日誌）。

> 本專案實際採用的文件系統（CHANGELOG + todolist + work-log + ticket frontmatter）見 `.claude/references/document-system.md` 與 `.claude/skills/doc-flow/SKILL.md`；Ticket 機制是 work-log 層的細化管理工具。

---

## 第五章：積極派發原則

> 理論依據：Will Guidara《Unreasonable Hospitality》——即興款待（Improvisational Hospitality）。本章為 Ticket 服務精神的權威處（atomic-ticket 等方法論路由至此）。

### 5.1 核心理念

**"Inject meaningful surprises in scalable ways."** Ticket 不只是解決問題的工具，而是為專案品質提供服務的載體。不追求在單一 Ticket 中完成所有任務，而是積極派發新 Ticket，建立可追溯的任務鏈。

**95/5 規則**：95% 結構化執行（原 Ticket 按計劃完成、遵循流程/格式/驗收/TDD 四階段）+ 5% 創意探索（發現的改進機會派發為新 Ticket、研究性 Ticket、深入分析、學習記錄）。

**反饋文化**：測試失敗是反饋不是懲罰；批評行為而非個人（記錄「發生了什麼」而非「誰的錯」）；常態化失敗記錄以消除恐懼。

### 5.2 何時應該派發子 Ticket

| 觸發條件 | 說明 | 範例 |
|----------|------|------|
| 發現新問題 | 執行中發現原本未預見的問題 | 修復 A 時發現 B 也有問題 |
| 範圍擴大 | 需求比預期複雜，超出原 Ticket 範圍 | 原本只改一個方法，發現需改整個類別 |
| 學習機會 | 發現值得深入研究的技術點 | 遇到不熟悉的 API 值得研究 |
| 阻塞解除 | 需先完成其他任務才能繼續 | 發現缺少前置條件 |
| 品質改進 | 發現可以做得更好的地方 | 效能可優化、錯誤處理可更完善 |

**決策**：評估新情況是否超出原 Ticket 範圍——否則繼續在原 Ticket 處理；是則依性質處理（阻塞當前 → 派子 Ticket 標依賴；獨立 → 派新 Ticket 可並行；未來改進 → 記為技術債務 Ticket）。

### 5.3 Ticket 類型選擇指南

| 類型 | 代號 | 適用場景 | 驗收標準重點 |
|------|------|---------|-------------|
| Research | RES | 探索未知領域、技術調研 | 調研報告、可行性評估 |
| Analysis | ANA | 理解現狀、問題分析 | 分析報告、根因識別 |
| Evaluation | EVA | 比較方案、風險評估 | 方案比較表、建議決策 |
| Implementation | IMP | 執行具體任務、功能實作 | 程式碼、測試通過 |
| Investigation | INV | 深入追蹤問題根因 | 問題報告、解決方案 |
| Documentation | DOC | 記錄和傳承經驗 | 文件完成、連結正確 |

> 行為分離原則（開發 IMP → 測試 TST → 調整 ADJ 分開追蹤）與完整類型矩陣見 `.claude/methodologies/atomic-ticket-methodology.md` 與 `.claude/skills/ticket/references/field-semantics.md`。

### 5.4 反模式警告

| 反模式 | 問題 | 正確做法 |
|--------|------|---------|
| 一個 Ticket 做太多事 | 難以追蹤、驗收模糊 | 拆分為多個單一職責 Ticket |
| 發現問題但不記錄 | 問題被遺忘、重複發生 | 立即派發新 Ticket |
| 強迫在原 Ticket 完成 | 範圍膨脹、品質下降 | 評估後派發子 Ticket |
| 為派發而派發 | 過度碎片化、管理成本高 | 遵循單一職責原則判斷 |

---

## 與其他方法論的整合

- [Atomic Ticket 方法論](./atomic-ticket-methodology.md) — 單一職責原則、四大檢查、拆分範例（核心參考）
- [敏捷重構方法論](./agile-refactor-methodology.md) — 三重文件原則、代理人協作
- [TDD 協作開發流程](../tdd-collaboration-flow.md) — 四階段流程、測試驅動

---

**版本歷史**：

- v3.0.0：W8-019.2 整併瘦身（1168 → 30 秒核心 + 路由）。移除 emoji；通用 Clean Architecture 教學、Ticket/主版本日誌完整模板、生命週期 7 狀態詳述、即時 Review 16 項清單、文件更新流程逐步說明等去重至各權威方法論（lifecycle / instant-review / acceptance-criteria / doc-flow）；保留 distinct 核心：Ticket vs worklog 定位、三大目標、Clean Architecture 設計哲學、TDD 對應、積極派發原則（服務精神權威處）。歷史 v1.0.0（48,438 tokens）~v2.1.0 完整版見 git log。
