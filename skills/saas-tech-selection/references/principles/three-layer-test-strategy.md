# Three-Layer Test Strategy

> **角色**：本卡是 `saas-tech-selection` 的支撐型原則（principle）、被 `dimensions/reliability.md` 引用。
>
> **何時讀**：reliability 維度展開時、討論「測試打算寫到什麼程度」— 三層測試策略決定 mock 的邊界和 integration test 的必要性。

## 原則

測試分成三層，每層驗證不同的對象。單靠一層無論寫多少 test 都無法跨越另一層的職責。

| 層級                 | 驗證對象                   | 工具             |
| -------------------- | -------------------------- | ---------------- |
| Unit test            | 程式碼邏輯                 | Mock 外部依賴    |
| Protocol integration | 程式碼和真實服務的協議互動 | 真實服務實例     |
| Screen state test    | 使用者可見的畫面狀態覆蓋度 | Widget / UI test |

## Mock 遮蔽

Mock 模擬的是 API 層的契約（方法簽名、參數型別），不模擬協議層的語意（frame type、handshake、編碼格式）。Mock 遮蔽有兩種模式：功能存在但行為錯誤（mock 接受了真實服務不接受的輸入）、功能根本沒實作（mock 不需要這個步驟就能成功）。

用 mock 數量彌補 mock 盲區是常見反模式 — 在 unit test 層加更多 test 只增加同層覆蓋率、不會跨越到協議層。

## Protocol integration test 的成本判斷

是否需要這一層取決於：協議複雜度（API 簽名是否隱藏協議行為分支）、mock 寬鬆度（mock 跳過多少業務關鍵步驟）、失敗靜默度（外部服務是否靜默忽略錯誤輸入）。Server 可以在 test 環境輕鬆啟動時（Docker 一行、同機程序）成本極低。

## Reliability 維度的銜接

reliability 維度的「測試起始集」應該明確層級：unit test 覆蓋業務邏輯分支、protocol integration test 覆蓋外部服務互動（至少涵蓋 event catalog 中跨 domain 的協議路徑）。「名義 integration test」（名稱含 integration 但全用 fake）要辨識並標明真實驗證邊界。
