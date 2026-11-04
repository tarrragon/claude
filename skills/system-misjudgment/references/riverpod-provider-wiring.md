# Riverpod provider 接線

設計規範見 `dart-provider-architecture` skill；本檔只收「讀測試結果」的誤判。

## RP-1 測試全綠，被讀成 provider 已接線

| 欄位 | 內容 |
|------|------|
| 症狀 | 測試全綠，App 啟動卻出現 provider 錯誤畫面或 `ProviderException` |
| 常見誤判 | 測試覆蓋足夠，啟動錯誤是環境問題 |
| 實際機制 | 必接線 provider（`throw UnimplementedError` 式）在測試中被 `ProviderScope.overrides` 覆寫，app root 的真實接線從未被測試走過 |
| 檢查方法 | 找出每個 `throw UnimplementedError` 式 provider：`grep -rn "UnimplementedError" lib/`；確認各有一個不帶 override、經 app root 建立的 wiring test；再實機啟動 App 看首屏 |
| 正向對照 | 暫時移除 app root 對某個 provider 的 override，wiring test 必須變紅 |
| 判讀標準 | 每個必接線 provider 都有會因接線缺失而紅的 wiring test，且實機首屏正常 → 才算接線；僅帶 override 的測試綠不算 |
| 來源 | `PC-165`；`dart-provider-architecture` skill 的必接線 provider 配對規則 |
