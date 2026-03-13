# 行為優先 TDD 方法論

## 核心概念

測試耦合到行為（Module API），而非結構（Class Methods）。重構時測試保持穩定。

**Sociable Unit Tests**（推薦）：
- Unit = Module（1 個或多個類別）
- 只 Mock 外部依賴（Database, File System, External Services）
- 使用真實 Domain Entities

**Solitary Unit Tests**（特殊情況）：
- Unit = Class
- Mock 所有協作者
- 測試脆弱、維護成本高

## 執行步驟

1. **判斷測試策略**：優先使用 Sociable，只在數學演算法/加密系統才用 Solitary
2. **定義測試邊界**：測試透過 Module/UseCase 的 Public API 互動
3. **Mock 策略**：只 Mock Repository/Gateway 等外部依賴，Domain Entities 使用真實物件
4. **撰寫測試**：Given-When-Then 格式，業務語言描述

## 檢查清單

### 測試耦合檢查

- [ ] 測試只呼叫 Module/UseCase 的 Public API
- [ ] 測試不知道內部有哪些類別
- [ ] 只 Mock 外部依賴（Repository, Gateway）
- [ ] Domain Entities 使用真實物件

### 重構安全性驗證

- [ ] 改變內部邏輯 → 測試不變
- [ ] 調整類別結構 → 測試不變
- [ ] 重新命名內部方法 → 測試不變

全部「測試不變」= Sociable（正確）
任何「測試需改」= Solitary（重新設計）

### 適用場景

| 專案類型 | 推薦 |
|---------|------|
| 業務應用程式 | Sociable |
| CRUD/Web API | Sociable |
| 數學演算法 | Solitary |
| 金融計算 | 混合 |

## 前置條件與 Sociable Unit Tests 的關係（v1.2.0 新增）

### 核心連結

Sociable Unit Tests 的「使用真實 Domain Entities」原則，直接要求測試必須先建立真實的前置狀態。這不只是程式碼風格的選擇，而是確保前置條件驗證有意義的基礎。

| 測試類型 | 前置條件來源 | 前置條件可驗性 |
|---------|------------|--------------|
| Sociable（真實物件） | 透過真實 Domain Entity 建立，狀態真實可驗 | 高（前置條件即是真實業務狀態） |
| Solitary（Mock 一切） | Mock 物件回傳預設值，狀態是假設的 | 低（前置條件只是測試假設，不反映真實行為） |

**結論**：Sociable Unit Tests 使前置條件驗證有實際意義——「按鈕存在」是真實渲染的結果，而非 Mock 的預設值。

### 行為推演在單元測試中的應用

Sociable Unit Tests 對應行為鏈推演的三個層次：

| 行為鏈層次 | Sociable Unit Tests 對應 |
|----------|------------------------|
| A（前置條件） | 透過 UseCase 或 Repository Mock 準備真實資料，驗證初始狀態 |
| B（行為觸發） | 呼叫 Module 的 Public API（UseCase.execute()） |
| C（結果確認） | 驗證 Mock Repository 接收到正確的呼叫、或驗證回傳的 Domain Entity 狀態 |

### 前置條件建立的正確模式

```
// Sociable 測試中的前置條件建立（正確）
Given:
  - 建立真實 Book Entity（不是 Mock）
  - 設定 MockBookRepository 回傳此 Entity
  - 驗證 repository.findById() 確實會回傳此 Entity（前置驗證）

When:
  - 呼叫 GetBookDetailUseCase.execute(bookId)

Then:
  - 回傳的 BookDetail 包含正確的 title 和 author
```

**禁止模式**：直接假設 Mock 會回傳正確值而不驗證 Mock 設定是否正確。

### Sociable Unit Tests 行為推演檢查清單

- [ ] 測試的前置狀態是透過真實物件建立的，而非 Mock 硬編碼
- [ ] Mock 的回傳值符合真實業務邏輯（不是任意假值）
- [ ] 每個 Given 步驟有對應的驗證斷言（確認前置條件確實成立）
- [ ] 行為觸發（When）只呼叫 Module Public API，不呼叫內部方法
- [ ] 結果確認（Then）驗證的是行為的可觀察輸出，不是 Mock 被呼叫的次數

---

## 路徑驅動測試（v1.3.0 新增）

> 來源：2026-03 多廚房印表機列印功能——28 個測試全過，上實機後陸續發現四個 Bug。

### Bug 遮蔽模式

同一條執行路徑上不同深度的 Bug 會互相遮蔽。程式走到第一個錯誤就中斷，後面的都被遮蔽。每修一個，程式才能走到下一個。

```
真實路徑：  接收訂單 → 組裝收據 → 列印中心 → 表格列印/文字列印 → 印表機底層
測試路徑：  接收訂單 → （手動構造結果，後面都沒跑）
```

**根因**：測試沒有走過完整的呼叫路徑。問題不在測試數量，而在測試覆蓋的路徑深度。

### 核心原則：從呼叫路徑出發，而非從程式碼結構出發

按「使用者操作觸發了什麼路徑」來規劃測試，而非按「這個 class 有哪些方法」來分配。

```
使用者操作                    要測試的完整路徑
─────────                    ──────────────
追加點餐送出     →  handler.printAppendedOrder
                      → _buildItemPrinterMapping  ← 分派邏輯
                      → buildReceiptLines          ← 收據組裝
                      → printReceiptLines           ← 實際列印
                      → printText / printRow        ← 印表機操作
```

按路徑規劃之後，每個測試案例都會走過完整的鏈路，中間環節的問題自然會被觸發。

### 整合測試與單元測試的分工

| | 單元測試 | 整合測試 |
|---|---------|---------|
| 測什麼 | 單一方法的輸入輸出 | 多個元件串接的結果 |
| 假設什麼 | 其他元件是正確的 | 驗證元件之間的銜接 |
| 能抓到什麼 Bug | 演算法邏輯錯誤 | 初始化遺漏、依賴缺失、介面不匹配、狀態傳遞錯誤 |

功能涉及多個元件協作時，只有單元測試是不夠的。整合測試才能抓到元件之間的銜接問題。

---

## try-catch 測試策略（v1.3.0 新增）

### 問題模式

try-catch 範圍太大時，會把程式碼 bug 和預期的執行期錯誤混在一起處理，導致 bug 在開發和測試階段都沒有任何異常跡象。

```dart
// 問題寫法：所有錯誤都被吞掉
try {
  final lines = await receiptBuilder.buildReceiptLines(data, template);
  await printCenter.printReceiptLines(lines: lines, printer: printer);
  return true;
} catch (e) {
  return false;
}

// 正確寫法：資料準備不在 try 裡，只攔截特定的預期錯誤
final lines = await receiptBuilder.buildReceiptLines(data, template);
try {
  await printCenter.printReceiptLines(lines: lines, printer: printer);
  return true;
} on PrinterException catch (e) {
  return false;
}
```

### 三個對策

| 對策 | 說明 | 對應問題 |
|------|------|---------|
| 斷言成功路徑的值 | 不只檢查「沒拋錯」，要檢查回傳值是 `true` | 斷言只檢查 `containsKey`，不管值是 true 還是 false |
| 提供完整的依賴 | 讓 try 區塊能完整執行，而非依賴 catch 來「通過」測試 | 缺少依賴被 catch 吞掉，測試照樣通過 |
| 寫專門的失敗測試 | 故意製造失敗條件，驗證錯誤處理行為符合預期 | 無法區分程式碼 bug 和硬體故障 |

### 設計原則

- 區分「預期的執行期錯誤」和「程式碼 bug」，只攔截前者
- 定義專用的 exception 類型，在 IO 邊界包裝，上層只 catch 這個類型
- 資料準備、邏輯運算等步驟不要放在 try-catch 裡面，讓錯誤直接拋出

---

## Fake / Mock 設計原則（v1.3.0 新增）

| | Fake（假實作） | Mock（模擬物件） |
|---|--------------|----------------|
| 適用場景 | 需要跑通完整路徑 | 只需驗證互動次數/參數 |

### Fake 設計確認項目

設計 Fake 時必須確認：

1. 繼承/實作的方法中，有哪些是上層呼叫者**實際會用到的**？
2. 這些方法依賴哪些**內部狀態**（如 `late` 變數）？
3. Fake 的初始化是否正確建立了這些內部狀態？
4. Fake 回傳的資料是否足以讓下游**所有分支**都被觸發？

### 常見錯誤

| 錯誤 | 後果 | 對策 |
|------|------|------|
| 只覆寫子類別自己的方法，沒測繼承的方法 | 上層呼叫繼承方法時，內部狀態未初始化 | 確認上層實際呼叫到的繼承方法也有被測試覆蓋 |
| 回傳資料只覆蓋部分分支 | 某些程式碼路徑從未被執行 | 先確認下游有哪些分支，確認回傳資料能觸發這些分支 |
| 回傳資料缺少邊界值 | 空字串、空列表等邊界情況未測試 | 回傳資料中加入邊界值 |

---

## 測試自我檢查清單（v1.3.0 新增）

寫完測試後對照：

1. 這個測試有走過真實的呼叫路徑嗎？還是只測了資料搬運？
2. 斷言是驗證「值」還是只驗證「存在」？
3. 所有依賴都有提供嗎？缺少的依賴會不會被 try-catch 吞掉？
4. 模擬子類別覆寫的方法之外，繼承的方法有被測到嗎？
5. 模擬元件回傳的資料有觸發下游的所有分支嗎？
6. 邊界值（空字串、空列表、null）有出現在測試資料中嗎？
7. try-catch 的範圍是否只包含 IO 操作？資料準備和邏輯運算是否在 try 外面？
8. 有寫反向測試（故意觸發錯誤）來確認理解了 Bug 的根因嗎？

---

## Reference

### 相關方法論

- [BDD 測試方法論](./bdd-testing-methodology.md) - Given-When-Then 格式與行為鏈式推演
- [混合測試策略方法論](./hybrid-testing-strategy-methodology.md) - 分層測試決策樹

### 外部文獻

- Kent Beck,《Test Driven Development By Example》- TDD 原始定義
- Martin Fowler,《Refactoring》- 重構定義
- Google,《Software Engineering at Google》- 大規模實踐驗證

---

**Last Updated**: 2026-03-12
**Version**: 1.3.0
**Updates**:
- v1.3.0 (2026-03-12): 新增路徑驅動測試、Bug 遮蔽模式、try-catch 測試策略、Fake/Mock 設計原則、自我檢查清單（來源：2026-03 多廚房印表機列印經驗）
- v1.2.0 (2026-03-12): 新增前置條件與 Sociable Unit Tests 的關係、行為推演在單元測試中的應用（0.1.0-W44-002）