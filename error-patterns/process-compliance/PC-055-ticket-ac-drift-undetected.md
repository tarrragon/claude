---
id: PC-055
title: Ticket AC 與實況漂移未被系統偵測
category: process-compliance
severity: medium
first_seen: 2026-04-12
related_proposals: [PROP-010]
---

# PC-055: Ticket AC 與實況漂移未被系統偵測

## 症狀

- Ticket 建立當下的 Acceptance Criteria（AC）與實際狀態隨時間漂移
- 其他 Ticket 的修復行為外溢達成該 Ticket 的 AC，但 Ticket 狀態仍為 pending
- PM claim Ticket 前如無主動驗證，可能派發代理人「重做已完成工作」

## 典型場景

v0.18.0 觸發案例：

| Ticket | AC | 建立時間 | 實況 | 實際達成者 |
|--------|----|---------|------|-----------|

PM claim 前跑 `npm test` 才發現 AC 已被達成，若無此警覺性，代理人會被派發去重做完成工作。

## 根因

1. **AC 是靜態標記**：Ticket 的 `[ ]` 僅為 frontmatter 字串，無自動驗證機制
2. **修復外溢效應**：一個 Ticket 的修復範圍可能影響其他 Ticket 的 AC 狀態
3. **時間漂移**：Ticket pending 時間越長，漂移機率越高（案例 9 天）
4. **依賴 PM 警覺性**：系統未提醒，PM 可能遺漏檢查

## 影響範圍

- 所有 pending 時間較長的 Ticket（> 7 天）
- 多 Ticket 並行修復時的交叉影響區
- 跨 Wave 的測試 / 驗證類 Ticket（AC 常為「測試通過」、「品質達標」）

## 解決方案

### 短期（修復發生後）

發現 AC 已被外溢達成的 Ticket：
1. `ticket track append-log` 記錄「AC 已由 {上游 Ticket ID} 外溢達成」
2. `ticket track check-acceptance --all` 勾選所有 AC
3. `ticket track complete`（不重新派發）

### 長期（系統性防護）

**PROP-010 Phase 1 MVP**：
- 方案 2：`claim` 前 AC 自動驗證（+ 某 Ticket）
- 方案 4：Ticket 年齡 stale 警告

## 防護措施

### PM 行為層面

在 claim 任何 pending 超過 7 天的 Ticket 前，執行：

```bash
# 檢查 Ticket 建立時間
ticket track query {ticket-id}

# 若 AC 可機器驗證，手動驗證一次
npm test / npm run lint / 其他 AC 對應指令
```

### 系統層面（PROP-010 實作後自動化）

- `claim` 前自動解析 AC，匹配驗證模板執行
- 發現 AC 已達成時提供 y/n/c 三選一（繼續 claim / 取消 / 轉 complete 記錄外溢）
- `query/list` 時對 stale Ticket 標記警告

## 關聯模式

- PROP-009: Ticket CLI 完整性提升（互補，前者處理 create/complete 時點）
- PROP-010: Ticket AC 與實況漂移偵測機制（本模式的系統性解方）
- quality-baseline 規則 5: 所有發現必須追蹤 — 本模式驅動建立 W5 Tickets
- pm-quality-baseline 規則 6: 框架修改優先於專案進度 — PROP-010 立即在 v0.18.0 實作

## 驗收標準

PROP-010 Phase 1 完成後，本模式的自動化防護應滿足：

1. 重現觸發案例 → 系統自動輸出 stale 警告 + AC 已達成提示
2. 新建 Ticket（<= 7 天）claim → 不觸發警告
3. 無可機器驗證 AC 的 Ticket → 跳過驗證不報錯
