# IMP-044: 生命週期階段缺乏可觀測性 — 除錯盲區

## 錯誤摘要

| 項目 | 說明 |
|------|------|
| **分類** | Implementation |
| **嚴重性** | Medium（不影響功能，但大幅增加除錯成本） |
| **發現版本** | v0.2.0 |
| **相關 Ticket** | 0.2.0-W7-001, 0.2.0-W7-002 |

## 症狀

- 功能異常時，console 沒有任何有用的 log
- UI 停在中間狀態（如 "Connecting..."）但不知道卡在哪個階段
- 排查需要逐一閱讀原始碼猜測問題位置，而非從 log 定位
- 實際除錯時間遠超預期（本案例花費大量時間排查，最終原因是 `connect()` 未呼叫）

## 根因分析

- 多階段流程（啟動 → 連線 → 載入 → 顯示）的每個階段轉換點沒有 log 輸出
- 錯誤處理只做了 try-catch 但沒有輸出錯誤細節
- 「沒有發生的事」比「發生了錯誤的事」更難偵測：如果函式根本沒被呼叫，不會有任何 log
- 具體案例：WebSocket 連線流程沒有 log 顯示「嘗試連線到哪個 URL」「連線結果是什麼」「重連策略狀態」

## 防護措施

### 1. 每個生命週期階段必須有 log

| 階段 | 必須記錄 |
|------|---------|
| 開始動作 | `debugPrint('WebSocketService: connecting to $uri')` |
| 成功結果 | `debugPrint('WebSocketService: connected')` |
| 失敗結果 | `debugPrint('WebSocketService: connection failed: $error')` |
| 重試/恢復 | `debugPrint('WebSocketService: reconnecting in ${delay}s (attempt $n)')` |

### 2. UI 狀態提示要具體

| 錯誤做法 | 正確做法 |
|---------|---------|
| "Connecting..." | "Connecting to localhost:8765..." |
| "Error" | "Connection refused: localhost:8765" |
| "Loading..." | "Loading session history..." |

### 3. 「沒發生的事」也要能偵測

Provider/Service 建構後，如果預期會有後續動作，可以用 delayed check：

```dart
// 建構後 5 秒如果還在 disconnected 狀態，輸出警告
Future.delayed(Duration(seconds: 5), () {
  if (connectionState == WsConnectionState.disconnected) {
    debugPrint('WARNING: WebSocketService created but connect() never called');
  }
});
```

## 錯誤模式特徵

**識別信號**：
- 功能不工作但 console 完全安靜
- 排查時需要加 print 語句才能定位問題
- 「如果當初有一行 log 就能省下 30 分鐘」

**適用場景**：
- 網路連線流程（WebSocket、HTTP、gRPC）
- 資料載入流程（DB、檔案、API）
- 初始化流程（DI、Plugin、Service）
- 任何有多步驟的非同步流程

---

**Last Updated**: 2026-03-27
**Version**: 1.0.0
