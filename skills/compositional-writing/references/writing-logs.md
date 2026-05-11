# Writing Logs — Log 輸出的組合式寫作指引

本文件為「撰寫 log 輸出」情境的完整寫作指引。Log 的讀者是未來的除錯者（人或 AI），寫作目標是讓讀者在最短時間內理解**發生了什麼、在哪裡、影響什麼**。

> **自包含聲明**：本文件不依賴其他 reference。讀完本文件即可獨立寫出合格 log。

---

## TL;DR — 五條核心規則

| 規則                           | 說明                                                          |
| ------------------------------ | ------------------------------------------------------------- |
| 一條 log 一個事件              | 不合併多事件；迴圈用摘要                                      |
| 結構化優先                     | Key-Value 或 JSON；禁止純字串拼接                             |
| 描述業務事件，不描述程式碼位置 | `event=order.created` 而非 `Entering function processOrder()` |
| Severity 標準：誰該被叫醒      | error=立刻處理；warn=定期檢視；info=查詢用；debug=開發用      |
| 跨元件必有 correlation ID      | 2+ 元件流程必帶 `request_id` / `trace_id`                     |

---

## 1. 原子化 × Log — 一條 log 一個事件

### 原則

一條 log 記錄**一個可識別的事件**。不要把多個事件合併成一條；也不要把一個事件拆成多條無法關聯的 log。

### 判斷標準

| 條件                                               | 是否該寫成一條 log                             |
| -------------------------------------------------- | ---------------------------------------------- |
| 這是一個有開始和結束的行動（如「載入檔案」）？     | 是，一條                                       |
| 這個行動橫跨多個階段（如「下載 → 驗證 → 儲存」）？ | 每階段一條，用 correlation ID 串接             |
| 這是迴圈中的重複事件（如「處理第 N 筆」）？        | 摘要一條（「處理 1000 筆完成」），不是每筆一條 |
| 這是異常發生的瞬間？                               | 一條（含完整上下文）                           |

### 正確範例

```text
正確：每個事件一條 log，可獨立理解
[INFO] request_id=abc123 user_id=42 event=order.created amount=NTD 1500
[INFO] request_id=abc123 event=payment.authorized gateway=stripe
[INFO] request_id=abc123 event=order.confirmed duration_ms=342
```

### 反例

```text
錯誤：三個事件混在一條，無法單獨分析
[INFO] Order abc123 created for user 42, paid via stripe, confirmed in 342ms
```

問題：

- 監控系統難以從這條 log 提取「付款成功率」
- 若只有付款失敗，這條 log 會變成「半成品」或「根本不輸出」
- 無法用 grep 找到「所有 payment.authorized 事件」

---

## 2. 索引 × Log — 結構化 log 設計

### 原則

Log 必須能被**機器聚合**和**人類搜尋**。結構化 log（key-value 或 JSON）同時滿足兩者；純文字只滿足人類，且在規模擴大後難以維護。

### 兩種結構化格式

#### 格式 A：Key-Value（人類友善，機器可解析）

```text
[INFO] 2026-04-16T12:00:00Z level=info component=checkout event=order.created request_id=abc123 user_id=42 amount=1500 currency=NTD
```

**適用場景**：CLI 工具、開發環境、日誌檔案。

**寫作要求**：

- 時間戳固定放最前面（ISO 8601 格式）
- `level` `component` `event` 固定三欄位（後述）
- 其餘欄位按「通用 → 業務」順序排列
- 欄位名稱全小寫，使用下底線（`user_id` 非 `userId`）

#### 格式 B：JSON（機器友善，適合日誌平台）

```json
{"timestamp":"2026-04-16T12:00:00Z","level":"info","component":"checkout","event":"order.created","request_id":"abc123","user_id":42,"amount":1500,"currency":"NTD"}
```

**適用場景**：生產環境、日誌平台（ELK/Loki/CloudWatch）、需要聚合分析。

**寫作要求**：

- 單行 JSON（不要換行，否則無法每行一事件聚合）
- 欄位順序不重要（機器會解析），但建議時間戳放第一個便於肉眼掃描
- 數值型欄位不加引號（`"amount":1500` 非 `"amount":"1500"`）

### Correlation ID（跨元件追蹤）

**強制要求**：任何跨越 2+ 元件或 2+ 行動的流程，必須有 correlation ID。

| 場景           | Correlation ID 類型 | 範例欄位名                   |
| -------------- | ------------------- | ---------------------------- |
| HTTP 請求流程  | 請求 ID             | `request_id`                 |
| 使用者 session | Session ID          | `session_id`                 |
| 批次任務       | Job ID              | `job_id`                     |
| 跨服務 RPC     | Trace ID            | `trace_id`（配合 `span_id`） |

**正確範例**：

```text
[INFO] request_id=abc123 component=api event=request.received path=/orders
[DEBUG] request_id=abc123 component=db event=query.start query=select_orders
[DEBUG] request_id=abc123 component=db event=query.end duration_ms=45 rows=3
[INFO] request_id=abc123 component=api event=response.sent status=200 duration_ms=89
```

單一 correlation ID `abc123` 串起整個請求生命週期。

---

## 3. 意圖顯性 × Log — 描述業務事件而非技術動作

### 原則

Log 訊息描述**發生了什麼業務事件**，而不是**程式碼執行到哪一行**。讀者想知道系統的狀態，不是程式的控制流。

### 對照表

| 技術動作（差）                     | 業務事件（好）                                                               |
| ---------------------------------- | ---------------------------------------------------------------------------- |
| `Entering function processOrder()` | `event=order.processing_started order_id=123`                                |
| `if branch taken`                  | `event=order.payment_method_selected method=credit_card`                     |
| `Loop iteration 5/10`              | `event=batch.progress processed=5 total=10 job_id=xyz`                       |
| `Exception caught`                 | `event=order.validation_failed reason=invalid_shipping_address order_id=123` |
| `Returning null`                   | `event=user.lookup_miss user_id=42 reason=not_found`                         |

### 錯誤 log 必含上下文

錯誤 log 的目的是「提供診斷所需的所有資訊」、不是「告訴讀者出錯了」 — 因為「出錯了」這件事系統其他訊號（HTTP 5xx、alert、使用者抱怨）已經傳達、log 此時的角色是讓除錯者重現問題、所以判準對齊到「重現所需的最小資訊集」。光寫「Failed to process order」沒有 order_id / user_id / 錯誤類型、除錯者要從頭追、log 等於白寫。

**必填欄位**（錯誤 log）：

| 欄位            | 範例                               | 為什麼必要              |
| --------------- | ---------------------------------- | ----------------------- |
| `error_type`    | `validation_error`                 | 分類錯誤，便於聚合統計  |
| `error_message` | `shipping_address_invalid`         | 人類可讀的原因          |
| `component`     | `order-service`                    | 定位出錯元件            |
| 業務識別        | `order_id=123 user_id=42`          | 定位受影響的資料/使用者 |
| Correlation ID  | `request_id=abc123`                | 串接事件鏈              |
| 錯誤瞬間的狀態  | `order_status=pending amount=1500` | 重現問題時的關鍵資訊    |

**可選欄位**：`stack_trace`（長，建議另存檔）、`retry_count`、`upstream_error`。

### 正確範例

```text
錯誤的錯誤 log：
[ERROR] Failed to process order

正確的錯誤 log：
[ERROR] component=order-service event=order.processing_failed request_id=abc123 order_id=123 user_id=42 error_type=payment_declined error_message=insufficient_funds gateway=stripe order_status=pending amount=1500 retry_count=2
```

第二條 log 讓讀者不需要重現問題就能理解：

- 哪個元件出錯（`order-service`）
- 哪筆訂單、哪個使用者受影響（`order_id=123 user_id=42`）
- 錯誤類型和原因（`payment_declined / insufficient_funds`）
- 事件背景（`gateway=stripe amount=1500`）
- 已重試幾次（`retry_count=2`）

---

## 4. 可查詢性 × Log — 關鍵字一致性與 Severity 分級

### 4.1 事件名稱的關鍵字一致性

**強制要求**：`event` 欄位使用固定命名慣例，讓 grep/聚合工具能精確匹配。

**推薦慣例**：`<domain>.<action>[_<result>]`

| 範例                    | 解釋                       |
| ----------------------- | -------------------------- |
| `order.created`         | 訂單被建立（動作完成）     |
| `order.creation_failed` | 訂單建立失敗               |
| `payment.authorized`    | 付款授權成功               |
| `payment.declined`      | 付款被拒                   |
| `user.login_attempted`  | 使用者嘗試登入（動作開始） |
| `user.login_succeeded`  | 登入成功                   |

**禁止不一致命名**：

| 禁止                                          | 原因                       |
| --------------------------------------------- | -------------------------- |
| `order.created` 和 `OrderCreated` 混用        | 破壞 grep 精確匹配         |
| `payment.ok` 和 `payment.authorized` 同義混用 | 聚合時變成兩種事件         |
| `event=處理成功`（中文）                      | 跨系統相容性差、regex 難寫 |

### 4.2 Severity 分級判斷標準

Severity 的**唯一標準**是「誰應該被叫醒」 — 因為 severity 在 production 的角色是「分流通知對象」（on-call / 工程師日報 / 查詢用 / 開發 debug）、判準應對齊到「該叫誰」。常被誤用的兩個替代判準都對不上分流目的：「問題嚴重度」會把使用者輸入錯誤判成 info（嚴重度低）、但若需要監控異常率該分到 warn；「發生頻率」會把高頻 debug 訊息誤升為 warn（頻率高）、但實際無人需要被叫醒。

| Severity | 觸發條件                                               | 必填資訊                                               | 誰該關注                      |
| -------- | ------------------------------------------------------ | ------------------------------------------------------ | ----------------------------- |
| `error`  | 業務功能失敗且需要介入（使用者看到錯誤、資料遺失風險） | 元件、錯誤類型、業務識別、correlation ID、錯誤瞬間狀態 | **on-call 工程師需立刻處理**  |
| `warn`   | 降級運作、重試成功、非預期但可自行恢復                 | 元件、警告類型、業務識別、恢復方式                     | 工程師需定期檢視（日報/週報） |
| `info`   | 業務事件發生（訂單建立、使用者登入、任務完成）         | 元件、事件名稱、業務識別                               | 供查詢使用，不主動通知        |
| `debug`  | 程式內部狀態、決策分支、效能測量                       | 元件、狀態描述、相關變數                               | 開發者除錯用，生產環境可關閉  |

### Severity 判斷流程

```text
這條 log 記錄的事件是否需要有人立刻處理？
├─ 是 → error
└─ 否 → 這個事件是否偏離預期但系統已自行處理？
        ├─ 是 → warn
        └─ 否 → 這是業務事件還是技術細節？
                ├─ 業務事件（使用者可感知） → info
                └─ 技術細節（內部狀態） → debug
```

### 常見誤用

| 誤用                     | 問題                     | 正確做法                                         |
| ------------------------ | ------------------------ | ------------------------------------------------ |
| Retry 成功寫 `error`     | 最終成功不該叫醒 on-call | 寫 `warn`（記錄重試次數）                        |
| 使用者輸入錯誤寫 `error` | 使用者錯誤不是系統問題   | 寫 `info`（業務事件）或 `warn`（若需監控異常率） |
| 查詢未命中寫 `warn`      | 「查不到」通常是正常業務 | 寫 `info`（`user.lookup_miss`）                  |
| 每次函式進入寫 `info`    | 污染業務事件流           | 寫 `debug`                                       |

### 4.3 欄位值的可查詢設計

| 設計                 | 好查詢                     | 壞查詢                                                       |
| -------------------- | -------------------------- | ------------------------------------------------------------ |
| 枚舉值用固定小寫字串 | `status=pending`           | `status=PENDING` 和 `status=pending` 混用                    |
| 數值不包單位         | `duration_ms=342`          | `duration="342ms"`（regex 難處理）                           |
| 布林用明確字串       | `is_retry=true`            | `is_retry=1` 或 `is_retry=yes` 混用                          |
| 陣列用分隔符         | `tags=urgent,priority,vip` | `tags=["urgent","priority","vip"]`（key-value 格式中難解析） |

---

## 5. 欄位設計 × Log — 不同 Severity 的必填欄位

### 通用必填欄位（所有 severity）

| 欄位        | 範例                   | 說明                   |
| ----------- | ---------------------- | ---------------------- |
| `timestamp` | `2026-04-16T12:00:00Z` | ISO 8601 帶時區        |
| `level`     | `info`                 | 小寫，見 Severity 分級 |
| `component` | `order-service`        | 元件名稱，kebab-case   |
| `event`     | `order.created`        | 事件名稱，見 4.1 節    |

### Severity 特定必填欄位

| Severity | 必填欄位                                                                                          | 格式範例                                                                                                                 |
| -------- | ------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------ |
| `error`  | `error_type`、`error_message`、業務識別（至少一個）、Correlation ID（跨元件時）、錯誤瞬間關鍵狀態 | `[ERROR] timestamp=... level=error component=... event=... error_type=... error_message=... order_id=... request_id=...` |
| `warn`   | `warn_type`、業務識別、恢復方式（若有）                                                           | `[WARN] timestamp=... level=warn component=... event=... warn_type=... order_id=... retry_count=2`                       |
| `info`   | 業務識別（讓這條 log 可被單獨查詢）                                                               | `[INFO] timestamp=... level=info component=... event=... order_id=...`                                                   |
| `debug`  | 無硬性業務欄位；允許記錄內部狀態、分支決策、變數值；必須能在生產環境關閉                          | `[DEBUG] timestamp=... level=debug component=... event=... <狀態欄位>`                                                   |

### 禁止記錄的欄位

| 禁止                                 | 原因                 | 替代                                         |
| ------------------------------------ | -------------------- | -------------------------------------------- |
| 密碼、API key、token 完整值          | 安全風險             | 記錄遮罩後的片段（`token_prefix=sk_abc...`） |
| 完整使用者 PII（姓名、地址、信用卡） | 隱私合規             | 記錄 ID（`user_id=42`）                      |
| 完整請求/回應 body                   | 太大、可能含敏感資料 | 記錄摘要（`body_size_bytes=1024`）           |
| 完整 SQL 查詢（含參數）              | 可能含使用者資料     | 記錄參數化 SQL + 參數雜湊                    |

---

## 6. 反模式對照表

| 反模式                                              | 症狀                                                                                             | 正確做法                                                                                                                         |
| --------------------------------------------------- | ------------------------------------------------------------------------------------------------ | -------------------------------------------------------------------------------------------------------------------------------- |
| 字串拼接代替結構化欄位                              | `[ERROR] Order 123 for user 42 failed because of insufficient funds at stripe` — grep 找不到這條 | `[ERROR] event=order.failed order_id=123 user_id=42 error_type=payment_declined error_message=insufficient_funds gateway=stripe` |
| Severity 表達「問題嚴重度」而非「應否叫醒 on-call」 | `[ERROR] User entered wrong password` — 使用者輸入錯誤不該觸發 on-call                           | `[INFO] event=user.login_failed user_id=42 reason=wrong_password`                                                                |
| Log 訊息依程式碼位置命名而非業務事件                | `[DEBUG] Entering orderController.create() at line 142` — 重構時立刻失效                         | `[DEBUG] event=order.creation.input_validating component=order-controller order_id=pending`                                      |
| 迴圈中每次迭代都寫 info log                         | `[INFO] Processing item 1` × 1000 條 — 污染 log、掩蓋真實事件                                    | `[INFO] event=batch.started job_id=xyz total=1000` + 完成時摘要                                                                  |
| 錯誤 log 只有 error_message 沒有業務識別            | `[ERROR] Database connection timeout` — 哪個查詢？哪個使用者？無法定位                           | `[ERROR] event=db.query_timeout component=order-service request_id=abc123 query=select_orders timeout_ms=5000`                   |
| 混用時間格式或時區                                  | `2026-04-16 12:00:00` vs `Apr 16 12:00:00` — 跨系統聚合無法排序                                  | 統一 ISO 8601 + UTC（`2026-04-16T12:00:00Z`）                                                                                    |
| Stack trace 塞進 log 訊息本體                       | `[ERROR] Failed: at func.a (line 12), at func.b (line 34)...` — 訊息被稀釋、工具解析困難         | `[ERROR] event=order.failed error_type=null_pointer stack_trace_id=st_abc123`（stack trace 另存）                                |
| 使用主觀形容詞                                      | `[WARN] Query is slow` — 「慢」沒有量化，無法監控                                                | `[WARN] event=db.query_slow duration_ms=3200 threshold_ms=1000 query_name=select_user_orders`                                    |

---

## 7. 自評檢查清單

寫完一條 log 後，自問以下問題。任一答「否」即需修改。

### 內容自評

- [ ] 半年後陌生工程師能僅憑這條 log 理解發生了什麼嗎？
- [ ] 這條 log 有明確的業務事件名稱（`event` 欄位）嗎？
- [ ] Severity 是依「誰該被叫醒」選的，不是依「感覺多嚴重」嗎？
- [ ] 錯誤 log 含足夠診斷資訊（錯誤類型、業務識別、瞬間狀態）嗎？
- [ ] 跨元件流程有 correlation ID 串接嗎？

### 格式自評

- [ ] 結構化（key-value 或 JSON）而非純字串拼接嗎？
- [ ] 欄位命名一致（小寫 + 下底線）嗎？
- [ ] 時間戳是 ISO 8601 + UTC 嗎？
- [ ] 數值不含單位字元（`duration_ms=342` 而非 `duration=342ms`）嗎？
- [ ] 事件名稱符合 `<domain>.<action>[_<result>]` 慣例嗎？

### 安全自評

- [ ] 沒有記錄密碼、完整 token、信用卡號嗎？
- [ ] 沒有記錄完整 PII（改記 ID）嗎？
- [ ] 沒有記錄完整請求/回應 body 嗎？

### 可查詢自評

- [ ] grep `event=<事件名>` 能精確找到所有相關 log 嗎？
- [ ] grep `<業務識別>=<值>` 能找到所有影響該實體的 log 嗎？
- [ ] 日誌聚合工具能從這條 log 提取統計指標嗎？

---

## 8. 速查表（寫作時在手邊）

### Severity 決策

```text
需要立刻叫醒 on-call？ → error
降級/自行恢復的異常？ → warn
業務事件（使用者可感知）？ → info
程式內部狀態/除錯？ → debug
```

### 必填欄位

```text
所有：timestamp, level, component, event
error：+ error_type, error_message, 業務識別, correlation_id
warn：+ warn_type, 業務識別
info：+ 業務識別
debug：無硬性要求
```

### 事件命名

```text
<domain>.<action>          — 動作完成：order.created
<domain>.<action>_failed   — 動作失敗：order.creation_failed
<domain>.<action>_started  — 動作開始：batch.started
<domain>.<action>ing       — 動作進行中：order.processing（罕用）
```

### 格式選擇

```text
開發/CLI/小型系統       → Key-Value
生產/日誌平台/大規模    → JSON（單行）
跨服務追蹤必要         → 加 trace_id / span_id
```

---

## 附錄：為什麼 log 寫不好就等於沒寫

好 log 與壞 log 的差距在事件發生時才被感受到。壞 log 的代價：

| 壞 log 症狀                         | 除錯代價                     |
| ----------------------------------- | ---------------------------- |
| 訊息模糊（`error happened`）        | 需要重現問題才能定位         |
| 缺少識別（沒有元件/使用者/請求 ID） | 無法串接跨模組事件           |
| Severity 用錯（info 當 error）      | 監控噪音太多，真實警報被淹沒 |
| 散落格式（半 JSON 半文字）          | 無法用工具聚合分析           |

**本文件目標**：讓你寫的 log 在半年後被陌生工程師搜尋到時，仍能單憑訊息本身理解事件。

---

**Scope**: Log output writing (所有程式語言與框架通用)
**Dependencies**: 無（自包含）
**Last Updated**: 2026-04-18
