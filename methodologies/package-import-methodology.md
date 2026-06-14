# Package 導入路徑語意化方法論

## 核心概念

導入聲明是依賴關係的明確宣告與架構的文件化，不是節省字元的機械化路徑表達。每個 import 都應讓讀者立即識別依賴來源、理解模組層級、評估耦合程度、追蹤依賴鏈路。

> 各語言具體實現機制、跨語言範例、工具配置：`.claude/references/package-import-language-mechanisms.md`

## 五原則

### 第一原則：導入路徑的架構語意性

每個導入路徑必須完整表達來源的架構位置，禁用相對路徑隱藏架構關係。

```dart
// 正確：完整路徑語意，立即理解 Book 來自 Library Domain 的 entities 層
import 'package:book_overview_app/domains/library/entities/book.dart';
// 錯誤：相對路徑隱藏架構關係
import '../entities/book.dart';
```

### 第二原則：依賴來源的即時識別

從導入聲明本身即可理解依賴的領域歸屬與架構層級，無需開啟被導入檔案。

```dart
// 從導入立即理解：這是 Library Domain 的核心實體
import 'package:book_overview_app/domains/library/entities/book.dart';
```

### 第三原則：跨語言的一致性標準

統一的「Package 導入 + 完整路徑語意」哲學適用於所有程式語言（Dart / TS / Node.js / PHP / Go / Python / Java）。

```typescript
// 各語言保持相同的完整路徑語意原則
import { Book } from '@book-overview-app/domains/library/entities/book';
```

> 各語言完整範例：`.claude/references/package-import-language-mechanisms.md`「各語言語意化導入範例」

### 第四原則：消除別名和簡化

別名是命名不清與架構缺陷的象徵，正確做法是重構命名消除重名衝突，而非用別名掩蓋設計問題。

```dart
// 錯誤：別名掩蓋命名衝突
import 'package:app/domains/user/user.dart' as UserEntity;
import 'package:app/services/user.dart' as UserService;
// 正確：重構命名，職責清楚
import 'package:app/domains/user/user.dart';                 // User (實體)
import 'package:app/services/user-management-service.dart';  // UserManagementService (服務)
```

> 跨語言別名禁用實踐與根本策略：`.claude/references/package-import-language-mechanisms.md`「消除別名的跨語言實踐」

### 第五原則：架構透明性

導入聲明集合即是架構文件，讀者可從中看出模組整合範圍與依賴方向，驗證是否符合乾淨架構（無反向依賴）。

```dart
// 從導入立即理解：跨 Domain 協調器，整合 Library/Import/Search 三領域，使用 Core 錯誤處理
import 'package:book_overview_app/core/errors/standard_error.dart';
import 'package:book_overview_app/domains/library/services/library_service.dart';
import 'package:book_overview_app/domains/import/services/import_service.dart';
import 'package:book_overview_app/domains/search/services/search_service.dart';
```

## 開發階段檢查清單

新增導入時：

- [ ] 架構位置確認：導入路徑完整表達來源架構位置，可立即理解依賴性質
- [ ] 依賴方向驗證：符合架構原則，無循環依賴
- [ ] 語意明確性：避免相對路徑，不使用別名或簡化表示
- [ ] 一致性維護：與專案其他檔案導入風格一致，符合命名規範

## Reference

- `.claude/references/package-import-language-mechanisms.md` - 各語言實踐機制、跨語言範例、Linter / IDE / 自動化工具配置、相對路徑重構策略
- `.claude/skills/methodology-writing/SKILL.md` - 方法論撰寫標準

---

**Last Updated**: 2026-06-14
**Version**: 2.0.0 - 瘦身校準首檔（735→核心化）：保留導入本質 + 5 原則（每原則 1 代表範例）+ 開發檢查清單；各語言實踐機制 / 跨語言範例 / 工具配置外移至 `.claude/references/package-import-language-mechanisms.md`（W8-020.1）。歷史完整版見 git log。
