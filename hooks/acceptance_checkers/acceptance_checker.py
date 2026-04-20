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


def _all_acceptance_items_checked(acceptance_list) -> bool:
    """判定 frontmatter acceptance list 是否全部項目以 [x] 開頭（勾選完成）。

    回傳 True 僅當 list 非空且所有項目（字串，strip 後）以 `[x]` 開頭。
    非字串項目或部分未勾選一律回傳 False。
    """
    if not acceptance_list or not isinstance(acceptance_list, list):
        return False
    for item in acceptance_list:
        if not isinstance(item, str):
            return False
        if not item.strip().startswith("[x]"):
            return False
    return True


def has_acceptance_record(
    ticket_content: str,
    logger,
    frontmatter: Optional[dict] = None,
) -> bool:
    """
    檢查 Ticket 是否有驗收記錄。

    資料源優先序（與 CLI track_acceptance.py 寫入端對齊）：
      1. 優先檢查 frontmatter acceptance list：全部項目 `[x]` 勾選 → True
      2. 空 list / 部分勾選 / 無欄位 → fallback body 關鍵字掃描

    Body 關鍵字（fallback，保留舊 Ticket 相容）：
    - 驗收結果: 通過
    - Acceptance Audit Report
    - 驗收通過
    - 驗收者：
    - Auditor:
    - PM 直接驗收
    - acceptance-auditor

    Args:
        ticket_content: Ticket 檔案內容（body 文字）
        logger: 日誌物件
        frontmatter: Ticket frontmatter 結構（可選；None 表示舊 caller）

    Returns:
        bool - 是否有驗收記錄
    """
    # 優先：frontmatter acceptance list 全勾選
    if frontmatter is not None:
        acceptance_list = frontmatter.get("acceptance")
        if _all_acceptance_items_checked(acceptance_list):
            logger.info(
                f"frontmatter acceptance list 全部勾選 "
                f"({len(acceptance_list)} 項)"
            )
            return True

    # Fallback：body 關鍵字掃描
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

    has_accept = has_acceptance_record(ticket_content, logger, frontmatter=frontmatter)

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
