---
id: IMP-055
title: PostToolUse Hook stdout 輸出純文字導致 JSON validation failed
category: implementation
severity: high
first_seen: 2026-04-11
---

# IMP-055: PostToolUse Hook stdout 輸出純文字導致 JSON validation failed

## 症狀

- Claude Code CLI 顯示 `JSON validation failed: Hook JSON output validation failed`
- 代理人執行期間大量觸發此錯誤，消耗回合或干擾工具呼叫
- Hook 日誌顯示 exit 0（看似正常），但 CLI 端報錯

## 根因

PostToolUse Hook 的 stdout 輸出了純文字（`print("message")`），而 Claude Code CLI 期望 PostToolUse/PreToolUse Hook 的 stdout 為 JSON 格式：

```python
# 錯誤：純文字
print(message)

# 正確：JSON 格式
output = {
    "hookSpecificOutput": {
        "hookEventName": "PostToolUse",
        "additionalContext": message
    }
}
print(json.dumps(output, ensure_ascii=False))
```

**注意**：`print(..., file=sys.stderr)` 不影響 JSON validation，只有 stdout 需要 JSON 格式。

## 影響範圍

- 2026-04-11 發現時有 3 個 PostToolUse Hook 使用純文字 stdout
- `worktree-merge-reminder-hook.py`（matcher=Bash）影響最大：每次 Bash 呼叫都觸發
- 2026-04-12 再發（commit bac38ac4）：matcher=Agent 的 2 個 hook JSON 結構不完整
  - `active-dispatch-tracker-hook.py`：有 `json.dumps` 但缺 `hookSpecificOutput` 包裹
  - `agent-dispatch-logger-hook.py`：`DEFAULT_OUTPUT` 缺 `hookEventName` 欄位

## 失敗變體（子模式）

不只「純文字 print」會觸發，以下半結構化 JSON 也會：

| 變體 | 錯誤輸出 | 原因 |
|------|---------|------|
| 純文字 | `print("msg")` | 非 JSON |
| 缺外層包裹 | `{"additionalContext": "msg"}` | 缺 `hookSpecificOutput` 層 |
| 缺 hookEventName | `{"hookSpecificOutput": {}}` | `hookSpecificOutput` 必須含 `hookEventName` |
| 缺 hookEventName 但有 context | `{"hookSpecificOutput": {"additionalContext": "msg"}}` | 同上 |

**正確結構（最小合法輸出）**：

```json
{"hookSpecificOutput": {"hookEventName": "PostToolUse"}}
```

**加上 additionalContext**：

```json
{"hookSpecificOutput": {"hookEventName": "PostToolUse", "additionalContext": "msg"}}
```

## 解決方案

1. 所有 PostToolUse/PreToolUse Hook 的 stdout 輸出改為 JSON 格式
2. 無內容要輸出時不印任何 stdout（直接 return 0）
3. 警告/錯誤訊息寫入 `stderr` 不受影響

## 防護措施

1. **新建 Hook 檢查清單**：stdout 必須是 JSON 格式（hookSpecificOutput）或無輸出
2. **區分 stdout vs stderr**：提醒內容用 JSON stdout，除錯訊息用 stderr
3. **與 IMP-051/IMP-054 聯動**：新建 Hook 三件套 — 註冊（IMP-051）+ 權限（IMP-054）+ JSON 輸出（IMP-055）

## 行為模式

Hook 開發者習慣用 `print()` 輸出提醒，但 Claude Code CLI 的 Hook 系統有特定的 JSON 協議。這在 SessionStart Hook 中不會出問題（SessionStart 的 stdout 直接作為 additionalContext），但 PreToolUse/PostToolUse 需要 JSON 封裝。
