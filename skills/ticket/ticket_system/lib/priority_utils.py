"""票清單優先級聚合工具。

Public API:
    highest_priority(tickets) -> Optional[str]
        回傳票清單中最高（數字最小）priority；無有效 priority 時回傳 None。

背景：`commands/track_topics.py`（主題摘要）與 `commands/track_board.py`
（board 主題分組模式）皆需要同一語意的「一組票的最高優先級」計算。
commands 模組之間不互相 import（既有分層原則，見
`lib/topic_assignments.py` 模組 docstring：commands 依賴 lib，不互相依
賴），故原本存於 `track_topics.py` 的私有函式下沉至 lib/ 供兩者共用；
`track_topics.py` 保留同名私有別名 re-export，呼叫端不變。
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from ticket_system.constants import PRIORITY_LEVELS


def highest_priority(tickets: List[Dict[str, Any]]) -> Optional[str]:
    """回傳票清單中最高（數字最小）priority；無有效 priority 時回傳 None。"""
    known = [t.get("priority") for t in tickets if t.get("priority") in PRIORITY_LEVELS]
    if not known:
        return None
    return min(known, key=PRIORITY_LEVELS.index)
