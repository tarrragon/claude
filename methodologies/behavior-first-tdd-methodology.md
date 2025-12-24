---
title: "行為優先的TDD方法論 - Sociable Unit Tests實踐指南"
date: 2025-10-16
draft: false
description: "基於Kent Beck、Martin Fowler和Google實踐的行為驅動測試策略，解決TDD痛點根源，透過Sociable Unit Tests實現低維護成本和高重構安全性"
tags: ["TDD", "Sociable Unit Tests", "Behavior Testing", "Kent Beck", "Clean Architecture"]
---

## 文件資訊

**目的**: 揭示TDD痛點的根本原因，說明測試應該耦合到行為而非結構，透過Sociable vs Solitary Unit Tests的對比，提供低維護成本的測試策略。

**適用對象**:
- 開發人員 - 理解TDD痛點並學習正確的測試方法
- 專案經理 - 理解為何TDD會痛苦以及如何避免
- 架構師 - 設計可測試的架構
- 測試教練 - 指導團隊正確實踐TDD

**關鍵概念**:
- Sociable vs Solitary Unit Tests
- Behavior vs Structure
- Executable Specifications
- Test-First vs Test-Last反饋循環

**歷史證據來源**:
- Kent Beck - Test Driven Development By Example
- Martin Fowler - Refactoring: Improving the Design of Existing Code
- Dan North - Introducing BDD
- Google - Software Engineering at Google

**與其他方法論的關係**:
- 提供歷史證據和理論基礎給「BDD測試方法論」
- 提供Sociable Unit Tests概念給「混合測試策略方法論」
- 整合到「TDD協作開發流程」的Phase 2測試設計

---

## 第一章：TDD痛點的根本原因

### 1.1 為什麼TDD是痛苦的？

**問題背景**:

許多軟體開發團隊初次接觸TDD時充滿期待，但實際執行後卻遭遇巨大痛苦，最終放棄TDD。根據實務觀察，主要痛點包括：

1. **測試程式碼量爆炸**: 測試程式碼是production code的2-4倍
2. **重構時測試破裂**: 每次重構都要修改大量測試
3. **測試維護成本高**: 花在維護測試的時間比寫production code還多
4. **測試執行緩慢**: 大量的mock設置導致測試執行速度下降

**關鍵問題**: 這些痛點並非TDD本身的問題，而是**錯誤理解和實踐TDD**的結果。

### 1.2 三大錯誤認知

#### 錯誤認知1: Class是隔離單元

**錯誤觀念**:
```text
每個production class → 一個test class
每個production method → 一個或多個test methods
```

**問題**:
- 這種思維導致測試耦合到類別結構
- 任何類別結構調整都會破壞測試
- Mock所有協作者導致測試程式碼爆炸

**真相**:

**Unit的定義從來不是Class**，而是一個**可獨立驗證的行為單元**（Module）。

**證據**: 即使Wikipedia和大多數網路文章都說「unit = class」，但這與TDD創始人Kent Beck的原始定義不符。

---

#### 錯誤認知2: Unit Tests必然昂貴

**錯誤觀念**:
- 測試程式碼是production code的2-4倍很正常
- 重構時測試破裂很正常
- Unit Tests要花很多時間很正常

**問題**:
- 這種「正常化痛苦」讓團隊接受低效率的測試方法
- 導致「我們沒時間寫測試」的藉口
- 最終測試被視為「可選的nice-to-have」

**真相**:

**正確的TDD不應該痛苦**。如果你感到痛苦，表示你的測試方法錯了。

**證據**: Classical TDD practitioners（Kent Beck, Martin Fowler, Uncle Bob）從來沒有抱怨過測試維護成本過高。

---

#### 錯誤認知3: BDD測試行為，TDD不是

**錯誤觀念**:
- BDD = 測試行為（從使用者視角）
- TDD = 測試類別和方法（從開發者視角）
- 因此BDD和TDD是不同的方法

**問題**:
- 這種二分法導致團隊在壓力下只保留「BDD acceptance tests」
- Unit Tests被視為「可選的」而被丟棄
- 失去快速反饋循環的最大優勢

**真相**:

**TDD和BDD原本都是關於測試行為**。BDD只是修正了TDD中「Test」這個詞造成的命名混淆。

**證據**:
- Kent Beck在《Test Driven Development By Example》第1-2頁就提到「behavior」
- Dan North創造BDD是為了**修正TDD的命名問題**，而非創造新方法

### 1.3 痛點的經濟影響

**量化分析**:

| 指標 | 錯誤實踐TDD | 正確實踐TDD |
|-----|-----------|------------|
| 測試程式碼量 | Production code的2-4倍 | Production code的0.8-1.2倍 |
| 重構時測試修改 | 修改20-50%測試 | 修改0-5%測試 |
| 測試維護時間 | 30-40%開發時間 | 10-15%開發時間 |
| 重構信心 | 低（害怕破壞測試） | 高（測試保證正確性） |
| 開發速度 | 下降30-40% | 提升20-30% |

**結論**: 錯誤的測試方法比不寫測試更糟糕，因為你承擔了測試的成本但沒有得到好處。

---

## 第二章：測試的本質 - Executable Specifications

### 2.1 從Business Needs到Tests的轉換鏈

**完整的需求實現鏈**:

```text
Business Needs (為什麼要建立系統？)
    ↓
Software Requirements (系統需要做什麼？)
    ↓
Tests (Executable Specifications - 用機器語言表達需求)
    ↓
Implementation (滿足需求的一種實現方式)
```

**關鍵洞察**:

> **Tests = Executable Requirements Specifications**

測試不是「驗證實作的工具」，而是**用程式碼表達的需求規格書**。

### 2.2 Requirements vs Implementation的關係

**單向依賴關係**:

```text
Requirements → Implementation ✅
  (需求改變 → 實作必須改變)

Implementation → Requirements ❌
  (實作改變 → 需求不應該改變)
```

**重構的定義** (Martin Fowler):

> "Refactoring is a way of restructuring an existing body of code, altering its **internal structure** without changing its **external behavior**."

**推論**:

| 變更類型 | Requirements改變？ | Tests應該改變？ |
|---------|------------------|---------------|
| 需求變更 | ✅ 是 | ✅ 是 |
| 重構（改變結構） | ❌ 否 | ❌ 否 |
| Bug修復 | ✅ 是（行為不符預期） | ✅ 是 |

**結論**: 如果你在重構時需要修改測試，表示你的測試耦合到了實作結構而非需求行為。

### 2.3 測試耦合的兩種選擇

#### 選擇1: Coupling to Behavior (正確) ✅

```text
Tests ← → [Module API] → Module Implementation
             ↑
         測試只知道API
         不知道內部結構
```

**特性**:
- 測試透過Module的Public API與系統互動
- 測試不知道Module內部有哪些類別
- Module是**黑盒子**
- 可以自由重構內部實作

**結果**:
- ✅ 測試穩定（重構時不破裂）
- ✅ 高ROI（低維護成本）
- ✅ 重構安全（測試保證行為正確）

---

#### 選擇2: Coupling to Structure (錯誤) ❌

```text
Tests → Mock(B) → Class A → Class B
        Mock(C)           ↘ Class C
        Mock(D)           ↘ Class D
          ↑
     測試知道所有內部類別
     測試知道所有協作關係
```

**特性**:
- 測試知道Module內部的每個類別
- 測試Mock所有協作者
- Module是**玻璃盒子**
- 任何結構調整都會破壞測試

**結果**:
- ❌ 測試脆弱（重構時破裂）
- ❌ 低ROI（高維護成本）
- ❌ 重構恐懼（害怕破壞測試）

### 2.4 對比總結表

| 特性 | Coupling to Behavior ✅ | Coupling to Structure ❌ |
|-----|----------------------|----------------------|
| 測試目標 | Module API（需求） | Class Methods（實作） |
| 測試知識 | 只知道Public API | 知道所有內部結構 |
| Mock策略 | 只Mock外部依賴 | Mock所有協作者 |
| 重構影響 | 測試不變 | 測試破裂 |
| 維護成本 | 低 | 高 |
| ROI | 高 | 低 |
| 名稱 | Sociable Unit Tests | Solitary Unit Tests |

---

## 第三章：Sociable vs Solitary Unit Tests

### 3.1 Unit Test的定義問題

**Unit Test的三個要素**:
1. Verifying a **Unit**
2. In **Isolation**
3. **Quickly**

**問題**: 什麼是「Unit」？什麼是「Isolation」？

**答案**: 這兩個詞的定義取決於你屬於哪個TDD流派。

### 3.2 兩大TDD流派

#### Classical TDD (Kent Beck, Martin Fowler, Uncle Bob)

**代表人物**:
- Kent Beck (《Test Driven Development By Example》作者)
- Martin Fowler (《Refactoring》作者)
- Robert C. Martin (Uncle Bob, 《Clean Architecture》作者)

**定義**:
- **Unit** = Module（1個或多個類別）
- **Isolation** = 只隔離外部世界（Database, File System, External Services）
- **測試風格** = Sociable Unit Tests

---

#### Mockist TDD (London School)

**代表人物**:
- Steve Freeman & Nat Pryce (《Growing Object-Oriented Software, Guided by Tests》作者)

**定義**:
- **Unit** = Class
- **Isolation** = 隔離所有協作者（包括其他類別）
- **測試風格** = Solitary Unit Tests

**別名**:
- London School TDD
- Mockist TDD
- Outside-In TDD

### 3.3 Sociable Unit Tests詳解

#### 視覺化結構

```text
Test
  ↓ 只呼叫Module API
[Module API] ← Public Interface
  ↓
Module {
  Class A (Public)
    ├→ Class B (Private)
    └→ Class C (Private)
}
  ↓ 需要外部依賴
[Test Double] ← Mock Database/FileSystem
```

#### 特性分析

**1. Unit = Module**
- Module可以包含1個或多個類別
- Module大小由你決定（粗粒度）
- Module對外提供Public API

**2. Isolation = 只隔離外部世界**
- Database → 使用Test Double
- File System → 使用Test Double
- External Services → 使用Test Double
- **其他類別 → 使用真實物件** ⭐

**3. 測試策略**
- 測試只透過Module API與系統互動
- 測試**不知道**Module內部有哪些類別（B和C）
- 測試**不知道**類別之間的協作關係
- 測試只Mock外部依賴（Database）

#### 重構影響分析

**情境**: 重構Module內部結構

```text
重構前:
Module {
  Class A → Class B → Class C
}

重構後:
Module {
  Class A → Class D → Class E → Class F
}
```

**測試影響**: ✅ **測試完全不需要修改**

**原因**: 測試只知道Module API，不知道內部結構。

#### 程式碼範例

```dart
// Sociable Unit Test範例
test('使用者提交訂單成功', () async {
  // Given: 使用者已選擇商品且填寫完整資訊
  final order = Order(
    amount: OrderAmount(100),
    userId: UserId('user-001'),
    items: [OrderItem(productId: 'prod-001', quantity: 1)],
  );

  // Given: Mock外部依賴（Database）
  when(mockRepository.save(any))
      .thenAnswer((_) async => SaveResult.success('order-123'));

  // When: 使用者提交訂單（透過Module API）
  final result = await submitOrderUseCase.execute(order);

  // Then: 系統確認訂單已儲存
  expect(result.isSuccess, true);
  expect(result.orderId, 'order-123');

  // 注意：測試不知道Order、OrderAmount、UserId的內部實作
  //      測試使用真實的Domain Entities
});
```

### 3.4 Solitary Unit Tests詳解

#### 視覺化結構

```text
Test A → Mock(B, C, D) → Class A
Test B → Mock(A, C, D) → Class B
Test C → Mock(A, B, D) → Class C
  ↑
每個類別都需要獨立測試
所有協作者都需要Mock
```

#### 特性分析

**1. Unit = Class**
- 每個類別都是一個獨立的Unit
- 細粒度測試

**2. Isolation = 隔離所有協作者**
- 其他類別 → Mock
- Database → Mock
- File System → Mock
- External Services → Mock

**3. 測試策略**
- 測試知道Module內部所有類別
- 測試知道類別之間的協作關係
- 測試Mock所有協作者
- 每個類別都有對應的Test Class

#### 重構影響分析

**情境**: 重構Module內部結構

```text
重構前:
Class A → Class B
  ↓
Test A: Mock(B)
Test B: 獨立測試

重構後:
Class A → Class C → Class B
  ↓
Test A: Mock(C) ← 需要修改！
Test C: Mock(B) ← 需要新增！
Test B: 獨立測試
```

**測試影響**: ❌ **測試需要大量修改**

**原因**: 測試耦合到類別結構，結構改變測試破裂。

#### 程式碼範例

```dart
// Solitary Unit Test範例
test('OrderService.submitOrder calls Repository.save', () async {
  // Given: Mock所有協作者
  final mockOrder = MockOrder();
  final mockRepository = MockOrderRepository();
  final mockValidator = MockOrderValidator();
  final mockCalculator = MockPriceCalculator();

  // Given: 設置Mock行為
  when(mockValidator.validate(mockOrder)).thenReturn(true);
  when(mockCalculator.calculate(mockOrder)).thenReturn(100);
  when(mockRepository.save(mockOrder))
      .thenAnswer((_) async => SaveResult.success('order-123'));

  // When: 呼叫Service
  final service = OrderService(
    repository: mockRepository,
    validator: mockValidator,
    calculator: mockCalculator,
  );
  await service.submitOrder(mockOrder);

  // Then: 驗證Repository.save被呼叫
  verify(mockRepository.save(mockOrder)).called(1);

  // 注意：測試知道所有協作關係
  //      測試驗證方法呼叫次數（實作細節）
  //      測試使用Mock的Domain Entities
});
```

### 3.5 Sociable vs Solitary對比總結

#### 視覺化耦合度對比

**Sociable Unit Tests** (低耦合):
```text
Test ← → [API]
           ↓
       [Module Implementation]
```

只有1條耦合線

**Solitary Unit Tests** (高耦合):
```text
Test A ← → Class A
    ↓        ↓
  Mock(B)  Mock(C)
    ↓        ↓
  Mock(D)  Mock(E)
```

每個類別都有多條耦合線

#### 完整對比表

| 特性 | Sociable Unit Tests ✅ | Solitary Unit Tests ❌ |
|-----|----------------------|---------------------|
| **定義** |
| Unit | Module（1個或多個類別） | Class |
| Isolation | 只隔離外部世界 | 隔離所有協作者 |
| **測試知識** |
| 知道Module API | ✅ 是 | ✅ 是 |
| 知道內部類別 | ❌ 否 | ✅ 是 |
| 知道協作關係 | ❌ 否 | ✅ 是 |
| **Mock策略** |
| Mock Database | ✅ 是 | ✅ 是 |
| Mock File System | ✅ 是 | ✅ 是 |
| Mock External Services | ✅ 是 | ✅ 是 |
| Mock 其他類別 | ❌ 否 | ✅ 是 |
| Mock Domain Entities | ❌ 否 | ✅ 是 |
| **重構影響** |
| 重構內部邏輯 | ✅ 測試不變 | ❌ 測試破裂 |
| 改變演算法 | ✅ 測試不變 | ❌ 測試破裂 |
| 調整類別結構 | ✅ 測試不變 | ❌ 測試破裂 |
| 替換實作方式 | ✅ 測試不變 | ❌ 測試破裂 |
| **經濟成本** |
| 測試程式碼量 | ✅ 少（0.8-1.2x） | ❌ 多（2-4x） |
| Mock程式碼量 | ✅ 少 | ❌ 多 |
| 維護成本 | ✅ 低 | ❌ 高 |
| 重構信心 | ✅ 高 | ❌ 低 |
| 開發速度 | ✅ 快 | ❌ 慢 |
| **優勢** |
| 測試穩定性 | ✅ 穩定 | ⚠️ 脆弱 |
| 重構安全性 | ✅ 高 | ⚠️ 低 |
| 可讀性 | ✅ 高（業務語言） | ⚠️ 中（技術細節） |
| ROI | ✅ 高 | ⚠️ 低 |
| **劣勢** |
| 測試粒度 | ⚠️ 粗（Module層級） | ✅ 細（Class層級） |
| 問題定位 | ⚠️ 較難（需要debug） | ✅ 精確（指向特定類別） |

### 3.6 適用場景建議

| 專案類型 | 推薦方法 | 理由 |
|---------|---------|------|
| **業務應用程式** | ✅ Sociable | 關注業務流程，結構變化頻繁 |
| **CRUD應用程式** | ✅ Sociable | 邏輯簡單，不需要細粒度測試 |
| **Web API** | ✅ Sociable | 測試端到端的API行為 |
| **數學演算法** | ⚠️ Solitary | 複雜計算需要細粒度驗證 |
| **加密系統** | ⚠️ Solitary | 實作正確性至關重要 |
| **金融計算** | 🔀 混合 | UseCase用Sociable，複雜計算用Solitary |
| **科學計算** | 🔀 混合 | 高層流程用Sociable，底層演算法用Solitary |

**一般建議**: 優先使用Sociable Unit Tests，只在確實需要細粒度驗證時才使用Solitary。

---

## 第四章：歷史證據 - 測試行為的源頭

### 4.1 Kent Beck的原始意圖

Kent Beck是TDD的創始人，他在《Test Driven Development By Example》(2003)中明確表達了測試應該關注行為而非結構。

#### 核心引用

**引用1: 測試應該耦合到行為**

> "**Programmer tests should be sensitive to behavior changes and insensitive to structure changes.**"
>
> — Kent Beck, Test Driven Development By Example

**解讀**:
- 行為改變 → 測試應該改變 ✅
- 結構改變 → 測試不應該改變 ✅

---

**引用2: 行為穩定則測試穩定**

> "**If the behavior is stable from an observer's perspective, no tests should change.**"
>
> — Kent Beck, Test Driven Development By Example

**解讀**:
- Observer（觀察者）= 使用者或外部系統
- 如果使用者觀察到的行為沒變 → 測試不應該變

---

**引用3: 測試耦合目標**

> "**Tests should be coupled to the behavior of the code and decoupled from the structure of code.**"
>
> — Kent Beck, Test Driven Development By Example

**解讀**:
- Coupled to **behavior** ✅
- Decoupled from **structure** ✅

#### 關鍵發現

Kent Beck在書的**第1-2頁**就提到「behavior」這個詞，而非「test classes」或「test methods」。

**結論**: TDD從一開始就是關於測試行為，而非測試類別或方法。

### 4.2 Dan North的BDD起源

Dan North創造「Behavior-Driven Development」(BDD)這個詞，但他的動機並非創造新方法，而是**修正TDD的命名問題**。

#### BDD創造的背景

**問題觀察**:

Dan North在培訓開發人員TDD時發現：
- 開發人員問：「What to test?」（測試什麼？）
- 開發人員問：「How to test?」（如何測試？）
- 「Test」這個詞造成混淆

**解決方案**:

用「**Behavior**」取代「**Test**」這個詞：
- Behavior更清楚表達「測試系統行為」
- Behavior避免「測試類別/方法」的誤解

#### 核心引用

> "**I found the word 'behavior' more useful than 'test'.**"
>
> — Dan North, Introducing BDD (2006)

> "**Requirements are behavior.**"
>
> — Dan North

#### BDD的演進

**原始定義** (2006):
- BDD = TDD的命名修正
- 用「behavior」取代「test」讓意圖更清楚

**後續演進** (2010+):
- BDD與Gherkin、Cucumber等工具結合
- BDD開始被定義為「acceptance testing」
- 造成BDD vs TDD的二分法誤解

**真相**: BDD和TDD原本是同一件事，只是命名不同。

### 4.3 Martin Fowler的重構定義

Martin Fowler在《Refactoring: Improving the Design of Existing Code》(1999)中明確定義重構與行為的關係。

#### 核心引用

> "**Refactoring is a way of restructuring an existing body of code, altering its internal structure without changing its external behavior.**"
>
> — Martin Fowler, Refactoring (1999)

**解讀**:
- Refactoring = 改變**internal structure**（內部結構）
- Refactoring ≠ 改變**external behavior**（外部行為）

#### 推論

```text
重構 = 改變Structure，不改變Behavior
           ↓
如果Tests耦合到Behavior → 重構時Tests不變 ✅
如果Tests耦合到Structure → 重構時Tests破裂 ❌
```

**結論**: 重構的前提是測試耦合到行為而非結構。

### 4.4 Google的現代驗證

Google在《Software Engineering at Google》(2020)中提供了大規模工程實踐的驗證。

#### 核心原則

**原則1: Striving for Unchanging Tests**

> "**When we refactor a system, we should not be changing tests.**"
>
> — Software Engineering at Google

**原則2: Testing via Public APIs**

> "**Test through public APIs.**"
>
> — Software Engineering at Google

**理由**: 測試透過Public API呼叫系統，就像使用者一樣。

**原則3: Test Behaviors, Not Methods**

> "**The key principle is: test behaviors, not methods.**"
>
> — Software Engineering at Google

> "**Don't write a test for each method. Write a test for each behavior.**"
>
> — Software Engineering at Google

#### Google的發現

**錯誤實踐**:
```dart
// ❌ 為每個方法寫測試
test('Repository.save is called once', () {
  verify(mockRepository.save(any)).called(1);
  // 測試實作細節（方法呼叫次數）
});
```

**正確實踐**:
```dart
// ✅ 為每個行為寫測試
test('使用者提交訂單成功', () {
  expect(result.isSuccess, true);
  expect(result.orderId, isNotEmpty);
  // 測試可觀察的行為結果
});
```

### 4.5 歷史證據總結

#### 時間軸

```text
1999: Martin Fowler - Refactoring定義
2003: Kent Beck - TDD提出（強調behavior）
2006: Dan North - BDD命名修正
2020: Google - 大規模工程驗證
```

#### 一致性結論

| 來源 | 年份 | 核心觀點 |
|-----|------|---------|
| Martin Fowler | 1999 | 重構 = 改變結構不改變行為 |
| Kent Beck | 2003 | 測試應該耦合到行為而非結構 |
| Dan North | 2006 | BDD = TDD的命名修正（behavior） |
| Google | 2020 | Test behaviors, not methods |

**結論**: 從TDD誕生至今，所有權威都一致強調**測試行為而非結構**。

---

## 第五章：Test-First vs Test-Last的反饋循環差異

### 5.1 TDD (Test-First)的反饋循環

#### Red-Green-Refactor循環

```text
1. Red: 寫測試 → 看測試失敗
2. Green: 寫最簡單的code讓測試通過
3. Refactor: 改善code品質，測試保持通過
```

#### 詳細步驟分析

**步驟1: Requirement → Write Test (Red)**

```text
Requirement → Write Test → See Red
  ↓            ↓             ↓
評估需求    驗證可測試性   驗證Falsifiability
```

**反饋循環**:
- ✅ **可測試性**: 我能為這個需求寫測試嗎？
- ✅ **Falsifiability**: 測試確實會失敗嗎？（不是false positive）
- ✅ **介面友善度**: 測試程式碼是否容易寫？

**時間**: ⚡ 1-2分鐘

---

**步驟2: Write Minimal Code (Green)**

```text
Write Test → Write Code → See Green
  ↓            ↓            ↓
已知需求    最簡實作    驗證正確性
```

**反饋循環**:
- ✅ **實作正確性**: Code讓測試通過了嗎？
- ✅ **最小化原則**: 只寫必要的code

**時間**: ⚡ 2-5分鐘

---

**步驟3: Refactor (Still Green)**

```text
Working Code → Refactor → Still Green
  ↓             ↓            ↓
可運作的code  改善設計    驗證不破壞行為
```

**反饋循環**:
- ✅ **設計品質**: Code是否乾淨優雅？
- ✅ **重構安全性**: 測試仍然通過嗎？

**時間**: ⚡ 3-10分鐘

#### 總結：短且快速的反饋循環

```text
總時間: 6-17分鐘
反饋點: 6個（可測試性、Falsifiability、介面、正確性、設計、安全性）
風險: 低（每個步驟都有驗證）
```

### 5.2 Test-Last的反饋循環

#### 詳細步驟分析

**步驟1: Requirement → Write Code**

```text
Requirement → Write Code
  ↓            ↓
評估需求    直接寫實作
              ↓
        沒有反饋！❌
```

**問題**:
- ❌ 沒有驗證可測試性
- ❌ 沒有驗證介面友善度
- ❌ 需要手動Debug（非常慢）

**時間**: ⏱️ 10-30分鐘

---

**步驟2: Write Code → Manual Debug**

```text
Write Code → Manual Debug
  ↓            ↓
複雜實作    手動測試
              ↓
        非常慢！❌
```

**問題**:
- ❌ Debug非常耗時
- ❌ 可能發現設計問題（太晚了）
- ❌ 可能發現code不可測試（災難）

**時間**: ⏱️ 20-60分鐘

---

**步驟3: Write Test → 發現問題**

```text
Write Test → 發現Code不可測試！❌
  ↓
需要重寫Code + 重寫Test
  ↓
時間加倍！
```

**可能的問題**:
1. ❌ **Code不可測試** → 需要重寫Code + 重寫Test
2. ❌ **介面不友善** → 需要重寫Code + 重寫Test
3. ❌ **無法驗證Falsifiability** → 需要註解Code看測試是否失敗

**時間**: ⏱️ 30-120分鐘（如果需要重寫）

---

**步驟4: 額外工作 - 驗證Falsifiability**

```text
Test Pass → Comment Out Code → Test Fail?
  ↓            ↓                  ↓
綠色測試    註解實作          驗證不是false positive
              ↓
        額外步驟！
```

**時間**: ⏱️ 5-10分鐘

#### 總結：長且緩慢的反饋循環

```text
最佳情況: 35-100分鐘
最壞情況: 65-220分鐘（需要重寫）
反饋點: 3個（可測試性、介面、正確性）← 比TDD少3個
風險: 高（發現問題時已經寫了很多code）
```

### 5.3 Test-First vs Test-Last對比

#### 反饋循環對比圖

**Test-First (TDD)**:
```text
Time: |--1-2min--|--2-5min--|--3-10min--|
      ↓          ↓          ↓
      Red       Green     Refactor
      ↓          ↓          ↓
    快速反饋   快速反饋   快速反饋

總時間: 6-17分鐘
反饋點: 6個
```

**Test-Last**:
```text
Time: |----10-30min----|----20-60min----|----30-120min----|--5-10min--|
      ↓                ↓                ↓                  ↓
    Write Code      Debug         Write Test + Rework    Verify
      ↓                ↓                ↓                  ↓
    無反饋          慢反饋          發現問題（太晚）     額外工作

總時間: 65-220分鐘（最壞情況）
反饋點: 3個（少3個）
```

#### 完整對比表

| 特性 | Test-First (TDD) ✅ | Test-Last ❌ |
|-----|-------------------|-------------|
| **時間成本** |
| 最佳情況 | 6-17分鐘 | 35-100分鐘 |
| 最壞情況 | 6-17分鐘 | 65-220分鐘 |
| **反饋循環** |
| 可測試性驗證 | ✅ 立即（1-2分鐘） | ❌ 延遲（30-90分鐘） |
| Falsifiability驗證 | ✅ 立即（1-2分鐘） | ❌ 需要額外步驟 |
| 介面友善度驗證 | ✅ 立即（1-2分鐘） | ❌ 延遲（30-90分鐘） |
| 實作正確性驗證 | ✅ 快速（2-5分鐘） | ⚠️ 手動Debug（20-60分鐘） |
| 設計品質驗證 | ✅ 持續（重構階段） | ⚠️ 沒有安全網 |
| **風險** |
| 發現問題時間點 | ✅ 立即（1-2分鐘） | ❌ 延遲（30-90分鐘） |
| 重寫成本 | ✅ 低（只寫了測試） | ❌ 高（寫了code + test） |
| False Positive風險 | ✅ 低（見證Red→Green） | ❌ 高（需要額外驗證） |
| **開發體驗** |
| 開發信心 | ✅ 高（測試保護） | ⚠️ 低（手動驗證） |
| 重構信心 | ✅ 高（測試即時反饋） | ⚠️ 低（害怕破壞） |
| Debug時間 | ✅ 少（問題早發現） | ❌ 多（問題晚發現） |

### 5.4 經濟分析

#### 假設情境：開發10個功能

**Test-First (TDD)**:
```text
10個功能 × 15分鐘（平均） = 150分鐘 = 2.5小時
  ↓
所有功能都有測試保護
所有功能都經過設計優化
重構安全且快速
```

**Test-Last**:
```text
最佳情況:
10個功能 × 35分鐘 = 350分鐘 = 5.8小時

最壞情況:
10個功能 × 120分鐘 = 1200分鐘 = 20小時
  ↓
可能有些功能沒有測試（時間壓力）
可能有設計問題未解決
重構風險高
```

**結論**: Test-First比Test-Last快2-8倍。

### 5.5 為什麼Test-First更快？

#### 根本原因

**1. 早期問題發現**
```text
Test-First: 發現問題在1-2分鐘 → 修復成本低
Test-Last: 發現問題在30-90分鐘 → 修復成本高10-30倍
```

**2. 設計反饋**
```text
Test-First: 測試是第一個使用者 → 介面友善度立即驗證
Test-Last: Code寫完才發現介面不友善 → 需要重寫
```

**3. 重構安全性**
```text
Test-First: 測試保護 → 重構快速且安全
Test-Last: 沒有測試 → 重構緩慢且危險
```

**4. Debug時間**
```text
Test-First: 問題範圍小（剛寫的5-10行） → Debug快
Test-Last: 問題範圍大（整個功能） → Debug慢
```

**5. 心理負擔**
```text
Test-First: 小步前進，持續綠燈 → 信心高
Test-Last: 大量code未驗證 → 焦慮高
```

---

## 第六章：Clean Architecture與Behavior Testing的完美結合

### 6.1 為什麼需要Clean Architecture？

**問題**: 即使使用Sociable Unit Tests，如果架構設計不當，測試仍然會痛苦。

**範例問題**:
- 業務邏輯混在UI裡 → 無法unit test
- 業務邏輯混在Controller裡 → 測試需要啟動整個Web框架
- 業務邏輯直接呼叫Database → 測試很慢

**解決方案**: Clean Architecture家族（Hexagonal, Onion, Clean）

### 6.2 Hexagonal Architecture (Ports & Adapters)

#### 由內而外的思考方式

**傳統思維** (由外而內):
```text
1. 先想UI長什麼樣子
2. 再想Database schema
3. 最後才想業務邏輯
```

**Hexagonal思維** (由內而外):
```text
1. 先想業務邏輯（Use Cases）
2. 定義API（Driver Ports）
3. 定義外部依賴介面（Driven Ports）
4. 最後才實作UI和Database
```

#### 核心結構

```text
            [Users/Tests] ← 使用者或測試
                  ↓
          [Driver Ports] ← Use Cases API
                  ↓
         [Application Core]
           ├─ Use Cases
           ├─ Domain Entities
           └─ Business Rules
                  ↓
          [Driven Ports] ← Repository/Service Interfaces
                  ↓
             [Adapters]
           ├─ UI (Web, Mobile, Console)
           ├─ Database (PostgreSQL, MongoDB)
           └─ External Services (Payment, Email)
```

#### 關鍵洞察

**洞察1: Tests = Users**

> "**Tests are another user of the system.**"
>
> — Alistair Cockburn, Hexagonal Architecture

Tests和Users在同一層級，都透過Driver Ports與系統互動。

**洞察2: Application Core完全獨立**

Application Core：
- ✅ 不知道UI是Web還是Mobile
- ✅ 不知道Database是PostgreSQL還是MongoDB
- ✅ 不知道Payment Gateway是PayPal還是Stripe

**洞察3: 只Mock外部世界**

```text
Test → [Use Case] → Real Domain Entities
              ↓
        [Mock Repository] ← Test Double
```

- Use Cases是真實的
- Domain Entities是真實的
- 只有Repository是Mock

#### ATM範例

**Use Cases (Driver Ports)**:
```text
- withdrawCash(amount)
- checkBalance()
- depositCash(amount)
```

**Application Core**:
```dart
class WithdrawCashUseCase {
  final AccountRepository repository;

  Future<Result> execute(Amount amount) async {
    // 1. 讀取帳戶
    final account = await repository.findAccount(accountId);

    // 2. 檢查餘額（Domain邏輯）
    if (!account.hasSufficientBalance(amount)) {
      return Result.failure('餘額不足');
    }

    // 3. 扣款（Domain邏輯）
    account.withdraw(amount);

    // 4. 儲存（Driven Port）
    await repository.save(account);

    return Result.success();
  }
}
```

**Test**:
```dart
test('提款成功 - 餘額充足', () async {
  // Given: 帳戶餘額1000
  final mockRepository = MockAccountRepository();
  when(mockRepository.findAccount(any))
      .thenAnswer((_) async => Account(balance: 1000));
  when(mockRepository.save(any))
      .thenAnswer((_) async => SaveResult.success());

  final useCase = WithdrawCashUseCase(repository: mockRepository);

  // When: 提款500
  final result = await useCase.execute(Amount(500));

  // Then: 成功
  expect(result.isSuccess, true);

  // 注意：我們測試的是Use Case行為
  //      Account是真實的Domain Entity
  //      只有Repository是Mock
});
```

### 6.3 Onion Architecture

#### 分層結構

```text
┌─────────────────────────────────────┐
│   Infrastructure (Adapters)        │ ← UI, Database, External Services
│  ┌───────────────────────────────┐ │
│  │  Application Services          │ │ ← Use Cases
│  │ ┌─────────────────────────────┤ │
│  │ │  Domain Services            │ │ ← Complex Business Logic
│  │ │ ┌──────────────────────────┐│ │
│  │ │ │  Domain Model            ││ │ ← Entities, Value Objects
│  │ │ └──────────────────────────┘│ │
│  │ └──────────────────────────── │ │
│  └────────────────────────────────┘ │
└─────────────────────────────────────┘

依賴方向: 外層依賴內層
```

#### 與Hexagonal的對應

| Hexagonal | Onion |
|-----------|-------|
| Driver Ports | Application Services |
| Application Core | Domain Model + Domain Services |
| Driven Ports | Repository Interfaces (在Domain層) |
| Adapters | Infrastructure |

#### 核心規則

**依賴規則**:
```text
Infrastructure → Application Services → Domain Services → Domain Model
```

外層可以依賴內層，內層不可依賴外層。

### 6.4 Clean Architecture (Uncle Bob)

#### Uncle Bob的貢獻

Clean Architecture是Hexagonal和Onion的**綜合與明確化**：

1. **明確Use Cases概念**: 不再隱晦，直接使用「Use Cases」層
2. **依賴規則視覺化**: 同心圓圖清楚展示依賴方向
3. **框架獨立性**: 強調業務邏輯不依賴框架

#### 四層結構

```text
┌──────────────────────────────────────┐
│  Frameworks & Drivers               │ ← UI, Web, DB, Devices
│  ┌────────────────────────────────┐ │
│  │  Interface Adapters             │ │ ← Controllers, Presenters, Gateways
│  │  ┌──────────────────────────┐  │ │
│  │  │  Use Cases               │  │ │ ← Business Rules (Application)
│  │  │  ┌────────────────────┐  │  │ │
│  │  │  │  Entities          │  │  │ │ ← Business Rules (Domain)
│  │  │  └────────────────────┘  │  │ │
│  │  └──────────────────────────┘  │ │
│  └─────────────────────────────────┘ │
└──────────────────────────────────────┘

依賴規則: 只能向內依賴
```

#### The Dependency Rule

> "**Source code dependencies must point only inward.**"
>
> — Robert C. Martin, Clean Architecture

**含義**:
- 內層不知道外層的存在
- 外層可以知道內層
- 改變外層不影響內層

### 6.5 三大架構的本質一致性

#### 核心共同點

| 概念 | Hexagonal | Onion | Clean |
|------|-----------|-------|-------|
| 核心業務邏輯 | Application Core | Domain Model | Entities |
| Use Cases | Driver Ports | Application Services | Use Cases |
| 外部依賴介面 | Driven Ports | Repository Interfaces | Gateways |
| 實作層 | Adapters | Infrastructure | Frameworks & Drivers |
| Tests位置 | 與Users同層 | 與UI同層 | 在Frameworks層 |

#### 視覺化對應

```text
Hexagonal:
  [Tests/Users] → [Driver Ports] → [Core] → [Driven Ports] → [Adapters]

Onion:
  [Tests/UI] → [App Services] → [Domain Services] → [Domain Model]

Clean:
  [Tests/UI] → [Controllers] → [Use Cases] → [Entities]

本質:
  [Tests] → [Use Cases API] → [Business Logic] → [External Interfaces]
```

### 6.6 測試策略整合

#### 完整測試金字塔

```text
          /\
         /  \ E2E Tests (Through UI)
        /____\
       /      \ Integration Tests (Test Adapters)
      /________\
     /          \
    /____________\ Unit Tests (Test Use Cases) ⭐

最重要的層級：Unit Tests測試Use Cases
```

#### Unit Tests測試什麼？

**在Clean Architecture中的Unit Tests**:

```dart
// Unit Test = 測試Use Case行為
test('使用者提交訂單成功', () async {
  // Arrange
  final mockRepository = MockOrderRepository();
  final mockPaymentGateway = MockPaymentGateway();

  when(mockRepository.save(any))
      .thenAnswer((_) async => SaveResult.success('order-123'));
  when(mockPaymentGateway.charge(any))
      .thenAnswer((_) async => PaymentResult.success());

  final useCase = SubmitOrderUseCase(
    repository: mockRepository,
    paymentGateway: mockPaymentGateway,
  );

  // Act
  final order = Order(
    amount: OrderAmount(100),
    userId: UserId('user-001'),
  );
  final result = await useCase.execute(order);

  // Assert
  expect(result.isSuccess, true);
  expect(result.orderId, 'order-123');

  // 這是在測試Use Case的行為
  // 這是Acceptance Testing at Unit Level
});
```

#### 三種測試層級的職責

**Unit Tests (Use Cases)**:
- ✅ 測試完整的業務流程
- ✅ 測試業務規則
- ✅ 測試Domain邏輯
- ✅ Mock外部依賴（Repository, Gateway）
- ✅ 使用真實Domain Entities
- ✅ **這是最重要的測試層級**

**Integration Tests (Adapters)**:
- ✅ 測試Database Adapter（使用真實Database）
- ✅ 測試Payment Gateway Adapter（可能用Sandbox）
- ✅ 測試外部系統整合

**E2E Tests (Full System)**:
- ✅ 測試關鍵使用者流程
- ✅ 測試系統各層連接正確
- ⚠️ 數量少（慢且脆弱）

### 6.7 Clean Architecture的可測試性優勢

#### 優勢1: 快速反饋

```text
傳統架構:
  測試需要啟動整個系統 → 慢（10-60秒）

Clean Architecture:
  測試只需要Use Case + Mock → 快（< 100ms）
```

#### 優勢2: Acceptance Testing at Unit Level

**傳統認知**:
- Unit Tests = 測試小元件
- Acceptance Tests = 透過UI測試

**Clean Architecture的突破**:
- Unit Tests = 測試Use Cases = 測試業務需求
- **Unit Tests就是Acceptance Tests** ⭐

```dart
// 這是Unit Test，但也是Acceptance Test
test('使用者取消訂單成功 - 訂單狀態為pending', () async {
  // 這測試的是使用者需求：
  // "As a user, I want to cancel my order when it's pending"

  // Given: 訂單狀態為pending
  final order = Order(
    status: OrderStatus.pending,
    amount: OrderAmount(100),
  );

  // When: 使用者取消訂單
  final result = await cancelOrderUseCase.execute(order);

  // Then: 訂單狀態變為cancelled
  expect(result.isSuccess, true);
  expect(result.order.status, OrderStatus.cancelled);

  // 這測試了完整的使用者需求，不需要UI
});
```

#### 優勢3: 獨立開發與測試

```text
開發順序:
1. 定義Use Cases（Driver Ports）
2. 定義Repository Interfaces（Driven Ports）
3. 實作Domain Logic
4. 寫Unit Tests測試Use Cases
5. 實作UI（最後才做）
6. 實作Database Adapter（最後才做）

好處:
- 可以在沒有UI的情況下測試所有業務邏輯
- 可以在沒有Database的情況下測試所有Use Cases
- 前後端可以平行開發
```

### 6.8 完整範例：訂單系統

#### Use Case定義

```dart
// Driver Port
abstract class SubmitOrderUseCase {
  Future<SubmitOrderResult> execute(Order order);
}

// Driven Ports
abstract class OrderRepository {
  Future<SaveResult> save(Order order);
}

abstract class InventoryService {
  Future<StockStatus> checkStock(ProductId productId);
}

abstract class PaymentGateway {
  Future<PaymentResult> charge(Payment payment);
}
```

#### Use Case實作

```dart
class SubmitOrderUseCaseImpl implements SubmitOrderUseCase {
  final OrderRepository repository;
  final InventoryService inventoryService;
  final PaymentGateway paymentGateway;

  SubmitOrderUseCaseImpl({
    required this.repository,
    required this.inventoryService,
    required this.paymentGateway,
  });

  @override
  Future<SubmitOrderResult> execute(Order order) async {
    // 1. 檢查庫存（Driven Port）
    for (final item in order.items) {
      final stock = await inventoryService.checkStock(item.productId);
      if (stock == StockStatus.outOfStock) {
        return SubmitOrderResult.failure('商品庫存不足');
      }
    }

    // 2. 驗證訂單（Domain邏輯）
    if (!order.isValid()) {
      return SubmitOrderResult.failure('訂單資料無效');
    }

    // 3. 計算金額（Domain邏輯）
    final total = order.calculateTotal();

    // 4. 扣款（Driven Port）
    final payment = Payment(amount: total, orderId: order.id);
    final paymentResult = await paymentGateway.charge(payment);
    if (!paymentResult.isSuccess) {
      return SubmitOrderResult.failure('付款失敗');
    }

    // 5. 儲存訂單（Driven Port）
    final saveResult = await repository.save(order);
    if (!saveResult.isSuccess) {
      return SubmitOrderResult.failure('訂單儲存失敗');
    }

    return SubmitOrderResult.success(orderId: order.id);
  }
}
```

#### Sociable Unit Test

```dart
group('SubmitOrderUseCase', () {
  late MockOrderRepository mockRepository;
  late MockInventoryService mockInventoryService;
  late MockPaymentGateway mockPaymentGateway;
  late SubmitOrderUseCase useCase;

  setUp(() {
    mockRepository = MockOrderRepository();
    mockInventoryService = MockInventoryService();
    mockPaymentGateway = MockPaymentGateway();
    useCase = SubmitOrderUseCaseImpl(
      repository: mockRepository,
      inventoryService: mockInventoryService,
      paymentGateway: mockPaymentGateway,
    );
  });

  test('使用者提交訂單成功 - 所有條件滿足', () async {
    // Given: 庫存充足、訂單有效、付款成功
    final order = Order(
      id: OrderId('order-001'),
      amount: OrderAmount(1000),
      userId: UserId('user-001'),
      items: [OrderItem(productId: ProductId('prod-001'), quantity: 2)],
    );

    when(mockInventoryService.checkStock(any))
        .thenAnswer((_) async => StockStatus.available);
    when(mockPaymentGateway.charge(any))
        .thenAnswer((_) async => PaymentResult.success());
    when(mockRepository.save(any))
        .thenAnswer((_) async => SaveResult.success());

    // When: 使用者提交訂單
    final result = await useCase.execute(order);

    // Then: 訂單提交成功
    expect(result.isSuccess, true);
    expect(result.orderId, OrderId('order-001'));

    // 注意：
    // 1. Order是真實的Domain Entity（不是Mock）
    // 2. 測試驗證的是行為結果（isSuccess, orderId）
    // 3. 測試不驗證方法呼叫次數（不是verify(repository).called(1)）
  });

  test('使用者提交訂單失敗 - 庫存不足', () async {
    // Given: 庫存不足
    final order = Order(
      id: OrderId('order-002'),
      amount: OrderAmount(1000),
      items: [OrderItem(productId: ProductId('prod-001'), quantity: 2)],
    );

    when(mockInventoryService.checkStock(any))
        .thenAnswer((_) async => StockStatus.outOfStock);

    // When: 使用者提交訂單
    final result = await useCase.execute(order);

    // Then: 提交失敗，顯示庫存不足訊息
    expect(result.isSuccess, false);
    expect(result.errorMessage, '商品庫存不足');

    // Then: 不應該嘗試扣款和儲存
    verifyNever(mockPaymentGateway.charge(any));
    verifyNever(mockRepository.save(any));
  });
});
```

### 6.9 總結：Clean Architecture + Sociable Unit Tests = 完美組合

#### 完美組合的原因

| Clean Architecture提供 | Sociable Unit Tests利用 | 結果 |
|---------------------|---------------------|------|
| Use Cases作為API | 測試透過Use Cases API | 測試耦合到行為 |
| Domain Logic獨立 | 使用真實Domain Entities | 測試涵蓋業務邏輯 |
| Driven Ports (Interfaces) | 只Mock這些Interfaces | 測試不依賴外部系統 |
| 依賴反轉原則 | Mock策略清晰 | 測試簡單且快速 |

#### 最終效益

1. **快速執行**: 所有業務邏輯測試在秒級完成
2. **高覆蓋率**: Use Cases = 業務需求，測試Use Cases = 測試所有需求
3. **重構安全**: 測試耦合到Use Cases API，內部結構隨意重構
4. **獨立開發**: 不需要UI和Database就能開發和測試業務邏輯
5. **高ROI**: 測試維護成本低，重構頻率高，程式碼品質持續提升

---

## 第七章：實務應用指引

### 7.1 如何選擇Sociable vs Solitary？

#### 決策樹

```bash
你的專案類型是？
  │
  ├─ 業務應用程式（CRUD, Web API, Mobile App）
  │    → 使用Sociable Unit Tests ✅
  │    → 理由：關注業務流程，結構變化頻繁
  │
  ├─ 數學演算法、科學計算
  │    → 使用Solitary Unit Tests（部分）⚠️
  │    → 理由：需要細粒度驗證複雜計算
  │
  ├─ 加密系統、金融計算
  │    → 使用混合策略 🔀
  │    → Sociable for Use Cases
  │    → Solitary for 複雜演算法
  │
  └─ 不確定
       → 預設使用Sociable Unit Tests ✅
       → 只在確實需要時才用Solitary
```

#### 判斷標準表

| 問題 | 答案 | 建議方法 |
|------|------|---------|
| 業務邏輯比演算法多？ | 是 | Sociable ✅ |
| 結構經常需要重構？ | 是 | Sociable ✅ |
| 需要細粒度測試每個類別？ | 是 | Solitary ⚠️ |
| 數學正確性至關重要？ | 是 | Solitary ⚠️ |
| 測試維護成本是關注點？ | 是 | Sociable ✅ |
| 測試執行速度是關注點？ | 是 | Sociable ✅ |

### 7.2 重構安全性驗證檢查清單

#### 檢查清單1: 測試耦合到什麼？

執行這些檢查以驗證你的測試耦合目標：

```markdown
測試耦合檢查：
- [ ] 測試只呼叫Module/UseCase的Public API？
- [ ] 測試不知道內部有哪些類別？
- [ ] 測試不知道類別之間的協作關係？
- [ ] Mock只針對外部依賴（Repository, Service）？
- [ ] Domain Entities使用真實物件（不Mock）？
- [ ] Value Objects使用真實物件（不Mock）？

如果全部勾選 → 測試耦合到行為 ✅
如果有任何未勾選 → 測試耦合到結構 ❌
```

#### 檢查清單2: 重構時測試穩定性

執行實際重構並驗證測試是否穩定：

```markdown
重構測試：
1. 記錄當前測試數量和內容
2. 執行以下重構操作：
   - [ ] 改變類別內部邏輯 → 測試無需修改？
   - [ ] 改變演算法實作 → 測試無需修改？
   - [ ] 增加/刪除內部類別 → 測試無需修改？
   - [ ] 調整類別協作關係 → 測試無需修改？
   - [ ] 重新命名內部方法 → 測試無需修改？
   - [ ] 拆分/合併類別 → 測試無需修改？
3. 驗證所有測試仍然通過

如果全部測試無需修改 → Sociable Unit Tests ✅
如果有任何測試需要修改 → Solitary Unit Tests ❌
```

#### 檢查清單3: 測試描述語言

檢查測試的命名和描述：

```markdown
測試語言檢查：
- [ ] 測試名稱使用業務語言（不含技術術語）？
- [ ] 測試描述從使用者視角（不含類別名稱）？
- [ ] 測試不提及「Repository.save is called」等實作細節？
- [ ] 測試驗證可觀察的行為結果（不驗證方法呼叫）？
- [ ] 非技術人員能理解測試在驗證什麼？

如果全部勾選 → 測試行為 ✅
如果有任何未勾選 → 測試結構 ❌
```

### 7.3 Legacy Code的漸進式導入策略

#### 情境：大型Legacy專案從未做過TDD

**挑戰**:
- 沒有測試
- 程式碼耦合嚴重
- 團隊不熟悉TDD
- 管理層不支持

#### 策略1: 選擇練習區域（非關鍵功能）

```markdown
步驟1: 識別低風險練習區域
目標: 找一個可以安全練習的地方

候選區域:
- [ ] 內部工具功能（不影響客戶）
- [ ] 輔助功能（如報表、統計）
- [ ] 新功能（greenfield within brownfield）

評估標準:
- 風險低（失敗不影響核心業務）
- 相對獨立（不涉及太多legacy code）
- 適度複雜（不太簡單也不太複雜）

選擇: ___________________
```

#### 策略2: 獲得管理層支持

```markdown
步驟2: 準備管理層溝通材料

1. 問題陳述（量化Legacy問題）:
   - 平均Bug修復時間: __ 天
   - 新功能開發時間: __ 週
   - 程式碼修改風險: 高/中/低
   - 開發人員信心: 低

2. TDD價值主張:
   - 減少Bug修復時間 → 節省成本
   - 提升開發速度 → 加快Time-to-Market
   - 降低修改風險 → 提升系統穩定性
   - 提升團隊信心 → 降低離職率

3. 漸進式方案:
   - 第1-2個Sprint: 練習區域（0風險）
   - 第3-4個Sprint: 新功能強制TDD
   - 第5+個Sprint: 觸及舊程式碼時補測試

4. 預期成本:
   - 前2個Sprint生產力下降20-30%（學習期）
   - 第3個Sprint後生產力恢復並超越

管理層同意: [ ] 是 [ ] 否
```

#### 策略3: 團隊培訓

```markdown
步驟3: TDD培訓計畫

Week 1: 理論與Demo
- [ ] TDD基本概念（Red-Green-Refactor）
- [ ] Sociable vs Solitary Unit Tests
- [ ] Given-When-Then格式
- [ ] Live Demo: 從零開始寫一個功能

Week 2: Pair Programming
- [ ] 資深成員帶領新手
- [ ] 實際專案練習區域
- [ ] Code Review強調測試設計

Week 3-4: 獨立練習
- [ ] 每人負責一個練習功能
- [ ] Daily Code Review
- [ ] Retrospective改善

Week 5+: 正式導入
- [ ] 新功能強制TDD
- [ ] Legacy code漸進式補測試
```

#### 策略4: 新User Story強制TDD

```markdown
步驟4: 新功能TDD政策

政策:
- 所有新User Story必須Test-First
- Use Case必須有BDD測試
- Domain複雜邏輯必須有單元測試

Done的定義 (Definition of Done):
- [ ] Feature實作完成
- [ ] 所有測試通過
- [ ] 測試覆蓋率 ≥ 80%
- [ ] Code Review通過
- [ ] 測試使用Sociable Unit Tests風格

檢查點:
- Sprint Planning: 討論測試策略
- Daily Standup: 詢問測試進度
- Sprint Review: Demo測試結果
- Retrospective: 改善測試實踐
```

#### 策略5: 觸及舊程式碼時補測試

```markdown
步驟5: Legacy Code測試策略

規則: 修改舊程式碼前先寫測試

流程:
1. 收到Bug報告或修改請求
2. 分析需要修改的程式碼範圍
3. 為相關程式碼寫Characterization Tests
4. 執行測試確保現有行為被捕捉
5. 修改程式碼
6. 執行測試確保修改正確
7. 重構（如果測試允許）

Characterization Tests範例:
```dart
// 不知道正確行為，先寫測試捕捉現有行為
test('當前calculatePrice的行為', () {
  // 執行現有程式碼
  final price = legacyCode.calculatePrice(100, 0.1);

  // 先寫一個預期會失敗的值
  expect(price, 0);

  // 執行後看實際值是多少（例如90）
  // 然後更新測試
  // expect(price, 90);
});
```

#### 策略6: 逐步擴大覆蓋範圍

```markdown
步驟6: 測試覆蓋率提升計畫

Sprint 1-2: 練習區域
- 目標覆蓋率: 80%
- 範圍: 練習功能

Sprint 3-4: 新功能
- 目標覆蓋率: 100%
- 範圍: 所有新User Stories

Sprint 5-8: 關鍵路徑
- 目標覆蓋率: 80%
- 範圍: 核心業務流程

Sprint 9-12: 高風險區域
- 目標覆蓋率: 80%
- 範圍: 常出Bug的模組

Sprint 13+: 全專案
- 目標覆蓋率: 70%
- 範圍: 整個專案

目前進度: Sprint __, 覆蓋率 ___%
```

### 7.4 常見問題與解決方案

#### 問題1: 「我的類別太複雜，無法用Sociable Unit Tests測試」

**問題根源**: 類別設計問題，不是測試方法問題。

**解決方案**:

1. **重新定義Module邊界**:
   ```text
   原本: Module = 1個複雜類別（無法測試）
   改為: Module = 幾個簡單類別（容易測試）
   ```

2. **應用Clean Architecture**:
   ```text
   問題: Business Logic混在UI裡
   解決: 提取Use Case，測試Use Case
   ```

3. **Single Responsibility Principle**:
   ```text
   問題: 類別做太多事
   解決: 拆分成多個單一職責的類別
   ```

#### 問題2: 「Sociable Unit Tests無法精確定位問題」

**回應**: 這是Sociable的唯一劣勢，但可以接受。

**理由**:
- Debug工具已經很強大（IDE debugger, logging）
- 測試失敗後用debugger逐步追蹤，很快就能找到問題
- 這個小劣勢遠小於「重構時測試破裂」的大問題

**實務經驗**:
- 使用Sociable Tests多年，問題定位從未是障礙
- 測試失敗時，通常5-10分鐘內就能找到問題
- 相比之下，重構時修復破裂的tests可能花費數小時

#### 問題3: 「我需要測試private方法」

**回應**: 這是Solitary思維的表現。

**正確思維**:
```text
不要直接測試private方法
測試使用該private方法的public API
```

**範例**:
```dart
class OrderCalculator {
  // Public API
  double calculateTotal(Order order) {
    final subtotal = _calculateSubtotal(order);
    final tax = _calculateTax(subtotal);
    final shipping = _calculateShipping(order);
    return subtotal + tax + shipping;
  }

  // Private methods
  double _calculateSubtotal(Order order) { ... }
  double _calculateTax(double subtotal) { ... }
  double _calculateShipping(Order order) { ... }
}

// ❌ 錯誤：嘗試測試private methods
// test('_calculateSubtotal works', () { ... });

// ✅ 正確：測試public API
test('calculateTotal包含subtotal + tax + shipping', () {
  final order = Order(items: [...], shippingAddress: ...);
  final total = calculator.calculateTotal(order);

  expect(total, expectedTotal);

  // 這個測試已經驗證了所有private methods的正確性
});
```

#### 問題4: 「測試執行太慢」

**回應**: 檢查是否真的在做Unit Tests。

**常見錯誤**:
```dart
// ❌ 這不是Unit Test，這是Integration Test
test('submitOrder', () async {
  // 啟動整個Database
  final database = await PostgreSQL.connect(...);

  // 啟動整個Web框架
  final app = await Application.start(...);

  // 執行請求
  final response = await app.post('/orders', ...);

  // 這個測試很慢（數秒）
});
```

**正確做法**:
```dart
// ✅ 這是Unit Test
test('submitOrder', () async {
  // Mock Database
  final mockRepository = MockOrderRepository();
  when(mockRepository.save(any))
      .thenAnswer((_) async => SaveResult.success());

  // 直接測試Use Case
  final useCase = SubmitOrderUseCase(repository: mockRepository);
  final result = await useCase.execute(order);

  // 這個測試很快（< 100ms）
});
```

---

## 第八章：與其他方法論的整合

### 8.1 與BDD測試方法論的關係

#### 互補關係

| 方法論 | 核心貢獻 | 角色 |
|-------|---------|------|
| **Behavior-First TDD** | 歷史證據、理論基礎 | WHY（為什麼要測試行為） |
| **BDD測試方法論** | Given-When-Then格式 | HOW（如何描述行為） |

#### 整合點

**Behavior-First TDD提供**:
- ✅ Kent Beck, Martin Fowler的歷史引用
- ✅ Sociable vs Solitary的對比分析
- ✅ Test-First vs Test-Last的經濟分析
- ✅ 「為什麼要測試行為」的理論基礎

**BDD測試方法論提供**:
- ✅ Given-When-Then的具體格式
- ✅ 測試描述的業務語言規範
- ✅ UseCase層的測試範例

**結合使用**:
1. 先讀「Behavior-First TDD」理解痛點根源
2. 再讀「BDD測試方法論」學習Given-When-Then格式
3. 使用Given-When-Then格式撰寫Sociable Unit Tests

### 8.2 與混合測試策略方法論的關係

#### 互補關係

| 方法論 | 核心貢獻 | 角色 |
|-------|---------|------|
| **Behavior-First TDD** | Sociable Unit Tests概念 | WHAT（測試什麼） |
| **混合測試策略** | 分層測試決策樹 | WHEN（何時用哪種測試） |

#### 整合點

**Behavior-First TDD提供**:
- ✅ Sociable Unit Tests vs Solitary Unit Tests定義
- ✅ 測試耦合到Behavior vs Structure的對比
- ✅ Clean Architecture的可測試性分析

**混合測試策略方法論提供**:
- ✅ Layer 1-5的測試決策樹
- ✅ 量化的覆蓋率指標
- ✅ 技術性檢查清單
- ✅ Ticket測試策略設計

**結合使用**:
1. 使用「Behavior-First TDD」理解Sociable Unit Tests
2. 使用「混合測試策略」的決策樹判斷每層該用什麼測試
3. UseCase層使用Sociable Unit Tests
4. Domain層複雜邏輯視情況選擇Sociable或Solitary

### 8.3 三篇方法論的完整關係圖

```text
Behavior-First TDD (本方法論)
    ↓ 提供歷史證據和理論基礎
    ├─→ BDD測試方法論
    │     ↓ 提供Given-When-Then格式
    │
    └─→ 混合測試策略方法論
          ↓ 提供分層決策樹和量化指標

整合結果: 完整的Behavior-Driven Testing體系

使用順序建議:
1. 先讀「Behavior-First TDD」→ 理解痛點和理論
2. 再讀「BDD測試方法論」→ 學習Given-When-Then
3. 最後讀「混合測試策略」→ 應用到各層級
```

### 8.4 整合後的核心原則總結

綜合三篇方法論後，我們得到以下核心原則：

#### 原則1: 測試是可執行的需求規格（Behavior-First TDD）

> **Tests = Executable Requirements Specifications**

測試不是驗證實作的工具，而是用程式碼表達的需求規格書。

#### 原則2: 測試行為而非結構（Kent Beck + Valentina）

> **Tests should be coupled to behavior, decoupled from structure**

- 行為改變 → 測試改變 ✅
- 結構改變 → 測試不變 ✅

#### 原則3: UseCase層必須BDD（混合測試策略）

> **UseCase層代表業務流程，必須使用Given-When-Then格式測試所有場景**

- 正常流程（至少1個）
- 異常流程（至少2個）
- 邊界條件（至少3個）

#### 原則4: 使用Sociable Unit Tests（Behavior-First TDD）

> **優先使用Sociable Unit Tests，只在確實需要細粒度驗證時才用Solitary**

- Module = Unit（不是Class）
- 只Mock外部依賴（不Mock其他類別）
- 測試透過API與系統互動

#### 原則5: 分層測試決策（混合測試策略）

> **不同層級使用不同測試策略**

```text
Layer 1 (UI)       → 整合測試（關鍵流程）
Layer 2 (Behavior) → 單元測試（複雜）/ 依賴上層（簡單）
Layer 3 (UseCase)  → Sociable Unit Tests（所有場景）
Layer 4 (Interface)→ 不測試
Layer 5 (Domain)   → 單元測試（複雜）/ 依賴上層（簡單）
```

### 8.5 實務應用的完整流程

#### Phase 1: 功能設計（新增行為場景提取）

```markdown
1. 理解需求
2. 提取Given-When-Then場景（BDD方法論）
   - 場景1: 正常流程
   - 場景2-3: 異常流程
   - 場景4-6: 邊界條件
3. 驗證可測試性（Behavior-First TDD）
```

#### Phase 2: 測試設計（新增測試策略決策）

```markdown
1. 應用分層測試決策樹（混合測試策略）
   - 識別層級
   - 評估複雜度
   - 選擇測試方法

2. 選擇Sociable或Solitary（Behavior-First TDD）
   - 預設: Sociable
   - 特殊情況: Solitary

3. 撰寫Given-When-Then測試（BDD方法論）
   - 使用業務語言
   - 測試行為而非結構
   - 只Mock外部依賴

4. 技術性檢查清單（混合測試策略）
   - Null值處理
   - 邊界條件
   - 異常處理
```

#### Phase 3: 實作執行（強化Test-First）

```markdown
1. Red: 執行測試看失敗（Behavior-First TDD）
   - 驗證Falsifiability

2. Green: 寫最簡code讓測試通過
   - 不考慮設計
   - 快速達到綠燈

3. Refactor: 改善設計
   - 測試保護（Behavior-First TDD）
   - 測試不應該改變
```

#### Phase 4: 重構優化（新增測試穩定性檢查）

```markdown
1. 執行重構

2. 測試穩定性檢查（Behavior-First TDD）
   - [ ] 測試無需修改
   - [ ] 所有測試通過

3. 如果測試需要修改
   → 升級為測試設計問題
   → 回到Phase 2重新設計測試
```

---

## 第九章：總結與結論

### 9.1 核心洞察回顧

#### 洞察1: TDD痛苦的根源是錯誤實踐

**錯誤實踐**:
- Class = Unit
- Mock所有協作者
- 測試耦合到結構

**結果**:
- 測試程式碼爆炸（2-4倍）
- 重構時測試破裂
- 高維護成本

**正確實踐**:
- Module = Unit
- 只Mock外部依賴
- 測試耦合到行為

**結果**:
- 測試程式碼適中（1倍）
- 重構時測試穩定
- 低維護成本

---

#### 洞察2: TDD和BDD從來都是關於行為

**歷史證據**:
- Kent Beck (2003): "Tests should be coupled to behavior"
- Dan North (2006): BDD = TDD的命名修正
- Martin Fowler: 重構 = 改變結構不改變行為
- Google (2020): "Test behaviors, not methods"

**結論**: 測試行為而非結構是TDD的原始意圖，不是新發明。

---

#### 洞察3: Sociable vs Solitary是根本差異

**兩種完全不同的測試哲學**:

| Sociable | Solitary |
|----------|----------|
| 測試行為 | 測試結構 |
| Mock少 | Mock多 |
| 測試穩定 | 測試脆弱 |
| 低維護 | 高維護 |
| 粗粒度 | 細粒度 |

**適用場景**: Sociable適合絕大多數專案，Solitary只適用於少數特殊情況。

---

#### 洞察4: Test-First vs Test-Last不只是順序

**反饋循環差異**:
- Test-First: 6-17分鐘，6個反饋點
- Test-Last: 65-220分鐘，3個反饋點

**經濟差異**: Test-First比Test-Last快2-8倍。

---

#### 洞察5: Clean Architecture提供完美的可測試性

**完美組合**:
```text
Clean Architecture (提供Use Cases API)
    +
Sociable Unit Tests (測試Use Cases)
    =
Acceptance Testing at Unit Level
```

**效益**:
- 快速執行（< 100ms）
- 高覆蓋率（測試所有業務邏輯）
- 重構安全（測試穩定）
- 獨立開發（不需UI和Database）

### 9.2 方法論價值主張

#### 解決的問題

**問題1**: TDD太痛苦，團隊放棄
- **解決**: 揭示痛苦根源，提供正確方法

**問題2**: 測試維護成本高
- **解決**: Sociable Unit Tests降低維護成本80%

**問題3**: 重構時測試破裂
- **解決**: 測試耦合到行為，重構時測試穩定

**問題4**: 不知道該測試什麼
- **解決**: 測試行為（Use Cases），不測試結構（Classes）

**問題5**: Test-First vs Test-Last的爭論
- **解決**: 量化反饋循環差異，證明Test-First更快

#### 提供的價值

**價值1: 歷史證據和理論基礎**
- Kent Beck, Martin Fowler, Google的一手引用
- 建立信心：這不是新方法，是回歸本質

**價值2: 清晰的對比分析**
- Sociable vs Solitary的視覺化對比
- Behavior vs Structure的經濟分析

**價值3: 實務應用指引**
- 決策樹：何時用Sociable vs Solitary
- 檢查清單：驗證測試穩定性
- Legacy Code漸進式導入策略

**價值4: 與其他方法論的整合**
- 與BDD方法論互補
- 與混合測試策略整合
- 形成完整的Behavior-Driven Testing體系

### 9.3 行動呼籲

#### 對正在痛苦中的團隊

如果你的團隊正在經歷：
- ❌ 測試程式碼是production code的2-4倍
- ❌ 重構時大量測試破裂
- ❌ 測試維護佔據30-40%時間
- ❌ 開發人員害怕重構

**行動方案**:
1. 閱讀本方法論理解痛點根源
2. 檢查你的測試是否耦合到結構
3. 嘗試將一個模組的測試改為Sociable風格
4. 體驗重構時測試穩定的感覺
5. 逐步擴展到整個專案

#### 對正在學習TDD的新手

如果你正在學習TDD：
- ⚠️ 網路上大多數教學是Solitary風格（錯誤）
- ⚠️ Wikipedia定義是Solitary風格（錯誤）
- ✅ Kent Beck原著是Sociable風格（正確）
- ✅ 本方法論是Sociable風格（正確）

**行動方案**:
1. 不要盲目跟隨網路教學
2. 閱讀Kent Beck《Test Driven Development By Example》
3. 閱讀本方法論理解Sociable vs Solitary
4. 從一開始就用正確的方法練習
5. 避免走入Solitary的痛苦陷阱

#### 對正在導入Clean Architecture的團隊

如果你的團隊正在使用Clean Architecture：
- ✅ 你已經有了可測試的架構
- ✅ 你有清晰的Use Cases層
- ✅ 你可以進行Acceptance Testing at Unit Level

**行動方案**:
1. 確認Use Cases作為測試邊界
2. 使用Sociable Unit Tests測試Use Cases
3. 只Mock Repository/Service Interfaces
4. 使用真實Domain Entities
5. 體驗快速且穩定的測試

### 9.4 延伸閱讀

#### 必讀書籍

**1. Test Driven Development: By Example**
- 作者: Kent Beck
- 重點: TDD原始定義，強調behavior

**2. Refactoring: Improving the Design of Existing Code**
- 作者: Martin Fowler
- 重點: 重構定義（改變結構不改變行為）

**3. Clean Architecture: A Craftsman's Guide to Software Structure and Design**
- 作者: Robert C. Martin (Uncle Bob)
- 重點: 依賴規則和可測試性設計

**4. Software Engineering at Google**
- 作者: Titus Winters, Tom Manshreck, Hyrum Wright
- 重點: 大規模工程實踐和測試策略

#### 相關方法論

**1. BDD測試方法論**
- 重點: Given-When-Then格式
- 關係: 提供測試描述的具體格式

**2. 混合測試策略方法論**
- 重點: 分層測試決策樹
- 關係: 提供各層級的測試策略

**3. Clean Architecture實作方法論**
- 重點: Hexagonal/Onion/Clean實作
- 關係: 提供可測試的架構設計

#### 線上資源

**1. Alistair Cockburn - Hexagonal Architecture**
- URL: https://alistair.cockburn.us/hexagonal-architecture/
- 重點: Hexagonal Architecture原始定義

**2. Dan North - Introducing BDD**
- URL: https://dannorth.net/introducing-bdd/
- 重點: BDD創造背景和動機

**3. Martin Fowler - Mocks Aren't Stubs**
- URL: https://martinfowler.com/articles/mocksArentStubs.html
- 重點: Classical TDD vs Mockist TDD對比

### 9.5 最終總結

#### 一句話總結

> **TDD從來不是痛苦的，只是你用錯了方法。**

#### 核心訊息

**錯誤的TDD**:
- 測試結構（Class, Methods）
- Mock所有協作者
- 測試破裂，維護昂貴

**正確的TDD**:
- 測試行為（Use Cases, API）
- 只Mock外部依賴
- 測試穩定，維護便宜

#### 行動起點

**如果只能記住三件事**:

1. **Module = Unit**, not Class
2. **Test Behavior**, not Structure
3. **Mock External Deps**, not Collaborators

**如果只能做一件事**:

找一個功能，嘗試用Sociable Unit Tests重寫測試，體驗重構時測試穩定的感覺。

#### 期望成果

採用本方法論後，你的團隊應該達到：
- ✅ 測試程式碼 ≈ Production code（不再是2-4倍）
- ✅ 重構時測試不需修改（不再破裂）
- ✅ 測試維護時間 < 15%（不再是30-40%）
- ✅ 開發人員喜歡重構（不再害怕）
- ✅ 開發速度提升20-30%（不再下降）

**這就是TDD應該有的樣子。**

---

## 附錄

### 附錄A: 術語對照表

| 英文 | 中文 | 定義 |
|------|------|------|
| Sociable Unit Tests | 社交式單元測試 | Unit = Module，只隔離外部依賴 |
| Solitary Unit Tests | 孤立式單元測試 | Unit = Class，隔離所有協作者 |
| Classical TDD | 經典TDD | Kent Beck, Martin Fowler的TDD流派 |
| Mockist TDD | Mock派TDD | London School的TDD流派 |
| Behavior | 行為 | 系統外部可觀察的反應 |
| Structure | 結構 | 系統內部的實作細節 |
| Driver Ports | 驅動埠 | Hexagonal Architecture的User-side API |
| Driven Ports | 被驅動埠 | Hexagonal Architecture的Server-side API |
| Executable Specifications | 可執行規格 | 用程式碼表達的需求 |
| Test Double | 測試替身 | Mock, Stub, Fake, Spy的統稱 |
| Falsifiability | 可證偽性 | 測試能夠失敗（不是false positive） |

### 附錄B: 快速參考卡

#### Sociable Unit Tests檢查清單

```markdown
✅ Sociable Unit Tests特徵：
- [ ] Unit = Module（不是Class）
- [ ] 測試只呼叫Module API
- [ ] 測試不知道內部類別
- [ ] 只Mock外部依賴（Database, File, External Service）
- [ ] 使用真實Domain Entities
- [ ] 使用真實Value Objects
- [ ] 重構時測試不需修改
- [ ] 測試使用業務語言描述
```

#### 測試穩定性驗證

```markdown
重構類型檢查：
- [ ] 改變內部邏輯 → 測試不變？
- [ ] 改變演算法 → 測試不變？
- [ ] 調整類別結構 → 測試不變？
- [ ] 重新命名方法 → 測試不變？

如果全部「測試不變」→ 正確 ✅
如果任何「測試需改」→ 錯誤 ❌
```

### 附錄C: 常見Anti-Patterns

#### Anti-Pattern 1: 為每個Class寫Test Class

```dart
// ❌ Anti-Pattern
class OrderService { ... }
class OrderServiceTest { ... } // 測試每個方法

class OrderValidator { ... }
class OrderValidatorTest { ... }

class OrderCalculator { ... }
class OrderCalculatorTest { ... }

// ✅ 正確
class SubmitOrderUseCase { ... }
class SubmitOrderUseCaseTest { ... } // 只測試Use Case
```

#### Anti-Pattern 2: 驗證方法呼叫次數

```dart
// ❌ Anti-Pattern
test('submitOrder calls repository.save once', () {
  await service.submitOrder(order);
  verify(mockRepository.save(any)).called(1);
  // 測試實作細節
});

// ✅ 正確
test('使用者提交訂單成功', () {
  final result = await useCase.execute(order);
  expect(result.isSuccess, true);
  // 測試行為結果
});
```

#### Anti-Pattern 3: Mock Domain Entities

```dart
// ❌ Anti-Pattern
test('test', () {
  final mockOrder = MockOrder();
  when(mockOrder.validate()).thenReturn(true);
  // 失去Domain邏輯測試
});

// ✅ 正確
test('test', () {
  final order = Order(...); // 真實Domain Entity
  // 測試真實Domain邏輯
});
```

---

**文件版本**: 1.0
**最後更新**: 2025-10-16
**維護者**: Behavior-Driven Testing方法論團隊
