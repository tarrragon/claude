# 修復前強制評估 - 決策矩陣參考

## 修復決策矩陣

根據以下矩陣決策修復方向：

| 情況 | 測試狀態 | 程式狀態 | 開 Ticket | 修復行動 |
|------|---------|---------|----------|---------|
| **語法錯誤** | - | ❌ 語法錯誤 | ❌ 不需要 | 直接精確修復 |
| **程式實作不完整** | ❌ 失敗 | ❌ 缺少實作 | ✅ 必須 | 評估 → 開 Ticket → 補完實作 |
| **程式邏輯錯誤** | ❌ 失敗 | ✅ 已實作 | ✅ 必須 | 評估 → 開 Ticket → 修正邏輯 |
| **測試過時** | ❌ 失敗 | ✅ 正確 | ✅ 必須 | 評估 → 開 Ticket → 驗證文件 → 更新測試 |
| **設計變更** | ❌ 失敗 | ❌ 無實作 | ✅ 必須 | 評估 → PM 審核 → 開 Ticket → 實作 → 測試 |

## 代理人分派決策樹

### 錯誤分類後的分派決策

```
修復 Ticket 已建立
    │
    ├─ 語法錯誤 (SYNTAX_ERROR)
    │   └─ 分派: mint-format-specialist
    │       ├─ 理由: 直接精確修復括號/分號
    │       ├─ 修復時間: < 5 分鐘
    │       └─ Ticket: 不需要
    │
    ├─ 編譯錯誤 (COMPILATION_ERROR)
    │   ├─ 檢查根因
    │   │   ├─ 未完成實作?
    │   │   │   ├─ 是 → parsley-flutter-developer (補完實作)
    │   │   │   └─ 否 → parsley-flutter-developer (修正邏輯)
    │   │   │
    │   │   └─ 設計變更?
    │   │       ├─ 是 → PM 審核 → rosemary-project-manager
    │   │       │       └─ 通過後 → parsley-flutter-developer
    │   │       └─ 否 → parsley-flutter-developer
    │   │
    │   └─ 分派指南:
    │       ├─ 類型不匹配 → 檢查介面定義 → PM 審核?
    │       ├─ 符號未定義 → 檢查實作進度 → 補完?
    │       └─ 導入失敗 → 檢查檔案存在 → 修復路徑?
    │
    ├─ 測試失敗 (TEST_FAILURE)
    │   ├─ 檢查根因
    │   │   ├─ 邏輯錯誤?
    │   │   │   ├─ 是 → parsley-flutter-developer (修正邏輯)
    │   │   │   └─ 否 → 繼續分析
    │   │   │
    │   │   ├─ 測試過時?
    │   │   │   ├─ 是 → pepper-test-implementer (更新測試)
    │   │   │   └─ 否 → 繼續分析
    │   │   │
    │   │   └─ 設計變更?
    │   │       ├─ 是 → PM 審核 → 確認需求變更
    │   │       └─ 否 → 繼續分析
    │   │
    │   └─ 分派指南:
    │       ├─ Expected/Actual 不匹配 → 邏輯錯誤 → parsley
    │       ├─ 多個測試失敗 → 根因分析 → 根據根因分派
    │       └─ 測試無法執行 → 檢查測試框架 → pepper
    │
    └─ Analyzer 警告 (ANALYZER_WARNING)
        ├─ 檢查警告類型
        │   ├─ 未使用符號?
        │   │   └─ 是 → mint-format-specialist (移除/修復)
        │   │
        │   ├─ 棄用 API?
        │   │   └─ 是 → mint-format-specialist (更新 API 使用)
        │   │
        │   └─ 其他 lint 警告?
        │       ├─ Critical → 立即修復 → mint-format-specialist
        │       └─ Warning → 可延遲 → 記錄為待辦
        │
        └─ 分派指南:
            ├─ deprecated warning → 查詢新 API → 更新使用
            ├─ unused variable → 確認是否需要 → 移除
            └─ style warning → 格式化 → mint
```

## 根因分析決策樹

### 確定根本原因的流程

```
偵測到問題
    │
    ├─ 第一層判斷：類型
    │   ├─ 語法錯誤 (括號、分號)
    │   │   └─ 根因: 簡單拼寫
    │   │
    │   ├─ 編譯錯誤
    │   │   ├─ 類型不匹配?
    │   │   │   ├─ 是 → 檢查介面定義 → 設計變更?
    │   │   │   └─ 否 → 檢查實作
    │   │   │
    │   │   ├─ 符號未定義?
    │   │   │   ├─ 是 → 檢查實作進度 → 是否應該存在?
    │   │   │   └─ 否 → 檢查導入
    │   │   │
    │   │   └─ 導入失敗?
    │   │       └─ 是 → 檢查檔案路徑 → 修復路徑
    │   │
    │   └─ 測試失敗
    │       ├─ 斷言失敗?
    │       │   ├─ 是 → 檢查程式邏輯
    │       │   └─ 程式正確? → 測試過時
    │       │
    │       └─ 異常拋出?
    │           └─ 是 → 檢查初始化 → 依賴問題?
    │
    └─ 第二層判斷：原因類別
        ├─ 簡單拼寫 → mint 直接修
        ├─ 未完成實作 → parsley 補完
        ├─ 邏輯錯誤 → parsley 修正
        ├─ 測試過時 → pepper 更新
        ├─ 設計變更 → PM 審核
        └─ 依賴問題 → 根據具體情況
```

## 錯誤類型優先級

### 分類優先級

```
Priority 1: SYNTAX_ERROR
├─ 識別: 括號、分號、拼字
├─ 流程: 簡化（直接修復）
└─ Exit Code: 0 (允許)

Priority 2: COMPILATION_ERROR
├─ 識別: 類型、引用、導入
├─ 流程: 完整評估
└─ Exit Code: 2 (阻塊)

Priority 3: TEST_FAILURE
├─ 識別: 斷言失敗、失敗計數
├─ 流程: 完整評估
└─ Exit Code: 2 (阻塊)

Priority 4: ANALYZER_WARNING
├─ 識別: lint 警告、棄用 API
├─ 流程: 評估+延遲處理
└─ Exit Code: 2 (阻塊)

Priority 5: UNKNOWN
├─ 識別: 無法分類的錯誤
├─ 流程: 手動分析
└─ Exit Code: 0 (允許)
```

### 優先級應用

優先級高的錯誤會被優先分類。例如，如果輸出中同時包含語法錯誤和編譯錯誤的特徵，系統會優先識別為語法錯誤。

## 常見根因分析對應表

| 錯誤訊息特徵 | 可能根因 | 確認方法 | 修復分派 |
|-----------|--------|---------|--------|
| `Expected '}' but` | 缺少括號 | 查看代碼行 | mint 直修 |
| `Undefined name` | 未實作方法 | 檢查檔案 | parsley 補完 |
| `can't be assigned` | 類型不匹配 | 檢查介面 | 如設計變更→PM |
| `is not a subtype of` | 類型檢查失敗 | 檢查類型定義 | parsley 修正 |
| `Expected: true, Actual: false` | 邏輯錯誤 | 檢查程式邏輯 | parsley 修正 |
| `No such file` | 檔案不存在 | 檢查路徑 | 補完或修復路徑 |
| `null pointer` | 初始化失敗 | 檢查初始化順序 | parsley 修正 |
| `unused import` | 多餘導入 | 確認是否使用 | mint 刪除 |
| `deprecated API` | API 已棄用 | 查詢新 API | mint 更新 |

## 根因 → 決策 映射表

| 根因類別 | 根因描述 | 立即行動 | Ticket 需求 | 代理人 |
|---------|--------|--------|-----------|--------|
| 語法 | 括號/分號/拼字 | 直接修復 | ❌ 不需 | mint |
| 未完成實作 | TODO/缺失方法 | 評估範圍 | ✅ 必須 | parsley |
| 邏輯錯誤 | 條件/計算/邊界 | 分析根因 | ✅ 必須 | parsley |
| 測試過時 | 需求變更,測試未同步 | 驗證文件 | ✅ 必須 | pepper |
| 設計變更 | 介面/簽名改變 | 評估影響 | ✅ 必須 | PM + parsley |
| 依賴問題 | 版本/初始化 | 分析根因 | ✅ 必須 | parsley |
| 配置問題 | 路徑/環境 | 修復配置 | 可選 | 根據具體 |

## Ticket 決策判斷樹

### 何時需要開 Ticket?

```
偵測到問題
    │
    ├─ 錯誤類型是什麼?
    │   ├─ SYNTAX_ERROR
    │   │   └─ Ticket 需求: ❌ 不需要
    │   │       └─ 原因: 可直接修復
    │   │
    │   └─ 其他 (COMPILATION/TEST_FAILURE/WARNING)
    │       └─ Ticket 需求: ✅ 必須
    │           ├─ COMPILATION_ERROR → 開 Ticket 記錄修復
    │           ├─ TEST_FAILURE → 開 Ticket 記錄分析
    │           └─ ANALYZER_WARNING → 開 Ticket 追蹤
```

## 修復驗收檢查清單

修復完成後，按以下清單驗證：

```
修復完成
    │
    ├─ 功能驗證
    │   ├─ [ ] 執行 flutter test 後 100% 通過
    │   ├─ [ ] 無新增失敗
    │   ├─ [ ] 與設計文件一致
    │   └─ [ ] 代碼邏輯清晰
    │
    ├─ 品質驗證
    │   ├─ [ ] 代碼風格符合規範
    │   ├─ [ ] 修改範圍最小化
    │   ├─ [ ] 無遺留 TODO
    │   └─ [ ] 註解清晰完整
    │
    └─ 流程驗收
        ├─ [ ] Ticket 已更新為完成狀態
        ├─ [ ] 工作日誌已記錄
        └─ [ ] 相關文件已同步

最終結論: 所有項目通過 → 修復完成
```

## 版本發布時的根因統計

當發布新版本時，可以按根因分析統計修復情況：

```
v0.X.Y 修復統計
├─ 語法錯誤: N 個 (直接修復)
├─ 編譯錯誤: N 個 (parsley)
├─ 邏輯錯誤: N 個 (parsley)
├─ 測試更新: N 個 (pepper)
├─ API 更新: N 個 (mint)
└─ 設計變更: N 個 (PM reviewed)
```

這些統計可幫助改進開發流程和識別模式。
