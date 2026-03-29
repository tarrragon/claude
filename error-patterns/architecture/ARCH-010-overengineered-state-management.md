# ARCH-010: 過度設計的狀態管理 — 框架機制已解決的問題不需要額外狀態層

## 症狀

- Phase 1 設計引入了完整的狀態管理方案（Riverpod Notifier + family provider + 參數穿透）
- 直到 Phase 4a linux 審查才發現框架內建機制（ValueKey）就能解決問題
- 程式碼量從「1 行 ValueKey」膨脹為「150+ 行 Notifier + 參數穿透 + 測試」

## 根因

**設計階段未優先驗證框架內建機制是否足夠**。

lavender-interface-designer 在 Phase 1 分析問題後，跳過了「Flutter Key 機制是否足夠」的驗證，直接設計了全域狀態管理方案。後續 Phase 2/3a/3b 都基於這個前提繼續，直到 Phase 4a linux 審查才質疑根本設計。

行為模式：
1. 看到「狀態在 rebuild 時丟失」→ 直覺反應「需要外部狀態管理」
2. 未驗證 Flutter 的 Key reconciliation 機制是否已解決此問題
3. 後續 Phase 全部基於錯誤前提構建，成本累積

## 影響

- 浪費 Phase 3b 實作 + Phase 4b 重構的工時
- 引入不必要的 `keepAlive: true` provider（記憶體洩漏風險）
- panelIndex 參數穿透 3 層（不必要的耦合）

## 解決方案

Phase 4b 回滾：刪除 Notifier + .g.dart + 測試，回退為 StatelessWidget，只保留 `ValueKey(eventKey)` 在 ExpansionTile 上。

## 防護措施

### Phase 1 設計檢查清單（Widget 狀態管理場景）

在設計外部狀態管理方案前，必須依序驗證：

| 步驟 | 問題 | 若「是」則 |
|------|------|----------|
| 1 | 框架內建機制（Key/GlobalKey）是否已解決？ | 停止，使用 Key |
| 2 | StatefulWidget 本地狀態是否足夠？ | 停止，使用本地狀態 |
| 3 | 狀態是否需要跨 Widget 共享？ | 考慮 InheritedWidget 或 Provider |
| 4 | 狀態是否需要持久化或跨頁面？ | 使用全域狀態管理 |

**原則：從最簡單的方案開始驗證，逐步升級複雜度，而非直接跳到最複雜的方案。**

### 代理人 Prompt 改善

Phase 1 派發 lavender-interface-designer 時，應在 prompt 中加入：
```
設計前必須先驗證框架內建機制是否已解決問題（如 Flutter 的 Key、React 的 key prop）。
只有在內建機制不足時，才設計外部狀態管理方案。
```

## 相關 Ticket

- 0.2.1-W7-003 — Tool 氣泡 ExpansionTile 摺疊狀態在對話刷新時被重置

## 適用範圍

任何 UI 框架（Flutter、React、SwiftUI 等）中，遇到「Widget/Component 狀態在重建時丟失」的問題時。

---

**Created**: 2026-03-29
**Source**: 0.2.1-W7-003 Phase 4a linux Garbage 評分
