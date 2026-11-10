"""
ticket track set-closed-by 子命令

提供 closed 票 `closed_by` 欄位的合法修正路徑。

背景：close 對已 closed 票拒絕覆寫（`CLOSE_ALREADY_CLOSED`），CLI 無 reopen
子命令，ticket md 的直接 Edit 被 `ticket-file-access-guard-hook` 阻擋——三條
既有路徑皆封閉，`closed_by` 一旦填錯即永久錯誤（如誤填代理人名稱而非
Ticket ID）。本命令補上這條缺口路徑，設計為方向 (b)：專用子命令而非
`close --force-update` 覆寫語意擴張。

僅限修正 `closed_by`（現有已知需求）。若日後 `close_reason` /
`closed_at` 也需要同類修正路徑，優先評估擴充本命令為
`--field {closed_by,close_reason,closed_at}` 通用入口，而非逐一新增
`set-close-reason` / `set-closed-at` 等子命令。

值域與 close 相同，依該票的 close_reason 限定（權威：`.claude/lib/close_resolution.py`）：
superseded_by／duplicate 收 Ticket ID；transferred_to_issue 收 issue 參照
`owner/repo#N`；其餘收 `none` 或 Ticket ID。Ticket ID 須指向存在的票。

格式：
  ticket track set-closed-by <id> --value <ticket-id|none|owner/repo#N> [--version <v>]
"""

if __name__ == "__main__":
    import sys
    print("[ERROR] 此檔案不支援直接執行，請使用 ticket track set-closed-by")
    sys.exit(1)


import argparse
import sys as _sys
from pathlib import Path

from ticket_system.constants import STATUS_CLOSED
from ticket_system.lib.close_resolution_check import check_closed_by
from ticket_system.lib.file_lock import file_lock
from ticket_system.lib.ticket_loader import get_ticket_path, load_ticket, save_ticket
from ticket_system.lib.ticket_ops import (
    load_and_validate_ticket,
    resolve_ticket_path,
)


def execute_set_closed_by(args: argparse.Namespace, version: str) -> int:
    """
    修正 closed 票的 closed_by 欄位（closed 態欄位修正入口）。

    僅允許對 status=closed 的票操作（closed_by 只在 closed 狀態下有意義）。
    新值須落在該票 close_reason 允許的值域內（與 close 同一個驗證函式），
    禁止填入代理人名稱等非引用值。
    修正動作輸出既有值與新值，並走 auto-commit 使 git log 可追溯
    （與 set-acceptance 同保護等級）。
    """
    ticket_id = args.ticket_id
    new_value = args.value

    lock_target = Path(get_ticket_path(version, ticket_id))
    with file_lock(lock_target):
        ticket, load_error = load_and_validate_ticket(version, ticket_id)
        if load_error:
            return 1

        status = ticket.get("status", "")
        if status != STATUS_CLOSED:
            print(
                f"[Error] set-closed-by 僅適用 status=closed 的票，"
                f"{ticket_id} 現況為 {status!r}"
            )
            return 1

        error = check_closed_by(ticket.get("close_reason"), new_value, load_ticket)
        if error:
            print(f"{error}（--value）")
            return 1

        old_value = ticket.get("closed_by", "")
        if old_value == new_value:
            print(f"[INFO] {ticket_id} 的 closed_by 已是 {new_value!r}，無需修改")
            return 0

        ticket["closed_by"] = new_value
        ticket_path = resolve_ticket_path(ticket, version, ticket_id)
        save_ticket(ticket, ticket_path)

        from ticket_system.lib import git_utils
        commit_failed = git_utils.commit_ticket_md_reporting(
            "set-closed-by", str(ticket_path), ticket_id, "closed_by",
            operation="set-closed-by",
        )

    print(f"[OK] {ticket_id} 的 closed_by 已修正")
    print(f"   舊值: {old_value!r}")
    print(f"   新值: {new_value!r}")
    return git_utils.EXIT_AUTO_COMMIT_FAILED if commit_failed else 0
