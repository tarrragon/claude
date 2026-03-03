# 六階段評估流程詳細說明

修復前強制評估的完整六階段流程。非語法錯誤必須完成 Stage 1-4 後才能進入 Stage 5-6。

---

## Stage 1: 錯誤分類

**目標**: 準確識別錯誤類型和影響範圍

**檢查項目**:
- 錯誤訊息關鍵字分析
- 錯誤位置定位
- 相關檔案和模組識別
- 潛在影響面分析

**Hook 自動完成的項目**:
- 使用正則表達式分類錯誤類型
- 提供分類結果和建議流程
- 記錄評估結果到日誌

**輸出範例**:

```
Stage 1: 錯誤分類

錯誤類型: TEST_FAILURE
錯誤訊息: Expected: true, Actual: false
位置: test/unit/domains/import/services/import_service_test.dart:234
影響範圍: ImportService 相關功能
```

---

## Stage 2: BDD 意圖分析（僅適用於非語法錯誤）

**目標**: 理解測試用例或程式邏輯的業務意圖

**分析項目**:
- **Given**: 初始狀態和前置條件
- **When**: 觸發的動作或條件變化
- **Then**: 預期的結果和行為

**關鍵問題**:
- 這個測試/程式在驗證什麼業務邏輯？
- 當前實作是否應該滿足這個需求？
- 業務需求是否發生變化？

**輸出範例**:

```
Stage 2: BDD 意圖分析

Given: ImportService 載入了 Chrome 書籍列表
When: 執行 importBooks() 方法
Then: 應返回導入結果且不拋出異常

測試意圖: 驗證 Chrome 擴充套件書籍匯入功能
當前問題: importBooks() 方法拋出未預期的例外
```

---

## Stage 3: 設計文件查詢

**目標**: 檢查設計文件以確認需求和決策

**查詢檔案**:
- `docs/app-requirements-spec.md` - 應用需求規格
- `docs/app-use-cases.md` - 詳細用例說明
- `docs/ui_design_specification.md` - UI 設計
- `docs/work-logs/` - 相關的開發工作日誌
- `docs/app-error-handling-design.md` - 錯誤處理設計

**檢查項目**:
- 需求文件中是否定義了此功能？
- 是否有相關的設計決策記錄？
- 是否有已知的實作缺陷或待辦事項？
- 工作日誌中是否記錄了此問題？
- 是否有相關的設計變更記錄？

**輸出範例**:

```
Stage 3: 設計文件查詢

docs/app-use-cases.md:
  找到 Chrome 擴充套件匯入用例
  狀態: 已計畫，尚未實作完整

docs/app-requirements-spec.md:
  確認需要支援 Chrome 擴充套件書籍匯入
  必要欄位: title, author, ISBN, dateAdded

docs/work-logs/:
  找到相關記錄: v0.5.2-W1-003 (Chrome 書籍解析功能)
  狀態: 實作中
```

---

## Stage 4: 根因定位

**目標**: 準確確定問題根本原因

**分析模式**:

| 問題現象 | 可能根因 | 判斷方法 |
|---------|---------|---------|
| 測試失敗 + 程式未實作 | 功能未完成 | 檢查程式碼是否有 TODO 或占位符 |
| 測試失敗 + 程式已實作 | 邏輯錯誤 | 檢查演算法和邊界條件 |
| 測試失敗 + 程式正確 | 測試過時 | 檢查設計文件是否有新的需求變更 |
| 編譯失敗 + 類型不匹配 | 設計變更 | 檢查介面定義是否已更新 |
| 語法錯誤 | 簡單拼寫 | 直接定位到括號/分號位置 |

**根因問題清單**:
1. 是否是未完成的實作？(TODO/占位符)
2. 是否是邏輯錯誤？(邊界條件、計算錯誤)
3. 是否是過度設計？(不需要的複雜性)
4. 是否是設計變更？(需求更新，文件未同步)
5. 是否是依賴問題？(版本衝突、缺少初始化)

**輸出範例**:

```
Stage 4: 根因定位

根因分析結果:
  問題: importBooks() 方法拋出 null pointer 異常
  根因: EventBus 在方法執行時尚未初始化
  原因類別: 依賴問題 (初始化順序)

相關程式碼位置:
  - lib/domains/import/services/import_service.dart:45
  - 調用: eventBus.post(BookImportedEvent(...))
  - 問題: eventBus 為 null
```

---

## Stage 5: 開 Ticket 記錄（強制）

**目標**: 將評估結果記錄為可追蹤的 Ticket

**強制要求**:
- 必須使用 `/ticket create` 建立 Ticket（除語法錯誤外）
- Ticket 必須包含前四階段的完整分析結果
- Ticket 必須明確指定修復策略
- Ticket 必須包含明確的驗收條件

**Ticket 建立提示模板**:

```markdown
# Fix {ErrorType}: {簡短描述}

## 錯誤分類
- 錯誤類型: {Stage 1 結果}
- 位置: {檔案路徑:行號}
- 影響範圍: {影響模組}

## BDD 分析
**Given**: {前置條件}
**When**: {觸發動作}
**Then**: {預期結果}

## 文件查詢結果
- 需求規格: {查詢結果}
- 相關用例: {查詢結果}
- 工作日誌: {查詢結果}

## 根因分析
**根因**: {Stage 4 結果}
**根因類別**: {分類}

## 修復策略
- **Action**: {修復動作: 補完/修正/更新}
- **Target**: {修復目標}
- **Approach**: {具體修復步驟}

## 驗收條件
- [ ] {測試通過條件}
- [ ] {相關檢查}
- [ ] {文件同步}

## 5W1H 分析
- **Who**: {代理人} (執行者) | rosemary-project-manager (分派者)
- **What**: 修復 {錯誤類型}
- **When**: 評估完成後立即執行
- **Where**: {檔案路徑}
- **Why**: {根因分析}
- **How**: [Task Type: Implementation] {修復步驟}
```

---

## Stage 6: 分派執行

**目標**: 將 Ticket 分派給專業代理人執行

**分派規則**: 依據 `.claude/rules/flows/incident-response.md` 的「派發對應表」決定代理人。

**分派前檢查清單**:
- [ ] Ticket 已建立並有 ID
- [ ] Stage 1-4 分析完整
- [ ] 根因明確
- [ ] 修復策略清晰可行
- [ ] 代理人選擇符合 incident-response.md 派發對應表
- [ ] 驗收條件完整

**分派指令格式**:

```python
Task(
    subagent_type="{incident-response.md 對應代理人}",
    description="修復 {ErrorType}: {簡短描述}",
    prompt="""
    修復 Ticket #{TICKET_ID}

    問題: {根因分析結果}

    修復策略:
    {詳細修復步驟}

    驗收條件:
    {完整的驗收檢查清單}

    禁止:
    - 不要修改測試邏輯
    - 不要進行大規模重寫
    - 執行後必須執行完整測試
    """
)
```
