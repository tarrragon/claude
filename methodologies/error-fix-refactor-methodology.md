# 錯誤修復和重構方法論

## 方法論目的

本方法論定義程式錯誤修復和重構的執行標準，確保所有修改都遵循物件導向設計原則和測試驅動開發流程，避免破壞架構完整性。

## 核心原則宣告

### 我們要求的設計原則

- **封閉開放原則 (Open-Closed Principle)**：程式對擴展開放，對修改封閉
- **領域驅動設計 (Domain-Driven Design)**：業務邏輯獨立於技術實現
- **測試驅動開發 (Test-Driven Development)**：測試定義需求，程式實現測試

### 我們拒絕的實作方式

- **內部曝露**：直接存取物件或類別內部元素
- **行為旁路**：繞過正常業務流程的捷徑
- **測試任意修改**：為配合程式錯誤而調整測試需求

## 錯誤分類和判斷標準

### 第一層：程式實作錯誤

#### 定義
程式實作不符合測試需求，但測試需求本身正確且架構未變更。

#### 邊界
- 包含：邏輯錯誤、型別錯誤、演算法實作錯誤
- 不包含：需求變更、架構調整、測試規格修正

#### 判斷標準
- 測試需求明確且未變更 → 程式實作錯誤
- 現有測試通過但新需求失敗 → 程式實作錯誤
- 相同輸入產生錯誤輸出 → 程式實作錯誤

### 第二層：架構變更需求

#### 定義
程式架構必須調整，導致現有測試需要對應修改。

#### 邊界
- 包含：設計模式變更、依賴關係調整、介面重新定義
- 不包含：單純效能優化、程式碼格式調整、註解修正

#### 判斷標準
- 需求文件已更新且與現有測試不符 → 架構變更需求
- 業務流程變更影響多個模組 → 架構變更需求
- 新增功能需要調整現有介面 → 架構變更需求

## 執行規則

### 規則一：程式實作錯誤處理

#### 遇到程式實作錯誤時
1. **檢查測試需求** → 確認測試定義的預期行為
2. **保持測試不變** → 絕不修改測試來配合錯誤的程式
3. **調整程式實作** → 修改程式碼直到符合測試需求
4. **驗證修復結果** → 確認所有相關測試通過

#### 禁止行為
- ❌ 修改測試來配合錯誤的程式實作
- ❌ 新增測試來覆蓋錯誤行為
- ❌ 直接存取物件內部狀態進行除錯

#### 正確修復範例

```dart
// ❌ 錯誤：直接修改測試配合程式錯誤
test('計算總價應該包含稅金', () {
  // 原本測試期望: price = 100, tax = 10, total = 110
  // 程式計算錯誤返回 105
  expect(calculator.calculateTotal(100, 0.1), equals(105)); // 錯誤：修改期望值
});

// ✅ 正確：保持測試不變，修正程式實作
test('計算總價應該包含稅金', () {
  expect(calculator.calculateTotal(100, 0.1), equals(110)); // 維持正確期望
});

// 在 Calculator 類別中修正實作
class Calculator {
  double calculateTotal(double price, double taxRate) {
    return price + (price * taxRate); // 修正計算邏輯
  }
}
```

### 規則二：架構變更需求處理

#### 遇到架構變更需求時
1. **檢查開發文件** → 確認需求規格書是否已更新
2. **PM代理人確認** → 啟動 PM 代理人評估變更範圍
3. **測試規格調整** → 依文件要求列出需要修改的測試
4. **重構代理人檢視** → 確保測試修改與文件需求一致

#### 必要檢查點
- 需求規格書已反映變更 ✓
- 變更範圍已經確認 ✓
- 受影響的測試已識別 ✓
- 新測試需求已定義 ✓

#### 架構變更處理範例

```dart
// 情境：書籍管理需求從「單一標題」變更為「多語言標題」

// 1. 檢查 app-requirements-spec.md 是否已更新
// 2. PM代理人確認變更範圍：Book entity, BookRepository, BookService
// 3. 重構代理人檢視測試需求

// ❌ 錯誤：直接修改測試而不檢查文件
test('書籍應該有標題', () {
  expect(book.title, equals('Programming Guide')); // 舊需求
  // 直接改為: expect(book.titles['en'], equals('Programming Guide'));
});

// ✅ 正確：確認文件更新後，有計畫地調整測試
test('書籍應該支援多語言標題', () {
  book.addTitle('en', 'Programming Guide');
  book.addTitle('zh', '程式設計指南');

  expect(book.getTitle('en'), equals('Programming Guide'));
  expect(book.getTitle('zh'), equals('程式設計指南'));
});
```

### 規則三：測試編譯錯誤處理

#### 測試內部編譯錯誤時
1. **重構代理人檢視** → 確認測試邏輯符合需求
2. **修正編譯問題** → 解決語法、型別、依賴錯誤
3. **驗證測試意圖** → 確保修正後測試仍驗證原始需求
4. **執行完整測試** → 確認修復不影響其他測試

#### 測試修復範例

```dart
// ❌ 錯誤：為了編譯通過而改變測試意圖
test('書籍儲存應該成功', () {
  // 原本要測試: repository.save(book) 返回成功結果
  // 因為介面變更導致編譯錯誤，錯誤修復：
  expect(repository.save(book), isNotNull); // 改變了測試意圖
});

// ✅ 正確：修正編譯問題但保持測試意圖
test('書籍儲存應該成功', () {
  final result = await repository.save(book); // 修正異步調用
  expect(result.isSuccess, isTrue); // 保持原始測試意圖
  expect(result.data, equals(book)); // 驗證儲存的書籍資料
});
```

## 觀測和驗證原則

### 行為觀測標準

我們觀測：
- **公開行為**：透過公開介面的輸入輸出
- **狀態變化**：透過公開屬性的變化
- **事件觸發**：透過事件系統的通知

我們不觀測：
- **內部實作**：私有方法的調用順序
- **內部狀態**：私有屬性的中間值
- **實作細節**：演算法的中間步驟

### 測試驗證範例

```dart
// ❌ 錯誤：觀測內部實作
test('書籍驗證應該檢查所有欄位', () {
  final validator = BookValidator();
  validator.validate(invalidBook);

  // 錯誤：檢查內部方法調用
  expect(validator._titleValidated, isTrue);
  expect(validator._isbnValidated, isTrue);
});

// ✅ 正確：觀測公開行為
test('書籍驗證應該檢查所有欄位', () {
  final validator = BookValidator();
  final result = validator.validate(invalidBook);

  // 正確：檢查驗證結果和錯誤訊息
  expect(result.isValid, isFalse);
  expect(result.errors, contains('標題不可為空'));
  expect(result.errors, contains('ISBN 格式錯誤'));
});
```

## 代理人協作流程

### PM代理人觸發條件

- 發現需求文件與現有測試不一致
- 架構變更影響超過3個模組
- 業務流程需要重新設計
- 新功能需要調整現有介面

### 重構代理人觸發條件

- 測試需要修改或重寫
- 程式架構需要調整
- 設計模式需要變更
- 程式碼重複需要抽取

### 協作執行順序

1. **問題識別** → 分類為程式錯誤或架構變更
2. **PM代理人介入**（如需要）→ 確認變更範圍和影響
3. **重構代理人檢視** → 規劃測試和程式修改策略
4. **執行修復** → 按照方法論執行修改
5. **驗證結果** → 確認修復達到要求

## 驗證機制

### 修復完成檢查清單

- [ ] 所有測試通過 (100% 通過率)
- [ ] 程式架構符合設計文件
- [ ] 沒有內部狀態曝露
- [ ] 沒有行為旁路實作
- [ ] 修改有對應的測試保護

### 品質門檻標準

- **測試通過率**：必須 100%，無例外
- **架構一致性**：程式實作符合設計文件
- **封裝完整性**：所有內部狀態透過公開介面存取
- **測試覆蓋率**：修改的程式碼都有測試保護

## 常見錯誤和修正

### 反模式一：測試遷就程式

#### ❌ 錯誤做法
```dart
// 發現程式返回錯誤結果，修改測試來配合
test('計算折扣價格', () {
  // 程式有 bug，返回 90 而不是期望的 80
  expect(priceCalculator.calculateDiscount(100, 0.2), equals(90)); // 錯誤
});
```

#### ✅ 正確做法
```dart
// 保持測試需求，修正程式實作
test('計算折扣價格', () {
  expect(priceCalculator.calculateDiscount(100, 0.2), equals(80)); // 維持正確期望
});

// 在 PriceCalculator 中修正實作
double calculateDiscount(double price, double rate) {
  return price * (1 - rate); // 修正計算邏輯
}
```

### 反模式二：內部狀態依賴

#### ❌ 錯誤做法
```dart
test('書籍狀態管理', () {
  book.updateStatus('available');

  // 錯誤：檢查內部私有屬性
  expect(book._internalState, equals('AVAILABLE'));
  expect(book._lastModified, isNotNull);
});
```

#### ✅ 正確做法
```dart
test('書籍狀態管理', () {
  book.updateStatus('available');

  // 正確：透過公開介面驗證行為
  expect(book.isAvailable(), isTrue);
  expect(book.canBeBorrowed(), isTrue);
});
```

### 反模式三：跳過文件檢查

#### ❌ 錯誤做法
```dart
// 發現需求變更，直接修改測試而不檢查文件
test('使用者借書', () {
  // 直接改變測試以配合新需求，沒有確認文件更新
  expect(library.borrowBook(user, book, duration: 30), isTrue);
});
```

#### ✅ 正確做法
```dart
// 1. 檢查 app-requirements-spec.md 是否反映借書期限變更
// 2. PM代理人確認變更範圍
// 3. 依據文件更新測試
test('使用者借書應該支援自定義期限', () {
  final result = library.borrowBook(user, book, duration: 30);

  expect(result.isSuccess, isTrue);
  expect(result.borrowRecord.dueDate,
         equals(DateTime.now().add(Duration(days: 30))));
});
```

## 實施指引

### 開始修復前檢查

1. 確認錯誤類型（程式實作 vs 架構變更）
2. 檢查相關文件是否最新
3. 識別受影響的測試範圍
4. 評估是否需要代理人協作

### 修復過程中維持

- 隨時檢查測試通過狀態
- 確保不曝露內部實作
- 記錄重要的設計決策
- 驗證修改符合原始需求

### 修復完成後驗證

- 執行完整測試套件
- 檢查程式架構一致性
- 確認沒有新的技術債務
- 更新相關文件記錄

## 結論

錯誤修復和重構必須遵循嚴格的方法論。程式服務於測試，測試服務於需求，需求反映於文件。

任何違反此流程的修復都會累積技術債務，最終影響專案品質。我們要求每次修復都是對架構完整性的加強，而不是妥協。

這是品質標準，確保每次修復都強化架構完整性，而非技術妥協。
