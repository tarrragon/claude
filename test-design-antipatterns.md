# 測試設計反模式分析與預防

## 📖 文件目的

本文件分析假設性數字測試設計的根本原因，並提供正確的測試設計指導原則，避免重複產生相同的錯誤測試模式。

## 🔍 假設性數字測試的產生原因分析

### 1. **錯誤的測試哲學觀念**

#### ❌ 混淆了「驗證」與「監控」

```javascript
// 錯誤思維：把測試當作監控工具
expect(executionTime).toBeLessThan(1000) // "確保效能不退化"
expect(memoryUsage).toBeLessThan(50MB)   // "確保記憶體不超標"
```

**問題根源**: 將測試視為效能監控或資源監控工具，而非邏輯驗證工具

### 2. **對外部系統的錯誤理解**

#### ❌ 試圖測試不可控的外部限制

```javascript
// 錯誤思維：測試 Chrome 系統特性
expect(chromeStorage.quota).toBe(5 * 1024 * 1024)
expect(chromeStorage.available).toBeGreaterThan(4.9 * 1024 * 1024)
```

**問題根源**:

- 對 Chrome Extension 環境的誤解
- 認為測試應該驗證平台特性
- 混淆了「我們的程式行為」與「系統環境特性」

### 3. **對測試穩定性的錯誤解決方案**

#### ❌ 用容差掩蓋不確定性

```javascript
// 錯誤思維：為了讓測試通過而設計容差
expect(actualValue).toBeCloseTo(expectedValue, 1)
expect(actualValue).toBeGreaterThan(expectedValue - 100)
```

**問題根源**:

- 測試在不同環境中結果不一致
- 用「容差」來解決問題，而非找出根本原因
- 沒有區分「測試環境差異」與「程式邏輯問題」

### 4. **經驗不足的防禦性程式設計**

#### ❌ 過度防禦導致測試變質

```javascript
// 錯誤思維：「以防萬一」的測試設計
if (process.env.NODE_ENV === 'test') {
  expect(result).toBeGreaterThan(0.7) // 70% 就夠了
} else {
  expect(result).toBe(1.0) // 生產環境要 100%
}
```

**問題根源**:

- 對測試可靠性缺乏信心
- 認為「寬鬆的測試」比「嚴格的測試」更安全
- 不了解測試應該驗證確定性而非機率性

### 5. **複製既有錯誤模式**

#### ❌ 延續了不良的測試範例

```javascript
// 錯誤思維：照抄其他專案的測試模式
// 許多開源專案都有類似的容差測試
expect(performance.now() - startTime).toBeLessThan(100)
```

**問題根源**:

- 沒有深入思考測試的真正目的
- 盲目複製看似「實用」的測試模式
- 缺乏測試設計的理論基礎

## 🎯 正確的測試思維轉換

### ✅ 應該測試什麼

#### 1. **我們程式的邏輯正確性**

```javascript
// ✅ 正確：測試確定的輸入輸出關係
expect(validator.validate(validData)).toBe(true)
expect(validator.validate(invalidData)).toBe(false)
expect(processor.process(inputData)).toEqual(expectedOutput)
```

#### 2. **我們的錯誤處理**

```javascript
// ✅ 正確：測試錯誤處理邏輯
expect(() => parser.parse(malformedData))
  .toMatchObject({ code: 'VALIDATION_ERROR' })
```

#### 3. **我們的狀態管理**

```javascript
// ✅ 正確：測試狀態轉換
expect(stateMachine.currentState).toBe('IDLE')
stateMachine.process(event)
expect(stateMachine.currentState).toBe('PROCESSING')
```

#### 4. **我們的 API 契約**

```javascript
// ✅ 正確：測試介面行為一致性
expect(api.getData()).resolves.toMatchObject({
  success: true,
  data: expect.any(Array)
})
```

### ❌ 不應該測試什麼

#### 1. **外部系統的特性**

```javascript
// ❌ 錯誤：測試 Chrome 系統限制
expect(chrome.storage.local.QUOTA_BYTES).toBe(5242880)

// ✅ 正確：測試我們對系統回應的處理
expect(storageService.handleQuotaExceeded()).toMatchObject({
  error: 'STORAGE_QUOTA_EXCEEDED'
})
```

#### 2. **環境變異性**

```javascript
// ❌ 錯誤：測試執行時間
expect(Date.now() - startTime).toBeLessThan(1000)

// ✅ 正確：測試操作完成狀態
expect(operation.isCompleted()).toBe(true)
expect(operation.getResult()).toBeDefined()
```

#### 3. **統計性結果**

```javascript
// ❌ 錯誤：測試機率性結果
expect(successRate).toBeGreaterThan(0.8) // 80%

// ✅ 正確：測試每個案例的確定結果
mockData.forEach(item => {
  expect(processor.process(item).success).toBe(true)
})
```

#### 4. **硬體資源限制**

```javascript
// ❌ 錯誤：測試記憶體使用量
expect(process.memoryUsage().heapUsed).toBeLessThan(50 * 1024 * 1024)

// ✅ 正確：測試資源管理邏輯
expect(resourceManager.allocate(resource)).toBe(true)
expect(resourceManager.release(resource)).toBe(true)
```

## 💡 關鍵洞察

### 🎯 根本原因

這種錯誤測試設計的最根本原因是：**混淆了「驗證程式正確性」與「監控系統效能」兩個完全不同的目標**。

### 🎯 核心原則

測試的核心目的是確保程式邏輯的**確定性**和**可預測性**，而不是監控執行環境的**變異性**。當我們寫出依賴假設性數字的測試時，實際上是在測試環境而非程式，這違背了單元測試的基本原則。

### 🎯 正確做法

**程式邏輯用測試驗證，系統效能用監控工具追蹤**，兩者各司其職，不應混淆。

## 📋 測試審查檢查清單

### 🚨 立即修正的反模式

- [ ] `expect(...).toBeGreaterThan(百分比)`
- [ ] `expect(時間).toBeLessThan(...)`
- [ ] `expect(記憶體).toBeLessThan(...)`
- [ ] `expect(配額).toBe(硬編碼數值)`
- [ ] `expect(...).toBeCloseTo(..., tolerance)`
- [ ] 任何基於「系統差異容忍」的測試設計

### ✅ 正確的測試模式

- [x] 精確的輸入輸出對應關係
- [x] 明確的成功/失敗狀態檢查
- [x] 完整的資料結構驗證
- [x] 純粹的邏輯行為測試
- [x] 確定性的錯誤處理驗證

## 🛠 實際應用指南

### 情境 1: 儲存操作測試

```javascript
// ❌ 錯誤方式
test('storage should not exceed quota', async () => {
  const result = await storage.save(data)
  const usage = await storage.getUsage()
  expect(usage.used).toBeLessThan(5 * 1024 * 1024) // 硬編碼 Chrome 限制
})

// ✅ 正確方式
test('storage should handle save operation correctly', async () => {
  const result = await storage.save(data)
  expect(result.success).toBe(true)
  expect(result.saved).toBe(true)

  const retrieved = await storage.get(data.key)
  expect(retrieved).toEqual(data)
})
```

### 情境 2: 效能測試

```javascript
// ❌ 錯誤方式
test('processing should be fast', async () => {
  const start = Date.now()
  await processor.process(data)
  const duration = Date.now() - start
  expect(duration).toBeLessThan(1000) // 任意時間限制
})

// ✅ 正確方式
test('processing should complete successfully', async () => {
  const result = await processor.process(data)
  expect(result.completed).toBe(true)
  expect(result.processedData).toMatchObject(expectedFormat)
  expect(result.errors).toHaveLength(0)
})
```

### 情境 3: 批量操作測試

```javascript
// ❌ 錯誤方式
test('most items should process successfully', async () => {
  const results = await processor.processBatch(items)
  const successRate = results.filter(r => r.success).length / results.length
  expect(successRate).toBeGreaterThan(0.8) // 80% 成功率假設
})

// ✅ 正確方式
test('each item should process according to its validity', async () => {
  const validItems = items.filter(item => validator.isValid(item))
  const invalidItems = items.filter(item => !validator.isValid(item))

  const results = await processor.processBatch(items)

  // 精確驗證：有效項目必須成功，無效項目必須失敗
  validItems.forEach((item, index) => {
    expect(results[index].success).toBe(true)
  })

  invalidItems.forEach((item, index) => {
    const resultIndex = validItems.length + index
    expect(results[resultIndex].success).toBe(false)
    expect(results[resultIndex].error).toBeDefined()
  })
})
```

## 📚 延伸閱讀

- [CLAUDE.md - 測試設計哲學強制原則](../CLAUDE.md#-測試設計哲學強制原則)
- [TDD 協作開發流程](./tdd-collaboration-flow.md)
- [程式碼品質範例彙編](./code-quality-examples.md)

---

**建立日期**: 2025-09-18
**最後更新**: 2025-09-18
**版本**: v1.0.0
