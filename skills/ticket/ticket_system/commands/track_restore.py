"""
ticket track restore 子命令

提供 closed 票的還原路徑（closed -> pending）。

背景：closed 為 STATUS_TRANSITIONS 定義的終態，release 與 claim 皆被
enum-gate 擋下（closed 合法出邊：無），ticket md 另有 read guard 使 PM
無法直接編輯——三條既有路徑同時封死。一個不可逆的操作配上會誤判的
判準，等於把判準的誤差率直接轉成永久損失。本命令補上這條缺口路徑，
且刻意設計為唯一可觸發 closed -> pending 的入口（`STATUS_TRANSITIONS`
只開放這一個出邊，不開放 in_progress/blocked，release/claim 因此仍被擋）。

設計要點：
- 必填 --reason，禁止靜默改狀態
- 落地清除 close_reason / close_reason_note / closed_by / closed_at /
  completed_at 五個 close 相關欄位（completed_at 通常已是 null，一併
  清除以防 close 前為 completed 轉 closed 的情境殘留舊值）
- 票面留下還原記錄：restored_at / restored_by / restore_reason 三個新欄位

格式：
  ticket track restore <id> --reason <text> [--as <agent>] [--version <v>]
"""

if __name__ == "__main__":
    import sys
    print("[ERROR] 此檔案不支援直接執行，請使用 ticket track restore")
    sys.exit(1)


import argparse
import sys as _sys
from datetime import datetime
from pathlib import Path

from ticket_system.constants import STATUS_CLOSED, STATUS_PENDING
from ticket_system.lib.file_lock import file_lock
from ticket_system.lib.ticket_loader import get_ticket_path, save_ticket
from ticket_system.lib.ticket_ops import (
    load_and_validate_ticket,
    resolve_ticket_path,
)

_CLOSE_FIELDS_TO_CLEAR = (
    "close_reason",
    "close_reason_note",
    "closed_by",
    "closed_at",
    "completed_at",
)


def execute_restore(args: argparse.Namespace, version: str) -> int:
    """
    還原 closed 票為 pending（closed 態唯一合法出邊）。

    僅允許對 status=closed 的票操作。--reason 必填，落地時清除全部
    close 相關欄位並在票面寫入還原記錄（何時、誰、為何），走 auto-commit
    使 git log 可追溯（與 set-closed-by 同保護等級）。
    """
    ticket_id = args.ticket_id
    reason = getattr(args, "reason", "") or ""
    as_agent = getattr(args, "as_agent", "") or ""

    if not reason.strip():
        print("[Error] --reason 必填，禁止靜默還原")
        return 1

    lock_target = Path(get_ticket_path(version, ticket_id))
    with file_lock(lock_target):
        ticket, load_error = load_and_validate_ticket(version, ticket_id)
        if load_error:
            return 1

        status = ticket.get("status", "")
        if status != STATUS_CLOSED:
            print(
                f"[Error] restore 僅適用 status=closed 的票，"
                f"{ticket_id} 現況為 {status!r}"
            )
            return 1

        old_snapshot = {
            field: ticket.get(field) for field in _CLOSE_FIELDS_TO_CLEAR
        }

        ticket["status"] = STATUS_PENDING
        for field in _CLOSE_FIELDS_TO_CLEAR:
            ticket.pop(field, None)

        restored_at = datetime.now().isoformat(timespec="seconds")
        ticket["restored_at"] = restored_at
        ticket["restored_by"] = as_agent or "PM"
        ticket["restore_reason"] = reason

        ticket_path = resolve_ticket_path(ticket, version, ticket_id)
        save_ticket(ticket, ticket_path)

        from ticket_system.lib import git_utils
        try:
            commit_status = git_utils._auto_commit_ticket_md(
                str(ticket_path), ticket_id, "status",
                operation="restore",
            )
            if commit_status in ("not_git_repo", "git_failed"):
                _sys.stderr.write(
                    f"[restore] auto-commit skipped（{commit_status}，非致命）；"
                    f"body 已保留 working tree，可手動 git commit 持久化。\n"
                )
        except Exception as exc:
            _sys.stderr.write(
                f"[restore] auto-commit 失敗（非致命，body 已保留 working tree）：{exc}\n"
            )

    print(f"[OK] {ticket_id} 已從 closed 還原為 pending")
    print(f"   還原時間: {restored_at}")
    print(f"   還原者: {ticket['restored_by']}")
    print(f"   還原理由: {reason}")
    print(f"   已清除欄位: {', '.join(_CLOSE_FIELDS_TO_CLEAR)}")
    return 0
