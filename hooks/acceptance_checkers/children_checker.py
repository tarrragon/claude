"""
Children Checker - 子任務完成度檢查

檢查 Ticket 的所有子任務是否已完成，未完成時產生阻擋訊息。
"""

import sys
from pathlib import Path
from typing import Optional, Tuple, List

# 加入 hooks 目錄（acceptance_checkers 的上層）
_hooks_dir = Path(__file__).parent.parent
if str(_hooks_dir) not in sys.path:
    sys.path.insert(0, str(_hooks_dir))

from hook_utils import find_ticket_file, parse_ticket_frontmatter
from lib.hook_messages import GateMessages, format_message
from acceptance_checkers.ticket_parser import extract_children_from_frontmatter


def check_children_completed(
    children: List[str], project_dir: Path, logger
) -> Tuple[bool, List[Tuple[str, str, str]]]:
    """
    檢查所有子任務是否已完成

    Args:
        children: 子任務 ID 清單
        project_dir: 專案根目錄
        logger: 日誌物件

    Returns:
        tuple - (all_completed, incomplete_children)
            - all_completed: 是否全部完成
            - incomplete_children: [(child_id, title, status), ...] 未完成的子任務清單
    """
    incomplete_children = []

    for child_id in children:
        child_file = find_ticket_file(child_id, project_dir, logger)

        if not child_file:
            logger.warning(f"無法找到子任務檔案: {child_id}")
            incomplete_children.append((child_id, "未知", "not_found"))
            continue

        try:
            content = child_file.read_text(encoding="utf-8")
            frontmatter = parse_ticket_frontmatter(content)

            status = frontmatter.get("status", "unknown")
            title = frontmatter.get("title", "未知")

            if status != "completed":
                logger.warning(f"子任務未完成: {child_id} (status={status})")
                incomplete_children.append((child_id, title, status))
            else:
                logger.info(f"子任務已完成: {child_id}")

        except Exception as e:
            logger.warning(f"無法讀取子任務檔案 {child_file}: {e}")
            incomplete_children.append((child_id, "未知", "read_error"))

    all_completed = len(incomplete_children) == 0
    return all_completed, incomplete_children


def check_children_completed_from_frontmatter(
    ticket_file: Path,
    frontmatter: dict,
    project_dir: Path,
    ticket_id: str,
    logger,
) -> Tuple[bool, Optional[str]]:
    """
    從 frontmatter 檢查子任務完成度（orchestrator 呼叫入口）。

    Args:
        ticket_file: Ticket 檔案路徑
        frontmatter: Ticket frontmatter 結構
        project_dir: 專案根目錄
        ticket_id: Ticket ID
        logger: 日誌物件

    Returns:
        tuple - (should_block, error_message)
    """
    children = extract_children_from_frontmatter(frontmatter, logger)

    if not children:
        return False, None

    logger.info(f"Ticket {ticket_id} 有 {len(children)} 個子任務")
    all_completed, incomplete_children = check_children_completed(
        children, project_dir, logger
    )

    if not all_completed:
        title = frontmatter.get("title", "未知")
        incomplete_list = "\n".join(
            f"  - {child_id}: {child_title} (status: {status})"
            for child_id, child_title, status in incomplete_children
        )
        error_msg = format_message(
            GateMessages.CHILDREN_INCOMPLETE_ERROR,
            ticket_id=ticket_id,
            title=title,
            incomplete_list=incomplete_list,
        )
        logger.error(f"Ticket {ticket_id} 有未完成的子任務 - 阻擋執行")
        return True, error_msg

    logger.info(f"Ticket {ticket_id} 所有子任務已完成")
    return False, None
