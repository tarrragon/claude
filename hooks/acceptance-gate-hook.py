#!/usr/bin/env -S uv run --quiet --script
# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///

"""
Acceptance Gate Hook - 驗收狀態驗證

在 `ticket track complete` 執行前檢查驗收狀態。

功能：
- 監控 Bash 工具中的 ticket track complete 命令
- 檢查子任務是否全部完成
- 檢查是否有驗收記錄（除了 DOC 類型）
- 子任務未完成時阻擋（exit 2）
- 未驗收時輸出警告（exit 0，允許但提醒）

Exit Code：
- 0 (EXIT_SUCCESS): 命令允許執行
- 2 (EXIT_BLOCK): 阻止執行（子任務未完成）
- 1 (EXIT_ERROR): Hook 執行錯誤

Hook 類型: PreToolUse
觸發時機: Bash 工具執行前

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

from hook_utils import setup_hook_logging, run_hook_safely
from lib.hook_messages import GateMessages, CoreMessages, AskUserQuestionMessages, format_message

import re
from datetime import datetime
from typing import Dict, Any, Optional, Tuple, List


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



def read_json_from_stdin(logger) -> Dict[str, Any]:
    """
    從 stdin 讀取 JSON 輸入

    Args:
        logger: 日誌物件

    Returns:
        dict - 解析後的 JSON 資料

    Raises:
        ValueError: JSON 格式錯誤
    """
    try:
        input_data = json.load(sys.stdin)
        logger.debug(f"輸入 JSON: {json.dumps(input_data, ensure_ascii=False, indent=2)}")
        return input_data
    except json.JSONDecodeError as e:
        logger.error(f"JSON 解析錯誤: {e}")
        raise ValueError(f"Invalid JSON input: {e}")


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
# Ticket 檔案操作
# ============================================================================

def find_ticket_file(ticket_id: str, project_dir: Path, logger) -> Optional[Path]:
    """
    搜尋 Ticket 檔案

    Args:
        ticket_id: Ticket ID
        project_dir: 專案根目錄
        logger: 日誌物件

    Returns:
        Path - Ticket 檔案路徑或 None
    """
    # 搜尋位置 1: docs/work-logs/*/tickets/
    work_logs_dir = project_dir / "docs" / "work-logs"
    if work_logs_dir.exists():
        for version_dir in work_logs_dir.iterdir():
            if version_dir.is_dir():
                tickets_dir = version_dir / "tickets"
                ticket_file = tickets_dir / f"{ticket_id}.md"
                if ticket_file.is_file():
                    logger.info(f"找到 Ticket 檔案: {ticket_file}")
                    return ticket_file

    # 搜尋位置 2: .claude/tickets/
    claude_tickets_dir = project_dir / ".claude" / "tickets"
    ticket_file = claude_tickets_dir / f"{ticket_id}.md"
    if ticket_file.is_file():
        logger.info(f"找到 Ticket 檔案: {ticket_file}")
        return ticket_file

    logger.debug(f"未找到 Ticket 檔案: {ticket_id}")
    return None


def parse_ticket_frontmatter(content: str) -> Dict[str, str]:
    """
    解析 Ticket YAML frontmatter

    Args:
        content: Ticket 檔案內容

    Returns:
        dict - frontmatter 鍵值對
    """
    frontmatter = {}

    if not content.startswith("---"):
        return frontmatter

    # 找到 frontmatter 結尾
    end_marker = content.find("---", 3)
    if end_marker == -1:
        return frontmatter

    frontmatter_text = content[3:end_marker]

    # 簡單的 YAML 解析（只針對我們需要的欄位）
    lines = frontmatter_text.split("\n")
    i = 0
    while i < len(lines):
        line = lines[i]
        if ":" in line and not line.startswith("#"):
            key, value = line.split(":", 1)
            key = key.strip()
            value = value.strip()

            # 處理多行 YAML 字符串 (e.g., "children: |")
            if value in ["|", ">", "|-", ">-"] or value == "":
                # 收集下面的縮排行
                multiline_value = []
                i += 1
                while i < len(lines):
                    next_line = lines[i]
                    # 如果行以 2+ 個空格開頭，則屬於多行值
                    if next_line.startswith("  ") and next_line.strip():
                        multiline_value.append(next_line.strip())
                        i += 1
                    elif not next_line.strip():
                        # 空行
                        i += 1
                        break
                    else:
                        # 新的 key-value 對
                        break

                if multiline_value:
                    frontmatter[key] = "\n".join(multiline_value)
                else:
                    frontmatter[key] = value
            else:
                frontmatter[key] = value

        i += 1

    return frontmatter


# ============================================================================
# 子任務檢查
# ============================================================================

def extract_children_from_frontmatter(frontmatter: Dict[str, str], logger) -> List[str]:
    """
    從 frontmatter 提取 children 欄位

    Args:
        frontmatter: frontmatter 鍵值對
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


def get_ticket_status(content: str, logger) -> Optional[str]:
    """
    從 Ticket 內容提取狀態

    Args:
        content: Ticket 檔案內容
        logger: 日誌物件

    Returns:
        str - Ticket 狀態或 None
    """
    frontmatter = parse_ticket_frontmatter(content)
    status = frontmatter.get("status")

    if status:
        logger.debug(f"Ticket 狀態: {status}")

    return status


def get_ticket_type(content: str, logger) -> Optional[str]:
    """
    從 Ticket 內容提取型別

    Args:
        content: Ticket 檔案內容
        logger: 日誌物件

    Returns:
        str - Ticket 型別或 None
    """
    frontmatter = parse_ticket_frontmatter(content)
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
# 檢查邏輯
# ============================================================================

def check_acceptance_status(ticket_id: str, project_dir: Path, logger) -> Tuple[bool, bool, Optional[str]]:
    """
    檢查 Ticket 的驗收狀態

    Args:
        ticket_id: Ticket ID
        project_dir: 專案根目錄
        logger: 日誌物件

    Returns:
        tuple - (should_block, has_acceptance, message)
            - should_block: 是否應該阻擋執行（子任務未完成）
            - has_acceptance: 是否有驗收記錄
            - message: 錯誤或警告訊息
    """
    # 找到 Ticket 檔案
    ticket_file = find_ticket_file(ticket_id, project_dir, logger)

    if not ticket_file:
        logger.error(f"找不到 Ticket 檔案: {ticket_id}")
        return False, False, None

    try:
        content = ticket_file.read_text(encoding="utf-8")
        frontmatter = parse_ticket_frontmatter(content)

        # 提取欄位
        ticket_type = frontmatter.get("type")
        title = frontmatter.get("title", "未知")

        # 檢查子任務
        children = extract_children_from_frontmatter(frontmatter, logger)

        if children:
            logger.info(f"Ticket {ticket_id} 有 {len(children)} 個子任務")
            all_completed, incomplete_children = check_children_completed(children, project_dir, logger)

            if not all_completed:
                # 子任務未完成 → 阻擋
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
                return True, False, error_msg

            logger.info(f"Ticket {ticket_id} 所有子任務已完成")

        # 檢查驗收記錄（除非是 DOC 類型且沒有子任務）
        should_check_acceptance = True

        if is_doc_type(ticket_type) and not children:
            logger.info(f"Ticket {ticket_id} 為 DOC 類型且無子任務，豁免驗收檢查")
            should_check_acceptance = False

        has_acceptance = has_acceptance_record(content, logger)

        if should_check_acceptance and not has_acceptance:
            # 未驗收 → 警告（exit 0）
            warning_msg = format_message(
                GateMessages.ACCEPTANCE_RECORD_MISSING_WARNING,
                ticket_id=ticket_id,
                ticket_type=ticket_type,
                title=title
            )

            logger.warning(f"Ticket {ticket_id} 未找到驗收記錄 - 輸出警告")
            return False, False, warning_msg

        logger.info(f"Ticket {ticket_id} 驗收檢查通過")
        return False, has_acceptance, None

    except Exception as e:
        logger.error(f"檢查驗收狀態失敗: {e}", exc_info=True)
        return False, False, None


# ============================================================================
# 輸出生成
# ============================================================================

def generate_hook_output(
    should_block: bool,
    message: Optional[str],
    ask_user_reminder: bool = False
) -> Dict[str, Any]:
    """
    生成 Hook 輸出

    Args:
        should_block: 是否應該阻擋執行
        message: 錯誤或警告訊息
        ask_user_reminder: 是否追加 AskUserQuestion 提醒

    Returns:
        dict - Hook 輸出 JSON
    """
    output = {
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "deny" if should_block else "allow"
        }
    }

    if message:
        context = message
        if ask_user_reminder:
            context += "\n\n" + AskUserQuestionMessages.COMPLETE_REMINDER
        output["hookSpecificOutput"]["additionalContext"] = context
    elif ask_user_reminder:
        output["hookSpecificOutput"]["additionalContext"] = AskUserQuestionMessages.COMPLETE_REMINDER

    output["check_result"] = {
        "should_block": should_block,
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
# 主入口點
# ============================================================================

def main() -> int:
    """
    主入口點

    執行流程:
    1. 初始化日誌
    2. 讀取 JSON 輸入
    3. 驗證輸入格式
    4. 識別是否為 ticket track complete 命令
    5. 提取 Ticket ID
    6. 檢查驗收狀態（子任務 + 驗收記錄）
    7. 生成 Hook 輸出
    8. 儲存日誌
    9. 決定 exit code

    Returns:
        int - Exit code (EXIT_SUCCESS, EXIT_BLOCK, 或 EXIT_ERROR)
    """
    # 初始化 logger
    logger = setup_hook_logging("acceptance-gate")

    try:
        # 步驟 1: 初始化日誌
        logger.info(CoreMessages.HOOK_START.format(hook_name="Acceptance Gate Hook"))

        # 步驟 2: 讀取 JSON 輸入
        input_data = read_json_from_stdin(logger)

        # 步驟 3: 驗證輸入格式
        if not validate_input(input_data, logger):
            logger.error("輸入格式錯誤")
            print(json.dumps({
                "hookSpecificOutput": {"hookEventName": "PreToolUse", "permissionDecision": "allow"}
            }, ensure_ascii=False, indent=2))
            return EXIT_SUCCESS

        tool_name = input_data.get("tool_name", "")
        tool_input = input_data.get("tool_input", {})

        # 不是 Bash 工具，直接放行
        if tool_name != "Bash":
            logger.debug(f"非 Bash 工具: {tool_name}，直接放行")
            output = generate_hook_output(False, None)
            print(json.dumps(output, ensure_ascii=False, indent=2))
            return EXIT_SUCCESS

        command = tool_input.get("command", "")

        # 步驟 4: 識別是否為 ticket track complete 命令
        if not is_complete_command(command):
            logger.debug(f"非 ticket track complete 命令: {command}")
            output = generate_hook_output(False, None)
            print(json.dumps(output, ensure_ascii=False, indent=2))
            return EXIT_SUCCESS

        logger.info(f"識別到 ticket track complete 命令: {command}")

        # 步驟 5: 提取 Ticket ID
        ticket_id = extract_ticket_id_from_command(command, logger)

        if not ticket_id:
            logger.error("無法從命令中提取 Ticket ID")
            output = generate_hook_output(False, None)
            print(json.dumps(output, ensure_ascii=False, indent=2))
            return EXIT_SUCCESS

        logger.info(f"提取 Ticket ID: {ticket_id}")

        # 步驟 6: 檢查驗收狀態
        import os
        project_dir = Path(os.getenv("CLAUDE_PROJECT_DIR", Path.cwd()))

        should_block, has_acceptance, message = check_acceptance_status(ticket_id, project_dir, logger)
        logger.info(f"驗收狀態檢查: should_block={should_block}, has_acceptance={has_acceptance}")

        # 步驟 7: 生成 Hook 輸出
        output = generate_hook_output(should_block, message, ask_user_reminder=True)
        print(json.dumps(output, ensure_ascii=False, indent=2))

        # 步驟 8: 儲存日誌
        save_check_log(ticket_id, should_block, project_dir, logger)

        # 步驟 9: 決定 exit code
        if should_block:
            logger.warning("Acceptance Gate Hook：子任務未完成，阻止執行")
            return EXIT_BLOCK

        logger.info("Acceptance Gate Hook 檢查完成：允許執行")
        return EXIT_SUCCESS

    except Exception as e:
        logger.critical(f"Hook 執行錯誤: {e}", exc_info=True)
        error_output = {
            "hookSpecificOutput": {
                "hookEventName": "PreToolUse",
                "permissionDecision": "allow",
                "additionalContext": "Hook 執行錯誤，詳見日誌: .claude/hook-logs/acceptance-gate/"
            },
            "error": {
                "type": type(e).__name__,
                "message": str(e)
            }
        }
        print(json.dumps(error_output, ensure_ascii=False, indent=2))
        return EXIT_ERROR


if __name__ == "__main__":
    sys.exit(run_hook_safely(main, "acceptance-gate"))
