# APP 類專案測試脈絡

> 本檔承載 APP 類專案（Flutter/React Native 等行動應用）在各斷言類型上的考量脈絡差異。
> 內容為輕量脈絡提示，不含具體 API 用法或重構步驟。

---

## 適用專案類型

- Flutter / Dart 行動應用
- React Native 應用
- 任何以行動應用框架為主的專案

---

## 各斷言類型的 APP 脈絡

### 類型 1–4（環境依賴 flaky 族）

APP 環境中計時問題常見於：

- 動畫持續時間斷言（斷言動畫在 N ms 內完成）
- 平台通道回調的延遲斷言

**計時類（類型 1–3）脈絡提示**：APP 框架的 UI 執行緒排程受裝置效能影響，計時斷言在低階裝置或模擬器環境下特別不穩定。計時門檻應移至效能測試套件獨立執行。

**記憶體類（類型 4）脈絡提示**：APP 的記憶體用量受 widget 樹規模與 image cache 影響，絕對上限在不同裝置與模擬器差異大；應改用操作前後的洩漏差值偵測。

### 類型 5：非同步時序

APP 環境中非同步問題最常見於：

- Widget rebuild 後的 UI 狀態（Flutter 的 frame pump 未完成）
- 平台通道（platform channel）非同步回調
- 動畫完成前的狀態斷言

**脈絡提示**：APP 框架的 UI 驅動特性使「等待 UI 穩定再斷言」更為關鍵。等待機制因框架而異（Flutter 有 `pumpAndSettle`，React Native 有 `act`），但「等完成再斷言」的原則一致。

### 類型 6：亂數輸出

APP 環境中隨機性常見於：

- 隨機生成的業務 ID（訂單號、用戶 ID）
- A/B 測試分組邏輯
- 資料隨機取樣（如隨機推薦）

**脈絡提示**：APP 專案中業務 ID 生成通常需要可控的隨機源，以確保測試的確定性。判斷重點在於「是否斷言了特定隨機輸出值，而非演算法行為特性」。

### 類型 7：測試隔離

APP 環境中共享狀態常見於：

- 全域 singleton service（dependency injection 容器）
- 本地儲存（SharedPreferences、SQLite）的跨測試殘留
- 靜態狀態（如 Flutter `GlobalKey`）

**脈絡提示**：APP 的 singleton 服務模式（BLoC、Provider、Riverpod 等）使全域狀態隔離問題更為普遍。識別信號：測試單獨通過但在全套件中失敗，且失敗原因指向服務初始化狀態。

### 類型 8：快照過度覆蓋

APP 環境中快照最常見於：

- Flutter Widget tree 的 Golden test（像素比對）
- 整個頁面的 Widget 結構快照

**脈絡提示**：Flutter Golden test 的像素精度使其特別脆弱——字體渲染差異、陰影計算、平台字元集都可能觸發 false positive。判斷重點在於「是在驗證視覺設計意圖，還是驗證業務邏輯」。

### 類型 9：斷言過度集中

APP 的 Widget 測試中，常見的過度集中模式：

- 一個 test 驗整個頁面所有 Widget 的文字內容、顏色、狀態
- 將多個用戶流程塞入同一個測試案例

**脈絡提示**：識別信號是測試描述（test name）難以用一個行為面向概括。

---

**Last Updated**: 2026-05-21
**Version**: 1.2.0 — 第 2 輪審查：環境依賴族 section 補類型 4（記憶體絕對值）、標題改 1–4。1.1.0：F1 編號對齊、F7 補計時 section（W1-027）
