# Protocol Integration Testing

## 核心問題

Unit test 全綠但實機全壞——當被測元件的正確性取決於與外部服務的協議契約時，mock 從結構上無法驗證這件事。mock 忠實模擬 API 行為契約，但 API 和真實服務之間的協議語意層（frame type、auth handshake、序列化格式）被完全跳過。不補 protocol integration test，協議層差異在整個測試套件中不可見，只會在實機部署後才暴露。

**monitor 專案提示**：SDK（Python/JS/Dart）透過 HTTP POST JSON 與 collector 通訊，`schema/event.schema.json` 是契約 SOT。mock HTTP client 不驗證序列化格式、content-type、response code 語意——這些都是 protocol integration test 的覆蓋範圍。

**實戰案例**：app_tunnel v1.2.0——192 個 FakeWebSocketChannel mock test 全綠，實機部署後 WS 握手/auth/frame 三項同時失敗。建立 4 個 protocol integration test 後秒抓 binary frame 差異（ttyd 傳 binary frame 而非 text frame）。

---

## Mock 遮蔽機制

mock 的遮蔽不是缺陷，而是本質——mock 的職責是讓 unit test 快速且確定性，但協議語意不在其模擬範圍內。

| 層級 | 模擬什麼 | 遮蔽什麼 |
|------|---------|---------|
| **API Mock** | 語言 API 的呼叫契約（函式簽名、回傳型別） | 傳輸協議語意（HTTP method、content-type、status code 語意） |
| **協議語意** | — | 序列化格式差異（JSON 欄位順序、encoding）、認證握手、batch 語意 |
| **環境真實行為** | — | 真實服務的啟動狀態、版本差異、併發行為 |

### Monitor 專案 mapping

| 遮蔽面 | 具體風險 |
|--------|---------|
| HTTP transport | SDK mock HTTP client 不驗證 POST body 是否符合 `event.schema.json` 的序列化要求 |
| Schema 驗證 | collector 的 schema validation 邏輯在 mock 環境中未被觸發——SDK 送出格式錯誤的 event，mock 不會拒絕 |
| Batch flush | SDK 的 batch flush 在 mock 中「總是成功」，真實 collector 可能因 payload 過大或格式錯誤回傳 4xx |

---

## 三層測試策略

| 層 | 職責 | 驗證什麼 | 遮蔽什麼 |
|----|------|---------|---------|
| **Unit（mock）** | 內部邏輯正確性 | 狀態轉換、錯誤處理、資料轉換 | 協議差異、真實服務行為 |
| **Protocol integration** | 協議契約正確性 | HTTP method/body/status、schema 合規性、batch 語意 | UI 互動、用戶體驗 |
| **E2E script** | 端到端資料流完整性 | 從 SDK init 到 query 回傳的完整鏈路 | 效能、併發、大規模資料 |

### Unit test（保留既有）

用 mock HTTP client 驗證各 SDK 的內部邏輯：event 建構、session 管理、flush 觸發條件、retry 邏輯、錯誤處理路徑。

### Protocol integration test（核心新增）

對真實 collector 驗證 HTTP 協議契約。關鍵：不用 mock，直接連本機 collector。

```
# 概念示例 — 對真實 collector 驗證 event 送收
1. 啟動 collector（localhost:8080）
2. SDK 建構 event（含 session、timestamp、type）
3. POST /v1/events，body 為 JSON array
4. 驗證 response status 200 + body 含 accepted count
5. GET /v1/events?type={type}
6. 驗證回傳包含剛送出的 event，欄位完整
```

**成本低**：collector 是本機 Go binary，`go run ./collector --port 8080` 即可啟動。CI 腳本先啟動 collector → 跑 SDK integration test → 停止 collector。不需要雲端服務。

### E2E script（完整鏈路驗證）

用 `examples/` 範例腳本跑完整鏈路：SDK init → event/error 送出 → flush → collector 驗證 → 儲存 → query。驗證端到端資料流完整性。

---

## 何時需要 Protocol Integration Test

| 條件 | 需要 protocol integration test |
|------|------|
| 被測元件直接對接外部協議（HTTP/WS/gRPC） | 是 |
| Mock 和真實服務之間有協議語意差異（序列化、認證、status code） | 是 |
| 外部服務可在本機啟動（成本低） | 強烈建議 |
| 被測元件只做資料轉換（不碰網路） | 不需要 |
| 外部服務只能在雲端啟動（成本高） | 用 contract test 替代 |

**monitor 專案優勢**：collector 是本機 Go binary，SDK 和 collector 都在同一台機器上。啟動 collector 然後跑 SDK test，成本極低但價值極高——schema 驗證、HTTP status code 語意、batch flush 行為都能在這層直接抓到。

---

## Monitor 專案三層對應

### Unit（mock）——各 SDK 內部邏輯

| 元件 | 測試目標 | mock 對象 |
|------|---------|---------|
| collector（Go） | schema validator、query 篩選、storage 寫入邏輯 | HTTP request（用 `httptest`） |
| sdk-python | event 建構、session 管理、flush 觸發、retry | HTTP client（用 `unittest.mock`） |
| sdk-js | event 建構、session 管理、batch queue | fetch（用 test double） |
| sdk-flutter | event 建構、session 管理、platform channel | HTTP client（用 `MockClient`） |

### Protocol integration——SDK↔collector HTTP roundtrip

| 測試路徑 | 驗證重點 |
|---------|---------|
| sdk-python → collector | POST body 符合 `event.schema.json`、content-type 為 `application/json`、collector 回傳 200 + accepted count |
| sdk-js → collector | 同上（fetch API 的 body 序列化） |
| sdk-flutter → collector | 同上（Dart http package 的序列化） |
| collector 內部 | schema validation 拒絕不合規 event（回傳 400 + 錯誤訊息） |
| query roundtrip | POST events → GET /v1/events 回傳正確結果 |

### E2E script——完整資料鏈

```
SDK init → event/error 送出 → flush → collector 驗證 → SQLite 儲存 → query 回傳
```

用 `examples/` 的 Python 範例腳本驅動，驗證整條鏈路。各 SDK 各跑一次。

---

## 反模式

**用 mock 數量彌補 mock 盲區**：「測試不夠多」然後再加更多 mock test——300 個用同一個 mock HTTP client 的 test 仍然抓不到序列化格式錯誤。測試策略的品質用層級覆蓋衡量，不是數量。一個對真實 collector 的 5 行 protocol test，比 50 個新增的 mock test 更能防止部署失敗。

---

## 相關文件

- `references/phase2-test-design.md` — 測試金字塔和測試設計（本文是其 protocol integration 擴充）
- `references/doc-handoff.md` — 整合測試 vs 單元測試分工框架
- `references/layered-test-strategy.md` — Clean Arch 五層測試方法選擇
- `docs/transport.md` — SDK↔collector 通訊契約
- `schema/event.schema.json` — 事件格式契約 SOT

---

**Last Updated**: 2026-06-22
**Version**: 1.0.0 — 初始建立。從 blog work-log 提煉 Mock 遮蔽機制 + 三層策略，對應 monitor 專案
**Source**: `~/Projects/blog/content/work-log/testing_three_layer_strategy.md`
