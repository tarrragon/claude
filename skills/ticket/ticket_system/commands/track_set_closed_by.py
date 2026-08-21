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

格式：
  ticket track set-closed-by <id> --value <ticket-id> [--version <v>]
"""

if __name__ == "__main__":
    import sys
    print("[ERROR] 此檔案不支援直接執行，請使用 ticket track set-closed-by")
    sys.exit(1)


import argparse
import sys as _sys
from pathlib import Path

from ticket_system.constants import STATUS_CLOSED, TICKET_ID_RE
from ticket_system.lib.file_lock import file_lock
from ticket_system.lib.ticket_loader import get_ticket_path, load_ticket, save_ticket
from ticket_system.lib.ticket_ops import (
    load_and_validate_ticket,
    resolve_ticket_path,
)


def _validate_new_closed_by(value: str) -> str:
    """驗證 --value 為合法且存在的 Ticket ID。

    Returns:
        錯誤訊息字串；驗證通過回傳空字串。
    """
    match = TICKET_ID_RE.match(value or "")
    if not match:
        return f"[Error] --value 須為合法 Ticket ID 格式，收到：{value!r}"
    resolved_version = match.group(1)
    if not load_ticket(resolved_version, value):
        return f"[Error] --value 指向的 Ticket 不存在：{value}"
    return ""


def execute_set_closed_by(args: argparse.Namespace, version: str) -> int:
    """
    修正 closed 票的 closed_by 欄位（closed 態欄位修正入口）。

    僅允許對 status=closed 的票操作（closed_by 只在 closed 狀態下有意義）。
    新值須為合法且存在的 Ticket ID，禁止填入代理人名稱等非 ticket 引用。
    修正動作輸出既有值與新值，並走 auto-commit 使 git log 可追溯
    （與 set-acceptance 同保護等級）。
    """
    ticket_id = args.ticket_id
    new_value = args.value

    error = _validate_new_closed_by(new_value)
    if error:
        print(error)
        return 1

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

        old_value = ticket.get("closed_by", "")
        if old_value == new_value:
            print(f"[INFO] {ticket_id} 的 closed_by 已是 {new_value!r}，無需修改")
            return 0

        ticket["closed_by"] = new_value
        ticket_path = resolve_ticket_path(ticket, version, ticket_id)
        save_ticket(ticket, ticket_path)

        from ticket_system.lib import git_utils
        try:
            commit_status = git_utils._auto_commit_ticket_md(
                str(ticket_path), ticket_id, "closed_by",
                operation="set-closed-by",
            )
            if commit_status in ("not_git_repo", "git_failed"):
                _sys.stderr.write(
                    f"[set-closed-by] auto-commit skipped（{commit_status}，非致命）；"
                    f"body 已保留 working tree，可手動 git commit 持久化。\n"
                )
        except Exception as exc:
            _sys.stderr.write(
                f"[set-closed-by] auto-commit 失敗（非致命，body 已保留 working tree）：{exc}\n"
            )

    print(f"[OK] {ticket_id} 的 closed_by 已修正")
    print(f"   舊值: {old_value!r}")
    print(f"   新值: {new_value!r}")
    return 0
