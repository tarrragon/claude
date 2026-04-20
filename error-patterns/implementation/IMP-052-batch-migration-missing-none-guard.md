---
id: IMP-052
title: 批量遷移後部分 Hook 缺少 None guard
category: implementation
severity: high
first_seen: 2026-04-07
---

# IMP-052: 批量遷移後部分 Hook 缺少 None guard

## 症狀

- 多個 PostToolUse:Bash hook 間歇性顯示 "hook error"
- 錯誤：`AttributeError: 'NoneType' object has no attribute 'get'`
- `read_json_from_stdin()` 回傳 `None` 後直接呼叫 `.get()`

## 根因

某歷史 Ticket 將 27 個 Hook 統一遷移到 `read_json_from_stdin()`，但遷移時未確保所有 Hook 都在呼叫後加入 `if not input_data: return 0` 的 None guard。

4 個受影響的 Hook：
- `worktree-merge-reminder-hook.py`
- `cli-failure-help-reminder-hook.py`
- `skill-cli-error-feedback-hook.py`
- `session-context-guard-hook.py`

## 解決方案

在 `read_json_from_stdin()` 呼叫後，一律加入：
```python
if not input_data:
    return 0  # 或 return EXIT_SUCCESS
```

## 防護措施

1. **批量遷移後全量測試**：遷移完成後用真實 JSON 輸入測試每個修改的 Hook
2. **統一模式檢查**：`grep -l "read_json_from_stdin" *.py` 後確認每個檔案都有 None guard
3. **模板強制**：Hook 模板中 `read_json_from_stdin` 後必須包含 None guard

## 行為模式

批量修改的「長尾效應」——大部分檔案正確修改，但少數遺漏只在特定條件下觸發。單獨測試可能通過（因為 stdin 有資料），但真實環境中 stdin 可能為空或格式不同。
