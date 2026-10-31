---
id: TEST-GPD-1005
title: "以 async 函式 override Riverpod 的 FutureProvider 來模擬「已載入」，首幀仍是 loading，畫面先走未載入分支"
severity: low
category: test
related: [TEST-GPD-1003]
created: 2026-10-30
---

# TEST-GPD-1005: 以 async 函式 override Riverpod 的 FutureProvider 來模擬「已載入」，首幀仍是 loading，畫面先走未載入分支

## 基本資訊

| 項目 | 內容 |
|------|------|
| 風險等級 | 低 |
| 分類 | test |
| 來源版本 | 0.5.0 |
| 首次觀測 | 2026-10-30 |

## 症狀

一個 widget 測試要模擬「provider 已經有值」的正式路徑，寫成 `provider.overrideWith((ref) async => '0.0.1')`，並斷言畫面不走未載入分支（例如未載入分支的診斷留痕為 0 筆）。結果測試轉紅：未載入分支被執行了一次。

測試者容易把這個紅燈讀成產品碼的缺陷（「已載入時也誤記一筆」），而實際上是測試沒有建出它想要的狀態。

## 根因

`async` 函式回傳的 `Future` 即使內容是常數，也要等到下一個 microtask 才完成。FutureProvider 在第一次被 watch 時同步建立狀態，此時 future 尚未完成，狀態是 `AsyncLoading`。所以第一次 build 時，`maybeWhen(data: ..., orElse: ...)` 走的是 `orElse`，也就是未載入分支。之後 future 完成、widget 重建才會拿到 data，但未載入分支的副作用已經發生了。

正式路徑的前提往往是「provider 在畫面建立前就已經是 data」（例如上游的 gate 已經等過這個 provider）。用 `async` override 建出的狀態不符合這個前提。

## 解決方案

- 用 `SynchronousFuture(value)`（`package:flutter/foundation.dart`）override：`provider.overrideWith((ref) => SynchronousFuture('0.0.1'))`。SynchronousFuture 的 `then` 會同步執行，FutureProvider 第一次讀取時就是 `AsyncData`。
- 「未載入」的對照則用永不完成的 future（例如 `Completer<String>().future`），讓狀態固定在 loading。
- 不要用 `overrideWithValue(AsyncData(...))` 處理 FutureProvider：Riverpod 2.6.1 的 FutureProvider 沒有這個 API，會編譯失敗。

## 預防措施

- 模擬「provider 已載入」時，先確認正式路徑在畫面建立前是否已經是 data。若是，測試要讓首幀就是 data，用 SynchronousFuture，不用 `async` 函式。
- 未載入分支帶副作用（記錄、導覽、送出事件）時，正反兩向都要測（TEST-GPD-1003、test-assertion-design E2）：只測「未載入時有副作用」，看不出「已載入時也觸發」；而反向測試若用 `async` override，又會把測試自己的問題誤判成產品缺陷。
- 反向測試轉紅時，先在測試中印出首幀的 provider 狀態（`AsyncLoading` 或 `AsyncData`），確認測試建出的狀態，再判斷產品碼。

## 關聯 Ticket

本地案例票號只記在專案票面（框架檔案依引用穩定性規則 8 不引用專案層級識別符）。
