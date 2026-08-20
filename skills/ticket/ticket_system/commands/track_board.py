"""
Ticket 看板命令模組

提供 Kanban 風格的看板視圖，視覺化展示各狀態的任務分佈。
"""
# 防止直接執行此模組
if __name__ == "__main__":
    import sys
    # 模組直接執行時套件 import 不可用，用局部常數替代 SEPARATOR_PRIMARY
    _SEP = "=" * 60
    print(_SEP)
    print("[ERROR] 此檔案不支援直接執行")
    print(_SEP)
    print()
    print("正確使用方式：")
    print("  ticket track board")
    print("  ticket track board --version 0.31.0")
    print("  ticket track board --ascii")
    print()
    print("詳見 SKILL.md")
    print(_SEP)
    sys.exit(1)


import argparse
import sys
from typing import Any, Dict, List

from ticket_system.constants import PRIORITY_LEVELS
from ticket_system.lib.ticket_loader import list_tickets
from ticket_system.lib.constants import TERMINAL_STATUSES
from ticket_system.lib.messages import format_error
from ticket_system.lib.command_tracking_messages import (
    TrackBoardMessages,
    format_msg,
)
from ticket_system.lib.priority_utils import highest_priority
from ticket_system.lib.topic_assignments import list_assignments
from ticket_system.lib.ui_constants import SEPARATOR_SECONDARY
from ticket_system.lib.ticket_validator import extract_wave_from_ticket_id
from typing import Tuple

# board --group-by 選項值（GROUP_BY_WAVE 為預設，維持既有 Wave 分組行為不變）
GROUP_BY_WAVE = "wave"
GROUP_BY_TOPIC = "topic"


def filter_incomplete_tickets(tickets: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """過濾未完成任務（保留 pending, in_progress, blocked），排除無效 ticket"""
    return [
        t for t in tickets
        if t.get("status") is not None and t.get("status") not in TERMINAL_STATUSES
    ]


def extract_wave_number(ticket_id: str) -> str:
    """從 Ticket ID 提取 Wave 號（顯示格式，如 W9）"""
    wave = extract_wave_from_ticket_id(ticket_id)
    return f"W{wave}" if wave is not None else "Unknown"


def group_by_wave(tickets: List[Dict[str, Any]]) -> Dict[str, List[Dict[str, Any]]]:
    """按 Wave 分組，升序排列"""
    groups = {}
    for ticket in tickets:
        wave = extract_wave_number(ticket.get("id", ""))
        if wave not in groups:
            groups[wave] = []
        groups[wave].append(ticket)

    # 按 Wave 號排序（提取數字）
    sorted_waves = sorted(groups.keys(), key=lambda w: int(w[1:]) if w != "Unknown" else 9999)
    return {w: groups[w] for w in sorted_waves}


def group_by_topic(
    tickets: List[Dict[str, Any]], assignments: Dict[str, str]
) -> Tuple[Dict[str, List[Dict[str, Any]]], List[Dict[str, Any]]]:
    """
    按主題分組（board 主題分組模式，與 group_by_wave 平行新增）

    Args:
        tickets: Ticket 清單
        assignments: ticket_id -> topic 映射（來自 list_assignments()）

    Returns:
        Tuple[Dict[str, List], List]:
            - 主題分組字典（已排序），鍵為主題名，值為該主題的票清單
            - 未歸屬票清單（assignments 中無對應主題者）

    排序依據（acceptance 4）：
        主題內最高優先級（highest_priority()，P0 最優先）為第一鍵；同優先
        級時，票數較多者排前（票數愈多代表待決策範圍愈大，愈需優先檢
        視）。無有效 priority 的主題視為最低優先級，排在有 priority 的
        主題之後。
    """
    groups: Dict[str, List[Dict[str, Any]]] = {}
    unassigned: List[Dict[str, Any]] = []

    for ticket in tickets:
        topic = assignments.get(ticket.get("id", ""))
        if topic is None:
            unassigned.append(ticket)
            continue
        groups.setdefault(topic, []).append(ticket)

    def _topic_sort_key(topic_name: str) -> Tuple[int, int]:
        topic_tickets = groups[topic_name]
        priority = highest_priority(topic_tickets)
        priority_rank = (
            PRIORITY_LEVELS.index(priority) if priority in PRIORITY_LEVELS else len(PRIORITY_LEVELS)
        )
        return (priority_rank, -len(topic_tickets))

    sorted_topics = sorted(groups.keys(), key=_topic_sort_key)
    return {t: groups[t] for t in sorted_topics}, unassigned


def build_tree_structure(tickets: List[Dict[str, Any]]) -> Tuple[Dict[str, List[str]], List[str]]:
    """構建樹狀索引"""
    ticket_ids = {t.get("id") for t in tickets}
    parent_to_children: Dict[str, List[str]] = {}
    root_ids = []

    for ticket in tickets:
        tid = ticket.get("id", "")
        # 判斷是否為子任務（ID 包含 "." 如 W7-001.1）
        if "." in tid.split("-")[-1]:
            # 找父任務 ID
            parts = tid.rsplit(".", 1)
            parent_id = parts[0]
            if parent_id in ticket_ids:
                if parent_id not in parent_to_children:
                    parent_to_children[parent_id] = []
                parent_to_children[parent_id].append(tid)
            else:
                root_ids.append(tid)
        else:
            root_ids.append(tid)

    # 排序子任務
    for parent in parent_to_children:
        parent_to_children[parent].sort()
    root_ids.sort()

    return parent_to_children, root_ids


def render_tree_node(
    ticket_id: str,
    tickets_dict: Dict[str, Dict[str, Any]],
    tree_structure: Dict[str, List[str]],
    prefix: str = "",
    is_last: bool = True
) -> List[str]:
    """遞迴渲染單一節點"""
    lines = []
    ticket = tickets_dict.get(ticket_id)
    if not ticket:
        return lines

    # 節點符號
    connector = "└── " if is_last else "├── "

    # 格式化顯示
    short_id = simplify_ticket_id(ticket_id)
    priority = ticket.get("priority", "P2")
    # Tree view 顯示完整標題（不截斷）
    title = ticket.get("title", "")

    lines.append(f"{prefix}{connector}{short_id} [{priority}] {title}")

    # 子節點前綴
    child_prefix = prefix + ("    " if is_last else "│   ")

    # 遞迴渲染子節點
    children = tree_structure.get(ticket_id, [])
    for i, child_id in enumerate(children):
        child_is_last = (i == len(children) - 1)
        lines.extend(render_tree_node(child_id, tickets_dict, tree_structure, child_prefix, child_is_last))

    return lines


def render_board_tree(
    tickets: List[Dict[str, Any]],
    version: str,
    show_all: bool = False
) -> str:
    """
    渲染樹狀看板

    Args:
        tickets: Ticket 清單
        version: 版本號
        show_all: 是否顯示所有任務（包含已完成）
    """
    lines = []

    # 標題
    if show_all:
        lines.append(format_msg(TrackBoardMessages.TREE_TITLE_ALL, version=version))
    else:
        lines.append(format_msg(TrackBoardMessages.TREE_TITLE_INCOMPLETE, version=version))
    lines.append(SEPARATOR_SECONDARY)
    lines.append("")

    # 過濾任務
    if show_all:
        filtered = tickets
    else:
        filtered = filter_incomplete_tickets(tickets)

    if not filtered:
        lines.append(TrackBoardMessages.NO_TASKS_TEXT)
        return "\n".join(lines)

    # 按 Wave 分組
    wave_groups = group_by_wave(filtered)

    # 建立 ticket_id -> ticket 映射
    tickets_dict = {t.get("id"): t for t in filtered}

    # 渲染每個 Wave
    for wave, wave_tickets in wave_groups.items():
        # Wave 標題
        lines.append(format_msg(TrackBoardMessages.WAVE_TITLE_FORMAT, wave=wave, count=len(wave_tickets)))

        # 構建該 Wave 的樹狀結構
        tree_structure, root_ids = build_tree_structure(wave_tickets)

        # 渲染根節點
        for i, root_id in enumerate(root_ids):
            is_last = (i == len(root_ids) - 1)
            lines.extend(render_tree_node(root_id, tickets_dict, tree_structure, "", is_last))

        lines.append("")  # Wave 間空行

    return "\n".join(lines)


def _render_ticket_group(
    group_tickets: List[Dict[str, Any]],
    tickets_dict: Dict[str, Dict[str, Any]],
    lines: List[str],
) -> None:
    """以既有樹狀結構（build_tree_structure/render_tree_node）渲染一組票，
    供 render_board_topics 的主題節與未歸屬節共用（DRY）"""
    tree_structure, root_ids = build_tree_structure(group_tickets)
    for i, root_id in enumerate(root_ids):
        is_last = (i == len(root_ids) - 1)
        lines.extend(render_tree_node(root_id, tickets_dict, tree_structure, "", is_last))


def render_board_topics(
    tickets: List[Dict[str, Any]],
    assignments: Dict[str, str],
    version: str,
    show_all: bool = False
) -> str:
    """
    渲染依主題分組的樹狀看板（board 主題分組模式，與 render_board_tree 平行新增）

    Args:
        tickets: Ticket 清單
        assignments: ticket_id -> topic 映射（來自 list_assignments()）
        version: 版本號
        show_all: 是否顯示所有任務（包含已完成）

    未歸屬票（assignments 中無對應主題者）獨立成節置於末尾，不與任一
    主題混列（acceptance 2）。
    """
    lines = []

    # 標題（沿用既有樹狀標題訊息，模式差異不影響標題文字）
    if show_all:
        lines.append(format_msg(TrackBoardMessages.TREE_TITLE_ALL, version=version))
    else:
        lines.append(format_msg(TrackBoardMessages.TREE_TITLE_INCOMPLETE, version=version))
    lines.append(SEPARATOR_SECONDARY)
    lines.append("")

    # 過濾任務
    if show_all:
        filtered = tickets
    else:
        filtered = filter_incomplete_tickets(tickets)

    if not filtered:
        lines.append(TrackBoardMessages.NO_TASKS_TEXT)
        return "\n".join(lines)

    # 按主題分組（已依 highest_priority -> ticket 數排序）
    topic_groups, unassigned = group_by_topic(filtered, assignments)

    # 建立 ticket_id -> ticket 映射
    tickets_dict = {t.get("id"): t for t in filtered}

    # 渲染每個主題節（acceptance 1）
    for topic, topic_tickets in topic_groups.items():
        priority = highest_priority(topic_tickets) or TrackBoardMessages.TOPIC_NO_PRIORITY_TEXT
        lines.append(format_msg(
            TrackBoardMessages.TOPIC_TITLE_FORMAT,
            topic=topic,
            count=len(topic_tickets),
            priority=priority,
        ))
        _render_ticket_group(topic_tickets, tickets_dict, lines)
        lines.append("")  # 主題間空行

    # 渲染未歸屬節（acceptance 2，獨立成節置於末尾）
    if unassigned:
        lines.append(format_msg(TrackBoardMessages.TOPIC_UNASSIGNED_TITLE_FORMAT, count=len(unassigned)))
        _render_ticket_group(unassigned, tickets_dict, lines)
        lines.append("")

    return "\n".join(lines)


def simplify_ticket_id(full_id: str) -> str:
    """
    簡化 Ticket ID（去除版本前綴）

    Args:
        full_id: 完整 ID（如 "0.31.0-W7-001"）

    Returns:
        str: 簡化 ID（如 "W7-001"）

    邏輯：
        1. 驗證輸入（None 或空字串 → "Unknown"）
        2. 分割字串（以 "-" 為分隔符）
        3. 組合 Wave 和序號
    """
    # Guard Clause：驗證輸入
    if not full_id:
        return "Unknown"

    # 分割字串
    parts = full_id.split("-")

    # 組合 Wave 和序號
    if len(parts) >= 3:
        # 預期格式: ["版本號", "Wave", "序號"]
        # 如 "0.31.0-W7-001" → ["0.31.0", "W7", "001"]
        return f"{parts[1]}-{parts[2]}"
    else:
        # 如果無法分割，返回原始值
        return full_id


def execute_board(args: argparse.Namespace, version: str) -> int:
    """
    執行 board 命令主入口（預設輸出 Wave 分組樹狀看板）

    Args:
        args: 命令列參數（包含 --version, --wave, --all, --group-by 選項）
        version: 目標版本號（從 resolve_version 取得）

    Returns:
        int: 0 表示成功，1 表示失敗

    --group-by 未指定或為 GROUP_BY_WAVE 時，行為與新增本旗標前逐字相同
    （acceptance 3：呼叫 render_board_tree，不經任何主題相關路徑）。
    """
    try:
        # 載入 Ticket 資料
        tickets = list_tickets(version)

        # 套用 Wave 過濾
        if hasattr(args, "wave") and args.wave:
            wave = args.wave
            tickets = [t for t in tickets if f"-{wave}-" in t.get("id", "")]

        # 判斷是否顯示所有任務
        show_all = getattr(args, "all", False)

        # 分組模式：預設 GROUP_BY_WAVE 維持既有行為不變
        group_by = getattr(args, "group_by", None) or GROUP_BY_WAVE

        if group_by == GROUP_BY_TOPIC:
            assignments = list_assignments()
            output = render_board_topics(tickets, assignments, version, show_all=show_all)
        else:
            output = render_board_tree(tickets, version, show_all=show_all)
        print(output)

        return 0

    except Exception as e:
        print(format_error(f"{TrackBoardMessages.ERROR_RENDERING_BOARD_PREFIX} {str(e)}"))
        return 1
