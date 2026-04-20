# IMP-049: Hook 原始碼引用未定義常數

## 症狀

- Hook 測試全部 FAILED，錯誤為 `NameError: name 'XXX' is not defined`
- Hook 在生產環境中被 try-except 包裹，NameError 被靜默吞掉，回傳 `allow`
- Hook 看似正常運作（不阻止任何操作），但實際上所有檢查邏輯從未執行

## 根因

Hook 原始碼在重構或初始 sync 時，函式內引用的模組級常數（正則模式、允許清單、驗證矩陣等）未被一起帶入。

具體案例：`5w1h-compliance-check-hook.py` 引用 6 個常數但均未定義：
- `WHO_PATTERN_DELEGATE`, `WHO_PATTERN_SELF`, `HOW_PATTERN`（正則模式）
- `ALLOWED_AGENTS`, `ALLOWED_TASK_TYPES`, `VIOLATION_MATRIX`（驗證清單）

## 行為模式

1. 開發者將 Hook 邏輯拆分為函式 + 常數
2. 函式被正確放入檔案，但常數定義遺漏
3. Hook 的 `main()` 函式有 try-except，NameError 被捕獲後回傳 allow
4. Hook 不阻止任何操作 → 看起來「正常運作」
5. 只有跑測試才會暴露 NameError

## 解決方案

1. 補回所有缺失的常數定義
2. 測試修復後驗證 Hook 的所有檢查路徑（allow 和 block）都能正確觸發

## 預防措施

- Hook 修改後必須跑對應的測試套件
- Hook 的 try-except 不應吞掉 NameError/ImportError 等程式碼缺陷類異常
- Code Review 時檢查：所有引用的模組級名稱是否有對應的定義

## 關聯 Ticket


---

**Created**: 2026-04-07
**Category**: implementation
