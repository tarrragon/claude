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
from ticket_system.lib.ticket_ops import (
    load_and_validate_ticket,
    resolve_ticket_path,
)


DICT_FIELD_SUBKEY: Dict[str, str] = {
    "who": "current",
    "where": "layer",
    "how": "strategy",
}
"""dict 型欄位與主要子欄位的對應表（W10-086 修復）。

Why: set-who/set-where/set-how 應僅更新子欄位（current/layer/strategy），
保留 dict 其他 key（history/files/task_type）；原實作直接覆寫整個 dict 為 string，
導致後續 dict.get 操作 AttributeError。

How to apply: execute_set_field 依此表分流 dict 與 string 欄位的寫入邏輯。
"""


_DICT_FIELD_DEFAULTS: Dict[str, Dict[str, Any]] = {
    "who": {"current": "pending", "history": {}},
    "where": {"layer": "待定義", "files": []},
    "how": {"task_type": "Implementation", "strategy": "待定義"},
}


def _build_dict_field(field_name: str, subkey: str, new_value: Any) -> Dict[str, Any]:
    """為降級（原值已被壓扁為 string）/ 初始化場景重建完整 dict 結構。"""
    result = {k: v for k, v in _DICT_FIELD_DEFAULTS[field_name].items()}
    result[subkey] = new_value
    return result


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
    ticket, error = load_and_validate_ticket(version, args.ticket_id)
    if error:
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
    ticket, error = load_and_validate_ticket(version, args.ticket_id)
    if error:
        return 1

    # 決定欄位名稱（優先使用參數傳入，否則從 args 中取得）
    actual_field_name = field_name or getattr(args, "field", None)
    if not actual_field_name:
        print(format_error(ErrorMessages.MISSING_FIELD_NAME))
        return 1

    # 取得新值
    new_value = args.value

    # 更新欄位：dict 型欄位僅更新子欄位（W10-086 修復，防止壓扁 dict 為 string）
    if actual_field_name in DICT_FIELD_SUBKEY:
        subkey = DICT_FIELD_SUBKEY[actual_field_name]
        existing = ticket.get(actual_field_name)
        if isinstance(existing, dict):
            existing[subkey] = new_value
            ticket[actual_field_name] = existing
        else:
            ticket[actual_field_name] = _build_dict_field(actual_field_name, subkey, new_value)
    else:
        ticket[actual_field_name] = new_value

    # 儲存
    ticket_path = resolve_ticket_path(ticket, version, args.ticket_id)
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


def execute_set_priority(args: argparse.Namespace, version: str) -> int:
    """設定 Ticket 的 priority 欄位"""
    return execute_set_field(args, version, "priority")


def execute_add_acceptance(args: argparse.Namespace, version: str) -> int:
    """追加驗收條件到 Ticket"""
    ticket, error = load_and_validate_ticket(version, args.ticket_id)
    if error:
        return 1

    acceptance = ticket.get("acceptance") or []
    new_item = f"[ ] {args.value}"
    acceptance.append(new_item)
    ticket["acceptance"] = acceptance

    ticket_path = resolve_ticket_path(ticket, version, args.ticket_id)
    ticket_loader.save_ticket(ticket, ticket_path)

    print(format_info(InfoMessages.FIELD_UPDATED, ticket_id=args.ticket_id, field_name="acceptance"))
    print(f"   新增: {new_item}")
    print(f"   目前共 {len(acceptance)} 項")
    return 0


def execute_remove_acceptance(args: argparse.Namespace, version: str) -> int:
    """移除驗收條件（按 index，從 1 開始）"""
    import sys

    ticket, error = load_and_validate_ticket(version, args.ticket_id)
    if error:
        return 1

    acceptance = ticket.get("acceptance") or []
    index = args.index - 1

    if index < 0 or index >= len(acceptance):
        print(format_error(f"索引超出範圍：{args.index}（共 {len(acceptance)} 項）"), file=sys.stderr)
        return 1

    removed = acceptance.pop(index)
    ticket["acceptance"] = acceptance

    ticket_path = resolve_ticket_path(ticket, version, args.ticket_id)
    ticket_loader.save_ticket(ticket, ticket_path)

    print(format_info(InfoMessages.FIELD_UPDATED, ticket_id=args.ticket_id, field_name="acceptance"))
    print(f"   移除: {removed}")
    print(f"   剩餘 {len(acceptance)} 項")
    return 0


def execute_add_spawned(args: argparse.Namespace, version: str) -> int:
    """追加 spawned_tickets 項目"""
    ticket, error = load_and_validate_ticket(version, args.ticket_id)
    if error:
        return 1

    spawned = ticket.get("spawned_tickets") or []
    if args.value in spawned:
        print(format_info(InfoMessages.FIELD_UPDATED, ticket_id=args.ticket_id, field_name="spawned_tickets"))
        print(f"   已存在: {args.value}")
        return 0

    spawned.append(args.value)
    ticket["spawned_tickets"] = spawned

    ticket_path = resolve_ticket_path(ticket, version, args.ticket_id)
    ticket_loader.save_ticket(ticket, ticket_path)

    print(format_info(InfoMessages.FIELD_UPDATED, ticket_id=args.ticket_id, field_name="spawned_tickets"))
    print(f"   新增: {args.value}")
    print(f"   目前共 {len(spawned)} 項")
    return 0


def execute_set_decision_tree(args: argparse.Namespace, version: str) -> int:
    """設定 Ticket 的 decision_tree_path 欄位（3 個子欄位）"""
    ticket, error = load_and_validate_ticket(version, args.ticket_id)
    if error:
        return 1

    dt = ticket.get("decision_tree_path") or {}
    if args.entry:
        dt["entry_point"] = args.entry
    if args.decision:
        dt["final_decision"] = args.decision
    if args.rationale:
        dt["rationale"] = args.rationale

    ticket["decision_tree_path"] = dt

    ticket_path = resolve_ticket_path(ticket, version, args.ticket_id)
    ticket_loader.save_ticket(ticket, ticket_path)

    print(format_info(InfoMessages.FIELD_UPDATED, ticket_id=args.ticket_id, field_name="decision_tree_path"))
    for key, val in dt.items():
        print(f"   {key}: {val}")
    return 0
