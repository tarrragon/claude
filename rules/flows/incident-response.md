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
| 效能問題 | - | ginger-performance-tuner |
| 安全問題 | - | security-reviewer |

---

## 修復三階段強制規則（分析→審核→執行）

> **來源**：0.31.1-W1-009 — 跳過分析審核直接派發修復 62 個 error，導致新增 25 個測試失敗。

修復任何錯誤必須嚴格遵循三個階段，禁止跳過任何階段。

```
[階段 1] 分析
    派發 incident-responder 分析根因
    → 分類錯誤（按架構層、依賴關係分組）
    → 識別影響範圍
    → 產出分析報告到 Ticket

[階段 2] 方案設計與審核
    → 設計解決方案（修改哪些檔案、如何修改）
    → 派發 parallel-evaluation 多視角審查方案
    → 確認方案不會引入新問題

[階段 3] 執行修復
    → 依審核通過的方案執行
    → 按「測試驗證金字塔」逐層驗證
```

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

---

## 測試驗證金字塔順序規則

> **來源**：0.31.1-W1-009 — 修復後直接跑全量測試（3+ 分鐘），應先用單元測試快速驗證。

修復完成後的測試驗證必須從底層開始，逐層上升，前一層通過才進入下一層。

```
[Level 1] 單元測試（秒級）
    → 執行修改檔案對應的單元測試
    → 失敗 → 立即修復，不進入下一層
    → 無對應單元測試 → 先評估是否需要建立

[Level 2] 模組測試（秒～分鐘級）
    → 執行修改模組/目錄的測試
    → 例如：flutter test test/unit/domain/export/

[Level 3] 相關整合測試（分鐘級）
    → 執行涉及修改模組的整合測試
    → 例如：flutter test test/integration/uc02_*

[Level 4] 全量測試（僅在 Level 1-3 全通過後）
    → 使用摘要腳本或 compact reporter
    → 確認無迴歸
```

**強制規則**：

| 規則 | 說明 |
|------|------|
| 禁止跳級 | Level 1 未通過前禁止執行 Level 2+ |
| 無單元測試時 | 先評估是否需建立，再決定從哪層開始 |
| 全量測試限制 | 僅在 Level 1-3 全通過後才執行 |
| 輸出限制 | 全量測試必須用 compact reporter 或摘要腳本，防止 context 溢出 |

---

## 禁止行為

| 禁止 | 說明 |
|------|------|
| 直接修改程式碼 | 只能分析，不能修復 |
| 跳過 Ticket 建立 | 必須建立 Ticket |
| 自行決定派發 | 只提供建議，PM 決定 |
| 跳過分析直接修復 | 必須先分析根因和影響範圍 |
| 修復後直接跑全量測試 | 必須從單元測試開始逐層驗證 |

---

## 相關文件

- .claude/references/incident-response-details.md - 詳細規則（多視角分析、安全等級、報告格式）
- .claude/agents/incident-responder.md - 代理人定義
- .claude/rules/forbidden/skip-gate.md - Skip-gate 防護
- .claude/rules/core/decision-tree.md - 主線程決策樹

---

**Last Updated**: 2026-03-05
**Version**: 3.1.0 - 新增修復三階段強制規則（分析→審核→執行）和測試驗證金字塔順序規則（W1-009）
