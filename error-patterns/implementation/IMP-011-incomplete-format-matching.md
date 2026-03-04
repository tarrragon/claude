# IMP-011: 修復中引入新的格式假設錯誤

## 基本資訊

- **Pattern ID**: IMP-011
- **分類**: 實作
- **來源版本**: v0.31.1
- **發現日期**: 2026-03-04
- **風險等級**: 高
- **來源 Ticket**: 0.31.1-W3-006

## 問題描述

### 症狀

- W3-005 修復了 GC 狀態語義衝突（IMP-010），新增 `should_preserve_pending_json()` 函式
- 修復提交後，GC 仍然刪除 `to-sibling` 和 `to-child` 的 pending JSON
- `ticket resume --list` 在下一個 session 依然回報「無待恢復任務」
- 只有 `to-parent`（無目標 ID 後綴）的 handoff 被正確保留

### 根本原因 (5 Why 分析)

1. Why 1: pending JSON 仍然被 GC 刪除
2. Why 2: `should_preserve_pending_json()` 回傳 False，GC 未保留
3. Why 3: 函式使用精確匹配 `direction in {"to-sibling", "to-parent", "to-child"}`
4. Why 4: 實際 direction 值為 `"to-sibling:0.31.1-W3-002"`（帶目標 ID 後綴），精確匹配失敗
5. Why 5: (根本原因) **修復時未查閱 direction 欄位的完整格式規範**。開發者假設 direction 是簡單字串，但實際上 `_resolve_direction_from_args()` 會附加 `:{target_id}` 後綴

### 錯誤模式歸納

**修復中引入新的格式假設錯誤**：修復 Bug A 時，新增的程式碼對某個欄位的格式做了不完整的假設，導致修復無效或引入 Bug B。

**通用公式**：
```
1. Bug A 被發現（GC 誤刪）
2. 開發者新增修復函式，但對輸入格式做了隱含假設（direction 是簡單字串）
3. 實際格式比假設更複雜（direction 帶有 :TARGET_ID 後綴）
4. 修復函式在部分輸入下有效（to-parent），部分輸入下無效（to-sibling:ID）
5. Bug A 表面上已修復，實際上在特定條件下仍然存在
```

**與 IMP-010 的關係**：IMP-010 是設計問題（GC 缺少上下文判斷），IMP-011 是修復品質問題（修復時未完整理解資料格式）。兩者是連環錯誤。

**適用場景**：字串匹配、欄位格式解析、修復驗證、資料格式假設

## 解決方案

### 正確做法

修復前必須查閱欄位的**生產者**（寫入端），確認完整格式：

```python
# 正確：使用前綴匹配，容許後綴變化
def should_preserve_pending_json(direction: str, logger) -> bool:
    """判斷是否保留 pending JSON。

    direction 格式：
    - "to-parent"（無後綴）
    - "to-sibling:{target_id}"（帶目標 ID）
    - "to-child:{target_id}"（帶目標 ID）
    - "context-refresh"（非任務鏈）
    """
    chain_prefixes = ("to-sibling", "to-parent", "to-child")
    direction_type = direction.split(":")[0]
    return direction_type in chain_prefixes
```

**修復品質檢查清單**：

1. [ ] 新增程式碼使用的**每個欄位**，是否已查閱其生產者（寫入端）？
2. [ ] 欄位值是否有多種格式（帶/不帶後綴、大小寫差異等）？
3. [ ] 測試是否覆蓋欄位的**所有已知格式變體**？
4. [ ] 是否有文件字串記錄欄位的完整格式規範？

### 錯誤做法 (避免)

```python
# 錯誤：精確匹配，假設欄位是簡單字串
chain_directions = {"to-sibling", "to-parent", "to-child"}
if direction in chain_directions:  # "to-sibling:ID" 不在 set 中
    return True
```

## 防護措施

### 修復階段

1. **查閱生產者**：修復程式碼讀取某個欄位前，先找到寫入該欄位的函式，確認完整格式
2. **列舉格式變體**：在函式文件字串中明確列出欄位的所有可能格式
3. **測試格式邊界**：測試案例必須包含「帶後綴」和「不帶後綴」的變體

### Code Review 檢查點

- [ ] 新增的字串比較是精確匹配還是前綴/包含匹配？
- [ ] 被比較的欄位是否有多種格式？
- [ ] 測試是否覆蓋了真實資料的格式（而非理想化的簡單格式）？
- [ ] 修復是否有端對端驗證（不只是單元測試）？

### 連環修復防護

- [ ] 修復後是否用**原始失敗場景**重新測試？
- [ ] 是否確認修復在生產環境的資料格式下有效？
- [ ] 修復 commit 訊息是否記錄了格式假設？

## 相關資源

- Ticket: 0.31.1-W3-006（修復 direction 前綴匹配）
- 前置 Ticket: 0.31.1-W3-005（修復 GC 狀態語義衝突）
- IMP-010: GC 狀態語義衝突（前置錯誤模式）
- 修復 commit: `fix: 修復 GC should_preserve_pending_json 的 direction 匹配方式`
- 修改檔案: `.claude/hooks/handoff-auto-resume-stop-hook.py`
- 測試檔案: `.claude/hooks/tests/test_stop_hook.py`（新增 10 個測試用例）
- 格式生產者: `.claude/skills/ticket/ticket_system/commands/handoff.py` (`_resolve_direction_from_args`)

## 標籤

`#字串匹配` `#格式假設` `#修復品質` `#連環錯誤` `#handoff` `#GC` `#Hook`
