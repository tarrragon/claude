# v0.17.0 規格盲點案例集

> **背景**：4 個模組在獨立 worktree 各自實作了結構相同的驗證邏輯，合併後發現 20% 程式碼重複。規格未指出應共用驗證引擎。
> **用途**：作為 Decision Questions 的真實參考案例，說明規格盲點如何導致實作問題

---

## 案例 1：驗證框架重複（P1-1/2）

**對應 Decision Question**：組 1 Q1-Q2（跨模組共用策略）

### 問題描述

BookSchemaV2 和 TagSchema 分別在 W1 規格中定義，各自描述了驗證規則（字串長度、格式檢查、必填欄位）。規格未指出兩者的驗證邏輯結構相同，導致 W3 實作階段三個代理人在獨立 worktree 各自實作，產生重複程式碼。

### 具體數據

| 項目 | BookSchemaV2 | TagSchema |
|------|-------------|-----------|
| 驗證邏輯位置 | BookSchemaV2.js:81-123 | TagSchema.js:57-107 |
| 驗證項目 | 字串長度、格式、必填 | 字串長度、格式、必填 |
| 重複行數估計 | ~50 行 | ~50 行 |

### 根因

規格分別定義了各模組的驗證規則，但未在規格層級標注「這些驗證邏輯結構相同，應考慮共用」。Phase 3a 策略規劃也未識別此共用機會。

### 若當時有 Decision Questions

Q1 回答：「是，BookSchemaV2 和 TagSchema 都驗證字串長度和格式」
Q2 回答：「相似度 70%，修改驗證規則時兩邊必須同步，重複約 100 行 -> 應定義共用驗證引擎」

### 額外發現

狀態轉換邏輯也有重複：BookSchemaV2.js:245 的 `mapV1StatusToV2` 和 v1-to-v2.js:91 的 `migrateReadingStatus` 執行相同的轉換，但各自定義映射表。

---

## 案例 2：Date.now() ID 碰撞（P1-4）

**對應 Decision Question**：組 2 Q3-Q4（ID 欄位設計）

### 問題描述

規格定義 tag 分類 ID 格式為 `cat_{Date.now()}`，但未考慮批量建立場景。在迴圈中快速建立多個分類時（< 1ms 間隔），`Date.now()` 回傳相同的毫秒值，導致 ID 碰撞。

### 具體位置

- tag-storage-adapter.js:189

### 根因

規格只定義了 ID 的「格式」（`cat_` 前綴 + 時間戳），但未定義「唯一性保證」。規格撰寫者假設操作間隔足夠大，未考慮程式化批量操作場景。

### 若當時有 Decision Questions

Q3 回答：「是，批量匯入 tag 時會在迴圈中連續建立，間隔 < 1ms」
Q4 回答：「選擇 timestamp+random，改為 cat_{Date.now()}_{Math.random().toString(36).slice(2,8)}」

---

## 案例 3：author vs authors 欄位映射缺失

**對應 Decision Question**：補充 Q_new1（欄位命名一致性）

### 問題描述

v1 Schema 使用 `author`（字串），v2 Schema 改為 `authors`（陣列）。規格定義了 v2 的 schema 結構，但未建立完整的 v1->v2 欄位映射表。實作者在不同模組中混用 `book.author` 和 `book.authors`，導致去重邏輯靜默失效。

### 具體位置

- overview-page-controller.js:1409 - `_buildTitleAuthorKey` 使用 `book.author`（單數）
- 測試資料同時殘留 `author` 和 `authors` 欄位，測試碰巧通過

### 根因

規格分別定義了 v1 和 v2 的 schema，但未提供映射表。開發者需要自行推斷哪些欄位改名了，容易遺漏。

### 若當時有 Decision Questions

Q_new1 回答：

| 舊版本欄位 | 新版本欄位 | 型別變化 | 遷移邏輯 |
|-----------|-----------|---------|---------|
| author | authors | string -> string[] | `[book.author]` 包裝為陣列 |
| status | readingStatus | string -> enum | 映射表見 migration spec |
| category | tags | string -> Tag[] | 轉換為 Tag 物件陣列 |

有了映射表，所有消費端程式碼都能查表確認正確的欄位名稱。

---

## 案例 4：零日誌可觀測性（P1-3）

**對應 Decision Question**：組 3 Q5（出錯時操作者如何知道）

### 問題描述

tag-storage-adapter.js 全檔案的所有 catch 區塊不記錄任何日誌。CRUD 操作失敗時，錯誤被靜默吞掉，操作者無從得知問題發生。

### 根因

規格只定義了功能正確性需求（CRUD 成功/失敗的回傳值），未定義非功能性需求（可觀測性）。可觀測性規則存在於 `.claude/rules/core/observability-rules.md`，但未轉化為規格中的具體要求。

### 若當時有 Decision Questions

Q5 回答：「日誌，warning 等級，包含操作名稱 + 錯誤訊息 + 影響的資料 ID」

---

**Last Updated**: 2026-04-04
**Version**: 1.0.0 - 初始建立，來自 0.17.0-W4-004 根因分析（0.17.0-W4-005.1）
