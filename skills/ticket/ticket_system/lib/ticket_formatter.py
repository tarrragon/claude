"""
Ticket 格式化模組

提供 Ticket 格式化輸出功能。
"""
# 防止直接執行此模組
from typing import Dict, Any, List, Optional, Union

from .constants import STATUS_LABELS, STATUS_COMPLETED
from .ui_constants import (
    DEFAULT_UNKNOWN_VALUE,
    DEFAULT_ELAPSED_TIME_FORMAT_HOURS,
    DEFAULT_ELAPSED_TIME_FORMAT_MINUTES,
    INDENT_SYMBOL,
    TREE_BRANCH_PREFIX,
    TABLE_SEPARATOR,
)


def format_status_icon(status: str) -> str:
    """
    格式化狀態圖示

    Args:
        status: 狀態字串

    Returns:
        str: 格式化的狀態圖示

    Examples:
        >>> format_status_icon("pending")
        '[待處理]'
        >>> format_status_icon("completed")
        '[已完成]'
    """
    status_icons = {
        "pending": "[待處理]",
        "in_progress": "[進行中]",
        "completed": "[已完成]",
        "blocked": "[被阻塞]",
    }
    return status_icons.get(status, f"[{DEFAULT_UNKNOWN_VALUE}]")


def get_ticket_what(ticket: Dict[str, Any]) -> str:
    """
    取得 Ticket 的簡短描述（what）。

    使用 Guard Clause 模式，優先順序逐層遞減。
    目的是提供簡潔易讀的 Ticket 單行描述。

    優先順序:
    1. what：Ticket 專用簡短描述欄位（最優先）
    2. action + target：動作和目標的組合
    3. title：Ticket 標題
    4. id/ticket_id：最後手段，使用 ID 作為描述

    Args:
        ticket: Ticket 資料字典

    Returns:
        str: Ticket 簡短描述
             若無任何描述欄位，返回預設值（DEFAULT_UNKNOWN_VALUE = "?"）

    Examples:
        >>> ticket = {"what": "實作新功能"}
        >>> get_ticket_what(ticket)
        '實作新功能'
        >>> ticket = {"action": "建立", "target": "Ticket 系統"}
        >>> get_ticket_what(ticket)
        '建立 Ticket 系統'
        >>> ticket = {"title": "系統重構", "id": "0.31.0-W4-001"}
        >>> get_ticket_what(ticket)
        '系統重構'
    """
    # Guard Clause 1：優先使用 what 欄位（專用簡述欄位）
    if ticket.get("what"):
        return ticket["what"]

    # Guard Clause 2：組合 action 和 target
    action = ticket.get("action", "")
    target = ticket.get("target", "")
    if action and target:
        return f"{action} {target}"

    # Guard Clause 3-5：逐層遞減，使用可用的欄位
    # 優先 title，次選 id/ticket_id
    return ticket.get("title", ticket.get("id", ticket.get("ticket_id", DEFAULT_UNKNOWN_VALUE)))


def format_ticket_summary(ticket: Dict[str, Any], include_elapsed: bool = False) -> str:
    """
    格式化 Ticket 摘要（一行）

    Args:
        ticket: Ticket 資料字典
        include_elapsed: 是否包含經過時間

    Returns:
        str: 格式化的 Ticket 摘要

    Examples:
        >>> ticket = {
        ...     "id": "0.31.0-W3-001",
        ...     "status": "pending",
        ...     "what": "實作功能"
        ... }
        >>> format_ticket_summary(ticket)
        '0.31.0-W3-001 | [待處理] | 實作功能'
    """
    ticket_id = ticket.get("id") or ticket.get("ticket_id", DEFAULT_UNKNOWN_VALUE)
    status = ticket.get("status", "pending")
    what = get_ticket_what(ticket)

    status_icon = format_status_icon(status)

    result = f"{ticket_id} {TABLE_SEPARATOR} {status_icon} {TABLE_SEPARATOR} {what}"

    # 可選：加入經過時間
    if include_elapsed and ticket.get("started_at"):
        from datetime import datetime

        try:
            start = datetime.fromisoformat(
                ticket["started_at"].replace("Z", "+00:00")
            )
            elapsed = datetime.now() - start.replace(tzinfo=None)
            hours = int(elapsed.total_seconds() // 3600)
            minutes = int((elapsed.total_seconds() % 3600) // 60)

            if hours > 0:
                elapsed_str = DEFAULT_ELAPSED_TIME_FORMAT_HOURS.format(hours=hours, minutes=minutes)
            else:
                elapsed_str = DEFAULT_ELAPSED_TIME_FORMAT_MINUTES.format(minutes=minutes)

            result += elapsed_str
        except (ValueError, TypeError):
            pass

    return result


def _find_children(tickets: List[Dict[str, Any]], parent_id: str) -> List[Dict[str, Any]]:
    """
    查找給定父 Ticket 的所有子 Ticket

    相容 chain.parent 和 parent_id 兩種欄位格式。

    Args:
        tickets: Ticket 列表
        parent_id: 父 Ticket ID

    Returns:
        List[Dict[str, Any]]: 子 Ticket 列表
    """
    return [
        t for t in tickets
        if t.get("chain", {}).get("parent") == parent_id
        or t.get("parent_id") == parent_id
    ]


def _extract_who_name(who_field: Union[str, Dict[str, Any], None]) -> str:
    """
    從 who 欄位提取代理人名稱。

    處理多種型態（字典、字串或 None），從不同的 who 欄位結構中
    提取代理人名稱，並支援提取簡稱。

    支援的欄位結構：
    - None：未指派，返回預設值
    - str：代理人全稱（如 parsley-flutter-developer）或簡稱
    - dict：包含 "current" 欄位的字典（歷史記錄格式）

    代理人全稱格式：shortname-description（如 parsley-flutter-developer）
    當包含 "-" 時，僅返回 shortname 部分

    Args:
        who_field: who 欄位，可能的型態為：
                  - None
                  - str: 代理人名稱
                  - dict: {"current": "代理人名稱", ...}

    Returns:
        str: 代理人簡稱或完整名稱
             - 若為全稱（含 "-"）→ 返回簡稱（"-" 前部分）
             - 若為簡稱 → 返回完整名稱
             - 若無法提取 → 返回預設值 "?"

    Examples:
        >>> _extract_who_name("parsley-flutter-developer")
        'parsley'
        >>> _extract_who_name({"current": "sage-test-architect"})
        'sage'
        >>> _extract_who_name("lavender")
        'lavender'
        >>> _extract_who_name(None)
        '?'
    """
    # Guard Clause：欄位為空
    if who_field is None:
        return DEFAULT_UNKNOWN_VALUE

    # 根據型態提取名稱
    if isinstance(who_field, dict):
        name = who_field.get("current", DEFAULT_UNKNOWN_VALUE)
    else:
        name = str(who_field)

    # 若包含 "-"，取第一部分作為簡稱
    if "-" in name:
        return name.split("-")[0]

    return name


def _build_tree_node(ticket: Dict[str, Any], indent: str) -> str:
    """
    格式化單一樹節點。

    用於任務樹顯示，根據縮排決定是根節點還是子節點。
    節點格式：[縮排][分支符] ID [狀態] - 描述

    演算法:
    1. 提取 Ticket 資訊：ID、狀態、描述
    2. 格式化狀態圖示（[待處理]、[進行中] 等）
    3. 根據縮排判斷節點深度：
       - 無縮排 → 根節點（無分支符）
       - 有縮排 → 子節點（加分支符號）

    Args:
        ticket: Ticket 資料字典（需要 id、status、title/what 等欄位）
        indent: 縮排字串（用於表示樹深度）
                根節點為空字串 ""，子節點為重複的縮排單位（如 "  "）

    Returns:
        str: 格式化的單行樹節點（包含 ID、狀態圖示、描述）

    Examples:
        >>> ticket = {"id": "0.31.0-W4-001", "status": "completed", "title": "實作功能"}
        >>> _build_tree_node(ticket, "")
        '0.31.0-W4-001 [已完成] - 實作功能'
        >>> _build_tree_node(ticket, "  ")
        '  ├─ 0.31.0-W4-001 [已完成] - 實作功能'
    """
    # 提取 Ticket 關鍵資訊
    ticket_id = ticket.get("id") or ticket.get("ticket_id", DEFAULT_UNKNOWN_VALUE)
    status = ticket.get("status", "pending")
    what = get_ticket_what(ticket)
    status_icon = format_status_icon(status)

    # 根據縮排決定節點格式
    if not indent:
        # 根節點：無縮排和分支符（列表最頂層）
        return f"{ticket_id} {status_icon} - {what}"
    else:
        # 子節點：有縮排和樹分支符號（├─）
        # TREE_BRANCH_PREFIX 通常為 "├─ "
        return f"{indent}{TREE_BRANCH_PREFIX}{ticket_id} {status_icon} - {what}"


def format_ticket_tree(
    tickets: List[Dict[str, Any]],
    root_id: Optional[str] = None,
    depth: int = 0,
) -> str:  # type: ignore
    """
    格式化任務樹結構

    遞迴顯示 parent-child 關係。

    Args:
        tickets: Ticket 列表
        root_id: 根 Ticket ID（若為 None 則顯示所有無父的 Ticket）
        depth: 當前深度（內部使用）

    Returns:
        str: 格式化的任務樹

    Examples:
        >>> tickets = [
        ...     {"id": "0.31.0-W3-001", "status": "completed", "what": "實作"},
        ...     {"id": "0.31.0-W3-001.1", "parent_id": "0.31.0-W3-001",
        ...      "status": "pending", "what": "子任務"},
        ... ]
        >>> print(format_ticket_tree(tickets, "0.31.0-W3-001"))
        0.31.0-W3-001 [已完成] - 實作
        + 0.31.0-W3-001.1 [待處理] - 子任務
    """
    # 尋找匹配的根 Ticket
    if root_id is None:
        matching = [
            t for t in tickets
            if not t.get("chain", {}).get("parent") and not t.get("parent_id")
        ]
    else:
        matching = [t for t in tickets if t.get("id") == root_id or t.get("ticket_id") == root_id]

    # 格式化所有匹配的 Ticket 及其子項
    indent = INDENT_SYMBOL * depth
    lines = []

    for ticket in matching:
        # 格式化當前節點
        lines.append(_build_tree_node(ticket, indent))

        # 遞迴格式化子 Ticket
        ticket_id = ticket.get("id") or ticket.get("ticket_id")
        children = _find_children(tickets, ticket_id)
        for child in children:
            child_id = child.get("ticket_id") or child.get("id")
            child_lines = format_ticket_tree(tickets, child_id, depth + 1)
            lines.append(child_lines)

    return "\n".join(lines)


def format_ticket_list(
    tickets: List[Dict[str, Any]],
    separator: str = "|",
    include_who: bool = False,
) -> str:
    """
    格式化 Ticket 清單

    Args:
        tickets: Ticket 列表
        separator: 欄位分隔符
        include_who: 是否包含執行者 (who) 欄位

    Returns:
        str: 格式化的清單

    Examples:
        >>> tickets = [
        ...     {"id": "0.31.0-W3-001", "status": "pending", "what": "實作"},
        ... ]
        >>> print(format_ticket_list(tickets))
        0.31.0-W3-001 | [待處理] | 實作
    """
    lines = []

    for ticket in tickets:
        ticket_id = ticket.get("id") or ticket.get("ticket_id", DEFAULT_UNKNOWN_VALUE)
        status = ticket.get("status", "pending")
        what = get_ticket_what(ticket)
        status_icon = format_status_icon(status)

        if include_who:
            who_field = ticket.get("who", DEFAULT_UNKNOWN_VALUE)
            who_name = _extract_who_name(who_field)
            line = f"{ticket_id} {separator} {status_icon} {separator} {who_name} {separator} {what}"
        else:
            line = f"{ticket_id} {separator} {status_icon} {separator} {what}"

        lines.append(line)

    return "\n".join(lines)


def get_ticket_stats(tickets: List[Dict[str, Any]]) -> Dict[str, int]:
    """
    計算 Ticket 統計資訊

    Args:
        tickets: Ticket 列表

    Returns:
        Dict[str, int]: 統計資訊（pending, in_progress, completed, blocked）

    Examples:
        >>> tickets = [
        ...     {"status": "completed"},
        ...     {"status": "pending"},
        ...     {"status": "pending"},
        ... ]
        >>> stats = get_ticket_stats(tickets)
        >>> stats["completed"]
        1
        >>> stats["pending"]
        2
    """
    stats = {
        "pending": 0,
        "in_progress": 0,
        "completed": 0,
        "blocked": 0,
    }

    for ticket in tickets:
        status = ticket.get("status", "pending")
        if status in stats:
            stats[status] += 1

    stats["total"] = len(tickets)

    return stats


def format_ticket_stats(stats: Dict[str, int]) -> str:
    """
    格式化 Ticket 統計資訊

    Args:
        stats: 統計資訊字典

    Returns:
        str: 格式化的統計訊息

    Examples:
        >>> stats = {"pending": 2, "in_progress": 1, "completed": 1, "blocked": 0, "total": 4}
        >>> format_ticket_stats(stats)
        '[已完成]: 1 | [進行中]: 1 | [待處理]: 2 | [被阻塞]: 0 (總計 4)'
    """
    completed = stats.get("completed", 0)
    in_progress = stats.get("in_progress", 0)
    pending = stats.get("pending", 0)
    blocked = stats.get("blocked", 0)
    total = stats.get("total", 0)

    return (
        f"[已完成]: {completed} | [進行中]: {in_progress} | "
        f"[待處理]: {pending} | [被阻塞]: {blocked} (總計 {total})"
    )


if __name__ == "__main__":
    from ticket_system.lib.messages import print_not_executable_and_exit
    print_not_executable_and_exit()
