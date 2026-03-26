#!/usr/bin/env -S uv run --quiet --script
# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///

"""
SKILL CLI 錯誤自動偵測與引導不足回饋機制 - PostToolUse Hook

功能: 當 Bash 工具執行 ticket/skill CLI 命令失敗時，自動偵測錯誤類型
     （參數不存在、格式錯誤、未知子命令）並提示 SKILL 引導可能不足。

觸發時機: Bash 工具執行後，命令包含 ticket 或 skill CLI
檢測邏輯:
  1. 驗證 tool_name == "Bash"
  2. 檢查命令是否為 ticket/skill 相關命令
  3. 檢查是否有非零退出碼（錯誤發生）
  4. 分析 stderr/stdout 中的錯誤類型：
     - "unrecognized arguments" → 參數不存在
     - "error: argument" → 參數格式錯誤
     - "invalid choice" → 未知子命令
  5. 排除業務邏輯錯誤（如 Ticket 不存在、無法認領等）
  6. 若為 SKILL 引導缺陷，輸出回饋訊息

行為: 不阻擋（exit 0），僅在 additionalContext 輸出回饋訊息

設計原則:
- 關注於「SKILL 引導不足」的信號，而非一般 CLI 失敗
- 幫助改進 SKILL 文檔的完整性
- 記錄所有 SKILL CLI 錯誤，便於後續分析和改善

HOOK_METADATA (JSON):
{
  "event_type": "PostToolUse",
  "matcher": "Bash",
  "timeout": 5000,
  "description": "SKILL CLI 錯誤自動偵測與引導不足回饋",
  "dependencies": [],
  "version": "1.0.0"
}
"""

import sys
import json
import re
from pathlib import Path
from typing import Dict, Any, Optional

sys.path.insert(0, str(Path(__file__).parent))

from hook_utils import setup_hook_logging, run_hook_safely

# ============================================================================
# 常數定義
# ============================================================================

EXIT_SUCCESS = 0

# 需要偵測的 CLI 命令前綴
SKILL_CLI_COMMANDS = [
    "ticket",
    "skill",
    "/ticket",
    "/skill",
]

# SKILL 引導缺陷的錯誤模式
# 格式: (pattern, error_type)
SKILL_ERROR_PATTERNS = [
    # 參數不存在
    (r"unrecognized arguments?:", "參數不存在"),
    (r"unrecognized sub-command", "參數不存在"),
    (r"argument .+ not recognized", "參數不存在"),

    # 參數格式錯誤
    (r"error: argument .+: ", "參數格式錯誤"),
    (r"invalid argument", "參數格式錯誤"),
    (r"argument .+ expected", "參數格式錯誤"),

    # 未知子命令
    (r"invalid choice: '([^']+)'", "未知子命令"),
    (r"unknown command '([^']+)'", "未知子命令"),
    (r"no such command", "未知子命令"),
]

# 排除的錯誤模式（業務邏輯錯誤，不是 SKILL 引導問題）
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

# PostToolUse Hook 的標準輸出結構
DEFAULT_OUTPUT = {
    "hookSpecificOutput": {
        "hookEventName": "PostToolUse"
    }
}

# 訊息範本
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


# ============================================================================
# 輔助函式
# ============================================================================

def is_skill_cli_command(command: str) -> bool:
    """判斷命令是否為 ticket/skill CLI 命令（首 token 比對）

    處理 && 鏈式命令、管道命令、子 shell 等情況，避免子字串誤判
    （例如 echo "ticket" 或 grep ticket 不應被認為是 ticket CLI 命令）
    """
    # 將命令分段：處理 && 鏈式、管道、子 shell 等
    for segment in re.split(r'[|&;]+', command):
        segment = segment.strip().lstrip('(').strip()
        if not segment:
            continue
        # 取第一個 token（空格分隔）
        tokens = segment.split()
        if tokens:
            first_token = tokens[0]
            # 移除斜線前綴（/ticket → ticket）
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
    """
    偵測 SKILL 引導缺陷錯誤類型

    Args:
        stderr: 標準錯誤輸出
        stdout: 標準輸出

    Returns:
        錯誤類型字串，若無匹配返回 None
    """
    combined = stderr + " " + stdout

    for pattern, error_type in SKILL_ERROR_PATTERNS:
        if re.search(pattern, combined, re.IGNORECASE):
            return error_type

    return None


def extract_command_summary(command: str, stderr: str) -> tuple[str, str]:
    """
    提取命令摘要和基本命令

    Args:
        command: 完整命令行
        stderr: 錯誤訊息

    Returns:
        (command_summary, command_base) 元組
    """
    # 簡化命令（最多 80 字符）
    command_summary = command[:80] if len(command) > 80 else command

    # 提取基本命令（第一個空格前）
    parts = command.strip().split()
    command_base = parts[0] if parts else command

    # 移除斜線前綴（/ticket → ticket）
    if command_base.startswith("/"):
        command_base = command_base[1:]

    return command_summary, command_base


def main() -> int:
    """
    主入口點

    流程:
    1. 讀取 stdin JSON（PostToolUse 格式）
    2. 驗證工具類型是否為 Bash
    3. 檢查命令是否為 ticket/skill CLI 命令
    4. 分析錯誤類型，排除業務邏輯錯誤
    5. 若為 SKILL 引導缺陷，輸出回饋訊息
    """
    logger = setup_hook_logging("skill-cli-error-feedback")

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

    # 檢查是否為 SKILL CLI 命令
    if not is_skill_cli_command(command):
        logger.debug("跳過: 非 ticket/skill CLI 命令")
        print(json.dumps(DEFAULT_OUTPUT, ensure_ascii=False))
        return EXIT_SUCCESS

    # 檢查是否有錯誤
    tool_response = input_data.get("tool_response") or {}

    # 支援 tool_response 為字串或字典
    if isinstance(tool_response, str):
        stderr = ""
        stdout = tool_response
    else:
        stderr = tool_response.get("stderr", "")
        stdout = tool_response.get("stdout", "")

    # 檢查退出碼：exit_code=0 表示命令成功，跳過
    if isinstance(tool_response, dict):
        exit_code = tool_response.get("exit_code")
        if exit_code is not None and exit_code == 0:
            logger.debug("命令成功（exit_code=0），跳過")
            print(json.dumps(DEFAULT_OUTPUT, ensure_ascii=False))
            return EXIT_SUCCESS

    # 若無錯誤信息，命令可能成功，跳過
    if not stderr and not stdout:
        logger.debug("無錯誤信息，跳過")
        print(json.dumps(DEFAULT_OUTPUT, ensure_ascii=False))
        return EXIT_SUCCESS

    # 排除業務邏輯錯誤（Ticket 不存在、無法認領等）
    if is_excluded_error(stderr, stdout):
        logger.debug("業務邏輯錯誤，跳過: %s", command[:80])
        print(json.dumps(DEFAULT_OUTPUT, ensure_ascii=False))
        return EXIT_SUCCESS

    # 偵測 SKILL 引導缺陷錯誤
    error_type = detect_skill_error_type(stderr, stdout)

    if not error_type:
        logger.debug("未偵測到 SKILL 引導缺陷錯誤")
        print(json.dumps(DEFAULT_OUTPUT, ensure_ascii=False))
        return EXIT_SUCCESS

    # 檢測到 SKILL 引導缺陷，輸出回饋訊息
    logger.info("偵測到 SKILL 引導缺陷錯誤: %s", error_type)
    logger.info("失敗命令: %s", command[:120])
    logger.info("stderr 摘要: %s", stderr[:200])

    command_summary, command_base = extract_command_summary(command, stderr)

    feedback_message = SKILL_CLI_ERROR_FEEDBACK_TEMPLATE.format(
        error_type=error_type,
        command_summary=command_summary,
        command_base=command_base,
    )

    output = {
        "hookSpecificOutput": {
            "hookEventName": "PostToolUse",
            "additionalContext": feedback_message
        }
    }

    print(json.dumps(output, ensure_ascii=False, indent=2))
    return EXIT_SUCCESS


if __name__ == "__main__":
    exit_code = run_hook_safely(main, "skill-cli-error-feedback")
    sys.exit(exit_code)
