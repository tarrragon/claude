#!/usr/bin/env -S uv run --quiet --script
# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///

"""
CLI 失敗提醒 Hook - PostToolUse Hook

功能: 偵測 Bash 工具非零退出碼，提醒先查 --help 再歸因。
防護 PC-005 錯誤模式：CLI 失敗時基於假設歸因。

觸發時機: Bash 工具執行後
檢測邏輯:
  1. 驗證 tool_name == "Bash"
  2. 檢查 tool_response 是否包含 stderr（非零退出指標）
  3. 排除已由其他 Hook 處理的情境（測試失敗、編譯錯誤）
  4. 排除預期會有 stderr 的命令（grep 無結果等）
  5. 若偵測到 CLI 失敗，輸出 PC-005 調查步驟提醒

行為: 不阻擋（exit 0），僅在 additionalContext 輸出提醒訊息

HOOK_METADATA (JSON):
{
  "event_type": "PostToolUse",
  "matcher": "Bash",
  "timeout": 5000,
  "description": "CLI 失敗時提醒查 --help - PC-005 防護",
  "dependencies": [],
  "version": "1.0.0"
}
"""

import sys
import json
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from hook_utils import setup_hook_logging, run_hook_safely
from lib.hook_messages import WorkflowMessages

# ============================================================================
# 常數定義
# ============================================================================

EXIT_SUCCESS = 0

# 已由其他 Hook 處理的命令模式（避免重複提醒）
# - pre-fix-evaluation-hook 處理測試和程式碼品質命令
# - skill-cli-error-feedback-hook 處理 ticket/skill CLI 命令
HANDLED_BY_OTHER_HOOKS = [
    "flutter test",
    "dart test",
    "dart analyze",
    "go test",
    "go vet",
    "pytest",
    "uv run pytest",
    "ticket ",
    "skill ",
    "uv run ticket",
]

# 預期可能有 stderr 輸出但非真正失敗的命令
EXPECTED_STDERR_COMMANDS = [
    "grep",
    "rg",
    "find",
    "which",
    "command -v",
    "type ",
    "hash ",
]

# git 命令中預期的非錯誤 stderr（git 常把資訊輸出到 stderr）
GIT_INFO_STDERR_PATTERNS = [
    "Already up to date",
    "Already on",
    "Switched to",
    "Your branch is",
    "nothing to commit",
    "Everything up-to-date",
]

# PostToolUse Hook 的標準輸出結構
DEFAULT_OUTPUT = {
    "hookSpecificOutput": {
        "hookEventName": "PostToolUse"
    }
}


# ============================================================================
# 主要邏輯
# ============================================================================

def is_handled_by_other_hooks(command: str) -> bool:
    """判斷命令是否已由其他 Hook 處理（如 pre-fix-evaluation-hook）"""
    for pattern in HANDLED_BY_OTHER_HOOKS:
        if pattern in command:
            return True
    return False


def is_expected_stderr(command: str, stderr: str) -> bool:
    """判斷 stderr 是否為預期輸出（非真正的 CLI 失敗）"""
    # 預期有 stderr 的命令類型
    for pattern in EXPECTED_STDERR_COMMANDS:
        if command.strip().startswith(pattern):
            return True

    # git 命令的資訊性 stderr
    if "git " in command:
        for info_pattern in GIT_INFO_STDERR_PATTERNS:
            if info_pattern in stderr:
                return True

    return False


def main() -> int:
    """
    主入口點

    流程:
    1. 讀取 stdin JSON（PostToolUse 格式）
    2. 驗證工具類型是否為 Bash
    3. 檢查是否有 stderr（非零退出指標）
    4. 排除已處理和預期情境
    5. 若為 CLI 失敗，輸出 PC-005 調查步驟提醒
    """
    logger = setup_hook_logging("cli-failure-help-reminder")

    try:
        input_data = json.load(sys.stdin)
    except json.JSONDecodeError as e:
        logger.error("JSON 解析錯誤: %s", e)
        print(json.dumps(DEFAULT_OUTPUT, ensure_ascii=False))
        return EXIT_SUCCESS

    # 驗證工具類型
    tool_name = input_data.get("tool_name", "")
    if tool_name != "Bash":
        logger.debug("跳過: 工具類型為 %s，非 Bash", tool_name)
        print(json.dumps(DEFAULT_OUTPUT, ensure_ascii=False))
        return EXIT_SUCCESS

    # 取得命令和回應
    tool_input = input_data.get("tool_input") or {}
    command = tool_input.get("command", "")

    tool_response = input_data.get("tool_response") or {}

    # 支援 tool_response 為字串或字典
    if isinstance(tool_response, str):
        stderr = ""
    else:
        stderr = tool_response.get("stderr", "")

    # 無 stderr 表示命令成功，跳過
    if not stderr or not stderr.strip():
        logger.debug("無 stderr，命令成功，跳過")
        print(json.dumps(DEFAULT_OUTPUT, ensure_ascii=False))
        return EXIT_SUCCESS

    # 排除已由其他 Hook 處理的命令
    if is_handled_by_other_hooks(command):
        logger.debug("已由其他 Hook 處理: %s", command[:80])
        print(json.dumps(DEFAULT_OUTPUT, ensure_ascii=False))
        return EXIT_SUCCESS

    # 排除預期的 stderr
    if is_expected_stderr(command, stderr):
        logger.debug("預期的 stderr，跳過: %s", command[:80])
        print(json.dumps(DEFAULT_OUTPUT, ensure_ascii=False))
        return EXIT_SUCCESS

    # 偵測到 CLI 失敗，輸出 PC-005 提醒
    logger.info("偵測到 CLI 失敗，輸出 PC-005 調查步驟提醒")
    logger.info("失敗命令: %s", command[:120])
    logger.info("stderr 摘要: %s", stderr[:200])

    output = {
        "hookSpecificOutput": {
            "hookEventName": "PostToolUse",
            "additionalContext": WorkflowMessages.CLI_FAILURE_HELP_REMINDER
        }
    }

    print(json.dumps(output, ensure_ascii=False, indent=2))
    return EXIT_SUCCESS


if __name__ == "__main__":
    exit_code = run_hook_safely(main, "cli-failure-help-reminder")
    sys.exit(exit_code)
