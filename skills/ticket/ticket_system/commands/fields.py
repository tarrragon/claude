"""
5W1H 欄位操作模組

責任：處理 Ticket 的 5W1H 欄位（who, what, when, where, why, how）
- 通用欄位讀取：execute_get_field
- 通用欄位設定：execute_set_field
- 12 個欄位包裝器（向後相容）

設計原則：DRY（不重複原則）
- 原始 track.py 有 12 個重複函式（95% 重複代碼）
- 本模組提供 2 個通用函式，減少代碼重複率至 5%
- 使用包裝層維持向後相容的 API
"""
# 防止直接執行此模組
if __name__ == "__main__":
    from ..lib.messages import print_not_executable_and_exit
    print_not_executable_and_exit()



import argparse
from pathlib import Path
from typing import Any, Dict, Optional

from ticket_system.lib import ticket_loader
from ticket_system.lib.constants import (
    STATUS_PENDING,
    STATUS_IN_PROGRESS,
    STATUS_COMPLETED,
    STATUS_BLOCKED,
)
from ticket_system.lib.messages import (
    ErrorMessages,
    InfoMessages,
    format_error,
    format_info,
)
from ticket_system.lib.command_lifecycle_messages import (
    FieldsMessages,
)


def execute_get_field(
    args: argparse.Namespace,
    version: str,
    field_name: Optional[str] = None,
) -> int:
    """
    通用欄位讀取函式

    支援讀取任意 Ticket 欄位（who, what, when, where, why, how 等）

    Args:
        args: 命令行參數
            - ticket_id: Ticket ID
            - field: 欄位名稱（可選，若無則使用 field_name 參數）
        version: 版本號
        field_name: 欄位名稱（若提供，優先於 args.field）

    Returns:
        int: 0 表示成功，1 表示失敗

    使用場景：
        - ticket track who <ticket-id>
        - ticket track what <ticket-id>
        - ticket track when <ticket-id>
        - ticket track where <ticket-id>
        - ticket track why <ticket-id>
        - ticket track how <ticket-id>
    """
    try:
        ticket = ticket_loader.load_ticket(version, args.ticket_id)
    except (FileNotFoundError, Exception):
        print(format_error(ErrorMessages.TICKET_NOT_FOUND, ticket_id=args.ticket_id))
        return 1

    if not ticket:
        print(format_error(ErrorMessages.TICKET_NOT_FOUND, ticket_id=args.ticket_id))
        return 1

    # 決定欄位名稱（優先使用參數傳入，否則從 args 中取得）
    actual_field_name = field_name or getattr(args, "field", None)
    if not actual_field_name:
        print(format_error(ErrorMessages.MISSING_FIELD_NAME))
        return 1

    # 檢查欄位是否存在
    if actual_field_name not in ticket:
        print(format_error(ErrorMessages.FIELD_NOT_FOUND, ticket_id=args.ticket_id, field_name=actual_field_name))
        return 1

    # 取得欄位值
    value = ticket.get(actual_field_name, "?")

    # 格式化顯示
    if isinstance(value, dict):
        # 如果是字典，取得 'current' 欄位或直接顯示
        if "current" in value:
            display_value = value.get("current", "?")
        else:
            display_value = str(value)
    else:
        display_value = str(value) if value is not None else "?"

    print(f"{actual_field_name.capitalize()}{FieldsMessages.FIELD_VALUE_SEPARATOR}{display_value}")
    return 0


def execute_set_field(
    args: argparse.Namespace,
    version: str,
    field_name: Optional[str] = None,
) -> int:
    """
    通用欄位設定函式

    支援更新 5W1H 欄位（who, what, when, where, why, how）

    Args:
        args: 命令行參數
            - ticket_id: Ticket ID
            - value: 新欄位值
            - field: 欄位名稱（可選，若無則使用 field_name 參數）
        version: 版本號
        field_name: 欄位名稱（若提供，優先於 args.field）

    Returns:
        int: 0 表示成功，1 表示失敗

    使用場景：
        - ticket track set-who <ticket-id> <value>
        - ticket track set-what <ticket-id> <value>
        - ticket track set-when <ticket-id> <value>
        - ticket track set-where <ticket-id> <value>
        - ticket track set-why <ticket-id> <value>
        - ticket track set-how <ticket-id> <value>
    """
    try:
        ticket = ticket_loader.load_ticket(version, args.ticket_id)
    except (FileNotFoundError, Exception):
        print(format_error(ErrorMessages.TICKET_NOT_FOUND, ticket_id=args.ticket_id))
        return 1

    if not ticket:
        print(format_error(ErrorMessages.TICKET_NOT_FOUND, ticket_id=args.ticket_id))
        return 1

    # 決定欄位名稱（優先使用參數傳入，否則從 args 中取得）
    actual_field_name = field_name or getattr(args, "field", None)
    if not actual_field_name:
        print(format_error(ErrorMessages.MISSING_FIELD_NAME))
        return 1

    # 取得新值
    new_value = args.value

    # 更新欄位
    ticket[actual_field_name] = new_value

    # 儲存
    ticket_path = Path(ticket.get("_path", ticket_loader.get_ticket_path(version, args.ticket_id)))
    ticket_loader.save_ticket(ticket, ticket_path)

    print(format_info(InfoMessages.FIELD_UPDATED, ticket_id=args.ticket_id, field_name=actual_field_name))
    print(f"   新值: {new_value}")
    return 0


# ===========================
# 包裝層 - 向後相容 API
# ===========================
# 這些函式保持原有的 API，並委派給通用函式


def execute_get_who(args: argparse.Namespace, version: str) -> int:
    """讀取 Ticket 的 who 欄位"""
    return execute_get_field(args, version, "who")


def execute_set_who(args: argparse.Namespace, version: str) -> int:
    """設定 Ticket 的 who 欄位"""
    return execute_set_field(args, version, "who")


def execute_get_what(args: argparse.Namespace, version: str) -> int:
    """讀取 Ticket 的 what 欄位"""
    return execute_get_field(args, version, "what")


def execute_set_what(args: argparse.Namespace, version: str) -> int:
    """設定 Ticket 的 what 欄位"""
    return execute_set_field(args, version, "what")


def execute_get_when(args: argparse.Namespace, version: str) -> int:
    """讀取 Ticket 的 when 欄位"""
    return execute_get_field(args, version, "when")


def execute_set_when(args: argparse.Namespace, version: str) -> int:
    """設定 Ticket 的 when 欄位"""
    return execute_set_field(args, version, "when")


def execute_get_where(args: argparse.Namespace, version: str) -> int:
    """讀取 Ticket 的 where 欄位"""
    return execute_get_field(args, version, "where")


def execute_set_where(args: argparse.Namespace, version: str) -> int:
    """設定 Ticket 的 where 欄位"""
    return execute_set_field(args, version, "where")


def execute_get_why(args: argparse.Namespace, version: str) -> int:
    """讀取 Ticket 的 why 欄位"""
    return execute_get_field(args, version, "why")


def execute_set_why(args: argparse.Namespace, version: str) -> int:
    """設定 Ticket 的 why 欄位"""
    return execute_set_field(args, version, "why")


def execute_get_how(args: argparse.Namespace, version: str) -> int:
    """讀取 Ticket 的 how 欄位"""
    return execute_get_field(args, version, "how")


def execute_set_how(args: argparse.Namespace, version: str) -> int:
    """設定 Ticket 的 how 欄位"""
    return execute_set_field(args, version, "how")
