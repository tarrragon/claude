"""
ticket track set-coordination 子命令

寫入或清除 frontmatter `coordination: true`（協調票旗標，
由 multi-session-orchestration 的 coordination_ticket.py 消費）。

格式：
  ticket track set-coordination <id> [--clear] [--version <v>]
"""

if __name__ == "__main__":
    import sys
    print("[ERROR] 此檔案不支援直接執行，請使用 ticket track set-coordination")
    sys.exit(1)


import argparse
from pathlib import Path

from ticket_system.lib.file_lock import file_lock
from ticket_system.lib.ticket_loader import get_ticket_path, save_ticket
from ticket_system.lib.ticket_ops import (
    load_and_validate_ticket,
    resolve_ticket_path,
)


def execute_set_coordination(args: argparse.Namespace, version: str) -> int:
    """設定（預設）或清除（--clear）票的 coordination 旗標；冪等。"""
    ticket_id = args.ticket_id
    clear = bool(getattr(args, "clear", False))

    lock_target = Path(get_ticket_path(version, ticket_id))
    with file_lock(lock_target):
        ticket, load_error = load_and_validate_ticket(version, ticket_id)
        if load_error:
            return 1

        current = ticket.get("coordination") is True
        if current != clear:
            state = "已清除" if clear else "已設定"
            print(f"[INFO] {ticket_id} 的 coordination 旗標{state}，無需修改")
            return 0

        if clear:
            ticket.pop("coordination", None)
        else:
            ticket["coordination"] = True
        ticket_path = resolve_ticket_path(ticket, version, ticket_id)
        save_ticket(ticket, ticket_path)

        from ticket_system.lib import git_utils
        commit_failed = git_utils.commit_ticket_md_reporting(
            "set-coordination", str(ticket_path), ticket_id, "coordination",
            operation="set-coordination",
        )

    action = "清除" if clear else "設定"
    print(f"[OK] {ticket_id} 的 coordination 旗標已{action}")
    return git_utils.EXIT_AUTO_COMMIT_FAILED if commit_failed else 0
