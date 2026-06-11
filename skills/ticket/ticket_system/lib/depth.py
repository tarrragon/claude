"""
Ticket 嵌套深度計算模組（W1-056.5 協議 v2 D3）

深度沿 `parent_id` 鏈回溯計算，為世界平面 SSOT（field-semantics.md），
與 ticket ID 字串格式解耦。

設計背景（linux F1 fatal 修正）：
    協議 v1 曾以 `ticket_id.count('.') + 1` 計算深度，但完整 ticket ID 含版本號
    前綴（如 `1.0.0-W1-056.5` 有 3 個點），會算出錯誤深度（silent bug）。
    v2 改為沿 parent_id 鏈計數：parent_id 由 CLI 自動維護，是層級結構的權威來源。

純分析層補強：
    本模組需要 load_ticket（I/O）以回溯 parent_id 鏈，因此並非純函式。
    深度計算邏輯（given parent_id resolver）抽為 `_depth_via_resolver`，
    便於單元測試以記憶體字典注入，無需真實檔案。
"""
from typing import Callable, Optional

from ticket_system.constants import MAX_TICKET_DEPTH
from ticket_system.lib.parser import load_ticket
from ticket_system.lib.ticket_validator import extract_version_from_ticket_id

# 防止無限迴圈的安全上限（parent_id 鏈異常成環時）
_MAX_CHAIN_WALK = 100


def _depth_via_resolver(
    ticket_id: str,
    parent_of: Callable[[str], Optional[str]],
) -> int:
    """
    沿 parent_id 鏈計算深度（純邏輯，I/O 由 resolver 注入）。

    深度定義：根任務（parent_id 為 None）為 depth 1，每往下一層 +1。

    Args:
        ticket_id: 起始 Ticket ID
        parent_of: 給定 ticket_id 回傳其 parent_id 的函式（None 表示根或不存在）

    Returns:
        int: 深度（>= 1）

    Examples:
        >>> chain = {"A.1": "A", "A": None}
        >>> _depth_via_resolver("A.1", lambda tid: chain.get(tid))
        2
        >>> _depth_via_resolver("A", lambda tid: chain.get(tid))
        1
    """
    depth = 1
    current = ticket_id
    for _ in range(_MAX_CHAIN_WALK):
        parent = parent_of(current)
        if not parent:
            return depth
        depth += 1
        current = parent
    # 鏈長異常（疑似成環），回傳目前累積深度避免無限迴圈
    return depth


def compute_depth(ticket_id: str, version: Optional[str] = None) -> int:
    """
    計算 Ticket 的嵌套深度（沿 parent_id 鏈，世界平面 SSOT）。

    深度定義：
        - 根任務（parent_id: null）→ depth 1
        - 一級子任務 → depth 2
        - 二級子任務 → depth 3

    Args:
        ticket_id: 目標 Ticket ID（如 "1.0.0-W1-056.5"）
        version: 版本號（可選，預設從 ticket_id 提取）

    Returns:
        int: 深度（>= 1）；若 ticket 不存在則以 ID 計為 depth 1

    Examples:
        >>> # 1.0.0-W1-056（parent_id: null）→ 1
        >>> # 1.0.0-W1-056.5（parent_id: 1.0.0-W1-056）→ 2
        >>> # 1.0.0-W1-056.5.1（parent_id: 1.0.0-W1-056.5）→ 3
    """
    resolved_version = version or extract_version_from_ticket_id(ticket_id)

    def parent_of(tid: str) -> Optional[str]:
        if not resolved_version:
            return None
        ticket = load_ticket(resolved_version, tid)
        if not ticket:
            return None
        return ticket.get("parent_id")

    return _depth_via_resolver(ticket_id, parent_of)


def can_descend(ticket_id: str, version: Optional[str] = None) -> bool:
    """
    判斷該 Ticket 是否仍可往下嵌套派發（唯一判準）。

    can_descend = depth(ticket) < MAX_TICKET_DEPTH

    Args:
        ticket_id: 目標 Ticket ID
        version: 版本號（可選）

    Returns:
        bool: True 表示尚可 descend；False 表示已達深度上限
    """
    return compute_depth(ticket_id, version) < MAX_TICKET_DEPTH


if __name__ == "__main__":
    from ticket_system.lib.messages import print_not_executable_and_exit
    print_not_executable_and_exit()
