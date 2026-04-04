# v0.17.0 任務粒度案例：按優先級打包的反模式

> **背景**：Phase 4 審查發現 4 個 P1 問題（驗證框架重複、狀態轉換重複、零日誌、ID 碰撞），PM 按優先級合成 1 個 Ticket 派發。代理人花 27 分鐘在 4 個毫不相關的上下文間切換，而這 4 個問題完全可以並行。
> 教訓：把多個不相關問題按優先級合成一個 Ticket，導致代理人執行時間膨脹、無法並行。

---

## 案例：W4-002 — 4 個 P1 問題合成 1 個 Ticket

**問題編號**：GRAN-001（任務粒度反模式 - Priority Bundling）

**根因分類**：流程缺失（Phase 4 建立修復 Ticket 時無粒度檢查）

**問題場景**：Phase 4 多視角審查發現 4 個 P1 問題（驗證框架重複、狀態轉換重複、零日誌可觀測性、ID 碰撞風險），PM 按優先級合成為 1 個 Ticket，驗收條件 4 項、涉及 4 個不相關檔案。代理人需在驗證邏輯、日誌補充、ID 生成三個毫不相關的上下文之間切換。

**原始 Ticket**：

```yaml
id: 0.17.0-W4-002
title: "修復 P1: 驗證框架重複 + 狀態轉換重複 + 可觀測性 + ID碰撞"
acceptance:
  - 提取共用驗證引擎
  - 統一狀態轉換函式
  - tag-storage-adapter 加入日誌
  - ID 生成加隨機後綴
where:
  files:
    - src/data-management/BookSchemaV2.js
    - src/data-management/TagSchema.js
    - src/storage/adapters/tag-storage-adapter.js
    - src/data-management/migration/v1-to-v2.js
```

**執行結果**：27 分鐘（15:06 → 15:33），跨 4 個檔案、4 個不相關關注點。

---

## 問題分析

### 為什麼 27 分鐘太長？

| 指標 | 實際值 | 閾值 | 超標 |
|------|--------|------|------|
| 驗收條件數 | 4 項 | <= 2 | 是 |
| 修改檔案數 | 4 個 | <= 2 | 是 |
| 關注點數 | 4 個 | 1 | 是 |
| 執行時間 | 27 min | <= 10 min | 是 |

### 4 個關注點之間有依賴嗎？

| 關注點 | 依賴其他？ | 可獨立嗎？ |
|--------|-----------|-----------|
| 提取共用驗證引擎 | 否 | 是 |
| 統一狀態轉換函式 | 否 | 是 |
| 補充日誌 | 否 | 是 |
| ID 生成防碰撞 | 否 | 是 |

**結論**：4 個關注點完全獨立，可 100% 並行。合成一個 Ticket 是純粹的浪費。

---

## 正確拆分

### Ticket A：提取共用驗證引擎

```yaml
title: "重構 BookSchemaV2 和 TagSchema 共用驗證邏輯"
acceptance:
  - BookSchemaV2 和 TagSchema 的型別檢查、必填驗證共用 ValidationEngine
where:
  files:
    - src/data-management/BookSchemaV2.js
    - src/data-management/TagSchema.js
```

預估時間：5-7 分鐘。2 個檔案但同一關注點（提取共用）。

### Ticket B：統一狀態轉換函式

```yaml
title: "合併重複的閱讀狀態轉換函式"
acceptance:
  - mapV1StatusToV2 和 migrateReadingStatus 統一為單一函式
where:
  files:
    - src/data-management/BookSchemaV2.js
    - src/data-management/migration/v1-to-v2.js
```

預估時間：5 分鐘。2 個檔案但同一關注點（消除重複）。

### Ticket C：補充 tag-storage-adapter 日誌

```yaml
title: "補充 tag-storage-adapter catch 區塊日誌"
acceptance:
  - 所有 catch 區塊加入 logger.error 記錄
where:
  files:
    - src/storage/adapters/tag-storage-adapter.js
```

預估時間：3 分鐘。1 個檔案、機械性修改。

### Ticket D：ID 生成防碰撞

```yaml
title: "修復 tag category ID 碰撞風險"
acceptance:
  - cat_{timestamp} 改為 cat_{timestamp}_{random4} 格式
where:
  files:
    - src/storage/adapters/tag-storage-adapter.js
```

預估時間：3 分鐘。1 個檔案、1 行核心修改。

### 拆分效益

| 指標 | 原始（1 Ticket） | 拆分後（4 Tickets） |
|------|-----------------|-------------------|
| 總執行時間 | 27 min（序列） | ~7 min（並行） |
| 最長單一 Ticket | 27 min | 7 min |
| 並行度 | 0% | 100%（4 路並行） |
| 失敗隔離 | 1 個失敗 = 全部重做 | 1 個失敗 = 只重做該 Ticket |
| Code Review 難度 | 4 個不相關變更混在一起 | 每個 commit 只含一個關注點 |

---

## 識別信號

遇到以下信號時，應懷疑 Ticket 過大：

| 信號 | 範例 |
|------|------|
| 標題含「+」 | 「修復 X + Y + Z」 |
| 驗收條件 > 2 項 | 4 項驗收，彼此無關聯 |
| 修改多個不相關檔案 | 4 個檔案分屬不同模組 |
| 執行者需要在多個上下文間切換 | 驗證邏輯 → 日誌 → ID 生成 |

---

## 防護措施

PM 在建立 Phase 4 修復 Ticket 時，必須遵循：

1. **一個發現 = 一個 Ticket**，不按 P0/P1/P2 合併
2. 檢查 Ticket 標題是否含「+」「和」「及」
3. 檢查驗收條件是否 <= 2 項
4. 確認關注點數 = 1

> 粒度規則完整定義：task-granularity-rules.md

---

## 回測驗證

若當時遵循「一個發現 = 一個 Ticket」規則：
- 4 個 P1 問題建立 4 個獨立 Ticket（A/B/C/D）
- 4 路並行派發，最長單一 Ticket ~7 min，總時間 ~7 min（vs 原始 27 min）
- Ticket C（補日誌）和 Ticket D（ID 防碰撞）修改同一檔案但不同函式，可安全並行
- 若其中一個失敗（如 Ticket A 提取共用引擎方案不合適），其他 3 個不受影響

**結論**：規則有效。並行效率提升 ~4 倍，失敗隔離從 0% 提升到 75%。

---

**Last Updated**: 2026-04-04
**Version**: 1.0.0 - 初始建立（基於 v0.17.0 回顧分析）
