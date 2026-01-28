# Skip-gate 防護機制

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

當以下情況發生時，**必須強制派發**給 [incident-responder](../agents/incident-responder.md)：

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

> 詳細流程：[incident-response](../flows/incident-response.md)

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
        |               （建議執行 /ticket-create）
        |
        +-- 有 Ticket --> 檢查認領狀態
            |
            +-- 未認領 --> 輸出警告，禁止繼續
            |            （建議執行 /ticket-track claim）
            |
            +-- 已認領 --> 允許繼續執行
```

### Level 2 監控機制

**命令入口驗證閘門 Hook**：
- **Hook 檔案**：`.claude/hooks/command-entrance-gate-hook.py`
- **Hook 類型**：UserPromptSubmit
- **觸發時機**：主線程接收任何用戶命令時
- **檢查邏輯**：
  1. 識別命令是否為「開發/修改命令」
  2. 若是，查詢最新待處理 Ticket（status: pending 或 in_progress）
  3. 若無 Ticket 或 Ticket 未認領，輸出警告訊息
  4. 日誌記錄所有檢查結果

**警告訊息格式**：

無 Ticket 情況：
```
警告：未找到待處理的 Ticket

建議操作:
1. 執行 `/ticket-create` 建立新 Ticket
2. 或執行 `/ticket-track claim {id}` 認領現有 Ticket

詳見: .claude/rules/core/decision-tree.md
```

Ticket 未認領情況：
```
警告：Ticket {id} 尚未認領

建議操作:
1. 執行 `/ticket-track claim {ticket_id}` 認領 Ticket
2. 使用 `/ticket-track query {ticket_id}` 查看詳細資訊

詳見: .claude/rules/core/decision-tree.md
```

---

## 違規判定標準

### 違規行為清單

| 行為 | 違規層級 | 處理方式 |
|------|---------|---------|
| **Level 1 違規** | - | - |
| 主線程直接使用 Edit 修改程式碼（錯誤上下文） | 嚴重違規 | 立即停止，回滾修改 |
| 跳過 incident-responder | 違規 | 停止，重新走流程 |
| 未建立 Ticket 就派發修復任務 | 違規 | 先建立 Ticket |
| 開發代理人自行決定修復方向 | 輕微違規 | 升級到 incident-responder |
| **Level 2 違規** | - | - |
| 在收到開發命令後直接派發代理人，未檢查 Ticket | 嚴重違規 | 停止，執行 /ticket-create |
| 開發命令後派發未認領的 Ticket | 違規 | 停止，執行 /ticket-track claim |
| 忽視命令入口驗證閘門的警告訊息 | 違規 | 撤回派發，完成驗證流程 |
| **Level 3 違規** | - | - |
| 主線程直接編輯程式碼檔案 `lib/*` 或 `test/*` | 嚴重違規 | Hook 阻止操作，立即停止 |
| 主線程修改 `pubspec.yaml` | 嚴重違規 | Hook 阻止操作，派發 system-engineer |
| 主線程編輯 `.dart` 檔案（應用程式碼） | 嚴重違規 | Hook 阻止操作，通知適當代理人 |
| 主線程編輯超出允許範圍的檔案 | 違規 | Hook 阻止操作，輸出警告訊息 |

### 違規處理流程

#### Level 1 違規處理（錯誤修復防護）

```
發現 Level 1 違規
    |
    v
立即停止當前操作
    |
    v
記錄違規行為到工作日誌
    |
    v
回滾已做的修改（如有）
    |
    v
重新從 /pre-fix-eval 開始流程
```

#### Level 2 違規處理（命令入口防護）

```
發現 Level 2 違規
    |
    v
立即停止派發或執行
    |
    v
執行對應驗證命令:
    - 無 Ticket: /ticket-create
    - Ticket 未認領: /ticket-track claim {id}
    |
    v
完成驗證後重新派發
    |
    v
記錄違規行為到工作日誌
```

#### Level 3 違規處理（主線程編輯限制）

```
嘗試編輯檔案
    |
    v
[強制] Hook 檢查檔案路徑
    |
    +-- 在允許範圍內 --> 允許操作
    |
    +-- 在禁止範圍內 --> [強制] Hook 阻止操作
        |
        v
        輸出警告訊息
        |
        v
        分類違規類型:
        - 程式碼檔案 --> 派發對應代理人
        - pubspec.yaml --> 派發 system-engineer
        - 超出允許範圍 --> 提示路徑規範
        |
        v
        記錄違規行為到日誌
```

---

## 豁免情況

### 允許直接修復的情況

| 情況 | 說明 | 條件 |
|------|------|------|
| 明顯的筆誤 | 如變數名稱拼錯 | 單字元/單詞修改 |
| 格式化問題 | 如縮排、空格 | 使用 lint 工具自動修復 |
| 文件更新 | 非程式碼修改 | 不影響功能 |

### 豁免條件

即使是豁免情況，也必須：

1. 在工作日誌記錄修改
2. 說明為何適用豁免
3. 確認修改不影響測試

---

## 監控機制

### Hook 系統整合

#### Level 1 監控

- **PreToolUse Hook**：監控 Edit/Write 工具使用，檢查是否在錯誤上下文中
- **UserPromptSubmit Hook**：檢查用戶訊息是否包含錯誤關鍵字
- **PostToolUse Hook**：驗證修改是否通過 incident-responder

#### Level 2 監控

- **UserPromptSubmit Hook**（命令入口驗證閘門）：
  - **檔案**：`.claude/hooks/command-entrance-gate-hook.py`
  - **功能**：在接收用戶命令時驗證 Ticket 存在和認領狀態
  - **觸發**：對所有命令檢查，開發命令時強制驗證
  - **日誌**：`.claude/hook-logs/command-entrance-gate/`

### 違規警告訊息

#### Level 1 警告

```
[WARNING] Skip-gate Protection Triggered (Level 1)
- 偵測到錯誤上下文中的直接修改嘗試
- 請遵循正確流程：
  1. 執行 /pre-fix-eval
  2. 等待 incident-responder 分析
  3. 建立 Ticket
  4. 派發對應代理人
```

#### Level 2 警告

無 Ticket 情況：
```
[WARNING] Skip-gate Protection Triggered (Level 2)
- 命令入口驗證失敗：未找到待處理的 Ticket
- 請先執行：/ticket-create
- 詳見：.claude/rules/forbidden/skip-gate.md
```

Ticket 未認領情況：
```
[WARNING] Skip-gate Protection Triggered (Level 2)
- 命令入口驗證失敗：Ticket {id} 尚未認領
- 請先執行：/ticket-track claim {id}
- 詳見：.claude/rules/forbidden/skip-gate.md
```

#### Level 3 監控

- **PreToolUse Hook**（主線程編輯限制）：
  - **檔案**：`.claude/hooks/main-thread-edit-guard-hook.py`
  - **功能**：在接收 Edit/Write 工具時驗證檔案路徑
  - **觸發**：對主線程的所有 Edit/Write 操作
  - **日誌**：`.claude/hook-logs/main-thread-edit-guard/`

### 違規警告訊息

#### Level 3 警告

程式碼檔案編輯嘗試：
```
[ERROR] Skip-gate Protection Triggered (Level 3)
- 主線程禁止直接編輯程式碼檔案：{file_path}
- 建議操作：
  1. 確認任務是否應由代理人執行
  2. 建立對應 Ticket
  3. 派發 parsley-flutter-developer 或對應代理人
- 詳見：.claude/rules/forbidden/skip-gate.md
```

依賴檔案編輯嘗試：
```
[ERROR] Skip-gate Protection Triggered (Level 3)
- 主線程禁止直接編輯依賴管理檔案：{file_path}
- 建議操作：
  1. 派發 system-engineer 處理依賴更新
  2. 使用 /ticket-create 建立環境配置 Ticket
- 詳見：.claude/rules/forbidden/skip-gate.md
```

超出允許範圍的編輯：
```
[ERROR] Skip-gate Protection Triggered (Level 3)
- 檔案路徑超出主線程允許編輯範圍：{file_path}
- 允許編輯的路徑：.claude/plans/*, .claude/rules/*, docs/work-logs/*, 等
- 詳見：.claude/rules/forbidden/skip-gate.md
```

### 規則 5：主線程編輯限制（Level 3）

主線程（rosemary-project-manager）只能編輯以下檔案範圍：

| 允許範圍 | 路徑模式 | 說明 |
|---------|---------|------|
| 計畫檔案 | `.claude/plans/*` | 計畫文件、決策記錄 |
| Claude 配置 | `.claude/rules/*` | 規則、流程、指南 |
| Claude 配置 | `.claude/methodologies/*` | 方法論、最佳實踐 |
| Claude 配置 | `.claude/hooks/*` | Hook 系統檔案 |
| Claude 配置 | `.claude/skills/*` | Skill 工具檔案 |
| 工作日誌 | `docs/work-logs/*` | 版本工作日誌、執行記錄 |
| Ticket 檔案 | `.claude/tickets/*` | Ticket 設計、追蹤 |
| 待辦清單 | `docs/todolist.md` | 待辦事項、技術債務清單 |

**禁止編輯**：

| 禁止範圍 | 說明 |
|---------|------|
| `lib/*` | 應用程式碼（業務邏輯） |
| `test/*` | 測試程式碼 |
| `*.dart` | 所有 Dart 程式碼檔案（除 .claude/ 中的） |
| `pubspec.yaml` | 依賴管理（派發給 system-engineer） |
| `CHANGELOG.md` | 版本變更記錄（由流程自動產出） |

**違規處理**：Hook 系統會在執行 Edit/Write 工具時驗證檔案路徑，如果超出允許範圍，將阻止操作並輸出警告訊息。

---

## 角色職責邊界

### incident-responder 職責（Level 1）

| 職責 | 負責 | 禁止 |
|------|------|------|
| 分析錯誤原因 | 是 | - |
| 分類錯誤類型 | 是 | - |
| 建立 Ticket | 是 | - |
| 提供派發建議 | 是 | - |
| 實際修復程式碼 | - | 禁止 |
| 決定最終派發 | - | PM 決定 |

### 主線程職責（Level 1 + Level 2 + Level 3）

| 職責 | 層級 | 負責 | 禁止 |
|------|------|------|------|
| 接收錯誤訊息 | Level 1 | 是 | - |
| 派發 incident-responder | Level 1 | 是 | - |
| 根據建議決定最終派發 | Level 1 | 是 | - |
| 驗收修復結果 | Level 1 | 是 | - |
| 分析錯誤原因 | Level 1 | - | 不負責 |
| 直接修復程式碼 | Level 1 | - | 禁止 |
| 驗證開發命令前置條件 | Level 2 | 是 | - |
| 檢查 Ticket 存在性 | Level 2 | 是 | - |
| 檢查 Ticket 認領狀態 | Level 2 | 是 | - |
| 忽視命令入口警告 | Level 2 | - | 禁止 |
| 編輯允許路徑檔案 | Level 3 | 是 | - |
| 編輯程式碼檔案 | Level 3 | - | 禁止 |
| 編輯依賴管理檔案 | Level 3 | - | 禁止 |
| 編輯禁止路徑檔案 | Level 3 | - | 禁止 |

---

## 實施檢查清單

### Level 1 檢查清單（每次錯誤發生時）

- [ ] 是否執行了 `/pre-fix-eval`？
- [ ] 是否派發了 incident-responder？
- [ ] incident-responder 是否完成了 Incident Report？
- [ ] 是否建立了對應的 Ticket？
- [ ] 派發的代理人是否正確？
- [ ] 修復是否在 Ticket 範圍內？

### Level 2 檢查清單（每次接收開發命令時）

- [ ] 是否識別出開發/修改命令？
- [ ] 是否查詢到待處理的 Ticket？
- [ ] Ticket 是否已被認領？
- [ ] 是否檢視了命令入口驗證閘門的警告訊息？
- [ ] 是否在派發前完成了所有前置驗證？
- [ ] 派發代理人是否與 Ticket 內容相符？

### Level 3 檢查清單（每次主線程嘗試編輯檔案時）

- [ ] 編輯的檔案路徑在允許範圍內？
- [ ] 是否為以下允許路徑：
  - [ ] `.claude/plans/*`（計畫文件）
  - [ ] `.claude/rules/*`（規則、流程）
  - [ ] `.claude/methodologies/*`（方法論）
  - [ ] `.claude/hooks/*`（Hook 系統）
  - [ ] `.claude/skills/*`（Skill 工具）
  - [ ] `docs/work-logs/*`（工作日誌）
  - [ ] `.claude/tickets/*`（Ticket 檔案）
  - [ ] `docs/todolist.md`（待辦清單）
- [ ] 是否嘗試編輯禁止檔案：
  - [ ] `lib/*`（程式碼）？
  - [ ] `test/*`（測試）？
  - [ ] `.dart` 檔案？
  - [ ] `pubspec.yaml`？
- [ ] 如編輯被阻止，是否已遵循建議派發對應代理人？

---

## 相關文件

- [incident-responder](../agents/incident-responder.md) - 代理人定義
- [incident-response](../flows/incident-response.md) - 事件回應流程
- [decision-tree](../core/decision-tree.md) - 主線程決策樹
- [command-entrance-gate-hook.py]($CLAUDE_PROJECT_DIR/.claude/hooks/command-entrance-gate-hook.py) - 命令入口驗證閘門實作
- [ticket-lifecycle](../flows/ticket-lifecycle.md) - Ticket 生命週期

---

**Last Updated**: 2026-01-27
**Version**: 2.2.0
**Purpose**: Skip-gate Prevention with Multi-Level Protection
**Changes**:
- 新增 Level 3 主線程編輯限制
- 新增 Level 3 允許和禁止檔案路徑表格
- 新增 Level 3 違規判定標準和處理流程
- 新增 Level 3 監控機制和警告訊息
- 更新防護層級架構表格
- 更新主線程職責表格，加入 Level 3 職責邊界
- 新增 Level 3 檢查清單
