# Context Bundle 規範

> **目標**：PM 在派發代理人前，將該代理人需要的所有資訊寫入 Ticket，代理人只需讀取 Ticket 即可開始工作。

---

## 定義

**Context Bundle** 是 Ticket 執行日誌中的一個區段。PM 在派發代理人前，透過 `ticket track append-log --section "Execution Log" "### Context Bundle\n..."` 寫入下一階段代理人所需的前置資訊。

---

## 核心原則

1. **Inline 優先**：關鍵資訊直接寫入，不是只給路徑讓代理人自己讀
2. **1 Read 原則**：代理人只需 1 次 Read Ticket 就能獲得全部 context
3. **簡短有效**：不超過 5K tokens，只寫代理人真正需要的

---

## 通用模板

所有 Phase 轉換和任務派發使用同一模板，PM 按需填寫相關欄位：

```markdown
### Context Bundle

**需求摘要**: {一句話描述代理人要做什麼}
**API 簽名**: {代理人需要知道的介面，inline}
**相關檔案**: {路徑 + 一句話說明，只列代理人必須讀的}
**驗收條件**: {從 Ticket 5W1H 提取}
**約束**: {代理人應知道的限制或注意事項}
**測試指令**: {如適用}
```

欄位按需填寫，不強制全填。各 Phase 有特定的額外欄位建議，詳見 `.claude/references/context-bundle-phase-guide.md`。

---

## 認領時 Context 驗證

PM 認領 Ticket 後、填寫 Context Bundle 前，必須先完成 Context 驗證：

| 驗證項 | 動作 | 失敗時處理 |
|-------|------|-----------|
| 目標檔案存在 | glob/ls 確認 where.files 路徑 | 關閉 Ticket 或修正 where.files |
| 前提假設成立 | 確認架構/依賴/API 未變更 | 更新 Ticket 描述或重新評估 |
| 跨專案關聯性 | 確認範疇正確、無重疊 Ticket | 關閉/遷移/合併重疊 Ticket |

> **來源**：歷史經驗——曾有 Ticket 的目標檔案不存在於當前 codebase，浪費認領後的分析時間。

---

## PM 填寫流程

```
代理人完成 Phase N → PM 讀取回報 → 提取關鍵資訊 → 寫入 Context Bundle → 派發下一階段
```

**派發 prompt 只需**：Ticket 路徑 + 動作指令 + 「Context Bundle 已準備，讀取 Ticket 後開始」。

### 標準 Agent Prompt 模板

```
Ticket: {ticket_id}
任務: {ticket title}
Ticket 路徑: docs/work-logs/v{version}/tickets/{ticket_id}.md

請 Read Ticket 取得完整 Context Bundle 和驗收條件。
完成後用 ticket track append-log 更新 Solution 和 Test Results。
```

> **[強制] Prompt 長度上限**：Agent prompt 不得超過 30 行。超過表示 context 未正確存入 Ticket。（PC-040）

---

## 代理人完成摘要格式

代理人完成任務後，寫入 Ticket Solution 區段：

```markdown
### Phase {N} 完成摘要
**產出物**: {路徑}
**關鍵決策**: {1-3 個}
**下一階段需注意**: {代理人認為下一階段應知道的事}
**結果**: {數字摘要}
```

PM 從此摘要提取資訊填入下一個 Context Bundle。

---

## 代理人中間進度更新

> **目標**：PM 查 Ticket 即可知道代理人進度，不需要查代理人 output。只有異常（失敗/阻塞）時才需要 PM-代理人直接溝通。

### 更新時機

代理人在以下時機執行 `ticket track append-log` 更新 Ticket：

| 時機 | 更新內容 | 範例 |
|------|---------|------|
| 開始工作 | 確認已讀取 Context Bundle | `開始執行，已讀取 Context Bundle` |
| 關鍵階段完成 | 階段結果 + 下一步 | `測試通過 5/5，開始實作第二個函式` |
| 遇到阻塞 | 阻塞原因 + 需要什麼 | `缺少 X 模組的 API 簽名，需 PM 補充` |
| 任務完成 | 完成摘要（見上節） | 完整的 Phase N 完成摘要 |

### 標準 Agent Prompt 模板（含中間更新）

```
Ticket: {ticket_id}
任務: {ticket title}
Ticket 路徑: docs/work-logs/v{version}/tickets/{ticket_id}.md

請 Read Ticket 取得完整 Context Bundle 和驗收條件。

進度更新規範：
- 開始時：ticket track append-log {ticket_id} "開始執行，已讀取 Context Bundle"
- 關鍵階段完成時：ticket track append-log {ticket_id} "階段摘要"
- 完成時：更新 Solution 和 Test Results 區段
```

### PM 行為

| PM 想知道進度時 | 正確做法 | 禁止做法 |
|---------------|---------|---------|
| 查詢單一 Ticket | `ticket track query {id}` 看 log | 用 SendMessage 問代理人 |
| 查詢全局進度 | `ticket track snapshot` | 逐一檢查每個代理人的 output |
| 代理人阻塞 | 代理人已更新 Ticket，PM 看到後補充資訊 | 定時輪詢代理人狀態 |

---

## Layer 1 自檢

代理人完成任務後、complete 前，執行 Layer 1 自律審查輪，攔截低階品質違規。

### 觸發時機

| 時機 | 動作 |
|------|------|
| IMP/ANA/DOC ticket 的 ticket body 填寫完畢後 | 依 `.claude/references/agent-self-check-template.md` 執行一輪掃描 |
| 純機械任務（格式修正、路徑替換） | 可省略；需在 commit msg 標記「Layer 1 不適用 by 純格式修正」 |

### 如何觸發

PM 在派發 prompt 末段加入以下任一形式（詳見 `.claude/references/agent-dispatch-template.md` 的「Layer 1 自檢觸發指引」章節）：

- **標準版**：「完成後 complete 前，依 agent-self-check-template 執行 Layer 1 自檢」
- **精簡版**：「commit 前快速掃描禁用字和 emoji」

### 自檢結果寫入位置

| 自檢結論 | 寫入位置 |
|---------|---------|
| 發現違規（已修正） | Solution `### 自檢結果`：列出違規項目與處理方式 |
| 零違規 | 可省略記錄；若有 Layer 2 委員審查需求時補寫 |

### 與 Layer 2 委員的邊界

Layer 1 寫入 `## Solution` 的子章節；Layer 2 委員報告寫入 `## Test Results`。兩者不重疊，PM 合併 ticket 時不會覆寫衝突。

---

## PM 預寫策略與 Solution 職責邊界

> **來源**：W17-206 ANA 根因 b+c（PM 預寫 Solution H2 違規 + 雙寫重複，W17-205 案例）。落地方案 D+C：規則明示 + Context Bundle 改寫。

### 條款 1：PM 預寫實作策略放 Context Bundle，不放 Solution

PM 派發前若需預寫實作策略（PC-040 反推情境：先分析確認代理人執行路徑），應將策略寫入 Context Bundle 的 H3 子節，而非寫入 `## Solution`。

**Why**：`## Solution` 章節設計為 agent 執行結果的記錄載體；PM 預寫會產生 H2 違規（W17-072）且與後續 agent 填寫的 Solution 高度重疊（雙寫），造成 ticket 歷史混淆。

**Consequence**：PM 寫入 `## Solution` 的內容若觸發 W17-072 自訂 H2 警告，代理人補寫時又會形成結構衝突，PM 需要額外整理，增加不必要成本。

**Action**：預寫策略使用 `### 實作策略（PM 預寫）` 子節，與 `### Context Bundle` 同為 H3 層級（邏輯上同屬 CB 區段），緊接在 Context Bundle 內容之後，例如：

```markdown
### Context Bundle

**需求摘要**: 修改 X 模組的 Y 邏輯

### 實作策略（PM 預寫）
- 優先修改 A 檔案的 B 函式
- 注意 C 依賴關係，不動 D 介面
```

此結構中，`### 實作策略（PM 預寫）` 在文件標題層次上與 `### Context Bundle` 同級，但內容上屬於 CB 的補充子節，不屬於 `## Solution` 範圍。

### 條款 2：Solution 章節為 agent 專屬，PM 不寫入

`## Solution` 內容由執行 agent 填寫。PM 若需補強 Solution（如記錄派發決策背景），應使用 H3 子節（`### PM 補充`）寄生於既有 `## Solution` 而非建立新 H2。

**Why**：H2 章節由 Schema 定義（`.claude/pm-rules/ticket-body-schema.md`），自訂 H2 會切斷 validator 的 section 擷取範圍（W17-072 規則）。H3 子節在 Schema 章節內自由組織，不受此限制。

**Consequence**：PM 在 `## Solution` 下直接用 `ticket track append-log --section Solution` 寫入 `## 實作策略` 等自訂 H2，觸發 W17-072 警告，agent complete 時 hook 可能誤判章節邊界。

**Action**：PM 確認需補充時，改用 `--section Solution` + 內容以 `### ` 開頭的 H3 子節；或使用條款 1 的 Context Bundle 路徑。

**雙層防護**（W17-208 + W1-068 方案 B）：

| 層級 | 機制 | 行為 |
|------|------|------|
| 寫入層（W17-208 + W1-068） | `append-log` CLI 偵測 Schema 章節內容含 `^## ` | stderr warning 提示違規 + **自動降級 H2 → H3** 規範化（source-level 阻斷） |
| Complete 層（W17-072） | acceptance-gate-hook 偵測非 Schema H2 章節 | stderr warning（不阻擋 complete），最後一道防線涵蓋非 append-log 路徑寫入（如手動 Edit ticket md） |

**Why 雙層**：寫入層攔截最常見的 append-log 路徑（涵蓋多數用例）；complete 層覆蓋手動 Edit ticket md 等不經過 CLI 的旁路（如 PM Edit、IDE 直接編輯、其他腳本批次操作）。單層皆有覆蓋缺口，雙層互補形成完整防護。

> 自 W1-068 起，透過 `append-log` 寫入時用戶仍可寫 `## H2`，但會被自動轉為 `### H3`（W17-072 違規源頭已阻斷）。本條款的「Action」仍為最佳實踐——主動使用 H3 子節更符合 PM 規範意圖。

### 條款 3：PM vs agent Solution 填寫職責邊界

| 角色 | 填寫位置 | 內容類型 |
|------|---------|---------|
| PM（派發前） | `### Context Bundle` 的 H3 子節 | 前置策略、執行指引、背景分析 |
| Agent（執行後） | `## Solution` 的 H3 子節 | 執行結果、決策記錄、產出摘要 |
| PM（驗收後補充） | `## Solution` 的 `### PM 補充` H3 | 驗收決策、後續規劃（限 H3） |

**場景辨識**：「PM 派發前」= ticket 尚未 claim 或 agent 尚未開始執行；「PM 驗收後補充」= agent complete 後 PM 需追記決策背景或後續規劃。遇到此兩情境，對照上表選擇正確填寫位置。

**核心原則**：Context Bundle = PM 派發前情境準備；Solution = agent 執行結果。兩者載體分離，職責不重疊。

**交叉引用**：
- `.claude/rules/core/agent-definition-standard.md`「執行責任：Ticket body 填寫」— agent 填 Solution 的主責定義
- `.claude/pm-rules/ticket-body-schema.md` Solution 章節 — H2/H3 章節結構規則（W17-072）

---

## 禁止行為

| 禁止 | 原因 |
|------|------|
| 只給路徑不給內容 | 代理人還是要花 tool calls 讀檔案 |
| 要求代理人「自行探索」 | 浪費 50%+ tool calls |
| 跳過 Context Bundle 直接派發 | subagent ~20 tool calls 預算，探索就耗盡 |
| 將 context 嵌入 Agent prompt 而非 Ticket | Prompt 是 ephemeral 載體，agent 失敗後 context 不可重用（PC-040） |
| PM 在 `## Solution` 寫入自訂 H2 預寫策略 | 違反 W17-072；與 agent Solution 雙寫重複（W17-206 根因 b+c） |
| PM 用 append-log 寫 `## 實作策略` 等自訂 H2 | W17-208 stderr warning + W1-068 自動降級為 `### 實作策略`（H3 子節）；主動使用 H3 子節更符規範意圖（條款 1/2） |

---

## 與現有規則的關係

- `tdd-flow.md` — 階段轉換時 PM 填寫 Context Bundle 為強制動作
- `decision-tree.md` — 派發前檢查 Context Bundle 是否已填寫
- `two-stage-dispatch.md` — 任務 A 產出寫入 Context Bundle
- `claude-code-platform-limits.md` — 背景約束（~20 tool calls、32K output）

---

**Last Updated**: 2026-05-17
**Version**: 2.4.0 — 新增「PM 預寫策略與 Solution 職責邊界」章節（W17-207）：三條款落地（預寫策略放 CB / Solution agent 專屬 / PM vs agent 職責邊界表）+ 禁止行為補列兩項（W17-206 根因 b+c）

**Version**: 2.3.0 — 新增「Layer 1 自檢」章節（W17-061）：觸發時機表、觸發方式、寫入位置、與 Layer 2 委員的邊界分工

**Version**: 2.2.0 — 新增代理人中間進度更新規範
