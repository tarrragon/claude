"""已結案父票的子票寫入守衛。

complete 會擋「父票帶未完成子票」，但 complete 之後若仍能以
`create --parent` 或 `track add-child` 掛上未完成子票，父票就停在
completed／closed 而底下有 pending 子票，complete 的子票檢查形同虛設
（tarrragon/claude#70）。兩個寫入點在寫入前都呼叫本模組判定。

不提供 --force 旁路：已結案父票要追加後續工作時，合法路徑是
`--source-ticket <父票>` 建立衍生票，或先把父票重開；旁路等於保留同一個
不一致狀態的產生路徑。
"""

from typing import Any, Dict, Optional

from ticket_system.constants import TERMINAL_STATUSES


def terminal_parent_hint(parent_id: str, parent_ticket: Optional[Dict[str, Any]]) -> Optional[str]:
    """父票為 completed／closed 時回傳拒絕說明，否則回傳 None。

    父票讀不到（None）時回傳 None，交由呼叫端既有的不存在處理。
    """
    if not parent_ticket:
        return None
    status = parent_ticket.get("status")
    if status not in TERMINAL_STATUSES:
        return None
    return (
        f"父票 {parent_id} 狀態為 {status}，不可再掛子票："
        "子票掛上後父票會停在已結案而底下有未完成工作，complete 的子票檢查因此失效。\n"
        f"  - 後續工作屬新範圍：改用 --source-ticket {parent_id} 建立衍生票"
        "（排入後續版本時加 --version <目標版本>）\n"
        "  - 父票其實未完成：先把父票改回 in_progress 再建子票"
    )
