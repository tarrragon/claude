---
id: TEST-GPD-1004
title: "package:test 的 setUpAll／tearDownAll 預設逾時是 12 分鐘而非 30 秒，以一般測試的 30 秒推論合成測試的逾時行為會對不上紀錄"
severity: low
category: test
related: [IMP-GPD-014]
created: 2026-10-30
---

# TEST-GPD-1004: package:test 的 setUpAll／tearDownAll 預設逾時是 12 分鐘而非 30 秒，以一般測試的 30 秒推論合成測試的逾時行為會對不上紀錄

## 基本資訊

| 項目 | 內容 |
|------|------|
| 風險等級 | 低 |
| 分類 | test |
| 來源版本 | 0.5.0 |
| 首次觀測 | 2026-10-30 |

## 症狀

Dart／Flutter 測試的紀錄寫著「setUpAll 逾時 12 分鐘」，分析者以「package:test 預設逾時 30 秒」為前提，判定紀錄與機制對不上，轉而懷疑有自訂 timeout、量錯對象，或紀錄有誤，並據此規劃重現實驗。

實際上 setUpAll 與 tearDownAll 在 package:test 中是合成測試（synthetic test），有自己的預設上限：test_api 的 `Declarer` 以 `const Timeout(Duration(minutes: 12))` 建立 "(setUpAll)"／"(tearDownAll)" 測試。30 秒只適用一般 `test()`（`Invoker.heartbeat` 的 `defaultTimeout`）。紀錄與機制本來就一致。

實測分布（2026-10-30，8 核機器，以 16 個 CPU 負載程序製造負載，量測中 1 分鐘 load 約 19–33，N=5）：一支會實體化約 7000 個檔案暫存樹的 setUpAll，無負載時 2–4 秒，負載下 19–29 秒（中位數約 24 秒），5 輪全數通過。這個耗時已接近一般測試的 30 秒，但離 12 分鐘上限還很遠；只有在換頁級的記憶體壓力下才觀測到跑滿 12 分鐘。

## 根因

**「預設逾時 30 秒」被當成全體測試的通則記憶**。文件與錯誤訊息最常出現的是一般測試的 30 秒（"Test timed out after 30 seconds"），合成測試的 12 分鐘只寫在 `declarer.dart` 的私有欄位，不在常見的使用說明中。

**逾時是靜默套用的**。專案沒有 `dart_test.yaml`、測試沒有 `Timeout` 註解，也沒有傳 `--timeout`，讀程式碼找不到任何「12 分鐘」字樣，於是推論它不存在。

## 解決方案

- 判讀 setUpAll／tearDownAll 的逾時紀錄時，以 12 分鐘為預設上限；一般 `test()`／`setUp()` 內的工作才以 30 秒判讀。
- 查證逾時來源時，讀 pubspec.lock 鎖定的 test_api 版本，在 `lib/src/backend/declarer.dart` 找 synthetic tests 的 `_timeout`，以及 `invoker.dart` 的 `heartbeat()`；不要只找專案內的 timeout 設定。
- 若需要讓重量級 setUpAll 在異常時提早失敗，以 group 或檔案層的 `Timeout` 明確設定。設定前要評估：上限一旦低於負載下的實測分布，就會在合法的高負載下誤判為紅燈。

## 預防措施

- 把重量級準備工作（大量實體化、建索引）從 setUpAll 移到一般 `test()` 或 `setUp()` 時，逾時上限會從 12 分鐘降到 30 秒。移動前先量負載下的耗時分布；接近 30 秒時要明確設定 timeout，或保留在 setUpAll。
- 紀錄逾時時寫明是「哪一類測試」以及「錯誤訊息中的 timeout 值」（例如 `TimeoutException after 0:12:00`），讓後續讀者不必反推上限。

## 關聯 Ticket

本地案例票號只記在專案票面（框架檔案依引用穩定性規則 8 不引用專案層級識別符）。
