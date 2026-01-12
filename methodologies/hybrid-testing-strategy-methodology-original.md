---
title: "混合測試策略方法論"
date: 2025-10-13
draft: false
description: "整合 BDD 和單元測試的分層測試策略,為層級隔離派工方法論提供測試設計補充"
tags: ["測試", "BDD", "方法論", "Clean Architecture", "Ticket"]
---

## 文件資訊

**目的**: 定義混合測試策略（BDD + 單元測試 + 整合測試），為 layered-ticket-methodology.md 提供測試設計補充，明確每層 ticket 的測試策略、量化指標和驗證標準。

**適用對象**:

- 開發人員 - 根據層級設計測試
- 專案經理 - 在 ticket 中定義測試策略
- Code Reviewer - 審查測試設計和品質
- 架構師 - 制定測試架構標準

**關鍵概念**:

- 分層測試決策樹
- 混合測試策略（BDD + 單元測試 + 整合測試）
- 測試覆蓋率量化指標
- Ticket 測試策略設計

**與其他方法論的關係**:

- 補充 `layered-ticket-methodology.md` 的測試設計部分
- 實踐 `bdd-testing-methodology.md` 的理論指引
- 整合 `clean-architecture-implementation-methodology.md` 的架構原則

---

## 第一章：方法論概述

### 1.1 為什麼需要混合測試策略

**問題背景**:

layered-ticket-methodology 定義了「單層修改原則」，但缺少測試設計指引：

- ❌ Layer 1 (UI) ticket 要怎麼測試？
- ❌ Layer 2 (Behavior) ticket 要怎麼測試？
- ❌ Layer 3 (UseCase) ticket 要怎麼測試？
- ❌ Layer 5 (Domain) ticket 要怎麼測試？
- ❌ 測試覆蓋率要求是什麼？

**根本原因**:

不同層級的程式碼特性不同，測試策略也應該不同。單一測試方法（純 BDD 或純單元測試）無法滿足所有層級的需求。

**混合測試策略解決的問題**:

1. **明確測試策略**: 每層 ticket 都有清楚的測試設計指引
2. **平衡測試成本**: 關鍵邏輯完整測試，簡單邏輯依賴上層測試
3. **確保測試品質**: 量化指標和驗證機制
4. **降低測試維護成本**: BDD 測試行為，單元測試實作細節

### 1.2 核心定位

**立場宣告**:

這是測試執行標準，補充 layered-ticket-methodology.md。我們不修改現有的單層修改原則，而是為每層提供測試設計指引。

**我們接受**:

- 不同層級需要不同測試策略
- UseCase 層必須 BDD 測試
- 複雜邏輯必須單元測試
- 測試覆蓋率必須量化驗證

**我們拒絕**:

- 所有層級使用相同測試方法
- 所有程式碼都寫單元測試（過度測試）
- 沒有測試覆蓋率要求（測試不足）
- 測試實作細節而非行為

### 1.3 解決方案概覽

混合測試策略 = BDD + 單元測試 + 整合測試：

```
Layer 1 (UI)         → 整合測試（關鍵流程）
Layer 2 (Behavior)   → 單元測試（複雜轉換）
Layer 3 (UseCase)    → BDD 測試（所有場景）
Layer 4 (Interface)  → 不測試（由實作層測試）
Layer 5 (Domain)     → 單元測試（複雜邏輯）
```

**判斷流程**:

1. 識別程式碼屬於哪一層
2. 根據決策樹判斷測試策略
3. 設計測試場景
4. 撰寫測試程式碼
5. 驗證測試覆蓋率

---

## 第二章：混合測試策略定義

### 2.1 定義與邊界

**定義**:

混合測試策略是整合 BDD、單元測試和整合測試的組合策略。根據程式碼的層級和複雜度，選擇最適合的測試方法。

**邊界**:

包含：
- 測試類型選擇標準
- 測試覆蓋率要求
- 測試品質驗證機制

不包含：
- 測試框架選擇（技術決策）
- 測試執行環境設置（基礎設施）
- CI/CD 整合（部署流程）

### 2.2 三種測試方法的定義

**BDD 測試（Behavior-Driven Development）**:

**定義**: 測試系統的業務行為，使用 Given-When-Then 格式描述場景。

**適用層級**: Layer 3 (UseCase)

**特點**:

- 測試行為而非實作
- 使用業務語言描述
- 與實作解耦，重構時測試穩定

---

**單元測試（Unit Testing）**:

**定義**: 測試單一元件（函式、類別）的功能，驗證輸入輸出的正確性。

**適用層級**: Layer 5 (Domain)、Layer 2 (Behavior)

**特點**:

- 測試粒度細，快速定位問題
- 涵蓋邊界條件和異常處理
- 測試與實作緊密，重構時可能需要修改

---

**整合測試（Integration Testing）**:

**定義**: 測試多個元件協作的流程，驗證端到端的使用者操作。

**適用層級**: Layer 1 (UI)

**特點**:

- 測試完整的使用者流程
- 測試成本高，執行速度慢
- 驗證系統整體行為

### 2.3 核心原則

>**原則 1: UseCase 層必須 BDD**
>
> UseCase 層代表業務流程，必須使用 BDD 測試所有場景（正常流程、異常流程、邊界條件）。

---

>**原則 2: 複雜邏輯必須單元測試**
>
> Domain 層的複雜業務規則、Behavior 層的複雜轉換邏輯，必須使用單元測試覆蓋所有分支和邊界條件。

---

>**原則 3: 關鍵流程必須整合測試**
>
> UI 層的關鍵互動流程（登入、支付、表單提交），必須使用整合測試驗證端到端操作。

---

>**原則 4: 簡單邏輯依賴上層測試**
>
> 簡單的 getter/setter、直接映射、CRUD Entity，不需要獨立測試，由上層測試覆蓋。

---

## 第三章：分層測試決策樹

### 3.1 決策樹概覽

```
程式碼屬於哪一層？
│
├─ Layer 1 (UI/Presentation)
│  │
│  └─ 是否為關鍵互動流程？
│     ├─ 是 → 整合測試（模擬使用者操作）
│     │       範例：登入、支付、表單提交
│     │
│     └─ 否 → 人工測試 + Snapshot 測試
│             範例：靜態頁面、簡單展示
│
├─ Layer 2 (Application/Behavior)
│  │
│  └─ 是否有複雜轉換邏輯？
│     ├─ 是 → 單元測試
│     │       範例：多欄位資料轉換、複雜計算
│     │
│     └─ 否 → 依賴 UseCase 層測試覆蓋
│             範例：簡單 DTO → ViewModel 映射
│
├─ Layer 3 (UseCase)
│  │
│  └─ 所有業務行為 → BDD 測試（Given-When-Then）
│                     必須涵蓋：正常流程、異常流程、邊界條件
│
├─ Layer 4 (Domain Events/Interfaces)
│  │
│  └─ 介面定義 → 不需要測試（由實作層測試）
│
└─ Layer 5 (Domain Implementation)
   │
   └─ 是否有複雜業務規則或計算邏輯？
      ├─ 是 → 單元測試（全面覆蓋邊界條件）
      │       範例：訂單金額計算、值物件驗證、狀態轉換
      │
      └─ 否 → 依賴 UseCase 層測試覆蓋
              範例：簡單 CRUD Entity、純資料容器
```

### 3.2 判斷標準詳解

**如何判斷「關鍵互動流程」（Layer 1）**:

| 問題 | 是 | 否 |
|------|----|----|
| 流程失敗會影響核心業務嗎？ | 關鍵流程 | 非關鍵流程 |
| 需要多步驟使用者操作嗎？ | 關鍵流程 | 非關鍵流程 |
| 涉及金流或敏感資料嗎？ | 關鍵流程 | 非關鍵流程 |

範例：

- ✅ 關鍵流程：使用者登入、訂單支付、會員註冊、表單提交
- ❌ 非關鍵流程：關於我們頁面、商品列表展示、靜態文章頁

---

**如何判斷「複雜轉換邏輯」（Layer 2）**:

| 問題 | 是 | 否 |
|------|----|----|
| 轉換包含條件判斷嗎？ | 複雜轉換 | 簡單轉換 |
| 轉換包含計算邏輯嗎？ | 複雜轉換 | 簡單轉換 |
| 轉換涉及多個來源資料嗎？ | 複雜轉換 | 簡單轉換 |
| 轉換邏輯超過 10 行程式碼嗎？ | 複雜轉換 | 簡單轉換 |

範例：

- ✅ 複雜轉換：訂單狀態對應顯示文字和顏色、多欄位資料聚合、格式化計算
- ❌ 簡單轉換：DTO 欄位直接映射到 ViewModel、getter/setter

---

**如何判斷「複雜業務規則」（Layer 5）**:

| 問題 | 是 | 否 |
|------|----|----|
| 包含業務規則驗證嗎？ | 複雜邏輯 | 簡單邏輯 |
| 包含計算邏輯嗎？ | 複雜邏輯 | 簡單邏輯 |
| 包含狀態轉換邏輯嗎？ | 複雜邏輯 | 簡單邏輯 |
| 包含不變量檢查嗎？ | 複雜邏輯 | 簡單邏輯 |

範例：

- ✅ 複雜邏輯：訂單金額計算（折扣、運費、稅）、Email 格式驗證、訂單狀態轉換規則
- ❌ 簡單邏輯：純資料容器 Entity、簡單的 CRUD 操作

---

## 第四章：各層測試策略詳解

### 4.1 Layer 1 (UI/Presentation) 測試策略

**定義**:

UI 層負責視覺呈現和使用者互動，包含頁面、表單、按鈕、導航等。

**測試類型**:

整合測試（關鍵流程）+ 人工測試（非關鍵流程）

**必須測試的場景**:

- ✅ 使用者登入流程
- ✅ 訂單支付流程
- ✅ 表單提交（註冊、聯絡我們）
- ✅ 關鍵導航流程
- ✅ 錯誤處理（網路錯誤、驗證失敗）

**選擇性測試的場景**:

- ⚠️ 靜態頁面展示
- ⚠️ 簡單列表顯示
- ⚠️ 純展示元件

**測試重點**:

1. 使用者操作正確觸發事件
2. 錯誤訊息正確顯示
3. 導航流程正確
4. 關鍵互動可完成

**範例**:

✅ **正確：整合測試關鍵流程**

```dart
testWidgets('使用者登入流程 - 成功', (tester) async {
  // Given: 使用者在登入頁面
  await tester.pumpWidget(MyApp());
  await tester.pumpAndSettle();
  
  // When: 使用者輸入帳號密碼並點擊登入
  await tester.enterText(
    find.byKey(Key('email_field')),
    'user@example.com',
  );
  await tester.enterText(
    find.byKey(Key('password_field')),
    'password123',
  );
  await tester.tap(find.byKey(Key('login_button')));
  await tester.pumpAndSettle();
  
  // Then: 使用者進入首頁
  expect(find.byType(HomePage), findsOneWidget);
  expect(find.text('歡迎回來'), findsOneWidget);
});

testWidgets('使用者登入流程 - 失敗（帳號密碼錯誤）', (tester) async {
  // Given: 使用者在登入頁面
  await tester.pumpWidget(MyApp());
  
  // When: 使用者輸入錯誤的帳號密碼
  await tester.enterText(
    find.byKey(Key('email_field')),
    'wrong@example.com',
  );
  await tester.enterText(
    find.byKey(Key('password_field')),
    'wrongpassword',
  );
  await tester.tap(find.byKey(Key('login_button')));
  await tester.pumpAndSettle();
  
  // Then: 顯示錯誤訊息
  expect(find.text('帳號或密碼錯誤'), findsOneWidget);
  expect(find.byType(HomePage), findsNothing);
});
```

❌ **錯誤：測試所有 UI 元件**

```dart
// 不需要測試的場景
testWidgets('關於我們頁面顯示正確', (tester) async {
  // 靜態頁面不需要整合測試
  // 可以用人工測試或 Snapshot 測試
});

testWidgets('按鈕顏色正確', (tester) async {
  // UI 樣式細節不需要測試
  // 可以用視覺回歸測試工具
});
```

**驗證標準**:

- [ ] 所有關鍵互動流程都有整合測試
- [ ] 測試涵蓋成功和失敗場景
- [ ] 測試驗證使用者可觀察的結果（頁面、訊息）
- [ ] 測試不依賴實作細節（Widget 內部狀態）

### 4.2 Layer 2 (Application/Behavior) 測試策略

**定義**:

Behavior 層負責 ViewModel 轉換、事件處理、UI 邏輯，是 UI 和 UseCase 之間的橋樑。

**測試類型**:

單元測試（複雜轉換）+ 依賴上層測試（簡單轉換）

**必須測試的場景**:

- ✅ 複雜資料轉換（多欄位聚合、條件判斷）
- ✅ 多步驟狀態管理
- ✅ 格式化邏輯（日期、金額、文字）
- ✅ 條件顯示邏輯

**選擇性測試的場景**:

- ⚠️ 簡單 getter/setter
- ⚠️ 直接欄位映射（DTO → ViewModel）
- ⚠️ 純資料傳遞

**測試重點**:

1. 轉換邏輯正確性
2. 邊界條件處理
3. null 值處理
4. 格式化結果正確

**範例**:

✅ **正確：單元測試複雜轉換**

```dart
group('OrderViewModel', () {
  test('訂單狀態轉換為顯示文字和顏色 - 待付款', () {
    // Given: 訂單狀態為 pending
    final orderDTO = OrderDTO(
      id: 'order-001',
      status: OrderStatus.pending,
      amount: 1000,
    );
    
    // When: 轉換為 ViewModel
    final viewModel = OrderViewModel.fromDTO(orderDTO);
    
    // Then: 顯示文字和顏色正確
    expect(viewModel.statusText, '待付款');
    expect(viewModel.statusColor, Colors.orange);
    expect(viewModel.canCancel, true);
  });
  
  test('訂單狀態轉換為顯示文字和顏色 - 已完成', () {
    // Given: 訂單狀態為 completed
    final orderDTO = OrderDTO(
      id: 'order-001',
      status: OrderStatus.completed,
      amount: 1000,
    );
    
    // When: 轉換為 ViewModel
    final viewModel = OrderViewModel.fromDTO(orderDTO);
    
    // Then: 顯示文字和顏色正確
    expect(viewModel.statusText, '已完成');
    expect(viewModel.statusColor, Colors.green);
    expect(viewModel.canCancel, false);
  });
  
  test('訂單金額格式化 - 千分位顯示', () {
    // Given: 訂單金額為 123456
    final orderDTO = OrderDTO(
      id: 'order-001',
      status: OrderStatus.pending,
      amount: 123456,
    );
    
    // When: 轉換為 ViewModel
    final viewModel = OrderViewModel.fromDTO(orderDTO);
    
    // Then: 金額格式化為千分位
    expect(viewModel.formattedAmount, 'NT$ 123,456');
  });
  
  test('訂單日期格式化 - 顯示相對時間', () {
    // Given: 訂單建立於 1 小時前
    final orderDTO = OrderDTO(
      id: 'order-001',
      status: OrderStatus.pending,
      amount: 1000,
      createdAt: DateTime.now().subtract(Duration(hours: 1)),
    );
    
    // When: 轉換為 ViewModel
    final viewModel = OrderViewModel.fromDTO(orderDTO);
    
    // Then: 日期格式化為相對時間
    expect(viewModel.formattedCreatedAt, '1 小時前');
  });
});
```

❌ **錯誤：測試簡單映射**

```dart
// 不需要的測試
test('ViewModel 欄位映射正確', () {
  final dto = OrderDTO(id: '001', amount: 100);
  final viewModel = OrderViewModel.fromDTO(dto);
  
  expect(viewModel.id, '001');
  expect(viewModel.amount, 100);
  
  // 簡單的欄位映射不需要測試
  // 這些由 UseCase 層測試覆蓋
});
```

✅ **正確：簡單轉換依賴 UseCase 測試**

```dart
// 不寫獨立測試，在 UseCase 層測試中驗證
test('使用者查詢訂單成功', () async {
  // Given, When: 執行 UseCase
  final result = await getOrderUseCase.execute('order-001');
  
  // Then: 驗證 ViewModel 轉換正確（間接測試 Behavior 層）
  expect(result.order.id, 'order-001');
  expect(result.order.formattedAmount, 'NT$ 1,000');
  
  // 簡單轉換邏輯由此測試覆蓋，不需要獨立測試
});
```

**驗證標準**:

- [ ] 複雜轉換邏輯都有單元測試
- [ ] 測試涵蓋所有分支和條件
- [ ] 測試涵蓋 null 值和邊界條件
- [ ] 簡單映射不寫獨立測試

### 4.3 Layer 3 (UseCase) 測試策略

**定義**:

UseCase 層負責編排業務流程，整合 Domain 邏輯和 Repository/Service。

**測試類型**:

BDD 測試（所有場景，使用 Given-When-Then）

**必須測試的場景**:

- ✅ 正常流程（Happy Path）
- ✅ 異常流程（業務規則驗證失敗）
- ✅ 邊界條件（極端值、null、空集合）
- ✅ 錯誤處理（網路錯誤、超時）

**測試重點**:

1. 業務流程完整性
2. 業務規則正確執行
3. 錯誤處理和回饋
4. 事件發布（如適用）

**範例**:

詳細範例請參考「BDD 測試方法論」第九章。

**驗證標準**:

- [ ] 所有 UseCase 都有 BDD 測試
- [ ] 每個 UseCase 至少涵蓋：1 個正常流程、2 個異常流程、3 個邊界條件
- [ ] 測試使用 Given-When-Then 格式
- [ ] 測試描述使用業務語言
- [ ] 只 Mock 外層依賴（Repository, Service）
- [ ] 使用真實的 Domain Entity 和 Value Object

### 4.4 Layer 4 (Domain Events/Interfaces) 測試策略

**定義**:

Interface 層只定義抽象介面（Port），沒有實作邏輯。

**測試類型**:

不測試

**理由**:

介面本身沒有可測試的行為。介面的正確性由以下方式驗證：
1. UseCase 層測試透過 Mock 驗證介面使用正確
2. Infrastructure 層實作測試驗證介面實作正確

**驗證標準**:

- [ ] Interface 定義清晰（方法簽名、參數、返回值）
- [ ] Interface 有完整的文檔註解
- [ ] 沒有為 Interface 撰寫測試

### 4.5 Layer 5 (Domain Implementation) 測試策略

**定義**:

Domain 層包含核心業務邏輯、Entity、Value Object、業務規則。

**測試類型**:

單元測試（複雜邏輯）+ 依賴上層測試（簡單邏輯）

**必須測試的場景**:

- ✅ 業務規則驗證（例如：訂單金額計算）
- ✅ 值物件驗證（例如：Email 格式、金額範圍）
- ✅ 實體不變量（例如：訂單狀態轉換規則）
- ✅ 複雜計算邏輯

**選擇性測試的場景**:

- ⚠️ 簡單 CRUD Entity
- ⚠️ 純資料容器
- ⚠️ 沒有業務規則的 Entity

**測試重點**:

1. 業務規則正確性
2. 所有分支和邊界條件
3. 異常拋出時機
4. 不變量維持

**範例**:

✅ **正確：單元測試複雜業務規則**

```dart
group('OrderAmount (Value Object)', () {
  test('建立有效金額 - 正整數', () {
    // Given & When: 建立金額 100
    final amount = OrderAmount(100);
    
    // Then: 金額建立成功
    expect(amount.value, 100);
  });
  
  test('建立無效金額 - 負數拋出例外', () {
    // Given & When: 嘗試建立負數金額
    // Then: 拋出 InvalidAmountException
    expect(
      () => OrderAmount(-100),
      throwsA(isA<InvalidAmountException>()),
    );
  });
  
  test('建立無效金額 - 零拋出例外', () {
    // Given & When: 嘗試建立零金額
    // Then: 拋出 InvalidAmountException
    expect(
      () => OrderAmount(0),
      throwsA(isA<InvalidAmountException>()),
    );
  });
  
  test('建立無效金額 - 超過上限拋出例外', () {
    // Given & When: 嘗試建立超過上限的金額
    // Then: 拋出 InvalidAmountException
    expect(
      () => OrderAmount(1000001), // 上限 100 萬
      throwsA(isA<InvalidAmountException>()),
    );
  });
});

group('Order (Entity)', () {
  test('訂單總金額計算 - 含運費', () {
    // Given: 訂單金額 500，運費 60
    final order = Order(
      amount: OrderAmount(500),
      shippingFee: ShippingFee(60),
      items: [OrderItem(productId: 'prod-001', quantity: 1, price: 500)],
    );
    
    // When: 計算總金額
    final total = order.calculateTotal();
    
    // Then: 總金額 = 金額 + 運費
    expect(total.value, 560);
  });
  
  test('訂單總金額計算 - 滿額免運', () {
    // Given: 訂單金額 1000（滿 1000 免運）
    final order = Order(
      amount: OrderAmount(1000),
      shippingFee: ShippingFee(60),
      items: [OrderItem(productId: 'prod-001', quantity: 2, price: 500)],
    );
    
    // When: 計算總金額
    final total = order.calculateTotal();
    
    // Then: 總金額 = 金額（免運費）
    expect(total.value, 1000);
  });
  
  test('訂單狀態轉換 - pending 可轉為 confirmed', () {
    // Given: 訂單狀態為 pending
    final order = Order(
      id: 'order-001',
      status: OrderStatus.pending,
      amount: OrderAmount(100),
    );
    
    // When: 確認訂單
    order.confirm();
    
    // Then: 訂單狀態轉為 confirmed
    expect(order.status, OrderStatus.confirmed);
  });
  
  test('訂單狀態轉換 - completed 不可轉為 cancelled', () {
    // Given: 訂單狀態為 completed
    final order = Order(
      id: 'order-001',
      status: OrderStatus.completed,
      amount: OrderAmount(100),
    );
    
    // When & Then: 嘗試取消訂單拋出例外
    expect(
      () => order.cancel(),
      throwsA(isA<InvalidStatusTransitionException>()),
    );
  });
});

group('Email (Value Object)', () {
  test('建立有效 Email', () {
    // Given & When: 建立有效 Email
    final email = Email('user@example.com');
    
    // Then: Email 建立成功
    expect(email.value, 'user@example.com');
  });
  
  test('建立無效 Email - 缺少 @ 符號', () {
    // Given & When: 建立無效 Email
    // Then: 拋出 InvalidEmailException
    expect(
      () => Email('invalid-email'),
      throwsA(isA<InvalidEmailException>()),
    );
  });
  
  test('建立無效 Email - 缺少網域', () {
    // Given & When: 建立無效 Email
    // Then: 拋出 InvalidEmailException
    expect(
      () => Email('user@'),
      throwsA(isA<InvalidEmailException>()),
    );
  });
});
```

❌ **錯誤：測試簡單 CRUD Entity**

```dart
// 不需要的測試
group('Product (Entity)', () {
  test('建立 Product', () {
    final product = Product(
      id: 'prod-001',
      name: 'Product A',
      price: 100,
    );
    
    expect(product.id, 'prod-001');
    expect(product.name, 'Product A');
    expect(product.price, 100);
    
    // 簡單的資料容器不需要測試
    // 這些由 UseCase 層測試覆蓋
  });
});
```

**驗證標準**:

- [ ] 所有業務規則都有單元測試
- [ ] 所有值物件驗證都有測試
- [ ] 所有實體不變量都有測試
- [ ] 測試涵蓋所有分支和邊界條件
- [ ] 測試驗證異常拋出的正確性
- [ ] 簡單 CRUD Entity 不寫獨立測試

---

## 第五章：測試覆蓋率量化指標

### 5.1 覆蓋率指標定義

**UseCase 層（Layer 3）**:

- **行為場景覆蓋率**: 100%
  - 定義：所有業務場景（正常、異常、邊界）都有對應測試
  - 驗證：檢查測試清單，確認每個場景都有測試

- **程式碼覆蓋率**: 不強制（副產品）
  - 定義：測試執行時涵蓋的程式碼行數比例
  - 說明：BDD 聚焦行為，程式碼覆蓋率是副產品而非目標

---

**Domain 層（Layer 5，複雜邏輯）**:

- **程式碼覆蓋率**: 100%
  - 定義：所有業務規則、值物件驗證、實體不變量的程式碼都被測試執行
  - 驗證：使用覆蓋率工具（如 `flutter test --coverage`）檢查

- **分支覆蓋率**: 100%
  - 定義：所有 if-else、switch-case 分支都被測試執行
  - 驗證：覆蓋率報告顯示所有分支都被覆蓋

---

**Behavior 層（Layer 2，複雜轉換）**:

- **邏輯覆蓋率**: 100%
  - 定義：所有轉換邏輯的條件判斷都被測試
  - 驗證：檢查測試是否涵蓋所有轉換分支

---

**UI 層（Layer 1，關鍵流程）**:

- **關鍵路徑覆蓋率**: 100%
  - 定義：所有關鍵互動流程都有整合測試
  - 驗證：檢查關鍵流程清單，確認都有測試

---

**整體專案**:

- **新增程式碼覆蓋率**: 80%
  - 定義：本次 commit 新增的程式碼被測試執行的比例
  - 驗證：CI/CD 工具檢查 diff 覆蓋率

- **核心業務邏輯覆蓋率**: 100%
  - 定義：UseCase 和 Domain（複雜邏輯）的覆蓋率
  - 驗證：覆蓋率工具針對特定目錄檢查

### 5.2 量化指標檢查清單

**Ticket 完成前檢查**:

- [ ] UseCase 層：所有業務場景都有 BDD 測試
- [ ] Domain 層（複雜邏輯）：程式碼覆蓋率 100%
- [ ] Behavior 層（複雜轉換）：邏輯覆蓋率 100%
- [ ] UI 層（關鍵流程）：整合測試已撰寫
- [ ] 整體專案：新增程式碼覆蓋率 ≥ 80%

**Code Review 檢查**:

- [ ] 測試類型符合分層策略
- [ ] 測試覆蓋率達標
- [ ] 測試品質符合標準（詳見第九章）

**CI/CD 自動檢查**:

- [ ] 所有測試通過
- [ ] 覆蓋率達標（整體 ≥ 80%）
- [ ] 沒有測試被跳過（skip）

### 5.3 覆蓋率工具使用

**Flutter/Dart 專案**:

```bash
# 執行測試並產生覆蓋率報告
flutter test --coverage

# 檢視覆蓋率報告（需要安裝 lcov）
genhtml coverage/lcov.info -o coverage/html
open coverage/html/index.html
```

**檢查特定目錄覆蓋率**:

```bash
# 只檢查 UseCase 層覆蓋率
flutter test --coverage test/use_case/

# 只檢查 Domain 層覆蓋率
flutter test --coverage test/domain/
```

**設置覆蓋率門檻**:

在 CI/CD 配置中設置：

```yaml
# .github/workflows/test.yml
- name: Check coverage
  run: |
    flutter test --coverage
    # 檢查覆蓋率是否達 80%
    lcov --summary coverage/lcov.info | grep "lines......: 8[0-9]" || exit 1
```

---

## 第六章：Ticket 測試策略設計

### 6.1 Ticket 模板新增欄位

**在 layered-ticket-methodology 的 Ticket 模板中新增「測試策略」欄位**:

```markdown
## Ticket 資訊

### 基本資訊
- Ticket ID: [自動產生]
- 標題: [簡短描述]
- 層級: Layer X
- 類型: 新增/修改/重構/修復

### 測試策略
- **測試類型**: BDD / 單元測試 / 整合測試 / 不需要測試
- **測試範圍**: [列出必須測試的場景]
- **測試工具**: [測試框架名稱]
- **覆蓋率要求**: [具體數值或標準]
- **依賴關係**: 獨立測試 / 依賴 [Layer X] 測試

### 實作內容
[...]

### 測試場景清單
- [ ] 場景 1: [描述]
- [ ] 場景 2: [描述]
- [ ] 場景 3: [描述]

### 驗收標準
- [ ] 功能實作完成
- [ ] 測試全部通過
- [ ] 覆蓋率達標
- [ ] Code Review 通過
```

### 6.2 不同層級 Ticket 的測試策略範例

#### 範例 1: Layer 3 (UseCase) Ticket

```markdown
## Ticket 資訊

### 基本資訊
- Ticket ID: TICKET-001
- 標題: 實作「使用者提交訂單」UseCase
- 層級: Layer 3 (UseCase)
- 類型: 新增

### 測試策略
- **測試類型**: BDD 測試（Given-When-Then）
- **測試範圍**: 
  - 正常流程：使用者提交訂單成功
  - 異常流程：商品庫存不足
  - 異常流程：訂單金額無效
  - 邊界條件：訂單金額為 0
  - 邊界條件：訂單金額為負數
  - 邊界條件：訂單金額超過上限
- **測試工具**: Dart test + Mockito
- **覆蓋率要求**: 100% 行為場景覆蓋
- **依賴關係**: 獨立測試（Mock Repository 和 Service）

### 實作內容
[...]

### 測試場景清單
- [ ] 場景 1: 使用者提交訂單成功
- [ ] 場景 2: 使用者提交訂單失敗 - 商品庫存不足
- [ ] 場景 3: 使用者提交訂單失敗 - 訂單金額無效
- [ ] 場景 4: 邊界條件 - 訂單金額為 0
- [ ] 場景 5: 邊界條件 - 訂單金額為負數
- [ ] 場景 6: 邊界條件 - 訂單金額超過上限

### 驗收標準
- [ ] SubmitOrderUseCase 實作完成
- [ ] 所有 BDD 測試通過
- [ ] 行為場景覆蓋率 100%
- [ ] Given-When-Then 格式正確
- [ ] 只 Mock 外層依賴
- [ ] Code Review 通過
```

#### 範例 2: Layer 5 (Domain) Ticket

```markdown
## Ticket 資訊

### 基本資訊
- Ticket ID: TICKET-002
- 標題: 實作 OrderAmount 值物件驗證邏輯
- 層級: Layer 5 (Domain)
- 類型: 新增

### 測試策略
- **測試類型**: 單元測試
- **測試範圍**:
  - 建立有效金額（正整數）
  - 建立無效金額（0, 負數, 超過上限）
  - 金額比較邏輯
  - 金額運算邏輯（加減）
- **測試工具**: Dart test
- **覆蓋率要求**: 100% 程式碼覆蓋率 + 100% 分支覆蓋率
- **依賴關係**: 獨立測試（不依賴其他層）

### 實作內容
[...]

### 測試場景清單
- [ ] 建立有效金額 - 正整數
- [ ] 建立無效金額 - 0 拋出例外
- [ ] 建立無效金額 - 負數拋出例外
- [ ] 建立無效金額 - 超過上限拋出例外
- [ ] 金額比較 - 相等
- [ ] 金額比較 - 大於/小於
- [ ] 金額運算 - 加法
- [ ] 金額運算 - 減法

### 驗收標準
- [ ] OrderAmount 值物件實作完成
- [ ] 所有單元測試通過
- [ ] 程式碼覆蓋率 100%
- [ ] 分支覆蓋率 100%
- [ ] Code Review 通過
```

#### 範例 3: Layer 2 (Behavior) Ticket - 複雜轉換

```markdown
## Ticket 資訊

### 基本資訊
- Ticket ID: TICKET-003
- 標題: 實作 OrderViewModel 訂單狀態轉換邏輯
- 層級: Layer 2 (Behavior)
- 類型: 新增

### 測試策略
- **測試類型**: 單元測試
- **測試範圍**:
  - 訂單狀態對應顯示文字（pending, confirmed, completed, cancelled）
  - 訂單狀態對應顯示顏色
  - 訂單狀態對應可操作按鈕（可取消、可確認）
  - 金額格式化（千分位）
  - 日期格式化（相對時間）
- **測試工具**: Dart test
- **覆蓋率要求**: 100% 邏輯覆蓋率
- **依賴關係**: 獨立測試（不依賴 UseCase）

### 實作內容
[...]

### 測試場景清單
- [ ] 狀態轉換 - pending → 待付款 / 橘色 / 可取消
- [ ] 狀態轉換 - confirmed → 已確認 / 藍色 / 不可取消
- [ ] 狀態轉換 - completed → 已完成 / 綠色 / 不可取消
- [ ] 狀態轉換 - cancelled → 已取消 / 灰色 / 不可取消
- [ ] 金額格式化 - 123456 → NT$ 123,456
- [ ] 日期格式化 - 1 小時前

### 驗收標準
- [ ] OrderViewModel 轉換邏輯實作完成
- [ ] 所有單元測試通過
- [ ] 邏輯覆蓋率 100%
- [ ] Code Review 通過
```

#### 範例 4: Layer 2 (Behavior) Ticket - 簡單映射

```markdown
## Ticket 資訊

### 基本資訊
- Ticket ID: TICKET-004
- 標題: 實作 ProductViewModel 簡單欄位映射
- 層級: Layer 2 (Behavior)
- 類型: 新增

### 測試策略
- **測試類型**: 不需要獨立測試
- **測試範圍**: N/A（簡單映射，由 UseCase 層測試覆蓋）
- **測試工具**: N/A
- **覆蓋率要求**: 由 UseCase 層測試達成
- **依賴關係**: 依賴 Layer 3 (UseCase) 測試

### 實作內容
實作 ProductViewModel.fromDTO，直接映射欄位：
- id → id
- name → name
- price → price
- imageUrl → imageUrl

### 測試場景清單
- [ ] 由 GetProductUseCase 測試驗證映射正確性

### 驗收標準
- [ ] ProductViewModel 實作完成
- [ ] GetProductUseCase 測試通過（間接驗證）
- [ ] Code Review 通過
```

#### 範例 5: Layer 1 (UI) Ticket - 關鍵流程

```markdown
## Ticket 資訊

### 基本資訊
- Ticket ID: TICKET-005
- 標題: 實作使用者登入頁面和流程
- 層級: Layer 1 (UI)
- 類型: 新增

### 測試策略
- **測試類型**: 整合測試（Widget Test）
- **測試範圍**:
  - 使用者輸入帳號密碼並成功登入
  - 使用者輸入錯誤帳號密碼顯示錯誤訊息
  - 使用者未填寫欄位點擊登入顯示驗證錯誤
- **測試工具**: Flutter Widget Test
- **覆蓋率要求**: 關鍵路徑 100% 覆蓋
- **依賴關係**: 整合測試（Mock LoginUseCase）

### 實作內容
[...]

### 測試場景清單
- [ ] 使用者登入成功 - 進入首頁
- [ ] 使用者登入失敗 - 帳號密碼錯誤
- [ ] 使用者登入失敗 - 未填寫欄位
- [ ] 使用者點擊「忘記密碼」- 進入重設密碼頁

### 驗收標準
- [ ] 登入頁面 UI 實作完成
- [ ] 所有整合測試通過
- [ ] 關鍵路徑覆蓋率 100%
- [ ] 人工測試通過
- [ ] Code Review 通過
```

### 6.3 測試策略決策流程

**Ticket 建立時的決策流程**:

```
1. 識別程式碼屬於哪一層？
   → 查看 Ticket 的「層級」欄位

2. 根據決策樹判斷測試類型
   → Layer 1: 是否關鍵流程？
   → Layer 2: 是否複雜轉換？
   → Layer 3: 必須 BDD
   → Layer 4: 不測試
   → Layer 5: 是否複雜邏輯？

3. 填寫「測試策略」欄位
   → 測試類型
   → 測試範圍
   → 覆蓋率要求

4. 列出測試場景清單
   → 正常流程
   → 異常流程
   → 邊界條件

5. 設定驗收標準
   → 包含測試相關項目
```

---

## 第七章：技術性測試檢查清單

### 7.1 為什麼需要技術性檢查清單

**問題背景**:

BDD 強調業務場景，可能忽略技術性的邊界條件：

- Null 值處理
- 空集合處理
- 併發場景
- 網路錯誤
- 超時處理

這些「非功能性」測試容易被遺漏，導致系統穩定性風險。

**解決方案**:

建立技術性測試檢查清單，在測試設計階段強制檢查。

### 7.2 檢查清單內容

**必須檢查的項目**:

#### 1. Null 值處理

- [ ] 輸入參數為 null 時的行為（拋出例外或預設值）
- [ ] 回傳值可能為 null 的情況
- [ ] Optional 欄位為 null 的處理

**範例**:

```dart
test('使用者提交訂單失敗 - UserId 為 null', () {
  expect(
    () => Order(amount: OrderAmount(100), userId: null),
    throwsA(isA<ArgumentError>()),
  );
});
```

#### 2. 空集合處理

- [ ] 輸入集合為空時的行為
- [ ] 回傳空集合而非 null
- [ ] 空集合的迭代邏輯

**範例**:

```dart
test('使用者提交訂單失敗 - 訂單項目為空', () {
  final order = Order(
    amount: OrderAmount(100),
    userId: UserId('user-001'),
    items: [], // 空集合
  );
  
  final result = await useCase.execute(order);
  
  expect(result.isSuccess, false);
  expect(result.error, '訂單必須包含至少一項商品');
});
```

#### 3. 邊界值測試

- [ ] 數值為 0
- [ ] 數值為負數
- [ ] 數值為最大值
- [ ] 字串長度為 0
- [ ] 字串長度超過限制

**範例**:

```dart
test('訂單金額邊界值 - 0', () {
  expect(
    () => OrderAmount(0),
    throwsA(isA<InvalidAmountException>()),
  );
});

test('訂單金額邊界值 - 最大值', () {
  expect(
    () => OrderAmount(1000001), // 上限 100 萬
    throwsA(isA<InvalidAmountException>()),
  );
});
```

#### 4. 異常處理

- [ ] 網路錯誤（連線失敗、超時）
- [ ] 資料庫錯誤（儲存失敗、查詢失敗）
- [ ] 外部 API 錯誤（回應異常、格式錯誤）
- [ ] 業務規則驗證失敗

**範例**:

```dart
test('使用者提交訂單失敗 - 網路連線失敗', () async {
  when(mockRepository.save(any))
      .thenThrow(NetworkException('連線失敗'));
  
  final result = await useCase.execute(order);
  
  expect(result.isSuccess, false);
  expect(result.error, '網路連線失敗，請稍後再試');
});

test('使用者提交訂單失敗 - 資料庫儲存失敗', () async {
  when(mockRepository.save(any))
      .thenAnswer((_) async => SaveResult.failure('儲存失敗'));
  
  final result = await useCase.execute(order);
  
  expect(result.isSuccess, false);
  expect(result.message, '訂單提交失敗，請稍後再試');
});
```

#### 5. 併發場景（如適用）

- [ ] 多個請求同時執行
- [ ] 資料競爭條件（Race Condition）
- [ ] 重複提交防護

**範例**:

```dart
test('使用者重複提交訂單 - 第二次提交被拒絕', () async {
  final order = Order(id: 'order-001', ...);
  
  // 第一次提交成功
  await useCase.execute(order);
  
  // 第二次提交失敗（重複提交）
  final result = await useCase.execute(order);
  
  expect(result.isSuccess, false);
  expect(result.error, '訂單已提交，請勿重複操作');
});
```

#### 6. 資料驗證

- [ ] 格式驗證（Email, Phone, URL）
- [ ] 範圍驗證（數值範圍、字串長度）
- [ ] 必填欄位驗證

**範例**:

```dart
test('Email 格式驗證 - 無效格式', () {
  expect(
    () => Email('invalid-email'),
    throwsA(isA<InvalidEmailException>()),
  );
});

test('訂單備註長度驗證 - 超過 200 字', () {
  final longNote = 'a' * 201;
  
  expect(
    () => Order(amount: OrderAmount(100), note: longNote),
    throwsA(isA<ValidationException>()),
  );
});
```

### 7.3 檢查清單使用流程

**測試設計階段**:

1. 列出業務場景（正常、異常、邊界）
2. 使用技術性檢查清單逐項檢查
3. 補充遺漏的技術性測試場景
4. 撰寫測試程式碼

**Code Review 階段**:

Reviewer 必須檢查：
- [ ] 技術性檢查清單是否完整勾選
- [ ] 遺漏的項目是否有正當理由（例如：不適用）

**驗收標準**:

- [ ] 技術性檢查清單全部勾選
- [ ] 所有技術性測試通過

---

## 第八章：測試輔助工具設計

### 8.1 為什麼需要測試輔助工具

**問題背景**:

UseCase 層的 BDD 測試需要：
- Mock 多個依賴（Repository, Service, Event Publisher）
- 準備複雜的測試資料（DTO, Entity, Value Object）
- 重複的測試設置程式碼

導致測試程式碼冗長、維護成本高。

**解決方案**:

建立測試輔助工具：
- Test Helper: 集中管理 Mock 物件建立
- Builder Pattern: 簡化測試資料建立
- Test Fixture: 提供預設測試資料

### 8.2 Test Helper 設計

**設計原則**:

1. 集中管理 Mock 物件建立
2. 提供預設 Mock 行為
3. 支援自訂 Mock 行為
4. 命名清晰易懂

**範例**:

```dart
/// UseCase 測試輔助工具
class UseCaseTestHelper {
  /// 建立 Mock OrderRepository
  static MockOrderRepository createMockOrderRepository({
    SaveResult? saveResult,
    Order? findByIdResult,
  }) {
    final mock = MockOrderRepository();
    
    if (saveResult != null) {
      when(mock.save(any)).thenAnswer((_) async => saveResult);
    }
    
    if (findByIdResult != null) {
      when(mock.findById(any)).thenAnswer((_) async => findByIdResult);
    }
    
    return mock;
  }
  
  /// 建立 Mock InventoryService
  static MockInventoryService createMockInventoryService({
    StockStatus stockStatus = StockStatus.available,
  }) {
    final mock = MockInventoryService();
    when(mock.checkStock(any)).thenAnswer((_) async => stockStatus);
    return mock;
  }
  
  /// 建立 Mock EventPublisher
  static MockEventPublisher createMockEventPublisher() {
    final mock = MockEventPublisher();
    when(mock.publish(any)).thenAnswer((_) async => true);
    return mock;
  }
}

// 使用 Test Helper
test('使用者提交訂單成功', () async {
  // Given: 使用 Helper 快速建立 Mock
  final mockRepository = UseCaseTestHelper.createMockOrderRepository(
    saveResult: SaveResult.success('order-123'),
  );
  final mockInventoryService = UseCaseTestHelper.createMockInventoryService(
    stockStatus: StockStatus.available,
  );
  final mockEventPublisher = UseCaseTestHelper.createMockEventPublisher();
  
  final useCase = SubmitOrderUseCase(
    repository: mockRepository,
    inventoryService: mockInventoryService,
    eventPublisher: mockEventPublisher,
  );
  
  // When, Then: ...
  
  // 測試程式碼更簡潔
});
```

### 8.3 Builder Pattern 應用

**設計原則**:

1. 提供預設值
2. 支援 fluent API（鏈式呼叫）
3. 只暴露需要自訂的欄位
4. 命名清晰表達意圖

**範例**:

```dart
/// Order 建構器
class OrderBuilder {
  String _id = 'order-001';
  int _amount = 1000;
  String _userId = 'user-001';
  List<OrderItem> _items = [
    OrderItem(productId: 'prod-001', quantity: 1, price: 1000),
  ];
  OrderStatus _status = OrderStatus.pending;
  Address? _shippingAddress;
  
  OrderBuilder withId(String id) {
    _id = id;
    return this;
  }
  
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
  
  OrderBuilder withStatus(OrderStatus status) {
    _status = status;
    return this;
  }
  
  OrderBuilder withShippingAddress(Address address) {
    _shippingAddress = address;
    return this;
  }
  
  Order build() {
    return Order(
      id: _id,
      amount: OrderAmount(_amount),
      userId: UserId(_userId),
      items: _items,
      status: _status,
      shippingAddress: _shippingAddress,
    );
  }
}

// 使用 Builder
test('使用者提交訂單成功', () async {
  // Given: 使用 Builder 快速建立測試資料
  final order = OrderBuilder()
      .withAmount(1500)
      .withUserId('user-002')
      .withShippingAddress(Address(city: '台北市', district: '信義區'))
      .build();
  
  // 只自訂需要的欄位，其他使用預設值
  
  // When, Then: ...
});

test('使用者提交訂單失敗 - 訂單金額為 0', () async {
  // Given: 使用 Builder 建立特殊測試資料
  final order = OrderBuilder()
      .withAmount(0)
      .build();
  
  // 快速建立邊界條件測試資料
  
  // When, Then: ...
});
```

**預定義 Builder 方法**:

```dart
class OrderBuilder {
  // ... 基本方法 ...
  
  /// 建立有效訂單（預設）
  static OrderBuilder valid() {
    return OrderBuilder();
  }
  
  /// 建立無效訂單 - 金額為 0
  static OrderBuilder withZeroAmount() {
    return OrderBuilder().withAmount(0);
  }
  
  /// 建立高金額訂單
  static OrderBuilder withHighAmount() {
    return OrderBuilder().withAmount(50000);
  }
  
  /// 建立免運費訂單
  static OrderBuilder withFreeShipping() {
    return OrderBuilder().withAmount(1000); // 滿 1000 免運
  }
}

// 使用預定義 Builder
test('使用者提交高金額訂單成功', () async {
  final order = OrderBuilder.withHighAmount().build();
  // ...
});
```

### 8.4 Test Fixture 設計

**定義**:

Test Fixture 是預先準備好的測試資料集，供多個測試共用。

**範例**:

```dart
/// 測試 Fixture
class TestFixtures {
  // 有效的測試資料
  static final validUser = User(
    id: 'user-001',
    email: 'user@example.com',
    name: 'Test User',
  );
  
  static final validProduct = Product(
    id: 'prod-001',
    name: 'Product A',
    price: 1000,
    stock: 100,
  );
  
  static final validOrder = Order(
    id: 'order-001',
    amount: OrderAmount(1000),
    userId: UserId('user-001'),
    items: [
      OrderItem(productId: 'prod-001', quantity: 1, price: 1000),
    ],
    status: OrderStatus.pending,
  );
  
  // 無效的測試資料
  static final invalidEmail = 'invalid-email';
  static final zeroAmount = 0;
  static final negativeAmount = -100;
  
  // Mock 預設行為
  static SaveResult successSaveResult = SaveResult.success('order-123');
  static SaveResult failureSaveResult = SaveResult.failure('儲存失敗');
  static StockStatus availableStock = StockStatus.available;
  static StockStatus outOfStock = StockStatus.outOfStock;
}

// 使用 Test Fixture
test('使用者提交訂單成功', () async {
  // Given: 使用 Fixture 快速準備測試資料
  final order = TestFixtures.validOrder;
  
  when(mockRepository.save(any))
      .thenAnswer((_) async => TestFixtures.successSaveResult);
  when(mockInventoryService.checkStock(any))
      .thenAnswer((_) async => TestFixtures.availableStock);
  
  // When, Then: ...
});
```

### 8.5 測試輔助工具組織結構

```
test/
├─ helpers/
│  ├─ use_case_test_helper.dart      # UseCase 測試 Helper
│  ├─ domain_test_helper.dart        # Domain 測試 Helper
│  └─ ui_test_helper.dart            # UI 測試 Helper
│
├─ builders/
│  ├─ order_builder.dart             # Order Builder
│  ├─ user_builder.dart              # User Builder
│  └─ product_builder.dart           # Product Builder
│
├─ fixtures/
│  └─ test_fixtures.dart             # 共用測試資料
│
└─ [測試檔案]
```

---

## 第九章：Code Review 檢查項目

### 9.1 測試設計審查

**Reviewer 必須檢查**:

#### 1. 測試類型是否符合分層策略

- [ ] Layer 1 (UI) - 關鍵流程使用整合測試
- [ ] Layer 2 (Behavior) - 複雜轉換使用單元測試
- [ ] Layer 3 (UseCase) - 所有場景使用 BDD 測試
- [ ] Layer 5 (Domain) - 複雜邏輯使用單元測試

**判斷方法**:

檢查測試檔案位置和類型：
```
test/
├─ ui/               → 整合測試
├─ behavior/         → 單元測試
├─ use_case/         → BDD 測試
└─ domain/           → 單元測試
```

---

#### 2. BDD 測試是否聚焦行為而非實作

**檢查項目**:

- [ ] 測試名稱使用業務語言
- [ ] 測試描述從使用者視角
- [ ] 沒有測試實作細節（如 Repository 方法呼叫）
- [ ] Given-When-Then 結構清晰

**範例判斷**:

❌ **錯誤：測試實作**
```dart
test('Repository.save 被呼叫 1 次', () {
  // 測試實作細節
  verify(mockRepository.save(any)).called(1);
});
```

✅ **正確：測試行為**
```dart
test('使用者提交訂單成功', () {
  // 測試業務行為
  expect(result.isSuccess, true);
  expect(result.orderId, isNotEmpty);
});
```

---

#### 3. Given-When-Then 是否清晰

**檢查項目**:

- [ ] Given 明確描述前置條件
- [ ] When 只有單一動作
- [ ] Then 驗證可觀察的結果
- [ ] 註解使用 Given-When-Then 標記

**範例判斷**:

❌ **錯誤：結構混亂**
```dart
test('測試提交訂單', () {
  final order = Order(...);
  when(mockRepository.save(any)).thenAnswer(...);
  final result = await useCase.execute(order);
  expect(result.isSuccess, true);
  
  // 沒有 Given-When-Then 標記
  // 前置條件和動作混在一起
});
```

✅ **正確：結構清晰**
```dart
test('使用者提交訂單成功', () {
  // Given: 使用者已選擇商品且填寫完整資訊
  final order = Order(...);
  when(mockRepository.save(any)).thenAnswer(...);
  
  // When: 使用者點擊「提交訂單」
  final result = await useCase.execute(order);
  
  // Then: 系統確認訂單已儲存
  expect(result.isSuccess, true);
  expect(result.orderId, isNotEmpty);
});
```

---

#### 4. 是否涵蓋技術性檢查清單

**檢查項目**:

- [ ] Null 值處理
- [ ] 空集合處理
- [ ] 邊界值測試
- [ ] 異常處理
- [ ] 併發場景（如適用）
- [ ] 資料驗證

**判斷方法**:

檢查測試場景清單是否完整：
```
正常流程：✅
異常流程：✅
邊界條件：✅
- Null 值：✅
- 空集合：✅
- 0 值：✅
- 負數：✅
- 超過上限：✅
異常處理：✅
- 網路錯誤：✅
- 儲存失敗：✅
```

---

#### 5. 測試覆蓋率是否達標

**檢查項目**:

- [ ] UseCase 層：100% 行為場景覆蓋
- [ ] Domain 層（複雜邏輯）：100% 程式碼覆蓋率
- [ ] Behavior 層（複雜轉換）：100% 邏輯覆蓋率
- [ ] 整體專案：新增程式碼 ≥ 80% 覆蓋率

**判斷方法**:

1. 檢查 CI/CD 覆蓋率報告
2. 手動檢查測試場景完整性
3. 使用覆蓋率工具驗證

---

### 9.2 測試品質審查

#### 1. 測試是否獨立

**檢查項目**:

- [ ] 測試可以單獨執行
- [ ] 測試不依賴執行順序
- [ ] 測試不共享可變狀態
- [ ] 使用 setUp/tearDown 清理狀態

**範例判斷**:

❌ **錯誤：測試依賴順序**
```dart
late Order sharedOrder;

test('測試 1：建立訂單', () {
  sharedOrder = Order(...);
  // 錯誤：測試 2 依賴測試 1 的結果
});

test('測試 2：修改訂單', () {
  sharedOrder.update(...);
  // 錯誤：依賴 sharedOrder 已被建立
});
```

✅ **正確：測試獨立**
```dart
test('測試 1：建立訂單', () {
  final order = Order(...);
  // 獨立測試
});

test('測試 2：修改訂單', () {
  final order = Order(...);
  order.update(...);
  // 獨立測試
});
```

---

#### 2. Mock 策略是否正確

**檢查項目**:

- [ ] 只 Mock 外層依賴（Repository, Service）
- [ ] 沒有 Mock 內層邏輯（Domain Entity, Value Object）
- [ ] Mock 行為設置合理
- [ ] 驗證關鍵行為而非所有呼叫

**範例判斷**:

❌ **錯誤：Mock 內層邏輯**
```dart
final mockOrder = MockOrder();
when(mockOrder.validate()).thenReturn(true);
// 錯誤：Mock Domain Entity
```

✅ **正確：只 Mock 外層依賴**
```dart
final mockRepository = MockOrderRepository();
when(mockRepository.save(any)).thenAnswer(...);

final order = Order(...); // 使用真實 Entity
```

---

#### 3. 測試可讀性

**檢查項目**:

- [ ] 測試名稱清楚描述場景
- [ ] Given-When-Then 註解清晰
- [ ] 測試邏輯易於理解
- [ ] 使用 Helper 和 Builder 減少重複

**範例判斷**:

❌ **錯誤：測試不可讀**
```dart
test('test1', () {
  final o = Order(a: 100, u: 'u1');
  when(r.save(o)).thenAnswer((_) => SaveResult.success('o1'));
  final res = await uc.execute(o);
  expect(res.isSuccess, true);
  
  // 命名不清楚
  // 沒有註解
  // 變數名稱不明確
});
```

✅ **正確：測試可讀**
```dart
test('使用者提交訂單成功', () {
  // Given: 使用者已選擇商品且填寫完整資訊
  final order = OrderBuilder()
      .withAmount(100)
      .withUserId('user-001')
      .build();
  
  when(mockRepository.save(any))
      .thenAnswer((_) async => SaveResult.success('order-123'));
  
  // When: 使用者點擊「提交訂單」
  final result = await submitOrderUseCase.execute(order);
  
  // Then: 系統確認訂單已儲存
  expect(result.isSuccess, true);
  expect(result.orderId, 'order-123');
  
  // 命名清楚
  // 註解明確
  // 使用 Builder 提升可讀性
});
```

---

#### 4. 測試維護性

**檢查項目**:

- [ ] 避免重複的測試設置
- [ ] 使用 setUp/tearDown 共用邏輯
- [ ] 使用 Test Helper 減少 Mock 重複
- [ ] 使用 Builder 減少測試資料重複

**範例判斷**:

❌ **錯誤：大量重複**
```dart
test('測試 1', () {
  final mockRepo = MockOrderRepository();
  final mockInventory = MockInventoryService();
  final mockEvent = MockEventPublisher();
  when(mockRepo.save(any)).thenAnswer(...);
  when(mockInventory.checkStock(any)).thenAnswer(...);
  final useCase = SubmitOrderUseCase(
    repository: mockRepo,
    inventoryService: mockInventory,
    eventPublisher: mockEvent,
  );
  // 重複的設置程式碼
});

test('測試 2', () {
  final mockRepo = MockOrderRepository();
  final mockInventory = MockInventoryService();
  final mockEvent = MockEventPublisher();
  when(mockRepo.save(any)).thenAnswer(...);
  when(mockInventory.checkStock(any)).thenAnswer(...);
  final useCase = SubmitOrderUseCase(
    repository: mockRepo,
    inventoryService: mockInventory,
    eventPublisher: mockEvent,
  );
  // 重複的設置程式碼
});
```

✅ **正確：共用設置**
```dart
group('SubmitOrderUseCase', () {
  late MockOrderRepository mockRepository;
  late MockInventoryService mockInventoryService;
  late MockEventPublisher mockEventPublisher;
  late SubmitOrderUseCase useCase;
  
  setUp(() {
    // 共用設置邏輯
    mockRepository = MockOrderRepository();
    mockInventoryService = MockInventoryService();
    mockEventPublisher = MockEventPublisher();
    useCase = SubmitOrderUseCase(
      repository: mockRepository,
      inventoryService: mockInventoryService,
      eventPublisher: mockEventPublisher,
    );
  });
  
  test('測試 1', () {
    // 只設置此測試特定的 Mock 行為
    when(mockRepository.save(any))
        .thenAnswer((_) async => SaveResult.success('order-123'));
    // ...
  });
  
  test('測試 2', () {
    // 只設置此測試特定的 Mock 行為
    when(mockRepository.save(any))
        .thenAnswer((_) async => SaveResult.failure('儲存失敗'));
    // ...
  });
});
```

---

### 9.3 Code Review 檢查清單

**完整檢查清單**:

```markdown
## 測試設計審查

- [ ] 測試類型符合分層策略
  - [ ] UI 層：整合測試（關鍵流程）
  - [ ] Behavior 層：單元測試（複雜轉換）或依賴上層
  - [ ] UseCase 層：BDD 測試（所有場景）
  - [ ] Domain 層：單元測試（複雜邏輯）或依賴上層

- [ ] BDD 測試聚焦行為
  - [ ] 測試名稱使用業務語言
  - [ ] 沒有測試實作細節
  - [ ] Given-When-Then 結構清晰

- [ ] 場景完整性
  - [ ] 涵蓋正常流程
  - [ ] 涵蓋異常流程（至少 2 個）
  - [ ] 涵蓋邊界條件（至少 3 個）

- [ ] 技術性檢查清單
  - [ ] Null 值處理
  - [ ] 空集合處理
  - [ ] 邊界值測試
  - [ ] 異常處理
  - [ ] 併發場景（如適用）
  - [ ] 資料驗證

- [ ] 測試覆蓋率達標
  - [ ] UseCase 層：100% 行為場景覆蓋
  - [ ] Domain 層（複雜邏輯）：100% 程式碼覆蓋率
  - [ ] 整體：新增程式碼 ≥ 80% 覆蓋率

## 測試品質審查

- [ ] 測試獨立性
  - [ ] 測試可獨立執行
  - [ ] 不依賴執行順序
  - [ ] 使用 setUp/tearDown 清理狀態

- [ ] Mock 策略正確
  - [ ] 只 Mock 外層依賴
  - [ ] 沒有 Mock 內層邏輯
  - [ ] Mock 行為設置合理

- [ ] 測試可讀性
  - [ ] 測試名稱清楚
  - [ ] Given-When-Then 註解清晰
  - [ ] 使用 Helper 和 Builder

- [ ] 測試維護性
  - [ ] 避免重複設置
  - [ ] 使用共用邏輯
  - [ ] 測試程式碼結構清晰

## 其他檢查

- [ ] 所有測試通過
- [ ] 沒有測試被跳過（skip）
- [ ] 測試執行速度合理
- [ ] 測試檔案組織結構清晰
```

---

## 第十章：正反範例

### 10.1 UseCase 層（BDD）完整範例

詳細範例請參考「BDD 測試方法論」第九章。

### 10.2 Domain 層（單元測試）範例

詳細範例請參考「BDD 測試方法論」第九章和本方法論第 4.5 節。

### 10.3 Behavior 層（單元測試）範例

詳細範例請參考本方法論第 4.2 節。

### 10.4 UI 層（整合測試）範例

詳細範例請參考本方法論第 4.1 節。

### 10.5 測試輔助工具使用範例

詳細範例請參考本方法論第八章。

---

## 結論

混合測試策略是測試執行標準，補充 layered-ticket-methodology.md。

**核心定位**:

這是為每層 ticket 提供明確的測試設計指引，確保測試品質和覆蓋率。

**實際功能**:

- 分層測試決策樹：明確每層使用什麼測試方法
- 量化指標：明確測試覆蓋率要求
- Ticket 測試策略：整合到 ticket 設計流程
- Code Review 檢查：確保測試品質

**執行準則**:

我們採用混合測試策略：

- Layer 1 (UI)：整合測試（關鍵流程）
- Layer 2 (Behavior)：單元測試（複雜轉換）+ 依賴上層（簡單轉換）
- Layer 3 (UseCase)：BDD 測試（所有場景）
- Layer 4 (Interface)：不測試
- Layer 5 (Domain)：單元測試（複雜邏輯）+ 依賴上層（簡單邏輯）

我們透過分層測試決策樹、技術性檢查清單、測試輔助工具和 Code Review 檢查項目，確保測試品質和一致性。

配合「BDD 測試方法論」的理論指引，我們建立完整的測試設計和執行體系。
