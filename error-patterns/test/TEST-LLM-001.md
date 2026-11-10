---
id: TEST-LLM-001
title: "integration_test 等待真實平台 I/O 時 pumpAndSettle 提前返回，畫面停在 loading，後續 finder 時紅時綠"
severity: medium
status: active
related:
 - TEST-GPD-1000
 - TEST-GPD-1008
---

# TEST-LLM-001: integration_test 等待真實平台 I/O 時 pumpAndSettle 提前返回，畫面停在 loading，後續 finder 時紅時綠

## 基本資訊

| 項目 | 值 |
|------|-----|
| 分類 | test |
| 來源版本 | 3.1.0 |
| 風險等級 | 中 |
| 首次觀察 | 2026-11（consumer 回報，收入 canonical） |

**判準**：on-device 測試中，`pumpAndSettle` 返回不代表真實 I/O 已完成。

## 症狀

Flutter App 的 integration_test（on-device，本例為 macOS 目標）啟動 App 後，首次 `pumpAndSettle` 返回，接著的 finder 找不到預期元件。同一測試未改程式碼連跑，結果時紅時綠：

| 形態 | 徵狀 | 取樣 |
|------|------|------|
| 找不到元件 | 目標元件 `find.byType(...)` 0 個 | 單次觀察 |
| 讀取容器失敗 | 讀 `IndexedStack` 時 `StateError: No element` | 未修改連跑 5 次，3 紅 |

**誤判風險**：徵狀與「元件改名、finder 過時」同形。第一個實例最初就被歸為元件改名，追了一輪改名才排除。

## 根因

App 啟動後等待真實平台 I/O（本例為 sqflite 讀取），畫面停在 loading。這段期間沒有排程中的幀，`pumpAndSettle` 的迴圈條件 `binding.hasScheduledFrame` 不成立，於是判定「已穩定」並立即返回。

真實 I/O 不受測試 binding 的 fake-async 時鐘驅動，多 pump 幾次也不會讓它完成，I/O 要等真實時間經過才結束。後續 finder 的結果取決於 I/O 剛好比 pump 快或慢，於是時紅時綠。

**與既有兩則 pumpAndSettle 模式的區別**：

| Pattern | 機制 | pumpAndSettle 的表現 |
|---------|------|---------------------|
| TEST-GPD-1000 | 無限動畫持續排幀 | 逾時 |
| TEST-GPD-1008 | App hidden 時 `framesEnabled` 為 false，幀排不進去 | 一次 pump 即返回 |
| 本 pattern | 幀可以排、也沒有動畫，但等待的對象（真實 I/O）不在 fake 時鐘上 | 立即返回，畫面停在 loading |

## 解決方案

首次 `pumpAndSettle` 後加有界輪詢：以 `tester.runAsync` 讓出真實時間，再 pump，直到目標元件出現或達上限。

```dart
for (var i = 0; i < maxPolls && find.byType(Target).evaluate().isEmpty; i++) {
  await tester.runAsync(() => Future<void>.delayed(pollInterval));
  await tester.pumpAndSettle();
}
expect(find.byType(Target), findsOneWidget);
```

- 上限要明確（實例用過 20×250ms 與 50×200ms）。超過上限時仍以原 finder 斷言失敗，訊息可讀，不會變成無限等待。
- 輪詢條件用「目標元件出現」，不用「loading 元件消失」：後者在 loading 尚未掛上的瞬間就成立。

**驗證**：smoke 測試套用後連跑 5 次 5 綠 0 紅（修前 5 次 3 紅）；另一支 seam 測試同法修復。

## 預防措施

- on-device 測試的首個斷言，只要前面有任何真實 I/O（資料庫、檔案、平台 channel、網路），就不能只靠 `pumpAndSettle`；用上面的有界輪詢等到目標元件，並把等待的對象寫在輪詢條件裡。
- 判讀 integration flaky 前，先確認紅燈當下畫面是否仍在 loading（例如截圖或 dump widget tree），再考慮元件改名、finder 過時等解讀。
- 取樣判讀 flaky 時 N >= 5，並記錄紅綠分佈（PC-168）。

## 相關 Pattern

- TEST-GPD-1000：無限動畫使 `pumpAndSettle` 逾時
- TEST-GPD-1008：App hidden 時 `framesEnabled` 為 false，`pumpAndSettle` 一次 pump 即返回
- PC-168：少量綠燈不等於 always 綠燈（flaky 取樣）

## 來源

tarrragon/claude#126（consumer 提出的 error-pattern 提案，由 canonical 收入）。
