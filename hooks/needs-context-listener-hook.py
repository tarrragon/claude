#!/usr/bin/env -S uv run --quiet --script
# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///

"""
NeedsContext Listener Hook - PostToolUse (Bash)

功能:
  監聽 `ticket track append-log ... --section NeedsContext ...` 命令執行事件，
  當代理人透過 NeedsContext section 回報資料缺口時，觸發 PushNotification 讓 PM
  立即得知並補料，避免代理人靜默卡住或用錯誤假設繼續工作。

觸發時機: Bash 工具呼叫後 (PostToolUse, matcher: Bash)
行為:
  - 若命令為 ticket track append-log --section NeedsContext 且執行成功，
    輸出 systemMessage 讓 PM 看到提示
  - 其他情況靜默通過 (exit 0)

來源:
  - 0.18.0-W17-010（W17-007 ANA 三 IMP 合併）
  - 協議定義：ticket body 中 `## NeedsContext` section，子項含缺失項/觸發位置/
    影響/建議補料/重派成本
"""

import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from hook_utils import (
    setup_hook_logging,
    read_json_from_stdin,
    extract_tool_input,
    run_hook_safely,
)

HOOK_NAME = "needs-context-listener-hook"
EXIT_SUCCESS = 0

# 匹配 ticket track append-log <id> --section "NeedsContext" (非貪婪，且 --section
# 緊跟在 ticket_id 後 token；避免 NeedsContext 出現在 content payload 時的誤判)
# 正確用法：ticket track append-log <id> --section "NeedsContext" "content..."
_SECTION_ARG_RE = re.compile(
    r"ticket\s+track\s+append-log\s+(\S+)\s+--section\s+['\"]?([^'\"\s]+)['\"]?"
)


def extract_ticket_id(command: str) -> str | None:
    """若命令為 ticket track append-log <id> --section NeedsContext，回傳 ticket_id。

    僅匹配 --section 參數值恰為 NeedsContext 的情況；content 內文出現 NeedsContext
    不會觸發（避免 W17-010 自我實測時的 false positive）。
    """
    if not command:
        return None
    match = _SECTION_ARG_RE.search(command)
    if not match:
        return None
    ticket_id, section = match.group(1), match.group(2)
    if section != "NeedsContext":
        return None
    return ticket_id


def main_logic() -> int:
    logger = setup_hook_logging(HOOK_NAME)
    payload = read_json_from_stdin(logger)
    tool_input = extract_tool_input(payload)
    command = tool_input.get("command", "") if isinstance(tool_input, dict) else ""

    ticket_id = extract_ticket_id(command)
    if not ticket_id:
        return EXIT_SUCCESS

    # 檢查執行是否成功（tool_response.success 或無錯誤指示）
    tool_response = payload.get("tool_response", {}) if isinstance(payload, dict) else {}
    if isinstance(tool_response, dict):
        # 若有明確失敗指示則不通知（避免誤報）
        if tool_response.get("success") is False:
            return EXIT_SUCCESS

    message = (
        f"[NeedsContext] 代理人已於 {ticket_id} 回報資料缺口；"
        f"請 PM 執行 `ticket track full {ticket_id}` 檢視 NeedsContext section 並補料"
    )
    logger.info(message)

    # 透過 hookSpecificOutput systemMessage 讓 PM 看到
    output = {
        "hookSpecificOutput": {
            "hookEventName": "PostToolUse",
            "additionalContext": message,
        }
    }
    print(json.dumps(output, ensure_ascii=False))
    return EXIT_SUCCESS


def main() -> int:
    return run_hook_safely(main_logic, HOOK_NAME)


if __name__ == "__main__":
    sys.exit(main())
