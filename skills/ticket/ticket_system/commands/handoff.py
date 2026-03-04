"""
Ticket handoff 命令模組

負責任務交接功能，包含 Ticket 存在性強制檢查。
"""
# 防止直接執行此模組
if __name__ == "__main__":
    from ..lib.messages import print_not_executable_and_exit
    print_not_executable_and_exit()



import argparse
import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional

from ticket_system.lib.constants import (
    STATUS_IN_PROGRESS,
    STATUS_COMPLETED,
    STATUS_PENDING,
    STATUS_BLOCKED,
    HANDOFF_DIR,
    HANDOFF_PENDING_SUBDIR,
    HANDOFF_ARCHIVE_SUBDIR,
)
from ticket_system.lib.ticket_loader import (
    get_project_root,
    load_ticket,
    get_ticket_path,
    resolve_version,
    list_tickets,
)
from ticket_system.lib.ticket_validator import validate_ticket_id
from ticket_system.lib.messages import (
    ErrorMessages,
    WarningMessages,
    InfoMessages,
    SectionHeaders,
    format_error,
    format_warning,
    format_info,
)
from ticket_system.lib.command_lifecycle_messages import (
    HandoffMessages,
    format_msg,
)
from ticket_system.lib.chain_analyzer import ChainAnalyzer, Recommendation


# ============================================================================
# 輔助函式
# ============================================================================

def _check_yaml_error(ticket: Optional[Dict[str, Any]], ticket_id: str) -> bool:
    """
    檢查 Ticket 是否有 YAML 解析錯誤。

    Args:
        ticket: load_ticket() 回傳的 Ticket 字典
        ticket_id: Ticket ID（用於錯誤訊息）

    Returns:
        bool: True 表示有錯誤，False 表示無錯誤
    """
    if ticket and "_yaml_error" in ticket:
        print(format_error(
            f"Ticket {ticket_id} 的 YAML 格式錯誤：{ticket['_yaml_error']}"
        ))
        return True
    return False


def _verify_handoff_status(
    ticket: Dict[str, Any],
    ticket_id: str,
    context_refresh: bool = False,
) -> bool:
    """
    驗證 Ticket 是否可進行 handoff。

    允許的狀態：
    - 獨立任務（無 children）：
      - context_refresh=False：必須為 completed
      - context_refresh=True：允許 in_progress
    - 有 children 的父任務：允許 in_progress 或 completed

    Args:
        ticket: Ticket 資料
        ticket_id: Ticket ID（用於錯誤訊息）
        context_refresh: 是否為 context refresh handoff

    Returns:
        bool: True 表示可以 handoff，False 表示不可以
    """
    status = ticket.get("status")
    children = ticket.get("children", [])
    has_children: bool = bool(children)

    # 如果有 children，允許 in_progress 或 completed
    if has_children:
        if status in (STATUS_IN_PROGRESS, STATUS_COMPLETED):
            return True
    # 獨立任務（無 children）
    else:
        # context-refresh 允許 in_progress 狀態
        if context_refresh and status == STATUS_IN_PROGRESS:
            return True
        # 傳統 handoff 要求 completed 狀態
        if not context_refresh and status == STATUS_COMPLETED:
            return True

    # 狀態檢查失敗，輸出錯誤訊息
    print(format_error(
        f"Ticket {ticket_id} 無法執行 handoff"
    ))
    print()
    print(f"當前狀態：{status}")
    if has_children:
        print(f"需要狀態：{STATUS_IN_PROGRESS} 或 {STATUS_COMPLETED}")
    else:
        if context_refresh:
            print(f"需要狀態（context-refresh）：{STATUS_IN_PROGRESS}")
        else:
            print(f"需要狀態：{STATUS_COMPLETED}")
    print()
    print("說明：")
    if has_children:
        print("  有 children 的父任務允許在 in_progress 或 completed 時進行 handoff")
    elif context_refresh:
        print("  context-refresh 允許在 in_progress 時進行 handoff")
    else:
        print("  只有狀態為 'completed' 的獨立任務才能進行 handoff")
        print("  如要在 in_progress 時 handoff，使用 --context-refresh 旗標")
    print(f"  請先將此 Ticket 標記為適當的狀態")
    return False


def _verify_handoff_dependencies(ticket: Dict[str, Any], ticket_id: str, version: str) -> bool:
    """
    驗證 Ticket 的 blockedBy 依賴是否都已完成。

    Args:
        ticket: Ticket 資料
        ticket_id: Ticket ID（用於錯誤訊息）
        version: 版本號（用於載入依賴 Ticket）

    Returns:
        bool: True 表示所有依賴已完成，False 表示有未完成的依賴
    """
    blocked_by = ticket.get("blockedBy", [])

    # 若 blockedBy 是空列表或不存在，視為無依賴
    if not blocked_by:
        return True

    # 標準化 blockedBy：可能是字符串或列表
    if isinstance(blocked_by, str):
        blocked_by = [d.strip() for d in blocked_by.split(",") if d.strip()]
    elif not isinstance(blocked_by, list):
        blocked_by = []

    # 檢查每個依賴 Ticket 的狀態
    incomplete_deps = []
    for dep_id in blocked_by:
        dep_ticket = load_ticket(version, dep_id)
        if not dep_ticket:
            incomplete_deps.append(f"{dep_id} (未找到)")
        elif dep_ticket.get("status") != STATUS_COMPLETED:
            incomplete_deps.append(f"{dep_id} (狀態：{dep_ticket.get('status')})")

    # 若有未完成的依賴，輸出錯誤訊息
    if incomplete_deps:
        print(format_error(
            f"Ticket {ticket_id} 有未完成的阻塞依賴"
        ))
        print()
        print("阻塞依賴：")
        for dep in incomplete_deps:
            print(f"  - {dep}")
        print()
        print("說明：")
        print("  此 Ticket 被以下 Ticket 阻塞，無法執行 handoff")
        print("  請先完成這些依賴 Ticket")
        return False

    return True


def _check_all_acceptance_complete(ticket: Dict[str, Any]) -> bool:
    """
    檢查 Ticket 的所有驗收條件是否已全部勾選。

    驗收條件格式支援：
    - "[x] 項目" 表示完成
    - "[ ] 項目" 表示未完成
    - 無前綴的項目（舊格式）視為未完成

    Args:
        ticket: Ticket 資料

    Returns:
        bool: True 表示全部已勾選，False 表示有未完成項目或無驗收條件
    """
    from ticket_system.lib.ticket_validator import validate_acceptance_criteria

    acceptance_list = ticket.get("acceptance")
    if not acceptance_list:
        return False  # 無驗收條件，不觸發警告

    # 使用驗證工具檢查驗收條件
    all_complete, incomplete_items = validate_acceptance_criteria(ticket.get("id", ""), acceptance_list)
    return all_complete


def _warn_and_prompt_complete_before_handoff(
    ticket: Dict[str, Any],
    ticket_id: str,
    version: str,
    context_refresh: bool = False,
) -> int:
    """
    當所有驗收條件已完成但 status 仍為 in_progress 時，
    顯示警告並提供自動 complete 選項。

    防止 PC-003 錯誤：handoff 前未執行 complete，導致任務鏈狀態不一致。

    Args:
        ticket: Ticket 資料
        ticket_id: Ticket ID
        version: 版本號
        context_refresh: 是否為 context-refresh handoff

    Returns:
        int: 0 表示繼續 handoff（用戶跳過或 complete 成功）
             1 表示中止 handoff（complete 失敗）
    """
    status = ticket.get("status", "")

    # context-refresh 不需要檢查（允許 in_progress）
    if context_refresh:
        return 0

    # 只對 in_progress 的 ticket 做檢查
    if status != STATUS_IN_PROGRESS:
        return 0

    # 有未完成的驗收條件，不顯示警告
    if not _check_all_acceptance_complete(ticket):
        return 0

    # 所有驗收條件已勾選，但 status 仍 in_progress → 顯示警告
    print()
    print("[WARNING] 驗收條件前置檢查")
    print("=" * 60)
    print(f"  Ticket {ticket_id} 的所有驗收條件已勾選 [x]，")
    print(f"  但狀態仍為 in_progress。")
    print()
    print("  建議在 handoff 前先執行 complete，以確保任務鏈完整性。")
    print()
    print(f"  執行命令: ticket track complete {ticket_id}")
    print("=" * 60)
    print()

    # 詢問是否自動 complete
    if not _is_interactive():
        # 非互動環境下，顯示提示但不自動執行
        print("  在非互動環境下，請手動執行 complete 命令。")
        print("  或使用 --context-refresh 旗標跳過此檢查。")
        return 0

    try:
        response = input("  是否自動執行 complete 再繼續 handoff？[Y/n] ").strip().lower()
    except (EOFError, KeyboardInterrupt):
        response = "n"

    if response in ("", "y", "yes"):
        # 執行 complete
        from ticket_system.commands.lifecycle import execute_complete

        complete_args = argparse.Namespace(ticket_id=ticket_id, version=version)
        result = execute_complete(complete_args)

        if result != 0:
            print(f"[Error] complete 執行失敗，中止 handoff")
            return 1

        print(f"[OK] {ticket_id} 已完成，繼續 handoff...")
        return 0
    else:
        print("  已跳過 complete，繼續 handoff...")
        return 0


def _print_id_error() -> None:
    """列印 Ticket ID 格式錯誤訊息"""
    print(f"{ErrorMessages.INVALID_TICKET_ID}")
    print()
    print(HandoffMessages.ID_FORMAT_EXPECTED)
    print(HandoffMessages.ID_FORMAT_EXAMPLE)


def _print_version_error() -> None:
    """列印版本偵測錯誤訊息"""
    print(f"{ErrorMessages.VERSION_NOT_DETECTED}")
    print()
    print(HandoffMessages.VERSION_ERROR_REASONS)
    print(HandoffMessages.VERSION_ERROR_REASON_1)
    print(HandoffMessages.VERSION_ERROR_REASON_2)
    print()
    print(HandoffMessages.VERSION_ERROR_SOLUTION)
    print(HandoffMessages.VERSION_ERROR_SOLUTION_1)
    print(HandoffMessages.VERSION_ERROR_SOLUTION_EXAMPLE)


def _print_ticket_not_found_error(ticket_id: str, version: str) -> None:
    """列印 Ticket 不存在錯誤訊息"""
    print(format_warning(WarningMessages.BLOCKED_EXECUTION, ticket_id=ticket_id))
    print()
    print(HandoffMessages.TICKET_NOT_FOUND_REASONS)
    print(format_msg(HandoffMessages.TICKET_NOT_FOUND_REASON_1, version=version))
    print(HandoffMessages.TICKET_NOT_FOUND_REASON_2)
    print(HandoffMessages.TICKET_NOT_FOUND_REASON_3)
    print()
    print(HandoffMessages.TICKET_NOT_FOUND_SUGGESTIONS)
    print(HandoffMessages.TICKET_NOT_FOUND_SUGGESTION_1)
    print(format_msg(HandoffMessages.TICKET_NOT_FOUND_SUGGESTION_2, ticket_id=ticket_id, version=version))
    print(HandoffMessages.TICKET_NOT_FOUND_SUGGESTION_3)
    print()
    print(HandoffMessages.TICKET_NOT_FOUND_EXIT_CODE)


def _create_handoff_file_internal(ticket: Dict[str, Any], direction: str) -> int:
    """
    內部 handoff 檔案建立函式（供 lifecycle.py 內部調用）

    只建立檔案，不輸出任何訊息。

    Args:
        ticket: Ticket 資料
        direction: 交接方向 (to-parent, to-child, to-sibling, context-refresh)

    Returns:
        int: exit code (0 成功, 1 失敗)
    """
    root = get_project_root()
    handoff_dir = root / HANDOFF_DIR / HANDOFF_PENDING_SUBDIR
    handoff_dir.mkdir(parents=True, exist_ok=True)

    ticket_id = ticket.get("id")
    handoff_file = handoff_dir / f"{ticket_id}.json"

    handoff_data = {
        "ticket_id": ticket_id,
        "direction": direction,
        "timestamp": datetime.now().isoformat(),
        "from_status": ticket.get("status"),
        "title": ticket.get("title"),
        "what": ticket.get("what"),
        "chain": ticket.get("chain", {}),
        "resumed_at": None,  # 未接手時為 None，resume 時更新
    }

    try:
        with open(handoff_file, "w", encoding="utf-8") as f:
            json.dump(handoff_data, f, ensure_ascii=False, indent=2)
        return 0
    except (IOError, OSError):
        return 1


def _create_handoff_file(ticket: Dict[str, Any], direction: str) -> int:
    """
    建立 handoff 交接檔案

    Args:
        ticket: Ticket 資料
        direction: 交接方向 (to-parent, to-child, to-sibling)

    Returns:
        int: exit code
    """
    # 調用內部函式建立檔案
    exit_code = _create_handoff_file_internal(ticket, direction)

    if exit_code != 0:
        root = get_project_root()
        print(format_error(ErrorMessages.FILE_CREATION_FAILED, error="Unknown error"))
        return 1

    # 輸出成功訊息
    root = get_project_root()
    ticket_id = ticket.get("id")
    handoff_file = root / HANDOFF_DIR / HANDOFF_PENDING_SUBDIR / f"{ticket_id}.json"
    print(format_info(InfoMessages.HANDOFF_FILE_CREATED, path=str(handoff_file.relative_to(root))))
    print()
    print("=" * 60)
    print(InfoMessages.HANDOFF_NEXT_STEP)
    print("=" * 60)
    return 0


def _execute_handoff(args: argparse.Namespace) -> int:
    """
    執行 handoff 命令

    流程：
    1. 驗證 Ticket ID 格式
    2. 解析版本
    3. 驗證 Ticket 存在（exit code 2 如果不存在）
    4. 驗證互斥旗標（context-refresh 與方向旗標）
    5. 驗證 Ticket 狀態
    6. 驗證 blockedBy 依賴都已完成（除非 context-refresh）
    7. 根據方向建立交接檔案
    """
    ticket_id = args.ticket_id

    # 步驟 1：驗證 Ticket ID 格式
    if not validate_ticket_id(ticket_id):
        _print_id_error()
        return 1

    # 步驟 2：解析版本
    version = resolve_version(getattr(args, "version", None))
    if not version:
        _print_version_error()
        return 1

    # 步驟 3：驗證 Ticket 存在
    ticket = load_ticket(version, ticket_id)
    if not ticket:
        _print_ticket_not_found_error(ticket_id, version)
        return 2

    # 步驟 3.5：檢查 YAML 錯誤
    if _check_yaml_error(ticket, ticket_id):
        return 2

    # 步驟 4：驗證互斥旗標
    context_refresh = getattr(args, "context_refresh", False)
    direction_specified = (
        getattr(args, "to_parent", False)
        or getattr(args, "to_child", None)
        or getattr(args, "to_sibling", None)
    )

    if context_refresh and direction_specified:
        print(format_error(
            "錯誤：--context-refresh 與方向旗標（--to-parent, --to-child, --to-sibling）互斥"
        ))
        return 1

    # 步驟 5：驗證 Ticket 狀態
    if not _verify_handoff_status(ticket, ticket_id, context_refresh=context_refresh):
        return 1

    # 步驟 5.5：驗收條件前置檢查（防止 PC-003）
    acceptance_check_result = _warn_and_prompt_complete_before_handoff(ticket, ticket_id, version, context_refresh=context_refresh)
    if acceptance_check_result != 0:
        return acceptance_check_result

    # 步驟 6：驗證 blockedBy 依賴都已完成（除非 context-refresh）
    if not context_refresh:
        if not _verify_handoff_dependencies(ticket, ticket_id, version):
            return 1

    # 步驟 7：根據方向建立交接檔案
    if context_refresh:
        direction = "context-refresh"
    else:
        direction = _resolve_direction_from_args(args)
        if direction == "auto":
            direction = ChainAnalyzer.determine_direction(ticket, version)

    return _create_handoff_file(ticket, direction)


def _resolve_direction_from_args(args: argparse.Namespace) -> str:
    """
    從命令列參數解析交接方向。

    Args:
        args: 命令列參數

    Returns:
        str: 方向 (to-parent, to-child, to-sibling, auto)
    """
    if getattr(args, "to_parent", False):
        return "to-parent"
    if getattr(args, "to_child", None):
        return f"to-child:{args.to_child}"
    if getattr(args, "to_sibling", None):
        return f"to-sibling:{args.to_sibling}"
    return "auto"




def _print_status(ticket: dict) -> int:
    """
    列印 handoff 狀態資訊。

    Args:
        ticket: Ticket 資料

    Returns:
        int: exit code 0
    """
    ticket_id = ticket.get("id")
    status = ticket.get("status")
    title = ticket.get("title")
    chain = ticket.get("chain", {})
    children = ticket.get("children", [])

    print(format_msg(HandoffMessages.STATUS_HEADER_TICKET_ID, ticket_id=ticket_id))
    print(format_msg(HandoffMessages.STATUS_HEADER_TITLE, title=title))
    print(format_msg(HandoffMessages.STATUS_HEADER_STATUS, status=status))
    print(format_msg(HandoffMessages.STATUS_HEADER_DEPTH, depth=chain.get('depth', 0)))
    print()
    print(HandoffMessages.STATUS_CHAIN_INFO)
    print(format_msg(HandoffMessages.STATUS_CHAIN_ROOT, root=chain.get('root', 'N/A')))
    print(format_msg(HandoffMessages.STATUS_CHAIN_PARENT, parent=chain.get('parent', 'N/A')))
    print()

    if children:
        print(format_msg(HandoffMessages.STATUS_CHILDREN_COUNT, count=len(children)))
        # 從 ticket_id 提取 version (格式: 0.31.0-W4-010)
        version = ticket_id.split("-W")[0] if "-W" in ticket_id else None
        for child_id in children:
            # children 是 ID 字串列表，需要載入實際 ticket
            if isinstance(child_id, str):
                child_ticket = load_ticket(version, child_id) if version else None
                if child_ticket:
                    child_status = child_ticket.get("status", "unknown")
                    print(format_msg(HandoffMessages.STATUS_CHILD_ITEM, child_id=child_id, status=child_status))
                else:
                    print(format_msg(HandoffMessages.STATUS_CHILD_NOT_FOUND, child_id=child_id))
            elif isinstance(child_id, dict):
                # 相容舊格式（如果 children 是 dict 列表）
                print(format_msg(HandoffMessages.STATUS_CHILD_ITEM, child_id=child_id.get('id', 'unknown'), status=child_id.get('status', 'unknown')))

    print()
    print(HandoffMessages.STATUS_OPTIONS)
    # 從 ticket_id 提取 version
    version = ticket_id.split("-W")[0] if "-W" in ticket_id else None
    direction = ChainAnalyzer.determine_direction(ticket, version)

    if direction == "to-parent" and chain.get("parent"):
        print(format_msg(HandoffMessages.STATUS_USE_TO_PARENT, ticket_id=ticket_id))
    elif direction == "to-child":
        for child_id in children:
            # children 可能是 ID 字串或 dict
            if isinstance(child_id, str):
                print(format_msg(HandoffMessages.STATUS_USE_TO_CHILD, ticket_id=ticket_id, child_id=child_id))
            elif isinstance(child_id, dict):
                print(format_msg(HandoffMessages.STATUS_USE_TO_CHILD, ticket_id=ticket_id, child_id=child_id.get('id')))
    elif direction == "to-sibling":
        # 從父任務載入兄弟列表
        parent_id = chain.get("parent")
        if parent_id and version:
            parent_ticket = load_ticket(version, parent_id)
            if parent_ticket:
                siblings = parent_ticket.get("children", [])
                for sibling_id in siblings:
                    if isinstance(sibling_id, str):
                        if sibling_id == ticket_id:
                            continue
                        sibling_ticket = load_ticket(version, sibling_id)
                        if sibling_ticket and sibling_ticket.get("status") != STATUS_COMPLETED:
                            print(format_msg(HandoffMessages.STATUS_USE_TO_SIBLING, ticket_id=ticket_id, sibling_id=sibling_id))
                    elif isinstance(sibling_id, dict):
                        if sibling_id.get("id") == ticket_id:
                            continue
                        if sibling_id.get("status") != STATUS_COMPLETED:
                            print(format_msg(HandoffMessages.STATUS_USE_TO_SIBLING, ticket_id=ticket_id, sibling_id=sibling_id.get('id')))
    elif direction == "wait":
        print(HandoffMessages.STATUS_WAIT_DEPENDENCIES)
    elif direction == "completed":
        print(HandoffMessages.STATUS_NO_PENDING_TASKS)

    # 建議下一步
    print()
    print("=" * 50)
    print(SectionHeaders.SUGGESTED_NEXT_STEP)
    print("=" * 50)
    _print_recommendation(ticket, direction, version)

    return 0


def _print_recommendation(ticket: dict, direction: str, version: str = None) -> None:
    """
    列印建議下一步行動。

    根據 ticket-lifecycle.md 的設計，分析優先級為：
    1. 有子 Ticket 可開始
    2. 有被解除阻塞的 Ticket
    3. 有同層兄弟 Ticket
    4. 同 Wave 有其他 pending
    5. 任務鏈全部完成

    Args:
        ticket: Ticket 資料
        direction: 交接方向
        version: 版本號
    """
    recommendation = ChainAnalyzer.get_recommendation(direction, ticket, version)

    # 根據方向類型輸出對應資訊
    if recommendation.direction == "to-child":
        print(format_msg(HandoffMessages.RECOMMENDATION_ENTER_CHILD, child_id=recommendation.next_target_id))
        if recommendation.next_target_title:
            print(format_msg(HandoffMessages.RECOMMENDATION_TITLE, title=recommendation.next_target_title))
        print(format_msg(HandoffMessages.RECOMMENDATION_REASON, reason=recommendation.reason))
    elif recommendation.direction == "to-sibling":
        print(format_msg(HandoffMessages.RECOMMENDATION_SWITCH_SIBLING, sibling_id=recommendation.next_target_id))
        if recommendation.next_target_title:
            print(format_msg(HandoffMessages.RECOMMENDATION_TITLE, title=recommendation.next_target_title))
        print(format_msg(HandoffMessages.RECOMMENDATION_REASON, reason=recommendation.reason))
    elif recommendation.direction == "to-parent":
        print(format_msg(HandoffMessages.RECOMMENDATION_RETURN_PARENT, parent_id=recommendation.next_target_id))
        if recommendation.next_target_title:
            print(format_msg(HandoffMessages.RECOMMENDATION_TITLE, title=recommendation.next_target_title))
        print(format_msg(HandoffMessages.RECOMMENDATION_REASON, reason=recommendation.reason))
    elif recommendation.direction == "wait":
        print(HandoffMessages.RECOMMENDATION_WAIT)
        if recommendation.blocked_by:
            print(format_msg(HandoffMessages.RECOMMENDATION_BLOCKED_BY, blocked_by=', '.join(recommendation.blocked_by)))
        print(format_msg(HandoffMessages.RECOMMENDATION_REASON, reason=recommendation.reason))
    elif recommendation.direction == "completed":
        print(format_msg(HandoffMessages.RECOMMENDATION_COMPLETED, root_id=recommendation.next_target_id))
        print(format_msg(HandoffMessages.RECOMMENDATION_REASON, reason=recommendation.reason))
    else:
        print(format_msg(HandoffMessages.RECOMMENDATION_REASON, reason=recommendation.reason))

    # 輸出執行命令
    print()
    if recommendation.command:
        if recommendation.direction == "wait" and recommendation.blocked_by:
            print(format_msg(HandoffMessages.RECOMMENDATION_EXECUTE, command=recommendation.command) + "  " + HandoffMessages.RECOMMENDATION_EXECUTE_COMMENT_CHECK)
        elif recommendation.direction == "completed":
            print(format_msg(HandoffMessages.RECOMMENDATION_EXECUTE, command=recommendation.command) + "  " + HandoffMessages.RECOMMENDATION_EXECUTE_COMMENT_COMPLETE)
        else:
            print(format_msg(HandoffMessages.RECOMMENDATION_EXECUTE, command=recommendation.command))


def _find_completed_tickets(version: str) -> list[Dict[str, Any]]:
    """
    找出當前版本中最近完成的任務（用於 auto-detect handoff）。

    回傳最近 N 個 completed tickets，依 completed_at 欄位倒序排列。
    缺少 completed_at 欄位的 tickets 會被排除。

    Args:
        version: 版本號

    Returns:
        list[Dict]: 最近 completed 的 Ticket 列表（最多 MAX_RECENT_COMPLETED 個）
    """
    MAX_RECENT_COMPLETED = 10

    all_tickets = list_tickets(version)
    completed_with_date = [
        t for t in all_tickets
        if t.get("status") == STATUS_COMPLETED and t.get("completed_at")
    ]

    sorted_tickets = sorted(
        completed_with_date,
        key=lambda t: str(t.get("completed_at", "")),
        reverse=True,
    )
    return sorted_tickets[:MAX_RECENT_COMPLETED]


def _find_in_progress_tickets(version: str) -> list[Dict[str, Any]]:
    """
    找出當前版本中所有 in_progress 的任務。

    Args:
        version: 版本號

    Returns:
        list[Dict]: in_progress 的 Ticket 列表
    """
    all_tickets = list_tickets(version)
    return [t for t in all_tickets if t.get("status") == STATUS_IN_PROGRESS]


def _is_interactive() -> bool:
    """
    判斷是否為互動環境。

    Returns:
        bool: 如果標準輸入連接到終端機則返回 True，否則返回 False
    """
    return sys.stdin.isatty()


def _prompt_select_ticket(tickets: list[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    """
    當有多個 in_progress Ticket 時，提示用戶選擇。

    在非互動環境下，輸出明確的錯誤訊息和使用指南。

    Args:
        tickets: in_progress 的 Ticket 列表

    Returns:
        Optional[Dict]: 選中的 Ticket，或 None（如果取消或非互動環境）
    """
    # 非互動環境處理
    if not _is_interactive():
        print(format_msg(HandoffMessages.MULTIPLE_TASKS_NO_INTERACTIVE))
        print()
        print(HandoffMessages.PLEASE_SPECIFY_TICKET_ID)
        print(HandoffMessages.SPECIFY_TICKET_USAGE)
        print()
        print(HandoffMessages.IN_PROGRESS_TASKS)
        for t in tickets:
            ticket_id = t.get("id", "unknown")
            title = t.get("title", "")
            print(f"  - {ticket_id}: {title}")
        return None

    print(HandoffMessages.MULTIPLE_TASKS_FOUND)
    print()

    for idx, ticket in enumerate(tickets, 1):
        ticket_id = ticket.get("id", "unknown")
        title = ticket.get("title", "")
        print(f"{idx}. {ticket_id} - {title}")

    print()

    while True:
        try:
            choice = input(format_msg(HandoffMessages.SELECT_TASK_PROMPT, count=len(tickets)))
            choice_idx = int(choice)

            if choice_idx == 0:
                return None

            if 1 <= choice_idx <= len(tickets):
                return tickets[choice_idx - 1]

            print(format_msg(HandoffMessages.INVALID_SELECTION, count=len(tickets)))
        except (ValueError, EOFError):
            print("無效的輸入或非互動環境")
            return None


def execute(args: argparse.Namespace) -> int:
    """執行 handoff 命令"""
    # 檢查 --status 選項
    if getattr(args, "status", False):
        ticket_id = getattr(args, "ticket_id", None)

        # 如果沒有 ticket_id，嘗試自動找到 in_progress 的任務
        if not ticket_id:
            version = resolve_version(getattr(args, "version", None))
            if not version:
                _print_version_error()
                return 1

            in_progress_tickets = _find_in_progress_tickets(version)

            if not in_progress_tickets:
                print(HandoffMessages.NO_IN_PROGRESS_TASKS)
                return 0

            if len(in_progress_tickets) == 1:
                ticket = in_progress_tickets[0]
            else:
                # 多個任務時提示選擇
                ticket = _prompt_select_ticket(in_progress_tickets)
                if not ticket:
                    print(HandoffMessages.CANCELLED_OPERATION)
                    return 0
        else:
            # 提供了 ticket_id，按原流程處理
            if not validate_ticket_id(ticket_id):
                _print_id_error()
                return 1

            version = resolve_version(getattr(args, "version", None))
            if not version:
                _print_version_error()
                return 1

            ticket = load_ticket(version, ticket_id)
            if not ticket:
                _print_ticket_not_found_error(ticket_id, version)
                return 2

            if _check_yaml_error(ticket, ticket_id):
                return 2

        return _print_status(ticket)

    # 檢查是否提供了 Ticket ID（用於 handoff）
    # 注意：--status 可以單獨執行（無 ticket_id），已在上面處理
    ticket_id = getattr(args, "ticket_id", None)
    if not ticket_id:
        # 自動搜尋最近 completed 的 ticket
        version = resolve_version(getattr(args, "version", None))
        if not version:
            _print_version_error()
            return 1

        completed_tickets = _find_completed_tickets(version)

        if not completed_tickets:
            print(format_info(HandoffMessages.NO_COMPLETED_TASKS))
            return 0

        if len(completed_tickets) == 1:
            # Auto-detect: 使用副本避免修改原始 args 物件
            import copy
            handoff_args = copy.copy(args)
            handoff_args.ticket_id = completed_tickets[0].get("id")
            return _execute_handoff(handoff_args)

        # 多個已完成的 ticket：列出供選擇
        print(format_info(HandoffMessages.MULTIPLE_COMPLETED_TASKS))
        print()
        for t in completed_tickets:
            tid = t.get("id", "unknown")
            title = t.get("title", "")
            print(f"  - {tid}: {title}")
        print()
        print(HandoffMessages.SPECIFY_HANDOFF_USAGE)
        return 1

    return _execute_handoff(args)


def register(subparsers: argparse._SubParsersAction) -> None:
    """註冊 handoff 子命令"""
    parser = subparsers.add_parser("handoff", help=HandoffMessages.HELP_TEXT)
    parser.add_argument(
        "ticket_id",
        nargs="?",
        default=None,
        help=HandoffMessages.ARG_TICKET_ID_HELP
    )
    parser.add_argument(
        "--to-parent",
        action="store_true",
        help=HandoffMessages.ARG_TO_PARENT_HELP
    )
    parser.add_argument(
        "--to-child",
        metavar="ID",
        help=HandoffMessages.ARG_TO_CHILD_HELP
    )
    parser.add_argument(
        "--to-sibling",
        metavar="ID",
        help=HandoffMessages.ARG_TO_SIBLING_HELP
    )
    parser.add_argument(
        "--context-refresh",
        action="store_true",
        help="Context 刷新交接：允許 in_progress 獨立任務進行 handoff，跳過依賴檢查"
    )
    parser.add_argument(
        "--status",
        action="store_true",
        help=HandoffMessages.ARG_STATUS_HELP
    )
    parser.add_argument(
        "--version",
        help=HandoffMessages.ARG_VERSION_HELP
    )
    parser.set_defaults(func=execute)
