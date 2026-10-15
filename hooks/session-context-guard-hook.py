#!/usr/bin/env -S uv run --quiet --script
# /// script
# requires-python = ">=3.9"
# dependencies = ["pyyaml"]
# ///

"""
Session Context Guard Hook - PostToolUse Hook

功能: 追蹤當前 session 內完成的 Ticket 數量，在超過閾值時輸出警告，
      提醒 PM 考慮 handoff 以保護下一個任務的思考品質。

觸發時機: Bash 工具執行後
檢測邏輯:
  1. 驗證 tool_name == "Bash"
  2. 以共用解析器檢查 command 是否為 ticket track complete/finish/batch-complete
  3. 檢查 stdout 是否包含完成標記（"已完成"）
  4. 若偵測成功，遞增計數器並在閾值時輸出警告

計數器存放: /tmp/claude-session-completed-tickets-{session_id}
（session_id 取自 hook 輸入；一次 complete 只由本 hook 計數，post-ticket-lifecycle-hook 不再計數）
失敗語意: fail-open——取不到 session_id 或檔案讀寫失敗時略過計數，不阻擋
閾值:
  - 2 個：輕度提醒（context 正在累積）
  - 3 個以上：強烈建議 handoff

研究背景（W9-016）：
  Claude Code 的 hook 事件不暴露 token 使用量，因此使用
  「session 內完成的 Ticket 數量」作為 context 累積程度的代理指標。
  依據 PC-009：Handoff first，繼續 session 是例外，不是預設。

行為: 不阻擋（exit 0），僅在 additionalContext 輸出警告訊息
"""

import sys
import json
from pathlib import Path
from typing import Optional

sys.path.insert(0, str(Path(__file__).parent))
sys.path.insert(0, str(Path(__file__).parent.parent))

from lib import setup_hook_logging, run_hook_safely, read_json_from_stdin, emit_hook_output
from lib.ticket_command_parse import has_complete_command
from lib.bash_tool_response import (
    FAILURE_EVENT_NAME, is_failure_event, auto_commit_failure_as_success, is_bash_success,
)
from lib.ticket_completed_verifier import make_completed_verifier, is_complete_transition_success
from lib.constants import SESSION_COMPLETED_TICKETS_COUNTER_TEMPLATE
from lib.session_state_key import session_state_path

# ============================================================================
# 常數定義
# ============================================================================

EXIT_SUCCESS = 0

HOOK_NAME = "session-context-guard"

# 計數器檔案路徑（以 hook 輸入的 session_id 識別 session）
COUNTER_FILE_TEMPLATE = SESSION_COMPLETED_TICKETS_COUNTER_TEMPLATE

# 輕度提醒閾值（完成 2 個 Ticket）
SOFT_WARN_THRESHOLD = 2

# 強烈建議閾值（完成 3 個以上 Ticket）
STRONG_WARN_THRESHOLD = 3

# 完成成功標記（ticket CLI 輸出）
COMPLETE_SUCCESS_MARKER = "已完成"

# PostToolUse Hook 的標準輸出結構
DEFAULT_OUTPUT = {
    "hookSpecificOutput": {
        "hookEventName": "PostToolUse"
    }
}


# ============================================================================
# 計數器管理
# ============================================================================

def get_counter_file(input_data: dict, logger=None) -> Optional[Path]:
    """取得計數器檔案路徑（以 hook 輸入的 session_id 識別 session；取不到回傳 None）"""
    return session_state_path(COUNTER_FILE_TEMPLATE, input_data, logger)


def read_counter(input_data: dict, logger=None) -> int:
    """讀取當前 session 完成的 Ticket 計數（無檔案或讀取失敗為 0，fail-open）"""
    counter_file = get_counter_file(input_data, logger)
    if counter_file is None or not counter_file.exists():
        return 0
    try:
        return int(counter_file.read_text().strip())
    except (ValueError, IOError):
        return 0


def increment_counter(input_data: dict, logger=None) -> int:
    """遞增計數器並回傳新值；取不到 session_id 時略過並回傳 0（fail-open，不觸發提醒）"""
    counter_file = get_counter_file(input_data, logger)
    if counter_file is None:
        return 0
    count = read_counter(input_data, logger) + 1
    try:
        counter_file.write_text(str(count))
    except IOError as e:
        # fail-open：寫入失敗只少一次累計，不阻擋操作；留日誌可追蹤
        if logger is not None:
            logger.warning("計數器寫入失敗: %s", e)
    return count


# ============================================================================
# 指令偵測
# ============================================================================

def is_ticket_complete_command(command: str) -> bool:
    """判斷是否為 ticket track complete/finish/batch-complete 命令。

    走共用解析器；無法解析（未閉合引號）時視為非完成命令（本 hook 不阻擋，
    漏計數優於誤計數）。
    """
    return has_complete_command(command) is True


def is_complete_successful(tool_response, command: str) -> bool:
    """判斷 ticket complete 是否成功（分層：未遮蔽即成功、遮蔽以票面驗證、其餘比對標記）"""
    return is_complete_transition_success(
        tool_response,
        [COMPLETE_SUCCESS_MARKER],
        command,
        make_completed_verifier(command),
    )


# ============================================================================
# 警告訊息生成
# ============================================================================

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


# ============================================================================
# 主要邏輯
# ============================================================================

def main() -> int:
    """
    主入口點

    流程:
    1. 讀取 stdin JSON（PostToolUse 格式）
    2. 驗證工具類型是否為 Bash
    3. 檢查命令是否為 ticket track complete
    4. 檢查輸出是否包含成功標記
    5. 若全部符合，遞增計數器並依閾值輸出警告
    """
    logger = setup_hook_logging(HOOK_NAME)

    try:
        input_data = read_json_from_stdin(logger)
    except json.JSONDecodeError as e:
        logger.error("JSON 解析錯誤: %s", e)
        print(json.dumps(DEFAULT_OUTPUT, ensure_ascii=False))
        return EXIT_SUCCESS

    if not input_data:
        print(json.dumps(DEFAULT_OUTPUT, ensure_ascii=False))
        return EXIT_SUCCESS

    # PostToolUseFailure：僅結束碼 75（動作完成、auto-commit 失敗）沿用完成後處理
    event_name = "PostToolUse"
    if is_failure_event(input_data):
        input_data = auto_commit_failure_as_success(input_data)
        if input_data is None:
            logger.debug("失敗事件非結束碼 75，不處理")
            print(json.dumps(DEFAULT_OUTPUT, ensure_ascii=False))
            return EXIT_SUCCESS
        event_name = FAILURE_EVENT_NAME

    # 驗證工具類型
    tool_name = input_data.get("tool_name", "")
    if tool_name != "Bash":
        print(json.dumps(DEFAULT_OUTPUT, ensure_ascii=False))
        return EXIT_SUCCESS

    # 取得命令和輸出
    tool_input = input_data.get("tool_input") or {}
    command = tool_input.get("command", "")

    tool_response = input_data.get("tool_response") or {}

    # 偵測 ticket track complete 成功（共用分層判定；計數只在此判定成功時遞增一次）
    if not (is_ticket_complete_command(command) and is_complete_successful(tool_response, command)):
        print(json.dumps(DEFAULT_OUTPUT, ensure_ascii=False))
        return EXIT_SUCCESS

    # 遞增計數器
    count = increment_counter(input_data, logger)
    logger.info("Ticket 完成計數：%d", count)

    # 依閾值決定輸出
    if count >= STRONG_WARN_THRESHOLD:
        warning = build_strong_warning(count)
        logger.info("強烈建議 handoff（%d 個 Ticket）", count)
    elif count >= SOFT_WARN_THRESHOLD:
        warning = build_soft_warning(count)
        logger.info("輕度提醒 handoff（%d 個 Ticket）", count)
    else:
        # 第 1 個 Ticket，靜默通過
        print(json.dumps(DEFAULT_OUTPUT, ensure_ascii=False))
        return EXIT_SUCCESS

    # handoff 提醒為 PM-only：統一出口過濾 subagent 觸發（PC-V1-004 防護 C）
    emit_hook_output(
        event_name,
        additional_context=warning,
        audience="pm_only",
        input_data=input_data,
    )
    return EXIT_SUCCESS


if __name__ == "__main__":
    exit_code = run_hook_safely(main, HOOK_NAME)
    sys.exit(exit_code)
