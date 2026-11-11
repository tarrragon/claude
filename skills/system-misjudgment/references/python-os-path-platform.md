# Python os.path 平台實作（posixpath／ntpath）

`os.path` 依執行平台綁定不同模組：macOS／Linux 為 posixpath，Windows 為 ntpath。被測程式自己呼叫的路徑函式，決定了路徑字串進入判定時長什麼樣子。

## OSP-1 在 POSIX 上以反斜線字串實測，被讀成 Windows 已驗證

| 欄位 | 內容 |
|------|------|
| 症狀 | 修正 Windows 路徑問題後，在 macOS／Linux 以反斜線字串（如 `D:\side\termchat`）餵入，程式不崩潰、判定看似正確 |
| 常見誤判 | 輸入已是 Windows 形式，所以 Windows 上的行為已被驗證 |
| 實際機制 | posixpath 把反斜線當一般檔名字元，`realpath`／`dirname` 的回傳值仍是正斜線前綴；Windows 上 ntpath 回傳反斜線，下游以 "/" 比對或切分的判定全數不命中 |
| 檢查方法 | 在測試中把被測模組的 `os` 換成代理物件，`path` 指向 ntpath（複製到 `types.SimpleNamespace`），`exists`／`isdir` 用假實作模擬 Windows 檔案系統；以該設定重跑同一批輸入 |
| 正向對照 | 修正前的版本在此設定下必須能重現 Windows 上已知的錯誤行為（例如該擋的寫入被放行）；重現不出來，代表替換沒有生效，先查代理物件是否真的換進被測模組 |
| 判讀標準 | 只有在 ntpath 設定下通過、且正向對照成立，才算驗證過 Windows 語意；只用主機原生 `os.path` 跑過的結果，不能作為 Windows 的結論 |
| 來源 | TEST-LLM-003 |
