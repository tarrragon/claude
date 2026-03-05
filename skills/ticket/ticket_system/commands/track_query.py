"""
Ticket track 查詢操作模組

負責處理所有與查詢相關的 track 子命令：
- query: 查詢單一 Ticket
- summary: 快速摘要
- tree: 任務鏈樹狀結構
- chain: 完整任務鏈
- full: 完整內容顯示
- log: 執行日誌顯示
- list: Ticket 列表
- version: 版本進度摘要
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
import re
from pathlib import Path
from typing import Any, Dict, List, Optional

from ticket_system.lib.constants import (
    STATUS_PENDING,
    STATUS_IN_PROGRESS,
    STATUS_COMPLETED,
    STATUS_BLOCKED,
    WORK_LOGS_DIR,
)
from ticket_system.lib.ticket_loader import (
    list_tickets,
    load_ticket,
)
from ticket_system.lib.paths import get_project_root
from ticket_system.lib.ticket_formatter import (
    format_ticket_summary,
    format_ticket_list,
    get_ticket_stats,
    format_ticket_stats,
    format_ticket_tree,
)
from ticket_system.lib.messages import (
    ErrorMessages,
    WarningMessages,
    format_error,
    format_warning,
)
from ticket_system.lib.command_tracking_messages import (
    TrackQueryMessages,
    format_msg,
)
from ticket_system.lib.ui_constants import (
    DEFAULT_UNKNOWN_VALUE,
    SECTION_5W1H_TITLE,
    SECTION_5W1H_INDENT,
    SEPARATOR_CHAR,
    SEPARATOR_WIDTH,
    EXECUTION_LOG_PATTERN,
    DOTALL_FLAG,
    VERSION_PREFIX,
    VERSION_PREFIX_LENGTH,
)

# 狀態值映射
STATUS_MAP = {
    "pending": STATUS_PENDING,
    "in_progress": STATUS_IN_PROGRESS,
    "completed": STATUS_COMPLETED,
    "blocked": STATUS_BLOCKED,
}

# 舊 flag 到狀態值映射
FLAG_TO_STATUS = {
    "pending": STATUS_PENDING,
    "in_progress": STATUS_IN_PROGRESS,
    "completed": STATUS_COMPLETED,
    "blocked": STATUS_BLOCKED,
}


# ============================================================================
# 輔助函式
# ============================================================================

def _check_yaml_error(ticket: Optional[Dict[str, Any]], ticket_id: str) -> bool:
    """
    檢查 Ticket 是否有 YAML 解析錯誤。

    若有錯誤，直接印出錯誤訊息並返回 True。

    Args:
        ticket: load_ticket() 回傳的 Ticket 字典
        ticket_id: Ticket ID（用於錯誤訊息）

    Returns:
        bool: True 表示有錯誤，False 表示無錯誤
    """
    if ticket and "_yaml_error" in ticket:
        print(format_error(
            format_msg(TrackQueryMessages.YAML_ERROR_FORMAT, ticket_id=ticket_id, error=ticket['_yaml_error'])
        ))
        return True
    return False


def _print_cross_version_warning(current_version: str) -> None:
    """
    掃描所有版本，若其他版本有未完成的 Ticket 則印出警告。

    Args:
        current_version: 當前顯示的版本號（無 v 前綴，如 "0.3.0"）
    """
    root = get_project_root()
    work_logs = root / WORK_LOGS_DIR

    if not work_logs.exists():
        return

    version_pattern = re.compile(r"^v\d+\.\d+\.\d+$")
    current_v_prefix = f"v{current_version}"

    warnings = []
    for version_dir in sorted(work_logs.iterdir()):
        if not version_dir.is_dir() or not version_pattern.match(version_dir.name):
            continue
        if version_dir.name == current_v_prefix:
            continue

        version_str = version_dir.name[1:]  # 移除 v 前綴
        tickets = list_tickets(version_str)
        if not tickets:
            continue

        pending_count = sum(1 for t in tickets if t.get("status") == STATUS_PENDING)
        in_progress_count = sum(1 for t in tickets if t.get("status") == STATUS_IN_PROGRESS)

        if pending_count > 0 or in_progress_count > 0:
            warnings.append(format_msg(
                TrackQueryMessages.CROSS_VERSION_WARNING_ITEM,
                version=version_str,
                pending=pending_count,
                in_progress=in_progress_count,
            ))

    if warnings:
        print()
        print(TrackQueryMessages.CROSS_VERSION_WARNING_HEADER)
        for line in warnings:
            print(line)
        print(TrackQueryMessages.CROSS_VERSION_WARNING_HINT)


def execute_query(args: argparse.Namespace, version: str) -> int:
    """查詢單一 Ticket"""
    ticket = load_ticket(version, args.ticket_id)
    if not ticket:
        print(format_error(ErrorMessages.TICKET_NOT_FOUND, ticket_id=args.ticket_id))
        return 1

    if _check_yaml_error(ticket, args.ticket_id):
        return 1

    summary = format_ticket_summary(ticket, include_elapsed=True)
    print(summary)

    # 顯示詳細資訊
    print(f"\n{SECTION_5W1H_TITLE}")
    who = ticket.get("who", DEFAULT_UNKNOWN_VALUE)
    if isinstance(who, dict):
        print(f"{SECTION_5W1H_INDENT}Who: {who.get('current', DEFAULT_UNKNOWN_VALUE)}")
    else:
        print(f"{SECTION_5W1H_INDENT}Who: {who}")

    print(f"{SECTION_5W1H_INDENT}What: {ticket.get('what', DEFAULT_UNKNOWN_VALUE)}")
    print(f"{SECTION_5W1H_INDENT}When: {ticket.get('when', DEFAULT_UNKNOWN_VALUE)}")
    print(f"{SECTION_5W1H_INDENT}Where: {ticket.get('where', {}).get('layer', DEFAULT_UNKNOWN_VALUE) if isinstance(ticket.get('where'), dict) else ticket.get('where', DEFAULT_UNKNOWN_VALUE)}")
    print(f"{SECTION_5W1H_INDENT}Why: {ticket.get('why', DEFAULT_UNKNOWN_VALUE)}")

    return 0


def execute_summary(args: argparse.Namespace, version: str) -> int:
    """快速摘要"""
    tickets = list_tickets(version)

    if not tickets:
        print(format_msg(TrackQueryMessages.SUMMARY_NO_TICKETS_TITLE, version=version))
        print(TrackQueryMessages.NO_TICKETS_MESSAGE)
        _print_cross_version_warning(version)
        return 0

    stats = get_ticket_stats(tickets)

    print(format_msg(TrackQueryMessages.SUMMARY_TITLE, version=version, completed=stats['completed'], total=stats['total']))
    print(f"   {format_ticket_stats(stats)}")
    print(SEPARATOR_CHAR * SEPARATOR_WIDTH)

    # 顯示 Ticket 列表
    formatted = format_ticket_list(tickets, include_who=True)
    if formatted:
        print(formatted)

    _print_cross_version_warning(version)

    return 0


def execute_tree(args: argparse.Namespace, version: str) -> int:
    """顯示任務鏈樹狀結構"""
    ticket = load_ticket(version, args.ticket_id)
    if not ticket:
        print(format_error(ErrorMessages.TICKET_NOT_FOUND, ticket_id=args.ticket_id))
        return 1

    if _check_yaml_error(ticket, args.ticket_id):
        return 1

    # 取得所有 Tickets 用於構建樹狀結構
    all_tickets = list_tickets(version)

    # 格式化並輸出樹狀結構
    tree_output = format_ticket_tree(all_tickets, root_id=args.ticket_id)
    print(tree_output)

    return 0


def execute_chain(args: argparse.Namespace, version: str) -> int:
    """顯示完整任務鏈（從 root 到所有 leaf）"""
    ticket = load_ticket(version, args.ticket_id)
    if not ticket:
        print(format_error(ErrorMessages.TICKET_NOT_FOUND, ticket_id=args.ticket_id))
        return 1

    if _check_yaml_error(ticket, args.ticket_id):
        return 1

    # 從 chain 欄位取得 root
    chain_info = ticket.get("chain", {})
    root_id = chain_info.get("root")

    if not root_id:
        print(format_warning(WarningMessages.TICKET_CHAIN_ROOT_NOT_FOUND, ticket_id=args.ticket_id))
        print(f"   {TrackQueryMessages.CHAIN_ROOT_NOT_FOUND_HINT}")
        root_id = args.ticket_id

    # 取得所有 Tickets 用於構建樹狀結構
    all_tickets = list_tickets(version)

    # 格式化並輸出樹狀結構
    tree_output = format_ticket_tree(all_tickets, root_id=root_id)
    print(tree_output)

    return 0


def execute_full(args: argparse.Namespace, version: str) -> int:
    """顯示 Ticket 完整內容"""
    ticket = load_ticket(version, args.ticket_id)
    if not ticket:
        print(format_error(ErrorMessages.TICKET_NOT_FOUND, ticket_id=args.ticket_id))
        return 1

    if _check_yaml_error(ticket, args.ticket_id):
        return 1

    # 重建檔案內容（YAML frontmatter + body）
    import yaml

    # 分離特殊欄位
    body = ticket.pop("_body", "")
    ticket.pop("_path", None)

    # 產出 frontmatter
    frontmatter_yaml = yaml.dump(
        ticket,
        allow_unicode=True,
        default_flow_style=False,
        sort_keys=False,
    )

    # 組合完整內容
    full_content = f"---\n{frontmatter_yaml}---\n\n{body}"

    print(full_content)

    # 恢復特殊欄位
    if body:
        ticket["_body"] = body

    return 0


def execute_log(args: argparse.Namespace, version: str) -> int:
    """顯示執行日誌區塊"""
    ticket = load_ticket(version, args.ticket_id)
    if not ticket:
        print(format_error(ErrorMessages.TICKET_NOT_FOUND, ticket_id=args.ticket_id))
        return 1

    if _check_yaml_error(ticket, args.ticket_id):
        return 1

    # 從 _body 中提取 Execution Log 區塊
    body = ticket.get("_body", "")

    if not body:
        print(format_warning(WarningMessages.NO_BODY_CONTENT, ticket_id=args.ticket_id))
        return 0

    # 尋找 "# Execution Log" 區塊
    # 匹配 "# Execution Log" 及其後續內容
    # 直到遇到下一個 "#" 標題或檔案結束
    match = re.search(EXECUTION_LOG_PATTERN, body, re.DOTALL if DOTALL_FLAG else 0)

    if match:
        log_content = match.group(0)
        print(log_content)
        return 0
    else:
        print(format_warning(WarningMessages.NO_EXECUTION_LOG, ticket_id=args.ticket_id))
        return 0


def execute_version(args: argparse.Namespace, current_version: str) -> int:
    """顯示指定版本的進度摘要"""
    # 優先使用 args.version_str（命令行位置參數）
    # 次選 args.version_param（--version 選項）
    # 最後使用 current_version（自動偵測）
    target_version_str = args.version_str

    # 確保版本號格式正確
    if not target_version_str.startswith(VERSION_PREFIX):
        target_version_str = f"{VERSION_PREFIX}{target_version_str}"

    # 移除 v 前綴用於顯示和比對
    display_version = target_version_str[VERSION_PREFIX_LENGTH:] if target_version_str.startswith(VERSION_PREFIX) else target_version_str

    # 載入該版本的所有 Tickets
    tickets = list_tickets(target_version_str)

    if not tickets:
        print(format_msg(TrackQueryMessages.VERSION_NO_TICKETS_TITLE, display_version=display_version))
        print(TrackQueryMessages.NO_TICKETS_MESSAGE)
        return 0

    stats = get_ticket_stats(tickets)

    print(format_msg(TrackQueryMessages.VERSION_TITLE, display_version=display_version, completed=stats['completed'], total=stats['total']))
    print(f"   {format_ticket_stats(stats)}")
    print(SEPARATOR_CHAR * SEPARATOR_WIDTH)

    # 顯示 Ticket 列表
    formatted = format_ticket_list(tickets, include_who=True)
    if formatted:
        print(formatted)

    return 0


def execute_list(args: argparse.Namespace, version: str) -> int:
    """列出 Tickets，支援狀態篩選、Wave 篩選和多種輸出格式"""
    all_tickets = list_tickets(version)
    if not all_tickets:
        print(format_msg(TrackQueryMessages.LIST_NO_TICKETS_TITLE, version=version))
        print(TrackQueryMessages.NO_TICKETS_MESSAGE)
        _print_cross_version_warning(version)
        return 0

    # 應用狀態篩選（支援 --status 和 --pending 等 flag）
    status_filters = _build_status_filters(args)
    filtered_tickets = all_tickets
    if status_filters:
        filtered_tickets = [t for t in filtered_tickets if t.get("status") in status_filters]

    # 應用 Wave 篩選（如果指定）
    wave_value = getattr(args, "wave", None)
    if wave_value is not None:
        filtered_tickets = [t for t in filtered_tickets if t.get("wave") == wave_value]

    if not filtered_tickets:
        print(format_warning(WarningMessages.NO_TICKETS))
        return 0

    # 根據格式輸出
    output_format = getattr(args, "format", "table")
    result = _output_tickets(filtered_tickets, version, output_format)
    _print_cross_version_warning(version)
    return result


def _build_status_filters(args: argparse.Namespace) -> set:
    """
    構建狀態篩選集合。支援 --status 參數和舊 flag。

    Args:
        args: 命令列引數

    Returns:
        set: 狀態值集合
    """
    # 優先使用 --status 參數
    status_value = getattr(args, "status", None)
    if status_value and status_value in STATUS_MAP:
        return {STATUS_MAP[status_value]}

    # 其次檢查舊 flag（向後相容）
    status_filters = set()
    for flag_name, status in FLAG_TO_STATUS.items():
        if getattr(args, flag_name.replace("_", "_"), False):
            status_filters.add(status)

    return status_filters


def _output_tickets(tickets: list, version: str, output_format: str) -> int:
    """
    以指定格式輸出 Ticket 列表。

    Args:
        tickets: 篩選後的 Ticket 列表
        version: 版本號
        output_format: 輸出格式（table/ids/yaml）

    Returns:
        int: 退出碼
    """
    if output_format == "ids":
        return _output_ids(tickets)
    elif output_format == "yaml":
        return _output_yaml(tickets)
    else:
        # table 格式（預設）
        return _output_table(tickets, version)


def _output_ids(tickets: list) -> int:
    """只輸出 Ticket ID，一行一個"""
    for ticket in tickets:
        ticket_id = ticket.get("id") or ticket.get("ticket_id", "")
        if ticket_id:
            print(ticket_id)
    return 0


def _output_yaml(tickets: list) -> int:
    """以 YAML 格式輸出 Ticket 列表"""
    import yaml

    # 準備輸出資料（只包含關鍵欄位）
    output_data = []
    for ticket in tickets:
        ticket_data = {
            "id": ticket.get("id") or ticket.get("ticket_id", ""),
            "title": ticket.get("title", ""),
            "status": ticket.get("status", "pending"),
            "wave": ticket.get("wave", ""),
            "type": ticket.get("type", ""),
            "priority": ticket.get("priority", ""),
        }
        output_data.append(ticket_data)

    yaml_output = yaml.dump(
        output_data,
        allow_unicode=True,
        default_flow_style=False,
        sort_keys=False,
    )
    print(yaml_output)
    return 0


def _output_table(tickets: list, version: str) -> int:
    """以表格格式輸出 Ticket 列表（預設）"""
    stats = get_ticket_stats(tickets)
    print(format_msg(TrackQueryMessages.LIST_TITLE, version=version, completed=stats["completed"], total=stats["total"]))
    print(f"   {format_ticket_stats(stats)}")
    print(SEPARATOR_CHAR * SEPARATOR_WIDTH)

    # 顯示 Ticket 列表
    formatted = format_ticket_list(tickets, include_who=True)
    if formatted:
        print(formatted)

    return 0
