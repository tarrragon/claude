# IMP-001: 重複程式碼散落各處

## 基本資訊

- **Pattern ID**: IMP-001
- **分類**: 程式碼實作
- **來源版本**: v0.28.0
- **發現日期**: 2026-01-19
- **風險等級**: 中

## 問題描述

### 症狀

相同功能在多個檔案中重複實作：

```python
# hooks/pre_commit.py
def run_git_command(cmd):
    result = subprocess.run(cmd, capture_output=True, text=True)
    return result.stdout.strip()

# hooks/post_merge.py
def run_git_command(cmd):
    result = subprocess.run(cmd, capture_output=True, text=True)
    return result.stdout.strip()

# hooks/branch_check.py
def run_git_command(cmd):
    result = subprocess.run(cmd, capture_output=True, text=True)
    return result.stdout.strip()

# hooks/worktree_guardian.py
def run_git_command(cmd):
    result = subprocess.run(cmd, capture_output=True, text=True)
    return result.stdout.strip()
```

### 根本原因 (5 Why 分析)

1. Why 1: 相同的 run_git_command 函式在 4 個檔案中重複
2. Why 2: 每個 Hook 獨立開發，沒有共用模組
3. Why 3: 缺乏 Hook 系統的架構設計和共用程式庫規劃
4. Why 4: 快速開發時複製貼上最快
5. Why 5: **缺乏 DRY (Don't Repeat Yourself) 原則的強制檢查機制**

## 解決方案

### 正確做法

建立共用程式庫，集中管理通用功能：

```python
# lib/git_utils.py
import subprocess
from typing import List, Optional

def run_git_command(cmd: List[str], cwd: Optional[str] = None) -> str:
    """執行 Git 命令並返回輸出。

    Args:
        cmd: Git 命令列表
        cwd: 工作目錄（可選）

    Returns:
        命令輸出（已去除首尾空白）
    """
    result = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        cwd=cwd
    )
    return result.stdout.strip()
```

```python
# hooks/pre_commit.py
from lib.git_utils import run_git_command

def check_branch():
    current_branch = run_git_command(["git", "branch", "--show-current"])
    # 使用共用函式
```

### 共用程式庫組織

```
.claude/lib/
├── __init__.py
├── git_utils.py      # Git 操作
├── file_utils.py     # 檔案處理
├── config_loader.py  # 配置載入
└── output_utils.py   # 輸出格式化
```

### 識別重複程式碼

```bash
# 找出重複的函式定義
grep -rh "^def " .claude/hooks/*.py | sort | uniq -c | sort -rn | head -20

# 找出相似的程式碼區塊
# 使用 PMD CPD 或類似工具
```

### 錯誤做法 (避免)

```python
# 錯誤：每個檔案都有自己的版本
# hooks/file1.py
def parse_worktree_output(line):
    return line[9:]

# hooks/file2.py
def parse_worktree_output(line):
    return line[9:]

# hooks/file3.py
def parse_worktree_output(line):
    return line[9:]
```

## 重構步驟

1. **識別**: 找出重複的程式碼區塊
2. **抽取**: 將重複程式碼提取到共用模組
3. **替換**: 更新所有使用處改為引用共用模組
4. **測試**: 確保功能不變
5. **文件**: 記錄共用 API

## 檢測方法

```bash
# 列出所有函式定義
grep -rh "^def " .claude/hooks/*.py | sort | uniq -c | sort -rn

# 找出可能的重複（出現超過 1 次的函式名）
grep -rh "^def " .claude/hooks/*.py | sort | uniq -d
```

## 相關資源

- Commit: 60f1b95 (Hook 系統共用程式庫重構)
- 工作日誌: docs/work-logs/v0.28.0-hook-refactoring.md
- 建立的共用模組: .claude/lib/

## 標籤

`#實作` `#DRY原則` `#程式碼品質` `#重複程式碼` `#重構`
