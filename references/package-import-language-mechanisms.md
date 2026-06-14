# Package 導入各語言實踐機制與工具支援

> **用途**：本檔為 `.claude/methodologies/package-import-methodology.md` 的衛星參考檔，存放各語言的語意化導入實現機制、跨語言程式碼範例、Linter / 自動化工具配置。寫具體語言的導入程式碼或配置工具前按需讀取。
>
> **核心方法論（5 原則 + 檢查清單）**：`.claude/methodologies/package-import-methodology.md`（需回顧原則定義或開發階段檢查清單時讀）

---

## 各語言語意化導入範例

各語言在「Package 導入 + 完整路徑語意」哲學下的具體寫法。正例展示如何讓讀者從導入立即理解依賴來源；反例展示無法識別依賴性質的寫法。

### Dart/Flutter

```dart
// 正確：清楚表達依賴來源（外部 package 與內部模組）
import 'package:flutter/material.dart';
import 'package:book_overview_app/domains/library/entities/book.dart';
import 'package:book_overview_app/core/errors/standard_error.dart';

// 錯誤：相對路徑隱藏架構關係，無法識別依賴性質
import 'material.dart';
import '../entities/book.dart';
import '../../../core/errors/standard_error.dart';
```

### TypeScript/JavaScript

```typescript
// Module 導入 + 完整路徑語意
import { Book } from '@book-overview-app/domains/library/entities/book';
import { ApiService } from '@book-overview-app/domains/search/services/api-service';
```

### Node.js/CommonJS (V1 專案實踐，無框架)

```javascript
// 使用相對於當前檔案明確位置的完整路徑語意
const BaseModule = require('./lifecycle/base-module');
const MessageRouter = require('./messaging/message-router');
const PageDomainCoordinator = require('./domains/page/page-domain-coordinator');
```

### PHP 原生

```php
<?php
// 完整命名空間 + autoloader
use BookOverview\Domains\Library\Entities\Book;
use BookOverview\Core\Errors\StandardError;
```

### PHP Laravel

```php
<?php
namespace App\Domains\Library\Entities;

use App\Domains\Search\Services\ApiService;
use Illuminate\Database\Eloquent\Model;
```

### Go

```go
import (
    // 外部依賴使用 module path
    "github.com/gin-gonic/gin"
    // 內部模組使用完整 module path
    "book-overview-app/domains/library/entities"
    "book-overview-app/core/errors"
)
```

### Python

```python
from book_overview_app.domains.library.entities import book
from book_overview_app.core.errors import standard_error
```

### Java

```java
import com.bookoverview.domains.library.entities.Book;
import com.bookoverview.core.errors.StandardError;
```

---

## 消除別名的跨語言實踐

別名是程式設計不佳的象徵，反映命名不清、架構缺陷、職責模糊、技術債務。正確做法是重構命名消除重名衝突，而非用別名掩蓋。

### Dart

```dart
// 避免：別名掩蓋命名衝突
import 'package:app/domains/user/user.dart' as UserEntity;
import 'package:app/services/user.dart' as UserService;

// 正確：重構命名，消除衝突
import 'package:app/domains/user/user.dart';                    // User (實體)
import 'package:app/services/user-management-service.dart';     // UserManagementService (服務)
```

### TypeScript

```typescript
// 避免：別名妥協
import { Component as BaseComponent } from './base';
import { Component as UIComponent } from './ui';

// 正確：明確命名
import { BaseComponent } from './base-component';
import { UIComponent } from './ui-component';
```

### Go

```go
// 避免：Package 別名
import (
    httputil "net/http/httputil"
    customutil "project/http/util"
)

// 正確：重新組織 Package
import (
    "net/http/httputil"
    "project/http/custom-utilities"
)
```

### 別名禁用的根本策略

| 策略 | 說明 |
|------|------|
| 重新審視命名責任 | 兩領域同名類別依職責重新命名（如 library 的 Book 保留、search 的 Book 改為 SearchResult） |
| 領域邊界清晰化 | 不同模組相同名稱依職責重命名（如 AuthenticatedUser / UserProfile） |
| 架構重構優於別名妥協 | Package 內部衝突時重新設計 Package 結構 |

---

## 各語言實現機制說明

### Dart/Flutter: Package 系統

- `pubspec.yaml` 定義 package 名稱，Dart Package Manager 建立全域命名空間
- 編譯器將 `package:book_overview_app/` 映射到專案根目錄的 `lib/` 資料夾

```yaml
# pubspec.yaml
name: book_overview_app
dependencies:
  flutter:
    sdk: flutter
```

### Node.js/CommonJS: 專案根目錄相對路徑 (V1 實踐)

V1 專案不使用任何框架，仍能達成語意化導入。關鍵：所有 `require()` 相對於當前檔案的明確位置。

V1 成功關鍵：嚴格的目錄命名規範、限制目錄深度（≤ 4 層）、一致的模組組織方式、清楚的領域邊界。

**測試環境語意化（Jest moduleNameMapper）**：

```javascript
// tests/jest.config.js
module.exports = {
  moduleNameMapper: {
    '^src/(.*)$': '<rootDir>/src/$1',
    '^@/(.*)$': '<rootDir>/src/$1',
    '^@tests/(.*)$': '<rootDir>/tests/$1'
  }
}
```

測試檔案因此可寫 `require('src/core/errors/ErrorCodes')`，由 Jest 攔截映射到實際路徑，避免 `require('../../../../src/core/errors/ErrorCodes')` 的複雜相對路徑。V1 統一以 `npm test` 為入口（一致性管理、環境隔離、工具鏈整合）。

### PHP 原生: 命名空間 + Autoloader

```php
// composer.json
{
    "autoload": {
        "psr-4": { "BookOverview\\": "src/" }
    }
}
```

Composer autoloader 依 PSR-4 標準將命名空間映射到檔案路徑，`use` 語句提供完整類別來源資訊。

### PHP Laravel: 框架級別命名空間

```php
"autoload": {
    "psr-4": {
        "App\\": "app/",
        "Database\\Factories\\": "database/factories/"
    }
}
```

框架預先定義標準目錄結構、Service Provider 自動註冊依賴、Facade 提供統一存取介面、強制命名規範。

### Go: Module System

```go
// go.mod
module book-overview-app
go 1.21
```

Module path 必須全域唯一、編譯時檢查所有依賴、無相對路徑導入選項（除同 package）、強制 package 組織方式。

### TypeScript/JavaScript: Module Resolution

```json
// tsconfig.json
{
  "compilerOptions": {
    "baseUrl": ".",
    "paths": {
      "@/*": ["src/*"],
      "@domains/*": ["src/domains/*"]
    }
  }
}
```

框架特定支援：Next.js 自動支援 `@` 別名、Angular 使用 barrel exports、Vue.js 使用 alias 配置。

### 語言特性對比總結

| 語言 | 實現機制 | 優勢 | 注意事項 | 測試環境支援 |
|------|----------|------|----------|-------------|
| Dart | Package system | 編譯時解析，IDE 支援佳 | 需正確配置 pubspec.yaml | 原生支援 package: 導入 |
| Go | Module system | 強制語意化，無相對路徑 | Module path 必須全域唯一 | 測試檔案用相同 module path |
| PHP Laravel | 框架 + Composer | 自動載入，標準化目錄 | 依賴框架規範 | PHPUnit 自動載入命名空間 |
| TypeScript | Module resolution | 彈性配置，工具支援 | 需配置 path mapping | Jest/Vitest 支援 path mapping |
| Node.js (V1) | 相對路徑 + Jest 映射 | 生產簡單，測試語意化 | 需目錄規範 + Jest 配置 | Jest moduleNameMapper 實現語意化 |
| Python | Package imports | 簡潔語法，標準化 | 需正確的 __init__.py | pytest 原生支援 package 導入 |

### 實踐選擇指南

| 專案類型 | 實現方式 |
|---------|---------|
| 有框架的專案 | 使用框架提供的模組系統（Laravel / Angular / Next.js），測試環境通常繼承框架的模組解析 |
| 無框架的專案（如 V1） | 生產環境用嚴格目錄規範 + 相對路徑；測試環境用 Jest moduleNameMapper；限制目錄深度 ≤ 4 層 |
| 混合策略專案 | 生產環境用簡單相對路徑，測試環境透過工具配置實現語意化 |
| 跨語言團隊 | 統一命名空間概念、一致的目錄結構規範、相同的領域驅動設計原則、測試策略一致性 |

---

## 工具支援與自動化

### Linter 規則配置（Dart）

```yaml
# analysis_options.yaml
linter:
  rules:
    prefer_relative_imports: false      # 強制使用 package 導入
    avoid_relative_lib_imports: true    # 禁用相對路徑導入
```

### IDE 配置（VS Code Dart）

```json
{
  "dart.organizeDirectivesOnSave": true,
  "dart.usePackageDirectives": true
}
```

### 自動化檢查腳本

```bash
#!/bin/bash
# scripts/check-import-compliance.sh
relative_imports=$(grep -r "import '\.\." lib/ | wc -l)
if [ "$relative_imports" -gt 0 ]; then
    echo "[FAIL] 發現 $relative_imports 個相對路徑導入"
    grep -r "import '\.\." lib/
    exit 1
else
    echo "[OK] 所有導入都使用 package 路徑"
fi
```

### 重構既有相對路徑的策略

1. 識別現有相對路徑：`grep -r "import '\.\." lib/`
2. 按模組逐步轉換：先轉換 Core 模組，再轉換 Domain 模組，避免大規模破壞
3. 驗證轉換結果：`flutter test` + `flutter analyze`

---

**Last Updated**: 2026-06-14
**Version**: 1.0.0 - 從 package-import-methodology.md 外移各語言實踐機制、跨語言範例、工具配置（W8-020.1 方法論瘦身校準）
