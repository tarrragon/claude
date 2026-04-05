# PC-018: PM Resume 後未檢查 5W1H 完整性即派發

## 錯誤摘要

PM 從 handoff 恢復任務後，直接進入派發流程，未檢查 Ticket 的 5W1H 欄位完整性。導致 acceptance-auditor 審核 REJECT（why/when/where/how 均為「待定義」），需要回頭補填再重新審核。

## 症狀

- acceptance-auditor 報告多個 5W1H 欄位為「待定義」
- 審核結果 REJECT，需要額外一輪修正+重新審核
- 浪費 2 個代理人的回合（auditor + analyst）

## 根因分析

1. **Resume 流程缺引導**：`/ticket resume` 只載入 context，未提示 PM 檢查 5W1H 完整性
2. **Ticket 建立時留白**：W2 Ticket 在規劃 session 中快速建立，5W1H 大量留為「待定義」
3. **PM 未執行 creation_accepted 前置檢查**：直接進入派發流程

## 觸發條件

- `/ticket resume` 恢復 wave-level handoff
- 恢復的 Ticket 含有未填的 5W1H 欄位
- PM 未在 claim 前檢查 creation_accepted 狀態

## 防護措施

1. **Ticket 建立時強制 why 必填**（根源修復）：`ticket create` 流程必須要求 why 欄位非「待定義」，建立時即填寫完整而非留到 resume 時補救
2. **批量建立時同樣強制**：批量建立 Ticket 的場景（如 Wave 規劃）不可省略 why
3. **Agent 派發 prompt 必須包含 Ticket ID**：格式 `Ticket: {id}`，由 agent-ticket-validation-hook 強制

## 相關 Ticket

- 0.17.2-W2-002, 0.17.2-W2-003（首次發現）

## 發現日期

2026-04-05

---

**Last Updated**: 2026-04-05
**Version**: 1.0.0
