# PC-052: 忽略既有 error-pattern 警告直接實作

## 錯誤症狀

- 實作修改後發現 error-patterns 已有完全相同的失敗記錄
- 修改方向與 error-pattern 警告的「錯誤修復嘗試」完全一致
- 需要額外的 WRAP 決策和回退 commit 來修正

## 根因分析

**直接原因**：領取 Ticket 後未查詢 error-patterns，直接按 Ticket 描述實作。

**行為鏈**：
1. Ticket 描述了問題和修復方向（W10-002：修改 `run_hook_safely` exit code）
2. 認領檢查清單有「已查詢是否有相關的 error-patterns」但未執行
3. 直接實作 Ticket 描述的修復方案
4. 實作完成後才發現 IMP-049 已記錄：
   - 完全相同的修改（`run_hook_safely` 改為 exit 0）
   - 已失敗 2 次
   - 明確警告「不要修改 Hook 系統核心來繞過 CLI bug」

**深層原因**：Ticket 的修復方向被視為「已驗證的指令」而非「待驗證的假設」。Ticket 建立時可能不知道 IMP-049 的存在。

## 解決方案

認領 IMP 類型 Ticket 後，**在閱讀 Ticket 和實作之間**，執行：

```bash
# 用 Ticket 的關鍵字查詢 error-patterns
/error-pattern query hook exit code
/error-pattern query run_hook_safely
/error-pattern query <Ticket 涉及的核心函式名>
```

如果找到匹配的 error-pattern：
1. 閱讀完整記錄，特別是「錯誤的修復嘗試」和「防護措施」章節
2. 評估 Ticket 的修復方向是否與已知失敗嘗試重疊
3. 如果重疊 → 更新 Ticket 描述或建議替代方案，不盲目執行

## 防護措施

| 規則 | 說明 |
|------|------|
| 認領後先查 error-patterns | 用核心函式名和問題關鍵字搜尋 |
| Ticket 描述是假設不是指令 | Ticket 建立時的資訊可能不完整 |
| 修改高影響函式前必讀歷史 | `run_hook_safely` 等核心函式有累積的失敗經驗 |
| 發現衝突時暫停實作 | 回報 PM 或用 WRAP 重新評估 |

## 與認領檢查清單的關係

認領檢查清單已有「已查詢是否有相關的 error-patterns」項目（IMP/ADJ 類型），但：
- 這是 checkbox 形式，容易被跳過
- 查詢關鍵字的選擇影響命中率（用函式名比用問題描述更精確）
- 建議查詢時同時用「問題描述關鍵字」和「涉及的核心函式名」

## 關聯

- **Ticket**: 0.17.3-W10-002
- **被忽略的 error-pattern**: IMP-049（hook error 是 CLI bug，修改 run_hook_safely 已失敗 2 次）
- **修正方式**: WRAP 決策框架（選擇性回退）

---

**Created**: 2026-04-10
**Category**: process-compliance
**Severity**: 中（浪費一次 commit + 需要額外回退）
**Key Lesson**: error-pattern 查詢不是儀式，是防止重蹈覆轍的實質檢查
