#!/usr/bin/env -S uv run --quiet --script
# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///

"""
CHANGELOG 更新提醒 Hook (PostToolUse)

功能:
  偵測 git commit 後，檢查 CHANGELOG.md 是否已同步更新。
  若本次 commit 未包含 CHANGELOG.md 的變更，輸出提醒訊息。

觸發時機: PostToolUse (Bash: git commit)

輸出:
  已更新: 無輸出（靜默通過）
  未更新: stderr 輸出提醒（不阻止操作）

排除條件:
  - commit message 包含 "chore" 或 "docs" 或 "refactor(hooks)" 等維護性質
  - 透過 /version-release 流程執行的 commit

HOOK_METADATA (JSON):
{
  "event_type": "PostToolUse",
  "matcher": "Bash",
  "description": "CHANGELOG 更新提醒 - git commit 後檢查 CHANGELOG 同步",
  "dependencies": [],
  "version": "1.0.0"
}
"""

import json
import os
import re
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from hook_utils import setup_hook_logging, run_hook_safely

# 不需要 CHANGELOG 提醒的 commit 類型
SKIP_PREFIXES = (
    "chore",
    "docs",
    "style",
    "ci",
    "test",
    "refactor(hooks)",
    "refactor(rules)",
    "refactor(skills)",
)


def is_git_commit(tool_input: dict) -> bool:
    """判斷是否為 git commit 命令。"""
    command = tool_input.get("command", "")
    return "git commit" in command


def is_commit_successful(tool_result: dict) -> bool:
    """判斷 commit 是否成功。"""
    stdout = tool_result.get("stdout", "")
    stderr = tool_result.get("stderr", "")
    # git commit 成功時 stdout 包含 commit hash 或 "create mode"
    # 失敗時包含 "nothing to commit" 或 "Aborting"
    if "nothing to commit" in stdout or "Aborting" in stdout:
        return False
    if "nothing to commit" in stderr or "Aborting" in stderr:
        return False
    return True


def should_skip_reminder(tool_input: dict) -> bool:
    """判斷是否應跳過 CHANGELOG 提醒。"""
    command = tool_input.get("command", "")

    # 透過 version-release 流程
    if os.environ.get("VERSION_RELEASE_SCRIPT") == "1":
        return True

    # 維護性質的 commit
    for prefix in SKIP_PREFIXES:
        if prefix in command.lower():
            return True

    return False


def check_changelog_in_commit(project_dir: Path) -> bool:
    """檢查最近一次 commit 是否包含 CHANGELOG.md 變更。"""
    try:
        result = subprocess.run(
            ["git", "diff-tree", "--no-commit-id", "--name-only", "-r", "HEAD"],
            capture_output=True,
            text=True,
            cwd=project_dir,
            timeout=5,
        )
        if result.returncode == 0:
            changed_files = result.stdout.strip().split("\n")
            return "CHANGELOG.md" in changed_files
    except (subprocess.TimeoutExpired, FileNotFoundError):
        pass
    return False


def get_commit_subject(project_dir: Path) -> str:
    """取得最近一次 commit 的 subject。"""
    try:
        result = subprocess.run(
            ["git", "log", "-1", "--format=%s"],
            capture_output=True,
            text=True,
            cwd=project_dir,
            timeout=5,
        )
        if result.returncode == 0:
            return result.stdout.strip()
    except (subprocess.TimeoutExpired, FileNotFoundError):
        pass
    return ""


def main():
    logger = setup_hook_logging("changelog-update-hook")
    input_data = json.load(sys.stdin)
    tool_name = input_data.get("tool_name", "")
    tool_input = input_data.get("tool_input", {})
    tool_result = input_data.get("tool_result", {})

    # 只處理 Bash git commit
    if tool_name != "Bash" or not is_git_commit(tool_input):
        return 0

    # commit 失敗則跳過
    if not is_commit_successful(tool_result):
        return 0

    # 維護性質 commit 跳過
    if should_skip_reminder(tool_input):
        return 0

    project_dir = Path(os.getenv("CLAUDE_PROJECT_DIR", Path.cwd()))

    # 檢查 CHANGELOG 是否在此次 commit 中更新
    if check_changelog_in_commit(project_dir):
        return 0

    # 取得 commit subject 供提醒使用
    subject = get_commit_subject(project_dir)

    message = (
        f"[CHANGELOG Reminder] commit \"{subject}\" 未包含 CHANGELOG.md 更新。\n"
        f"  如果此 commit 包含使用者可感知的變更（feat/fix），"
        f"建議在版本發布前更新 CHANGELOG.md。\n"
        f"  使用 /version-release 流程可自動處理。"
    )
    print(message)
    logger.info(message)
    return 0


if __name__ == "__main__":
    sys.exit(run_hook_safely(main, "changelog-update-hook"))
