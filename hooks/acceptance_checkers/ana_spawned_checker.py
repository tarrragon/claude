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

from hook_utils import find_ticket_file, parse_ticket_frontmatter
from lib.hook_messages import GateMessages, format_message
from acceptance_checkers.ticket_parser import extract_children_from_frontmatter
# 單一真實來源：terminal 狀態定義由 children_checker 集中管理（W12-004）
from acceptance_checkers.children_checker import TERMINAL_STATUSES


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


def check_spawned_tickets_status(
    spawned: List[str],
    project_dir: Path,
    logger,
) -> Optional[str]:
    """檢查 spawned tickets 的狀態，列出非 terminal 的項目。

    Phase 1 警告層（W12-004）：
        當防護性 ANA 的 spawned IMP 仍處於 pending/in_progress/blocked 時，
        產生警告訊息（不 block），讓 PM 看到防護缺口的可見訊號。

    Shallow 一層（明示不 recurse）：
        本函式只檢查 spawned 自身的 status，不遞迴進 spawned 的子任務。
        避免與 children_checker 的責任重疊——children 鏈完整性由
        check_children_completed_from_frontmatter 負責。

    Args:
        spawned: spawned ticket ID 清單
        project_dir: 專案根目錄
        logger: 日誌物件

    Returns:
        Optional[str] - 警告訊息（spawned 任一非 terminal 時）或 None（全 terminal 或 spawned 為空時）
    """
    if not spawned:
        return None

    non_terminal: List[Tuple[str, str]] = []  # [(ticket_id, status), ...]

    for spawned_id in spawned:
        spawned_file = find_ticket_file(spawned_id, project_dir, logger)

        if not spawned_file:
            logger.warning(f"無法找到 spawned ticket 檔案: {spawned_id}")
            non_terminal.append((spawned_id, "not_found"))
            continue

        try:
            content = spawned_file.read_text(encoding="utf-8")
            spawned_fm = parse_ticket_frontmatter(content)
            status = spawned_fm.get("status", "unknown")

            if status not in TERMINAL_STATUSES:
                logger.warning(
                    f"spawned ticket 非 terminal: {spawned_id} (status={status})"
                )
                non_terminal.append((spawned_id, status))
            else:
                logger.info(
                    f"spawned ticket terminal: {spawned_id} (status={status})"
                )
        except Exception as e:
            logger.warning(f"讀取 spawned ticket 失敗 {spawned_file}: {e}")
            non_terminal.append((spawned_id, "read_error"))

    if not non_terminal:
        return None

    non_terminal_list = "\n".join(
        f"  - {sid}: status={status}" for sid, status in non_terminal
    )

    warning_msg = format_message(
        GateMessages.ANA_SPAWNED_NON_TERMINAL_WARNING,
        non_terminal_list=non_terminal_list,
        non_terminal_count=len(non_terminal),
    )
    return warning_msg


def check_spawned_tickets_blocking(
    ticket_id: str,
    title: str,
    spawned: List[str],
    project_dir: Path,
    logger,
) -> Tuple[bool, Optional[str]]:
    """檢查 spawned tickets 是否全完成；未完成時回傳阻擋訊息（W15-003）。

    循環引用防護：
        使用 visited set 記錄已查詢的 spawned_id，避免 A spawns B / B spawns A 造成無限遞迴。
        此為 shallow 一層檢查（不 recurse 進 spawned 的 children），
        但仍檢查 spawned 的 spawned（追蹤衍生鏈）。

    Args:
        ticket_id: 當前 ANA Ticket ID
        title: 當前 Ticket 標題
        spawned: spawned ticket ID 清單
        project_dir: 專案根目錄
        logger: 日誌物件

    Returns:
        (should_block, error_message):
            - should_block=True + 完整阻擋訊息（未全完成）
            - should_block=False + None（全完成或 spawned 為空）
    """
    if not spawned:
        return False, None

    # Shallow 一層檢查（對齊 acceptance_auditor.validate_spawned_tickets_completed）：
    # 只檢查 spawned 自身的 status，不 recurse 進 spawned 的 children/spawned。
    # visited 集合保留給循環引用防護（本 shallow 版不會觸發，但保護未來升級）。
    non_terminal: List[Tuple[str, str]] = []
    visited: set = {ticket_id}

    for sid in spawned:
        if sid in visited:
            continue
        visited.add(sid)
        sfile = find_ticket_file(sid, project_dir, logger)
        if not sfile:
            non_terminal.append((sid, "not_found"))
            continue
        try:
            content = sfile.read_text(encoding="utf-8")
            fm = parse_ticket_frontmatter(content)
            status = fm.get("status", "unknown")
            if status not in TERMINAL_STATUSES:
                non_terminal.append((sid, status))
        except Exception as e:
            logger.warning(f"讀取 spawned ticket 失敗 {sfile}: {e}")
            non_terminal.append((sid, "read_error"))

    if not non_terminal:
        logger.info(f"ANA {ticket_id} 所有 spawned tickets 全 terminal")
        return False, None

    non_terminal_ids = {sid for sid, _ in non_terminal}
    direct_completed = sum(1 for sid in spawned if sid not in non_terminal_ids)
    non_terminal_list = "\n".join(
        f"  - {sid}: status={status}" for sid, status in non_terminal
    )

    error_msg = format_message(
        GateMessages.ANA_SPAWNED_INCOMPLETE_ERROR,
        ticket_id=ticket_id,
        title=title,
        completed_count=direct_completed,
        total_count=len(spawned),
        non_terminal_count=len(non_terminal),
        non_terminal_list=non_terminal_list,
    )
    logger.error(
        f"ANA {ticket_id} spawned_tickets 未全完成 "
        f"（{direct_completed}/{len(spawned)}）- 阻擋 complete"
    )
    sys.stderr.write(
        f"ERROR: ANA {ticket_id} spawned_tickets 未全完成，阻擋 complete\n"
    )
    return True, error_msg
