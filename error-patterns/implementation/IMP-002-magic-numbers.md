# IMP-002: 魔法數字

## 基本資訊

- **Pattern ID**: IMP-002
- **分類**: 程式碼實作
- **來源版本**: v0.28.0
- **發現日期**: 2026-01-19
- **風險等級**: 低

## 問題描述

### 症狀

程式碼中出現無法理解其含義的數字或字串切片：

```python
# 看到 line[9:] 無法理解為什麼是 9
def parse_worktree_line(line: str) -> str:
    if line.startswith("worktree "):
        return line[9:]  # 魔法數字：為什麼是 9？
    return line

# 其他常見的魔法數字
if len(branch) > 50:  # 為什麼是 50？
    raise Error("分支名稱過長")

time.sleep(3)  # 為什麼等 3 秒？
```

### 根本原因 (5 Why 分析)

1. Why 1: 程式碼中出現難以理解的數字 line[9:]
2. Why 2: 開發時知道 "worktree " 長度是 9，直接寫數字
3. Why 3: 快速開發時忽略可讀性
4. Why 4: 沒有程式碼審查機制檢查魔法數字
5. Why 5: **缺乏「自文件化程式碼」的開發習慣和規範**

## 解決方案

### 正確做法

使用具名常數替代魔法數字：

```python
# 方法 1：使用 len() 動態計算
WORKTREE_PREFIX = "worktree "

def parse_worktree_line(line: str) -> str:
    if line.startswith(WORKTREE_PREFIX):
        return line[len(WORKTREE_PREFIX):]
    return line
```

```python
# 方法 2：使用常數定義
WORKTREE_PREFIX = "worktree "
WORKTREE_PREFIX_LEN = len(WORKTREE_PREFIX)  # 9

def parse_worktree_line(line: str) -> str:
    if line.startswith(WORKTREE_PREFIX):
        return line[WORKTREE_PREFIX_LEN:]
    return line
```

```python
# 方法 3：使用 removeprefix（Python 3.9+）
WORKTREE_PREFIX = "worktree "

def parse_worktree_line(line: str) -> str:
    return line.removeprefix(WORKTREE_PREFIX)
```

### 常見魔法數字處理

| 魔法數字 | 正確做法 | 範例 |
|---------|---------|------|
| 字串長度 | 使用 len() | `line[len("prefix "):]` |
| 時間限制 | 定義常數 | `TIMEOUT_SECONDS = 30` |
| 大小限制 | 定義常數並加註解 | `MAX_BRANCH_LENGTH = 50  # Git 建議長度` |
| 重試次數 | 定義常數 | `MAX_RETRIES = 3` |

### 錯誤做法 (避免)

```python
# 錯誤：魔法數字散落各處
if line[9:].startswith("refs/"):
    time.sleep(3)
    for i in range(5):
        if len(result) > 100:
            break
```

### 進階：使用 Enum 管理相關常數

```python
from enum import IntEnum

class Limits(IntEnum):
    MAX_BRANCH_LENGTH = 50
    MAX_COMMIT_MSG_LENGTH = 72
    MAX_RETRIES = 3
    TIMEOUT_SECONDS = 30
```

## 檢測方法

```bash
# 找出可能的魔法數字（數字切片）
grep -rn "\[[0-9]*:\]" .claude/hooks/*.py

# 找出硬編碼的數字
grep -rn "sleep([0-9]" .claude/hooks/*.py
grep -rn "range([0-9]" .claude/hooks/*.py
grep -rn "> [0-9][0-9]" .claude/hooks/*.py
```

## 相關資源

- Commit: 60f1b95 (Hook 系統共用程式庫重構)
- 工作日誌: docs/work-logs/v0.28.0-hook-refactoring.md
- 參考：Clean Code - Robert C. Martin

## 標籤

`#實作` `#程式碼品質` `#可讀性` `#魔法數字` `#Clean Code`
