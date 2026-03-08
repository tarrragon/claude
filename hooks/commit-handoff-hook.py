#!/usr/bin/env -S uv run --quiet --script
# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///

"""
Commit Handoff Hook - PostToolUse Hook

功能: 偵測 git commit 成功後，輸出 AskUserQuestion 場景 11 提醒。
每次 commit 都是 context 切換的決策點。

觸發時機: Bash 工具執行後
檢測邏輯:
  1. 驗證 tool_name == "Bash"
  2. 檢查 command 是否包含 git commit（排除 --amend 等變體）
  3. 檢查 stdout 是否包含 commit 成功標記
  4. 若偵測成功，輸出 AskUserQuestionMessages.COMMIT_HANDOFF_REMINDER

行為: 不阻擋（exit 0），僅在 additionalContext 輸出提醒訊息
"""

import sys
import json
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from hook_utils import setup_hook_logging, run_hook_safely
from lib.hook_messages import AskUserQuestionMessages, CoreMessages
from lib.ask_user_question_reminders import AskUserQuestionReminders

# ============================================================================
# 常數定義
# ============================================================================

EXIT_SUCCESS = 0

# 排除的命令模式（非 commit 操作）
EXCLUDED_COMMAND_PATTERNS = [
    "git log",
    "git show",
    "git diff",
    "git status",
    "git commit --amend",
]

# 自動跳過 #16 的 commit 類型（conventional commit 前綴）
SKIP_SCENE16_COMMIT_PREFIXES = frozenset({
    "docs",
    "chore",
    "style",
    "revert",
    "test",
    "ci",
    "build",
})

# commit 成功標記
COMMIT_SUCCESS_MARKERS = [
    "files changed",
    "file changed",
    "insertions(+)",
    "deletions(-)",
    "create mode",
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

def is_git_commit_command(command: str) -> bool:
    """
    判斷是否為 git commit 命令

    Args:
        command: Bash 命令字串

    Returns:
        bool - 是否為 git commit 操作（排除 --amend 等特殊情況）
    """
    if "git commit" not in command:
        return False

    # 排除不需要提醒的 commit 變體
    for excluded in EXCLUDED_COMMAND_PATTERNS:
        if excluded in command:
            return False

    return True


def is_commit_successful(stdout: str) -> bool:
    """
    判斷 commit 是否成功

    Args:
        stdout: Bash 命令的標準輸出

    Returns:
        bool - 是否偵測到 commit 成功標記
    """
    for marker in COMMIT_SUCCESS_MARKERS:
        if marker in stdout:
            return True
    return False


def extract_commit_type(command: str) -> str:
    """
    從 git commit 命令中提取 conventional commit 類型

    支援格式：
    - git commit -m "type: ..."
    - git commit -m "type(scope): ..."
    - git commit -m "$(cat <<'EOF'\ntype: ...\nEOF\n)"

    Args:
        command: Bash 命令字串

    Returns:
        str - commit 類型（如 "docs", "chore"），無法提取時回傳 ""
    """
    import re
    # 匹配 -m "type: ..." 或 -m "type(scope): ..."
    match = re.search(r'-m\s+["\']([a-z]+)(?:\([^)]*\))?:', command)
    if match:
        return match.group(1).lower()
    # 匹配 heredoc 中的類型（COMMIT_MSG=... 或直接在 EOF 區塊）
    match = re.search(r'\n\s*([a-z]+)(?:\([^)]*\))?:', command)
    if match:
        return match.group(1).lower()
    return ""


def main() -> int:
    """
    主入口點

    流程:
    1. 讀取 stdin JSON（PostToolUse 格式）
    2. 驗證工具類型是否為 Bash
    3. 檢查命令是否為 git commit
    4. 檢查輸出是否包含成功標記
    5. 若全部符合，輸出 AskUserQuestion 提醒
    """
    logger = setup_hook_logging("commit-handoff")

    try:
        # 讀取 PostToolUse JSON
        input_data = json.load(sys.stdin)
    except json.JSONDecodeError as e:
        logger.error("JSON 解析錯誤: %s", e)
        # JSON 解析失敗：輸出預設允許訊息
        print(json.dumps(DEFAULT_OUTPUT, ensure_ascii=False))
        return EXIT_SUCCESS

    # 驗證工具類型
    tool_name = input_data.get("tool_name", "")
    if tool_name != "Bash":
        logger.debug("跳過: 工具類型為 %s，非 Bash", tool_name)
        print(json.dumps(DEFAULT_OUTPUT, ensure_ascii=False))
        return EXIT_SUCCESS

    # 取得命令和輸出
    tool_input = input_data.get("tool_input", {})
    command = tool_input.get("command", "")

    tool_response = input_data.get("tool_response", {})
    stdout = tool_response.get("stdout", "")

    # 檢測 git commit 成功
    if is_git_commit_command(command) and is_commit_successful(stdout):
        commit_type = extract_commit_type(command)
        should_skip_scene16 = commit_type in SKIP_SCENE16_COMMIT_PREFIXES

        if should_skip_scene16:
            logger.info(
                "偵測到 git commit 成功（type=%s），自動跳過場景 #16，輸出 Skip16 提醒",
                commit_type,
            )
            reminder = AskUserQuestionMessages.COMMIT_HANDOFF_SKIP16_REMINDER
        else:
            logger.info(
                "偵測到 git commit 成功（type=%s），輸出含 #16 的 AskUserQuestion 提醒",
                commit_type or "unknown",
            )
            reminder = AskUserQuestionMessages.COMMIT_HANDOFF_REMINDER

        output = {
            "hookSpecificOutput": {
                "hookEventName": "PostToolUse",
                "additionalContext": reminder
            }
        }
    else:
        # 不符合條件：正常流程
        logger.debug("未偵測到 commit 成功或不符合條件")
        output = DEFAULT_OUTPUT

    print(json.dumps(output, ensure_ascii=False, indent=2))
    return EXIT_SUCCESS


if __name__ == "__main__":
    exit_code = run_hook_safely(main, "commit-handoff")
    sys.exit(exit_code)
