#!/usr/bin/env -S uv run --quiet --script
# /// script
# requires-python = ">=3.9"
# dependencies = []
# ///

"""
Session Context Guard Hook - PostToolUse Hook

功能: 追蹤當前 session 內完成的 Ticket 數量，在超過閾值時輸出警告，
      提醒 PM 考慮 handoff 以保護下一個任務的思考品質。

觸發時機: Bash 工具執行後
檢測邏輯:
  1. 驗證 tool_name == "Bash"
  2. 檢查 command 是否包含 "ticket track complete" 或 "ticket complete"
  3. 檢查 stdout 是否包含完成標記（"已完成"）
  4. 若偵測成功，遞增計數器並在閾值時輸出警告

計數器存放: /tmp/claude-session-completed-tickets-{ppid}
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
import os
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from hook_utils import setup_hook_logging, run_hook_safely

# ============================================================================
# 常數定義
# ============================================================================

EXIT_SUCCESS = 0

HOOK_NAME = "session-context-guard"

# 計數器檔案路徑（使用 ppid 識別 session）
COUNTER_FILE_TEMPLATE = "/tmp/claude-session-completed-tickets-{ppid}"

# 輕度提醒閾值（完成 2 個 Ticket）
SOFT_WARN_THRESHOLD = 2

# 強烈建議閾值（完成 3 個以上 Ticket）
STRONG_WARN_THRESHOLD = 3

# 完成指令關鍵字
COMPLETE_COMMAND_PATTERNS = [
    "ticket track complete",
    "ticket complete",
]

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


# ============================================================================
# 指令偵測
# ============================================================================

def is_ticket_complete_command(command: str) -> bool:
    """判斷是否為 ticket track complete 命令"""
    return any(pattern in command for pattern in COMPLETE_COMMAND_PATTERNS)


def is_complete_successful(stdout: str) -> bool:
    """判斷 ticket complete 是否成功"""
    return COMPLETE_SUCCESS_MARKER in stdout


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
        input_data = json.load(sys.stdin)
    except json.JSONDecodeError as e:
        logger.error("JSON 解析錯誤: %s", e)
        print(json.dumps(DEFAULT_OUTPUT, ensure_ascii=False))
        return EXIT_SUCCESS

    # 驗證工具類型
    tool_name = input_data.get("tool_name", "")
    if tool_name != "Bash":
        print(json.dumps(DEFAULT_OUTPUT, ensure_ascii=False))
        return EXIT_SUCCESS

    # 取得命令和輸出
    tool_input = input_data.get("tool_input", {})
    command = tool_input.get("command", "")

    tool_response = input_data.get("tool_response", {})
    stdout = tool_response.get("stdout", "")

    # 偵測 ticket track complete 成功
    if not (is_ticket_complete_command(command) and is_complete_successful(stdout)):
        print(json.dumps(DEFAULT_OUTPUT, ensure_ascii=False))
        return EXIT_SUCCESS

    # 遞增計數器
    count = increment_counter()
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

    output = {
        "hookSpecificOutput": {
            "hookEventName": "PostToolUse",
            "additionalContext": warning
        }
    }
    print(json.dumps(output, ensure_ascii=False, indent=2))
    return EXIT_SUCCESS


if __name__ == "__main__":
    exit_code = run_hook_safely(main, HOOK_NAME)
    sys.exit(exit_code)
