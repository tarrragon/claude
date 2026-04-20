---
id: IMP-050
title: hook_utils 是 Package 不是檔案，派發時路徑資訊不準確導致代理人回合耗盡
category: implementation
severity: medium
first_seen: 2026-04-07
---

# IMP-050: hook_utils Package 路徑資訊不準確

## 症狀

- 代理人收到 prompt 指示 `from lib.hook_utils import ...`（暗示 `hook_utils.py` 是 `lib/` 下的單一檔案）
- 代理人在 `.claude/hooks/lib/` 目錄找不到 `hook_utils.py`，花費多個 tool call 探索
- 最終回合耗盡，核心任務未開始

## 根因

`hook_utils` 是一個 **Python Package**（目錄），不是單一 `.py` 檔案：

```
.claude/hooks/hook_utils/        # Package 目錄
    __init__.py                  # re-export 入口
    hook_logging.py              # 日誌相關
    hook_io.py                   # I/O 操作
    hook_ticket.py               # Ticket 操作
```

Hook 檔案的 import 方式是：
```python
sys.path.insert(0, str(Path(__file__).parent))  # 加入 hooks/ 目錄
from hook_utils import setup_hook_logging, read_json_from_stdin  # Package import
```

而非 `from lib.hook_utils import ...`。

## 解決方案

派發代理人建立 Hook 時，prompt 中必須提供準確的 import 路徑：

```python
# 正確的 import 模式（hooks/ 目錄下的所有 hook 都這樣用）
sys.path.insert(0, str(Path(__file__).parent))
from hook_utils import setup_hook_logging, run_hook_safely, read_json_from_stdin

# lib/ 下的自訂模組需額外 path
sys.path.insert(0, str(Path(__file__).parent / "lib"))
from dispatch_tracker import record_dispatch
```

## 防護措施

1. **派發前確認 import 路徑**：PM 在撰寫 prompt 前，先 `grep` 一個現有 Hook 的 import 區段作為範例
2. **提供現有 Hook 作為參考**：prompt 中包含 `參考 agent-commit-verification-hook.py 的 import 模式`
3. **避免假設模組路徑**：不要用記憶中的路徑，每次都先確認

## 行為模式

這是「PM prompt 中包含不準確的技術資訊」的一個實例。代理人信任 prompt 中的路徑資訊，當資訊錯誤時會浪費大量回合探索，而非直接質疑 prompt。

## 相關模式

- IMP-047: worktree subagent read-only exhaustion（代理人回合耗盡的另一個原因）
