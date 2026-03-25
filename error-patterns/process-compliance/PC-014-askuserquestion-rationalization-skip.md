# PC-014: AskUserQuestion 合理化跳過

---

## 分類資訊

| 項目 | 值 |
|------|------|
| 編號 | PC-014 |
| 類別 | process-compliance |
| 來源版本 | v0.1.0 |
| 發現日期 | 2026-03-17 |
| 風險等級 | 中 |
| 來源 | session 對話中發現 3 次 AskUserQuestion 未觸發 |

### 症狀

1. PM 向用戶提出二元確認問句（「要我先...嗎？」）但使用純文字而非 AskUserQuestion 工具
2. commit 後 Hook 輸出了 AskUserQuestion 提醒，但 PM 以「這不是正式 Ticket 的任務」為由跳過
3. PM 向用戶提出多選問句（「需要 push 嗎？還是先結束 session？」）但使用純文字

### 根本原因（5 Why 分析）

1. Why 1：PM 在 3 個決策點使用了純文字提問而非 AskUserQuestion 工具
2. Why 2：PM 將當前工作歸類為「非正式任務」，認為可以豁免流程
3. Why 3：規則中沒有明確說明「無 Ticket 場景是否適用」，留下合理化空間
4. Why 4：通用觸發原則只存在於規則文件中，非 commit 場景無 Hook 自動提醒
5. Why 5：根本原因：**規則的豁免邊界不明確 + Hook 覆蓋不完整**

### 常見合理化話術

| 話術 | 為何無效 |
|------|---------|
| 「這不是正式 Ticket 的任務」 | 規則 4 明確：無 Ticket 場景仍適用 |
| 「這只是臨時小修正」 | 通用觸發原則不區分任務大小 |
| 「本次不需要記錄錯誤學習」 | PM 不能自行跳過 #16，必須透過 AskUserQuestion 讓用戶選擇 |
| 「流程太重了」 | AskUserQuestion 只是工具選擇，不增加實質工作量 |

### 防護措施

| 措施 | 狀態 | 說明 |
|------|------|------|
| 規則 4：無 Ticket 場景仍適用 | 已實施 | askuserquestion-rules.md v3.5.0 |
| commit-handoff-hook 強化語氣 | 已實施 | 「不可跳過」+ 引用規則 4 |
| 通用觸發原則 Hook 覆蓋 | 未實施 | 技術限制：無法偵測 Claude 純文字輸出中的問句 |

### 教訓

AskUserQuestion 的使用不是流程負擔，而是防止 Hook 誤判用戶回答的安全機制。任何形式的「選擇」（多選或二元確認）都必須透過工具呈現，與任務是否有 Ticket 無關。

---

## 相關文件

- .claude/rules/core/askuserquestion-rules.md - 規則 4（新增）
- .claude/hooks/lib/ask_user_question_reminders.py - 強化 #16 提醒語氣
