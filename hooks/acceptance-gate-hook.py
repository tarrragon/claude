#!/usr/bin/env -S uv run --quiet --script
# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///

"""
Acceptance Gate Hook - 驗收流程完整引導

在 `ticket track complete` 執行前檢查並引導驗收流程。

功能：
- 監控 Bash 工具中的 ticket track complete 命令
- 檢查子任務是否全部完成（阻塊）
- 檢查是否有驗收記錄（警告）
- 檢查同 Wave 中的 pending sibling tickets（場景 #9）
- 在檢查完成後輸出 AskUserQuestion 場景提醒：
  * 場景 #1（complete 前）：驗收方式確認（標準/簡化/先完成後補）
  * 場景 #2（complete 後的邏輯）：complete 後下一步選擇（下個 Ticket/Wave 收尾/版本發布）
  * 場景 #9（Handoff 方向選擇）：同 Wave 中有 2+ pending sibling tickets 時觸發
  * 場景 #17（錯誤學習確認）：執行期間新增 error-pattern 時觸發（與 #1/#9 並存，不互斥）
  * 補充說明：此時仍在 PreToolUse，complete 尚未執行，故提醒涵蓋整個 complete 流程
  * 修復 W22-012：#17 原本會壓制 #1/#9，現已改為並存觸發
- 使用 hook_utils 統一日誌系統

Exit Code：
- 0 (EXIT_SUCCESS): 命令允許執行
- 2 (EXIT_BLOCK): 阻止執行（子任務未完成）
- 1 (EXIT_ERROR): Hook 執行錯誤

Hook 類型: PreToolUse
觸發時機: Bash 工具執行前，命令含 "ticket track complete" 或 "ticket track batch-complete"

Matcher 條件（settings.json）:
  matcher: "Bash"
  command 須含 "ticket track complete" 或 "ticket track batch-complete"

使用方式:
    echo '{"tool_name":"Bash","tool_input":{"command":"ticket track complete 0.31.0-W4-036"}}' | python3 acceptance-gate-hook.py
"""

import sys
import json
from pathlib import Path

# 加入 hook_utils 路徑（相同目錄）
_hooks_dir = Path(__file__).parent
if _hooks_dir not in [p for p in sys.path if Path(p) == _hooks_dir]:
    sys.path.insert(0, str(_hooks_dir))

from hook_utils import (
    setup_hook_logging,
    run_hook_safely,
    read_json_from_stdin,
    extract_tool_input,
    parse_ticket_frontmatter,
    parse_ticket_date,
    check_error_patterns_changed,
    get_project_root,
    scan_ticket_files_by_version,
    find_ticket_file,
)
from lib.hook_messages import GateMessages, CoreMessages, AskUserQuestionMessages, format_message

import re
from datetime import datetime
from typing import Dict, Any, Optional, Tuple, List, NamedTuple, TypedDict


# ============================================================================
# 資料結構定義
# ============================================================================

class TicketFrontmatter(TypedDict, total=False):
    """Ticket Frontmatter 結構

    提供型別檢查和文件化，欄位皆可選（因為不是所有 Ticket 都有所有欄位）。
    """
    id: str
    title: str
    type: str
    status: str
    children: str
    created: str
    started_at: str
    priority: str


class AcceptanceCheckResult(NamedTuple):
    """驗收狀態檢查結果"""
    should_block: bool
    has_acceptance: bool
    message: Optional[str]
    has_new_error_patterns: bool
    new_error_pattern_files: List[str]
    pending_sibling_tickets: List[str] = []
    task_type: str = ""
    priority: str = ""


# ============================================================================
# 常數定義
# ============================================================================

# Exit Code
EXIT_SUCCESS = 0
EXIT_ERROR = 1
EXIT_BLOCK = 2

# Ticket ID 格式正則表達式
TICKET_ID_PATTERN = r'\d+\.\d+\.\d+-W\d+-\d+(?:\.\d+)*'


# ============================================================================
# 日誌設置
# ============================================================================


def validate_input(input_data: Dict[str, Any], logger) -> bool:
    """
    驗證輸入格式

    Args:
        input_data: Hook 輸入資料
        logger: 日誌物件

    Returns:
        bool - 輸入格式是否正確
    """
    # PreToolUse Hook 需要 tool_name 和 tool_input
    if "tool_name" not in input_data or "tool_input" not in input_data:
        logger.error("缺少必要欄位: tool_name 或 tool_input")
        return False

    return True


# ============================================================================
# 命令識別
# ============================================================================

def extract_ticket_id_from_command(command: str, logger) -> Optional[str]:
    """
    從命令中提取 Ticket ID

    Args:
        command: Bash 命令字串
        logger: 日誌物件

    Returns:
        str - Ticket ID 或 None
    """
    # 搜尋 ticket track complete 或 ticket track batch-complete 命令
    if "ticket track complete" not in command and "ticket track batch-complete" not in command:
        return None

    # 從命令中提取 Ticket ID（格式：\d+\.\d+\.\d+-W\d+-\d+(?:\.\d+)*）
    match = re.search(TICKET_ID_PATTERN, command)
    if match:
        ticket_id = match.group(0)
        logger.info(f"從命令中提取 Ticket ID: {ticket_id}")
        return ticket_id

    logger.debug(f"無法從命令中提取 Ticket ID: {command}")
    return None


def is_complete_command(command: str) -> bool:
    """
    判斷是否為 ticket track complete 命令

    Args:
        command: Bash 命令字串

    Returns:
        bool - 是否為 complete 命令
    """
    return "ticket track complete" in command or "ticket track batch-complete" in command






# ============================================================================
# 子任務檢查
# ============================================================================

def extract_children_from_frontmatter(frontmatter: TicketFrontmatter, logger) -> List[str]:
    """
    從 frontmatter 提取 children 欄位

    Args:
        frontmatter: Ticket frontmatter 結構
        logger: 日誌物件

    Returns:
        list - 子任務 ID 清單
    """
    children_str = frontmatter.get("children", "").strip()

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

    logger.info(f"提取 {len(children)} 個子任務: {children}")
    return children


def get_ticket_status(frontmatter: TicketFrontmatter, logger) -> Optional[str]:
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


def get_ticket_type(frontmatter: TicketFrontmatter, logger) -> Optional[str]:
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


def check_children_completed(children: List[str], project_dir: Path, logger) -> Tuple[bool, List[Tuple[str, str, str]]]:
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


# ============================================================================
# 驗收記錄檢查
# ============================================================================

def has_acceptance_record(ticket_content: str, logger) -> bool:
    """
    檢查 Ticket 是否有驗收記錄

    尋找以下關鍵字：
    - 驗收結果: 通過
    - Acceptance Audit Report
    - 驗收通過
    - 驗收者：
    - Auditor:

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


def is_doc_type(ticket_type: Optional[str]) -> bool:
    """
    判斷是否為 DOC 類型 Ticket

    Args:
        ticket_type: Ticket 類型

    Returns:
        bool - 是否為 DOC 類型
    """
    return ticket_type and ticket_type.upper() == "DOC"


# ============================================================================
# Sibling Ticket 檢查（場景 #9）
# ============================================================================

def extract_wave_from_ticket_id(ticket_id: str, logger) -> Optional[int]:
    """
    從 Ticket ID 中提取 Wave 號

    格式範例: "0.1.0-W22-025" → wave=22

    Args:
        ticket_id: Ticket ID (格式: version-WN-number)
        logger: 日誌物件

    Returns:
        int - Wave 號，或 None（格式不符）
    """
    # 使用正則表達式提取 W 後面的數字
    wave_match = re.search(r'-W(\d+)-', ticket_id)
    if wave_match:
        wave_num = int(wave_match.group(1))
        logger.debug(f"從 Ticket ID {ticket_id} 提取 Wave 號: {wave_num}")
        return wave_num
    else:
        logger.warning(f"無法從 Ticket ID 中提取 Wave 號: {ticket_id}")
        return None


def extract_version_from_ticket_id(ticket_id: str, logger) -> Optional[str]:
    """
    從 Ticket ID 中提取版本號

    格式範例: "0.1.0-W22-025" → version="0.1.0"

    Args:
        ticket_id: Ticket ID (格式: version-WN-number)
        logger: 日誌物件

    Returns:
        str - 版本號，或 None（格式不符）
    """
    # 使用正則表達式提取版本號（版本號格式: \d+\.\d+\.\d+）
    version_match = re.match(r'(\d+\.\d+\.\d+)-W', ticket_id)
    if version_match:
        version = version_match.group(1)
        logger.debug(f"從 Ticket ID {ticket_id} 提取版本號: {version}")
        return version
    else:
        logger.warning(f"無法從 Ticket ID 中提取版本號: {ticket_id}")
        return None


def find_pending_sibling_tickets(
    ticket_id: str,
    project_dir: Path,
    logger
) -> List[str]:
    """
    查詢同 Wave 中的 pending sibling tickets

    搜尋邏輯:
    1. 從 ticket_id 提取 wave 號和版本號
    2. 掃描 docs/work-logs/v{version}/tickets/ 目錄
    3. 找出所有 "WN-" 中 N 相同的 tickets，且 status=pending
    4. 排除當前 ticket 自身
    5. 返回 pending sibling 清單（不排序，保持掃描順序）

    Args:
        ticket_id: 當前 Ticket ID (e.g., "0.1.0-W22-025")
        project_dir: 專案根目錄
        logger: 日誌物件

    Returns:
        list - pending sibling ticket ID 清單，若查詢失敗或無 sibling，返回 []
    """
    # 步驟 1: 提取 wave 號和版本號
    wave_num = extract_wave_from_ticket_id(ticket_id, logger)
    version = extract_version_from_ticket_id(ticket_id, logger)

    if wave_num is None or version is None:
        logger.warning(f"無法從 {ticket_id} 提取 wave 或 version，返回空清單")
        return []

    # 步驟 2: 構造 tickets 目錄路徑
    tickets_dir = project_dir / "docs" / "work-logs" / f"v{version}" / "tickets"

    if not tickets_dir.exists():
        logger.debug(f"Tickets 目錄不存在: {tickets_dir}，返回空清單")
        return []

    logger.info(f"掃描 sibling tickets 在 Wave {wave_num}，目錄: {tickets_dir}")

    sibling_tickets = []

    try:
        # 步驟 3-5: 掃描並過濾 tickets（使用共用函式）
        ticket_files = scan_ticket_files_by_version(project_dir, version, logger)
        for ticket_file in sorted(ticket_files):
            try:
                file_ticket_id = ticket_file.stem  # 移除 .md 副檔名

                # 排除當前 ticket 自身
                if file_ticket_id == ticket_id:
                    logger.debug(f"排除自身 Ticket: {file_ticket_id}")
                    continue

                # 檢查是否為同 Wave
                file_wave = extract_wave_from_ticket_id(file_ticket_id, logger)
                if file_wave != wave_num:
                    logger.debug(f"不同 Wave: {file_ticket_id} (Wave {file_wave})")
                    continue

                # 讀取檔案取得 status
                content = ticket_file.read_text(encoding="utf-8")
                frontmatter = parse_ticket_frontmatter(content)
                status = frontmatter.get("status", "unknown")

                # 篩選 pending 狀態
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


# ============================================================================
# Error Pattern 檢查
# ============================================================================

def _get_ticket_start_time(frontmatter: TicketFrontmatter, logger) -> Optional[datetime]:
    """取得 Ticket 開始執行的時間，用於 error-pattern 偵測基準。

    優先使用 started_at（認領時間，有精確時間戳），
    fallback 到 created（建立時間，僅日期精度）。

    Args:
        frontmatter: Ticket frontmatter 結構
        logger: 日誌物件

    Returns:
        datetime 物件或 None（無法解析時）

    說明：
        started_at 格式為 ISO 8601 字串，如 '2026-03-10T04:48:01'，精度為秒級。
        created 格式為簡單日期字串，如 '2026-03-10'，精度為日期級。
        場景 #17 檢查的是「Ticket 執行期間新增的 error-pattern」，起點應是
        started_at（認領時間），而非 created（建立時間）。
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


def get_ticket_created_time(frontmatter: TicketFrontmatter, logger) -> Optional[datetime]:
    """
    從 Ticket frontmatter 讀取 created 欄位並解析為 datetime

    [已棄用] 改用 _get_ticket_start_time，可自動使用 started_at（精確時間）。

    Args:
        frontmatter: Ticket frontmatter 結構
        logger: 日誌物件

    Returns:
        datetime 物件或 None（無法解析時）
    """
    try:
        # 取得 created 欄位值
        created_value = frontmatter.get("created")
        if not created_value:
            logger.warning("Ticket frontmatter 缺少 created 欄位")
            return None

        # 使用通用日期解析函式（來自 hook_utils）
        dt = parse_ticket_date(created_value, logger)
        if dt:
            logger.info(f"Ticket created at: {dt.isoformat()}")
        return dt

    except Exception as e:
        logger.warning(f"解析 ticket created 時間失敗: {e}")
        sys.stderr.write(f"WARNING: 解析 ticket created 時間失敗: {e}\n")
        return None


# ============================================================================
# 檢查邏輯
# ============================================================================

def _check_children_completed(ticket_file: Path, frontmatter: TicketFrontmatter, project_dir: Path, ticket_id: str, logger) -> Tuple[bool, Optional[str]]:
    """
    子任務完成度檢查。

    Args:
        ticket_file: Ticket 檔案路徑
        frontmatter: Ticket frontmatter 結構
        project_dir: 專案根目錄
        ticket_id: Ticket ID
        logger: 日誌物件

    Returns:
        tuple - (should_block, error_message)
            - should_block: 是否應阻擋執行
            - error_message: 錯誤訊息或 None
    """
    children = extract_children_from_frontmatter(frontmatter, logger)

    if not children:
        return False, None

    logger.info(f"Ticket {ticket_id} 有 {len(children)} 個子任務")
    all_completed, incomplete_children = check_children_completed(children, project_dir, logger)

    if not all_completed:
        # 子任務未完成 → 阻擋
        title = frontmatter.get("title", "未知")
        incomplete_list = "\n".join(
            f"  - {child_id}: {child_title} (status: {status})"
            for child_id, child_title, status in incomplete_children
        )
        error_msg = format_message(
            GateMessages.CHILDREN_INCOMPLETE_ERROR,
            ticket_id=ticket_id,
            title=title,
            incomplete_list=incomplete_list
        )
        logger.error(f"Ticket {ticket_id} 有未完成的子任務 - 阻擋執行")
        return True, error_msg

    logger.info(f"Ticket {ticket_id} 所有子任務已完成")
    return False, None


def _verify_acceptance_record(ticket_content: str, frontmatter: TicketFrontmatter, ticket_id: str, logger) -> Tuple[bool, Optional[str], bool, bool]:
    """
    驗收記錄驗證。

    Args:
        ticket_content: Ticket 檔案內容
        frontmatter: Ticket frontmatter 結構
        ticket_id: Ticket ID
        logger: 日誌物件

    Returns:
        tuple - (should_block, warning_message, should_check_acceptance, has_acceptance)
            - should_block: 是否應阻擋執行
            - warning_message: 警告訊息或 None
            - should_check_acceptance: 是否應檢查 error-pattern
            - has_acceptance: 是否有驗收記錄
    """
    ticket_type = frontmatter.get("type")
    title = frontmatter.get("title", "未知")

    # 決定是否需要檢查驗收
    should_check_acceptance = True
    children = extract_children_from_frontmatter(frontmatter, logger)

    if is_doc_type(ticket_type) and not children:
        logger.info(f"Ticket {ticket_id} 為 DOC 類型且無子任務，豁免驗收檢查")
        should_check_acceptance = False

    has_acceptance = has_acceptance_record(ticket_content, logger)

    if should_check_acceptance and not has_acceptance:
        # 未驗收 → 警告
        warning_msg = format_message(
            GateMessages.ACCEPTANCE_RECORD_MISSING_WARNING,
            ticket_id=ticket_id,
            ticket_type=ticket_type,
            title=title
        )
        logger.warning(f"Ticket {ticket_id} 未找到驗收記錄 - 輸出警告")
        return False, warning_msg, should_check_acceptance, has_acceptance

    logger.info(f"Ticket {ticket_id} 驗收檢查通過")
    return False, None, should_check_acceptance, has_acceptance




def check_acceptance_status(ticket_id: str, project_dir: Path, logger) -> AcceptanceCheckResult:
    """
    檢查 Ticket 的驗收狀態（主協調函式）

    此函式協調四個子檢查函式：
    1. 子任務完成度檢查
    2. 驗收記錄驗證
    3. Error-pattern 新增檢查
    4. Sibling tickets 完成度檢查（場景 #9）

    Args:
        ticket_id: Ticket ID
        project_dir: 專案根目錄
        logger: 日誌物件

    Returns:
        AcceptanceCheckResult 物件，包含：
            - should_block: 是否應該阻擋執行（子任務未完成）
            - has_acceptance: 是否有驗收記錄
            - message: 錯誤或警告訊息
            - has_new_error_patterns: 是否有新增/修改的 error-pattern
            - new_error_pattern_files: 新增/修改的 error-pattern 檔案清單
            - pending_sibling_tickets: 同 Wave 中的 pending sibling tickets（場景 #9）
    """
    # 找到 Ticket 檔案
    ticket_file = find_ticket_file(ticket_id, project_dir, logger)

    if not ticket_file:
        logger.error(f"找不到 Ticket 檔案: {ticket_id}")
        return AcceptanceCheckResult(False, False, None, False, [])

    try:
        # 一次讀取檔案及解析 frontmatter，避免重複讀取（問題 3 修復）
        content = ticket_file.read_text(encoding="utf-8")
        frontmatter = parse_ticket_frontmatter(content)

        # 步驟 1：檢查子任務完成度
        should_block, error_msg = _check_children_completed(ticket_file, frontmatter, project_dir, ticket_id, logger)
        if should_block:
            return AcceptanceCheckResult(True, False, error_msg, False, [])

        # 步驟 2：驗證驗收記錄
        should_block, warning_msg, should_check_acceptance, has_acceptance = _verify_acceptance_record(content, frontmatter, ticket_id, logger)

        # 問題 1 修復：不提前 return，繼續執行步驟 3 和 4，將 warning_msg 帶入最終結果
        if not warning_msg:
            logger.info(f"Ticket {ticket_id} 驗收檢查通過")

        # 步驟 3：檢查 error-pattern 新增
        has_new_error_patterns = False
        new_error_pattern_files = []

        if should_check_acceptance:
            # 使用 started_at（精確時間戳）做為基準，避免日期精度不足的誤報
            ticket_start_time = _get_ticket_start_time(frontmatter, logger)
            if ticket_start_time:
                # 檢查 error-patterns 目錄
                has_new_error_patterns, new_error_pattern_files = check_error_patterns_changed(
                    project_dir,
                    ticket_start_time,
                    logger
                )
                if has_new_error_patterns:
                    logger.info(f"發現 {len(new_error_pattern_files)} 個新增/修改的 error-pattern")
            else:
                logger.warning(f"無法取得 ticket 的開始時間，跳過 error-pattern 檢查")

        # 步驟 4：檢查 pending sibling tickets（場景 #9）
        pending_siblings = find_pending_sibling_tickets(ticket_id, project_dir, logger)
        logger.info(f"發現 {len(pending_siblings)} 個 pending sibling tickets")

        task_type = frontmatter.get("type", "")
        priority = frontmatter.get("priority", "")

        return AcceptanceCheckResult(
            False,
            has_acceptance,
            warning_msg,  # 將 warning_msg 帶入最終結果（不提前 return）
            has_new_error_patterns,
            new_error_pattern_files,
            pending_siblings,
            task_type,
            priority,
        )

    except Exception as e:
        logger.error(f"檢查驗收狀態失敗: {e}", exc_info=True)
        sys.stderr.write(f"ERROR: 檢查驗收狀態失敗: {e}\n")
        return AcceptanceCheckResult(False, False, None, False, [])


# ============================================================================
# 輸出生成
# ============================================================================

def generate_hook_output(
    ticket_id: str,
    check_result: AcceptanceCheckResult,
    project_dir: Path,
    logger,
) -> Dict[str, Any]:
    """
    生成 Hook 輸出

    Args:
        ticket_id: Ticket ID（用於日誌和調試）
        check_result: AcceptanceCheckResult 物件，包含驗收狀態和 sibling tickets
        project_dir: 專案根目錄（用於 sibling 查詢，已通過 check_result.pending_sibling_tickets 傳入）
        logger: 日誌物件（用於日誌記錄）

    Returns:
        dict - Hook 輸出 JSON

    優先級順序:
    1. 錯誤或警告訊息（should_block 或 message）
    2. Error-pattern 場景 #17 提醒（has_new_error_patterns）
    3. Handoff 方向選擇（場景 #9，pending siblings >= 2）
    4. complete 流程提醒（場景 #1，驗收方式確認）
    5. complete 後下一步提醒（場景 #2，路由選擇）
    """
    output = {
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "deny" if check_result.should_block else "allow"
        }
    }

    context_parts = []

    # 優先級 1：錯誤或警告訊息
    if check_result.message:
        context_parts.append(check_result.message)

    # 優先級 2：error-pattern 場景 #17 提醒（與 warning_msg 並存觸發）
    if check_result.has_new_error_patterns:
        file_list_formatted = "\n".join(f"  - {f}" for f in (check_result.new_error_pattern_files or []))
        reminder_msg = AskUserQuestionMessages.ERROR_PATTERN_REMINDER.format(
            file_list=file_list_formatted
        )
        context_parts.append(reminder_msg)
        logger.info(f"新增場景 #17 (error-pattern) 提醒")

    # 優先級 3：Handoff 方向選擇 場景 #9（無訊息時，sibling >= 2）
    # 注意：即使有 error-pattern（#17 已觸發），仍需提醒 Handoff 方向
    if (
        not check_result.message
        and len(check_result.pending_sibling_tickets) >= 2
    ):
        sibling_list_formatted = "\n".join(
            f"  - {sibling_id}"
            for sibling_id in check_result.pending_sibling_tickets
        )
        reminder_msg = AskUserQuestionMessages.HANDOFF_DIRECTION_REMINDER.format(
            sibling_count=len(check_result.pending_sibling_tickets),
            sibling_list=sibling_list_formatted
        )
        context_parts.append(reminder_msg)
        logger.info(f"新增場景 #9 (Handoff 方向) 提醒，sibling 數量: {len(check_result.pending_sibling_tickets)}")

    # 優先級 4：complete 流程提醒（驗收方式，場景 #1）
    # 觸發條件：P0 且非 DOC/ANA 類型 → 需人工確認驗收方式
    # 豁免條件：DOC/ANA 類型 或 非 P0（P1/P2/...） → 自動採用簡化驗收，不觸發
    # 注意：即使有 error-pattern（#17 已觸發），仍需提醒驗收方式確認
    # 修復：原本 has_new_error_patterns 會壓制 #1，導致 PM 錯過驗收確認（W22-012）
    if (
        not check_result.message
        and len(check_result.pending_sibling_tickets) < 2
    ):
        ticket_type_upper = (check_result.task_type or "").upper()
        priority_upper = (check_result.priority or "").upper()
        is_auto_accept_type = ticket_type_upper in ("DOC", "ANA")
        needs_manual_confirmation = priority_upper == "P0" and not is_auto_accept_type

        if needs_manual_confirmation:
            context_parts.append(AskUserQuestionMessages.COMPLETE_REMINDER)
            logger.info(f"新增場景 #1 (complete 流程) 提醒（P0 Ticket，type={ticket_type_upper}）")
        else:
            logger.info(
                f"跳過場景 #1（自動簡化驗收，priority={priority_upper}, type={ticket_type_upper}）"
            )

    # 優先級 5：complete 後下一步提醒（路由選擇，場景 #2）
    # 問題 2 修復：場景 #2 不應只在 sibling < 2 時觸發，即使有 2+ sibling（場景 #9），
    # 也需要在完成當前 ticket 後附加場景 #2 的下一步提醒
    if not check_result.message:
        context_parts.append(AskUserQuestionMessages.COMPLETE_NEXT_STEP_REMINDER)
        logger.info("新增場景 #2 (complete 後下一步) 提醒")

    if context_parts:
        output["hookSpecificOutput"]["additionalContext"] = "\n\n".join(context_parts)

    output["check_result"] = {
        "should_block": check_result.should_block,
        "timestamp": datetime.now().isoformat()
    }

    return output


def save_check_log(ticket_id: str, should_block: bool, project_dir: Path, logger) -> None:
    """
    儲存檢查日誌

    Args:
        ticket_id: Ticket ID
        should_block: 是否阻擋執行
        project_dir: 專案根目錄
        logger: 日誌物件
    """
    log_dir = project_dir / ".claude" / "hook-logs" / "acceptance-gate"
    log_dir.mkdir(parents=True, exist_ok=True)

    log_file = log_dir / f"checks-{datetime.now().strftime('%Y%m%d')}.log"

    try:
        status = "BLOCKED" if should_block else "ALLOWED"
        log_entry = f"""[{datetime.now().isoformat()}]
  TicketID: {ticket_id}
  Status: {status}

"""
        with open(log_file, "a", encoding="utf-8") as f:
            f.write(log_entry)
        logger.debug(f"檢查日誌已儲存: {log_file}")
    except Exception as e:
        logger.warning(f"儲存檢查日誌失敗: {e}")


# ============================================================================
# 主入口點輔助函式
# ============================================================================

def _output_allow_json() -> None:
    """
    輸出允許執行的 Hook 應答 JSON。

    此函式用於 PreToolUse Hook 的快速通行路徑，輸出標準的
    允許執行決策 JSON，無需進行深入檢查。

    輸出格式：
        {"hookSpecificOutput": {"hookEventName": "PreToolUse", "permissionDecision": "allow"}}
    """
    print(json.dumps({
        "hookSpecificOutput": {"hookEventName": "PreToolUse", "permissionDecision": "allow"}
    }, ensure_ascii=False, indent=2))


def _parse_and_validate_input(input_data: Dict[str, Any], logger) -> Optional[Tuple[str, str]]:
    """
    解析並驗證輸入資料。

    驗證 Hook 輸入格式並提取必要欄位。若輸入無效，直接輸出 allow JSON 並回傳 None。

    Args:
        input_data: Hook 輸入資料
        logger: 日誌物件

    Returns:
        Tuple[str, str] - (tool_name, command) 或 None（無效時）
    """
    # 防護：input_data 可能為 None（read_json_from_stdin 返回）
    if input_data is None:
        logger.debug("輸入資料為 None，跳過驗證")
        _output_allow_json()
        return None

    if not validate_input(input_data, logger):
        logger.error("輸入格式錯誤")
        _output_allow_json()
        return None

    tool_name = input_data.get("tool_name", "")
    tool_input = extract_tool_input(input_data, logger)
    command = tool_input.get("command", "")

    return tool_name, command


def _extract_ticket_or_skip(tool_name: str, command: str, logger) -> Optional[str]:
    """
    識別 complete 命令並提取 Ticket ID。

    驗證是 Bash 工具且是 complete 命令，則提取 Ticket ID。
    不符合條件時，直接輸出 allow JSON 並回傳 None。

    Args:
        tool_name: 工具名稱
        command: Bash 命令字串
        logger: 日誌物件

    Returns:
        str - Ticket ID 或 None（不符合條件時）
    """
    # 不是 Bash 工具
    if tool_name != "Bash":
        logger.debug(f"非 Bash 工具: {tool_name}，直接放行")
        _output_allow_json()
        return None

    # 不是 complete 命令
    if not is_complete_command(command):
        logger.debug(f"非 ticket track complete 命令: {command}")
        _output_allow_json()
        return None

    logger.info(f"識別到 ticket track complete 命令: {command}")

    # 提取 Ticket ID
    ticket_id = extract_ticket_id_from_command(command, logger)
    if not ticket_id:
        logger.error("無法從命令中提取 Ticket ID")
        _output_allow_json()
        return None

    logger.info(f"提取 Ticket ID: {ticket_id}")
    return ticket_id


# ============================================================================
# 主入口點
# ============================================================================

def main() -> int:
    """
    主入口點 - 驗收流程協調

    驗收流程：
    1. 解析驗證輸入
    2. 識別 complete 命令並提取 Ticket ID
    3. 檢查驗收狀態
    4. 生成 Hook 輸出並儲存日誌
    5. 決定 exit code

    Returns:
        int - Exit code (EXIT_SUCCESS, EXIT_BLOCK, 或 EXIT_ERROR)
    """
    logger = setup_hook_logging("acceptance-gate")

    try:
        logger.info(CoreMessages.HOOK_START.format(hook_name="Acceptance Gate Hook"))

        # 步驟 1: 解析驗證輸入
        input_data = read_json_from_stdin(logger)
        parsed = _parse_and_validate_input(input_data, logger)
        if parsed is None:
            return EXIT_SUCCESS
        tool_name, command = parsed

        # 步驟 2: 識別命令並提取 Ticket ID
        ticket_id = _extract_ticket_or_skip(tool_name, command, logger)
        if ticket_id is None:
            return EXIT_SUCCESS

        # 步驟 3: 檢查驗收狀態
        project_dir = get_project_root()
        result = check_acceptance_status(ticket_id, project_dir, logger)
        logger.info(
            f"驗收結果: should_block={result.should_block}, "
            f"has_acceptance={result.has_acceptance}, "
            f"has_new_error_patterns={result.has_new_error_patterns}, "
            f"pending_siblings={len(result.pending_sibling_tickets)}"
        )

        # 步驟 4: 生成輸出並儲存日誌
        output = generate_hook_output(ticket_id, result, project_dir, logger)
        print(json.dumps(output, ensure_ascii=False, indent=2))
        save_check_log(ticket_id, result.should_block, project_dir, logger)

        # 步驟 5: 決定 exit code
        if result.should_block:
            logger.warning("Acceptance Gate Hook：子任務未完成，阻止執行")
            return EXIT_BLOCK
        logger.info("Acceptance Gate Hook 檢查完成：允許執行")
        return EXIT_SUCCESS

    except Exception as e:
        logger.critical(f"Hook 執行錯誤: {e}", exc_info=True)
        print(json.dumps({
            "hookSpecificOutput": {
                "hookEventName": "PreToolUse",
                "permissionDecision": "allow",
                "additionalContext": "Hook 執行錯誤，詳見日誌: .claude/hook-logs/acceptance-gate/"
            },
            "error": {"type": type(e).__name__, "message": str(e)}
        }, ensure_ascii=False, indent=2))
        return EXIT_ERROR


if __name__ == "__main__":
    sys.exit(run_hook_safely(main, "acceptance-gate"))
