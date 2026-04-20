# 專案特定規範（Readmoo 書庫管理器）

> **用途**：本檔案從 CLAUDE.md §6 lazy-load 引入，載入時機為寫產品程式碼前。內容為本專案特有的錯誤處理體系與架構骨架。

---

## 錯誤處理體系

專案採用分層錯誤處理，基於 ErrorCodes 常數和專用錯誤類別：

| 錯誤類型 | 檔案位置 | 用途 |
|---------|---------|------|
| ErrorCodes | `src/core/errors/ErrorCodes.js` | 核心錯誤代碼常數 |
| NetworkError | `src/core/errors/NetworkError.js` | 網路相關錯誤 |
| BookValidationError | `src/core/errors/BookValidationError.js` | 書籍資料驗證錯誤 |
| ErrorHelper | `src/core/errors/ErrorHelper.js` | 統一錯誤處理工具 |
| OperationResult | `src/core/errors/OperationResult.js` | 統一操作結果結構 |
| UC0X ErrorFactory/Adapter | `src/core/errors/UC0XError*.js` | 用例特定錯誤工廠 |

**強制規範**：

- 禁止 `throw 'error message'` 或 `throw new Error('message')`，使用專案錯誤類別
- 使用 `OperationResult` 統一回應格式
- 詳見：`src/core/errors/` 目錄

---

## 專案架構

```
src/
├── background/       # Service Worker 和後台邏輯
├── content/          # Content Script（頁面注入）
├── popup/            # 彈出視窗 UI
├── core/             # 核心模組（errors, enums 等）
├── extractors/       # 資料提取器
├── handlers/         # 事件處理器
├── storage/          # 儲存管理
├── export/           # 匯出功能
├── ui/               # 通用 UI 元件
├── utils/            # 工具函式
├── data-management/  # 資料管理
├── overview/         # 書庫總覽
├── performance/      # 效能相關
└── platform/         # 平台抽象層
```

**完整結構說明**：`docs/struct.md`

---

**來源**：從 CLAUDE.md §6 外移（W10-077.1 實施 W10-073.3 骨架設計）
