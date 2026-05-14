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
| 輕量（light） | 拼字修正 / 格式調整 / 重命名（純語意調整，無新內容） | 低 |
| 標準（standard） | 單版本影響 / 1-2 UC 變動 / 功能新增但不改架構 | 中 |
| 重量（heavy） | 跨版本（跨 2 個以上大版本） / 跨專案（APP / Extension / CLI 任兩者以上） / framework 類（變更規則或方法論） / 3+ UC 結構性變動 / 架構層級改動 | 高 |

**Light 純語意收斂（W10-099 落地）**：light 從原本「spec 盤點批次建立 / 拼字 / 格式 / 重命名」收斂為「純語意調整」。**Why**：W10-099 重現實驗（11/11 PROP）證實 light 100% 承載 grandfather 妥協（draft 章節未完整），0% 用於設計目的（純拼字）。**Consequence**：未收斂會讓 light 持續成為 draft 探索期的規避手段，PROP 真實強度與 evaluation_level 脫節，promote 時遺漏重評。**Action**：探索期 PROP 改用 `status: draft` 搭配實際強度的 `evaluation_level`（standard/heavy），由 hook 自動豁免章節檢查（豁免優先序 P2，見規則 2.5）；light 只保留純語意調整用例。

> **Deprecation trigger**：light 機制是否完全取消，待 ANA-C（規則精簡 follow-up，源 W10-099）評估後決定，本規則暫保留以維持向後相容。

### 分級強制

PROP frontmatter 必須標示 `evaluation_level: light | standard | heavy`。未標示者視為 standard。

### 豁免判定

以下情況可使用輕量模板或免做完整評估：

| 豁免類型 | 說明 |
|---------|------|
| 拼字修正 | 明顯的錯字 / 標點修正 |
| 格式調整 | Markdown 排版 / 表格對齊 / 無語義變動 |
| 重命名 | 檔名 / 識別符的語意化重命名 |
| Spec 盤點批次 | 從規格反推的盤點清單，建議用「盤點清單 + 候選提案」兩階段分離 |

---

## 規則 2：各級評估要求

不同分級對應不同評估深度。evaluation_level 必須符合下列要求才能從 draft → discussing → confirmed。

### 2.0 Draft 階段豁免（W10-109 新增）

PROP 處於 `status: draft` 階段時，由 hook 自動豁免下列檢查：

| 規則 | 豁免狀態 |
|------|---------|
| 規則 1（evaluation_level 必填且合法） | **不豁免**（draft 仍須標示實際強度，避免促 promote 時遺漏） |
| 規則 2 章節必填（standard / heavy） | **全豁免** |
| 規則 3 Reality Test 章節 | **豁免**（探索期不要求實證） |
| 規則 4 ticket_refs 綁定 | **豁免**（僅對 confirmed/approved 強制） |

**Why**：Draft 屬探索期，章節通常未完整；強制完整章節會阻擋創意 brainstorming，違反 draft 設計目的，並讓提案者改用 light 規避（W10-099 重現實驗證實的 grandfather 模式）。

**Consequence**：未明示 draft 豁免會讓 light 機制持續被誤用為 draft 暫設手段，long-term 治理上 PROP level 與真實強度脫節。

**Action**：探索期 PROP 維持 `status: draft` + 實際強度 `evaluation_level`；準備收斂時改 `status: discussing`，hook 自動切走嚴格路徑（P4），此時補充章節即可通過。

### 2.5 豁免優先序總覽

Hook `proposal-evaluation-gate-hook.py` 依下列優先序判定豁免（高優先序先觸發，低優先序為 fall-through）：

| 優先序 | 觸發條件 | 豁免範圍 | hook 觸發點 |
|-------|---------|---------|------------|
| P1 | Edit/MultiEdit 改動 < 30 字元（MICRO_EDIT_THRESHOLD） | 整檔豁免章節檢查 | `is_micro_edit` 早 return |
| P2 | `status: draft`（任何 level） | 章節檢查 + Reality Test + ticket_refs | `check_prop_content` status=draft 分支 |
| P3 | `evaluation_level: light`（任何 status） | 章節檢查 + Reality Test | `check_prop_content` level=light 分支 |
| P4 | status≠draft 且 level=standard/heavy | 嚴格章節檢查 | fall-through 預設路徑 |

**Why**：多重豁免機制需明示優先序，避免讀者混淆「draft + light」「draft + heavy」「discussing + light」等組合的判定結果。

**Consequence**：未明示優先序會讓 PROP 作者在 promote 時誤判（如「status=discussing + level=heavy 還能豁免嗎？」），導致非預期阻擋或誤通過。

**Action**：撰寫 PROP 時對照本表確認所在優先序層級；promote 跨層級時 hook 自動切換判定路徑，無需手動處理。

**互斥保證**：P1 在 `is_micro_edit` 階段早 return（不進入 `check_prop_content`）；P2/P3 在 `check_prop_content` 內各為獨立分支；P4 是 fall-through 預設路徑。物理上 P2 與 P3 為 OR 關係（兩條獨立早 return path），規則層敘述採 P2 先於 P3 順序對齊「狀態優先於分級」的語意。

### 輕量（light）

| 章節 | 必填 |
|------|------|
| 動機（為何做） | 是 |
| AC（驗收條件） | 是 |
| target_version（單版本） | 是 |
| 替代方案 | 否 |
| 失敗防護 | 否 |
| Reality Test | 否 |

**流程**：PM 自覺 → 建立 PROP → 直接進 confirmed（不須 WRAP）。

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

PROP 模板（`.claude/templates/proposal-template.md` 或 `docs/proposals/README.md` 定義的模板）必須新增以下必填章節。

### Reality Test / 觸發案例實證

| 子章節 | 內容 |
|-------|------|
| 觸發案例 | 引發本提案的具體事件、現象、問題 |
| 假設列舉 | 本提案成立所依賴的假設（明確列為可驗證陳述） |
| 實驗驗證 | 每個假設如何驗證？執行過什麼實驗/觀察？結果是什麼？ |
| 已驗證 vs 未驗證 | 區分「實驗證實的事實」與「尚未驗證的假設」 |

**目的**：讓假設與現況對照顯性化。禁止「我覺得應該會有這個問題」的直覺性提案，必須有具體實證。

### 輕量提案豁免

輕量提案不要求 Reality Test 章節（拼字修正不需實驗）。

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

- Q1：本提案分級為？[light / standard / heavy]
- Q2：若 standard 或 heavy，是否已完成所需評估章節？
- Q3：若 heavy，是否已派發多視角審查？

未選擇 heavy 但實際條件符合 heavy 者，由 AUQ 後設檢查提示 PM 重新分級。

### 第三層：Hook 層（自動化強制，待實作）

- PreToolUse hook 攔截 `docs/proposals/` 的 Write
- 檢查 PROP frontmatter 是否有 `evaluation_level`
- 檢查對應章節是否完備（依分級要求）
- 檢查 confirmed 狀態是否綁 ticket_refs

> **本規則發布時 Hook 尚未實作**，後續由子 Ticket 追蹤並派發 basil-hook-architect 實作。

---

## 檢查清單

### 建立新 PROP 時

- [ ] 已在 frontmatter 標示 `evaluation_level`
- [ ] 文件章節符合分級要求（輕/標/重）
- [ ] 若為 standard / heavy：已執行對應 WRAP 深度
- [ ] 若為 heavy：已派發多視角審查並記錄結果
- [ ] Reality Test 章節已填寫（輕量豁免）

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

**Last Updated**: 2026-05-13
**Version**: 1.1.0 — W10-099 多視角審查仲裁採方案 D 落地（W10-109）：規則 1 light 收斂為純語意（移除 spec 盤點批次 / 拼字 / 格式 / 重命名以外用例，僅保留純語意調整）；規則 2 新增 2.0 Draft 階段豁免（status=draft 自動豁免章節 + Reality Test + ticket_refs）與 2.5 豁免優先序總覽（P1 micro_edit / P2 draft / P3 light / P4 嚴格路徑）；hook check_prop_content 同步新增 P2 分支與測試 13 case
**Version**: 1.0.0 — 初始建立，基於開發流程摩擦力配置倒置結構性問題分析產出
