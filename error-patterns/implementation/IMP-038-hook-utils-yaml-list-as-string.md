# IMP-038: hook_utils YAML 解析器回傳列表為換行分隔字串

## 錯誤摘要

| 項目 | 說明 |
|------|------|
| **分類** | Implementation |
| **嚴重性** | 中（測試失敗，功能邏輯錯誤） |
| **發現版本** | v0.1.2 |
| **相關 Ticket** | 0.1.2-W2-008 |

## 症狀

- 讀取 Ticket frontmatter 的 `where.files` 欄位時，預期得到 Python list，實際得到換行符分隔的字串
- 對字串做 `for f in where_files` 迭代時，Python 逐字符迭代
- `"./Lib/Delete.py"` 變成 `['.', '/', 'L', 'i', 'b', ...]`
- 路徑匹配邏輯全部失敗，衝突偵測無效

## 根因分析

**行為模式**：`hook_utils/hook_ticket.py` 的 YAML 解析器將 YAML 列表項目累積為換行符分隔的字串，而非轉換為 Python list。

**技術原因**：hook_utils 使用自訂的輕量級 YAML 解析（非 PyYAML），將多行 `- item` 格式串接為 `"item1\nitem2\nitem3"` 字串。

**消費端假設錯誤**：file-ownership-guard-hook 的 `get_active_tickets()` 和 `find_file_ownership_conflicts()` 假設 `where_files` 是 list 類型，未做型別檢查。

## 解決方案

新增 `_ensure_file_list()` 助手函式，統一處理兩種格式：

```python
def _ensure_file_list(where_value: object) -> list[str]:
    """確保 where.files 為列表格式。

    hook_utils YAML 解析器將列表項目累積為換行符分隔的字串，
    此函式轉換回列表格式。
    """
    if isinstance(where_value, list):
        return where_value
    if isinstance(where_value, str):
        if not where_value:
            return []
        return [line.strip() for line in where_value.split('\n') if line.strip()]
    return []
```

## 防護措施

1. **使用 hook_utils 讀取 YAML 資料時，永遠不要假設集合欄位是 list 類型**
2. 消費端必須做型別檢查或使用轉換函式
3. 新建 Hook 讀取 Ticket 的 list 欄位（where.files、children、blockedBy 等）時，加入 `_ensure_file_list()` 防護
4. 考慮未來在 hook_utils 層級修正，讓所有 YAML list 欄位回傳 Python list

## 檢查清單

寫新 Hook 讀取 Ticket frontmatter 時：

- [ ] 確認 hook_utils 回傳的集合欄位型別（可能是 str 而非 list）
- [ ] 加入 `_ensure_file_list()` 或等效的型別轉換
- [ ] 測試案例覆蓋 list 輸入和 str 輸入兩種情況

---

**Last Updated**: 2026-03-25
**Version**: 1.0.0
**Source**: 0.1.2-W2-008 Phase 3b 測試失敗修復過程
