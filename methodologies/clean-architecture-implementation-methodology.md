# Clean Architecture 實作方法論

## 核心概念

Clean Architecture 是分層架構模式，核心原則：**依賴只能由外向內**。

### 四層架構

| 層級 | 責任 | 依賴方向 |
|-----|------|---------|
| **Entities** | 核心業務規則、Value Objects | 最內層（無依賴） |
| **Use Cases** | 應用業務邏輯、定義 Ports | 依賴 Entities |
| **Interface Adapters** | Controller、Presenter、Repository 介面 | 依賴 Use Cases |
| **Frameworks & Drivers** | DB、Web、UI 具體實作 | 依賴 Interface Adapters |

### 依賴反轉原則（DIP）

- Use Case 依賴 Repository **介面**（在 Use Cases 層定義）
- Repository **實作**（在 Frameworks 層）依賴該介面
- 組裝階段（Composition Root）注入具體實作

## 執行步驟

### 設計階段（Inner → Outer）

1. **Entities 設計** - 識別業務實體、定義 Value Objects、驗證業務不變量
2. **Use Cases 設計** - 定義 Input/Output Ports、定義 Repository Ports
3. **Interface Adapters 設計** - Controller 轉換請求、Presenter 格式化輸出
4. **Frameworks 設計** - 選擇技術框架、實作 Repository

### 實作階段（Outer → Inner）

1. **定義 Ports** - 先定義 Use Case 和 Repository 介面
2. **外層依賴介面開發** - Controller 使用 Mock Use Case 開發測試
3. **內層補完實作** - Interactor 實作業務邏輯、Repository 實作資料存取
4. **組裝依賴注入** - Composition Root 連接所有元件

## 檢查清單

### 依賴方向

- [ ] Entities 不依賴任何外層
- [ ] Use Cases 只依賴 Entities 和自己定義的 Ports
- [ ] Interface Adapters 依賴 Use Cases 介面
- [ ] Frameworks 實作 Interface Adapters 定義的介面

### 介面契約

- [ ] Repository Port 在 Use Cases 層定義
- [ ] Repository 回傳 Entity（不是 DTO）
- [ ] Input/Output Ports 不洩漏技術細節

### 業務邏輯位置

- [ ] 業務不變量在 Entity 建構子驗證
- [ ] 應用邏輯在 Use Case Interactor
- [ ] Controller 只負責轉換和呼叫

### Interface-Driven Development

- [ ] Ports 在設計階段定義完成
- [ ] 外層使用 Mock 介面開發測試
- [ ] 內層實作後組裝注入

## Reference

### 整合方法論

- [TDD 協作開發流程](../tdd-collaboration-flow.md) - TDD 四階段與 Clean Architecture 整合
- [敏捷重構方法論](./agile-refactor-methodology.md) - Agent 分派與架構層級對應

### 實作詳解

- Clean Architecture SKILL（規劃中）- 完整程式碼範例和案例研究