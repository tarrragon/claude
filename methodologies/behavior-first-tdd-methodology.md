# 行為優先 TDD 方法論

## 核心概念

測試耦合到行為（Module API），而非結構（Class Methods）。重構時測試保持穩定。

**Sociable Unit Tests**（推薦）：
- Unit = Module（1 個或多個類別）
- 只 Mock 外部依賴（Database, File System, External Services）
- 使用真實 Domain Entities

**Solitary Unit Tests**（特殊情況）：
- Unit = Class
- Mock 所有協作者
- 測試脆弱、維護成本高

## 執行步驟

1. **判斷測試策略**：優先使用 Sociable，只在數學演算法/加密系統才用 Solitary
2. **定義測試邊界**：測試透過 Module/UseCase 的 Public API 互動
3. **Mock 策略**：只 Mock Repository/Gateway 等外部依賴，Domain Entities 使用真實物件
4. **撰寫測試**：Given-When-Then 格式，業務語言描述

## 檢查清單

### 測試耦合檢查

- [ ] 測試只呼叫 Module/UseCase 的 Public API
- [ ] 測試不知道內部有哪些類別
- [ ] 只 Mock 外部依賴（Repository, Gateway）
- [ ] Domain Entities 使用真實物件

### 重構安全性驗證

- [ ] 改變內部邏輯 → 測試不變
- [ ] 調整類別結構 → 測試不變
- [ ] 重新命名內部方法 → 測試不變

全部「測試不變」= Sociable（正確）
任何「測試需改」= Solitary（重新設計）

### 適用場景

| 專案類型 | 推薦 |
|---------|------|
| 業務應用程式 | Sociable |
| CRUD/Web API | Sociable |
| 數學演算法 | Solitary |
| 金融計算 | 混合 |

## 前置條件與 Sociable Unit Tests 的關係（v1.2.0 新增）

### 核心連結

Sociable Unit Tests 的「使用真實 Domain Entities」原則，直接要求測試必須先建立真實的前置狀態。這不只是程式碼風格的選擇，而是確保前置條件驗證有意義的基礎。

| 測試類型 | 前置條件來源 | 前置條件可驗性 |
|---------|------------|--------------|
| Sociable（真實物件） | 透過真實 Domain Entity 建立，狀態真實可驗 | 高（前置條件即是真實業務狀態） |
| Solitary（Mock 一切） | Mock 物件回傳預設值，狀態是假設的 | 低（前置條件只是測試假設，不反映真實行為） |

**結論**：Sociable Unit Tests 使前置條件驗證有實際意義——「按鈕存在」是真實渲染的結果，而非 Mock 的預設值。

### 行為推演在單元測試中的應用

Sociable Unit Tests 對應行為鏈推演的三個層次：

| 行為鏈層次 | Sociable Unit Tests 對應 |
|----------|------------------------|
| A（前置條件） | 透過 UseCase 或 Repository Mock 準備真實資料，驗證初始狀態 |
| B（行為觸發） | 呼叫 Module 的 Public API（UseCase.execute()） |
| C（結果確認） | 驗證 Mock Repository 接收到正確的呼叫、或驗證回傳的 Domain Entity 狀態 |

### 前置條件建立的正確模式

```
// Sociable 測試中的前置條件建立（正確）
Given:
  - 建立真實 Book Entity（不是 Mock）
  - 設定 MockBookRepository 回傳此 Entity
  - 驗證 repository.findById() 確實會回傳此 Entity（前置驗證）

When:
  - 呼叫 GetBookDetailUseCase.execute(bookId)

Then:
  - 回傳的 BookDetail 包含正確的 title 和 author
```

**禁止模式**：直接假設 Mock 會回傳正確值而不驗證 Mock 設定是否正確。

### Sociable Unit Tests 行為推演檢查清單

- [ ] 測試的前置狀態是透過真實物件建立的，而非 Mock 硬編碼
- [ ] Mock 的回傳值符合真實業務邏輯（不是任意假值）
- [ ] 每個 Given 步驟有對應的驗證斷言（確認前置條件確實成立）
- [ ] 行為觸發（When）只呼叫 Module Public API，不呼叫內部方法
- [ ] 結果確認（Then）驗證的是行為的可觀察輸出，不是 Mock 被呼叫的次數

---

## Reference

### 相關方法論

- [BDD 測試方法論](./bdd-testing-methodology.md) - Given-When-Then 格式與行為鏈式推演
- [混合測試策略方法論](./hybrid-testing-strategy-methodology.md) - 分層測試決策樹

### 外部文獻

- Kent Beck,《Test Driven Development By Example》- TDD 原始定義
- Martin Fowler,《Refactoring》- 重構定義
- Google,《Software Engineering at Google》- 大規模實踐驗證

---

**Last Updated**: 2026-03-12
**Version**: 1.2.0
**Updates**:
- v1.2.0 (2026-03-12): 新增前置條件與 Sociable Unit Tests 的關係、行為推演在單元測試中的應用（0.1.0-W44-002）