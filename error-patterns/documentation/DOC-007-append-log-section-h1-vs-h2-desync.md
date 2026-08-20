---
id: DOC-007
title: append-log 有效區段說明包含 H1 heading 導致 CLI 報錯
category: documentation
severity: low
created: 2026-03-07
---
# DOC-007: append-log 有效區段說明包含 H1 heading 導致 CLI 報錯

## 基本資訊

- **Pattern ID**: DOC-007
- **分類**: 文件設計
- **來源版本**: v0.1.1
- **發現日期**: 2026-03-07
- **風險等級**: 低

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

### Ticket 模板結構（2026-03 記錄當時；現況見下方「現況」節）

```
# Execution Log          ← H1（根標題，非 append-log 目標）

## Task Summary          ← H2（但不是 append-log 目標）
## Problem Analysis      ← H2（有效 append-log 區段）
## Solution              ← H2（有效 append-log 區段）
## Test Results          ← H2（有效 append-log 區段）
## Completion Info       ← H2（非 append-log 目標）
```

### 實際有效區段值（2026-03 記錄當時）

當時的有效 `--section` 值只有三個：`Problem Analysis`、`Solution`、`Test Results`。

此清單已過期。現行有效值為 `constants.py` 的 `CANONICAL_BODY_SECTIONS` 全 10 章（含當時標為「非 append-log 目標」的 `Task Summary` 與 `Completion Info`），見下方「現況」節。

## 現況（2026-08-18 結案）

`Execution Log` 已明確定義為**不受 append-log 支援**。承載它的 `APPEND_LOG_EXTRA_SECTIONS` 常數一併刪除——該擴充點歷史上唯一一次被使用就是本案的缺陷，留著等於在不該打開的門上掛警告牌；日後真有非 Schema 章節需求時加回是一行。白名單現直接等於 `CANONICAL_BODY_SECTIONS`，與 `SCHEMA_H2_SECTIONS` 完全等價。`--section "Execution Log"` 現在於白名單階段即回 `[Error] 無效的 section: Execution Log`（exit 1），並列出全部合法值。

### 為何選擇移除而非修好

**判準**：一個功能若同時滿足「加進白名單後從未可用」與「其不可用未被任何使用者察覺」，其存在價值須重新論證後才修，不預設修好。論證的舉證責任在主張保留的一方，需指出至少一個現行無替代路徑的具體用途；舉不出即移除。

兩條件只成立其一時不適用本判準，改依下表處置：

| 情況 | 處置 |
|---|---|
| 從未可用，但有使用者回報需要 | 修好。有需求即有價值，不可用只是缺陷 |
| 可用但無人使用 | 不急於移除。可用功能的移除是破壞性變更，成本高於留著 |
| 兩者皆成立 | 套用上述判準：舉證保留，否則移除 |

本案兩條件皆成立。事實依據：`"Execution Log"` 曾被加進 `APPEND_LOG_EXTRA_SECTIONS`，`track_acceptance.py` 亦寫了專屬的時間戳列表格式化，但存在性檢查呼叫 `find_section` 時未覆寫 `levels`（預設只匹配 H2），對 H1 的 `# Execution Log` 恆判定為缺失並提前 `return 1`，格式化邏輯成為到不了的死碼。五個月間未見任何一次成功寫入紀錄，亦無缺少此功能的回報——後者是弱證據（無回報不等於無需求），故不單獨作為移除依據。真正的支撐是強證據：其唯一已知用途（PM 派發前寫 Context Bundle）已由正式的 `Context Bundle` H2 章節承接，移除後無功能缺口。

### 已同步的下游描述

| 位置 | 修正 |
|---|---|
| `constants.py` | 刪除 `APPEND_LOG_EXTRA_SECTIONS` 常數，白名單改直接取 `CANONICAL_BODY_SECTIONS` |
| `track_acceptance.py` | 刪除專屬格式化死碼、三處 `section != "Execution Log"` 分支，以及白名單等價後恆為假的 `section_missing` 判定 |
| `command_tracking_messages.py` `ARG_SECTION` | 改自 `CANONICAL_BODY_SECTIONS` 衍生（原手寫枚舉同時漏列三個合法章節、列出一個失效章節） |
| `skills/ticket/SKILL.md` | 有效區段值改為 10 章正典，明示 Execution Log 不受支援 |
| `references/track-command.md`（2 處） | 移除 Execution Log |
| `pm-rules/context-bundle-spec.md` / `two-stage-dispatch.md` | 寫法改 `--section "Context Bundle"` |
| `pm-rules/dispatch-gate.md` | 檢查項改指 `## Context Bundle` 章節 |

## 預防措施

### 說明側與程式側同源

**觸發時機**：撰寫或修改任何「列出合法值」的說明字串時（CLI help、docstring 的有效值清單、文件的列舉表）。

列合法值的說明字串應自該清單的權威常數衍生，不手寫。手寫清單會與程式接受的值各自漂移，且漂移是雙向的——本次修正時 `ARG_SECTION` 同時列出一個已失效的值，也漏列 `Task Summary` / `Spawn Requests` / `Completion Info` 三個合法值，後者五個月無人察覺。

### 白名單新增條目時的驗證要求

**觸發時機**：往任何「合法值白名單」加入新條目時。

必須實際執行一次該值的完整寫入路徑，不可只確認清單改了。本案的死碼正是靜態閱讀看起來完整、實際執行才發現到不了。

**可稽核產物**：把該次執行的原始輸出（含 exit code）貼進 ticket 的 Test Results 章節。缺此產物時，「我執行過了」與「我以為我執行過了」無法區分。
