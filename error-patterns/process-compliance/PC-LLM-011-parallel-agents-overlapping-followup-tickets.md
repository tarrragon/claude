---
id: PC-LLM-011
title: 並行代理人建立重疊的後續 Ticket
category: process-compliance
severity: medium
status: active
created: 2026-03-21
---

# PC-LLM-011: 並行代理人建立重疊的後續 Ticket

> **來源**：本檔於 v3.4.0 依 canonical issue #63 從 git 歷史復原。曾用編號：某 consumer 的 `PC-018-parallel-agents-overlapping-followup-tickets`（與 canonical PC-018 撞號）；canonical 於 v1.49.1 改認 `PC-183-parallel-agents-overlapping-followup-tickets`。該檔在 2026-06 一次未宣告的 sync-push `--clean` 中被刪除（推送方從未擁有此檔）。flat 號屬凍結核心，復原改用前綴號。仍保有 `PC-183-parallel-...` 副本的 consumer，可刪除該副本改用本檔。

## 基本資訊

| 項目 | 值 |
|------|-----|
| 分類 | process-compliance |
| 來源版本 | 3.4.0 |
| 風險等級 | 中 |
| 首次觀察 | 2026-03-21 |

## 症狀

- 並行派發的代理人各自完成分析後，獨立建立後續修正 Ticket
- 不同代理人建立的 Ticket 解決同一個問題但範圍不同（一個聚焦特定 agent，一個覆蓋所有 agent）
- PM 彙整時發現多個 Ticket 的工作已被其他 Ticket 覆蓋，需關閉為重複

## 根因分析

### 行為模式

並行代理人無法感知彼此的產出物。當一張 ANA Ticket 分析完成後建立子 Ticket（補強某 agent 的職責聲明、補強 skip-gate 標註），與同時執行的 ADJ Ticket（已為 skip-gate 加標註、已為所有 agent 加聲明）產生重疊。

### 具體案例

| 重疊 Ticket | 被覆蓋的 Ticket | 原因 |
|-------------|----------------|------|
| ANA 子票：單一 agent 職責聲明 | ADJ 票：所有 agent 職責聲明 | ADJ 票範圍更廣，已包含該 agent |
| ANA 子票：skip-gate applies_to | ADJ 票：skip-gate 角色標註 | ADJ 票已完成相同工作 |

### 結構性原因

1. 並行代理人各自獨立產出，無法查詢其他代理人的產出
2. ANA Ticket 的「建立後續修正 Ticket」驗收條件鼓勵代理人積極建立子 Ticket
3. PM 未在派發前明確告知「ADJ 票已在處理相同範圍，ANA 的子 Ticket 應聚焦差異」

## 解決方案

### 事後處理

關閉重疊 Ticket 為重複，在 Solution 中標記由哪張 Ticket 覆蓋。

### 預防措施

| 措施 | 說明 |
|------|------|
| **派發時明確範圍邊界** | PM 派發並行 ANA + ADJ 時，在 prompt 中明確告知各自負責範圍，避免後續 Ticket 重疊 |
| **ANA 建立子 Ticket 前查詢** | ANA 代理人建立後續 Ticket 前，應先查詢同 Wave 是否已有相同目標的 Ticket |
| **PM 彙整時檢查重疊** | 並行代理人全部完成後，PM 在 commit 前檢查新建 Ticket 是否有重疊 |

## 防護建議

在 parallel-dispatch.md 的「代理人回報原則」章節新增提醒：

> 並行派發含 ANA + ADJ/IMP 的混合任務組時，PM 應在各代理人 prompt 中標記其他代理人的修改範圍，防止 ANA 的後續 Ticket 與 ADJ/IMP 的直接修改重疊。

## 相關文件

- .claude/pm-rules/parallel-dispatch.md - 並行派發指南
- .claude/pm-rules/plan-to-ticket-flow.md - 執行中額外發現規則
