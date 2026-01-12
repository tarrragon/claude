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

## Reference

### 相關方法論

- [BDD 測試方法論](./bdd-testing-methodology.md) - Given-When-Then 格式
- [混合測試策略方法論](./hybrid-testing-strategy-methodology.md) - 分層測試決策樹

### 外部文獻

- Kent Beck,《Test Driven Development By Example》- TDD 原始定義
- Martin Fowler,《Refactoring》- 重構定義
- Google,《Software Engineering at Google》- 大規模實踐驗證