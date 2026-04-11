"""
ANA Spawned Checker - ANA Ticket 後續 Ticket 檢查

檢查 ANA（分析）Ticket 是否已將分析結論轉化為可追蹤的子任務或獨立 Ticket。
"""

import sys
from pathlib import Path
from typing import Optional, Tuple, List

# 加入 hooks 目錄（acceptance_checkers 的上層）
_hooks_dir = Path(__file__).parent.parent
if str(_hooks_dir) not in sys.path:
    sys.path.insert(0, str(_hooks_dir))

from lib.hook_messages import GateMessages, format_message
from acceptance_checkers.ticket_parser import extract_children_from_frontmatter


def extract_spawned_tickets_from_frontmatter(frontmatter: dict, logger) -> List[str]:
    """
    從 frontmatter 提取 spawned_tickets 欄位

    Args:
        frontmatter: Ticket frontmatter 結構
        logger: 日誌物件

    Returns:
        list - 後續 Ticket ID 清單
    """
    spawned_raw = frontmatter.get("spawned_tickets", [])

    # YAML 解析後可能是 list 或 string（取決於解析器）
    if isinstance(spawned_raw, list):
        # 已解析為 list：過濾空值
        spawned = [str(s).strip() for s in spawned_raw if s]
    elif isinstance(spawned_raw, str):
        spawned_str = spawned_raw.strip()
        if not spawned_str:
            logger.debug("Ticket 無 spawned_tickets 欄位")
            return []
        # 解析 YAML 清單格式 (e.g., "- 0.31.0-W4-036\n- 0.31.0-W4-037")
        spawned = []
        for line in spawned_str.split("\n"):
            line = line.strip()
            if line.startswith("-"):
                ticket_id = line[1:].strip()
                if ticket_id:
                    spawned.append(ticket_id)
    else:
        logger.debug("Ticket 無 spawned_tickets 欄位")
        return []

    if not spawned:
        logger.debug("Ticket 無 spawned_tickets 欄位")
        return []

    logger.info(f"提取 {len(spawned)} 個後續 Ticket: {spawned}")
    return spawned


def check_ana_has_spawned_tickets(
    frontmatter: dict, logger
) -> Tuple[bool, Optional[str]]:
    """
    檢查 ANA Ticket 是否有後續 Ticket（children 或 spawned_tickets）

    Args:
        frontmatter: Ticket frontmatter 結構
        logger: 日誌物件

    Returns:
        tuple - (should_warn, warning_message)
            - should_warn: 是否應輸出警告
            - warning_message: 警告訊息或 None（不阻擋，僅警告）
    """
    children = extract_children_from_frontmatter(frontmatter, logger)
    spawned = extract_spawned_tickets_from_frontmatter(frontmatter, logger)

    if not children and not spawned:
        title = frontmatter.get("title", "未知")
        ticket_id = frontmatter.get("id", "未知")
        warning_msg = format_message(
            GateMessages.ANA_MISSING_SPAWNED_TICKETS_WARNING,
            ticket_id=ticket_id,
            title=title,
        )
        logger.warning(f"ANA Ticket {ticket_id} 缺少後續 Ticket - 輸出警告")
        sys.stderr.write(
            f"WARNING: ANA Ticket {ticket_id} 缺少後續 Ticket（children 或 spawned_tickets）\n"
        )
        return True, warning_msg

    logger.info(f"ANA Ticket 有後續 Ticket: children={len(children)}, spawned={len(spawned)}")
    return False, None
