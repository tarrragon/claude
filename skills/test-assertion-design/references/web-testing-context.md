# WEB 類專案測試脈絡

> 本檔承載 WEB 類專案（JS/TS + Jest/Vitest/Playwright 等）在各斷言類型上的考量脈絡差異。
> 內容為輕量脈絡提示，不含具體 API 用法或重構步驟。

---

## 適用專案類型

- 前端 SPA（React、Vue、Svelte 等）
- Chrome Extension
- 任何以 JS/TS 為主要語言、Jest/Vitest/Playwright 為測試框架的前端/瀏覽器環境專案

> Node.js 後端服務（REST API、GraphQL 服務端）屬後端類，見 `backend-testing-context.md`。

---

## 各斷言類型的 WEB 脈絡

### 類型 1–4（環境依賴 flaky 族）

WEB 的 Jest/jsdom 環境下，`performance.now()` 和 `Date.now()` 受 fake timer 設定影響，計時值可能為 mock 固定值或真實計時——需區分。

**計時類（類型 1–3）脈絡提示**：若計時值是 mock 回傳的固定數字，斷言該固定值是確定性的，不屬環境依賴 flaky。識別方式：追溯計時值來源，確認是否經過 `performance.now()` 的真實差值計算。

**記憶體類（類型 4）脈絡提示**：前端專案的記憶體絕對值斷言少見；若在 Node 測試環境出現 `heapUsed` 斷言，受測試框架自身記憶體佔用干擾，應改用操作前後的洩漏差值偵測。

### 類型 5：非同步時序

WEB 環境中非同步問題最常見於：

- DOM 更新（React state change 後的 render cycle 未完成）
- `setTimeout` / `setInterval` 計時器回調
- `fetch` / `XMLHttpRequest` 網路請求完成前

**脈絡提示**：WEB 測試框架通常提供 fake timer 或 waitFor 等待工具。判斷此類問題時，識別信號是「斷言在觸發後但在回調執行前」。

### 類型 6：亂數輸出

WEB 環境中隨機性常見於：

- `Math.random()` 驅動的 UI 排序、顏色選擇、A/B 測試分組
- `crypto.getRandomValues()` 驅動的 UUID / token 生成

**脈絡提示**：全域 `Math.random` 可在測試環境替換為確定性函式，但替換後需確認斷言驗證的是演算法邏輯，而非特定輸出序列。

### 類型 7：測試隔離

WEB 環境中共享狀態常見於：

- 全域 DOM 狀態（jsdom 環境下測試間的 document 殘留）
- `localStorage` / `sessionStorage` 未清除
- ES module 快取（同一模組跨測試共享 singleton）

**脈絡提示**：Chrome Extension 專案需特別注意 `chrome.*` API mock 的重置，以及 service worker 狀態在測試間的隔離。

### 類型 8：快照過度覆蓋

WEB 環境中快照最常見於：

- Jest snapshot 對 React component tree 的全結構比對
- API response 快照

**脈絡提示**：WEB 專案的 UI component 變更頻率高，快照過度覆蓋問題尤為明顯。識別信號：CSS class 名稱更改、裝飾性屬性新增導致大量快照失敗。

### 類型 9：斷言過度集中

WEB 環境中過度集中常見於：

- 一個 test case 驗整個頁面所有 DOM 屬性（文字、樣式、狀態、可見性）
- 整合測試中單一 test 驗多個 API endpoint 的回應結構

**脈絡提示**：識別信號是測試描述（test name / it description）難以用單一行為面向概括，或測試失敗時訊息顯示 10 個以上斷言同時失敗。

---

**Last Updated**: 2026-05-21
**Version**: 1.2.0 — 第 2 輪審查：環境依賴族 section 補類型 4（記憶體絕對值）、標題改 1–4。1.1.0：F1 編號對齊、F6 移除 Node.js、F7 補類型 9（W1-027）
