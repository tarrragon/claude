"""
Ticket 批量操作模組

負責批量認領和完成 Ticket。
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
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Dict, Tuple, Optional

from ticket_system.lib.constants import (
    STATUS_PENDING,
    STATUS_IN_PROGRESS,
    STATUS_COMPLETED,
)
from ticket_system.lib.ticket_loader import (
    get_ticket_path,
    save_ticket,
    list_tickets,
)
from ticket_system.lib.ticket_validator import (
    validate_claimable_status,
    validate_completable_status,
    validate_acceptance_criteria,
)
from ticket_system.lib.messages import (
    ErrorMessages,
    InfoMessages,
    format_error,
    format_info,
    format_warning,
)
from ticket_system.lib.command_tracking_messages import (
    TrackBatchMessages,
    format_msg,
)
from ticket_system.lib.ticket_ops import (
    load_and_validate_ticket,
    resolve_ticket_path,
)
from ticket_system.lib.ui_constants import SEPARATOR_PRIMARY


# ============================================================================
# 訊息常數
# ============================================================================

class BatchEnhancedMessages:
    """批量操作增強功能訊息（補充 TrackBatchMessages）"""
    DRY_RUN_HEADER = "【模擬執行】將完成以下 Ticket："
    DRY_RUN_ITEM_FORMAT = "  {ticket_id}: {title}"
    DRY_RUN_SUMMARY = "共 {count} 個 Ticket（未實際執行）"
    SEARCH_BY_WAVE = "搜尋 Wave {wave} 中的 Ticket..."
    SEARCH_BY_PARENT = "搜尋父任務 {parent_id} 的子任務..."
    NO_TICKETS_FOUND = "找不到符合條件的 Ticket"


# ============================================================================
# 輔助函式
# ============================================================================

def _collect_ids_from_wave(version: str, wave: int, status: str) -> list[str]:
    """
    從指定 Wave 蒐集 Ticket ID

    Args:
        version: 版本號
        wave: Wave 編號
        status: 篩選狀態（如 "in_progress"）

    Returns:
        list[str]: 符合條件的 Ticket ID 清單
    """
    tickets = list_tickets(version)
    matched_ids = []

    for ticket in tickets:
        ticket_wave = ticket.get("wave")
        ticket_status = ticket.get("status")

        if ticket_wave == wave and ticket_status == status:
            matched_ids.append(ticket.get("id"))

    return matched_ids


def _collect_ids_from_parent(version: str, parent_id: str) -> list[str]:
    """
    從指定父任務蒐集子任務 ID

    支援新格式（chain.parent）和舊格式（頂層 parent）的 Ticket。

    Args:
        version: 版本號
        parent_id: 父任務 ID

    Returns:
        list[str]: 子任務 ID 清單
    """
    tickets = list_tickets(version)
    child_ids = []

    for ticket in tickets:
        # 優先檢查 chain.parent，回退到頂層 parent（向後相容）
        ticket_parent = ticket.get("parent") or ticket.get("chain", {}).get("parent")
        if ticket_parent == parent_id:
            child_ids.append(ticket.get("id"))

    return child_ids


def _resolve_ticket_ids_for_complete(
    args: argparse.Namespace,
    version: str,
) -> Optional[str]:
    """
    根據參數（--wave, --parent 或逗號分隔 ID）解析 Ticket ID 清單

    Args:
        args: 命令列引數
        version: 版本號

    Returns:
        str: 逗號分隔的 Ticket ID 或 None（失敗時）
    """
    wave = None
    if hasattr(args, "wave") and isinstance(args.wave, int):
        wave = args.wave

    parent_id = None
    if hasattr(args, "parent") and isinstance(args.parent, str):
        parent_id = args.parent

    ticket_ids_arg = getattr(args, "ticket_ids", "").strip()

    # 驗證參數：必須有 --wave 或 --parent 或 ticket_ids
    if wave is None and not parent_id and not ticket_ids_arg:
        print(format_error(ErrorMessages.NO_VALID_TICKETS))
        return None

    # 優先使用 --wave 篩選
    if wave is not None:
        status = getattr(args, "status", STATUS_IN_PROGRESS)
        print(format_info(BatchEnhancedMessages.SEARCH_BY_WAVE, wave=wave))
        ticket_ids = _collect_ids_from_wave(version, wave, status)
        if not ticket_ids:
            print(format_warning(BatchEnhancedMessages.NO_TICKETS_FOUND))
            return None
        return ",".join(ticket_ids)

    # 其次使用 --parent 篩選
    if parent_id:
        print(format_info(BatchEnhancedMessages.SEARCH_BY_PARENT, parent_id=parent_id))
        ticket_ids = _collect_ids_from_parent(version, parent_id)
        if not ticket_ids:
            print(format_warning(BatchEnhancedMessages.NO_TICKETS_FOUND))
            return None
        return ",".join(ticket_ids)

    # 最後使用逗號分隔 ID
    return ticket_ids_arg


def _parse_ticket_ids(ids_str: str) -> list[str]:
    """
    解析逗號分隔的 Ticket ID 字串

    Args:
        ids_str: 逗號分隔的 Ticket ID

    Returns:
        list[str]: 清理後的 Ticket ID 列表
    """
    return [tid.strip() for tid in ids_str.split(",") if tid.strip()]


def _validate_operation_type(operation: str) -> None:
    """驗證操作類型是否有效"""
    valid_types = ("claim", "complete")
    if operation not in valid_types:
        raise ValueError(f"不支援的操作類型: {operation}")


def _process_batch_claim(ticket: Dict[str, Any], ticket_id: str) -> Tuple[bool, str]:
    """
    處理單一 Ticket 的認領操作

    Args:
        ticket: Ticket 資料字典
        ticket_id: Ticket ID

    Returns:
        Tuple[bool, str]: (是否成功, 訊息)
    """
    status = ticket.get("status", STATUS_PENDING)

    # 驗證是否可認領
    can_claim, error_msg = validate_claimable_status(ticket_id, status)
    if not can_claim:
        return False, error_msg

    # 更新狀態
    ticket["status"] = STATUS_IN_PROGRESS
    ticket["assigned"] = True
    ticket["started_at"] = datetime.now().isoformat(timespec="seconds")

    return True, format_msg(TrackBatchMessages.CLAIM_SUCCESS_FORMAT, ticket_id=ticket_id)


def _process_batch_complete(ticket: Dict[str, Any], ticket_id: str) -> Tuple[bool, str]:
    """
    處理單一 Ticket 的完成操作

    Args:
        ticket: Ticket 資料字典
        ticket_id: Ticket ID

    Returns:
        Tuple[bool, str]: (是否成功, 訊息)
    """
    status = ticket.get("status", STATUS_PENDING)
    completed_at = ticket.get("completed_at")

    # 驗證狀態
    can_complete, status_msg, is_already_complete = validate_completable_status(
        ticket_id,
        status,
        completed_at
    )

    # 已完成的 Ticket：略過（計為成功）
    if is_already_complete:
        return True, format_msg(TrackBatchMessages.ALREADY_COMPLETE_FORMAT, ticket_id=ticket_id)

    # 不可完成
    if not can_complete:
        return False, status_msg

    # 驗證驗收條件
    acceptance_list = ticket.get("acceptance")
    criteria_complete, incomplete_items = validate_acceptance_criteria(
        ticket_id,
        acceptance_list
    )

    if not criteria_complete:
        return False, format_msg(TrackBatchMessages.ACCEPTANCE_INCOMPLETE_FORMAT, ticket_id=ticket_id, count=len(incomplete_items))

    # 更新狀態
    ticket["status"] = STATUS_COMPLETED
    ticket["completed_at"] = datetime.now().isoformat(timespec="seconds")

    return True, format_msg(TrackBatchMessages.COMPLETE_SUCCESS_FORMAT, ticket_id=ticket_id)


def _execute_batch_operation(
    args: argparse.Namespace,
    version: str,
    operation: str,
    operation_name: str,
    result_message_key: str,
    processor: Callable[[Dict[str, Any], str], Tuple[bool, str]],
) -> int:
    """
    通用批量操作框架，支援 dry-run

    Args:
        args: 命令列引數
        version: 版本號
        operation: 操作類型 (claim/complete)
        operation_name: 操作名稱（用於輸出訊息）
        result_message_key: 結果訊息的 InfoMessages 鍵值
        processor: 處理單一 Ticket 的函式

    Returns:
        int: 結束碼 (0 成功, 1 失敗)
    """
    _validate_operation_type(operation)

    # 解析 ID 列表
    ticket_ids = _parse_ticket_ids(args.ticket_ids)

    if not ticket_ids:
        print(format_error(ErrorMessages.NO_VALID_TICKETS))
        return 1

    # 檢查 dry-run 模式（僅在 complete 操作且明確設定才啟用）
    is_dry_run = operation == "complete" and hasattr(args, "dry_run") and args.dry_run is True

    if is_dry_run:
        # 模擬執行模式：只顯示清單
        print(format_info(BatchEnhancedMessages.DRY_RUN_HEADER))
        for ticket_id in ticket_ids:
            ticket, _ = load_and_validate_ticket(version, ticket_id, auto_print_error=False)
            if ticket:
                title = ticket.get("title", "無標題")
                print(format_info(BatchEnhancedMessages.DRY_RUN_ITEM_FORMAT, ticket_id=ticket_id, title=title))
        print()
        print(format_info(BatchEnhancedMessages.DRY_RUN_SUMMARY, count=len(ticket_ids)))
        return 0

    # 實際執行模式
    print(format_msg(TrackBatchMessages.BATCH_OPERATION_HEADER, operation_name=operation_name, count=len(ticket_ids)))

    success_count = 0
    for ticket_id in ticket_ids:
        # 使用 auto_print_error=False 以支援自訂 BATCH 格式
        ticket, error = load_and_validate_ticket(version, ticket_id, auto_print_error=False)
        if error:
            print(f"   {format_error(ErrorMessages.TICKET_NOT_FOUND_IN_BATCH, ticket_id=ticket_id)}")
            continue

        # 處理 Ticket
        success, message = processor(ticket, ticket_id)

        if success:
            # 保存更改
            ticket_path = resolve_ticket_path(ticket, version, ticket_id)
            save_ticket(ticket, ticket_path)
            # 使用 format_info 確保一致的訊息格式
            print(f"   {TrackBatchMessages.OK_PREFIX} {message}")
            success_count += 1
        else:
            print(f"   {format_error(ErrorMessages.STATUS_ERROR, status_msg=message)}")

    print()
    print(format_info(result_message_key, success=success_count, total=len(ticket_ids)))

    return 0 if success_count > 0 else 1


def execute_batch_claim(args: argparse.Namespace, version: str) -> int:
    """批量認領多個 Ticket"""
    return _execute_batch_operation(
        args=args,
        version=version,
        operation="claim",
        operation_name="Claim",
        result_message_key=InfoMessages.BATCH_CLAIM_RESULTS,
        processor=_process_batch_claim,
    )


def execute_batch_complete(args: argparse.Namespace, version: str) -> int:
    """
    批量完成多個 Ticket

    支援三種模式：
    1. 逗號分隔 ID：ticket track batch-complete "id1,id2"
    2. 按 Wave：ticket track batch-complete --wave 28
    3. 按 Parent：ticket track batch-complete --parent 0.31.0-W28-001
    4. Dry-run：ticket track batch-complete --wave 28 --dry-run
    """
    # 解析 Ticket ID（支援 --wave, --parent, 或逗號分隔）
    ticket_ids = _resolve_ticket_ids_for_complete(args, version)
    if ticket_ids is None:
        return 1

    args.ticket_ids = ticket_ids

    return _execute_batch_operation(
        args=args,
        version=version,
        operation="complete",
        operation_name="Complete",
        result_message_key=InfoMessages.BATCH_COMPLETE_RESULTS,
        processor=_process_batch_complete,
    )
