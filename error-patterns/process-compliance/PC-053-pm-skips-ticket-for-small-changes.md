---
id: PC-053
title: PM 對「小修改」跳過 Ticket 和 error-pattern 記錄
category: process-compliance
severity: medium
first_seen: 2026-04-11
---

# PC-053: PM 對「小修改」跳過 Ticket 和 error-pattern 記錄

## 症狀

- PM 直接修改規則/文件並 commit，未建立 Ticket
- 修改完成後未記錄 error-pattern
- Session 後段（10+ commit 後）流程合規度明顯下降
- 品質檢查清單存在但沒有自動攔截

## 根因

三因素組合：
1. **閾值模糊**：PM 覺得「只是更新幾行」不值得建 Ticket，但累積起來是重大流程變更
2. **流程意識衰退**：Session 越長，PM 對流程的遵守度越低（認知疲勞）
3. **無自動攔截**：品質檢查清單是被動的 checklist，PM 可以跳過

## 解決方案

1. **明確閾值**：任何修改 `.claude/rules/`、`.claude/pm-rules/`、`.claude/skills/` 的內容都需要 Ticket
2. **commit 前 Hook 提醒**：偵測到修改規則/流程檔案但無 in_progress Ticket 時，輸出 WARNING
3. **Session 長度絆腳索**：超過 10 個 commit 後提醒 PM 檢查流程合規度

## 防護措施

1. quality-baseline.md 品質檢查清單新增「修改有對應 Ticket？」
2. 決策樹 command-routing.md 明確規定所有規則修改需要 Ticket
3. 建議：未來考慮 Hook 自動偵測

## 行為模式

PM 把規則/流程修改視為「附帶工作」而非「正式變更」，但這些修改影響所有後續 session 的行為。文件修改和程式碼修改一樣需要追蹤。
