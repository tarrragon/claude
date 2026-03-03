#!/usr/bin/env -S uv run --quiet --script
# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///

"""
Bash Edit Guard Hook - PreToolUse Hook

功能: 偵測 Bash 中的檔案編輯操作，建議使用 Edit 工具替代

觸發時機: 執行 Bash 工具時
檢測模式:
  - sed -i 或 sed --in-place (原地編輯)
  - sed 配合管道輸出到檔案
  - awk 輸出到檔案（>）
  - perl -pi (原地編輯)
  - 輸出重定向到程式碼檔案 (>.dart, >.arb, >.json)

行為: 輸出警告訊息到 stderr，允許命令繼續執行 (exit code 0)
"""

import json
import sys
import re
from pathlib import Path

# 加入 hook_utils 路徑（相同目錄）
_hooks_dir = Path(__file__).parent
if _hooks_dir not in [p for p in sys.path if Path(p) == _hooks_dir]:
    sys.path.insert(0, str(_hooks_dir))

from hook_utils import setup_hook_logging, run_hook_safely
from lib.hook_messages import ValidationMessages, format_message


def _detect_bash_edit_patterns(command: str) -> bool:
    """
    檢測是否為編輯操作

    檢測模式:
    1. sed -i 或 sed --in-place
    2. sed 配合管道輸出到檔案 (| tee / > file)
    3. awk 輸出到檔案（>）
    4. perl -pi
    5. 輸出重定向到程式碼檔案 (>.dart, >.arb, >.json)

    Args:
        command: Bash 命令

    Returns:
        bool - 是否偵測到編輯模式
    """
    # 模式 1: sed -i 或 sed --in-place
    if re.search(r'sed\s+(-i|--in-place)', command):
        return True

    # 模式 2: sed 配合輸出重定向 (> file)
    if re.search(r'sed\s+.*[>].*\.dart|sed\s+.*[>].*\.arb|sed\s+.*[>].*\.json', command):
        return True

    # 模式 3: sed 配合管道輸出到檔案 (| tee / > file)
    if re.search(r'sed\s+.*[|]\s*(tee|cat)', command) and re.search(r'[>]\s*\S+\.(dart|arb|json)', command):
        return True

    # 模式 4: awk 輸出到檔案
    if re.search(r'awk\s+.*[>].*\.dart|awk\s+.*[>].*\.arb|awk\s+.*[>].*\.json', command):
        return True

    # 模式 5: perl -pi (原地編輯)
    if re.search(r'perl\s+(-pi|-i\.bak)', command):
        return True

    # 模式 6: 通用輸出重定向到程式碼檔案（任何命令 > *.dart/arb/json）
    if re.search(r'[>]\s*\S+\.(dart|arb|json|md|txt|yaml|yml)', command):
        # 排除某些已知的安全操作（如註解、日誌等）
        if not any(pattern in command for pattern in ['echo', 'printf', '#', 'comment', 'log']):
            # 檢查是否為明確的程式碼編輯操作
            if any(pattern in command for pattern in ['sed', 'awk', 'perl', 'tr', 'cut']):
                return True

    return False


def _print_warning_message(command: str) -> None:
    """
    輸出警告訊息到 stderr

    Args:
        command: 檢測到的 Bash 命令
    """
    # 截短命令顯示（最多 100 字元）
    display_command = command[:100] + ('...' if len(command) > 100 else '')

    warning = format_message(
        ValidationMessages.BASH_EDIT_DETAILED_WARNING,
        command=display_command
    )
    print(warning)


def main() -> int:
    """主入口點"""
    logger = setup_hook_logging("bash-edit-guard")

    try:
        # 讀取 JSON 輸入
        input_data = json.load(sys.stdin)
        tool_name = input_data.get("tool_name", "")
        tool_input = input_data.get("tool_input", {})

        # 檢查是否為 Bash 工具
        if tool_name != "Bash":
            # 非 Bash 工具：直接允許
            logger.info("跳過: 工具類型 %s 不是 Bash", tool_name)
            return 0

        # 取得命令內容
        command = tool_input.get("command", "")

        # 檢測編輯模式
        if not _detect_bash_edit_patterns(command):
            # 不符合編輯模式：直接允許
            logger.info("允許: 正常 Bash 命令")
            return 0

        # 偵測到編輯模式：輸出警告並記錄
        logger.info("警告: 偵測到編輯操作 - %s", command[:100])
        _print_warning_message(command)

        # 輸出符合官方規範的 JSON 格式（允許繼續執行）
        result = {
            "hookSpecificOutput": {
                "hookEventName": "PreToolUse",
                "permissionDecision": "allow",
                "permissionDecisionReason": "Bash 編輯操作警告已發送，允許執行"
            }
        }
        print(json.dumps(result, ensure_ascii=False))

        return 0

    except json.JSONDecodeError as e:
        logger.error("JSON 解析錯誤: %s", e)
        # JSON 解析失敗：直接允許執行，不阻塊
        return 0
    except Exception as e:
        logger.error("執行錯誤: %s", e)
        # 任何錯誤都不阻塊（非阻塞原則）
        return 0


if __name__ == "__main__":
    exit_code = run_hook_safely(main, "bash-edit-guard")
    sys.exit(exit_code)
