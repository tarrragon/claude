"""
Sibling Checker - 同 Wave pending sibling tickets 檢查（場景 #9）

查詢同 Wave 中的 pending sibling tickets，用於 Handoff 方向選擇提醒。
"""

import sys
from pathlib import Path
from typing import List

# 加入 hooks 目錄（acceptance_checkers 的上層）
_hooks_dir = Path(__file__).parent.parent
if str(_hooks_dir) not in sys.path:
    sys.path.insert(0, str(_hooks_dir))

from hook_utils import (
    parse_ticket_frontmatter,
    scan_ticket_files_by_version,
    extract_version_from_ticket_id,
    extract_wave_from_ticket_id,
)


def find_pending_sibling_tickets(
    ticket_id: str,
    project_dir: Path,
    logger,
) -> List[str]:
    """
    查詢同 Wave 中的 pending sibling tickets

    搜尋邏輯:
    1. 從 ticket_id 提取 wave 號和版本號
    2. 掃描 docs/work-logs/v{version}/tickets/ 目錄
    3. 找出所有同 Wave 且 status=pending 的 tickets
    4. 排除當前 ticket 自身

    Args:
        ticket_id: 當前 Ticket ID (e.g., "0.1.0-W22-025")
        project_dir: 專案根目錄
        logger: 日誌物件

    Returns:
        list - pending sibling ticket ID 清單
    """
    wave_num = extract_wave_from_ticket_id(ticket_id)
    version = extract_version_from_ticket_id(ticket_id)

    if wave_num is None or version is None:
        logger.warning(f"無法從 {ticket_id} 提取 wave 或 version，返回空清單")
        return []

    tickets_dir = project_dir / "docs" / "work-logs" / f"v{version}" / "tickets"

    if not tickets_dir.exists():
        logger.debug(f"Tickets 目錄不存在: {tickets_dir}，返回空清單")
        return []

    logger.info(f"掃描 sibling tickets 在 Wave {wave_num}，目錄: {tickets_dir}")

    sibling_tickets = []

    try:
        ticket_files = scan_ticket_files_by_version(project_dir, version, logger)
        for ticket_file in sorted(ticket_files):
            try:
                file_ticket_id = ticket_file.stem

                if file_ticket_id == ticket_id:
                    logger.debug(f"排除自身 Ticket: {file_ticket_id}")
                    continue

                file_wave = extract_wave_from_ticket_id(file_ticket_id)
                if file_wave != wave_num:
                    logger.debug(f"不同 Wave: {file_ticket_id} (Wave {file_wave})")
                    continue

                content = ticket_file.read_text(encoding="utf-8")
                frontmatter = parse_ticket_frontmatter(content)
                status = frontmatter.get("status", "unknown")

                if status == "pending":
                    sibling_tickets.append(file_ticket_id)
                    logger.info(f"找到 pending sibling ticket: {file_ticket_id}")
                else:
                    logger.debug(f"非 pending 狀態，排除: {file_ticket_id} (status: {status})")

            except Exception as e:
                logger.warning(f"讀取 Ticket 檔案失敗 {ticket_file}: {e}")
                continue

    except Exception as e:
        logger.warning(f"掃描 sibling tickets 失敗: {e}")
        return []

    logger.info(f"掃描完成，共找到 {len(sibling_tickets)} 個 pending sibling tickets: {sibling_tickets}")
    return sibling_tickets
