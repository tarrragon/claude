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
import os
import sys
import re
from datetime import datetime
from pathlib import Path


def setup_logging():
    """初始化日誌系統"""
    project_dir = Path(os.getenv("CLAUDE_PROJECT_DIR", Path.cwd()))
    log_dir = project_dir / ".claude" / "hook-logs" / "bash-edit-guard"
    log_dir.mkdir(parents=True, exist_ok=True)

    log_file = log_dir / f"bash-edit-guard-{datetime.now().strftime('%Y%m%d')}.log"
    return log_file


def log_message(log_file: Path, message: str):
    """記錄訊息到日誌檔案"""
    try:
        with open(log_file, "a", encoding="utf-8") as f:
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            f.write(f"[{timestamp}] {message}\n")
    except Exception:
        # 日誌失敗不應該影響 Hook 執行
        pass


def detect_bash_edit_patterns(command: str) -> bool:
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


def print_warning_message(command: str):
    """
    輸出警告訊息到 stderr

    Args:
        command: 檢測到的 Bash 命令
    """
    warning = f"""[Bash Edit Guard] 警告: 偵測到使用 Bash 進行檔案編輯操作

檢測到的命令:
  {command[:100]}{'...' if len(command) > 100 else ''}

建議: 請使用 Edit Tool 替代 Bash sed/awk，以獲得更好的權限控制和變更追蹤

詳情: 參考 .claude/agent-collaboration.md 的「工具使用強制規範」
"""
    print(warning, file=sys.stderr)


def main():
    """主入口點"""
    log_file = setup_logging()

    try:
        # 讀取 JSON 輸入
        input_data = json.load(sys.stdin)
        tool_name = input_data.get("tool_name", "")
        tool_input = input_data.get("tool_input", {})

        # 檢查是否為 Bash 工具
        if tool_name != "Bash":
            # 非 Bash 工具：直接允許
            log_message(log_file, f"跳過: 工具類型 {tool_name} 不是 Bash")
            sys.exit(0)

        # 取得命令內容
        command = tool_input.get("command", "")

        # 檢測編輯模式
        if not detect_bash_edit_patterns(command):
            # 不符合編輯模式：直接允許
            log_message(log_file, f"允許: 正常 Bash 命令")
            sys.exit(0)

        # 偵測到編輯模式：輸出警告並記錄
        log_message(log_file, f"警告: 偵測到編輯操作 - {command[:100]}")
        print_warning_message(command)

        # 輸出符合官方規範的 JSON 格式（允許繼續執行）
        result = {
            "hookSpecificOutput": {
                "hookEventName": "PreToolUse",
                "permissionDecision": "allow",
                "permissionDecisionReason": "Bash 編輯操作警告已發送，允許執行"
            }
        }
        print(json.dumps(result, ensure_ascii=False))

        # Exit code 0 = 允許並記錄警告
        sys.exit(0)

    except json.JSONDecodeError as e:
        log_message(log_file, f"JSON 解析錯誤: {e}")
        # JSON 解析失敗：直接允許執行，不阻塊
        sys.exit(0)
    except Exception as e:
        log_message(log_file, f"執行錯誤: {e}")
        # 任何錯誤都不阻塊（非阻塞原則）
        sys.exit(0)


if __name__ == "__main__":
    main()
