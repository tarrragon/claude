# 即時 Review 機制方法論

## 方法論概述

### 方法論定位

本方法論聚焦於**即時 Review 機制**的設計、執行和持續改善，確保程式碼品質問題在最早時機被發現和修正。

### 核心問題

本方法論解決以下 5 個核心問題：

1. **發現問題太晚**
   - 傳統「實作完成後才 review」導致偏差已形成
   - 修正成本隨時間指數增長
   - 返工時間長，影響開發節奏

2. **無法並行開發**
   - 必須等待所有任務完成才能 review
   - 累積多個 Ticket 一起 review，效率低
   - 阻礙持續整合和敏捷開發

3. **開發者體驗差**
   - 實作完成後才發現方向錯誤
   - 產生「白做了」的挫折感
   - 影響士氣和積極性

4. **Review 標準不一致**
   - 缺乏統一的 Review 檢查項目
   - Reviewer 憑經驗判斷，標準不統一
   - 容易遺漏關鍵檢查項

5. **偏差糾正流程不明確**
   - 發現問題後不知道如何處理
   - 缺乏結構化的偏差糾正流程
   - 無法有效積累經驗教訓

### 方法論目標

本方法論達成以下 5 個目標：

1. **即時發現問題**：每完成一個 Ticket 即觸發 review，問題在最早時機被發現
2. **降低修正成本**：問題範圍限定在單一 Ticket，修正成本最小化
3. **提升開發體驗**：即時回饋，快速修正，避免挫折感
4. **標準化 Review**：16 項檢查項目，確保 Review 品質一致
5. **持續改善**：結構化偏差糾正流程，積累經驗教訓

### 核心原則

本方法論基於以下 5 個核心原則：

1. **即時原則**：每完成一個 Ticket 立即觸發 review，不累積
2. **快速原則**：Review 快速完成（目標 ≤ 30 分鐘），聚焦核心問題
3. **標準化原則**：使用統一的 16 項檢查清單，確保品質一致
4. **並行原則**：Review 不阻礙後續 Ticket 開發，可並行進行
5. **改善原則**：每次偏差都記錄並總結經驗教訓

### 適用場景

本方法論適用於以下場景：

1. **敏捷開發團隊**：需要快速迭代和持續整合
2. **TDD 開發流程**：Phase 4 重構階段的品質檢查
3. **多人協作專案**：需要統一的 Review 標準
4. **高品質要求專案**：需要嚴格的品質控制機制

### 方法論結構

本方法論包含以下 6 個章節：

1. **第一章：即時 Review 核心原則** - 傳統 Review 問題分析與即時 Review 效益
2. **第二章：Review 觸發時機與機制** - 何時觸發 Review，如何快速執行
3. **第三章：Review 檢查項目詳解** - 4 大類 16 項完整檢查清單
4. **第四章：偏差糾正流程** - 發現問題後的結構化處理流程
5. **第五章：Review 記錄與追蹤** - 標準化記錄格式與持續追蹤
6. **第六章：即時 Review 最佳實踐** - 完整案例、常見問題與解決方案

---

## 第一章：即時 Review 核心原則

### 1.1 傳統 Review 問題分析

#### 問題 1：發現問題太晚

**問題描述**：
- 實作偏差已形成，程式碼結構已定型
- 需要大幅修改已完成的程式碼
- 相關測試和文檔都需要調整

**實際影響**：
```text
時間軸：
Day 1-3: 實作 5 個 Ticket（方向錯誤）
Day 4:   Review 發現架構偏差
Day 5-7: 返工修正 5 個 Ticket
Day 8:   再次 Review

總計：8 天（原本只需 4 天）
```

**修正成本分析**：

| 發現時機 | 影響範圍 | 修正時間 | 成本倍數 |
|---------|---------|---------|---------|
| **即時發現**（Ticket 完成時） | 單一 Ticket | 0.5 天 | 1x |
| **延遲 1 天**（累積 2-3 個 Ticket） | 2-3 個 Ticket | 1.5 天 | 3x |
| **延遲 3 天**（累積 5+ 個 Ticket） | 5+ 個 Ticket | 3-5 天 | 6-10x |

#### 問題 2：返工時間長

**問題描述**：
- 架構偏差已經擴散到多個檔案
- 測試程式碼也需要大幅修改
- 文檔和註解都需要重新撰寫

**實際案例**：

❌ **延後 Review 的後果**：
```dart
// Day 1: 實作 BookRepository（方向錯誤）
class BookRepository {
  // 直接依賴 SQLite（違反依賴倒置）
  final SQLiteDatabase _db;

  Future<Book> getBook(String id) {
    // 50 行程式碼...
  }
}

// Day 2-3: 基於錯誤架構繼續開發
// - 10 個測試檔案依賴 BookRepository
// - 3 個 UseCase 依賴 BookRepository
// - 5 個 UI 組件間接依賴

// Day 4: Review 發現問題
// - 需要重構成 IBookRepository + BookRepositoryImpl
// - 10 個測試需要重寫（使用 Mock）
// - 3 個 UseCase 需要調整依賴
// - 相關文檔需要更新

// 返工時間：3 天
```

✅ **即時 Review 的效果**：
```dart
// Day 1: 實作 BookRepository
class BookRepository {
  final SQLiteDatabase _db;

  Future<Book> getBook(String id) {
    // 50 行程式碼...
  }
}

// 當天 Review：發現依賴倒置問題
// 立即修正（只影響 1 個 Ticket）

// 修正後
abstract class IBookRepository {
  Future<Book> getBook(String id);
}

class BookRepositoryImpl implements IBookRepository {
  final SQLiteDatabase _db;

  @override
  Future<Book> getBook(String id) {
    // 50 行程式碼...
  }
}

// 返工時間：0.5 天
```

#### 問題 3：士氣影響大

**心理影響分析**：

| 情境 | 開發者感受 | 士氣影響 | 後續表現 |
|------|----------|---------|---------|
| **即時 Review** | 「感謝及時指出問題」 | 正面 ✅ | 積極改善 |
| **延遲 1-2 天** | 「幸好發現得早」 | 中性 ⚠️ | 正常執行 |
| **延遲 3+ 天** | 「白做了這麼多天」 | 負面 ❌ | 消極應付 |

**實際影響**：
```text
即時 Review 情境：
→ 開發者：「這個架構問題我現在就修正，只需要半天」
→ 心態：問題在掌控範圍內，積極面對

延遲 Review 情境：
→ 開發者：「我做了 3 天的程式碼全部要重寫？」
→ 心態：產生挫折感，質疑開發流程

長期影響：
→ 即時 Review：開發者信任流程，願意接受回饋
→ 延遲 Review：開發者抗拒 Review，覺得是「找麻煩」
```

#### 問題 4：無法並行

**傳統 Review 阻塞問題**：

```text
傳統流程（序列執行）：
─────────────────────────────────────────────
Ticket 1-5 實作（5 天）
           ↓
        Review（1 天）- 阻塞所有後續工作
           ↓
        修正（2 天）
           ↓
        再次 Review（1 天）
─────────────────────────────────────────────
總計：9 天

即時 Review 流程（並行執行）：
─────────────────────────────────────────────
Ticket 1（1 天）→ Review（0.2 天）→ 完成
Ticket 2（1 天）→ Review（0.2 天）→ 完成
Ticket 3（1 天）→ Review（0.2 天）→ 完成
Ticket 4（1 天）→ Review（0.2 天）→ 完成
Ticket 5（1 天）→ Review（0.2 天）→ 完成
─────────────────────────────────────────────
總計：6 天（節省 33% 時間）
```

### 1.2 即時 Review 核心原則

#### 原則 1：每完成一個 Ticket 觸發 Review

**觸發機制**：
```text
Ticket 開始
    ↓
執行實作
    ↓
自我檢查驗收條件
    ↓
標記 Ticket 為「Review 中」
    ↓
觸發 Review 通知 ← 自動觸發，無需等待
    ↓
Reviewer 執行 Review
    ↓
Review 結果（通過/未通過）
```

**關鍵點**：
- ✅ **立即觸發**：不等待其他 Ticket 完成
- ✅ **單一 Ticket**：每次只 review 一個 Ticket
- ✅ **自動通知**：系統自動通知 Reviewer
- ❌ **禁止累積**：不累積 2+ 個 Ticket 一起 review

#### 原則 2：Review 快速完成，聚焦核心問題

**時間目標**：
- **目標時間**：≤ 30 分鐘
- **最長時間**：≤ 1 小時
- **超過 1 小時**：表示 Ticket 拆分不當或問題嚴重

**聚焦策略**：

| Review 重點 | 檢查內容 | 時間分配 |
|-----------|---------|---------|
| **核心功能**（40%） | 功能是否符合 Ticket 描述 | 12 分鐘 |
| **架構合規**（30%） | Clean Architecture 分層 | 9 分鐘 |
| **測試品質**（20%） | 測試通過率 100% | 6 分鐘 |
| **文檔同步**（10%） | 基本文檔更新 | 3 分鐘 |

**不深究細節**：
- ❌ 不花時間討論命名偏好（如果不影響可讀性）
- ❌ 不花時間討論程式風格（如果符合專案規範）
- ✅ 聚焦在功能正確性、架構合規性、測試品質
- ✅ 小問題記錄下來，不阻塞 Review 通過

#### 原則 3：只 Review 當前 Ticket，不累積

**單一 Ticket Review 優勢**：

```text
單一 Ticket Review：
→ 問題範圍小，容易定位
→ 修正成本低，影響範圍可控
→ Review 速度快，不阻塞開發
→ 可並行執行多個 Ticket

累積 Review 問題：
→ 問題交織，難以定位根因
→ 修正連鎖反應，影響範圍擴大
→ Review 時間長，阻塞開發
→ 序列執行，效率低
```

**實際對比**：

| 維度 | 單一 Ticket Review | 累積 3 個 Ticket Review |
|------|------------------|----------------------|
| **Review 時間** | 30 分鐘 | 2 小時 |
| **問題定位** | 立即定位 | 需要交叉比對 |
| **修正成本** | 0.5 天 | 1.5 天 |
| **開發節奏** | 不阻塞 | 阻塞後續開發 |

#### 原則 4：發現問題立即建立修正 Ticket

**即時糾正機制**：

```text
Review 發現問題
    ↓
暫停當前 Ticket（標記為「Review 中」）
    ↓
立即建立修正 Ticket
    ↓
記錄偏差問題（描述、影響、根因）
    ↓
執行修正 Ticket
    ↓
修正完成後再次 Review
    ↓
通過 → 標記原 Ticket 為「已完成」
```

**關鍵點**：
- ✅ **立即建立**：不延後，不累積
- ✅ **記錄根因**：分析為什麼會出錯
- ✅ **總結教訓**：更新檢查清單，避免重複發生
- ❌ **禁止直接修改**：必須建立修正 Ticket，保持追蹤

### 1.3 即時 Review 效益分析

#### 效益對比表

| 維度 | 傳統 Review | 即時 Review | 改善幅度 |
|------|-----------|------------|---------|
| **問題發現時機** | 實作完成後（數天後） | 每個 Ticket 完成後（即時） | ⬆️ 快 3-5 天 |
| **修正成本** | 高（需大幅修改） | 低（只需修正單一 Ticket） | ⬇️ 降低 80% |
| **開發者體驗** | 挫折感（白做了） | 即時回饋（快速修正） | ⬆️ 提升士氣 |
| **可並行性** | 低（必須等全部完成） | 高（可持續並行開發） | ⬆️ 提升 30% 效率 |
| **問題定位** | 困難（問題交織） | 容易（範圍明確） | ⬆️ 節省 70% 時間 |
| **Review 時間** | 長（2-4 小時） | 短（≤ 30 分鐘） | ⬇️ 節省 75% 時間 |

#### 實際效益案例

**案例 1：架構偏差即時發現**

```text
情境：開發者實作 BookRepository 時違反依賴倒置原則

傳統 Review：
→ Day 1-3: 完成 3 個 Repository（都有相同問題）
→ Day 4: Review 發現架構偏差
→ Day 5-6: 重構 3 個 Repository + 10 個測試
→ 總計：6 天，成本 6x

即時 Review：
→ Day 1: 完成第 1 個 Repository
→ 當天 Review: 發現架構偏差
→ 立即修正第 1 個 Repository（0.5 天）
→ Day 2-3: 其他 2 個 Repository 使用正確架構
→ 總計：3.5 天，成本 1x

效益：節省 2.5 天（42%），避免返工挫折感
```

**案例 2：測試品質問題即時發現**

```text
情境：開發者測試覆蓋率不足，缺少邊界情況測試

傳統 Review：
→ 完成 5 個 Ticket 才 Review
→ 發現每個 Ticket 都缺少邊界測試
→ 需要補寫 15 個測試（每個 Ticket 3 個）
→ 補測試時間：2 天

即時 Review：
→ 第 1 個 Ticket Review 發現測試不足
→ 立即補寫 3 個測試（0.5 天）
→ 後續 4 個 Ticket 吸取教訓，直接寫完整測試
→ 補測試時間：0.5 天

效益：節省 1.5 天（75%），提升測試意識
```

#### 長期效益

**開發文化改善**：
1. **建立品質意識**：開發者知道每個 Ticket 都會被 review，自然提高品質標準
2. **即時學習機制**：發現問題立即修正，快速學習正確做法
3. **降低技術債務**：問題不累積，技術債務不擴散
4. **提升團隊信任**：Review 變成「幫助改善」而非「找麻煩」

**量化效益**：
- **開發速度**：提升 20-30%（減少返工時間）
- **Bug 率**：降低 40-50%（問題早期發現）
- **技術債務**：降低 60-70%（不累積問題）
- **團隊士氣**：提升 30-40%（即時回饋，減少挫折）

---

## 第二章：Review 觸發時機與機制

### 2.1 主要觸發時機

#### 觸發條件 1：每完成一個 Ticket（主要）

**觸發流程**：

```text
開發者完成 Ticket 實作
    ↓
執行自我檢查（驗收條件）
    ↓
所有驗收條件都打勾 ✅
    ↓
標記 Ticket 為「Review 中」
    ↓
系統自動觸發 Review 通知
    ↓
Reviewer 收到通知
    ↓
開始 Review（目標 ≤ 30 分鐘）
```

**自我檢查清單**（Review 前必須完成）：

- [ ] 所有驗收條件都打勾
- [ ] 所有測試 100% 通過（`dart test` 或 `flutter test`）
- [ ] `dart analyze` 0 錯誤
- [ ] 程式碼已提交到版本控制
- [ ] 工作日誌已更新

**觸發時機原則**：
- ✅ **立即觸發**：完成自我檢查後立即標記「Review 中」
- ❌ **禁止等待**：不等待其他 Ticket 完成
- ❌ **禁止累積**：不累積 2+ 個 Ticket 一起 review
- ✅ **允許並行**：可同時有多個 Ticket 在「Review 中」狀態

#### 觸發條件 2：每完成 3-5 個 Ticket（可選）

**階段性 Review 目的**：
- 檢查整體架構一致性
- 驗證模組間整合是否順暢
- 發現單一 Ticket Review 可能遺漏的整合問題

**觸發時機**：
```text
完成第 1 個 Ticket → 即時 Review ✅
完成第 2 個 Ticket → 即時 Review ✅
完成第 3 個 Ticket → 即時 Review ✅
    ↓
階段性 Review（檢查 3 個 Ticket 整體一致性）
    ↓
繼續下一個 Ticket
```

**階段性 Review 檢查項**：
- 3 個 Ticket 的架構是否一致？
- 介面設計是否協調？
- 是否有重複程式碼？
- 是否有整合問題？

**時間控制**：
- 單一 Ticket Review：≤ 30 分鐘
- 階段性 Review：≤ 1 小時

#### 觸發條件 3：每完成一個模組（可選）

**模組整合 Review 目的**：
- 驗證模組功能完整性
- 檢查模組對外介面設計
- 確認模組文檔完整

**觸發時機**：
```text
模組所有 Ticket 完成
    ↓
所有單一 Ticket Review 都通過
    ↓
觸發模組整合 Review
    ↓
檢查模組整體品質
    ↓
模組標記為「已完成」
```

**模組整合 Review 檢查項**：
- 模組功能是否完整？
- 對外介面是否清晰？
- 模組文檔是否完整？
- 整合測試是否通過？

### 2.2 Review 執行機制

#### 機制 1：Reviewer 分配

**分配策略**：

| Ticket 類型 | Reviewer | 理由 |
|-----------|----------|------|
| **架構設計類** | 架構師 | 需要架構經驗 |
| **核心業務邏輯** | 資深開發者 | 需要業務理解 |
| **一般功能實作** | 同儕開發者 | 促進知識分享 |
| **測試程式碼** | 測試專家 | 確保測試品質 |

**輪流 Review 原則**：
- 避免單一 Reviewer 過載
- 促進團隊知識共享
- 提升整體 Review 能力

#### 機制 2：Review 時間控制

**時間分配原則**：

```text
收到 Review 通知
    ↓
2 小時內開始 Review（SLA）
    ↓
30 分鐘內完成 Review（目標）
    ↓
1 小時內完成 Review（最長）
    ↓
超過 1 小時 → 升級處理
```

**超時處理**：

| 情況 | 處理方式 |
|------|---------|
| **Review 超過 1 小時** | 暫停 Review，分析原因（Ticket 太大？問題太多？） |
| **Review 延遲 > 4 小時** | 升級給 Team Lead，重新分配 Reviewer |
| **Review 積壓 > 3 個** | 增加 Reviewer 人力，加速處理 |

#### 機制 3：Review 通知系統

**通知時機**：

1. **Ticket 標記為「Review 中」**：立即通知 Reviewer
2. **Review 超過 2 小時未開始**：提醒 Reviewer
3. **Review 完成**：通知開發者結果
4. **修正 Ticket 建立**：通知開發者修正事項

**通知內容**：

```text
📋 Review 通知

Ticket: #42 實作 SQLiteBookRepository
開發者: 張三
狀態: 待 Review
預估時間: 30 分鐘
優先級: 高

[開始 Review] [查看 Ticket]
```

### 2.3 Review 快速執行策略

#### 策略 1：使用標準化檢查清單

**16 項檢查清單**：

```markdown
### Review 檢查清單 - Ticket #N

**類別 1：功能正確性（4 項）**
- [ ] Ticket 描述的功能是否實現？
- [ ] 驗收條件是否全部滿足？
- [ ] 是否有未處理的邊界情況？
- [ ] 錯誤處理是否完整？

**類別 2：架構合規性（4 項）**
- [ ] 是否符合 Clean Architecture 分層原則？
- [ ] 依賴方向是否正確（內層不依賴外層）？
- [ ] 是否使用 Interface-Driven 開發？
- [ ] 是否有架構債務產生？

**類別 3：測試通過率（4 項）**
- [ ] 相關單元測試是否 100% 通過？
- [ ] 相關整合測試是否 100% 通過？
- [ ] 測試覆蓋率是否達標（> 80%）？
- [ ] 是否有測試被 skip？

**類別 4：文檔同步性（4 項）**
- [ ] Ticket 工作日誌是否更新？
- [ ] 設計決策是否記錄？
- [ ] API 文檔是否同步？
- [ ] README 是否需要更新？
```

**使用方式**：
1. 逐項檢查，打勾確認
2. 發現問題立即記錄
3. 所有項目通過 → Review 通過
4. 任一項目未通過 → Review 未通過

#### 策略 2：聚焦核心問題

**優先級排序**：

| 優先級 | 檢查項 | 處理方式 |
|-------|-------|---------|
| **P0（阻塞）** | 功能錯誤、架構偏差、測試失敗 | 必須修正才能通過 |
| **P1（重要）** | 邊界情況缺失、文檔不完整 | 建立修正 Ticket |
| **P2（建議）** | 命名改善、程式風格 | 記錄建議，不阻塞 |

**聚焦策略**：
- ✅ P0 問題：立即要求修正
- ✅ P1 問題：建立修正 Ticket
- ⚠️ P2 問題：記錄建議，可延後處理
- ❌ 不深究：命名偏好（不影響可讀性時）、程式風格（符合規範時）

#### 策略 3：批量檢查工具

**自動化檢查工具**：

```bash
# 測試通過率自動檢查
dart test --coverage

# 靜態分析自動檢查
dart analyze

# 測試覆蓋率報告
genhtml coverage/lcov.info -o coverage/html

# 架構依賴檢查（自動化工具）
dart run dependency_validator
```

**檢查結果整合**：
```text
自動檢查通過 → 跳過相關手動檢查
自動檢查失敗 → 立即要求修正
```

### 2.4 Review 不阻塞開發

#### 並行開發策略

**允許的並行情況**：

```text
開發者 A:
Ticket #1（進行中）
Ticket #2（Review 中）← 不阻塞後續開發
Ticket #3（待執行）

開發者 A 可以：
→ 繼續執行 Ticket #3
→ 不需要等待 Ticket #2 Review 結果
→ 如果 Ticket #2 Review 未通過，稍後處理修正 Ticket
```

**WIP（Work In Progress）限制**：
- 單一開發者：≤ 2 個 Ticket 同時進行
- 其中 1 個可以是「Review 中」狀態
- 確保不過載，保持專注

#### 修正 Ticket 處理

**修正 Ticket 優先級**：

| 情況 | 處理方式 | 優先級 |
|------|---------|-------|
| **Review 發現功能錯誤** | 立即處理修正 Ticket | P0（最高） |
| **Review 發現架構偏差** | 優先處理修正 Ticket | P0（最高） |
| **Review 發現邊界缺失** | 插入當前工作，優先處理 | P1（高） |
| **Review 建議改善** | 列入待辦，可延後處理 | P2（中） |

**處理流程**：
```text
Ticket #2 Review 未通過
    ↓
建立修正 Ticket #2.1
    ↓
評估優先級
    ├─ P0/P1 → 立即處理（暫停 Ticket #3）
    └─ P2 → 列入待辦（繼續 Ticket #3）
    ↓
修正 Ticket #2.1 完成
    ↓
再次 Review Ticket #2
    ↓
通過 → 標記 Ticket #2 為「已完成」
```

---

## 第三章：Review 檢查項目詳解

### 3.1 功能正確性檢查（4 項）

#### 檢查項 1：Ticket 描述的功能是否實現？

**檢查方法**：
1. 打開 Ticket，閱讀「目標」欄位
2. 對照實際程式碼，確認功能實現
3. 執行程式，驗證功能運作

**通過標準**：
- ✅ 功能完全符合 Ticket 描述
- ✅ 無多餘功能（避免 over-engineering）
- ✅ 無缺失功能

**常見問題**：

❌ **功能不完整**：
```dart
// Ticket 描述：實作 Book 的 CRUD 功能
// 問題：只實作了 Create 和 Read，缺少 Update 和 Delete

class BookRepository {
  Future<Book> create(Book book) { /* ... */ }
  Future<Book?> getById(String id) { /* ... */ }
  // ❌ 缺少 update() 和 delete()
}
```

❌ **多餘功能**：
```dart
// Ticket 描述：實作 Book 的基本查詢
// 問題：額外實作了複雜的搜尋功能（Ticket 沒有要求）

class BookRepository {
  Future<Book?> getById(String id) { /* ... */ }

  // ❌ Ticket 沒有要求的複雜搜尋功能
  Future<List<Book>> advancedSearch({
    String? title,
    String? author,
    DateRange? publishDate,
    List<String>? tags,
  }) { /* ... */ }
}
```

✅ **正確實作**：
```dart
// Ticket 描述：實作 Book 的 CRUD 功能
// ✅ 完整實作 4 個方法，無多餘功能

abstract class IBookRepository {
  Future<Book> create(Book book);
  Future<Book?> getById(String id);
  Future<Book> update(Book book);
  Future<void> delete(String id);
}

class BookRepositoryImpl implements IBookRepository {
  @override
  Future<Book> create(Book book) { /* ... */ }

  @override
  Future<Book?> getById(String id) { /* ... */ }

  @override
  Future<Book> update(Book book) { /* ... */ }

  @override
  Future<void> delete(String id) { /* ... */ }
}
```

#### 檢查項 2：驗收條件是否全部滿足？

**檢查方法**：
1. 打開 Ticket，查看「驗收條件」欄位
2. 逐項檢查每個條件是否打勾 ✅
3. 實際執行測試，驗證條件確實滿足

**通過標準**：
- ✅ 所有驗收條件都打勾
- ✅ 打勾的條件確實滿足（不是假打勾）
- ✅ 有測試證明條件滿足

**驗收條件範例**：

```markdown
### 驗收條件

- [x] `BookRepositoryImpl` 實作完成，符合 `IBookRepository` 介面
- [x] `create()` 方法正確插入書籍資料，回傳新增的 Book 物件
- [x] `getById()` 方法正確查詢書籍資料，找不到時回傳 null
- [x] `update()` 和 `delete()` 方法實作完成且功能正確
- [x] 單元測試覆蓋所有 CRUD 方法，測試通過率 100%
- [x] `dart analyze` 0 錯誤，程式碼符合專案規範
```

**Review 驗證**：
- 逐項檢查每個條件
- 執行測試確認功能正確
- 執行 `dart analyze` 確認 0 錯誤

#### 檢查項 3：是否有未處理的邊界情況？

**常見邊界情況**：

| 情境 | 需要處理的邊界 |
|------|--------------|
| **字串輸入** | null, empty, 超長字串, 特殊字元 |
| **數值輸入** | 0, 負數, 極大值, 極小值 |
| **列表輸入** | null, empty list, 單一元素, 大量元素 |
| **日期輸入** | null, 過去日期, 未來日期, 無效日期 |

**檢查方法**：
1. 識別所有輸入參數
2. 列出每個參數的邊界情況
3. 檢查程式碼是否處理這些情況
4. 檢查測試是否覆蓋這些情況

**常見問題**：

❌ **未處理 null**：
```dart
Future<Book> create(Book book) async {
  // ❌ 未檢查 book 是否為 null
  final id = await _db.insert('books', book.toMap());
  return book.copyWith(id: id);
}
```

❌ **未處理 empty**：
```dart
Future<Book?> getById(String id) async {
  // ❌ 未檢查 id 是否為空字串
  final result = await _db.query('books', where: 'id = ?', whereArgs: [id]);
  if (result.isEmpty) return null;
  return Book.fromMap(result.first);
}
```

✅ **正確處理邊界**：
```dart
Future<Book> create(Book book) async {
  // ✅ 檢查 null 和驗證資料
  ArgumentError.checkNotNull(book, 'book');

  if (book.title.isEmpty) {
    throw ValidationException.requiredField('title');
  }

  if (book.isbn.isEmpty) {
    throw ValidationException.requiredField('isbn');
  }

  final id = await _db.insert('books', book.toMap());
  return book.copyWith(id: id);
}

Future<Book?> getById(String id) async {
  // ✅ 檢查 id 是否為空
  if (id.isEmpty) {
    throw ValidationException.requiredField('id');
  }

  final result = await _db.query('books', where: 'id = ?', whereArgs: [id]);
  if (result.isEmpty) return null;
  return Book.fromMap(result.first);
}
```

#### 檢查項 4：錯誤處理是否完整？

**檢查方法**：
1. 識別所有可能拋出異常的操作
2. 檢查是否有 try-catch 處理
3. 檢查異常類型是否正確
4. 檢查異常訊息是否清晰

**錯誤處理標準**：

| 錯誤類型 | 處理方式 | 異常類別 |
|---------|---------|---------|
| **資料驗證錯誤** | 拋出 ValidationException | `ValidationException` |
| **資料庫錯誤** | 拋出 StorageException | `StorageException` |
| **網路錯誤** | 拋出 NetworkException | `NetworkException` |
| **業務邏輯錯誤** | 拋出 BusinessException | `BusinessException` |

**常見問題**：

❌ **未處理異常**：
```dart
Future<Book> create(Book book) async {
  // ❌ 直接呼叫，沒有 try-catch
  final id = await _db.insert('books', book.toMap());
  return book.copyWith(id: id);
}
```

❌ **異常類型不明確**：
```dart
Future<Book> create(Book book) async {
  try {
    final id = await _db.insert('books', book.toMap());
    return book.copyWith(id: id);
  } catch (e) {
    // ❌ 使用通用 Exception，無法區分錯誤類型
    throw Exception('新增書籍失敗: $e');
  }
}
```

✅ **正確錯誤處理**：
```dart
Future<Book> create(Book book) async {
  try {
    // 驗證資料
    if (book.title.isEmpty) {
      throw ValidationException.requiredField('title');
    }

    // 檢查是否已存在
    final existing = await _checkDuplicate(book.isbn);
    if (existing != null) {
      throw BusinessException.duplicate(book.isbn);
    }

    // 插入資料
    final id = await _db.insert('books', book.toMap());
    return book.copyWith(id: id);

  } on ValidationException {
    rethrow; // 重新拋出驗證異常
  } on BusinessException {
    rethrow; // 重新拋出業務異常
  } catch (e) {
    // 包裝資料庫異常
    throw StorageException.database(
      message: '新增書籍失敗',
      originalError: e,
    );
  }
}
```

### 3.2 架構合規性檢查（4 項）

#### 檢查項 5：是否符合 Clean Architecture 分層原則？

**Clean Architecture 分層**：

```text
┌─────────────────────────────────┐
│      Presentation Layer         │ ← UI, State Management
├─────────────────────────────────┤
│      Application Layer          │ ← UseCases, Services
├─────────────────────────────────┤
│        Domain Layer             │ ← Entities, Interfaces
├─────────────────────────────────┤
│     Infrastructure Layer        │ ← Repository Impl, API
└─────────────────────────────────┘
```

**檢查方法**：
1. 確認檔案位置是否正確
2. 確認依賴方向是否正確（外層→內層）
3. 確認是否有跨層依賴

**檔案位置標準**：

| 層級 | 路徑 | 內容 |
|------|------|------|
| **Domain** | `lib/domains/{domain}/entities/` | Entity 類別 |
| **Domain** | `lib/domains/{domain}/repositories/` | Repository Interface |
| **Application** | `lib/domains/{domain}/use_cases/` | UseCase 類別 |
| **Infrastructure** | `lib/infrastructure/repositories/` | Repository 實作 |
| **Presentation** | `lib/presentation/{feature}/` | UI 和 State |

**常見問題**：

❌ **檔案位置錯誤**：
```text
❌ lib/repositories/book_repository.dart
   （應該放在 infrastructure 層）

✅ lib/infrastructure/repositories/book_repository_impl.dart
   （正確位置）
```

❌ **依賴方向錯誤**：
```dart
// ❌ Domain 層依賴 Infrastructure 層（錯誤）
// lib/domains/library/entities/book.dart

import 'package:book_overview_app/infrastructure/database/sqlite_database.dart';

class Book {
  final SQLiteDatabase _db; // ❌ Entity 不應依賴具體實作
}
```

✅ **正確分層**：
```dart
// ✅ Domain 層定義介面
// lib/domains/library/repositories/i_book_repository.dart

abstract class IBookRepository {
  Future<Book> create(Book book);
  Future<Book?> getById(String id);
}

// ✅ Infrastructure 層實作介面
// lib/infrastructure/repositories/book_repository_impl.dart

import 'package:book_overview_app/domains/library/repositories/i_book_repository.dart';

class BookRepositoryImpl implements IBookRepository {
  final SQLiteDatabase _db;

  @override
  Future<Book> create(Book book) { /* ... */ }

  @override
  Future<Book?> getById(String id) { /* ... */ }
}
```

#### 檢查項 6：依賴方向是否正確（內層不依賴外層）？

**依賴方向原則**：

```text
Presentation → Application → Domain ← Infrastructure
                                ↑
                            只依賴介面
```

**檢查方法**：
1. 檢查每個檔案的 import 語句
2. 確認沒有內層依賴外層
3. 確認 Infrastructure 只依賴 Domain Interface

**常見問題**：

❌ **Domain 依賴 Infrastructure**：
```dart
// ❌ lib/domains/library/use_cases/add_book_use_case.dart

import 'package:book_overview_app/infrastructure/repositories/book_repository_impl.dart';

class AddBookUseCase {
  final BookRepositoryImpl _repository; // ❌ 依賴具體實作

  AddBookUseCase(this._repository);
}
```

❌ **Domain 依賴 Presentation**：
```dart
// ❌ lib/domains/library/entities/book.dart

import 'package:flutter/material.dart'; // ❌ Domain 依賴 UI 框架

class Book {
  final Color coverColor; // ❌ 使用 UI 類別
}
```

✅ **正確依賴方向**：
```dart
// ✅ lib/domains/library/use_cases/add_book_use_case.dart

import 'package:book_overview_app/domains/library/repositories/i_book_repository.dart';

class AddBookUseCase {
  final IBookRepository _repository; // ✅ 依賴介面

  AddBookUseCase(this._repository);

  Future<Book> execute(Book book) async {
    return await _repository.create(book);
  }
}

// ✅ lib/infrastructure/repositories/book_repository_impl.dart

import 'package:book_overview_app/domains/library/repositories/i_book_repository.dart';

class BookRepositoryImpl implements IBookRepository {
  // ✅ 實作介面，正確依賴方向
}
```

#### 檢查項 7：是否使用 Interface-Driven 開發？

**Interface-Driven 原則**：
- 外層依賴 Interface，不直接依賴實作
- 所有跨層依賴都透過 Interface
- 方便測試和替換實作

**檢查方法**：
1. 檢查 UseCase 是否依賴 Repository Interface
2. 檢查 UI 是否依賴 UseCase Interface（如果有定義）
3. 檢查依賴注入是否注入 Interface

**常見問題**：

❌ **直接依賴實作**：
```dart
// ❌ lib/domains/library/use_cases/add_book_use_case.dart

import 'package:book_overview_app/infrastructure/repositories/book_repository_impl.dart';

class AddBookUseCase {
  final BookRepositoryImpl _repository; // ❌ 直接依賴實作

  AddBookUseCase(this._repository);
}
```

❌ **依賴注入錯誤**：
```dart
// ❌ 依賴注入時注入具體實作而非介面

GetIt.instance.registerSingleton<AddBookUseCase>(
  AddBookUseCase(BookRepositoryImpl(database)), // ❌ 直接傳入實作
);
```

✅ **正確 Interface-Driven**：
```dart
// ✅ 定義 Repository Interface
// lib/domains/library/repositories/i_book_repository.dart

abstract class IBookRepository {
  Future<Book> create(Book book);
  Future<Book?> getById(String id);
}

// ✅ UseCase 依賴 Interface
// lib/domains/library/use_cases/add_book_use_case.dart

import 'package:book_overview_app/domains/library/repositories/i_book_repository.dart';

class AddBookUseCase {
  final IBookRepository _repository; // ✅ 依賴介面

  AddBookUseCase(this._repository);

  Future<Book> execute(Book book) async {
    return await _repository.create(book);
  }
}

// ✅ 依賴注入配置
// lib/core/di/dependency_injection.dart

void setupDependencies() {
  // 註冊 Repository 實作
  GetIt.instance.registerLazySingleton<IBookRepository>(
    () => BookRepositoryImpl(GetIt.instance<SQLiteDatabase>()),
  );

  // 註冊 UseCase
  GetIt.instance.registerFactory<AddBookUseCase>(
    () => AddBookUseCase(GetIt.instance<IBookRepository>()), // ✅ 注入介面
  );
}
```

#### 檢查項 8：是否有架構債務產生？

**架構債務定義**：
- 違反 SOLID 原則
- 違反 Clean Architecture 分層
- 產生緊耦合
- 缺乏抽象和擴展性

**常見架構債務**：

| 債務類型 | 具體表現 | 嚴重程度 |
|---------|---------|---------|
| **違反單一職責** | 一個類別做太多事 | P0（高） |
| **違反開放封閉** | 修改現有程式碼而非擴展 | P1（中） |
| **違反依賴倒置** | 依賴具體實作而非抽象 | P0（高） |
| **緊耦合** | 類別間直接依賴 | P0（高） |
| **重複程式碼** | 相同邏輯出現多次 | P1（中） |

**檢查方法**：
1. 檢查類別職責是否單一
2. 檢查是否有緊耦合
3. 檢查是否有重複程式碼
4. 檢查是否違反 SOLID 原則

**常見問題**：

❌ **違反單一職責**：
```dart
// ❌ BookService 做太多事（資料存取 + 業務邏輯 + 格式化）

class BookService {
  final SQLiteDatabase _db;

  // 資料存取
  Future<Book> saveBook(Book book) async {
    final id = await _db.insert('books', book.toMap());
    return book.copyWith(id: id);
  }

  // 業務邏輯
  Future<bool> isBookAvailable(String isbn) async {
    final book = await getBookByIsbn(isbn);
    return book != null && book.stock > 0;
  }

  // 格式化
  String formatBookTitle(Book book) {
    return '${book.title} (${book.author})';
  }
}
```

✅ **正確職責劃分**：
```dart
// ✅ Repository：只負責資料存取
class BookRepositoryImpl implements IBookRepository {
  final SQLiteDatabase _db;

  @override
  Future<Book> create(Book book) async {
    final id = await _db.insert('books', book.toMap());
    return book.copyWith(id: id);
  }

  @override
  Future<Book?> getByIsbn(String isbn) async {
    final result = await _db.query('books', where: 'isbn = ?', whereArgs: [isbn]);
    if (result.isEmpty) return null;
    return Book.fromMap(result.first);
  }
}

// ✅ UseCase：只負責業務邏輯
class CheckBookAvailabilityUseCase {
  final IBookRepository _repository;

  CheckBookAvailabilityUseCase(this._repository);

  Future<bool> execute(String isbn) async {
    final book = await _repository.getByIsbn(isbn);
    return book != null && book.stock > 0;
  }
}

// ✅ Formatter：只負責格式化
class BookFormatter {
  static String formatTitle(Book book) {
    return '${book.title} (${book.author})';
  }
}
```

### 3.3 測試通過率檢查（4 項）

#### 檢查項 9：相關單元測試是否 100% 通過？

**檢查方法**：
```bash
# 執行單元測試
dart test

# 或針對特定檔案
dart test test/domains/library/use_cases/add_book_use_case_test.dart
```

**通過標準**：
- ✅ 所有測試通過，0 失敗
- ✅ 無 skip 的測試
- ✅ 測試執行時間合理（< 1 分鐘）

**常見問題**：

❌ **測試失敗**：
```text
00:01 +0 -1: test/domains/library/use_cases/add_book_use_case_test.dart: should save book successfully [E]
  Expected: <Instance of 'Book'>
  Actual: <null>
```

❌ **測試被 skip**：
```dart
test('should save book successfully', () {
  // 測試邏輯
}, skip: 'TODO: fix later'); // ❌ 不允許 skip
```

✅ **所有測試通過**：
```text
00:05 +10: All tests passed!
```

#### 檢查項 10：相關整合測試是否 100% 通過？

**整合測試範圍**：
- 跨層測試（UseCase + Repository + Database）
- API 整合測試
- UI 整合測試（Widget Test）

**檢查方法**：
```bash
# 執行整合測試
flutter test integration_test/

# 或執行 Widget 測試
flutter test test/presentation/
```

**通過標準**：
- ✅ 所有整合測試通過
- ✅ 測試涵蓋關鍵整合路徑
- ✅ 測試資料隔離（不影響其他測試）

#### 檢查項 11：測試覆蓋率是否達標？

**覆蓋率標準**：
- **目標**：> 80%
- **核心業務邏輯**：> 90%
- **UI 層**：> 60%（允許較低）

**檢查方法**：
```bash
# 生成覆蓋率報告
dart test --coverage=coverage
genhtml coverage/lcov.info -o coverage/html

# 查看覆蓋率
open coverage/html/index.html
```

**通過標準**：
- ✅ 整體覆蓋率 > 80%
- ✅ 核心 Domain/Application 層 > 90%
- ✅ 關鍵路徑 100% 覆蓋

#### 檢查項 12：是否有測試被 skip？

**檢查方法**：
```bash
# 搜尋 skip 關鍵字
grep -r "skip:" test/
grep -r ".skip" test/
```

**通過標準**：
- ✅ 無 skip 的測試
- ✅ 所有測試都執行

**不允許的情況**：
```dart
// ❌ 不允許
test('should handle error', () {
  // ...
}, skip: 'TODO: implement error handling');

// ❌ 不允許
group('Error handling', () {
  // ...
}).skip('Complex to implement');
```

### 3.4 文檔同步性檢查（4 項）

#### 檢查項 13：Ticket 工作日誌是否更新？

**工作日誌內容**：
- 執行過程記錄
- 遇到的問題和解決方法
- 設計決策和理由
- 完成時間

**檢查方法**：
1. 打開對應的 Ticket 工作日誌
2. 確認記錄執行過程
3. 確認記錄設計決策

**通過標準**：
- ✅ 工作日誌已更新
- ✅ 記錄關鍵決策和理由
- ✅ 記錄遇到的問題和解決方法

#### 檢查項 14：設計決策是否記錄？

**需要記錄的設計決策**：
- 架構選擇（為什麼這樣設計？）
- 技術選型（為什麼選這個方案？）
- 重構決策（為什麼需要重構？）

**記錄格式**：
```markdown
### 設計決策

**決策 1：使用 Repository Pattern**
- **理由**：分離資料存取邏輯，方便測試和替換實作
- **替代方案**：直接在 UseCase 中存取資料庫（耦合度高，不易測試）
- **選擇原因**：符合 Clean Architecture 原則，提升可測試性

**決策 2：使用 Interface-Driven 開發**
- **理由**：UseCase 依賴 IBookRepository 介面而非具體實作
- **替代方案**：直接依賴 BookRepositoryImpl（緊耦合）
- **選擇原因**：方便 Mock 測試，符合依賴倒置原則
```

#### 檢查項 15：API 文檔是否同步？

**API 文檔要求**：
- 公開類別必須有 dartdoc 註解
- 公開方法必須有參數說明
- 公開方法必須有回傳值說明
- 必須有使用範例

**檢查方法**：
```dart
// ✅ 完整的 API 文檔

/// Book 實體類別，代表一本書籍
///
/// 包含書籍的基本資訊，如標題、作者、ISBN 等。
///
/// 使用範例：
/// ```dart
/// final book = Book(
///   id: '1',
///   title: 'Clean Code',
///   author: 'Robert C. Martin',
///   isbn: '978-0132350884',
/// );
/// ```
class Book {
  /// 書籍唯一識別碼
  final String id;

  /// 書籍標題
  final String title;

  /// 書籍作者
  final String author;

  /// ISBN 國際標準書號
  final String isbn;

  /// 建立 Book 實例
  ///
  /// 參數：
  /// - [id]: 書籍唯一識別碼，不可為空
  /// - [title]: 書籍標題，不可為空
  /// - [author]: 書籍作者，不可為空
  /// - [isbn]: ISBN 國際標準書號，不可為空
  Book({
    required this.id,
    required this.title,
    required this.author,
    required this.isbn,
  });
}
```

#### 檢查項 16：README 是否需要更新？

**需要更新 README 的情況**：
- 新增了公開 API
- 變更了使用方式
- 新增了依賴項
- 變更了設定方式

**檢查方法**：
1. 確認是否有上述變更
2. 如有變更，更新 README
3. 確認範例程式碼仍然有效

---

## 第四章：偏差糾正流程

### 4.1 偏差糾正流程概述

#### 流程圖

```text
Review 發現偏差
    ↓
暫停當前 Ticket（標記為「Review 中」）
    ↓
記錄偏差問題
├─ 偏差描述
├─ 影響範圍
└─ 根因分析
    ↓
分析根因類型
├─ 理解錯誤？ → 釐清需求，建立修正 Ticket
├─ 技術問題？ → 尋求技術支援，建立修正 Ticket
└─ 架構問題？ → 修正架構設計，建立修正 Ticket
    ↓
建立修正 Ticket
├─ Ticket #N.1: 修正 [問題描述]
├─ 優先級：P0/P1/P2
└─ 參考：原 Ticket #N
    ↓
執行修正 Ticket
    ↓
修正完成後再次 Review
├─ 通過 → 標記原 Ticket #N 為「已完成」
└─ 未通過 → 重複偏差糾正流程
    ↓
總結經驗教訓
├─ 更新檢查清單（避免重複發生）
├─ 更新開發指引
└─ 分享團隊經驗
```

### 4.2 偏差記錄格式

#### 標準格式

```markdown
### Review 偏差記錄 #N

**發現時間**：2025-10-10 14:30

**原 Ticket**：#42 實作 SQLiteBookRepository

**偏差類型**：架構偏差 / 功能錯誤 / 測試缺失 / 文檔不完整

**偏差描述**：
[清楚描述發現的問題]

**影響範圍**：
- [受影響的檔案、模組、功能]
- [需要修正的測試]
- [需要更新的文檔]

**根因分析**：
[為什麼會發生這個問題？]

**根因分類**：
- [ ] 理解錯誤（需求不清楚）
- [ ] 技術問題（不知道如何實作）
- [ ] 架構問題（設計不當）
- [ ] 測試問題（測試不完整）
- [ ] 文檔問題（文檔不同步）

**糾正措施**：
- [x] 建立修正 Ticket #42.1
- [x] 釐清需求（如果是理解錯誤）
- [x] 尋求技術支援（如果是技術問題）
- [x] 修正架構設計（如果是架構問題）

**責任歸屬**：
- 開發者：[責任分析]
- Reviewer：[是否應該更早發現]
- 需求方：[需求是否清楚]

**經驗教訓**：
[從這次偏差中學到什麼？如何避免重複發生？]

**檢查清單更新**：
- [ ] 更新 Review 檢查清單
- [ ] 更新開發指引
- [ ] 分享團隊經驗
```

#### 偏差記錄範例

**範例 1：架構偏差**

```markdown
### Review 偏差記錄 #1

**發現時間**：2025-10-10 14:30

**原 Ticket**：#42 實作 SQLiteBookRepository

**偏差類型**：架構偏差

**偏差描述**：
實作的 Repository 直接使用具體類別 `SQLiteBookRepository`，未定義 Interface `IBookRepository`，導致 UseCase 無法透過依賴注入替換實作，違反依賴倒置原則。

**影響範圍**：
- `lib/infrastructure/repositories/book_repository.dart`（需要重構）
- `lib/domains/library/use_cases/add_book_use_case.dart`（需要調整依賴）
- `test/domains/library/use_cases/add_book_use_case_test.dart`（需要使用 Mock）

**根因分析**：
開發者未遵循 Clean Architecture 的 Interface-Driven 開發原則，直接實作具體類別而未先定義介面。

**根因分類**：
- [x] 架構問題（未遵循 Clean Architecture 原則）
- [ ] 理解錯誤
- [ ] 技術問題
- [ ] 測試問題
- [ ] 文檔問題

**糾正措施**：
- [x] 建立修正 Ticket #42.1：定義 IBookRepository 介面
- [x] 建立修正 Ticket #42.2：重構 BookRepository 實作 IBookRepository
- [x] 建立修正 Ticket #42.3：調整 UseCase 依賴 IBookRepository
- [x] 更新測試使用 Mock IBookRepository

**責任歸屬**：
- 開發者：未遵循 Clean Architecture 原則（主要責任）
- Reviewer：應在 Review 中即時發現（次要責任）

**經驗教訓**：
1. 實作 Repository 前必須先定義 Interface
2. Review 時必須檢查是否使用 Interface-Driven 開發
3. 將「定義 Interface」加入 Repository 實作的檢查清單

**檢查清單更新**：
- [x] 更新 Review 檢查清單：新增「是否先定義 Interface」檢查項
- [x] 更新開發指引：強調 Interface-Driven 開發
- [x] 分享團隊經驗：在 Standup 中討論此案例
```

**範例 2：測試缺失**

```markdown
### Review 偏差記錄 #2

**發現時間**：2025-10-11 09:15

**原 Ticket**：#45 實作 Book 驗證邏輯

**偏差類型**：測試缺失

**偏差描述**：
實作的 Book 驗證邏輯缺少邊界情況測試，包括：
- 書名為空字串的測試
- ISBN 格式錯誤的測試
- 頁數為負數的測試

**影響範圍**：
- `test/domains/library/entities/book_test.dart`（需要補充測試）

**根因分析**：
開發者只測試了正常情況（Happy Path），未考慮邊界情況和異常情況。

**根因分類**：
- [ ] 架構問題
- [ ] 理解錯誤
- [ ] 技術問題
- [x] 測試問題（測試不完整）
- [ ] 文檔問題

**糾正措施**：
- [x] 建立修正 Ticket #45.1：補充邊界情況測試
- [x] 明確測試覆蓋標準：必須包含邊界和異常情況

**責任歸屬**：
- 開發者：測試不完整（主要責任）
- Reviewer：應在 Review 中檢查測試覆蓋率（次要責任）

**經驗教訓**：
1. 測試必須包含邊界情況（null, empty, 負數, 極值）
2. Review 時必須檢查測試是否涵蓋邊界情況
3. 建立邊界情況測試檢查清單

**檢查清單更新**：
- [x] 更新 Review 檢查清單：新增「邊界情況測試檢查」
- [x] 更新測試指引：明確邊界情況測試標準
- [x] 建立邊界情況測試範本
```

### 4.3 根因分析方法

#### 根因分類

| 根因類型 | 具體表現 | 糾正措施 |
|---------|---------|---------|
| **理解錯誤** | 需求理解偏差、Ticket 描述不清 | 釐清需求，重新執行 |
| **技術問題** | 不知道如何實作、技術選型錯誤 | 尋求技術支援，研究方案 |
| **架構問題** | 違反 Clean Architecture、緊耦合 | 修正架構設計，重構程式碼 |
| **測試問題** | 測試不完整、測試品質差 | 補充測試，提升測試品質 |
| **文檔問題** | 文檔不同步、註解缺失 | 更新文檔，補充註解 |

#### 5 Why 分析法

**範例：為什麼 Repository 沒有定義 Interface？**

```text
Why 1: 為什麼 Repository 沒有定義 Interface？
→ 因為開發者直接實作具體類別

Why 2: 為什麼開發者直接實作具體類別？
→ 因為開發者不知道需要先定義 Interface

Why 3: 為什麼開發者不知道需要先定義 Interface？
→ 因為開發指引未明確說明 Interface-Driven 開發

Why 4: 為什麼開發指引未明確說明？
→ 因為我們假設開發者都知道 Clean Architecture

Why 5: 為什麼假設開發者都知道？
→ 因為我們缺少新人訓練和開發規範檢查

根本原因：
- 缺少新人訓練機制
- 缺少開發規範檢查清單
- 缺少 Review 時的架構檢查

糾正措施：
- 建立新人訓練課程
- 建立開發規範檢查清單
- 更新 Review 檢查清單，強化架構檢查
```

### 4.4 修正 Ticket 建立標準

#### 修正 Ticket 格式

```markdown
## Ticket #N.1: 修正 [問題描述]

### 1. 背景（Background）
**原 Ticket**：#N [原 Ticket 標題]
**Review 偏差記錄**：#N
**偏差類型**：架構偏差 / 功能錯誤 / 測試缺失 / 文檔不完整

### 2. 目標（Objective）
修正 Review 中發現的 [具體問題描述]

### 3. 步驟（Steps）
1. [修正步驟 1]
2. [修正步驟 2]
3. [修正步驟 3]

### 4. 驗收條件（Acceptance Criteria）
- [ ] [修正完成的驗證條件 1]
- [ ] [修正完成的驗證條件 2]
- [ ] [修正完成的驗證條件 3]
- [ ] 再次 Review 通過

### 5. 參考文件（References）
- 原 Ticket #N
- Review 偏差記錄 #N
- [相關設計文檔]

### 6. 優先級（Priority）
- P0（阻塞）/ P1（重要）/ P2（建議）
```

#### 修正 Ticket 範例

```markdown
## Ticket #42.1: 修正 BookRepository 缺少 Interface 定義

### 1. 背景（Background）
**原 Ticket**：#42 實作 SQLiteBookRepository
**Review 偏差記錄**：#1
**偏差類型**：架構偏差

Review 發現 BookRepository 直接實作具體類別，未定義 Interface，違反依賴倒置原則。

### 2. 目標（Objective）
定義 IBookRepository 介面，並重構 BookRepository 實作該介面，確保 UseCase 依賴介面而非具體實作。

### 3. 步驟（Steps）
1. 定義 `IBookRepository` 介面（位置：`lib/domains/library/repositories/i_book_repository.dart`）
2. 重構 `BookRepository` 實作 `IBookRepository`（重命名為 `BookRepositoryImpl`）
3. 調整 `AddBookUseCase` 依賴 `IBookRepository` 介面
4. 更新測試使用 Mock `IBookRepository`
5. 更新依賴注入配置

### 4. 驗收條件（Acceptance Criteria）
- [ ] `IBookRepository` 介面定義完成，包含所有必要方法
- [ ] `BookRepositoryImpl` 正確實作 `IBookRepository`
- [ ] `AddBookUseCase` 依賴 `IBookRepository` 而非具體實作
- [ ] 測試使用 Mock `IBookRepository`，所有測試通過
- [ ] `dart analyze` 0 錯誤
- [ ] 再次 Review 通過

### 5. 參考文件（References）
- 原 Ticket #42
- Review 偏差記錄 #1
- Clean Architecture 開發指引

### 6. 優先級（Priority）
- P0（阻塞）- 架構問題必須立即修正
```

### 4.5 持續改善機制

#### 檢查清單更新

**每次偏差糾正後必須更新檢查清單**：

```markdown
### 檢查清單更新記錄

**更新時間**：2025-10-10 15:00

**觸發偏差**：Review 偏差記錄 #1（BookRepository 缺少 Interface）

**更新內容**：
- 在「架構合規性檢查」中新增：
  - [ ] Repository 是否先定義 Interface？
  - [ ] UseCase 是否依賴 Interface 而非具體實作？

**更新理由**：
避免重複發生 Repository 缺少 Interface 的架構偏差。

**影響範圍**：
所有 Repository 實作的 Review 都必須檢查此項。
```

#### 經驗分享機制

**團隊經驗分享會（每週）**：

```markdown
### 經驗分享會議記錄

**日期**：2025-10-12

**主題**：Review 偏差案例分享

**案例 1：BookRepository 缺少 Interface**
- **偏差描述**：Repository 未定義 Interface，違反依賴倒置
- **根本原因**：缺少 Interface-Driven 開發意識
- **糾正措施**：更新檢查清單，強化架構檢查
- **經驗教訓**：實作 Repository 前必須先定義 Interface

**案例 2：測試缺少邊界情況**
- **偏差描述**：測試只覆蓋正常情況，缺少邊界測試
- **根本原因**：測試標準不明確
- **糾正措施**：建立邊界情況測試檢查清單
- **經驗教訓**：測試必須包含 null, empty, 負數, 極值

**行動項**：
- [ ] 所有成員閱讀更新的檢查清單
- [ ] 下次 Review 實踐新的檢查項
- [ ] 兩週後檢視改善效果
```

---

## 第五章：Review 記錄與追蹤

### 5.1 Review 記錄標準格式

#### 完整記錄格式

```markdown
### Review 記錄 - Ticket #N

**Review 時間**：2025-10-10 15:00

**Reviewer**：張三

**Ticket 標題**：[Ticket 完整標題]

**Review 結果**：✅ 通過 / ❌ 未通過

**檢查項目**：

**類別 1：功能正確性（4/4 通過）**
- [x] Ticket 描述的功能是否實現？
- [x] 驗收條件是否全部滿足？
- [x] 是否有未處理的邊界情況？
- [x] 錯誤處理是否完整？

**類別 2：架構合規性（4/4 通過）**
- [x] 是否符合 Clean Architecture 分層原則？
- [x] 依賴方向是否正確（內層不依賴外層）？
- [x] 是否使用 Interface-Driven 開發？
- [x] 是否有架構債務產生？

**類別 3：測試通過率（4/4 通過）**
- [x] 相關單元測試是否 100% 通過？
- [x] 相關整合測試是否 100% 通過？
- [x] 測試覆蓋率是否達標（> 80%）？
- [x] 是否有測試被 skip？

**類別 4：文檔同步性（4/4 通過）**
- [x] Ticket 工作日誌是否更新？
- [x] 設計決策是否記錄？
- [x] API 文檔是否同步？
- [x] README 是否需要更新？

**發現問題**：
- 無（如果有，列出問題清單）

**建議改善**（可選）：
- [建議 1]
- [建議 2]

**Review 時間**：30 分鐘

**下一步行動**：
- [x] 標記 Ticket 為「已完成」
- [x] 更新主版本日誌索引
```

### 5.2 Review 記錄範例

#### 範例 1：Review 通過

```markdown
### Review 記錄 - Ticket #42

**Review 時間**：2025-10-10 15:00

**Reviewer**：張三

**Ticket 標題**：實作 SQLiteBookRepository

**Review 結果**：✅ 通過

**檢查項目**：

**類別 1：功能正確性（4/4 通過）**
- [x] Ticket 描述的功能是否實現？
  → 確認：4 個 CRUD 方法完整實作
- [x] 驗收條件是否全部滿足？
  → 確認：所有 6 個驗收條件都打勾且確實滿足
- [x] 是否有未處理的邊界情況？
  → 確認：處理了 null、empty、異常輸入
- [x] 錯誤處理是否完整？
  → 確認：使用 ValidationException、StorageException 處理錯誤

**類別 2：架構合規性（4/4 通過）**
- [x] 是否符合 Clean Architecture 分層原則？
  → 確認：位於 Infrastructure 層，實作 Domain 層介面
- [x] 依賴方向是否正確（內層不依賴外層）？
  → 確認：只依賴 Domain 層的 IBookRepository 介面
- [x] 是否使用 Interface-Driven 開發？
  → 確認：實作 IBookRepository 介面
- [x] 是否有架構債務產生？
  → 確認：無架構債務，符合 SOLID 原則

**類別 3：測試通過率（4/4 通過）**
- [x] 相關單元測試是否 100% 通過？
  → 確認：12 個測試全部通過
- [x] 相關整合測試是否 100% 通過？
  → 確認：3 個整合測試全部通過
- [x] 測試覆蓋率是否達標（> 80%）？
  → 確認：覆蓋率 95%
- [x] 是否有測試被 skip？
  → 確認：無 skip 測試

**類別 4：文檔同步性（4/4 通過）**
- [x] Ticket 工作日誌是否更新？
  → 確認：記錄執行過程和設計決策
- [x] 設計決策是否記錄？
  → 確認：記錄 Repository Pattern 選擇理由
- [x] API 文檔是否同步？
  → 確認：所有公開方法都有 dartdoc 註解
- [x] README 是否需要更新？
  → 確認：不需要更新（內部實作，不影響公開 API）

**發現問題**：
- 無

**建議改善**（可選）：
- 建議補充更多邊界情況測試（如超長字串）
- 建議補充效能測試（大量資料查詢）

**Review 時間**：25 分鐘

**下一步行動**：
- [x] 標記 Ticket #42 為「已完成」
- [x] 更新 v0.12.0-main.md 索引
- [x] 建議改善列入 Backlog（可延後處理）
```

#### 範例 2：Review 未通過

```markdown
### Review 記錄 - Ticket #45

**Review 時間**：2025-10-11 09:30

**Reviewer**：李四

**Ticket 標題**：實作 Book 驗證邏輯

**Review 結果**：❌ 未通過

**檢查項目**：

**類別 1：功能正確性（3/4 通過）**
- [x] Ticket 描述的功能是否實現？
  → 確認：驗證邏輯實作完成
- [x] 驗收條件是否全部滿足？
  → 確認：5 個驗收條件都打勾
- [ ] 是否有未處理的邊界情況？
  → ❌ 問題：缺少書名為空字串、ISBN 格式錯誤、頁數為負數的處理
- [x] 錯誤處理是否完整？
  → 確認：使用 ValidationException 處理錯誤

**類別 2：架構合規性（4/4 通過）**
- [x] 是否符合 Clean Architecture 分層原則？
- [x] 依賴方向是否正確？
- [x] 是否使用 Interface-Driven 開發？
- [x] 是否有架構債務產生？

**類別 3：測試通過率（2/4 通過）**
- [x] 相關單元測試是否 100% 通過？
  → 確認：8 個測試全部通過
- [x] 相關整合測試是否 100% 通過？
  → 確認：2 個整合測試通過
- [ ] 測試覆蓋率是否達標（> 80%）？
  → ❌ 問題：覆蓋率只有 65%，缺少邊界情況測試
- [ ] 是否有測試被 skip？
  → ❌ 問題：1 個測試被 skip（錯誤處理測試）

**類別 4：文檔同步性（4/4 通過）**
- [x] Ticket 工作日誌是否更新？
- [x] 設計決策是否記錄？
- [x] API 文檔是否同步？
- [x] README 是否需要更新？

**發現問題**：

**問題 1：邊界情況未處理（P0）**
- 描述：缺少書名為空字串、ISBN 格式錯誤、頁數為負數的處理
- 影響：可能產生無效資料
- 建議：補充邊界情況處理邏輯

**問題 2：測試覆蓋率不足（P1）**
- 描述：測試覆蓋率只有 65%，缺少邊界情況測試
- 影響：無法確保邊界情況正確處理
- 建議：補充邊界情況測試

**問題 3：測試被 skip（P0）**
- 描述：錯誤處理測試被 skip
- 影響：無法確保錯誤處理正確
- 建議：移除 skip，完成測試

**建議改善**：
- 無（必須先修正上述問題）

**Review 時間**：35 分鐘

**下一步行動**：
- [x] 建立修正 Ticket #45.1：補充邊界情況處理
- [x] 建立修正 Ticket #45.2：補充邊界情況測試
- [x] 建立修正 Ticket #45.3：移除 skip 測試
- [x] 建立 Review 偏差記錄 #2
- [x] 通知開發者修正事項
```

### 5.3 Review 統計追蹤

#### Review 效率統計

**每週 Review 統計報告**：

```markdown
### Review 統計報告 - Week 41

**統計期間**：2025-10-07 ~ 2025-10-13

**Review 總數**：15 次

**Review 結果**：
- ✅ 通過：12 次（80%）
- ❌ 未通過：3 次（20%）

**平均 Review 時間**：28 分鐘
- 最短：15 分鐘
- 最長：45 分鐘
- 目標：≤ 30 分鐘

**問題分類統計**：
- 功能正確性問題：2 次（13%）
- 架構合規性問題：1 次（7%）
- 測試通過率問題：3 次（20%）
- 文檔同步性問題：1 次（7%）

**常見問題 Top 3**：
1. 測試覆蓋率不足（3 次）
2. 邊界情況未處理（2 次）
3. 測試被 skip（2 次）

**改善建議**：
- 強化測試標準培訓
- 建立邊界情況測試檢查清單
- 禁止 skip 測試

**下週重點**：
- 提升測試品質意識
- 推廣邊界情況測試範本
```

#### Review 品質追蹤

**Review 品質指標**：

| 指標 | 目標 | 實際 | 達成率 |
|------|------|------|-------|
| **Review 通過率** | > 80% | 80% | ✅ 達成 |
| **平均 Review 時間** | ≤ 30 分鐘 | 28 分鐘 | ✅ 達成 |
| **問題發現率** | > 90% | 95% | ✅ 達成 |
| **修正一次通過率** | > 90% | 85% | ⚠️ 未達成 |

**改善行動**：
- 修正一次通過率未達成 → 加強偏差記錄分析，避免重複問題

---

## 第六章：即時 Review 最佳實踐

### 6.1 完整案例研究

#### 案例：BookRepository 實作的即時 Review 流程

**背景**：
- Ticket #42：實作 SQLiteBookRepository
- 開發者：張三
- Reviewer：李四

**完整流程**：

```text
Day 1 上午（09:00）：
→ 張三領取 Ticket #42
→ 閱讀 Ticket 描述和驗收條件
→ 開始實作

Day 1 下午（15:00）：
→ 張三完成實作
→ 執行自我檢查：
  - 所有驗收條件打勾 ✅
  - 測試 100% 通過 ✅
  - dart analyze 0 錯誤 ✅
  - 工作日誌已更新 ✅
→ 標記 Ticket #42 為「Review 中」
→ 系統自動通知李四

Day 1 下午（15:10）：
→ 李四收到 Review 通知
→ 開始 Review（目標 30 分鐘）

Review 過程（15:10 - 15:35）：

1. 功能正確性檢查（10 分鐘）
   - [x] 對照 Ticket 描述，確認 4 個 CRUD 方法完整實作
   - [x] 逐項檢查驗收條件，確認都滿足
   - [x] 檢查邊界情況處理（null, empty, 異常輸入）
   - [x] 檢查錯誤處理（ValidationException, StorageException）

2. 架構合規性檢查（8 分鐘）
   - [x] 確認檔案位於 Infrastructure 層
   - [x] 確認實作 IBookRepository 介面
   - [x] 確認依賴方向正確（只依賴 Domain 層）
   - [x] 確認無架構債務

3. 測試通過率檢查（5 分鐘）
   - [x] 執行測試，確認 12 個測試全部通過
   - [x] 檢查測試覆蓋率，確認 95%
   - [x] 確認無 skip 測試

4. 文檔同步性檢查（2 分鐘）
   - [x] 確認工作日誌已更新
   - [x] 確認設計決策已記錄
   - [x] 確認 API 文檔已同步

Day 1 下午（15:40）：
→ 李四完成 Review（實際 25 分鐘）
→ Review 結果：✅ 通過
→ 記錄 Review 結果（5 分鐘）
→ 標記 Ticket #42 為「已完成」
→ 通知張三 Review 通過

總計時間：
- 實作時間：6 小時
- Review 時間：30 分鐘（含記錄）
- 總計：6.5 小時（當天完成）
```

**效益分析**：

```text
即時 Review 方式：
→ 當天完成實作和 Review
→ 無返工時間
→ 開發者即時獲得回饋
→ 總計：6.5 小時

假設延遲 3 天 Review：
→ Day 1-3: 實作 5 個 Ticket（6 小時 × 5 = 30 小時）
→ Day 4: Review 發現架構問題（2 小時）
→ Day 5-6: 返工修正 5 個 Ticket（12 小時）
→ Day 7: 再次 Review（2 小時）
→ 總計：46 小時（多花 16 小時，35% 效率損失）

效益：
- 節省時間：16 小時
- 避免挫折感：開發者不需要大幅返工
- 提升品質：問題早期發現
```

### 6.2 常見問題與解決方案

#### 問題 1：Review 速度慢，超過 1 小時

**問題描述**：
- Review 經常超過 1 小時
- Reviewer 花太多時間討論細節
- 阻塞開發節奏

**根本原因**：
1. Ticket 拆分不當，Ticket 太大
2. Reviewer 過度關注細節（如命名偏好）
3. 缺乏標準化檢查清單

**解決方案**：

**方案 1：使用標準化檢查清單**
```markdown
### Review 檢查清單（目標 30 分鐘）

- [ ] 功能正確性（10 分鐘）
- [ ] 架構合規性（8 分鐘）
- [ ] 測試通過率（5 分鐘）
- [ ] 文檔同步性（2 分鐘）
- [ ] 記錄 Review 結果（5 分鐘）

總計：30 分鐘
```

**方案 2：聚焦核心問題**
```text
P0（阻塞）：功能錯誤、架構偏差、測試失敗 → 必須修正
P1（重要）：邊界缺失、文檔不完整 → 建立修正 Ticket
P2（建議）：命名改善、程式風格 → 記錄建議，不深究

Review 時只關注 P0 和 P1，P2 快速記錄即可
```

**方案 3：拆分 Ticket**
```text
Ticket 太大（> 8 小時） → 拆分成多個小 Ticket
每個 Ticket ≤ 4 小時 → Review 時間 ≤ 30 分鐘
```

#### 問題 2：Review 發現問題太晚

**問題描述**：
- 開發者完成 5 個 Ticket 才 Review
- 發現架構問題，需要大幅返工
- 開發者士氣受影響

**根本原因**：
1. 未遵循「每完成一個 Ticket 觸發 Review」原則
2. Reviewer 延遲處理 Review 請求
3. 缺乏 Review 時效性監控

**解決方案**：

**方案 1：嚴格執行即時 Review**
```text
Ticket 完成 → 立即標記「Review 中」
              ↓
        自動通知 Reviewer
              ↓
    2 小時內開始 Review（SLA）
              ↓
    30 分鐘內完成 Review
              ↓
     立即回饋給開發者
```

**方案 2：Review 時效性監控**
```markdown
### Review SLA 監控

**目標**：
- 收到通知後 2 小時內開始 Review
- 30 分鐘內完成 Review

**超時警報**：
- 超過 2 小時未開始 → 發送提醒通知
- 超過 4 小時未開始 → 升級給 Team Lead
- 超過 1 小時未完成 → 分析原因（Ticket 太大？）

**統計追蹤**：
- 每週統計平均 Review 時間
- 每週統計超時次數
- 持續改善 Review 效率
```

**方案 3：輪流 Review 制度**
```text
避免單一 Reviewer 過載：
→ 團隊成員輪流擔任 Reviewer
→ 每人每天 Review 2-3 個 Ticket
→ 確保 Review 不延遲
```

#### 問題 3：開發者不願接受 Review 意見

**問題描述**：
- 開發者認為 Review 是「找麻煩」
- 開發者抗拒修正建議
- 團隊氛圍緊張

**根本原因**：
1. Review 語氣不友善，讓人感覺被批評
2. Review 意見不明確，缺乏具體建議
3. Review 標準不一致，讓人覺得不公平

**解決方案**：

**方案 1：友善的 Review 語氣**

❌ **不友善的語氣**：
```markdown
問題：你的程式碼違反依賴倒置原則，為什麼不先定義 Interface？
```

✅ **友善的語氣**：
```markdown
建議：這個 Repository 可以先定義 IBookRepository 介面，然後讓 BookRepositoryImpl 實作它。這樣可以方便測試和替換實作，符合依賴倒置原則。

範例：
// lib/domains/library/repositories/i_book_repository.dart
abstract class IBookRepository {
  Future<Book> create(Book book);
}

// lib/infrastructure/repositories/book_repository_impl.dart
class BookRepositoryImpl implements IBookRepository {
  @override
  Future<Book> create(Book book) { /* ... */ }
}

參考文件：Clean Architecture 開發指引
```

**方案 2：明確的修正建議**

❌ **模糊的建議**：
```markdown
問題：測試不夠完整
```

✅ **明確的建議**：
```markdown
建議：補充以下邊界情況測試：

1. 書名為空字串時應拋出 ValidationException
   test('should throw ValidationException when title is empty', () { ... });

2. ISBN 格式錯誤時應拋出 ValidationException
   test('should throw ValidationException when ISBN format is invalid', () { ... });

3. 頁數為負數時應拋出 ValidationException
   test('should throw ValidationException when pages is negative', () { ... });

參考：邊界情況測試檢查清單
```

**方案 3：一致的 Review 標準**
```markdown
### Review 標準化

**使用統一的 16 項檢查清單**：
- 所有 Reviewer 使用相同的檢查清單
- 確保 Review 標準一致
- 避免「因人而異」的標準

**定期 Review 校準會議**：
- 每月一次 Reviewer 校準會議
- 討論 Review 標準和尺度
- 分享 Review 經驗和技巧
- 確保團隊 Review 標準一致
```

#### 問題 4：Review 積壓，影響開發節奏

**問題描述**：
- 同時有 5+ 個 Ticket 等待 Review
- Reviewer 過載，無法及時處理
- 開發者等待 Review，無法繼續

**根本原因**：
1. Reviewer 人數不足
2. Reviewer 時間分配不當
3. 缺乏 WIP（Work In Progress）限制

**解決方案**：

**方案 1：增加 Reviewer 人力**
```text
團隊規模 vs Reviewer 配置：
- 3-5 人團隊：2 名 Reviewer（輪流）
- 6-10 人團隊：3-4 名 Reviewer（輪流）
- 10+ 人團隊：專職 Reviewer + 輪流 Reviewer

原則：
→ 每名 Reviewer 每天 Review 2-3 個 Ticket
→ 避免單一 Reviewer 過載
```

**方案 2：Review 時間保護**
```text
每天固定 Review 時段：
- 上午 10:00-11:00：Review 時段
- 下午 15:00-16:00：Review 時段

原則：
→ Review 時段不安排會議
→ Reviewer 專注處理 Review
→ 確保 Review 不延遲
```

**方案 3：WIP 限制**
```text
限制同時進行的 Ticket 數量：
- 單一開發者：≤ 2 個 Ticket（包含「Review 中」）
- 團隊整體：≤ 團隊人數 × 1.5

目的：
→ 避免 Ticket 積壓
→ 確保 Review 及時處理
→ 保持穩定的開發節奏
```

### 6.3 即時 Review 效益總結

#### 量化效益

| 維度 | 傳統 Review | 即時 Review | 改善幅度 |
|------|-----------|------------|---------|
| **開發速度** | 100% | 120-130% | ⬆️ +20-30% |
| **Bug 率** | 100% | 50-60% | ⬇️ -40-50% |
| **技術債務** | 100% | 30-40% | ⬇️ -60-70% |
| **團隊士氣** | 100% | 130-140% | ⬆️ +30-40% |
| **Review 時間** | 2-4 小時 | ≤ 30 分鐘 | ⬇️ -75% |
| **修正成本** | 高（6-10x） | 低（1x） | ⬇️ -80-90% |

#### 質化效益

**開發文化改善**：
1. **建立品質意識**：開發者知道每個 Ticket 都會被 review，自然提高品質標準
2. **即時學習機制**：發現問題立即修正，快速學習正確做法
3. **降低技術債務**：問題不累積，技術債務不擴散
4. **提升團隊信任**：Review 變成「幫助改善」而非「找麻煩」

**長期效益**：
- **標準化流程**：建立統一的 Review 標準和流程
- **知識共享**：Reviewer 輪流制度促進團隊知識共享
- **持續改善**：偏差記錄和經驗總結機制持續提升品質
- **敏捷開發**：即時 Review 支援快速迭代和持續整合

---

## 方法論總結

### 核心價值

本方法論的核心價值在於：

1. **即時發現問題**：在最早時機發現和修正問題，避免問題擴散
2. **降低修正成本**：問題範圍限定在單一 Ticket，修正成本最小化
3. **提升開發體驗**：即時回饋，快速修正，避免挫折感
4. **標準化 Review**：16 項檢查清單，確保 Review 品質一致
5. **持續改善**：結構化偏差糾正流程，積累經驗教訓

### 實踐要點

**執行即時 Review 的 3 個關鍵**：

1. **每完成一個 Ticket 立即觸發**：不等待，不累積
2. **30 分鐘快速完成**：聚焦核心問題，不深究細節
3. **標準化檢查清單**：使用 16 項檢查清單，確保一致性

**成功的 4 個條件**：

1. **團隊共識**：所有成員理解和接受即時 Review 原則
2. **時間保護**：Reviewer 有固定時段處理 Review
3. **標準化流程**：使用統一的檢查清單和記錄格式
4. **持續改善**：定期檢視 Review 效率和品質

### 與其他方法論的整合

本方法論與其他方法論的關係：

```text
[Ticket 拆分標準方法論]
    ↓ 拆分成多個小 Ticket
[Ticket 生命週期管理方法論]
    ↓ 執行 Ticket，完成後標記「Review 中」
[即時 Review 機制方法論] ← 本方法論
    ↓ Review 通過，標記「已完成」
[Code Smell 品質閘門檢測方法論]
    ↓ 持續監控程式碼品質
```

整合原則：
- **Ticket 拆分**確保每個 Ticket 可在 1 天內完成，Review 時間 ≤ 30 分鐘
- **生命週期管理**定義 Ticket 狀態流轉，即時 Review 是「Review 中」階段的核心
- **即時 Review**確保每個 Ticket 品質，避免問題累積
- **Code Smell 檢測**在 Review 基礎上持續監控，雙重保障

---

## 附錄 A：術語表

| 術語 | 英文 | 定義 |
|------|------|------|
| **即時 Review** | Instant Review | 每完成一個 Ticket 立即觸發 Review，不累積 |
| **Review 中** | In Review | Ticket 生命週期中的一個狀態，表示正在等待 Review |
| **偏差糾正** | Deviation Correction | Review 發現問題後的結構化處理流程 |
| **修正 Ticket** | Fix Ticket | Review 未通過時建立的 Ticket，用於修正問題 |
| **Review 檢查清單** | Review Checklist | 標準化的 16 項檢查項目，確保 Review 品質一致 |
| **Review 偏差記錄** | Review Deviation Log | 記錄 Review 發現的問題、根因、糾正措施 |
| **根因分析** | Root Cause Analysis | 分析問題發生的根本原因，避免重複發生 |
| **5 Why 分析** | 5 Why Analysis | 連續問 5 次「為什麼」，找出根本原因 |
| **Review SLA** | Review Service Level Agreement | Review 時效性標準（2 小時內開始，30 分鐘內完成） |
| **WIP 限制** | Work In Progress Limit | 限制同時進行的 Ticket 數量，避免過載 |
| **Review 通過率** | Review Pass Rate | Review 一次通過的比率（目標 > 80%） |
| **修正一次通過率** | Fix Pass Rate | 修正 Ticket 一次通過 Review 的比率（目標 > 90%） |
| **P0/P1/P2 優先級** | Priority Level | 問題優先級分類（P0 阻塞、P1 重要、P2 建議） |
| **Interface-Driven** | Interface-Driven Development | 依賴介面而非具體實作的開發原則 |

---

## 附錄 B：快速參考表

### Review 觸發時機

| 觸發條件 | 時機 | 必要性 |
|---------|------|-------|
| **每完成一個 Ticket** | Ticket 標記為「Review 中」 | 必要 ✅ |
| **每完成 3-5 個 Ticket** | 階段性 Review | 可選 ⚠️ |
| **每完成一個模組** | 模組整合 Review | 可選 ⚠️ |

### Review 檢查清單（16 項）

**類別 1：功能正確性（4 項）**
- [ ] Ticket 描述的功能是否實現？
- [ ] 驗收條件是否全部滿足？
- [ ] 是否有未處理的邊界情況？
- [ ] 錯誤處理是否完整？

**類別 2：架構合規性（4 項）**
- [ ] 是否符合 Clean Architecture 分層原則？
- [ ] 依賴方向是否正確（內層不依賴外層）？
- [ ] 是否使用 Interface-Driven 開發？
- [ ] 是否有架構債務產生？

**類別 3：測試通過率（4 項）**
- [ ] 相關單元測試是否 100% 通過？
- [ ] 相關整合測試是否 100% 通過？
- [ ] 測試覆蓋率是否達標（> 80%）？
- [ ] 是否有測試被 skip？

**類別 4：文檔同步性（4 項）**
- [ ] Ticket 工作日誌是否更新？
- [ ] 設計決策是否記錄？
- [ ] API 文檔是否同步？
- [ ] README 是否需要更新？

### 偏差糾正流程

```text
1. 暫停當前 Ticket
2. 記錄偏差問題（描述、影響、根因）
3. 分析根因類型
4. 建立修正 Ticket
5. 執行修正 Ticket
6. 再次 Review
7. 總結經驗教訓
```

### Review 時效性標準

| 階段 | 時間標準 | 超時處理 |
|------|---------|---------|
| **開始 Review** | ≤ 2 小時 | 發送提醒 |
| **完成 Review** | ≤ 30 分鐘 | 分析原因 |
| **最長 Review** | ≤ 1 小時 | 升級處理 |

---

## 附錄 C：與其他方法論的整合指引

### 與「Ticket 拆分標準方法論」整合

**整合目標**：確保每個 Ticket 可在 1 天內完成，Review 時間 ≤ 30 分鐘

**整合流程**：

```text
大任務
    ↓
[Ticket 拆分標準方法論]
    - 評估複雜度
    - 拆分成多個小 Ticket（每個 ≤ 4-8 小時）
    ↓
多個小 Ticket
    ↓
[Ticket 生命週期管理方法論]
    - 執行 Ticket
    - 標記「Review 中」
    ↓
[即時 Review 機制方法論]
    - 快速 Review（≤ 30 分鐘）
    - 即時回饋
    ↓
Ticket 完成
```

**關鍵整合點**：
- Ticket 大小影響 Review 時間
- Ticket ≤ 4 小時 → Review ≤ 20 分鐘
- Ticket ≤ 8 小時 → Review ≤ 30 分鐘
- Ticket > 8 小時 → Review > 1 小時（需要拆分）

### 與「Ticket 生命週期管理方法論」整合

**整合目標**：即時 Review 是 Ticket 生命週期的核心環節

**整合流程**：

```text
待執行（Pending）
    ↓
進行中（In Progress）
    ↓
[完成實作]
    ↓
Review 中（In Review） ← [即時 Review 機制方法論]
    ├─ Review 通過 → 已完成（Completed）
    └─ Review 未通過 → 建立修正 Ticket → 進行中（In Progress）
```

**關鍵整合點**：
- 「Review 中」狀態的處理流程由即時 Review 方法論定義
- Review 檢查項目與生命週期管理的驗收條件對應
- 偏差糾正流程是生命週期管理的重要補充

### 與「Code Smell 品質閘門檢測方法論」整合

**整合目標**：即時 Review 是第一道品質閘門，Code Smell 檢測是持續監控

**整合流程**：

```text
[即時 Review 機制方法論]
    - 每個 Ticket 完成後立即 Review
    - 檢查功能、架構、測試、文檔
    ↓
Ticket 通過 Review
    ↓
[Code Smell 品質閘門檢測方法論]
    - Hook 系統持續監控程式碼品質
    - 發現 Code Smell 立即警報
    - 建立修正 Ticket
    ↓
持續改善
```

**關鍵整合點**：
- 即時 Review 是「主動檢查」，Code Smell 檢測是「被動監控」
- 即時 Review 聚焦單一 Ticket，Code Smell 檢測聚焦整體品質
- 兩者互補，形成雙重品質保障

### 與「敏捷重構方法論」整合

**整合目標**：Review 是敏捷重構的重要反饋機制

**整合流程**：

```text
[敏捷重構方法論]
    - Phase 1: 設計
    - Phase 2: 測試
    - Phase 3: 實作
    ↓
Phase 3 完成
    ↓
[即時 Review 機制方法論]
    - Review Phase 3 實作品質
    - 發現問題立即糾正
    ↓
Phase 4: 重構
    ↓
[即時 Review 機制方法論]
    - Review Phase 4 重構品質
    - 確保重構改善程式碼
```

**關鍵整合點**：
- Phase 3 完成後必須 Review
- Phase 4 完成後必須 Review
- Review 確保每個 Phase 品質達標

---

**方法論版本**：v1.0
**最後更新**：2025-10-11
**維護責任**：架構團隊
