# Dart VM service Logging／flutter run

可執行工具：專案的實機驗證配方（如有）提供的 VM service Logging 訂閱腳本（訂閱後直接寫檔）。無此配方時，以任一 VM service 用戶端訂閱 Logging stream 並直接寫檔。

## DV-1 `flutter run` stdout 沒有 developer.log，被讀成沒有 log

| 欄位 | 內容 |
|------|------|
| 症狀 | `fvm flutter run` 的輸出裡看不到程式以 `developer.log` 寫的訊息 |
| 常見誤判 | 程式沒執行到該行，或 log 沒寫出 |
| 實際機制 | `developer.log` 走 VM service 的 Logging stream，不一定進 stdout |
| 檢查方法 | 以 `--start-paused` 啟動，經 VM service 訂閱 Logging stream 後再 resume；用專案配方的 Logging 訂閱腳本直接寫檔（輸入：ws-uri、輸出檔、秒數、訂閱後 resume；用法見該配方）。ws-uri 取得：`fvm flutter run -d macos --start-paused` 的輸出會印出 `http://127.0.0.1:<port>/<token>/`，改寫成 `ws://127.0.0.1:<port>/<token>/ws`（`http` 換 `ws`，結尾加 `ws`） |
| 正向對照 | 訂閱後先觸發一個必定寫 log 的動作（例如啟動時的固定 log 行），檔內必須出現 |
| 判讀標準 | 訂閱已建立且正向對照 log 出現，才可據 log 內是否有目標訊息下結論 |
| 來源 | 機制：`developer.log` 走 VM service Logging stream 而非 stdout；實測依據：訂閱後重放得到 stdout 看不到的記錄 |

## DV-2 多層 grep 加 Monitor 管線，漏行被讀成事件不存在

| 欄位 | 內容 |
|------|------|
| 症狀 | 事件確定發生過，管線輸出卻缺行 |
| 常見誤判 | 事件沒有發生 |
| 實際機制 | 多層 `grep`、背景 monitor 緩衝會改寫或吞掉資料；工具本身沒驗證過時，零結果不是證據 |
| 檢查方法 | 收 log 直接寫檔，不經管線；讀檔後檢查 `sequenceNumber` 是否連續 |
| 正向對照 | 重連 VM service 取完整重送歷史，與先前檔案交叉比對 |
| 判讀標準 | `sequenceNumber` 連續、無缺號 → 觀測完整，才可下「事件不存在」的結論；有缺號 → 觀測無效 |
| 來源 | 機制：多層管線與背景緩衝會吞資料，工具未自證完整前零結果不是證據；實測依據：改直接寫檔後 `sequenceNumber` 連續 |

## DV-3 腳本自印時間戳，被讀成記錄時間

| 欄位 | 內容 |
|------|------|
| 症狀 | 新連線重送的記錄時間看起來都是「連線當下」 |
| 常見誤判 | 重送記錄的時間被改寫，或時序不可信 |
| 實際機制 | 時間戳是腳本自己用 `new Date()` 印的；記錄本身的 `timestamp` 欄位保留原始時間 |
| 檢查方法 | 讀記錄物件的 `timestamp` 欄位，不讀腳本印出的時間 |
| 正向對照 | 同一筆記錄在兩次連線讀到的 `timestamp` 欄位值相同 |
| 判讀標準 | 以記錄的 `timestamp` 欄位判時序 |
| 來源 | 機制：重送記錄保留原始 `timestamp`，腳本自印時間是連線當下；實測依據：兩次連線同一筆記錄的欄位值相同 |

## DV-4 新連線重送「不完整」

| 欄位 | 內容 |
|------|------|
| 症狀 | 新連線只看到重送到首輪完成的記錄 |
| 常見誤判 | VM service 重送只送一部分 |
| 實際機制 | 經管線讀取時才不完整；直接寫檔連兩次，各得完整且相同的記錄 |
| 檢查方法 | 同 DV-2：直接寫檔，連兩次，比對兩份檔的 `sequenceNumber` 範圍與內容 |
| 正向對照 | 兩次重送的檔案內容逐筆相同 |
| 判讀標準 | 兩份檔相同且序號連續 → 重送完整；不同 → 才進一步調查 |
| 來源 | 機制：不完整來自管線讀取；實測依據：直接寫檔連兩次，各得完整且相同的記錄 |

## DV-5 長字串被截斷，訊息尾端的內容遺失

| 欄位 | 內容 |
|------|------|
| 症狀 | log 訊息結尾缺少預期的欄位，例如 `watch failed` 後面的 reason |
| 常見誤判 | 程式沒有帶出 reason，或 onError 與 onDone 兩條路徑無法區分 |
| 實際機制 | VM service 對長字串只回傳截斷的 `valueAsString`，同時 `valueAsStringIsTruncated` 為 true；未取全文就寫出會把截斷值當全文 |
| 檢查方法 | 檢查記錄的 `message.valueAsStringIsTruncated`，為 true 時以 `getObject`（帶 count）取全文；讀檔時搜尋該旗標：`grep -c valueAsStringIsTruncated <log 檔>` |
| 正向對照 | 對已知超長的訊息，取全文後尾端內容必須出現 |
| 判讀標準 | 旗標為 true 的記錄，取全文前不得以其內容缺漏為證據 |
| 來源 | 目前 `vm_log.mjs` 不取全文，遇截斷旗標直接寫出截斷值 |
