# 認知負擔設計方法論：來源範例與 SOLID 視角詳解

> **用途**：本檔為 `.claude/methodologies/cognitive-load-design-methodology.md` 的衛星參考檔，存放五大認知負擔來源的完整正反程式碼範例，以及 SOLID 五原則的認知負擔視角詳解。需要對照具體範例理解某一來源如何拉高認知負擔、或需要深入某一 SOLID 原則的認知負擔分析時按需讀取。
>
> **核心方法論（三種類型 + 來源概念 + 五原則 + SOLID 視角概要）**：`.claude/methodologies/cognitive-load-design-methodology.md`（需回顧認知負擔類型、來源分類或原則定義時讀）

---

## 認知負擔來源的完整範例

對應主檔「認知負擔的來源」節（5 類來源的概念說明）。本節提供每一類來源的問題程式碼與改善方式對照。

### 來源 1：變數狀態追蹤

每個變數都是閱讀者需要「記住」的項目。

**問題程式碼**：

```dart
void processOrder(Order order) {
  var items = order.items;
  var total = 0.0;
  var discount = 0.0;
  var tax = 0.0;
  var shipping = 0.0;
  var finalPrice = 0.0;
  var isValid = true;
  var errorMessage = '';
  // 閱讀者需要同時追蹤 8 個變數狀態
}
```

**改善方式**：

```dart
void processOrder(Order order) {
  final pricing = _calculatePricing(order);
  final validation = _validateOrder(order);
  // 閱讀者只需追蹤 2 個概念
}
```

### 來源 2：呼叫層級追蹤

追蹤呼叫鏈需要「堆疊」記憶。

**問題**：

```dart
// 閱讀者需要追蹤 4 層呼叫才能理解邏輯
methodA() -> methodB() -> methodC() -> methodD()
```

**改善方式**：

```dart
// 扁平化，讓閱讀者在同一層級理解
methodA() {
  resultB = methodB();
  resultC = methodC(resultB);
  return finalProcess(resultC);
}
```

### 來源 3：命名品質

不佳的命名增加「翻譯」負擔。

| 問題命名 | 認知負擔 | 改善命名 |
|---------|---------|---------|
| `d` | 需要猜測含義 | `discountAmount` |
| `temp` | 臨時？什麼的臨時？ | `previousBalance` |
| `data` | 什麼資料？ | `userProfile` |
| `process()` | 處理什麼？怎麼處理？ | `calculateTotalPrice()` |
| `handle()` | 處理什麼事件？ | `onUserLoginSuccess()` |

### 來源 4：條件分支複雜度

每個分支都是需要考慮的「路徑」。

**問題**：

```dart
if (condition1) {
  if (condition2) {
    if (condition3) {
      // 閱讀者需要同時記住 3 個條件
    }
  }
}
```

**改善方式**：

```dart
// 使用 Guard Clause 扁平化
if (!condition1) return;
if (!condition2) return;
if (!condition3) return;

// 主邏輯在這裡，只有一層縮排
```

### 來源 5：隱藏的副作用

函式名稱未反映其真實行為。

**問題**：

```dart
// 名稱說「取得」，但實際上會修改資料庫
User getUser(int id) {
  _database.updateLastAccessTime(id); // 隱藏副作用！
  return _database.findById(id);
}
```

**改善方式**：

```dart
// 分離查詢和命令
User findUserById(int id) {
  return _database.findById(id);
}

void recordUserAccess(int id) {
  _database.updateLastAccessTime(id);
}
```

---

## SOLID 原則的認知負擔視角詳解

對應主檔「SOLID 原則的認知負擔視角」節（5 原則的傳統解釋 + 認知負擔視角概要）。本節提供各原則的對照表與流程示意。

### SRP（單一責任原則）

**傳統解釋**：一個類別只有一個改變的原因。

**認知負擔視角**：一個類別只代表一個概念，閱讀者只需建立一個心智模型。

| 類別 | 責任數 | 認知負擔 |
|------|--------|---------|
| `UserRepository` | 1 | 低 |
| `UserServiceAndValidator` | 2 | 中 |
| `UserManagerAndLoggerAndNotifier` | 3+ | 高 |

### OCP（開放封閉原則）

**傳統解釋**：對擴展開放，對修改封閉。

**認知負擔視角**：新增功能不需要理解現有程式碼的所有細節。

**未遵循 OCP 時**：

```
新增折扣類型
    |
    +-- 需要理解 calculatePrice() 所有邏輯
    +-- 需要修改 switch/case
    +-- 需要理解所有現有折扣的互動
    |
    認知負擔：高（需要理解整個系統）
```

**遵循 OCP 時**：

```
新增折扣類型
    |
    +-- 只需理解 Discount 介面
    +-- 實作新的 DiscountStrategy
    +-- 註冊到系統
    |
    認知負擔：低（只需理解介面契約）
```

### LSP（里氏替換原則）

**傳統解釋**：子類別可以替換父類別。

**認知負擔視角**：使用者不需要知道具體實作，減少需要考慮的情況。

### ISP（介面隔離原則）

**傳統解釋**：不應該強迫依賴不需要的方法。

**認知負擔視角**：介面只包含相關概念，閱讀者不需要過濾不相關資訊。

### DIP（依賴反轉原則）

**傳統解釋**：高層模組不應依賴低層模組。

**認知負擔視角**：透過抽象隔離複雜度，閱讀者可以分層理解系統。

---

**Last Updated**: 2026-06-14
**Version**: 1.0.0 — 從 cognitive-load-design-methodology.md 外移：五大來源完整程式碼範例 + SOLID 五原則認知負擔視角詳解（1.0.0-W8-020.8）
