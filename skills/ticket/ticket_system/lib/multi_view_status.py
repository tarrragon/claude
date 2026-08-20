"""multi_view_status 欄位覆寫格式驗證。

背景：`.claude/hooks/acceptance_checkers/multi_view_checker.py` 於 ANA Ticket
complete 前檢查 Solution 區段的 `multi_view_status` 欄位，合法值僅
reviewed / skipped / n_a（權威定義 `.claude/config/ana-solution-schema.yaml`）。
該欄位屬自由撰寫章節（Solution），寫入後無法透過 append-log 修正（僅能追加）、
CLI 無編輯指令、Edit 工具因白名單限制被拒——三層疊加使非法值一旦寫入即永久
固定，且不阻擋 complete（gate 僅警告）。本模組供
`commands/track_multi_view_status.py` 使用，讓 CLI 能對既有
`multi_view_status:` 行原地覆寫其值，補上事後修正的合法途徑。

SSOT 邊界（刻意不 import）：合法值域的權威定義在
`.claude/config/ana-solution-schema.yaml`。本模組複製而非動態讀取該 YAML——
與 `lib/exempt_marker.py` 同理由：`.claude/hooks/` 與 `.claude/config/` 路徑
在 subagent 隔離測試環境下不保證存在，複製一份固定清單可讓本模組單獨測試
不依賴專案佈局。兩處清單不同步的最壞情況是 CLI 端誤放行一個 hook 端仍會
擋下的值，使用者仍會在下一個檢查點（acceptance-gate）看到錯誤，不構成安全
性後門。
"""
from __future__ import annotations

import re
from typing import Optional, Tuple

# 與 .claude/config/ana-solution-schema.yaml 的 allowed_values 逐字同步。
ALLOWED_VALUES = frozenset({"reviewed", "skipped", "n_a"})

REASON_MIN_LEN = 10

# 定位既有 `multi_view_status: <value>` 行（與 multi_view_checker.py 的
# _parse_field pattern 同語意：MULTILINE + 大小寫不敏感 + 抓到行尾）。
FIELD_LINE_PATTERN = re.compile(
    r"^(\s*)multi_view_status\s*:\s*.+$", re.MULTILINE | re.IGNORECASE
)


def validate_new_value(value: str) -> Tuple[bool, Optional[str]]:
    """驗證新值是否屬合法值域。

    Returns:
        (is_valid, err_code)。err_code 為 None 時代表通過；否則為
        "value-whitelist"。
    """
    if value not in ALLOWED_VALUES:
        return (False, "value-whitelist")
    return (True, None)


def validate_reason(reason: str) -> Tuple[bool, Optional[str]]:
    """驗證 reason 是否非空且達最小長度。"""
    if not reason or len(reason) < REASON_MIN_LEN:
        return (False, "reason-too-short")
    return (True, None)


def build_field_line(indent: str, value: str) -> str:
    """組出覆寫後的 `multi_view_status: <value>` 行（不含結尾換行）。"""
    return f"{indent}multi_view_status: {value}"
