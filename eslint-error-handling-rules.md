# 📋 ESLint 錯誤處理規範強制規則

**版本**: v1.0  
**建立日期**: 2025-09-11  
**狀態**: 已實施並啟用  

## 🎯 目的

基於專案的錯誤處理標準化規範 ([error-handling-standardization-plan.md](../domains/03-reference/archive/architecture/error-handling-standardization-plan.md))，建立 ESLint 規則自動檢測和防止違反規範的程式碼。

### 強制執行的規範

1. **統一異常管理**: 禁止使用原生 `Error`，強制使用 `StandardError` 體系
2. **ErrorCodes 常量使用**: 禁止在 StandardError 中使用魔法字串，強制使用 `ErrorCodes` 常量
3. **結構化測試方法**: 禁止測試中的字串錯誤比較，強制使用 `toMatchObject()`
4. **標準化回應格式**: 建議使用 `OperationResult` 統一格式

## 🚨 規則詳情

### 規則 1: 禁止字串錯誤拋出
**規則 ID**: `no-restricted-syntax` (ThrowStatement > Literal)

```javascript
// ❌ 違規 - 會被 ESLint 報錯
throw 'This is an error message'
throw "Another error message"

// ✅ 正確 - 符合規範
const { StandardError } = require('src/core/errors')
throw new StandardError('ERROR_CODE', 'This is an error message', { details })
```

**錯誤訊息**: `🚨 不允許拋出字串錯誤。請使用 StandardError 或其子類 (如 BookValidationError)`

### 規則 2: 禁止原生 Error 使用
**規則 ID**: `no-restricted-syntax` (ThrowStatement > NewExpression[callee.name="Error"])

```javascript
// ❌ 違規 - 會被 ESLint 報錯
throw new Error('Something went wrong')

// ✅ 正確 - 符合規範
const { StandardError } = require('src/core/errors')
throw new StandardError('OPERATION_FAILED', 'Something went wrong', { 
  context: 'user_action',
  timestamp: Date.now() 
})
```

**錯誤訊息**: `🚨 不允許使用原生 Error。請使用 StandardError 或其子類，提供錯誤代碼和結構化詳情`

### 規則 3: 禁止 StandardError 中使用魔法字串
**規則 ID**: `no-restricted-syntax` (NewExpression[callee.name="StandardError"] > Literal:first-child)

```javascript
// ❌ 違規 - 會被 ESLint 報錯
const { StandardError } = require('src/core/errors')
throw new StandardError('VALIDATION_FAILED', 'Validation failed', {})
throw new StandardError('NETWORK_ERROR', 'Network error')

// ✅ 正確 - 符合規範
const { ErrorCodes } = require('src/core/errors/ErrorCodes')
const { StandardError } = require('src/core/errors')
throw new StandardError(ErrorCodes.VALIDATION_FAILED, 'Validation failed', {})
throw new StandardError(ErrorCodes.NETWORK_ERROR, 'Network error')
```

**錯誤訊息**: `🚨 不允許在 StandardError 中使用魔法字串。請使用 ErrorCodes 常量`

### 規則 4: 禁止測試中字串錯誤比較
**適用範圍**: `**/*.test.js`, `**/test/**/*.js`  
**規則 ID**: `no-restricted-syntax` (CallExpression[callee.property.name="toThrow"] > Literal)

```javascript
// ❌ 違規 - 會被 ESLint 報錯
expect(() => someFunction()).toThrow('Error message')
expect(asyncFunction()).rejects.toThrow('Async error message')

// ✅ 正確 - 符合規範
expect(() => someFunction()).toMatchObject({
  code: 'VALIDATION_FAILED',
  details: expect.objectContaining({
    field: 'email',
    category: 'validation'
  })
})

expect(asyncFunction()).rejects.toMatchObject({
  code: 'NETWORK_ERROR',
  message: expect.any(String),
  details: expect.any(Object)
})
```

**錯誤訊息**: `🚨 測試中不允許使用字串比較錯誤。請使用 toMatchObject() 驗證錯誤結構，包含 code 和 details`

## 📊 檢測結果

### 專案目前狀況 (2025-09-16)

```bash
npm run lint 2>&1 | grep "🚨" | wc -l
```

- **原生 Error 使用**: ~200+ 處違規
- **StandardError 魔法字串**: ~267+ 處違規 (UNKNOWN_ERROR 等)
- **測試字串錯誤比較**: ~385 處違規
- **字串錯誤拋出**: 少量違規

### 規則生效驗證

```bash
# 執行 lint 檢查所有違規
npm run lint

# 僅檢查錯誤處理規範違規
npm run lint 2>&1 | grep "🚨"

# 統計各類違規數量
npm run lint 2>&1 | grep "🚨.*不允許使用原生 Error" | wc -l
npm run lint 2>&1 | grep "🚨.*不允許在 StandardError 中使用魔法字串" | wc -l
npm run lint 2>&1 | grep "🚨.*測試中不允許使用字串比較錯誤" | wc -l
```

## 🛠 規則配置檔案

### 主配置檔案: `package.json` 中的 `eslintConfig`

**✅ 保留原本所有 ESLint 規則，並加入錯誤處理規範**

```json
{
  "eslintConfig": {
    "extends": ["standard"],
    "env": {
      "browser": true,
      "node": true,
      "jest": true,
      "webextensions": true
    },
    "globals": {
      "chrome": "readonly"
    },
    "rules": {
      // 原本的所有規則保持不變
      "no-console": "warn",
      "no-debugger": "error",
      "prefer-const": "error",
      // ... 其他原本規則
    },
    // 🚨 新增的錯誤處理規範 (不影響原本規則)
    "overrides": [
      {
        "files": ["**/*.js"],
        "rules": {
          "no-restricted-syntax": [
            "error",
            {
              "selector": "ThrowStatement > Literal",
              "message": "🚨 不允許拋出字串錯誤。請使用 StandardError 或其子類"
            },
            {
              "selector": "ThrowStatement > NewExpression[callee.name=\"Error\"]",
              "message": "🚨 不允許使用原生 Error。請使用 StandardError 或其子類"
            },
            {
              "selector": "NewExpression[callee.name=\"StandardError\"] > Literal:first-child",
              "message": "🚨 不允許在 StandardError 中使用魔法字串。請使用 ErrorCodes 常量"
            }
          ]
        }
      },
      {
        "files": ["**/*.test.js", "**/test/**/*.js"],
        "rules": {
          "no-restricted-syntax": [
            "error",
            {
              "selector": "ThrowStatement > Literal",
              "message": "🚨 測試中不允許拋出字串錯誤。請使用 StandardError 或其子類"
            },
            {
              "selector": "CallExpression[callee.property.name=\"toThrow\"] > Literal",
              "message": "🚨 測試中不允許使用字串比較錯誤。請使用 toMatchObject() 驗證錯誤結構"
            },
            {
              "selector": "CallExpression[callee.object.property.name=\"rejects\"][callee.property.name=\"toThrow\"] > Literal",
              "message": "🚨 測試中不允許使用字串比較錯誤。請使用 toMatchObject() 驗證錯誤結構"
            },
            {
              "selector": "NewExpression[callee.name=\"StandardError\"] > Literal:first-child",
              "message": "🚨 測試中不允許在 StandardError 中使用魔法字串。請使用 ErrorCodes 常量"
            }
          ]
        }
      }
    ]
  }
}
```

## 🔧 如何修復違規

### 1. 修復原生 Error 使用

```javascript
// 修復前
function validateData(data) {
  if (!data) {
    throw new Error('Data is required')
  }
}

// 修復後
function validateData(data) {
  const { StandardError } = require('src/core/errors')
  
  if (!data) {
    throw new StandardError('VALIDATION_FAILED', 'Data is required', {
      field: 'data',
      category: 'required_field'
    })
  }
}
```

### 2. 修復測試中的字串比較

```javascript
// 修復前
test('should throw error for invalid data', () => {
  expect(() => validateData(null)).toThrow('Data is required')
})

// 修復後  
test('should throw error for invalid data', () => {
  expect(() => validateData(null)).toMatchObject({
    code: 'VALIDATION_FAILED',
    message: 'Data is required',
    details: expect.objectContaining({
      field: 'data',
      category: 'required_field'
    })
  })
})
```

### 3. 修復 Promise rejection 測試

```javascript
// 修復前
test('should reject with error message', async () => {
  await expect(asyncFunction()).rejects.toThrow('Async operation failed')
})

// 修復後
test('should reject with structured error', async () => {
  await expect(asyncFunction()).rejects.toMatchObject({
    code: 'ASYNC_OPERATION_FAILED',
    details: expect.any(Object)
  })
})
```

## 📋 下一步行動

### 立即行動
1. **規範強化完成** ✅ - ESLint 規則已建立並啟用
2. **系統性檢查** - 搜尋並修復所有違規 (~585+ 處)
3. **批次修復** - 系統性修復字串比較測試
4. **文件更新** - 在 CLAUDE.md 中明確提及強制規範

### 優先修復順序
1. **高優先級**: 修復 DataValidationService 等核心服務中的違規
2. **中優先級**: 修復所有測試檔案中的字串比較
3. **低優先級**: 修復非核心檔案中的原生 Error 使用

### CI/CD 整合建議
```bash
# 在 CI/CD pipeline 中加入錯誤處理規範檢查
npm run lint | grep "🚨" && exit 1 || echo "錯誤處理規範檢查通過"
```

## 📝 相關文件

- [專案錯誤處理標準化方案](../domains/03-reference/archive/architecture/error-handling-standardization-plan.md)
- [StandardError 使用指引](../../../src/core/errors/README.md) (待建立)
- [TDD 協作開發流程](./tdd-collaboration-flow.md)
- [CLAUDE.md 主規範](../../CLAUDE.md)

---

**建立者**: Claude Code  
**最後更新**: 2025-09-11  
**規則狀態**: ✅ 已實施並啟用  
**預期效果**: 防止未來違反錯誤處理規範，自動化品質控制