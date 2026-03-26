# IMP-003: 重構作用域迴歸

## 基本資訊

- **Pattern ID**: IMP-003
- **分類**: 程式碼實作
- **來源版本**: v0.31.0
- **發現日期**: 2026-02-26
- **風險等級**: 高
- **來源 Ticket**: 0.31.0-W24（M-002 logger 初始化統一）

## 問題描述

### 症狀

Hook 在 Session 啟動時拋出 `NameError: name 'logger' is not defined`，但因 `run_hook_safely` 例外捕捉機制，錯誤被靜默吞掉（`suppressOutput: true`），只在 hook 日誌中可見。

7 個 hooks 受影響，共 41 個函式需要修正。

### 根本原因 (5 Why 分析)

1. Why 1: 函式在呼叫時 `logger` 變數不存在
2. Why 2: `logger` 從模組級（全域）移到了 `main()` 內部（區域）
3. Why 3: W24 M-002 修正要求統一 logger 初始化風格為「main() 內部」
4. Why 4: 執行修正時只移動了 `logger = setup_hook_logging(...)` 的位置，未檢查所有引用該變數的函式
5. Why 5 (根本原因): **重構作用域變更時缺乏「影響範圍分析」步驟** -- 沒有先列出所有引用 `logger` 的函式，再逐一確認每個函式是否能存取新作用域的變數

### 受影響模式

```python
# === 修正前（模組級 logger，全域可見）===
import sys
logger = setup_hook_logging("hook-name")  # 模組級，所有函式可存取

def helper_function():
    logger.info("doing something")  # OK: logger 是全域變數

def main():
    result = helper_function()
    logger.info("main done")

# === 修正後（logger 移入 main，但未更新引用）===
import sys

def helper_function():
    logger.info("doing something")  # BUG: NameError! logger 不在全域也不在參數中

def main():
    logger = setup_hook_logging("hook-name")  # 區域變數
    result = helper_function()  # 呼叫時 helper 找不到 logger
    logger.info("main done")
```

### 靜默失敗的危險

此 bug 特別危險，因為 hook 框架的 `run_hook_safely` 會捕捉所有例外：

```python
# hook_utils.py 中的安全包裝
def run_hook_safely(main_func, hook_name):
    try:
        main_func()
    except (KeyboardInterrupt, SystemExit):
        raise
    except Exception:
        # 例外被捕捉，輸出 suppressOutput: true
        # hook 靜默失敗，用戶不會看到任何錯誤
        print(json.dumps({"suppressOutput": True}))
```

這代表 7 個 hooks 在每次 session 啟動時都靜默失敗，但用戶完全不知道。

## 解決方案

### 正確做法

**Step 1: 影響範圍分析（修改前）**

使用 AST 分析或 grep 列出所有引用目標變數的函式：

```bash
# 找出所有引用 logger 但非 main() 的函式
python3 -c "
import ast, sys
tree = ast.parse(open(sys.argv[1]).read())
for node in ast.walk(tree):
    if isinstance(node, ast.FunctionDef) and node.name != 'main':
        for child in ast.walk(node):
            if isinstance(child, ast.Name) and child.id == 'logger':
                print(f'  {node.name}() references logger')
                break
" hook_file.py
```

**Step 2: 傳遞參數（正確修正）**

```python
def helper_function(logger):  # 加入 logger 參數
    logger.info("doing something")

def main():
    logger = setup_hook_logging("hook-name")
    result = helper_function(logger)  # 傳遞 logger
    logger.info("main done")
```

**Step 3: 驗證（修改後）**

```bash
# AST 驗證：確認所有引用 logger 的函式都接收 logger 作為參數
# 或至少在 main() 內定義（閉包）
```

### 錯誤做法 (避免)

| 錯誤做法 | 問題 |
|---------|------|
| 只移動變數定義位置，不檢查引用 | 產生 NameError |
| 依賴 `py_compile` 驗證 | 只檢查語法，不檢查作用域 |
| 依賴代理人自我報告 | 代理人可能未實際測試執行 |
| 把 logger 改回全域 | 違反統一風格的修正目標 |

### 防護措施

1. **修改作用域時的強制檢查清單**：
   - [ ] 列出所有引用該變數的函式
   - [ ] 每個函式確認：是透過參數接收？還是依賴全域？
   - [ ] 依賴全域的函式必須新增參數
   - [ ] 所有呼叫端必須傳遞新參數

2. **驗證方式**：AST 分析 > 實際執行 > py_compile（語法檢查不足以偵測此類問題）

## 影響統計

| 指標 | 數值 |
|------|------|
| 受影響 hooks | 7 個 |
| 受影響函式 | 41 個 |
| 靜默失敗時間 | 至少 2 次 session（直到手動觸發才發現）|
| 修正行數 | +143 / -81 |

## 相關資源

- `docs/work-logs/v0.31.0/tickets/0.31.0-W24-004.md` - W24 完整決策記錄
- `.claude/rules/core/quality-common.md` - 實作品質標準
- `.claude/hooks/hook_utils.py` - run_hook_safely 實作

## 標籤

`#重構` `#作用域` `#迴歸` `#靜默失敗` `#logger` `#hooks` `#並行派發`
