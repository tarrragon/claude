# 🎯 5W1H 自覺決策方法論：系統化決策框架

## 📖 方法論目的

本方法論建立基於5W1H原則的系統化決策框架，確保每個開發決策都經過完整思考，消除重複實作和逃避行為。

### 核心立場

我們要求：
- 每個todo建立前必須回答完整5W1H
- 每個決策都有明確的責任歸屬和實作策略
- 零容忍任何逃避性思維

我們拒絕：
- 未經5W1H思考的決策
- 重複功能的開發
- 逃避問題的權宜方案

我們的標準：
- 系統化思考取代直覺判斷
- 防止重複實作優於事後重構
- 完整解決問題優於症狀緩解

## 🔍 5W1H 判斷標準與執行規則

### 🔸 Who (誰) - 責任歸屬判斷

**定義**：確定功能責任歸屬，防止重複實作，並明確區分執行者和分派者

**格式要求**（敏捷重構合規）：
```markdown
Who: {執行代理人} (執行者) | {分派者} (分派者)
```

**適用場景**：
- **代理人執行實作**：`Who: parsley-flutter-developer (執行者) | rosemary-project-manager (分派者)`
- **主線程自行執行職責**：`Who: rosemary-project-manager (自行執行 - 分派/驗收)`
- **文件代理人執行**：`Who: thyme-documentation-integrator (執行者) | rosemary-project-manager (分派者)`

**邊界**：
- 包含：Domain類別、Service物件、既有功能模組、執行代理人、分派者
- 不包含：外部依賴、第三方函式庫

**判斷標準**：
- Domain中已存在相同功能 → **禁止新建**
- 責任明確歸屬於特定類別 → **允許執行**
- 多個類別可能負責 → **必須先釐清歸屬**
- 責任完全不明 → **禁止執行**
- **執行者是主線程但任務是 Implementation** → **違反敏捷重構原則**

**執行規則**：
```markdown
遇到新功能需求 → 執行以下檢查：
1. 搜尋現有Domain是否有相同功能
2. 檢查既有Service是否已實作
3. 確認測試覆蓋是否存在相關功能
4. 若存在則重用，若不存在則明確責任歸屬
```

**驗證機制**：
- 使用Grep搜尋相關功能實作
- 檢查測試檔案確認覆蓋範圍
- 查看Domain設計文件確認職責劃分

#### 📝 Who判斷範例

##### ✅ 正確的Who判斷（敏捷重構合規）

**範例1：代理人執行程式碼實作**
```markdown
## Who: parsley-flutter-developer (執行者) | rosemary-project-manager (分派者)
- Domain責任歸屬：Book Domain的BookValidator負責
- 執行者：parsley-flutter-developer 實作 validateISBN() 方法
- 分派者：rosemary-project-manager 設計 Ticket 並分派任務
```

**範例2：主線程執行分派職責**
```markdown
## Who: rosemary-project-manager (自行執行 - 分派/驗收)
- 職責：分析需求並設計 Ticket
- 執行者：主線程自己執行分派工作
```

**範例3：文件代理人執行文件更新**
```markdown
## Who: thyme-documentation-integrator (執行者) | rosemary-project-manager (分派者)
- 職責：將工作日誌轉化為方法論文件
- 執行者：thyme-documentation-integrator 執行文件整合
- 分派者：rosemary-project-manager 分派文件整合任務
```

##### ❌ 錯誤的Who判斷

**錯誤1：未檢查既有功能**
```markdown
## Who: 書籍驗證功能
- 需要驗證書籍資料
- 建立新的驗證類別
```
**錯誤原因**：未檢查既有功能，可能造成重複實作

**錯誤2：主線程執行 Implementation 任務**
```markdown
## Who: rosemary-project-manager
- 建立 Domain 事件類別
```
**錯誤原因**：違反敏捷重構原則，主線程不應執行程式碼實作

**錯誤3：缺少執行者/分派者標記**
```markdown
## Who: parsley-flutter-developer
- 實作書籍驗證功能
```
**錯誤原因**：未明確標記執行者和分派者，無法檢查合規性

### 🔸 What (什麼) - 功能定義判斷

**定義**：明確定義功能行為和邊界

**邊界**：
- 包含：具體輸入輸出、業務行為、異常處理
- 不包含：技術實作細節、效能最佳化

**判斷標準**：
- 單一職責且明確定義 → **正確**
- 包含多個不相關職責 → **必須拆分**
- 職責模糊不清 → **禁止執行**
- 與既有功能重疊 → **必須整合**

**執行規則**：
```markdown
遇到功能定義 → 執行以下驗證：
1. 確認輸入輸出明確定義
2. 檢查是否符合單一職責原則
3. 驗證與既有功能的邊界清晰
4. 若職責不明則重新定義
```

**驗證機制**：
- 能寫出明確的測試案例 Given-When-Then
- 功能描述不超過一個句子
- 無法拆分為更小的獨立功能

#### 📝 What判斷範例

##### ✅ 正確的What判斷

```markdown
## What: ISBN格式驗證
- 功能描述：驗證輸入字串是否符合ISBN-10或ISBN-13格式
- 輸入：String isbn
- 輸出：ValidationResult (success/failure + message)
- 異常：空字串或null拋出ValidationError
```

##### ❌ 錯誤的What判斷

```markdown
## What: 書籍處理
- 需要處理書籍相關的各種功能
- 包含驗證、儲存、查詢等
```
**錯誤原因**：職責過多，未符合單一職責原則

### 🔸 When (何時) - 觸發時機判斷

**定義**：明確功能觸發的事件和時機

**邊界**：
- 包含：使用者動作、系統事件、定時任務
- 不包含：內部實作的方法呼叫

**判斷標準**：
- 觸發事件明確且唯一 → **正確**
- 多個觸發點但邏輯相同 → **正確**
- 觸發時機不明確 → **必須釐清**
- 副作用未識別 → **禁止執行**

**執行規則**：
```markdown
遇到功能觸發設計 → 執行以下分析：
1. 識別所有可能的觸發事件
2. 確認事件處理的副作用
3. 驗證與Event-Driven架構的整合
4. 若時機不明則重新設計事件流
```

**驗證機制**：
- 能繪製完整的事件流程圖
- 所有副作用都有明確處理
- 與既有事件系統整合無衝突

#### 📝 When判斷範例

##### ✅ 正確的When判斷

```markdown
## When: ISBN掃描後驗證觸發
- 觸發事件：使用者完成ISBN條碼掃描
- 事件名稱：ISBNScannedEvent
- 副作用：觸發書籍資訊查詢、更新UI狀態
- 整合點：與ScanTask聚合根的事件系統整合
```

##### ❌ 錯誤的When判斷

```markdown
## When: 需要驗證的時候
- 書籍資料需要驗證時觸發
```
**錯誤原因**：觸發時機模糊，未明確事件來源

### 🔸 Where (何地) - 執行位置判斷

**定義**：確定功能執行的架構位置和UseCase

**邊界**：
- 包含：UI層、Domain層、Infrastructure層
- 不包含：第三方服務內部實作

**判斷標準**：
- UseCase明確且位置正確 → **正確**
- 位置錯誤但功能明確 → **重新定位**
- 執行位置不明 → **必須找出**
- 跨層級混亂 → **必須重新架構**

**執行規則**：
```markdown
遇到功能執行位置問題 → 執行以下確認：
1. 根據Clean Architecture確定正確層級
2. 驗證與DDD聚合根的關係
3. 確認UseCase的呼叫鏈路
4. 若位置錯誤則重新設計架構
```

**驗證機制**：
- 符合Clean Architecture分層原則
- DDD聚合根邊界清晰
- UseCase呼叫路徑可追蹤

#### 📝 Where判斷範例

##### ✅ 正確的Where判斷

```markdown
## Where: Book Domain的驗證層
- 架構位置：Domain Layer
- 具體位置：BookValidator in Book Aggregate
- UseCase：AddBookUseCase調用驗證邏輯
- 呼叫路徑：UI → UseCase → Domain → Validator
```

##### ❌ 錯誤的Where判斷

```markdown
## Where: 在需要的地方執行
- 書籍相關功能中執行驗證
```
**錯誤原因**：執行位置不明確，未考慮架構分層

### 🔸 Why (為何) - 動機驗證判斷

**定義**：驗證功能開發的真實需求和動機

**邊界**：
- 包含：使用者需求、業務價值、技術必要性
- 不包含：開發者偏好、技術炫技

**判斷標準**：
- 有明確需求編號和文件 → **正確**
- 有業務價值但無正式需求 → **必須補充需求**
- 純技術優化無業務影響 → **評估必要性**
- 逃避性動機 → **立即阻止**

**執行規則**：
```markdown
遇到功能需求 → 執行以下驗證：
1. 檢查是否有對應的需求文件
2. 確認業務價值和使用者場景
3. 識別是否為逃避問題的替代方案
4. 若動機不純則禁止開發
```

**驗證機制**：
- 需求文件中有對應條目
- 能說明具體的使用者價值
- 非用於迴避其他問題

**逃避動機識別清單**：
- 「先做簡單的」→ 逃避複雜問題
- 「這個功能比較好實作」→ 迴避困難任務
- 「順便加個功能」→ 缺乏明確需求
- 「優化一下效能」→ 可能迴避功能問題

#### 📝 Why判斷範例

##### ✅ 正確的Why判斷

```markdown
## Why: 滿足書籍管理需求
- 需求編號：UC-001書籍新增功能
- 業務價值：確保用戶輸入的書籍資料格式正確
- 使用場景：用戶手動輸入ISBN時需要即時驗證
- 文件位置：docs/app-requirements-spec.md#UC-001
```

##### ❌ 錯誤的Why判斷

```markdown
## Why: 增加驗證功能
- 系統需要更多驗證
- 提升程式碼品質
```
**錯誤原因**：無具體需求依據，可能為逃避性開發

### 🔸 How (如何) - 實作策略判斷

**定義**：確定實作方法和技術策略，並明確標記任務類型

**格式要求**（敏捷重構合規）：
```markdown
How: [Task Type: {任務類型}] {具體實作策略}
```

**任務類型分類**：
- **Implementation** - 程式碼實作（必須由執行代理人執行）
- **Dispatch** - 任務分派（主線程執行）
- **Review** - 驗收檢查（主線程執行）
- **Documentation** - 文件更新（文件代理人或主線程執行）
- **Analysis** - 問題分析（設計代理人或主線程執行）
- **Planning** - 策略規劃（主線程或設計代理人執行）

**邊界**：
- 包含：技術選擇、實作步驟、測試策略、任務類型標記
- 不包含：具體程式碼細節

**判斷標準**：
- TDD測試先行策略 → **正確**
- 完整的實作計劃 → **正確**
- 直接寫程式無測試 → **違反流程**
- **Task Type: Implementation 但執行者是主線程** → **違反敏捷重構原則**
- 包含架構債務 → **立即修正**
- 臨時解法 → **禁止**

**執行規則**：
```markdown
遇到實作規劃 → 執行以下驗證：
1. 確認採用TDD測試驅動開發
2. 檢查是否產生架構債務
3. 驗證符合現有程式碼標準
4. 若策略不當則重新規劃
```

**驗證機制**：
- 測試案例先於實作程式碼
- 不產生任何技術債務
- 符合專案程式碼品質標準

#### 📝 How判斷範例

##### ✅ 正確的How判斷（敏捷重構合規）

**範例1：程式碼實作任務**
```markdown
## How: [Task Type: Implementation] TDD驅動實作策略
1. 撰寫ISBN格式驗證的失敗測試
2. 實作BookValidator.validateISBN()讓測試通過
3. 重構程式碼提升可讀性
4. 整合到AddBookUseCase中
5. 確保100%測試覆蓋率
```
**檢查**：Task Type 是 Implementation，執行者必須是執行代理人

**範例2：任務分派**
```markdown
## How: [Task Type: Dispatch] 設計 Ticket 並分派給執行代理人
1. 分析需求並設計完整的 Ticket（包含 5 個核心欄位）
2. 確認 Ticket 的驗收條件符合 SMART 原則
3. 分派給 parsley-flutter-developer 執行
4. 等待執行結果並準備驗收
```
**檢查**：Task Type 是 Dispatch，執行者必須是主線程

**範例3：驗收檢查**
```markdown
## How: [Task Type: Review] 驗收代理人提交的程式碼
1. 檢查所有驗收條件是否達成
2. 確認測試通過率 100%
3. 檢查程式碼品質符合標準
4. 更新工作日誌和 todolist
```
**檢查**：Task Type 是 Review，執行者必須是主線程

##### ❌ 錯誤的How判斷

**錯誤1：未遵循TDD**
```markdown
## How: 快速實作
- 先建立基本功能
- 之後再加測試
- 臨時方案先解決問題
```
**錯誤原因**：未遵循TDD，包含逃避性語言

**錯誤2：缺少任務類型標記**
```markdown
## How: TDD驅動實作策略
1. 撰寫測試
2. 實作程式碼
```
**錯誤原因**：缺少 [Task Type: XXX] 標記，無法檢查合規性

**錯誤3：任務類型與執行者不匹配**
```markdown
Who: rosemary-project-manager (自行執行)
How: [Task Type: Implementation] 建立 Domain 事件類別
```
**錯誤原因**：違反敏捷重構原則，主線程不應執行 Implementation 任務

## 🚨 5W1H強制檢查機制

### 完整性檢查清單

每個todo建立前必須回答：

- [ ] **Who**: 責任歸屬明確，無重複功能
- [ ] **What**: 功能定義清晰，符合單一職責
- [ ] **When**: 觸發時機明確，副作用識別完整
- [ ] **Where**: 執行位置正確，符合架構原則
- [ ] **Why**: 需求依據充分，非逃避性動機
- [ ] **How**: 實作策略完整，遵循TDD原則

**缺失任何項目 → 禁止建立todo**

### 品質驗證標準

- 每個W/H都有明確答案，無模糊表述
- 所有判斷都是二元的（正確/錯誤）
- 實作策略不包含逃避性語言
- 需求追溯完整可驗證

### 🚨 敏捷重構合規性檢查（新增）

**目的**：防止主線程違反敏捷重構原則，確保執行者和任務類型正確匹配

**檢查規則**：

**Who 欄位檢查**：
- [ ] 是否明確標記「執行者」和「分派者」
- [ ] 執行者是否符合任務類型要求
- [ ] 主線程是否執行了應由代理人執行的任務

**How 欄位檢查**：
- [ ] 是否包含 `[Task Type: XXX]` 標記
- [ ] 任務類型是否與執行者匹配

**違反組合檢查**：
- [ ] `Task Type: Implementation` + 執行者是主線程 → ❌ 違反
- [ ] `Task Type: Dispatch` + 執行者是代理人 → ❌ 違反
- [ ] 缺少執行者/分派者標記 → ❌ 格式錯誤

**正確組合驗證**：
- [ ] `Task Type: Implementation` + 執行者是執行代理人 → ✅ 正確
- [ ] `Task Type: Dispatch` + 執行者是主線程 → ✅ 正確
- [ ] `Task Type: Review` + 執行者是主線程 → ✅ 正確
- [ ] `Task Type: Documentation` + 執行者是文件代理人或主線程 → ✅ 正確

**自動檢查機制**：
```python
def check_agile_refactor_compliance(who, how):
    # 提取執行者
    executor = extract_executor(who)

    # 提取任務類型
    task_type = extract_task_type(how)

    # 檢查違反組合
    if task_type == "Implementation" and executor == "rosemary-project-manager":
        return {"decision": "block",
               "reason": "違反敏捷重構原則：主線程不應執行 Implementation 任務"}

    if task_type == "Dispatch" and executor != "rosemary-project-manager":
        return {"decision": "block",
               "reason": "違反敏捷重構原則：代理人不應分派任務"}

    return {"decision": "allow"}
```

### 逃避行為識別

**逃避語言檢測基於「[Claude 自檢與逃避預防方法論]($CLAUDE_PROJECT_DIR/.claude/methodologies/claude-self-check-methodology.md)」的完整違規詞彙表**

#### 🚨 品質妥協和逃避責任類
- 「太複雜」「先將就」「暫時性修正」「症狀緩解」
- 「先這樣處理」「臨時解決方案」「回避」「不想處理」
- "too complex", "workaround", "hack", "temporary fix", "quick fix"
- "bypass", "ignore for now", "will fix later", "avoid dealing with", "skip for now"

#### 🚨 簡化妥協類
- 「更簡單的方法」「採用更簡單的方法」「用更簡單的方法」
- 「選擇更簡單的方法」「簡單的處理方式」「簡化處理」
- "simpler approach", "simpler way", "take the simpler approach"
- "use a simpler method", "easier approach", "simpler method", "simplify"

#### 🚨 發現問題但不解決類
- 「發現問題但不處理」「架構問題先不管」「程式異味先忽略」
- 「只加個 TODO」「問題太多先跳過」「技術債務之後處理」
- "ignore the issue", "architecture debt later", "code smell ignore"
- "just add todo", "too many issues skip", "technical debt later"

#### 🚨 測試品質妥協類
- 「簡化測試」「降低測試標準」「測試要求太嚴格」「放寬測試條件」
- 「測試太複雜」「簡單測試就好」「基本測試即可」「簡化測試環境」
- "simplify test", "simplified test", "lower test standard", "test too strict"
- "relax test requirement", "test too complex", "basic test only", "simple test case", "minimal test", "reduce test complexity"

#### 🚨 程式碼修改逃避類
- 「註解掉」「停用功能」「暫時關閉」「先用比較簡單」
- "comment out", "disable", "temporarily disable", "use simpler first"

#### 🚨 模糊不精確詞彙類
- 「智能」「自動」(無具體描述)「優化」(無具體指標)
- "smart", "intelligent", "auto" (without details), "optimize" (without metrics)

**檢測到任何逃避語言 → 立即阻止決策並要求修正**

## 🔧 Hook系統整合

### Hook觸發時機

- **PreToolUse(TodoWrite)**: 檢查5W1H完整性
- **任何W/H缺失**: 阻止todo建立
- **發現逃避語言**: 進入修復模式

### 檢查機制

```python
# 核心檢查邏輯
def check_5w1h_compliance(todo_content):
    required_sections = ['Who', 'What', 'When', 'Where', 'Why', 'How']

    for section in required_sections:
        if not has_section_answer(todo_content, section):
            return {"decision": "block",
                   "reason": f"必須回答{section}：{get_section_prompt(section)}"}

    if has_avoidance_language(todo_content):
        return {"decision": "block",
               "reason": "發現逃避性語言，必須修正"}

    return {"decision": "allow"}
```

### 修復機制

發現問題時的處理流程：

1. **阻止操作**：立即停止todo建立
2. **提供指引**：明確說明缺失的5W1H項目
3. **要求補充**：必須完整回答所有問題
4. **再次驗證**：確認所有答案符合標準

## 🎯 執行驗證機制

### 成功標準

- 每個決策都有完整的5W1H記錄
- 無重複功能開發
- 零逃避行為
- 所有實作都基於明確需求

### 失敗處理

- 缺失5W1H → 補充完整後重新提交
- 發現重複功能 → 使用既有實作
- 逃避行為 → 按照永不放棄鐵律重新規劃
- 需求不明 → 先澄清需求再開發

### 持續改進

- 定期檢視5W1H執行品質
- 更新逃避語言識別清單
- 優化Hook檢查邏輯
- 補充判斷標準邊界案例

## 📋 方法論執行檢查清單

**執行前確認**：
- [ ] Hook系統已正確配置
- [ ] 5W1H檢查腳本運作正常
- [ ] 逃避語言清單完整更新

**執行中監控**：
- [ ] 每個todo都經過5W1H檢查
- [ ] 無法回答的問題立即處理
- [ ] 重複功能被及時發現

**執行後驗證**：
- [ ] 開發決策品質提升
- [ ] 重複實作情況減少
- [ ] 逃避行為有效控制

---

**這是決策框架，確保每個開發決策都經過系統化思考和完整驗證。**
