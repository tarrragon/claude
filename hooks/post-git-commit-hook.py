#!/usr/bin/env -S uv run --quiet --script
# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///

"""
Git Commit 後置 Hook (PostToolUse) - 合併版

合併以下 3 個 Hook：
1. changelog-update-hook.py — git commit 後檢查 CHANGELOG 是否更新
2. commit-handoff-hook.py — git commit 後輸出 handoff 提醒
3. post-commit-fetch-hook.py — git commit 後背景 fetch

觸發時機: PostToolUse (Bash: git commit)
"""

import json
import os
import re
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, List

sys.path.insert(0, str(Path(__file__).parent))

from hook_utils import (
    setup_hook_logging,
    run_hook_safely,
    read_json_from_stdin,
    run_git,
    get_project_root,
    get_current_version_from_todolist,
    is_subagent_environment,
    parse_ticket_frontmatter,
)
from lib.hook_messages import AskUserQuestionMessages
from lib.ask_user_question_reminders import AskUserQuestionReminders

# ============================================================================
# 常數定義
# ============================================================================

EXIT_SUCCESS = 0

# --- changelog 子邏輯常數 ---
CHANGELOG_SKIP_PREFIXES = (
    "chore", "docs", "style", "ci", "test",
    "refactor(hooks)", "refactor(rules)", "refactor(skills)",
)

# --- handoff 子邏輯常數 ---
EXCLUDED_COMMAND_PATTERNS = [
    "git log", "git show", "git diff", "git status",
    "git commit --amend",
]

SKIP_SCENE16_COMMIT_PREFIXES = frozenset({
    "docs", "chore", "style", "revert", "test", "ci", "build",
})

COMMIT_SUCCESS_MARKERS = [
    "files changed", "file changed",
    "insertions(+)", "deletions(-)", "create mode",
]


# ============================================================================
# 子邏輯 1: CHANGELOG 更新檢查（來自 changelog-update-hook.py）
# ============================================================================

def is_commit_successful(stdout: str, stderr: str = "") -> bool:
    """判斷 commit 是否成功（統一判斷：排除失敗標記 + 確認成功標記）。"""
    combined = stdout + stderr
    if "nothing to commit" in combined or "Aborting" in combined:
        return False
    for marker in COMMIT_SUCCESS_MARKERS:
        if marker in stdout:
            return True
    return False


def _changelog_should_skip(tool_input: dict) -> bool:
    """判斷是否應跳過 CHANGELOG 提醒。"""
    command = tool_input.get("command", "")
    if os.environ.get("VERSION_RELEASE_SCRIPT") == "1":
        return True
    for prefix in CHANGELOG_SKIP_PREFIXES:
        if prefix in command.lower():
            return True
    return False


def _changelog_in_commit(project_dir: Path, logger) -> bool:
    """檢查最近一次 commit 是否包含 CHANGELOG.md 變更。"""
    output = run_git(
        ["git", "diff-tree", "--no-commit-id", "--name-only", "-r", "HEAD"],
        cwd=project_dir, timeout=5, logger=logger,
    )
    if output:
        return "CHANGELOG.md" in output.split("\n")
    return False


def _get_commit_subject(project_dir: Path, logger) -> str:
    """取得最近一次 commit 的 subject。"""
    output = run_git(
        ["git", "--no-optional-locks", "log", "-1", "--format=%s"],
        cwd=project_dir, timeout=5, logger=logger,
    )
    return output if output else ""


def check_changelog_update(input_data: dict, tool_input: dict, logger):
    """子邏輯 1: 檢查 CHANGELOG 是否更新。回傳提醒訊息或 None。"""
    tool_response = input_data.get("tool_response") or {}
    stdout = tool_response.get("stdout", "")
    stderr = tool_response.get("stderr", "")

    if not is_commit_successful(stdout, stderr):
        logger.debug("changelog: commit 失敗，跳過")
        return None

    if _changelog_should_skip(tool_input):
        logger.debug("changelog: 維護性質 commit，跳過")
        return None

    project_dir = get_project_root()

    if _changelog_in_commit(project_dir, logger):
        logger.debug("changelog: CHANGELOG.md 已在 commit 中更新")
        return None

    subject = _get_commit_subject(project_dir, logger)
    logger.info("changelog: commit '%s' 未包含 CHANGELOG.md 更新", subject)
    return (
        f"[CHANGELOG Reminder] commit \"{subject}\" 未包含 CHANGELOG.md 更新。\n"
        f"  如果此 commit 包含使用者可感知的變更（feat/fix），"
        f"建議在版本發布前更新 CHANGELOG.md。\n"
        f"  使用 /version-release 流程可自動處理。"
    )


# ============================================================================
# 子邏輯 2: Commit Handoff 提醒（來自 commit-handoff-hook.py）
# ============================================================================

def _is_git_commit_command(command: str) -> bool:
    """判斷是否為 git commit 命令（排除 --amend 等）。"""
    if "git commit" not in command:
        return False
    for excluded in EXCLUDED_COMMAND_PATTERNS:
        if excluded in command:
            return False
    return True




def _extract_commit_type(command: str) -> str:
    """從 git commit 命令中提取 conventional commit 類型。"""
    match = re.search(r'-m\s+["\']([a-z]+)(?:\([^)]*\))?:', command)
    if match:
        return match.group(1).lower()
    match = re.search(r'\n\s*([a-z]+)(?:\([^)]*\))?:', command)
    if match:
        return match.group(1).lower()
    return ""


def _scan_wave_tickets(
    project_dir: Path, version: str, logger
) -> List[Dict[str, Optional[str]]]:
    """掃描版本目錄中的 Ticket 檔案。"""
    tickets_dir = project_dir / "docs" / "work-logs" / f"v{version}" / "tickets"
    if not tickets_dir.exists():
        return []

    tickets = []
    try:
        for ticket_file in sorted(tickets_dir.glob("*.md")):
            fm = parse_ticket_frontmatter(ticket_file, logger)
            tickets.append({
                "wave": str(fm.get("wave", "")) or None,
                "status": fm.get("status"),
                "file": ticket_file.name,
            })
    except Exception as e:
        logger.warning(f"掃描 Ticket 目錄失敗: {e}")
    return tickets


def _find_current_wave(tickets: List[Dict]) -> Optional[str]:
    """從 ticket 列表找出 in_progress ticket 的 wave。"""
    for ticket in tickets:
        if ticket.get("status") == "in_progress":
            return ticket.get("wave")
    return None


def _detect_wave_completion(logger) -> bool:
    """偵測是否為情境 C（當前 Wave 完成，無 pending ticket）。"""
    try:
        project_dir = get_project_root()
        current_version = get_current_version_from_todolist(project_dir, logger)
        if not current_version:
            return False

        tickets = _scan_wave_tickets(project_dir, current_version, logger)
        current_wave = _find_current_wave(tickets)
        if current_wave is None:
            return False

        pending = sum(1 for t in tickets if t.get("wave") == current_wave and t.get("status") == "pending")
        if pending == 0:
            logger.info(f"偵測到情境 C：Wave {current_wave} 完成")
            return True
        return False
    except Exception as e:
        logger.warning(f"偵測 Wave 完成狀態時發生錯誤: {e}")
        return False


def check_commit_handoff(input_data: dict, tool_input: dict, logger):
    """子邏輯 2: Commit 後產生 handoff 提醒。回傳提醒訊息或 None。"""
    if is_subagent_environment(input_data):
        logger.info("偵測到 subagent 環境，跳過 handoff 提醒")
        return None

    command = tool_input.get("command", "")
    tool_response = input_data.get("tool_response") or {}
    stdout = tool_response.get("stdout", "")

    if not (_is_git_commit_command(command) and is_commit_successful(stdout)):
        logger.debug("handoff: 非 commit 成功，跳過")
        return None

    commit_type = _extract_commit_type(command)
    if commit_type in SKIP_SCENE16_COMMIT_PREFIXES:
        reminder = AskUserQuestionMessages.COMMIT_HANDOFF_SKIP16_REMINDER
    else:
        reminder = AskUserQuestionMessages.COMMIT_HANDOFF_REMINDER

    if _detect_wave_completion(logger):
        reminder += "\n" + AskUserQuestionReminders.WAVE_COMPLETION_REMINDER

    logger.info(f"handoff: 輸出提醒（type={commit_type}）")
    return reminder


# ============================================================================
# 子邏輯 3: 背景 Fetch（來自 post-commit-fetch-hook.py）
# ============================================================================

def run_background_fetch(input_data: dict, tool_input: dict, logger):
    """子邏輯 3: git commit 後同步 fetch。無 additionalContext 回傳。"""
    tool_response = input_data.get("tool_response") or {}
    stdout = tool_response.get("stdout", "")

    if not is_commit_successful(stdout):
        logger.debug("fetch: commit 未成功，跳過")
        return

    try:
        subprocess.run(
            ["git", "fetch", "--quiet", "--all"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            timeout=4,
        )
        logger.debug("fetch: git fetch 完成")
    except subprocess.TimeoutExpired:
        print(
            "[WARNING] git fetch timeout after 4s, process killed",
            file=sys.stderr,
        )
        logger.warning("fetch: git fetch 超時（4s）")


# ============================================================================
# 主程式
# ============================================================================

def main() -> int:
    """主入口點：git commit 後依序執行 3 個子邏輯。"""
    logger = setup_hook_logging("post-git-commit-hook")

    input_data = read_json_from_stdin(logger)
    if input_data is None:
        return EXIT_SUCCESS

    tool_name = input_data.get("tool_name", "")
    if tool_name != "Bash":
        return EXIT_SUCCESS

    tool_input = input_data.get("tool_input") or {}
    command = tool_input.get("command", "")

    if "git commit" not in command:
        return EXIT_SUCCESS

    logger.info("偵測到 git commit 命令，開始執行子邏輯")

    messages = []

    # 子邏輯 1: CHANGELOG 檢查
    try:
        msg = check_changelog_update(input_data, tool_input, logger)
        if msg:
            messages.append(msg)
    except Exception as e:
        logger.error("changelog 子邏輯失敗: %s", e, exc_info=True)

    # 子邏輯 2: Handoff 提醒
    try:
        msg = check_commit_handoff(input_data, tool_input, logger)
        if msg:
            messages.append(msg)
    except Exception as e:
        logger.error("handoff 子邏輯失敗: %s", e, exc_info=True)

    # 子邏輯 3: 背景 Fetch（無 additionalContext 回傳）
    try:
        run_background_fetch(input_data, tool_input, logger)
    except Exception as e:
        logger.error("fetch 子邏輯失敗: %s", e, exc_info=True)

    # 統一輸出
    if messages:
        output = {
            "hookSpecificOutput": {
                "hookEventName": "PostToolUse",
                "additionalContext": "\n\n".join(messages)
            }
        }
        print(json.dumps(output, ensure_ascii=False, indent=2))

    return EXIT_SUCCESS


if __name__ == "__main__":
    sys.exit(run_hook_safely(main, "post-git-commit-hook"))
