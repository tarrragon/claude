# v0.17.0 測試盲點案例集

> 來源：0.17.0-W4-004（Phase 4 多視角審查報告）
> 適用：Phase 2 測試設計時的反面教材

---

## P0-1：book.author 碰巧通過 — 測試資料殘留 v1 欄位

### 背景

v0.17.0 W3 實作 Tag-based Book Model，Schema v2 將 `author`（字串）改為 `authors`（陣列）。`_buildTitleAuthorKey` 是新寫的私有方法，用於跨平台去重。

### 問題

`_buildTitleAuthorKey` 讀取 `book.author`（v1 單數形式）而非 `book.authors`（v2 陣列形式）。但測試資料工廠 `createBookV2()` 同時包含兩個欄位：

```javascript
// 測試資料工廠（有問題的版本）
function createBookV2(overrides = {}) {
  return {
    title: 'Test Book',
    author: 'Author Name',      // v1 欄位 — 不應存在於 v2 工廠
    authors: ['Author Name'],   // v2 欄位
    // ...
  };
}
```

因為 `author` 和 `authors[0]` 的值相同，`_buildTitleAuthorKey` 讀取錯誤欄位但產生了正確的 key，測試碰巧通過。

### 根因分類

測試盲點：
1. 測試只驗「合併結果是否正確」，未測「key 生成函式」這個中間步驟（Q7 未回答）
2. 測試資料工廠殘留 v1 欄位（Q11 未回答）
3. 測試資料讓讀錯欄位名的 bug 碰巧通過（Q9 未回答）

### 正確防護

**測試資料工廠修正**：

```javascript
// 修正後：只包含 v2 欄位
function createBookV2(overrides = {}) {
  return {
    title: 'Test Book',
    authors: ['Author Name'],   // 只有 v2 欄位
    // 完全移除 author
    // ...
  };
}
```

**中間步驟測試**：

```javascript
// Phase 2 應預定義 key 生成的契約測試
test('_buildTitleAuthorKey 使用 authors 陣列', () => {
  const book = createBookV2({ authors: ['Alice', 'Bob'] });
  const key = _buildTitleAuthorKey(book);
  expect(key).toContain('Alice');
  expect(key).toContain('Bob');
});

// 反向驗證：無 author 欄位時不應出錯
test('_buildTitleAuthorKey 無 author 欄位不報錯', () => {
  const book = createBookV2(); // 無 author 欄位
  expect(() => _buildTitleAuthorKey(book)).not.toThrow();
});
```

### 對應 Decision Questions

| Question | 本案例的答案 |
|----------|------------|
| Q7 | 只測最終結果（去重結果），未測中間步驟（key 生成） |
| Q9 | 測試資料同時有 author 和 authors，讀錯欄位碰巧通過 |
| Q11 | createBookV2() 殘留 v1 欄位 author |

---

## P1-3：catch 區塊零日誌 — 測試未覆蓋可觀測性

### 背景

v0.17.0 W3 實作 tag-storage-adapter.js，包含 8 個 catch 區塊。專案的可觀測性規則（`.claude/rules/core/observability-rules.md`）要求「catch 區塊必須有日誌」。

### 問題

W2 測試設計只驗證功能正確性（CRUD 成功/失敗的回傳值），完全沒有驗證 catch 區塊是否記錄日誌。所有 8 個 catch 區塊都是空的或只有 `return false`，零日誌輸出。

```javascript
// tag-storage-adapter.js（有問題的版本）
async addTag(tag) {
  try {
    // ... CRUD 操作
    return true;
  } catch (e) {
    return false;  // 零日誌，靜默失敗
  }
}
```

### 根因分類

測試盲點：
1. 可觀測性規則存在於 rules 中但未轉化為測試案例（Q10 未回答）
2. 測試只驗功能不驗非功能性需求（Q_new4 未回答）
3. expect 只驗證回傳值（存在性/值），未驗證副作用（日誌）（Q_new3 未完整回答）

### 正確防護

**Phase 2 應建立非功能性需求測試對照表**：

| Phase 1 非功能性需求 | 對應測試場景 | 驗證方式 | 覆蓋狀態 |
|--------------------|------------|---------|---------|
| catch 區塊必須有日誌 | catch 區塊日誌測試 | Mock logger，驗證 call count | 未覆蓋 |
| 日誌含錯誤訊息和元件名稱 | 日誌內容結構測試 | 驗證日誌參數 | 未覆蓋 |

**測試範例**：

```javascript
test('addTag 失敗時應記錄 warning 日誌', async () => {
  const mockLogger = { warn: jest.fn(), error: jest.fn() };
  const adapter = new TagStorageAdapter({ logger: mockLogger });

  // 故意觸發失敗（如 storage 不可用）
  mockStorage.set.mockRejectedValue(new Error('storage unavailable'));

  const result = await adapter.addTag(testTag);

  expect(result).toBe(false);
  expect(mockLogger.warn).toHaveBeenCalledTimes(1);
  expect(mockLogger.warn).toHaveBeenCalledWith(
    expect.stringContaining('addTag'),
    expect.objectContaining({ error: expect.any(Error) })
  );
});
```

### 對應 Decision Questions

| Question | 本案例的答案 |
|----------|------------|
| Q10 | 8 個 catch 區塊，0 個有對應日誌測試 |
| Q_new3 | expect 只驗證回傳值（isFalse），未驗證副作用（logger.warn） |
| Q_new4 | Phase 1 定義的異常處理路徑 vs 失敗測試對照表完全為空 |

---

## 總結：Phase 2 應如何避免

| 盲點 | 遺漏的 Decision Question | 防護動作 |
|------|------------------------|---------|
| 中間步驟未測 | Q7, Q8 | 列出中間步驟清單，各加獨立測試 |
| 碰巧通過 | Q9 | 檢查測試資料是否允許「讀錯欄位名但結果相同」 |
| 非功能性需求未測 | Q10, Q_new4 | 建立非功能性需求測試對照表 |
| 存在性驗證不足 | Q_new3 | 逐一列舉 expect 語句，確認是值驗證 |
| 舊版欄位殘留 | Q11 | 檢查測試資料工廠，移除非目標版本欄位 |

---

**Last Updated**: 2026-04-04
**Version**: 1.0.0 - 初始建立（0.17.0-W4-005.2）
