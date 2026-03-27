# PC-030: Phase 4 未使用程式碼判斷未全專案 grep 驗證

## 錯誤分類

| 項目 | 值 |
|------|---|
| 編號 | PC-030 |
| 類別 | process-compliance |
| 嚴重度 | 中 |
| 首次發現 | 2026-03-27 |
| 相關 Ticket | 0.2.0-W3-031 |

## 症狀

Phase 4 評估報告宣告某函式為「未使用程式碼」，建議移除並建立技術債 Ticket。但該函式實際上仍被其他模組引用，Ticket 執行時才發現描述不正確。

## 根因分析

Phase 4 重構代理人（cinnamon）在評估「未使用程式碼」時，只追蹤了當前 Ticket 變更範圍內的引用移除，未對全專案執行 grep 驗證。

具體案例：
- 0.2.1-W2-003 將 `_sessionSubtitle` 中的 `extractProjectName` 呼叫移除
- Phase 4 判定 `extractProjectName` 為未使用
- 實際上 0.2.1-W2-001（並行開發的專案頁籤功能）在 `session_list_page.dart:147` 和 `session_group_utils.dart:39-41` 新增了引用

**根本原因**：並行開發的 Ticket 之間產生的引用，在單一 Ticket 的 Phase 4 視角中不可見。

## 解決方案

Phase 4 判斷「未使用程式碼」時，必須執行全專案 grep 搜尋確認零引用：

```bash
# 強制步驟：判定未使用前必須執行
grep -rn "functionName" ui/lib/ ui/test/ server/
```

僅當 grep 結果為零匹配（排除定義本身）時，才可判定為未使用。

## 防護措施

### 給 Phase 4 代理人（cinnamon）的強制檢查清單

判定任何程式碼為「未使用」前：

| 步驟 | 動作 | 驗證方式 |
|------|------|---------|
| 1 | 全專案 grep 搜尋函式/類別名稱 | `grep -rn "name" ui/lib/ server/` |
| 2 | 確認引用數為 0（排除定義行） | 人工確認每個匹配 |
| 3 | 檢查是否有並行 Ticket 可能新增引用 | 查看同 Wave/版本的其他 Ticket |

### 給 PM 的驗證點

接收到「移除未使用程式碼」類型的技術債 Ticket 時，在 claim 前先驗證：

```bash
grep -rn "functionName" ui/lib/ server/
```

## 行為模式

Phase 4 代理人傾向於在自己 Ticket 的變更範圍內思考，忽略了並行開發產生的新引用。這是「tunnel vision」問題 — 重構評估的視角需要比實作更寬。

---

**Last Updated**: 2026-03-27
**Version**: 1.0.0
