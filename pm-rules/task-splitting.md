# 任務拆分指南

> **核心目標**：遵循 SRP（單一職責原則），讓每個任務聚焦單一職責，提高思考深度和實作品質。
> **次要目標**：將認知負擔控制在可管理範圍內（指數 < 10），避免超出平台限制。
>
> **拆分不是為了「代理人能不能做完」，而是為了「代理人能不能做好」。**

---

## 拆分觸發條件（任一符合即需拆分）

| 條件 | 閾值 |
|------|------|
| 變數狀態數 | > 5 個 |
| 架構層級數 | > 2 層 |
| 依賴關係數 | > 3 個 |
| 修改檔案數 | > 5 個 |
| 認知負擔指數 | > 10 |
| Subagent tool call 預算 | > 15 次（估算） |

### Subagent Tool Call 預算

> Subagent 每 turn 約 ~20 tool calls（軟限制，觸發 `pause_turn`）。
> **15 次**是安全預算（75% 緩衝），**非硬性斷點**。超過 15 次的任務應評估拆分或精簡 prompt。
> 三階分級判斷規則和分工流程：`.claude/pm-rules/two-stage-dispatch.md`
> 平台限制資料來源：`.claude/references/claude-code-platform-limits.md`

---

## 3b 派發前檢查（PM 派發 Phase 3b 實作前的強制檢查門）

> **核心定位**：本章節是 PM 在 TDD Phase 3b（GREEN 實作派發）之前的整合性檢查門，將上方通用拆分條件收斂為三項核心閾值與單一 CLI 入口，避免 PM 派發過大任務壓垮代理人認知負擔。

**Why**：3b 派發決策路徑歷史上缺乏強制檢查點——通用拆分條件涵蓋多場景（變數狀態、層級、依賴、檔案、認知負擔、tool call），PM 派發前若逐項對照，認知負擔本身即超過 7±2 上限，導致 PM 趕時間直接跳過；W17-048 系列即為「派發後撞 Hook 30 行硬上限才被迫拆分」的典型案例。

**Consequence**：缺乏 3b 派發前檢查門會導致（1）代理人回合耗盡，commit 時遺漏部分職責；（2）Context Bundle 膨脹超過 20K tokens 在實作前已逼近 context window 上限；（3）PM 在 Hook 阻擋後才補拆分，浪費已寫入的 prompt 與 Context Bundle。

**Action**：派發 3b 實作 ticket 前，PM 在主線程執行 CLI 主動檢查，並對照三項閾值清單；任一項超標則建立拆分 ticket 並更新 `spawned_tickets`。

### 三項核心閾值（速查）

| 閾值 | 拆分門檻 | 取得方式 |
|------|---------|---------|
| 功能職責數 | > 2 須拆分 | 數 ticket 涵蓋的獨立功能職責（一個職責 = 一個動詞 + 單一目標） |
| 修改檔案數 | > 5 須拆分 | `where.files` 計數，或從 Problem Analysis 影響範圍推算 |
| Context Bundle tokens | > 3000 軟上限 / > 5000 強制拆分 | claim 後 `ticket show <id>` 查 PCB 區段字數 |

> **權威來源（SSOT）**：三項閾值的完整 Why/Consequence/Action、跨進程同步修復豁免條款、與通用閾值矩陣的關係定義於 `.claude/references/cognitive-load-execution-details.md` §3b 派發前閾值。本章節僅作流程錨點與檢查入口，**不重複定義**閾值內容；如需修改閾值請改 references 檔，本檔自動跟隨。

### 主檢查機制：`ticket track dispatch-readiness` CLI

PM 派發 3b 子任務前，對該 ticket 執行：

```bash
ticket track dispatch-readiness <ticket-id>
```

**Exit code 行為**：

| Exit Code | 語意 | PM 動作 |
|-----------|------|---------|
| 0 | pass（三項閾值均通過） | 可派發 |
| 1 | 軟警告（接近閾值或某項 borderline） | 手動覆核後決定派發或拆分 |
| 2 | 強制拆分（任一項超標）或 IO 錯誤 | 必須拆分後重新檢查 |

> **CLI 邊界**：閾值 1（功能職責數）以 acceptance 條目近似，含驗證類條目時可能高估；PM 於 WARN/FAIL 應手動覆核功能職責是否真的 > 2。完整參數與輸出格式見 `.claude/skills/ticket/SKILL.md`「track dispatch-readiness 子命令」與 `references/track-command.md`。

> **與既有 Hook 的分工**：`agent-prompt-length-guard-hook` 檢 prompt 行數（30 行硬上限），偵測「prompt 大小」；`dispatch-readiness` 檢三項閾值，偵測「任務大小」。兩者不同維度，互補而非重複（W17-049 三方審查共識）。

### PM 派發前檢查清單

派發 3b 實作 ticket 前，PM 在主線程逐項勾選：

- [ ] 已執行 `ticket track dispatch-readiness <ticket-id>` 且 exit code = 0
- [ ] 功能職責數 ≤ 2（一個 ticket 一個動詞 + 單一目標，最多兩個高度耦合的副職責）
- [ ] 修改檔案數 ≤ 5（`where.files` 或 Problem Analysis 影響範圍）
- [ ] Context Bundle tokens ≤ 3000（> 3000 走豁免說明；> 5000 必拆）
- [ ] 若任一項超標，已建立拆分 ticket 並更新 `spawned_tickets`
- [ ] 已對照跨進程同步修復豁免條款（如適用，於 Problem Analysis 顯性記錄）

### 升級條件（Tripwire）

> **定位**：本章節是「規則層 + CLI 主動執行」雙層方案的升級觀測指標，30 天後依實證決定是否擴展至 Hook 強制層、縮範圍或廢棄。

**觀測期**：3b 派發前檢查章節落地後 30 天

**三項觀測指標**：

| 指標 | 量測方式 | 升級門檻 |
|------|---------|---------|
| CLI 主動執行率 | 30 天內 3b 派發次數中執行 `dispatch-readiness` 的比率 | < 50% → 加 Hook 純 metadata 兜底（零 token 成本，僅檢 `where.files` 數） |
| 派發一次通過率 | 通過 CLI 後派發未撞 prompt-length-guard 或回合耗盡的比率 | < 80% → 三項閾值需重校（功能職責數定義或門檻調整） |
| 誤擋率 | CLI 回 exit 2 但 PM 覆核後確認可派發的比率 | > 20% → 閾值門檻過嚴，需放寬或加豁免條款 |

**評估流程**：

| 步驟 | 操作 |
|------|------|
| 1. 採樣 | 30 天內所有 3b 派發 ticket 標註 CLI 執行狀態與派發結果 |
| 2. 計算指標 | 依上表三項公式計算實際比率 |
| 3. 觸發決策 | 任一指標越過升級門檻 → 建立評估 ticket，依方向（加 Hook / 重校閾值 / 加豁免）規劃下一步；無越界 → 結案保留現方案 |
| 4. 升級條件結算 ticket | 由 W17-055（30 天後效果驗證）執行 |

> **觀測對象 ticket**：W17-055（30 天後效果驗證）為本 tripwire 的結算入口。詳細評估流程與假設清單見 W17-049 ANA「仍未驗證假設」章節。

---

## 拆分策略速查

| 策略 | 適用情境 | 關鍵原則 |
|------|---------|---------|
| 1. 按架構層 | 跨多個 Clean Architecture 層 | 由底層向上，每層一個任務 |
| 2. 按功能模組 | 涉及多個獨立模組 | 共用模組先完成，獨立可並行 |
| 3. 按操作類型 | 混合機械性和邏輯修改 | 機械可並行，邏輯需序列 |
| 4. 按 TDD 階段 | 完整功能開發 | 嚴格序列 Phase 1→4 |
| 5. 批量修正 | Review/Audit 跨多檔案 | 拆分單元是**檔案**不是問題 |
| 6. 檔案所有權 | 2+ ticket 預期並行 | 同 Wave 每檔最多一個 ticket 寫入 |
| 7. 按測試群組（SRP 導向） | Phase 3b 實作拆分 | 以 **SRP 功能職責** 為首要判斷，以 **Phase 2 GWT scenario group** 為拆分單位 |
| 8. 按依賴鏈序列 | 步驟間有嚴格先後依賴 | 上游 Ticket 完成後才能開始下游，用 `blockedBy` 標記 |

> **策略 7 核心原則**：拆分判斷的首要標準是「功能職責是否單一」（SRP），而非 context 預算或代理人能否處理。每個子任務應聚焦單一功能面，代理人只需讀取對應的 API 簽名 + 測試案例。測試群組間有依賴時，透過序列派發解決，不以依賴為由合併。

> 各策略詳細說明和範例：.claude/references/task-splitting-strategies.md

---

## 拆分後組織方式

| 場景 | 組織方式 | 建立指令 |
|------|---------|---------|
| 拆分產生的子步驟（共享目標） | 子任務 | `/ticket create --parent {parent_id}` |
| 拆分中發現的獨立問題 | 獨立 Ticket | `/ticket create` |
| 原 Ticket 過大需拆分 | 子任務群組 | 原 Ticket 改為協調任務，各子步驟建為子任務 |

**決策流程**：

```
拆分產生的新任務
    |
    v
與原 Ticket 共享完成目標？
    +-- 是 → 移除原 Ticket 後此任務是否仍有意義？
    |        +-- 否 → 子任務（--parent）
    |        +-- 是 → 獨立 Ticket（可能有 relatedTo）
    +-- 否 → 獨立 Ticket
```

**實際案例**：

| 案例 | 決策 | 理由 |
|------|------|------|
| 拆分 Hook 任務 → 衍生「統一 helper」任務 | 獨立 Ticket | 統一 helper 任務有獨立價值，移除原 Hook 拆分任務後仍有意義 |
| 分析任務 → 分析結論衍生 3 項改善子任務 | 子任務 | 三項改善都源自同一分析結論，移除分析任務後子任務失去 context |
| 分析任務 → 過程中發現獨立模組 bug | 獨立 Ticket（spawned） | bug 修復是獨立問題，不依賴分析任務存在 |

---

## 拆分後檢查清單

### A. Atomic 性（每個 ticket）

- [ ] 能用「動詞 + 單一目標」描述
- [ ] 只有一個修改原因
- [ ] `where.files` 已填寫完整修改檔案清單

### B. 檔案所有權（跨 ticket，強制）

- [ ] 檔案所有權矩陣無 Write-Write 衝突
- [ ] 共用檔案的問題已合併到同一 ticket

### C. 並行可行性

- [ ] 認知負擔指數 < 10（每個 ticket）
- [ ] 依賴關係明確標記（blockedBy）
- [ ] Wave 無跨越

### D. 交接 Context 品質（SRP 核心）

拆分的目的是讓每個任務聚焦思考。交接時必須確保下游任務有足夠 context 獨立深度思考：

| 交接類型 | Context 要求 | 驗證方式 |
|---------|-------------|---------|
| 父 → 子 | 父任務的分析結論寫入 execution log | 子任務能從父 Ticket 的 Solution 取得完整 context |
| 兄弟 → 兄弟 | handoff 包含前一任務的產出摘要 | 下一個兄弟不需要重新分析前一個的結論 |
| ANA → IMP | 分析結論 1:1 對應到 IMP 的 AC | IMP 代理人不需要重讀 ANA 的原始資料 |

**反模式**：

| 反模式 | 問題 | 正確做法 |
|--------|------|---------|
| 子任務只有 title 沒有 context | 代理人要重新探索，浪費 SRP 聚焦時間 | 5W1H 完整 + Solution 有具體策略 |
| Handoff 只寫方向不寫內容 | 下一個 session 的 PM 失去前一個的思考深度 | Handoff 包含結論摘要和下一步建議 |
| ANA 結論散落在 execution log 沒有結構化 | IMP 代理人要從長文中提取關鍵資訊 | ANA Solution 按 AC 結構化，IMP 直接引用 |

---

## 決策樹

```
任務進入 → 認知負擔 <= 10? → 是 → 直接派發
                             → 否 → 識別複雜度來源
                                    → 跨架構層 → 策略 1
                                    → 跨模組 → 策略 2
                                    → 混合操作 → 策略 3
                                    → 新功能 → 策略 4
                                    → 批量修正 → 策略 5
                                    → Phase 3b 實作 → 策略 7
                                    → 步驟間嚴格先後依賴 → 策略 8
                                    ↓
                              [強制] 檔案所有權驗證（策略 6）
                                    → 無衝突 → 建立 Ticket
                                    → 有衝突 → 合併後重新驗證
```

---

## 常見錯誤

| 錯誤 | 解決 |
|------|------|
| 拆分過細 | 確保每個子任務有足夠獨立性 |
| 隱藏依賴 | 仔細分析依賴，明確標記 |
| 混合操作類型 | 按操作類型分離 |
| 檔案所有權重疊 | 建立矩陣，合併共用檔案 |

---

## 相關文件

- .claude/references/task-splitting-strategies.md - 策略詳細說明和範例
- .claude/rules/core/cognitive-load.md - 認知負擔設計原則
- .claude/pm-rules/parallel-dispatch.md - 並行派發指南

---

**Last Updated**: 2026-05-17
**Version**: 5.1.0 — 新增「3b 派發前檢查」章節（W17-054 落地，W17-049 ANA 階段三）：引用 cognitive-load-execution-details.md SSOT、`ticket track dispatch-readiness` CLI 為主檢查機制、tripwire 三項觀測指標（CLI 主動執行率 / 派發一次通過率 / 誤擋率）。歷史 5.0 版見 git log。
