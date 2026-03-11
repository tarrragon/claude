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
- 支援豁免機制：特定代理人類型（如 Explore）可跳過 Ticket 驗證

豁免機制：
- Explore 代理人：用於前置資訊蒐集，在建立 Ticket 之前執行
- 豁免的代理人類型定義在 TICKET_EXEMPT_AGENT_TYPES 常數中

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
import re
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, Optional, Tuple

# 加入 hook_utils 路徑（相同目錄）
sys.path.insert(0, str(Path(__file__).parent))

from hook_utils import (
    setup_hook_logging, run_hook_safely, read_json_from_stdin, get_project_root,
    find_ticket_files, find_ticket_file, validate_ticket_has_decision_tree, save_check_log,
    is_handoff_recovery_mode, validate_hook_input
)

# ============================================================================
# 常數定義
# ============================================================================

# Ticket ID 引用格式（支援子任務 ID，如 0.31.0-W3-002.1.1）
TICKET_ID_PATTERNS = [
    r"Ticket:\s*(\d+\.\d+\.\d+-W\d+-\d+(?:\.\d+)*)",
    r"#Ticket-(\d+\.\d+\.\d+-W\d+-\d+(?:\.\d+)*)",
    r"\[Ticket\s+(\d+\.\d+\.\d+-W\d+-\d+(?:\.\d+)*)\]"
]

# 豁免 Ticket 驗證的代理人類型
# 這些代理人用於前置資訊蒐集，在建立 Ticket 之前執行
TICKET_EXEMPT_AGENT_TYPES = [
    "Explore",  # 探索代理人：用於蒐集資訊以建立 Ticket
]

# Exit Code
EXIT_SUCCESS = 0
EXIT_ERROR = 1
EXIT_BLOCK = 2

# validate_input 已遷移至 hook_utils.validate_hook_input

# ============================================================================
# Ticket ID 提取
# ============================================================================

def extract_ticket_reference(prompt: str, logger) -> Optional[str]:
    """
    從 prompt 中提取 Ticket ID 引用

    Args:
        prompt: 派發提示文本
        logger: 日誌物件

    Returns:
        str - Ticket ID，或 None 如未找到

    格式範例：
    - Ticket: 0.30.1-W2-003
    - #Ticket-0.30.1-W2-003
    - [Ticket 0.30.1-W2-003]
    """
    if not prompt:
        logger.debug("prompt 為空")
        return None

    for pattern in TICKET_ID_PATTERNS:
        match = re.search(pattern, prompt)
        if match:
            ticket_id = match.group(1)
            logger.info(f"從 prompt 提取 Ticket ID: {ticket_id}")
            return ticket_id

    logger.debug(f"未在 prompt 中找到 Ticket ID 引用")
    return None

# ============================================================================
# Ticket 檔案查找和驗證
# ============================================================================

def load_ticket_content(ticket_path: Path, logger) -> Optional[str]:
    """
    讀取 Ticket 檔案內容

    Args:
        ticket_path: Ticket 檔案路徑
        logger: 日誌物件

    Returns:
        str - 檔案內容，或 None 如讀取失敗
    """
    try:
        content = ticket_path.read_text(encoding="utf-8")
        logger.debug(f"成功讀取 Ticket 檔案: {ticket_path}")
        return content
    except Exception as e:
        logger.error(f"無法讀取 Ticket 檔案 {ticket_path}: {e}")
        return None

def validate_ticket(ticket_id: str, logger) -> Tuple[bool, Optional[str]]:
    """
    驗證 Ticket 的完整性

    Args:
        ticket_id: Ticket ID
        logger: 日誌物件

    Returns:
        tuple - (is_valid, error_message)
            - is_valid: Ticket 是否有效
            - error_message: 錯誤訊息（如有），成功時為 None
    """
    # 尋找 Ticket 檔案
    ticket_path = find_ticket_file(ticket_id, logger=logger)
    if not ticket_path:
        msg = f"找不到 Ticket: {ticket_id}"
        logger.error(msg)
        return False, msg

    # 讀取 Ticket 內容
    content = load_ticket_content(ticket_path, logger)
    if not content:
        msg = f"無法讀取 Ticket 檔案: {ticket_id}"
        logger.error(msg)
        return False, msg

    # 驗證決策樹欄位
    if not validate_ticket_has_decision_tree(content, logger):
        msg = f"Ticket {ticket_id} 缺少決策樹欄位，為無效 Ticket"
        logger.error(msg)
        return False, msg

    logger.info(f"Ticket {ticket_id} 驗證通過")
    return True, None

# ============================================================================
# 派發驗證
# ============================================================================

# is_handoff_recovery_mode 已遷移至 hook_utils

def is_exempt_agent_type(subagent_type: str, logger) -> bool:
    """
    檢查代理人類型是否豁免 Ticket 驗證

    Args:
        subagent_type: 代理人類型
        logger: 日誌物件

    Returns:
        bool - 是否豁免驗證

    豁免的代理人類型用於前置資訊蒐集，在建立 Ticket 之前執行。
    例如：Explore 代理人用於探索 codebase 以蒐集建立 Ticket 所需的資訊。
    """
    if not subagent_type:
        return False

    is_exempt = subagent_type in TICKET_EXEMPT_AGENT_TYPES
    if is_exempt:
        logger.info(f"代理人類型 '{subagent_type}' 豁免 Ticket 驗證（用於前置資訊蒐集）")
    return is_exempt

def validate_task_dispatch(tool_input: Dict[str, Any], logger) -> Tuple[bool, Optional[str], Optional[str]]:
    """
    驗證 Task 派發是否有效

    Args:
        tool_input: 工具輸入資料
        logger: 日誌物件

    Returns:
        tuple - (is_valid, error_message, ticket_id)
            - is_valid: 派發是否有效
            - error_message: 錯誤訊息（如有），成功時為 None
            - ticket_id: 提取的 Ticket ID，或 None（豁免/handoff 模式或未找到）

    驗證流程：
    0. 檢查是否為 Handoff 恢復模式
    1. 檢查是否為豁免的代理人類型（如 Explore）
    2. 從 prompt 提取 Ticket ID 引用
    3. 驗證 Ticket 是否存在且包含決策樹欄位
    """
    prompt = tool_input.get("prompt", "")
    subagent_type = tool_input.get("subagent_type", "")

    # 步驟 0: 檢查 Handoff 恢復模式
    if is_handoff_recovery_mode(logger):
        logger.info("Handoff 恢復模式: 略過 Ticket 驗證")
        return True, None, None

    # 步驟 1: 檢查豁免代理人類型
    if is_exempt_agent_type(subagent_type, logger):
        return True, None, None

    # 步驟 2: 提取 Ticket ID
    ticket_id = extract_ticket_reference(prompt, logger)
    if not ticket_id:
        msg = "派發任務必須引用有效的 Ticket ID（格式：Ticket: {id} 或 #Ticket-{id} 或 [Ticket {id}]）"
        logger.error(msg)
        return False, msg, None

    # 步驟 3: 驗證 Ticket
    is_valid, error_msg = validate_ticket(ticket_id, logger)
    return is_valid, error_msg, ticket_id

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
    logger = setup_hook_logging("agent-ticket-validation")
    try:
        # 步驟 1: 初始化日誌
        logger.info("Agent Ticket Validation Hook 啟動")

        # 步驟 2: 讀取 JSON 輸入
        input_data = read_json_from_stdin(logger)

        # 步驟 3: 驗證輸入格式
        if not validate_hook_input(input_data, logger, ("tool_input",)):
            logger.error("輸入格式錯誤")
            print(json.dumps({
                "hookSpecificOutput": {"hookEventName": "PreToolUse"}
            }, ensure_ascii=False, indent=2))
            return EXIT_SUCCESS

        tool_input = input_data.get("tool_input", {})

        # 步驟 4: 驗證 Task 派發有效性
        is_valid, error_message, ticket_id = validate_task_dispatch(tool_input, logger)

        logger.info(f"Task 派發驗證: is_valid={is_valid}, ticket_id={ticket_id}")

        # 步驟 5: 生成 Hook 輸出
        hook_output = generate_hook_output(is_valid, error_message if not is_valid else None)
        print(json.dumps(hook_output, ensure_ascii=False, indent=2))

        # 步驟 6: 儲存日誌
        log_entry = f"""[{datetime.now().isoformat()}]
  TicketID: {ticket_id}
  IsValid: {is_valid}
  ErrorMessage: {error_message if not is_valid else None}
  Status: {"ALLOWED" if is_valid else "DENIED"}

"""
        save_check_log("agent-ticket-validation", log_entry, logger)

        # 步驟 7: 決定 exit code
        if is_valid:
            logger.info("Agent Ticket Validation Hook 檢查通過")
            return EXIT_SUCCESS
        else:
            logger.warning("Agent Ticket Validation Hook 拒絕派發")
            # 輸出到 stderr 確保 PM 可見（品質基線規則 4）
            print(f"[Agent Ticket Validation] 派發被拒絕: {error_message}", file=sys.stderr)
            return EXIT_BLOCK

    except Exception as e:
        logger.critical(f"Hook 執行錯誤: {e}", exc_info=True)
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
    sys.exit(run_hook_safely(main, "agent-ticket-validation"))
