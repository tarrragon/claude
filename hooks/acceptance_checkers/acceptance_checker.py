"""
Acceptance Checker - 驗收記錄檢查

檢查 Ticket 是否有驗收記錄（關鍵字搜尋），以及是否需要驗收。
"""

import sys
from pathlib import Path
from typing import Optional, Tuple

# 加入 hooks 目錄（acceptance_checkers 的上層）
_hooks_dir = Path(__file__).parent.parent
if str(_hooks_dir) not in sys.path:
    sys.path.insert(0, str(_hooks_dir))

from lib.hook_messages import GateMessages, format_message
from acceptance_checkers.ticket_parser import (
    extract_children_from_frontmatter,
    is_doc_type,
)


def has_acceptance_record(ticket_content: str, logger) -> bool:
    """
    檢查 Ticket 是否有驗收記錄

    尋找以下關鍵字：
    - 驗收結果: 通過
    - Acceptance Audit Report
    - 驗收通過
    - 驗收者：
    - Auditor:
    - PM 直接驗收
    - acceptance-auditor

    Args:
        ticket_content: Ticket 檔案內容
        logger: 日誌物件

    Returns:
        bool - 是否有驗收記錄
    """
    acceptance_keywords = [
        "驗收結果: 通過",
        "Acceptance Audit Report",
        "驗收通過",
        "驗收者：",
        "Auditor:",
        "PM 直接驗收",
        "acceptance-auditor",
    ]

    for keyword in acceptance_keywords:
        if keyword in ticket_content:
            logger.info(f"找到驗收記錄關鍵字: {keyword}")
            return True

    logger.debug("未找到驗收記錄")
    return False


def verify_acceptance_record(
    ticket_content: str,
    frontmatter: dict,
    ticket_id: str,
    logger,
) -> Tuple[bool, Optional[str], bool, bool]:
    """
    驗收記錄驗證。

    Args:
        ticket_content: Ticket 檔案內容
        frontmatter: Ticket frontmatter 結構
        ticket_id: Ticket ID
        logger: 日誌物件

    Returns:
        tuple - (should_block, warning_message, should_check_acceptance, has_acceptance)
    """
    ticket_type = frontmatter.get("type")
    title = frontmatter.get("title", "未知")

    # 決定是否需要檢查驗收
    should_check_acceptance = True
    children = extract_children_from_frontmatter(frontmatter, logger)

    if is_doc_type(ticket_type) and not children:
        logger.info(f"Ticket {ticket_id} 為 DOC 類型且無子任務，豁免驗收檢查")
        should_check_acceptance = False

    has_accept = has_acceptance_record(ticket_content, logger)

    if should_check_acceptance and not has_accept:
        warning_msg = format_message(
            GateMessages.ACCEPTANCE_RECORD_MISSING_WARNING,
            ticket_id=ticket_id,
            ticket_type=ticket_type,
            title=title,
        )
        logger.warning(f"Ticket {ticket_id} 未找到驗收記錄 - 輸出警告")
        return False, warning_msg, should_check_acceptance, has_accept

    logger.info(f"Ticket {ticket_id} 驗收檢查通過")
    return False, None, should_check_acceptance, has_accept
