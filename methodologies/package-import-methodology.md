# Package 導入路徑語意化方法論

## 導入聲明的本質

### 導入不是什麼

導入聲明不是：

- **文件路徑的機械化表達**：不是為了節省字元數而設計
- **相對位置的簡化表示**：不是為了避免長路徑而妥協
- **開發便利性的工具**：不是為了快速輸入而犧牲可讀性
- **IDE 自動生成的結果**：不是讓工具決定程式碼結構

### 導入是什麼

導入聲明是：

- **依賴關係的明確宣告**：清楚表達模組間的連接
- **程式碼架構的文件化**：展示系統的組織結構
- **依賴來源的即時說明**：讓讀者立即理解依賴的性質
- **架構意圖的表達方式**：體現設計者對模組劃分的思考

## 第一原則：導入路徑的架構語意性

### 每個導入都必須清楚表達來源的架構位置

每個 import 聲明都必須讓閱讀者能夠：

- **立即識別依賴來源**：知道這個類別來自哪個領域
- **理解模組層級關係**：明白依賴的深度和性質
- **評估耦合程度**：判斷模組間的連接是否合理
- **追蹤依賴鏈路**：理解資料和控制的流向

### Package 導入的架構語意標準

#### 外部依賴的 Package 導入

```dart
// ✅ 正確：清楚表達外部依賴來源
import 'package:equatable/equatable.dart';
import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

// ❌ 錯誤：無法識別依賴性質
import 'equatable.dart';
import 'material.dart';
import 'provider.dart';
```

#### 內部模組的 Package 導入

```dart
// ✅ 正確：完整的架構路徑語意
import 'package:book_overview_app/domains/library/entities/book.dart';
import 'package:book_overview_app/domains/search/services/google_books_api.dart';
import 'package:book_overview_app/core/errors/standard_error.dart';

// ❌ 錯誤：相對路徑隱藏架構關係
import '../entities/book.dart';
import '../../search/services/google_books_api.dart';
import '../../../core/errors/standard_error.dart';
```

## 第二原則：依賴來源的即時識別

### 從導入聲明立即理解依賴性質

#### Domain 層級的語意表達

```dart
// 從導入立即理解：這是 Library Domain 的核心實體
import 'package:book_overview_app/domains/library/entities/book.dart';

// 從導入立即理解：這是 Import Domain 的值物件
import 'package:book_overview_app/domains/import/value_objects/import_task_id.dart';

// 從導入立即理解：這是 Search Domain 的服務
import 'package:book_overview_app/domains/search/services/book_similarity_calculator.dart';
```

#### 架構層級的語意表達

```dart
// 從導入立即理解：這是核心基礎設施
import 'package:book_overview_app/core/errors/standard_error.dart';

// 從導入立即理解：這是共用工具函式
import 'package:book_overview_app/shared/utils/date_formatter.dart';

// 從導入立即理解：這是使用者介面組件
import 'package:book_overview_app/ui/widgets/book_list_widget.dart';
```

## 第三原則：跨語言的一致性標準

### 統一的導入哲學適用於所有程式語言

#### Dart/Flutter 標準

```dart
// Package 導入 + 完整路徑語意
import 'package:book_overview_app/domains/library/entities/book.dart';
import 'package:book_overview_app/domains/search/services/api_service.dart';
```

#### TypeScript/JavaScript 標準

```typescript
// Module 導入 + 完整路徑語意
import { Book } from '@book-overview-app/domains/library/entities/book';
import { ApiService } from '@book-overview-app/domains/search/services/api-service';
```

#### Node.js/CommonJS 標準 (V1 專案實踐)

```javascript
// V1 專案：無框架的純 Node.js 實踐
// 使用相對於專案根目錄的完整路徑語意

const BaseModule = require('./lifecycle/base-module');
const LifecycleCoordinator = require('./lifecycle/lifecycle-coordinator');
const MessageRouter = require('./messaging/message-router');
const EventCoordinator = require('./events/event-coordinator');

// 或跨領域導入
const PageDomainCoordinator = require('./domains/page/page-domain-coordinator');
const ContentScriptService = require('./domains/page/services/content-script-coordinator-service');
```

#### PHP 原生標準

```php
<?php
// 使用完整命名空間 + autoloader
use BookOverview\Domains\Library\Entities\Book;
use BookOverview\Domains\Search\Services\ApiService;
use BookOverview\Core\Errors\StandardError;

// 或使用 require_once 的語意化路徑
require_once __DIR__ . '/../../domains/library/entities/Book.php';
require_once __DIR__ . '/../../domains/search/services/ApiService.php';
```

#### PHP Laravel 框架標準

```php
<?php
// Laravel 的命名空間 + Composer Autoloader
namespace App\Domains\Library\Entities;

use App\Domains\Search\Services\ApiService;
use App\Core\Errors\StandardError;
use Illuminate\Database\Eloquent\Model;
use Illuminate\Support\Facades\Log;

class Book extends Model
{
    // 完整命名空間讓讀者立即理解依賴來源
}
```

#### Go 語言標準

```go
package main

import (
    // 外部依賴使用 module path
    "github.com/gin-gonic/gin"
    "gorm.io/gorm"

    // 內部模組使用完整 module path
    "book-overview-app/domains/library/entities"
    "book-overview-app/domains/search/services"
    "book-overview-app/core/errors"
)

// 從導入立即理解模組來源和架構層級
func main() {
    book := entities.NewBook()
    service := services.NewApiService()
}
```

#### Python 標準

```python
# Package 導入 + 完整路徑語意
from book_overview_app.domains.library.entities import book
from book_overview_app.domains.search.services import api_service
from book_overview_app.core.errors import standard_error
```

#### Java 標準

```java
// Package 導入 + 完整路徑語意
import com.bookoverview.domains.library.entities.Book;
import com.bookoverview.domains.search.services.ApiService;
import com.bookoverview.core.errors.StandardError;
```

## 第四原則：消除別名和簡化

### 導入路徑必須保持完整性和明確性

#### 禁用別名的核心原則

**別名是程式設計不佳的象徵**，它反映的問題包括：

1. **命名不夠清晰明確**：導致不同模組產生重名衝突
2. **架構設計缺陷**：同一概念在不同領域使用相同名稱
3. **職責劃分不清**：模組邊界和責任沒有明確定義
4. **技術債務累積**：用別名掩蓋設計問題而非解決問題

#### 錯誤的別名解決方案

```dart
// ❌ 錯誤：使用別名掩蓋設計問題
import 'package:book_overview_app/domains/library/entities/book.dart' as LibBook;
import 'package:book_overview_app/domains/search/entities/book.dart' as SearchBook;

// 使用時仍然模糊不清
LibBook.Book bookEntity = LibBook.Book();
SearchBook.Book searchResult = SearchBook.Book();
```

#### 正確的重構解決方案

```dart
// ✅ 正確：重構命名，消除重名衝突
import 'package:book_overview_app/domains/library/entities/book.dart';
import 'package:book_overview_app/domains/search/entities/search_result.dart';

// 使用時語意清楚，職責明確
Book libraryBook = Book();
SearchResult searchData = SearchResult();
```

#### 別名問題的根本解決策略

**1. 重新審視命名責任**：
```dart
// 問題：兩個領域都有 'Book' 類別
// domains/library/entities/book.dart
// domains/search/entities/book.dart

// 解決：根據職責重新命名
// domains/library/entities/book.dart          -> Book (保留，因為是核心實體)
// domains/search/entities/book.dart           -> SearchResult (重構為更精確的名稱)
```

**2. 領域邊界清晰化**：
```typescript
// 問題：不同模組使用相同名稱
import { User } from './auth/user';      // 認證用戶
import { User } from './profile/user';   // 用戶資料

// 解決：依據職責重新命名
import { AuthenticatedUser } from './auth/authenticated-user';
import { UserProfile } from './profile/user-profile';
```

**3. 架構重構優於別名妥協**：
```go
// 問題：Package 內部衝突
import (
    authUser "project/auth/user"
    profileUser "project/profile/user"
)

// 解決：重新設計 Package 結構
import (
    "project/auth/authenticated-user"
    "project/profile/user-profile"
)
```

#### 別名禁用的實際效益

**1. 強制架構改善**：
- 禁用別名迫使開發者正視命名衝突
- 推動更清晰的領域劃分
- 改善整體系統架構

**2. 提升程式碼可讀性**：
- 每個導入都有唯一、明確的名稱
- 消除閱讀時的歧義
- 降低認知負擔

**3. 防止技術債務累積**：
- 避免用別名掩蓋設計問題
- 強制解決根本的架構缺陷
- 維護程式碼品質標準

#### 跨語言的別名禁用實踐

**Dart 範例**：
```dart
// ❌ 避免：別名掩蓋問題
import 'package:app/domains/user/user.dart' as UserEntity;
import 'package:app/services/user.dart' as UserService;

// ✅ 正確：重構消除衝突
import 'package:app/domains/user/user.dart';                    // User (實體)
import 'package:app/services/user-management-service.dart';     // UserManagementService (服務)
```

**TypeScript 範例**：
```typescript
// ❌ 避免：別名妥協
import { Component as BaseComponent } from './base';
import { Component as UIComponent } from './ui';

// ✅ 正確：明確命名
import { BaseComponent } from './base-component';
import { UIComponent } from './ui-component';
```

**Go 範例**：
```go
// ❌ 避免：Package 別名
import (
    httputil "net/http/httputil"
    customutil "project/http/util"
)

// ✅ 正確：重新組織 Package
import (
    "net/http/httputil"
    "project/http/custom-utilities"
)
```

#### 完整路徑的價值

```dart
// 讀者可以立即理解：
// 1. Book 來自 Library Domain 的 entities 層
// 2. GoogleBooksApi 來自 Search Domain 的 services 層
// 3. StandardError 來自 Core 基礎設施的 errors 模組

import 'package:book_overview_app/domains/library/entities/book.dart';
import 'package:book_overview_app/domains/search/services/google_books_api.dart';
import 'package:book_overview_app/core/errors/standard_error.dart';
```

## 第五原則：架構透明性

### 導入聲明作為架構文件

#### 從導入理解系統設計

```dart
// 從這個檔案的導入可以立即理解：
// 1. 這是一個跨 Domain 的協調器
// 2. 主要整合 Library、Import、Search 三個領域
// 3. 使用 Core 的標準錯誤處理
// 4. 依賴外部的 HTTP 套件

import 'package:http/http.dart';
import 'package:book_overview_app/core/errors/standard_error.dart';
import 'package:book_overview_app/domains/library/services/library_service.dart';
import 'package:book_overview_app/domains/import/services/import_service.dart';
import 'package:book_overview_app/domains/search/services/search_service.dart';
```

#### 依賴方向的視覺化

```dart
// 讀者可以立即看出依賴方向：
// UI → Domain → Core
// 沒有反向依賴，符合乾淨架構原則

import 'package:book_overview_app/core/interfaces/repository.dart';           // 向下依賴
import 'package:book_overview_app/domains/library/entities/book.dart';       // 平行依賴
import 'package:book_overview_app/domains/library/value_objects/book_id.dart'; // 向下依賴
```

## 實踐指導原則

### 開發階段的導入管理

#### 新增導入時的檢查清單

1. **架構位置確認**
   - [ ] 導入路徑完整表達了來源的架構位置
   - [ ] 可以從路徑立即理解依賴的性質

2. **依賴方向驗證**
   - [ ] 確認依賴方向符合架構原則
   - [ ] 沒有產生循環依賴

3. **語意明確性**
   - [ ] 避免使用相對路徑
   - [ ] 不使用別名或簡化表示

4. **一致性維護**
   - [ ] 與專案內其他檔案的導入風格一致
   - [ ] 符合團隊制定的命名規範

### IDE 配置建議

#### 自動導入設定

```json
// VS Code settings.json
{
  "dart.insertArgumentPlaceholders": false,
  "dart.includeArgumentPlaceholdersInClosingLabels": false,
  "dart.showTodos": false,
  "dart.analysisServerFolding": false,
  "dart.normalizePathCasing": true,
  "dart.organizeDirectivesOnSave": true,
  "dart.usePackageDirectives": true  // 強制使用 package 導入
}
```

### 重構既有相對路徑的策略

#### 漸進式轉換流程

1. **識別現有相對路徑**
   ```bash
   # 找出所有相對路徑導入
   grep -r "import '\.\." lib/
   ```

2. **按模組逐步轉換**
   ```bash
   # 一次轉換一個模組，避免大規模破壞
   # 先轉換 Core 模組，再轉換 Domain 模組
   ```

3. **驗證轉換結果**
   ```bash
   # 確保測試通過
   flutter test
   # 確保 linter 通過
   flutter analyze
   ```

## 各語言實踐機制說明

### 如何在不同語言中實現語意化導入

#### Dart/Flutter: Package 系統

**實現機制**：
- `pubspec.yaml` 定義 package 名稱
- Dart Package Manager 建立全域命名空間
- IDE 自動解析 `package:` 前綴路徑

```yaml
# pubspec.yaml
name: book_overview_app

# 啟用 package 導入
dependencies:
  flutter:
    sdk: flutter
```

**為什麼可以避免相對路徑**：Dart 編譯器將 `package:book_overview_app/` 映射到專案根目錄的 `lib/` 資料夾。

#### Node.js/CommonJS: 專案根目錄相對路徑 (V1 實踐)

**V1 專案的實現機制**：
```javascript
// V1 專案不使用任何 Node.js 框架，但仍能達成語意化導入
// 關鍵：所有檔案的 require() 都相對於當前檔案的明確位置

// 在 /src/background/background-coordinator.js 中
const BaseModule = require('./lifecycle/base-module')              // 同級子目錄
const PageDomainCoordinator = require('./domains/page/page-domain-coordinator')  // 跨領域

// 在 /src/background/domains/page/services/ 中的檔案
const BaseModule = require('../../../lifecycle/base-module')       // 明確的層級關係
```

**為什麼 V1 可以不需要絕對路徑**：
1. **一致的目錄結構**：所有模組都在 `/src/background/` 下，層級關係固定
2. **明確的相對路徑語意**：`./` = 同級，`../` = 上一級，路徑語意清楚
3. **模組化的檔案組織**：每個領域都有固定的目錄結構
4. **避免深層嵌套**：最多 3-4 層目錄，相對路徑仍然可讀
5. **Jest 測試環境的語意化導入支援**：透過 Jest 配置實現測試檔案的語意化路徑

**V1 的成功關鍵**：
- 嚴格的目錄命名規範
- 限制目錄深度
- 一致的模組組織方式
- 清楚的領域邊界

#### V1 專案的測試環境語意化實踐

**Jest 配置的關鍵設計**：

```javascript
// tests/jest.config.js - V1 專案的 Jest 配置
module.exports = {
  // 模組名稱映射 - 支援標準化語意路徑
  moduleNameMapper: {
    '^src/(.*)$': '<rootDir>/src/$1',           // src/ 路徑語意化
    '^@/(.*)$': '<rootDir>/src/$1',             // @ 別名映射
    '^@tests/(.*)$': '<rootDir>/tests/$1',      // 測試檔案語意化
    '^@mocks/(.*)$': '<rootDir>/tests/mocks/$1', // Mock 檔案語意化
    '^@fixtures/(.*)$': '<rootDir>/tests/fixtures/$1' // 測試資料語意化
  }
}
```

**V1 測試檔案的語意化導入實踐**：

```javascript
// 在測試檔案中 - 語意化導入實現
const { ErrorCodes } = require('src/core/errors/ErrorCodes')
const QualityAssessmentService = require('src/background/domains/data-management/services/quality-assessment-service.js')
const { StandardError } = require('src/core/errors/StandardError')

// 對比：如果沒有 Jest 配置會需要的複雜相對路徑
// const { ErrorCodes } = require('../../../../src/core/errors/ErrorCodes')
// const QualityAssessmentService = require('../../../../src/background/domains/data-management/services/quality-assessment-service.js')
```

**npm test vs Jest 直接執行的選擇**：

V1 專案最終選擇了 **npm test** 作為主要測試指令，原因：

1. **一致性管理**：
   ```json
   // package.json - 統一的測試入口
   "scripts": {
     "test": "npm run test:core",
     "test:core": "jest tests/unit tests/integration",
     "test:unit": "jest tests/unit",
     "test:integration": "jest tests/integration"
   }
   ```

2. **環境隔離**：透過 npm script 確保所有開發者使用相同的測試環境配置

3. **工具鏈整合**：可以在測試前後執行額外的設置和清理工作

**測試路徑語意化的實現機制**：

```javascript
// Jest 如何解析 V1 的語意化路徑：
// 1. 測試檔案寫入: require('src/core/errors/ErrorCodes')
// 2. Jest moduleNameMapper 攔截: '^src/(.*)$': '<rootDir>/src/$1'
// 3. 實際解析路徑: /project-root/src/core/errors/ErrorCodes.js
// 4. Node.js 載入模組: 成功匯入 ErrorCodes
```

**為什麼這種方式適合無框架專案**：

1. **零額外依賴**：不需要額外的模組解析工具或建置系統
2. **Jest 內建支援**：現代測試框架的標準功能
3. **配置簡單**：只需要一個 Jest 配置檔案
4. **維護性佳**：測試路徑變更只需要修改一個配置檔案
5. **團隊一致性**：所有開發者都使用相同的路徑語意

#### PHP 原生: 命名空間 + Autoloader

**實現機制**：
```php
// composer.json 設定 autoloader
{
    "autoload": {
        "psr-4": {
            "BookOverview\\": "src/"
        }
    }
}
```

**為什麼可以避免 include/require 路徑**：
- Composer autoloader 自動載入類別
- PSR-4 標準映射命名空間到檔案路徑
- `use` 語句提供完整的類別來源資訊

#### PHP Laravel: 框架級別的命名空間

**實現機制**：
```php
// Laravel 預設的命名空間映射
"autoload": {
    "psr-4": {
        "App\\": "app/",
        "Database\\Factories\\": "database/factories/",
        "Database\\Seeders\\": "database/seeders/"
    }
}
```

**為什麼框架能提供更好的語意化**：
- 框架預先定義了標準的目錄結構
- Service Provider 自動注冊依賴
- Facade 提供統一的服務存取介面
- 強制性的命名規範

#### Go: Module System

**實現機制**：
```go
// go.mod 定義 module 名稱
module book-overview-app

go 1.21

// 導入時使用完整 module path
import "book-overview-app/domains/library/entities"
```

**為什麼 Go 的導入最語意化**：
- Module path 必須是全域唯一的
- 編譯時檢查所有依賴
- 沒有相對路徑導入的選項（除了同 package）
- 強制性的 package 組織方式

#### TypeScript/JavaScript: Module Resolution

**實現機制**：
```json
// tsconfig.json 或 package.json
{
  "compilerOptions": {
    "baseUrl": ".",
    "paths": {
      "@/*": ["src/*"],
      "@domains/*": ["src/domains/*"],
      "@core/*": ["src/core/*"]
    }
  }
}
```

**框架特定的實現**：
```javascript
// Next.js 自動支援 @ 別名
import { Book } from '@/domains/library/entities/book'

// Angular 使用 barrel exports
import { Book } from '@domains/library'

// Vue.js 使用 alias 配置
import { Book } from '@domains/library/entities/book'
```

### 語言特性對比總結

| 語言 | 實現機制 | 優勢 | 注意事項 | 測試環境支援 |
|------|----------|------|----------|-------------|
| **Dart** | Package system | 編譯時解析，IDE 支援佳 | 需要正確配置 pubspec.yaml | 原生支援 package: 導入 |
| **Go** | Module system | 強制語意化，無相對路徑 | Module path 必須全域唯一 | 測試檔案使用相同 module path |
| **PHP Laravel** | 框架 + Composer | 自動載入，標準化目錄 | 依賴框架規範 | PHPUnit 自動載入命名空間 |
| **TypeScript** | Module resolution | 彈性配置，工具支援 | 需要配置 path mapping | Jest/Vitest 支援 path mapping |
| **Node.js (V1)** | 相對路徑 + Jest 映射 | 生產簡單，測試語意化 | 需要目錄規範 + Jest 配置 | **Jest moduleNameMapper 實現語意化** |
| **Python** | Package imports | 簡潔語法，標準化 | 需要正確的 __init__.py | pytest 原生支援 package 導入 |

### 實踐選擇指南

#### 選擇適合的實現方式

1. **有框架的專案**:
   - 使用框架提供的模組系統
   - 例如：Laravel、Angular、Next.js
   - 測試環境通常自動繼承框架的模組解析

2. **無框架的專案 (如 V1 範例)**:
   - **生產環境**：採用嚴格的目錄規範 + 相對路徑
   - **測試環境**：使用 Jest moduleNameMapper 實現語意化
   - 限制目錄深度 (≤ 4 層)
   - 關鍵優勢：生產簡單，測試語意化

3. **混合策略專案**:
   - 生產環境使用簡單的相對路徑
   - 測試環境透過工具配置實現語意化
   - 適合輕量級 Node.js 專案

4. **跨語言團隊**:
   - 統一使用類似的命名空間概念
   - 建立一致的目錄結構規範
   - 採用相同的領域驅動設計原則
   - **測試策略一致性**：確保所有語言都有語意化的測試導入

## 工具支援和自動化

### Linter 規則配置

#### analysis_options.yaml 設定

```yaml
analyzer:
  strong-mode:
    implicit-casts: false
    implicit-dynamic: false

linter:
  rules:
    # 強制使用 package 導入
    prefer_relative_imports: false
    # 禁用相對路徑導入
    avoid_relative_lib_imports: true
```

### 自動化檢查腳本

#### 導入合規性檢查

```bash
#!/bin/bash
# scripts/check-import-compliance.sh

echo "檢查相對路徑導入..."
relative_imports=$(grep -r "import '\.\." lib/ | wc -l)

if [ "$relative_imports" -gt 0 ]; then
    echo "❌ 發現 $relative_imports 個相對路徑導入"
    grep -r "import '\.\." lib/
    exit 1
else
    echo "✅ 所有導入都使用 package 路徑"
fi
```

## 總結

Package 導入路徑語意化方法論的核心價值：

1. **架構透明性**：從導入立即理解系統結構
2. **維護便利性**：減少理解和修改的認知負擔
3. **團隊協作**：統一的導入風格提升溝通效率
4. **跨語言一致性**：建立統一的程式碼組織哲學

遵循這個方法論，程式碼將成為自說明的架構文件，每個導入聲明都清楚表達系統的設計意圖和模組關係。
