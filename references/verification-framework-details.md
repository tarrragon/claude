# 驗證框架操作指引

本文件為 `.claude/rules/core/verification-framework.md` 的詳細展開，包含各層級驗證內容、流程圖、檢查清單、失敗處理流程和指標。

---

## 驗證流程圖

```
用戶輸入命令
    |
    v
[Level 1] 入口層驗證 (Hook 系統)
    |
    +-- Ticket 存在? --> 否 --> 提示 /ticket create → 阻止執行
    +-- 已認領? --> 否 --> 提示 /ticket track claim → 阻止執行
    |
    v
[Level 2] 執行層驗證 (代理人)
    |
    +-- 前置條件滿足? / 依賴 Ticket 完成? / 資源可用?
    |
    v
執行任務
    |
    v
[Level 3] 完成層驗證 (Hook 系統 + 代理人)
    |
    +-- 驗收條件勾選? / 工作日誌記錄? / 測試全部通過?
    |
    v
[Level 4] 驗收層驗證 (PM)
    |
    +-- 驗收條件全部滿足? / 品質標準符合? / 文件記錄完整?
    |
    v
Ticket 標記完成
```

---

## Level 1: 入口層驗證

**驗證者**：Hook 系統（command-entrance-gate-hook.py）

| 驗證項 | 驗證條件 | 失敗處理 |
|-------|---------|--------|
| Ticket 存在 | 系統中存在對應的 pending/in_progress Ticket | 提示 /ticket create |
| Ticket 認領 | Ticket 狀態為 in_progress（已認領） | 提示 /ticket track claim |
| 開發命令識別 | 判斷是否為開發/修改命令 | 不是開發命令則跳過檢查 |
| Ticket 內容品質 | Task Summary 完整（所有 Ticket 適用） | 建議補充內容 |
| Solution 並行化 | Solution 已評估並行化可能性（所有 Ticket 適用） | 建議評估並行化 |
| 建立後品質審核 | acceptance-auditor + system-analyst 並行審核通過（creation_accepted: true） | 派發審核代理人 |

**責任**：Hook 系統負責檢查和提示；用戶負責建立或認領 Ticket；PM 負責監督 Ticket 生命週期

**實作位置**：`.claude/hooks/command-entrance-gate-hook.py` (W2-001)

> Hook 實作細節：.claude/references/verification-hook-implementation.md

---

## Level 2: 執行層驗證

**驗證者**：執行代理人（各 TDD 階段代理人）

| 驗證項 | 驗證條件 | 失敗處理 |
|-------|---------|--------|
| 前置依賴 | 依賴的 Ticket 已完成 | 停止執行，升級 PM |
| 前置條件 | 進入階段的前置條件滿足 | 停止執行，升級 PM |
| 環境正確 | 開發環境、工具鏈可用 | 派發 system-engineer |
| 資料準備 | 必需的資料/測試資料已準備 | 停止執行，補充資料 |
| 認知負擔 | 任務複雜度在可管理範圍 | 升級 PM 進行任務拆分 |

**責任**：代理人負責驗證和決定是否開始；無法繼續時必須升級；PM 負責處理升級的決策

---

## Level 3: 完成層驗證

**驗證者**：Hook 系統（phase-completion-gate-hook.py）+ 代理人

| 驗證項 | 驗證條件 | 失敗處理 |
|-------|---------|--------|
| 驗收條件 | Ticket 中所有驗收條件已勾選 | 提示補充 |
| 工作日誌 | 階段完成報告已記錄到 worklog | 提示更新 worklog |
| 產出物完整 | 所有期望的產出物都已產出 | 提示補充 |
| 測試結果 | 相關測試全部通過（必要時） | 提示修復失敗測試 |
| Ticket 更新 | /ticket track complete 已執行 | 提示執行命令 |
| 並行派發後驗證 | `git diff --stat` 比對代理人報告 vs 實際變更（並行派發時） | 補派缺失檔案的代理人 |

**責任**：Hook 系統負責識別和檢查；代理人負責確保產出物完整；PM 負責監督工作日誌更新

**實作位置**：`.claude/hooks/phase-completion-gate-hook.py` (W2-004)

> Hook 實作細節：.claude/references/verification-hook-implementation.md

---

## Level 4: 驗收層驗證

**驗證者**：acceptance-auditor（執行驗收）+ rosemary-project-manager（最終決策）

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
Ticket 完成請求 → [派發] acceptance-auditor → 執行驗收檢查 → 產出驗收報告
→ [提交] rosemary-PM → 通過 → 完成 / 不通過 → 回到執行修正
```

---

## 驗證失敗處理流程

```
驗證失敗
    |
    v
[分類] 失敗類型
    |
    +-- Level 1 失敗（Ticket 問題）→ [提示] 建立/認領 Ticket
    +-- Level 2 失敗（前置條件）→ [升級] 派發 PM 或協助代理人
    +-- Level 3 失敗（產出物缺陷）→ [提示] 補充產出物或更新文件
    +-- Level 4 失敗（品質問題）→ [建立] 修正 Ticket → [派發] 對應代理人
```

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

## 驗證指標

| 指標 | 計算方法 | 目標 |
|------|--------|------|
| Level 1 通過率 | 開發命令中有效 Ticket 的比例 | > 95% |
| Level 2 耗時 | 發現前置條件問題的平均時間 | < 5 分鐘 |
| Level 3 完整率 | worklog 完整度 | 100% |
| Level 4 驗收率 | 一次驗收通過的比例 | > 90% |

**驗證報告位置**：`.claude/hook-logs/`（各層級驗證的檢查結果、失敗原因和建議改善）

---

## 相關文件

- .claude/rules/core/verification-framework.md - 主檔（框架定義和統一責任對照表）
- .claude/references/verification-scenario-examples.md - 場景範例
- .claude/references/verification-hook-implementation.md - Hook 實作細節

---

**Last Updated**: 2026-03-11
**Version**: 1.0.0 - 從 verification-framework.md 提取操作指引（0.1.0-W35-001.6）
