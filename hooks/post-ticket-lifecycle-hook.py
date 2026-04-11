#!/usr/bin/env -S uv run --quiet --script
# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///

"""
Ticket 生命週期合併 Hook - PostToolUse Hook

合併自:
- session-context-guard-hook.py（session 內 Ticket 完成計數與 handoff 警告）
- post-ticket-complete-checkpoint-hook.py（Ticket complete 後的 Checkpoint 1/1.5 提醒）

觸發時機: Bash 工具執行後，command 包含 ticket track complete/batch-complete
執行順序:
  1. update_session_counter — 更新 session 完成計數器（先執行，因為 checkpoint 可能參考計數）
  2. output_checkpoint_reminder — 輸出 Checkpoint 1/1.5 提醒

行為: 不阻擋（exit 0），僅在 additionalContext 輸出提醒訊息

HOOK_METADATA (JSON):
{
  "event_type": "PostToolUse",
  "matcher": "Bash",
  "timeout": 5000,
  "description": "Ticket 完成後生命週期處理（合併 session-context-guard + post-ticket-complete-checkpoint）",
  "dependencies": [],
  "version": "1.0.0"
}
"""

import sys
import json
import os
from pathlib import Path
from typing import Optional, Dict, Any, List

sys.path.insert(0, str(Path(__file__).parent))

from hook_utils import (
    setup_hook_logging,
    run_hook_safely,
    read_json_from_stdin,
    extract_tool_input,
    extract_tool_response,
    is_subagent_environment,
)
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

# 完成指令關鍵字
COMPLETE_COMMAND_PATTERNS = [
    "ticket track complete",
    "ticket track batch-complete",
    "ticket complete",
]

# 完成成功標記
COMPLETE_SUCCESS_MARKERS = [
    "已完成",
]

# --- Session Context Guard 常數 ---

COUNTER_FILE_TEMPLATE = "/tmp/claude-session-completed-tickets-{ppid}"
SOFT_WARN_THRESHOLD = 2
STRONG_WARN_THRESHOLD = 3


# ============================================================================
# 共用偵測函式
# ============================================================================

def is_ticket_complete_command(command: str) -> bool:
    """判斷是否為 ticket track complete 命令"""
    return any(pattern in command for pattern in COMPLETE_COMMAND_PATTERNS)


def is_complete_successful(stdout: str) -> bool:
    """判斷 ticket complete 是否成功"""
    return any(marker in stdout for marker in COMPLETE_SUCCESS_MARKERS)


# ============================================================================
# 子邏輯 1: Session Context Guard（來自 session-context-guard-hook）
# ============================================================================

def get_counter_file() -> Path:
    """取得計數器檔案路徑（以 ppid 識別 session）"""
    ppid = os.getppid()
    return Path(COUNTER_FILE_TEMPLATE.format(ppid=ppid))


def read_counter() -> int:
    """讀取當前 session 完成的 Ticket 計數"""
    counter_file = get_counter_file()
    if not counter_file.exists():
        return 0
    try:
        return int(counter_file.read_text().strip())
    except (ValueError, IOError):
        return 0


def increment_counter() -> int:
    """遞增計數器並回傳新值"""
    counter_file = get_counter_file()
    count = read_counter() + 1
    try:
        counter_file.write_text(str(count))
    except IOError:
        pass
    return count


def build_soft_warning(count: int) -> str:
    """建立輕度提醒訊息（2 個 Ticket）"""
    return (
        f"============================================================\n"
        f"[Session Context Guard] 本 session 已完成 {count} 個 Ticket\n"
        f"============================================================\n"
        f"\n"
        f"Context 正在累積。每次 commit 後請考慮 handoff 以保持清晰的思考品質。\n"
        f"\n"
        f"核心原則（PC-009）：Handoff first，繼續 session 是例外，不是預設。\n"
        f"============================================================"
    )


def build_strong_warning(count: int) -> str:
    """建立強烈建議訊息（3 個以上 Ticket）"""
    return (
        f"============================================================\n"
        f"[Session Context Guard] 本 session 已完成 {count} 個 Ticket - 強烈建議 Handoff\n"
        f"============================================================\n"
        f"\n"
        f"本 session 已執行多個 Ticket，context 累積可能影響後續任務的思考品質。\n"
        f"\n"
        f"建議：下次 commit 後選擇 Handoff，在新 session 以乾淨 context 繼續工作。\n"
        f"\n"
        f"核心原則（PC-009）：Context 是有限資源。Handoff first，繼續 session 是例外。\n"
        f"============================================================"
    )


def update_session_counter(input_data: Dict[str, Any], logger) -> Optional[str]:
    """
    更新 session 完成計數器並回傳警告訊息（來自 session-context-guard-hook）

    Returns:
        警告訊息字串，或 None 表示不需要警告
    """
    count = increment_counter()
    logger.info("session-counter: Ticket 完成計數：%d", count)

    if count >= STRONG_WARN_THRESHOLD:
        logger.info("session-counter: 強烈建議 handoff（%d 個 Ticket）", count)
        return build_strong_warning(count)
    elif count >= SOFT_WARN_THRESHOLD:
        logger.info("session-counter: 輕度提醒 handoff（%d 個 Ticket）", count)
        return build_soft_warning(count)

    return None


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
    stdout = tool_response.get("stdout", "")

    # 檢查是否為 ticket complete 成功
    if not (is_ticket_complete_command(command) and is_complete_successful(stdout)):
        print(json.dumps(DEFAULT_OUTPUT, ensure_ascii=False))
        return EXIT_SUCCESS

    # 收集所有子邏輯的輸出
    messages: List[str] = []

    # 子邏輯 1: Session Counter（先執行）
    try:
        counter_msg = update_session_counter(input_data, logger)
        if counter_msg:
            messages.append(counter_msg)
    except Exception as e:
        logger.error("update_session_counter 例外: %s", e, exc_info=True)

    # 子邏輯 2: Checkpoint Reminder
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
                "hookEventName": "PostToolUse",
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
