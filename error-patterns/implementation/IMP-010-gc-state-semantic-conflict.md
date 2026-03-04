# IMP-010: GC 狀態語義衝突導致有效資料誤刪

## 基本資訊

- **Pattern ID**: IMP-010
- **分類**: 實作
- **來源版本**: v0.31.1
- **發現日期**: 2026-03-04
- **風險等級**: 高
- **來源 Ticket**: 0.31.1-W3-005

## 問題描述

### 症狀

- `ticket handoff --to-sibling` 成功建立 `pending/*.json` 檔案
- 19 秒後 Session 結束，pending 檔案消失
- 下一個 Session 的 `ticket resume --list` 回報「無待恢復任務」
- 用戶的工作 context 無法恢復

### 根本原因 (5 Why 分析)

1. Why 1: pending JSON 被 GC 刪除了
2. Why 2: GC 判定該 Ticket 狀態為 `completed`，認為是 stale 殘留
3. Why 3: GC 只檢查來源 Ticket 的 `status`，未考慮 handoff 的 `direction`
4. Why 4: `to-sibling` handoff 中，來源 Ticket `completed` 是**預期狀態**（先 complete 再 handoff 到兄弟任務），但 GC 將其視為「過期」
5. Why 5: (根本原因) **同一個狀態值（completed）在不同上下文有不同語義**。GC 上下文中 completed = stale，handoff 上下文中 completed = expected。設計時未區分這兩種語義。

### 錯誤模式歸納

**狀態語義衝突**：當一個狀態值在系統的不同模組中具有不同含義時，若模組間共享該狀態但未傳遞上下文，就會產生誤判。

**通用公式**：
```
模組 A 設定狀態 S = V（在 A 的語境中 V 表示「正常完成」）
模組 B 讀取狀態 S = V（在 B 的語境中 V 表示「可以清理」）
→ 模組 B 做出錯誤的清理決策
```

**適用場景**：GC 機制、快取清理、狀態機轉換、跨模組狀態共享

## 解決方案

### 正確做法

在 GC 判斷中加入**上下文欄位**檢查，區分不同語義：

```python
# 正確：檢查上下文（direction）後再決定是否刪除
if is_ticket_completed(project_root, ticket_id, logger):
    direction = handoff_data.get("direction", "")
    if direction in ("to-sibling", "to-parent", "to-child"):
        # 任務鏈 handoff，completed 是預期狀態，保留
        logger.info(f"保留 {direction} handoff: {ticket_id}")
        continue
    # 非任務鏈類型（如 context-refresh），completed 表示 stale
    file_path.unlink()
```

**設計原則**：
- GC 不能只依賴單一狀態值做清理決策
- 必須結合上下文（direction、timestamp、type 等）判斷
- 若無法判斷，寧可保留也不要刪除（保守策略）

### 錯誤做法 (避免)

```python
# 錯誤：只檢查狀態，不考慮上下文
if is_ticket_completed(project_root, ticket_id, logger):
    file_path.unlink()  # 一律刪除 → 誤刪有效的 handoff
```

## 防護措施

### 設計階段

1. **GC 設計時必須回答**：「這個狀態值在所有使用場景中是否有相同語義？」
2. **狀態共享時必須回答**：「讀取方是否需要額外上下文才能正確解讀此狀態？」
3. **採用保守策略**：不確定時保留資料，讓用戶手動清理，不要自動刪除

### 實作階段

1. GC 邏輯必須讀取完整的資料結構，不能只看一個欄位
2. 刪除操作前的日誌必須記錄決策依據（哪些欄位、什麼值）
3. 新增 GC 規則時，必須列舉所有可能的上下文組合

### Code Review 檢查點

- [ ] GC 刪除條件是否只依賴單一狀態值？
- [ ] 該狀態值在所有上下文中語義是否一致？
- [ ] 是否有其他欄位需要一起檢查？
- [ ] 刪除日誌是否包含足夠的決策依據？

## 相關資源

- Ticket: 0.31.1-W3-005
- 修復 commit: `fix: 修復 handoff GC 誤刪 to-sibling/to-parent pending JSON 的 bug`
- 修改檔案: `.claude/hooks/handoff-auto-resume-stop-hook.py`（新增 `should_preserve_pending_json()`）
- 附帶修復: `.claude/hooks/handoff-cleanup-hook.py`（簡化命令匹配邏輯）

## 標籤

`#GC` `#狀態語義` `#誤刪` `#handoff` `#上下文缺失` `#Hook`
