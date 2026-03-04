# 驗證責任分配框架

本文件定義系統性的「驗證責任分配」框架，明確各層級的驗證職責，防止未來類似的功能缺口和職責混亂。

> **核心理念**：驗證是多層級、多角色的責任分工。不同階段有不同的驗證者，確保完整的檢查覆蓋。

---

## 框架總覽

### 驗證層級架構

```
Level 1: 入口層 (事前防護)
  ↓ 驗證 Ticket 存在 + 認領狀態
  |
Level 2: 執行層 (過程驗證)
  ↓ 驗證前置條件 + 依賴完成
  |
Level 3: 完成層 (事後驗證)
  ↓ 驗證產出物 + 文件記錄
  |
Level 4: 驗收層 (最終驗收)
  ↓ 驗證驗收條件 + 品質標準
  |
任務完成
```

### 驗證流程圖

```
用戶輸入命令
    |
    v
[Level 1] 入口層驗證 (Hook 系統)
    |
    +-- Ticket 存在? --> 否 --> 提示 /ticket create
    |                          |
    |                          v
    |                     阻止執行
    |
    +-- 已認領? --> 否 --> 提示 /ticket track claim
    |               |
    |               v
    |          阻止執行 (或警告)
    |
    v
命令進入執行流程
    |
    v
[Level 2] 執行層驗證 (代理人)
    |
    +-- 前置條件滿足?
    +-- 依賴 Ticket 完成?
    +-- 資源可用?
    |
    v
執行任務
    |
    v
[Level 3] 完成層驗證 (Hook 系統 + 代理人)
    |
    +-- 驗收條件勾選?
    +-- 工作日誌記錄?
    +-- /ticket track complete 執行?
    +-- 測試全部通過?
    |
    v
[Level 4] 驗收層驗證 (PM)
    |
    +-- 驗收條件全部滿足?
    +-- 品質標準符合?
    +-- 文件記錄完整?
    |
    v
Ticket 標記完成
```

---

## 驗證層級詳細定義

### Level 1: 入口層驗證

**目標**：在任務開始前驗證基本條件，防止無計畫的工作

**驗證時機**：命令入口（用戶輸入時）

**驗證者**：Hook 系統（command-entrance-gate-hook.py）

**驗證內容**：

| 驗證項 | 驗證條件 | 失敗處理 |
|-------|---------|--------|
| Ticket 存在 | 系統中存在對應的 pending/in_progress Ticket | 提示 /ticket create |
| Ticket 認領 | Ticket 狀態為 in_progress（已認領） | 提示 /ticket track claim |
| 開發命令識別 | 判斷是否為開發/修改命令 | 不是開發命令則跳過檢查 |
| Ticket 內容品質 | Task Summary 完整（所有 Ticket 適用） | 建議補充內容 |
| Solution 並行化 | Solution 已評估並行化可能性（所有 Ticket 適用） | 建議評估並行化 |
| 建立後品質審核 | acceptance-auditor + system-analyst 並行審核通過（creation_accepted: true） | 派發審核代理人 |

**實作位置**：`.claude/hooks/command-entrance-gate-hook.py` (W2-001)

**責任**：
- Hook 系統負責檢查和提示
- 用戶負責建立或認領 Ticket
- PM 負責監督 Ticket 生命週期

> 實作細節：.claude/references/verification-hook-implementation.md

---

### Level 2: 執行層驗證

**目標**：確保執行環境正確、前置條件滿足、無隱藏依賴

**驗證時機**：任務開始時、階段切換時

**驗證者**：執行代理人（各 TDD 階段代理人）

**驗證內容**：

| 驗證項 | 驗證條件 | 失敗處理 |
|-------|---------|--------|
| 前置依賴 | 依賴的 Ticket 已完成 | 停止執行，升級 PM |
| 前置條件 | 進入階段的前置條件滿足 | 停止執行，升級 PM |
| 環境正確 | 開發環境、工具鏈可用 | 派發 system-engineer |
| 資料準備 | 必需的資料/測試資料已準備 | 停止執行，補充資料 |
| 認知負擔 | 任務複雜度在可管理範圍 | 升級 PM 進行任務拆分 |

**責任**：
- 代理人負責驗證和決定是否開始
- 代理人無法繼續時必須升級
- PM 負責處理升級的決策

---

### Level 3: 完成層驗證

**目標**：確保任務完成時所有產出物都已記錄、檔案結構完整

**驗證時機**：階段完成時、Ticket 標記完成前

**驗證者**：Hook 系統（phase-completion-gate-hook.py）+ 代理人

**驗證內容**：

| 驗證項 | 驗證條件 | 失敗處理 |
|-------|---------|--------|
| 驗收條件 | Ticket 中所有驗收條件已勾選 | 提示補充 |
| 工作日誌 | 階段完成報告已記錄到 worklog | 提示更新 worklog |
| 產出物完整 | 所有期望的產出物都已產出 | 提示補充 |
| 測試結果 | 相關測試全部通過（必要時） | 提示修復失敗測試 |
| Ticket 更新 | /ticket track complete 已執行 | 提示執行命令 |
| 並行派發後驗證 | `git diff --stat` 比對代理人報告 vs 實際變更（並行派發時） | 補派缺失檔案的代理人 |

**實作位置**：`.claude/hooks/phase-completion-gate-hook.py` (W2-004)

**責任**：
- Hook 系統負責識別和檢查
- 代理人負責確保產出物完整
- PM 負責監督工作日誌更新

> 實作細節：.claude/references/verification-hook-implementation.md

---

### Level 4: 驗收層驗證

**目標**：最終確認任務符合所有驗收標準和品質要求

**驗證時機**：Ticket complete 後、任務正式結束前

**驗證者**：acceptance-auditor（執行驗收）+ rosemary-project-manager（最終決策）

**驗證內容**：

| 驗證項 | 驗證條件 | 失敗處理 |
|-------|---------|--------|
| 驗收條件 | 所有驗收條件都已完成 | 不認可，要求補充 |
| 建議追蹤 | 所有建議已處理（無 pending） | 要求補充 |
| 品質標準 | 符合專案品質基線 | 建立 Ticket 修正 |
| 文件記錄 | 工作日誌、Ticket 記錄完整 | 要求補充 |
| 測試通過 | 相關測試 100% 通過 | 派發 incident-responder |
| 無已知問題 | 無記錄的阻塞問題 | 處理阻塞或延後完成 |

**驗收標準**：
1. 所有驗收條件勾選完成
2. 所有建議已處理（adopted/rejected/deferred，無 pending）
3. 工作日誌有完整的執行記錄
4. 相關測試 100% 通過
5. 代碼審查（如適用）通過
6. 無遺留的已知問題
7. 技術債務已記錄（如有）
8. 驗收報告已產出

**驗收流程**：
```
Ticket 完成請求
    |
    v
[派發] acceptance-auditor
    |
    v
執行驗收檢查
    |
    v
產出驗收報告
    |
    v
[提交] rosemary-PM
    |
    v
PM 審核並做最終決策
    |
    +-- 通過 --> Ticket 標記完成
    +-- 不通過 --> 回到執行修正
```

---

## 統一責任對照表

| 驗證項 | 驗證者 | 所屬層級 | 無法通過時 | 最終決策 |
|-------|-------|--------|-----------|--------|
| Ticket 存在 | Hook | Level 1 | 提示建立 | 用戶決定 |
| Ticket 認領 | Hook | Level 1 | 提示認領 | 用戶決定 |
| Ticket 內容品質 | PM | Level 1 | 建議補充 | PM 決定 |
| Solution 並行化 | PM | Level 1 | 建議評估 | PM 決定 |
| 建立後品質審核 | acceptance-auditor + system-analyst | Level 1 | 派發審核代理人 | PM 決定 |
| 前置依賴 | 代理人 | Level 2 | 升級 PM | PM 決定 |
| 環境正常 | 代理人 | Level 2 | 派發 SE | SE 處理 |
| 產出物完整 | Hook | Level 3 | 提示補充 | 代理人決定 |
| 工作日誌 | Hook | Level 3 | 提示更新 | 代理人決定 |
| 並行派發後驗證 | PM | Level 3 | 補派代理人 | PM 決定 |
| 驗收條件 | acceptance-auditor | Level 4 | 要求補充 | PM 決定 |
| 建議追蹤 | acceptance-auditor | Level 4 | 要求處理 | PM 決定 |
| 品質標準 | acceptance-auditor | Level 4 | 建立修正 Ticket | PM 決定 |
| 測試通過 | acceptance-auditor | Level 4 | 派發 incident | PM 決定 |

---

## 驗證失敗處理

### 失敗流程

```
驗證失敗
    |
    v
[分類] 失敗類型
    |
    +-- Level 1 失敗（Ticket 問題）
    |   → [提示] 建立/認領 Ticket
    |
    +-- Level 2 失敗（前置條件）
    |   → [升級] 派發 PM 或協助代理人
    |
    +-- Level 3 失敗（產出物缺陷）
    |   → [提示] 補充產出物或更新文件
    |
    +-- Level 4 失敗（品質問題）
        → [建立] 修正 Ticket
        → [派發] 對應代理人
```

### 失敗恢復規則

| 失敗類型 | 恢復方式 | 時限 |
|---------|--------|------|
| Ticket 問題 | 建立或認領 | 立即 |
| 環境問題 | 派發 system-engineer | 2 小時內 |
| 前置條件缺失 | 升級 PM 並拆分任務 | 立即升級 |
| 產出物缺陷 | 補充或修正 | 同日內 |
| 品質問題 | 建立修正 Ticket | 本版本內 |

---

## 與現有規則的整合

### 與 Skip-gate 的關係

**Skip-gate 防護機制對應**：

| Skip-gate 層級 | 防護機制 | 驗證框架對應 |
|---------------|--------|------------|
| Level 2 | 命令入口防護 | Level 1 入口層驗證 |
| Level 3 | 階段完成防護 | Level 3 完成層驗證 |

### 與決策樹的關係

驗證框架在決策樹的多個層級提供支撐：

| 決策樹層級 | 驗證層級 | 驗證者 |
|-----------|--------|-------|
| 第零層（明確性檢查） | Level 1 | Hook + 代理人 |
| 第四層（Ticket 執行） | Level 1 | Hook |
| 第五層（TDD 階段） | Level 2 + Level 3 | 代理人 + Hook |
| 第七層（完成判斷） | Level 4 | PM |

### TDD 階段驗證檢查點

每個 TDD 階段都有對應的驗證要點：

| Phase | Level 2 前置條件 | Level 3 驗收條件 |
|-------|---------------|----------------|
| SA | - | 架構評估完成 |
| Phase 1 | SA 審查通過 | API 定義完整 |
| Phase 2 | Phase 1 完成 | 測試案例設計完成 |
| Phase 3a | Phase 2 完成 | 策略文件完整 |
| Phase 3b | Phase 3a 完成 | 測試 100% 通過 |
| Phase 4 | Phase 3b 完成 | 評估報告完成 |

---

## 驗證檢查清單

### 代理人開始任務前（Level 2）

- [ ] 當前 Ticket 已認領（status: in_progress）
- [ ] 依賴的前置 Ticket 已完成
- [ ] 必需的輸入/資料已準備
- [ ] 開發環境正常
- [ ] 任務複雜度在可管理範圍內
- [ ] 理解了任務的完整要求

### 代理人完成任務時（Level 3）

- [ ] 所有驗收條件已完成並勾選
- [ ] 工作日誌已更新（問題、方案、結果）
- [ ] 所有預期的產出物已交付
- [ ] 相關測試全部通過
- [ ] 技術債務已記錄（如有）
- [ ] 執行 /ticket track complete {id}

### PM 驗收任務時（Level 4）

- [ ] Ticket 狀態為 completed
- [ ] 工作日誌記錄完整
- [ ] 所有驗收條件都已滿足
- [ ] 相關測試 100% 通過
- [ ] 代碼質量符合要求
- [ ] 無遺留的已知阻塞問題
- [ ] 技術債務已正確記錄
- [ ] 可安全進入下一個 Ticket 或階段

---

## 場景範例

本框架的常見驗證場景和詳細流程範例：

> 詳見：.claude/references/verification-scenario-examples.md

---

## Hook 實作規範

### 入口層驗證 Hook (W2-001: command-entrance-gate-hook.py)

**實作位置**：`.claude/hooks/command-entrance-gate-hook.py`

**功能**：驗證開發命令時是否有對應的待認領 Ticket

**執行時機**：UserPromptSubmit（用戶輸入時）

**關鍵檢查**：
- 識別開發命令關鍵字（實作、建立、修復等）
- 搜尋 .claude/tickets/ 和 docs/work-logs/*/tickets/
- 檢查 frontmatter 中的 status 欄位

### 完成層驗證 Hook (W2-004: phase-completion-gate-hook.py)

**實作位置**：`.claude/hooks/phase-completion-gate-hook.py`

**功能**：驗證 Phase 完成時是否有完整的工作日誌記錄

**執行時機**：PostToolUse（Write/Edit 工具執行後）

**關鍵檢查**：
- 檢查 Phase 完成標記（Phase 3b、Phase 4 等）
- 驗證必需的 markdown 部分存在（Problem Analysis、Solution、Test Results）
- 檢查部分中是否有實際內容（非 TODO）

> 完整實作規範：.claude/references/verification-hook-implementation.md

---

## 指標和報告

### 驗證指標

| 指標 | 計算方法 | 目標 |
|------|--------|------|
| Level 1 通過率 | 開發命令中有效 Ticket 的比例 | > 95% |
| Level 2 耗時 | 發現前置條件問題的平均時間 | < 5 分鐘 |
| Level 3 完整率 | worklog 完整度 | 100% |
| Level 4 驗收率 | 一次驗收通過的比例 | > 90% |

### 驗證報告

Hook 系統自動產出的驗證報告存放在：

**位置**：`.claude/hook-logs/`

**內容**：各層級驗證的檢查結果、失敗原因和建議改善、時間戳和相關上下文

---

## 相關文件

- @.claude/rules/core/decision-tree.md - 主線程決策樹
- @.claude/rules/forbidden/skip-gate.md - Skip-gate 防護機制
- @.claude/rules/core/cognitive-load.md - 認知負擔設計原則
- @.claude/rules/flows/tdd-flow.md - TDD 流程
- @.claude/rules/flows/incident-response.md - 事件回應流程
- .claude/references/verification-scenario-examples.md - 場景範例
- .claude/references/verification-hook-implementation.md - Hook 實作細節

---

**Last Updated**: 2026-03-04
**Version**: 1.5.0 - Level 1 新增建立後品質審核（W4-002, PC-002）
**Status**: Active
**Responsible**: rosemary-project-manager, acceptance-auditor, Hook 系統

**Change Log**:
- v1.5.0 (2026-03-04): Level 1 新增建立後品質審核（W4-002）
  - Level 1 驗證表格新增「建立後品質審核」項目
  - 統一責任對照表新增對應項目
  - 配合 ticket-lifecycle.md v5.1.0 建立後強制審核流程
- v1.4.0 (2026-02-26): Level 3 新增並行派發後驗證（W25-003）
  - Level 3 驗證表格新增「並行派發後驗證」項目（git diff --stat 強制驗證）
  - 統一責任對照表新增對應項目（PM 負責、Level 3）
  - 配合 parallel-dispatch.md v2.5.0 新增並行派發後驗證章節
- v1.3.0 (2026-02-10): Level 1 新增 Ticket 內容品質驗證（W17-001）
  - Level 1 驗證表格新增「Ticket 內容品質」和「Solution 並行化」兩項
  - 統一責任對照表新增對應項目
  - 配合 ticket-lifecycle.md v4.1.0 建立後品質驗收機制
- v1.2.0 (2026-02-06): Context 最佳化
  - 簡化主檔案結構，移除重複說明
  - 新增「統一責任對照表」（合併原有 2 個表格）
  - 「常見驗證場景」移至 verification-scenario-examples.md
  - 「Hook 實作規範」詳細內容移至 verification-hook-implementation.md
  - 保留核心架構圖和流程圖完整
  - 添加參考連結方便查閱
- v1.1.0 (2026-01-30): Level 4 驗收層更新
- v1.0.0 (2026-01-23): 初始版本
