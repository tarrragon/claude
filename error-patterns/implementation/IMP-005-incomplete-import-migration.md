# IMP-005: 模組遷移後 Import 路徑未同步更新

## 基本資訊

- **Pattern ID**: IMP-005
- **分類**: 程式碼實作
- **來源版本**: v0.31.0
- **發現日期**: 2026-02-26
- **風險等級**: 高
- **來源 Ticket**: 0.31.0-W25-007（修復 Hook Import 路徑）

## 問題描述

### 症狀

Hook 在 Session 啟動時出現 `ModuleNotFoundError`，Claude Code 顯示 "hook error" 但無法看到具體錯誤來源。每次 session 啟動出現 3 個 SessionStart hook error + 多個 PreToolUse/PostToolUse hook error。

5 個 hooks 受影響，涵蓋 SessionStart、PostToolUse、UserPromptSubmit 三種事件類型。

### 根本原因 (5 Why 分析)

1. Why 1: Hook 在 import 階段拋出 `ModuleNotFoundError`
2. Why 2: `from common_functions import ...` 找不到模組
3. Why 3: `common_functions.py` 已從 `.claude/hooks/` 遷移至 `.claude/hooks/lib/`
4. Why 4: W22 重構執行遷移時，只更新了部分 hook 的 import 路徑
5. Why 5 (根本原因): **模組遷移後缺乏「全量引用更新」步驟** -- 沒有搜尋所有 `from common_functions import` 的使用處，逐一確認每個引用者都已更新

### 受影響模式

```python
# === 遷移前（模組在同一目錄）===
sys.path.insert(0, str(Path(__file__).parent))
from common_functions import hook_output  # OK: 同目錄下可找到

# === 遷移後（模組移到 lib/ 子目錄，但 import 未更新）===
sys.path.insert(0, str(Path(__file__).parent))
from common_functions import hook_output  # FAIL: ModuleNotFoundError

# === 正確的遷移後 import ===
sys.path.insert(0, str(Path(__file__).parent))
from lib.common_functions import hook_output  # OK: 使用 lib. 前綴
```

### 可偵測性

| 偵測方式 | 可偵測 | 說明 |
|---------|--------|------|
| `uv run python hook.py < /dev/null` | 是 | 直接觸發 ModuleNotFoundError |
| `grep -r "from common_functions" .claude/hooks/*.py` | 是 | 找出所有未遷移的引用 |
| py_compile | 否 | 只檢查語法，不檢查 import 解析 |
| dart analyze | 不適用 | Python 檔案不受 Dart 分析影響 |

## 防護措施

### 遷移時強制檢查清單

執行模組遷移（移動 .py 檔案位置）前必須完成：

| 步驟 | 動作 | 驗證方式 |
|------|------|---------|
| 1 | `grep -r "from {module} import"` 列出所有引用者 | 確認完整清單 |
| 2 | `grep -r "import {module}"` 列出所有直接 import | 確認完整清單 |
| 3 | 逐一更新每個引用者的 import 路徑 | 修改每個檔案 |
| 4 | 逐一執行 `uv run python {file} < /dev/null` | 確認無 ImportError |

### Import 防護機制

所有 hook 入口處應包裹 try-except，確保 import 失敗時顯示具體原因：

```python
try:
    from hook_utils import setup_hook_logging
    from lib.common_functions import hook_output
except ImportError as e:
    print(f"[Hook Import Error] {Path(__file__).name}: {e}", file=sys.stderr)
    sys.exit(1)
```

**效果**：即使 import 失敗，stderr 會顯示 `[Hook Import Error] hook-name.py: No module named 'common_functions'`，而非只有 "hook error"。

### 與 IMP-003 的關係

IMP-003（作用域迴歸）和 IMP-005（import 遷移不完整）都屬於**重構引用更新不完整**的變體：

| Pattern | 重構類型 | 遺漏 | 偵測盲點 |
|---------|---------|------|---------|
| IMP-003 | 變數作用域變更 | 引用該變數的函式未更新 | py_compile 不偵測 |
| IMP-005 | 模組路徑遷移 | 引用該模組的檔案未更新 | py_compile 不偵測 |

**共通防護原則**：任何重構都需要先 `grep` 列出所有引用，再逐一更新，最後逐一驗證。

## 修復紀錄

### 第二次（2026-03-02）：sys.path 遺漏 .claude/lib/

- **症狀**: 每次使用 Agent 工具都出現 `PreToolUse:Agent hook error`（4 個 error 對應 2 次 Agent 呼叫）
- **根因**: `task-dispatch-readiness-check.py` 的 sys.path 只有 `.claude/hooks/`，缺少 `.claude/lib/`，導致 `from hook_io import` 失敗
- **背景**: v0.28.0 將 `hook_io.py` 遷移至 `.claude/lib/`，`branch-verify-hook.py` 和 `version-release-guard-hook.py` 有加 lib 路徑，但 `task-dispatch-readiness-check.py` 遺漏。W24 統一 sys.path 風格重構也未補上
- **延遲發現原因**: 與 IMP-006 案例 C（hookify plugin timeout 10ms）的 error 疊加，移除 hookify 後以為修好，實際只消除了其中一個來源
- **修復方式**: 新增 `sys.path.insert(0, str(Path(__file__).parent.parent / "lib"))`
- **受影響檔案**: task-dispatch-readiness-check.py

**教訓**：
1. 統一重構（如 W24 sys.path 標準化）應先 `grep` 全量 import，比對 sys.path 是否完整覆蓋所有需要的路徑
2. 多源 hook error 修復後，應逐一驗證每個 hook 是否正常，不能依賴 error 數量變化判斷

### 第一次（2026-02-26）：import 路徑未同步更新

- **W25-007**: 修復 5 個 hook 的 import 路徑 + 加入 import 防護
- **修復方式**: `from common_functions import` 改為 `from lib.common_functions import`
- **受影響檔案**: hook-health-monitor.py, lsp-environment-check.py, branch-status-reminder.py, pre-fix-evaluation-hook.py, parallel-suggestion-hook.py
- **防護新增**: 5 個 hook 加入 try-except import 防護

---

**Last Updated**: 2026-03-02
**Version**: 1.1.0 - 新增第二次發生案例（sys.path 遺漏 .claude/lib/）
