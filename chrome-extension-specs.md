# 📦 Chrome Extension 與專案規範

## Chrome Extension 特定要求

### Manifest V3 規範

- 嚴格遵循 Manifest V3 API
- 使用 Service Worker 而非 Background Pages
- 實現適當的權限請求策略

### 安全性要求

- 所有資料處理在本地進行
- 避免將敏感資料傳送到外部服務
- 實現適當的 CSP (Content Security Policy)
- 最小權限原則：只請求必要的權限

### 技術規格

- **測試框架**: Jest + Chrome Extension API Mocks
- **建置工具**: npm scripts
- **程式碼檢查**: ESLint
- **版本控制**: Git
- **無外部依賴**: 為了安全性和效能考量

## 專案概覽

這是一個基於 **Chrome Extension (Manifest V3)** 的 Readmoo 電子書平台資料提取和管理工具。專案嚴格遵循 **TDD (測試驅動開發)** 和 **事件驅動架構**。

### 核心架構原則

1. **事件驅動架構**: 所有模組通過中央化事件系統通訊
2. **單一責任原則**: 每個模組、處理器和組件只有一個明確目的
3. **TDD 優先**: 所有程式碼必須先寫測試，使用 Red-Green-Refactor 循環
4. **Chrome Extension 最佳實踐**: 遵循 Manifest V3 規範

### 主要組件

- **Background Service Worker** (`src/background/`): 處理擴展生命週期和跨上下文事件
- **Content Scripts** (`src/content/`): 從 Readmoo 頁面提取資料
- **Popup 界面** (`src/popup/`): 主要使用者互動界面
- **儲存系統** (`src/storage/`): 管理資料持久化，支援多種適配器
- **事件系統** (`src/core/`): 模組通訊的中央事件總線

## 檔案管理嚴格規則

- **絕對不創建非必要的檔案**
- **優先編輯現有檔案而非創建新檔案**
- **永不主動創建文件檔案 (\*.md) 或 README 檔案**，除非使用者明確要求
- 臨時檔案和輔助腳本在任務完成後必須清理

## 語言規範

**所有回應必須使用繁體中文 (zh-TW)**

- 產品使用者和開發者為台灣人，使用台灣特有的程式術語
- 程式碼中的中文註解和變數命名嚴格遵循台灣語言慣例
- 如不確定用詞，優先使用英文而非中國用語

---

**🔗 相關文件連結**:

- [返回主指導文件](./../../CLAUDE.md)
- [事件驅動架構規範](./event-driven-architecture.md)
- [Agent 協作規範](./agent-collaboration.md)
