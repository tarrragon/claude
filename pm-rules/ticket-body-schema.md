# Ticket Body Schema（type-aware）

本文件定義不同 Ticket type 在 body 章節的**必填 / 選填 / 免填**對照，作為 PM 派發、代理人填寫、Hook 驗證的唯一依據。

> **來源**：W17-016.1 盤點結論（樣本 ANA × 4 + IMP × 1；DOC 樣本不足，現以保守建議落地）。完整樣本統計見該 ticket Solution 章節。
> **落地時機**：W17-016.2 寫入 template + SKILL.md；W17-016.3 上 Hook 驗證；3 個月後若完整率 < 50% 重啟盤點（樣本 40+）。

---

## Schema 對照表

| Section | ANA | IMP | DOC |
|---------|-----|-----|-----|
| Task Summary | 必填 | 必填 | 必填 |
| Problem Analysis | 必填 | 選填 | 選填 |
| 重現實驗結果（三子節） | 必填（PC-063） | 免填 | 免填 |
| Solution | 必填 | 選填 | 免填 |
| Test Results | 選填（若有實驗） | 必填 | 免填 |
| Completion Info | 必填 | 必填 | 必填（附變更摘要） |

**狀態定義**：

| 狀態 | 語義 | 填寫要求 |
|------|------|---------|
| 必填 | 章節存在且內容非 placeholder | claim/complete 時 Hook 應驗證 |
| 選填 | 章節存在，內容可為 placeholder 或省略 | 有助於後人查閱時填寫 |
| 免填 | 章節可省略或保留空結構 | 不強制檢查，template 可省 |

---

## 各 type 重點說明

### ANA（Analysis）

**核心價值**：根因 / WRAP / ROI 表 / 實驗結果的持久參考價值。

- `Problem Analysis` + `重現實驗結果` + `Solution` 為三大必填，構成「問題→實驗→結論」完整鏈路。
- `Test Results` 僅在有實驗輸出時填寫；樣本顯示 ANA 普遍無獨立測試輸出（4/4 missing），故列選填。

#### Solution 章節：Spawn 落地確認（W17-167 強制）

ANA Solution 章節若含 IMP/DOC/ANA spawn 規劃表格，必須在 complete 前確認以下子節（被 acceptance-gate-hook Step 2.5.2 自動偵測）：

```markdown
### Spawn 落地確認

- [ ] 所有規劃項目已建 ticket（`spawned_tickets` 或 `children` 已記錄對應 ID）
- [ ] 或在本章節顯性標註「無需建 ticket：[具體理由]」
```

**Why**：acceptance 勾選「產出 spawned 清單」只檢文字產出，不檢 ticket 是否實際建立；Solution 寫了表格但未建 ticket = 無 trigger 延後決策（PC-093 模式）。

**Consequence**：缺此 checklist，分析代理人 complete 時 frontmatter 為空也能放行，spawn 規劃靜默丟失（W17-167 元層級反例已證明）。

**Action**：

| 情境 | 填寫方式 |
|------|---------|
| 全部已建 ticket | 勾選第一項，列出對應 ticket ID 清單 |
| 部分未建 | complete 前先補建（PM 接手 ticket create 職責） |
| 評估後不需建 | 勾選第二項，標註「無需建 ticket：[理由]」 |

**交叉引用**：

- 規則層：`.claude/rules/core/quality-baseline.md` 規則 5「ANA Solution 內 spawn 規劃」
- Lifecycle 層：`.claude/pm-rules/ticket-lifecycle.md`「ANA Solution Spawn 規劃落地（強制）」
- 強制層：acceptance-gate-hook Step 2.5.2（W17-168 落地）

### Solution 章節：H3 子標題與表格使用慣例（W10-123 / W10-124 / W10-125 補強）

ANA / IMP Solution 章節支援 H3 子標題組織內容（如「### WRAP 完整分析」「### 修復策略」「### 變更總覽」），並支援 markdown 表格作為主要展示形式。Validator 層級規則：

| 元素 | 規則 |
|------|------|
| `### multi_view_status`（ANA 專用） | 不可作為 H3 子章節；必須以平鋪 `multi_view_status: <reviewed/skipped/n_a>` + `reason: ...` 寫入 Solution 文字內容（schema 來源：`.claude/config/ana-solution-schema.yaml`） |
| `### 自檢結果`（Layer 1） | 可作為 H3 子章節；hook 識別前綴匹配，可含中文括號補充說明（W10-124 修復後） |
| 表格 cell 中的 `N/A` / `TODO` / `TBD` | 屬合法「不適用 / 待辦 / 待定」標示，不視為 placeholder（W10-125 修復後；PC-138 / PC-144） |
| 章節整體只有 placeholder 字面（無表格） | 仍視為 placeholder，阻擋 complete |

**為何 multi_view_status 例外**：hook 用 regex 跨行掃描平鋪 YAML-like 結構，H3 子章節包裝會切斷掃描範圍（PC-117 / W17-111 設計）。

### Type-aware Quality Gate（W10-123 補強）

`ticket-quality-gate-hook` 對不同 ticket type 套用不同檢查：

| Type | c2 incomplete check | c3 ambiguous responsibility check |
|------|-------------------|--------------------------------|
| ANA | 跳過（不適用實作測試路徑要求） | 跳過（不適用 Layer 1-5 分層） |
| DOC | 跳過 | 跳過 |
| IMP | 觸發 | 觸發 |
| 缺 type frontmatter | 觸發（向後相容） | 觸發 |

配置位置：`.claude/hooks/quality_config.yaml` 的 `trigger_conditions.type_excludes`（預設 `["ANA", "DOC"]`）。

### IMP（Implementation）

**核心價值**：commit SHA + 測試輸出 + 實機驗證作為 proof。

- `Test Results` 必填：至少記錄執行指令與通過數（或 commit SHA）。
- `Problem Analysis` / `Solution` 選填：小型 IMP 以 frontmatter how/acceptance 已足；大型 IMP 建議補充決策理由。

### DOC（Documentation）

**核心價值**：變更摘要 + 引用的檔案清單。

- `Completion Info` 必填，需附「變更摘要」（哪些文件 / 章節更新）。
- `Solution` / `Test Results` 免填（文件變更本身即為產出）。
- `Problem Analysis` 選填：若 DOC 起因於某缺陷或盤點結論，可記錄背景。

---

## 與既有規則的關係

| 規則 | 關係 |
|------|------|
| `.claude/pm-rules/ticket-lifecycle.md` | 本 schema 是 lifecycle 各階段填寫粒度的細化 |
| `.claude/error-patterns/process-compliance/PC-063` | ANA「重現實驗結果」強制章節來源，schema 保留此強制 |
| `.claude/rules/core/quality-baseline.md` 規則 5 | 本 schema 不改追蹤原則，只規範 body 顆粒度 |

---

## 歷史豁免

已完成（status=completed）的 ticket 不回頭補章節。schema 只對新建 + in_progress 的 ticket 生效。Hook 驗證（W17-016.3）應以 `status != completed` 為前置條件。

---

## 變更紀錄

| 版本 | 日期 | 變更 |
|------|------|------|
| 1.2.0 | 2026-05-13 | 新增「Solution 章節：H3 子標題與表格使用慣例」+「Type-aware Quality Gate」兩段（W10-123 / W10-124 / W10-125 規則收斂；W10-126 落地） |
| 1.1.0 | 2026-05-08 | ANA Solution 章節新增「Spawn 落地確認」子節 checklist（W17-167 L3 落地，配合 W17-168 hook + W17-169 quality-baseline / ticket-lifecycle 同步修訂） |
| 1.0.0 | 2026-04-20 | 初版（W17-016.2 落地 W17-016.1 盤點結論） |

**Last Updated**: 2026-05-13
**Version**: 1.2.0
