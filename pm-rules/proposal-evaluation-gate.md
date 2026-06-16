# 提案評估強制機制

本文件定義 Proposal（提案）在進入開發流程前的強制評估機制，防止錯誤假設蔓延到後續所有 Phase。

> **理論依據**：摩擦力管理方法論「開發流程階段的摩擦力曲線」——Proposal 屬前期決策點，摩擦力必須高。錯誤提案假設會在所有 Phase 放大，修復成本隨階段指數上升。

---

## 適用範圍

| 對象 | 適用 |
|------|------|
| `docs/proposals/` 下新增 PROP 文件 | 是 |
| 修改既有 PROP 狀態為 confirmed/approved | 是 |
| 修改 PROP 的 target_version（跨版本變更） | 是 |
| 拼字修正 / 格式調整 / 重命名 | 否（豁免） |
| 規格文件（docs/spec/）變更 | 否（另循 Phase 1 流程） |

---

## 規則 1：提案分級

所有 PROP 必須分級後才能接受（accepted）或 confirmed。分級決定評估要求強度。

### 分級判定表

| 分級 | 判定條件（滿足任一） | 評估摩擦力 |
|------|-------------------|----------|
| 標準（standard） | 單版本影響 / 1-2 UC 變動 / 功能新增但不改架構 | 中 |
| 重量（heavy） | 跨版本（跨 2 個以上大版本） / 跨專案（APP / Extension / CLI 任兩者以上） / framework 類（變更規則或方法論） / 3+ UC 結構性變動 / 架構層級改動 | 高 |

**二分制**：evaluation_level 只有 standard / heavy 兩個合法值；探索期 PROP 改用 `status: draft` 搭配實際強度的 `evaluation_level`，hook 自動豁免章節檢查（豁免優先序 P2，見規則 2.5）。**Why**：W3-002 ANA 結論（W10-099 收斂後）11 個 PROP 樣本中 light 真實使用 = 0，屬 PC-093 yagni-deferred 候選。**Action**：存量 PROP 若標有 `evaluation_level: light`，hook 將視為非法值阻擋寫入，需改為 standard 或 heavy（light 已於 2026-05-30 移除）。

### 分級強制

PROP frontmatter 必須標示 `evaluation_level: standard | heavy`。未標示者視為違規（hook 阻擋）。

### 豁免判定

以下情況免做完整評估（hook 微調豁免，見規則 2.5 P1）：

| 豁免類型 | 說明 |
|---------|------|
| 拼字修正 | 明顯的錯字 / 標點修正（Edit 差異 < 30 字元） |
| 格式調整 | Markdown 排版 / 表格對齊 / 無語義變動（Edit 差異 < 30 字元） |
| 重命名 | 檔名 / 識別符的語意化重命名（Edit 差異 < 30 字元） |

---

## 規則 2：各級評估要求

不同分級對應不同評估深度。evaluation_level 必須符合下列要求才能從 draft → discussing → confirmed。

### 2.-1 章節檢查觸發時機：升級閘門，非維護閘門（W2-025）

章節完備度檢查屬「**升級閘門**」——只在 PROP 的 `status` 由非 confirmed/approved（draft / discussing / 空 / 新建檔）**升級轉換**為 confirmed/approved 的當下觸發，**不在每次編輯時觸發**。

| 編輯前 status | 編輯後 status | 章節檢查 |
|--------------|--------------|---------|
| draft / discussing / 空 / 新建檔 | confirmed / approved | **觸發**（缺章節阻擋） |
| confirmed / approved | confirmed / approved（維護編輯） | **豁免** |
| confirmed / approved | discussing / withdrawn（降級） | 豁免 |
| 任意 | draft | 豁免（P2 draft 豁免優先） |

**Why**：章節完備度是「進入 confirmed/approved 的一次性把關」，而非對既已 confirmed 的 PROP 每次維護都重掃。對 confirmed PROP「每次編輯」都掃整檔章節，會凍結 pre-existing 缺章節的 confirmed PROP——連改一段執行策略（如 §7）都被擋（W2-024 §7 修訂被擋實證）。

**Consequence**：若把升級閘門誤實作為維護閘門，所有早於本機制建立、章節不齊的 confirmed PROP（如 PROP-007）將完全無法維護，違反「本規則對既有 PROP 不追溯」（見文末漸進落地）。

**Action**：維護既有 confirmed PROP 時可自由編輯，hook 不掃章節；準備將 draft/discussing PROP 升級為 confirmed/approved 時，hook 在升級當下檢查章節完備度，此時補齊章節即可通過。**新建檔若直接寫入 confirmed/approved**（無前態）視為升級，仍須通過章節檢查。

**與微調豁免的互動**：一行 `status` flip（字元差異 < 30）雖屬微調體量，但若構成升級轉換則**不套用** P1 微調豁免——升級是語意重大變更，升級閘門優先於微調豁免。

### 2.0 Draft 階段豁免（W10-109 新增）

PROP 處於 `status: draft` 階段時，由 hook 自動豁免下列檢查：

| 規則 | 豁免狀態 |
|------|---------|
| 規則 1（evaluation_level 必填且合法） | **不豁免**（draft 仍須標示實際強度，避免促 promote 時遺漏） |
| 規則 2 章節必填（standard / heavy） | **全豁免** |
| 規則 3 Reality Test 章節 | **豁免**（探索期不要求實證） |
| 規則 4 ticket_refs 綁定 | **豁免**（僅對 confirmed/approved 強制） |

**Why**：Draft 屬探索期，章節通常未完整；強制完整章節會阻擋創意 brainstorming，違反 draft 設計目的，並讓提案者改用 light 規避（W10-099 重現實驗證實的 grandfather 模式）。

**Consequence**：未明示 draft 豁免會讓提案者以不正確的 level（如把 heavy 改標 standard 以通過章節檢查）繞過強制機制，long-term 治理上 PROP level 與真實強度脫節。

**Action**：探索期 PROP 維持 `status: draft` + 實際強度 `evaluation_level`；準備收斂時改 `status: discussing`，hook 自動切走嚴格路徑（P4），此時補充章節即可通過。

### 2.5 豁免優先序總覽

Hook `proposal-evaluation-gate-hook.py` 依下列優先序判定豁免（高優先序先觸發，低優先序為 fall-through）：

| 優先序 | 觸發條件 | 豁免範圍 | hook 觸發點 |
|-------|---------|---------|------------|
| P1 | Edit/MultiEdit 改動 < 30 字元（MICRO_EDIT_THRESHOLD）**且非升級轉換** | 整檔豁免章節檢查 | `is_micro_edit` 且 `not is_prop_upgrade` 早 return |
| P2 | `status: draft`（任何 level） | 章節檢查 + Reality Test + ticket_refs | `check_prop_content` status=draft 分支 |
| P3 | 非升級轉換（編輯後 status 非 confirmed/approved，或維護 confirmed→confirmed） | 章節檢查 | `is_upgrade_transition` 為 False 早 return |
| P4 | 升級轉換（非 confirmed/approved → confirmed/approved，含新建檔直接 confirmed） | 嚴格章節檢查 | fall-through 預設路徑 |

**Why**：多重豁免機制需明示優先序，避免讀者混淆「draft + heavy」「confirmed 維護編輯」等組合的判定結果。章節檢查屬升級閘門（見規則 2.-1），P3 對非升級編輯豁免，P4 僅在升級當下嚴格檢查。

**Consequence**：未明示優先序會讓 PROP 作者在 promote 時誤判（如「confirmed 維護編輯還會掃章節嗎？」），導致非預期阻擋（凍結 confirmed PROP）或誤通過。

**Action**：撰寫 PROP 時對照本表確認所在優先序層級；promote（升級）時 hook 自動切走 P4 嚴格路徑，此時補章節即可通過；維護既有 confirmed PROP 落在 P3 豁免。

**互斥保證**：P1 在 `is_micro_edit` 且非升級時早 return；P2 在 `check_prop_content` 內為獨立 draft 分支早 return；P3 在 `is_upgrade_transition` 為 False 時早 return；P4 是 fall-through 嚴格路徑。**升級轉換優先於 P1 微調豁免**——一行 status flip 雖小但屬升級，仍走 P4。

### 標準（standard）

| 章節 | 必填 |
|------|------|
| 動機（為何做） | 是 |
| AC（驗收條件） | 是 |
| 替代方案（至少 2 個候選） | 是 |
| 失敗防護（至少 1 個失敗情境 + 對應防護） | 是 |
| Reality Test / 觸發案例實證 | 是 |
| 機會成本 | 是 |

**流程**：PM 執行簡化 WRAP（W/A/P 三問） → PROP 文件涵蓋上表章節 → 進 discussing。

### 重量（heavy）

| 章節 | 必填 |
|------|------|
| 動機（為何做） | 是 |
| AC（驗收條件） | 是 |
| 替代方案（至少 3 個候選 + 逐一評估表） | 是 |
| 失敗防護（至少 3 個失敗情境 + 對應防護） | 是 |
| Reality Test / 觸發案例實證（必須在本專案端獨立執行，不可只引用其他專案） | 是 |
| 機會成本 | 是 |
| 多視角審查記錄 | 是 |
| 分階段實施計畫 | 是（若跨 2+ 大版本） |

**流程**：PM 執行完整 WRAP 四階段 → 派發多視角審查（至少 linux + 1 領域視角） → PROP 文件涵蓋上表章節 → 進 discussing。

---

## 規則 3：PROP 模板必填「Reality Test」章節

PROP 模板（`.claude/skills/doc/templates/proposal-template.md` 或 `docs/proposals/README.md` 定義的模板）必須新增以下必填章節。

### Reality Test / 觸發案例實證

| 子章節 | 內容 |
|-------|------|
| 觸發案例 | 引發本提案的具體事件、現象、問題 |
| 假設列舉 | 本提案成立所依賴的假設（明確列為可驗證陳述） |
| 實驗驗證 | 每個假設如何驗證？執行過什麼實驗/觀察？結果是什麼？ |
| 已驗證 vs 未驗證 | 區分「實驗證實的事實」與「尚未驗證的假設」 |

**目的**：讓假設與現況對照顯性化。禁止「我覺得應該會有這個問題」的直覺性提案，必須有具體實證。

### 微調豁免

Edit/MultiEdit 改動 < 30 字元（MICRO_EDIT_THRESHOLD）的拼字修正 / 格式調整類寫入，不要求 Reality Test 章節（hook P1 豁免）。

---

## 規則 4：狀態流轉與實作 Ticket 綁定

PROP 狀態從 confirmed/approved 起，必須綁定至少 1 個實作 ticket（在 `ticket_refs` 欄位）。

### 狀態規則

| 狀態 | ticket_refs 要求 |
|------|----------------|
| draft | 不要求 |
| discussing | 不要求 |
| confirmed | 至少 1 個實作 ticket（非純分析 ticket） |
| approved | 至少 1 個實作 ticket |
| implemented | 對應的 ticket 全部 completed |
| withdrawn | 不要求（但應有退回說明） |

### 違規處理

confirmed / approved 狀態但 ticket_refs 為空者：

- 提案應**回退為 discussing**，或
- **補建實作 ticket** 並寫入 ticket_refs

### 分析 ticket vs 實作 ticket 區分

- 分析 ticket（type: ANA）：僅完成需求分析，不算落地實作
- 實作 ticket（type: IMP / DOC 規則文件）：能產出實際變更者

僅有 ANA ticket 的 PROP 不符合本規則，必須補 IMP ticket。

---

## 規則 5：強制機制三層組合

本規則透過三層協同強制落地，依優先度排序：

### 第一層：規則層（本文件）

- 位置：`.claude/pm-rules/proposal-evaluation-gate.md`（本檔）
- 強制力：PM 自覺 + 規則引用
- 適用：PM 建立或修改 PROP 時查閱並遵守

### 第二層：AUQ 層（PM 建 PROP 時引導）

PM 建立 PROP 時，使用 AskUserQuestion 引導分級和評估強度：

- Q1：本提案分級為？[standard / heavy]
- Q2：若 standard 或 heavy，是否已完成所需評估章節？
- Q3：若 heavy，是否已派發多視角審查？

未選擇 heavy 但實際條件符合 heavy 者，由 AUQ 後設檢查提示 PM 重新分級。

### 第三層：Hook 層（自動化強制，待實作）

- PreToolUse hook 攔截 `docs/proposals/` 的 Write
- 檢查 PROP frontmatter 是否有 `evaluation_level`
- 檢查對應章節是否完備（依分級要求）
- 檢查 confirmed 狀態是否綁 ticket_refs

---

## 檢查清單

### 建立新 PROP 時

- [ ] 已在 frontmatter 標示 `evaluation_level`
- [ ] 文件章節符合分級要求（standard/heavy）
- [ ] 已執行對應 WRAP 深度（standard: 簡化 WRAP；heavy: 完整 WRAP）
- [ ] 若為 heavy：已派發多視角審查並記錄結果
- [ ] Reality Test 章節已填寫（微調豁免：Edit < 30 字元；draft 豁免：status=draft）

### 修改 PROP 狀態為 confirmed / approved 時

- [ ] 已綁定至少 1 個實作 ticket（ticket_refs 非空）
- [ ] 實作 ticket 類型為 IMP / DOC，非僅 ANA
- [ ] 若跨版本：已確認本專案端獨立 Reality Test 存在

### 跨版本 / 跨專案 PROP

- [ ] 本專案端獨立 Reality Test 已執行（不可只引用他專案）
- [ ] 跨版本的分階段實施計畫已明示
- [ ] 失敗防護涵蓋「跨專案同步失敗」情境

---

## 與既有規則的關係

| 相關規則 | 關聯 |
|---------|------|
| `.claude/methodologies/friction-management-methodology.md` 「開發流程階段的摩擦力曲線」 | 本規則為 Proposal 階段摩擦力配置的具體落地 |
| `.claude/skills/wrap-decision/SKILL.md` | 評估時執行的 WRAP 框架工具（通用原理） |
| `.claude/skills/wrap-decision/references/project-integration/` | 本專案 WRAP 整合層（觸發條件、案例、pm-rules 索引） |
| `.claude/pm-rules/decision-tree.md` | 決策樹路由本規則 |
| `.claude/rules/core/quality-baseline.md` 規則 5「所有發現必須追蹤」 | Reality Test 發現的問題須建 Ticket 追蹤 |

---

## 本規則的漸進落地

本規則自公布日起對**新建 PROP** 強制，**既有 PROP**（建立於公布日之前者）不追溯。

既有 PROP 若需升級分級或補充章節，由持續管理逐一處理，不列為違規。

---

**Last Updated**: 2026-06-14
**Version**: 1.3.0 — W2-025 修正章節檢查觸發時機：新增規則 2.-1「升級閘門，非維護閘門」（章節檢查僅在 status 由非 confirmed/approved 升級為 confirmed/approved 時觸發；confirmed→confirmed 維護編輯豁免；新建檔直接 confirmed/approved 視為升級）；規則 2.5 豁免優先序表更新為 P1 微調（非升級）/P2 draft/P3 非升級豁免/P4 升級嚴格檢查，並明示「升級轉換優先於微調豁免」。背景：W2-024 §7 修訂被舊 hook（每次編輯掃章節）阻擋，凍結 pre-existing 缺章節的 confirmed PROP-007
**Version**: 1.2.0 — W3-093 移除 light evaluation_level enum（W3-002 ANA 結論落地）：evaluation_level 收斂為 standard/heavy 二分制；規則 1 分級判定表移除 light 列；規則 2.5 豁免優先序移除 P3 light 列（原 P4 嚴格路徑升為 P3）；規則 3 輕量提案豁免改為微調豁免（< 30 字元）；hook 同步移除 VALID_LEVELS light + level=light 早 return 分支
**Version**: 1.1.0 — W10-099 多視角審查仲裁採方案 D 落地（W10-109）：規則 1 light 收斂為純語意；規則 2 新增 2.0 Draft 階段豁免與 2.5 豁免優先序總覽（P1 micro_edit / P2 draft / P3 light / P4 嚴格路徑）；hook check_prop_content 同步新增 P2 分支與測試 13 case
**Version**: 1.0.0 — 初始建立，基於開發流程摩擦力配置倒置結構性問題分析產出
