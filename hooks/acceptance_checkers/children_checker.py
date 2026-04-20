"""
Children Checker - 子任務完成度檢查（遞迴，含 closed/completed 終態）

檢查父 Ticket 的所有後代（子、孫…）是否已落入終止狀態
（`completed` 或 `closed`），未完成時產生阻擋訊息。

設計理念（對應 0.18.0-W10-036 任務鏈核心哲學）：
    父 Ticket 的責任是「問題被解決」，不是「分析報告寫完」。
    子 Ticket 實作/驗證完成才是父責任履行的證據；
    若後代仍有未完成項，父就不應該 complete。
"""

import sys
from pathlib import Path
from typing import Optional, Tuple, List, Set

# 加入 hooks 目錄（acceptance_checkers 的上層）
_hooks_dir = Path(__file__).parent.parent
if str(_hooks_dir) not in sys.path:
    sys.path.insert(0, str(_hooks_dir))

# 加入 .claude/skills/ticket 目錄以解析 ticket_system package
# W14-004: TERMINAL_STATUSES 單一來源由 ticket_system.constants 提供，
# hook 與 skill 雙邊從同處 import，避免雙邊宣告與語意飄移。
# W14-016: 改用 package 頂層 ticket_system.constants（非 lib/constants），
# 避免觸發 lib/__init__.py eager-import ticket_loader → parser → yaml 依賴鏈。
# hook 以系統 Python 啟動（無 yaml），lib 路徑會噴 ModuleNotFoundError（已觀察 97 次）。
_ticket_skill_dir = _hooks_dir.parent / "skills" / "ticket"
if str(_ticket_skill_dir) not in sys.path:
    sys.path.insert(0, str(_ticket_skill_dir))

from hook_utils import find_ticket_file, parse_ticket_frontmatter
from lib.hook_messages import GateMessages, format_message
from acceptance_checkers.ticket_parser import extract_children_from_frontmatter
from ticket_system.constants import TERMINAL_STATUSES  # noqa: F401（re-export 供 ana_spawned_checker 向後相容引用）


def _extract_children_robust(
    ticket_file: Path, frontmatter: dict, logger
) -> List[str]:
    """解析 children：使用 frontmatter dict。

    W11-003.4 修復後，hook_utils._parse_yaml_lines 已正確處理頂層
    YAML 列表（block-style 與 flow-style），不再需要原始文字 fallback。
    保留 ticket_file 參數以維持呼叫端簽名向後相容。
    """
    return extract_children_from_frontmatter(frontmatter, logger)


def check_children_completed(
    children: List[str], project_dir: Path, logger
) -> Tuple[bool, List[Tuple[str, str, str]]]:
    """
    檢查所有子任務是否已完成（非遞迴，只檢查直接子）。

    Args:
        children: 子任務 ID 清單
        project_dir: 專案根目錄
        logger: 日誌物件

    Returns:
        tuple - (all_completed, incomplete_children)
            - all_completed: 是否全部完成（含 closed）
            - incomplete_children: [(child_id, title, status), ...] 未完成清單
    """
    incomplete_children: List[Tuple[str, str, str]] = []

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

            if status not in TERMINAL_STATUSES:
                logger.warning(f"子任務未完成: {child_id} (status={status})")
                incomplete_children.append((child_id, title, status))
            else:
                logger.info(f"子任務已完成: {child_id} (status={status})")

        except Exception as e:
            logger.warning(f"無法讀取子任務檔案 {child_file}: {e}")
            incomplete_children.append((child_id, "未知", "read_error"))

    all_completed = len(incomplete_children) == 0
    return all_completed, incomplete_children


def _collect_incomplete_descendants(
    children: List[str],
    project_dir: Path,
    logger,
    visited: Optional[Set[str]] = None,
) -> List[Tuple[str, str, str]]:
    """
    遞迴收集所有未完成的後代（子、孫…）。

    行為（對應 AC 1「遞迴含孫層」）：
    - 每個 child 若非 completed/closed → 列為未完成
    - 每個 child 無論自身狀態為何，仍往下檢查其後代（避免子 completed
      但孫 pending 的情況被忽略）
    - 使用 visited 集合防止循環引用造成的無限遞迴

    Args:
        children: 當前層要檢查的 Ticket ID 清單
        project_dir: 專案根目錄
        logger: 日誌物件
        visited: 已訪問 ID 集合（防循環）

    Returns:
        List[(id, title, status)] — 所有層級中未完成的 Ticket
    """
    if visited is None:
        visited = set()

    incomplete: List[Tuple[str, str, str]] = []

    for child_id in children:
        if child_id in visited:
            logger.debug(f"跳過已訪問的 Ticket（防循環）: {child_id}")
            continue
        visited.add(child_id)

        child_file = find_ticket_file(child_id, project_dir, logger)

        if not child_file:
            logger.warning(f"無法找到子任務檔案: {child_id}")
            incomplete.append((child_id, "未知", "not_found"))
            continue

        try:
            content = child_file.read_text(encoding="utf-8")
            frontmatter = parse_ticket_frontmatter(content)
            status = frontmatter.get("status", "unknown")
            title = frontmatter.get("title", "未知")
        except Exception as e:
            logger.warning(f"無法讀取子任務檔案 {child_file}: {e}")
            incomplete.append((child_id, "未知", "read_error"))
            continue

        if status not in TERMINAL_STATUSES:
            logger.warning(f"後代未完成: {child_id} (status={status})")
            incomplete.append((child_id, title, status))

        # 無論此層狀態為何，均遞迴檢查下一層（孫層防護）
        grand_children = _extract_children_robust(child_file, frontmatter, logger)
        if grand_children:
            logger.debug(
                f"{child_id} 有 {len(grand_children)} 個下層 Ticket，遞迴檢查"
            )
            incomplete.extend(
                _collect_incomplete_descendants(
                    grand_children, project_dir, logger, visited
                )
            )

    return incomplete


def check_children_completed_from_frontmatter(
    ticket_file: Path,
    frontmatter: dict,
    project_dir: Path,
    ticket_id: str,
    logger,
) -> Tuple[bool, Optional[str]]:
    """
    從 frontmatter 檢查子任務完成度（orchestrator 呼叫入口）。

    檢查規則（對應 0.18.0-W10-036.2 AC）：
    1. 遞迴檢查所有後代（子 + 孫 + …）
    2. 任一後代非 `completed` 且非 `closed` → block (exit 2)
    3. 錯誤訊息列出所有未完成後代 ID、標題、狀態
    4. 無子任務 → pass
    5. 所有後代 completed/closed → pass

    Args:
        ticket_file: Ticket 檔案路徑
        frontmatter: Ticket frontmatter 結構
        project_dir: 專案根目錄
        ticket_id: Ticket ID
        logger: 日誌物件

    Returns:
        tuple - (should_block, error_message)
            - should_block: True 表示必須阻止 complete
            - error_message: block 時的錯誤訊息（pass 時為 None）
    """
    children = _extract_children_robust(ticket_file, frontmatter, logger)

    if not children:
        return False, None

    logger.info(f"Ticket {ticket_id} 有 {len(children)} 個直接子任務（遞迴檢查後代）")

    incomplete = _collect_incomplete_descendants(
        children, project_dir, logger, visited={ticket_id}
    )

    if incomplete:
        title = frontmatter.get("title", "未知")
        incomplete_list = "\n".join(
            f"  - {child_id}: {child_title} (status: {status})"
            for child_id, child_title, status in incomplete
        )
        error_msg = format_message(
            GateMessages.CHILDREN_INCOMPLETE_ERROR,
            ticket_id=ticket_id,
            title=title,
            incomplete_list=incomplete_list,
        )
        logger.error(
            f"Ticket {ticket_id} 有 {len(incomplete)} 個未完成後代 - 阻擋執行"
        )
        return True, error_msg

    logger.info(f"Ticket {ticket_id} 所有後代皆已 completed/closed")
    return False, None
