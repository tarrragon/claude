#!/usr/bin/env python3
# /// script
# requires-python = ">=3.11"
# dependencies = ["pyyaml"]
# ///

"""
Creation Acceptance Gate Hook - 建立後驗收閘門

在 `ticket track claim` 執行前檢查目標 Ticket 的 `creation_accepted` 欄位。
欄位為 false 或缺失時阻止認領。

功能：
- 識別 ticket track claim 和 ticket track batch-claim 命令
- 檢查 Ticket 的 creation_accepted 欄位
- creation_accepted: true → 靜默通過（exit 0）
- creation_accepted: false 或缺失 → 阻止執行（exit 2）
- Ticket 檔案不存在 → 靜默通過（exit 0）
- 非 claim 命令 → 靜默通過（exit 0）

Exit Code：
- 0 (EXIT_SUCCESS): 命令允許執行
- 2 (EXIT_BLOCK): 阻止執行（creation_accepted 未通過）
- 1 (EXIT_ERROR): Hook 執行錯誤

Hook 類型: UserPromptSubmit
觸發時機: 接收用戶命令時

環境變數:
    HOOK_DEBUG: 啟用詳細日誌（true/false）

HOOK_METADATA (JSON):
{
  "event_type": "UserPromptSubmit",
  "timeout": 5000,
  "description": "建立後驗收閘門 - 檢查 Ticket creation_accepted 欄位",
  "version": "1.0.0"
}
"""

import sys
import json
from pathlib import Path

# 加入 hook_utils 路徑（相同目錄）
_hooks_dir = Path(__file__).parent
if _hooks_dir not in [p for p in sys.path if Path(p) == _hooks_dir]:
    sys.path.insert(0, str(_hooks_dir))

from hook_utils import (
    setup_hook_logging, run_hook_safely, read_json_from_stdin,
    parse_ticket_frontmatter, get_project_root, save_check_log,
    validate_hook_input
)
from hook_utils.hook_ticket import find_ticket_file
from lib.hook_messages import GateMessages, CoreMessages, format_message

import re
from datetime import datetime
from typing import Dict, Any, Optional, Tuple, List

try:
    import yaml
    HAS_YAML = True
except ImportError:
    HAS_YAML = False

# ============================================================================
# 常數定義
# ============================================================================

# Exit Code
EXIT_SUCCESS = 0
EXIT_ERROR = 1
EXIT_BLOCK = 2


# ============================================================================
# 日誌設置
# ============================================================================


# validate_input 已遷移至 hook_utils.validate_hook_input


# ============================================================================
# 命令識別
# ============================================================================

def extract_claim_ticket_ids(prompt: str, logger) -> Optional[List[str]]:
    """
    從 prompt 中提取 claim 命令的 Ticket ID

    支援的命令格式：
    - ticket track claim <id>
    - ticket track batch-claim "id1,id2,id3"
    - /ticket track claim <id>
    - /ticket track batch-claim "id1,id2,id3"

    Args:
        prompt: 用戶命令文本
        logger: 日誌物件

    Returns:
        list - Ticket ID 清單，如果不是 claim 命令則返回 None
    """
    if not prompt:
        return None

    prompt = prompt.strip()

    # 移除開頭的 / 符號（如 /ticket track claim）
    if prompt.startswith("/"):
        prompt = prompt[1:].strip()

    # 識別 ticket track claim 命令
    claim_pattern = r"ticket\s+track\s+claim\s+(\S+)"
    claim_match = re.search(claim_pattern, prompt, re.IGNORECASE)
    if claim_match:
        ticket_id = claim_match.group(1).strip('"\'')
        logger.info(f"識別 ticket track claim 命令，Ticket ID: {ticket_id}")
        return [ticket_id]

    # 識別 ticket track batch-claim 命令
    batch_pattern = r"ticket\s+track\s+batch-claim\s+[\"'](.+?)[\"']"
    batch_match = re.search(batch_pattern, prompt, re.IGNORECASE)
    if batch_match:
        ids_str = batch_match.group(1)
        ticket_ids = [tid.strip() for tid in ids_str.split(",")]
        logger.info(f"識別 ticket track batch-claim 命令，Ticket IDs: {ticket_ids}")
        return ticket_ids

    logger.debug("未識別為 claim 命令")
    return None


# ============================================================================
# Ticket 檔案操作
# ============================================================================

def check_creation_accepted(ticket_id: str, logger) -> Tuple[bool, Optional[str]]:
    """
    檢查 Ticket 的 creation_accepted 欄位

    Args:
        ticket_id: Ticket ID
        logger: 日誌物件

    Returns:
        tuple - (is_accepted, message)
            - is_accepted: True 表示允許執行，False 表示阻止（EXIT_BLOCK）
            - message: 錯誤訊息（阻止時）或警告訊息（矛盾狀態時）；正常通過時為 None
    """
    ticket_file = find_ticket_file(ticket_id, logger=logger)

    # Ticket 檔案不存在 → 靜默通過（不阻止，讓後續命令處理錯誤）
    if not ticket_file:
        logger.info(f"Ticket 檔案不存在 {ticket_id}，靜默通過（由後續命令處理）")
        return True, None

    # 解析 frontmatter
    frontmatter = parse_ticket_frontmatter(ticket_file, logger)

    # 檢查 creation_accepted 欄位
    creation_accepted = frontmatter.get("creation_accepted", False)

    # 正規化布林值
    if isinstance(creation_accepted, str):
        creation_accepted = creation_accepted.lower() in ("true", "yes", "1")
    elif creation_accepted is None:
        creation_accepted = False

    logger.info(f"Ticket {ticket_id} creation_accepted: {creation_accepted}")

    if creation_accepted:
        return True, None

    # 檢查矛盾狀態：in_progress + creation_accepted: false
    # 此狀態發生於 Ticket 在建立審核機制加入前就已認領
    # re-claim 是 no-op，不應觸發 EXIT_BLOCK 導致 session 終止
    current_status = frontmatter.get("status", "pending")
    if current_status == "in_progress":
        logger.warning(f"Ticket {ticket_id} 矛盾狀態（in_progress + creation_accepted: false），允許繼續")
        warning_msg = format_message(
            GateMessages.CONTRADICTORY_STATE_WARNING,
            ticket_id=ticket_id
        )
        return True, warning_msg

    # 正常阻止：pending + creation_accepted: false
    error_msg = format_message(
        GateMessages.CREATION_NOT_ACCEPTED_ERROR,
        ticket_id=ticket_id
    )

    return False, error_msg


# ============================================================================
# 輸出生成
# ============================================================================

def generate_hook_output(
    is_blocked: bool,
    error_messages: List[str]
) -> Dict[str, Any]:
    """
    生成 Hook 輸出

    Args:
        is_blocked: 是否被阻止
        error_messages: 錯誤訊息清單

    Returns:
        dict - Hook 輸出 JSON
    """
    output = {
        "hookSpecificOutput": {
            "hookEventName": "UserPromptSubmit"
        }
    }

    if error_messages:
        output["hookSpecificOutput"]["additionalContext"] = "\n\n".join(error_messages)

    output["check_result"] = {
        "is_blocked": is_blocked,
        "error_count": len(error_messages),
        "exit_code": "EXIT_BLOCK" if is_blocked else "EXIT_SUCCESS",
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
    4. 識別是否為 claim 命令
    5. 檢查各 Ticket 的 creation_accepted 欄位
    6. 生成 Hook 輸出
    7. 儲存日誌
    8. 決定 exit code

    Returns:
        int - Exit code (EXIT_SUCCESS, EXIT_BLOCK, 或 EXIT_ERROR)
    """
    # 初始化 logger
    logger = setup_hook_logging("creation-acceptance-gate")

    try:
        # 步驟 1: 初始化日誌
        logger.info(CoreMessages.HOOK_START.format(hook_name="Creation Acceptance Gate Hook"))

        # 步驟 2: 讀取 JSON 輸入
        input_data = read_json_from_stdin(logger)

        # 步驟 3: 驗證輸入格式
        if not validate_hook_input(input_data, logger, ("prompt",)):
            logger.error("輸入格式錯誤")
            print(json.dumps({
                "hookSpecificOutput": {"hookEventName": "UserPromptSubmit"}
            }, ensure_ascii=False, indent=2))
            return EXIT_SUCCESS

        prompt = input_data.get("prompt", "")

        # 步驟 4: 識別是否為 claim 命令
        ticket_ids = extract_claim_ticket_ids(prompt, logger)

        # 非 claim 命令 → 靜默通過
        if ticket_ids is None:
            logger.debug("非 claim 命令，靜默通過")
            output = generate_hook_output(False, [])
            print(json.dumps(output, ensure_ascii=False, indent=2))
            log_entry = f"""[{datetime.now().isoformat()}]
  Prompt: {prompt[:100]}...
  TicketIDs: none
  Errors: 0
  Status: ALLOWED

"""
            save_check_log("creation-acceptance-gate", log_entry, logger)
            return EXIT_SUCCESS

        # 步驟 5: 檢查各 Ticket 的 creation_accepted 欄位
        error_messages = []
        warning_messages = []
        is_blocked = False

        for ticket_id in ticket_ids:
            is_accepted, msg = check_creation_accepted(ticket_id, logger)
            if not is_accepted:
                is_blocked = True
                error_messages.append(msg)
            elif msg:
                # 允許執行但有警告（矛盾狀態）
                warning_messages.append(msg)

        # 步驟 6: 生成 Hook 輸出（警告訊息也包含在 additionalContext 中）
        hook_output = generate_hook_output(is_blocked, error_messages + warning_messages)
        print(json.dumps(hook_output, ensure_ascii=False, indent=2))

        # 步驟 7: 儲存日誌
        status = "BLOCKED" if is_blocked else "ALLOWED"
        ticket_ids_str = ", ".join(ticket_ids) if ticket_ids else "none"
        log_entry = f"""[{datetime.now().isoformat()}]
  Prompt: {prompt[:100]}...
  TicketIDs: {ticket_ids_str}
  Errors: {len(error_messages)}
  Status: {status}

"""
        save_check_log("creation-acceptance-gate", log_entry, logger)

        # 步驟 8: 決定 exit code
        if is_blocked:
            logger.warning("Creation Acceptance Gate Hook：驗收檢查失敗，阻止執行")
            return EXIT_BLOCK

        logger.info("Creation Acceptance Gate Hook 檢查完成：允許執行")
        return EXIT_SUCCESS

    except Exception as e:
        logger.critical(f"Hook 執行錯誤: {e}", exc_info=True)
        error_output = {
            "hookSpecificOutput": {
                "hookEventName": "UserPromptSubmit",
                "additionalContext": "Hook 執行錯誤，詳見日誌: .claude/hook-logs/creation-acceptance-gate/"
            },
            "error": {
                "type": type(e).__name__,
                "message": str(e)
            }
        }
        print(json.dumps(error_output, ensure_ascii=False, indent=2))
        return EXIT_ERROR


if __name__ == "__main__":
    sys.exit(run_hook_safely(main, "creation-acceptance-gate"))
