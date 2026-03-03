#!/usr/bin/env python3
"""
AskUserQuestion Reminder Hook - 多任務派發提醒

在 Task 工具的 prompt 中偵測到 2+ 個 Ticket ID 時，
提醒 PM 使用 AskUserQuestion 確認派發方式。

Hook 類型: PreToolUse (matcher: Task)
觸發條件: Task prompt 包含 2+ 個 Ticket ID pattern
行為: 輸出提醒到 additionalContext，不阻擋（exit 0）

Exit Code:
- 0: 允許執行（可能帶有提醒）
"""

import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

try:
    from hook_utils import setup_hook_logging
    from lib.hook_messages import AskUserQuestionMessages
except ImportError as e:
    print(f"[Hook Import Error] {Path(__file__).name}: {e}", file=sys.stderr)
    sys.exit(0)  # Import 失敗不阻擋

# Ticket ID 正則表達式
TICKET_ID_PATTERN = re.compile(r"\d+\.\d+\.\d+-W\d+-\d+")


def main() -> int:
    """主入口點"""
    logger = setup_hook_logging("askuserquestion-reminder")

    try:
        logger.info("AskUserQuestion Reminder Hook 啟動")

        # 讀取輸入
        input_data = json.load(sys.stdin)
        tool_name = input_data.get("tool_name", "")

        # 只處理 Task 工具
        if tool_name != "Task":
            logger.debug(f"非 Task 工具: {tool_name}，跳過")
            output = {
                "hookSpecificOutput": {
                    "hookEventName": "PreToolUse",
                    "permissionDecision": "allow"
                }
            }
            print(json.dumps(output, ensure_ascii=False, indent=2))
            return 0

        # 提取 Task prompt
        tool_input = input_data.get("tool_input", {})
        prompt = tool_input.get("prompt", "")

        # 搜尋 Ticket ID
        ticket_ids = TICKET_ID_PATTERN.findall(prompt)
        unique_ids = set(ticket_ids)

        logger.info(f"在 Task prompt 中找到 {len(unique_ids)} 個 Ticket ID")

        output = {
            "hookSpecificOutput": {
                "hookEventName": "PreToolUse",
                "permissionDecision": "allow"
            }
        }

        # 2+ 個 Ticket ID 時輸出提醒
        if len(unique_ids) >= 2:
            logger.info(f"偵測到多任務派發: {unique_ids}")
            output["hookSpecificOutput"]["additionalContext"] = (
                AskUserQuestionMessages.DISPATCH_REMINDER
            )

        print(json.dumps(output, ensure_ascii=False, indent=2))
        return 0

    except json.JSONDecodeError:
        logger.warning("JSON 解析錯誤，預設允許")
        output = {
            "hookSpecificOutput": {
                "hookEventName": "PreToolUse",
                "permissionDecision": "allow"
            }
        }
        print(json.dumps(output, ensure_ascii=False, indent=2))
        return 0

    except Exception as e:
        logger.error(f"Hook 執行錯誤: {e}", exc_info=True)
        output = {
            "hookSpecificOutput": {
                "hookEventName": "PreToolUse",
                "permissionDecision": "allow"
            }
        }
        print(json.dumps(output, ensure_ascii=False, indent=2))
        return 0


if __name__ == "__main__":
    sys.exit(main())
