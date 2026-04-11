#!/usr/bin/env -S uv run --quiet --script
# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///

"""
CLI 錯誤回饋合併 Hook - PostToolUse Hook

合併自:
- cli-failure-help-reminder-hook.py（一般 CLI 命令失敗提醒，PC-005 防護）
- skill-cli-error-feedback-hook.py（ticket/skill CLI 錯誤偵測，SKILL 引導不足回饋）

觸發時機: Bash 工具執行後
執行順序:
  1. check_skill_cli_error — 優先處理 ticket/skill CLI 錯誤（更 specific）
  2. check_general_cli_failure — 處理一般 CLI 失敗（若 skill CLI 已處理則跳過）

行為: 不阻擋（exit 0），僅在 additionalContext 輸出提醒訊息

HOOK_METADATA (JSON):
{
  "event_type": "PostToolUse",
  "matcher": "Bash",
  "timeout": 5000,
  "description": "CLI 錯誤偵測與回饋（合併 cli-failure-help-reminder + skill-cli-error-feedback）",
  "dependencies": [],
  "version": "1.0.0"
}
"""

import sys
import json
import re
from pathlib import Path
from typing import Optional, Dict, Any, Tuple

sys.path.insert(0, str(Path(__file__).parent))

from hook_utils import setup_hook_logging, run_hook_safely, read_json_from_stdin, is_subagent_environment
from lib.hook_messages import WorkflowMessages

# ============================================================================
# 常數定義
# ============================================================================

EXIT_SUCCESS = 0

# PostToolUse Hook 的標準輸出結構
DEFAULT_OUTPUT = {
    "hookSpecificOutput": {
        "hookEventName": "PostToolUse"
    }
}

# --- Skill CLI Error 常數（來自 skill-cli-error-feedback-hook） ---

# 需要偵測的 CLI 命令前綴
SKILL_CLI_COMMANDS = [
    "ticket",
    "skill",
    "/ticket",
    "/skill",
]

# SKILL 引導缺陷的錯誤模式
SKILL_ERROR_PATTERNS = [
    (r"unrecognized arguments?:", "參數不存在"),
    (r"unrecognized sub-command", "參數不存在"),
    (r"argument .+ not recognized", "參數不存在"),
    (r"error: argument .+: ", "參數格式錯誤"),
    (r"invalid argument", "參數格式錯誤"),
    (r"argument .+ expected", "參數格式錯誤"),
    (r"invalid choice: '([^']+)'", "未知子命令"),
    (r"unknown command '([^']+)'", "未知子命令"),
    (r"no such command", "未知子命令"),
]

# 排除的錯誤模式（業務邏輯錯誤）
EXCLUDED_ERROR_PATTERNS = [
    r"ticket not found",
    r"no pending ticket",
    r"ticket already .+",
    r"cannot .+ completed ticket",
    r"not in progress",
    r"blocked ticket",
    r"insufficient permission",
    r"version mismatch",
    r"no such file or directory",
    r"permission denied",
    r"json decode error",
    r"invalid json",
]

SKILL_CLI_ERROR_FEEDBACK_TEMPLATE = """
============================================================
[SKILL 引導品質回饋] CLI 錯誤偵測
============================================================

檢測到 SKILL/Ticket CLI 命令使用了不存在或格式錯誤的參數。

錯誤類型：{error_type}
失敗命令：{command_summary}

可能原因：
  SKILL 引導不足，使用者嘗試了 SKILL.md 中未明確說明的用法

建議動作：
  1. 確認 SKILL.md 是否有此使用情境的說明
  2. 查閱完整語法：執行 `{command_base} --help`
  3. 若多人遇到同樣困惑，建立改善 Ticket
     `/ticket create --type ADJ --title "[ADJ] 補充 SKILL.md 文檔"`

詳見: .claude/skills/ticket/SKILL.md

============================================================
"""

# --- General CLI Failure 常數（來自 cli-failure-help-reminder-hook） ---

# 已由其他 Hook 處理的命令模式（避免重複提醒）
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

# git 命令中預期的非錯誤 stderr
GIT_INFO_STDERR_PATTERNS = [
    "Already up to date",
    "Already on",
    "Switched to",
    "Your branch is",
    "nothing to commit",
    "Everything up-to-date",
]


# ============================================================================
# Skill CLI Error 子邏輯（來自 skill-cli-error-feedback-hook）
# ============================================================================

def is_skill_cli_command(command: str) -> bool:
    """判斷命令是否為 ticket/skill CLI 命令（首 token 比對）"""
    for segment in re.split(r'[|&;]+', command):
        segment = segment.strip().lstrip('(').strip()
        if not segment:
            continue
        tokens = segment.split()
        if tokens:
            first_token = tokens[0]
            if first_token.startswith("/"):
                first_token = first_token[1:]
            if first_token in SKILL_CLI_COMMANDS:
                return True
    return False


def is_excluded_error(stderr: str, stdout: str) -> bool:
    """判斷錯誤是否為排除類型（業務邏輯錯誤）"""
    combined = (stderr + " " + stdout).lower()
    for pattern in EXCLUDED_ERROR_PATTERNS:
        if re.search(pattern, combined, re.IGNORECASE):
            return True
    return False


def detect_skill_error_type(stderr: str, stdout: str) -> Optional[str]:
    """偵測 SKILL 引導缺陷錯誤類型"""
    combined = stderr + " " + stdout
    for pattern, error_type in SKILL_ERROR_PATTERNS:
        if re.search(pattern, combined, re.IGNORECASE):
            return error_type
    return None


def extract_command_summary(command: str) -> Tuple[str, str]:
    """提取命令摘要和基本命令"""
    command_summary = command[:80] if len(command) > 80 else command
    parts = command.strip().split()
    command_base = parts[0] if parts else command
    if command_base.startswith("/"):
        command_base = command_base[1:]
    return command_summary, command_base


def check_skill_cli_error(input_data: Dict[str, Any], logger) -> Optional[str]:
    """
    檢查 skill/ticket CLI 錯誤（來自 skill-cli-error-feedback-hook）

    Returns:
        additionalContext 字串，或 None 表示未觸發
    """
    tool_input = input_data.get("tool_input") or {}
    command = tool_input.get("command", "")

    if not is_skill_cli_command(command):
        logger.debug("skill-cli: 跳過，非 ticket/skill CLI 命令")
        return None

    tool_response = input_data.get("tool_response") or {}
    if isinstance(tool_response, str):
        stderr = ""
        stdout = tool_response
    else:
        stderr = tool_response.get("stderr", "")
        stdout = tool_response.get("stdout", "")

    # exit_code=0 表示命令成功
    if isinstance(tool_response, dict):
        exit_code = tool_response.get("exit_code")
        if exit_code is not None and exit_code == 0:
            logger.debug("skill-cli: 命令成功（exit_code=0），跳過")
            return None

    if not stderr and not stdout:
        logger.debug("skill-cli: 無錯誤資訊，跳過")
        return None

    if is_excluded_error(stderr, stdout):
        logger.debug("skill-cli: 業務邏輯錯誤，跳過: %s", command[:80])
        return None

    error_type = detect_skill_error_type(stderr, stdout)
    if not error_type:
        logger.debug("skill-cli: 未偵測到 SKILL 引導缺陷錯誤")
        return None

    logger.info("skill-cli: 偵測到 SKILL 引導缺陷錯誤: %s", error_type)
    logger.info("skill-cli: 失敗命令: %s", command[:120])

    command_summary, command_base = extract_command_summary(command)
    return SKILL_CLI_ERROR_FEEDBACK_TEMPLATE.format(
        error_type=error_type,
        command_summary=command_summary,
        command_base=command_base,
    )


# ============================================================================
# General CLI Failure 子邏輯（來自 cli-failure-help-reminder-hook）
# ============================================================================

def is_handled_by_other_hooks(command: str) -> bool:
    """判斷命令是否已由其他 Hook 處理"""
    for pattern in HANDLED_BY_OTHER_HOOKS:
        if pattern in command:
            return True
    return False


def is_expected_stderr(command: str, stderr: str) -> bool:
    """判斷 stderr 是否為預期輸出（非真正的 CLI 失敗）"""
    for pattern in EXPECTED_STDERR_COMMANDS:
        if command.strip().startswith(pattern):
            return True
    if "git " in command:
        for info_pattern in GIT_INFO_STDERR_PATTERNS:
            if info_pattern in stderr:
                return True
    return False


def check_general_cli_failure(input_data: Dict[str, Any], logger) -> Optional[str]:
    """
    檢查一般 CLI 失敗（來自 cli-failure-help-reminder-hook）

    Returns:
        additionalContext 字串，或 None 表示未觸發
    """
    tool_input = input_data.get("tool_input") or {}
    command = tool_input.get("command", "")

    tool_response = input_data.get("tool_response") or {}
    if isinstance(tool_response, str):
        stderr = ""
    else:
        stderr = tool_response.get("stderr", "")

    if not stderr or not stderr.strip():
        logger.debug("general-cli: 無 stderr，命令成功，跳過")
        return None

    if is_handled_by_other_hooks(command):
        logger.debug("general-cli: 已由其他 Hook 處理: %s", command[:80])
        return None

    if is_expected_stderr(command, stderr):
        logger.debug("general-cli: 預期的 stderr，跳過: %s", command[:80])
        return None

    logger.info("general-cli: 偵測到 CLI 失敗，輸出 PC-005 調查步驟提醒")
    logger.info("general-cli: 失敗命令: %s", command[:120])

    return WorkflowMessages.CLI_FAILURE_HELP_REMINDER


# ============================================================================
# 主要邏輯
# ============================================================================

def main() -> int:
    """
    主入口點

    流程:
    1. 讀取 stdin JSON（PostToolUse 格式）
    2. 驗證工具類型是否為 Bash
    3. 優先檢查 skill CLI 錯誤（更 specific）
    4. 若未觸發，檢查一般 CLI 失敗
    5. 輸出結果
    """
    logger = setup_hook_logging("cli-error-feedback-hook")

    try:
        input_data = read_json_from_stdin(logger)
    except json.JSONDecodeError as e:
        logger.error("JSON 解析錯誤: %s", e)
        print(json.dumps(DEFAULT_OUTPUT, ensure_ascii=False))
        return EXIT_SUCCESS

    if not input_data:
        print(json.dumps(DEFAULT_OUTPUT, ensure_ascii=False))
        return EXIT_SUCCESS

    # subagent 環境跳過（CLI 錯誤回饋給 PM 看，代理人不需要）
    if is_subagent_environment(input_data):
        return EXIT_SUCCESS

    # 驗證工具類型
    tool_name = input_data.get("tool_name", "")
    if tool_name != "Bash":
        logger.debug("跳過: 工具類型為 %s，非 Bash", tool_name)
        print(json.dumps(DEFAULT_OUTPUT, ensure_ascii=False))
        return EXIT_SUCCESS

    additional_context = None

    # 子邏輯 1: Skill CLI 錯誤（優先，更 specific）
    try:
        additional_context = check_skill_cli_error(input_data, logger)
    except Exception as e:
        logger.error("check_skill_cli_error 例外: %s", e, exc_info=True)

    # 子邏輯 2: 一般 CLI 失敗（若 skill CLI 未觸發）
    if additional_context is None:
        try:
            additional_context = check_general_cli_failure(input_data, logger)
        except Exception as e:
            logger.error("check_general_cli_failure 例外: %s", e, exc_info=True)

    # 輸出結果
    if additional_context:
        output = {
            "hookSpecificOutput": {
                "hookEventName": "PostToolUse",
                "additionalContext": additional_context
            }
        }
    else:
        output = DEFAULT_OUTPUT

    print(json.dumps(output, ensure_ascii=False, indent=2))
    return EXIT_SUCCESS


if __name__ == "__main__":
    exit_code = run_hook_safely(main, "cli-error-feedback-hook")
    sys.exit(exit_code)
