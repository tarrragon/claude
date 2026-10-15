"""session 狀態檔的鍵：取自 hook 輸入的 session_id。

為何不用父程序 pid：runtime 以 uv run 啟動 hook，hook 的父程序是當次的
uv 程序，每次呼叫都不同（實測確認），ppid 鍵使同 session 內的狀態每次歸零
或讀寫對不上。Claude Code 交給每個 hook 的輸入都帶 session_id，同一 session
內固定不變。

失敗語意（fail-open）：取不到 session_id 時不退回 ppid（它本身不穩定），
回傳 None，由呼叫端略過該次狀態讀寫；本模組負責記 warning 並寫 stderr。
狀態類 hook 皆為提醒型（exit 0），略過狀態只會少一次提醒，不會擋下操作。
"""

import re
import sys
from pathlib import Path
from typing import Any, Dict, Optional

# 檔名只允許這些字元；其餘（路徑分隔符、空白、..）一律換成底線，防路徑穿越
_UNSAFE_CHARS = re.compile(r"[^A-Za-z0-9_-]")
_MAX_KEY_LENGTH = 128


def session_state_key(input_data: Optional[Dict[str, Any]], logger=None) -> Optional[str]:
    """由 hook 輸入取出可安全用於檔名的 session 鍵；取不到回傳 None。"""
    raw = input_data.get("session_id") if isinstance(input_data, dict) else None
    if not isinstance(raw, str) or not raw.strip():
        message = "hook 輸入缺少 session_id，略過 session 狀態讀寫（不退回 ppid）"
        if logger is not None:
            logger.warning(message)
        sys.stderr.write("[session_state_key] %s\n" % message)
        return None
    return _UNSAFE_CHARS.sub("_", raw.strip())[:_MAX_KEY_LENGTH]


def session_state_path(
    template: str, input_data: Optional[Dict[str, Any]], logger=None
) -> Optional[Path]:
    """以 {session_id} 佔位符展開狀態檔路徑；取不到 session_id 回傳 None。"""
    key = session_state_key(input_data, logger)
    if key is None:
        return None
    return Path(template.format(session_id=key))
