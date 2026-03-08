# DOC-007: append-log 有效區段說明包含 H1 heading 導致 CLI 報錯

## 基本資訊

- **Pattern ID**: DOC-007
- **分類**: 文件設計
- **來源版本**: v0.1.1
- **發現日期**: 2026-03-07
- **風險等級**: 低
- **來源 Ticket**: 0.1.1-W3-002

## 問題描述

### 症狀

執行 `ticket track append-log <id> --section "Execution Log" "內容"` 時，CLI 回傳：

```
[Error] 0.1.1-W3-002 無 'Execution Log' 區段
```

### 根本原因 (5 Why 分析)

1. Why 1: `append-log` 找不到 `"Execution Log"` 區段
2. Why 2: `append-log` 搜尋的是 `## {section}`（H2 標題），不是 `# {section}`（H1 標題）
3. Why 3: Ticket 模板中 `# Execution Log` 是 H1 根標題，其下的 H2 子區段才是有效操作目標
4. Why 4: 執行者參照 SKILL.md 中列出的有效區段值：`Problem Analysis、Solution、Test Results、Execution Log`
5. Why 5（根本原因）：**SKILL.md 錯誤地將 H1 標題 `Execution Log` 列入 `append-log` 的有效區段值**

### Ticket 模板結構

```
# Execution Log          ← H1（根標題，非 append-log 目標）

## Task Summary          ← H2（但不是 append-log 目標）
## Problem Analysis      ← H2（有效 append-log 區段）
## Solution              ← H2（有效 append-log 區段）
## Test Results          ← H2（有效 append-log 區段）
## Completion Info       ← H2（非 append-log 目標）
```

### 實際有效區段值

`append-log` 的有效 `--section` 值只有三個：
- `Problem Analysis`
- `Solution`
- `Test Results`

## 解決方案

**短期**：使用正確的 H2 區段名稱，不使用 `"Execution Log"`

**長期**：更新 SKILL.md 移除 `Execution Log` 或說明其為 H1 根標題：

```
有效區段值（`--section` 參數）：`Problem Analysis`、`Solution`、`Test Results`
注意：`Execution Log` 是 Ticket 的 H1 根標題，不是 append-log 的目標區段。
```

## 預防措施

### append-log 使用前確認

- [ ] 確認目標區段是否為 `Problem Analysis`、`Solution`、`Test Results` 之一
- [ ] 不使用 `Execution Log` 作為 section 名稱

### SKILL.md 待修正

- 位置：`.claude/skills/ticket/SKILL.md`，`append-log` 說明段落
- 修改：移除 `Execution Log` 或加上說明「此為 H1 根標題，非有效 section」

## 後續行動

建立 Ticket 修正 SKILL.md 說明（待排程，優先級 P3）。
