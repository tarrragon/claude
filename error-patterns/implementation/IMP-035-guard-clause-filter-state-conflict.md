# IMP-035: Guard Clause 與篩選狀態衝突

## 錯誤摘要

| 項目 | 說明 |
|------|------|
| **分類** | Implementation |
| **嚴重性** | 中（功能邏輯錯誤，非崩潰） |
| **發現版本** | v0.1.1 |
| **相關 Ticket** | 0.1.1-W9-002.1 |

## 症狀

- 函式在「篩選後只剩一個結果」時，誤觸「無結果」的 guard clause
- 使用者查詢特定項目時得到「找不到任何項目」的錯誤訊息
- 測試中 mock 正確設定但斷言失敗（輸出為空結果提示）

## 根因分析

**行為模式**：函式同時承擔「全量列表」和「篩選查詢」兩種模式，但 guard clause 只考慮了全量列表場景。篩選後的合法單一結果被 guard clause 誤判為「無資料」。

**具體案例**：

```python
# cmd_status 同時支援：
# 1. 無參數 → 列出全部 worktree
# 2. 有 ticket_id → 篩選特定 worktree

# Step 2: 篩選（正確找到目標）
if ticket_id is not None:
    worktrees = [target_worktree]  # 篩選後長度 = 1

# Step 3: guard clause（只考慮全量場景）
if len(worktrees) <= 1:  # 篩選結果也觸發了！
    print("目前沒有任何 worktree")  # 錯誤訊息
```

**衝突本質**：guard clause 的條件 `len <= 1` 在全量模式下語義正確（只有主倉庫 = 無額外 worktree），但在篩選模式下語義錯誤（找到 1 個 = 有結果）。

## 解決方案

在 guard clause 加入模式判斷條件，區分「全量無結果」和「篩選有結果」：

```python
# 修復：guard clause 只在未篩選時生效
if ticket_id is None and len(worktrees) <= 1:
    print("目前沒有任何 worktree")
```

## 預防措施

### 設計時檢查（函式支援多模式時）

當一個函式同時支援「列出全部」和「篩選特定」兩種模式時：

1. **guard clause 必須考慮所有模式**：每個 early return / guard clause 都要問「這個條件在篩選模式下是否也成立？」
2. **優先拆分函式**：如果模式差異大，考慮拆為 `list_all()` 和 `get_one()` 兩個函式
3. **測試覆蓋所有模式**：每個 guard clause 至少有「全量」和「篩選」兩個測試案例

### 附帶模式：dry-run 語義定位

同一 Ticket 也發現 `cmd_create` 的 dry-run 放在 git 狀態檢查之後，導致 dry-run 依賴外部狀態。

**原則**：dry-run 應在「格式驗證後、副作用前」返回。如果 dry-run 需要真實外部狀態才能執行，它就不是真正的 dry-run。

---

## 防護措施

### 設計時檢查清單（多模式函式 Guard Clause 審查，強制）

> **觸發時機**：函式透過 optional 參數、flag、enum 等控制不同操作模式（全量/篩選/查詢/建立等），且函式內包含 guard clause 或 early return。

**強制檢查清單**（設計或修改多模式函式時必須完成）：

| 步驟 | 問題 | 驗證方式 |
|------|------|---------|
| 1 | 列出函式支援的所有操作模式（全量、篩選、查詢、建立等） | 檢查 optional 參數和分支邏輯 |
| 2 | 列出函式內的所有 guard clause / early return | 搜尋 `if ... return`、`if ... raise`、`if ... print + return` |
| 3 | 對每個 guard clause 逐一問：「這個條件在模式 X 下語義是否正確？」 | 逐模式交叉驗證 |
| 4 | 若任一模式下語義不正確，guard clause 必須加入模式判斷條件 | 修改 guard clause 條件 |
| 5 | 每個 guard clause 至少有「每種模式各一個」的測試案例 | 檢查測試覆蓋 |

### 正確做法範例

**錯誤**（guard clause 不區分模式）：

```python
def list_items(filter_id=None):
    items = get_all_items()
    if filter_id:
        items = [i for i in items if i.id == filter_id]
    # guard clause 只考慮全量場景
    if len(items) == 0:
        print("沒有任何項目")
        return
    # ... 顯示邏輯
```

**正確**（guard clause 區分模式）：

```python
def list_items(filter_id=None):
    items = get_all_items()
    if filter_id:
        items = [i for i in items if i.id == filter_id]
        if len(items) == 0:
            print(f"找不到 ID 為 {filter_id} 的項目")
            return
    else:
        if len(items) == 0:
            print("沒有任何項目")
            return
    # ... 顯示邏輯
```

**最佳**（拆分為獨立函式）：

```python
def list_all_items():
    items = get_all_items()
    if len(items) == 0:
        print("沒有任何項目")
        return
    # ... 顯示邏輯

def get_item_by_id(item_id):
    item = find_item(item_id)
    if item is None:
        print(f"找不到 ID 為 {item_id} 的項目")
        return
    # ... 顯示邏輯
```

### 禁止行為

| 禁止行為 | 原因 |
|---------|------|
| 多模式函式中 guard clause 不區分模式 | 篩選結果會被全量模式的 guard clause 誤判（本錯誤模式核心問題） |
| 只測試全量模式的 guard clause 路徑 | 篩選模式的邊界條件未覆蓋，無法發現衝突 |
| guard clause 條件使用「共用閾值」而不考慮模式語義差異 | 同一數值在不同模式下可能有完全不同的含義（如 `len <= 1`） |

### Code Review 檢查項目

Code Review 時遇到多模式函式，必須確認以下項目：

| # | 檢查項目 | 判定方式 |
|---|---------|---------|
| 1 | 函式是否有 optional 參數控制不同行為路徑？ | 檢查參數列表中的 `=None`、`=False`、`Optional` |
| 2 | 函式內是否有 guard clause 或 early return？ | 搜尋 `if ... return` 模式 |
| 3 | 每個 guard clause 的條件是否在所有模式下語義一致？ | 逐模式代入條件驗證 |
| 4 | 測試是否覆蓋每個 guard clause 在每種模式下的行為？ | 檢查測試案例矩陣 |

---

## 偵測方式

- Code review 時搜尋「同一函式內有 optional 參數控制不同模式 + guard clause」的組合
- 測試時確保每個 guard clause 在「有參數」和「無參數」兩種呼叫方式下都有測試

---

**記錄日期**: 2026-03-18
**更新日期**: 2026-03-21
**記錄者**: rosemary-project-manager
**Version**: 1.1.0 - 補充防護措施章節（檢查清單、正確做法範例、Code Review 項目）（0.1.1-W12-008）
