---
id: PC-V1-011
title: PM claim 待派發 ticket 導致代理人認領失敗
severity: low
category: process-compliance
first_seen: 2026-06-22
source_ticket: 1.2.0-W2-007
---

# PC-V1-011: PM claim 待派發 ticket 導致代理人認領失敗

## 症狀

代理人派發後回報「ticket 已被接手」無法 claim。PM 需手動 release 再通知代理人重試，浪費 2-3 個 tool call 回合。

## 根因

PM 在寫 Context Bundle 前習慣性執行 `ticket track claim --as rosemary-project-manager`，將 ticket 狀態從 pending 改為 in_progress。後續派發代理人時，代理人 `claim --as <agent>` 被 status precondition 拒絕（ticket 已被 PM 持有）。

## 觸發條件

PM claim ticket → PM append-log 寫 Context Bundle → PM 派發代理人 → 代理人 claim 失敗。

## 為何不需要 claim

`append-log --section "Problem Analysis"` 和 `--section "Context Bundle"` 對 pending 狀態已豁免 status precondition（W1-058 派發前章節例外）。PM 寫 Context Bundle 不需要先 claim。

## 正確流程 vs 反模式

| 步驟 | 正確流程 | 反模式 |
|------|---------|--------|
| 1 | `ticket create`（pending） | `ticket create`（pending） |
| 2 | `append-log --section "Problem Analysis"`（pending 直寫） | `claim --as PM`（多餘，佔住 ticket） |
| 3 | `Agent(prompt="Ticket: ...")`（派發） | `append-log`（此時已 in_progress） |
| 4 | 代理人 `claim --as agent`（成功） | `Agent(...)`（派發） |
| 5 | — | 代理人 `claim` 失敗 |

## 規則

PM 派發代理人執行的 ticket，禁止 PM 先 claim。PM 自行執行的 ticket（ANA 分析等）才 claim。

## 防護

- 規則層：pm-role.md「派發 agent 前」流程已含 append-log Context Bundle 步驟，不含 claim
- 記憶層：feedback memory 記錄此模式

## 相關

- W1-058：append-log 派發前章節 pending 直寫豁免
- PC-040：Context Bundle 必須寫入 ticket 非 prompt
- pm-role.md：派發前流程
