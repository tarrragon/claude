# 拆分策略詳細指南

任務拆分是並行化的基礎。本文檔提供四種主要拆分策略及其適用場景。

## 策略 1：按架構層拆分

### 適用場景

跨越多個 Clean Architecture 層的功能修改。

**例**：「實作用戶認證功能」涉及 UI、ViewModel、Domain、Repository、API 層。

### 拆分邏輯

```
從底層向上拆分
    |
    +-- Domain 層：定義 User entity 和 authentication service
    |   └─ Ticket A (parsley)
    |
    +-- Repository 層：實作 AuthRepository interface
    |   └─ Ticket B (parsley，依賴 A)
    |
    +-- Presentation 層：AuthViewModel 和 LoginWidget
    |   └─ Ticket C (parsley，依賴 B)
```

### 執行順序

**必須嚴格序列**：
1. Domain 層（最低層）完成
2. Repository/Infrastructure 層（中間層）完成
3. Presentation 層（上層）完成

**理由**：上層依賴下層，不能並行。

### 檢查清單

- [ ] 已識別涉及的架構層
- [ ] 每層獨立為一個 Ticket
- [ ] 層之間的依賴清晰標記（blockedBy）
- [ ] 執行順序由底至上

---

## 策略 2：按功能模組拆分

### 適用場景

同層級但涉及多個獨立功能模組的修改。

**例**：「實作多個獨立 Feature 的相同修改」（如為 5 個 Feature 都新增搜尋功能）。

### 拆分邏輯

```
識別共用組件和獨立模組
    |
    +-- 共用組件（如 SearchService）
    |   └─ Ticket A（先完成，所有模組依賴此）
    |
    +-- Feature 1 整合
    |   └─ Ticket B（可並行，依賴 A）
    |
    +-- Feature 2 整合
    |   └─ Ticket C（可並行，依賴 A）
    |
    +-- Feature N 整合
    |   └─ Ticket N+1（可並行，依賴 A）
```

### 執行策略

1. **先完成共用組件** → Ticket A
2. **獨立模組可並行** → Tickets B, C, D... 同時執行（數量無上限）

### 檢查清單

- [ ] 已識別共用和獨立部分
- [ ] 共用部分單獨建立 Ticket
- [ ] 獨立部分分別建立 Ticket
- [ ] 獨立 Ticket 標記 blockedBy 共用 Ticket

---

## 策略 3：按操作類型拆分

### 適用場景

同一功能中混合了多種操作類型（機械性 vs 邏輯性）。

**例**：「重構 UserRepository，包括變數重命名、方法提取、邏輯修改」。

### 拆分邏輯

```
識別操作類型
    |
    +-- 機械性操作（重命名、格式化、移動檔案）
    |   └─ Ticket A（可大量並行，多個 Agent）
    |
    +-- 邏輯修改（業務規則更新、算法變更）
    |   └─ Ticket B（需謹慎序列，少數 Agent）
    |
    +-- 新增功能（新方法、新類）
    |   └─ Ticket C（depends on B 完成）
```

### 執行策略

| 操作類型 | 並行性 | 代理人數 | 順序 |
|---------|--------|---------|------|
| 機械操作 | 高（可大量並行） | 無上限 | 第一 |
| 邏輯修改 | 低（需序列） | 1-2 | 第二 |
| 新功能 | 中（部分並行） | 2-3 | 第三 |

### 檢查清單

- [ ] 已分離機械性和邏輯性操作
- [ ] 機械操作 Ticket 可並行標記
- [ ] 邏輯修改 Ticket 必須序列
- [ ] 新功能依賴邏輯完成

---

## 策略 4：按 TDD 階段拆分

### 適用場景

實現完整新功能，需要完整 TDD 流程。

### 拆分邏輯

```
新功能實現
    |
    v
Phase 0：SA 前置審查
    └─ Ticket 0 (system-analyst)
    |
    v
Phase 1：功能設計
    └─ Ticket 1 (lavender-interface-designer)
    |
    v
Phase 2：測試設計
    └─ Ticket 2 (sage-test-architect)
    |
    v
Phase 3a：實作策略
    └─ Ticket 3a (pepper-test-implementer)
    |
    v
Phase 3b：實作執行
    └─ Ticket 3b (parsley-flutter-developer)
    |
    v
Phase 4：重構評估
    └─ Ticket 4 (cinnamon-refactor-owl)
```

### 執行策略

**嚴格序列，不能並行或跳過任何 Phase。**

| Phase | 代理人 | 前置條件 | 產出 |
|-------|--------|--------|------|
| 0 | system-analyst | 新功能需求 | 架構審查報告 |
| 1 | lavender | SA 通過 | 功能規格 |
| 2 | sage | Phase 1 完成 | 測試案例 |
| 3a | pepper | Phase 2 完成 | 實作策略 |
| 3b | parsley | Phase 3a 完成 | 可執行程式碼 |
| 4 | cinnamon | Phase 3b 完成 | 重構評估 |

### 檢查清單

- [ ] 為每個 Phase 建立獨立 Ticket
- [ ] Ticket 間的 blockedBy 關係明確
- [ ] 不跳過任何 Phase
- [ ] Phase 4 評估完成後才認為功能完成

---

## 策略選擇決策樹

```
任務進入
    |
    v
跨越多個架構層？ ─是→ 策略 1（按架構層）
    |
    └─否→ 涉及多個獨立模組？ ─是→ 策略 2（按功能模組）
              |
              └─否→ 混合機械性和邏輯操作？ ─是→ 策略 3（按操作類型）
                        |
                        └─否→ 是完整新功能？ ─是→ 策略 4（按 TDD 階段）
                                |
                                └─否→ 直接派發（不拆分）
```

---

## 複雜案例：多策略組合

### 例：「實現多語言支援系統」

**分析**：
- 涉及多個 Feature（策略 2）
- 每個 Feature 中有 Domain/Repository/UI 層（策略 1）
- 包括變數重命名和邏輯修改（策略 3）
- 是新功能，需要完整 TDD（策略 4）

**拆分方案**：

1. **Phase 0**（SA 審查）
   - system-analyst 審查多語言系統架構

2. **Phase 1-3**（功能設計和測試）
   - 整體由一個代理人完成（涉及多層和多模組）

3. **Phase 3b**（實作執行）
   - 按 Feature 拆分為 5 個並行 Ticket（策略 2）
   - 每個 Feature Ticket 內部按層拆分（策略 1）

4. **Phase 4**（重構評估）
   - cinnamon 整體評估

**執行計畫**：

```
Phase 0: 1 個 Ticket（系統架構）
    ↓
Phase 1-3: 1 個大 Ticket（整體設計）
    ↓
Phase 3b: 5 個並行 Ticket
    - Feature A: Domain → Repo → UI（3 層，序列）
    - Feature B: Domain → Repo → UI（3 層，序列）
    - ... 並行執行
    ↓
Phase 4: 1 個 Ticket（整體評估）
```

---

## 常見錯誤和修正

| 錯誤 | 原因 | 修正 |
|------|------|------|
| 拆分過細 | 過度拆分導致依賴複雜 | 優化依賴關係 |
| 隱藏依賴 | 遺漏了 Ticket 間的依賴 | 再次分析，使用依賴矩陣 |
| 混合操作類型 | 機械和邏輯操作沒分開 | 應用策略 3 |
| 跨 Wave 拆分 | 跨越 Wave 邊界的 Ticket | 確保同 Wave 內完成 |
| 並行化不足 | 可並行的 Ticket 仍序列 | 重新評估依賴，最大化並行 |

---

**Last Updated**: 2026-03-02
**Version**: 1.0.0
