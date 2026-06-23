# BDD 行為測試指引

## 目的

定義 BDD（Behavior-Driven Development）在 TDD 流程中的定位：測試描述系統的「行為」而非「實作」。

**Why**：測試耦合實作細節時，重構內部結構（即使業務邏輯不變）會導致大量測試失敗，維護成本超過撰寫功能本身。BDD 要求測試只耦合可觀察的行為，使重構時測試保持穩定。

**Consequence**：不區分行為與實作的測試套件，在替換儲存層、重構內部類別結構等合理重構後會連鎖失敗，團隊逐漸放棄維護測試或迴避重構。

**Action**：用三問判別法篩選測試內容、用 Sociable/Solitary 框架選擇測試風格、用分層 Mock 原則控制耦合範圍。

---

## 行為 vs 實作判別

對每個測試斷言，依序問三個問題：

| 問題 | 答案為「是」 | 答案為「否」 |
|------|------------|------------|
| 使用者能否觀察到這個結果？ | 偏向行為 | 偏向實作 |
| 改變實作方式會影響這個結果嗎？ | 偏向實作 | 偏向行為 |
| 產品經理需要關心這個結果嗎？ | 偏向行為 | 偏向實作 |

三問結果為「能觀察、不影響、需關心」→ 行為；反之 → 實作細節。

### 對照範例

測試實作（耦合結構，重構即失敗）：

```
test "save order calls database.insert":
  repository.save(order)
  verify database.insert("orders", order.to_json()) called 1 time
```

測試行為（耦合可觀察結果，重構不影響）：

```
test "使用者提交訂單 - 訂單成功儲存":
  Given: order = valid_order()
  When:  result = submit_order.execute(order)
  Then:  assert result.is_success == true
         assert result.order_id is not empty
```

---

## Sociable vs Solitary 選擇框架

TDD 有兩種測試風格，核心差異在耦合對象數量：

| 特性 | Sociable（Classical TDD） | Solitary（Mockist TDD） |
|------|--------------------------|------------------------|
| 測試單元 | Module（一組協作的類別） | 單一 Class |
| 耦合線 | 一條（Module Public API） | 多條（每個 Mock 一條） |
| Mock 範圍 | 只 Mock 外部依賴（DB、API） | Mock 所有協作者 |
| Domain Entity | 使用真實物件 | Mock |
| 重構時表現 | 測試不動 | 測試跟著改 |
| 適用場景 | 商業應用（大多數情況） | 演算法、加密等需細粒度驗證 |

**選擇準則**：商業應用預設 Sociable；只在需要精確定位到具體類別的場景（數學演算法、加密系統）使用 Solitary。

### 重構安全性驗證

驗證自己的測試風格是否正確：

1. 改變 Module 內部結構（拆類別、提取方法、重命名內部方法）
2. 所有測試不需修改且通過 → Sociable（正確）
3. 任何測試需跟著改 → Solitary（重新設計測試邊界）

**判斷標準**：替換儲存層實作、改變內部演算法 → 測試不應失敗；改變業務規則、調整可觀察的錯誤訊息 → 測試應失敗。

---

## 分層 Mock 原則

核心規則：**只 Mock 外層依賴，禁止 Mock Domain Entity**。

| 類別 | Mock？ | 理由 |
|------|--------|------|
| Repository / Service / Gateway | 是 | 外部系統依賴，透過 Interface 隔離 |
| Event Publisher / Message Queue | 是 | 外部基礎設施 |
| Domain Entity / Value Object | **禁止** | 內層業務邏輯，必須用真實物件測試 |
| UseCase 內部 Helper | **禁止** | Module 內部結構，Mock 即耦合實作 |

正確（Mock 外層，真實 Domain）：

```
test "使用者提交訂單成功":
  mock_repository.on_save -> return success("order-123")
  order = Order(amount=100, user_id="user-001")    // 真實 Domain Entity
  result = submit_order.execute(order)
  assert result.is_success == true
```

錯誤（Mock Domain Entity，測不到業務邏輯）：

```
test "使用者提交訂單成功":
  mock_order = MockOrder()
  mock_order.on_validate -> return true    // 跳過真實驗證邏輯
  // 測試通過但業務規則未被驗證
```

---

## 架構分層 × BDD 適用度

| 架構層級 | 測試方法 | 覆蓋率要求 | 說明 |
|---------|---------|-----------|------|
| UseCase | **BDD**（GWT） | 行為場景 100% | 核心應用層，每個場景一個 GWT |
| Domain | 單元測試 | 分支 100% | 值物件驗證、實體不變量、業務規則邊界 |
| Behavior / ViewModel | 條件單元測試 | 複雜轉換才測 | 簡單轉換由 UseCase 層覆蓋 |
| UI | 整合測試 | 關鍵路徑 | 測試成本高，只測關鍵互動 |
| Interface | **不測** | — | 只定義契約無實作邏輯 |

---

## 與 TDD 四階段整合

| Phase | BDD 角色 |
|-------|---------|
| Phase 1 功能設計 | 從需求識別使用者行為場景（正常 + 異常 + 邊界） |
| Phase 2 測試設計 | 將行為場景轉換為 GWT 測試結構，設置 Mock |
| Phase 3 實作 | Red→Green→Refactor，測試先行 |
| Phase 4 重構 | 行為測試必須保持穩定——重構導致測試修改代表耦合了實作 |

Phase 4 品質判斷：替換實作不讓測試失敗 = 正確；改變業務規則讓測試失敗 = 正確。兩者反過來都是設計問題。

---

## BDD 前置產出物完整性（涉及 UI 時）

涉及 UI 的 BDD 操作盤點，除了操作/主情境/失敗情境表，必須額外產出**畫面狀態矩陣**（畫面 × 狀態 × 可用操作 × 退出路徑）。缺此矩陣，widget test 和導航測試無法完整覆蓋——UC 步驟轉 GWT 時只有 happy path 行為，忽略每個畫面的狀態切換和退出路徑。

**實戰教訓**：app_tunnel v1.2.0 有 192 個 unit test 全綠，實機發現 4 個畫面缺返回按鈕和斷線處理，根因是 BDD 操作盤點未產出畫面狀態機。

---

## BDD→單元拆分判準

當 BDD 整合測試覆蓋的 Module 變大，需判斷何時拆出獨立的單元測試：

| 訊號 | 動作 |
|------|------|
| Domain 層出現複雜分支邏輯（> 3 條件組合） | 拆為 Domain 單元測試，驗證分支覆蓋 |
| 值物件驗證規則多（> 5 個邊界條件） | 拆為 Value Object 單元測試 |
| BDD 測試的 Given 設置過長（> 10 行 Mock） | Module 過大，考慮拆分 Module 而非加測試 |
| 步驟正確性由元件自身決定（非串接決定） | 拆為單元測試（見 `doc-handoff.md` 分工框架） |
| 步驟正確性由串接決定 | 留在整合測試 |
| 步驟正確性由配置決定 | 拆為參數化測試 |

**分工邊界**：UseCase 層行為用 BDD 保護；Domain 層邏輯用單元測試保護；兩者互補，BDD 覆蓋業務流程正確性，單元測試覆蓋邏輯分支完整性。

---

## 常見挑戰速查

| 挑戰 | 對策 |
|------|------|
| **覆蓋率盲點**：BDD 只測「重要行為」，可能漏掉程式碼 | 混合策略——UseCase 100% BDD + Domain 100% 單元 + 整體 80% 行數 |
| **行為粒度**：太粗難定位失敗，太細變回單元測試 | 一個 UseCase = 一個核心行為，名稱以動詞開頭 |
| **測試設置複雜**：UseCase 需 Mock 多個外部依賴 | 建立 Test Helper / Builder Pattern 減少重複設置 |
| **假行為測試**：看似 GWT 格式但斷言仍驗證實作 | 用三問判別法逐一檢查每個斷言 |

---

## 相關文件

- `references/phase2-test-design.md` — GWT 格式、場景設計原則（Phase 2 操作層）
- `references/layered-test-strategy.md` — 依架構層級選測試方法的決策樹
- `references/doc-handoff.md`「整合測試 vs 單元測試分工」— 整合/單元判斷框架
- `references/test-naming-conventions.md` — 測試命名規範

---

**Last Updated**: 2026-06-22
**Version**: 1.0.0 — 從 blog 提煉。BDD 核心判別法 + Sociable/Solitary 選擇 + 分層 Mock + BDD→單元拆分判準
**Source**: `~/Projects/blog/content/record/bdd-testing-methodology.md`、`~/Projects/blog/content/record/behavior-first-tdd-methodology.md`
