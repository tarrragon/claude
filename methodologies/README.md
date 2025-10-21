# 行為驅動測試方法論體系導覽

> **測試是可執行的需求規格書，而非驗證實作的工具。**
> — Kent Beck, Martin Fowler

## 📚 方法論體系概覽

本目錄包含三篇互補的測試方法論，共同構成完整的行為驅動測試體系。

```text
行為驅動測試體系架構
│
├─ 理論基礎層（WHY）
│  └─ behavior-first-tdd-methodology.md
│     揭示TDD痛點根源，提供歷史證據
│
├─ 實作格式層（HOW）
│  └─ bdd-testing-methodology.md
│     Given-When-Then格式規範
│
└─ 決策執行層（WHEN）
   └─ hybrid-testing-strategy-methodology.md
      分層測試決策樹，量化覆蓋率指標
```

---

## 🎯 三篇方法論的角色定位

### 1️⃣ Behavior-First TDD 方法論（理論基礎 - WHY）

**檔案**: [`behavior-first-tdd-methodology.md`](./behavior-first-tdd-methodology.md)

**核心定位**：揭示TDD痛點的根本原因，說明測試應該耦合到行為而非結構。

**主要內容**：
- 🔍 **TDD痛點的根本原因** - 為什麼TDD變得痛苦？
- 📖 **歷史證據** - Kent Beck、Martin Fowler、Google的實踐經驗
- 🆚 **Sociable vs Solitary Unit Tests** - 兩種測試風格的完整對比
- ⚖️ **Test-First vs Test-Last** - 反饋循環的差異分析

**核心概念**：
- ✅ **Sociable Unit Tests** - Module層級測試，只Mock外部依賴
- ❌ **Solitary Unit Tests** - Class層級測試，Mock所有協作者
- 📋 **Executable Specifications** - 測試是可執行的需求規格書
- 🔄 **Coupling to Behavior** - 測試耦合到行為而非結構

**適合閱讀時機**：
- 想理解「為什麼TDD會痛苦」
- 需要說服團隊採用行為驅動測試
- 想了解TDD的歷史演進和流派差異

**關鍵引用**：
> "Tests should be coupled to the behavior of the code and decoupled from the structure of code."
> — Kent Beck, Test Driven Development By Example

---

### 2️⃣ BDD 測試方法論（實作格式 - HOW）

**檔案**: [`bdd-testing-methodology.md`](./bdd-testing-methodology.md)

**核心定位**：定義Given-When-Then格式規範，整合到Clean Architecture和TDD四階段流程。

**主要內容**：
- 📋 **Given-When-Then結構** - BDD測試場景撰寫規範
- 🏗 **Clean Architecture整合** - 分層測試策略（Layer 1-5）
- 🔄 **TDD四階段整合** - Phase 1-4的BDD測試設計
- ✅ **核心原則** - 測試行為而非實作、UseCase層BDD、Mock策略

**核心概念**：
- 📝 **Given-When-Then** - 業務場景描述格式
- 🎯 **UseCase層測試** - BDD的核心應用層
- 🔀 **Mock策略** - 只Mock外層依賴（Repository, Service）
- 🚫 **不Mock Domain** - 使用真實的Domain Entity和Value Object

**適合閱讀時機**：
- 需要撰寫BDD測試時
- 想了解如何整合BDD到TDD流程
- 需要學習Given-When-Then格式

**關鍵章節**：
- 第二章：BDD核心原則
- 第三章：BDD與Clean Architecture整合
- 第四章：BDD與TDD四階段流程整合
- 第八章：Given-When-Then撰寫規範
- 第九章：正反範例

---

### 3️⃣ 混合測試策略方法論（決策執行 - WHEN）

**檔案**: [`hybrid-testing-strategy-methodology.md`](./hybrid-testing-strategy-methodology.md)

**核心定位**：為每層Ticket提供明確的測試設計指引，包含分層測試決策樹和量化覆蓋率指標。

**主要內容**：
- 🌳 **分層測試決策樹** - Layer 1-5測試策略判斷流程
- 📊 **量化覆蓋率指標** - 每層的測試覆蓋率要求
- 🎫 **Ticket測試策略設計** - 整合到Ticket設計流程
- 🔍 **技術性檢查清單** - Null、空集合、邊界條件、異常處理

**核心概念**：
- 🏗 **Layer 1 (UI)** - 整合測試（關鍵流程）
- 🔄 **Layer 2 (Behavior)** - 單元測試（複雜轉換）
- 📋 **Layer 3 (UseCase)** - BDD測試（所有場景）
- 🧩 **Layer 5 (Domain)** - 單元測試（複雜邏輯）

**適合閱讀時機**：
- 規劃Ticket的測試策略時
- 不確定該用哪種測試方法時
- 需要量化測試覆蓋率指標時

**關鍵章節**：
- 第三章：分層測試決策樹
- 第四章：各層測試策略詳解
- 第五章：測試覆蓋率量化指標
- 第六章：Ticket測試策略設計
- 第七章：技術性測試檢查清單

---

## 🎓 閱讀順序建議

### 🌱 新手路徑（第一次接觸行為驅動測試）

建議按照「理論 → 格式 → 決策」的順序閱讀：

**Step 1: 理解痛點和原則**
- 閱讀：[`behavior-first-tdd-methodology.md`](./behavior-first-tdd-methodology.md)
- 重點章節：第1章（TDD痛點）、第2章（測試本質）、第3章（Sociable vs Solitary）
- 目標：理解「為什麼測試要耦合到行為」

**Step 2: 學習撰寫格式**
- 閱讀：[`bdd-testing-methodology.md`](./bdd-testing-methodology.md)
- 重點章節：第2章（BDD核心原則）、第8章（Given-When-Then規範）、第9章（正反範例）
- 目標：學會撰寫Given-When-Then測試

**Step 3: 應用決策指引**
- 閱讀：[`hybrid-testing-strategy-methodology.md`](./hybrid-testing-strategy-methodology.md)
- 重點章節：第3章（決策樹）、第4章（各層策略）、第6章（Ticket設計）
- 目標：知道什麼時候用什麼測試方法

---

### 🚀 老手路徑（快速參考）

根據具體需求快速查找：

| 需求場景 | 參考方法論 | 關鍵章節 |
|---------|-----------|---------|
| 需要理論依據說服團隊 | Behavior-First TDD | 第1章、第3章、第5章 |
| 需要撰寫UseCase測試 | BDD測試方法論 | 第8章、第9章 |
| 需要撰寫Domain測試 | 混合測試策略 | 第4.5節 |
| 不確定測試類型 | 混合測試策略 | 第3章決策樹 |
| 需要檢查測試品質 | BDD測試方法論 | 第7章 |
| 需要設計Ticket測試 | 混合測試策略 | 第6章 |
| 需要Code Review檢查 | 混合測試策略 | 第9章 |

---

### 🎯 問題導向路徑

根據遇到的問題直接查找解決方案：

**問題 1: 「我不知道該測試什麼」**
- 閱讀：`behavior-first-tdd-methodology.md` → 第2章（測試本質）
- 答案：測試需求行為而非實作細節

**問題 2: 「重構時測試總是破裂」**
- 閱讀：`behavior-first-tdd-methodology.md` → 第3章（Sociable vs Solitary）
- 答案：測試耦合到結構了，應該耦合到行為

**問題 3: 「測試程式碼量是production code的3倍」**
- 閱讀：`behavior-first-tdd-methodology.md` → 第3.5節（對比總結）
- 答案：Solitary Unit Tests導致大量Mock，改用Sociable Unit Tests

**問題 4: 「不知道Given-When-Then怎麼寫」**
- 閱讀：`bdd-testing-methodology.md` → 第8章（撰寫規範）
- 答案：完整的Given-When-Then格式規範和範例

**問題 5: 「Layer 2的簡單映射要不要測試？」**
- 閱讀：`hybrid-testing-strategy-methodology.md` → 第4.2節（Behavior層策略）
- 答案：簡單映射不需要獨立測試，由UseCase層測試覆蓋

**問題 6: 「測試覆蓋率要求是多少？」**
- 閱讀：`hybrid-testing-strategy-methodology.md` → 第5章（量化指標）
- 答案：UseCase 100%場景、Domain 100%程式碼、整體≥80%

**問題 7: 「要不要Mock Domain Entity？」**
- 閱讀：`bdd-testing-methodology.md` → 第3.3節（依賴倒置測試）
- 答案：不要Mock，使用真實的Domain Entity和Value Object

---

## 🔗 與TDD四階段流程的整合

三篇方法論如何對應到TDD四階段：

```text
Phase 1: 功能設計（lavender-interface-designer）
├─ 使用：BDD測試方法論
└─ 行為場景提取（Given-When-Then）

Phase 2: 測試設計（sage-test-architect）
├─ 使用：混合測試策略方法論
│  └─ 分層測試決策樹
├─ 使用：BDD測試方法論
│  └─ Given-When-Then格式
└─ 理論基礎：Behavior-First TDD方法論
   └─ Sociable Unit Tests原則

Phase 3a: 語言無關策略（pepper-test-implementer）
└─ 使用：混合測試策略方法論
   └─ 技術性檢查清單

Phase 3b: 程式碼實作（parsley-flutter-developer）
└─ 使用：BDD測試方法論
   └─ Mock策略和驗證標準

Phase 4: 重構優化（cinnamon-refactor-owl）
└─ 使用：Behavior-First TDD方法論
   └─ 測試穩定性檢查（測試不應破裂）
```

---

## 🧭 核心原則快速參考

### 測試的本質

> **Tests = Executable Requirements Specifications**
>
> 測試不是「驗證實作的工具」，而是**用程式碼表達的需求規格書**。

### 測試耦合原則

| 應該耦合到 | 不應該耦合到 |
|----------|-----------|
| ✅ 行為（Behavior） | ❌ 結構（Structure） |
| ✅ Module API | ❌ Class Methods |
| ✅ 需求規格 | ❌ 實作細節 |
| ✅ 可觀察的結果 | ❌ 內部狀態 |

### Sociable Unit Tests核心

| 概念 | 說明 |
|-----|------|
| **Unit** | Module（1個或多個類別） |
| **Isolation** | 只隔離外部世界（Database, File System, External Services） |
| **Mock策略** | 只Mock外層依賴，不Mock其他類別和Domain Entities |
| **測試目標** | 透過Module API測試行為，不知道內部結構 |

### 分層測試策略

| 層級 | 測試類型 | 覆蓋率要求 |
|-----|---------|----------|
| **Layer 1 (UI)** | 整合測試（關鍵流程） | 關鍵路徑100% |
| **Layer 2 (Behavior)** | 單元測試（複雜轉換） | 邏輯覆蓋100% |
| **Layer 3 (UseCase)** | BDD測試（所有場景） | 行為場景100% |
| **Layer 4 (Interface)** | 不測試 | N/A |
| **Layer 5 (Domain)** | 單元測試（複雜邏輯） | 程式碼覆蓋100% |

### Given-When-Then規範

```dart
test('使用者提交訂單成功', () async {
  // Given: 使用者已選擇商品且填寫完整資訊
  final order = Order(...);
  when(mockRepository.save(any)).thenAnswer(...);

  // When: 使用者點擊「提交訂單」
  final result = await submitOrderUseCase.execute(order);

  // Then: 系統確認訂單已儲存
  expect(result.isSuccess, true);
  expect(result.orderId, isNotEmpty);
});
```

**規範要點**：
- ✅ Given明確描述前置條件
- ✅ When只有單一動作
- ✅ Then驗證可觀察的結果
- ✅ 使用業務語言而非技術術語

### Mock策略原則

| 依賴類型 | Mock策略 | 理由 |
|---------|---------|------|
| Repository | ✅ Mock | 外層依賴，隔離Database |
| Service | ✅ Mock | 外層依賴，隔離External Services |
| Event Publisher | ✅ Mock | 外層依賴，驗證事件發布 |
| Domain Entity | ❌ 不Mock | 內層邏輯，使用真實物件 |
| Value Object | ❌ 不Mock | 內層邏輯，使用真實物件 |

---

## 🎯 常見場景指引

### 場景 1: 撰寫UseCase測試

**推薦閱讀順序**：
1. `bdd-testing-methodology.md` → 第4.3節（Phase 2測試設計）
2. `bdd-testing-methodology.md` → 第8章（Given-When-Then規範）
3. `bdd-testing-methodology.md` → 第9.1節（UseCase測試完整範例）

**關鍵檢查清單**：
- [ ] 使用Given-When-Then格式
- [ ] 測試名稱使用業務語言
- [ ] 涵蓋正常流程、異常流程、邊界條件
- [ ] 只Mock外層依賴（Repository, Service）
- [ ] 使用真實的Domain Entity和Value Object

---

### 場景 2: 撰寫Domain層測試

**推薦閱讀順序**：
1. `hybrid-testing-strategy-methodology.md` → 第4.5節（Domain層策略）
2. `bdd-testing-methodology.md` → 第9.1節（正反範例）

**關鍵檢查清單**：
- [ ] 複雜業務規則必須單元測試
- [ ] 值物件驗證必須單元測試
- [ ] 實體不變量必須單元測試
- [ ] 簡單CRUD Entity依賴UseCase層測試
- [ ] 程式碼覆蓋率100%

---

### 場景 3: 判斷是否需要獨立測試

**推薦閱讀順序**：
1. `hybrid-testing-strategy-methodology.md` → 第3章（決策樹）
2. `hybrid-testing-strategy-methodology.md` → 第4章（各層策略詳解）

**決策流程**：
```text
Step 1: 識別程式碼屬於哪一層？
→ Layer 1, 2, 3, 5

Step 2: 根據決策樹判斷
→ 是否為關鍵流程/複雜邏輯？

Step 3: 查看對應章節
→ 第4.1節（Layer 1）
→ 第4.2節（Layer 2）
→ 第4.3節（Layer 3）
→ 第4.5節（Layer 5）
```

---

### 場景 4: 設計Ticket的測試策略

**推薦閱讀順序**：
1. `hybrid-testing-strategy-methodology.md` → 第6章（Ticket測試策略設計）
2. `hybrid-testing-strategy-methodology.md` → 第6.2節（範例）

**Ticket模板欄位**：
```markdown
### 測試策略
- **測試類型**: BDD / 單元測試 / 整合測試 / 不需要測試
- **測試範圍**: [列出必須測試的場景]
- **測試工具**: [測試框架名稱]
- **覆蓋率要求**: [具體數值或標準]
- **依賴關係**: 獨立測試 / 依賴 [Layer X] 測試
```

---

### 場景 5: Code Review測試品質

**推薦閱讀順序**：
1. `hybrid-testing-strategy-methodology.md` → 第9章（Code Review檢查項目）
2. `bdd-testing-methodology.md` → 第7.4節（測試品質驗證）

**檢查清單**：
- [ ] 測試類型符合分層策略
- [ ] BDD測試聚焦行為
- [ ] Given-When-Then結構清晰
- [ ] Mock策略正確
- [ ] 場景完整性（正常、異常、邊界）
- [ ] 技術性檢查清單完整
- [ ] 測試覆蓋率達標

---

### 場景 6: 說服團隊採用行為驅動測試

**推薦閱讀順序**：
1. `behavior-first-tdd-methodology.md` → 第1章（TDD痛點根本原因）
2. `behavior-first-tdd-methodology.md` → 第5章（歷史證據）
3. `behavior-first-tdd-methodology.md` → 第3.5節（對比總結）

**關鍵論據**：
- ✅ Kent Beck、Martin Fowler等TDD創始人都使用Sociable Unit Tests
- ✅ Google實踐證明：測試行為而非實作降低維護成本
- ✅ 量化對比：重構時測試修改從20-50%降至0-5%

---

## 📊 整合關係圖

```text
┌─────────────────────────────────────────────────────────┐
│          行為驅動測試方法論體系                            │
├─────────────────────────────────────────────────────────┤
│                                                         │
│  Behavior-First TDD（理論基礎 - WHY）                    │
│  ┌───────────────────────────────────────────┐         │
│  │ • TDD痛點根源                              │         │
│  │ • Sociable vs Solitary對比                │         │
│  │ • 歷史證據（Kent Beck, Martin Fowler）    │         │
│  │ • Test-First vs Test-Last反饋循環        │         │
│  └───────────────┬───────────────────────────┘         │
│                  │ 提供理論基礎                         │
│                  ↓                                      │
│  BDD測試方法論（實作格式 - HOW）                         │
│  ┌───────────────────────────────────────────┐         │
│  │ • Given-When-Then格式規範                  │         │
│  │ • Clean Architecture整合                   │         │
│  │ • TDD四階段流程整合                        │         │
│  │ • Mock策略原則                             │         │
│  └───────────────┬───────────────────────────┘         │
│                  │ 提供實作格式                         │
│                  ↓                                      │
│  混合測試策略（決策執行 - WHEN）                         │
│  ┌───────────────────────────────────────────┐         │
│  │ • 分層測試決策樹（Layer 1-5）              │         │
│  │ • 量化覆蓋率指標                           │         │
│  │ • Ticket測試策略設計                       │         │
│  │ • Code Review檢查清單                      │         │
│  └───────────────────────────────────────────┘         │
│                                                         │
└─────────────────────────────────────────────────────────┘
```

---

## 🚨 重要提醒

### 測試的核心原則（不可妥協）

> **"Tests should be coupled to the behavior of the code and decoupled from the structure of code."**
> — Kent Beck

**這意味著**：
1. ✅ 重構時測試不應該破裂（如果破裂，表示測試耦合到結構）
2. ✅ 測試描述「系統做什麼」而非「系統怎麼做」
3. ✅ 測試使用業務語言而非技術術語
4. ✅ 測試透過Module API而非直接存取內部類別

### 常見誤解

**誤解 1**: 「BDD和TDD是不同的方法」
- ❌ 錯誤：BDD創造了新的測試方法
- ✅ 真相：BDD只是修正了TDD中「Test」這個詞造成的命名混淆

**誤解 2**: 「Unit Test必須測試單一Class」
- ❌ 錯誤：Unit = Class
- ✅ 真相：Unit = Module（可包含多個類別）

**誤解 3**: 「所有協作者都要Mock」
- ❌ 錯誤：Solitary Unit Tests（Mock所有協作者）
- ✅ 真相：Sociable Unit Tests（只Mock外部依賴）

**誤解 4**: 「測試程式碼是production code的2-4倍很正常」
- ❌ 錯誤：接受測試的高維護成本
- ✅ 真相：正確的測試方法不會產生如此高的成本

### 閱讀注意事項

1. **不要跳過理論基礎** - `behavior-first-tdd-methodology.md`提供的歷史證據和理論基礎是理解其他兩篇的關鍵
2. **理解WHY再學HOW** - 先理解「為什麼要測試行為」再學習「如何撰寫Given-When-Then」
3. **決策樹是工具不是規則** - `hybrid-testing-strategy-methodology.md`的決策樹是指引，具體情況可彈性調整
4. **範例比理論重要** - 三篇方法論都提供大量正反範例，務必仔細閱讀

---

## 📖 延伸閱讀

### 經典書籍

1. **Kent Beck - Test Driven Development By Example**
   - TDD的原始定義和實踐方法
   - Sociable Unit Tests的源頭

2. **Martin Fowler - Refactoring: Improving the Design of Existing Code**
   - 重構的定義和原則
   - 測試應該保持穩定的理論基礎

3. **Dan North - Introducing BDD**
   - BDD的起源和動機
   - Given-When-Then格式的創造過程

4. **Google - Software Engineering at Google**
   - 大規模測試實踐
   - 測試維護成本的量化分析

### 相關專案文件

- [🤝 TDD 協作開發流程]($CLAUDE_PROJECT_DIR/.claude/tdd-collaboration-flow.md) - TDD四階段流程
- [🏗 Clean Architecture實作方法論]($CLAUDE_PROJECT_DIR/.claude/methodologies/clean-architecture-implementation-methodology.md) - 架構分層原則
- [📋 Ticket設計派工方法論]($CLAUDE_PROJECT_DIR/.claude/methodologies/ticket-design-dispatch-methodology.md) - 任務拆分和設計
- [🧭 程式碼品質範例彙編]($CLAUDE_PROJECT_DIR/.claude/code-quality-examples.md) - 具體程式碼範例

---

## 🆘 需要幫助？

如果在閱讀過程中遇到問題，可以：

1. **查看FAQ** - 每篇方法論的「常見問題」章節
2. **參考範例** - 第九章或第十章的正反範例
3. **使用決策樹** - `hybrid-testing-strategy-methodology.md`第3章
4. **向主線程請求** - rosemary-project-manager協助

---

**文件版本**: v1.0
**建立日期**: 2025-10-16
**維護者**: thyme-documentation-integrator
**狀態**: ✅ 已啟用
