# IMP-018: 生命週期不完整 — 狀態更新未串接後續清理

## 錯誤模式

狀態更新函式只完成「標記」動作，但未執行對應的「清理/移動」動作，導致資源殘留。

## 症狀

- 已處理的資源持續出現在待處理清單中
- Hook 或排程任務重複觸發已完成的項目
- 手動清理後問題暫時消失，但新產生的項目仍會殘留

## 根因分析

### 行為模式

開發者實作「狀態標記」和「資源清理」為獨立函式（正確的 SRP），但在呼叫端只串接了標記函式，遺漏了清理函式的呼叫。

### 為什麼會發生

1. **兩個函式各自測試通過**：`mark_handoff_as_resumed()` 和 `archive_handoff_file()` 都有獨立測試且通過，掩蓋了串接缺失
2. **呼叫端缺少整合測試**：`_execute_resume()` 的測試只驗證了「resumed_at 已更新」，未驗證「檔案已從 pending/ 移至 archive/」
3. **SRP 拆分後的串接盲點**：拆分為獨立函式是正確的，但呼叫端的「完整流程」驗證被忽略

## 具體案例

**發現於**：0.1.0-W2-018

```python
# resume.py - _execute_resume()
# 修復前：只標記，不歸檔
if not mark_handoff_as_resumed(ticket_id):
    return 1
# 缺少：archive_handoff_file(ticket_id)

# 修復後：標記 + 歸檔
if not mark_handoff_as_resumed(ticket_id):
    return 1
if not archive_handoff_file(ticket_id):
    print(format_warning(...))  # 非致命，只警告
```

**影響**：handoff-reminder-hook 每次 session 啟動重複提醒已恢復的任務。

## 解決方案

在呼叫端補上遺漏的清理函式呼叫。清理失敗應為非致命錯誤（核心功能已完成）。

## 預防措施

### 設計層面

| 措施 | 說明 |
|------|------|
| 整合測試覆蓋完整流程 | 測試不只驗證狀態變更，也驗證副作用（檔案移動、資源釋放） |
| 生命週期檢查清單 | 每個「狀態變更」操作旁列出對應的「資源清理」操作 |

### Code Review 檢查點

遇到狀態更新函式時，問：

1. 狀態更新後，相關資源（檔案、快取、註冊）是否需要同步處理？
2. 呼叫端是否串接了完整的生命週期動作？
3. 整合測試是否驗證了「狀態 + 資源」的一致性？

## 相關模式

- IMP-010: GC 狀態語義衝突（同為資源清理問題，但根因不同）
- ARCH-002: 不完整清理（Plugin 解除安裝只清理部分儲存層）

## 關聯 Ticket

- 0.1.0-W2-018: 修復 ticket resume 完成後自動清除 pending handoff JSON 檔案

---

**Last Updated**: 2026-03-06
**Version**: 1.0.0
