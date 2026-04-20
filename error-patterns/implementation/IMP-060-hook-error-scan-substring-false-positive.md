---
id: IMP-060
title: Hook error 掃描純字串匹配產生誤報循環
category: implementation
severity: medium
first_seen: 2026-04-13
---

# IMP-060: Hook error 掃描純字串匹配產生誤報循環

## 症狀

- `agent-commit-verification-hook.py` 於代理人完成時產出「Hook Error 摘要」，誤報多個 Hook 有錯誤記錄
- PM 為診斷誤報而執行 `grep "ERROR\|FAIL\|Exception"` 命令，反而觸發更多誤報（反饋循環）
- 真陽性（如派發被拒）與假陽性（命令字串夾帶關鍵字）混雜，PM 無法區分

## 根因

`scan_hook_errors()` 使用純字串匹配掃描 hook-log：

```python
HOOK_ERROR_KEYWORDS = ("ERROR", "FAIL", "Exception", "Traceback", "TypeError", "NameError")
# ...
for log_file in hook_dir.glob("*.log"):
    content = log_file.read_text(encoding="utf-8", errors="ignore")
    if any(kw in content for kw in HOOK_ERROR_KEYWORDS):
        error_counts[hook_name] = error_counts.get(hook_name, 0) + 1
```

**設計缺陷**：

1. 匹配目標是**整個檔案內容**，不是特定 log level
2. Hook log 格式為 `[timestamp] LEVEL - message`，其中 message 會完整記錄使用者的 Bash 命令字串
3. 使用者命令中夾帶的關鍵字（如 commit message 提到「collection errors 修復」、grep 命令含 `"ERROR\|FAIL"`）被誤判為 Hook 自己的 ERROR

## 實際觸發案例

### 案例 1：commit message 字串夾帶

Commit 訊息：
```
docs: W5-003 Ticket — Hook 測試 collection errors 修復
```

PreToolUse hook 記錄此命令到 log：
```
DEBUG - 命令 '{"command":"git commit -m \"W5-003 Hook 測試 collection errors 修復\"..."}'
```

掃描器看到「errors」（大小寫無關? 實際是 substring match，此例「errors」不含「ERROR」，但「FAILED」出現在其他命令中就會觸發）。

### 案例 2：診斷命令自我觸發

PM 執行 `grep "ERROR\|FAIL\|Exception\|Traceback\|TypeError\|NameError"` 診斷。

handoff-cleanup hook 記錄此命令：
```
DEBUG - 命令非 ticket track complete: grep "ERROR\|FAIL\|Exception\|Traceback\|TypeError\|NameError" ...
```

掃描器看到 6 個關鍵字全部匹配 → 把 handoff-cleanup 誤報為有錯誤。

**反饋循環**：PM 越診斷越多誤報。

## 影響範圍

- 所有代理人背景派發完成後的「Hook Error 摘要」都可能混雜真假陽性
- PM 必須逐一驗證每個誤報，耗費 context 和時間
- 真陽性（如 Hook 程式碼有 Exception、派發被拒）被噪音稀釋，降低預警價值
- 診斷行為本身加劇誤報（self-fulfilling prophecy）

## 解決方案

改用 **log level 精確匹配** 代替整檔字串匹配：

```python
import re

# log 格式：[YYYY-MM-DD HH:MM:SS] LEVEL - message
_ERROR_LEVEL_RE = re.compile(r'\] (ERROR|CRITICAL|FATAL) - ')
_TRACEBACK_RE = re.compile(r'^Traceback \(most recent call last\):', re.MULTILINE)

def _has_hook_error(content: str) -> bool:
    """只在真正的 ERROR level 行或 Traceback 標記出現時判定為 Hook error。"""
    return bool(_ERROR_LEVEL_RE.search(content) or _TRACEBACK_RE.search(content))
```

**取代**：
```python
if any(kw in content for kw in HOOK_ERROR_KEYWORDS):  # 有誤報
```

**改為**：
```python
if _has_hook_error(content):  # 精確
```

## 防護措施

### 檢查規則

| 場景 | 規則 |
|------|------|
| Hook 錯誤掃描 | 必須基於 log level 或結構化標記（如 Traceback 起首） |
| 關鍵字掃描避免誤觸 user 命令 | 排除 DEBUG/INFO/WARNING 行中 message 部分的內容 |
| 自我診斷工具 | 不可依賴同類關鍵字，或至少提供「關鍵字被動觸發」過濾器 |

### 擴充適用範圍

此反模式適用於所有「從 log 檔案做字串計數」的場景，包括但不限於：
- 測試失敗統計（`grep -c "FAILED"` 可能算到 test 名稱本身含 FAILED 的）
- Lint 違規統計（規則名稱含 "error" 字樣可能誤報）
- CI 結果解析

**通用原則**：掃描結構化 log 時，匹配 **log level 欄位** 或 **結構化標記**（如 `[ERROR]`、`Traceback (most recent call last):`），不做整檔 substring match。

## 相關規則

- `.claude/rules/core/quality-baseline.md` 規則 4 — Hook 失敗必須可見（本模式反向：誤報影響可見性的信號價值）
- `.claude/error-patterns/implementation/IMP-048-hook-stderr-triggers-hook-error-display.md` — 類似的 Hook 錯誤顯示誤觸模式

## 修復位置

- 檔案：`.claude/hooks/agent-commit-verification-hook.py:433-476` (scan_hook_errors)
- 關鍵字常數：`HOOK_ERROR_KEYWORDS` (line 113)

---

**Last Updated**: 2026-04-13
**Version**: 1.0.0
