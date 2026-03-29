# ARCH-010: 模組組裝遺漏導致功能鏈路靜默斷裂

## 基本資訊

- **Pattern ID**: ARCH-010
- **分類**: 架構/依賴注入
- **來源版本**: v0.15.4
- **發現日期**: 2026-03-29
- **風險等級**: 高
- **關聯 Ticket**: 0.15.4-W3-002

## 問題描述

### 症狀

功能端到端不通，但各模組獨立運作正常、無錯誤訊息或僅有不顯眼的警告。
典型表現：資料提取成功（96 本書）→ 書庫頁面無任何記錄。

本次實際發現 3 個層疊的組裝遺漏：

1. **async listener**：`chrome.runtime.onMessage` 的 callback 定義為 `async`，回傳 Promise 而非 `true`，Chrome 立即關閉訊息通道
2. **ContentMessageHandler 未注入**：`background-coordinator.js` 建立 `MessageRouter` 時未傳入 `contentMessageHandler`，導致所有 content-script 事件轉發被丟棄
3. **EventCoordinator 未啟動**：只呼叫 `initialize()` 未呼叫 `start()`，`EXTRACTION.COMPLETED` 監聽器從未註冊

### 根本原因 (5 Why 分析)

1. Why 1: 書庫頁面沒有書籍資料
2. Why 2: `chrome.storage` 中無 `readmoo_books` 資料
3. Why 3: `EXTRACTION.COMPLETED` 事件監聽器未註冊，書籍資料未寫入 storage
4. Why 4: `EventCoordinator.start()` 從未被呼叫（只呼叫了 `initialize()`）；`ContentMessageHandler` 從未被實例化注入到 `MessageRouter`
5. Why 5: 模組化重構時，組裝層（coordinator）未完整連接所有依賴和生命週期

### 特徵識別

- 各模組單元測試通過，但端到端功能不通
- 日誌中只有不顯眼的警告（`沒有處理器處理訊息類型`），無明確錯誤
- 問題在模組組裝層（coordinator/bootstrap），不在模組內部

## 解決方案

### 問題 1: async listener

```javascript
// 錯誤：async 回傳 Promise，Chrome 不認
this.chromeMessageListener = async (message, sender, sendResponse) => {
  // ...async 邏輯
  return true  // Chrome 收到的是 Promise，不是 true
}

// 正確：同步回傳 true，非同步邏輯分離
this.chromeMessageListener = (message, sender, sendResponse) => {
  this._handleMessageAsync(message, sender, sendResponse)
  return true  // 同步回傳 true
}
```

### 問題 2: 依賴未注入

```javascript
// 錯誤：未傳入 contentMessageHandler
this.messageRouter = new MessageRouter(commonDependencies)

// 正確：建立並注入
const contentMessageHandler = new ContentMessageHandler(commonDependencies)
this.messageRouter = new MessageRouter({
  ...commonDependencies,
  contentMessageHandler
})
```

### 問題 3: 生命週期不完整

```javascript
// 錯誤：只初始化未啟動
await this.eventCoordinator.initialize()

// 正確：初始化 + 啟動
await this.eventCoordinator.initialize()
await this.eventCoordinator.start()
```

## 防護措施

### 1. Coordinator 組裝檢查清單

每個 Coordinator 建立模組時，必須確認：

| 檢查項 | 說明 |
|--------|------|
| 依賴注入完整 | constructor 的所有 optional dependencies 是否都已提供 |
| 生命週期完整 | initialize() + start() 都已呼叫 |
| 事件監聽器已註冊 | 核心事件有對應的 listener |
| 訊息路由已連接 | 所有訊息來源（content/popup/background）都有處理器 |

### 2. Chrome Extension Manifest V3 注意事項

- `chrome.runtime.onMessage` listener **必須同步回傳 `true`**
- 不可使用 `async` listener，非同步邏輯必須分離到獨立方法

### 3. 端到端煙霧測試

建議建立整合測試：Content Script 提取 → Background 儲存 → Overview 讀取，驗證完整資料流。

## 教訓

- **模組化重構的風險不在模組內部，在組裝層**：單元測試全過不代表系統可用
- **靜默失敗是最危險的**：這 3 個問題都沒有明確的錯誤拋出，只有不起眼的警告
- **Chrome Extension 的 Manifest V3 有特殊的 API 契約**：async/sync 行為與一般 JS 不同

---

**Last Updated**: 2026-03-29
