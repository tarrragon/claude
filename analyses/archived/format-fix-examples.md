# 📋 文件格式化與修正案例範例集

**文件版本**: v1.0  
**建立日期**: 2025-09-06  
**適用範圍**: 主線程、sub-agent (mint-format-specialist)  
**用途**: 標準化修正模式，確保一致性和品質

---

## 🎯 使用指南

### 📖 **如何使用此範例集**

**主線程開發者**:
- 遇到格式化問題時，參考對應章節的修正模式
- 按照「Before → After」模式進行修正
- 確保符合專案程式碼規範要求

**Sub-Agent (mint-format-specialist)**:
- 作為批量處理的標準參考
- 確保所有修正都符合既定模式
- 產生報告時引用相關範例說明修正邏輯

**工作流程整合**:
- 修正前：查閱相關章節確認修正方式
- 修正中：嚴格按照範例模式執行
- 修正後：驗證結果符合範例標準

---

## 📁 檔案路徑語意化修正範例

### 🎯 **路徑語意化原則**

**✅ 標準化路徑格式確定**:
- ✅ **標準格式**: 使用 `src/` 前綴（不含 `./`）
- ✅ **Jest 相容性**: 透過 moduleNameMapper `'^src/(.*)$': '<rootDir>/src/$1'` 支援
- ✅ **Node.js 相容**: 完全相容，支援跨目錄引用
- ✅ **Chrome Extension**: 符合 Manifest V3 最佳實踐
- ✅ **技術驗證**: 已通過測試，可全面實施

**📋 判斷與處理方式**:
1. **相對路徑深度 > 2**: 如 `../../../` → 改為 `src/` 語意路徑
2. **錯誤的 `./src/` 格式**: 移除 `./` 前綴，改為 `src/`
3. **混合路徑格式**: 統一改為 `src/` 標準格式
4. **npm 模組路徑**: 保持不變（如 `lodash`, `moment` 等）
5. **Node.js 內建模組**: 保持不變（如 `fs`, `path`, `crypto` 等）

### 🔧 **1. JavaScript 模組引用路徑修正**

#### ❌ **修正前 (Before)**
```javascript
// 深層相對路徑 - 不易理解且容易錯誤
const BaseModule = require('../../../background/lifecycle/base-module')
const Logger = require('../../../../core/logging/Logger')
const MessageDict = require('../../../core/messages/MessageDictionary')

// 錯誤的 ./src/ 格式 - 在 Node.js 測試中會失敗
const DataService = require('./src/background/domains/data-management/services/data-service')

// 混合路徑格式 - 維護性差
const EventHandler = require('../core/event-handler')
const FileReader = require('./src/utils/file-reader-factory')
```

#### ✅ **修正後 (After)**
```javascript
// 標準化語意路徑 - 清晰且 Node.js + Jest 相容
const BaseModule = require('src/background/lifecycle/base-module')
const Logger = require('src/core/logging/Logger')
const MessageDict = require('src/core/messages/MessageDictionary')

// 統一格式 - 所有專案內模組使用 src/ 前綴
const DataService = require('src/background/domains/data-management/services/data-service')

// 保持一致性 - 所有引用使用相同格式
const EventHandler = require('src/core/event-handler')
const FileReader = require('src/utils/file-reader-factory')
```

**📋 修正規則**:
- ✅ 所有專案內模組使用 `src/` 前綴
- ✅ 路徑直接指向模組的完整語意位置
- ✅ 避免深層相對路徑（`../../../`）
- ✅ 移除錯誤的 `./src/` 格式
- ❌ 不修正 npm 模組（如 `lodash`, `moment`）
- ❌ 不修正 Node.js 內建模組（如 `fs`, `path`）

**🔧 技術判斷邏輯**:
```javascript
// 判斷是否需要修正的邏輯
function shouldFixPath(requirePath) {
  // 保留 npm 模組（不含路徑分隔符）
  if (!requirePath.includes('/') && !requirePath.includes('\\')) {
    return false // 如: require('lodash')
  }
  
  // 保留 Node.js 內建模組
  const builtinModules = ['fs', 'path', 'crypto', 'util', 'events', 'os'];
  if (builtinModules.includes(requirePath)) {
    return false
  }
  
  // 需要修正的格式
  if (requirePath.startsWith('../') || requirePath.startsWith('./src/')) {
    return true
  }
  
  return false
}

// 路徑轉換邏輯  
function convertToStandardPath(requirePath, currentFilePath) {
  // 案例 1: 深層相對路徑
  if (requirePath.match(/^(\.\.\/){2,}/)) {
    // 分析目標模組的實際位置，轉換為 src/ 路徑
    return convertRelativeToSrc(requirePath, currentFilePath)
  }
  
  // 案例 2: 錯誤的 ./src/ 格式  
  if (requirePath.startsWith('./src/')) {
    return requirePath.substring(2) // 移除 './'
  }
  
  // 案例 3: 已經是正確格式
  if (requirePath.startsWith('src/')) {
    return requirePath // 保持不變
  }
  
  return requirePath
}
```

**⚠️ 邊界案例處理**:
- **測試檔案路徑**: tests/ 開頭的路徑保持相對路徑格式
- **腳本檔案**: scripts/ 中的檔案可能需要不同處理方式
- **配置檔案**: 根目錄配置檔案的引用需要特別判斷

### 🔧 **2. 文檔連結路徑修正**

#### ❌ **修正前 (Before)**
```markdown
## 相關文件
- [開發實戰指南](../02-development/) - 具體開發流程和規範
- [領域設計詳解](../02-development/architecture/domain-design.md) - DDD 實踐細節
- [測試策略文件](../02-development/testing/) - 深入學習測試最佳實踐
```

#### ✅ **修正後 (After)**
```markdown
## 相關文件
- [開發實戰指南](./docs/domains/02-development/) - 具體開發流程和規範
- [領域設計詳解](./docs/domains/02-development/architecture/domain-design.md) - DDD 實踐細節
- [測試策略文件](./docs/domains/02-development/testing/) - 深入學習測試最佳實踐
```

**修正原則**:
- 所有文件引用使用 `./docs/domains/` 為起始路徑
- 保持路徑的完整語意性
- 確保每個路徑段都具有明確意義

### 🔧 **2. 雙層相對路徑修正**

#### ❌ **修正前 (Before)**
```markdown
參考文件：
- [事件驅動架構規範](../../claude/event-driven-architecture.md)
- [專案用語規範字典](../../claude/terminology-dictionary.md)
- [TDD 協作開發流程](../../claude/tdd-collaboration-flow.md)
```

#### ✅ **修正後 (After)**
```markdown
參考文件：
- [事件驅動架構規範](./docs/claude/event-driven-architecture.md)
- [專案用語規範字典](./docs/claude/terminology-dictionary.md)
- [TDD 協作開發流程](./docs/claude/tdd-collaboration-flow.md)
```

**修正原則**:
- Claude 文檔使用 `./docs/claude/` 為起始路徑
- 專案規範類文檔統一路徑格式
- 保持連結的語意化和可讀性

### 🔧 **3. 三層相對路徑修正**

#### ❌ **修正前 (Before)**
```javascript
// 程式碼中的相對路徑引用
const { BookValidationError, NetworkError } = require('../../../core/errors/BookValidationError')
const { OperationResult } = require('../../../core/errors/OperationResult')
const { OperationStatus } = require('../../../core/enums/OperationStatus')
```

#### 🔄 **修正暫停 (技術問題待解決)**
```javascript
// ⚠️ 當前問題：Jest 環境無法解析語意化路徑
// 臨時方案：維持相對路徑直到技術問題解決
const { BookValidationError, NetworkError } = require('../../../core/errors/BookValidationError')
const { OperationResult } = require('../../../core/errors/OperationResult')
const { OperationStatus } = require('../../../core/enums/OperationStatus')

// 目標格式（待技術確認）：
// const { BookValidationError, NetworkError } = require('src/core/errors/BookValidationError')
```

**當前狀況**:
- ❌ **實施暫停**: Jest 環境路徑解析問題
- 🔄 **技術評估**: 尋找穩定的路徑策略
- ✅ **測試優先**: 確保 100% 測試通過率

### 🔧 **4. 混合路徑修正**

#### ❌ **修正前 (Before)**
```markdown
### 快速導覽
1. [核心架構總覽](./core-architecture.md) - 當前檔案同層引用
2. [開發問題診斷](../03-reference/troubleshooting/) - 跨域引用  
3. [專案規範](../../claude/chrome-extension-specs.md) - Claude文檔引用
```

#### ✅ **修正後 (After)**
```markdown
### 快速導覽  
1. [核心架構總覽](./docs/domains/01-getting-started/core-architecture.md) - 完整語意路徑
2. [開發問題診斷](./docs/domains/03-reference/troubleshooting/) - 完整語意路徑
3. [專案規範](./docs/claude/chrome-extension-specs.md) - 完整語意路徑
```

**修正原則**:
- 即使是同層文件，也使用完整語意化路徳
- 統一所有引用格式，提升維護性
- 讓路徑「單看就理解」來源與責任

### 🔧 **5. 大規模路徑語意化專案範例**

#### ❌ **修正前 (Before)**
```markdown
# 專案中發現的612個相對路徑引用分佈：
- 單層相對路徑：372個 (如 ../02-development/)
- 雙層相對路徑：112個 (如 ../../claude/event-driven-architecture.md)
- 三層相對路徑：45個 (如 ../../../core/errors/BookValidationError)
- 其他深度路徑：83個 (如 ../../../../utils/helpers)
```

#### ✅ **修正後 (After)**
```markdown
# 全部轉換為語意化根路徑：
- 文件引用：docs/domains/, docs/claude/
- 程式碼引用：src/core/, src/domains/
- 配置檔案：使用專案根路徑
- 完全消除相對深度計算 (../../../)
```

**修正原則**:
- ✅ 612個引用全部轉換，零遺漏政策
- ✅ 批次處理：每批50個文件，確保品質
- ✅ 分類處理：文件類、程式碼類、配置類分別處理
- ✅ 完整驗證：每批次後驗證連結完整性
- ✅ 量化追蹤：提供具體修正統計數據

**批次處理策略**:
```markdown
Phase 1: 文檔類路徑修正 (372個單層 + 部分雙層)
- 批次大小: 50個文件/批
- 驗證重點: 文件連結完整性
- 預估批次: 8批次

Phase 2: Claude文檔路徑修正 (112個雙層引用)
- 批次大小: 25個文件/批  
- 驗證重點: 規範文檔可訪問性
- 預估批次: 5批次

Phase 3: 程式碼類路徑修正 (45個三層 + 83個其他)
- 批次大小: 20個文件/批
- 驗證重點: 模組引用正確性
- 預估批次: 7批次
```

---

## 📦 模組匯入/匯出一致性修正範例

### 🔧 **1. 解構匯入與匯出方式不匹配**

#### ❌ **修正前 (Before)**
```javascript
// 檔案: messaging-domain-coordinator.js
// 錯誤：使用解構匯入，但服務使用直接匯出
const { MessageRoutingService } = require('src/background/domains/messaging/services/message-routing-service')
const { SessionManagementService } = require('src/background/domains/messaging/services/session-management-service')
const { ConnectionMonitoringService } = require('src/background/domains/messaging/services/connection-monitoring-service')
const { MessageValidationService } = require('src/background/domains/messaging/services/message-validation-service')
const { QueueManagementService } = require('src/background/domains/messaging/services/queue-management-service')

// 使用服務時會報錯：TypeError: MessageRoutingService is not a constructor
this.services.set('routing', new MessageRoutingService(dependencies))
this.services.set('session', new SessionManagementService(dependencies))
```

#### ✅ **修正後 (After)**
```javascript
// 檔案: messaging-domain-coordinator.js
// 正確：根據服務的實際匯出方式使用對應的匯入語法

// 直接匯出的服務：使用直接匯入
const MessageRoutingService = require('src/background/domains/messaging/services/message-routing-service')
const SessionManagementService = require('src/background/domains/messaging/services/session-management-service')

// 物件匯出的服務：使用解構匯入
const { ConnectionMonitoringService } = require('src/background/domains/messaging/services/connection-monitoring-service')
const { MessageValidationService } = require('src/background/domains/messaging/services/message-validation-service')
const { QueueManagementService } = require('src/background/domains/messaging/services/queue-management-service')

// 正常使用服務
this.services.set('routing', new MessageRoutingService(dependencies))
this.services.set('session', new SessionManagementService(dependencies))
```

**修正判斷規則**:
```javascript
// 檢查服務檔案的匯出方式
// 案例 1: 直接匯出 → 使用直接匯入
module.exports = ServiceClass
// 對應匯入: const ServiceClass = require('path/to/service')

// 案例 2: 物件匯出 → 使用解構匯入  
module.exports = { ServiceClass, OTHER_EXPORTS }
// 對應匯入: const { ServiceClass } = require('path/to/service')
```

### 🔧 **2. 重複匯入問題修正**

#### ❌ **修正前 (Before)**
```javascript
// 檔案頂部已有匯入
const MessageRoutingService = require('./services/message-routing-service')
const SessionManagementService = require('./services/session-management-service')
const { ConnectionMonitoringService } = require('./services/connection-monitoring-service')
const { MessageValidationService } = require('./services/message-validation-service')
const { QueueManagementService } = require('./services/queue-management-service')

// 方法內部又重複匯入 - 錯誤！
initializeServices(dependencies) {
  // 重複匯入，並且使用錯誤的解構語法
  const { MessageRoutingService } = require('src/background/domains/messaging/services/message-routing-service')
  const { SessionManagementService } = require('src/background/domains/messaging/services/session-management-service')
  const { ConnectionMonitoringService } = require('src/background/domains/messaging/services/connection-monitoring-service')
  const { MessageValidationService } = require('src/background/domains/messaging/services/message-validation-service')
  const { QueueManagementService } = require('src/background/domains/messaging/services/queue-management-service')

  // 使用服務...
}
```

#### ✅ **修正後 (After)**  
```javascript
// 檔案頂部統一匯入
const MessageRoutingService = require('./services/message-routing-service')
const SessionManagementService = require('./services/session-management-service')
const { ConnectionMonitoringService } = require('./services/connection-monitoring-service')
const { MessageValidationService } = require('./services/message-validation-service')
const { QueueManagementService } = require('./services/queue-management-service')

// 方法內直接使用已匯入的服務
initializeServices(dependencies) {
  // 使用頂部已匯入的服務類別，無需重新載入
  
  // 創建微服務實例
  this.services.set('validation', new MessageValidationService(dependencies))
  this.services.set('queue', new QueueManagementService(dependencies))
  this.services.set('connection', new ConnectionMonitoringService(dependencies))
  this.services.set('session', new SessionManagementService(dependencies))
  this.services.set('routing', new MessageRoutingService(dependencies))
}
```

### 🔧 **3. 混合匯出方式統一化**

#### 📋 **問題識別**
```javascript
// 發現專案中服務匯出方式不一致：

// 方式 1: 直接匯出 (2個服務)
module.exports = SessionManagementService
module.exports = MessageRoutingService

// 方式 2: 物件匯出 (3個服務) 
module.exports = { ConnectionMonitoringService, LIMITS, TIMEOUTS }
module.exports = { MessageValidationService, VALIDATION_RULES, SECURITY_RULES }
module.exports = { QueueManagementService, QUEUE_CONFIG, PROCESSING_CONFIG }
```

#### ✅ **統一化建議**
```javascript
// 建議：統一使用物件匯出方式，提供更好的擴展性
// 優點：可以匯出多個相關的類別、常數、工具函數

// 統一格式：
module.exports = { 
  SessionManagementService,
  // 未來可以添加相關常數或工具函數
}

module.exports = { 
  MessageRoutingService,
  // 未來可以添加路由相關常數
}

// 對應的統一匯入格式：
const { SessionManagementService } = require('./services/session-management-service')
const { MessageRoutingService } = require('./services/message-routing-service')
const { ConnectionMonitoringService } = require('./services/connection-monitoring-service')
const { MessageValidationService } = require('./services/message-validation-service')
const { QueueManagementService } = require('./services/queue-management-service')
```

**修正優先級**:
1. 🔴 **Critical**: 修正匯入/匯出不匹配導致的運行時錯誤
2. 🟡 **High**: 消除重複匯入，簡化程式碼結構
3. 🟢 **Medium**: 統一匯出方式，提升程式碼一致性

**檢查清單**:
- [ ] 確認每個服務檔案的實際匯出方式
- [ ] 修正所有匯入語句匹配對應的匯出方式
- [ ] 消除方法內部的重複匯入
- [ ] 驗證修正後所有服務能正常實例化
- [ ] 執行整合測試確保修正無誤

---

## 🚨 StandardError 錯誤代碼語意化修正範例

### 🎯 **錯誤代碼語意化原則**

**✅ 語意化錯誤代碼設計**:
- ✅ **具體化**: 使用具體的錯誤代碼而非 `UNKNOWN_ERROR`
- ✅ **領域導向**: 錯誤代碼反映所屬領域和操作類型
- ✅ **一致性**: 同類型錯誤使用統一的命名模式
- ✅ **可維護**: 錯誤代碼有明確的業務含義

**📋 錯誤代碼分類與命名規範**:
1. **驗證錯誤**: `{DOMAIN}_VALIDATION_ERROR` 或 `{OPERATION}_VALIDATION_FAILED`
2. **操作錯誤**: `{DOMAIN}_{OPERATION}_ERROR`
3. **系統錯誤**: `{COMPONENT}_ERROR` 或 `{SERVICE}_SYSTEM_ERROR`
4. **配置錯誤**: `{COMPONENT}_CONFIG_ERROR`

### 🔧 **1. 搜尋協調器錯誤代碼修正**

#### ❌ **修正前 (Before)**
```javascript
// 使用泛用的 UNKNOWN_ERROR - 缺乏語意
_validateSearchInputs (query, filters) {
  if (query === null || query === undefined) {
    throw new StandardError('UNKNOWN_ERROR', 'Search query is required', {
      category: 'ui'
    })
  }

  if (typeof query !== 'string') {
    throw new StandardError('UNKNOWN_ERROR', 'Search query must be a string', {
      category: 'ui'
    })
  }

  if (filters === null || filters === undefined) {
    throw new StandardError('UNKNOWN_ERROR', 'Filter conditions are required', {
      category: 'ui'
    })
  }
}

_validateFilterInputs (searchResults, filters) {
  if (!Array.isArray(searchResults)) {
    throw new StandardError('UNKNOWN_ERROR', 'Search results array is required', {
      category: 'ui'
    })
  }
}

// 運行時錯誤
async executeSearch (query, filters = {}) {
  try {
    // ... 執行邏輯
  } catch (error) {
    throw new StandardError('UNKNOWN_ERROR', 'Search coordination failed: ' + error.message, {
      category: 'ui'
    })
  }
}
```

#### ✅ **修正後 (After)**
```javascript
// 使用語意化的錯誤代碼 - 明確的業務含義
_validateSearchInputs (query, filters) {
  if (query === null || query === undefined) {
    throw new StandardError('SEARCH_VALIDATION_ERROR', 'Search query is required', {
      category: 'ui',
      field: 'query',
      validationType: 'required'
    })
  }

  if (typeof query !== 'string') {
    throw new StandardError('SEARCH_VALIDATION_ERROR', 'Search query must be a string', {
      category: 'ui',
      field: 'query',
      validationType: 'type',
      expectedType: 'string',
      actualType: typeof query
    })
  }

  if (filters === null || filters === undefined) {
    throw new StandardError('FILTER_VALIDATION_ERROR', 'Filter conditions are required', {
      category: 'ui',
      field: 'filters',
      validationType: 'required'
    })
  }
}

_validateFilterInputs (searchResults, filters) {
  if (!Array.isArray(searchResults)) {
    throw new StandardError('FILTER_VALIDATION_ERROR', 'Search results array is required', {
      category: 'ui',
      field: 'searchResults',
      validationType: 'type',
      expectedType: 'array',
      actualType: typeof searchResults
    })
  }
}

// 運行時錯誤
async executeSearch (query, filters = {}) {
  try {
    // ... 執行邏輯
  } catch (error) {
    throw new StandardError('SEARCH_COORDINATION_ERROR', 'Search coordination failed: ' + error.message, {
      category: 'ui',
      operation: 'executeSearch',
      originalError: error.message
    })
  }
}
```

### 🔧 **2. 測試期望更新**

#### ❌ **修正前 (Before)**
```javascript
// 測試期望使用 TEST_ERROR - 與實際錯誤代碼不符
const expectAsyncStandardError = async (promise, expectedCode = 'TEST_ERROR') => {
  try {
    await promise
    fail('Expected promise to throw StandardError')
  } catch (error) {
    expect(error).toBeInstanceOf(StandardError)
    expect(error.code).toBe('TEST_ERROR')  // 硬編碼測試用錯誤代碼
    expect(error.message).toBeDefined()
    expect(error.details).toBeDefined()
  }
}

it('should validate search query before execution', async () => {
  try {
    await searchCoordinator.executeSearch(null, {})
  } catch (error) {
    expect(error.code).toBe('TEST_ERROR')  // 與實際不符
  }
})
```

#### ✅ **修正後 (After)**
```javascript
// 測試期望使用實際的語意化錯誤代碼
const expectAsyncStandardError = async (promise, expectedCode = 'SEARCH_VALIDATION_ERROR') => {
  try {
    await promise
    fail('Expected promise to throw StandardError')
  } catch (error) {
    expect(error).toBeInstanceOf(StandardError)
    expect(error.code).toBe(expectedCode)  // 使用實際的錯誤代碼
    expect(error.message).toBeDefined()
    expect(error.details).toBeDefined()
  }
}

it('should validate search query before execution', async () => {
  // 測試搜尋查詢驗證
  try {
    await searchCoordinator.executeSearch(null, {})
  } catch (error) {
    expect(error.code).toBe('SEARCH_VALIDATION_ERROR')  // 對應實際錯誤代碼
    expect(error.details.field).toBe('query')
    expect(error.details.validationType).toBe('required')
  }

  // 測試篩選條件驗證
  try {
    await searchCoordinator.applyFiltersToResults([], null)
  } catch (error) {
    expect(error.code).toBe('FILTER_VALIDATION_ERROR')  // 篩選相關錯誤
    expect(error.details.field).toBe('filters')
  }
})
```

### 📋 **修正效益**

**✅ 修正成果**:
- 🎯 **語意清晰**: 錯誤代碼直接反映問題域和類型
- 🔍 **除錯容易**: 開發者可立即識別錯誤來源和類型
- 📊 **統計友善**: 可按錯誤類型進行監控和分析
- 🧪 **測試準確**: 測試期望與實際錯誤代碼完全對應
- 📝 **文件一致**: 錯誤處理策略與專案規範一致

**🎯 應用場景**:
- 搜尋功能錯誤處理改善
- 篩選器驗證錯誤分類
- 協調器運行時錯誤追蹤
- 測試斷言準確性提升

---

## 🧹 Lint 問題修正範例

### 🔧 **1. 格式化問題修正**

#### ❌ **修正前 (Before)**
```javascript
// trailing spaces, 不正確的縮排和分號
function validateBookData( bookData ){
if(bookData.title&&bookData.author)  {
console.log( "Validating book data..." )  
return true    
}
return false
}
```

#### ✅ **修正後 (After)**
```javascript
// 正確的格式化
function validateBookData(bookData) {
    if (bookData.title && bookData.author) {
        console.log("Validating book data...");
        return true;
    }
    return false;
}
```

**修正項目**:
- ✅ 移除尾隨空格 (trailing spaces)
- ✅ 修正函數括號前的空格 (space-before-function-paren)
- ✅ 統一縮排格式 (4空格)
- ✅ 加入必要的分號
- ✅ 優化運算符空格

### 🔧 **2. 未使用變數清理**

#### ❌ **修正前 (Before)**
```javascript
import { BookDataExtractor, ValidationHelper, StorageManager } from './extractors';
import { NetworkService } from './services';

function extractBookData(url) {
    const extractor = new BookDataExtractor();
    const unusedHelper = new ValidationHelper(); // 未使用
    const unusedService = new NetworkService(); // 未使用
    
    return extractor.extract(url);
}
```

#### ✅ **修正後 (After)**
```javascript
import { BookDataExtractor } from './extractors';

function extractBookData(url) {
    const extractor = new BookDataExtractor();
    return extractor.extract(url);
}
```

**修正項目**:
- ✅ 移除未使用的匯入 (unused imports)
- ✅ 移除未使用的變數宣告
- ✅ 簡化程式碼結構
- ✅ 提升程式碼可讀性

### 🔧 **3. Console.log 警告處理**

#### ❌ **修正前 (Before)**
```javascript
function processBookData(data) {
    console.log("Processing book data:", data); // 開發除錯用
    console.log("Data validation started"); // 開發除錯用

    if (!data.title) {
        console.log("Title is missing"); // 開發除錯用
        return null;
    }

    console.log("Processing completed"); // 開發除錯用
    return processedData;
}
```

#### ✅ **修正後 (After)**
```javascript
import { Logger } from 'src/core/utils/Logger';

function processBookData(data) {
    Logger.debug("Processing book data:", data);
    Logger.debug("Data validation started");

    if (!data.title) {
        Logger.warn("Title is missing");
        return null;
    }

    Logger.debug("Processing completed");
    return processedData;
}
```

**修正項目**:
- ✅ 使用專案 Logger 系統替換 console.log
- ✅ 適當的日誌等級 (debug, warn, error)
- ✅ 統一日誌管理機制
- ✅ 生產環境日誌控制

---

## 📝 Markdown 格式標準化範例

### 🔧 **1. 標題格式標準化**

#### ❌ **修正前 (Before)**
```markdown
##核心功能
### 資料提取
####驗證機制
```

#### ✅ **修正後 (After)**
```markdown
## 核心功能

### 資料提取

#### 驗證機制
```

**修正項目**:
- ✅ 標題符號後加空格
- ✅ 標題前後加空行分隔
- ✅ 統一標題層級結構

### 🔧 **2. 程式碼區塊格式化**

#### ❌ **修正前 (Before)**
````markdown
```
function test() {
return true;
}
```
````

#### ✅ **修正後 (After)**
````markdown
```javascript
function test() {
    return true;
}
```
````

**修正項目**:
- ✅ 指定程式語言類型
- ✅ 正確縮排格式
- ✅ 提升語法高亮效果

### 🔧 **3. 清單格式統一**

#### ❌ **修正前 (Before)**
```markdown
* 項目一
- 項目二  
+ 項目三
    * 子項目a
    - 子項目b
```

#### ✅ **修正後 (After)**
```markdown
- 項目一
- 項目二
- 項目三
  - 子項目a
  - 子項目b
```

**修正項目**:
- ✅ 統一使用 `-` 作為清單符號
- ✅ 正確的巢狀縮排 (2空格)
- ✅ 一致的格式風格

---

## 🔧 Logger 使用模式標準化範例

### 🎯 **Logger 使用模式分類**

**三種標準化 Logger 使用模式**:

#### **模式1: Background Services (系統服務)**
```javascript
// ❌ Before: 缺乏設計理念註釋
this.logger = dependencies.logger || console

// ✅ After: 完整設計理念說明
// Logger 模式: Background Service (系統服務設計)
// 設計理念: 長期運行的系統服務需要完整日誌記錄能力
// 資源考量: Service Worker 環境資源充足，優先診斷能力
// 後備機制: console 提供基本日誌功能但功能有限
// 建議: 應優先使用完整 Logger 實例以獲得最佳診斷能力
this.logger = dependencies.logger || console
```

#### **模式2: UI Components (輕量化設計)**
```javascript
// ❌ Before: 混淆的 logger 初始化模式
this.logger = logger
if (this.logger) {
  this.logger.error(message, data)
} else {
  console.error(message, data)
}

// ✅ After: 明確的設計理念和使用模式
// Logger 模式: UI Component (輕量化設計)
// 設計理念: 短期存在的 UI 組件，優先效能和輕量化
// 資源考量: 頻繁創建/銷毀，避免不必要的物件分配
// 依賴注入: 外部提供 logger，可能為 null
this.logger = logger

// UI Component Logger 模式: 後備機制確保基本除錯能力
// 設計考量: 避免因 logger 不存在導致錯誤無法追蹤
// 效能優先: console.error 提供輕量級的錯誤記錄
if (this.logger) {
  this.logger.error(message, data)
} else {
  // 後備機制: 確保錯誤仍能被記錄和除錯
  console.error(message, data)
}
```

#### **模式3: Core Framework (基礎框架元件)**
```javascript
// ❌ Before: 缺乏架構考量說明
this.logger = new Logger(name || 'EventHandler')

// ✅ After: 完整的架構設計考量
// Logger 模式: Core EventHandler (基礎框架元件)
// 設計理念: 作為所有事件處理的基礎類別，必須提供完整日誌功能
// 架構考量: 核心元件負責統一的事件處理和錯誤記錄
// 繼承考量: 子類別可以依賴 this.logger 的存在，無需重新初始化
this.logger = new Logger(name || 'EventHandler')
```

### 🚨 **不一致案例修正**

#### **問題案例: 混合使用模式**
```javascript
// ❌ Before: UI Handler 錯誤地強制實例化 Logger
class BaseUIHandler extends EventHandler {
  constructor() {
    super()
    if (!this.logger) {
      this.logger = new Logger('BaseUIHandler') // ❌ 違反 UI 輕量化原則
    }
  }
}

// ✅ After: 符合架構分層的使用模式
class BaseUIHandler extends EventHandler {
  constructor() {
    super() // EventHandler 已提供 logger

    // Logger 模式: UI Handler (混合設計)
    // 設計理念: UI Handler 需要確保日誌功能可用性
    // 架構考量: 繼承自 EventHandler，可能已有 logger
    // 後備機制: 當 logger 未初始化時提供基本實例
    // 注意: 這個模式需要優化為純依賴注入模式
    if (!this.logger) {
      this.logger = new Logger('BaseUIHandler')
    }
  }
}
```

### 📋 **標準註釋模板**

**Background Services 模板**:
```javascript
// Logger 模式: Background Service (系統服務設計)
// 設計理念: 長期運行的系統服務需要完整日誌記錄能力
// 資源考量: Service Worker 環境資源充足，優先診斷能力
// 後備機制: console 提供基本日誌功能但功能有限
// 建議: 應優先使用完整 Logger 實例以獲得最佳診斷能力
this.logger = dependencies.logger || console
```

**UI Components 模板**:
```javascript
// Logger 模式: UI Component (輕量化設計)
// 設計理念: 短期存在的 UI 組件，優先效能和輕量化
// 資源考量: 頻繁創建/銷毀，避免不必要的物件分配
// 依賴注入: 外部提供 logger，可能為 null
this.logger = logger

// 使用時的後備機制模板:
// UI Component Logger 模式: 後備機制確保基本除錯能力
// 設計考量: 避免因 logger 不存在導致錯誤無法追蹤
// 效能優先: console.error 提供輕量級的錯誤記錄
if (this.logger) {
  this.logger.error(messageKey, data)
} else {
  // 後備機制: 確保錯誤仍能被記錄和除錯
  console.error(message, data)
}
```

---

## 🎯 檔案命名規範修正範例

### 🔧 **1. 檔名格式標準化**

#### ❌ **修正前 (Before)**
```
BookDataExtractor.js          # PascalCase 檔名
book_data_extractor.js        # snake_case 檔名
bookdataextractor.js          # 無分隔符檔名
BookData-Extractor.js         # 混合格式檔名
```

#### ✅ **修正後 (After)**
```
book-data-extractor.js        # kebab-case 檔名
validation-helper.service.js  # feature.type.js 格式
domain-coordinator.js         # 語意化命名
error-handler.util.js         # 功能責任清晰
```

**修正原則**:
- ✅ 使用 kebab-case 命名格式
- ✅ 採用 `feature.type.js` 結構  
- ✅ 檔名反映功能責任
- ✅ 避免縮寫和模糊名稱

### 🔧 **2. 目錄結構語意化**

#### ❌ **修正前 (Before)**
```
src/
├── utils/
├── helpers/
├── misc/
└── stuff/
```

#### ✅ **修正後 (After)**
```
src/
├── core/
│   ├── errors/
│   ├── validators/  
│   └── coordinators/
├── domains/
│   ├── data-management/
│   ├── book-extraction/
│   └── storage-sync/
└── infrastructure/
    ├── adapters/
    └── services/
```

**修正原則**:
- ✅ 目錄名稱具體表意
- ✅ 反映 domain 責任邊界
- ✅ 避免模糊的通用名稱
- ✅ 支援語意化路徑引用

---

## 🚀 批量處理最佳實踐

### 🔧 **1. 分批處理策略**

```markdown
## 批次處理計劃

**Phase 1**: 文檔類路徑修正 (150個文件)
- 批次大小: 25個文件/批
- 驗證重點: 連結完整性
- 預估時間: 6批次

**Phase 2**: 程式碼類路徑修正 (89個文件)  
- 批次大小: 15個文件/批
- 驗證重點: 模組引用正確性
- 預估時間: 6批次

**Phase 3**: Lint問題修正 (3760個問題)
- 批次大小: 500個問題/批
- 驗證重點: 功能無破壞性
- 預估時間: 8批次
```

### 🔧 **2. 品質確認檢查點**

```markdown
## 每批次完成後檢查

**連結完整性驗證**:
- [ ] 所有修正後的連結都能正確訪問
- [ ] 沒有產生 404 或破壞的連結
- [ ] 路徑語意與實際位置一致

**功能無破壞性驗證**:
- [ ] 修正後程式碼能正常執行
- [ ] 模組引用沒有產生錯誤
- [ ] 測試仍然通過

**格式一致性驗證**:
- [ ] 所有修正都符合專案標準
- [ ] 命名規範統一執行
- [ ] 程式碼風格一致
```

---

## 📊 修正效果評估標準

### 🎯 **成功指標**

**文件路徑語意化**:
- ✅ 轉換準確率: 100%
- ✅ 連結有效率: 100%  
- ✅ 語意清晰度: 95% 以上

**Lint 問題修復**:
- ✅ 自動修復率: 95% 以上
- ✅ 功能無破壞: 100%
- ✅ 程式碼品質提升: ESLint score 提升 80%

**整體品質提升**:
- ✅ 新人理解時間縮短 50%
- ✅ 文件維護成本降低 40%
- ✅ 開發效率提升 30%

---

## 🔄 持續改善機制

### 📋 **範例更新流程**

1. **新問題類型發現** → 記錄到範例集
2. **修正方式驗證** → 更新最佳實踐
3. **效果評估完成** → 調整修正策略
4. **工具優化需求** → 改善自動化流程

**範例集維護**:
- 每月回顧並更新範例
- 新增常見問題的修正模式
- 移除過時或不適用的範例
- 持續優化修正效率

---

**📚 Reference Index**:
- [Mint Format Specialist](./mint-format-specialist.md) - 專業格式化 sub-agent
- [程式碼品質範例](./code-quality-examples.md) - 程式碼品質標準  
- [檔案路徑語意規範](./../../CLAUDE.md#檔案路徑語意規範) - 路徑規範詳細說明

**🔧 Tool Integration**: 此範例集與 `mint-format-specialist` sub-agent 完全整合，確保修正的一致性和標準化。

---

## 📊 實施狀態更新

### ✅ **路徑語意化修正技術驗證完成**
**更新日期**: 2025-09-07  
**狀態**: ✅ 技術可行，正式實施中

**技術驗證結果**:
- ✅ Jest 環境完全支援 `src/` 前綴語意化路徑
- ✅ package.json 中 moduleNameMapper 配置正確：`"^src/(.*)$": "<rootDir>/src/$1"`
- ✅ 實際測試驗證無衝突，路徑解析正常運行
- ✅ Chrome Extension 環境相容性確認

**實施進度**:
1. ✅ **技術方案驗證通過** - Jest + Node.js 環境完全支援
2. 🔄 **批量修正進行中** - 已修正8個檔案，剩餘72個檔案
3. 📋 **品質確認機制** - 每批修正後執行測試驗證

**修正統計 (截至當前)**:
- **總需修正**：118個 require 語句，80個檔案
- **已完成修正**：12個語句，8個檔案  
- **剩餘待修正**：106個語句，72個檔案
- **修正準確率**：100% (無回滾案例)

**下一步行動**:
- 完成剩餘72個檔案的批量修正
- 執行完整測試套件驗證
- 建立 ESLint 規則防止未來引入錯誤格式