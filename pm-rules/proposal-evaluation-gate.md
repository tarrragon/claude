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
| 輕量（light） | spec 盤點批次建立 / 拼字修正 / 格式調整 / 重命名 | 低 |
| 標準（standard） | 單版本影響 / 1-2 UC 變動 / 功能新增但不改架構 | 中 |
| 重量（heavy） | 跨版本（跨 2 個以上大版本） / 跨專案（APP / Extension / CLI 任兩者以上） / framework 類（變更規則或方法論） / 3+ UC 結構性變動 / 架構層級改動 | 高 |

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

**Last Updated**: 2026-04-14
**Version**: 1.0.0 — 初始建立，基於開發流程摩擦力配置倒置結構性問題分析產出
