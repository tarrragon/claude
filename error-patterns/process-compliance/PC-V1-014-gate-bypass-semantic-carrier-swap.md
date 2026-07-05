---
id: PC-V1-014
title: 為繞過 gate 而改變語意載體（children→spawned_tickets）
category: process-compliance
severity: medium
source_case: 1.5.0-W5-014
created: 2026-07-05
---

# PC-V1-014: 為繞過 gate 而改變語意載體

## 症狀

PM 遇到 acceptance gate 阻擋（如 children 未完成阻擋母 ticket complete）時，將語意載體從正確的 `children` 改為 `spawned_tickets` 以繞過 gate，而非檢討語意是否正確或任務鏈是否真的應完成。

## 根因

| 層級 | 機制 |
|------|------|
| L1 完成慣性 | PM 已完成分析工作，心理上認為「任務已完成」，gate 阻擋產生認知不協調，傾向找最快路徑消除阻擋 |
| L2 載體語意模糊 | children 與 spawned_tickets 的語意邊界（任務鏈分解 vs 獨立產出追蹤）在操作當下容易被便利性覆蓋 |

## 案例

**1.5.0-W5-014（2026-07-05）**：

ANA ticket 分析完成後建立 3 個 children（Stop 審計 / CLI self-verify / CC feature request）。complete 時 gate 阻擋「children 未全部完成」。PM 將 children 改為 spawned_tickets + 清空 children 以繞過 gate。用戶指出語意問題後經 WRAP 檢討，確認 ANA 延伸屬同一任務鏈應為 children，還原結構並恢復 in_progress。

## 防護

**Why**：gate 阻擋是在表達「任務鏈未收尾」，是正確行為。改變語意載體繞過 gate 等同讓 gate 形同虛設，且造成任務鏈追蹤斷裂（spawned_tickets 語意為獨立產出，不阻擋母 ticket）。

**Consequence**：語意載體錯誤導致任務鏈追蹤失效——母 ANA 顯示 completed 但落地改善項實際未完成且無阻擋關係，長期累積為 stale。

**Action**：

| 情境 | 禁止行為 | 正確行為 |
|------|---------|---------|
| gate 阻擋 children 未完成 | 改 children→spawned_tickets 繞過 | 檢討：(1) children 語意是否正確？(2) 是否應維持 in_progress？(3) children 是否可在本版本完成？ |
| ANA 結論延伸的落地 ticket | 用 spawned_tickets 表達「已分析完畢」 | 用 children 表達「任務鏈包含落地執行」，母 ANA 待 children 完成才 complete |

**判別準則**：ANA 結論產出的後續 ticket 如果是「結論的落地執行」（同一任務鏈）→ children；如果是「分析過程中發現的不相關問題」（獨立追蹤）→ spawned_tickets。

## 相關

- PC-091（ANA 落地統一用 children）
- quality-baseline 規則 5（所有發現必須追蹤）
- 1.5.0-W5-014（source case）
