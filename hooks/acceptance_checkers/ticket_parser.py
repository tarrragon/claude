"""
Ticket Parser - Ticket frontmatter 欄位提取和型別判斷

負責從 Ticket frontmatter 提取 children、status、type 等欄位，
以及判斷 Ticket 類型（DOC/ANA）。
"""

import sys
from pathlib import Path
from datetime import datetime
from typing import Optional, List

# 加入 hooks 目錄（acceptance_checkers 的上層）
_hooks_dir = Path(__file__).parent.parent
if str(_hooks_dir) not in sys.path:
    sys.path.insert(0, str(_hooks_dir))

from hook_utils import parse_ticket_date


def extract_children_from_frontmatter(frontmatter: dict, logger) -> List[str]:
    """
    從 frontmatter 提取 children 欄位

    Args:
        frontmatter: Ticket frontmatter 結構
        logger: 日誌物件

    Returns:
        list - 子任務 ID 清單
    """
    children_raw = frontmatter.get("children", [])

    # YAML 解析後可能是 list 或 string（取決於解析器）
    if isinstance(children_raw, list):
        # 已解析為 list：過濾空值
        children = [str(c).strip() for c in children_raw if c]
    elif isinstance(children_raw, str):
        children_str = children_raw.strip()
        if not children_str:
            logger.debug("Ticket 無 children 欄位")
            return []
        # 解析 YAML 清單格式 (e.g., "- 0.31.0-W4-036.1\n- 0.31.0-W4-036.2")
        children = []
        for line in children_str.split("\n"):
            line = line.strip()
            if line.startswith("-"):
                child_id = line[1:].strip()
                if child_id:
                    children.append(child_id)
    else:
        logger.debug("Ticket 無 children 欄位")
        return []

    if not children:
        logger.debug("Ticket 無 children 欄位")
        return []

    logger.info(f"提取 {len(children)} 個子任務: {children}")
    return children


def get_ticket_status(frontmatter: dict, logger) -> Optional[str]:
    """
    從 Ticket frontmatter 提取狀態

    Args:
        frontmatter: Ticket frontmatter 結構
        logger: 日誌物件

    Returns:
        str - Ticket 狀態或 None
    """
    status = frontmatter.get("status")

    if status:
        logger.debug(f"Ticket 狀態: {status}")

    return status


def get_ticket_type(frontmatter: dict, logger) -> Optional[str]:
    """
    從 Ticket frontmatter 提取型別

    Args:
        frontmatter: Ticket frontmatter 結構
        logger: 日誌物件

    Returns:
        str - Ticket 型別或 None
    """
    ticket_type = frontmatter.get("type")

    if ticket_type:
        logger.debug(f"Ticket 型別: {ticket_type}")

    return ticket_type


def is_doc_type(ticket_type: Optional[str]) -> bool:
    """判斷是否為 DOC 類型 Ticket"""
    return ticket_type is not None and ticket_type.upper() == "DOC"


def is_ana_type(ticket_type: Optional[str]) -> bool:
    """判斷是否為 ANA 類型 Ticket"""
    return ticket_type is not None and ticket_type.upper() == "ANA"


def get_ticket_start_time(frontmatter: dict, logger) -> Optional[datetime]:
    """取得 Ticket 開始執行的時間，用於 error-pattern 偵測基準。

    優先使用 started_at（認領時間，有精確時間戳），
    fallback 到 created（建立時間，僅日期精度）。

    Args:
        frontmatter: Ticket frontmatter 結構
        logger: 日誌物件

    Returns:
        datetime 物件或 None（無法解析時）
    """
    try:
        # 優先使用 started_at（精確時間戳）
        started_at = frontmatter.get("started_at")
        if started_at:
            dt = parse_ticket_date(started_at, logger)
            if dt:
                logger.info(f"使用 started_at 作為 error-pattern 偵測基準: {dt.isoformat()}")
                return dt

        # Fallback 到 created（僅日期精度）
        logger.info("started_at 不可用，fallback 到 created")
        created_value = frontmatter.get("created")
        if not created_value:
            logger.warning("Ticket frontmatter 缺少 created 欄位")
            return None

        dt = parse_ticket_date(created_value, logger)
        if dt:
            logger.info(f"使用 created 作為 error-pattern 偵測基準: {dt.isoformat()}")
        return dt

    except Exception as e:
        logger.warning(f"解析 ticket 開始時間失敗: {e}")
        sys.stderr.write(f"WARNING: 解析 ticket 開始時間失敗: {e}\n")
        return None
