# v0.17.0 任務粒度案例：Use Case 驅動拆分 vs 全範圍重寫

> **背景**：一個「重寫 Chrome Storage adapter」的 Ticket 花了 15 分鐘、一個「撰寫 Schema v2 所有測試」的 Ticket 花了 29 分鐘。追溯根因發現 Phase 1 只產出一個大 Use Case，沒有分解為獨立的行為單元。
> 教訓：問題的根因不是「Ticket 太大需要切割」，而是「Phase 1 沒有把 Use Case 拆解為行為單元」。

---

**問題編號**：GRAN-002（任務粒度反模式 - Full-Scope Rewrite）

**根因分類**：規格盲點（Phase 1 未將 Use Case 分解為行為單元）

**問題場景**：Chrome Storage adapter 需從舊格式重寫為 tag-based 結構。Phase 1 只產出一個大 Use Case「tag-based 儲存」，未分解為行為單元。導致 Phase 2 測試（29 min、4 項驗收混合欄位/狀態/CRUD/邊界）和 Phase 3 實作（15 min、3 個檔案含結構定義/CRUD/配額）都過大。

---

## 根因分析：為什麼 Ticket 會過大？

v0.17.0 的 Ticket 粒度問題不是派發時的疏忽，而是 **Phase 1 規格設計** 的產出不夠細：

```
Phase 1 產出：                    導致的 Phase 2/3 Ticket：
───────────────                  ─────────────────────────
UC: tag-based 儲存（大 UC）  →   W2-002: 撰寫全部測試（29 min）
                              →   W3-002: 重寫全部 adapter（15 min）

應該的 Phase 1 產出：             對應的 Phase 2/3 Ticket：
───────────────────              ─────────────────────────
行為單元 1: 定義結構          →   T-001: 結構驗證測試 → I-001: 結構實作
行為單元 2: 建立 tag          →   T-002: 建立測試     → I-002: 建立實作
行為單元 3: 讀取 tag          →   T-003: 讀取測試     → I-003: 讀取實作
行為單元 4: 更新 tag          →   T-004: 更新測試     → I-004: 更新實作
行為單元 5: 刪除 tag          →   T-005: 刪除測試     → I-005: 刪除實作
行為單元 6: 配額檢查          →   T-006: 配額測試     → I-006: 配額實作
```

**如果 Phase 1 就把 Use Case 分解為 6 個行為單元，Phase 2/3 的 Ticket 自然就是 6 個，不需要事後「拆分」。**

---

## 案例 1：W3-002 — 從 Use Case 回推正確拆分

### 原始 Ticket（全範圍重寫）

```yaml
id: 0.17.0-W3-002
title: "重寫 Chrome Storage adapter（tag-based 結構）"
acceptance:
  - Chrome Storage 資料結構已改為 tag-based
  - tag_categories 和 tags CRUD 操作已實作
  - 配額管理已更新
  - W2-002 所有測試通過
```

**執行結果**：15 分鐘，4 項驗收混合了 3 個不同的行為單元。

### 正確做法：Phase 1 應產出的行為單元清單

| 行為單元 | Given | When | Then | 邊界條件 |
|---------|-------|------|------|---------|
| 定義結構 | tag schema 定義 | 驗證結構 | 合法/拒絕 | 空 schema、欄位遺漏 |
| 建立 tag | 有效 tag 資料 | createTag | 寫入 storage | 重複名稱、空名稱、配額滿 |
| 讀取 tag | 已存在 tag | getTag | 回傳資料 | tag 不存在、category 不存在 |
| 更新 tag | 已存在 tag | updateTag | 資料更新 | 更新不存在的 tag、名稱衝突 |
| 刪除 tag | 已存在 tag | deleteTag | 資料移除 | 刪除被引用的 tag、不存在的 tag |
| 配額檢查 | 接近配額限制 | 寫入 | 拒絕或警告 | 剛好滿、剛好未滿 |

**每個行為單元包含自己的邊界條件**，不另外建立「邊界條件 Ticket」。

### Phase 2 測試 Ticket（自然產出）

```yaml
# T-001: tag 結構驗證測試（~5 min）
# Given-When-Then 來自行為單元「定義結構」
acceptance:
  - TagSchema 欄位型別和必填驗證測試
  - 無效結構拒絕測試（空 schema、欄位遺漏）

# T-002: 建立 tag 測試（~5 min）
# Given-When-Then 來自行為單元「建立 tag」
acceptance:
  - 正常建立 + 重複名稱/空名稱拒絕測試

# T-003: 讀取 tag 測試（~3 min）
acceptance:
  - 正常讀取 + 不存在回傳 null 測試

# T-004: 更新 tag 測試（~5 min）
acceptance:
  - 正常更新 + 不存在/名稱衝突拒絕測試

# T-005: 刪除 tag 測試（~5 min）
acceptance:
  - 正常刪除 + 被引用拒絕 + 不存在回傳錯誤測試

# T-006: 配額檢查測試（~3 min）
acceptance:
  - 接近/達到/超過配額時的行為測試
```

### Phase 3b 實作 Ticket（1:1 映射）

每個測試 Ticket 自動對應一個實作 Ticket，不需要額外拆分思考。

### 整合測試 Ticket（額外）

```yaml
# T-INT-001: tag CRUD 端到端流程（~5 min）
# 目的：驗證單元之間的串連，不重複驗證單元行為
acceptance:
  - 建立 → 讀取 → 更新 → 讀取確認 → 刪除 → 讀取確認不存在
```

**整合測試只驗證串連**，不重複驗證邊界條件（那是各單元測試的責任）。

---

## 案例 2：W2-001 — 測試 Ticket 的自然拆分

### 原始 Ticket

```yaml
id: 0.17.0-W2-001
title: "撰寫測試 Book Schema v2 驗證測試"
acceptance:
  - 新欄位驗證測試（必填/選填/型別/預設值）
  - 6 種閱讀狀態的狀態轉換測試
  - tag 結構 CRUD 驗證測試
  - 無效資料拒絕測試（邊界條件）
```

**執行結果**：29 分鐘。4 項驗收涵蓋 3 個不同概念（欄位 / 狀態 / tag）。

### 根因

Phase 1 只定義了一個大 Use Case「Book Schema v2」，沒有分解為行為單元。如果 Phase 1 識別了：

| 行為單元 | 屬於哪個概念 |
|---------|------------|
| 欄位型別驗證 | Schema 結構 |
| 必填/選填欄位驗證 | Schema 結構 |
| 閱讀狀態合法轉換 | 狀態機 |
| 閱讀狀態非法轉換拒絕 | 狀態機 |
| tag 結構驗證 | Tag Schema |

測試 Ticket 就會自然對應到這些行為單元，而不是一個大包。

### 正確拆分

```yaml
# T-001: Schema 欄位驗證測試（~7 min）
# 行為單元：欄位型別 + 必填/選填
acceptance:
  - 新欄位型別和預設值驗證
  - 必填欄位缺失拒絕

# T-002: 閱讀狀態轉換測試（~5 min）
# 行為單元：狀態機
acceptance:
  - 6 種合法轉換 + 非法轉換拒絕矩陣

# T-003: tag 結構驗證測試（~5 min）
# 行為單元：Tag Schema
acceptance:
  - tag category 和 tag 結構的合法/拒絕驗證
```

**注意**：原始 Ticket 的第 4 項「無效資料拒絕測試」不應獨立成 Ticket — 邊界條件跟隨所屬行為單元。每個 T-00x 已包含自己的拒絕/邊界測試。

---

## 識別信號與引導問題

### Phase 1 設計時問自己

| 問題 | 如果答案是... | 行動 |
|------|-------------|------|
| 這個 UC 包含幾個獨立可測試的行為？ | > 1 | 拆解為行為單元 |
| 每個行為單元能用一個 GWT 場景描述嗎？ | 否 | 繼續拆解 |
| 邊界條件歸屬到哪個行為單元？ | 說不清 | 行為單元定義不夠清楚 |

### Phase 2 設計時驗證

| 信號 | 表示 | 行動 |
|------|------|------|
| 一個測試 Ticket 需要 > 5 個 test case | 混入了多個行為單元 | 回到 Phase 1 重新拆分 |
| 測試 Ticket 有多個不相關的 Given 條件 | 混入了多個行為單元 | 回到 Phase 1 重新拆分 |
| 邊界條件測試無法對應到單一行為單元 | Phase 1 單元識別不完整 | 補充行為單元定義 |

---

## 量化效益

| 指標 | v0.17.0 實際（大 Ticket） | Use Case 驅動拆分 |
|------|-------------------------|-------------------|
| W2-001 時間 | 29 min（1 Ticket） | ~17 min total（3 Ticket 可部分並行） |
| W3-002 時間 | 15 min（1 Ticket） | ~10 min total（6 Ticket 可並行） |
| 最長單一 Ticket | 29 min | 7 min |
| 失敗隔離 | 失敗 = 整個重做 | 失敗 = 只重做 1 個單元 |
| Code Review | 混合多個概念 | 每個 commit 只含一個行為單元 |

---

## 回測驗證

**案例 1（W3-002 adapter 重寫）**：若 Phase 1 識別了 6 個行為單元：
- 6 個測試 Ticket + 6 個實作 Ticket，每個 3-5 min
- 結構定義（a）先完成 → CRUD（b/c/d/e）和配額（f）5 路並行
- 總時間 ~8 min（a 序列 3 min + b-f 並行 5 min）vs 原始 15 min
- 任一 CRUD 失敗不影響其他操作的實作

**案例 2（W2-001 測試撰寫）**：若按行為單元拆為 3 個測試 Ticket：
- 欄位驗證（7 min）+ 狀態轉換（5 min）+ tag 結構（5 min）可並行
- 總時間 ~7 min vs 原始 29 min
- 邊界條件跟隨各自的行為單元，不會出現「邊界測試通過但跨單元整合失敗」的情況

**結論**：Use Case → 行為單元的拆分在源頭解決粒度問題，效果顯著。

---

**Last Updated**: 2026-04-04
**Version**: 2.0.0 - 重構為 Use Case 驅動視角，展示 Phase 1 拆分不足是根因（v0.17.0 回顧）
