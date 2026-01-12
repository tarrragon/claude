# 層級隔離實踐案例

**主文件**: [層級隔離派工方法論](./layered-ticket-methodology.md)

---

## 案例總覽

| 案例 | 場景 | 重點 |
|-----|------|------|
| 案例 1 | 新增書籍搜尋功能 | 完整五層實作 |
| 案例 2 | 重構現有程式碼 | 違規識別與修正 |
| 案例 3 | 架構遷移 | Interface-First 策略 |

---

## 案例 1：新增書籍搜尋功能

**需求**：使用者輸入 ISBN 或書名，搜尋並顯示結果列表

### Ticket 拆分

| Ticket | 層級 | 變更範圍 |
|--------|------|---------|
| Ticket 1 | Layer 5 | Book Entity, ISBN Value Object |
| Ticket 2 | Layer 4 | IBookRepository 介面 |
| Ticket 3 | Layer 3 | SearchBookUseCase |
| Ticket 4 | Layer 2 | BookSearchController |
| Ticket 5 | Layer 1 | 搜尋頁面 UI |

### 關鍵實作模式

**Layer 5 - Domain**：
```dart
class ISBN {
  final String value;
  ISBN(this.value) {
    if (!_isValid(value)) throw ValidationException('ISBN 格式無效');
  }
}
```

**Layer 4 - Interface**：
```dart
abstract class IBookRepository {
  Future<OperationResult<List<Book>>> searchByIsbn(String isbn);
  Future<OperationResult<List<Book>>> searchByTitle(String title);
}
```

**Layer 3 - UseCase**：
```dart
class SearchBookUseCase {
  final IBookRepository bookRepository;
  Future<OperationResult<List<Book>>> execute(String query) async {
    final isIsbn = ISBN.isValidFormat(query);
    return isIsbn
        ? await bookRepository.searchByIsbn(query)
        : await bookRepository.searchByTitle(query);
  }
}
```

**Layer 2 - Controller**：
```dart
class BookSearchController extends ChangeNotifier {
  final SearchBookUseCase searchBookUseCase;
  Future<void> onSearch(String query) async {
    final result = await searchBookUseCase.execute(query);
    // 更新 UI 狀態
  }
}
```

**Layer 1 - UI**：
```dart
class BookSearchPage extends StatelessWidget {
  final BookSearchController controller;
  Widget build(BuildContext context) {
    return ListView.builder(
      itemCount: controller.searchResults.length,
      itemBuilder: (_, i) => ListTile(title: Text(controller.searchResults[i].title)),
    );
  }
}
```

---

## 案例 2：重構現有程式碼

### 問題：所有邏輯都在 Widget 中

```dart
// ❌ 違規：Widget 包含業務邏輯和 Repository 呼叫
class _BookListPageState extends State<BookListPage> {
  Future<void> _loadBooks() async {
    final response = await http.get(...);  // ❌ 直接呼叫 API
    books = books.where((b) => b.publishYear >= 2020).toList();  // ❌ 業務邏輯
  }
}
```

### 重構 Ticket 拆分

| Ticket | 動作 | 層級 |
|--------|------|------|
| R1 | 提取 Book Entity | Layer 5 |
| R2 | 定義 IBookRepository | Layer 4 |
| R3 | 提取 LoadBooksUseCase | Layer 3 |
| R4 | 提取 BookListController | Layer 2 |
| R5 | 精簡 BookListPage | Layer 1 |

---

## 案例 3：架構遷移（Interface-First）

### 五階段遷移策略

| 階段 | 動作 | 風險 |
|-----|------|------|
| 階段 1 | 定義新介面（Layer 4）| 低 |
| 階段 2 | 實作新介面（Infrastructure）| 低 |
| 階段 3 | 建立適配器 | 中 |
| 階段 4 | 逐步替換呼叫端 | 中 |
| 階段 5 | 移除舊程式碼 | 低 |

### 關鍵原則

- **先定義介面，後實作**
- **適配器模式過渡**
- **逐步替換，不要一次全換**
- **每階段可獨立測試**

---

## 檢查清單

### 新功能開發
- [ ] 從 Layer 5 開始定義 Domain
- [ ] 每層有對應的測試
- [ ] 從外而內實作時使用 Mock

### 重構
- [ ] 識別所有違規點
- [ ] 按層級拆分 Ticket
- [ ] 每個 Ticket 獨立驗證

### 架構遷移
- [ ] Interface-First 策略
- [ ] 適配器過渡期
- [ ] 舊程式碼完全移除

---

## Reference

- [層級隔離派工方法論](./layered-ticket-methodology.md) - 完整方法論
- [層級檢查機制](./layered-architecture-quality-checking.md) - 品質檢查
- [快速開始指南](./layered-ticket-quick-start.md) - 角色快速入門
