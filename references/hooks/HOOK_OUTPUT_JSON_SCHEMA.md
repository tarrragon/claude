# PostToolUse / PreToolUse Hook 輸出 JSON Schema 檢查清單

> **來源**：IMP-055（PostToolUse Hook stdout 純文字導致 JSON validation failed）+ 2026-04-12 再發（半結構化 JSON 也失敗）
>
> **適用範圍**：所有 `PostToolUse` / `PreToolUse` 事件註冊的 Hook。`SessionStart`、`UserPromptSubmit`、`Stop` 事件不適用本文件。

---

## 核心規範

`PostToolUse` 與 `PreToolUse` 的 **stdout** 必須是以下三種形式之一：

| 型態 | 說明 | 範例 |
|------|------|------|
| 1. 空字串 | 完全不輸出任何 stdout | 直接 `return 0`，不呼叫 `print()` |
| 2. 完整 hookSpecificOutput | 含 `hookEventName` 的 JSON 物件 | 見下方範例 |
| 3. 頂層協議欄位 | 只含 Claude Code 官方協議欄位 | `{"continue": false, "stopReason": "..."}` |

**警告**：所有除錯、提示、錯誤訊息一律寫入 **stderr**，不得污染 stdout。

---

## 最小合法輸出

```python
import json

output = {
    "hookSpecificOutput": {
        "hookEventName": "PostToolUse"  # 或 "PreToolUse"
    }
}
print(json.dumps(output))
```

---

## 附帶 additionalContext（常見情境）

```python
output = {
    "hookSpecificOutput": {
        "hookEventName": "PostToolUse",
        "additionalContext": "記得提交 worktree 的變更"
    }
}
print(json.dumps(output, ensure_ascii=False))
```

---

## PreToolUse 拒絕（permissionDecision）

```python
output = {
    "hookSpecificOutput": {
        "hookEventName": "PreToolUse",
        "permissionDecision": "deny",
        "permissionDecisionReason": "禁止的操作理由"
    }
}
print(json.dumps(output, ensure_ascii=False))
```

---

## 半結構化 JSON 失敗變體（禁止使用）

Claude Code CLI 的 JSON validator 不只檢查「是否為 JSON」，還檢查**欄位結構完整性**。以下皆會觸發 `JSON validation failed`：

| 變體 | 錯誤輸出 | 失敗原因 |
|------|---------|---------|
| 純文字 | `print("msg")` | 非 JSON 根本無法解析 |
| 缺外層包裹 | `{"additionalContext": "msg"}` | `additionalContext` 必須在 `hookSpecificOutput` 內 |
| 缺 hookEventName | `{"hookSpecificOutput": {}}` | `hookSpecificOutput` 必須含 `hookEventName` |
| 缺 hookEventName 但有 context | `{"hookSpecificOutput": {"additionalContext": "msg"}}` | 同上 |
| 未知頂層欄位 | `{"hookSpecificOutput": {...}, "check_result": {...}}` | 頂層僅允許官方協議欄位；自訂欄位請放入 `hookSpecificOutput` 內 |
| hookEventName 不符 | `PostToolUse` hook 輸出 `{"hookSpecificOutput": {"hookEventName": "PreToolUse"}}` | 必須與註冊事件一致 |

### 允許的頂層欄位

| 欄位 | 用途 |
|------|------|
| `continue` | 控制後續 Hook 鏈是否繼續 |
| `stopReason` | 搭配 `continue: false` 說明停止原因 |
| `suppressOutput` | 抑制 tool 輸出顯示 |
| `decision` / `reason` | 舊版決策協議 |
| `systemMessage` | 系統訊息 |
| `hookSpecificOutput` | Hook 特定輸出（推薦主要用此欄位） |

**自訂欄位（例如 log metadata）必須放進 `hookSpecificOutput` 內**，不可放頂層。

---

## 驗證腳本

位於 `.claude/hooks/lib/hook_output_validator.py`，會：

1. 從 `.claude/settings.json` 解析所有 PostToolUse/PreToolUse Hook
2. 以 dummy 輸入執行每個 Hook（`echo JSON | python3 HOOK.py`）
3. 檢查 stdout 符合本規範

### 使用方式

```bash
# 掃描所有已註冊的 PostToolUse/PreToolUse Hook
python3 .claude/hooks/lib/hook_output_validator.py

# 僅驗證單一 Hook（預設視為 PostToolUse）
python3 .claude/hooks/lib/hook_output_validator.py --hook .claude/hooks/my-new-hook.py

# 指定事件類型
python3 .claude/hooks/lib/hook_output_validator.py --hook .claude/hooks/my-new-hook.py --event PreToolUse

# 顯示每個 Hook 的 stdout/stderr 預覽
python3 .claude/hooks/lib/hook_output_validator.py --verbose
```

### 退出碼

| Exit Code | 意義 |
|-----------|------|
| 0 | 所有 Hook 通過驗證 |
| 1 | 至少一個 Hook 失敗（報告末尾列出 FAILED HOOKS） |

---

## 新建 Hook 時的強制檢查清單

開發新 PostToolUse/PreToolUse Hook 時，提交前必須逐項確認：

- [ ] stdout 為空 **或** 輸出完整 `hookSpecificOutput` JSON
- [ ] `hookSpecificOutput.hookEventName` 與 settings.json 註冊的事件一致
- [ ] 除錯/提示/錯誤訊息**一律**寫入 stderr（不污染 stdout）
- [ ] 自訂欄位（metadata、check_result、error 等）放進 `hookSpecificOutput` 內，不放頂層
- [ ] 使用 `hook_utils.run_hook_safely` 包裝 main（crash 時 traceback 寫 stderr）
- [ ] 在 `.claude/settings.json` 註冊 Hook（IMP-051）
- [ ] 權限設定正確（IMP-054）
- [ ] **跑過驗證腳本**：`python3 .claude/hooks/lib/hook_output_validator.py --hook <path> --event <PostToolUse|PreToolUse>`

---

## 相關文件

- `.claude/error-patterns/implementation/IMP-055-hook-stdout-plain-text-breaks-json-validation.md` — 完整錯誤模式（含失敗變體）
- `.claude/error-patterns/implementation/IMP-051-new-hook-registration-check-missed-silent-inactive.md` — Hook 未註冊
- `.claude/error-patterns/implementation/IMP-054-hook-permission-not-granted.md` — Hook 權限問題
- `.claude/hooks/hook_utils.py` — 統一日誌與例外處理工具
- `.claude/hooks/lib/hook_output_validator.py` — 本規範的自動驗證工具

---

**Last Updated**: 2026-04-12
**Version**: 1.0.0 — IMP-055 再發後建立，整合驗證工具與完整檢查清單
