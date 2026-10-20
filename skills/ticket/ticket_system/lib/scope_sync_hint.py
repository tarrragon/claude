"""範圍欄位同步提示

票的範圍由五個欄位共同表達：title、what、acceptance、where.files、how.strategy。
其中一個被 set- 改動時，其餘欄位容易停留在舊範圍；本模組在寫入後列出其餘
非空欄位的現值與對應 set- 指令。只印不擋，不影響 exit code。
"""

from typing import Any, Dict, List, Optional

HINT_TITLE = "[提示] 範圍欄位同步提示：已改動 {changed}，其餘範圍欄位現值如下，請確認是否需同步"

_MAX_SUMMARY = 60

# (欄位鍵, 顯示名, 對應 set- 指令樣板)
_SCOPE_FIELDS = (
    ("title", "title", "ticket track set-title {tid} <value>"),
    ("what", "what", "ticket track set-what {tid} <value>"),
    ("acceptance", "acceptance", "ticket track set-acceptance {tid} --add|--edit ..."),
    ("where.files", "where.files", "ticket track set-where {tid} --files <a,b>"),
    ("how.strategy", "how.strategy", "ticket track set-how {tid} --strategy <value>"),
)


def read_scope_value(ticket: Dict[str, Any], key: str) -> Any:
    """取出範圍欄位現值；dict 子欄位以 'a.b' 鍵讀取。"""
    if "." not in key:
        return ticket.get(key)
    parent, sub = key.split(".", 1)
    container = ticket.get(parent)
    return container.get(sub) if isinstance(container, dict) else None


def is_scope_value_empty(value: Any) -> bool:
    """空值判定：None、空字串、空清單，或建票預設的「待定義」。"""
    if value is None:
        return True
    if isinstance(value, (list, tuple)):
        return len(value) == 0
    return str(value).strip() in ("", "待定義")


def _summarize(value: Any) -> str:
    if isinstance(value, (list, tuple)):
        text = f"{len(value)} 項：" + "; ".join(str(v) for v in value)
    else:
        text = str(value)
    text = " ".join(text.split())
    return text if len(text) <= _MAX_SUMMARY else text[: _MAX_SUMMARY - 1] + "…"


def build_scope_sync_hint(
    ticket: Dict[str, Any], changed_key: str, ticket_id: str
) -> List[str]:
    """回傳提示行；其餘範圍欄位皆為空時回傳空清單。"""
    lines: List[str] = []
    for key, label, cmd in _SCOPE_FIELDS:
        if key == changed_key:
            continue
        value = read_scope_value(ticket, key)
        if is_scope_value_empty(value):
            continue
        lines.append(f"   - {label}: {_summarize(value)}")
        lines.append(f"       同步：{cmd.format(tid=ticket_id)}")
    if not lines:
        return []
    return [HINT_TITLE.format(changed=changed_key)] + lines


def print_scope_sync_hint(
    ticket: Dict[str, Any],
    changed_key: str,
    ticket_id: str,
    prior_value: Optional[Any],
) -> None:
    """寫入後印出提示。prior_value 為被改欄位的原值；原值為空（首次填寫）不印。"""
    if is_scope_value_empty(prior_value):
        return
    for line in build_scope_sync_hint(ticket, changed_key, ticket_id):
        print(line)
