"""who.history 追加與最後執行者推導。

who.history 的形狀為 ``{ISO 時間: 原 current}``，依插入順序保存改派軌跡。
改派路徑（set-who、claim --as、PM 暫代管讓出）改變 current 時追加一筆；
complete 時以 ``last_non_pm_executor`` 找回真正的執行者，避免 PM 於 complete
前把 who 改成自己後，執行者資訊從 frontmatter 消失。
"""

from datetime import datetime
from typing import Any, Dict, Optional

from ticket_system.lib.identity_guard import PM_AGENT_NAME

# 建票預設值，不是任何人的執行軌跡
_PLACEHOLDER_CURRENT = ("", "pending")


def record_who_change(who: Dict[str, Any], new_current: Any) -> None:
    """current 即將改為 new_current 時，把原 current 追加進 history（原地修改）。

    current 未變、或原值為空／placeholder 時不追加。須在寫入 current 之前呼叫。
    """
    old_current = who.get("current")
    if old_current == new_current or old_current in _PLACEHOLDER_CURRENT:
        return
    history = who.get("history")
    if not isinstance(history, dict):
        history = {}
        who["history"] = history
    stamp = datetime.now().isoformat(timespec="seconds")
    while stamp in history:
        stamp += "+"  # 同秒多次改派：保留每一筆，不互相覆蓋
    history[stamp] = old_current


def _is_named_executor(agent: Any) -> bool:
    return isinstance(agent, str) and agent not in _PLACEHOLDER_CURRENT and agent != PM_AGENT_NAME


def last_non_pm_executor(who: Any) -> Optional[str]:
    """current 非 PM 取 current，否則取 history 中最後一個非 PM 者；皆無回 None。"""
    if not isinstance(who, dict):
        return None
    if _is_named_executor(who.get("current")):
        return who["current"]
    history = who.get("history")
    if isinstance(history, dict):
        for agent in reversed(list(history.values())):
            if _is_named_executor(agent):
                return agent
    return None
