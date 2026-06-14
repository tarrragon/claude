# 5W1H 自覺決策方法論：判斷範例與 Hook 程式碼

> **用途**：本檔為 `.claude/methodologies/5w1h-self-awareness-methodology.md` 的衛星參考檔，存放 5W1H 六個維度的完整正反判斷範例，以及 Hook 系統整合程式碼。需要對照具體正反範例落實某一維度判斷，或需要實作 5W1H 檢查與敏捷重構合規 Hook 邏輯時按需讀取。
>
> **核心方法論（六維度判斷標準 + 強制檢查機制 + 逃避行為識別 + 執行驗證）**：`.claude/methodologies/5w1h-self-awareness-methodology.md`（需回顧維度判斷標準、檢查清單或逃避語言清單時讀）

---

## Who 判斷範例

### 正確的 Who 判斷（敏捷重構合規）

**範例 1：代理人執行程式碼實作**
```markdown
## Who: parsley-flutter-developer (執行者) | rosemary-project-manager (分派者)
- Domain 責任歸屬：Book Domain 的 BookValidator 負責
- 執行者：parsley-flutter-developer 實作 validateISBN() 方法
- 分派者：rosemary-project-manager 設計 Ticket 並分派任務
```

**範例 2：主線程執行分派職責**
```markdown
## Who: rosemary-project-manager (自行執行 - 分派/驗收)
- 職責：分析需求並設計 Ticket
- 執行者：主線程自己執行分派工作
```

**範例 3：文件代理人執行文件更新**
```markdown
## Who: thyme-documentation-integrator (執行者) | rosemary-project-manager (分派者)
- 職責：將工作日誌轉化為方法論文件
- 執行者：thyme-documentation-integrator 執行文件整合
- 分派者：rosemary-project-manager 分派文件整合任務
```

### 錯誤的 Who 判斷

**錯誤 1：未檢查既有功能**
```markdown
## Who: 書籍驗證功能
- 需要驗證書籍資料
- 建立新的驗證類別
```
錯誤原因：未檢查既有功能，可能造成重複實作

**錯誤 2：主線程執行 Implementation 任務**
```markdown
## Who: rosemary-project-manager
- 建立 Domain 事件類別
```
錯誤原因：違反敏捷重構原則，主線程不應執行程式碼實作

**錯誤 3：缺少執行者/分派者標記**
```markdown
## Who: parsley-flutter-developer
- 實作書籍驗證功能
```
錯誤原因：未明確標記執行者和分派者，無法檢查合規性

---

## What 判斷範例

### 正確的 What 判斷

```markdown
## What: ISBN 格式驗證
- 功能描述：驗證輸入字串是否符合 ISBN-10 或 ISBN-13 格式
- 輸入：String isbn
- 輸出：ValidationResult (success/failure + message)
- 異常：空字串或 null 拋出 ValidationError
```

### 錯誤的 What 判斷

```markdown
## What: 書籍處理
- 需要處理書籍相關的各種功能
- 包含驗證、儲存、查詢等
```
錯誤原因：職責過多，未符合單一職責原則

---

## When 判斷範例

### 正確的 When 判斷

```markdown
## When: ISBN 掃描後驗證觸發
- 觸發事件：使用者完成 ISBN 條碼掃描
- 事件名稱：ISBNScannedEvent
- 副作用：觸發書籍資訊查詢、更新 UI 狀態
- 整合點：與 ScanTask 聚合根的事件系統整合
```

### 錯誤的 When 判斷

```markdown
## When: 需要驗證的時候
- 書籍資料需要驗證時觸發
```
錯誤原因：觸發時機模糊，未明確事件來源

---

## Where 判斷範例

### 正確的 Where 判斷

```markdown
## Where: Book Domain 的驗證層
- 架構位置：Domain Layer
- 具體位置：BookValidator in Book Aggregate
- UseCase：AddBookUseCase 調用驗證邏輯
- 呼叫路徑：UI -> UseCase -> Domain -> Validator
```

### 錯誤的 Where 判斷

```markdown
## Where: 在需要的地方執行
- 書籍相關功能中執行驗證
```
錯誤原因：執行位置不明確，未考慮架構分層

---

## Why 判斷範例

### 正確的 Why 判斷

```markdown
## Why: 滿足書籍管理需求
- 需求編號：UC-001 書籍新增功能
- 業務價值：確保用戶輸入的書籍資料格式正確
- 使用場景：用戶手動輸入 ISBN 時需要即時驗證
- 文件位置：docs/app-requirements-spec.md#UC-001
```

### 錯誤的 Why 判斷

```markdown
## Why: 增加驗證功能
- 系統需要更多驗證
- 提升程式碼品質
```
錯誤原因：無具體需求依據，可能為逃避性開發

---

## How 判斷範例

### 正確的 How 判斷（敏捷重構合規）

**範例 1：程式碼實作任務**
```markdown
## How: [Task Type: Implementation] TDD 驅動實作策略
1. 撰寫 ISBN 格式驗證的失敗測試
2. 實作 BookValidator.validateISBN() 讓測試通過
3. 重構程式碼提升可讀性
4. 整合到 AddBookUseCase 中
5. 確保 100% 測試覆蓋率
```
檢查：Task Type 是 Implementation，執行者必須是執行代理人

**範例 2：任務分派**
```markdown
## How: [Task Type: Dispatch] 設計 Ticket 並分派給執行代理人
1. 分析需求並設計完整的 Ticket（包含 5 個核心欄位）
2. 確認 Ticket 的驗收條件符合 SMART 原則
3. 分派給 parsley-flutter-developer 執行
4. 等待執行結果並準備驗收
```
檢查：Task Type 是 Dispatch，執行者必須是主線程

**範例 3：驗收檢查**
```markdown
## How: [Task Type: Review] 驗收代理人提交的程式碼
1. 檢查所有驗收條件是否達成
2. 確認測試通過率 100%
3. 檢查程式碼品質符合標準
4. 更新工作日誌和 todolist
```
檢查：Task Type 是 Review，執行者必須是主線程

### 錯誤的 How 判斷

**錯誤 1：未遵循 TDD**
```markdown
## How: 快速實作
- 先建立基本功能
- 之後再加測試
- 臨時方案先解決問題
```
錯誤原因：未遵循 TDD，包含逃避性語言

**錯誤 2：缺少任務類型標記**
```markdown
## How: TDD 驅動實作策略
1. 撰寫測試
2. 實作程式碼
```
錯誤原因：缺少 [Task Type: XXX] 標記，無法檢查合規性

**錯誤 3：任務類型與執行者不匹配**
```markdown
Who: rosemary-project-manager (自行執行)
How: [Task Type: Implementation] 建立 Domain 事件類別
```
錯誤原因：違反敏捷重構原則，主線程不應執行 Implementation 任務

---

## Hook 系統整合程式碼

### Hook 觸發時機

- PreToolUse(TodoWrite)：檢查 5W1H 完整性
- 任何 W/H 缺失：阻止 todo 建立
- 發現逃避語言：進入修復模式

### 5W1H 完整性檢查邏輯

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

### 敏捷重構合規性自動檢查

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

### 修復機制

發現問題時的處理流程：

1. 阻止操作：立即停止 todo 建立
2. 提供指引：明確說明缺失的 5W1H 項目
3. 要求補充：必須完整回答所有問題
4. 再次驗證：確認所有答案符合標準

---

**Last Updated**: 2026-06-14
**Version**: 1.0.0 - 從 5w1h-self-awareness-methodology.md 瘦身外移（W8-020.4）：六維度完整正反判斷範例 + Hook 系統整合程式碼（5W1H 完整性檢查 + 敏捷重構合規性檢查）
