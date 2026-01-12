# 層級隔離派工方法論

**版本**: v1.0.0
**建立日期**: 2025-10-11
**最後更新**: 2025-10-11
**適用範圍**: 所有遵循 Clean Architecture 的專案
**語言**: 繁體中文

---

## 📋 文件資訊

**目的**: 定義 Clean Architecture 五層劃分標準和單層修改原則，指導 Ticket 拆分和實作順序

> **⚠️ 與 Atomic Ticket 方法論的關係**：
>
> 本方法論專注於**層級隔離**原則（單層修改），與 [🎯 Atomic Ticket 方法論](./atomic-ticket-methodology.md) 的**單一職責**原則互補使用：
> - **Atomic Ticket**：一個 Action + 一個 Target（職責維度）
> - **層級隔離**：一個 Ticket 只修改一個架構層級（層級維度）
>
> **本文件中的量化指標（檔案數、行數等）僅供參考**，Ticket 拆分的核心依據仍是單一職責原則。

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

## 衛星文件導覽

本方法論的詳細章節已拆分為衛星文件，便於快速查閱：

| 衛星文件 | 內容 |
|---------|------|
| [快速開始指南](./layered-ticket-quick-start.md) | PM/開發人員/Reviewer 角色快速入門 |
| [層級檢查機制](./layered-architecture-quality-checking.md) | 品質檢查、違規模式識別、自動化工具 |
| [實踐案例](./layered-ticket-examples.md) | 新功能、重構、架構遷移案例 |
| [FAQ 與參考資料](./layered-ticket-faq.md) | 常見問題、參考文獻、工具腳本 |

---

## 檢查清單

### 單層修改檢查
- [ ] 所有修改都在同一層級？
- [ ] 變更原因單一且明確？
- [ ] 測試範圍限定在該層級？

### Ticket 設計檢查
- [ ] 符合粒度標準（1-5 檔案）？
- [ ] 有明確的驗收條件？
- [ ] 可獨立測試和驗收？

### 依賴方向檢查
- [ ] 外層依賴內層？
- [ ] 內層不依賴外層？
- [ ] 透過介面隔離？

---

## Reference

- [Atomic Ticket 方法論](./atomic-ticket-methodology.md) - 單一職責設計原則
- [敏捷重構方法論](./agile-refactor-methodology.md) - Agent 分工協作模式
- [TDD 四階段流程](../tdd-collaboration-flow.md) - 開發流程整合
