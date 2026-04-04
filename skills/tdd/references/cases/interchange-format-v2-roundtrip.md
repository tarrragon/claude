# Interchange Format v2 Round-trip：匯出→匯入→匯出資料一致性

> **背景**：使用者從裝置 A 匯出書庫、在裝置 B 匯入、再從裝置 B 匯出。匯出→匯入→匯出後的資料是否和原始一致？tag 引用可能斷裂、浮點數精度可能丟失、時間戳格式可能變化。規格未定義 round-trip 保證。
> 對應 Phase：Phase 1（功能規格設計）
> 對應 Decision Question：Q9（跨平台欄位轉換的精度保證與格式穩定性）

---

## 問題概述

Interchange Format v2 是 Extension 和 Flutter App 之間的資料交換格式。匯出時需將 Extension 內部格式轉換為通用格式（如 progress 100 → 1.0），匯入時反向轉換。Round-trip（匯出→匯入→再匯出）後，資料必須完全一致。浮點精度、tag_tree 序列化、欄位名稱映射都是潛在的一致性破壞點。

---

## 欄位轉換規則

### Extension → Interchange Format v2

| Extension 欄位 | Interchange 欄位 | 轉換規則 |
|---------------|-----------------|---------|
| `progress` (0-100, integer) | `readingProgress` (0.0-1.0, float) | `progress / 100` |
| `cover` (string URL) | `coverUrl` (string) | 僅欄位名不同 |
| `extractedAt` (ISO string) | `createdAt` (ISO string) | 僅欄位名不同 |
| `source` (string) | `platform` (string) | 僅欄位名不同 |
| `readingStatus` (string) | `readingStatus` (string) | 不變 |
| `isManualStatus` (boolean) | `isManualStatus` (boolean) | 不變 |
| `tagIds` (array) | `tagIds` (array) | 不變 |

### tag_tree 序列化

```javascript
// Interchange Format v2 的 tag_tree 結構
{
  "tag_tree": [
    {
      "category": { "id": "cat_001", "name": "類別", "color": "#4A90D9" },
      "tags": [
        { "id": "tag_001", "name": "小說" },
        { "id": "tag_002", "name": "科幻" }
      ]
    }
  ]
}
```

---

## 關鍵邊界條件

### 1. Float 精度問題

| Extension progress | 匯出 readingProgress | 匯入回 progress | 一致嗎？ |
|-------------------|---------------------|----------------|---------|
| 0 | 0.0 | 0 | 一致 |
| 100 | 1.0 | 100 | 一致 |
| 33 | 0.33 | 33 | 一致（Math.round(0.33 * 100) = 33） |
| 67 | 0.67 | 67 | 一致（Math.round(0.67 * 100) = 67） |
| 1 | 0.01 | 1 | 一致 |
| 99 | 0.99 | 99 | 一致 |

**風險點**：JavaScript 浮點運算 `0.33 * 100 = 33.00000000000000.4`，必須使用 `Math.round()` 確保整數回復。

**驗證公式**：`Math.round(readingProgress * 100) === originalProgress`

### 2. 特殊值處理

| 值 | Extension 內部 | Interchange | 匯入回 | 測試重點 |
|----|---------------|-------------|--------|---------|
| progress = undefined | undefined | 省略或 null | undefined | 缺失值保留 |
| progress = null | null | null | null | null 值保留 |
| progress = 0 | 0 | 0.0 | 0 | 零值不被省略 |
| progress = NaN | NaN | 應轉為 null 或 0 | 0 或 null | 非法值清理 |
| isManualStatus = undefined | undefined | 省略或 false | false | v1 資料缺少此欄位 |

### 3. tag_tree Round-trip

| 場景 | 測試重點 |
|------|---------|
| 空 tag_tree（無 category 和 tag） | `tag_tree: []` 匯出匯入後仍為空陣列 |
| category 有 tag 但無書籍引用 | tag_tree 包含 tag 但 books 的 tagIds 為空 |
| tag 被多本書共用 | 匯入時 tag 不重複建立 |
| 匯入端已有同名但不同 ID 的 tag | ID 衝突處理策略（保留匯入端？合併？） |
| tag 的 sortOrder 和 color 等可選欄位 | 匯出匯入後可選欄位不遺失 |
| Unicode 字元（中文 tag 名稱） | 序列化/反序列化不亂碼 |

### 4. 完整 Round-trip 驗證

**測試流程**：

```
Extension 資料（原始）
    → 匯出為 Interchange Format v2（JSON 檔案）
    → 匯入回 Extension
    → 再次匯出為 Interchange Format v2（JSON 檔案）
    → 比對兩次匯出的 JSON 內容
```

**一致性檢查點**：

| 檢查項 | 驗證方式 |
|-------|---------|
| books 陣列長度 | 完全相等 |
| 每本書的所有欄位值 | 深度比較（忽略欄位順序） |
| tag_tree 結構 | 深度比較（忽略陣列元素順序） |
| format_version | 完全相等 |
| 匯出時間戳 | 允許不同（匯出時間本來就不同） |

### 5. 格式偵測

| JSON 結構 | 判定格式 | 處理方式 |
|----------|---------|---------|
| 頂層是 Array | v1 舊格式 | 直接作為 books 陣列匯入 |
| 頂層是 Object，含 `format_version` | Interchange Format v2 | 解析 books + tag_tree |
| 頂層是 Object，無 `format_version` | 未知格式 | 報錯 |

---

## 測試設計建議

### Round-trip 測試最小資料集

測試資料應包含：

1. 一本 progress=0 的 unread 書（邊界值）
2. 一本 progress=33 的 reading 書（浮點精度）
3. 一本 progress=100 的 finished 書（邊界值）
4. 一本 isManualStatus=true 的 queued 書（手動狀態）
5. 一本有 3 個 tagIds 的書（tag 引用）
6. 一本無 tagIds 的書（空引用）
7. 2 個 tag_category，共 5 個 tag
8. 至少一個含中文名稱的 tag

### 驗證斷言

```javascript
// Round-trip 核心斷言
assert.deepStrictEqual(
  sortBooks(secondExport.books),
  sortBooks(firstExport.books),
  'Round-trip 後 books 資料不一致'
);

assert.deepStrictEqual(
  sortTagTree(secondExport.tag_tree),
  sortTagTree(firstExport.tag_tree),
  'Round-trip 後 tag_tree 資料不一致'
);
```

### 需要特別注意的陷阱

| 陷阱 | 說明 | 防護 |
|------|------|------|
| JSON.stringify 的 key 排序 | 不同引擎可能產生不同的 key 順序 | 比較前排序或用深度比較 |
| undefined vs 省略 | `{a: undefined}` 和 `{}` 在 JSON 序列化後相同 | 明確定義哪些欄位可省略 |
| 浮點比較 | 0.33 !== 0.3300000000000004 | 使用 Math.round 轉換後比較整數 |
| 日期格式 | ISO 8601 毫秒精度差異 | 統一為秒級或毫秒級 |

---

## 風險等級與影響範圍

| 風險點 | 風險等級 | 影響範圍 |
|-------|---------|---------|
| Float 精度導致 progress 偏移 | 高 | 所有匯出匯入操作 |
| tag_tree 序列化不一致 | 中 | 跨裝置同步場景 |
| 格式偵測誤判 | 中 | v1/v2 格式混用場景 |
| 欄位名稱映射遺漏 | 高 | 新增欄位時容易漏改 |

---

## 教訓

1. **Round-trip 測試是格式轉換的最低要求** -- 單向轉換測試無法發現精度丟失，只有完整的匯出→匯入→匯出才能驗證資料保真度
2. **Float 精度是已知陷阱** -- progress 100 → 1.0 → 100 看似簡單，但中間值（33 → 0.33 → ?）需要明確的取整策略
3. **tag_tree 的匯入策略需要在規格中定義** -- 同名不同 ID 的 tag 如何處理，不能留給實作者決定

---

**Last Updated**: 2026-04-04
**Version**: 1.0.0 - 初始建立（0.17.0-W5-002）
