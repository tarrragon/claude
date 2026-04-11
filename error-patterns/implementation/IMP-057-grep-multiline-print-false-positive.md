---
id: IMP-057
title: grep 單行比對多行 print() 語句產生誤報
category: implementation
severity: medium
first_seen: 2026-04-11
ticket: 0.17.4-W2-003
---

# IMP-057: grep 單行比對多行 print() 語句產生誤報

## 症狀

- 使用 `grep -v "file=sys.stderr"` 篩選 bare print() 時，多行 print 語句被誤判為違規
- 掃描報告的違規數量比實際多（本次：grep 報 18 處，AST 驗證為 14 處，3 個 Hook 為誤報）

## 根因

Python 的 `print()` 可以跨行書寫：

```python
# grep 只看到 line 275 有 print(，沒有 file=sys.stderr → 誤判為 bare stdout
print(                          # line 275 ← grep 匹配此行
    "[WARNING] message",        # line 276
    file=sys.stderr,            # line 277 ← 關鍵資訊在另一行
)                               # line 278
```

`grep -v "file=sys.stderr"` 是逐行比對，無法跨行關聯 `print(` 和 `file=sys.stderr`。

## 影響範圍

- 任何需要掃描 Python print() 語句用途的分析任務
- 本次影響：3 個 Hook（post-git-commit-hook, branch-verify-hook, layer-boundary-validator-hook）被誤報為違規

## 解決方案

使用 Python AST 分析代替 grep 進行精確掃描：

```python
import ast

for node in ast.walk(tree):
    if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == "print":
        has_stderr = any(
            kw.arg == "file" and isinstance(kw.value, ast.Attribute) and kw.value.attr == "stderr"
            for kw in node.keywords
        )
        has_json = any(
            isinstance(arg, ast.Call) and isinstance(arg.func, ast.Attribute) and arg.func.attr == "dumps"
            for arg in node.args
        )
        if not has_stderr and not has_json:
            print(f"BARE stdout: {hook}:{node.lineno}")
```

## 防護措施

1. **掃描 Python 語法結構時優先使用 AST**：grep 適合文字搜尋，不適合語法分析
2. **grep 初篩 + AST 精確驗證**：先用 grep 快速縮小範圍，再用 AST 排除誤報
3. **建立子 Ticket 前先驗證數據**：基於 grep 結果建立的 Ticket 應在派發前用 AST 驗證實際數量

## 行為模式

開發者習慣用 grep 做 code scan，對於大多數場景足夠。但 Python 的多行語法（函式呼叫、字典、列表等跨行書寫）讓逐行 grep 失效。這在需要理解「語法結構」而非「文字出現」時特別明顯。
