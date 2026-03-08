# IMP-025: 新模組引入 `except Exception: pass` 靜默吞掉異常

## 分類
- **類型**: implementation
- **嚴重度**: 中
- **發現版本**: v0.1.0
- **發現日期**: 2026-03-08
- **來源 Ticket**: 0.1.0-W11-004

## 模式描述

實作代理人（thyme/parsley）在建立新模組時，對非關鍵操作使用 `except Exception: pass`
或類似的靜默異常處理，導致資料一致性錯誤、IO 失敗等問題在執行時完全不可見。

此模式在 Phase 3b 實作階段容易引入，並在 Phase 4a（linux Good Taste 審核）才被發現。

## 具體案例

### 案例：version_shift.py 的跨版本引用更新

`_update_cross_version_refs()` 中的跨 Ticket 掃描：

```python
# 錯誤：靜默吞掉 YAML 解析錯誤
for ticket_path in other_tickets:
    try:
        content = ticket_path.read_text()
        # ... 執行替換 ...
        ticket_path.write_text(updated)
    except Exception:
        pass  # ← 資料一致性錯誤完全不可見

# 正確：至少輸出警告（修復後的版本）
for ticket_path in other_tickets:
    try:
        content = ticket_path.read_text()
        # ... 執行替換 ...
        ticket_path.write_text(updated)
    except Exception as e:
        format_warning(f"更新 {ticket_path.name} 跨版本引用失敗: {e}")
        # 繼續處理其他 ticket，但讓失敗可見
```

### 常見出現位置

實作代理人引入靜默異常的典型場景：

| 場景 | 常見的靜默處理 | 正確做法 |
|------|--------------|---------|
| 批量遍歷（迴圈中） | `except Exception: pass` | 輸出警告，繼續循環 |
| 非關鍵 IO（備份） | `except Exception: pass` | 記錄警告，回傳 False |
| 清理操作 | `except Exception: pass` | 記錄 debug，繼續 |
| 格式解析 | `except Exception: pass` | 輸出警告，跳過此項目 |

## 根本原因

1. **認知錯誤**：代理人認為「非關鍵操作失敗不影響主流程，靜默跳過是合理的」
2. **過度防禦**：在批量遍歷中怕單一失敗中斷整個迴圈，用 `pass` 做過度防護
3. **缺乏觀測性意識**：未意識到靜默失敗讓除錯變得幾乎不可能

實際上，即使操作確實「非關鍵」，失敗也應該被**可見地記錄**。
靜默失敗和允許失敗是兩種不同的設計決策，前者從不可接受。

## 影響

- 資料一致性問題（如跨版本引用未更新）在執行時完全不可見
- 除錯時無任何線索，用戶只能看到「命令成功完成」但結果不正確
- 違反品質基線規則 4（所有異常必須可見）

## 解決方案

### except 區塊最低要求

每個 `except` 區塊必須滿足至少一項：
1. 輸出到 stderr（`print(..., file=sys.stderr)` 或 `logger.warning()`）
2. 輸出到 UI（`format_warning()` 或等效函式）
3. 回傳明確的失敗值（`return False`）並由呼叫端處理

唯一可接受的例外：在 docstring 或行內注解中明確說明靜默的理由。

```python
# 可接受：有明確說明的靜默
try:
    temp_file.unlink()
except FileNotFoundError:
    pass  # 目標檔案不存在視為清理成功，無需警告

# 不可接受：無說明的靜默
try:
    update_cross_refs(ticket)
except Exception:
    pass  # ← 資料一致性操作靜默失敗，永遠不可接受
```

### 批量迴圈中的異常處理模板

```python
failed_items = []
for item in items:
    try:
        process(item)
    except Exception as e:
        format_warning(f"處理 {item} 失敗: {e}")
        failed_items.append(item)

if failed_items:
    format_warning(f"共 {len(failed_items)} 個項目處理失敗，請手動檢查")
```

## 防護措施

### Phase 3b 實作時

- [ ] 所有 `except` 區塊至少輸出 warning 或 return 明確失敗值
- [ ] `except Exception: pass` 在 code review 時視為 bug，不是風格問題
- [ ] 批量遍歷中的異常應收集並在最後統一報告

### Phase 4a 審核時

- [ ] linux Good Taste 視角專門掃描 `except.*pass` 和 `except.*:$`（空 except body）
- [ ] 靜默異常在 Worth-It Filter 中評定為「高幅度（Bug）」，不論風險

### 程式碼規則

品質基線規則 4 的 `except` 區塊要求（`.claude/rules/core/quality-baseline.md`）：
- 必須寫入 stderr 或日誌
- `except` 後直接 `pass` 或 `return` 而不記錄：**必須在注解中說明原因**

## 相關錯誤模式

- IMP-006: Hook 靜默失效（同屬「錯誤不可見」類型）
- IMP-003: 重構作用域迴歸（Phase 4a 才發現的 Phase 3b 問題，同屬「後期發現」類型）
