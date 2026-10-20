"""bare-commit-guard-hook.py 的輔助套件：staged 範圍判定與阻擋／提醒訊息。

hook 檔本體保留豁免判定與 main 流程；派發範圍判定與進行中操作偵測在
`.claude/lib/dispatch_scope.py`、`.claude/lib/git_operation_state.py`。
"""

import sys
from pathlib import Path

# 套件自行保證 `lib` 可匯入：不假設呼叫端（hook 檔、測試、分派器）已加 sys.path。
_CLAUDE_DIR = str(Path(__file__).parent.parent.parent)
if _CLAUDE_DIR not in sys.path:
    sys.path.insert(0, _CLAUDE_DIR)
