# 印表機列印功能：測試覆蓋深度不足導致四個 Bug 上線

> 來源：2026-03 多廚房印表機列印功能。寫了 28 個測試，全部通過，上實機後陸續發現四個 Bug。
> 對應 Phase：Phase 2（測試設計）、Phase 3（實作品質）

---

## 問題概述

四個 Bug 都在同一條執行路徑上，只是深度不同。程式走到第一個錯誤就中斷，後面的都被遮蔽。每修一個，程式才能走到下一個：

```
Bug 1（印表機內部元件未初始化）
  -> 修好，程式碼走得更遠
Bug 2（品項分派邏輯錯誤，全部送到同一台）
  -> 修好，兩台印表機都有被呼叫
Bug 3（多欄表格的欄位寬度不符合規定）
  -> 修好，表格列印通過驗證，繼續往下
Bug 4（空行觸發第三方 library 的越界錯誤）
```

測試沒有發現這些問題，因為測試沒有走過完整路徑：

```
真實路徑：  接收訂單 -> 組裝收據 -> 列印中心 -> 表格列印/文字列印 -> 印表機底層
測試路徑：  接收訂單 -> （手動構造結果，後面都沒跑）
```

| Bug | 出了什麼事 | 測試沒抓到的原因 |
|-----|-----------|-----------------|
| Bug 1: 印表機元件未初始化 | 模擬印表機的初始化漏掉了內部元件 | 只測了「送出資料」，沒測「組裝列印指令」這個步驟 |
| Bug 2: 品項全分到同一台 | 分派邏輯找到第一台可用的印表機就全部送過去 | 手動構造預期結果，分派邏輯沒有被執行 |
| Bug 3: 欄位寬度錯誤 | 欄位比例不符合 library 要求的總和 12 | 模擬的收據內容只有純文字行，沒有多欄表格行 |
| Bug 4: 空行越界錯誤 | 第三方 library 沒有處理空字串 | 被 Bug 3 擋住，程式從未執行到這一行 |

---

## 坑 1：測試的是「手動構造的結果」，不是「程式的行為」

> 對應 Decision Question Q7（中間步驟測試）、Q9（碰巧通過）

**怎麼發現的：** 實機上兩台廚房印表機只有一台收到品項，另一台完全沒動。但測試裡的分派測試是通過的。

**怎麼找到原因的：** 回頭看測試程式碼，發現測試裡的分派結果是手動寫死的：

```dart
test('品項分派邏輯', () {
  // 手動構造預期結果，沒有走過真正的分派邏輯
  final result = OnlineOrderPrintResult(
    itemPrinterMapping: {'item-1': 'kitchen-2'},
  );
  record.applyPrintResult(result);
  expect(record.kitchenItemPrintJobs['item-1']!.printerId, 'kitchen-2');
});
```

測試名稱寫的是分派邏輯，實際測的是資料儲存。品項分派的程式碼從頭到尾沒有被執行過。

**怎麼修的：** 改成從入口方法開始呼叫，讓分派邏輯實際跑一遍：

```dart
test('2 台空 productNames 印表機：品名奇偶分配到不同印表機', () async {
  PrintCenter.to.initFakeKitchenPrinters();
  final result = await handler.printAppendedOrder(payload, printMain: false);
  expect(result.itemPrinterMapping['item-1'], 'kitchen-2');
  expect(result.kitchenResults['kitchen-1'], isTrue);
});
```

---

## 坑 2：只測了子類別自己的方法，沒測從父類別繼承的方法

**怎麼發現的：** 實機上廚房印表機列印全部失敗，log 顯示內部元件未初始化的錯誤，但測試裡模擬印表機的初始化和列印測試都是通過的。

**怎麼找到原因的：** 測試裡呼叫的是模擬印表機自己覆寫的「送出資料」方法（改成什麼都不做），但實際列印時上層呼叫的是從父類別繼承的「組裝列印指令」方法，這個方法內部依賴一個需要初始化的元件。測試覆蓋到的方法，和實際執行路徑走到的方法不是同一個。

**怎麼修的：**

```dart
// 測試實際列印路徑會用到的方法
test('init 後 printText 不報錯（驗證 generator 已初始化）', () async {
  final printer = FakePrinterAdapter('test-printer');
  await printer.init();
  await printer.printText('測試文字'); // 走 generator.text() -> sendBytes
});

// 反向驗證：確認未初始化的行為
test('未 init 就呼叫 printText 會拋出錯誤', () async {
  final printer = FakePrinterAdapter('test-printer');
  expect(() => printer.printText('測試文字'), throwsA(isA<Error>()));
});
```

---

## 坑 3：斷言只檢查「有沒有」，沒檢查「對不對」

> 對應 Decision Question Q_new3（值驗證 vs 存在性驗證）

**怎麼發現的：** 修完 Bug 1 和 2 之後重跑測試，通過了。但 log 顯示列印結果都是 `false`（失敗），和測試通過的結果矛盾。

**怎麼找到原因的：** 斷言寫的是 `containsKey`：

```dart
expect(result.kitchenResults.containsKey('kitchen-1'), isTrue);
```

只檢查「有沒有這台印表機的結果」，不管結果是成功還是失敗。列印在 try-catch 裡失敗後回傳 `false`，但 key 存在，所以斷言通過。

**怎麼修的：** 改成直接檢查值：

```dart
expect(result.kitchenResults['kitchen-1'], isTrue,
    reason: '廚房1 列印應成功');
```

---

## 坑 4：模擬元件的回傳資料只覆蓋了部分分支

**怎麼發現的：** 修完 Bug 1、2，也修正了斷言之後，測試全過，列印結果也都是 `true`。但上實機測試時仍全部失敗，log 顯示「欄位寬度總和必須等於 12」。

**怎麼找到原因的：** 測試環境和實機的差異在於收據的內容。實機用的是真實的廚房收據模板，包含多欄表格（品名+數量）。測試用的是模擬的收據產生器，只回傳一行純文字：

```dart
class FakeReceiptBuilderService extends ReceiptBuilderService {
  Future<List<ReceiptLine>> buildReceiptLines(...) async {
    return [ReceiptLine.singleLine(data.title)]; // 只有標題
  }
}
```

純文字走的是「文字列印」，多欄表格走的是「表格列印」——兩條不同的分支。模擬的資料只觸發了文字列印，表格列印從未被測試執行過。

---

## 坑 5：替 try-catch 設計專門的測試

try-catch 會把錯誤吞掉，讓測試誤以為一切正常。Bug 1、3、4 都有一個共同特徵——錯誤被 try-catch 吞掉，回傳 `false`，沒有任何明顯的異常。

**三個對策**：

1. **斷言成功路徑的值**：不要只檢查「沒拋錯」，要檢查回傳值是 `true`
2. **提供完整的依賴**：讓 try 區塊能完整執行，而非依賴 catch 來「通過」測試
3. **寫專門的失敗測試**：故意製造失敗條件，驗證錯誤處理行為

```dart
test('完整列印路徑成功', () async {
  PrintCenter.to.initFakePrinters();
  final receiptBuilder = FakeReceiptBuilderService();
  final result = await handler._printKitchenReceipt(data, receiptBuilder);
  expect(result, isTrue);
});

test('缺少依賴時返回 false（try-catch 生效）', () async {
  final result = await handler._printKitchenReceipt(data, null);
  expect(result, isFalse);
});
```

---

## 坑 6：try-catch 的範圍太大，把程式碼 bug 和硬體故障混在一起處理

**問題**：`catch (e)` 攔截了所有錯誤，不區分類型。裡面混了兩種性質不同的錯誤：

- **印表機故障**（連線逾時、無紙、裝置離線）-> 執行期的預期狀況，應該攔截
- **程式碼 bug**（未初始化的元件、欄位寬度不合法、空字串越界）-> 開發階段就該被發現的問題，不應該被靜默吞掉

**怎麼修的：**

1. 定義 `PrinterException`，專門代表印表機硬體/連線錯誤
2. 在列印中心（IO 邊界）把印表機拋出的 `Exception` 包成 `PrinterException`，但不攔截 `Error`
3. 列印方法改為 `on PrinterException catch`，只處理印表機故障

```dart
// 改動前：所有錯誤都被吞掉
try {
  final lines = await receiptBuilder.buildReceiptLines(data, template);
  await printCenter.printReceiptLines(lines: lines, printer: printer);
  return true;
} catch (e) {
  return false;
}

// 改動後：資料準備不在 try 裡，只攔截印表機錯誤
final lines = await receiptBuilder.buildReceiptLines(data, template);
try {
  await printCenter.printReceiptLines(lines: lines, printer: printer);
  return true;
} on PrinterException catch (e) {
  return false;
}
```

---

## 對應 Decision Questions

| Question | 本案例的答案 |
|----------|------------|
| Q7 | 測試只從入口到中間就停了，後半段路徑從未執行 |
| Q9 | 手動構造結果讓「沒跑過的邏輯」碰巧通過 |
| Q_new3 | `containsKey` 只驗存在性，未驗值的正確性 |
| Q10 | catch 區塊零日誌，靜默吞掉程式碼 bug |

---

**Last Updated**: 2026-04-04
**Version**: 1.0.0 - 從 phase2/rules.md 抽出為獨立案例檔
