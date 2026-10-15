#!/usr/bin/env -S uv run --quiet --script
# /// script
# requires-python = ">=3.11"
# dependencies = ["pyyaml"]
# ///

"""
Ticket 生命週期合併 Hook - PostToolUse Hook

合併自:
- post-ticket-complete-checkpoint-hook.py（Ticket complete 後的 Checkpoint 1/1.5 提醒）

session 完成計數不在此 hook：同一次 complete 只由 session-context-guard-hook.py 計數。

觸發時機: Bash 工具執行後，command 含 ticket track complete/finish/batch-complete
執行內容:
  output_checkpoint_reminder — 輸出 Checkpoint 1/1.5 提醒

行為: 不阻擋（exit 0），僅在 additionalContext 輸出提醒訊息
"""

import sys
import json
from pathlib import Path
from typing import Optional, Dict, Any, List

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "hooks"))

from lib import (
    setup_hook_logging,
    run_hook_safely,
    read_json_from_stdin,
    extract_tool_input,
    extract_tool_response,
    is_subagent_environment,
)
from lib.hook_messages import AskUserQuestionMessages
from lib.ticket_command_parse import has_complete_command
from lib.bash_tool_response import (
    FAILURE_EVENT_NAME, is_failure_event, auto_commit_failure_as_success, is_bash_success,
)
from lib.ticket_completed_verifier import make_completed_verifier, is_complete_transition_success

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

# 完成成功標記
COMPLETE_SUCCESS_MARKERS = [
    "已完成",
]



# ============================================================================
# 共用偵測函式
# ============================================================================

def is_ticket_complete_command(command: str) -> bool:
    """判斷是否為完成類命令（complete／finish／batch-complete），走共用解析器。

    無法解析（未閉合引號）時視為非完成命令：本 hook 不阻擋，漏計數優於誤計數。
    """
    return has_complete_command(command) is True


def is_complete_successful(tool_response, command: str) -> bool:
    """判斷 ticket complete 是否成功（分層：未遮蔽即成功、遮蔽以票面驗證、其餘比對標記）"""
    return is_complete_transition_success(
        tool_response,
        COMPLETE_SUCCESS_MARKERS,
        command,
        make_completed_verifier(command),
    )


# ============================================================================
# 子邏輯 1: Session Context Guard（來自 session-context-guard-hook）
# ============================================================================

# Session 完成計數已移除：同一次 complete 只由 session-context-guard-hook 計數
# （該 hook 另有 PM-only 受眾過濾；兩 hook 同註冊於 PostToolUse:Bash 時重複計數）。


# ============================================================================
# 子邏輯 2: Checkpoint Reminder（來自 post-ticket-complete-checkpoint-hook）
# ============================================================================

def output_checkpoint_reminder(input_data: Dict[str, Any], logger) -> Optional[str]:
    """
    輸出 Checkpoint 1/1.5 提醒（來自 post-ticket-complete-checkpoint-hook）

    Returns:
        提醒訊息字串，或 None（subagent 環境跳過）
    """
    # subagent 環境不提醒
    if is_subagent_environment(input_data):
        logger.info("checkpoint: 偵測到 subagent 環境，跳過提醒")
        return None

    logger.info("checkpoint: 輸出 Checkpoint 1/1.5 強制提醒")
    return AskUserQuestionMessages.POST_TICKET_COMPLETE_CHECKPOINT_REMINDER


# ============================================================================
# 主要邏輯
# ============================================================================

def main() -> int:
    """
    主入口點

    流程:
    1. 讀取 stdin JSON（PostToolUse 格式）
    2. 驗證工具類型是否為 Bash
    3. 檢查是否為 ticket complete 命令且成功
    4. 依序呼叫子邏輯：session counter → checkpoint reminder
    5. 合併輸出
    """
    logger = setup_hook_logging("post-ticket-lifecycle-hook")

    try:
        input_data = read_json_from_stdin(logger)
    except (json.JSONDecodeError, Exception) as e:
        logger.error("JSON 解析錯誤: %s", e)
        print(json.dumps(DEFAULT_OUTPUT, ensure_ascii=False))
        return EXIT_SUCCESS

    if input_data is None:
        logger.info("無法解析輸入，安全降級")
        print(json.dumps(DEFAULT_OUTPUT, ensure_ascii=False))
        return EXIT_SUCCESS

    # PostToolUseFailure：僅結束碼 75（動作完成、auto-commit 失敗）沿用完成後處理
    if is_failure_event(input_data):
        input_data = auto_commit_failure_as_success(input_data)
        if input_data is None:
            logger.debug("失敗事件非結束碼 75，不處理")
            print(json.dumps(DEFAULT_OUTPUT, ensure_ascii=False))
            return EXIT_SUCCESS
        event_name = FAILURE_EVENT_NAME
    else:
        event_name = DEFAULT_OUTPUT["hookSpecificOutput"]["hookEventName"]

    # 驗證工具類型
    tool_name = input_data.get("tool_name", "")
    if tool_name != "Bash":
        logger.debug("跳過: 工具類型為 %s，非 Bash", tool_name)
        print(json.dumps(DEFAULT_OUTPUT, ensure_ascii=False))
        return EXIT_SUCCESS

    # 取得命令和輸出
    tool_input = extract_tool_input(input_data, logger)
    command = tool_input.get("command", "")

    tool_response = extract_tool_response(input_data, logger)

    # 檢查是否為 ticket complete 成功
    if not (is_ticket_complete_command(command) and is_complete_successful(tool_response, command)):
        print(json.dumps(DEFAULT_OUTPUT, ensure_ascii=False))
        return EXIT_SUCCESS

    # 收集所有子邏輯的輸出
    messages: List[str] = []

    # Checkpoint Reminder
    try:
        checkpoint_msg = output_checkpoint_reminder(input_data, logger)
        if checkpoint_msg:
            messages.append(checkpoint_msg)
    except Exception as e:
        logger.error("output_checkpoint_reminder 例外: %s", e, exc_info=True)

    # 輸出結果
    if messages:
        output = {
            "hookSpecificOutput": {
                "hookEventName": event_name,
                "additionalContext": "\n\n".join(messages)
            }
        }
    else:
        output = DEFAULT_OUTPUT

    print(json.dumps(output, ensure_ascii=False, indent=2))
    return EXIT_SUCCESS


if __name__ == "__main__":
    exit_code = run_hook_safely(main, "post-ticket-lifecycle-hook")
    sys.exit(exit_code)
