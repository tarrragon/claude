# CQ-003: Exception 定義後無實際拋出點（設計意圖未實現）

**發現日期**: 2026-03-07
**相關 Ticket**: 0.1.0-W5-001, 0.1.1-W5-003

## 症狀

- `exceptions.py` 中定義了 `HandoffDirectionUnknownError`
- 但 `resume.py`、`handoff.py`、`handoff_gc.py` 均未在讀取未知 direction 時拋出此 exception
- Exception 類別存在但從未被拋出（dead code）

## 根因

設計 Exception 階層時，超前定義了「未來可能需要」的 exception，但 Phase 3b 實作時只實作了當下需要的。這是 IMP-013「設計意圖未實現」模式的再現：新增了 API（exception 類別），但未實作對應的使用端。

## 解決方案

在讀取 direction 後加入驗證，實際拋出已定義的 exception。

## 預防措施

1. 定義 Exception 類別時，同步建立對應的觸發點（拋出 exception 的程式碼）
2. 若 exception 為「未來預留」，在類別 docstring 中明確標注
3. Phase 4 重構評估時，檢查是否有未使用的 exception 類別（IMP-013 模式）
4. 可以使用靜態分析工具或測試確認每個 exception 至少有一個測試路徑
