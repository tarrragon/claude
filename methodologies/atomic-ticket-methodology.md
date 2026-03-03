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

## Ticket 關聯追蹤

### 關聯欄位定義

每個 Ticket 包含三個關聯欄位，用於追蹤 Ticket 之間的因果關係：

| 欄位 | 類型 | 說明 | 範例 |
|------|------|------|------|
| `source_ticket` | string | 觸發此 Ticket 的來源 | `0.31.0-W2-001` |
| `spawned_tickets` | array | 此 Ticket 衍生的後續 Tickets | `["0.31.0-W2-010", "0.31.0-W2-011"]` |
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
uv run ticket track chain 0.31.0-W2-001

# 添加衍生 Ticket
uv run ticket track spawn 0.31.0-W2-001 0.31.0-W2-010 "測試失敗，需修復"
```

### 典型關聯鏈範例

**開發-測試-調整鏈**：

```yaml
# 開發 Ticket
id: 0.31.0-W1-001
type: IMP
spawned_tickets: ["0.31.0-W1-002"]

# 測試 Ticket
id: 0.31.0-W1-002
type: TST
source_ticket: "0.31.0-W1-001"
dispatch_reason: "開發完成，需執行區塊測試驗證"
spawned_tickets: ["0.31.0-W2-001"]

# 調整 Ticket
id: 0.31.0-W2-001
type: ADJ
source_ticket: "0.31.0-W1-002"
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
- `0.15.16-W1-001` - v0.15.16, Wave 1, 第 1 個（根任務）
- `0.15.16-W2-003` - v0.15.16, Wave 2, 第 3 個（根任務）
- `0.31.0-W3-002.1` - 0.31.0-W3-002 的第 1 個子任務
- `0.31.0-W3-002.1.1` - 0.31.0-W3-002.1 的第 1 個子任務

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
# 建立 0.31.0-W3-002 的第一個子任務（自動分配序號）
uv run ticket create \
  --version 0.31.0 --wave 3 \
  --parent 0.31.0-W3-002 \
  --action "實作" \
  --target "chain_analyzer.py" \
  --who "thyme-python-developer"
```

**SKILL 方式**：
```
/ticket create --parent 0.31.0-W3-002
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
0.31.0-W3-002              # ticket-handoff 功能（根，depth=0）
├── 0.31.0-W3-002.1        # chain_analyzer 模組（depth=1）
│   ├── 0.31.0-W3-002.1.1  # 問題修復（depth=2）
│   └── 0.31.0-W3-002.1.2  # 測試補充（depth=2）
├── 0.31.0-W3-002.2        # handoff_executor 模組（depth=1）
└── 0.31.0-W3-002.3        # 文件更新（depth=1）
```

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

### Ticket YAML 格式

```yaml
---
id: 0.29.0-W1-001
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
0.15.16-W1-001: 實作 startScan() 方法
0.15.16-W1-002: 實作 stopScan() 方法
0.15.16-W1-003: 實作 validateIsbn10() 驗證邏輯
0.15.16-W1-004: 實作 validateIsbn13() 驗證邏輯
0.15.16-W2-005: 實作離線掃描支援（依賴 W1）
0.15.16-W2-006: 實作批次掃描模式（依賴 W1）
...
```

### 範例 2：測試拆分

**原始需求**：
```text
修復 Exception 序列化的 10 個測試
```

**正確拆分**：
```text
0.15.16-W1-001: 修復 ValidationException.toJson() 序列化
0.15.16-W1-002: 修復 AppException.toJson() 序列化
0.15.16-W1-003: 修復 CommonErrors 效能測試
0.15.16-W2-004: 修復 AppException.wrap() 工廠方法（依賴 W1-002）
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
0.15.16-W1-001: 實作 BookRepository.save() 方法
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
- v2.2.0 (2026-01-29): 新增「子任務建立指引」章節，支援任務鏈 ID 格式（如 0.31.0-W3-002.1.1）
- v2.1.0 (2026-01-28): 擴展 Ticket 類型（新增 TST/ADJ）、新增「Ticket 關聯追蹤」章節、新增「行為分離原則」
- v2.0.0 (2026-01-23): 加入 5W1H 欄位、版本驅動任務管理
- v1.1.0 (2026-01-14): 新增「Ticket 服務精神」章節，整合《Unreasonable Hospitality》核心原則
- v1.0.0 (2025-12-25): 初版，基於單一職責原則設計
