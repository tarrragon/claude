"""
Ticket track depth 查詢模組（W1-056.8 / 協議 v2 D3）

提供 `ticket track depth <id>` 命令，沿 parent_id 鏈計算並回報嵌套深度與
can_descend 判定，供 agent 自檢層級自覺（無需上層 prompt 傳遞層級資訊）。
"""
# 防止直接執行此模組
if __name__ == "__main__":
    from ticket_system.lib.messages import print_not_executable_and_exit
    print_not_executable_and_exit()

import argparse

from ticket_system.constants import MAX_TICKET_DEPTH
from ticket_system.lib.depth import compute_depth, can_descend
from ticket_system.lib.parser import load_ticket
from ticket_system.lib.messages import format_error
from ticket_system.lib.command_tracking_messages import TrackMessages


def register_depth(subparsers) -> None:
    """註冊 depth 子命令。"""
    p_depth = subparsers.add_parser(
        "depth",
        help="查詢 Ticket 嵌套深度（沿 parent_id 鏈）與 can_descend 判定",
    )
    p_depth.add_argument("ticket_id", help=TrackMessages.ARG_TICKET_ID)
    p_depth.add_argument("--version", help=TrackMessages.ARG_VERSION)


def execute_depth(args: argparse.Namespace, version: str) -> int:
    """
    查詢單一 Ticket 的嵌套深度。

    輸出：
        depth = N
        max_depth = MAX_TICKET_DEPTH
        can_descend = true/false（depth < MAX_TICKET_DEPTH）

    Returns:
        int: 0 成功；1 失敗（ticket 不存在）
    """
    ticket_id = args.ticket_id
    ticket = load_ticket(version, ticket_id)
    if not ticket:
        print(format_error(f"找不到 Ticket: {ticket_id}"))
        return 1

    depth = compute_depth(ticket_id, version)
    descend = can_descend(ticket_id, version)

    print(f"[Ticket 嵌套深度] {ticket_id}")
    print(f"  depth = {depth}")
    print(f"  max_depth = {MAX_TICKET_DEPTH}")
    print(f"  can_descend = {'true' if descend else 'false'}")
    if not descend:
        print("  [Note] 已達深度上限，不應再往下嵌套派發子任務（協議 v2 A-6）")
    return 0
