---
# 用例（Use Case）模板
# 複製本檔案並重新命名為 UC-{XX}-{簡短描述}.md

id: UC-XX
title: "{用例名稱}"
status: draft                    # draft / review / approved / deprecated
source_proposal: null            # 來源提案 ID，如 PROP-001
created: "YYYY-MM-DD"
updated: "YYYY-MM-DD"
version: "1.0"                   # 用例版本

# 行為者
primary_actor: ""                # 主要行為者，如「使用者」
secondary_actors: []             # 次要行為者

# 平台歸屬
platform: ""                     # both / app / extension
extension_status: ""             # implemented / partial / not-applicable

# 驗證面（紅燈層級順序判準，見 /tdd references/phase2/rules.md「紅燈層級順序」節）
runtime_surface: ""              # yes / no — 場景有無可駕駛的執行面（畫面、CLI、API endpoint）。
                                 # 必填：UC 進入紅燈測試設計（version-bootstrap Step 5）前不可留空，
                                 # 留空不得視同 no（靜默跳過外圈正是本欄要防的盲區）。
                                 # yes：測試設計須先立外圈驗收紅燈（整合/on-device）再寫單元紅燈；
                                 # no（純 domain 計算、data contract、演算法）：豁免外圈，單元/契約層先紅

# 關聯
related_specs: []                # 對應的規格，如 [SPEC-001]
related_usecases: []             # 相關的其他用例
ticket_refs: []                  # 實作此用例的 ticket
---

# UC-{XX}: {用例名稱}

## 基本資訊

| 項目 | 值 |
|------|-----|
| 用例 ID | UC-{XX} |
| 用例名稱 | {名稱} |
| 主要行為者 | {行為者} |
| 利益關係人 | {利益關係人及其利益} |
| 前置條件 | {系統或使用者的初始狀態} |
| 成功保證 | {成功完成後的系統狀態} |

## 主要成功場景

1. **{步驟名稱}**
   - {使用者動作}
   - {系統回應}

2. **{步驟名稱}**
   - {使用者動作}
   - {系統回應}

3. **{步驟名稱}**
   - {使用者動作}
   - {系統回應}

## 替代場景

### {XX}a: {替代場景名稱}

**觸發條件**：{何時進入此替代路徑}

1. {步驟}
2. {步驟}
3. 回到主要場景步驟 {N}

### {XX}b: {替代場景名稱}

**觸發條件**：{何時進入此替代路徑}

1. {步驟}
2. {步驟}

## 流程拓撲（結構化 Flow 區塊，選填）

> FlowStep 型別現階段屬**提案中（proposed）**，尚未升級為正式契約，本區塊選填。
> `uc_registry.py` 未偵測到本區塊時，自動 fallback 至既有散文解析（見
> `.claude/skills/doc/references/usecases.md`「流程拓撲（結構化 Flow 區塊）」章節）。
> 本區塊是上方「主要成功場景」「替代場景」的機器可讀對應，不取代散文描述。

### ID 設計注意事項

- ID 為**不透明穩定識別符**：不得編碼位置（如「1a」）或父步驟。已知真實案例
  中，替代場景群以流水號命名（如 1a-1d），其中一項的實際分岔點與流水號暗示
  的主流程步驟不一致——位置編碼在既有語料上已產生誤讀，本規則即為防此重演。
- 具體 ID 格式（命名慣例、唯一性規則）留待首個 UC 完成結構化回填、取得真實
  結構樣本後再定案，本模板僅提供概念範例，不構成規範。

```yaml
flow:
  - id: "{step-id}"              # 不透明穩定識別符，見上方注意事項
    name: "{步驟名稱}"            # 對應散文標題
    next: ["{step-id}"]          # 後續步驟 id；主要成功場景步驟填寫，場景結尾留空陣列 []
    branch_from: null            # 僅替代場景步驟填寫：分岔自哪個主要成功場景步驟 id。
                                  # 方向為主流程→替代場景，唯一儲存欄位落在替代場景側；
                                  # 「某步驟分岔出哪些替代場景」由消費端掃描所有步驟的
                                  # branch_from 衍生取得，不另存反向欄位。
    return_to: null               # 僅替代場景步驟填寫：回歸到哪個步驟 id。
                                  # back-edge，繪圖/佈局工具須排除於 DAG 佈局。
    implements: []                 # 對應 FR 編號，如 ["FR-01"]，選填
    emits: []                      # 對應 EVT 編號，提案中型別，選填
    consumes: []                   # 對應 EVT 編號，提案中型別，選填
```

**emits / consumes 說明**：EVT 型別現階段屬提案中，尚未進 validator 必填
契約。兩欄位選填，待首個真實 EVT 實例出現後再視需要升級為建議填寫。

**範例（依真實 UC 案例示範，說明性質，非規範化 ID）**：

```yaml
flow:
  - id: create-accounts          # 主要成功場景步驟 1
    name: "建立項目"
    next: [first-inventory]
    implements: [FR-01]
  - id: first-inventory          # 主要成功場景步驟 2
    name: "首次盤點"
    next: [view-net-worth]
    implements: [FR-02]
  - id: view-net-worth           # 主要成功場景步驟 3
    name: "檢視淨資產"
    next: [assess-leverage]
    implements: [FR-04, FR-13]
  - id: reject-invalid-input     # 替代場景：分岔自「首次盤點」步驟，非第一個主流程步驟
    name: "輸入驗證攔截"
    next: []
    branch_from: first-inventory
    return_to: first-inventory
    implements: [FR-24]
```

上例刻意示範常見缺口：替代場景的散文標題編號常暗示分岔自第一個主流程步驟，
但 `branch_from` 實際指向的是另一個步驟——結構化欄位不受標題編號誤導，此為
本區塊存在的核心價值。

## 例外場景

### EX-{XX}-{NN}: {例外名稱}

| 項目 | 值 |
|------|-----|
| 觸發條件 | {何時發生} |
| 錯誤碼 | {對應的 ErrorCode} |
| 處理方式 | {系統如何處理} |
| 使用者提示 | {顯示給使用者的訊息} |
| 恢復策略 | {使用者可以做什麼} |

### EX-{XX}-{NN}: {例外名稱}

{...重複上方格式...}

## 驗收條件

### 功能驗收

- [ ] {主要場景可正常執行}
- [ ] {替代場景 a 可正常執行}
- [ ] {例外場景正確處理}

### 邊界條件

- [ ] {邊界條件 1}
- [ ] {邊界條件 2}

### 效能要求（如適用）

| 指標 | 目標值 |
|------|--------|
| {回應時間} | {< N ms} |
| {處理量} | {N 筆/秒} |

## UI 互動流程（如適用）

{描述使用者介面的互動流程，可使用文字描述或 ASCII 圖}

```
[畫面 A] --按鈕--> [畫面 B] --確認--> [畫面 C]
                           \--取消--> [畫面 A]
```

## 變更歷史

| 版本 | 日期 | 變更內容 |
|------|------|---------|
| 1.0 | YYYY-MM-DD | 初始版本 |
