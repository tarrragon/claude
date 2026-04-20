# Atomic Ticket 方法論

**版本**: v2.0.0
**建立日期**: 2025-12-25
**更新日期**: 2026-01-23
**核心原則**: 單一職責原則 (Single Responsibility Principle)

---

## 核心定義

### 什麼是 Atomic Ticket？

**Atomic Ticket** = 一個 Action + 一個 Target

```text
Atomic Ticket = 動詞 + 單一目標
```

**核心特徵**：
- **單一職責**：只有一個修改原因
- **獨立驗收**：可以獨立完成和驗收
- **不可再拆分**：拆分後會產生循環依賴

---

## Ticket 服務精神

> 理論依據：Will Guidara《Unreasonable Hospitality》

### 核心理念

**Service is black and white; hospitality is color.**

Ticket 不只是任務追蹤工具，而是為專案品質提供服務的載體。每一張 Ticket 都是一次服務機會，而非僅僅是待解決的問題。

### 心態轉變

| 舊思維 | 新思維 |
|--------|--------|
| Ticket = 解決問題的工具 | Ticket = 提供服務的載體 |
| 測試失敗 = 需要修復的錯誤 | 測試失敗 = 寶貴的學習機會（反饋文化） |
| 追求在單一 Ticket 完成所有任務 | 積極派發新 Ticket（即興款待） |
| 關注「問題是否解決」 | 關注「服務品質是否提升」 |
| 嚴格遵循原計劃 | 允許需求主導決策（認真但輕鬆） |

### 95/5 規則應用

> "Manage 95% down to the penny; spend the last 5% 'foolishly'."

- **95% 結構化執行**：遵循流程、格式、驗收條件、TDD 四階段
- **5% 創意探索**：研究性 Ticket、深入分析、學習記錄、改進提案

### 三大支柱

| 支柱 | 原則 | Ticket 實踐 |
|------|------|-------------|
| **保持臨在** | 放慢速度，專注傾聽 | 專注當前 Ticket，深入理解問題本質 |
| **認真但輕鬆** | 允許需求主導決策 | Ticket 可以調整方向，派發子 Ticket |
| **一對一量身** | 最好的服務是量身訂製 | 每個 Ticket 都是獨特的服務載體 |

### 持續改進文化

> "Excellence is the culmination of thousands of details executed perfectly."

- **每個 Ticket 完成都是改進機會**
- **小改進累積成卓越品質**
- **學習記錄不是可選，是必要**
- **測試失敗是反饋，不是懲罰**

### 反饋文化原則

| 原則 | Ticket 應用 |
|------|-------------|
| 批評行為而非個人 | 記錄「發生了什麼」而非「誰的錯」 |
| 私下而非公開 | 在 Ticket 內部討論，不公開指責 |
| 常態化以消除恐懼 | 讓失敗記錄成為正常流程的一部分 |

### Ticket 多元類型矩陣

| 類型 | 代碼 | 用途 | 典型時長 | 範例 |
|------|------|------|---------|------|
| Implementation | IMP | 開發新功能 | 1-4 小時 | 實作 SearchQuery 值物件 |
| Testing | TST | 執行測試驗證 | 30 分鐘-2 小時 | 執行 UC-01 區塊測試 |
| Adjustment | ADJ | 調整/修復問題 | 30 分鐘-2 小時 | 修復測試失敗 |
| Research | RES | 探索未知領域 | 1-2 小時 | 調查新技術可行性 |
| Analysis | ANA | 理解現狀和問題 | 30 分鐘-1 小時 | 分析測試失敗根因 |
| Investigation | INV | 深入追蹤問題根因 | 1-2 小時 | 追查效能瓶頸 |
| Documentation | DOC | 記錄和傳承經驗 | 30 分鐘-1 小時 | 整合方法論 |

### 行為分離原則

**開發、測試、調整三種行為必須分開追蹤**：

```
開發 (IMP) → 測試 (TST) → 調整 (ADJ)
                 ↓
              發現問題
                 ↓
           分析 (ANA) → 調整 (ADJ)
```

| 行為類型 | Ticket 類型 | 說明 |
|---------|-------------|------|
| 開發類 | IMP | 實作新功能、建立新元件 |
| 測試類 | TST | 執行測試、驗證功能 |
| 調整類 | ADJ | 修復問題、調整實作 |

**為什麼需要分離？**
- 測試是有後續狀況的需求，需要獨立追蹤
- 開發完成後的測試結果可能產生調整需求
- 完整追蹤鏈：開發 → 測試 → 調整

---

## 任務鏈核心哲學

> **核心命題**：Ticket 結構 = 任務鏈（Task Chain）。Ticket 不是孤立的任務單位，而是一張可移動的網格，支援責任與 context 在父子、兄弟之間無損傳遞。

### 為什麼採用「任務鏈」視角？

傳統待辦清單把 Ticket 視為獨立項目，完成即勾除。這種視角在以下場景失效：

| 場景 | 孤立視角的問題 | 任務鏈視角的處理 |
|------|--------------|----------------|
| 分析型 ANA Ticket 建議「後續建立 X」 | 父 ANA 完成 = 分析報告寫完 | 父責任由子 Ticket 的實作/驗證完成驗證 |
| Session 中斷需切換 context | 當前 Ticket context 散落在記憶中 | handoff 檔案 + append-log 持久化 context |
| 發現問題需開分支 Ticket | 新 Ticket 與原任務關聯遺失 | spawned_tickets / relatedTo / blockedBy 維持鏈 |

**任務鏈視角**：責任不止於當前 Ticket 的文件完成，而是鏈上所有節點都到達 completed/closed；context 不止於當前 session 的對話，而是持久化在 Ticket 結構和 handoff 檔案中。

### 結構：三種移動方向

任務鏈支援三種移動方向，對應不同的協作場景：

| 方向 | 關係 | 觸發情境 | 範例 |
|------|------|---------|------|
| **上移（子→父）** | 子任務完成返回父任務驗收 | 子任務履行父責任的一部分 | 實作完成後回到父 ANA 確認結論落地 |
| **下移（父→子）** | 父任務衍生子任務或切換到既有子任務 | 父被阻塞、父分派責任給子 | ANA Solution 項目拆為 IMP 子 Ticket |
| **水平（兄弟↔兄弟）** | 同父下的兄弟任務互相協調 | 並行/串行/互補/替代 | 多個 DOC 子任務協同完成一份方法論 |

**移動的具體實作**：建立關係欄位（parent_id/children/relatedTo/blockedBy）、handoff 命令（--to-parent/--to-child/--to-sibling），以及 chain 欄位自動計算。詳見本方法論後續「Ticket 關聯追蹤」章節（欄位語義）和「子任務建立指引」章節（CLI 操作與 chain 欄位）。

### 父子責任傳遞

**核心原則**：父 Ticket 的責任由子 Ticket 的完成來履行，而非父本身的文件完成。

| 概念 | 定義 |
|------|------|
| 父文件完成 | 父 Ticket 的 AC 欄位全部勾選、Problem Analysis 寫完 |
| 父責任履行 | 父的所有衍生子 Ticket（含遞迴孫層）全部 completed 或 closed |

**必然推論**：父 Ticket 的 complete 前置條件包含「所有子 Ticket 已 completed 或 closed」。父不可越過未完成的子任務獨立 complete。

> **執行規則**：父 complete 前置檢查的具體規則和 Hook 實作，見 `.claude/methodologies/ticket-lifecycle-management-methodology.md` 的「父 complete 前置條件」章節。

### Context 保留機制

任務鏈移動時，context 必須無損傳遞。本方法論定義三個協同機制：

| 機制 | 承載內容 | 生命週期 |
|------|---------|---------|
| **handoff 檔案** | 方向（to-parent/to-child/to-sibling）+ 前狀態 + 觸發摘要 | Session 間（跨 /clear） |
| **append-log 區段** | Problem Analysis / Solution / Test Results | Ticket 生命週期內持久化 |
| **chain 欄位** | root / parent / depth / sequence | 結構性恆存，隨 Ticket 檔案 |

三者協同保證：無論 PM 從哪個節點進入，都能重建「鏈在哪」、「鏈要去哪」、「鏈已走過什麼」的完整 context。

> **實作細節**：handoff 命令用法見 `.claude/skills/ticket/references/handoff-command.md`；append-log 區段定義和 chain 欄位自動計算方式見本方法論後續「子任務建立指引」章節。

### 任務鏈移動方向示範

下列任務鏈展示三種移動方向的協同運作（角色化命名，非特定專案實例）：

```
Ticket-Seed (IMP, 單點實作)
    ↓ 上移衍生（PM 驗收暴露規格缺口）
Ticket-Analysis-1 (ANA, 規格完整性分析)
    ↓ 上移衍生（單點分析揭示結構性問題）
Ticket-Analysis-Meta (ANA, Meta 層結構分析)
    ├─ Ticket-Meta.1 (ANA, 強制機制設計)
    ├─ Ticket-Meta.2 (DOC, 方法論補強)
    ├─ Ticket-Meta.3 (ANA, 系統審計)
    ├─ Ticket-Meta.4 (IMP, 前置檢查強化)
    └─ Ticket-Meta.5 (ANA, 設計指引前期先行)
    ↓ 水平衍生（理念層橫向延伸）
Ticket-Doc-Parent (DOC, 理念修正父任務)
    ├─ Ticket-Doc.1 (DOC, 核心哲學)
    ├─ Ticket-Doc.2 (DOC, 規則層補強)
    ├─ Ticket-Doc.3 (DOC, references 同步)
    ├─ Ticket-Doc.4 (DOC, 實務指南)
    └─ Ticket-Doc.5 (IMP, Hook 行為對齊)
```

**展示要點**：
- **上移**：Seed → Analysis-1 → Analysis-Meta，每步都是子節點發現問題後建立上層 ANA
- **下移**：Analysis-Meta 衍生 5 個子 ANA/DOC/IMP，責任分派到子層
- **水平**：Doc-Parent 透過 relatedTo 與 Analysis-Meta 產生橫向連結（理念修正源自 Meta ANA 過程）
- **父責任**：Doc-Parent 作為父 DOC，其 complete 前置依賴 5 個子 Ticket 全部 completed——本方法論章節完成即是其責任履行的一部分

---

## Ticket 關聯追蹤

### 關聯欄位定義

每個 Ticket 包含三個關聯欄位，用於追蹤 Ticket 之間的因果關係：

| 欄位 | 類型 | 說明 | 範例 |
|------|------|------|------|
| `source_ticket` | string | 觸發此 Ticket 的來源 | `{version}-W{n}-{seq}` |
| `spawned_tickets` | array | 此 Ticket 衍生的後續 Tickets | `["{version}-W{n}-{seq1}", "{version}-W{n}-{seq2}"]` |
| `dispatch_reason` | string | 派發原因和交接理由 | `UC-01 測試失敗，需修復 ImportService` |

### 關聯追蹤圖

```
[開發 Ticket (IMP)]
    |
    | spawned → [測試 Ticket (TST)]
    |               |
    |               | source ←
    |               |
    |               | 測試失敗
    |               |
    |               | spawned → [調整 Ticket (ADJ)]
    |                               |
    |                               | source ← dispatch_reason: "UC-01 測試失敗"
    v                               v
完成                              修復完成
```

### 關聯追蹤命令

```bash
# 查詢 Ticket 關聯鏈
uv run ticket track chain {version}-W2-001

# 添加衍生 Ticket
uv run ticket track spawn {version}-W2-001 {version}-W2-010 "測試失敗，需修復"
```

### 典型關聯鏈範例

**開發-測試-調整鏈**：

```yaml
# 開發 Ticket
id: {version}-W1-001
type: IMP
spawned_tickets: ["{version}-W1-002"]

# 測試 Ticket
id: {version}-W1-002
type: TST
source_ticket: "{version}-W1-001"
dispatch_reason: "開發完成，需執行區塊測試驗證"
spawned_tickets: ["{version}-W2-001"]

# 調整 Ticket
id: {version}-W2-001
type: ADJ
source_ticket: "{version}-W1-002"
dispatch_reason: "UC-01 測試失敗，需修復 ImportService"
```

---

## 單一職責評估方式

### 評估原則（四大檢查）

**單一職責是唯一的評估標準**。以下四個檢查方式用於判斷是否符合單一職責：

### 1. 語義檢查

**問題**：Ticket 能用「動詞 + 單一目標」表達嗎？

**符合單一職責** ✅：
```text
實作 startScan() 方法
修復 ISBN 驗證邏輯
新增 BookRepository.save() 測試
重構 SearchService 的錯誤處理
```

**違反單一職責** ❌：
```text
實作 ISBNScannerService 的掃描功能和離線支援  ← 兩個目標
修復 ISBN 驗證和優化效能  ← 兩個行動
新增 BookRepository 的所有測試  ← 多個目標
```

### 2. 修改原因檢查

**問題**：只有一個原因會導致這個 Ticket 需要修改嗎？

**符合單一職責** ✅：
```text
Ticket: 實作 startScan() 方法
修改原因: 只有「掃描 API 變更」會影響
→ 單一修改原因 ✅
```

**違反單一職責** ❌：
```text
Ticket: 實作掃描功能和離線支援
修改原因 1: 掃描 API 變更
修改原因 2: 離線儲存格式變更
→ 多個修改原因 ❌ → 應拆分
```

### 3. 驗收條件一致性

**問題**：所有驗收條件都指向同一個目標嗎？

**符合單一職責** ✅：
```yaml
ticket: 實作 startScan() 方法
acceptance:
  - startScan() 方法簽名正確
  - startScan() 回傳值類型正確
  - startScan() 單元測試通過
# 所有驗收條件都是關於 startScan() ✅
```

**違反單一職責** ❌：
```yaml
ticket: 實作掃描功能
acceptance:
  - startScan() 方法通過測試
  - stopScan() 方法通過測試
  - 離線快取功能正常
  - 批次掃描模式可用
# 驗收條件指向多個不同目標 ❌ → 應拆分
```

### 4. 依賴獨立性檢查

**問題**：如果拆成兩個 Ticket，它們是否有循環依賴？

**可以拆分** ✅（無循環依賴）：
```text
Ticket A: 實作 startScan()
Ticket B: 實作 stopScan()
依賴關係: B 依賴 A（單向）
→ 獨立 ✅ → 應拆分為兩個 Ticket
```

**不應拆分** ❌（有循環依賴）：
```text
Ticket A: 實作掃描啟動邏輯
Ticket B: 實作掃描狀態管理
依賴關係: A 需要 B 的狀態，B 需要 A 的啟動
→ 循環依賴 ❌ → 應該是同一個 Ticket
```

---

## 禁止使用的評估方式

**以下指標不能作為單一職責的判斷依據**：

| 指標 | 為什麼不使用 |
|------|-------------|
| **時間**（30 分鐘、1 小時） | 時間是結果，不是原因。單一職責的任務可能需要 5 分鐘或 2 小時 |
| **程式碼行數**（50 行、100 行） | 行數是實作細節。單一職責可能只需 10 行或需要 200 行 |
| **檔案數量**（2 個、5 個） | 檔案數量是組織方式。單一職責可能跨多個檔案 |
| **測試數量**（5 個、10 個） | 測試數量取決於邊界情況，不是職責數量 |

**正確做法**：只用「單一職責四大檢查」來評估

---

## Ticket ID 命名規範

### 格式

```text
根任務:   {Version}-W{Wave}-{Seq}
子任務:   {根ID}.{n}[.{n}...]
```

**範例**：
- `{version}-W1-001` - Wave 1, 第 1 個（根任務）
- `{version}-W2-003` - Wave 2, 第 3 個（根任務）
- `{version}-W3-002.1` - {version}-W3-002 的第 1 個子任務
- `{version}-W3-002.1.1` - {version}-W3-002.1 的第 1 個子任務

### 命名規則

| 部分 | 說明 | 範例 |
|------|------|------|
| Version | 所屬版本號 | 0.15.16 |
| Wave | 執行波次（依賴層級） | W1, W2, W3 |
| Seq | 波次內序號（三位數） | 001, 002, 015 |
| .{n} | 子任務序號（可無限巢狀） | .1, .2, .1.1 |

### Wave 定義

- **W1**: 無依賴，可並行執行
- **W2**: 依賴 W1 的部分 Ticket
- **W3**: 依賴 W2 的部分 Ticket
- ...以此類推

---

## 子任務建立指引

### 何時建立子任務

| 情境 | 說明 | 範例 |
|------|------|------|
| TDD 階段任務 | 一個功能的各階段（Phase 0-4） | 根任務為功能，子任務為各 Phase |
| 問題衍生修復 | 執行中發現的問題需要另開任務 | 測試失敗產生的修復子任務 |
| 功能細分 | 主功能拆分為多個獨立元件 | 主功能為根，各元件為子任務 |
| 阻塞處理 | 父任務被阻塞，產生解除阻塞的子任務 | 依賴問題的解決子任務 |

### 建立方式

**CLI 方式**：
```bash
# 建立 {version}-W3-002 的第一個子任務（自動分配序號）
uv run ticket create \
  --version 0.31.0 --wave 3 \
  --parent {version}-W3-002 \
  --action "實作" \
  --target "chain_analyzer.py" \
  --who "thyme-python-developer"
```

**SKILL 方式**：
```
/ticket create --parent {version}-W3-002
```

### 命名規則

- **序號自動分配**：取父任務下最大序號 + 1
- **從 1 開始**：`.1`, `.2`, `.3`...
- **支援無限深度**：`.1.1`, `.1.1.1`...

### chain 欄位自動計算

建立子任務時，系統自動計算 chain 欄位：

| 欄位 | 計算方式 |
|------|---------|
| root | 任務鏈的根任務 ID |
| parent | 直接父任務 ID |
| depth | 根任務 depth=0，每層 +1 |
| sequence | 從根任務到當前任務的序號路徑 |

### 範例任務鏈

```
{version}-W3-002              # ticket-handoff 功能（根，depth=0）
├── {version}-W3-002.1        # chain_analyzer 模組（depth=1）
│   ├── {version}-W3-002.1.1  # 問題修復（depth=2）
│   └── {version}-W3-002.1.2  # 測試補充（depth=2）
├── {version}-W3-002.2        # handoff_executor 模組（depth=1）
└── {version}-W3-002.3        # 文件更新（depth=1）
```

### 兄弟任務關聯模式

> **原則**：同父下的兄弟任務之間**預設平行無依賴**。有依賴關係時，依賴者應下沉一層或重組為聚合父結構。單向時序依賴在嚴格條件下可保留（見下方「串行兄弟」）。見 error-pattern `ARCH-017: 兄弟任務隱藏依賴`。

同層兄弟的四種協調模式：

| 模式 | 特徵 | 適用場景 |
|------|------|---------|
| **並行** | 兄弟彼此獨立，可同時派發 | 多個不相交功能的實作（推薦） |
| **串行** | 兄弟間有單向時序依賴（顯式 `blockedBy`） | 規格→實作、方法論→Hook 對齊（需滿足 4 條件） |
| **互補** | 兄弟職責互補，合起來完成一個大目標 | 正反測試（正常流程 + 邊界情況） |
| **替代** | 兄弟是不同方案，擇一採用 | A/B 方案並行探索，決策後關閉另一方 |

**串行兄弟合法 4 條件**（須全滿足，否則回歸 ARCH-017 重組）：

1. **單向**：A → B，B 不依賴 A 以外的兄弟
2. **無環**：兄弟依賴形成 DAG
3. **規格→實作時序**：A 為規格/介面/方法論，B 為實作/驗證/Hook（非內容面向並列）
4. **不可深度化**：B 若成為 A 的子會違反內容邊界（如 Hook 不是方法論的子章節）

**違反原則的訊號**：
- 兄弟 A 的 `relatedTo` 或文件中引用兄弟 B 的產物 → B 應為 A 的父
- 兄弟 A 的 `blockedBy` 含多個兄弟 → 應作為聚合父的最後一個子（或下一 Wave）
- 執行時必須照特定順序不能並行、但不滿足串行 4 條件 → 依賴關係應升格為父子結構

### 兄弟-父銜接關係

父 Ticket 的責任由所有子 Ticket 的完成來履行。兄弟完成時的銜接規則：

| 情境 | 處理方式 |
|------|---------|
| 所有兄弟皆 completed/closed | 父可 complete（見 `ticket-lifecycle-management-methodology.md` 父 complete 前置條件） |
| 部分兄弟 completed，其餘 in_progress/pending | 父**保持 in_progress**，不可 complete |
| 某兄弟執行中發現新需求 | 建立新 spawned ticket（可為兄弟層級或子層級），不擴大當前兄弟的 scope |
| 某兄弟執行結論改變父目標 | 透過 append-log 記錄到父 Problem Analysis；若父需重新拆分，建立新 Ticket |

**禁止行為**：父越過未完成兄弟獨立 complete（違反 `atomic-ticket-methodology.md` 父子責任傳遞）。

### 多層嵌套指南

任務鏈支援無限深度（`.1`, `.1.1`, `.1.1.1` ...），但深度應反映依賴結構，非任意分層。

| 深度 | 建議 |
|------|------|
| 1 層（根 + 直接子） | 標準情況，多數拆分足以處理 |
| 2 層（含孫層） | 孫層代表「某個子任務內部的子任務」，常見於 Phase 拆分 |
| 3 層（含曾孫） | **軟上限**，超過時考慮以 Wave 分離（跨版本序列）替代 |
| > 3 層 | 反模式，常見於過度拆分，應重新評估 Ticket 粒度 |

**何時建立 grandchildren（.1.1.1）**：

| 情境 | 建議 |
|------|------|
| 子任務 .1.1 執行中發現新子問題 | 建立 .1.1.1 作為 spawned child |
| 子任務 .1.1 的 TDD 需細分 Phase | 各 Phase 作為 .1.1.1, .1.1.2, ... |
| 預先規劃就拆成三層 | 通常過度設計，先建兩層執行看狀況 |

**反模式**：將同責任的內部步驟拆為 grandchildren（如「建構式簽名」「建構式邏輯」「建構式驗證」分為 .1.1.1/.1.1.2/.1.1.3）。這違反 atomic 原則，應保持為單一 Ticket。

### 任務拆分決策樹

拆分父任務時，依序判斷：

```
拆分父任務
    |
    v
Q1: 子任務彼此是否真的獨立（可同時執行）？
    |
    +-- 是 → 平行兄弟（無 blockedBy 依賴）
    |
    +-- 否 → Q2
         |
         v
Q2: 依賴方向是否單向（A 被 B/C/... 依賴，A 是 hub）？
    |
    +-- 是 → 將 hub 與被依賴者包為聚合父（見下方聚合父重組範式）
    |
    +-- 否（依賴關係複雜） → Q3
         |
         v
Q3: 是否需要跨版本序列（Wave 分層）？
    |
    +-- 是 → 將依賴者放入下一個 Wave，不同時執行
    |
    +-- 否 → 重新檢視：可能是同一責任誤拆，應合併
```

**不應拆分的情境**（保持為單一 Ticket）：

- 同一責任的內部步驟（實作 vs 簽名 vs 驗證）
- 拆分會產生循環依賴（見本方法論「單一職責評估 — 依賴獨立性檢查」）
- 拆分後任一子無法獨立驗收

### 聚合父重組範式

某父任務最初設計為 5 平行兄弟（.1/.2/.3/.4/.5），但 .2/.3/.5 都 relatedTo .1 哲學章節，.4 blockedBy 其他 4 個——違反兄弟無依賴原則。重組過程：

```
重組前（反例，5 平行兄弟含隱藏依賴）：
Parent
├── .1 哲學 (hub)
├── .2 規則 (relatedTo .1)
├── .3 references (relatedTo .1)
├── .4 Hook (blockedBy .1/.2/.3/.5)
└── .5 實務指南 (relatedTo .1)

重組後（正例，2 平行兄弟 + 聚合父）：
Parent
├── .1（聚合父）方法論組
│   ├── .1.1 (hub, 哲學)
│   ├── .1.2 (規則, 引用 .1.1)
│   ├── .1.3 (references, 引用 .1.1)
│   └── .1.4 (實務指南, 引用 .1.1)
└── .2 (Hook, blockedBy .1)
```

要點：
- 兄弟層從 5 個依賴纏繞 → 2 個清晰（方法論組 vs Hook 實作）
- .1 聚合父表達內部依賴（.1.1 hub + .1.2/.1.3/.1.4 引用者）
- .1.2/.1.3/.1.4 彼此不依賴，可並行（符合 Q1 → 平行兄弟）
- 重組由 `ticket migrate` 指令執行，需配合 frontmatter 驗證（見 `IMP-061`）

---

## 5W1H 驅動的 Ticket 欄位

每個 Ticket 的 YAML 欄位對應 5W1H 問題：

| 5W1H | 欄位 | 說明 |
|------|------|------|
| Who | `who.current` + `who.history` | 當前負責代理人 + Phase 歷史 |
| What | `what` | 任務目標（動詞 + 單一目標） |
| When | `when` | 觸發時機 |
| Where | `where.layer` + `where.files` | 架構層級 + 影響檔案 |
| Why | `why` | 需求依據 |
| How | `how.task_type` + `how.strategy` | Task Type + 實作策略 |

### where.files 撰寫指引：拆分檔案配對

#### 背景：骨架與實質內容的拆分架構

本專案的 `.claude/` 規則目錄採用「骨架（索引）+ 實質內容（詳版）」雙檔拆分架構（自 W10-076.1 落地）：

- **骨架**（auto-load）：`rules/core/X.md`、`pm-rules/X.md` — 每次 session 自動載入，只含觸發指標、摘要、索引表
- **實質內容**（按需讀取）：`references/X.md`、`references/X-details.md` — 詳細規則、範例、深度說明

骨架第一行通常包含「完整規則：references/X.md（按需讀取）」的明示引用，表示規則實質內容落在 references 端。

**Why**: 骨架只是索引——骨架的存在承諾讀者「內容看 references/」，因此擴充規則內容必然牽動 references/，而非骨架本身。忽略此結構會導致 ticket where.files 僅列骨架，但 agent 實際修改 references/ 而產生範圍漂移。

#### 規則 1：列「實質修改會發生的位置」

PM 撰寫 where.files 時的核心問題：「此 ticket 的修改本質是改變規則『入口索引』還是『規則本身的內容』？」

| 修改類型 | where.files 列法 | 判別問題 |
|---------|-----------------|---------|
| 骨架索引變更（版本號、索引表、導航連結） | 只列骨架路徑 | 「只改入口，不動內容」 |
| 實質內容擴充（新增規則、修改規則細節） | 列 references/ 實質檔路徑 | 「改的是規則內容本身」 |
| 同步變更（索引表更新 + 規則細節同步） | 兩者都列 | 「入口和內容都要動」 |

**Consequence**: 僅列骨架時，agent 必須自裁決定是否延伸到 references/，有範圍漂移風險且缺乏明示記錄。

#### 規則 2：PM 撰寫 where.files 前的拆分偵測

列 where.files 時，若看到路徑包含 `rules/core/` 或 `pm-rules/`，必須檢查是否存在對應的 references/ 拆分配對：

```bash
# 偵測配對的快速指令
for path in $(echo "$where_files" | grep -E "(rules/core|pm-rules)/"); do
  basename=$(basename "$path" .md)
  find .claude/references -name "${basename}*.md"
done
```

**本專案已知 10+ 組拆分對**（任何修改這些規則內容的 ticket 都有 where.files 漂移風險）：

| 骨架（auto-load） | 實質內容（按需讀取） | 拆分類型 |
|-----------------|-------------------|---------|
| rules/core/quality-common.md | references/quality-common.md | 同名 |
| rules/core/bash-tool-usage-rules.md | references/bash-tool-usage-details.md | -details |
| pm-rules/askuserquestion-rules.md | references/askuserquestion-scene-details.md | -details |
| pm-rules/decision-tree.md | references/decision-tree-checkpoint-details.md | -details |
| pm-rules/incident-response.md | references/incident-response-details.md | -details |
| pm-rules/parallel-dispatch.md | references/parallel-dispatch-details.md | -details |
| pm-rules/tdd-flow.md | references/tdd-flow-details.md | -details |
| pm-rules/verification-framework.md | references/verification-framework-details.md | -details |
| pm-rules/version-progression.md | references/version-progression-details.md | -details |
| pm-rules/plan-to-ticket-flow.md | references/plan-to-ticket-details.md + references/plan-to-ticket-mapping-details.md | 1-to-many |

> 本規則適用於所有涉及上表拆分對的 ticket，不限於 quality-common。新增規則檔案後，應同步維護上表。

#### 規則 3：Agent 延伸 where.files 外檔的行為規範

Agent 若發現實際修改必須延伸到 where.files 未列的檔案（例如骨架-references 拆分配對的另一邊）：

| 情境 | 允許行為 |
|------|---------|
| 延伸符合 ticket 意圖（規則實質內容落在 references/） | 允許延伸，必須 append-log 記錄：「延伸至 X.md，原因：[理由]」 |
| 延伸超出 ticket 意圖（新增無關模組、修改非配對檔） | 禁止延伸，停止並回報 PM |

**預設禁止默默擴展未記錄**。

**Action**: Agent 每次觸發「延伸符合意圖」時，立即在 Solution 章節寫一行：`延伸至 [path]，原因：[骨架第 N 行明示引用此 references/]`。

#### 正反案例

**反例**（W10-011 事件）：

```yaml
# ticket where.files 僅列骨架
where:
  files:
    - .claude/rules/core/quality-common.md   # 骨架，auto-load 索引
    # 遺漏 references/quality-common.md      # 實質內容在此
```

問題：agent 必須自裁決定是否延伸到 references/；延伸後未在 ticket 記錄，PM 驗收時無法追蹤實際修改範圍。

**正例 A**（修改規則內容時同步列兩者）：

```yaml
where:
  files:
    - .claude/rules/core/quality-common.md   # 骨架（若索引表需更新）
    - .claude/references/quality-common.md   # 實質內容（規則細節擴充）
```

**正例 B**（僅修改規則細節，不動骨架索引）：

```yaml
where:
  files:
    - .claude/references/quality-common.md   # 只列實質檔，骨架不需改
```

### Ticket YAML 格式

```yaml
---
id: {version}-W1-001
title: "實作 SearchQuery 值物件"
type: IMP
status: pending

version: 0.29.1
priority: P1

parent_id: null
children: []
blockedBy: []

who:
  current: parsley-flutter-developer
  history:
    phase1: lavender-interface-designer
    phase2: sage-test-architect
what: "實作 SearchQuery 值物件"
when: "Phase 3b 開始時"
where:
  layer: Domain
  files:
    - lib/features/book/domain/entities/search_query.dart
why: "支援書籍搜尋功能"
how:
  task_type: Implementation
  strategy: "TDD 循環"

created: 2026-01-23
updated: 2026-01-23
---
```

---

## 版本驅動任務管理

### 版本號分配原則

| 情況 | 版本分配 | 執行方式 |
|------|---------|---------|
| 無依賴任務 | 同小版本 | 可並行執行 |
| 有依賴任務 | 不同小版本 | 序列執行 |
| 技術債務 | 專用小版本或下個中版本 | 視優先級 |

### 版本號層級

```text
v1.0.0（大版本）
├── v0.29.0（中版本）- Feature 級別
│   ├── v0.29.1（小版本）- 無依賴 Tickets
│   ├── v0.29.2（小版本）- 依賴 v0.29.1
│   └── v0.29.3（小版本）- 技術債務
└── ...
```

### 拆分工具

使用 `/tdd-phase1-split` 在 Phase 1 進行 SOLID 原則驅動的拆分：

```bash
uv run .claude/skills/tdd-phase1-split/scripts/tdd-phase1-split.py suggest \
  --description "實作書籍搜尋功能" \
  --version 0.29.0
```

---

## 拆分範例

### 範例 1：功能拆分

**原始需求**：
```text
實作 ISBNScannerService 的 15 個測試
```

**違反單一職責**：一個 Ticket 包含 15 個不同的測試目標

**正確拆分**（每個 Ticket 只有一個目標）：
```text
{version}-W1-001: 實作 startScan() 方法
{version}-W1-002: 實作 stopScan() 方法
{version}-W1-003: 實作 validateIsbn10() 驗證邏輯
{version}-W1-004: 實作 validateIsbn13() 驗證邏輯
{version}-W2-005: 實作離線掃描支援（依賴 W1）
{version}-W2-006: 實作批次掃描模式（依賴 W1）
...
```

### 範例 2：測試拆分

**原始需求**：
```text
修復 Exception 序列化的 10 個測試
```

**正確拆分**：
```text
{version}-W1-001: 修復 ValidationException.toJson() 序列化
{version}-W1-002: 修復 AppException.toJson() 序列化
{version}-W1-003: 修復 CommonErrors 效能測試
{version}-W2-004: 修復 AppException.wrap() 工廠方法（依賴 {version}-W1-002）
...
```

### 範例 3：反例 - 不應拆分

**需求**：
```text
實作 BookRepository.save() 方法
```

**不應拆分的情況**：
```text
Ticket A: 實作 save() 方法簽名
Ticket B: 實作 save() 方法邏輯
Ticket C: 實作 save() 方法驗證
```

**原因**：這三個部分有循環依賴，簽名、邏輯、驗證是同一個職責的不同面向

**正確做法**：保持為單一 Ticket
```text
{version}-W1-001: 實作 BookRepository.save() 方法
```

---

## 與其他方法論的關係

### 與 ticket-design-dispatch-methodology.md 的關係

**Atomic Ticket 方法論**是 Ticket 設計的核心原則，ticket-design-dispatch-methodology.md 應引用本方法論作為拆分標準。

### 與 frontmatter-ticket-tracking-methodology.md 的關係

**Atomic Ticket** 產生的 YAML Frontmatter 定義是唯一事實源，Frontmatter 內建在 Ticket 檔案中追蹤狀態。

### 與 ticket-lifecycle-management-methodology.md 的關係

每個 **Atomic Ticket** 都遵循相同的生命週期：待執行 → 進行中 → Review → 完成

---

## 檢查清單

### 建立 Ticket 前的檢查

- [ ] **語義檢查**：能用「動詞 + 單一目標」表達嗎？
- [ ] **修改原因**：只有一個修改原因嗎？
- [ ] **驗收一致性**：所有驗收條件指向同一目標嗎？
- [ ] **依賴獨立性**：拆分後不會產生循環依賴嗎？

### 常見違反模式

| 模式 | 問題 | 修正 |
|------|------|------|
| 「實作 X 和 Y」 | 兩個目標 | 拆成兩個 Ticket |
| 「修復所有 X 測試」 | 多個測試目標 | 每個測試一個 Ticket |
| 「重構 X 並優化 Y」 | 兩個行動 | 拆成兩個 Ticket |
| 「建立 X 的完整功能」 | 模糊目標 | 明確列出每個功能 |

---

## 參考文件

- [Ticket 設計派工方法論](./ticket-design-dispatch-methodology.md)
- [Ticket 生命週期管理方法論](./ticket-lifecycle-management-methodology.md)
- [Frontmatter Ticket 追蹤方法論](./frontmatter-ticket-tracking-methodology.md)

---

*版本歷史*：
- v2.2.0 (2026-01-29): 新增「子任務建立指引」章節，支援任務鏈 ID 格式（如 {version}-W3-002.1.1）
- v2.1.0 (2026-01-28): 擴展 Ticket 類型（新增 TST/ADJ）、新增「Ticket 關聯追蹤」章節、新增「行為分離原則」
- v2.0.0 (2026-01-23): 加入 5W1H 欄位、版本驅動任務管理
- v1.1.0 (2026-01-14): 新增「Ticket 服務精神」章節，整合《Unreasonable Hospitality》核心原則
- v1.0.0 (2025-12-25): 初版，基於單一職責原則設計
