# isManualStatus 狀態轉換矩陣：36 種組合的合法性與自動追蹤交互

> **背景**：新增 isManualStatus 欄位（使用者手動覆蓋 Readmoo 同步的閱讀狀態）後，6 種閱讀狀態 x 6 種目標狀態 = 36 種轉換組合。規格只定義了「正常轉換路徑」，未回答：手動覆蓋後 Readmoo 再次同步時，以誰為準？
> 對應 Phase：Phase 1（功能規格設計）
> 對應 Decision Question：Q8（狀態轉換的完整性與 isManualStatus 行為）

---

## 問題概述

閱讀狀態從 v1 的 3 種（isNew/isFinished 布林組合）擴展為 v2 的 6 種具名狀態（unread/reading/finished/queued/abandoned/reference），並引入 `isManualStatus` 布林欄位區分自動轉換和手動設定。6x6 = 36 種轉換組合中，需明確定義哪些合法、哪些禁止、`isManualStatus` 在每種轉換中的行為。

---

## 狀態分類

| 類別 | 狀態 | 設定方式 | isManualStatus |
|------|------|---------|---------------|
| 自動狀態 | unread | 系統自動或手動重設 | false（若手動重設則重設為 false） |
| 自動狀態 | reading | 系統自動或手動重設 | false（若手動重設則重設為 false） |
| 自動狀態 | finished | 系統自動或手動重設 | false（若手動重設則重設為 false） |
| 手動狀態 | queued | 僅手動設定 | true |
| 手動狀態 | abandoned | 僅手動設定 | true |
| 手動狀態 | reference | 僅手動設定 | true |

---

## 完整轉換矩陣（36 種組合）

### 自動轉換（系統觸發，僅在 isManualStatus === false 時生效）

| 來源 → 目標 | 觸發條件 | isManualStatus 變化 | 合法性 |
|------------|---------|-------------------|--------|
| unread → reading | progress 從 0 變為 > 0 | false → false | 合法 |
| reading → finished | progress 達到 100 | false → false | 合法 |
| unread → finished | progress 直接跳到 100（極端情況） | false → false | 合法 |

**注意**：以下自動轉換不存在（系統不會自動降級）：

| 來源 → 目標 | 原因 |
|------------|------|
| reading → unread | progress 不會自動歸零 |
| finished → reading | 完成後不會自動「未完成」 |
| finished → unread | 完成後不會自動「未讀」 |

### 手動轉換（使用者觸發）

| 來源 → 目標 | isManualStatus 變化 | 合法性 | 說明 |
|------------|-------------------|--------|------|
| 任何 → queued | 設為 true | 合法 | 加入待讀清單 |
| 任何 → abandoned | 設為 true | 合法 | 放棄閱讀 |
| 任何 → reference | 設為 true | 合法 | 標記為參考書 |
| 任何 → unread | 設為 false | 合法 | 恢復自動追蹤 |
| 任何 → reading | 設為 false | 合法 | 恢復自動追蹤 |
| 任何 → finished | 設為 false | 合法 | 恢復自動追蹤 |

### 自動追蹤阻斷規則

| 場景 | isManualStatus | progress 變化 | 狀態是否自動轉換 |
|------|---------------|--------------|----------------|
| queued 的書被開始閱讀 | true | 0 → 30 | 否（保持 queued） |
| abandoned 的書被繼續閱讀 | true | 50 → 80 | 否（保持 abandoned） |
| reference 的書 progress 更新 | true | 任何變化 | 否（保持 reference） |
| unread 的書被開始閱讀 | false | 0 → 10 | 是（自動轉為 reading） |
| reading 的書讀完 | false | 90 → 100 | 是（自動轉為 finished） |

---

## 關鍵邊界條件

### 1. 手動設為自動狀態後的行為

使用者手動將書設為 reading（isManualStatus 重設為 false），之後 progress 達到 100。

**預期**：自動轉換為 finished（因為 isManualStatus === false，自動追蹤已恢復）。

### 2. 連續手動切換

使用者將書從 queued → abandoned → reference → unread，每次切換的 isManualStatus 變化：

```
queued (true) → abandoned (true) → reference (true) → unread (false)
```

### 3. 同狀態重複設定

使用者手動將已經是 reading 的書再次設為 reading。

**預期**：isManualStatus 設為 false（手動設定自動狀態 = 恢復自動追蹤），無論之前是 true 或 false。

### 4. progress 與狀態不一致

| progress | 手動狀態 | 是否合法 | 說明 |
|----------|---------|---------|------|
| 100 | queued | 合法 | 使用者決定重讀但先排入待讀 |
| 0 | finished | 合法 | 使用者手動標記已讀完（可能是紙本已讀） |
| 50 | abandoned | 合法 | 讀了一半放棄 |
| 0 | reference | 合法 | 參考書不需要閱讀進度 |

**設計決策**：progress 欄位在任何狀態下都可獨立更新，不受 readingStatus 約束。

### 5. v1 → v2 遷移後的 isManualStatus

所有 v1 資料遷移到 v2 後，`isManualStatus` 預設為 false（因為 v1 沒有手動設定功能，所有狀態都是系統自動判定）。

---

## 測試設計建議

### 矩陣覆蓋策略

1. **自動轉換路徑**（3 種）：驗證 progress 變化觸發正確的狀態轉換
2. **手動設定為手動狀態**（3 種目標 x 6 種來源 = 18 種）：驗證 isManualStatus 設為 true
3. **手動重設為自動狀態**（3 種目標 x 6 種來源 = 18 種）：驗證 isManualStatus 重設為 false
4. **自動追蹤阻斷**（3 種手動狀態 x 2 種 progress 變化 = 6 種）：驗證 isManualStatus === true 時自動轉換不觸發

### 最小測試集（覆蓋關鍵路徑）

| 測試 | 來源狀態 | 操作 | 預期結果 |
|------|---------|------|---------|
| 自動升級 | unread (false) | progress 0→50 | reading (false) |
| 自動完成 | reading (false) | progress 90→100 | finished (false) |
| 手動排入 | reading (false) | 手動設 queued | queued (true) |
| 阻斷自動 | queued (true) | progress 0→50 | queued (true)，不變 |
| 恢復追蹤 | abandoned (true) | 手動設 reading | reading (false) |
| 恢復後自動 | reading (false)（從 abandoned 恢復） | progress 90→100 | finished (false) |
| 同狀態重設 | reading (true) | 手動設 reading | reading (false) |

### 禁止的測試假設

| 假設 | 原因 |
|------|------|
| progress 和 readingStatus 必然一致 | 手動狀態下兩者可以不一致 |
| isManualStatus 只在 queued/abandoned/reference 時為 true | 理論上不存在，但需防禦 |
| 自動轉換一定會觸發 | 必須先檢查 isManualStatus |

---

## 風險等級與影響範圍

| 風險點 | 風險等級 | 影響範圍 |
|-------|---------|---------|
| 自動轉換在 isManualStatus=true 時仍觸發 | 高 | 覆蓋使用者的手動設定，使用者體驗嚴重受損 |
| 手動設自動狀態後 isManualStatus 未重設 | 中 | 自動追蹤永久失效，使用者需手動管理所有狀態 |
| v1 遷移後 isManualStatus 未初始化 | 中 | undefined 值導致自動轉換判斷錯誤 |

---

## 教訓

1. **6 種狀態的轉換矩陣必須完整列出** -- 「任何 → 任何」聽起來簡單，但 36 種組合中每一種的 isManualStatus 行為都需要明確定義
2. **isManualStatus 是第二維度** -- 狀態轉換不是一維的 A→B，而是二維的 (A, isManual) → (B, isManual')，測試矩陣需要覆蓋兩個維度
3. **progress 與 status 解耦是設計決策** -- 必須在規格中明確「progress 可在任何狀態下獨立更新」，否則實作者可能假設兩者耦合

---

**Last Updated**: 2026-04-04
**Version**: 1.0.0 - 初始建立（0.17.0-W5-002）
