# BDD 測試方法論

## 核心概念

BDD 是測試行為而非實作的策略。測試從使用者視角描述系統行為，使用 Given-When-Then 結構。

**核心價值**：重構時測試保持穩定，因為測試只關心行為結果。

---

## Given-When-Then 結構

| 元素 | 定義 | 規範 |
|-----|------|------|
| **Given** | 系統初始狀態 | 明確、完整、可重現 |
| **When** | 使用者操作 | 單一動作、業務語言 |
| **Then** | 預期結果 | 可驗證、可觀察的行為 |

---

## 行為 vs 實作判斷

| 問題 | 是行為 | 是實作 |
|-----|-------|-------|
| 使用者能直接觀察到？ | Yes | No |
| 改變實作會影響測試？ | No | Yes |
| 產品經理需要關心？ | Yes | No |

---

## 分層測試策略

| 層級 | 測試策略 |
|-----|---------|
| UseCase (Layer 3) | BDD 測試（必須） |
| Domain (Layer 5) | 複雜規則 → 單元測試 |
| Behavior (Layer 2) | 複雜轉換 → 單元測試 |
| UI (Layer 1) | 關鍵流程 → 整合測試 |
| Interface (Layer 4) | 不測試 |

---

## Mock 策略

| 依賴類型 | Mock？ |
|---------|-------|
| Repository / Service / Event Publisher | Yes（外層依賴） |
| Domain Entity / Value Object | No（使用真實物件） |

---

## 執行步驟

1. 從需求提取 Given-When-Then 場景
2. 場景轉換為測試程式碼
3. 測試先行（Red → Green → Refactor）
4. 重構時測試保持穩定

---

## 檢查清單

### 場景完整性
- [ ] 有正常流程測試
- [ ] 有異常流程測試（至少 2 個）
- [ ] 有邊界條件測試（null、0、負數、上限）

### 測試品質
- [ ] 測試名稱使用業務語言
- [ ] Given-When-Then 結構清晰
- [ ] When 只有單一動作
- [ ] Then 驗證可觀察結果（非實作細節）

### Mock 策略
- [ ] 只 Mock 外層依賴
- [ ] Domain Entity 使用真實物件
- [ ] 沒有驗證內部方法呼叫次數

### 重構驗證
- [ ] 重構內部邏輯 → 測試無需修改？
- [ ] 改變演算法 → 測試無需修改？

---

## Reference

- [混合測試策略方法論](./hybrid-testing-strategy-methodology.md) - 分層測試決策樹
- [行為優先 TDD 方法論](./behavior-first-tdd-methodology.md) - Sociable vs Solitary 詳細對比
- [TDD 協作開發流程](../tdd-collaboration-flow.md) - 四階段流程整合