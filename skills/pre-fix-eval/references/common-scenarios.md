# 常見情況處理指南

修復前評估流程中的常見錯誤場景及處理方式。

---

## 情況 1: 語法錯誤

**識別**: 括號、分號、引號相關的錯誤

**流程**:
1. Hook 自動識別，提示簡化流程
2. 直接分派 mint-format-specialist
3. 無需開 Ticket

**範例**:
```
Error: Expected '}' but found 'void'

Hook 識別: SYNTAX_ERROR
流程: 簡化 (直接修復)
代理人: mint-format-specialist
Ticket: 不需要
```

---

## 情況 2: 編譯錯誤 - 未完成實作

**識別**: Undefined name, missing implementation

**流程**:
1. 完成六階段評估
2. 開 Ticket: "實作缺失的方法"
3. 分派 parsley-flutter-developer

**範例**:
```
Error: Undefined name 'startBookScan'

Stage 4 根因: startBookScan() 方法在 ScanService 中未實作
原因類別: 功能未完成
Ticket: Implement ScanService.startBookScan()
Agent: parsley-flutter-developer
```

---

## 情況 3: 測試失敗 - 邏輯錯誤

**識別**: Test assertion failed, expected X but got Y

**流程**:
1. 進行 BDD 分析確認測試意圖正確
2. 檢查程式邏輯是否正確實作
3. 開 Ticket: "修正邏輯錯誤"
4. 分派 parsley-flutter-developer

**範例**:
```
Test: test_import_returns_results_count()
Actual: 0 books imported
Expected: 3 books imported

Stage 2 BDD:
  Given: ImportService 有 3 本書籍待匯入
  When: importBooks() 執行
  Then: 返回 3 本書籍

Stage 4 根因: importBooks() 中的迴圈條件錯誤
Agent: parsley-flutter-developer
```

---

## 情況 4: 測試失敗 - 過時測試

**識別**: Test passes in old code, passes in other modules, but fails for this module

**流程**:
1. 檢查設計文件是否有需求變更
2. 確認測試是否應該更新
3. 開 Ticket: "更新過時測試"
4. 分派 pepper-test-implementer

**範例**:
```
Test: test_widget_displays_rating()
Expected: Rating 顯示為 5 星
Actual: Widget 已移除評級功能

Stage 3 文件查詢:
  新需求: 移除評級功能
  設計更新: UI 規格已修改

Ticket: Update tests for removed rating feature
Agent: pepper-test-implementer
```

---

## 情況 5: 測試失敗 - 功能未實作

**識別**: Test expects behavior that is not implemented (parameter accepted but not used, method exists but empty)

**流程**:
1. 進行 BDD 分析確認測試驗證的功能
2. **必須查詢設計文件確認功能需求狀態**
3. 根據文件查詢結果決定處理方式
4. 開 Ticket 或刪除測試（禁止直接跳過）

**文件查詢決策樹**:

```
測試驗證的功能在文件中的狀態？
    |
    +-- 高優先級（必須實作）
    |   -> 開實作 Ticket -> 分派 parsley-flutter-developer
    |
    +-- 中優先級（建議實作）
    |   -> 開技術債 Ticket (TD-XXX) -> 目標版本設為未來版本
    |
    +-- 低優先級（可選實作）
    |   -> 開技術債 Ticket -> 標記為「延後」
    |
    +-- 已放棄/被替代
        -> 刪除測試 -> 記錄刪除原因到工作日誌
```

**禁止行為**:
- 禁止直接刪除測試而不查文件
- 禁止直接標記測試為 `skip` 而不開 Ticket
- 禁止假設功能不需要而跳過

**必須執行的步驟**:
1. 查詢 `docs/app-requirements-spec.md` 確認功能定義
2. 查詢 `docs/app-use-cases.md` 確認用例狀態
3. 查詢 `docs/usecase-flowcharts-review-report.md` 確認優先級
4. 根據文件結果建立對應 Ticket 或刪除測試

**後續行動檢查清單**:
- [ ] 文件查詢完成，優先級已確認
- [ ] 對應 Ticket 已建立（實作 Ticket 或技術債 Ticket）
- [ ] Ticket 已加入 todolist.yaml 技術債務追蹤表
- [ ] 測試已調整（驗證現有功能，不依賴未實作功能）
- [ ] 工作日誌已記錄處理決策

---

## 情況 6: 編譯錯誤 - 設計變更

**識別**: Type mismatch, method signature changes

**流程**:
1. 檢查設計文件確認介面定義
2. PM 評估影響範圍
3. 開 Ticket: "同步設計變更"
4. 分派 parsley-flutter-developer

**範例**:
```
Error: The method 'create' expects 2 arguments, but 3 are provided

Stage 3 文件查詢:
  新設計: Book.create() 簽名已變更
  文件記錄: v0.6.0 API 更新

Stage 4 根因: 呼叫方未同步新簽名，5 個檔案受影響
Agent: parsley-flutter-developer
```
