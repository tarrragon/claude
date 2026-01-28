#!/usr/bin/env -S uv run --quiet --script
# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///

"""
Agent Ticket Validation Hook

驗證派發任務是否引用有效的 Ticket ID。

功能：
- 從 prompt 中提取 Ticket ID 引用
- 驗證 Ticket 是否存在
- 驗證 Ticket 是否包含決策樹欄位
- 無效時拒絕派發

Hook 類型: PreToolUse（阻塞式）
Matcher: Task

使用方式:
    PreToolUse Hook 自動觸發，或手動測試:
    echo '{"tool_input":{"prompt":"Ticket: 0.30.1-W2-003..."}}' | python3 agent-ticket-validation-hook.py

環境變數:
    HOOK_DEBUG: 啟用詳細日誌（true/false）
"""

import sys
import json
import logging
import re
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, Optional, Tuple


# ============================================================================
# 常數定義
# ============================================================================

# Ticket ID 引用格式
TICKET_ID_PATTERNS = [
    r"Ticket:\s*(\d+\.\d+\.\d+-W\d+-\d+)",
    r"#Ticket-(\d+\.\d+\.\d+-W\d+-\d+)",
    r"\[Ticket\s+(\d+\.\d+\.\d+-W\d+-\d+)\]"
]

# 決策樹欄位識別
DECISION_TREE_MARKERS = [
    "decision_tree_path:",
    "## 決策樹路徑",
    "decision_nodes:",
    "## 決策樹"
]

# Exit Code
EXIT_SUCCESS = 0
EXIT_ERROR = 1
EXIT_BLOCK = 2


# ============================================================================
# 日誌設置
# ============================================================================

def setup_logging() -> None:
    """初始化日誌系統"""
    import os

    log_level = logging.DEBUG if os.getenv("HOOK_DEBUG") == "true" else logging.INFO

    # 建立日誌目錄
    project_dir = Path(os.getenv("CLAUDE_PROJECT_DIR", Path.cwd()))
    log_dir = project_dir / ".claude" / "hook-logs" / "agent-ticket-validation"
    log_dir.mkdir(parents=True, exist_ok=True)

    log_file = log_dir / "agent-ticket-validation.log"

    logging.basicConfig(
        level=log_level,
        format="[%(asctime)s] %(levelname)s - %(message)s",
        handlers=[
            logging.FileHandler(log_file),
            logging.StreamHandler(sys.stderr)
        ]
    )


# ============================================================================
# 輸入讀取和驗證
# ============================================================================

def read_json_from_stdin() -> Dict[str, Any]:
    """
    從 stdin 讀取 JSON 輸入

    Returns:
        dict - 解析後的 JSON 資料

    Raises:
        ValueError: JSON 格式錯誤
    """
    try:
        input_data = json.load(sys.stdin)
        logging.debug(f"輸入 JSON: {json.dumps(input_data, ensure_ascii=False, indent=2)}")
        return input_data
    except json.JSONDecodeError as e:
        logging.error(f"JSON 解析錯誤: {e}")
        raise ValueError(f"Invalid JSON input: {e}")


def validate_input(input_data: Dict[str, Any]) -> bool:
    """
    驗證輸入格式

    Args:
        input_data: Hook 輸入資料

    Returns:
        bool - 輸入格式是否正確
    """
    # PreToolUse Hook 需要 tool_input 欄位
    if "tool_input" not in input_data:
        logging.error("缺少必要欄位: tool_input")
        return False

    tool_input = input_data.get("tool_input", {})
    if "prompt" not in tool_input:
        logging.error("缺少必要欄位: tool_input.prompt")
        return False

    return True


# ============================================================================
# Ticket ID 提取
# ============================================================================

def extract_ticket_reference(prompt: str) -> Optional[str]:
    """
    從 prompt 中提取 Ticket ID 引用

    Args:
        prompt: 派發提示文本

    Returns:
        str - Ticket ID，或 None 如未找到

    格式範例：
    - Ticket: 0.30.1-W2-003
    - #Ticket-0.30.1-W2-003
    - [Ticket 0.30.1-W2-003]
    """
    if not prompt:
        logging.debug("prompt 為空")
        return None

    for pattern in TICKET_ID_PATTERNS:
        match = re.search(pattern, prompt)
        if match:
            ticket_id = match.group(1)
            logging.info(f"從 prompt 提取 Ticket ID: {ticket_id}")
            return ticket_id

    logging.debug(f"未在 prompt 中找到 Ticket ID 引用")
    return None


# ============================================================================
# Ticket 檔案查找和驗證
# ============================================================================

def find_ticket_file(ticket_id: str) -> Optional[Path]:
    """
    尋找 Ticket 檔案

    Args:
        ticket_id: Ticket ID

    Returns:
        Path - Ticket 檔案路徑，或 None 如未找到
    """
    import os

    project_dir = Path(os.getenv("CLAUDE_PROJECT_DIR", Path.cwd()))

    # 搜尋位置：.claude/tickets/ 和 docs/work-logs/*/tickets/
    search_locations = [
        project_dir / ".claude" / "tickets",
        project_dir / "docs" / "work-logs"
    ]

    # 搜尋 .claude/tickets/
    if search_locations[0].exists():
        ticket_file = search_locations[0] / f"{ticket_id}.md"
        if ticket_file.exists():
            logging.info(f"在 .claude/tickets/ 中找到 Ticket: {ticket_id}")
            return ticket_file

    # 搜尋 docs/work-logs/*/tickets/
    for version_dir in search_locations[1].glob("v*"):
        tickets_dir = version_dir / "tickets"
        if tickets_dir.exists():
            ticket_file = tickets_dir / f"{ticket_id}.md"
            if ticket_file.exists():
                logging.info(f"在 {tickets_dir} 中找到 Ticket: {ticket_id}")
                return ticket_file

    logging.warning(f"未找到 Ticket 檔案: {ticket_id}")
    return None


def load_ticket_content(ticket_path: Path) -> Optional[str]:
    """
    讀取 Ticket 檔案內容

    Args:
        ticket_path: Ticket 檔案路徑

    Returns:
        str - 檔案內容，或 None 如讀取失敗
    """
    try:
        content = ticket_path.read_text(encoding="utf-8")
        logging.debug(f"成功讀取 Ticket 檔案: {ticket_path}")
        return content
    except Exception as e:
        logging.error(f"無法讀取 Ticket 檔案 {ticket_path}: {e}")
        return None


def validate_ticket_has_decision_tree(content: str) -> bool:
    """
    驗證 Ticket 是否包含決策樹欄位

    Args:
        content: Ticket 檔案內容

    Returns:
        bool - 是否包含決策樹欄位

    檢查項目：
    - YAML frontmatter 中的 decision_tree_path 欄位
    - 內容中的決策樹相關標記
    """
    if not content:
        logging.warning("Ticket 內容為空")
        return False

    # 檢查任何決策樹欄位
    for marker in DECISION_TREE_MARKERS:
        if marker in content:
            logging.info(f"Ticket 包含決策樹欄位: {marker}")
            return True

    logging.warning("Ticket 缺少決策樹欄位")
    return False


def validate_ticket(ticket_id: str) -> Tuple[bool, str]:
    """
    驗證 Ticket 的完整性

    Args:
        ticket_id: Ticket ID

    Returns:
        tuple - (is_valid, error_message)
            - is_valid: Ticket 是否有效
            - error_message: 錯誤訊息（如有）
    """
    # 尋找 Ticket 檔案
    ticket_path = find_ticket_file(ticket_id)
    if not ticket_path:
        msg = f"找不到 Ticket: {ticket_id}"
        logging.error(msg)
        return False, msg

    # 讀取 Ticket 內容
    content = load_ticket_content(ticket_path)
    if not content:
        msg = f"無法讀取 Ticket 檔案: {ticket_id}"
        logging.error(msg)
        return False, msg

    # 驗證決策樹欄位
    if not validate_ticket_has_decision_tree(content):
        msg = f"Ticket {ticket_id} 缺少決策樹欄位，為無效 Ticket"
        logging.error(msg)
        return False, msg

    logging.info(f"Ticket {ticket_id} 驗證通過")
    return True, ""


# ============================================================================
# 派發驗證
# ============================================================================

def validate_task_dispatch(tool_input: Dict[str, Any]) -> Tuple[bool, str]:
    """
    驗證 Task 派發是否有效

    Args:
        tool_input: 工具輸入資料

    Returns:
        tuple - (is_valid, error_message)
            - is_valid: 派發是否有效
            - error_message: 錯誤訊息（如有）

    驗證流程：
    1. 從 prompt 提取 Ticket ID 引用
    2. 驗證 Ticket 是否存在且包含決策樹欄位
    """
    prompt = tool_input.get("prompt", "")

    # 步驟 1: 提取 Ticket ID
    ticket_id = extract_ticket_reference(prompt)
    if not ticket_id:
        msg = "派發任務必須引用有效的 Ticket ID（格式：Ticket: {id} 或 #Ticket-{id} 或 [Ticket {id}]）"
        logging.error(msg)
        return False, msg

    # 步驟 2: 驗證 Ticket
    is_valid, error_msg = validate_ticket(ticket_id)
    return is_valid, error_msg


# ============================================================================
# 輸出生成
# ============================================================================

def generate_hook_output(
    is_valid: bool,
    error_message: Optional[str] = None
) -> Dict[str, Any]:
    """
    生成 Hook 輸出

    Args:
        is_valid: 派發是否有效
        error_message: 錯誤訊息（如有）

    Returns:
        dict - Hook 輸出 JSON

    驗證失敗時，輸出 deny 決策和錯誤原因。
    """
    output = {
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse"
        }
    }

    if not is_valid:
        output["hookSpecificOutput"]["permissionDecision"] = "deny"
        output["hookSpecificOutput"]["permissionDecisionReason"] = (
            error_message or "派發任務驗證失敗"
        )
    else:
        output["hookSpecificOutput"]["permissionDecision"] = "allow"

    # 記錄檢查結果
    output["check_result"] = {
        "is_valid": is_valid,
        "error_message": error_message,
        "timestamp": datetime.now().isoformat()
    }

    return output


def save_check_log(
    is_valid: bool,
    ticket_id: Optional[str],
    error_message: Optional[str]
) -> None:
    """
    儲存檢查日誌

    Args:
        is_valid: 驗證是否通過
        ticket_id: Ticket ID
        error_message: 錯誤訊息（如有）
    """
    import os

    project_dir = Path(os.getenv("CLAUDE_PROJECT_DIR", Path.cwd()))
    log_dir = project_dir / ".claude" / "hook-logs" / "agent-ticket-validation"
    log_dir.mkdir(parents=True, exist_ok=True)

    report_file = log_dir / f"checks-{datetime.now().strftime('%Y%m%d')}.log"

    try:
        log_entry = f"""[{datetime.now().isoformat()}]
  TicketID: {ticket_id}
  IsValid: {is_valid}
  ErrorMessage: {error_message}
  Status: {"ALLOWED" if is_valid else "DENIED"}

"""
        with open(report_file, "a", encoding="utf-8") as f:
            f.write(log_entry)
        logging.debug(f"檢查日誌已儲存: {report_file}")
    except Exception as e:
        logging.warning(f"儲存檢查日誌失敗: {e}")


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
    4. 驗證 Task 派發有效性
    5. 生成 Hook 輸出
    6. 儲存日誌
    7. 決定 exit code

    Returns:
        int - Exit code (0=allow, 2=deny, 1=error)
    """
    try:
        # 步驟 1: 初始化日誌
        setup_logging()
        logging.info("Agent Ticket Validation Hook 啟動")

        # 步驟 2: 讀取 JSON 輸入
        input_data = read_json_from_stdin()

        # 步驟 3: 驗證輸入格式
        if not validate_input(input_data):
            logging.error("輸入格式錯誤")
            print(json.dumps({
                "hookSpecificOutput": {"hookEventName": "PreToolUse"}
            }, ensure_ascii=False, indent=2))
            return EXIT_SUCCESS

        tool_input = input_data.get("tool_input", {})

        # 步驟 4: 驗證 Task 派發有效性
        is_valid, error_message = validate_task_dispatch(tool_input)
        ticket_id = extract_ticket_reference(tool_input.get("prompt", ""))

        logging.info(f"Task 派發驗證: is_valid={is_valid}, ticket_id={ticket_id}")

        # 步驟 5: 生成 Hook 輸出
        hook_output = generate_hook_output(is_valid, error_message if not is_valid else None)
        print(json.dumps(hook_output, ensure_ascii=False, indent=2))

        # 步驟 6: 儲存日誌
        save_check_log(is_valid, ticket_id, error_message if not is_valid else None)

        # 步驟 7: 決定 exit code
        if is_valid:
            logging.info("Agent Ticket Validation Hook 檢查通過")
            return EXIT_SUCCESS
        else:
            logging.warning("Agent Ticket Validation Hook 拒絕派發")
            return EXIT_BLOCK

    except Exception as e:
        logging.critical(f"Hook 執行錯誤: {e}", exc_info=True)
        error_output = {
            "hookSpecificOutput": {
                "hookEventName": "PreToolUse",
                "additionalContext": "Hook 執行錯誤，詳見日誌: .claude/hook-logs/agent-ticket-validation/"
            },
            "error": {
                "type": type(e).__name__,
                "message": str(e)
            }
        }
        print(json.dumps(error_output, ensure_ascii=False, indent=2))
        return EXIT_ERROR


if __name__ == "__main__":
    sys.exit(main())
