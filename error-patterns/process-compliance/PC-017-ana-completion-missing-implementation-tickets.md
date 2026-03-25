# PC-017: ANA Ticket 完成後未自動建立修復+防護 Ticket

---

## 分類資訊

| 項目 | 值 |
|------|------|
| 編號 | PC-017 |
| 類別 | process-compliance |
| 嚴重度 | 中 |
| 發現版本 | 0.1.1 |
| 發現日期 | 2026-03-20 |
| 來源 | 0.1.1-W15-002 執行過程 |

### 症狀

1. ANA（分析）Ticket 完成後，PM 直接走 Checkpoint 流程（commit → handoff），未依分析結論建立實作 Ticket
2. 用戶提醒後建立修復 Ticket，但只考慮「症狀修復」（搬移檔案），未同時建立「機制防護」Ticket（Hook/代理人定義補強）
3. 用戶二次提醒後才補建防護類 Ticket

### 根因

**行為模式**：PM 將 ANA Ticket 視為獨立閉環任務（分析完 → 記錄結論 → 完成），未認知到分析結論本身就是「建立後續 Ticket」的觸發條件。

**根本原因**：

1. **決策樹缺失**：決策樹第七層（完成判斷）和第八層（完成後路由）未包含「ANA 完成後強制建立實作 Ticket」的步驟
2. **修復思維偏差**：建立修復 Ticket 時，只聚焦於「修復當前錯誤狀態」（症狀），未同時考慮「為什麼會發生」（根因機制防護）
3. **缺乏強制檢查點**：ANA Ticket 的驗收條件未要求「分析結論已轉化為可追蹤的實作 Ticket」

### 解決方案

**立即修正**：

1. ANA Ticket 的標準驗收條件應包含：「分析結論已轉化為修復 Ticket + 防護 Ticket」
2. 決策樹第七層（完成判斷）新增 ANA 類型特殊處理：complete 前檢查是否已建立後續 Ticket

**機制防護建議**：

1. ANA Ticket 驗收條件模板新增強制項：`[ ] 已依分析結論建立修復 Ticket` + `[ ] 已依根因分析建立機制防護 Ticket`
2. acceptance-gate-hook 擴充：ANA 類型 Ticket complete 時，檢查是否有 children 或 spawned_tickets
3. 建立「修復+防護」雙軌建 Ticket 檢查清單，作為所有分析結論的標準轉換流程

### 預防措施

| 措施 | 實施方式 | 追蹤 |
|------|---------|------|
| ANA 驗收條件強制含「後續 Ticket 已建立」 | 修改 ticket create 的 ANA 模板 | 0.1.1-W15-003 |
| 決策樹新增 ANA 完成後建 Ticket 步驟 | 修改 decision-tree.md 第七層 | 0.1.1-W15-003 |
| 「症狀修復 + 根因防護」雙軌思維 | 記入 PM feedback memory | 本記錄 |

### 關聯 Ticket

- 0.1.1-W15-002（觸發本錯誤模式的 ANA Ticket）
- 0.1.1-W15-003（流程改進分析 Ticket）
