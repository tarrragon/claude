#!/usr/bin/env -S uv run --quiet --script
# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""
測試超時監控 - PreToolUse Hook
功能: 記錄測試開始時間

觸發時機: 執行 flutter test / dart test 或 mcp__dart__run_tests 工具前
記錄位置: .claude/hook-logs/test-monitor.json
"""

import json
import os
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from hook_utils import setup_hook_logging, run_hook_safely


def main():
    logger = setup_hook_logging("test-timeout-pre")
    input_data = json.load(sys.stdin)
    tool_name = input_data.get("tool_name", "")
    tool_input = input_data.get("tool_input", {})

    # 檢查是否為測試命令
    is_test_command = False
    if tool_name == "Bash":
        command = tool_input.get("command", "")
        is_test_command = "flutter test" in command or "dart test" in command
    elif tool_name == "mcp__dart__run_tests":
        is_test_command = True

    if not is_test_command:
        # 非測試命令：直接退出，不輸出任何內容（exit 0 = 成功）
        return 0

    # 記錄測試開始時間
    project_dir = Path(os.getenv("CLAUDE_PROJECT_DIR", Path.cwd()))
    monitor_file = project_dir / ".claude" / "hook-logs" / "test-monitor.json"
    monitor_file.parent.mkdir(parents=True, exist_ok=True)

    monitor_data = {
        "start_time": datetime.now().isoformat(),
        "start_timestamp": datetime.now().timestamp(),
        "tool_name": tool_name,
        "command": tool_input.get("command", str(tool_input)),
        "status": "running"
    }

    with open(monitor_file, "w") as f:
        json.dump(monitor_data, f, indent=2, ensure_ascii=False)

    # 輸出符合官方規範的 JSON 格式
    result = {
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "allow",
            "permissionDecisionReason": "測試超時監控已啟動 (5/15/30 分鐘閾值)"
        }
    }
    print(json.dumps(result, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(run_hook_safely(main, "test-timeout-pre"))
