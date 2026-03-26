# 事件回應流程

Skip-gate 防護機制的核心流程。

---

## 強制流程

```
錯誤發生 → /pre-fix-eval → 派發 incident-responder → 分析分類
→ 建立 Ticket → PM 決定派發 → 對應代理人修復
```

---

## 強制觸發條件

| 觸發情境 | 識別關鍵字 |
|---------|-----------|
| 測試失敗 | "test failed", "測試失敗", "FAILED" |
| 編譯錯誤 | "compile error", "編譯錯誤", "build failed" |
| 執行時錯誤 | "runtime error", "exception", "crash" |
| 用戶回報問題 | "bug", "問題", "不正常", "出錯" |
| 代理人環境問題 | "prompt too long", "context", "token limit" |

---

## 派發對應表

| 錯誤分類 | 子分類 | 派發代理人 |
|---------|-------|-----------|
| 編譯錯誤 | 依賴問題 | system-engineer |
| 編譯錯誤 | 類型錯誤 | parsley-flutter-developer |
| 測試失敗 | 測試本身問題 | sage-test-architect |
| 測試失敗 | 實作與預期不符 | parsley-flutter-developer |
| 測試失敗 | 設計邏輯錯誤 | system-analyst |
| 執行時錯誤 | 環境問題 | system-engineer |
| 執行時錯誤 | 資料問題 | data-administrator |
| 執行時錯誤 | 程式錯誤 | parsley-flutter-developer |
| 代理人環境 | context 耗盡（prompt too long） | PM 重新拆分子任務（縮小範圍後重新派發） |
| 效能問題 | - | ginger-performance-tuner |
| 安全問題 | - | security-reviewer |

---

## 修復三階段強制規則（分析→審核→執行）

> **來源**：0.31.1-W1-009 — 跳過分析審核直接派發修復 62 個 error，導致新增 25 個測試失敗。

修復任何錯誤必須嚴格遵循三個階段：(1) 分析 → (2) 方案設計與審核 → (3) 執行修復。禁止跳過任何階段。

**禁止行為**：

| 禁止 | 說明 | 來源 |
|------|------|------|
| 跳過分析直接修復 | 必須先分析分類，識別根因和影響範圍 | W1-009 |
| 跳過審核直接執行 | 多錯誤（>5 個）的修復方案必須經 parallel-evaluation 審查 | W1-009 |
| 將多層錯誤合併為單一修復任務 | 跨架構層的錯誤必須拆分為獨立子任務 | W1-009 |

**認知負擔拆分閾值**：

| 錯誤數量 | 處理方式 |
|---------|---------|
| 1-5 個（同一檔案/模組） | 可合併為單一修復 Ticket |
| 6-15 個（跨少數檔案） | 按架構層拆分為 2-3 個子任務 |
| >15 個（跨多檔案/多層） | 強制分析分類，按依賴關係拆分，逐批修復 |

> 三階段詳細流程、測試驗證金字塔 Level 1-4、CLI 調查步驟、操作失誤根因分析：.claude/references/incident-response-details.md

---

## 測試驗證金字塔（強制）

修復後從底層逐層驗證，前一層通過才進入下一層：單元測試 → 模組測試 → 整合測試 → 全量測試。

| 規則 | 說明 |
|------|------|
| 禁止跳級 | Level 1 未通過前禁止執行 Level 2+ |
| 全量測試限制 | 僅在 Level 1-3 全通過後才執行 |

---

## CLI/工具失敗調查（強制）

CLI 或內部工具報錯時，**禁止假設歸因**，必須依序：查語法 → 字面解讀 → 比對狀態 → 歸因。

> 詳細步驟：.claude/references/incident-response-details.md（CLI/工具失敗調查步驟章節）

---

## 操作失誤根因分析（強制）

操作行為失誤（非程式碼錯誤）必須執行三層根因分析：設計邊界 → 使用情境 → 說明充分性。

| 規則 | 說明 |
|------|------|
| 操作失誤必須三層分析 | 禁止只記錄「禁止行為」而不分析根因 |
| 分析結果必須建立 Ticket | 後續改善行動必須有追蹤 |

> 三層分析詳細流程和模板：.claude/references/incident-response-details.md（操作失誤根因分析章節）
> 方法論：.claude/methodologies/operational-error-root-cause-methodology.md

---

## 禁止行為

| 禁止 | 說明 |
|------|------|
| 直接修改程式碼 | 只能分析，不能修復 |
| 跳過 Ticket 建立 | 必須建立 Ticket |
| 自行決定派發 | 只提供建議，PM 決定 |
| 跳過分析直接修復 | 必須先分析根因和影響範圍 |
| 修復後直接跑全量測試 | 必須從單元測試開始逐層驗證 |
| 工具報錯時假設歸因 | 必須先查語法再歸因（PC-005） |

---

## 相關文件

- .claude/methodologies/operational-error-root-cause-methodology.md - 操作失誤三層根因分析方法論
- .claude/references/incident-response-details.md - 詳細規則（多視角分析、安全等級、報告格式）
- .claude/agents/incident-responder.md - 代理人定義
- .claude/pm-rules/skip-gate.md - Skip-gate 防護
- .claude/pm-rules/decision-tree.md - 主線程決策樹

---

**Last Updated**: 2026-03-26
**Version**: 3.5.0 - 派發對應表新增 context 耗盡子分類和代理人環境問題觸發條件（0.2.0-W5-011）
