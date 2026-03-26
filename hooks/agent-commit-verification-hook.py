#!/usr/bin/env -S uv run --quiet --script
# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///

"""
Agent Commit Verification Hook - PostToolUse (Agent)

功能: Agent 完成工作後，檢查是否有未 commit 的變更。
若偵測到未 commit 的修改，輸出警告提醒 PM 確認。

觸發時機: Agent 工具完成後 (PostToolUse, matcher: Agent)
行為: 不阻擋（exit 0），僅在 additionalContext 輸出警告

來源: PC-024 — 代理人完成實作但跳過 git commit，變更未持久化
Ticket: 0.2.0-W3-022
"""

import json
import logging
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from hook_utils import (
    setup_hook_logging,
    read_json_from_stdin,
    extract_tool_input,
    is_subagent_environment,
    get_project_root,
)

# ============================================================================
# 常數定義
# ============================================================================

HOOK_NAME = "agent-commit-verification-hook"
EXIT_SUCCESS = 0

# 預設輸出格式（靜默通過）
DEFAULT_OUTPUT = {
    "hookSpecificOutput": {
        "hookEventName": "PostToolUse"
    }
}

# Git 命令超時（秒）
GIT_STATUS_TIMEOUT = 5

# 顯示的最大未 commit 檔案數
MAX_FILES_DISPLAY = 15

# 排除的路徑前綴（不視為需要 commit 的變更）
EXCLUDED_PATH_PREFIXES = (
    ".claude/",
    "docs/",
)

# 訊息常數
MSG_SEPARATOR = "============================================================"
MSG_TITLE = "[Agent Commit 驗證警告]"
MSG_UNCOMMITTED_DETECTED = "偵測到代理人完成工作後有未 commit 的變更"
MSG_AGENT_DESCRIPTION = "代理人描述"
MSG_UNCOMMITTED_FILES = "未 commit 的檔案"
MSG_MORE_FILES = "... 還有 {} 個檔案"
MSG_SUGGESTED_ACTION = "建議動作"
MSG_SUGGESTION_REVIEW = "1. 確認變更內容是否符合預期"
MSG_SUGGESTION_COMMIT = '2. 執行 commit：git add <files> && git commit -m "feat: <description>"'
MSG_SUGGESTION_DISCARD = "3. 若不需要：git checkout -- <files>"


# ============================================================================
# 核心邏輯
# ============================================================================


def get_uncommitted_files(project_root: str, logger: logging.Logger) -> list[str]:
    """取得未 commit 的檔案清單（排除豁免路徑）

    Args:
        project_root: 專案根目錄路徑
        logger: Logger 實例

    Returns:
        list[str]: 未 commit 的檔案路徑清單
    """
    try:
        result = subprocess.run(
            ["git", "status", "--porcelain"],
            capture_output=True,
            text=True,
            timeout=GIT_STATUS_TIMEOUT,
            cwd=project_root,
        )
        if result.returncode != 0:
            logger.warning("git status failed: %s", result.stderr.strip())
            return []

        files = []
        for line in result.stdout.strip().splitlines():
            if len(line) < 4:
                continue
            # git status --porcelain 格式: XY filename
            file_path = line[3:].strip()
            # 排除豁免路徑
            if any(file_path.startswith(prefix) for prefix in EXCLUDED_PATH_PREFIXES):
                continue
            files.append(file_path)
        return files

    except subprocess.TimeoutExpired:
        logger.warning("git status timeout")
        return []
    except FileNotFoundError:
        logger.warning("git not found")
        return []


def build_warning_message(
    agent_description: str,
    uncommitted_files: list[str],
) -> str:
    """建構警告訊息

    Args:
        agent_description: 代理人的描述
        uncommitted_files: 未 commit 的檔案清單

    Returns:
        str: 格式化的警告訊息
    """
    lines = [
        MSG_SEPARATOR,
        MSG_TITLE,
        MSG_SEPARATOR,
        "",
        MSG_UNCOMMITTED_DETECTED,
        "",
        f"{MSG_AGENT_DESCRIPTION}: {agent_description}",
        "",
        f"{MSG_UNCOMMITTED_FILES} ({len(uncommitted_files)} 個):",
    ]

    display_count = min(len(uncommitted_files), MAX_FILES_DISPLAY)
    for file_path in uncommitted_files[:display_count]:
        lines.append(f"  - {file_path}")

    remaining = len(uncommitted_files) - display_count
    if remaining > 0:
        lines.append(f"  {MSG_MORE_FILES.format(remaining)}")

    lines.extend([
        "",
        f"{MSG_SUGGESTED_ACTION}:",
        f"  {MSG_SUGGESTION_REVIEW}",
        f"  {MSG_SUGGESTION_COMMIT}",
        f"  {MSG_SUGGESTION_DISCARD}",
        MSG_SEPARATOR,
    ])

    return "\n".join(lines)


def main() -> None:
    """主函式"""
    logger = setup_hook_logging(HOOK_NAME)

    input_data = read_json_from_stdin(logger)

    # 子代理人環境不觸發（避免巢狀警告）
    if is_subagent_environment(input_data):
        logger.debug("subagent environment, skip")
        print(json.dumps(DEFAULT_OUTPUT))
        sys.exit(EXIT_SUCCESS)
    if not input_data:
        logger.debug("no input data")
        print(json.dumps(DEFAULT_OUTPUT))
        sys.exit(EXIT_SUCCESS)

    tool_input = extract_tool_input(input_data, logger)

    # 取得代理人描述
    agent_description = tool_input.get("description", "unknown")

    # 取得專案根目錄
    project_root = get_project_root()

    # 檢查未 commit 的檔案
    uncommitted_files = get_uncommitted_files(str(project_root), logger)

    if not uncommitted_files:
        logger.debug("no uncommitted files after agent completed")
        print(json.dumps(DEFAULT_OUTPUT))
        sys.exit(EXIT_SUCCESS)

    # 有未 commit 的變更，輸出警告
    logger.info(
        "uncommitted files detected after agent: %s (%d files)",
        agent_description,
        len(uncommitted_files),
    )

    warning_message = build_warning_message(agent_description, uncommitted_files)

    # 同時輸出到 stderr（雙通道可觀測性）
    sys.stderr.write(f"[{HOOK_NAME}] {MSG_UNCOMMITTED_DETECTED}\n")

    output = {
        "hookSpecificOutput": {
            "hookEventName": "PostToolUse",
            "additionalContext": warning_message,
        }
    }
    print(json.dumps(output))
    sys.exit(EXIT_SUCCESS)


if __name__ == "__main__":
    main()
