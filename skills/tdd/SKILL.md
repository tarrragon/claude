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

### 用途

初始化一個新功能的 TDD 流程，確認從哪個 Phase 開始。

### 執行步驟

1. 描述功能需求（一句話）
2. 評估是否需要 Phase 0（SA 前置審查）
3. 確認 TDD 起點
4. 輸出此功能的 TDD 路線圖

### Phase 0 觸發評估

回答以下問題（任一「是」→ 需要 Phase 0）：

| 問題 | 答案 |
|------|------|
| 這是新功能（非 Bug 修復）？ | 是 / 否 |
| 影響 3 個以上模組？ | 是 / 否 |
| 需要架構層級變更？ | 是 / 否 |

### 任務類型豁免判斷

判斷是否為遷移任務（可簡化 TDD 流程）：

| 識別標準 | 說明 |
|---------|------|
| 主要工作是「轉換」而非「建立新業務邏輯」 | 例如：格式轉換、資料遷移 |
| 輸出可完全由輸入推導（無新業務規則） | 機械性轉換 |
| 現有測試或驗證步驟已足夠確認正確性 | 可驗證轉換結果 |

遷移任務豁免表：

| Phase | 遷移任務是否豁免 | 說明 |
|-------|-----------------|------|
| Phase 0 | 可豁免 | 純轉換無架構影響 |
| Phase 1 | 可簡化 | 只需確認輸入/輸出規格 |
| Phase 2 | 可簡化 | 驗證轉換正確性即可 |
| Phase 3a | 可簡化 | 無策略規劃需求 |
| Phase 3b | 必須執行 | 實際完成轉換 |
| Phase 4 | 可豁免 | 純轉換無重構需求 |

**禁止**：以「遷移任務」理由跳過結果驗證。

> **框架整合**：在本框架中，遷移任務豁免需在 Ticket 的 `tdd_stage` 欄位標記跳過的 Phase。

### 輸出

```
[TDD Start] 功能：{功能描述}

評估結果：
- 任務類型：標準新功能 / 遷移任務
- 起始 Phase：Phase {N}
- 預計 Phase 路線：{路線}

TDD 路線圖：
Phase 0 → Phase 1 → Phase 2 → Phase 3a → 3b 拆分評估 → Phase 3b → Phase 4a → Phase 4b → Phase 4c

執行 /tdd status 查看當前狀態
```

---

## `/tdd next` - 推進到下一個 Phase

### 用途

在當前 Phase 完成後，確認轉換條件並推進。

### 轉換條件檢查表

| 當前 Phase | 進入下一 Phase 的條件 |
|-----------|---------------------|
| Phase 0 | 架構一致性確認、無重複實作、需求文件完整 |
| Phase 1 | 功能規格完整、API 介面定義完成、驗收標準明確 |
| Phase 2 | 測試案例覆蓋正常/異常/邊界情境、GWT 格式規格化 |
| Phase 3a | 實作策略文件完成、認知負擔評估完成 |
| 3b 拆分評估 | PM 完成拆分或豁免決策 |
| Phase 3b | 所有測試通過（100%）、程式碼品質達標 |
| Phase 4a | 多維度分析報告完成 |
| Phase 4b | 重構執行完成、技術債務記錄完成 |
| Phase 4c | 再審核報告完成 |

### 執行

確認當前 Phase 轉換條件後，執行轉換。

> **框架整合**：執行 `/ticket track complete {id}` 標記當前 Phase Ticket 完成。Phase 1/2/3a 由執行者自行提交（git commit）。

---

## `/tdd split` - Phase 1 SOLID 拆分分析

### 用途

在 Phase 1 設計階段，使用 SOLID 原則分析功能需求，產出拆分建議。

**核心理念**：Phase 1 就要考慮 DIP/LSP/ISP，才能實踐 SRP/OCP。拆分時機是 Phase 1，不是 Phase 3a。

### 步驟 1：功能範圍分析

輸入功能需求，識別：

```
功能需求描述
    |
    +-- 輸入是什麼？
    +-- 輸出是什麼？
    +-- 涉及哪些實體？
    +-- 需要哪些操作？
```

### 步驟 2：SOLID 原則逐項檢查

| 原則 | 檢查問題 | 拆分信號 |
|------|---------|---------|
| SRP | 這個功能有幾個獨立的修改原因？能用「動詞 + 單一目標」描述嗎？ | 有 2+ 個修改原因；需要用「和」連接描述 |
| OCP | 未來擴展需要修改現有程式碼嗎？有沒有可以抽象的變化點？ | 需要 switch/case 處理不同類型；新增類型需修改既有程式碼 |
| LSP | 有繼承關係嗎？子類別能完全替換父類別嗎？ | 子類別需覆寫並改變父類別行為；某些方法在子類別中沒有意義 |
| ISP | 介面是否強迫實作不需要的方法？一個介面服務多少個不同客戶端？ | 實作類別有空方法；不同客戶端只使用介面的一部分 |
| DIP | 高層模組是否依賴低層模組？依賴的是抽象還是具體實作？ | 直接 import 具體類別；無法獨立測試 |

### 步驟 3：拆分決策

```
根據 SOLID 分析
    |
    +-- 識別獨立職責 → 各自一個任務
    +-- 識別需要的介面 → 介面定義任務
    +-- 識別依賴關係 → 決定執行順序
```

### 步驟 4：執行順序分配

| 依賴關係 | 執行順序 | 說明 |
|---------|---------|------|
| 無依賴任務 | 第一批（可並行） | Domain Entities、Value Objects |
| 依賴第一批 | 第二批 | Use Cases、Application Services |
| 依賴第二批 | 第三批 | UI Widget、Presentation |

### 拆分報告格式

```markdown
## Phase 1 拆分報告

### 原始需求
- 描述：{需求描述}
- 預估複雜度：高 / 中 / 低

### SOLID 分析

| 原則 | 分析結果 | 拆分建議 |
|------|---------|---------|
| SRP | {結果} | {建議} |
| OCP | {結果} | {建議} |
| LSP | {結果} | {建議} |
| ISP | {結果} | {建議} |
| DIP | {結果} | {建議} |

### 拆分清單

| 編號 | 描述 | 架構層 | 執行批次 | 依賴 |
|------|------|--------|---------|------|
| A | {描述} | Domain | 第一批 | 無 |
| B | {描述} | Application | 第二批 | A |

### 執行計畫
1. 第一批（可並行）：A、B、C
2. 第二批（序列）：D（依賴 A、B）
3. 第三批（序列）：E（依賴 D）
```

**範例**（書籍搜尋功能）：詳見 `references/phase1-design.md`

> **框架整合**：使用 `/ticket create --parent {parent_id}` 建立子 Ticket，依賴關係以 `blockedBy` 欄位標記。

---

## `/tdd status` - 查看當前進度

### 用途

確認目前所在 TDD 階段、完成情況、下一步行動。

### 輸出格式

```
[TDD Status] 功能：{功能描述}

當前 Phase：Phase {N} - {Phase 名稱}
階段目標：{本 Phase 要完成什麼}

轉換條件檢查：
- [x] {已完成條件}
- [ ] {待完成條件}

建議行動：
- {下一步動作}

完整路線圖：
[完成] Phase 0 → [完成] Phase 1 → [進行中] Phase 2 → Phase 3a → ...
```

---

## `/tdd phase4-exempt` - Phase 4 豁免評估

### 用途

Phase 3b 完成後，評估是否符合 Phase 4 豁免條件（跳過 4a/4c，直接執行 4b）。

### 豁免條件（任一符合即可簡化）

| 條件 | 說明 |
|------|------|
| 修改 <= 2 個檔案 | 影響範圍有限，多視角分析成本大於收益 |
| 純文件任務 | 不涉及程式碼品質 |
| 任務範圍單純 | 單一模組、修改目的明確 |

### 豁免後的流程

```
符合豁免條件
    |
    v
直接進入 Phase 4b（重構執行）
    |
    v
Phase 4b 完成後 → 記錄技術債務 → 完成
（跳過 Phase 4a 多視角分析 和 Phase 4c 再審核）
```

### 不符合豁免

```
不符合豁免條件
    |
    v
Phase 4a：多維度交叉審查（冗餘 / 耦合 / 複雜度）
    |
    v
Phase 4b：按分析報告執行重構
    |
    v
Phase 4c：再審核（可重用性 / 品質水準 / 效率）
```

> **框架整合**：Phase 4a 使用 `/parallel-evaluation B（Redundancy/Coupling/Complexity）`，Phase 4c 使用 `/parallel-evaluation A（Reuse/Quality/Efficiency）`。

---

## 3b 拆分評估（Phase 3a 完成後強制執行）

Phase 3a 策略文件完成後，必須評估 Phase 3b 是否需要拆分為多個並行子任務。

### 拆分觸發條件（任一符合）

| 指標 | 閾值 | 說明 |
|------|------|------|
| 預期修改檔案數 | > 5 個 | 必須拆分 |
| 認知負擔指數 | > 10 | 必須拆分 |
| 跨架構層級數 | > 2 層 | 必須拆分 |
| 策略文件的獨立模組數 | > 1 且無交叉依賴 | 建議拆分 |

### 認知負擔指數計算

```
認知負擔指數 = 變數數 + 分支數 + 巢狀深度 + 依賴數
```

| 指數 | 評估 | 行動 |
|------|------|------|
| 1-5 | 優良 | 不拆分 |
| 6-10 | 可接受 | 不拆分 |
| 11-15 | 需重構 | 建議拆分 |
| > 15 | 必須重構 | 必須拆分 |

### 拆分豁免條件（任一符合即不拆分）

| 條件 | 說明 |
|------|------|
| 修改 <= 5 個檔案 | 影響範圍有限，單一執行者可負責 |
| 單一模組內修改 | 無跨模組衝突風險 |
| 修改目的單一明確 | 低複雜度，無需拆分 |

> **框架整合**：拆分時建立子任務（`/ticket create --parent {3b_ticket_id}`），每個子任務指定修改檔案清單（`where.files`），確保無交集，然後並行派發執行者。

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

- TDD 流程規則：`.claude/rules/flows/tdd-flow.md`
- 任務拆分指南：`.claude/rules/guides/task-splitting.md`
- 並行派發指南：`.claude/rules/guides/parallel-dispatch.md`
- 認知負擔原則：`.claude/rules/core/cognitive-load.md`

---

**Last Updated**: 2026-03-12
**Version**: 1.1.0 - 整合 tdd-phase1-split 內容：新增 phase1-split-methodology.md 和 CLI 腳本（0.1.0-W44-001.6）
**Specialization**: TDD 全流程指導（Phase 0-4）
