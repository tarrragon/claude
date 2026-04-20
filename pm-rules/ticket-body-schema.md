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
| 1.0.0 | 2026-04-20 | 初版（W17-016.2 落地 W17-016.1 盤點結論） |

**Last Updated**: 2026-04-20
**Version**: 1.0.0
