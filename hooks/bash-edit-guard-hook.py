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

from hook_utils import setup_hook_logging, run_hook_safely, read_json_from_stdin, emit_hook_output
from lib.hook_messages import ValidationMessages, format_message


def _detect_bash_edit_patterns(command: str) -> bool:
    """
    檢測是否為高風險原地編輯操作（白名單降級版本）

    降級策略（W10-047.1）：
    原始 6 個 pattern 中保留 2 個高風險原地編輯模式（sed -i / perl -pi），
    移除 4 個噪音模式（輸出重定向 / awk 重定向 / 通用 > 檔案）。
    依據 W10-035.3 ANA：3d 觸發 1662 次 Action ~0%；
    保留的兩個 pattern 才是真正的原地編輯不可逆風險。

    保留模式:
    1. sed -i 或 sed --in-place（原地編輯，不可逆）
    2. perl -pi 或 perl -i.bak（原地編輯，不可逆）

    移除模式（觀察期 W10-047.3 起）:
    - sed/awk + > file 重定向（多為合法產出）
    - 通用命令 > 程式碼檔（多為合法產出，誤報率高）

    Args:
        command: Bash 命令

    Returns:
        bool - 是否偵測到高風險原地編輯模式
    """
    # 模式 1: sed -i 或 sed --in-place（原地編輯）
    if re.search(r'sed\s+(-i|--in-place)', command):
        return True

    # 模式 2: perl -pi 或 perl -i.bak（原地編輯）
    if re.search(r'perl\s+(-pi|-i\.bak)', command):
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
    return warning


def main() -> int:
    """主入口點"""
    logger = setup_hook_logging("bash-edit-guard")

    try:
        # 讀取 JSON 輸入
        input_data = read_json_from_stdin(logger)
        if input_data is None:
            return 0
        tool_name = input_data.get("tool_name", "")
        tool_input = input_data.get("tool_input") or {}

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
        warning_msg = _print_warning_message(command)

        # 單一 JSON 輸出：合併警告和 permissionDecision
        emit_hook_output(
            "PreToolUse",
            additional_context=warning_msg,
            permission_decision="allow",
            permission_decision_reason="Bash 編輯操作警告已發送，允許執行",
        )

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
