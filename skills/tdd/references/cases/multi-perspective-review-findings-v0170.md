# v0.17.0 Phase 4 多視角審查發現

> 來源：0.17.0-W4-004（Phase 4 多視角審查報告）

---

## 審查配置

- 情境：B（重構評估）
- 視角：Redundancy + Complexity/Coupling + linux Good Taste + linux 單獨評估
- 標的：BookSchemaV2.js, TagSchema.js, tag-storage-adapter.js, v1-to-v2.js, overview-page-controller.js

## 整體評分

| 維度 | 評分 |
|------|------|
| linux Good Taste | Acceptable |
| linux 單獨 | A |
| 程式碼品質 | A（架構分層合理，命名清晰，業務邏輯註解充分） |

---

## 發現摘要

### P0 — 立即修復

| # | 發現 | 位置 | 根因分類 |
|---|------|------|---------|
| 1 | `_buildTitleAuthorKey` 使用 `book.author` 但 Schema v2 定義為 `authors`（陣列），跨平台去重靜默失效 | overview-page-controller.js:1409 | 測試盲點 |
| 2 | dead import: `require('src/core/errors/ErrorCodes')` 未使用且為 bare specifier，build 可能失敗 | BookSchemaV2.js:12 | 實作品質 |

### P1 — 本版本處理

| # | 發現 | 位置 | 根因分類 |
|---|------|------|---------|
| 1 | 驗證框架重複（BookSchemaV2 + TagSchema），需提取共用驗證引擎 | BookSchemaV2.js:81-123, TagSchema.js:57-107 | 規格盲點 |
| 2 | 狀態轉換邏輯重複（mapV1StatusToV2 vs migrateReadingStatus） | BookSchemaV2.js:245, v1-to-v2.js:91 | 規格盲點 |
| 3 | tag-storage-adapter 零日誌可觀測性，所有 catch 區塊不記錄 | tag-storage-adapter.js 全檔案 | 測試盲點 |
| 4 | Date.now() ID 生成碰撞風險 | tag-storage-adapter.js:189 | 規格盲點 |

### P2 — 延後處理

| # | 發現 | 位置 | 根因分類 |
|---|------|------|---------|
| 1 | migrateV1ToV2 97 行，認知指數 23，5 層巢狀 | v1-to-v2.js:208-305 | 實作品質 |
| 2 | tag-storage-adapter 723 行需拆分模組 | tag-storage-adapter.js | 實作品質 |
| 3 | 回滾快照重複邏輯，提取 _withAtomicRollback() | tag-storage-adapter.js:261,449 | 實作品質 |
| 4 | 版本號 "3.0.0" 硬編碼重複 | v1-to-v2.js:21, tag-storage-adapter.js:677 | 規格盲點 |
| 5 | _handleDuplicateBooks 64 行，認知指數 25 | overview-page-controller.js:1322 | 實作品質 |

---

## 根因統計

| 根因分類 | 發現數 | 佔比 | 問題項 |
|---------|--------|------|--------|
| 規格盲點 | 4 | ~36% | P1-1/2 共用策略缺失、P1-4 碰撞防護、P2-4 共用常數 |
| 測試盲點 | 3 | ~27% | P0-1 中間步驟測試、P1-3 非功能性測試 |
| 實作品質 | 4 | ~36% | P0-2 dead import、P2-1/2/3/5 複雜度和重複 |

### 根因分析方法示範

對每個 P0/P1 發現，逐一追溯至三個階段：

1. **規格（Phase 1）**：規格是否涵蓋了這個面向？
2. **測試（Phase 2）**：測試是否驗證了這個行為？
3. **實作（Phase 3）**：代理人的實作品質是否有問題？

先追溯到最上游的根因，而非只標記直接原因。例如 P0-1（`book.author` vs `authors`）：
- 直接原因看似「實作品質」（寫錯欄位名）
- 但追溯發現 Phase 2 測試資料同時殘留 `author` 和 `authors`，導致測試碰巧通過
- 根因歸類為「測試盲點」，因為正確的測試資料會讓錯誤立即暴露

---

## 量化指標

| 指標 | 數值 |
|------|------|
| 重複率 | ~18-22%（約 280-330 行可提取） |
| 超標函式（認知指數 > 10） | 11 個 |
| 超標函式（認知指數 > 20） | 3 個 |
| 耦合問題 | 3 個隱式 Schema coupling + 1 個版本號重複 |

---

## 改善方向

### 規格面（Phase 1 強化）

1. 多個模組有相似結構時，規格應明確指出「共用策略」
2. ID 生成規格應包含唯一性保證要求，不只定義格式
3. 非功能性需求（可觀測性、錯誤處理）應在規格中有專門章節

### 測試面（Phase 2 強化）

1. 測試設計應涵蓋「中間步驟」而非只測最終結果
2. 增加非功能性需求測試項：catch 區塊日誌驗證
3. 測試資料工廠應嚴格只使用目標版本欄位，不殘留舊版欄位

### 流程面（Phase 3 強化）

1. 並行派發前的策略規劃應識別跨代理人的共用元件
2. 完成前執行清單強制 lint
3. 新建私有方法需比對規格欄位定義

---

**Last Updated**: 2026-04-04
**Version**: 1.0.0 - 初始建立（0.17.0-W4-005.3）
