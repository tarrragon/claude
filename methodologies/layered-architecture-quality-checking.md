# 層級架構品質檢查機制

**主文件**: [層級隔離派工方法論](./layered-ticket-methodology.md)

---

## 核心概念

層級檢查的價值：
- 預防問題：在 Commit 前發現層級違規
- 提升效率：自動化檢查減少人工審查成本
- 保持品質：確保架構原則被嚴格遵守

---

## 檔案路徑分析法

**原理**：根據檔案路徑判斷所屬層級

```text
lib/
├── ui/                    // Layer 1 (UI/Presentation)
├── application/           // Layer 2 (Application/Behavior)
├── usecases/             // Layer 3 (UseCase)
├── domain/
│   ├── events/           // Layer 4 (Domain Events)
│   ├── interfaces/       // Layer 4 (Interfaces)
│   ├── entities/         // Layer 5 (Domain Implementation)
│   ├── value_objects/    // Layer 5
│   └── services/         // Layer 5
└── infrastructure/       // Infrastructure
```

---

## 測試範圍分析法

**測試檔案路徑對應**：
```text
test/
├── ui/           // 對應 Layer 1 修改
├── application/  // 對應 Layer 2 修改
├── usecases/     // 對應 Layer 3 修改
└── domain/       // 對應 Layer 4/5 修改
```

**測試類型對應**：
| 層級 | 測試類型 |
|------|---------|
| Layer 1 | Widget Test, Golden Test |
| Layer 2 | 行為測試（模擬事件觸發）|
| Layer 3 | UseCase Test（Mock Repository）|
| Layer 4 | 介面測試（驗證契約）|
| Layer 5 | Domain Test（純單元測試）|

---

## 違規模式識別

### 模式 1：UI 層包含業務邏輯

```dart
// ❌ 違規：Widget 中包含業務邏輯
class BookListWidget extends StatelessWidget {
  Widget build(BuildContext context) {
    final books = _filterNewBooks(_getAllBooks());  // ❌
    return ListView.builder(...);
  }
}

// ✅ 正確：Widget 只負責渲染
class BookListWidget extends StatelessWidget {
  final BookListController controller;
  Widget build(BuildContext context) {
    return ListView.builder(items: controller.filteredBooks);
  }
}
```

### 模式 2：Controller 包含業務規則

```dart
// ❌ 違規：Controller 包含核心業務規則
class BookController {
  Future<void> addBook(Book book) async {
    if (book.isbn.length != 13) {  // ❌ 業務規則
      throw ValidationException('ISBN 必須為 13 碼');
    }
    await bookRepository.save(book);
  }
}

// ✅ 正確：Controller 只呼叫 UseCase
class BookController {
  final AddBookUseCase addBookUseCase;
  Future<void> addBook(Book book) async {
    await addBookUseCase.execute(book);
  }
}
```

### 模式 3：UseCase 直接依賴具體實作

```dart
// ❌ 違規：依賴具體實作
class SearchBookUseCase {
  final SqliteBookRepository repository;  // ❌
}

// ✅ 正確：依賴抽象介面
class SearchBookUseCase {
  final IBookRepository repository;  // ✅
}
```

---

## 自動化檢查

### Pre-commit Hook

```bash
#!/bin/bash
echo "🔍 執行層級隔離檢查..."

# 1. 檢查單層修改原則
./scripts/check_single_layer_modification.sh || exit 1

# 2. 檢查測試覆蓋率
flutter test --coverage || exit 1

echo "✅ 所有檢查通過"
```

### CI/CD 整合

```yaml
name: PR Architecture Check
on: [pull_request]
jobs:
  architecture_check:
    runs-on: ubuntu-latest
    steps:
      - name: 檢查單層修改原則
        run: ./scripts/check_single_layer_in_pr.sh
      - name: 檢查測試覆蓋率
        run: flutter test --coverage
```

---

## 檢查清單

- [ ] 檔案路徑屬於單一層級？
- [ ] import 語句依賴方向正確（外層→內層）？
- [ ] 測試檔案路徑對應層級？
- [ ] 測試覆蓋率 100%？
- [ ] 無違規模式（UI 包含邏輯、Controller 包含規則）？

---

## Reference

- [層級隔離派工方法論](./layered-ticket-methodology.md) - 完整方法論
- [快速開始指南](./layered-ticket-quick-start.md) - 角色快速入門
