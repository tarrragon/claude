---
title: "BDD 測試方法論"
date: 2025-10-13
draft: false
description: "行為驅動開發測試策略，整合 Clean Architecture 和 TDD 流程，透過測試行為而非實作降低維護成本"
tags: ["測試", "BDD", "方法論", "Clean Architecture", "TDD"]
---

## 文件資訊

**目的**: 定義 BDD (Behavior-Driven Development) 測試策略，說明如何整合到 Clean Architecture 和 TDD 四階段流程，透過測試行為而非實作細節來降低測試維護成本並提升需求追溯性。

**適用對象**:

- 開發人員 - 設計和撰寫 BDD 測試
- 專案經理 - 理解 BDD 如何支持敏捷開發
- 架構師 - 設計測試架構和策略
- Code Reviewer - 審查測試品質

**關鍵概念**:

- Given-When-Then 場景描述
- 測試行為而非實作
- UseCase 層為 BDD 核心應用層
- 混合測試策略（BDD + 單元測試）

---

## 第一章：方法論概述

### 1.1 BDD 的核心定位

**立場宣告**：

BDD (Behavior-Driven Development) 是行為驅動的測試策略。BDD 不是 TDD 的替代，而是 TDD 的演進。

**我們接受**：

- 測試必須驗證系統行為
- 測試必須從使用者視角出發
- 測試必須使用業務語言描述

**我們拒絕**：

- 測試實作細節的做法
- 過度耦合實作的測試
- 技術術語充斥的測試描述

### 1.2 核心價值主張

BDD 解決三個關鍵問題：

**問題 1: 測試維護成本高**

傳統單元測試緊密耦合實作細節。當重構程式碼時，即使行為未改變，測試仍需要大量修改。

✅ **BDD 解決方式**：測試行為而非實作，重構時測試保持穩定。

**問題 2: 需求追溯困難**

測試程式碼充滿技術細節，無法直接對應業務需求。產品經理和業務人員無法理解測試覆蓋的範圍。

✅ **BDD 解決方式**：Given-When-Then 場景即是需求文檔，測試即規格。

**問題 3: 團隊協作溝通成本**

開發人員、測試人員和業務人員使用不同語言描述系統行為，造成理解落差和誤解。

✅ **BDD 解決方式**：統一使用業務語言，建立共通的溝通基礎。

### 1.3 與現有流程的關係

BDD 不是獨立的開發方法，而是整合到現有流程：

```
Clean Architecture（架構模式）
    ↓
TDD 四階段流程（開發流程）
    ↓
BDD 測試策略（測試設計）
```

**整合原則**：

- Clean Architecture 定義架構分層
- TDD 定義開發節奏（測試先行）
- BDD 定義測試內容（測試什麼、如何測試）

---

## 第二章：BDD 核心原則

### 2.1 定義與邊界

**定義**：

BDD 是一種測試設計策略，要求測試必須描述系統的「行為」而非「實作」。行為是從使用者視角觀察到的系統反應，實作是程式內部的技術細節。

**邊界**：

BDD 包含：

- 使用者可觀察的系統行為
- 業務規則的執行結果
- 系統狀態的變化
- 跨元件的協作流程

BDD 不包含：

- 類別內部的私有方法
- 資料結構的實作細節
- 演算法的實作步驟
- 框架或工具的使用方式

### 2.2 Given-When-Then 結構

BDD 使用 Given-When-Then 結構描述測試場景：

**Given（前置條件）**：

**定義**：系統的初始狀態，包含必要的資料和環境設置。

**規範**：

- 必須明確且完整
- 必須可重現
- 必須與 When 和 Then 相關

**When（觸發動作）**：

**定義**：使用者對系統執行的操作或系統接收到的事件。

**規範**：

- 必須是單一明確的動作
- 必須使用業務語言
- 必須代表使用者意圖

**Then（預期結果）**：

**定義**：系統執行動作後的狀態變化或輸出結果。

**規範**：

- 必須可驗證
- 必須是可觀察的行為
- 必須聚焦業務價值

### 2.3 行為 vs 實作：判斷標準

**判斷方法**：

使用「使用者能否觀察到」作為判斷標準：

| 問題 | 是行為 | 是實作 |
|------|--------|--------|
| 使用者能直接觀察到嗎？ | ✅ 是 | ❌ 否 |
| 改變實作方式會影響嗎？ | ❌ 否 | ✅ 是 |
| 產品經理需要關心嗎？ | ✅ 是 | ❌ 否 |

**範例對比**：

❌ **錯誤：測試實作**

```dart
test('OrderRepository.save should call database.insert', () {
  // 測試實作細節：使用哪個方法、如何呼叫
  repository.save(order);
  verify(database.insert('orders', order.toJson()));
});
```

✅ **正確：測試行為**

```dart
test('使用者提交訂單 - 訂單成功儲存', () {
  // Given: 使用者已選擇商品並填寫完整資訊
  final order = validOrder;
  
  // When: 使用者提交訂單
  final result = await submitOrderUseCase.execute(order);
  
  // Then: 系統確認訂單已儲存
  expect(result.isSuccess, true);
  expect(result.orderId, isNotEmpty);
});
```

**差異說明**：

- 錯誤範例測試「如何儲存」（實作細節）
- 正確範例測試「訂單是否成功儲存」（行為結果）

### 2.4 使用者視角原則

**定義**：

所有測試場景必須從使用者視角描述，而非從系統內部視角。

**判斷標準**：

測試描述中：

- 使用「使用者」、「系統」等業務角色 → 正確
- 使用「Repository」、「Service」等技術元件 → 錯誤

**範例對比**：

❌ **錯誤：技術視角**

```dart
test('當 Repository 回傳 null 時 UseCase 拋出例外', () {
  // 從技術元件角度描述
});
```

✅ **正確：使用者視角**

```dart
test('使用者提交訂單失敗 - 商品庫存不足', () {
  // Given: 商品庫存為 0
  // When: 使用者嘗試提交訂單
  // Then: 系統回應「庫存不足」錯誤
});
```

---

## 第三章：BDD 與 Clean Architecture 整合

### 3.1 分層測試策略

BDD 不是應用於所有架構層級，而是根據層級特性選擇測試策略：

**Layer 3 (UseCase) - BDD 核心應用層** ✅

**定義**：UseCase 層負責編排業務流程，是業務行為的直接體現。

**測試策略**：

- 必須使用 BDD (Given-When-Then)
- 必須測試所有業務場景
- 必須涵蓋正常流程、異常流程、邊界條件

**理由**：UseCase 代表完整的使用者操作流程，是 BDD 的理想應用層。

---

**Layer 5 (Domain Implementation) - 單元測試** ✅

**定義**：Domain 層包含核心業務規則、值物件驗證、實體不變量。

**測試策略**：

- 複雜業務規則 → 必須單元測試
- 值物件驗證 → 必須單元測試
- 實體不變量 → 必須單元測試
- 簡單 CRUD Entity → 依賴 UseCase 層測試

**理由**：Domain 層的複雜邏輯需要細緻的邊界條件測試，單元測試更適合。

---

**Layer 2 (Application/Behavior) - 選擇性測試** ⚠️

**定義**：Behavior 層負責 ViewModel 轉換和事件處理。

**測試策略**：

- 複雜轉換邏輯 → 單元測試
- 多步驟狀態管理 → 單元測試
- 簡單 getter/setter → 依賴 UseCase 層測試
- 直接映射 → 依賴 UseCase 層測試

**理由**：只有複雜邏輯需要獨立測試，簡單轉換由上層測試覆蓋。

---

**Layer 1 (UI/Presentation) - 整合測試** ⚠️

**定義**：UI 層負責視覺呈現和使用者互動。

**測試策略**：

- 關鍵互動流程 → 整合測試
- 簡單頁面 → 人工測試

**理由**：UI 測試成本高，只測試關鍵路徑。

---

**Layer 4 (Domain Events/Interfaces) - 不測試** ❌

**定義**：Interface 層只定義契約，沒有實作邏輯。

**測試策略**：

- 介面定義 → 不需要測試
- 由實作層測試來驗證契約

**理由**：介面本身沒有可測試的行為。

### 3.2 依賴倒置的測試實現

**原則**：

測試 UseCase 時，必須透過 Interface (Port) mock 外層依賴，不直接依賴具體實作。

**判斷標準**：

| 依賴類型 | Mock 策略 | 理由 |
|----------|-----------|------|
| Repository (Interface) | ✅ Mock | 外層依賴，測試不關心實作 |
| Service (Interface) | ✅ Mock | 外層依賴，隔離外部系統 |
| Event Publisher (Interface) | ✅ Mock | 外層依賴，驗證事件發布 |
| Domain Entity | ❌ 不 Mock | 內層邏輯，直接使用真實物件 |
| Value Object | ❌ 不 Mock | 內層邏輯，直接使用真實物件 |

**範例**：

✅ **正確：只 Mock 外層依賴**

```dart
test('使用者提交訂單成功', () {
  // Given: Mock Repository (外層依賴)
  final mockRepository = MockOrderRepository();
  when(mockRepository.save(any))
      .thenAnswer((_) async => SaveResult.success('order-123'));
  
  // 使用真實的 Domain Entity (內層邏輯)
  final order = Order(
    amount: OrderAmount(100),
    userId: UserId('user-001'),
  );
  
  final useCase = SubmitOrderUseCase(repository: mockRepository);
  
  // When: 執行 UseCase
  final result = await useCase.execute(order);
  
  // Then: 驗證行為
  expect(result.isSuccess, true);
  expect(result.orderId, 'order-123');
});
```

❌ **錯誤：Mock 內層邏輯**

```dart
test('使用者提交訂單成功', () {
  // 錯誤：Mock Domain Entity
  final mockOrder = MockOrder();
  when(mockOrder.validate()).thenReturn(true);
  
  // 這樣測試失去意義，沒有測試到真實的業務邏輯
});
```

### 3.3 測試的依賴方向

**原則**：

測試的依賴方向必須與架構的依賴方向一致：

```
測試層級：
Test Layer 3 (UseCase) → Mock Layer 4 (Interface)
                        → Use Real Layer 5 (Domain)
```

**驗證方法**：

檢查測試程式碼的 import：

- ✅ 可以 import UseCase
- ✅ 可以 import Interface
- ✅ 可以 import Domain Entity
- ❌ 禁止 import Repository 實作
- ❌ 禁止 import Service 實作

---

## 第四章：BDD 與 TDD 四階段流程整合

### 4.1 整合概覽

BDD 融入 TDD 四階段流程：

```text
階段 1: 功能設計 → 提取行為場景
階段 2: 測試設計 → 撰寫 Given-When-Then
階段 3: 實作策略 → 測試先行
階段 4: 實作與重構 → 保持測試穩定
```

### 4.2 階段 1：功能設計 - 提取行為場景

**目標**：從需求中識別使用者行為場景。

**執行步驟**：

1. 閱讀需求描述
2. 識別使用者角色
3. 列出使用者操作
4. 定義預期結果

**範例**：

需求：「使用者可以提交訂單」

提取場景：

```
場景 1: 使用者提交訂單成功（正常流程）
  Given: 使用者已選擇商品且填寫完整資訊
  When: 使用者點擊「提交訂單」
  Then: 系統顯示「訂單提交成功」並產生訂單編號

場景 2: 使用者提交訂單失敗 - 商品庫存不足（異常流程）
  Given: 選擇的商品庫存為 0
  When: 使用者點擊「提交訂單」
  Then: 系統顯示「商品庫存不足」錯誤訊息

場景 3: 使用者提交訂單失敗 - 訂單金額為 0（邊界條件）
  Given: 訂單總金額為 0
  When: 使用者點擊「提交訂單」
  Then: 系統顯示「訂單金額必須大於 0」錯誤訊息
```

**驗證標準**：

- [ ] 每個場景都代表一個可獨立驗證的行為
- [ ] 涵蓋正常流程、異常流程、邊界條件
- [ ] 使用業務語言而非技術術語

### 4.3 階段 2：測試設計 - 撰寫 Given-When-Then

**目標**：將行為場景轉換為可執行的測試程式碼。

**執行步驟**：

1. 為每個場景建立測試案例
2. 實作 Given（準備測試資料和 Mock）
3. 實作 When（呼叫 UseCase）
4. 實作 Then（驗證結果）

**範例**：

```dart
group('SubmitOrderUseCase', () {
  late MockOrderRepository mockRepository;
  late MockInventoryService mockInventoryService;
  late SubmitOrderUseCase useCase;
  
  setUp(() {
    mockRepository = MockOrderRepository();
    mockInventoryService = MockInventoryService();
    useCase = SubmitOrderUseCase(
      repository: mockRepository,
      inventoryService: mockInventoryService,
    );
  });
  
  test('使用者提交訂單成功', () async {
    // Given: 使用者已選擇商品且填寫完整資訊
    final order = Order(
      amount: OrderAmount(100),
      userId: UserId('user-001'),
      items: [OrderItem(productId: 'prod-001', quantity: 1)],
    );
    
    when(mockInventoryService.checkStock(any))
        .thenAnswer((_) async => StockStatus.available);
    when(mockRepository.save(any))
        .thenAnswer((_) async => SaveResult.success('order-123'));
    
    // When: 使用者點擊「提交訂單」
    final result = await useCase.execute(order);
    
    // Then: 系統顯示「訂單提交成功」並產生訂單編號
    expect(result.isSuccess, true);
    expect(result.orderId, 'order-123');
    expect(result.message, '訂單提交成功');
  });
  
  test('使用者提交訂單失敗 - 商品庫存不足', () async {
    // Given: 選擇的商品庫存為 0
    final order = Order(
      amount: OrderAmount(100),
      userId: UserId('user-001'),
      items: [OrderItem(productId: 'prod-001', quantity: 1)],
    );
    
    when(mockInventoryService.checkStock(any))
        .thenAnswer((_) async => StockStatus.outOfStock);
    
    // When: 使用者點擊「提交訂單」
    final result = await useCase.execute(order);
    
    // Then: 系統顯示「商品庫存不足」錯誤訊息
    expect(result.isSuccess, false);
    expect(result.error, '商品庫存不足');
  });
});
```

### 4.4 階段 3：實作策略 - 測試先行

**原則**：

必須先完成所有測試場景，再開始實作 UseCase。

**執行順序**：

1. 撰寫所有測試場景（此時測試會失敗）
2. 執行測試，確認測試失敗（Red）
3. 實作 UseCase，讓測試通過（Green）
4. 重構程式碼，保持測試通過（Refactor）

**驗證方法**：

在實作前檢查：

- [ ] 所有場景都有對應測試
- [ ] 測試執行會失敗（因為尚未實作）
- [ ] 測試失敗原因是「UseCase 未實作」而非「測試寫錯」

### 4.5 階段 4：實作與重構 - 保持測試穩定

**原則**：

重構程式碼時，行為測試必須保持穩定。如果重構導致測試修改，表示測試耦合實作。

**判斷標準**：

| 變更類型 | 測試是否需要修改 | 判斷 |
|----------|------------------|------|
| 重構內部邏輯 | ❌ 否 | ✅ 正確（測試行為） |
| 改變演算法實作 | ❌ 否 | ✅ 正確（測試行為） |
| 替換 Repository 實作 | ❌ 否 | ✅ 正確（測試行為） |
| 改變業務規則 | ✅ 是 | ✅ 正確（行為改變） |
| 調整錯誤訊息 | ✅ 是 | ✅ 正確（可觀察行為改變） |

**驗證方法**：

重構後檢查：

- [ ] 測試沒有修改就能通過 → 測試聚焦行為（正確）
- [ ] 測試需要修改才能通過 → 測試耦合實作（錯誤）

---

## 第五章：BDD 的優勢

### 5.1 降低測試維護成本

**價值**：

BDD 測試與實作解耦，重構時測試保持穩定，大幅降低維護成本。

**量化效益**：

傳統單元測試：

- 重構內部邏輯 → 修改 10+ 測試
- 替換依賴實作 → 修改 20+ 測試
- 維護成本：高

BDD 測試：

- 重構內部邏輯 → 測試無需修改
- 替換依賴實作 → 測試無需修改
- 維護成本：低

### 5.2 提升需求追溯性

**價值**：

Given-When-Then 場景即是需求文檔，測試即規格。

**實際應用**：

產品經理可以直接閱讀測試程式碼：

```dart
test('使用者提交訂單成功', () {
  // Given: 使用者已選擇商品且填寫完整資訊
  // When: 使用者點擊「提交訂單」
  // Then: 系統顯示「訂單提交成功」並產生訂單編號
});
```

清楚理解系統行為，無需技術背景。

### 5.3 改善團隊協作

**價值**：

統一使用業務語言，建立開發人員、測試人員、產品經理的共通溝通基礎。

**協作流程**：

1. 產品經理定義需求（業務語言）
2. 開發人員撰寫 Given-When-Then 場景（業務語言）
3. 測試人員驗證場景完整性（業務語言）
4. 所有人使用相同語言討論系統行為

### 5.4 提高測試可讀性

**價值**：

場景化描述讓測試易於理解，新成員快速掌握系統行為。

**對比**：

❌ **傳統單元測試**：

```dart
test('test_execute_method_returns_success_when_repository_save_returns_true', () {
  // 測試名稱充滿技術細節
});
```

✅ **BDD 測試**：

```dart
test('使用者提交訂單成功', () {
  // 測試名稱描述業務行為
});
```

---

## 第六章：BDD 的挑戰與應對

### 6.1 挑戰 1：測試覆蓋率盲點風險

**定義**：

BDD 強調測試「重要行為」而非「所有程式碼」，可能導致某些程式碼未被測試覆蓋。

**影響**：

- Domain 層的複雜業務規則可能缺乏直接測試
- 邊界條件可能被遺漏
- 與「新增程式碼 100% 測試覆蓋率」要求產生衝突

**判斷標準**：

| 程式碼類型 | 測試策略 |
|-----------|----------|
| UseCase 業務流程 | ✅ BDD 測試（必須） |
| Domain 複雜業務規則 | ✅ 單元測試（必須） |
| Domain 值物件驗證 | ✅ 單元測試（必須） |
| Domain 簡單 CRUD Entity | ⚠️ 依賴 UseCase 測試 |
| Behavior 簡單轉換 | ⚠️ 依賴 UseCase 測試 |

**彌補策略**：

採用混合測試策略（BDD + 單元測試）：

- UseCase 層：100% BDD 測試
- Domain 層（複雜邏輯）：100% 單元測試
- Behavior 層（複雜轉換）：選擇性單元測試

**驗證方法**：

使用測試覆蓋率工具檢查：

- [ ] UseCase 層：100% 行為場景覆蓋
- [ ] Domain 層（複雜邏輯）：100% 程式碼覆蓋率
- [ ] 整體專案：80% 程式碼覆蓋率

### 6.2 挑戰 2：學習曲線和團隊適應成本

**定義**：

從「測試實作」轉向「測試行為」需要思維轉換，團隊需要時間適應。

**影響**：

- 初期可能寫出「假行為測試」（實際測試實作）
- 不同開發者對「行為」的理解不一致
- Code Review 需要花更多時間糾正

**彌補策略 1：建立 BDD 撰寫規範文件**

建立內部規範，包含：

- Given-When-Then 範例庫
- 常見錯誤範例（what NOT to do）
- 判斷清單：「這是測試行為還是實作？」

**彌補策略 2：團隊培訓**

- 舉辦 BDD 工作坊
- 前幾個 Sprint 由資深成員 pair programming
- 建立 BDD 範例專案供參考

**彌補策略 3：提供測試模板**

為常見場景提供模板：

```dart
// 模板：UseCase 正常流程
test('[業務場景描述] - 成功', () async {
  // Given: [前置條件]
  final input = [準備測試資料];
  [設置 Mock 行為];
  
  // When: [觸發動作]
  final result = await useCase.execute(input);
  
  // Then: [預期結果]
  expect(result.isSuccess, true);
  expect([驗證業務結果]);
});
```

**驗證方法**：

定期檢視測試品質：

- [ ] 測試描述使用業務語言
- [ ] Given-When-Then 結構清晰
- [ ] 沒有測試實作細節

### 6.3 挑戰 3：邊界條件和技術細節容易被忽略

**定義**：

BDD 強調業務場景，可能忽略技術性的邊界條件（null、異常、併發）。

**影響**：

業務場景：「使用者提交訂單成功」

可能遺漏：

- 訂單金額為 0
- 訂單金額為負數
- 訂單金額超過系統上限
- 商品庫存不足
- 網路中斷時的重試機制
- 併發提交同一訂單

**彌補策略 1：在 BDD 場景中顯式列出邊界條件**

每個業務流程必須包含：

```
場景 1: [業務流程] - 成功（正常流程）
場景 2: [業務流程] - 失敗 - [異常情況 1]
場景 3: [業務流程] - 失敗 - [異常情況 2]
場景 4: [業務流程] - 失敗 - [邊界條件 1]
場景 5: [業務流程] - 失敗 - [邊界條件 2]
```

**彌補策略 2：建立技術性測試檢查清單**

測試設計階段必須檢查：

- [ ] Null 值處理
- [ ] 空集合處理
- [ ] 邊界值（0, 負數, 最大值）
- [ ] 異常處理（網路錯誤、超時）
- [ ] 併發場景（如適用）
- [ ] 資料驗證（格式、範圍）

**彌補策略 3：Code Review 重點檢查**

Reviewer 必須檢查：

- [ ] 是否涵蓋 null 檢查
- [ ] 是否處理異常情況
- [ ] 是否測試邊界值

**驗證方法**：

檢查測試清單：

- [ ] 每個 UseCase 都有異常流程測試
- [ ] 每個 UseCase 都有邊界條件測試
- [ ] 技術性檢查清單全部勾選

### 6.4 挑戰 4：與單層修改原則的測試設計挑戰

**定義**：

layered-ticket-methodology 要求「單層修改」，但 BDD 主要集中在 UseCase 層，其他層的 ticket 測試策略不明確。

**影響**：

Layer 2 (Behavior) ticket：新增 ViewModel 轉換邏輯

- 問題：這層的 ticket 要怎麼測試？
- 是否需要寫獨立測試？
- 還是依賴 UseCase 層測試來驗證？

**彌補策略：建立分層測試指引**

明確定義每層的測試策略：

```markdown
Layer 1 (UI) ticket：

- 關鍵互動流程 → 必須整合測試
- 簡單畫面 → 人工測試

Layer 2 (Behavior) ticket：

- 複雜轉換邏輯 → 必須單元測試
- 簡單轉換 → 依賴 UseCase 層測試

Layer 3 (UseCase) ticket：

- 所有業務行為 → 必須 BDD 測試

Layer 4 (Interface) ticket：

- 介面定義 → 不需要測試

Layer 5 (Domain) ticket：

- 複雜業務規則 → 必須單元測試
- 簡單 CRUD → 依賴 UseCase 層測試
```

詳細指引請參考「混合測試策略方法論」。

**驗證方法**：

每個 ticket 必須明確說明：

- [ ] 測試策略（BDD / 單元測試 / 整合測試）
- [ ] 測試範圍（必須測試的場景）
- [ ] 測試依賴（依賴其他層測試或獨立測試）

### 6.5 挑戰 5：測試設置複雜度增加

**定義**：

UseCase 層的 BDD 測試需要 mock 多個依賴（Repository, Service, Event Publisher），測試設置程式碼可能變得冗長。

**影響**：

```dart
test('使用者提交訂單成功', () {
  // 需要設置大量 Mock
  final mockRepository = MockOrderRepository();
  final mockInventoryService = MockInventoryService();
  final mockPaymentService = MockPaymentService();
  final mockEventPublisher = MockEventPublisher();
  
  when(mockRepository.save(any)).thenAnswer(...);
  when(mockInventoryService.checkStock(any)).thenAnswer(...);
  when(mockPaymentService.processPayment(any)).thenAnswer(...);
  when(mockEventPublisher.publish(any)).thenAnswer(...);
  
  // 準備複雜的測試資料
  final order = Order(...);
  
  // 實際測試邏輯
  // ...
});
```

測試設置佔據大量程式碼，降低可讀性。

**彌補策略 1：建立 Test Helper**

```dart
class UseCaseTestHelper {
  static MockOrderRepository createMockRepository({
    required SaveResult saveResult,
  }) {
    final mock = MockOrderRepository();
    when(mock.save(any)).thenAnswer((_) async => saveResult);
    return mock;
  }
  
  static MockInventoryService createMockInventoryService({
    required StockStatus stockStatus,
  }) {
    final mock = MockInventoryService();
    when(mock.checkStock(any)).thenAnswer((_) async => stockStatus);
    return mock;
  }
}

// 使用 Helper
test('使用者提交訂單成功', () {
  final mockRepository = UseCaseTestHelper.createMockRepository(
    saveResult: SaveResult.success('order-123'),
  );
  final mockInventory = UseCaseTestHelper.createMockInventoryService(
    stockStatus: StockStatus.available,
  );
  
  // 測試程式碼更簡潔
});
```

**彌補策略 2：使用 Builder Pattern 建立測試資料**

```dart
class OrderBuilder {
  int _amount = 100;
  String _userId = 'user-001';
  List<OrderItem> _items = [];
  
  OrderBuilder withAmount(int amount) {
    _amount = amount;
    return this;
  }
  
  OrderBuilder withUserId(String userId) {
    _userId = userId;
    return this;
  }
  
  OrderBuilder withItems(List<OrderItem> items) {
    _items = items;
    return this;
  }
  
  Order build() {
    return Order(
      amount: OrderAmount(_amount),
      userId: UserId(_userId),
      items: _items,
    );
  }
}

// 使用 Builder
test('使用者提交訂單成功', () {
  final order = OrderBuilder()
      .withAmount(100)
      .withUserId('user-001')
      .build();
  
  // 測試程式碼更流暢
});
```

**彌補策略 3：共用測試設置邏輯**

```dart
group('SubmitOrderUseCase', () {
  late MockOrderRepository mockRepository;
  late MockInventoryService mockInventoryService;
  late SubmitOrderUseCase useCase;
  
  setUp(() {
    // 共用設置邏輯
    mockRepository = MockOrderRepository();
    mockInventoryService = MockInventoryService();
    useCase = SubmitOrderUseCase(
      repository: mockRepository,
      inventoryService: mockInventoryService,
    );
  });
  
  tearDown(() {
    // 清理邏輯
  });
  
  test('場景 1', () {
    // 只設置此場景特定的 Mock 行為
  });
  
  test('場景 2', () {
    // 只設置此場景特定的 Mock 行為
  });
});
```

**驗證方法**：

檢查測試程式碼：

- [ ] 使用 Test Helper 減少重複設置
- [ ] 使用 Builder Pattern 建立測試資料
- [ ] 使用 setUp/tearDown 共用邏輯
- [ ] 測試設置程式碼不超過實際測試邏輯

### 6.6 挑戰 6：行為粒度難以把握

**定義**：

「一個行為」的粒度界定模糊，粒度太粗或太細都有問題。

**影響**：

粒度太粗：

- 測試失敗時難以定位問題
- 一個測試涵蓋多個行為

粒度太細：

- 接近單元測試，失去 BDD 優勢
- 測試數量爆炸

**範例**：

「使用者下訂單」是一個行為？
還是應該拆分為：

- 使用者選擇商品
- 使用者填寫配送資訊
- 使用者選擇付款方式
- 使用者確認訂單

**彌補策略：一個 UseCase = 一個核心行為**

**判斷標準**：

| 粒度判斷 | UseCase 數量 | 測試粒度 |
|----------|-------------|----------|
| 一個完整業務流程 | 1 個 UseCase | ✅ 正確 |
| 業務流程的每個步驟 | 多個 UseCase | ❌ 粒度過細 |
| 多個業務流程合併 | 1 個 UseCase | ❌ 粒度過粗 |

**範例**：

✅ **正確粒度**：

```
SubmitOrderUseCase（一個完整流程）
  - test('使用者提交訂單成功')
  - test('使用者提交訂單失敗 - 庫存不足')
  - test('使用者提交訂單失敗 - 金額為 0')
```

❌ **粒度過細**：

```
SelectProductUseCase
ValidateProductUseCase
CalculateAmountUseCase
ProcessPaymentUseCase
SaveOrderUseCase
// 拆分太細，失去業務完整性
```

❌ **粒度過粗**：

```
OrderManagementUseCase（涵蓋所有訂單操作）
  - test('使用者提交訂單')
  - test('使用者取消訂單')
  - test('使用者查詢訂單')
  - test('使用者修改訂單')
// 太多行為在同一個 UseCase
```

**驗證方法**：

檢查 UseCase 設計：

- [ ] 一個 UseCase 代表一個使用者意圖
- [ ] UseCase 名稱是動詞開頭（Submit, Cancel, Query）
- [ ] 測試場景都屬於同一個業務流程

### 6.7 挑戰 7：業務需求變更時的測試維護

**定義**：

雖然 BDD 減少了與實作的耦合，但業務需求變更時，測試場景仍需要更新。

**影響**：

業務需求變更：「訂單金額滿 1000 元免運費」

需要更新的測試：

- 所有「提交訂單」相關的測試場景
- 所有「計算訂單總額」相關的測試
- 可能影響多個 UseCase

**彌補策略 1：使用參數化測試**

```dart
@parameterized([
  [999, false],   // 金額, 是否免運費
  [1000, true],
  [1001, true],
  [0, false],
])
test('訂單金額與免運費規則', (int amount, bool shouldFreeShipping) {
  // Given
  final order = OrderBuilder().withAmount(amount).build();
  
  // When
  final result = await useCase.execute(order);
  
  // Then
  expect(result.hasFreeShipping, shouldFreeShipping);
});
```

**彌補策略 2：集中管理業務規則**

```dart
// business_rules.dart
class OrderBusinessRules {
  static const int freeShippingThreshold = 1000;
  static const int maxOrderAmount = 100000;
  static const int minOrderAmount = 1;
}

// 測試中使用
test('訂單金額滿免運門檻可免運費', () {
  final order = OrderBuilder()
      .withAmount(OrderBusinessRules.freeShippingThreshold)
      .build();
  
  // 當業務規則改變，只需修改常數定義
});
```

**彌補策略 3：在 ticket 中評估測試影響範圍**

需求變更 ticket 必須列出：

```markdown
### 測試影響評估
- 受影響的 UseCase: SubmitOrderUseCase, CalculateOrderTotalUseCase
- 需要新增的測試場景: [列出新場景]
- 需要修改的測試場景: [列出修改項目]
- 需要刪除的測試場景: [列出刪除項目]
```

**驗證方法**：

需求變更時檢查：

- [ ] 已識別所有受影響的 UseCase
- [ ] 已更新所有相關測試場景
- [ ] 使用參數化測試減少重複
- [ ] 業務規則集中管理

---

## 第七章：執行原則

### 7.1 測試先行原則

**原則**：

行為場景必須先於實作。

**執行順序**：

1. 撰寫 Given-When-Then 場景描述
2. 轉換為測試程式碼
3. 執行測試，確認失敗（Red）
4. 實作 UseCase，讓測試通過（Green）
5. 重構程式碼，保持測試通過（Refactor）

**禁止的做法**：

❌ 先實作，後補測試
❌ 邊實作邊寫測試
❌ 實作完成後才設計場景

**驗證方法**：

- [ ] Git commit 歷史顯示測試程式碼先於實作程式碼
- [ ] 第一次 commit：測試程式碼（失敗）
- [ ] 第二次 commit：實作程式碼（測試通過）

### 7.2 場景完整性原則

**原則**：

每個業務流程必須涵蓋正常流程、異常流程和邊界條件。

**判斷標準**：

| 場景類型 | 定義 | 必須程度 |
|----------|------|----------|
| 正常流程 | 使用者操作成功的路徑 | ✅ 必須 |
| 異常流程 | 業務規則驗證失敗 | ✅ 必須 |
| 邊界條件 | 極端值、空值、null | ✅ 必須 |
| 效能場景 | 大量資料、併發 | ⚠️ 視需求 |

**範例檢查清單**：

SubmitOrderUseCase 場景完整性：

- [x] 正常流程：使用者提交訂單成功
- [x] 異常流程：商品庫存不足
- [x] 異常流程：支付失敗
- [x] 邊界條件：訂單金額為 0
- [x] 邊界條件：訂單金額為負數
- [x] 邊界條件：訂單金額超過上限
- [x] 邊界條件：null 檢查

**驗證方法**：

檢查測試清單：

- [ ] 每個 UseCase 至少有 1 個正常流程測試
- [ ] 每個 UseCase 至少有 2 個異常流程測試
- [ ] 每個 UseCase 至少有 3 個邊界條件測試

### 7.3 Mock 策略原則

**原則**：

只 mock 外層依賴（Interface），不 mock 內層邏輯（Domain Entity, Value Object）。

**判斷標準**：

| 依賴類型 | 位置 | Mock 策略 |
|----------|------|-----------|
| Repository | 外層（Infrastructure） | ✅ 必須 Mock |
| Service | 外層（Infrastructure） | ✅ 必須 Mock |
| Event Publisher | 外層（Infrastructure） | ✅ 必須 Mock |
| Domain Entity | 內層（Domain） | ❌ 禁止 Mock |
| Value Object | 內層（Domain） | ❌ 禁止 Mock |
| Business Rule | 內層（Domain） | ❌ 禁止 Mock |

**理由**：

- Mock 外層依賴：隔離外部系統，測試不依賴資料庫或網路
- 使用真實內層邏輯：確保測試涵蓋真實的業務邏輯

**驗證方法**：

檢查測試程式碼：

- [ ] 所有 Repository 都使用 Mock
- [ ] 所有 Service 都使用 Mock
- [ ] 所有 Domain Entity 都使用真實物件
- [ ] 所有 Value Object 都使用真實物件

### 7.4 測試品質驗證方法

**驗證檢查清單**：

**1. 測試描述檢查**：

- [ ] 測試名稱使用業務語言
- [ ] 測試名稱描述使用者行為
- [ ] 沒有技術術語（Repository, Service, Mock）

**2. 測試結構檢查**：

- [ ] Given-When-Then 結構清晰
- [ ] Given 準備完整的前置條件
- [ ] When 只有單一動作
- [ ] Then 驗證可觀察的結果

**3. 測試獨立性檢查**：

- [ ] 測試可以獨立執行
- [ ] 測試不依賴執行順序
- [ ] 測試不共享可變狀態

**4. Mock 策略檢查**：

- [ ] 只 mock 外層依賴
- [ ] 沒有 mock 內層邏輯
- [ ] Mock 行為設置合理

**5. 場景完整性檢查**：

- [ ] 涵蓋正常流程
- [ ] 涵蓋異常流程
- [ ] 涵蓋邊界條件

---

## 第八章：Given-When-Then 撰寫規範

### 8.1 Given（前置條件）撰寫規範

**定義**：

Given 描述系統的初始狀態，包含必要的資料和環境設置。

**撰寫規範**：

1. **必須明確**：清楚說明前置條件是什麼
2. **必須完整**：包含所有執行 When 所需的資料
3. **必須相關**：只包含與此場景相關的資料

**範例對比**：

❌ **錯誤：前置條件模糊**

```dart
test('使用者提交訂單成功', () {
  // Given: 訂單
  final order = someOrder;
  
  // 不清楚訂單的狀態是什麼
});
```

✅ **正確：前置條件明確**

```dart
test('使用者提交訂單成功', () {
  // Given: 使用者已選擇商品且填寫完整資訊
  final order = Order(
    amount: OrderAmount(100),
    userId: UserId('user-001'),
    items: [OrderItem(productId: 'prod-001', quantity: 1)],
    shippingAddress: Address(city: '台北市', district: '信義區'),
  );
  
  // Given: 商品庫存充足
  when(mockInventoryService.checkStock('prod-001'))
      .thenAnswer((_) async => StockStatus.available);
  
  // Given: Repository 可正常儲存
  when(mockRepository.save(any))
      .thenAnswer((_) async => SaveResult.success('order-123'));
  
  // 清楚描述所有前置條件
});
```

**常見錯誤**：

❌ **錯誤 1：過多無關資料**

```dart
// Given: 準備了一堆測試資料，但只用到其中一小部分
final user = createCompleteUserProfile(); // 100 個欄位
final products = createAllProducts(); // 1000 個商品
// 實際只需要 1 個 user 和 1 個 product
```

❌ **錯誤 2：前置條件不完整**

```dart
// Given: 訂單
final order = Order(...);
// 缺少 Mock 設置，When 執行時會失敗
```

❌ **錯誤 3：前置條件包含業務邏輯**

```dart
// Given
final order = Order(...);
order.validate(); // 不應該在 Given 中執行業務邏輯
order.calculate(); // 業務邏輯應該在 When 中測試
```

### 8.2 When（觸發動作）撰寫規範

**定義**：

When 描述使用者對系統執行的操作或系統接收到的事件。

**撰寫規範**：

1. **必須單一**：一個 When 只有一個動作
2. **必須明確**：清楚說明執行什麼操作
3. **必須使用業務語言**：描述使用者意圖而非技術細節

**範例對比**：

❌ **錯誤：多個動作**

```dart
test('使用者提交訂單成功', () {
  // Given: ...
  
  // When: 使用者提交訂單並確認付款
  final submitResult = await useCase.execute(order);
  final paymentResult = await paymentUseCase.execute(payment);
  
  // 兩個動作，應該拆分為兩個測試
});
```

✅ **正確：單一動作**

```dart
test('使用者提交訂單成功', () {
  // Given: ...
  
  // When: 使用者提交訂單
  final result = await submitOrderUseCase.execute(order);
  
  // Then: ...
});

test('使用者確認付款成功', () {
  // Given: 訂單已提交
  
  // When: 使用者確認付款
  final result = await confirmPaymentUseCase.execute(payment);
  
  // Then: ...
});
```

**常見錯誤**：

❌ **錯誤 1：技術術語**

```dart
// When: 呼叫 Repository 的 save 方法
await repository.save(order);
// 應該描述業務操作，不是技術操作
```

✅ **正確：業務語言**

```dart
// When: 使用者提交訂單
final result = await submitOrderUseCase.execute(order);
```

❌ **錯誤 2：包含驗證邏輯**

```dart
// When
final result = await useCase.execute(order);
expect(result.isSuccess, true); // 驗證應該在 Then
```

### 8.3 Then（預期結果）撰寫規範

**定義**：

Then 描述系統執行動作後的狀態變化或輸出結果。

**撰寫規範**：

1. **必須可驗證**：結果可以透過斷言檢查
2. **必須聚焦行為**：驗證可觀察的結果，不驗證實作細節
3. **必須完整**：驗證所有重要的結果

**範例對比**：

❌ **錯誤：驗證實作細節**

```dart
test('使用者提交訂單成功', () {
  // Given: ...
  // When: ...
  
  // Then: Repository 的 save 方法被呼叫 1 次
  verify(mockRepository.save(any)).called(1);
  
  // 這是驗證實作細節，不是行為
});
```

✅ **正確：驗證行為結果**

```dart
test('使用者提交訂單成功', () {
  // Given: ...
  // When: ...
  
  // Then: 系統確認訂單已儲存並回傳訂單編號
  expect(result.isSuccess, true);
  expect(result.orderId, isNotEmpty);
  expect(result.message, '訂單提交成功');
  
  // 驗證使用者可觀察的結果
});
```

**常見錯誤**：

❌ **錯誤 1：過度驗證**

```dart
// Then: 驗證所有內部方法呼叫
verify(mockRepository.save(any)).called(1);
verify(mockInventoryService.checkStock(any)).called(1);
verify(mockEventPublisher.publish(any)).called(1);
verify(mockLogger.log(any)).called(3);
// 過度關注實作細節
```

✅ **正確：聚焦關鍵結果**

```dart
// Then: 系統確認訂單已儲存
expect(result.isSuccess, true);
expect(result.orderId, isNotEmpty);

// Then: 系統發布訂單已建立事件（如果這是業務需求）
verify(mockEventPublisher.publish(any.having(
  (e) => e.type, 'event type', 'ORDER_CREATED'
))).called(1);
```

❌ **錯誤 2：驗證不完整**

```dart
// Then
expect(result.isSuccess, true);
// 只驗證成功，沒有驗證訂單編號等其他重要結果
```

✅ **正確：驗證完整**

```dart
// Then: 系統確認訂單已儲存並回傳完整資訊
expect(result.isSuccess, true);
expect(result.orderId, isNotEmpty);
expect(result.order.amount, 100);
expect(result.order.status, OrderStatus.submitted);
expect(result.message, '訂單提交成功');
```

---

## 第九章：正反範例

### 9.1 UseCase 測試完整範例

#### 場景：使用者提交訂單

**業務需求**：

- 使用者可以提交訂單
- 系統必須檢查商品庫存
- 系統必須驗證訂單金額
- 系統必須儲存訂單並回傳訂單編號

#### ❌ 錯誤範例 1：測試實作細節

```dart
group('SubmitOrderUseCase - 錯誤範例', () {
  test('test_repository_save_is_called_with_correct_parameters', () {
    // 錯誤：測試名稱充滿技術術語
    
    // Given
    final mockRepository = MockOrderRepository();
    final useCase = SubmitOrderUseCase(repository: mockRepository);
    final order = Order(amount: OrderAmount(100), userId: UserId('user-001'));
    
    when(mockRepository.save(any))
        .thenAnswer((_) async => SaveResult.success('order-123'));
    
    // When
    useCase.execute(order);
    
    // Then: 驗證 Repository 方法呼叫
    verify(mockRepository.save(argThat(
      (arg) => arg.amount == 100 && arg.userId == 'user-001'
    ))).called(1);
    
    // 錯誤：測試關注實作細節（如何呼叫 Repository）
    // 而非業務行為（訂單是否成功提交）
  });
});
```

**問題分析**：

- 測試名稱使用技術術語
- 驗證 Repository 方法呼叫次數和參數
- 重構 Repository 實作時測試會失敗
- 沒有驗證使用者可觀察的結果

#### ❌ 錯誤範例 2：過度 Mock 內層邏輯

```dart
group('SubmitOrderUseCase - 錯誤範例', () {
  test('使用者提交訂單成功', () {
    // Given
    final mockOrder = MockOrder(); // 錯誤：Mock Domain Entity
    final mockAmount = MockOrderAmount(); // 錯誤：Mock Value Object
    final mockRepository = MockOrderRepository();
    
    when(mockOrder.validate()).thenReturn(true);
    when(mockOrder.amount).thenReturn(mockAmount);
    when(mockAmount.value).thenReturn(100);
    
    when(mockRepository.save(mockOrder))
        .thenAnswer((_) async => SaveResult.success('order-123'));
    
    final useCase = SubmitOrderUseCase(repository: mockRepository);
    
    // When
    final result = await useCase.execute(mockOrder);
    
    // Then
    expect(result.isSuccess, true);
    
    // 錯誤：Mock 了 Domain Entity 和 Value Object
    // 沒有測試到真實的業務邏輯驗證
  });
});
```

**問題分析**：

- Mock Domain Entity 失去業務邏輯測試
- Mock Value Object 失去驗證邏輯測試
- 測試變成空殼，沒有實際價值

#### ❌ 錯誤範例 3：場景描述模糊

```dart
group('SubmitOrderUseCase - 錯誤範例', () {
  test('測試提交', () { // 錯誤：描述模糊
    // Given: 訂單 // 錯誤：不清楚訂單狀態
    final order = someOrder;
    
    // When: 執行 // 錯誤：不清楚執行什麼
    final result = await useCase.execute(order);
    
    // Then: 成功 // 錯誤：不清楚成功的定義
    expect(result, isNotNull);
  });
});
```

**問題分析**：

- 測試名稱不清楚測試什麼場景
- Given 沒有明確前置條件
- When 沒有描述使用者操作
- Then 驗證不具體

#### ✅ 正確範例：完整的 BDD 測試

```dart
group('SubmitOrderUseCase', () {
  late MockOrderRepository mockRepository;
  late MockInventoryService mockInventoryService;
  late MockEventPublisher mockEventPublisher;
  late SubmitOrderUseCase useCase;
  
  setUp(() {
    mockRepository = MockOrderRepository();
    mockInventoryService = MockInventoryService();
    mockEventPublisher = MockEventPublisher();
    useCase = SubmitOrderUseCase(
      repository: mockRepository,
      inventoryService: mockInventoryService,
      eventPublisher: mockEventPublisher,
    );
  });
  
  group('正常流程', () {
    test('使用者提交訂單成功', () async {
      // Given: 使用者已選擇商品且填寫完整資訊
      final order = Order(
        amount: OrderAmount(100),
        userId: UserId('user-001'),
        items: [
          OrderItem(productId: 'prod-001', quantity: 2),
        ],
        shippingAddress: Address(city: '台北市', district: '信義區'),
      );
      
      // Given: 商品庫存充足
      when(mockInventoryService.checkStock('prod-001'))
          .thenAnswer((_) async => StockStatus.available);
      
      // Given: Repository 可正常儲存
      when(mockRepository.save(any))
          .thenAnswer((_) async => SaveResult.success('order-123'));
      
      // When: 使用者點擊「提交訂單」
      final result = await useCase.execute(order);
      
      // Then: 系統確認訂單已儲存並回傳訂單編號
      expect(result.isSuccess, true);
      expect(result.orderId, 'order-123');
      expect(result.message, '訂單提交成功');
      
      // Then: 系統發布「訂單已建立」事件
      verify(mockEventPublisher.publish(any.having(
        (e) => e.type, 'event type', EventType.orderCreated,
      ))).called(1);
    });
  });
  
  group('異常流程', () {
    test('使用者提交訂單失敗 - 商品庫存不足', () async {
      // Given: 選擇的商品庫存為 0
      final order = Order(
        amount: OrderAmount(100),
        userId: UserId('user-001'),
        items: [
          OrderItem(productId: 'prod-001', quantity: 2),
        ],
      );
      
      when(mockInventoryService.checkStock('prod-001'))
          .thenAnswer((_) async => StockStatus.outOfStock);
      
      // When: 使用者點擊「提交訂單」
      final result = await useCase.execute(order);
      
      // Then: 系統回應「商品庫存不足」錯誤訊息
      expect(result.isSuccess, false);
      expect(result.error, ErrorType.outOfStock);
      expect(result.message, '商品庫存不足');
      
      // Then: 系統不儲存訂單
      verifyNever(mockRepository.save(any));
    });
    
    test('使用者提交訂單失敗 - Repository 儲存失敗', () async {
      // Given: Repository 無法儲存（網路錯誤）
      final order = Order(
        amount: OrderAmount(100),
        userId: UserId('user-001'),
        items: [OrderItem(productId: 'prod-001', quantity: 1)],
      );
      
      when(mockInventoryService.checkStock(any))
          .thenAnswer((_) async => StockStatus.available);
      when(mockRepository.save(any))
          .thenAnswer((_) async => SaveResult.failure('網路連線失敗'));
      
      // When: 使用者點擊「提交訂單」
      final result = await useCase.execute(order);
      
      // Then: 系統回應「訂單提交失敗」錯誤訊息
      expect(result.isSuccess, false);
      expect(result.error, ErrorType.saveFailed);
      expect(result.message, '訂單提交失敗，請稍後再試');
    });
  });
  
  group('邊界條件', () {
    test('使用者提交訂單失敗 - 訂單金額為 0', () async {
      // Given: 訂單總金額為 0
      final order = Order(
        amount: OrderAmount(0),
        userId: UserId('user-001'),
        items: [],
      );
      
      // When: 使用者點擊「提交訂單」
      final result = await useCase.execute(order);
      
      // Then: 系統回應「訂單金額必須大於 0」錯誤訊息
      expect(result.isSuccess, false);
      expect(result.error, ErrorType.invalidAmount);
      expect(result.message, '訂單金額必須大於 0');
    });
    
    test('使用者提交訂單失敗 - 訂單金額為負數', () async {
      // Given: 訂單金額為負數（異常資料）
      expect(
        () => Order(amount: OrderAmount(-100), userId: UserId('user-001')),
        throwsA(isA<InvalidAmountException>()),
      );
      
      // 驗證：Value Object 在建立時就拋出例外
    });
    
    test('使用者提交訂單失敗 - 訂單金額超過上限', () async {
      // Given: 訂單金額超過系統上限（100萬）
      final order = Order(
        amount: OrderAmount(1000001),
        userId: UserId('user-001'),
        items: [OrderItem(productId: 'prod-001', quantity: 10000)],
      );
      
      // When: 使用者點擊「提交訂單」
      final result = await useCase.execute(order);
      
      // Then: 系統回應「訂單金額超過上限」錯誤訊息
      expect(result.isSuccess, false);
      expect(result.error, ErrorType.amountExceedsLimit);
      expect(result.message, '訂單金額不可超過 1,000,000 元');
    });
    
    test('使用者提交訂單失敗 - UserId 為 null', () async {
      // Given: UserId 為 null（異常資料）
      expect(
        () => Order(amount: OrderAmount(100), userId: null),
        throwsA(isA<ArgumentError>()),
      );
      
      // 驗證：Entity 在建立時就拋出例外
    });
  });
});
```

**正確範例特點**：

- ✅ 測試名稱使用業務語言
- ✅ Given-When-Then 結構清晰
- ✅ 只 Mock 外層依賴（Repository, Service）
- ✅ 使用真實的 Domain Entity 和 Value Object
- ✅ 涵蓋正常流程、異常流程、邊界條件
- ✅ 驗證使用者可觀察的結果
- ✅ 測試與實作解耦，重構時測試穩定

### 9.2 Mock 策略對比

#### ❌ 錯誤：過度驗證實作細節

```dart
test('使用者提交訂單成功', () async {
  // Given, When: ...
  
  // Then: 過度驗證內部呼叫
  verify(mockInventoryService.checkStock('prod-001')).called(1);
  verify(mockRepository.save(any)).called(1);
  verify(mockEventPublisher.publish(any)).called(1);
  verify(mockLogger.log(any, level: LogLevel.info)).called(3);
  
  // 問題：測試關注太多實作細節
  // 重構時（例如改變呼叫順序）測試會失敗
});
```

#### ✅ 正確：只驗證關鍵行為

```dart
test('使用者提交訂單成功', () async {
  // Given, When: ...
  
  // Then: 只驗證使用者可觀察的結果
  expect(result.isSuccess, true);
  expect(result.orderId, isNotEmpty);
  expect(result.message, '訂單提交成功');
  
  // Then: 只驗證關鍵的業務行為（如果業務需求明確要求）
  // 例如：「系統必須發布訂單已建立事件供其他模組訂閱」
  verify(mockEventPublisher.publish(any.having(
    (e) => e.type, 'event type', EventType.orderCreated,
  ))).called(1);
  
  // 不驗證內部實作細節（如何呼叫 Repository、Logger）
});
```

---

## 結論

BDD 是測試設計策略，讓 TDD 和 Clean Architecture 更好。

**核心定位**：

BDD 透過測試行為而非實作，降低測試與程式碼的耦合，讓重構更安全、測試更穩定。

**實際功能**：

- 降低測試維護成本：重構時測試無需修改
- 提升需求追溯性：Given-When-Then 即是需求文檔
- 改善團隊協作：統一使用業務語言溝通
- 提高測試可讀性：場景化描述易於理解

**執行準則**：

我們將 BDD 整合到現有流程，而非取代：

- Clean Architecture 定義架構分層
- TDD 四階段流程定義開發節奏
- BDD 定義測試內容和撰寫規範

我們採用混合測試策略：

- UseCase 層：100% BDD 測試
- Domain 層（複雜邏輯）：100% 單元測試
- Behavior 層（複雜轉換）：選擇性單元測試
- UI 層（關鍵流程）：整合測試

我們透過明確的判斷標準、完整的範例和嚴格的驗證機制，確保 BDD 測試品質。

詳細的實踐指引請參考「混合測試策略方法論」。
