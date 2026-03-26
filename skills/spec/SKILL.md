---
name: spec
description: "需求完善度品質閘門。Use for: (1) Phase 1 開始時初始化功能規格骨架 (/spec init), (2) 驗證功能規格的需求完善度 (/spec validate), (3) 判斷需求是否足夠清晰可進入實作。Use when: lavender-interface-designer 在 Phase 1 進行功能設計時，作為內部工具使用。不是流程入口——/tdd 管流程編排，/spec 管產出物品質。"
---

# /spec - 需求完善度品質閘門

把模糊需求展開成無歧義的行為契約。

---

## 定位與分工

| 工具 | 問的問題 | 階段 | 關係 |
|------|---------|------|------|
| /tdd | 「流程走到哪了？下一步做什麼？」 | Phase 0-4 全流程 | 流程編排器 |
| /spec | 「需求描述得夠不夠清楚？」 | Phase 1 內部 | 產出物品質工具 |
| SA | 「該不該做？和現有系統一致嗎？」 | Phase 0 | 架構守門人 |

**/spec 不是流程入口**：lavender 在 Phase 1 內部使用 /spec 產出功能規格。/tdd 不呼叫 /spec，/spec 不呼叫 /tdd。兩者完全解耦。

---

## 子命令總覽

| 子命令 | 用途 | 適用時機 |
|--------|------|---------|
| `/spec init` | 初始化功能規格骨架 | Phase 1 開始，lavender 收到 Ticket 後 |
| `/spec validate` | 驗證需求完善度 | 規格撰寫完成後，進入 Phase 2 前 |

---

## `/spec init` - 初始化功能規格骨架

讀取 Ticket frontmatter，自動判斷模式，產出對應模板骨架。

### 輸入

- Ticket ID（必填）：從 frontmatter 讀取 type、where、priority 等欄位

### 模式判斷（自動）

```
讀取 Ticket frontmatter
    |
    v
符合 Full 任一條件？
    |
    +-- 是 → Full 模式（6 區段）
    |
    +-- 否 → Lite 模式（3 區段）
```

**Full 模式觸發條件**（任一符合）：

| 條件 | 判斷依據 |
|------|---------|
| 新功能開發 | type == IMP 且 how.task_type == "新增" |
| 修改檔案多 | where.files > 5 |
| 明確指定 | 用戶執行 `/spec init --mode full` |

**Lite 模式**：不符合任何 Full 條件，或用戶執行 `/spec init --mode lite`。

### 輸出

- 功能規格骨架檔案：`{ticket-id}-feature-spec.md`
- 存放位置：Ticket 所在目錄（`docs/work-logs/v{version}/tickets/`）
- **Spec 文件即 Phase 1 設計文件**（同一檔案，非額外產物）

### Lite 模式骨架（3 區段）

```markdown
# {Ticket ID} 功能規格

## 1. Purpose（目的）
<!-- 用一句話回答：這個功能解決什麼問題？為誰解決？ -->

## 2. Scenarios（行為場景）
<!-- 用 GWT 格式描述每個行為場景 -->
### 場景 1: {場景名稱}
- **Given**: {前置條件}
- **When**: {觸發動作}
- **Then**: {預期結果}

## 3. Acceptance（驗收條件）
<!-- 可直接驗證的條件清單 -->
- [ ] {條件 1}
```

### Full 模式骨架（6 區段）

```markdown
# {Ticket ID} 功能規格

## 1. Purpose（目的）
<!-- 問題背景、目標用戶、核心價值 -->

## 2. API Signatures（介面定義）
<!-- 函式簽名、輸入輸出型別、回傳值語義 -->

## 3. GWT Scenarios（行為場景）
<!-- Given-When-Then 格式，含正常流程和異常流程 -->

## 4. Error Handling（錯誤處理）
<!-- 每個錯誤情境的處理策略和回傳值 -->

## 5. Dependencies（依賴）
<!-- 外部依賴、前置條件、環境假設 -->

## 6. Acceptance（驗收條件）
<!-- 可直接驗證的條件清單，含效能指標（如適用） -->
```

> 完整模板含填寫指引和範例：`references/spec-template-lite.md`、`references/spec-template-full.md`

---

## `/spec validate` - 驗證需求完善度

兩層驗證：結構檢查（機械性）+ AI 語義推演（深度分析）。

### 輸入

- Spec 文件路徑（必填）：`{ticket-id}-feature-spec.md`

### Layer 1：結構檢查（自動，秒級）

檢查模板區段的存在性和非空性。

| 模式 | 必須存在的區段 | 檢查內容 |
|------|--------------|---------|
| Lite | Purpose, Scenarios, Acceptance | 區段標題存在且內容非空 |
| Full | 全部 6 區段 | 區段標題存在且內容非空 |

**額外結構檢查**：

| 檢查項 | 規則 |
|--------|------|
| GWT 格式 | Scenarios 區段至少 1 個 Given-When-Then 完整三元組 |
| Acceptance 可驗證性 | 每個條件以 `- [ ]` 開頭 |
| Purpose 簡潔性 | 不超過 200 字（Lite）/ 500 字（Full） |

**結構檢查失敗**：輸出缺失清單，不進入 Layer 2。

### Layer 2：AI 語義推演（深度，需思考）

沿 3 個核心維度掃描規格文件，找出**未被展開的需求假設**。每個維度產出一組「未回答問題」。Full 模式額外提示情境相關問題（不產出清單、不進入迭代）。

#### 掃描維度

| # | 維度 | 核心問題 | 適用模式 |
|---|------|---------|---------|
| 1 | 邊界完整性 | 極端值、空值、上限下限的行為定義了嗎？ | Lite + Full |
| 2 | 錯誤路徑 | 每個操作失敗時，系統如何回應？ | Lite + Full |
| 3 | 狀態完整性 | 所有狀態和轉換都定義了嗎？有不可達狀態嗎？ | Lite + Full |

**Lite 模式只掃描維度 1-3**，降低小型任務的認知負擔。

#### 情境相關提問（Full 模式額外提示）

Full 模式下，validate 完成維度 1-3 掃描後，**額外提示**以下問題供撰寫者自行考慮。這些不產出未回答問題清單，不進入迭代：

- **並發安全**：多個使用者/執行緒同時操作會怎樣？
- **效能約束**：資料量增長 10x/100x 時行為如何？有回應時間要求嗎？
- **安全性**：誰可以執行此操作？敏感資料如何保護？
- **依賴明確性**：外部依賴的契約是否明確？依賴不可用時的降級策略？

#### 語義推演輸出格式

```markdown
## /spec validate 結果

### 結構檢查：通過/未通過
{缺失清單，如有}

### 語義推演：{N} 個未回答問題

#### 維度 1: 邊界完整性
- Q1: 當 {參數} 為空值時，預期行為是什麼？
- Q2: {集合} 的上限是多少？超過上限時如何處理？

#### 維度 2: 錯誤路徑
- Q3: {操作} 失敗時，是否需要回滾已完成的步驟？

#### 維度 3: 狀態完整性
（無未回答問題）

### 建議
- 必須回答：Q1, Q3（影響 GWT 設計）
- 建議回答：Q2（影響效能設計）
- 可延後：無
```

---

## 迭代機制

/spec validate 可多次執行。回答問題後再次 validate，直到無新問題或達上限。

### 迭代上限（安全閥）

| 模式 | 上限 | 理由 |
|------|------|------|
| Lite | 2 次 | 小型任務不應花費過多時間在規格上 |
| Full | 3 次 | 第 3 次仍有大量問題表示需求本身不成熟，應升級 PM |

達上限時輸出警告，剩餘問題標記為 Phase 2 待解決。

---

## 使用流程

Phase 1 中 lavender 如何使用 /spec 的完整流程，詳見 lavender 代理人定義（`.claude/agents/lavender-interface-designer.md`「/spec 工具整合」章節）。

/spec 只負責「發現問題」（產出骨架和未回答問題清單），不負責「解決問題」（由 lavender 決定如何回答和組織）。

---

## 相關文件

- .claude/skills/tdd/SKILL.md - TDD 流程工具（流程編排）
- .claude/agents/lavender-interface-designer.md - Phase 1 設計代理人（/spec 的使用者）
- .claude/pm-rules/tdd-flow.md - TDD 完整流程定義
- references/spec-template-lite.md - Lite 模板（3 區段）
- references/spec-template-full.md - Full 模板（6 區段）

---

**Version**: 1.1.0
**Last Updated**: 2026-03-25
**Source**: 0.2.0-W3-003（Phase 3b context 耗盡 → 需求完善度品質閘門）
**Changes**: v1.1.0 - 三人組共識簡化（0.2.0-W3-011）：刪除核心抽象/反向提問策略、維度 4-7 降級為提示、精簡迭代機制、init 條件簡化為 2 個
