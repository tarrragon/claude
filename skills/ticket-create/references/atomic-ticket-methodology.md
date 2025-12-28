# Atomic Ticket 方法論

**版本**: v1.0.0
**建立日期**: 2025-12-25
**核心原則**: 單一職責原則 (Single Responsibility Principle)

---

## 核心定義

### 什麼是 Atomic Ticket？

**Atomic Ticket** = 一個 Action + 一個 Target

```text
Atomic Ticket = 動詞 + 單一目標
```

**核心特徵**：
- **單一職責**：只有一個修改原因
- **獨立驗收**：可以獨立完成和驗收
- **不可再拆分**：拆分後會產生循環依賴

---

## 單一職責評估方式

### 評估原則（四大檢查）

**單一職責是唯一的評估標準**。以下四個檢查方式用於判斷是否符合單一職責：

### 1. 語義檢查

**問題**：Ticket 能用「動詞 + 單一目標」表達嗎？

**符合單一職責** ✅：
```text
實作 startScan() 方法
修復 ISBN 驗證邏輯
新增 BookRepository.save() 測試
重構 SearchService 的錯誤處理
```

**違反單一職責** ❌：
```text
實作 ISBNScannerService 的掃描功能和離線支援  ← 兩個目標
修復 ISBN 驗證和優化效能  ← 兩個行動
新增 BookRepository 的所有測試  ← 多個目標
```

### 2. 修改原因檢查

**問題**：只有一個原因會導致這個 Ticket 需要修改嗎？

**符合單一職責** ✅：
```text
Ticket: 實作 startScan() 方法
修改原因: 只有「掃描 API 變更」會影響
→ 單一修改原因 ✅
```

**違反單一職責** ❌：
```text
Ticket: 實作掃描功能和離線支援
修改原因 1: 掃描 API 變更
修改原因 2: 離線儲存格式變更
→ 多個修改原因 ❌ → 應拆分
```

### 3. 驗收條件一致性

**問題**：所有驗收條件都指向同一個目標嗎？

**符合單一職責** ✅：
```yaml
ticket: 實作 startScan() 方法
acceptance:
  - startScan() 方法簽名正確
  - startScan() 回傳值類型正確
  - startScan() 單元測試通過
# 所有驗收條件都是關於 startScan() ✅
```

**違反單一職責** ❌：
```yaml
ticket: 實作掃描功能
acceptance:
  - startScan() 方法通過測試
  - stopScan() 方法通過測試
  - 離線快取功能正常
  - 批次掃描模式可用
# 驗收條件指向多個不同目標 ❌ → 應拆分
```

### 4. 依賴獨立性檢查

**問題**：如果拆成兩個 Ticket，它們是否有循環依賴？

**可以拆分** ✅（無循環依賴）：
```text
Ticket A: 實作 startScan()
Ticket B: 實作 stopScan()
依賴關係: B 依賴 A（單向）
→ 獨立 ✅ → 應拆分為兩個 Ticket
```

**不應拆分** ❌（有循環依賴）：
```text
Ticket A: 實作掃描啟動邏輯
Ticket B: 實作掃描狀態管理
依賴關係: A 需要 B 的狀態，B 需要 A 的啟動
→ 循環依賴 ❌ → 應該是同一個 Ticket
```

---

## 禁止使用的評估方式

**以下指標不能作為單一職責的判斷依據**：

| 指標 | 為什麼不使用 |
|------|-------------|
| **時間**（30 分鐘、1 小時） | 時間是結果，不是原因。單一職責的任務可能需要 5 分鐘或 2 小時 |
| **程式碼行數**（50 行、100 行） | 行數是實作細節。單一職責可能只需 10 行或需要 200 行 |
| **檔案數量**（2 個、5 個） | 檔案數量是組織方式。單一職責可能跨多個檔案 |
| **測試數量**（5 個、10 個） | 測試數量取決於邊界情況，不是職責數量 |

**正確做法**：只用「單一職責四大檢查」來評估

---

## Ticket ID 命名規範

### 格式

```text
{Version}-W{Wave}-{Seq}
```

**範例**：
- `0.15.16-W1-001` - v0.15.16, Wave 1, 第 1 個
- `0.15.16-W2-003` - v0.15.16, Wave 2, 第 3 個
- `0.16.0-W1-001` - v0.16.0, Wave 1, 第 1 個

### 命名規則

| 部分 | 說明 | 範例 |
|------|------|------|
| Version | 所屬版本號 | 0.15.16 |
| Wave | 執行波次（依賴層級） | W1, W2, W3 |
| Seq | 波次內序號（三位數） | 001, 002, 015 |

### Wave 定義

- **W1**: 無依賴，可並行執行
- **W2**: 依賴 W1 的部分 Ticket
- **W3**: 依賴 W2 的部分 Ticket
- ...以此類推

---

## 拆分範例

### 範例 1：功能拆分

**原始需求**：
```text
實作 ISBNScannerService 的 15 個測試
```

**違反單一職責**：一個 Ticket 包含 15 個不同的測試目標

**正確拆分**（每個 Ticket 只有一個目標）：
```text
0.15.16-W1-001: 實作 startScan() 方法
0.15.16-W1-002: 實作 stopScan() 方法
0.15.16-W1-003: 實作 validateIsbn10() 驗證邏輯
0.15.16-W1-004: 實作 validateIsbn13() 驗證邏輯
0.15.16-W2-005: 實作離線掃描支援（依賴 W1）
0.15.16-W2-006: 實作批次掃描模式（依賴 W1）
...
```

### 範例 2：測試拆分

**原始需求**：
```text
修復 Exception 序列化的 10 個測試
```

**正確拆分**：
```text
0.15.16-W1-001: 修復 ValidationException.toJson() 序列化
0.15.16-W1-002: 修復 AppException.toJson() 序列化
0.15.16-W1-003: 修復 CommonErrors 效能測試
0.15.16-W2-004: 修復 AppException.wrap() 工廠方法（依賴 W1-002）
...
```

### 範例 3：反例 - 不應拆分

**需求**：
```text
實作 BookRepository.save() 方法
```

**不應拆分的情況**：
```text
Ticket A: 實作 save() 方法簽名
Ticket B: 實作 save() 方法邏輯
Ticket C: 實作 save() 方法驗證
```

**原因**：這三個部分有循環依賴，簽名、邏輯、驗證是同一個職責的不同面向

**正確做法**：保持為單一 Ticket
```text
0.15.16-W1-001: 實作 BookRepository.save() 方法
```

---

## 與其他方法論的關係

### 與 ticket-design-dispatch-methodology.md 的關係

**Atomic Ticket 方法論**是 Ticket 設計的核心原則，ticket-design-dispatch-methodology.md 應引用本方法論作為拆分標準。

### 與 frontmatter-ticket-tracking-methodology.md 的關係

**Atomic Ticket** 產生的 YAML Frontmatter 定義是唯一事實源，Frontmatter 內建在 Ticket 檔案中追蹤狀態。

### 與 ticket-lifecycle-management-methodology.md 的關係

每個 **Atomic Ticket** 都遵循相同的生命週期：待執行 → 進行中 → Review → 完成

---

## 檢查清單

### 建立 Ticket 前的檢查

- [ ] **語義檢查**：能用「動詞 + 單一目標」表達嗎？
- [ ] **修改原因**：只有一個修改原因嗎？
- [ ] **驗收一致性**：所有驗收條件指向同一目標嗎？
- [ ] **依賴獨立性**：拆分後不會產生循環依賴嗎？

### 常見違反模式

| 模式 | 問題 | 修正 |
|------|------|------|
| 「實作 X 和 Y」 | 兩個目標 | 拆成兩個 Ticket |
| 「修復所有 X 測試」 | 多個測試目標 | 每個測試一個 Ticket |
| 「重構 X 並優化 Y」 | 兩個行動 | 拆成兩個 Ticket |
| 「建立 X 的完整功能」 | 模糊目標 | 明確列出每個功能 |

---

## 參考文件

- [Ticket 設計派工方法論](./ticket-design-dispatch-methodology.md)
- [Ticket 生命週期管理方法論](./ticket-lifecycle-management-methodology.md)
- [Frontmatter Ticket 追蹤方法論](./frontmatter-ticket-tracking-methodology.md)

---

*版本歷史*：
- v1.0.0 (2025-12-25): 初版，基於單一職責原則設計
