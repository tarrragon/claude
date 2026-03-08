#!/usr/bin/env -S uv run --quiet --script
# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///

"""
Post Ticket Complete Checkpoint Hook - PostToolUse Hook

功能: 偵測 ticket track complete 成功後，強制輸出 Checkpoint 1/1.5 提醒。

根本原因（PC-010 / 0.1.0-W15-010 分析）：
  acceptance-gate-hook 在 PreToolUse 觸發，PM 閱讀焦點是「能否 complete」，
  對「complete 後做什麼」的注意力低。ticket complete 成功後無任何 Hook，
  PM 看到成功訊息後容易停止，跳過 Checkpoint 1（git status）和 1.5（錯誤學習確認）。

觸發時機: Bash 工具執行後
檢測邏輯:
  1. 驗證 tool_name == "Bash"
  2. 檢查 command 是否包含 "ticket track complete" 或 "ticket track batch-complete"
  3. 檢查 stdout 是否包含成功標記（"已完成"）
  4. 若偵測成功，輸出 POST_TICKET_COMPLETE_CHECKPOINT_REMINDER

行為: 不阻擋（exit 0），僅在 additionalContext 輸出強制提醒
"""

import sys
import json
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from hook_utils import setup_hook_logging, run_hook_safely
from lib.hook_messages import AskUserQuestionMessages

# ============================================================================
# 常數定義
# ============================================================================

EXIT_SUCCESS = 0

# PostToolUse Hook 的標準輸出結構
DEFAULT_OUTPUT = {
    "hookSpecificOutput": {
        "hookEventName": "PostToolUse"
    }
}

# ticket complete 成功標記
COMPLETE_SUCCESS_MARKERS = [
    "已完成",
]

# ============================================================================
# 主要邏輯
# ============================================================================


def is_ticket_complete_command(command: str) -> bool:
    """
    判斷是否為 ticket track complete 命令

    Args:
        command: Bash 命令字串

    Returns:
        bool - 是否為 ticket track complete 操作
    """
    return "ticket track complete" in command or "ticket track batch-complete" in command


def is_complete_successful(stdout: str) -> bool:
    """
    判斷 ticket complete 是否成功

    Args:
        stdout: Bash 命令的標準輸出

    Returns:
        bool - 是否偵測到成功標記
    """
    for marker in COMPLETE_SUCCESS_MARKERS:
        if marker in stdout:
            return True
    return False


def main() -> int:
    """
    主入口點

    流程:
    1. 讀取 stdin JSON（PostToolUse 格式）
    2. 驗證工具類型是否為 Bash
    3. 檢查命令是否為 ticket track complete
    4. 檢查輸出是否包含成功標記
    5. 若全部符合，輸出 Checkpoint 1/1.5 強制提醒
    """
    logger = setup_hook_logging("post-ticket-complete-checkpoint")

    try:
        input_data = json.load(sys.stdin)
    except json.JSONDecodeError as e:
        logger.error("JSON 解析錯誤: %s", e)
        print(json.dumps(DEFAULT_OUTPUT, ensure_ascii=False))
        return EXIT_SUCCESS

    # 驗證工具類型
    tool_name = input_data.get("tool_name", "")
    if tool_name != "Bash":
        logger.debug("跳過: 工具類型為 %s，非 Bash", tool_name)
        print(json.dumps(DEFAULT_OUTPUT, ensure_ascii=False))
        return EXIT_SUCCESS

    # 取得命令和輸出
    tool_input = input_data.get("tool_input", {})
    command = tool_input.get("command", "")

    tool_response = input_data.get("tool_response", {})
    stdout = tool_response.get("stdout", "")

    # 偵測 ticket complete 成功
    if is_ticket_complete_command(command) and is_complete_successful(stdout):
        logger.info("偵測到 ticket track complete 成功，輸出 Checkpoint 1/1.5 強制提醒")
        output = {
            "hookSpecificOutput": {
                "hookEventName": "PostToolUse",
                "additionalContext": AskUserQuestionMessages.POST_TICKET_COMPLETE_CHECKPOINT_REMINDER
            }
        }
    else:
        logger.debug("未偵測到 ticket complete 成功或不符合條件")
        output = DEFAULT_OUTPUT

    print(json.dumps(output, ensure_ascii=False, indent=2))
    return EXIT_SUCCESS


if __name__ == "__main__":
    exit_code = run_hook_safely(main, "post-ticket-complete-checkpoint")
    sys.exit(exit_code)
