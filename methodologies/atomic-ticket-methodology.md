# Atomic Ticket 方法論

**版本**: v3.0.0
**核心原則**: 單一職責原則 (Single Responsibility Principle)

> **30 秒核心**：Atomic Ticket = 一個 Action（動詞）+ 一個 Target（單一目標）。是否需要拆分只用「單一職責四大檢查」判斷，禁用時間/行數/檔案數/測試數等量化指標。Ticket 是任務鏈（Task Chain）的節點，責任由子 Ticket 完成履行，非父本身文件完成。

---

## 核心定義

**Atomic Ticket** = 動詞 + 單一目標。三大特徵：

- **單一職責**：只有一個修改原因
- **獨立驗收**：可以獨立完成和驗收
- **不可再拆分**：拆分後會產生循環依賴

---

## 單一職責四大檢查（核心評估方式）

**單一職責是唯一的評估標準**。判斷是否符合單一職責的四個檢查：

| 檢查 | 問題 | 符合 | 違反 |
|------|------|------|------|
| 1. 語義檢查 | 能用「動詞 + 單一目標」表達嗎？ | `實作 startScan() 方法` | `實作掃描功能和離線支援`（兩個目標） |
| 2. 修改原因 | 只有一個原因會導致修改嗎？ | 只有「掃描 API 變更」會影響 | 「掃描 API」「離線格式」兩個修改原因 |
| 3. 驗收一致性 | 所有驗收條件指向同一目標嗎？ | AC 全部關於 `startScan()` | AC 指向 startScan/stopScan/快取多目標 |
| 4. 依賴獨立性 | 拆成兩個是否有循環依賴？ | `B 依賴 A`（單向，應拆） | A 需要 B 的狀態、B 需要 A 的啟動（應合併） |

### 禁止使用的評估方式

以下指標**不能**作為單一職責的判斷依據（這些是結果或實作細節，非職責數量）：

| 指標 | 為什麼不使用 |
|------|-------------|
| 時間（30 分鐘、1 小時） | 時間是結果。單一職責任務可能需 5 分鐘或 2 小時 |
| 程式碼行數（50 行、100 行） | 行數是實作細節。單一職責可能 10 行或 200 行 |
| 檔案數量（2 個、5 個） | 檔案數量是組織方式。單一職責可能跨多檔 |
| 測試數量（5 個、10 個） | 測試數量取決於邊界情況，非職責數量 |

---

## 任務鏈核心哲學

> **核心命題**：Ticket 結構 = 任務鏈（Task Chain）。Ticket 不是孤立任務單位，而是一張可移動的網格，支援責任與 context 在父子、兄弟之間無損傳遞。

### 為什麼採用「任務鏈」視角？

傳統待辦清單把 Ticket 視為獨立項目，完成即勾除。此視角在以下場景失效：

| 場景 | 孤立視角的問題 | 任務鏈視角的處理 |
|------|--------------|----------------|
| 分析型 ANA 建議「後續建立 X」 | 父 ANA 完成 = 分析報告寫完 | 父責任由子 Ticket 的實作/驗證完成驗證 |
| Session 中斷需切換 context | 當前 Ticket context 散落在記憶中 | handoff 檔案 + append-log 持久化 context |
| 發現問題需開分支 Ticket | 新 Ticket 與原任務關聯遺失 | spawned_tickets / relatedTo / blockedBy 維持鏈 |

**任務鏈視角**：責任不止於當前 Ticket 的文件完成，而是鏈上所有節點都到達 completed/closed；context 不止於當前 session 的對話，而是持久化在 Ticket 結構和 handoff 檔案中。

### 結構：三種移動方向

| 方向 | 關係 | 觸發情境 | 範例 |
|------|------|---------|------|
| 上移（子→父） | 子任務完成返回父任務驗收 | 子任務履行父責任的一部分 | 實作完成後回到父 ANA 確認結論落地 |
| 下移（父→子） | 父衍生子任務或切換到既有子任務 | 父被阻塞、父分派責任給子 | ANA Solution 項目拆為 IMP 子 Ticket |
| 水平（兄弟↔兄弟） | 同父下兄弟任務互相協調 | 並行/串行/互補/替代 | 多個 DOC 子任務協同完成一份方法論 |

移動的具體實作：建立關係欄位（parent_id/children/relatedTo/blockedBy）、handoff 命令（--to-parent/--to-child/--to-sibling），以及 chain 欄位自動計算。

### 父子責任傳遞

**核心原則**：父 Ticket 的責任由子 Ticket 的完成來履行，而非父本身的文件完成。

| 概念 | 定義 |
|------|------|
| 父文件完成 | 父 Ticket 的 AC 全部勾選、Problem Analysis 寫完 |
| 父責任履行 | 父的所有衍生子 Ticket（含遞迴孫層）全部 completed 或 closed |

**必然推論**：父 Ticket 的 complete 前置條件包含「所有子 Ticket 已 completed 或 closed」。父不可越過未完成的子任務獨立 complete。

> **執行規則**：父 complete 前置檢查的具體規則和 Hook 實作，見 `.claude/methodologies/ticket-lifecycle-management-methodology.md`「父 complete 前置條件」章節。

### Context 保留機制

任務鏈移動時 context 必須無損傳遞，由三個協同機制保證：

| 機制 | 承載內容 | 生命週期 |
|------|---------|---------|
| handoff 檔案 | 方向 + 前狀態 + 觸發摘要 | Session 間（跨 /clear） |
| append-log 區段 | Problem Analysis / Solution / Test Results | Ticket 生命週期內持久化 |
| chain 欄位 | root / parent / depth / sequence | 結構性恆存，隨 Ticket 檔案 |

三者協同保證：無論 PM 從哪個節點進入，都能重建「鏈在哪」「鏈要去哪」「鏈已走過什麼」的完整 context。

> **實作細節**：handoff 命令用法見 `.claude/skills/ticket/references/handoff-command.md`；append-log 區段定義和 chain 欄位自動計算見下方「子任務建立指引」。

---

## Ticket 關聯追蹤

三個關聯欄位追蹤 Ticket 之間的因果關係：

| 欄位 | 類型 | 說明 | 範例 |
|------|------|------|------|
| `source_ticket` | string | 觸發此 Ticket 的來源 | `{version}-W{n}-{seq}` |
| `spawned_tickets` | array | 此 Ticket 衍生的後續 Tickets | `["{version}-W{n}-{seq1}"]` |
| `dispatch_reason` | string | 派發原因和交接理由 | `UC-01 測試失敗，需修復 ImportService` |

典型關聯鏈（開發-測試-調整）：IMP（`spawned_tickets`）→ TST（`source_ticket` 指回 IMP，測試失敗 `spawned`）→ ADJ（`source_ticket` 指回 TST，`dispatch_reason` 記錄失敗原因）。

> 命令：`uv run ticket track chain {id}` 查詢關聯鏈；`uv run ticket track spawn {id} {new-id} "原因"` 添加衍生。

---

## Ticket ID 命名規範

```text
根任務:   {Version}-W{Wave}-{Seq}
子任務:   {根ID}.{n}[.{n}...]
```

| 部分 | 說明 | 範例 |
|------|------|------|
| Version | 所屬版本號 | `0.15.16` |
| Wave | 執行波次（依賴層級） | `W1`, `W2`, `W3` |
| Seq | 波次內序號（三位數） | `001`, `002`, `015` |
| `.{n}` | 子任務序號（可無限巢狀） | `.1`, `.2`, `.1.1` |

### Wave 依賴定義

- **W1**：無依賴，可並行執行
- **W2**：依賴 W1 的部分 Ticket
- **W3**：依賴 W2 的部分 Ticket（以此類推）

---

## 子任務建立指引

### 何時建立子任務

| 情境 | 範例 |
|------|------|
| TDD 階段任務（Phase 0-4） | 根任務為功能，子任務為各 Phase |
| 問題衍生修復 | 測試失敗產生的修復子任務 |
| 功能細分 | 主功能為根，各獨立元件為子任務 |
| 阻塞處理 | 父被阻塞，產生解除阻塞的子任務 |

### 建立方式與命名規則

```bash
# CLI：建立 {version}-W3-002 的子任務（序號自動分配）
uv run ticket create --version 0.31.0 --wave 3 --parent {version}-W3-002 \
  --action "實作" --target "chain_analyzer.py" --who "thyme-python-developer"
```

- 序號自動分配（取父任務下最大序號 + 1），從 `.1` 開始，支援無限深度（`.1.1`, `.1.1.1`...）。

### chain 欄位自動計算

建立子任務時系統自動計算：root（根任務 ID）、parent（直接父任務 ID）、depth（根=0，每層 +1）、sequence（從根到當前的序號路徑）。

### 兄弟任務關聯模式

> **原則**：同父下兄弟任務**預設平行無依賴**。有依賴關係時，依賴者應下沉一層或重組為聚合父結構。單向時序依賴在嚴格條件下可保留（見「串行兄弟」）。見 error-pattern `ARCH-017: 兄弟任務隱藏依賴`。

| 模式 | 特徵 | 適用場景 |
|------|------|---------|
| 並行 | 兄弟彼此獨立，可同時派發 | 多個不相交功能的實作（推薦） |
| 串行 | 兄弟間有單向時序依賴（顯式 `blockedBy`） | 規格→實作、方法論→Hook 對齊（需滿足 4 條件） |
| 互補 | 兄弟職責互補，合起來完成一個大目標 | 正反測試（正常流程 + 邊界情況） |
| 替代 | 兄弟是不同方案，擇一採用 | A/B 方案並行探索，決策後關閉另一方 |

**串行兄弟合法 4 條件**（須全滿足，否則回歸 ARCH-017 重組）：

1. **單向**：A → B，B 不依賴 A 以外的兄弟
2. **無環**：兄弟依賴形成 DAG
3. **規格→實作時序**：A 為規格/介面/方法論，B 為實作/驗證/Hook（非內容面向並列）
4. **不可深度化**：B 若成為 A 的子會違反內容邊界（如 Hook 不是方法論的子章節）

**違反原則的訊號**：

- 兄弟 A 文件中引用兄弟 B 的產物（如「依 B 完成的規格」）→ B 應為 A 的父或前置（用 `blockedBy`）。注意 `relatedTo` 是純 metadata 弱關聯，不作為結構升格訊號（見 `.claude/skills/ticket/references/field-semantics.md`）。
- 兄弟 A 的 `blockedBy` 含多個兄弟 → 應作為聚合父的最後一個子（或下一 Wave）。
- 執行時必須照特定順序不能並行、但不滿足串行 4 條件 → 依賴關係應升格為父子結構。

### 兄弟-父銜接關係

| 情境 | 處理方式 |
|------|---------|
| 所有兄弟皆 completed/closed | 父可 complete（見 `ticket-lifecycle-management-methodology.md`） |
| 部分兄弟 completed，其餘進行中 | 父**保持 in_progress**，不可 complete |
| 某兄弟執行中發現新需求 | 建立新 spawned ticket，不擴大當前兄弟 scope |
| 某兄弟結論改變父目標 | append-log 記錄到父 Problem Analysis；需重拆則建新 Ticket |

**禁止行為**：父越過未完成兄弟獨立 complete（違反父子責任傳遞）。

### 多層嵌套指南

任務鏈支援無限深度，但深度應反映依賴結構，非任意分層。

| 深度 | 建議 |
|------|------|
| 1 層（根 + 直接子） | 標準情況，多數拆分足以處理 |
| 2 層（含孫層） | 孫層代表「某子任務內部的子任務」，常見於 Phase 拆分 |
| 3 層（含曾孫） | **軟上限**，超過時考慮以 Wave 分離替代 |
| > 3 層 | 反模式，常見於過度拆分，應重新評估粒度 |

**何時建 grandchildren（.1.1.1）**：子任務內部需進一步拆分（與 .1.1 同因果）建直系子（`--parent .1.1`）；執行中發現獨立技術債（無因果）用 spawned（`--source-ticket .1.1`），避免血緣語意混用。**反模式**：將同責任的內部步驟（建構式簽名/邏輯/驗證）拆為 grandchildren，違反 atomic 原則應保持單一 Ticket。

### 聚合父重組範式

當某父最初設計為 5 平行兄弟（.1~.5），但 .2/.3/.5 都引用 .1 的 hub 章節、.4 blockedBy 其他 4 個——違反兄弟無依賴原則。重組為「2 平行兄弟 + 聚合父」：

```text
重組前（反例）：Parent → .1 hub / .2~.5（含 relatedTo/blockedBy 纏繞）
重組後（正例）：Parent
├── .1（聚合父）方法論組
│   ├── .1.1 (hub)
│   └── .1.2 / .1.3 / .1.4（引用 .1.1，彼此不依賴可並行）
└── .2 (Hook, blockedBy .1)
```

要點：兄弟層從 5 個依賴纏繞 → 2 個清晰；.1 聚合父表達內部依賴；.1.2/.1.3/.1.4 符合 Q1 平行兄弟。重組由 `ticket migrate` 執行，需配合 frontmatter 驗證（見 `IMP-061`）。

### 任務拆分決策樹

```text
拆分父任務
  ↓
Q1: 子任務彼此真的獨立（可同時執行）？
  ├─ 是 → 平行兄弟（無 blockedBy）
  └─ 否 → Q2: 依賴是否單向（A 是 hub，被 B/C/... 依賴）？
       ├─ 是 → 將 hub 與被依賴者包為聚合父
       └─ 否 → Q3: 需跨版本序列（Wave 分層）？
            ├─ 是 → 依賴者放下一 Wave，不同時執行
            └─ 否 → 重新檢視：可能同一責任誤拆，應合併
```

**不應拆分的情境**：同一責任的內部步驟（實作 vs 簽名 vs 驗證）、拆分會產生循環依賴、拆分後任一子無法獨立驗收。

---

## 5W1H 驅動的 Ticket 欄位

每個 Ticket 的 YAML 欄位對應 5W1H 問題：

| 5W1H | 欄位 | 說明 |
|------|------|------|
| Who | `who.current` + `who.history` | 當前負責代理人 + Phase 歷史 |
| What | `what` | 任務目標（動詞 + 單一目標） |
| When | `when` | 觸發時機 |
| Where | `where.layer` + `where.files` | 架構層級 + 影響檔案 |
| Why | `why` | 需求依據 |
| How | `how.task_type` + `how.strategy` | Task Type + 實作策略 |

> Ticket YAML frontmatter 完整欄位定義與格式範本見 `.claude/skills/ticket/references/field-semantics.md` 與 `.claude/references/ticket-frontmatter-yaml-rules.md`。

### where.files 撰寫指引：拆分檔案配對

#### 背景：骨架與實質內容的拆分架構

本專案 `.claude/` 規則目錄採「骨架（索引）+ 實質內容（詳版）」雙檔拆分架構（自 W10-076.1 落地）：

- **骨架**（auto-load）：`rules/core/X.md`、`pm-rules/X.md` — 每次 session 自動載入，只含觸發指標、摘要、索引表。
- **實質內容**（按需讀取）：`references/X.md`、`references/X-details.md` — 詳細規則、範例、深度說明。

骨架第一行通常含「完整規則：references/X.md（按需讀取）」明示引用。

**Why**：骨架只是索引——骨架的存在承諾讀者「內容看 references/」，因此擴充規則內容必然牽動 references/，而非骨架本身。忽略此結構會導致 where.files 僅列骨架，但 agent 實際修改 references/ 而產生範圍漂移。

#### 規則 1：列「實質修改會發生的位置」

核心問題：「此 ticket 的修改本質是改變規則『入口索引』還是『規則本身的內容』？」

| 修改類型 | where.files 列法 | 判別問題 |
|---------|-----------------|---------|
| 骨架索引變更（版本號、索引表、導航連結） | 只列骨架路徑 | 「只改入口，不動內容」 |
| 實質內容擴充（新增規則、修改細節） | 列 references/ 實質檔路徑 | 「改的是規則內容本身」 |
| 同步變更（索引更新 + 細節同步） | 兩者都列 | 「入口和內容都要動」 |

**Consequence**：僅列骨架時，agent 必須自裁決定是否延伸到 references/，有範圍漂移風險且缺乏明示記錄。

#### 規則 2：PM 撰寫 where.files 前的拆分偵測

列 where.files 時，若路徑含 `rules/core/` 或 `pm-rules/`，必須檢查是否存在對應的 references/ 拆分配對：

```bash
for path in $(echo "$where_files" | grep -E "(rules/core|pm-rules)/"); do
  basename=$(basename "$path" .md)
  find .claude/references -name "${basename}*.md"
done
```

**本專案已知 10+ 組拆分對**（任何修改這些規則內容的 ticket 都有 where.files 漂移風險）：

| 骨架（auto-load） | 實質內容（按需讀取） | 拆分類型 |
|-----------------|-------------------|---------|
| rules/core/quality-common.md | references/quality-common.md | 同名 |
| rules/core/bash-tool-usage-rules.md | references/bash-tool-usage-details.md | -details |
| pm-rules/askuserquestion-rules.md | references/askuserquestion-scene-details.md | -details |
| pm-rules/decision-tree.md | references/decision-tree-checkpoint-details.md | -details |
| pm-rules/incident-response.md | references/incident-response-details.md | -details |
| pm-rules/parallel-dispatch.md | references/parallel-dispatch-details.md | -details |
| pm-rules/tdd-flow.md | references/tdd-flow-details.md | -details |
| pm-rules/verification-framework.md | references/verification-framework-details.md | -details |
| pm-rules/version-progression.md | references/version-progression-details.md | -details |
| pm-rules/plan-to-ticket-flow.md | references/plan-to-ticket-details.md + references/plan-to-ticket-mapping-details.md | 1-to-many |

> 本規則適用於所有涉及上表拆分對的 ticket，不限於 quality-common。新增規則檔案後應同步維護上表。

#### 規則 3：Agent 延伸 where.files 外檔的行為規範

| 情境 | 允許行為 |
|------|---------|
| 延伸符合 ticket 意圖（規則實質內容落在 references/） | 允許延伸，必須 append-log：「延伸至 X.md，原因：[理由]」 |
| 延伸超出 ticket 意圖（新增無關模組、修改非配對檔） | 禁止延伸，停止並回報 PM |

**預設禁止默默擴展未記錄**。Agent 每次「延伸符合意圖」時，立即在 Solution 寫一行：`延伸至 [path]，原因：[骨架第 N 行明示引用此 references/]`。

> 反例（W10-011）：where.files 僅列骨架 `quality-common.md`，遺漏 `references/quality-common.md`（實質內容在此），agent 須自裁延伸且未記錄，PM 無法追蹤實際修改範圍。正例：修改規則內容時同步列兩者，或僅改細節時只列實質檔。

---

## 與其他方法論的關係

| 方法論 | 關係 |
|--------|------|
| `ticket-design-dispatch-methodology.md` | 派工方法論引用本方法論作為拆分標準（本方法論是 Ticket 設計核心原則） |
| `frontmatter-ticket-tracking-methodology.md` | Atomic Ticket 產生的 YAML Frontmatter 是唯一事實源 |
| `ticket-lifecycle-management-methodology.md` | 每個 Atomic Ticket 遵循相同生命週期：待執行 → 進行中 → Review → 完成 |
| `layered-ticket-methodology.md` | 本方法論管「職責維度」（一 Action + 一 Target），layered 管「層級維度」（一個架構層），互補 |

---

## 檢查清單

### 建立 Ticket 前

- [ ] **語義檢查**：能用「動詞 + 單一目標」表達嗎？
- [ ] **修改原因**：只有一個修改原因嗎？
- [ ] **驗收一致性**：所有驗收條件指向同一目標嗎？
- [ ] **依賴獨立性**：拆分後不會產生循環依賴嗎？

### 常見違反模式

| 模式 | 問題 | 修正 |
|------|------|------|
| 「實作 X 和 Y」 | 兩個目標 | 拆成兩個 Ticket |
| 「修復所有 X 測試」 | 多個測試目標 | 每個測試一個 Ticket |
| 「重構 X 並優化 Y」 | 兩個行動 | 拆成兩個 Ticket |
| 「建立 X 的完整功能」 | 模糊目標 | 明確列出每個功能 |

---

## 參考文件

- [Ticket 設計派工方法論](./ticket-design-dispatch-methodology.md) — 派工決策、5W1H 設計標準
- [Ticket 生命週期管理方法論](./ticket-lifecycle-management-methodology.md) — 生命週期、狀態轉換
- [Frontmatter Ticket 追蹤方法論](./frontmatter-ticket-tracking-methodology.md) — 狀態追蹤機制
- Ticket 服務精神（Will Guidara《Unreasonable Hospitality》：95/5 規則、反饋文化、積極派發）見 `.claude/methodologies/ticket-design-dispatch-methodology.md`「積極派發原則」章節（權威處，避免重複）

---

**版本歷史**：

- v3.0.0：W8-019.2 整併瘦身。保留 30 秒核心（單一職責四大檢查 + 任務鏈哲學 + 子任務建立指引 + where.files 拆分配對 + ID/Wave 命名，皆為外部引用的 load-bearing 章節）；移除 emoji 與冗長 code 範例（符合/違反對照壓為表格），「Ticket 服務精神」「行為分離原則」「拆分範例」「版本驅動任務管理」去重至 ticket-design-dispatch 與 ticket-lifecycle 權威處。歷史 v1.0.0~v2.2.0 完整版見 git log。
