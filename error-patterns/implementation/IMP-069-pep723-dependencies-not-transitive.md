---
id: IMP-069
title: PEP 723 inline dependencies 不會從 library 模組傳遞至 entry hook
category: implementation
severity: high
status: active
created: 2026-04-30
related:
- IMP-003
---

# IMP-069: PEP 723 inline dependencies 不會從 library 模組傳遞至 entry hook

## 問題描述

PEP 723 inline script metadata（`# /// script` ... `# dependencies = [...]` ... `# ///`）只在 **uv 直接執行的入口檔**上生效。當 entry hook 透過 `import` 引入 library 模組（如 `lib/frontmatter_parser.py`），library 的 PEP 723 metadata 是裝飾性的、**不會被 uv 採用為依賴宣告**。

結果：library 自己 `import yaml` 沒問題（如果單獨跑），但被 entry hook import 時，hook 的 PEP 723 environment 缺 `pyyaml`，觸發 `ModuleNotFoundError`。

### 具體觸發案例

`process-skip-guard-hook.py`（Hook 入口）：

```python
#!/usr/bin/env -S uv run --quiet --script
# /// script
# requires-python = ">=3.11"
# dependencies = []          # ← 缺 pyyaml
# ///
from lib.frontmatter_parser import parse_frontmatter   # ← 傳遞引入 yaml
```

`lib/frontmatter_parser.py`（被引入的 library）：

```python
#!/usr/bin/env -S uv run
# /// script
# requires-python = ">=3.10"
# dependencies = ["pyyaml>=6.0"]   # ← 此處宣告對 hook 無效
# ///
import yaml
```

執行時 stderr：

```
ModuleNotFoundError: No module named 'yaml'
  File "/.../hooks/process-skip-guard-hook.py", line 45
  File "/.../hooks/lib/frontmatter_parser.py", line 28
```

### 影響範圍

- Hook **每次 UserPromptSubmit 都失敗**（non-blocking exit 1）
- 用戶看到 stderr "Failed with non-blocking status code: Traceback ..."
- Hook 業務邏輯（流程省略偵測）整段 **靜默失效**——這比直接報錯更嚴重，因為功能看似存在實際無作用
- 觸發 commit：`2d64dc5f` (2026-03-26) sync 自外部 claude.git framework 時引入

## 根本原因

**PEP 723 是腳本級設定，非套件級**：uv 讀取的是 `sys.argv[0]` 或 `--script` 指定檔的 metadata，不會遞迴掃描所有 import。Library 模組的 metadata 只在被當 entry 直接執行時才有意義。

## 防護措施

### 規則

| 場景 | 必要動作 |
|------|---------|
| Hook entry 引入任何 lib/ 模組 | 必須將 lib 的 PEP 723 dependencies 全部複製到 hook entry |
| 新增 lib 模組依賴 | 必須掃描所有引用此 lib 的 entry hook 同步補充 |
| Sync 框架更新涉及 hooks/lib/ | 必須驗證每個 entry hook 的 dependencies 完整性 |

### 偵測方式

```bash
# 找出所有引用 frontmatter_parser 的 hook
grep -l "frontmatter_parser" .claude/hooks/*.py | while read f; do
  deps=$(sed -n 's/^# dependencies = //p' "$f" | head -1)
  echo "$f: $deps" | grep -v yaml && echo "  ⚠ 缺 pyyaml"
done
```

### 自動化建議

未來考慮建立 hook 啟動測試（`.claude/hooks/__health_check__.py`），對每個 hook 跑空 input，檢查 stderr 無 `ModuleNotFoundError`。在 sync-pull/sync-push 後自動執行。

## 相關 Pattern

- **IMP-003**：7 個 hooks 靜默失敗——同型「hook 失效但用戶看不見」問題；本案的 stderr 雖可見但 LLM 容易忽略「non-blocking」訊息
- **規則 4**（quality-baseline.md）：Hook 失敗必須對用戶可見——本案 stderr 已輸出但被 non-blocking 標記模糊化

## 修復案例

```diff
- # dependencies = []
+ # dependencies = ["pyyaml"]
```

驗證：

```bash
echo '{"prompt":"test","cwd":"/path"}' | .claude/hooks/process-skip-guard-hook.py
# 預期：輸出合法 JSON，不見 Traceback
```
