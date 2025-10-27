# 層級隔離派工方法論

**版本**: v1.0.0
**建立日期**: 2025-10-11
**最後更新**: 2025-10-11
**適用範圍**: 所有遵循 Clean Architecture 的專案
**語言**: 繁體中文

---

## 📋 文件資訊

**目的**: 定義 Clean Architecture 五層劃分標準和單層修改原則，指導 Ticket 拆分和實作順序

**適用對象**:
- 專案經理（PM）- 規劃和拆分 Ticket
- 開發人員 - 執行單層修改
- 架構師 - 設計和審查架構
- Code Reviewer - 檢查層級隔離原則

**關鍵概念**:
- Clean Architecture 五層架構
- 單層修改原則
- 從外而內實作順序
- Ticket 粒度標準

---

## 第一章：方法論概述

### 1.1 為什麼需要層級隔離

**問題背景**:

在軟體開發中，我們常常遇到以下問題：
- ❌ Ticket 範圍過大，一個 Ticket 修改多個架構層級
- ❌ 變更影響範圍不可控，修改 UI 卻影響 Domain 邏輯
- ❌ 測試困難，需要啟動整個系統才能測試單一功能
- ❌ Code Review 複雜，審查者需要理解所有層級

**根本原因**:
- 缺乏明確的層級劃分標準
- 缺乏單層修改的判斷標準
- 缺乏實作順序的指引

**層級隔離解決的問題**:
1. **降低變更風險**: 單層修改確保影響範圍最小化
2. **提升測試獨立性**: 每層可以獨立測試，不需要啟動整個系統
3. **加速開發循環**: 從外而內實作，快速驗證需求
4. **提升 Code Review 效率**: 審查者只需要關注單一層級

### 1.2 核心原則

本方法論基於以下核心原則：

**原則 1: 五層架構明確劃分**
```text
Layer 1: UI/Presentation         (視覺呈現)
Layer 2: Application/Behavior    (事件處理)
Layer 3: UseCase                 (業務流程)
Layer 4: Domain Events/Interfaces (介面契約)
Layer 5: Domain Implementation   (核心業務邏輯)
```

**原則 2: 單層修改**
> 一個 Ticket 只應該修改單一架構層級的程式碼，變更的原因單一且明確。

**原則 3: 從外而內實作**
> 實作順序為 Layer 1 → Layer 2 → Layer 3 → Layer 4 → Layer 5，影響範圍遞增。

**原則 4: 依賴倒置**
> 外層依賴內層的抽象介面，內層不依賴外層，所有依賴通過介面。

### 1.3 適用場景

**適用場景** ✅:
- 新功能開發（從零開始設計）
- 現有功能修改（優化或調整）
- 重構（改善程式品質）
- 架構遷移（從舊架構遷移到新架構）

**不適用場景** ❌:
- 緊急 Hotfix（可能需要快速跨層修改）
- 原型開發（需要快速驗證概念）
- 一次性腳本（不需要架構設計）

**特殊場景** ⚠️:
- 架構遷移 → 使用 Interface-First 策略
- 安全性修復 → 使用從內而外策略
- 第三方套件升級 → 視情況調整順序

### 1.4 與現有方法論的關係

**與 Clean Architecture 實作方法論的關係**:
- **Clean Architecture 實作方法論**: 定義如何實作每一層的程式碼
- **層級隔離派工方法論**: 定義如何拆分 Ticket 和實作順序
- **關係**: 互補，層級隔離方法論是 Clean Architecture 的派工指南

**與 TDD 四階段流程的關係**:
- **Phase 1 (功能設計)**: 使用層級隔離方法論拆分 Ticket
- **Phase 2 (測試驗證)**: 驗證每層的測試獨立性
- **Phase 3 (實作執行)**: 遵循從外而內實作順序
- **Phase 4 (重構優化)**: 評估是否違反單層修改原則

**與 Ticket 設計方法論的關係**:
- **Ticket 設計方法論**: 定義 Ticket 的基本格式和內容
- **層級隔離派工方法論**: 定義 Ticket 的粒度和拆分標準
- **關係**: 層級隔離方法論是 Ticket 設計方法論的具體應用

### 1.5 文件章節導覽

**快速導航**：根據您的角色和需求，選擇適合的章節開始閱讀

| 章節 | 主題 | 適用對象 | 核心內容 | 預計閱讀時間 |
|------|------|---------|---------|------------|
| **第一章** | 方法論概述 | 所有人 | 為什麼需要層級隔離、核心原則 | 10 分鐘 |
| **第二章** | 五層架構定義 | PM、開發人員、架構師 | Layer 1-5 完整定義、決策樹 | 30 分鐘 |
| **第三章** | 單層修改原則 | PM、開發人員 | 原則定義、違規模式識別 | 15 分鐘 |
| **第四章** | 實作順序指引 | 開發人員、架構師 | 從外而內策略、特殊場景處理 | 20 分鐘 |
| **第五章** | Ticket 粒度標準 | PM | 量化指標、拆分指引、範例 | 25 分鐘 |
| **第六章** | 層級檢查機制 | Code Reviewer、開發人員 | 自動化檢查、違規模式 | 20 分鐘 |
| **第七章** | 實踐案例 | 所有人 | 3 個完整案例（新增、重構、遷移） | 40 分鐘 |
| **第八章** | 方法論整合 | PM、架構師 | 與 TDD、敏捷、Clean Architecture 整合 | 10 分鐘 |
| **第九章** | 常見問題 FAQ | 所有人 | 12 個 Q&A（理論、實務、團隊協作） | 30 分鐘 |
| **第十章** | 參考資料 | 所有人 | 文獻、工具、線上資源 | 10 分鐘 |

**閱讀建議**：
- **PM**: 建議閱讀[第一章](#第一章方法論概述)、[第二章](#第二章clean-architecture-五層定義)、[第五章](#第五章ticket-粒度標準)、[第九章](#第九章常見問題-faq)（核心：Ticket 拆分和粒度標準）
- **開發人員**: 建議閱讀[第一章](#第一章方法論概述)、[第二章](#第二章clean-architecture-五層定義)、[第三章](#第三章單層修改原則)、[第四章](#第四章實作順序指引從外而內)、[第六章](#第六章層級檢查機制)（核心：單層修改和實作順序）
- **架構師**: 建議閱讀[第一章](#第一章方法論概述)、[第二章](#第二章clean-architecture-五層定義)、[第四章](#第四章實作順序指引從外而內)、[第七章](#第七章實踐案例)、[第八章](#第八章與其他方法論的整合)（核心：架構設計和方法論整合）
- **Code Reviewer**: 建議閱讀[第一章](#第一章方法論概述)、[第二章](#第二章clean-architecture-五層定義)、[第三章](#第三章單層修改原則)、[第六章](#第六章層級檢查機制)（核心：層級檢查機制）
- **新手**: 建議按順序完整閱讀，預計 3-4 小時

### 1.6 快速開始指引（5 分鐘）

**根據您的角色，選擇對應的快速開始流程**

#### 🎯 PM 快速開始

**目標**：學會拆分符合層級隔離原則的 Ticket

**4 步快速上手**：
1. **理解五層架構** → 閱讀 [2.2 五層架構完整定義](#22-五層架構完整定義)
2. **使用決策樹** → 閱讀 [2.4 決策樹](#24-判斷程式碼屬於哪一層的決策樹)
3. **按層級拆分 Ticket** → 閱讀 [5.3 良好 Ticket 範例](#53-良好的-ticket-設計範例)
4. **檢查粒度標準** → 閱讀 [5.2 量化指標](#52-量化指標定義)

**快速檢查清單**：
- [ ] 每個 Ticket 只修改單一層級？
- [ ] 檔案數在 1-5 個之間？
- [ ] 預估工時在 2-8 小時？
- [ ] 有明確的驗收條件？

---

#### 👨‍💻 開發人員快速開始

**目標**：執行符合層級隔離原則的單層修改

**4 步快速上手**：
1. **確認 Ticket 層級定位** → 檢查 Ticket 標題是否標明 [Layer X]
2. **遵循單層修改原則** → 閱讀 [3.1 單層修改原則定義](#31-單層修改原則定義)
3. **遵循從外而內順序** → 閱讀 [4.1 從外而內實作](#41-為什麼從外而內實作)
4. **確保測試通過** → 閱讀 [6.4 測試範圍分析](#64-測試範圍分析法)

**開發前檢查清單**：
- [ ] 確認此 Ticket 只修改單一層級？
- [ ] 確認依賴的內層介面已存在？
- [ ] 準備好 Mock 或 Stub（如果內層未完成）？
- [ ] 測試檔案路徑對應層級結構？

**開發後檢查清單**：
- [ ] 所有測試 100% 通過？
- [ ] 沒有跨層直接呼叫？
- [ ] 依賴方向正確（外層依賴內層）？

---

#### 🔍 Code Reviewer 快速開始

**目標**：快速檢查 PR 是否符合層級隔離原則

**3 步快速檢查**：
1. **檢查單層修改原則** → 使用 [6.2 檔案路徑分析法](#62-檔案路徑分析法)
2. **檢查測試覆蓋率** → 使用 [6.4 測試範圍分析法](#64-測試範圍分析法)
3. **識別違規模式** → 參考 [6.5 違規模式識別](#65-違規模式識別)

**Code Review 快速檢查清單**：
- [ ] 此 PR 是否只修改單一層級？（看檔案路徑）
- [ ] 依賴方向是否正確？（看 import 語句）
- [ ] 測試檔案路徑是否對應層級？（看 test/ 路徑）
- [ ] 測試覆蓋率是否達到 100%？
- [ ] 是否有違規模式？（UI 包含業務邏輯、Controller 包含業務規則等）

**快速判斷技巧**：
- **5 秒檢查**：看檔案路徑，判斷是否跨層
- **10 秒檢查**：看 import 語句，判斷依賴方向
- **30 秒檢查**：看測試檔案，判斷測試範圍

---

#### 📚 完整學習路徑

**新手建議**（3-4 小時完整閱讀）：

**步驟 1：理解背景和原則**（30 分鐘）
  - [第一章：方法論概述](#第一章方法論概述)
  - [第二章：五層架構定義](#第二章clean-architecture-五層定義)

**步驟 2：掌握核心技能**（1 小時）
  - [第三章：單層修改原則](#第三章單層修改原則)
  - [第四章：實作順序指引](#第四章實作順序指引從外而內)
  - [第五章：Ticket 粒度標準](#第五章ticket-粒度標準)

**步驟 3：學習檢查和實踐**（1.5 小時）
  - [第六章：層級檢查機制](#第六章層級檢查機制)
  - [第七章：實踐案例](#第七章實踐案例)

**步驟 4：深入整合和 FAQ**（1 小時）
  - [第八章：與其他方法論的整合](#第八章與其他方法論的整合)
  - [第九章：常見問題 FAQ](#第九章常見問題-faq)
  - [第十章：參考資料](#第十章參考資料)

---

## 第二章：Clean Architecture 五層定義

### 2.1 為什麼需要五層而非傳統的三層或四層？

**傳統 Clean Architecture 四層問題**:
```text
傳統四層:
Layer 1: Entities
Layer 2: Use Cases
Layer 3: Interface Adapters (Controller + Presenter + Gateway)
Layer 4: Frameworks & Drivers (UI + DB + External)

問題：
- Interface Adapters 層混合了「行為邏輯」和「資料轉換」
- Frameworks & Drivers 層混合了「UI 渲染」和「基礎設施」
- 難以判斷「事件處理邏輯」應該放在哪一層
```

**五層架構優勢**:
```text
優化後的五層:
Layer 1: UI/Presentation (視覺元素)
Layer 2: Application/Behavior (UI 邏輯和事件處理)
Layer 3: UseCase (業務流程編排)
Layer 4: Domain Events/Interfaces (事件定義和介面契約)
Layer 5: Domain Implementation (核心業務邏輯)

優勢：
- 職責邊界更清晰，每層的變更原因單一
- 符合 Flutter 實務架構（Widget ↔ Controller ↔ UseCase ↔ Repository ↔ Entity）
- 便於 Ticket 粒度檢查（一個 Ticket 只修改一層）
- 避免「行為邏輯」和「視覺呈現」混淆
```

### 2.2 五層架構完整定義

#### Layer 1: UI/Presentation（視覺呈現層）

**職責範圍**:
- **視覺元素**: Widgets, Components, UI Layout
- **樣式定義**: Colors, TextStyles, Themes
- **UI 狀態管理**: UI-specific State (如展開/收合、選中狀態)

**不負責**:
- ❌ 事件處理邏輯（屬於 Layer 2）
- ❌ 業務流程呼叫（屬於 Layer 3）
- ❌ 資料驗證（屬於 Layer 4 或 Layer 5）

**Flutter 對應**:
- `Widget` 類別（StatefulWidget, StatelessWidget）
- `build()` 方法內的 UI 樹結構
- Theme 和 Style 定義

**判斷標準**:
- **變更原因**: 只因為「視覺設計變更」而修改
- **測試類型**: Widget 測試（驗證 UI 渲染）
- **依賴方向**: 依賴 Layer 2 的 Controller 或 ViewModel

**範例**:
```dart
// ✅ Layer 1: 純粹的視覺呈現，不包含業務邏輯
class BookDetailPage extends StatelessWidget {
  final BookDetailController controller;

  const BookDetailPage({required this.controller});

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: Text('書籍詳情')),
      body: Column(
        children: [
          // 純粹的 UI 元素
          Text(controller.bookTitle),
          ElevatedButton(
            // 只呼叫 Controller 方法，不包含邏輯
            onPressed: controller.onAddToFavorite,
            child: Text('加入收藏'),
          ),
        ],
      ),
    );
  }
}
```

---

#### Layer 2: Application/Behavior（應用行為層）

**職責範圍**:
- **事件處理**: 處理 UI 事件（點擊、輸入、手勢）
- **UI 邏輯**: 控制 UI 狀態轉換、顯示/隱藏元素
- **輸入驗證**: 表單驗證、格式檢查（UI 層級）
- **UseCase 協調**: 呼叫 UseCase 並處理結果
- **資料轉換**: 將 Domain Entity 轉換為 UI 可顯示的 ViewModel

**不負責**:
- ❌ UI 渲染（屬於 Layer 1）
- ❌ 業務流程編排（屬於 Layer 3）
- ❌ 核心業務規則（屬於 Layer 5）

**Flutter 對應**:
- `Controller` 類別（如 `BookDetailController`）
- `ViewModel` 類別
- `Bloc` / `Cubit` 的事件處理部分
- `Presenter` 類別

**判斷標準**:
- **變更原因**: 因為「互動流程變更」或「事件處理邏輯變更」而修改
- **測試類型**: 行為測試（驗證事件觸發和狀態變更）
- **依賴方向**: 依賴 Layer 3 的 UseCase

**範例 1: 基本事件處理**:
```dart
// ✅ Layer 2: 處理 UI 事件，協調 UseCase
class BookDetailController {
  final AddBookToFavoriteUseCase addToFavoriteUseCase;

  BookDetailController({required this.addToFavoriteUseCase});

  String bookTitle = '';
  bool isLoading = false;

  // 事件處理邏輯
  Future<void> onAddToFavorite() async {
    isLoading = true;
    notifyListeners();

    // 呼叫 UseCase
    final result = await addToFavoriteUseCase.execute(bookId);

    // 處理結果並更新 UI 狀態
    isLoading = false;
    if (result.isSuccess) {
      showSuccessMessage('已加入收藏');
    } else {
      showErrorMessage(result.error);
    }
    notifyListeners();
  }
}
```

**範例 2: Presenter 資料轉換** (修正 #1):
```dart
// ✅ Layer 2: Presenter 負責資料轉換
class BookDetailController {
  final GetBookDetailUseCase getBookDetailUseCase;

  // ViewModel 用於 UI 顯示
  BookViewModel? bookViewModel;

  Future<void> loadBookDetail(String bookId) async {
    final result = await getBookDetailUseCase.execute(bookId);

    if (result.isSuccess) {
      // Layer 2 負責轉換 Domain Entity → ViewModel
      bookViewModel = BookPresenter.toViewModel(result.data);
      notifyListeners();
    }
  }
}

// Presenter 類別
class BookPresenter {
  static BookViewModel toViewModel(Book book) {
    return BookViewModel(
      title: book.title.value,
      author: book.author.name,
      publishYear: book.publicationDate.year.toString(),
      isNew: book.isNewRelease(), // 呼叫 Domain 方法
    );
  }
}

// ViewModel 定義
class BookViewModel {
  final String title;
  final String author;
  final String publishYear;
  final bool isNew;

  BookViewModel({
    required this.title,
    required this.author,
    required this.publishYear,
    required this.isNew,
  });
}
```

**範例 3: 錯誤處理轉換** (修正 #2):
```dart
// ✅ Layer 2: 捕捉 Domain 錯誤並轉換為 UI 可理解的格式
class BookSearchController {
  Future<void> searchBook(String isbn) async {
    try {
      final book = await searchBookUseCase.execute(isbn);
      bookViewModel = BookPresenter.toViewModel(book);
    } on BookNotFoundException catch (e) {
      // 轉換為 ErrorViewModel
      errorViewModel = ErrorViewModel(
        title: '找不到書籍',
        message: '查無 ISBN: ${e.isbn} 的書籍資料',
        errorCode: 'BOOK_NOT_FOUND',
        actionText: '重新搜尋',
      );
    } on NetworkException catch (e) {
      errorViewModel = ErrorViewModel(
        title: '網路錯誤',
        message: '請檢查網路連線',
        errorCode: 'NETWORK_ERROR',
        actionText: '重試',
      );
    }
    notifyListeners();
  }
}
```

**Presenter/DTO 轉換職責判斷**:
- 如果轉換目的是為了 UI 顯示 → Layer 2
- 如果轉換是業務流程的一部分（跨 Domain 資料整合）→ Layer 3

**錯誤處理的三階段流程** (修正 #2):

**Layer 5 (Domain) - 拋出錯誤**:
```dart
// Domain 拋出具體的業務錯誤
class BookService {
  Book getBookByIsbn(String isbn) {
    if (!_repository.exists(isbn)) {
      throw BookNotFoundException(
        isbn: isbn,
        message: 'Book with ISBN $isbn not found',
      );
    }
    return _repository.findByIsbn(isbn);
  }
}
```

**Layer 2 (Behavior) - 轉換錯誤**: （見上方範例 3）

**Layer 1 (UI) - 顯示錯誤**:
```dart
// Widget 只負責顯示錯誤訊息
class BookSearchPage extends StatelessWidget {
  Widget build(BuildContext context) {
    if (controller.errorViewModel != null) {
      return ErrorDialog(
        title: controller.errorViewModel!.title,
        message: controller.errorViewModel!.message,
        actionText: controller.errorViewModel!.actionText,
        onAction: controller.retry,
      );
    }
    // ... 正常 UI
  }
}
```

---

#### Layer 3: UseCase（業務流程層）

**職責範圍**:
- **業務流程編排**: 協調多個 Domain Services 或 Repository
- **資料整合**: 跨 Domain 的資料整合和轉換
- **錯誤處理**: 統一處理業務錯誤和異常
- **事件發布**: 發布 Domain Events

**不負責**:
- ❌ UI 邏輯（屬於 Layer 2）
- ❌ 核心業務規則（屬於 Layer 5）
- ❌ 資料持久化細節（屬於 Infrastructure）

**Flutter 對應**:
- `UseCase` 類別（如 `AddBookToFavoriteUseCase`）
- `execute()` 方法（執行業務流程）

**判斷標準**:
- **變更原因**: 因為「業務流程變更」或「編排邏輯變更」而修改
- **測試類型**: UseCase 測試（驗證業務流程正確性）
- **依賴方向**: 依賴 Layer 4 的介面（Repository Interface, Event Interface）

**範例**:
```dart
// ✅ Layer 3: 業務流程編排
class AddBookToFavoriteUseCase {
  final IBookRepository bookRepository;
  final IFavoriteRepository favoriteRepository;
  final IEventBus eventBus;

  AddBookToFavoriteUseCase({
    required this.bookRepository,
    required this.favoriteRepository,
    required this.eventBus,
  });

  Future<OperationResult<void>> execute(String bookId) async {
    try {
      // 1. 檢查書籍是否存在（協調多個 Repository）
      final bookResult = await bookRepository.findById(bookId);
      if (!bookResult.isSuccess) {
        return OperationResult.failure('書籍不存在');
      }

      // 2. 檢查是否已收藏
      final isFavorited = await favoriteRepository.contains(bookId);
      if (isFavorited) {
        return OperationResult.failure('已加入收藏');
      }

      // 3. 執行收藏操作
      await favoriteRepository.add(bookId);

      // 4. 發布事件
      eventBus.publish(BookFavoritedEvent(bookId: bookId));

      return OperationResult.success(null);
    } catch (e) {
      return OperationResult.failure('操作失敗: $e');
    }
  }
}
```

---

#### Layer 4: Domain Events/Interfaces（領域事件與介面層）

**職責範圍**:
- **事件定義**: 定義 Domain Events 的結構和語意
- **介面契約**: 定義 Repository, Service 的抽象介面
- **DTO 定義**: 定義跨層傳輸的資料結構
- **協議規範**: 定義外部系統整合的協議

**不負責**:
- ❌ 介面實作（屬於 Infrastructure）
- ❌ 事件處理邏輯（屬於 Layer 3 或 Layer 5）
- ❌ 核心業務規則（屬於 Layer 5）

**Flutter 對應**:
- `abstract class` 定義的介面（如 `IBookRepository`）
- `Event` 類別（如 `BookFavoritedEvent`）
- `DTO` 類別（如 `BookDto`）

**判斷標準**:
- **變更原因**: 因為「契約定義變更」或「事件結構變更」而修改
- **測試類型**: 介面測試（驗證契約完整性）
- **依賴方向**: 被 Layer 3 依賴，不依賴任何層級

**範例**:
```dart
// ✅ Layer 4: 介面契約定義
abstract class IBookRepository {
  Future<OperationResult<Book>> findById(String id);
  Future<OperationResult<void>> save(Book book);
  Future<OperationResult<void>> delete(String id);
}

// ✅ Layer 4: 事件定義
class BookFavoritedEvent {
  final String bookId;
  final DateTime timestamp;

  BookFavoritedEvent({
    required this.bookId,
    DateTime? timestamp,
  }) : timestamp = timestamp ?? DateTime.now();
}
```

---

#### Layer 5: Domain Implementation（領域實作層）

**職責範圍**:

- **核心業務邏輯**: Entities, Aggregates, Value Objects
- **業務規則**: Business Invariants, Domain Validations
- **Domain Services**: 複雜業務邏輯的封裝
- **業務計算**: 業務相關的計算和推導

**不負責**:

- ❌ 資料持久化（屬於 Infrastructure）
- ❌ UI 邏輯（屬於 Layer 2）
- ❌ 流程編排（屬於 Layer 3）

**Flutter 對應**:

- `Entity` 類別（如 `Book`, `Favorite`）
- `Value Object` 類別（如 `ISBN`, `Title`）
- `Domain Service` 類別

**判斷標準**:

- **變更原因**: 因為「核心業務規則變更」而修改
- **測試類型**: Domain 測試（驗證業務規則正確性）
- **依賴方向**: 不依賴任何層級（最內層）

**範例**:
```dart
// ✅ Layer 5: 核心業務邏輯
class Book {
  final ISBN isbn;
  final Title title;
  final Author author;
  final PublicationDate publicationDate;

  Book({
    required this.isbn,
    required this.title,
    required this.author,
    required this.publicationDate,
  }) {
    _validate();
  }

  // 業務不變量驗證
  void _validate() {
    if (!isbn.isValid()) {
      throw ValidationException('ISBN 格式無效');
    }
    if (title.isEmpty) {
      throw ValidationException('書名不可為空');
    }
  }

  // 業務規則：判斷是否為新書
  bool isNewRelease() {
    final now = DateTime.now();
    final monthsSincePublish = now.difference(publicationDate.value).inDays / 30;
    return monthsSincePublish <= 6;
  }
}
```

---

### 2.3 層級間依賴關係和依賴方向

**依賴方向規則**:
```text
Layer 1 (UI)
  ↓ 依賴
Layer 2 (Behavior)
  ↓ 依賴
Layer 3 (UseCase)
  ↓ 依賴
Layer 4 (Domain Events/Interfaces)
  ↑ 實作
Layer 5 (Domain Implementation)

關鍵規則：
1. 外層依賴內層，內層不依賴外層
2. Layer 4 是介面層，Layer 5 實作這些介面
3. Layer 3 只依賴 Layer 4 的抽象介面，不依賴 Layer 5 的具體實作
4. 所有依賴都通過介面（Dependency Inversion Principle）
```

**違反依賴方向的範例**:
```dart
// ❌ 錯誤：Layer 5 (Domain) 依賴 Layer 3 (UseCase)
class Book {
  final AddBookToFavoriteUseCase favoriteUseCase; // ❌ Domain 不應該依賴 UseCase

  Future<void> addToFavorite() async {
    await favoriteUseCase.execute(this.id);
  }
}

// ✅ 正確：Layer 5 (Domain) 發布事件，由 Layer 3 處理
class Book {
  void addToFavorite() {
    // Domain 只記錄狀態變更，不執行操作
    this.isFavorited = true;
  }
}
```

---

### 2.4 判斷「程式碼屬於哪一層」的決策樹

**完整決策樹**（包含 Infrastructure 層）(修正 #3):

```text
五層架構 + Infrastructure 層決策樹：

1. 這段程式碼是否「渲染 UI 元素」？
   - 渲染 Widget、Component
   - 定義 UI 佈局結構
   ├─ 是 → Layer 1 (UI/Presentation)
   └─ 否 → 繼續

2. 這段程式碼是否「處理 UI 事件」或「控制 UI 狀態」或「轉換資料給 UI 使用」？
   - 處理 UI 事件: 點擊、輸入、手勢
   - 控制 UI 狀態: Loading、Error、Success
   - 轉換資料: Domain Entity → ViewModel, Domain Exception → ErrorViewModel
   ├─ 是 → Layer 2 (Application/Behavior)
   └─ 否 → 繼續

3. 這段程式碼是否「協調多個 Domain Services」或「編排業務流程」？
   - 協調多個 Repository 或 Service
   - 編排業務流程步驟
   - 發布 Domain Events
   ├─ 是 → Layer 3 (UseCase)
   └─ 否 → 繼續

4. 這段程式碼是否「定義介面契約」或「定義事件結構」？
   - 定義 Repository Interface
   - 定義 Domain Event 結構
   - 定義 DTO 或 Value Object 介面
   ├─ 是 → Layer 4 (Domain Events/Interfaces)
   └─ 否 → 繼續

5. 這段程式碼是否「實作核心業務規則」或「定義業務實體」？
   - 定義 Entity 或 Aggregate
   - 實作業務規則驗證
   - 實作 Domain Service
   ├─ 是 → Layer 5 (Domain Implementation)
   └─ 否 → Infrastructure 層

Infrastructure 層（不在五層架構討論範圍內）:
- 資料持久化實作（SqliteBookRepository, SharedPreferencesCache）
- 第三方 API 整合（GoogleBooksApiClient, RestClient）
- 技術基礎設施（EventBusImpl, LoggerImpl, HttpClient）
- 框架特定實作（FlutterSecureStorage, SharedPreferences）
```

**Infrastructure 層說明** (修正 #3):

**為什麼 Infrastructure 層不納入層級隔離討論？**

1. **技術實作細節 vs 業務邏輯**:
   - Infrastructure 層處理技術實作（資料庫、網路、快取）
   - 五層架構專注於業務邏輯的層級劃分
   - 兩者的變更驅動因素不同

2. **變更模式差異**:
   - Infrastructure: 技術驅動（升級套件、效能優化）
   - 五層架構: 需求驅動（功能變更、業務規則調整）

3. **Ticket 設計模式**:
   - Infrastructure 層通常是獨立的技術任務
   - 例如：「升級 SQLite 到 v3.0」、「實作 Redis 快取」
   - 很少與業務邏輯層級混合修改

4. **測試策略差異**:
   - Infrastructure: 整合測試、效能測試
   - 五層架構: 單元測試、行為測試、Widget 測試

**Infrastructure 層的典型職責**:
- **資料持久化**: Repository 實作（SqliteBookRepository）
- **第三方整合**: API Client（GoogleBooksApiClient）
- **快取管理**: Cache 實作（BookCacheManager）
- **日誌記錄**: Logger 實作
- **EventBus 實作**: EventBusImpl

**Infrastructure 層 Ticket 範例**:
```markdown
### Ticket: 實作 SQLite Book Repository

**層級定位**: Infrastructure（技術實作）

**變更範圍**:
- 檔案: `lib/infrastructure/repositories/sqlite_book_repository.dart`
- 實作: IBookRepository 介面

**驗收條件**:
- [ ] 實作所有 Repository 介面方法
- [ ] 通過整合測試（實際資料庫操作）
- [ ] 效能符合標準（查詢 < 100ms）

**測試範圍**: 整合測試（真實資料庫）
```

---

## 第三章：單層修改原則

### 3.1 單層修改原則定義

**核心原則**:
> 一個 Ticket 只應該修改單一架構層級的程式碼，變更的原因單一且明確。

**正式定義**:
- **單層修改** = 所有程式碼變更都集中在同一個 Clean Architecture 層級
- **變更原因單一** = 符合 Single Responsibility Principle（SRP）
- **測試範圍限定** = 測試只驗證該層級的職責

**為什麼要單層修改**:
1. **降低變更風險**: 變更影響範圍最小化，減少破壞其他層級的可能性
2. **提升測試獨立性**: 每層都可以獨立測試，不需要啟動整個系統
3. **符合 SRP**: 每個 Ticket 只有一個修改的理由
4. **快速驗證循環**: 修改後可以立即驗證該層級的正確性
5. **便於 Code Review**: 審查者只需要關注單一層級的邏輯

### 3.2 理論依據

**Single Responsibility Principle (SRP)**:
- **定義**: 一個類別或模組應該只有一個修改的理由
- **應用**: 一個 Ticket 應該只有一個修改的理由（對應單一層級的職責）

**Dependency Inversion Principle (DIP)**:
- **定義**: 高層模組不應該依賴低層模組，兩者都應該依賴抽象
- **應用**: 修改內層時不影響外層，修改外層時不影響內層

**Separation of Concerns (SoC)**:
- **定義**: 不同的關注點應該分離到不同的模組
- **應用**: 視覺呈現（Layer 1）、事件處理（Layer 2）、業務流程（Layer 3）應該分離

### 3.3 單層修改判斷標準

**檢查清單**:
- [ ] 此 Ticket 的所有程式碼修改都在同一個架構層級？
- [ ] 變更的原因是否單一且明確（只因為該層級的職責變更）？
- [ ] 測試範圍是否限定在該層級（不需要啟動其他層級）？
- [ ] 是否可以獨立驗收而不依賴其他層級的完成？
- [ ] 修改該層級時，其他層級是否不需要同步修改？

**判斷流程**:
```text
步驟 1: 列出此 Ticket 涉及的所有檔案
步驟 2: 判斷每個檔案屬於哪一個層級
步驟 3: 檢查是否所有檔案都屬於同一層級
  ├─ 是 → 符合單層修改原則 ✅
  └─ 否 → 違反單層修改原則 ❌
步驟 4: 如果違反，分析是否可以拆分為多個 Ticket
  ├─ 可拆分 → 重新設計 Ticket
  └─ 不可拆分 → 檢查架構設計是否有問題
```

### 3.4 違反單層修改的常見模式

**模式 1: Shotgun Surgery（散彈槍手術）**
```text
問題：一個小變更需要同時修改多個層級
範例：新增一個欄位需要修改 UI、Controller、UseCase、Entity

原因：層級間耦合過緊，缺乏抽象介面
解決：引入 DTO 或 Adapter 層，隔離層級間的依賴
```

**模式 2: Feature Envy（功能嫉妒）**
```text
問題：一個層級過度依賴另一個層級的內部細節
範例：UI 層直接存取 Domain Entity 的內部欄位

原因：缺乏適當的資料轉換層
解決：引入 ViewModel 或 Presenter，轉換 Domain 資料為 UI 資料
```

**模式 3: Divergent Change（發散式變更）**
```text
問題：不同原因的變更都集中在同一層級的同一個類別
範例：BookController 同時負責列表顯示和詳情顯示

原因：違反 SRP，單一類別承擔多個職責
解決：拆分為 BookListController 和 BookDetailController
```

---

## 第四章：實作順序指引（從外而內）

### 4.1 為什麼從外而內實作？

**傳統思維（從內而外）**:
```text
設計思考：Domain → UseCase → UI
理由：先定義核心業務邏輯，再往外擴展

問題：
- 過早設計：內層設計可能過度工程化
- 需求偏差：實作到 UI 時才發現 Domain 設計不符需求
- 測試困難：內層完成前，外層無法測試
```

**優化思維（從外而內）**:
```text
實作順序：UI → Behavior → UseCase → Domain Events → Domain
理由：從最小影響範圍開始，逐步深入核心

優勢：
- 影響範圍遞增：先改 UI 影響最小，最後改 Domain 影響最大
- 需求驗證：及早發現需求偏差，調整成本低
- 快速迭代：每層完成後立即可以測試驗證
- 風險可控：發現問題時影響範圍最小
```

### 4.2 影響範圍遞增原則

**影響範圍分析**:
```text
Layer 1 (UI) 修改 → 影響範圍：視覺呈現
  風險：低（只影響畫面外觀）
  回滾成本：極低（重新渲染即可）

Layer 2 (Behavior) 修改 → 影響範圍：互動行為
  風險：中低（影響單一功能的互動流程）
  回滾成本：低（重新設定事件處理）

Layer 3 (UseCase) 修改 → 影響範圍：業務流程
  風險：中（影響業務邏輯編排）
  回滾成本：中（需重新測試業務流程）

Layer 4 (Domain Events) 修改 → 影響範圍：契約定義
  風險：中高（影響所有依賴此契約的模組）
  回滾成本：高（需同步修改所有依賴方）

Layer 5 (Domain) 修改 → 影響範圍：核心業務規則
  風險：高（影響整個系統的業務邏輯）
  回滾成本：極高（需重新設計和測試）
```

**實作策略**:
- **先實作影響小的層級**，快速驗證需求
- **再實作影響大的層級**，確保穩定性
- **每層完成後立即測試**，及早發現問題

### 4.3 每層的驗證時機和方法

**Layer 1 驗證**:
- **時機**: UI 實作完成後
- **方法**: Widget 測試（Golden Test, Screenshot Test）
- **驗證內容**: 視覺呈現、佈局、樣式
- **通過標準**: UI 符合設計稿，無視覺錯誤

**Layer 2 驗證**:
- **時機**: 事件處理邏輯實作完成後
- **方法**: 行為測試（模擬事件觸發）
- **驗證內容**: 事件處理、狀態變更、UseCase 呼叫
- **通過標準**: 事件正確觸發，狀態正確更新

**Layer 3 驗證**:
- **時機**: UseCase 編排邏輯實作完成後
- **方法**: UseCase 測試（Mock Repository）
- **驗證內容**: 業務流程、錯誤處理、事件發布
- **通過標準**: 業務流程正確執行，錯誤正確處理

**Layer 4 驗證**:
- **時機**: 介面契約定義完成後
- **方法**: 介面測試（驗證契約完整性）
- **驗證內容**: 介面簽名、事件結構、DTO 定義
- **通過標準**: 介面契約完整且明確

**Layer 5 驗證**:
- **時機**: Domain 邏輯實作完成後
- **方法**: Domain 測試（純單元測試）
- **驗證內容**: 業務規則、不變量、計算邏輯
- **通過標準**: 業務規則正確實作，不變量保持

### 4.4 特殊場景處理 (修正 #4)

**常規場景 vs 特殊場景識別**:

**常規場景**（適用從外而內）:
- ✅ 新增完整功能（如：書籍收藏）
- ✅ 修改現有功能（如：搜尋優化）
- ✅ 一般重構（如：拆分 Controller）

**特殊場景**（需要替代策略）:
- ⚠️ 架構遷移
- ⚠️ 安全性修復
- ⚠️ 緊急 Bug Fix（影響核心業務規則）
- ⚠️ 第三方套件升級（涉及介面變更）

---

**特殊場景 1: 架構遷移**

**問題描述**: 從三層架構遷移到五層架構，需要大範圍重構

**不適用從外而內的原因**:
- 需要先定義介面契約（Layer 4）再實作
- 外層修改依賴內層介面穩定
- 大爆炸式重構風險高

**替代策略: Interface-First**
```text
步驟 1: 定義 Layer 4 介面契約
  - 定義所有 Repository Interface
  - 定義所有 Domain Event 結構

步驟 2: 實作 Layer 5 Domain 邏輯
  - 提取現有業務規則到 Domain Entity
  - 實作 Domain Service

步驟 3: 實作 Layer 3 UseCase
  - 基於 Layer 4 介面編排業務流程
  - 使用 Mock Repository 進行開發

步驟 4: 調整 Layer 2 Behavior
  - 移除業務邏輯，改為呼叫 UseCase
  - 保持事件處理職責

步驟 5: 調整 Layer 1 UI
  - 移除直接依賴 Domain 的部分
  - 改為依賴 ViewModel
```

**風險控制**:
- 雙軌並行：新功能使用新架構，舊功能逐步遷移
- 漸進式重構：每週遷移 1-2 個模組
- 測試覆蓋率 100%：確保重構不破壞功能

---

**特殊場景 2: 安全性修復**

**問題描述**: 修復 Domain 層的安全漏洞（如：密碼加密不足）

**不適用從外而內的原因**:
- 安全問題必須從核心修復
- 外層調整是次要的（顯示邏輯）
- 業務規則正確性優先於 UI 變更

**替代策略: 從內而外（Core-First）**
```text
步驟 1: 修復 Layer 5 Domain 安全問題
  - 強化密碼加密演算法
  - 修正業務規則漏洞

步驟 2: 更新 Layer 4 介面契約
  - 如果介面簽名需要調整

步驟 3: 調整 Layer 3 UseCase
  - 更新呼叫方式以符合新介面

步驟 4: 調整 Layer 2 Behavior
  - 更新錯誤處理邏輯

步驟 5: 調整 Layer 1 UI
  - 更新錯誤訊息顯示（如果需要）
```

**Ticket 設計範例**:
```markdown
Ticket #1: [Layer 5] 修復密碼加密安全漏洞
Ticket #2: [Layer 4] 更新 UserRepository 介面
Ticket #3: [Layer 3] 調整 RegisterUserUseCase
Ticket #4: [Layer 2] 更新註冊錯誤處理
Ticket #5: [Layer 1] 更新註冊錯誤訊息
```

---

**特殊場景 3: 緊急 Bug Fix**

**場景判斷**:
- 如果 Bug 在 UI 層（渲染錯誤）→ 從外而內 ✅
- 如果 Bug 在 Domain 層（業務邏輯錯誤）→ 從內而外 ⚠️

**判斷標準**:
```text
檢查 Bug 的根因位於哪一層：
- Layer 1 Bug（UI 渲染）→ 只修 Layer 1
- Layer 2 Bug（事件處理）→ 只修 Layer 2
- Layer 5 Bug（業務規則）→ 從 Layer 5 開始修，向外調整
```

---

**特殊場景 4: 第三方套件升級**

**問題描述**: 升級套件導致介面簽名變更

**替代策略: 依賴位置決定順序**
```text
如果套件被 Infrastructure 層使用:
  → 從 Infrastructure 開始（技術驅動）

如果套件影響 Domain Interface:
  → Interface-First（先調整 Layer 4）
```

---

**特殊場景識別檢查清單**:
- [ ] 此任務是否涉及大範圍架構調整？ → 架構遷移
- [ ] 此任務是否修復核心業務規則？ → 安全性修復 / Bug Fix
- [ ] 此任務是否由技術升級驅動？ → 第三方套件升級
- [ ] 此任務是否需要先定義介面？ → Interface-First

### 4.5 風險控制策略

**策略 1: 介面先行（Interface-First）**
```text
實作內層前，先定義 Layer 4 的介面契約
優勢：
- 外層可以先使用 Mock 實作進行開發
- 內層實作時有明確的契約遵循
- 減少層級間的等待時間
```

**策略 2: 漸進式重構（Progressive Refactoring）**
```text
每層實作完成後，立即檢查是否需要重構
優勢：
- 問題及早發現，修正成本低
- 避免技術債務累積
- 保持程式碼品質
```

**策略 3: 逆向驗證（Backward Validation）**
```text
實作內層後，重新驗證外層是否仍然正確
優勢：
- 確保層級間的整合正確
- 及早發現介面不匹配問題
- 提升整體系統穩定性
```

---

## 第五章：Ticket 粒度標準

### 5.1 為什麼需要量化的粒度標準？

**問題背景**：
- ❌ Ticket 過大導致開發週期長，風險高
- ❌ Ticket 過小導致管理成本高，效率低
- ❌ 缺乏客觀判斷標準，依賴主觀經驗

**粒度標準的價值**：
- ✅ **可預測性**：依據標準快速估算工作量
- ✅ **風險控制**：限制 Ticket 影響範圍
- ✅ **品質保證**：確保測試覆蓋率和 Code Review 品質
- ✅ **敏捷節奏**：維持快速迭代和持續交付

### 5.2 量化指標定義

**核心指標**：

| 指標 | 標準值 | 容許範圍 | 說明 |
|------|--------|---------|------|
| **修改檔案數** | 1-3 個 | 最多 5 個 | 超過 5 個需拆分 |
| **程式碼行數** | 50-200 行 | 最多 300 行 | 包含測試程式碼 |
| **修改層級** | 1 層 | 最多 1 層 | 嚴格單層修改 |
| **測試檔案數** | 1-2 個 | 最多 3 個 | 對應修改檔案 |
| **開發時間** | 2-8 小時 | 最多 1 天 | 單人完成時間 |
| **測試覆蓋率** | 100% | 不容許低於 100% | 新增程式碼覆蓋率 |

**補充說明** (修正 #5)：

**修改檔案數邊界處理**：
```text
情境 1：剛好 5 個檔案
  判斷：檢查是否可拆分為更小的 Ticket
  行動：如果可拆分 → 拆分；如果職責單一且不可拆 → 保持

情境 2：6-7 個檔案
  判斷：超出標準，強制拆分
  行動：分析檔案依賴關係，拆分為 2 個 Ticket

情境 3：8+ 個檔案
  判斷：嚴重超標，架構設計可能有問題
  行動：重新評估架構設計，重新規劃 Ticket
```

**程式碼行數邊界處理**：
```text
情境 1：250-300 行
  判斷：接近上限，評估複雜度
  行動：如果是簡單重複邏輯 → 接受；如果是複雜邏輯 → 拆分

情境 2：300-400 行
  判斷：超出標準，需要拆分
  行動：識別可獨立的子功能，拆分為 2 個 Ticket

情境 3：400+ 行
  判斷：嚴重超標，職責不單一
  行動：重新設計，拆分為 3+ 個 Ticket
```

**開發時間邊界處理**：
```text
情境 1：6-8 小時
  判斷：接近上限，評估是否可並行
  行動：如果可獨立驗證 → 接受；如果依賴其他 Ticket → 拆分

情境 2：1-1.5 天
  判斷：超出標準，風險增加
  行動：拆分為 2 個半天 Ticket

情境 3：2+ 天
  判斷：嚴重超標，無法快速驗證
  行動：重新規劃，拆分為 4+ 個 Ticket
```

### 5.3 良好的 Ticket 設計範例

**範例組 1：UI 層 Ticket**

```markdown
### Ticket：[Layer 1] 實作書籍詳情頁 UI

**層級定位**：Layer 1 (UI/Presentation)

**功能描述**：
實作書籍詳情頁的視覺呈現，包含書名、作者、出版年份、封面圖、簡介等資訊。

**變更範圍**：
- 新增檔案：`lib/ui/pages/book_detail_page.dart` (約 80 行)
- 新增檔案：`lib/ui/widgets/book_cover_widget.dart` (約 40 行)

**依賴項目**：
- 依賴 BookDetailController (已存在)
- 依賴 Theme 定義 (已存在)

**驗收條件**：
- [ ] UI 符合設計稿
- [ ] 所有資訊正確顯示
- [ ] 響應式佈局正常
- [ ] 通過 Widget 測試

**測試範圍**：
- Widget 測試：`test/ui/pages/book_detail_page_test.dart`
- Golden Test：`test/golden/book_detail_page_golden_test.dart`

**預估工時**：4 小時
**粒度指標**：✅ 2 個檔案，120 行，1 層，4 小時
```

---

**範例組 2：Behavior 層 Ticket**

```markdown
### Ticket：[Layer 2] 實作書籍搜尋 Controller

**層級定位**：Layer 2 (Application/Behavior)

**功能描述**：
實作書籍搜尋的事件處理邏輯，包含輸入驗證、Loading 狀態管理、錯誤處理。

**變更範圍**：
- 新增檔案：`lib/application/controllers/book_search_controller.dart` (約 150 行)
- 新增檔案：`lib/application/viewmodels/book_search_viewmodel.dart` (約 50 行)

**依賴項目**：
- 依賴 SearchBookUseCase (需先完成 Layer 3 Ticket)
- 依賴 BookPresenter (已存在)

**驗收條件**：
- [ ] 輸入驗證正確
- [ ] Loading 狀態正確切換
- [ ] 錯誤訊息正確顯示
- [ ] 通過行為測試

**測試範圍**：
- 行為測試：`test/application/controllers/book_search_controller_test.dart`
- Mock UseCase 驗證呼叫邏輯

**預估工時**：6 小時
**粒度指標**：✅ 2 個檔案，200 行，1 層，6 小時
```

---

**範例組 3：UseCase 層 Ticket**

```markdown
### Ticket：[Layer 3] 實作書籍搜尋 UseCase

**層級定位**：Layer 3 (UseCase)

**功能描述**：
實作書籍搜尋的業務流程，協調 Repository 和 Cache，發布搜尋事件。

**變更範圍**：
- 新增檔案：`lib/usecases/search_book_usecase.dart` (約 100 行)

**依賴項目**：
- 依賴 IBookRepository (已存在於 Layer 4)
- 依賴 IEventBus (已存在於 Layer 4)

**驗收條件**：
- [ ] 搜尋邏輯正確
- [ ] 快取策略正確
- [ ] 事件正確發布
- [ ] 通過 UseCase 測試

**測試範圍**：
- UseCase 測試：`test/usecases/search_book_usecase_test.dart`
- Mock Repository 和 EventBus

**預估工時**：5 小時
**粒度指標**：✅ 1 個檔案，100 行，1 層，5 小時
```

### 5.4 不良的 Ticket 設計範例（反面教材）

**反面教材 1：跨層修改**

```markdown
### ❌ Ticket：實作書籍收藏功能

**問題分析**：
- 修改 4 個層級（UI, Behavior, UseCase, Domain）
- 違反單層修改原則
- 測試範圍過大，無法獨立驗證

**變更範圍**：
- lib/ui/pages/book_detail_page.dart (Layer 1)
- lib/application/controllers/book_detail_controller.dart (Layer 2)
- lib/usecases/add_book_to_favorite_usecase.dart (Layer 3)
- lib/domain/entities/favorite.dart (Layer 5)

**應該如何拆分**：
- Ticket 1：[Layer 5] 定義 Favorite Entity
- Ticket 2：[Layer 4] 定義 IFavoriteRepository
- Ticket 3：[Layer 3] 實作 AddBookToFavoriteUseCase
- Ticket 4：[Layer 2] 實作收藏按鈕事件處理
- Ticket 5：[Layer 1] 實作收藏按鈕 UI
```

---

**反面教材 2：職責不單一**

```markdown
### ❌ Ticket：優化書籍列表功能

**問題分析**：
- 包含多個不同的變更原因
- 混合了「效能優化」和「功能新增」
- 變更範圍過大，難以驗收

**變更範圍**：
- 新增分頁功能
- 新增排序功能
- 優化列表渲染效能
- 修復搜尋 Bug

**應該如何拆分**：
- Ticket 1：[Layer 3] 新增書籍列表分頁 UseCase
- Ticket 2：[Layer 2] 實作分頁控制邏輯
- Ticket 3：[Layer 3] 新增書籍排序 UseCase
- Ticket 4：[Layer 2] 實作排序控制邏輯
- Ticket 5：[Layer 1] 優化列表 Widget 渲染效能
- Ticket 6：[Layer 2] 修復搜尋輸入驗證 Bug
```

---

**反面教材 3：粒度過小**

```markdown
### ❌ Ticket：修改按鈕文字顏色

**問題分析**：
- 粒度過小，管理成本高於實作成本
- 應該合併為更大的 UI 調整 Ticket

**變更範圍**：
- lib/ui/pages/book_detail_page.dart (1 行)

**應該如何合併**：
- Ticket：[Layer 1] 調整書籍詳情頁 UI 樣式
  - 修改按鈕文字顏色
  - 調整間距
  - 更新字體大小
  - 優化佈局
```

### 5.5 Ticket 拆分指引

**拆分原則**：

1. **按架構層級拆分**：
   - 不同層級 = 不同 Ticket
   - 範例：UI Ticket, Behavior Ticket, UseCase Ticket

2. **按功能模組拆分**：
   - 不同功能 = 不同 Ticket
   - 範例：搜尋功能, 收藏功能, 分享功能

3. **按變更原因拆分**：
   - 不同原因 = 不同 Ticket
   - 範例：新增功能 vs Bug 修復 vs 效能優化

4. **按依賴關係拆分**：
   - 有明確先後順序 = 拆分為多個 Ticket
   - 範例：先實作 Domain → 再實作 UseCase → 再實作 UI

**拆分流程**：

```text
步驟 1：識別變更範圍
  - 列出所有需要修改的檔案
  - 判斷每個檔案屬於哪一層

步驟 2：檢查粒度指標
  - 檔案數 > 5？→ 需要拆分
  - 程式碼行數 > 300？→ 需要拆分
  - 跨多個層級？→ 需要拆分
  - 開發時間 > 1 天？→ 需要拆分

步驟 3：識別拆分維度
  - 按層級拆分（優先）
  - 按功能模組拆分
  - 按變更原因拆分

步驟 4：定義依賴關係
  - 確定 Ticket 執行順序
  - 標記依賴項目

步驟 5：驗證拆分結果
  - 每個 Ticket 職責單一？
  - 每個 Ticket 可獨立驗收？
  - 粒度指標符合標準？
```

**拆分範例**：

**原始需求**：實作書籍搜尋功能

**拆分結果**：
```markdown
Ticket 1：[Layer 5] 定義書籍 Entity 和驗證規則
Ticket 2：[Layer 4] 定義 IBookRepository 介面
Ticket 3：[Layer 3] 實作書籍搜尋 UseCase
Ticket 4：[Layer 2] 實作搜尋 Controller 和 ViewModel
Ticket 5：[Layer 1] 實作搜尋頁面 UI
Ticket 6：[Layer 1] 實作搜尋結果列表 Widget
```

### 5.6 粒度檢查清單

**開始實作前**：
- [ ] 此 Ticket 只修改單一架構層級？
- [ ] 修改檔案數量在 1-5 個之間？
- [ ] 程式碼行數預估在 50-300 行之間？
- [ ] 開發時間預估在 2-8 小時之間？
- [ ] 職責單一且明確？
- [ ] 可以獨立驗收？

**實作完成後**：
- [ ] 實際修改檔案數符合預估？
- [ ] 實際程式碼行數符合預估？
- [ ] 測試覆蓋率達到 100%？
- [ ] 所有測試通過？
- [ ] Code Review 可在 30 分鐘內完成？

**超出標準時的處理**：
```text
如果檔案數超過 5 個：
  → 分析是否可拆分為多個 Ticket
  → 如果不可拆分，評估架構設計是否合理

如果程式碼行數超過 300 行：
  → 檢查是否有重複邏輯可提取
  → 檢查是否職責過多需要拆分

如果開發時間超過 1 天：
  → 拆分為多個更小的 Ticket
  → 重新評估複雜度和依賴關係
```

---

## 第六章：層級檢查機制

### 6.1 為什麼需要層級檢查機制？

**問題背景**：
- 開發者可能無意間違反單層修改原則
- Code Review 時難以快速識別層級問題
- 缺乏自動化檢查工具

**層級檢查的價值**：
- ✅ **預防問題**：在 Commit 前發現層級違規
- ✅ **提升效率**：自動化檢查減少人工審查成本
- ✅ **保持品質**：確保架構原則被嚴格遵守
- ✅ **教育團隊**：檢查訊息幫助團隊理解架構

### 6.2 檔案路徑分析法

**原理**：根據檔案路徑判斷所屬層級

**路徑規範**：
```dart
lib/
├── ui/                    // Layer 1 (UI/Presentation)
│   ├── pages/
│   ├── widgets/
│   └── themes/
├── application/           // Layer 2 (Application/Behavior)
│   ├── controllers/
│   ├── viewmodels/
│   └── presenters/
├── usecases/             // Layer 3 (UseCase)
│   └── *.dart
├── domain/
│   ├── events/           // Layer 4 (Domain Events)
│   ├── interfaces/       // Layer 4 (Interfaces)
│   ├── entities/         // Layer 5 (Domain Implementation)
│   ├── value_objects/    // Layer 5
│   └── services/         // Layer 5
└── infrastructure/       // Infrastructure (不在五層討論範圍)
    ├── repositories/
    └── api/
```

**檢查腳本範例**：
```bash
#!/bin/bash

# 檢查 Commit 中的檔案是否跨層
check_single_layer_modification() {
  local files=$(git diff --cached --name-only)
  local layers=()

  for file in $files; do
    if [[ $file == lib/ui/* ]]; then
      layers+=("Layer1")
    elif [[ $file == lib/application/* ]]; then
      layers+=("Layer2")
    elif [[ $file == lib/usecases/* ]]; then
      layers+=("Layer3")
    elif [[ $file == lib/domain/events/* ]] || [[ $file == lib/domain/interfaces/* ]]; then
      layers+=("Layer4")
    elif [[ $file == lib/domain/* ]]; then
      layers+=("Layer5")
    fi
  done

  # 去重
  unique_layers=$(echo "${layers[@]}" | tr ' ' '\n' | sort -u | tr '\n' ' ')
  layer_count=$(echo "$unique_layers" | wc -w)

  if [ "$layer_count" -gt 1 ]; then
    echo "❌ 違反單層修改原則"
    echo "此 Commit 修改了 $layer_count 個層級：$unique_layers"
    echo "請將修改拆分為多個 Commit"
    exit 1
  fi

  echo "✅ 符合單層修改原則"
}
```

### 6.3 變更原因分析法

**原理**：檢查 Commit Message 和程式碼變更是否符合單一原因

**分析維度**：

1. **Commit Message 分析**：
   ```text
   良好範例：
   - "feat(ui): 新增書籍詳情頁 UI"
   - "fix(controller): 修復搜尋輸入驗證邏輯"
   - "refactor(usecase): 拆分書籍搜尋流程"

   不良範例：
   - "feat: 新增書籍搜尋功能"（過於籠統，可能跨層）
   - "fix: 修復多個問題"（變更原因不單一）
   - "update: 調整程式碼"（無法判斷變更原因）
   ```

2. **程式碼差異分析**：
   ```text
   檢查項目：
   - [ ] 新增的程式碼是否屬於同一層級？
   - [ ] 修改的程式碼是否因為相同原因？
   - [ ] 刪除的程式碼是否屬於同一層級？
   ```

### 6.4 測試範圍分析法

**原理**：測試檔案應該對應單一層級的修改

**檢查規則**：

1. **測試檔案路徑檢查**：
   ```dart
   test/
   ├── ui/           // 對應 Layer 1 修改
   ├── application/  // 對應 Layer 2 修改
   ├── usecases/     // 對應 Layer 3 修改
   └── domain/       // 對應 Layer 4/5 修改
   ```

2. **測試類型檢查**：
   ```text
   Layer 1 → Widget Test, Golden Test
   Layer 2 → 行為測試（模擬事件觸發）
   Layer 3 → UseCase Test（Mock Repository）
   Layer 4 → 介面測試（驗證契約）
   Layer 5 → Domain Test（純單元測試）
   ```

3. **測試覆蓋率檢查**：
   ```bash
   # 檢查新增程式碼的測試覆蓋率
   flutter test --coverage
   genhtml coverage/lcov.info -o coverage/html

   # 確保新增程式碼覆蓋率 100%
   ```

### 6.5 違規模式識別

**常見違規模式**：

**模式 1：UI 層包含業務邏輯**
```dart
// ❌ 違規：Widget 中包含業務邏輯
class BookListWidget extends StatelessWidget {
  @override
  Widget build(BuildContext context) {
    final books = _filterNewBooks(_getAllBooks());  // ❌ 業務邏輯
    return ListView.builder(...);
  }

  List<Book> _filterNewBooks(List<Book> books) {
    // ❌ 業務規則應該在 Domain 層
    return books.where((b) => b.publishYear >= DateTime.now().year).toList();
  }
}

// ✅ 正確：Widget 只負責渲染
class BookListWidget extends StatelessWidget {
  final BookListController controller;

  @override
  Widget build(BuildContext context) {
    final books = controller.filteredBooks;  // ✅ 由 Controller 提供資料
    return ListView.builder(...);
  }
}
```

---

**模式 2：Controller 包含業務規則**
```dart
// ❌ 違規：Controller 包含核心業務規則
class BookController {
  Future<void> addBook(Book book) async {
    // ❌ 業務規則應該在 Domain 層
    if (book.isbn.length != 13) {
      throw ValidationException('ISBN 必須為 13 碼');
    }

    await bookRepository.save(book);
  }
}

// ✅ 正確：Controller 只呼叫 UseCase
class BookController {
  final AddBookUseCase addBookUseCase;

  Future<void> addBook(Book book) async {
    final result = await addBookUseCase.execute(book);
    if (!result.isSuccess) {
      errorMessage = result.error;
    }
  }
}

// ✅ 業務規則在 Domain Entity
class Book {
  final ISBN isbn;

  Book({required this.isbn}) {
    _validate();
  }

  void _validate() {
    if (!isbn.isValid()) {
      throw ValidationException('ISBN 格式無效');
    }
  }
}
```

---

**模式 3：UseCase 直接依賴具體實作**
```dart
// ❌ 違規：UseCase 依賴具體實作
class SearchBookUseCase {
  final SqliteBookRepository repository;  // ❌ 具體實作

  SearchBookUseCase(this.repository);
}

// ✅ 正確：UseCase 依賴抽象介面
class SearchBookUseCase {
  final IBookRepository repository;  // ✅ 抽象介面

  SearchBookUseCase(this.repository);
}
```

### 6.6 自動化檢查工具整合

**Pre-commit Hook 範例**：
```bash
#!/bin/bash
# .git/hooks/pre-commit

echo "🔍 執行層級隔離檢查..."

# 1. 檢查單層修改原則
./scripts/check_single_layer_modification.sh || exit 1

# 2. 檢查測試覆蓋率
flutter test --coverage || exit 1
./scripts/check_coverage.sh || exit 1

# 3. 檢查 Commit Message 格式
./scripts/check_commit_message.sh || exit 1

echo "✅ 所有檢查通過"
```

**CI/CD 整合範例**：
```yaml
# .github/workflows/pr_check.yml
name: PR Architecture Check

on: [pull_request]

jobs:
  architecture_check:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v2

      - name: 檢查單層修改原則
        run: ./scripts/check_single_layer_in_pr.sh

      - name: 檢查測試覆蓋率
        run: |
          flutter test --coverage
          ./scripts/check_coverage.sh

      - name: 生成架構分析報告
        run: ./scripts/generate_architecture_report.sh
```

---

## 第七章：實踐案例

### 7.1 案例總覽

本章提供三個完整的實踐案例，展示如何在真實專案中應用層級隔離派工方法論。

**案例 1：新增書籍搜尋功能**（完整五層實作範例）
**案例 2：重構現有程式碼**（違反層級隔離的重構案例）
**案例 3：架構遷移案例** (修正 #6)（從舊架構遷移到五層架構）

---

### 7.2 案例 1：新增書籍搜尋功能（完整五層實作）

**需求描述**：
使用者可以在首頁輸入 ISBN 或書名，搜尋書籍，並顯示搜尋結果列表。

**Ticket 拆分結果**：

#### Ticket 1：[Layer 5] 定義 Book Entity 和 ISBN Value Object

**變更範圍**：
- 新增：`lib/domain/entities/book.dart`
- 新增：`lib/domain/value_objects/isbn.dart`

**實作重點**：
```dart
// lib/domain/value_objects/isbn.dart
class ISBN {
  final String value;

  ISBN(this.value) {
    if (!_isValid(value)) {
      throw ValidationException('ISBN 格式無效');
    }
  }

  bool _isValid(String isbn) {
    return isbn.length == 13 && RegExp(r'^\d{13}$').hasMatch(isbn);
  }

  bool isValid() => _isValid(value);
}

// lib/domain/entities/book.dart
class Book {
  final ISBN isbn;
  final Title title;
  final Author author;

  Book({
    required this.isbn,
    required this.title,
    required this.author,
  });
}
```

**測試範圍**：
```dart
// test/domain/value_objects/isbn_test.dart
test('ISBN 應該驗證格式', () {
  expect(() => ISBN('1234567890123'), returnsNormally);
  expect(() => ISBN('invalid'), throwsA(isA<ValidationException>()));
});
```

---

#### Ticket 2：[Layer 4] 定義 IBookRepository 介面

**變更範圍**：
- 新增：`lib/domain/interfaces/i_book_repository.dart`

**實作重點**：
```dart
// lib/domain/interfaces/i_book_repository.dart
abstract class IBookRepository {
  Future<OperationResult<List<Book>>> searchByIsbn(String isbn);
  Future<OperationResult<List<Book>>> searchByTitle(String title);
}
```

---

#### Ticket 3：[Layer 3] 實作 SearchBookUseCase

**變更範圍**：
- 新增：`lib/usecases/search_book_usecase.dart`

**實作重點**：
```dart
// lib/usecases/search_book_usecase.dart
class SearchBookUseCase {
  final IBookRepository bookRepository;
  final IEventBus eventBus;

  SearchBookUseCase({
    required this.bookRepository,
    required this.eventBus,
  });

  Future<OperationResult<List<Book>>> execute(String query) async {
    try {
      // 判斷查詢類型
      final isIsbn = ISBN.isValidFormat(query);

      final result = isIsbn
          ? await bookRepository.searchByIsbn(query)
          : await bookRepository.searchByTitle(query);

      if (result.isSuccess) {
        eventBus.publish(BookSearchedEvent(query: query, resultCount: result.data!.length));
      }

      return result;
    } catch (e) {
      return OperationResult.failure('搜尋失敗：$e');
    }
  }
}
```

**測試範圍**：
```dart
// test/usecases/search_book_usecase_test.dart
test('應該根據 ISBN 搜尋書籍', () async {
  when(mockRepository.searchByIsbn(any))
      .thenAnswer((_) async => OperationResult.success([mockBook]));

  final result = await useCase.execute('1234567890123');

  expect(result.isSuccess, true);
  verify(mockRepository.searchByIsbn('1234567890123')).called(1);
});
```

---

#### Ticket 4：[Layer 2] 實作 BookSearchController

**變更範圍**：
- 新增：`lib/application/controllers/book_search_controller.dart`
- 新增：`lib/application/viewmodels/book_search_viewmodel.dart`

**實作重點**：
```dart
// lib/application/controllers/book_search_controller.dart
class BookSearchController extends ChangeNotifier {
  final SearchBookUseCase searchBookUseCase;

  BookSearchController({required this.searchBookUseCase});

  bool isLoading = false;
  List<BookViewModel> searchResults = [];
  String? errorMessage;

  Future<void> onSearch(String query) async {
    if (query.isEmpty) {
      errorMessage = '請輸入搜尋關鍵字';
      notifyListeners();
      return;
    }

    isLoading = true;
    errorMessage = null;
    notifyListeners();

    final result = await searchBookUseCase.execute(query);

    isLoading = false;

    if (result.isSuccess) {
      searchResults = result.data!
          .map((book) => BookPresenter.toViewModel(book))
          .toList();
    } else {
      errorMessage = result.error;
    }

    notifyListeners();
  }
}
```

**測試範圍**：
```dart
// test/application/controllers/book_search_controller_test.dart
test('搜尋成功應該更新搜尋結果', () async {
  when(mockUseCase.execute(any))
      .thenAnswer((_) async => OperationResult.success([mockBook]));

  await controller.onSearch('test');

  expect(controller.searchResults.length, 1);
  expect(controller.isLoading, false);
  expect(controller.errorMessage, null);
});
```

---

#### Ticket 5：[Layer 1] 實作搜尋頁面 UI

**變更範圍**：
- 新增：`lib/ui/pages/book_search_page.dart`

**實作重點**：
```dart
// lib/ui/pages/book_search_page.dart
class BookSearchPage extends StatelessWidget {
  final BookSearchController controller;

  const BookSearchPage({required this.controller});

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: Text('書籍搜尋')),
      body: Column(
        children: [
          TextField(
            onSubmitted: controller.onSearch,
            decoration: InputDecoration(hintText: '輸入 ISBN 或書名'),
          ),
          if (controller.isLoading) CircularProgressIndicator(),
          if (controller.errorMessage != null) Text(controller.errorMessage!),
          Expanded(
            child: ListView.builder(
              itemCount: controller.searchResults.length,
              itemBuilder: (context, index) {
                final book = controller.searchResults[index];
                return ListTile(
                  title: Text(book.title),
                  subtitle: Text(book.author),
                );
              },
            ),
          ),
        ],
      ),
    );
  }
}
```

**測試範圍**：
```dart
// test/ui/pages/book_search_page_test.dart
testWidgets('應該顯示搜尋結果', (tester) async {
  controller.searchResults = [mockBookViewModel];

  await tester.pumpWidget(MaterialApp(home: BookSearchPage(controller: controller)));

  expect(find.text('測試書籍'), findsOneWidget);
});
```

---

### 7.3 案例 2：重構現有程式碼（違反層級隔離）

**問題場景**：
現有程式碼將業務邏輯混在 UI 層，需要重構為符合五層架構。

**原始程式碼（違規）**：
```dart
// ❌ 所有邏輯都在 Widget 中
class BookListPage extends StatefulWidget {
  @override
  _BookListPageState createState() => _BookListPageState();
}

class _BookListPageState extends State<BookListPage> {
  List<Book> books = [];
  bool isLoading = false;

  @override
  void initState() {
    super.initState();
    _loadBooks();
  }

  Future<void> _loadBooks() async {
    setState(() => isLoading = true);

    // ❌ 直接呼叫 Repository（應該透過 UseCase）
    final response = await http.get(Uri.parse('https://api.books.com/books'));
    final jsonData = jsonDecode(response.body);

    // ❌ 資料轉換邏輯（應該在 Presenter）
    books = (jsonData as List).map((json) => Book(
      isbn: ISBN(json['isbn']),
      title: Title(json['title']),
    )).toList();

    // ❌ 業務邏輯（應該在 Domain）
    books = books.where((b) => b.publishYear >= 2020).toList();

    setState(() => isLoading = false);
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      body: isLoading
          ? CircularProgressIndicator()
          : ListView.builder(
              itemCount: books.length,
              itemBuilder: (context, index) => ListTile(title: Text(books[index].title.value)),
            ),
    );
  }
}
```

**重構 Ticket 拆分**：

#### Ticket 1：[Layer 5] 定義 Book Entity 和業務規則

**變更範圍**：
- 新增：`lib/domain/entities/book.dart`

**實作重點**：
```dart
// lib/domain/entities/book.dart
class Book {
  final ISBN isbn;
  final Title title;
  final int publishYear;

  Book({
    required this.isbn,
    required this.title,
    required this.publishYear,
  });

  // ✅ 業務規則移到 Domain
  bool isNewRelease() {
    return publishYear >= DateTime.now().year - 1;
  }
}
```

---

#### Ticket 2：[Layer 4] 定義 IBookRepository 介面

**變更範圍**：
- 新增：`lib/domain/interfaces/i_book_repository.dart`

**實作重點**：
```dart
abstract class IBookRepository {
  Future<OperationResult<List<Book>>> getAllBooks();
}
```

---

#### Ticket 3：[Layer 3] 實作 GetAllBooksUseCase

**變更範圍**：
- 新增：`lib/usecases/get_all_books_usecase.dart`

**實作重點**：
```dart
class GetAllBooksUseCase {
  final IBookRepository repository;

  GetAllBooksUseCase({required this.repository});

  Future<OperationResult<List<Book>>> execute({bool onlyNewReleases = false}) async {
    final result = await repository.getAllBooks();

    if (result.isSuccess && onlyNewReleases) {
      // ✅ 業務邏輯使用 Domain 方法
      final filteredBooks = result.data!.where((b) => b.isNewRelease()).toList();
      return OperationResult.success(filteredBooks);
    }

    return result;
  }
}
```

---

#### Ticket 4：[Layer 2] 實作 BookListController

**變更範圍**：
- 新增：`lib/application/controllers/book_list_controller.dart`

**實作重點**：
```dart
class BookListController extends ChangeNotifier {
  final GetAllBooksUseCase getAllBooksUseCase;

  BookListController({required this.getAllBooksUseCase});

  List<BookViewModel> books = [];
  bool isLoading = false;

  Future<void> loadBooks({bool onlyNewReleases = false}) async {
    isLoading = true;
    notifyListeners();

    final result = await getAllBooksUseCase.execute(onlyNewReleases: onlyNewReleases);

    if (result.isSuccess) {
      // ✅ 使用 Presenter 轉換
      books = result.data!.map((book) => BookPresenter.toViewModel(book)).toList();
    }

    isLoading = false;
    notifyListeners();
  }
}
```

---

#### Ticket 5：[Layer 1] 重構 BookListPage UI

**變更範圍**：
- 修改：`lib/ui/pages/book_list_page.dart`

**實作重點**：
```dart
// ✅ Widget 只負責渲染
class BookListPage extends StatelessWidget {
  final BookListController controller;

  const BookListPage({required this.controller});

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      body: controller.isLoading
          ? CircularProgressIndicator()
          : ListView.builder(
              itemCount: controller.books.length,
              itemBuilder: (context, index) {
                final book = controller.books[index];
                return ListTile(title: Text(book.title));
              },
            ),
    );
  }
}
```

---

### 7.4 案例 3：架構遷移案例（從三層到五層） (修正 #6)

**遷移背景**：
專案原本使用簡單的 MVC 三層架構，現在需要遷移到五層 Clean Architecture。

**原始架構（三層）**：
```text
lib/
├── models/        // 混合了 Entity 和 ViewModel
├── controllers/   // 混合了 UI 邏輯和業務邏輯
└── views/         // UI 層
```

**目標架構（五層）**：
```text
lib/
├── ui/            // Layer 1
├── application/   // Layer 2
├── usecases/      // Layer 3
├── domain/        // Layer 4 + 5
└── infrastructure/
```

**遷移策略：Interface-First 五階段計畫** (修正 #6)：

#### 階段 1：定義 Layer 4 介面契約（不影響現有程式碼）

**目標**：建立新架構的介面骨架，與舊程式碼並存

**Ticket 範例**：
```markdown
### Ticket 1-1：[Layer 4] 定義所有 Repository 介面

**變更範圍**：
- 新增：`lib/domain/interfaces/i_book_repository.dart`
- 新增：`lib/domain/interfaces/i_favorite_repository.dart`
- 新增：`lib/domain/interfaces/i_event_bus.dart`

**特點**：
- 不修改任何現有程式碼
- 只定義介面，不實作
- 為後續遷移建立契約基礎
```

**實作重點**：
```dart
// lib/domain/interfaces/i_book_repository.dart
abstract class IBookRepository {
  Future<OperationResult<Book>> findById(String id);
  Future<OperationResult<List<Book>>> findAll();
  Future<OperationResult<void>> save(Book book);
}
```

---

#### 階段 2：提取 Domain Entity 和 Value Objects（漸進式遷移）

**目標**：將 `models/` 中的資料模型分離為 Domain Entity 和 ViewModel

**Ticket 範例**：
```markdown
### Ticket 2-1：[Layer 5] 提取 Book Entity

**變更範圍**：
- 新增：`lib/domain/entities/book.dart`
- 新增：`lib/domain/value_objects/isbn.dart`
- 保留：`lib/models/book_model.dart`（暫時保留）

**遷移策略**：
- 新建 Domain Entity，包含業務規則
- 舊的 Model 保留，添加 `toDomain()` 轉換方法
- 逐步將業務邏輯從 Controller 移到 Entity
```

**實作重點**：
```dart
// lib/domain/entities/book.dart (新)
class Book {
  final ISBN isbn;
  final Title title;

  Book({required this.isbn, required this.title}) {
    _validate();
  }

  void _validate() {
    if (!isbn.isValid()) throw ValidationException('ISBN 無效');
  }
}

// lib/models/book_model.dart (舊，暫時保留)
class BookModel {
  final String isbn;
  final String title;

  BookModel({required this.isbn, required this.title});

  // ✅ 添加轉換方法
  Book toDomain() {
    return Book(
      isbn: ISBN(isbn),
      title: Title(title),
    );
  }

  factory BookModel.fromDomain(Book book) {
    return BookModel(
      isbn: book.isbn.value,
      title: book.title.value,
    );
  }
}
```

---

#### 階段 3：實作 Layer 3 UseCase（新功能優先）

**目標**：新功能使用 UseCase，舊功能保持不變

**Ticket 範例**：
```markdown
### Ticket 3-1：[Layer 3] 實作 SearchBookUseCase（新功能）

**變更範圍**：
- 新增：`lib/usecases/search_book_usecase.dart`
- 使用 Mock Repository 開發（Infrastructure 尚未完成）

**遷移策略**：
- 新功能直接使用新架構
- 舊功能暫時保持舊邏輯
- 雙軌並行，逐步遷移
```

**實作重點**：
```dart
// lib/usecases/search_book_usecase.dart
class SearchBookUseCase {
  final IBookRepository repository;  // ✅ 依賴抽象介面

  SearchBookUseCase({required this.repository});

  Future<OperationResult<List<Book>>> execute(String query) async {
    return await repository.searchByTitle(query);
  }
}

// 開發階段使用 Mock
class MockBookRepository implements IBookRepository {
  @override
  Future<OperationResult<List<Book>>> searchByTitle(String query) async {
    // 返回測試資料
    return OperationResult.success([mockBook]);
  }
}
```

---

#### 階段 4：調整 Layer 2 Behavior（移除業務邏輯）

**目標**：將 Controller 的業務邏輯移到 UseCase

**Ticket 範例**：
```markdown
### Ticket 4-1：[Layer 2] 重構 BookController（移除業務邏輯）

**變更範圍**：
- 修改：`lib/controllers/book_controller.dart` → `lib/application/controllers/book_controller.dart`

**遷移策略**：
- 移除 Controller 中的業務邏輯
- 改為呼叫 UseCase
- 保持事件處理職責
```

**實作重點**：
```dart
// 舊 Controller（違規）
class BookController {
  Future<void> searchBook(String query) async {
    // ❌ 業務邏輯在 Controller
    if (query.length < 3) {
      errorMessage = '搜尋關鍵字至少 3 個字';
      return;
    }

    final response = await http.get(...);
    books = parseBooks(response.body);
  }
}

// 新 Controller（符合規範）
class BookController {
  final SearchBookUseCase searchBookUseCase;

  Future<void> searchBook(String query) async {
    // ✅ 只處理 UI 邏輯
    if (query.isEmpty) {
      errorMessage = '請輸入搜尋關鍵字';
      notifyListeners();
      return;
    }

    isLoading = true;
    notifyListeners();

    // ✅ 呼叫 UseCase
    final result = await searchBookUseCase.execute(query);

    isLoading = false;
    if (result.isSuccess) {
      books = result.data!.map((b) => BookPresenter.toViewModel(b)).toList();
    } else {
      errorMessage = result.error;
    }
    notifyListeners();
  }
}
```

---

#### 階段 5：調整 Layer 1 UI（移除直接依賴）

**目標**：UI 只依賴 Controller，不直接存取 Domain

**Ticket 範例**：
```markdown
### Ticket 5-1：[Layer 1] 重構 BookListPage（移除 Domain 依賴）

**變更範圍**：
- 修改：`lib/views/book_list_page.dart` → `lib/ui/pages/book_list_page.dart`

**遷移策略**：
- 移除 UI 對 Domain Entity 的直接依賴
- 改為使用 ViewModel
- 確保 UI 只渲染，不包含邏輯
```

**實作重點**：
```dart
// 舊 UI（違規）
class BookListPage extends StatelessWidget {
  Widget build(BuildContext context) {
    final books = controller.books;  // ❌ 直接使用 Domain Entity
    return ListView.builder(
      itemBuilder: (context, index) {
        final book = books[index];
        return ListTile(
          title: Text(book.title.value),  // ❌ 直接存取 Value Object
          subtitle: Text(book.isbn.value),
        );
      },
    );
  }
}

// 新 UI（符合規範）
class BookListPage extends StatelessWidget {
  Widget build(BuildContext context) {
    final books = controller.bookViewModels;  // ✅ 使用 ViewModel
    return ListView.builder(
      itemBuilder: (context, index) {
        final book = books[index];
        return ListTile(
          title: Text(book.title),  // ✅ 直接存取 String
          subtitle: Text(book.isbn),
        );
      },
    );
  }
}
```

---

**遷移進度管理**：

```markdown
## 架構遷移進度追蹤

### 階段 1：介面定義（完成度：100%）
- [x] IBookRepository 介面
- [x] IFavoriteRepository 介面
- [x] IEventBus 介面

### 階段 2：Domain 提取（完成度：60%）
- [x] Book Entity
- [x] Favorite Entity
- [ ] Reading Entity（進行中）
- [ ] Review Entity（待開始）

### 階段 3：UseCase 實作（完成度：40%）
- [x] SearchBookUseCase（新功能）
- [x] AddBookToFavoriteUseCase（新功能）
- [ ] GetBookDetailUseCase（待遷移）
- [ ] UpdateReadingProgressUseCase（待遷移）

### 階段 4：Controller 重構（完成度：20%）
- [x] BookSearchController（已重構）
- [ ] BookListController（進行中）
- [ ] FavoriteController（待開始）

### 階段 5：UI 調整（完成度：10%）
- [x] BookSearchPage（已遷移）
- [ ] BookListPage（待遷移）
- [ ] BookDetailPage（待遷移）
```

**風險控制措施**：

1. **雙軌並行**：
   - 新功能使用新架構
   - 舊功能保持運作
   - 逐步遷移，不大爆炸重構

2. **測試覆蓋率 100%**：
   - 每個遷移 Ticket 都包含完整測試
   - 確保重構不破壞功能

3. **每週遷移 1-2 個模組**：
   - 控制遷移節奏
   - 降低風險

4. **建立 Adapter 層**：
   - 舊程式碼呼叫新程式碼時，使用 Adapter 轉換
   - 新程式碼呼叫舊程式碼時，使用 Adapter 隔離

**遷移完成標準**：
- [ ] 所有 Controller 都移除業務邏輯
- [ ] 所有 UI 都使用 ViewModel
- [ ] 所有業務邏輯都在 Domain 或 UseCase
- [ ] 刪除舊的 `models/` 和 `controllers/` 目錄
- [ ] 測試覆蓋率維持 100%
- [ ] 所有功能正常運作

---

## 第八章：與其他方法論的整合

### 8.1 與 Clean Architecture 實作方法論的關係

**Clean Architecture 實作方法論**：
- **職責**：定義如何實作每一層的程式碼
- **內容**：依賴倒置、介面設計、模組邊界

**層級隔離派工方法論**：
- **職責**：定義如何拆分 Ticket 和實作順序
- **內容**：單層修改、從外而內、粒度標準

**整合方式**：
- Clean Architecture 定義「如何寫程式」
- 層級隔離派工定義「如何拆任務」
- 兩者互補，共同確保架構品質

**實務應用**：
```markdown
### Ticket：[Layer 3] 實作書籍搜尋 UseCase

**架構遵循**：
- 遵循 Clean Architecture：依賴 IBookRepository 抽象介面 ✅
- 遵循層級隔離：只修改 Layer 3，不修改其他層級 ✅

**程式碼範例**：
class SearchBookUseCase {
  final IBookRepository repository;  // ✅ 依賴抽象（Clean Architecture）

  // ✅ 單一職責：只負責搜尋業務流程（層級隔離）
  Future<OperationResult<List<Book>>> execute(String query) async {
    return await repository.searchByTitle(query);
  }
}
```

---

### 8.2 與 TDD 四階段流程的關係

**TDD 四階段流程**：
1. **Phase 1（功能設計）**：設計功能規格和介面
2. **Phase 2（測試驗證）**：撰寫測試，定義驗收標準
3. **Phase 3（實作執行）**：實作程式碼，通過測試
4. **Phase 4（重構優化）**：評估程式碼品質，執行重構

**層級隔離派工在 TDD 中的角色**：

**Phase 1 使用層級隔離**：
- 設計時使用決策樹判斷程式碼屬於哪一層
- 使用粒度標準拆分 Ticket
- 定義每個 Ticket 的層級定位

**Phase 2 驗證層級隔離**：
- 測試只驗證單一層級的職責
- 測試檔案路徑對應層級結構
- 測試覆蓋率檢查層級完整性

**Phase 3 實作符合層級隔離**：
- 遵循從外而內實作順序
- 每個 Ticket 只修改單一層級
- 修改完成後立即驗證

**Phase 4 評估層級隔離違規**：
- 檢查是否違反單層修改原則
- 檢查是否混合多層職責
- 重構時保持層級隔離

**整合範例**：

```markdown
## TDD 四階段 + 層級隔離

### Phase 1：功能設計
**任務**：設計書籍搜尋功能

**使用層級隔離方法論**：
- 使用決策樹拆分為 5 個層級的 Ticket
- 定義每個 Ticket 的粒度標準
- 確定從外而內實作順序

**產出**：
- Ticket 1：[Layer 5] 定義 Book Entity
- Ticket 2：[Layer 4] 定義 IBookRepository
- Ticket 3：[Layer 3] 實作 SearchBookUseCase
- Ticket 4：[Layer 2] 實作 SearchController
- Ticket 5：[Layer 1] 實作搜尋 UI

---

### Phase 2：測試驗證
**任務**：為每個 Ticket 撰寫測試

**使用層級隔離方法論**：
- 每層使用對應的測試類型
- 測試檔案路徑對應層級結構

**產出**：
- test/domain/entities/book_test.dart（Layer 5 測試）
- test/usecases/search_book_usecase_test.dart（Layer 3 測試）
- test/application/controllers/search_controller_test.dart（Layer 2 測試）
- test/ui/pages/search_page_test.dart（Layer 1 測試）

---

### Phase 3：實作執行
**任務**：實作程式碼並通過測試

**使用層級隔離方法論**：
- 遵循從外而內實作順序
- 每個 Ticket 實作完成後立即驗證

**執行順序**：
1. 實作 Layer 5（Domain）
2. 實作 Layer 4（Interface）
3. 實作 Layer 3（UseCase）
4. 實作 Layer 2（Behavior）
5. 實作 Layer 1（UI）

---

### Phase 4：重構優化
**任務**：評估程式碼品質，執行重構

**使用層級隔離方法論**：
- 檢查是否違反單層修改原則
- 檢查層級職責是否混淆

**檢查項目**：
- [ ] 每個檔案都屬於單一層級？
- [ ] 沒有跨層直接呼叫？
- [ ] 依賴方向正確（外層依賴內層）？
- [ ] 測試範圍符合層級定位？
```

---

### 8.3 與 Ticket 設計方法論的關係

**Ticket 設計方法論**：
- 定義 Ticket 的基本格式（標題、描述、驗收條件）
- 定義 Ticket 的寫作規範

**層級隔離派工方法論**：
- 定義 Ticket 的粒度標準（檔案數、行數、時間）
- 定義 Ticket 的拆分原則（按層級拆分）

**整合方式**：

**Ticket 模板整合**：
```markdown
### Ticket：[Layer X] {功能名稱}

**層級定位**：Layer X ({層級名稱})  ← 來自層級隔離派工

**功能描述**：  ← 來自 Ticket 設計方法論
{詳細功能描述}

**變更範圍**：  ← 來自層級隔離派工（粒度檢查）
- 新增檔案：lib/{layer}/{module}/{file}.dart (約 XX 行)

**依賴項目**：  ← 來自 Ticket 設計方法論
- 依賴 XXX (已存在)

**驗收條件**：  ← 來自 Ticket 設計方法論
- [ ] 功能正確實作
- [ ] 通過測試
- [ ] 符合層級隔離原則  ← 來自層級隔離派工

**測試範圍**：  ← 來自層級隔離派工（層級對應）
- test/{layer}/{file}_test.dart

**預估工時**：XX 小時  ← 來自層級隔離派工（粒度標準）
**粒度指標**：X 個檔案，XX 行，1 層，XX 小時  ← 來自層級隔離派工
```

---

### 8.4 與敏捷開發的整合

**Sprint 規劃**：
- 使用層級隔離派工拆分 Ticket
- 每個 Ticket 獨立驗收，符合敏捷快速迭代

**Daily Standup**：
- 每個 Ticket 只修改單一層級，易於溝通進度
- 問題定位清晰（屬於哪一層？）

**Code Review**：
- 單層修改降低 Review 複雜度
- 審查者只需關注單一層級的邏輯

**持續整合**：
- 每個 Ticket 完成後立即測試
- 測試獨立，不依賴其他層級

**整合範例**：

```markdown
## Sprint 1 規劃

**Sprint 目標**：實作書籍搜尋功能

**使用層級隔離派工方法論**：
- 拆分為 5 個 Ticket，每個 Ticket 對應單一層級
- 每個 Ticket 預估 4-6 小時
- 從外而內實作，快速驗證需求

**Sprint Backlog**：
| Ticket | 層級 | 預估工時 | 負責人 | 狀態 |
|--------|------|---------|--------|------|
| #1 | Layer 5 | 4h | Alice | ✅ Done |
| #2 | Layer 4 | 3h | Bob | ✅ Done |
| #3 | Layer 3 | 5h | Alice | 🔄 In Progress |
| #4 | Layer 2 | 6h | Carol | ⏳ To Do |
| #5 | Layer 1 | 4h | Bob | ⏳ To Do |

**Daily Standup**：
- Alice：「昨天完成 Layer 5 Book Entity，今天實作 Layer 3 SearchUseCase」
- Bob：「昨天完成 Layer 4 IBookRepository 介面，今天等待 Layer 3 完成」
- Carol：「等待 Layer 3 完成後開始 Layer 2 Controller」
```

---

## 第九章：常見問題 FAQ

### 9.1 方法論理解問題

**Q1：為什麼一定要單層修改？多層一起改不是更快嗎？**

A1：
- **短期看起來快**：一次改完所有層級，感覺省時間
- **長期風險高**：
  - 測試困難（需要啟動整個系統）
  - Code Review 複雜（審查者需要理解所有層級）
  - 問題定位困難（出錯時不知道是哪一層的問題）
  - 回滾困難（無法只回滾某一層）

**實例比較**：
```markdown
## 跨層修改（風險高）
Ticket：實作書籍搜尋功能
- 修改 Layer 1, 2, 3, 5（4 個層級）
- 測試需要啟動整個系統
- Code Review 需要 1 小時
- 出錯時無法判斷是哪一層的問題

## 單層修改（風險低）
Ticket 1：[Layer 5] 定義 Book Entity
Ticket 2：[Layer 3] 實作 SearchUseCase
Ticket 3：[Layer 2] 實作 SearchController
Ticket 4：[Layer 1] 實作搜尋 UI
- 每個 Ticket 獨立測試
- Code Review 每個只需 15 分鐘
- 問題定位清晰
```

---

**Q2：Infrastructure 層應該如何處理？**

A2：
- **Infrastructure 層不在五層架構討論範圍**
- **原因**：技術實作細節 vs 業務邏輯
- **Ticket 設計**：Infrastructure 層通常是獨立的技術任務

**實例**：
```markdown
### Ticket：[Infrastructure] 實作 SQLite Book Repository

**層級定位**：Infrastructure（技術實作）

**變更範圍**：
- 新增：lib/infrastructure/repositories/sqlite_book_repository.dart

**依賴項目**：
- 實作 IBookRepository 介面（Layer 4）

**測試範圍**：
- 整合測試（實際資料庫操作）
```

---

**Q3：決策樹無法判斷時怎麼辦？**

A3：
- **步驟 1**：重新檢視程式碼的職責
- **步驟 2**：問自己「這段程式碼的變更原因是什麼？」
  - 視覺變更 → Layer 1
  - 互動變更 → Layer 2
  - 業務流程變更 → Layer 3
  - 契約變更 → Layer 4
  - 業務規則變更 → Layer 5
- **步驟 3**：如果仍無法判斷，可能是職責不單一，需要拆分

---

### 9.2 實務操作問題

**Q4：Ticket 粒度太小，管理成本高怎麼辦？**

A4：
- **檢查是否過度拆分**：
  - 修改 1 行程式碼 = 粒度過小
  - 應該合併為更大的 Ticket
- **合併原則**：
  - 同一層級的小修改可以合併
  - 變更原因相同可以合併
- **範例**：
  ```markdown
  ❌ Ticket 1：修改按鈕顏色（1 行）
  ❌ Ticket 2：調整間距（2 行）

  ✅ Ticket：調整書籍詳情頁 UI 樣式
  - 修改按鈕顏色
  - 調整間距
  - 更新字體大小
  ```

---

**Q5：粒度標準超出容許範圍時怎麼辦？**

A5：
- **檔案數超過 5 個**：強制拆分為多個 Ticket
- **程式碼行數超過 300 行**：檢查是否有重複邏輯可提取
- **開發時間超過 1 天**：重新評估複雜度，拆分為更小的 Ticket

**處理流程**：
```text
步驟 1：分析超出原因
  - 職責過多？→ 拆分為多個 Ticket
  - 程式碼重複？→ 提取共用邏輯
  - 依賴複雜？→ 重新設計架構

步驟 2：重新規劃 Ticket
  - 按功能模組拆分
  - 按依賴關係拆分

步驟 3：驗證拆分結果
  - 每個 Ticket 符合粒度標準？
  - 每個 Ticket 可獨立驗收？
```

---

**Q6：從外而內實作，內層還沒完成怎麼測試？**

A6：
- **使用 Mock 或 Stub**：
  - 外層開發時，使用 Mock 實作內層介面
  - 內層完成後，替換為真實實作
- **範例**：
  ```dart
  // Layer 2 開發時，Layer 3 尚未完成

  // 使用 Mock UseCase
  class MockSearchBookUseCase implements SearchBookUseCase {
    @override
    Future<OperationResult<List<Book>>> execute(String query) async {
      // 返回測試資料
      return OperationResult.success([mockBook]);
    }
  }

  // Layer 2 測試
  test('搜尋成功應該更新結果', () async {
    final mockUseCase = MockSearchBookUseCase();
    final controller = BookSearchController(searchBookUseCase: mockUseCase);

    await controller.onSearch('test');

    expect(controller.searchResults.length, 1);
  });
  ```

---

### 9.3 團隊協作問題 (修正 #7)

**Q7：團隊成員對五層架構理解不一致怎麼辦？**

A7：
- **建立團隊共識**：
  1. 組織架構培訓（1-2 小時）
  2. Code Review 時加強溝通
  3. 建立架構決策文件（ADR）
  4. 定期架構回顧會議

- **實務做法**：
  ```markdown
  ## 團隊架構培訓計畫

  ### Week 1：理論培訓
  - 五層架構定義
  - 單層修改原則
  - 決策樹使用

  ### Week 2：實作練習
  - Pair Programming
  - 共同設計 Ticket
  - Code Review 互相學習

  ### Week 3：獨立開發
  - 每人負責不同層級的 Ticket
  - 每日 Standup 討論遇到的問題

  ### Week 4：回顧改進
  - 檢視違規案例
  - 更新團隊規範
  - 建立最佳實踐文件
  ```

---

**Q8：不同開發者對「層級定位」有爭議怎麼辦？**

A8：
- **使用決策樹客觀判斷**：
  - 不依賴主觀意見
  - 按照決策樹步驟逐一檢查

- **建立爭議解決機制**：
  1. **初步討論**：團隊內部討論 15 分鐘
  2. **決策樹判斷**：使用決策樹客觀分析
  3. **架構師裁決**：如仍有爭議，由架構師裁決
  4. **記錄決策**：寫入 ADR（Architecture Decision Record）

- **範例**：
  ```markdown
  ## ADR-001：資料轉換邏輯的層級定位

  **問題**：BookPresenter.toViewModel() 應該放在哪一層？

  **爭議點**：
  - 意見 A：放在 Layer 3（因為是資料轉換）
  - 意見 B：放在 Layer 2（因為是給 UI 使用）

  **決策樹判斷**：
  - 步驟 2：這段程式碼是否「轉換資料給 UI 使用」？
    - 是 → Layer 2

  **最終決定**：
  - BookPresenter.toViewModel() 屬於 Layer 2
  - 原因：轉換目的是為了 UI 顯示

  **執行標準**：
  - 所有 Presenter 都放在 `lib/application/presenters/`
  - 測試放在 `test/application/presenters/`
  ```

---

**Q9：團隊規模大，如何協調多人開發同一功能？**

A9：
- **按層級分工**：
  - 不同層級可以並行開發
  - 使用 Mock 介面隔離依賴

- **分工範例**：
  ```markdown
  ## 功能：書籍搜尋（團隊分工）

  ### Alice 負責 Domain 層（Layer 4 + 5）
  - Ticket 1：[Layer 5] 定義 Book Entity
  - Ticket 2：[Layer 4] 定義 IBookRepository
  - 預估：1 天

  ### Bob 負責 UseCase 層（Layer 3）
  - Ticket 3：[Layer 3] 實作 SearchBookUseCase
  - 依賴：等待 Alice 完成 Layer 4 介面
  - 開發策略：先用 Mock Repository 開發
  - 預估：1 天

  ### Carol 負責 Application 層（Layer 2）
  - Ticket 4：[Layer 2] 實作 SearchController
  - 依賴：等待 Bob 完成 Layer 3
  - 開發策略：先用 Mock UseCase 開發
  - 預估：1 天

  ### David 負責 UI 層（Layer 1）
  - Ticket 5：[Layer 1] 實作搜尋頁面 UI
  - 依賴：等待 Carol 完成 Layer 2
  - 開發策略：先用 Mock Controller 開發
  - 預估：1 天

  ### 協作時間線
  Day 1：Alice, Bob, Carol, David 同時開始（使用 Mock）
  Day 2：Alice 完成 → Bob 整合真實介面
  Day 3：Bob 完成 → Carol 整合真實 UseCase
  Day 4：Carol 完成 → David 整合真實 Controller
  Day 5：整合測試，功能完成
  ```

---

**Q10：Code Review 時如何快速檢查層級隔離原則？**

A10：
- **建立 Code Review Checklist**：
  ```markdown
  ## 層級隔離 Code Review Checklist

  ### 1. 單層修改檢查
  - [ ] 此 PR 是否只修改單一層級？
  - [ ] 如果跨層，是否有合理原因？（如架構遷移）

  ### 2. 依賴方向檢查
  - [ ] 外層是否依賴內層的抽象介面？
  - [ ] 內層是否沒有依賴外層？

  ### 3. 職責單一性檢查
  - [ ] 每個檔案是否只有單一職責？
  - [ ] UI 層是否沒有業務邏輯？
  - [ ] Controller 是否沒有核心業務規則？

  ### 4. 測試範圍檢查
  - [ ] 測試檔案路徑是否對應層級結構？
  - [ ] 測試類型是否符合層級定位？
  - [ ] 測試覆蓋率是否達到 100%？

  ### 5. Commit Message 檢查
  - [ ] Commit Message 是否標明層級（如 feat(layer2)）？
  - [ ] 變更原因是否單一且明確？
  ```

- **快速檢查技巧**：
  1. **看檔案路徑**：5 秒判斷是否跨層
  2. **看 import 語句**：檢查依賴方向
  3. **看測試檔案**：驗證測試範圍

---

**Q11：新成員加入，如何快速上手層級隔離派工？**

A11：
- **階段式培訓計畫**：

  **Week 1：理論學習（4 小時）**
  - 閱讀本文件（2 小時）
  - 觀看架構培訓影片（1 小時）
  - 完成決策樹練習（1 小時）

  **Week 2：實戰演練（Pair Programming）**
  - 與資深成員 Pair Programming（3 天）
  - 觀察 Ticket 拆分過程
  - 參與 Code Review

  **Week 3：獨立開發（有監督）**
  - 獨立負責單一層級的 Ticket
  - 每日與 Mentor 討論進度
  - Code Review 由 Mentor 仔細審查

  **Week 4：完全獨立**
  - 獨立設計 Ticket
  - 獨立開發和測試
  - 參與團隊 Code Review

- **學習資源清單**：
  ```markdown
  ## 層級隔離派工學習資源

  ### 必讀文件
  1. 本文件：層級隔離派工方法論
  2. Clean Architecture 實作方法論
  3. TDD 四階段流程文件

  ### 參考範例
  1. 案例 1：新增書籍搜尋功能（完整五層實作）
  2. 案例 2：重構現有程式碼（違規案例分析）
  3. 案例 3：架構遷移（五階段遷移計畫）

  ### 練習題
  1. 決策樹練習：判斷 10 段程式碼的層級定位
  2. Ticket 拆分練習：將完整功能拆分為單層 Ticket
  3. Code Review 練習：識別違規模式

  ### Mentor 指定
  - Mentor：{資深成員名稱}
  - 聯絡方式：{Slack/Email}
  - 每週一對一：30 分鐘
  ```

---

**Q12：如何衡量團隊的層級隔離執行品質？**

A12：
- **量化指標**：

  | 指標 | 計算方式 | 目標值 |
  |------|---------|--------|
  | **單層修改率** | 單層 Ticket 數 / 總 Ticket 數 | ≥ 90% |
  | **Ticket 粒度合規率** | 符合粒度標準的 Ticket 數 / 總數 | ≥ 85% |
  | **測試覆蓋率** | 新增程式碼測試覆蓋率 | 100% |
  | **Code Review 時間** | 平均每個 PR 的 Review 時間 | ≤ 30 分鐘 |
  | **架構違規數** | 每週發現的架構違規次數 | ≤ 2 次 |

- **定期檢視**：
  ```markdown
  ## 每月架構品質檢視會議

  ### 議程
  1. 回顧本月量化指標（15 分鐘）
  2. 分析違規案例（20 分鐘）
  3. 討論改進措施（15 分鐘）
  4. 更新團隊規範（10 分鐘）

  ### 產出
  - 架構品質月報
  - 違規案例分析文件
  - 改進行動計畫
  ```

---

## 第十章：參考資料

### 10.1 核心參考文獻

**Clean Architecture 相關**：
1. **Clean Architecture** - Robert C. Martin
   - 核心理論：依賴倒置、層級隔離、介面抽象
   - 本方法論的理論基礎

2. **Implementing Clean Architecture**
   - 實務指引：如何在真實專案中實作 Clean Architecture
   - 提供具體範例和最佳實踐

**軟體設計原則**：
3. **SOLID Principles**
   - Single Responsibility Principle（SRP）
   - Open/Closed Principle（OCP）
   - Liskov Substitution Principle（LSP）
   - Interface Segregation Principle（ISP）
   - Dependency Inversion Principle（DIP）

4. **Domain-Driven Design** - Eric Evans
   - Entity, Value Object, Aggregate 設計
   - 領域模型驅動設計

**敏捷與 TDD**：
5. **Test-Driven Development** - Kent Beck
   - TDD 實踐方法
   - 測試先行開發

6. **Agile Software Development** - Robert C. Martin
   - 敏捷開發原則
   - 快速迭代與持續交付

### 10.2 專案特定文件

**本專案方法論文件**：
1. **Clean Architecture 實作方法論**
   - 路徑：`.claude/methodologies/clean-architecture-implementation.md`
   - 內容：五層架構實作細節

2. **TDD 四階段流程**
   - 路徑：`.claude/tdd-collaboration-flow.md`
   - 內容：Phase 1-4 詳細流程

3. **Ticket 設計方法論**
   - 路徑：`.claude/methodologies/ticket-design-methodology.md`
   - 內容：Ticket 寫作規範

4. **5W1H 自覺決策方法論**
   - 路徑：`.claude/methodologies/5w1h-self-awareness-methodology.md`
   - 內容：決策框架和逃避行為檢測

5. **敏捷重構方法論**
   - 路徑：`.claude/methodologies/agile-refactor-methodology.md`
   - 內容：代理人分工協作模式

### 10.3 工具與腳本

**層級檢查工具**：

#### 1. 檔案路徑分析腳本

**用途**：檢查 Commit 是否跨層

**腳本位置**：`scripts/check_single_layer_modification.sh`

```bash
#!/bin/bash
# scripts/check_single_layer_modification.sh
# 檢查 Git Commit 是否符合單層修改原則

set -e

# 獲取修改的檔案列表
files=$(git diff --name-only HEAD~1)

# 定義層級關聯陣列
declare -A layers

# 分析每個檔案的層級
for file in $files; do
    if [[ $file == lib/presentation/pages/* ]] || [[ $file == lib/presentation/widgets/* ]]; then
        layers["Layer1"]=1
    elif [[ $file == lib/presentation/controllers/* ]] || [[ $file == lib/presentation/presenters/* ]]; then
        layers["Layer2"]=1
    elif [[ $file == lib/application/use_cases/* ]]; then
        layers["Layer3"]=1
    elif [[ $file == lib/domain/events/* ]] || [[ $file == lib/domain/interfaces/* ]]; then
        layers["Layer4"]=1
    elif [[ $file == lib/domain/entities/* ]] || [[ $file == lib/domain/services/* ]]; then
        layers["Layer5"]=1
    elif [[ $file == lib/infrastructure/* ]]; then
        layers["Infrastructure"]=1
    fi
done

# 檢查層級數量
layer_count=${#layers[@]}

if [[ $layer_count -eq 0 ]]; then
    echo "⚠️  無法判斷層級（可能是非程式碼檔案）"
    exit 0
elif [[ $layer_count -eq 1 ]]; then
    echo "✅ 符合單層修改原則"
    echo "📍 修改層級: ${!layers[@]}"
    exit 0
else
    echo "❌ 違反單層修改原則"
    echo "📍 涉及層級: ${!layers[@]}"
    echo ""
    echo "建議："
    echo "1. 將此 Commit 拆分為多個單層 Commit"
    echo "2. 每個 Commit 只修改單一層級"
    exit 1
fi
```

**使用方式**：
```bash
# 在 Git Hook 中執行
./scripts/check_single_layer_modification.sh

# 或在 CI/CD 中執行
bash scripts/check_single_layer_modification.sh
```

---

#### 2. 測試覆蓋率檢查腳本

**用途**：確保新增程式碼 100% 測試覆蓋率

**腳本位置**：`scripts/check_coverage.sh`

```bash
#!/bin/bash
# scripts/check_coverage.sh
# 檢查測試覆蓋率是否達到 100%

set -e

# 執行測試並生成覆蓋率報告
flutter test --coverage

# 檢查 lcov.info 是否存在
if [[ ! -f coverage/lcov.info ]]; then
    echo "❌ 找不到覆蓋率報告: coverage/lcov.info"
    exit 1
fi

# 使用 lcov 分析覆蓋率
lcov --summary coverage/lcov.info > coverage_summary.txt 2>&1

# 提取覆蓋率百分比
coverage=$(grep "lines" coverage_summary.txt | awk '{print $2}' | sed 's/%//')

echo "📊 當前測試覆蓋率: ${coverage}%"

# 檢查是否達到 100%
if (( $(echo "$coverage >= 100.0" | bc -l) )); then
    echo "✅ 測試覆蓋率達標（100%）"
    exit 0
elif (( $(echo "$coverage >= 95.0" | bc -l) )); then
    echo "⚠️  測試覆蓋率接近達標（${coverage}%），建議補充測試"
    exit 0
else
    echo "❌ 測試覆蓋率未達標（${coverage}% < 100%）"
    echo ""
    echo "建議："
    echo "1. 使用 genhtml 生成詳細報告：genhtml coverage/lcov.info -o coverage/html"
    echo "2. 開啟 coverage/html/index.html 查看未覆蓋的程式碼"
    echo "3. 補充缺失的測試案例"
    exit 1
fi
```

**使用方式**：
```bash
# 手動執行
./scripts/check_coverage.sh

# 在 CI/CD 中執行
bash scripts/check_coverage.sh
```

---

#### 3. Commit Message 驗證腳本

**用途**：驗證 Commit Message 是否符合層級隔離規範格式

**腳本位置**：`scripts/check_commit_message.sh`

```bash
#!/bin/bash
# scripts/check_commit_message.sh
# 驗證 Commit Message 是否符合層級隔離規範

set -e

# 讀取 Commit Message
commit_msg_file=$1
commit_msg=$(cat "$commit_msg_file")

# 定義合法的 Commit Message 格式
# 格式：[Layer X] <type>: <description>
# 範例：[Layer 1] feat: 新增書籍詳情頁面

layer_pattern='^\[Layer [1-5]\]'
infra_pattern='^\[Infrastructure\]'
type_pattern='(feat|fix|refactor|test|docs|style|chore):'

# 檢查是否符合層級格式
if [[ $commit_msg =~ $layer_pattern ]] || [[ $commit_msg =~ $infra_pattern ]]; then
    # 檢查類型格式
    if [[ $commit_msg =~ $type_pattern ]]; then
        echo "✅ Commit Message 格式正確"
        echo "📋 訊息內容: $commit_msg"
        exit 0
    else
        echo "❌ Commit Message 缺少類型標記"
        echo "📋 當前訊息: $commit_msg"
        echo ""
        echo "建議格式："
        echo "  [Layer X] <type>: <description>"
        echo ""
        echo "合法類型："
        echo "  - feat: 新功能"
        echo "  - fix: 修復"
        echo "  - refactor: 重構"
        echo "  - test: 測試"
        echo "  - docs: 文件"
        echo "  - style: 格式"
        echo "  - chore: 雜項"
        exit 1
    fi
else
    echo "❌ Commit Message 缺少層級標記"
    echo "📋 當前訊息: $commit_msg"
    echo ""
    echo "建議格式："
    echo "  [Layer 1] feat: UI 相關修改"
    echo "  [Layer 2] refactor: Controller 重構"
    echo "  [Layer 3] feat: 新增 UseCase"
    echo "  [Layer 4] feat: 定義新事件"
    echo "  [Layer 5] feat: Domain 邏輯實作"
    echo "  [Infrastructure] chore: 升級資料庫"
    exit 1
fi
```

**使用方式**：
```bash
# 在 Git Hook 中執行（commit-msg hook）
./scripts/check_commit_message.sh .git/COMMIT_EDITMSG

# 手動驗證
echo "[Layer 1] feat: 新增書籍詳情頁面" | ./scripts/check_commit_message.sh /dev/stdin
```

**CI/CD 整合**：
4. **GitHub Actions Workflow**
   - `.github/workflows/pr_check.yml`
   - PR 自動檢查層級隔離原則

5. **Pre-commit Hook**
   - `.git/hooks/pre-commit`
   - Commit 前自動檢查

### 10.4 延伸閱讀

**架構設計**：
1. **Hexagonal Architecture** - Alistair Cockburn
   - 六邊形架構
   - Ports and Adapters 模式

2. **Onion Architecture** - Jeffrey Palermo
   - 洋蔥架構
   - 層級隔離思想

**測試策略**：
3. **Growing Object-Oriented Software, Guided by Tests**
   - 測試驅動物件導向設計
   - Mock 和 Stub 使用

4. **The Art of Unit Testing** - Roy Osherove
   - 單元測試最佳實踐
   - 測試隔離技巧

**團隊協作**：
5. **Extreme Programming Explained** - Kent Beck
   - Pair Programming
   - 持續整合

6. **The Phoenix Project** - Gene Kim
   - DevOps 實踐
   - 持續交付流程

### 10.5 線上資源

**Clean Architecture 社群**：
1. **Clean Coders**
   - 網址：https://cleancoders.com
   - Robert C. Martin 的教學影片

2. **Flutter Clean Architecture Examples**
   - GitHub：flutter-clean-architecture-examples
   - 實際專案範例

**工具推薦**：
3. **PlantUML**
   - 架構圖繪製工具
   - 視覺化層級關係

4. **Dependency Cruiser**
   - 依賴關係分析工具
   - 檢測依賴方向違規

### 10.6 更新記錄

**v1.0.0** (2025-10-11)
- 初版發布
- 整合 Phase 1 原始設計（1707 行）
- 整合 Phase 1 修正內容（1098 行）
- 包含 7 個修正：
  - 修正 #1：Presenter 資料轉換職責明確定位
  - 修正 #2：錯誤轉換 vs 錯誤顯示邊界釐清
  - 修正 #3：決策樹涵蓋 Infrastructure 層判斷
  - 修正 #4：特殊場景處理（架構遷移、安全修復）
  - 修正 #5：Ticket 粒度標準邊界區間細化
  - 修正 #6：架構遷移 Interface-First 五階段指引
  - 修正 #7：團隊協作指引（Q7-Q12）

---

**文件結束**

---

**關於本文件**：

本文件定義了完整的層級隔離派工方法論，為所有遵循 Clean Architecture 的專案提供 Ticket 拆分和實作順序指引。

**適用對象**：
- 專案經理（PM）：規劃和拆分 Ticket
- 開發人員：執行單層修改
- 架構師：設計和審查架構
- Code Reviewer：檢查層級隔離原則

**核心價值**：
- 降低變更風險
- 提升測試獨立性
- 加速開發循環
- 提升 Code Review 效率

**持續改進**：
本文件將根據實務經驗持續更新，歡迎提供回饋和改進建議。

---
