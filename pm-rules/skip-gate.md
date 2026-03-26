# Skip-gate 防護機制

> **受眾**：本文件的限制規則僅適用於 rosemary-project-manager（主線程）。subagent 開發代理人不受「主線程禁止」類規則約束，其職責正是執行 PM 派發的開發任務。

本文件定義 Skip-gate 防護機制，明確禁止主線程直接修復測試失敗的行為。

---

## 背景：Skip-gate 事件

Skip-gate 事件暴露的根本問題：

> 無論寫再多規則或 Hook，都難以避免違規行為，因為主線程在沒有指定特定模式的處理方式下，無法自行判斷當前狀況是否符合規則中的某些條件。

**解決方案**：明確拆分工作狀態，將不同類型的工作分配給專門的代理人處理。

---

## 防護層級架構

Skip-gate 防護機制分為多層級，對應不同的工作流程階段：

| 層級 | 名稱 | 防護時機 | 防護範圍 | 狀態 |
|------|------|---------|---------|------|
| Level 1 | 錯誤修復防護 | 事後 | 錯誤發生後禁止直接修復 | 現有 |
| Level 2 | 命令入口防護 | 事前 | 開發命令執行前驗證 Ticket | 現有 |
| Level 3 | 主線程編輯限制 | 事前 | 限制主線程可編輯的檔案範圍 | 新增 |

**防護演進策略**：從被動響應（Level 1）升級為主動驗證（Level 2、3），實現「預防為主」的工程文化。

---

## 強制規則

### 規則 1：錯誤發生時強制派發 incident-responder

當以下情況發生時，**必須強制派發**給 .claude/agents/incident-responder.md ：

| 觸發情境 | 識別關鍵字 | 強制性 |
|---------|-----------|--------|
| 測試失敗 | "test failed", "測試失敗", "X tests failed" | 強制 |
| 編譯錯誤 | "compile error", "編譯錯誤", "build failed" | 強制 |
| 執行時錯誤 | "runtime error", "exception", "crash" | 強制 |
| 用戶回報問題 | "bug", "問題", "不正常", "出錯" | 強制 |

### 規則 2：主線程禁止直接修復

主線程（rosemary-project-manager）在任何情況下**禁止**：

| 禁止行為 | 說明 |
|---------|------|
| 直接修改程式碼 | 不得使用 Edit/Write 工具修改程式碼來修復錯誤 |
| 跳過分析階段 | 不得在未經 incident-responder 分析前嘗試修復 |
| 省略 Ticket 建立 | 不得在未建立 Ticket 前開始修復工作 |
| 自行判斷錯誤類型 | 必須由 incident-responder 進行分類 |

### 規則 3：必須遵循的修復流程

```
錯誤發生
    |
    v
[強制] 執行 /pre-fix-eval
    |
    v
[強制] 派發 incident-responder
    |
    v
incident-responder 分析和分類
    |
    v
[強制] 建立 Ticket
    |
    v
根據分類派發對應代理人
    |
    v
代理人執行修復
```

> 詳細流程：.claude/pm-rules/incident-response.md

---

### 規則 4：開發命令執行前的驗證（Level 2）

當主線程（rosemary-project-manager）接收到**開發/修改命令**時，**必須強制驗證**：

| 開發命令特徵 | 識別方式 | 驗證要求 |
|----------|---------|--------|
| 包含實作關鍵字 | 「實作」「建立」「修復」「處理」「重構」「轉換」「新增」「刪除」「修改」「優化」等 | 必須存在待處理 Ticket |
| 涉及程式碼修改 | 使用 Edit/Write 工具 | 必須先有 Ticket |
| 業務流程變更 | 「設計」「規劃」「整合」「升級」等 | 必須先有 Ticket |

### 驗證流程（命令入口防護）

```
接收開發/修改命令
    |
    v
[強制] 識別是否為開發命令?
    |
    +-- 否 --> 跳過驗證，繼續執行
    |
    +-- 是 --> [強制] 檢查 Ticket
        |
        +-- 無 Ticket --> 輸出警告，禁止繼續
        |               （建議執行 /ticket create）
        |
        +-- 有 Ticket --> 檢查認領狀態
            |
            +-- 未認領 --> 輸出警告，禁止繼續
            |            （建議執行 /ticket track claim）
            |
            +-- 已認領 --> 允許繼續執行
```

### Level 2 監控機制

**命令入口驗證閘門 Hook**：
- **Hook 檔案**：`.claude/hooks/command-entrance-gate-hook.py`
- **Hook 類型**：UserPromptSubmit
- **觸發時機**：主線程接收任何用戶命令時
- **檢查邏輯**：識別開發命令 → 查詢待處理 Ticket → 驗證認領狀態 → 輸出警告或允許執行

> 詳細警告訊息格式和監控配置：.claude/references/skip-gate-warning-templates.md

---

## 違規判定與處理

> 詳細的違規行為清單、判定標準和處理流程：.claude/references/skip-gate-violations.md

關鍵處理原則：
- **Level 1**：立即停止、回滾修改、重新走流程
- **Level 2**：停止派發、完成驗證、重新確認
- **Level 3**：Hook 阻止操作、通知對應代理人

---

## 監控與警告

### Hook 監控配置

| 層級 | Hook 檔案 | 觸發事件 | 功能 |
|------|---------|--------|------|
| Level 1 | PreToolUse | 工具使用前 | 檢查錯誤上下文 |
| Level 2 | UserPromptSubmit | 命令接收時 | 驗證 Ticket 存在性 |
| Level 3 | PreToolUse | 工具使用前 | 驗證編輯路徑 |

> 詳細警告訊息模板和 Hook 配置：.claude/references/skip-gate-warning-templates.md

---

## 豁免情況

| 情況 | 說明 | 必要條件 |
|------|------|---------|
| 明顯的筆誤 | 變數名稱拼錯 | 單字元/單詞修改、記錄到日誌 |
| 格式化問題 | 縮排、空格 | 使用 lint 工具自動修復、記錄到日誌 |
| 文件更新 | 非程式碼修改 | 不影響功能、記錄到日誌 |

### 規則 5：主線程編輯限制（Level 3）

主線程（rosemary-project-manager）只能編輯以下檔案範圍：

| 允許範圍 | 路徑模式 | 說明 |
|---------|---------|------|
| 計畫檔案 | `.claude/plans/*` | 計畫文件、決策記錄 |
| Claude 配置 | `.claude/rules/*` | 規則、流程、指南 |
| Claude 配置 | `.claude/methodologies/*` | 方法論、最佳實踐 |
| Claude 配置 | `.claude/hooks/*` | Hook 系統檔案 |
| Claude 配置 | `.claude/skills/*` | Skill 工具檔案 |
| 工作日誌 | `docs/work-logs/*`（不含 tickets/） | 版本工作日誌、執行記錄 |
| Ticket 檔案 | `docs/work-logs/*/tickets/*` | Ticket 檔案（唯一位置） |
| 待辦清單 | `docs/todolist.yaml` | 結構化版本索引 |

**禁止編輯**：

| 禁止範圍 | 說明 |
|---------|------|
| `lib/*` | 應用程式碼（業務邏輯） |
| `test/*` | 測試程式碼 |
| `*.dart` | 所有 Dart 程式碼檔案（除 .claude/ 中的） |
| `pubspec.yaml` | 依賴管理（派發給 system-engineer） |
| `CHANGELOG.md` | 版本變更記錄（由流程自動產出） |

**違規處理**：Hook 系統會在執行 Edit/Write 工具時驗證檔案路徑，如果超出允許範圍，將阻止操作並輸出警告訊息。

Subagent 的可編輯路徑見 decision-tree.md「代理人可編輯路徑對照表」（唯一 Source of Truth）。

### 規則 6：外部查詢工作流規則

外部資源查詢（WebFetch、WebSearch）應由 oregano-data-miner 專業代理人執行。

| 禁止行為 | 說明 |
|---------|------|
| 主線程直接使用 WebFetch | 應派發 oregano-data-miner |
| 主線程直接使用 WebSearch | 應派發 oregano-data-miner |

**工作流指導**：

主線程在使用 WebFetch 或 WebSearch 時，系統會自動輸出友好的工作流提示訊息，建議派發 oregano-data-miner 執行外部資源研究。

```
使用外部查詢工具（WebFetch/WebSearch）
    |
    v
[自動] external-query-guide-hook.py 檢測
    |
    v
輸出工作流提示：建議派發 oregano-data-miner
    |
    v
正確做法：
  1. 建立 Ticket 記錄外部查詢需求
  2. 派發 oregano-data-miner 執行查詢
  3. oregano-data-miner 完成資源蒐集和整理
  4. 回傳結果
```

**監控機制**：

- **Hook 檔案**：`.claude/hooks/external-query-guide-hook.py`
- **Hook 類型**：PreToolUse
- **觸發時機**：執行 WebFetch 或 WebSearch 工具時
- **行為**：輸出友好提示訊息，允許執行
- **日誌**：`.claude/hook-logs/external-query-guide/`

**好處**：

- 專業的資源蒐集和整理
- 更好的上下文管理
- 完整的執行記錄和追蹤
- 遵循工作流規範
- 提升資訊質量和準確性

---

## 角色職責邊界

### incident-responder 職責

| 職責 | 詳情 |
|------|------|
| 必須 | 分析錯誤原因、分類錯誤類型、建立 Ticket、提供派發建議 |
| 禁止 | 實際修復程式碼、決定最終派發 |

### 主線程職責

| 層級 | 必須 | 禁止 |
|------|------|------|
| L1 | 接收錯誤、派發 incident-responder、決定派發、驗收結果 | 分析錯誤、直接修復 |
| L2 | 驗證開發命令、檢查 Ticket、認領狀態確認、派發代理人 | 忽視驗證警告、跳過檢查 |
| L3 | 編輯允許路徑檔案 | 編輯程式碼、依賴檔、禁止路徑檔 |

---

## 實施檢查清單

> 詳細的各層級檢查清單：.claude/references/skip-gate-checklists.md

---

## 相關文件

- .claude/agents/incident-responder.md - 代理人定義
- .claude/pm-rules/incident-response.md - 事件回應流程
- .claude/pm-rules/decision-tree.md - 主線程決策樹
- .claude/hooks/command-entrance-gate-hook.py - 命令入口驗證閘門實作
- .claude/hooks/external-query-guide-hook.py - 外部查詢工作流指導實作
- .claude/agents/oregano-data-miner.md - 外部資源研究代理人
- .claude/pm-rules/ticket-lifecycle.md - Ticket 生命週期

---

**Last Updated**: 2026-03-21
**Version**: 2.7.0 - 適用對象標註集中至頂部受眾宣告，移除 4 處分散重複標註（0.1.1-W16-003）
**Purpose**: Skip-gate Prevention with Multi-Level Protection
**Changes**:
- v2.4.0 (2026-02-06): 精簡主檔案，外移參考內容
  - 精簡「違規判定標準」章節，外移至 skip-gate-violations.md
  - 精簡「監控機制」和「警告訊息」，外移至 skip-gate-warning-templates.md
  - 精簡「檢查清單」，外移至 skip-gate-checklists.md
  - 簡化「角色職責邊界」為表格式呈現
  - 減少重複內容，保留核心規則和決策邏輯
  - 預計節省 ~23% tokens（7.1k → 5.5k）
- v2.3.0 (2026-02-02): 新增規則 6 外部查詢工作流規則
- v2.2.0 (2026-01-27): 新增 Level 3 主線程編輯限制
