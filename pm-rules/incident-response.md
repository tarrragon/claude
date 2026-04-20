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

> **來源**：跳過分析審核直接派發批量修復，容易引入新測試失敗。

修復任何錯誤必須嚴格遵循三個階段：(1) 分析 → (2) 方案設計與審核 → (3) 執行修復。禁止跳過任何階段。

**禁止行為**：

| 禁止 | 說明 |
|------|------|
| 跳過分析直接修復 | 必須先分析分類，識別根因和影響範圍 |
| 跳過審核直接執行 | 多錯誤（>5 個）的修復方案必須經 parallel-evaluation 審查 |
| 將多層錯誤合併為單一修復任務 | 跨架構層的錯誤必須拆分為獨立子任務 |

**認知負擔拆分閾值**：

| 錯誤數量 | 處理方式 |
|---------|---------|
| 1-5 個（同一檔案/模組） | 可合併為單一修復 Ticket |
| 6-15 個（跨少數檔案） | 按架構層拆分為 2-3 個子任務 |
| >15 個（跨多檔案/多層） | 強制分析分類，按依賴關係拆分，逐批修復 |

> 三階段詳細流程、測試驗證金字塔 Level 1-4、CLI 調查步驟、操作失誤根因分析：.claude/references/incident-response-details.md

---

## Reality Test 閘門（強制）

> **來源**：PC-063 — W5-031 ANA Ticket 列 4 候選方案（A/B/C/D）皆基於未驗證假設，方案全部不匹配真正根因。PM 清 context 後 resume 時主動進行重現實驗，才發現方案需新增 F/H 才能根治。

**核心規則**：分析階段中，**禁止在未完成重現實驗前列候選方案**。Reality Test 是 ANA / incident-response / WRAP Widen 三類流程的共同前置閘門。

### 為什麼是強制閘門

| 沒做 Reality Test 的後果 | PC-063 觀察到的具體傷害 |
|---------------------|---------------------|
| 候選方案基於假設根因 | 4/4 候選方案脫靶 |
| WRAP Widen 收斂於同質假設變體 | 同一假設下衍生不同包裝的方案，仍未碰到真因 |
| 修復 Ticket 衍生後仍無效 | 方案 A/B/C/D 都做完問題仍重現 |
| 浪費代理人派發成本 | 派發實作後重新發現「實作了錯誤的東西」 |

### 4 類問題的重現實驗形式對照

| 問題類型 | 重現實驗形式 | 實驗最低證據 |
|---------|------------|------------|
| **測試污染** | 清理污染產物 → 跑全測 / 逐檔案測 → 觀察污染是否再現 → 鎖定 culprit 測試 | 列出污染源測試檔案 + 確認的 mock 缺失或路徑錯誤行號 |
| **Hook 失效** | 手動 stdin 觸發 hook script → 檢查 stderr / hook-logs → 對照 settings.json 註冊與預期觸發條件 | hook 實際 exit code + stderr 輸出 + log 確認執行路徑 |
| **CLI 異常** | 重現 CLI 命令 → 比對輸出與 docstring/--help → 確認 cwd 與環境變數 | 完整命令 + 實際輸出 + 預期輸出 + 兩者差異 |
| **邏輯 bug** | 寫 minimal failing test 重現條件 → 確認測試失敗 → 追根因到具體函式 / 行號 | failing test 程式碼 + 失敗訊息 + 定位的 source line |

### Reality Test 證據必填欄位

進行 Reality Test 後，必須在 ANA Ticket 的「重現實驗結果」章節（PC-063 防護 1，由 ticket-builder 自動帶入）填寫：

| 欄位 | 內容 |
|------|------|
| **實驗方法** | 用什麼指令/測試重現？關鍵環境條件是什麼？ |
| **實驗執行** | 實際執行步驟、觀察到的行為（含異常輸出） |
| **實驗發現** | 已驗證的事實 vs 仍未驗證的假設（清楚分開） |

### 禁止行為

| 禁止 | 原因 |
|------|------|
| 在 ANA Ticket Problem Analysis 章節列方案而未完成 Reality Test | 方案會基於未驗證假設，PC-063 已證明 100% 脫靶率風險 |
| WRAP Widen 階段提出方案前未完成重現 | Widen 出的選項仍是同假設變體，不增加真實覆蓋 |
| incident-responder 報告未含實驗證據即建立修復 Ticket | 修復方向錯誤，浪費後續派發成本 |
| 以「時間緊迫」為由跳過重現 | Reality Test 是節省時間的措施，跳過會在實作階段付出更高代價 |

### 與其他流程的關係

| 流程 | Reality Test 觸發點 |
|------|------------------|
| ANA Ticket | claim 後、Problem Analysis 完成「重現實驗結果」章節前禁止列方案 |
| /wrap-decision Widen | Widen 階段第一步必須是 Reality Test，再列選項 |
| incident-responder | 報告必須含實驗證據區塊才視為完整 |
| Phase 4 重構評估 | 多視角審查前必須先重現問題（不適用純規格類重構） |

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

### 核心系統修改前必須先搜社群（強制）

當手動測試正常但外部 CLI / runtime 仍顯示異常時，這是外部工具已知 bug 的強烈信號。**修改核心系統（Hook / CLI 共用模組 / 框架基礎設施）前，必須先搜尋社群確認是否為已知問題**。

| 觸發條件 | 動作 |
|---------|------|
| 手動重現測試正常，CLI 仍異常 | 先搜尋外部 bug 報告，而非修改自己程式碼 |
| 連續 2 次修改無法解決 | 停止修改，搜尋社群 |
| 關鍵字含 Claude Code / CC runtime 行為 | 搜尋 `site:github.com/anthropics/claude-code` + 關鍵字 |

**禁止行為**：

| 禁止 | 原因 |
|------|------|
| 多次猜測式修改 Hook 核心 | 若為 CLI 已知 bug，所有修改都是不必要的 |
| 以「試試看」動機修改共用模組 | 核心模組修改會連帶影響所有下游 Hook |
| 修改核心後未社群確認才 deploy | 可能讓問題惡化（修改與 CLI bug 疊加） |

**適用範圍**：Hook 核心工具（`run_hook_safely`、`hook_utils`）、ticket CLI 共用模組、跨專案使用的框架腳本。不適用於單一 Hook 腳本的業務邏輯修復。

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
| 未完成 Reality Test 即列候選方案 | ANA / Widen / incident report 共同強制閘門（PC-063） |

---

## 相關文件

- .claude/methodologies/operational-error-root-cause-methodology.md - 操作失誤三層根因分析方法論
- .claude/references/incident-response-details.md - 詳細規則（多視角分析、安全等級、報告格式）
- .claude/agents/incident-responder.md - 代理人定義
- .claude/pm-rules/skip-gate.md - Skip-gate 防護
- .claude/pm-rules/decision-tree.md - 主線程決策樹

---

## 代理人回合耗盡處理

> **核心理念**：回合耗盡 = 認知負擔過載的具體訊號。不只是「重試」或「PM 代做」，而是系統性訊號——某處的檔案體量或 domain 混合度需要降低。

### 應對流程

```
代理人回傳截斷/不完整結果
    |
    v
[強制] 更新 Ticket Context Bundle（PC-040）
    → 將代理人的部分產出/PM 分析寫入 Ticket
    → 確認 Agent prompt <= 30 行（只含 Ticket ID + 動作指令）
    → 禁止：膨脹 Agent prompt 補償 context 不足
    |
    v
檢查目標檔案體量（行數）
    |
    +-- 有 > 300 行的檔案 → 確認體量問題
    |     → 分析 domain 邊界，建立拆分 Ticket
    |     → 拆分完成後重新派發
    |
    +-- 均 < 200 行 → 非體量問題
          → 檢查任務複雜度（event 經過幾層）
          → 考慮拆分任務而非拆分檔案
```

### 情境對應表

| 情境 | 處理方式 |
|------|---------|
| 代理人回報 context 不足 | 先檢查目標檔案體量，再決定是精簡 prompt 還是拆分檔案 |
| 目標檔案 > 300 行 | 建立拆分 Ticket（以 DDD domain 邊界為拆分依據），拆分後重新派發 |
| 目標檔案 < 200 行但任務仍耗盡 | 拆分任務為更小的子 Ticket（任務複雜度過高） |
| 反覆失敗（3 次以上） | 執行 `/wrap-decision`（快速模式）重新擴增選項，再評估是否需要多 session 策略 |
| 代理人失敗後重派 | [強制] 先更新 Ticket Context Bundle，再重派。禁止膨脹 prompt（PC-040） |

禁止：無限重試同一 prompt。每次重試必須調整策略（縮小範圍或拆分檔案）。
禁止：透過膨脹 Agent prompt 補償 context 不足。必須更新 Ticket Context Bundle（PC-040）。

---

**Last Updated**: 2026-04-13
**Version**: 3.8.0 - 新增 Reality Test 閘門章節（PC-063 防護 2/4，0.18.0-W5-034）
