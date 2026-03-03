# 版本推進決策規則

> **核心原則**：開發過程中發現的問題，優先在當前版本處理。

---

## 版本層級語義

| 層級 | 語義 | 核心問題 |
|------|------|---------|
| **Wave** | 執行批次 | 同一個目標，分幾批做？ |
| **Patch** | 獨立可交付 | 完成後能獨立發布嗎？ |
| **Minor** | 功能里程碑 | 用戶能感知到新功能嗎？ |
| **Major** | 架構里程碑 | 系統基本能力改變了嗎？ |

---

## Q1-Q4 語義判斷

```
[Q1] 和當前版本主題相同? → 是 → 新增 Wave
                          → 否 ↓
[Q2] 完成後能獨立發布? → 是 → 推進 Patch
                        → 否 ↓
[Q3] 需當前版本完成後才能開始? → 是 → 等待後推進 Patch
                                → 否 → 可並行開發，推進 Patch
[Q4] Patch 系列達成功能里程碑? → 是 → 推進 Minor
```

---

## 快速判斷檢查清單

1. [ ] 是開發衍生問題？ YES → **當前版本處理** STOP
2. [ ] [Q1] 和當前版本主題相同？ YES → **新 Wave** STOP
3. [ ] [Q2] 完成後能獨立發布？ YES → **新 Patch** STOP
4. [ ] [Q4] 達成功能里程碑？ YES → **新 Minor**

---

## 強制規則

| 規則 | 說明 |
|------|------|
| 開發衍生不推進版本 | 流程缺口/技術債務/Bug 在當前版本處理 |
| 工具改善不推進版本 | Hook/SKILL/驗證機制在當前版本處理 |
| 版本推進需語義理由 | 必須通過 Q1-Q4 判斷 |
| 活躍版本由 todolist.yaml 決定 | `status: active` 為 Source of Truth |

---

## Wave 獨立性原則

Wave 是相互隔離的執行單位。禁止跨 Wave 依賴和並行派發。

> 詳細 Wave 規則和 Ticket 歸屬判斷：.claude/references/version-progression-details.md

---

## 相關文件

- .claude/references/version-progression-details.md - Wave 獨立性、Ticket 歸屬、二元決策流程
- .claude/references/version-decision-case-studies.md - 案例分析
- .claude/rules/flows/ticket-lifecycle.md - Ticket 生命週期

---

**Last Updated**: 2026-03-02
**Version**: 3.0.0 - Progressive Disclosure 精簡，詳細內容移至 references/
