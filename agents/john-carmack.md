---
name: john-carmack
description: "[DEPRECATED] 已合併至 ginger-performance-tuner。效能系統架構分析、熱路徑優化、控制流簡化、狀態管理設計等能力已整合到 ginger-performance-tuner v2.0.0。"
model: sonnet
---

# john-carmack [DEPRECATED]

**狀態**：已廢棄（Deprecated）

**合併日期**：2026-03-02

**合併目標**：`.claude/agents/ginger-performance-tuner.md`

**合併原因**：ginger-performance-tuner 和 john-carmack 功能重疊度約 60%（兩者都分析效能瓶頸、都只提供策略不執行程式碼）。合併為統一的「效能分析與架構優化」Agent，降低派發時的認知負擔。

---

## 重定向說明

原 john-carmack 的所有能力已整合至 ginger-performance-tuner v2.0.0：

| 原 john-carmack 能力 | 對應 ginger 章節 |
|----------------------|----------------|
| 熱路徑分析和優化 | 核心職責 > 4. 熱路徑分析和架構優化 |
| 狀態管理和副作用最小化 | 核心職責 > 5. 狀態管理和副作用最小化 |
| 控制流簡化和架構邊界設計 | 核心職責 > 4. 熱路徑分析和架構優化 |
| 最壞情況優化原則 | 設計原則 > 最壞情況優化 |
| 函式程式設計紀律 | 設計原則 > 函式程式設計紀律 |
| 淺層控制流原則 | 設計原則 > 淺層控制流 |
| 集中化控制原則 | 設計原則 > 集中化控制 |

---

## 對外部引用的影響

以下檔案仍引用 john-carmack，應在後續版本逐步更新為 ginger-performance-tuner：

- `.claude/agent-collaboration.md`
- `.claude/tdd-collaboration-flow.md`

---

**Last Updated**: 2026-03-02
**Version**: 2.0.0 - Deprecated, merged into ginger-performance-tuner
**Ticket**: 0.31.0-W28-003
