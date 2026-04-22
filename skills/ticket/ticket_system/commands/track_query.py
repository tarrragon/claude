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
    from ticket_system.lib.ui_constants import SEPARATOR_PRIMARY
    print(SEPARATOR_PRIMARY)
    print("[ERROR] 此檔案不支援直接執行")
    print(SEPARATOR_PRIMARY)
    print()
    print("正確使用方式：")
    print("  ticket track summary")
    print("  ticket track claim 0.31.0-W4-001")
    print()
    print("如尚未安裝，請執行：")
    print("  cd .claude/skills/ticket && uv tool install .")
    print()
    print("詳見 SKILL.md")
    print(SEPARATOR_PRIMARY)
    sys.exit(1)



import argparse
import re
import sys
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
from ticket_system.lib.staleness import (
    format_stale_warning,
    format_stale_list_summary,
    calculate_stale_level,
    LEVEL_WARNING,
    LEVEL_CRITICAL,
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
    SEPARATOR_PRIMARY,
    EXECUTION_LOG_PATTERN,
    DOTALL_FLAG,
    VERSION_PREFIX,
    VERSION_PREFIX_LENGTH,
)
from ticket_system.lib.ticket_ops import (
    load_and_validate_ticket,
)

# 狀態值映射
STATUS_MAP = {
    "pending": STATUS_PENDING,
    "in_progress": STATUS_IN_PROGRESS,
    "completed": STATUS_COMPLETED,
    "blocked": STATUS_BLOCKED,
}

# argparser flag（--pending/--in-progress/--completed/--blocked）對應的狀態值
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


def _format_where_field(where_value) -> str:
    """格式化 where 欄位顯示值（支援 dict 和 str 兩種格式）。"""
    if isinstance(where_value, dict):
        return where_value.get("layer", DEFAULT_UNKNOWN_VALUE)
    return where_value if where_value else DEFAULT_UNKNOWN_VALUE


def execute_query(args: argparse.Namespace, version: str) -> int:
    """查詢單一 Ticket"""
    ticket, error = load_and_validate_ticket(version, args.ticket_id)
    if error:
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
    print(f"{SECTION_5W1H_INDENT}Where: {_format_where_field(ticket.get('where'))}")
    print(f"{SECTION_5W1H_INDENT}Why: {ticket.get('why', DEFAULT_UNKNOWN_VALUE)}")

    # W15-003: 顯示 spawned_tickets 完成進度（僅對 ANA 類型有意義，但一律顯示）
    spawned = ticket.get("spawned_tickets") or []
    if spawned:
        completed_ids: List[str] = []
        incomplete_items: List[str] = []
        for sid in spawned:
            sub = load_ticket(version, sid)
            if not sub:
                incomplete_items.append(f"{sid} (not_found)")
                continue
            sub_status = sub.get("status", "unknown")
            if sub_status == STATUS_COMPLETED:
                completed_ids.append(sid)
            else:
                incomplete_items.append(f"{sid} (status={sub_status})")
        total = len(spawned)
        done = len(completed_ids)
        print(f"\n[Spawned IMPs 進度] {done}/{total} completed")
        for sid in completed_ids:
            print(f"  [x] {sid}")
        for item in incomplete_items:
            print(f"  [ ] {item}")

    # PROP-010 方案 4：query 時輸出 stale 警告（靜默失敗）
    try:
        level = calculate_stale_level(ticket.get("created"))
        # query 只在 WARNING / CRITICAL 時輸出（AC：超過 14 天輸出 WARNING）
        if level in (LEVEL_WARNING, LEVEL_CRITICAL):
            msg = format_stale_warning(ticket)
            if msg:
                print()
                print(msg)
    except Exception as exc:
        sys.stderr.write(f"[staleness] query stale 檢查異常：{exc}\n")

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
    ticket, error = load_and_validate_ticket(version, args.ticket_id)
    if error:
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
    ticket, error = load_and_validate_ticket(version, args.ticket_id)
    if error:
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


def _collect_spawned_tree(
    ticket_id: str,
    version: str,
    visited: set,
    depth: int,
    lines: List[str],
) -> None:
    """
    遞迴收集 spawned_tickets 樹狀結構到 lines。

    Args:
        ticket_id: 當前節點 Ticket ID
        version: 版本號（用於載入子 Ticket）
        visited: 已造訪集合，用於循環引用防護
        depth: 縮排深度（每層 2 空格）
        lines: 輸出行累積器
    """
    indent = "  " * depth
    if ticket_id in visited:
        lines.append(f"{indent}- {ticket_id} [CYCLE DETECTED, skipped]")
        return
    visited.add(ticket_id)

    sub = load_ticket(version, ticket_id)
    if not sub:
        lines.append(f"{indent}- {ticket_id} (not_found)")
        return

    status = sub.get("status", "unknown")
    title = sub.get("title", "")
    ttype = sub.get("type", "?")
    lines.append(f"{indent}- {ticket_id} [{status}] ({ttype}) {title}")

    children_spawned = sub.get("spawned_tickets") or []
    for child_id in children_spawned:
        _collect_spawned_tree(child_id, version, visited, depth + 1, lines)


REFLECTION_CHAIN_WARN_THRESHOLD = 3


def _compute_reflection_chain_depth(
    ticket: Dict[str, Any],
    version: str,
) -> tuple:
    """
    計算 ANA 反思鏈深度（沿 source_ticket 祖鏈回溯，計算連續 ANA type 的長度）。

    反思鏈定義：從當前 Ticket 出發，沿 source_ticket 欄位往上回溯，
    連續遇到的 ANA type Ticket 數量（包含當前 Ticket，若當前為 ANA）。
    遇到非 ANA type 或無 source_ticket 即停止。

    Args:
        ticket: 當前 Ticket 資料
        version: 版本號（用於載入祖鏈 Ticket）

    Returns:
        (depth, chain): depth=連續 ANA 層數；chain=[ticket_id, ...] 由遠到近
    """
    chain: List[str] = []
    visited: set = set()
    current = ticket
    while current and current.get("type") == "ANA":
        cid = current.get("id") or current.get("_id") or ""
        if cid in visited:
            break
        visited.add(cid)
        chain.append(cid)
        source_id = current.get("source_ticket")
        if not source_id:
            break
        current = load_ticket(version, source_id)
    chain.reverse()  # 由遠到近
    return len(chain), chain


def execute_deps(args: argparse.Namespace, version: str) -> int:
    """
    顯示 Ticket 衍生關係（spawned_tickets + source_ticket）。

    與 tree/chain（純血緣語意：parent_id/children/chain）分離，對齊業界慣例
    （Jira/Linear/GitHub）血緣與衍生分離展示。

    輸出：
    - 目標 Ticket 基本資訊
    - Spawned IMPs 遞迴樹狀展開（含循環引用防護）
    - Source ticket（若存在）
    """
    ticket, error = load_and_validate_ticket(version, args.ticket_id)
    if error:
        return 1

    if _check_yaml_error(ticket, args.ticket_id):
        return 1

    ticket_id = args.ticket_id
    title = ticket.get("title", "")
    ttype = ticket.get("type", "?")
    status = ticket.get("status", "unknown")

    print(f"{ticket_id} [{status}] ({ttype}) {title}")
    print(SEPARATOR_CHAR * SEPARATOR_WIDTH)

    # 反思鏈深度警示（Layer 2，W15-010/W15-021）：
    # 僅對 ANA type Ticket 計算沿 source_ticket 連續 ANA 祖鏈長度
    reflection_depth, reflection_chain = _compute_reflection_chain_depth(ticket, version)
    print(f"\nReflection Chain Depth: {reflection_depth}")
    if reflection_depth >= REFLECTION_CHAIN_WARN_THRESHOLD:
        chain_repr = " -> ".join(reflection_chain)
        print(
            f"[WARNING] 反思鏈深度 = {reflection_depth}"
            f"（ANA spawn ANA 連續 {reflection_depth} 層）"
        )
        print(f"          鏈: {chain_repr}")
        print(
            "          建議：評估是否繼續反思或終止（參見 W15-010 Layer 2 終止條件）"
        )

    # Spawned tickets（遞迴樹狀）
    spawned = ticket.get("spawned_tickets") or []
    print(f"\nSpawned Tickets ({len(spawned)}):")
    if not spawned:
        print("  （無）")
    else:
        visited: set = {ticket_id}  # 將自身加入 visited 防自引用
        lines: List[str] = []
        for child_id in spawned:
            _collect_spawned_tree(child_id, version, visited, 1, lines)
        for line in lines:
            print(line)

    # Source ticket
    source_id = ticket.get("source_ticket")
    print(f"\nSource Ticket:")
    if not source_id:
        print("  （無）")
    else:
        src = load_ticket(version, source_id)
        if not src:
            print(f"  - {source_id} (not_found)")
        else:
            src_status = src.get("status", "unknown")
            src_type = src.get("type", "?")
            src_title = src.get("title", "")
            print(f"  - {source_id} [{src_status}] ({src_type}) {src_title}")

    return 0


def execute_full(args: argparse.Namespace, version: str) -> int:
    """顯示 Ticket 完整內容"""
    ticket, error = load_and_validate_ticket(version, args.ticket_id)
    if error:
        return 1

    if _check_yaml_error(ticket, args.ticket_id):
        return 1

    # 重建檔案內容（YAML frontmatter + body）
    import yaml

    # 複製 dict 以避免修改原始資料
    frontmatter = {k: v for k, v in ticket.items() if not k.startswith("_")}
    body = ticket.get("_body", "")

    # 產出 frontmatter
    frontmatter_yaml = yaml.dump(
        frontmatter,
        allow_unicode=True,
        default_flow_style=False,
        sort_keys=False,
    )

    # 組合完整內容
    full_content = f"---\n{frontmatter_yaml}---\n\n{body}"

    print(full_content)
    return 0


def execute_log(args: argparse.Namespace, version: str) -> int:
    """顯示執行日誌區塊"""
    ticket, error = load_and_validate_ticket(version, args.ticket_id)
    if error:
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
    # 使用 args.version_str（命令行位置參數）
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
    # --version all: 跨版本查詢所有 Tickets（W9-002）
    if version == "all":
        return _execute_list_all_versions(args)

    # 當 --wave 指定但未明確指定 --version 時，搜尋所有 active 版本
    wave_value = getattr(args, "wave", None)
    explicit_version = getattr(args, "version", None)

    if wave_value is not None and not explicit_version:
        return _execute_list_cross_version(args, version, wave_value)

    return _execute_list_single_version(args, version, wave_value)


def _execute_list_all_versions(args: argparse.Namespace) -> int:
    """跨所有版本列出 Tickets（--version all，W9-002）"""
    from ticket_system.lib.version import get_active_versions

    active_versions = get_active_versions()
    if not active_versions:
        print(format_warning(WarningMessages.NO_TICKETS))
        return 0

    status_filters = _build_status_filters(args)
    wave_value = getattr(args, "wave", None)
    output_format = getattr(args, "format", "table")
    found_any = False

    for ver in sorted(active_versions):
        ver_clean = ver.lstrip("v")
        all_tickets = list_tickets(ver_clean)
        if not all_tickets:
            continue

        filtered = all_tickets
        if status_filters:
            filtered = [t for t in filtered if t.get("status") in status_filters]
        if wave_value is not None:
            filtered = [t for t in filtered if t.get("wave") == wave_value]

        if filtered:
            found_any = True
            _output_tickets(filtered, ver_clean, output_format)

    if not found_any:
        print(format_warning(WarningMessages.NO_TICKETS))
    return 0


def _execute_list_cross_version(
    args: argparse.Namespace, default_version: str, wave_value: int
) -> int:
    """跨版本搜尋 Wave — 當未指定 --version 時嘗試所有 active 版本"""
    from ticket_system.lib.version import get_active_versions

    active_versions = get_active_versions()
    # 標準化版本號（移除 v 前綴）
    candidates = [v.lstrip("v") for v in active_versions] if active_versions else [default_version]

    status_filters = _build_status_filters(args)

    # 聚合所有版本的結果（不止第一個匹配版本）
    all_filtered = []
    matched_versions = []
    for ver in candidates:
        all_tickets = list_tickets(ver)
        if not all_tickets:
            continue

        filtered = all_tickets
        if status_filters:
            filtered = [t for t in filtered if t.get("status") in status_filters]
        filtered = [t for t in filtered if t.get("wave") == wave_value]

        if filtered:
            all_filtered.extend(filtered)
            matched_versions.append(ver)

    if all_filtered:
        output_format = getattr(args, "format", "table")
        display_version = ", ".join(matched_versions) if matched_versions else default_version
        return _output_tickets(all_filtered, display_version, output_format)

    print(format_warning(WarningMessages.NO_TICKETS))
    return 0


def _execute_list_single_version(
    args: argparse.Namespace, version: str, wave_value: Optional[int]
) -> int:
    """單一版本列表（原始邏輯，用於明確指定 --version 時）"""
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
    # 優先使用 --status 參數（支援單值或多值）
    status_values = getattr(args, "status", None)
    if status_values:
        return {STATUS_MAP[v] for v in status_values if v in STATUS_MAP}

    # 其次檢查舊 flag（向後相容）
    status_filters = set()
    for flag_name, status in FLAG_TO_STATUS.items():
        if getattr(args, flag_name, False):
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

    # PROP-010 方案 4：list 標示 stale Ticket 數量（靜默失敗）
    try:
        summary = format_stale_list_summary(tickets)
        if summary:
            print()
            print(summary)
    except Exception as exc:
        sys.stderr.write(f"[staleness] list stale 摘要異常：{exc}\n")

    return 0


def execute_search(args: argparse.Namespace, version: str) -> int:
    """搜尋 Tickets — 依 UC/Spec/Prop 引用或檔案路徑（W9-002）"""
    ref_query = getattr(args, "ref", None)
    file_query = getattr(args, "file_path", None)

    if not ref_query and not file_query:
        print(format_error("必須指定 --ref 或 --file 搜尋條件"))
        return 1

    from ticket_system.lib.version import get_active_versions

    # 決定搜尋範圍
    if version == "all":
        versions = [v.lstrip("v") for v in get_active_versions()]
    else:
        versions = [version]

    output_format = getattr(args, "format", "table")
    matched_tickets = []

    for ver in sorted(versions):
        all_tickets = list_tickets(ver)
        if not all_tickets:
            continue

        for ticket in all_tickets:
            if _ticket_matches_search(ticket, ref_query, file_query):
                matched_tickets.append(ticket)

    if not matched_tickets:
        search_term = ref_query or file_query
        print(format_warning(f"未找到匹配 '{search_term}' 的 Tickets"))
        return 0

    # 輸出結果
    print(f"[Search] 找到 {len(matched_tickets)} 個匹配的 Tickets")
    print(SEPARATOR_CHAR * SEPARATOR_WIDTH)
    formatted = format_ticket_list(matched_tickets, include_who=True)
    if formatted:
        print(formatted)

    return 0


def _ticket_matches_search(
    ticket: dict, ref_query: Optional[str], file_query: Optional[str]
) -> bool:
    """檢查 Ticket 是否匹配搜尋條件"""
    if ref_query:
        ref_upper = ref_query.upper()
        # 搜尋 where.files、why、what、title 中的引用
        where = ticket.get("where", {})
        files = where.get("files", []) if isinstance(where, dict) else []
        searchable_text = " ".join([
            ticket.get("title", ""),
            ticket.get("what", ""),
            ticket.get("why", ""),
            " ".join(str(f) for f in files),
        ]).upper()
        return ref_upper in searchable_text

    if file_query:
        where = ticket.get("where", {})
        files = where.get("files", []) if isinstance(where, dict) else []
        file_lower = file_query.lower()
        return any(file_lower in str(f).lower() for f in files)

    return False
