# 驗證 Hook 實作規範

本文件包含驗證框架 Hook 系統的實作細節和參考規範。

> 主文件：@.claude/rules/core/verification-framework.md

---

## 入口層驗證 Hook (W2-001)

**檔案**：`.claude/hooks/command-entrance-gate-hook.py`

**功能**：驗證開發命令時是否有對應的待認領 Ticket

**執行時機**：UserPromptSubmit（用戶輸入時）

**檢查邏輯**：
1. 判斷是否為開發命令
2. 如果是，檢查是否有 pending/in_progress Ticket
3. 輸出警告或允許繼續

**輸出格式範例**：
```json
{
  "hookSpecificOutput": {
    "hookEventName": "UserPromptSubmit",
    "additionalContext": "警告訊息（如有）"
  },
  "check_result": {
    "is_development_command": bool,
    "has_ticket": bool,
    "ticket_id": string,
    "should_block": bool,
    "timestamp": "ISO8601"
  }
}
```

**關鍵實作要點**：
- 識別開發命令關鍵字（實作、建立、修復等）
- 搜尋 .claude/tickets/ 和 docs/work-logs/*/tickets/
- 檢查 frontmatter 中的 status 欄位

---

## 完成層驗證 Hook (W2-004)

**檔案**：`.claude/hooks/phase-completion-gate-hook.py`

**功能**：驗證 Phase 完成時是否有完整的工作日誌記錄

**執行時機**：PostToolUse（Write/Edit 工具執行後）

**檢查邏輯**：
1. 判斷是否為 worklog 寫入操作
2. 識別是否為 Phase 完成報告
3. 檢查 worklog 結構完整性
4. 輸出警告或確認

**必檢查的 worklog 部分**：
- Problem Analysis：問題分析
- Solution：解決方案
- Test Results：測試結果

**輸出格式範例**：
```json
{
  "hookSpecificOutput": {
    "hookEventName": "PostToolUse",
    "additionalContext": "警告訊息（如有）"
  }
}
```

**關鍵實作要點**：
- 檢查 Phase 完成標記（Phase 3b、Phase 4 等）
- 驗證必需的 markdown 部分存在
- 檢查部分中是否有實際內容（非 TODO）

---

## 未來擴展：階段轉換驗證

**計畫中的 Hook**：驗證階段轉換時是否滿足前置條件

**執行時機**：Ticket 狀態從 in_progress 變更為 completed 時

**檢查邏輯**：
1. 識別當前階段和目標階段
2. 驗證目標階段的前置條件
3. 確認可以安全轉換

---

**Last Updated**: 2026-02-06
**Version**: 1.0.0
