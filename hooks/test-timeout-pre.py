#!/usr/bin/env -S uv run --quiet --script
# /// script
# requires-python = ">=3.11"
# dependencies = ["pyyaml"]
# ///
"""
測試超時監控 - PreToolUse Hook
功能: 記錄測試開始時間

觸發時機: 執行測試命令（flutter／dart／npm／pytest，含 timeout、fvm、uv run、
          run-with-timeout.py 前綴）或 mcp__dart__run_tests 工具前；判定與 post-test-hook 共用
          lib/test_command_parse.py，寫入端與讀取端集合一致
記錄位置: .claude/hook-logs/test-monitor/<tool_use_id>.json（退路 session_id，再退回舊單檔 test-monitor.json）
背景命令: 不寫監控檔
"""

import json
import os
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
sys.path.insert(0, str(Path(__file__).parent.parent))
from lib import setup_hook_logging, run_hook_safely, get_project_root, read_json_from_stdin
from lib.test_command_parse import find_test_invocations
from lib.test_monitor_path import monitor_key, keyed_monitor_file, legacy_monitor_file, prune_stale_keyed_files


def main():
    logger = setup_hook_logging("test-timeout-pre")
    input_data = read_json_from_stdin(logger)
    if input_data is None:
        return 0

    tool_name = input_data.get("tool_name", "")
    tool_input = input_data.get("tool_input") or {}

    # 檢查是否為測試命令
    is_test_command = False
    if tool_name == "Bash":
        command = tool_input.get("command", "")
        # 解析失敗（None）視為非測試：監控型 hook，漏判只少一次計時
        is_test_command = bool(find_test_invocations(command))
    elif tool_name == "mcp__dart__run_tests":
        is_test_command = True

    if not is_test_command:
        # 非測試命令：直接退出，不輸出任何內容（exit 0 = 成功）
        return 0

    # 背景命令不寫監控檔：post 在背景啟動回傳時直接跳過收尾（無檔可收會停在 running），
    # 且單檔退路（無鍵）下寫入會覆寫前景命令的開始時間
    if tool_input.get("run_in_background") is True:
        logger.debug("run_in_background 為真，不建立監控檔")
        return 0

    # 記錄測試開始時間
    project_dir = get_project_root()
    key = monitor_key(input_data)
    monitor_file = (keyed_monitor_file(project_dir, key) if key
                    else legacy_monitor_file(project_dir))
    monitor_file.parent.mkdir(parents=True, exist_ok=True)
    # 有鍵時順手清掉逾時未收尾的殘留鍵檔（fail-open，不影響本次寫入）
    if key:
        prune_stale_keyed_files(project_dir, logger)

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
