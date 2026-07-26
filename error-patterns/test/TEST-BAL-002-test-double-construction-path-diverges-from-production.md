---
id: TEST-BAL-002
title: 測試替身走簡化建構路徑，繞過 production 裝配步驟使缺口對測試不可見
severity: high
category: test
related: [PC-165]
created: 2026-07-26
---

# TEST-BAL-002: 測試替身走簡化建構路徑，繞過 production 裝配步驟使缺口對測試不可見

## 症狀

- 規格宣告的功能在 production 完全不運作（資料表恆空、欄位恆 NULL），但全套件測試綠燈、CI 無告警
- 缺口存在期間新增的測試也照樣綠——測試從未觸及斷點所在的路徑
- 以真實 binary 執行端到端操作才暴露：修復前後同一請求的回應差異明確（`{"groups":[],"total":0}` vs 有資料）

## 根因

兩個獨立機制疊加，各自都讓缺口對測試不可見：

**機制一：建構路徑分歧。** production 走完整建構（`NewXxxFull`）含富化/裝配步驟；測試 helper 為省事走簡化建構，該步驟不在其中。測試驗證的是「簡化裝配下的行為」，而缺口正好落在簡化版跳過的那一段——測試與 production 驗證的不是同一條組裝線。

**機制二：測資形狀窄於真實輸入。** wire contract 兩端型別不符（envelope 宣告陣列、schema 宣告字串）會使真實輸入整筆反序列化失敗並靜默降級，但既有測資都不帶該欄位，這條路徑從未被執行。

兩者共同的深層成因：測試替身的**形狀**（建構路徑、測資欄位集合）由「寫測試時的方便」決定，而非由「production 實際形狀」決定。當替身比 production 簡單，簡化掉的部分就成為測試盲區，且盲區大小不可見——沒有任何訊號提示「這段沒被測到」。

## 解決方案

- **接線類缺口的 acceptance 不得只依賴既有測試轉綠**：修復前既有測試已全綠，轉綠無鑑別力。必須新增從真實入口貫穿到真實出口的端到端測試（HTTP POST → DB → GET），並補 runtime 層驗證（真實 binary + 真實請求，修復前後對照）
- **testhelper 形狀對齊 production**：測試 helper 的建構路徑應與 production 同源（呼叫同一個 `NewXxxFull`，或至少讓簡化版顯式標註「已跳過 X 步驟」）；測資欄位集合應覆蓋 wire contract 宣告的全部欄位形態
- **wire contract 兩端型別以 schema 為單一事實來源**：envelope 結構與 schema 宣告不一致時，以 schema 為準並補跨端型別測試

## 預防措施

- 規格宣告的 pipeline 應有「端到端存在性測試」：不驗行為細節，只驗「經真實入口送入後，真實出口拿得到資料」。這類測試對接線缺口有鑑別力，對重構無脆性
- Code review 訊號：看到 `NewXxxFull` 與 `NewXxx` 並存且測試只用後者 → 檢查兩者差異是否含業務步驟
- 修復「規格宣告但未接線」類缺口時，先自行 grep 全 production 呼叫點確認斷點數量——斷點常不只一處（實證：原判定一處，實測四處）

## 關聯

- PC-165（測試綠燈不等於 Runtime 正確）：同家族，但機制不同——PC-165 是 mock 替代真實依賴 + 斷言不檢查訊息文字；本模式是建構路徑分歧 + 測資形狀窄於真實輸入
- 實證：monitor 0.5.0-W4-002（2026-07-26），error fingerprint pipeline 斷在四處，`go test ./...` 262 PASS 全綠，runtime 驗證才暴露
