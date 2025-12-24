# Ticket #N: [動詞] [目標]

---

## 📖 模板使用說明

### 使用時機

**本模板適用於**：
- ✅ 單一明確的 Ticket 任務
- ✅ 從主版本任務拆分出的子任務
- ✅ 可獨立執行和驗收的工作單元
- ✅ 由單一執行代理人負責的任務

**不適用於**：
- ❌ 包含多個 Ticket 的主版本任務 → 請使用 `work-log-template.md`
- ❌ 需要多個代理人協作的複雜任務 → 拆分為多個 Ticket

### 模板選擇決策樹

```text
任務是否可拆分為多個獨立 Ticket？
├─ 是 → 使用 work-log-template.md 作為主日誌
│         - 為每個 Ticket 建立 ticket-log-template.md
│         - 主日誌包含 Ticket 索引表
│
└─ 否 → 任務是否為單一明確工作單元？
          ├─ 是 → 使用 ticket-log-template.md（本模板）
          └─ 否 → 使用 work-log-template.md

Ticket 是否已從主版本任務拆分？
├─ 是 → 使用 ticket-log-template.md（本模板）
│         - 檔名：vX.Y.Z-ticket-NNN.md
│         - 主版本日誌：vX.Y.Z-main.md
│
└─ 否 → 獨立 Ticket 或小型任務
          - 可使用 ticket-log-template.md
          - 或直接使用 work-log-template.md
```

### 檔案命名規範

**Ticket 日誌格式**：
- `vX.Y.Z-ticket-NNN.md` - Ticket 編號 3 位數（從主版本拆分）
- `vX.Y-ticket-NNN.md` - 中版本 Ticket（如適用）
- 範例：`v0.12.I-ticket-001.md`

**主版本日誌對應**：
- 主日誌：`v0.12.I.0-work-log-standardization-main.md`
- Ticket 1: `v0.12.I-ticket-001.md`
- Ticket 2: `v0.12.I-ticket-002.md`

### 與 Work-Log 模板的關係

| 項目 | work-log-template | ticket-log-template |
|-----|------------------|-------------------|
| **使用場景** | 主版本任務 | 單一 Ticket 任務 |
| **Ticket 數量** | 多個或不確定 | 單一明確 |
| **管理層級** | 主線程管理 | 執行代理人執行 |
| **記錄範圍** | 整體規劃和進度 | 單一 Ticket 詳細執行 |
| **Ticket 索引** | 包含 Ticket 索引表 | 不包含 |
| **5 個核心欄位** | 選擇性包含 | 必須包含 |

### Ticket 設計 5 個核心欄位

**基於 ticket-design-dispatch-methodology.md**：

1. **背景（Background）** - 為什麼需要這個 Ticket
2. **目標（Objective）** - 要達成什麼，成功標準
3. **執行步驟（Steps）** - 具體執行步驟清單
4. **驗收條件（Acceptance Criteria）** - SMART 原則驗收條件
5. **參考文件（References）** - 需求規格、設計文件、技術文檔

### 填寫原則

> **基於《清單革命》原則和 Ticket 生命週期管理方法論設計**。
> 整合標準化工作日誌格式和 Ticket 特定欄位。
> 所有標記為「❗必填」的欄位不可省略。

**核心原則**：
1. **5 個核心欄位必填** - 確保 Ticket 設計完整
2. **SMART 驗收條件** - 具體、可測量、可達成、相關、有時限
3. **單一職責** - 一個 Ticket 只做一件事
4. **獨立可驗收** - 可獨立執行和驗收，不依賴其他 Ticket（除明確標記依賴）

---

## Ticket 資訊

**Ticket 編號**: #N ❗必填
**Ticket 類型**: [定義/撰寫/實作/整合/修復/重構] ❗必填
**建立日期**: YYYY-MM-DD ❗必填
**狀態**: [參照下方「Ticket 狀態判定」] ❗必填
**完成日期**: YYYY-MM-DD HH:MM（未完成則標記「N/A」） ❗必填

**指派**: [執行代理人名稱]
**優先級**: [高/中/低]
**預估工時**: X 小時
**實際工時**: Y 小時（完成後填寫）

---

## 1. 背景（Background）❗必填

[為什麼需要這個 Ticket？來自哪個需求或問題？]

**來源需求**:
- `docs/app-requirements-spec.md` - #UC-XX
- `docs/work-logs/vX.Y.Z-main.md` - 主版本任務拆分

**相關問題**:
[連結到相關的 Issue 或問題描述]

---

## 2. 目標（Objective）❗必填

[這個 Ticket 要達成什麼？明確且可驗證的目標描述]

**成功標準**:
- [標準 1：具體、可測量]
- [標準 2：具體、可測量]

---

## 3. 執行步驟（Steps）❗必填

### 步驟清單

1. [具體執行步驟 1]
2. [具體執行步驟 2]
3. [具體執行步驟 3]
4. [具體執行步驟 4]
5. [具體執行步驟 5]

### 步驟執行追蹤

- [ ] 步驟 1 - [描述]
- [ ] 步驟 2 - [描述]
- [ ] 步驟 3 - [描述]
- [ ] 步驟 4 - [描述]
- [ ] 步驟 5 - [描述]

---

## 4. 驗收條件（Acceptance Criteria）❗必填

> **SMART 原則**：
> - **Specific**: 具體明確，無模糊描述
> - **Measurable**: 可測量，可客觀驗證
> - **Achievable**: 可達成，在 Ticket 範圍內
> - **Relevant**: 相關聯，與 Ticket 目標直接相關
> - **Time-bound**: 有時限，在預估工時內完成

### 功能驗收

- [ ] [功能驗收條件 1：檔案存在、測試通過等]
- [ ] [功能驗收條件 2：檔案存在、測試通過等]
- [ ] [功能驗收條件 3：檔案存在、測試通過等]

### 品質驗收

- [ ] 所有相關測試 100% 通過
- [ ] `dart analyze` 0 錯誤 0 警告
- [ ] 程式碼符合專案品質標準（code-quality-examples.md）
- [ ] 無 TODO 或技術債務標記（或已記錄到 todolist）

### 文件驗收

- [ ] 工作日誌已更新完成記錄
- [ ] 主版本日誌 Ticket 索引已更新
- [ ] 相關文件（README, API 文檔）已同步更新

---

## 5. 參考文件（References）❗必填

### 需求規格
- `docs/app-requirements-spec.md` - #UC-XX
- `docs/app-use-cases.md` - #UseCase-XX

### 設計文件
- `docs/work-logs/vX.Y.Z-design-decisions.md` - #決策N
- [其他相關設計文件]

### 技術文檔
- [相關技術文檔連結或路徑]
- [API 文檔、框架文檔等]

---

## 6. 依賴 Ticket（Dependencies，選填）

### 前置依賴（必須先完成）

- [ ] Ticket #X: [描述] - 狀態：[待執行/進行中/已完成]

### 並行依賴（可同時執行）

- [ ] Ticket #Y: [描述] - 狀態：[待執行/進行中/已完成]

### 後續依賴（依賴本 Ticket）

- [ ] Ticket #Z: [描述] - 將在本 Ticket 完成後開始

---

## 🎯 TDD 階段狀態

> **填寫規則**：
> - 每個階段只能有一個狀態：✅ 完成 / 🔄 進行中 / ⏸️ 待開始
> - 完成時間必須填寫實際時間（精確到分鐘）
> - 備註欄記錄關鍵成果或決策

| TDD 階段 | 狀態 | 完成時間 | 備註 |
|---------|------|---------|------|
| **Phase 1** 設計 | ⏸️ 待開始 | N/A | Ticket 建立即完成 Phase 1 |
| **Phase 2** 測試 | ⏸️ 待開始 | N/A | 測試案例數量：X 個 |
| **Phase 3** 實作 | ⏸️ 待開始 | N/A | 測試通過率：X/X |
| **Phase 4** 重構 | ⏸️ 待開始 | N/A | 重構項目：X 項 / 無需重構 |

### 📊 Ticket 狀態判定

> **Ticket 生命週期狀態**（基於 ticket-lifecycle-management-methodology.md）：
> - ⏸️ **待執行（Pending）** = Ticket 已建立，等待開發者領取
> - 🔄 **進行中（In Progress）** = 開發者正在執行，TDD Phase 1-3 階段
> - 👀 **Review 中（In Review）** = 開發者認為已完成，等待驗收
> - ✅ **已完成（Completed）** = Review 通過，所有驗收條件滿足

**當前狀態**: ⏸️ 待執行

**狀態說明**:
[說明當前狀態的原因或背景]

---

## 🤝 協作檢查點（Communication Checkpoints）

> **設計目標**: 確保跨代理人協作時關鍵資訊傳遞無誤
>
> **核心原則**：
> "這張表單叫做「溝通進度表」，也是一種清單，但追蹤的不是工程本身，而是溝通的進行狀況。"
> —《清單革命》

### Ticket 領取確認

**使用時機**: 開發者領取 Ticket 時

- [ ] 已閱讀並理解 Ticket 背景和目標
- [ ] 已確認所有依賴 Ticket 狀態（前置依賴已完成）
- [ ] 已確認參考文件可存取
- [ ] 已確認有足夠時間投入（預估工時合理）
- [ ] 已標記 Ticket 狀態為「進行中」並記錄開始時間

### Phase 交接溝通確認

**使用時機**: 每個 Phase 完成後

- [ ] 前一階段產出已完整記錄到工作日誌
- [ ] 下一階段代理人已閱讀前一階段產出
- [ ] 有疑問或不明確處已提出並解答
- [ ] 主線程已確認可以繼續下一階段

### Review 提交確認

**使用時機**: 提交 Review 前

- [ ] 所有步驟執行追蹤已打勾
- [ ] 所有驗收條件已逐項自我檢查並打勾
- [ ] 所有測試 100% 通過
- [ ] 工作日誌已更新完整執行記錄
- [ ] 已標記 Ticket 狀態為「Review 中」並通知 Reviewer

---

## ⏸️ 驗收暫停點（Verification Pause Points）

> **設計目標**: 明確定義何時必須停下來進行檢查
>
> **核心原則**：
> "在製作清單的時候，你必須做一些重要決定。首先，你得確定使用清單的暫停點。"
> —《清單革命》

### 暫停點使用規則

- ⏸️ 執行代理人完成階段後必須主動暫停
- 📋 主線程在暫停點執行驗收檢查
- ✅ 通過檢查後才能繼續下一階段
- ❌ 未通過檢查則返回修正

### Ticket 特定暫停點

**領取暫停點** - Ticket 領取後
- 觸發條件: 開發者領取 Ticket
- 檢查人: 開發者自我檢查
- 通過標準: Ticket 領取確認清單全部打勾

**Phase 2 暫停點** - 測試設計完成後
- 觸發條件: sage 標記 Phase 2 完成
- 檢查人: rosemary-project-manager
- 通過標準: Phase 2 驗收條件全部打勾

**Phase 3 暫停點** - 實作完成後
- 觸發條件: parsley 標記 Phase 3 完成
- 檢查人: 開發者自我檢查
- 通過標準: 所有步驟執行追蹤打勾 + 所有測試通過

**Review 提交暫停點** - 提交 Review 前
- 觸發條件: 開發者認為已完成
- 檢查人: 開發者自我檢查
- 通過標準: Review 提交確認清單全部打勾

**Review 完成暫停點** - Review 檢查完成後
- 觸發條件: Reviewer 完成檢查
- 檢查人: rosemary-project-manager
- 通過標準: 所有驗收條件打勾 + Review 通過

---

## 📋 清單使用模式（Checklist Usage Modes）

> **設計目標**: 明確不同場景下的清單使用方式
>
> **核心原則**：
> "你必須決定採用操作確認模式，或是大家一起一步步照著清單來做。"
> —《清單革命》

### 模式選擇

**本次使用模式**: [執行代理人填寫：DO-CONFIRM / READ-DO]

### 模式 1: 操作確認模式（DO-CONFIRM）

**適用場景**:
- 執行過類似 Ticket 3 次以上
- Ticket 步驟簡單明確
- 開發者對技術棧熟悉

**使用方式**: 先自主完成工作，然後暫停，對照清單逐項確認

### 模式 2: 步驟執行模式（READ-DO）

**適用場景**:
- 首次執行此類 Ticket
- Ticket 步驟複雜或有多個依賴
- 涉及不熟悉的技術或框架

**使用方式**: 邊看清單邊執行，逐項完成並打勾

---

## 📋 執行記錄

### Ticket 執行時間軸

**領取時間**: YYYY-MM-DD HH:MM
**開始時間**: YYYY-MM-DD HH:MM
**提交 Review 時間**: YYYY-MM-DD HH:MM
**Review 完成時間**: YYYY-MM-DD HH:MM
**完成時間**: YYYY-MM-DD HH:MM

**總耗時**: X 小時 Y 分鐘
**與預估差異**: +Z% / -Z%

### Phase 1: Ticket 建立（已完成）

**執行時間**: YYYY-MM-DD HH:MM ~ YYYY-MM-DD HH:MM
**執行人**: [PM 或 lavender-interface-designer]

**Ticket 設計**:
- 標題格式：[動詞] [目標]
- 5 個核心欄位已完整填寫
- 驗收條件符合 SMART 原則

---

### Phase 2: 測試設計

**執行時間**: YYYY-MM-DD HH:MM ~ YYYY-MM-DD HH:MM
**執行代理人**: sage-test-architect

**測試案例設計**:
[記錄測試案例數量、覆蓋範圍、測試策略]

**測試文件**:
- `test/...` - X 個測試案例

**遇到的問題**:
[記錄遇到的問題和解決方案]

---

### Phase 3: 實作執行

**執行時間**: YYYY-MM-DD HH:MM ~ YYYY-MM-DD HH:MM
**執行代理人**: pepper-test-implementer (Phase 3a 策略) + parsley-flutter-developer (Phase 3b 實作)

**實作策略**:
[記錄 pepper 提供的實作策略、虛擬碼、流程圖]

**程式碼實作**:
[記錄 parsley 實作的關鍵邏輯、程式碼片段]

**步驟執行記錄**:
- ✅ 步驟 1: [記錄完成情況]
- ✅ 步驟 2: [記錄完成情況]
- ✅ 步驟 3: [記錄完成情況]

**測試結果**:
- 測試通過率：X/X (100%)
- dart analyze：0 錯誤 0 警告

**遇到的問題**:
[記錄遇到的問題和解決方案]

---

### Phase 4: 重構優化

**執行時間**: YYYY-MM-DD HH:MM ~ YYYY-MM-DD HH:MM
**執行代理人**: cinnamon-refactor-owl

**重構評估**:
[記錄 cinnamon 的評估結果和建議]

**重構項目**:
- [ ] 重構項目 1（如有）
- [ ] 重構項目 2（如有）
- ✅ 確認無需重構（說明理由）

**重構結果**:
[記錄重構後的改善和測試結果]

---

## Review 記錄

### Review #1

**Reviewer**: XXX
**Review 日期**: YYYY-MM-DD
**Review 結果**: ✅ 通過 / ❌ 需修正

**檢查項目**:
- [ ] 所有驗收條件已滿足
- [ ] 測試 100% 通過
- [ ] 程式碼品質達標
- [ ] 文件已同步更新

**Review 建議**:
[記錄 Reviewer 的建議和改進意見]

**修正記錄**（如 Review 未通過）:
[記錄需要修正的項目和修正結果]

---

## 📦 產出檔案

### 新增檔案
- `lib/...` - [檔案說明]
- `test/...` - [測試檔案說明]

### 修改檔案
- `lib/...` - [修改說明]

### 文件更新
- `docs/work-logs/vX.Y.Z-main.md` - Ticket 索引已更新
- `docs/...` - [其他文件更新說明]

---

## 💡 執行心得（選填）

### 做得好的地方
- [記錄執行順利的部分和原因]

### 遇到的挑戰
- [記錄遇到的困難和解決方法]

### 改進建議
- [對 Ticket 設計或執行流程的改進建議]

### 知識沉澱
- [記錄可重用的知識和技巧]

---

**最後更新時間**: YYYY-MM-DD HH:MM
**最後更新人**: [代理人名稱]
**Ticket 狀態**: [待執行/進行中/Review 中/已完成]
