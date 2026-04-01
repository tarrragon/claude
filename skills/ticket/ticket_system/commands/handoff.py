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
from ticket_system.commands.exceptions import (
    HandoffTargetNotFoundError,
    HandoffDuplicateError,
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
from ticket_system.lib.ticket_ops import (
    load_and_validate_ticket,
    resolve_ticket_path,
    resolve_id_from_ref,
)
from ticket_system.lib.ticket_validator import extract_version_from_ticket_id
from ticket_system.lib.ui_constants import SEPARATOR_PRIMARY, SEPARATOR_SECONDARY


# ============================================================================
# 模組級常數
# ============================================================================

# 方向到訊息模板和參數名稱的映射表（消除三分支結構重複）
# 結構：direction -> (message_template, param_name)
# 適用於 to-child、to-sibling、to-parent 三個方向，統一參數名稱為目標 ID
_DIRECTION_MESSAGE_MAP = {
    "to-child": (HandoffMessages.RECOMMENDATION_ENTER_CHILD, "child_id"),
    "to-sibling": (HandoffMessages.RECOMMENDATION_SWITCH_SIBLING, "sibling_id"),
    "to-parent": (HandoffMessages.RECOMMENDATION_RETURN_PARENT, "parent_id"),
}


# ============================================================================
# 輔助函式
# ============================================================================

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
    print(SEPARATOR_PRIMARY)
    print(f"  Ticket {ticket_id} 的所有驗收條件已勾選 [x]，")
    print(f"  但狀態仍為 in_progress。")
    print()
    print("  建議在 handoff 前先執行 complete，以確保任務鏈完整性。")
    print()
    print(f"  執行命令: ticket track complete {ticket_id}")
    print(SEPARATOR_PRIMARY)
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


def _validate_target_ticket_exists(direction: str, version: str) -> None:
    """
    P1: 驗證 to-sibling/to-child handoff 的目標 ticket 存在。

    to-sibling:TARGET_ID 或 to-child:TARGET_ID 格式中，
    若 TARGET_ID 不存在則拋出 HandoffTargetNotFoundError（含可操作指引）。

    context-refresh 和 to-parent 不需要目標驗證。

    支援跨版本 handoff：從 target_id 提取版本號，而非使用來源版本號。

    Args:
        direction: handoff direction（如 "to-sibling:0.1.0-W5-002"）
        version: 版本號（目前未使用，保留用於向後相容）

    Raises:
        HandoffTargetNotFoundError: 目標 ticket 不存在時
    """
    # 只驗證帶有 target_id 的任務鏈 direction
    direction_parts = direction.split(":", 1)
    if len(direction_parts) < 2:
        return  # 無 target_id（如 "to-parent"、"context-refresh"）不需驗證

    direction_type = direction_parts[0]
    if direction_type not in ("to-sibling", "to-child"):
        return  # 非任務鏈跳轉類型不需驗證

    target_id = direction_parts[1]
    if not target_id:
        return  # 空 target_id 不需驗證

    # 從 target_id 提取版本號（支援跨版本 handoff）
    target_version = extract_version_from_ticket_id(target_id)
    if not target_version:
        raise HandoffTargetNotFoundError(target_id)

    # 驗證目標 ticket 是否存在
    target_ticket = load_ticket(target_version, target_id)
    if target_ticket is None:
        raise HandoffTargetNotFoundError(target_id)


def _validate_no_duplicate_handoff(ticket_id: str) -> None:
    """
    P2: 驗證 pending 目錄中不存在指向相同 ticket_id 的 handoff。

    若已存在相同目標的 pending handoff，拋出 HandoffDuplicateError（含可操作指引）。

    Args:
        ticket_id: 要建立 handoff 的 ticket ID

    Raises:
        HandoffDuplicateError: 已存在相同目標的 pending handoff 時
    """
    root = get_project_root()
    pending_dir = root / HANDOFF_DIR / HANDOFF_PENDING_SUBDIR

    if not pending_dir.exists():
        return

    existing_file = pending_dir / f"{ticket_id}.json"
    if not existing_file.exists():
        return

    # 讀取既有 handoff 的時間戳
    try:
        with open(existing_file, "r", encoding="utf-8") as f:
            existing_data = json.load(f)
        existing_timestamp = existing_data.get("timestamp", "（時間未知）")
    except (IOError, ValueError):
        existing_timestamp = "（無法讀取時間）"

    raise HandoffDuplicateError(ticket_id, existing_timestamp)


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
    print(SEPARATOR_PRIMARY)
    print(InfoMessages.HANDOFF_NEXT_STEP)
    print(SEPARATOR_PRIMARY)
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
    # 優先從 Ticket ID 提取版本，fallback 到 --version 或自動偵測
    explicit_version = getattr(args, "version", None)
    if not explicit_version:
        extracted = extract_version_from_ticket_id(ticket_id)
        if extracted:
            version = extracted
        else:
            version = resolve_version(None)
    else:
        version = resolve_version(explicit_version)
    if not version:
        _print_version_error()
        return 1

    # 步驟 3：驗證 Ticket 存在和格式
    ticket, error = load_and_validate_ticket(version, ticket_id, auto_print_error=False)
    if error:
        _print_ticket_not_found_error(ticket_id, version)
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

    # 步驟 7a：驗證目標 ticket 存在（P1）
    try:
        _validate_target_ticket_exists(direction, version)
    except HandoffTargetNotFoundError as e:
        print(f"[ERROR] {e}", file=sys.stderr)
        print(e.guidance, file=sys.stderr)
        return 1

    # 步驟 7b：驗證無重複 pending handoff（P2）
    try:
        _validate_no_duplicate_handoff(ticket_id)
    except HandoffDuplicateError as e:
        print(f"[ERROR] {e}", file=sys.stderr)
        print(e.guidance, file=sys.stderr)
        return 1

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

def _print_header(ticket: dict) -> None:
    """
    列印 handoff 狀態的基本資訊。

    包含 ticket_id、title、status、depth 和 chain 資訊。

    Args:
        ticket: Ticket 資料
    """
    ticket_id = ticket.get("id")
    status = ticket.get("status")
    title = ticket.get("title")
    chain = ticket.get("chain", {})

    print(format_msg(HandoffMessages.STATUS_HEADER_TICKET_ID, ticket_id=ticket_id))
    print(format_msg(HandoffMessages.STATUS_HEADER_TITLE, title=title))
    print(format_msg(HandoffMessages.STATUS_HEADER_STATUS, status=status))
    print(format_msg(HandoffMessages.STATUS_HEADER_DEPTH, depth=chain.get('depth', 0)))
    print()
    print(HandoffMessages.STATUS_CHAIN_INFO)
    print(format_msg(HandoffMessages.STATUS_CHAIN_ROOT, root=chain.get('root', 'N/A')))
    print(format_msg(HandoffMessages.STATUS_CHAIN_PARENT, parent=chain.get('parent', 'N/A')))
    print()


def _print_dict_child(child_item: dict) -> None:
    """
    列印字典型 child 資訊（已嵌入狀態）。

    Args:
        child_item: 字典型 child
    """
    print(format_msg(
        HandoffMessages.STATUS_CHILD_ITEM,
        child_id=child_item.get('id', 'unknown'),
        status=child_item.get('status', 'unknown'),
    ))


def _print_string_child(child_id: str, version: Optional[str]) -> None:
    """
    列印字串型 child 資訊（需要載入檔案）。

    Args:
        child_id: 子任務 ID
        version: 版本號（用於載入檔案）
    """
    child_ticket = load_ticket(version, child_id) if version else None
    if child_ticket:
        child_status = child_ticket.get("status", "unknown")
        print(format_msg(HandoffMessages.STATUS_CHILD_ITEM, child_id=child_id, status=child_status))
    else:
        print(format_msg(HandoffMessages.STATUS_CHILD_NOT_FOUND, child_id=child_id))


def _print_children_info(children: list, version: Optional[str]) -> None:
    """
    列印子任務資訊。

    args:
        children: 子任務 ID 清單（可能是字串或 dict）
        version: 版本號（用於載入子任務詳細資訊）
    """
    if not children:
        return

    print(format_msg(HandoffMessages.STATUS_CHILDREN_COUNT, count=len(children)))
    for child_item in children:
        # 提取子任務 ID
        child_id = resolve_id_from_ref(child_item)

        # 情況 1：字典型 child（已嵌入狀態）
        if isinstance(child_item, dict):
            _print_dict_child(child_item)
        # 情況 2：字串型 ID（需要載入檔案）
        elif child_id:
            _print_string_child(child_id, version)


def _print_direction_options(
    ticket: dict,
    direction: str,
    version: Optional[str],
    children: list,
    parent_ticket: Optional[Dict[str, Any]] = None,
) -> None:
    """
    列印根據交接方向可用的 handoff 選項。

    處理 5 種方向：to-parent、to-child、to-sibling、wait、completed。

    Args:
        ticket: Ticket 資料
        direction: 由 ChainAnalyzer 決定的交接方向
        version: 版本號
        children: 子任務清單
        parent_ticket: 預先載入的父任務資料（避免重複 I/O）
    """
    ticket_id = ticket.get("id")
    chain = ticket.get("chain", {})

    if direction == "to-parent" and chain.get("parent"):
        print(format_msg(HandoffMessages.STATUS_USE_TO_PARENT, ticket_id=ticket_id))
    elif direction == "to-child":
        _print_to_child_options(ticket_id, children)
    elif direction == "to-sibling":
        _print_to_sibling_options(ticket_id, chain, version, parent_ticket)
    elif direction == "wait":
        print(HandoffMessages.STATUS_WAIT_DEPENDENCIES)
    elif direction == "completed":
        print(HandoffMessages.STATUS_NO_PENDING_TASKS)


def _print_to_child_options(ticket_id: str, children: list) -> None:
    """
    列印 to-child 方向的子任務選項。

    Args:
        ticket_id: 當前 Ticket ID
        children: 子任務清單（可能是字串或 dict）
    """
    for child_item in children:
        # 提取子任務 ID
        child_id = resolve_id_from_ref(child_item)
        if child_id:
            print(format_msg(HandoffMessages.STATUS_USE_TO_CHILD, ticket_id=ticket_id, child_id=child_id))


def _print_dict_sibling(ticket_id: str, sibling_item: dict) -> None:
    """
    列印字典型 sibling 選項（已嵌入狀態）。

    Args:
        ticket_id: 當前 Ticket ID
        sibling_item: 字典型 sibling
    """
    if sibling_item.get("id") == ticket_id:
        return
    if sibling_item.get("status") != STATUS_COMPLETED:
        print(format_msg(
            HandoffMessages.STATUS_USE_TO_SIBLING,
            ticket_id=ticket_id,
            sibling_id=sibling_item.get('id'),
        ))


def _print_string_sibling(
    ticket_id: str,
    sibling_id: str,
    version: Optional[str],
) -> None:
    """
    列印字串型 sibling 選項（需要載入檔案）。

    Args:
        ticket_id: 當前 Ticket ID
        sibling_id: 兄弟任務 ID
        version: 版本號
    """
    if sibling_id == ticket_id:
        return
    sibling_ticket = load_ticket(version, sibling_id)
    if sibling_ticket and sibling_ticket.get("status") != STATUS_COMPLETED:
        print(format_msg(
            HandoffMessages.STATUS_USE_TO_SIBLING,
            ticket_id=ticket_id,
            sibling_id=sibling_id,
        ))


def _print_to_sibling_options(
    ticket_id: str,
    chain: dict,
    version: Optional[str],
    parent_ticket: Optional[Dict[str, Any]] = None,
) -> None:
    """
    列印 to-sibling 方向的兄弟任務選項。

    從父任務載入兄弟列表，過濾掉自己和已完成的兄弟。

    Args:
        ticket_id: 當前 Ticket ID
        chain: Ticket 的 chain 資訊（含 parent）
        version: 版本號
        parent_ticket: 預先載入的父任務資料（避免重複 I/O）
    """
    parent_id = chain.get("parent")
    if not (parent_id and version):
        return

    # 如果沒有預先載入的父任務，才進行載入
    if parent_ticket is None:
        parent_ticket = load_ticket(version, parent_id)

    if not parent_ticket:
        return

    siblings = parent_ticket.get("children", [])
    for sibling_item in siblings:
        # 提取兄弟任務 ID
        sibling_id = resolve_id_from_ref(sibling_item)

        # 情況 1：字典型兄弟（已嵌入狀態）
        if isinstance(sibling_item, dict):
            _print_dict_sibling(ticket_id, sibling_item)
        # 情況 2：字串型兄弟 ID（需要載入檔案）
        elif sibling_id:
            _print_string_sibling(ticket_id, sibling_id, version)


def _print_status(ticket: dict) -> int:
    """
    列印 handoff 狀態資訊。

    整合子函式的完整流程，包括基本資訊、子任務、方向選項和建議。

    Args:
        ticket: Ticket 資料

    Returns:
        int: exit code 0
    """
    ticket_id = ticket.get("id")
    children = ticket.get("children", [])
    chain = ticket.get("chain", {})

    # 版本號提取一次，傳入各子函式
    version = extract_version_from_ticket_id(ticket_id)

    # 預先載入父任務，避免兄弟選項查詢時重複 I/O
    parent_id = chain.get("parent")
    parent_ticket = None
    if parent_id and version:
        parent_ticket = load_ticket(version, parent_id)

    # 列印基本資訊
    _print_header(ticket)

    # 列印子任務資訊
    _print_children_info(children, version)
    print()

    # 列印交接方向選項
    print(HandoffMessages.STATUS_OPTIONS)
    direction = ChainAnalyzer.determine_direction(ticket, version)
    _print_direction_options(ticket, direction, version, children, parent_ticket)

    # 列印建議下一步
    print()
    print(SEPARATOR_SECONDARY)
    print(SectionHeaders.SUGGESTED_NEXT_STEP)
    print(SEPARATOR_SECONDARY)
    _print_recommendation(ticket, direction, version)

    return 0


def _print_direction_recommendation(
    rec: Recommendation,
    msg_template: str,
    param_name: str,
) -> None:
    """列印方向建議（to-child/to-sibling/to-parent）。使用映射表消除重複。"""
    kwargs = {param_name: rec.next_target_id}
    print(format_msg(msg_template, **kwargs))
    if rec.next_target_title:
        print(format_msg(HandoffMessages.RECOMMENDATION_TITLE, title=rec.next_target_title))
    print(format_msg(HandoffMessages.RECOMMENDATION_REASON, reason=rec.reason))


def _print_execute_command(rec: Recommendation) -> None:
    """列印建議執行的命令，根據方向添加對應註解。"""
    if not rec.command:
        return

    # 選擇註解文字
    if rec.direction == "wait" and rec.blocked_by:
        comment = HandoffMessages.RECOMMENDATION_EXECUTE_COMMENT_CHECK
    elif rec.direction == "completed":
        comment = HandoffMessages.RECOMMENDATION_EXECUTE_COMMENT_COMPLETE
    else:
        comment = None

    # 列印命令
    if comment:
        print(format_msg(
            HandoffMessages.RECOMMENDATION_EXECUTE_WITH_COMMENT,
            command=rec.command,
            comment=comment,
        ))
    else:
        print(format_msg(HandoffMessages.RECOMMENDATION_EXECUTE, command=rec.command))


def _print_direction_based_recommendation(
    recommendation: Recommendation,
) -> None:
    """
    列印方向類型的建議（to-child/to-sibling/to-parent）。

    Args:
        recommendation: 建議物件
    """
    msg_template, param_name = _DIRECTION_MESSAGE_MAP[recommendation.direction]
    _print_direction_recommendation(recommendation, msg_template, param_name)


def _print_wait_recommendation(recommendation: Recommendation) -> None:
    """
    列印 wait 方向的建議。

    Args:
        recommendation: 建議物件
    """
    print(HandoffMessages.RECOMMENDATION_WAIT)
    if recommendation.blocked_by:
        print(format_msg(
            HandoffMessages.RECOMMENDATION_BLOCKED_BY,
            blocked_by=', '.join(recommendation.blocked_by),
        ))
    print(format_msg(HandoffMessages.RECOMMENDATION_REASON, reason=recommendation.reason))


def _print_completed_recommendation(recommendation: Recommendation) -> None:
    """
    列印 completed 方向的建議。

    Args:
        recommendation: 建議物件
    """
    print(format_msg(
        HandoffMessages.RECOMMENDATION_COMPLETED,
        root_id=recommendation.next_target_id,
    ))
    print(format_msg(HandoffMessages.RECOMMENDATION_REASON, reason=recommendation.reason))


def _print_recommendation(ticket: dict, direction: str, version: str = None) -> None:
    """
    列印建議下一步行動。

    使用模組級映射表消除 to-child/to-sibling/to-parent 三分支的結構性重複。

    Args:
        ticket: Ticket 資料
        direction: 交接方向
        version: 版本號
    """
    recommendation = ChainAnalyzer.get_recommendation(direction, ticket, version)

    # 根據方向類型輸出對應資訊
    if recommendation.direction in _DIRECTION_MESSAGE_MAP:
        _print_direction_based_recommendation(recommendation)
    elif recommendation.direction == "wait":
        _print_wait_recommendation(recommendation)
    elif recommendation.direction == "completed":
        _print_completed_recommendation(recommendation)
    else:
        print(format_msg(HandoffMessages.RECOMMENDATION_REASON, reason=recommendation.reason))

    # 輸出執行命令
    print()
    _print_execute_command(recommendation)


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


def _execute_gc(args: argparse.Namespace) -> int:
    """執行 gc 子命令"""
    from ticket_system.commands.handoff_gc import execute_gc
    dry_run = getattr(args, "dry_run", False)
    execute_mode = getattr(args, "execute", False)
    # 預設為 dry-run（dry_run=True），除非明確指定 --execute
    return execute_gc(dry_run=(dry_run or not execute_mode))


def execute(args: argparse.Namespace) -> int:
    """執行 handoff 命令"""
    # 檢查是否為 gc 命令（改用 --gc 旗標，不用子命令）
    if getattr(args, "gc", False):
        return _execute_gc(args)

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

            # 優先從 Ticket ID 提取版本，fallback 到 --version 或自動偵測
            explicit_ver = getattr(args, "version", None)
            if not explicit_ver:
                extracted = extract_version_from_ticket_id(ticket_id)
                if extracted:
                    version = extracted
                else:
                    version = resolve_version(None)
            else:
                version = resolve_version(explicit_ver)
            if not version:
                _print_version_error()
                return 1

            ticket, error = load_and_validate_ticket(version, ticket_id, auto_print_error=False)
            if error:
                _print_ticket_not_found_error(ticket_id, version)
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
    """註冊 handoff 主命令"""
    parser = subparsers.add_parser("handoff", help=HandoffMessages.HELP_TEXT)

    # 註冊主 handoff 命令的參數
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
        "--gc",
        action="store_true",
        help="清理 stale handoff 檔案"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="（搭配 --gc）預覽 stale handoff 清單，不實際刪除"
    )
    parser.add_argument(
        "--execute",
        action="store_true",
        help="（搭配 --gc）執行清理，將 stale handoff 移至 archive/"
    )
    parser.add_argument(
        "--version",
        help=HandoffMessages.ARG_VERSION_HELP
    )
    parser.set_defaults(func=execute)
