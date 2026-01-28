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
    +-- Ticket 存在? --> 否 --> 提示 /ticket-create
    |                          |
    |                          v
    |                     阻止執行
    |
    +-- 已認領? --> 否 --> 提示 /ticket-track claim
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
    +-- /ticket-track complete 執行?
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
| Ticket 存在 | 系統中存在對應的 pending/in_progress Ticket | 提示 /ticket-create |
| Ticket 認領 | Ticket 狀態為 in_progress（已認領） | 提示 /ticket-track claim |
| 開發命令識別 | 判斷是否為開發/修改命令 | 不是開發命令則跳過檢查 |

**實作位置**：`.claude/hooks/command-entrance-gate-hook.py` (W2-001)

**驗證規則**：
```python
if is_development_command(prompt):
    if not has_pending_ticket():
        warn_no_ticket()
    elif ticket_status == "pending":
        warn_not_claimed()
    else:  # in_progress
        allow_execution()
```

**責任**：
- Hook 系統負責檢查和提示
- 用戶負責建立或認領 Ticket
- PM 負責監督 Ticket 生命週期

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

**實作位置**：各代理人的執行流程

**驗證規則（例：Phase 3b）**：
```
進入 Phase 3b
    |
    +-- Phase 3a 完成? --> 否 --> 升級
    +-- 測試案例設計完成? --> 否 --> 升級
    +-- 策略文件完整? --> 否 --> 升級
    +-- 環境正常? --> 否 --> 派發 SE
    |
    v
執行 Phase 3b
```

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
| Ticket 更新 | /ticket-track complete 已執行 | 提示執行命令 |

**實作位置**：`.claude/hooks/phase-completion-gate-hook.py` (W2-004)

**驗證規則**：
```python
if is_phase_completion_report(file_path):
    missing = check_worklog_structure(content)
    if missing:
        warn_incomplete(missing)
    else:
        allow_ticket_completion()
```

**worklog 結構檢查**：
- Problem Analysis：階段發現的問題
- Solution：解決方案概述
- Test Results：測試執行結果
- 產出物清單：Phase 預期的所有產出物

**責任**：
- Hook 系統負責識別和檢查
- 代理人負責確保產出物完整
- PM 負責監督工作日誌更新

---

### Level 4: 驗收層驗證

**目標**：最終確認任務符合所有驗收標準和品質要求

**驗證時機**：Ticket complete 後、任務正式結束前

**驗證者**：rosemary-project-manager

**驗證內容**：

| 驗證項 | 驗證條件 | 失敗處理 |
|-------|---------|--------|
| 驗收條件 | 所有驗收條件都已完成 | 不認可，要求補充 |
| 品質標準 | 符合專案品質基線 | 建立 Ticket 修正 |
| 文件記錄 | 工作日誌、Ticket 記錄完整 | 要求補充 |
| 測試通過 | 相關測試 100% 通過 | 派發 incident-responder |
| 無已知問題 | 無記錄的阻塞問題 | 處理阻塞或延後完成 |

**驗收標準**：
```
Ticket 驗收通過條件：
1. 所有驗收條件勾選完成
2. 工作日誌有完整的執行記錄
3. 相關測試 100% 通過
4. 代碼審查（如適用）通過
5. 無遺留的已知問題
6. 技術債務已記錄（如有）
```

**責任**：
- PM 負責最終驗收決策
- PM 可要求補充或修正
- PM 記錄驗收結果

---

## 責任矩陣

### 按角色劃分

| 角色 | Level 1 | Level 2 | Level 3 | Level 4 |
|------|---------|---------|---------|---------|
| Hook 系統 | 負責執行 | - | 負責執行 | - |
| 執行代理人 | - | 負責執行 | 協助驗證 | - |
| rosemary-PM | 監督 | 監督 | 監督 | 負責驗收 |
| 其他支援代理人 | - | 派發協助 | - | 派發修正 |

### 按驗證項劃分

| 驗證項 | 驗證者 | 無法通過時 | 最終決策 |
|-------|-------|-----------|--------|
| Ticket 存在 | Hook | 提示建立 | 用戶決定 |
| Ticket 認領 | Hook | 提示認領 | 用戶決定 |
| 前置依賴 | 代理人 | 升級 PM | PM 決定 |
| 環境正常 | 代理人 | 派發 SE | SE 處理 |
| 產出物完整 | Hook | 提示補充 | 代理人決定 |
| 工作日誌 | Hook | 提示更新 | 代理人決定 |
| 驗收條件 | PM | 要求補充 | PM 決定 |
| 品質標準 | PM | 建立修正 Ticket | PM 決定 |
| 測試通過 | PM | 派發 incident | incident 決定 |

---

## 驗證失敗處理流程

### 處理原則

1. **及時發現，快速反饋**：驗證失敗時立即通知相關方
2. **清晰的失敗原因**：說明具體缺陷和改善方向
3. **明確的補救方式**：提供具體的修正步驟
4. **記錄失敗和改善**：在工作日誌中記錄

### 失敗流程

```
驗證失敗
    |
    v
[分類] 失敗類型
    |
    +-- Level 1 失敗（Ticket 問題）
    |       |
    |       v
    |   [提示] 建立/認領 Ticket
    |
    +-- Level 2 失敗（前置條件）
    |       |
    |       v
    |   [升級] 派發 PM 或協助代理人
    |
    +-- Level 3 失敗（產出物缺陷）
    |       |
    |       v
    |   [提示] 補充產出物或更新文件
    |
    +-- Level 4 失敗（品質問題）
            |
            v
        [建立] 修正 Ticket
        [派發] 對應代理人
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

**Skip-gate 防護機制三層級**：

| 層級 | 機制 | 本框架對應 |
|------|------|----------|
| Level 1 | 錯誤修復防護 | 事後驗證（暫時）|
| Level 2 | 命令入口防護 | Level 1 入口層驗證 |
| Level 3 | 階段完成防護 | Level 3 完成層驗證 |

**集成方式**：
- Skip-gate Level 2 → 驗證框架 Level 1
- Skip-gate Level 3 → 驗證框架 Level 3
- 驗證框架補充了 Level 2（執行層）和 Level 4（驗收層）

### 與決策樹的關係

決策樹的各個層級都有對應的驗證點：

| 決策樹層級 | 對應驗證 | 驗證者 |
|-----------|---------|-------|
| 第零層（明確性檢查） | Level 1 | Hook + 代理人 |
| 第一層（訊息類型） | Level 2 | 代理人 |
| 第四層（Ticket 執行） | Level 1 | Hook |
| 第五層（TDD 階段） | Level 2 + Level 3 | 代理人 + Hook |
| 第七層（完成判斷） | Level 4 | PM |

### 與 TDD 流程的關係

每個 TDD 階段都有對應的驗證檢查點：

**Phase 1 (功能設計)**
- Level 2：前置條件（SA 審查通過）
- Level 3：驗收條件（API 定義完整）

**Phase 2 (測試設計)**
- Level 2：前置條件（Phase 1 完成）
- Level 3：驗收條件（測試案例設計完成）

**Phase 3a (策略規劃)**
- Level 2：前置條件（Phase 2 完成）
- Level 3：驗收條件（策略文件完整）

**Phase 3b (實作執行)**
- Level 2：前置條件（Phase 3a 完成）
- Level 3：驗收條件（測試 100% 通過）

**Phase 4 (重構優化)**
- Level 2：前置條件（Phase 3b 完成）
- Level 3：驗收條件（評估報告完成）

---

## Hook 實作規範

### 入口層驗證 Hook (W2-001: command-entrance-gate-hook.py)

**功能**：驗證開發命令時是否有對應的待認領 Ticket

**執行時機**：UserPromptSubmit（用戶輸入時）

**檢查邏輯**：
```
1. 判斷是否為開發命令
2. 如果是，檢查是否有 pending/in_progress Ticket
3. 輸出警告或允許繼續
```

**輸出格式**：
```json
{
  "hookSpecificOutput": {
    "hookEventName": "UserPromptSubmit",
    "additionalContext": "警告訊息（如有）"
  },
  "check_result": {
    "is_development_command": bool,
    "has_ticket": bool,
    "ticket_id": string,
    "should_block": bool,
    "timestamp": ISO8601
  }
}
```

**關鍵實作**：
- 識別開發命令關鍵字（實作、建立、修復等）
- 搜尋 .claude/tickets/ 和 docs/work-logs/*/tickets/
- 檢查 frontmatter 中的 status 欄位

---

### 完成層驗證 Hook (W2-004: phase-completion-gate-hook.py)

**功能**：驗證 Phase 完成時是否有完整的工作日誌記錄

**執行時機**：PostToolUse（Write/Edit 工具執行後）

**檢查邏輯**：
```
1. 判斷是否為 worklog 寫入操作
2. 識別是否為 Phase 完成報告
3. 檢查 worklog 結構完整性
4. 輸出警告或確認
```

**必檢查的 worklog 部分**：
- Problem Analysis：問題分析
- Solution：解決方案
- Test Results：測試結果

**輸出格式**：
```json
{
  "hookSpecificOutput": {
    "hookEventName": "PostToolUse",
    "additionalContext": "警告訊息（如有）"
  }
}
```

**關鍵實作**：
- 檢查 Phase 完成標記（Phase 3b、Phase 4 等）
- 驗證必需的 markdown 部分存在
- 檢查部分中是否有實際內容（非 TODO）

---

### 未來擴展：階段轉換驗證

**計畫中的 Hook**：驗證階段轉換時是否滿足前置條件

**執行時機**：Ticket 狀態從 in_progress 變更為 completed 時

**檢查邏輯**：
```
1. 識別當前階段和目標階段
2. 驗證目標階段的前置條件
3. 確認可以安全轉換
```

---

## 驗證檢查清單

### 代理人在開始任務前的檢查

```markdown
## 執行層驗證檢查清單 (Level 2)

- [ ] 當前 Ticket 已認領（status: in_progress）
- [ ] 依賴的前置 Ticket 已完成
- [ ] 必需的輸入/資料已準備
- [ ] 開發環境正常（如需要）
- [ ] 任務複雜度在可管理範圍內（< 10）
- [ ] 理解了任務的完整要求
```

### 代理人在完成任務時的檢查

```markdown
## 完成層驗證檢查清單 (Level 3)

- [ ] 所有驗收條件已完成並勾選
- [ ] 工作日誌已更新（包含問題、方案、結果）
- [ ] 所有預期的產出物已交付
- [ ] 相關測試全部通過
- [ ] 技術債務已記錄（如有）
- [ ] 執行 /ticket-track complete {id}
```

### PM 在驗收任務時的檢查

```markdown
## 驗收層驗證檢查清單 (Level 4)

- [ ] Ticket 狀態為 completed
- [ ] 工作日誌記錄完整
- [ ] 所有驗收條件都已滿足
- [ ] 相關測試 100% 通過
- [ ] 代碼質量符合要求（Dart analyze: 0 issues）
- [ ] 無遺留的已知阻塞問題
- [ ] 技術債務已正確記錄
- [ ] 可安全進入下一個 Ticket 或階段
```

---

## 常見驗證場景

### 場景 1：用戶嘗試開發，但沒有 Ticket

**驗證點**：Level 1（入口層）

**流程**：
```
用戶: 實作新功能
    ↓
Hook: 識別開發命令
    ↓
Hook: 檢查 Ticket
    ↓
Hook: 找不到 pending Ticket
    ↓
Hook: 提示執行 /ticket-create
    ↓
用戶: 建立 Ticket
    ↓
用戶: 認領 Ticket
    ↓
繼續執行
```

### 場景 2：代理人開始執行，缺少前置條件

**驗證點**：Level 2（執行層）

**流程**：
```
代理人: 開始 Phase 3b
    ↓
檢查: Phase 3a 完成？
    ↓
發現: Phase 3a 未完成
    ↓
行動: 升級 PM
    ↓
PM: 重新安排優先級或拆分任務
```

### 場景 3：Phase 完成，但工作日誌不完整

**驗證點**：Level 3（完成層）

**流程**：
```
代理人: 更新 worklog
    ↓
Hook: 識別 Phase 完成報告
    ↓
Hook: 檢查 worklog 結構
    ↓
發現: 缺少 Test Results 部分
    ↓
Hook: 警告訊息
    ↓
代理人: 補充 Test Results
    ↓
Hook: 驗證通過
    ↓
允許 /ticket-track complete
```

### 場景 4：PM 驗收，發現品質問題

**驗證點**：Level 4（驗收層）

**流程**：
```
PM: 驗收 Ticket
    ↓
檢查: Dart analyze 結果
    ↓
發現: 有 3 個 warnings
    ↓
決定: 需要修正
    ↓
建立: 修正 Ticket
    ↓
派發: parsley-flutter-developer
    ↓
修正後: 重新驗收
```

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

Hook 系統自動產出的驗證報告：

**位置**：`.claude/hook-logs/`

**內容**：
- 各層級驗證的檢查結果
- 失敗原因和建議改善
- 時間戳和相關上下文

---

## 相關文件

- [decision-tree](decision-tree.md) - 主線程決策樹
- [skip-gate](../forbidden/skip-gate.md) - Skip-gate 防護機制
- [cognitive-load](cognitive-load.md) - 認知負擔設計原則
- [agents/overview](../agents/overview.md) - 代理人職責矩陣
- [flows/tdd-flow](../flows/tdd-flow.md) - TDD 流程

---

**Last Updated**: 2026-01-23
**Version**: 1.0.0 - Verification Responsibility Allocation Framework
**Status**: Active
**Responsible**: rosemary-project-manager, Hook 系統
