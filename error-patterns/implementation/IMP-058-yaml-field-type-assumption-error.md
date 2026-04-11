---
id: IMP-058
title: YAML frontmatter 欄位型別假設錯誤（list vs string）
category: implementation
severity: high
first_seen: 2026-04-11
ticket: 0.17.4-W5-002
---

# IMP-058: YAML frontmatter 欄位型別假設錯誤（list vs string）

## 症狀

- acceptance-gate-hook 的 children/spawned_tickets 檢查靜默失敗
- ANA Ticket 有 pending 子任務卻能成功 complete
- Hook 日誌無明確錯誤（AttributeError 被 try-except 吞掉）

## 根因

YAML 解析後，清單欄位（如 `children`、`spawned_tickets`）回傳 Python `list`，但 parser 函式假設為 `string` 並呼叫 `.strip()`：

```python
# 錯誤：假設為 string
children_str = frontmatter.get("children", "").strip()
# → AttributeError: 'list' object has no attribute 'strip'

# 正確：處理 list 和 string 雙型別
children_raw = frontmatter.get("children", [])
if isinstance(children_raw, list):
    children = [str(c).strip() for c in children_raw if c]
elif isinstance(children_raw, str):
    # string 格式解析邏輯
    ...
```

**觸發條件**：frontmatter 中的清單欄位有值時。空清單 `[]` 不觸發（`.get("children", "")` 回傳空 list，但空 list 沒有 `.strip()` 也會 crash — 只是空 list 的 falsy 特性讓程式碼在 `if not children_str` 就提前返回了）。

## 影響範圍

- `acceptance_checkers/ticket_parser.py` — `extract_children_from_frontmatter`
- `acceptance_checkers/ana_spawned_checker.py` — `extract_spawned_tickets_from_frontmatter`
- 任何從 YAML frontmatter 讀取清單欄位並假設為 string 的程式碼

## 解決方案

對所有讀取 YAML 清單欄位的函式，使用 `isinstance` 判斷型別：
1. `list` → 直接使用（過濾空值）
2. `str` → 走原有的字串解析邏輯（向後相容）
3. 其他 → 回傳空清單

## 防護措施

### 開發時

- **從 YAML frontmatter 讀取欄位時，永遠不要假設型別**
- 清單欄位（`children`、`spawned_tickets`、`blockedBy`、`relatedTo`）解析後為 Python `list`
- 標量欄位（`status`、`title`、`type`）解析後為 Python `str`

### Code Review 檢查項

- [ ] 從 frontmatter 讀取的欄位是否有型別假設？
- [ ] `.strip()`、`.split()` 等 string 方法是否在 list 型別上呼叫？
- [ ] 預設值是否與實際型別一致？（`get("children", "")` 應改為 `get("children", [])`）

### Hook 拆分時的特別注意

此 bug 在 W3-001 拆分 acceptance-gate-hook 為 orchestrator + checkers 時引入。拆分大函式時，原本可能在同一個 context 中處理的型別轉換，拆分後容易在新模組中遺失。

## 關聯模式

- IMP-049: Hook 常數未定義靜默失敗 — 同屬「try-except 吞掉關鍵錯誤」模式
- IMP-003: 重構作用域變更回歸 — 同屬「拆分/重構引入的回歸」模式
- quality-baseline 規則 4: Hook 失敗必須可見 — 此 bug 違反雙通道可觀測性要求
