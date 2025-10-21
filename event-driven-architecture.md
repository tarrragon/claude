# 🎭 事件驅動架構規範

## 事件命名規範

- **格式**: `MODULE.ACTION.STATE`
- **範例**: `EXTRACTOR.DATA.EXTRACTED`、`STORAGE.SAVE.COMPLETED`、`UI.POPUP.OPENED`

## 事件優先級

- `URGENT` (0-99): 系統關鍵事件
- `HIGH` (100-199): 使用者互動事件
- `NORMAL` (200-299): 一般處理事件
- `LOW` (300-399): 背景處理事件

## 事件處理原則

- 每個模組通過事件總線通訊
- 避免直接模組間依賴
- 事件處理器必須有錯誤處理機制
- 實現事件的重試與降級機制

## 模組通訊方式

- Background ↔ Content Script: Chrome Runtime 訊息傳遞
- Background ↔ Popup: Chrome Extension APIs
- 內部模組: Event Bus 模式

---

**🔗 相關文件連結**:

- [返回主指導文件](./../../CLAUDE.md)
- [Agent 協作規範](./agent-collaboration.md)
- [Chrome Extension 與專案規範](./chrome-extension-specs.md)
