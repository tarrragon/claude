#!/usr/bin/env -S uv run --quiet --script
# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""
測試超時監控 - PostToolUse Hook
功能: 計算執行時間，根據閾值採取行動

閾值設定（混合模式）:
  - 警告閾值: 5 分鐘
  - 嚴重閾值: 15 分鐘
  - 自動終止: 30 分鐘

觸發時機: flutter test / dart test 或 mcp__dart__run_tests 工具完成後
"""

import json
import os
import subprocess
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from hook_utils import setup_hook_logging, run_hook_safely

# 閾值設定（秒）
WARNING_THRESHOLD = 300    # 5 分鐘
CRITICAL_THRESHOLD = 900   # 15 分鐘
AUTO_KILL_THRESHOLD = 1800  # 30 分鐘


def main():
    logger = setup_hook_logging("test-timeout-post")
    input_data = json.load(sys.stdin)
    tool_name = input_data.get("tool_name", "")

    # 檢查是否為測試命令
    is_test_command = False
    if tool_name == "Bash":
        command = input_data.get("tool_input", {}).get("command", "")
        is_test_command = "flutter test" in command or "dart test" in command
    elif tool_name == "mcp__dart__run_tests":
        is_test_command = True

    if not is_test_command:
        return 0

    # 讀取監控檔案
    project_dir = Path(os.getenv("CLAUDE_PROJECT_DIR", Path.cwd()))
    monitor_file = project_dir / ".claude" / "hook-logs" / "test-monitor.json"

    if not monitor_file.exists():
        return 0

    try:
        with open(monitor_file) as f:
            monitor_data = json.load(f)
    except (json.JSONDecodeError, OSError):
        return 0

    start_timestamp = monitor_data.get("start_timestamp", 0)
    if start_timestamp == 0:
        return 0

    duration = datetime.now().timestamp() - start_timestamp
    duration_minutes = duration / 60

    # 更新狀態
    monitor_data["end_time"] = datetime.now().isoformat()
    monitor_data["duration_seconds"] = duration
    monitor_data["status"] = "completed"

    # 根據時長決定行動
    message = ""
    if duration >= AUTO_KILL_THRESHOLD:
        # 自動終止
        subprocess.run(["pkill", "-f", "flutter_tester"], capture_output=True)
        message = f"測試執行 {duration_minutes:.1f} 分鐘，已自動終止 flutter_tester"
        monitor_data["action"] = "auto_killed"
    elif duration >= CRITICAL_THRESHOLD:
        message = f"嚴重警告：測試執行 {duration_minutes:.1f} 分鐘，建議手動終止"
        monitor_data["action"] = "critical_warning"
    elif duration >= WARNING_THRESHOLD:
        message = f"警告：測試執行 {duration_minutes:.1f} 分鐘，可能有卡住問題"
        monitor_data["action"] = "warning"
    else:
        message = f"測試完成：{duration_minutes:.1f} 分鐘"
        monitor_data["action"] = "normal"

    # 寫回監控檔案
    with open(monitor_file, "w") as f:
        json.dump(monitor_data, f, indent=2, ensure_ascii=False)

    # 記錄到歷史日誌
    history_file = project_dir / ".claude" / "hook-logs" / "test-duration-history.jsonl"
    with open(history_file, "a") as f:
        f.write(json.dumps(monitor_data, ensure_ascii=False) + "\n")

    # 輸出訊息到 stdout（會顯示給用戶）
    print(message)
    return 0


if __name__ == "__main__":
    sys.exit(run_hook_safely(main, "test-timeout-post"))
