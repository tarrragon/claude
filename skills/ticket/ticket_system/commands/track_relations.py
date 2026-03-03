"""
Ticket 關係和狀態管理模組

負責管理 Ticket 的父子關係、TDD Phase 和代理人派發等。
"""
# 防止直接執行此模組
if __name__ == "__main__":
    import sys
    print("=" * 60)
    print("[ERROR] 此檔案不支援直接執行")
    print("=" * 60)
    print()
    print("正確使用方式：")
    print("  ticket track summary")
    print("  ticket track claim 0.31.0-W4-001")
    print()
    print("如尚未安裝，請執行：")
    print("  cd .claude/skills/ticket && uv tool install .")
    print()
    print("詳見 SKILL.md")
    print("=" * 60)
    sys.exit(1)



import argparse
from pathlib import Path

from ticket_system.lib.constants import (
    STATUS_PENDING,
    STATUS_IN_PROGRESS,
    STATUS_COMPLETED,
    STATUS_BLOCKED,
)
from ticket_system.lib.ticket_loader import (
    get_ticket_path,
    list_tickets,
    load_ticket,
    save_ticket,
)
from ticket_system.lib.messages import (
    ErrorMessages,
    InfoMessages,
    AgentProgressMessages,
    format_error,
    format_info,
)
from ticket_system.lib.command_tracking_messages import (
    TrackRelationsMessages,
    format_msg,
)


def _normalize_ticket_id_list(value: str | list) -> list[str]:
    """
    標準化 Ticket ID 清單為列表

    將字符串或列表轉換為統一的列表格式。

    Args:
        value: Ticket ID 清單（字符串或列表）
               - 字符串：逗號或空格分隔
               - 列表：直接使用

    Returns:
        list[str]: 標準化的 ID 列表
    """
    if isinstance(value, str):
        # 支援逗號或空格分隔
        return [id_str.strip() for id_str in value.split(",") if id_str.strip()]
    elif isinstance(value, list):
        return value
    else:
        return []


def _execute_set_relation_field_replace(
    referenced_ids: list[str],
) -> list[str]:
    """替換模式：直接替換欄位值"""
    return referenced_ids


def _execute_set_relation_field_add(
    current_list: list[str],
    referenced_ids: list[str],
) -> list[str]:
    """追加模式：將 ID 加入列表（去重）"""
    new_value = current_list.copy()
    for ref_id in referenced_ids:
        if ref_id not in new_value:
            new_value.append(ref_id)
    return new_value


def _execute_set_relation_field_remove(
    current_list: list[str],
    referenced_ids: list[str],
) -> list[str]:
    """移除模式：從列表中移除指定的 ID"""
    return [id_str for id_str in current_list if id_str not in referenced_ids]


def _execute_set_relation_field(
    args: argparse.Namespace,
    version: str,
    field_name: str,
) -> int:
    """
    通用關係欄位設定函式

    支援 blockedBy 和 relatedTo 欄位的設定，包含三種模式：
    - replace（預設）：替換欄位值
    - --add：追加到欄位，去重
    - --remove：從欄位移除

    Args:
        args: 命令列參數
            - ticket_id: 目標 Ticket ID
            - value: 被引用的 Ticket ID（空格分隔或單個）
            - --add: 追加模式旗標
            - --remove: 移除模式旗標
        version: 版本號
        field_name: 欄位名稱 ("blockedBy" 或 "relatedTo")

    Returns:
        int: 0 表示成功，1 表示失敗
    """
    target_id = args.ticket_id

    # Step 1：載入目標 Ticket
    target_ticket = load_ticket(version, target_id)
    if not target_ticket:
        print(format_error(ErrorMessages.TICKET_NOT_FOUND, ticket_id=target_id))
        return 1

    # 解析被引用的 Ticket ID 清單
    value_str = args.value if hasattr(args, "value") else ""
    referenced_ids = [id_str.strip() for id_str in value_str.split() if id_str.strip()]

    # Step 2：驗證被引用 Ticket 存在（--remove 除外）
    is_remove_mode = getattr(args, "remove", False)
    if not is_remove_mode:
        for ref_id in referenced_ids:
            ref_ticket = load_ticket(version, ref_id)
            if not ref_ticket:
                print(format_error(ErrorMessages.TICKET_NOT_FOUND, ticket_id=ref_id))
                return 1

    # Step 3：取得並標準化目前欄位值
    current_value = target_ticket.get(field_name, [])
    current_list = _normalize_ticket_id_list(current_value)

    # Step 4：根據模式更新欄位值
    is_add_mode = getattr(args, "add", False)

    if is_remove_mode:
        new_value = _execute_set_relation_field_remove(current_list, referenced_ids)
    elif is_add_mode:
        new_value = _execute_set_relation_field_add(current_list, referenced_ids)
    else:
        new_value = _execute_set_relation_field_replace(referenced_ids)

    # Step 5：更新 Ticket 並保存
    target_ticket[field_name] = new_value

    ticket_path = Path(target_ticket.get("_path", get_ticket_path(version, target_id)))
    save_ticket(target_ticket, ticket_path)

    # Step 6：輸出成功訊息
    print(format_info(
        InfoMessages.FIELD_UPDATED,
        ticket_id=target_id,
        field_name=field_name,
    ))
    if new_value:
        print(f"  新值：{', '.join(new_value)}")
    else:
        print(f"  新值：（空）")

    return 0


def execute_set_blocked_by(args: argparse.Namespace, version: str) -> int:
    """
    設定 Ticket 的 blockedBy 欄位

    命令格式：ticket track set-blocked-by <ticket-id> <blocking-ids> [--add|--remove]

    Args:
        args: 命令列參數
        version: 版本號

    Returns:
        int: exit code
    """
    return _execute_set_relation_field(args, version, "blockedBy")


def execute_set_related_to(args: argparse.Namespace, version: str) -> int:
    """
    設定 Ticket 的 relatedTo 欄位

    命令格式：ticket track set-related-to <ticket-id> <related-ids> [--add|--remove]

    Args:
        args: 命令列參數
        version: 版本號

    Returns:
        int: exit code
    """
    return _execute_set_relation_field(args, version, "relatedTo")


def execute_add_child(args: argparse.Namespace, version: str) -> int:
    """
    建立 Ticket 父子關係

    命令格式：ticket track add-child <parent-id> <child-id>

    動作：
    1. 驗證父 Ticket 和子 Ticket 都存在
    2. 更新父 Ticket 的 children 陣列
    3. 更新子 Ticket 的 parent_id 欄位
    4. 避免重複添加
    """
    parent_id = args.parent_id
    child_id = args.child_id

    # Step 1：載入父 Ticket
    parent_ticket = load_ticket(version, parent_id)
    if not parent_ticket:
        print(format_error(ErrorMessages.TICKET_NOT_FOUND, ticket_id=parent_id))
        return 1

    # Step 2：載入子 Ticket
    child_ticket = load_ticket(version, child_id)
    if not child_ticket:
        print(format_error(ErrorMessages.TICKET_NOT_FOUND, ticket_id=child_id))
        return 1

    # Step 3：檢查是否已經是子 Ticket（避免重複）
    children = parent_ticket.get("children", [])
    if child_id in children:
        print(format_msg(TrackRelationsMessages.CHILD_ALREADY_EXISTS_FORMAT, child_id=child_id, parent_id=parent_id))
        return 0

    # Step 4：更新父 Ticket 的 children 陣列
    if "children" not in parent_ticket:
        parent_ticket["children"] = []
    parent_ticket["children"].append(child_id)

    # Step 5：更新子 Ticket 的 parent_id 欄位
    old_parent = child_ticket.get("parent_id")
    child_ticket["parent_id"] = parent_id

    # Step 6：更新 chain 欄位（如果存在）
    if "chain" not in child_ticket:
        child_ticket["chain"] = {}

    chain_info = child_ticket.get("chain", {})
    chain_info["parent"] = parent_id

    # 如果子 Ticket 有 root，維持不變；否則使用父的 root
    if "root" not in chain_info:
        parent_chain = parent_ticket.get("chain", {})
        parent_root = parent_chain.get("root", parent_id)
        chain_info["root"] = parent_root

    child_ticket["chain"] = chain_info

    # Step 7：保存父 Ticket
    parent_path = Path(parent_ticket.get("_path", get_ticket_path(version, parent_id)))
    save_ticket(parent_ticket, parent_path)

    # Step 8：保存子 Ticket
    child_path = Path(child_ticket.get("_path", get_ticket_path(version, child_id)))
    save_ticket(child_ticket, child_path)

    # Step 9：輸出成功訊息
    print(format_info(InfoMessages.CHILD_RELATION_CREATED))
    print(f"{TrackRelationsMessages.RELATION_PARENT_PREFIX} {parent_id}")
    print(f"{TrackRelationsMessages.RELATION_CHILD_PREFIX} {child_id}")
    if old_parent:
        print(f"{TrackRelationsMessages.RELATION_OLD_PARENT_PREFIX} {old_parent} {TrackRelationsMessages.RELATION_OLD_PARENT_SUFFIX}")

    return 0


def execute_phase(args: argparse.Namespace, version: str) -> int:
    """更新 Ticket 的 TDD Phase"""
    # 有效的 Phase 值
    VALID_PHASES = TrackRelationsMessages.VALID_PHASES

    ticket = load_ticket(version, args.ticket_id)
    if not ticket:
        print(format_error(ErrorMessages.TICKET_NOT_FOUND, ticket_id=args.ticket_id))
        return 1

    # 驗證 phase 參數
    phase = args.phase
    if phase not in VALID_PHASES:
        print(format_error(ErrorMessages.INVALID_PHASE_VALUE, phase=phase))
        print(f"{TrackRelationsMessages.PHASE_VALID_VALUES_PREFIX} {', '.join(VALID_PHASES)}")
        return 1

    # 更新 Ticket 欄位
    ticket["current_phase"] = phase
    ticket["assignee"] = args.agent

    ticket_path = Path(ticket.get("_path", get_ticket_path(version, args.ticket_id)))
    save_ticket(ticket, ticket_path)

    print(format_info(InfoMessages.PHASE_UPDATED, ticket_id=args.ticket_id))
    print(f"{TrackRelationsMessages.PHASE_PREFIX} {phase}")
    print(f"{TrackRelationsMessages.PHASE_ASSIGNEE_PREFIX} {args.agent}")
    return 0


def execute_agent(args: argparse.Namespace, version: str) -> int:
    """查詢特定代理人負責的所有 Tickets"""
    agent_name = args.agent_name.lower()
    all_tickets = list_tickets(version)

    if not all_tickets:
        print(format_info(AgentProgressMessages.AGENT_PROGRESS, agent_name=args.agent_name))
        print(TrackRelationsMessages.AGENT_SEPARATOR)
        print(AgentProgressMessages.NO_TICKETS)
        return 0

    # 過濾此代理人的 Tickets
    # 支援模糊匹配：parsley 可匹配 parsley-flutter-developer
    agent_tickets = []
    for ticket in all_tickets:
        # 從 assignee 或 who 欄位匹配代理人
        assignee = ticket.get("assignee", "").lower()
        who = ticket.get("who", "")
        if isinstance(who, dict):
            who = who.get("current", "").lower()
        else:
            who = str(who).lower()

        # 進行模糊匹配（子字串比對）
        if agent_name in assignee or agent_name in who:
            agent_tickets.append(ticket)

    # 按狀態分組
    pending_tickets = [t for t in agent_tickets if t.get("status") == STATUS_PENDING]
    in_progress_tickets = [t for t in agent_tickets if t.get("status") == STATUS_IN_PROGRESS]
    completed_tickets = [t for t in agent_tickets if t.get("status") == STATUS_COMPLETED]
    blocked_tickets = [t for t in agent_tickets if t.get("status") == STATUS_BLOCKED]

    # 顯示摘要
    print(format_info(AgentProgressMessages.AGENT_PROGRESS, agent_name=args.agent_name))
    print(TrackRelationsMessages.AGENT_SEPARATOR)
    print(format_info(AgentProgressMessages.TICKETS_COUNT, count=len(agent_tickets)))
    print()

    # 顯示進行中
    if in_progress_tickets:
        print(format_info(AgentProgressMessages.IN_PROGRESS, count=len(in_progress_tickets)))
        for ticket in in_progress_tickets:
            ticket_id = ticket.get("id", "?")
            ticket_type = ticket.get("type", "?")
            title = ticket.get("title", "?")
            print(f"{TrackRelationsMessages.AGENT_ITEM_PREFIX} {ticket_id}: [{ticket_type}] {title}")
    print()

    # 顯示待處理
    if pending_tickets:
        print(format_info(AgentProgressMessages.PENDING, count=len(pending_tickets)))
        for ticket in pending_tickets:
            ticket_id = ticket.get("id", "?")
            ticket_type = ticket.get("type", "?")
            title = ticket.get("title", "?")
            print(f"{TrackRelationsMessages.AGENT_ITEM_PREFIX} {ticket_id}: [{ticket_type}] {title}")
    print()

    # 顯示已完成
    if completed_tickets:
        print(format_info(AgentProgressMessages.COMPLETED, count=len(completed_tickets)))
        for ticket in completed_tickets:
            ticket_id = ticket.get("id", "?")
            ticket_type = ticket.get("type", "?")
            title = ticket.get("title", "?")
            print(f"{TrackRelationsMessages.AGENT_ITEM_PREFIX} {ticket_id}: [{ticket_type}] {title}")
    print()

    # 顯示被阻塞
    if blocked_tickets:
        print(format_info(AgentProgressMessages.BLOCKED, count=len(blocked_tickets)))
        for ticket in blocked_tickets:
            ticket_id = ticket.get("id", "?")
            ticket_type = ticket.get("type", "?")
            title = ticket.get("title", "?")
            print(f"{TrackRelationsMessages.AGENT_ITEM_PREFIX} {ticket_id}: [{ticket_type}] {title}")
        print()

    return 0
