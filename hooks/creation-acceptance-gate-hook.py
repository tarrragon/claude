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

from hook_utils import setup_hook_logging, run_hook_safely, read_json_from_stdin, parse_ticket_frontmatter
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


def validate_input(input_data: Dict[str, Any], logger) -> bool:
    """
    驗證輸入格式

    Args:
        input_data: Hook 輸入資料
        logger: 日誌物件

    Returns:
        bool - 輸入格式是否正確
    """
    # UserPromptSubmit Hook 至少需要 prompt 欄位
    if "prompt" not in input_data:
        logger.error("缺少必要欄位: prompt")
        return False

    return True


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

def locate_ticket_file(ticket_id: str, logger) -> Optional[Path]:
    """
    定位 Ticket 檔案

    根據 Ticket ID 格式解析版本號，定位檔案位置：
    docs/work-logs/v{version}/tickets/{ticket_id}.md

    Args:
        ticket_id: Ticket ID（格式如 0.31.0-W17-003）
        logger: 日誌物件

    Returns:
        Path - Ticket 檔案路徑，如果不存在則返回 None
    """
    import os

    project_dir = Path(os.getenv("CLAUDE_PROJECT_DIR", Path.cwd()))

    # 從 ID 中解析版本號
    # 格式：v{version}-W{wave}-{number}
    version_match = re.match(r"(\d+\.\d+\.\d+)", ticket_id)
    if not version_match:
        logger.warning(f"無法從 Ticket ID {ticket_id} 解析版本號")
        return None

    version = version_match.group(1)
    ticket_file = project_dir / "docs" / "work-logs" / f"v{version}" / "tickets" / f"{ticket_id}.md"

    if ticket_file.exists():
        logger.info(f"找到 Ticket 檔案: {ticket_file}")
        return ticket_file

    logger.debug(f"Ticket 檔案不存在: {ticket_file}")
    return None


def check_creation_accepted(ticket_id: str, logger) -> Tuple[bool, Optional[str]]:
    """
    檢查 Ticket 的 creation_accepted 欄位

    Args:
        ticket_id: Ticket ID
        logger: 日誌物件

    Returns:
        tuple - (is_accepted, error_message)
            - is_accepted: True 表示已接受，False 表示未接受或缺失
            - error_message: 如果未接受，提供錯誤訊息；否則為 None
    """
    ticket_file = locate_ticket_file(ticket_id, logger)

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

    # 生成阻止訊息
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


def save_check_log(
    prompt: str,
    ticket_ids: Optional[List[str]],
    is_blocked: bool,
    error_count: int,
    logger
) -> None:
    """
    儲存檢查日誌

    Args:
        prompt: 用戶提示文本
        ticket_ids: Ticket ID 清單
        is_blocked: 是否被阻止
        error_count: 錯誤數量
        logger: 日誌物件
    """
    import os

    project_dir = Path(os.getenv("CLAUDE_PROJECT_DIR", Path.cwd()))
    log_dir = project_dir / ".claude" / "hook-logs" / "creation-acceptance-gate"
    log_dir.mkdir(parents=True, exist_ok=True)

    report_file = log_dir / f"checks-{datetime.now().strftime('%Y%m%d')}.log"

    try:
        status = "BLOCKED" if is_blocked else "ALLOWED"
        ticket_ids_str = ", ".join(ticket_ids) if ticket_ids else "none"

        log_entry = f"""[{datetime.now().isoformat()}]
  Prompt: {prompt[:100]}...
  TicketIDs: {ticket_ids_str}
  Errors: {error_count}
  Status: {status}

"""
        with open(report_file, "a", encoding="utf-8") as f:
            f.write(log_entry)
        logger.debug(f"檢查日誌已儲存: {report_file}")
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
        if not validate_input(input_data, logger):
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
            save_check_log(prompt, None, False, 0, logger)
            return EXIT_SUCCESS

        # 步驟 5: 檢查各 Ticket 的 creation_accepted 欄位
        error_messages = []
        is_blocked = False

        for ticket_id in ticket_ids:
            is_accepted, error_msg = check_creation_accepted(ticket_id, logger)
            if not is_accepted:
                is_blocked = True
                error_messages.append(error_msg)

        # 步驟 6: 生成 Hook 輸出
        hook_output = generate_hook_output(is_blocked, error_messages)
        print(json.dumps(hook_output, ensure_ascii=False, indent=2))

        # 步驟 7: 儲存日誌
        save_check_log(prompt, ticket_ids, is_blocked, len(error_messages), logger)

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
