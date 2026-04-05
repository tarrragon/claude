#!/usr/bin/env python3
# /// script
# requires-python = ">=3.9"
# dependencies = []
# ///
"""
Worktree Commit-Before-Dispatch Hook - PreToolUse (Agent)

功能：派發 worktree agent 前，檢查 main 上是否有未 commit 的 tracked 變更。
未 commit 的變更可能在 worktree 操作後因 stash/checkout 丟失（PC-019）。

Hook 類型：PreToolUse
匹配工具：Agent
退出碼：0 = 放行，2 = 阻擋（stderr 回饋給 Claude）
"""

import json
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from hook_utils import setup_hook_logging, run_hook_safely


BLOCK_MESSAGE = """[PC-019 防護] main 上有未 commit 的 tracked 變更，禁止派發 worktree agent

未 commit 的檔案：
{files}

修復方式：
  先 commit main 上的變更，再派發 worktree agent
  git add <files> && git commit -m "chore: pre-dispatch commit"

詳見: .claude/pm-rules/worktree-operations.md（階段 1：派發前）"""


def main() -> int:
    """Hook 主邏輯。"""
    logger = setup_hook_logging("worktree-commit-before-dispatch")

    try:
        input_data = json.load(sys.stdin)
    except (json.JSONDecodeError, EOFError):
        logger.warning("無法解析 stdin JSON")
        return 0  # 解析失敗不阻擋

    tool_input = input_data.get("tool_input", {})
    isolation = tool_input.get("isolation", "")

    # 只檢查 worktree 隔離的派發
    if isolation != "worktree":
        logger.debug("非 worktree 隔離，跳過檢查")
        return 0

    logger.info("偵測到 worktree 派發，檢查未 commit 變更")

    # 檢查 tracked 檔案是否有未 commit 的變更
    try:
        unstaged = subprocess.run(
            ["git", "diff", "--name-only"],
            capture_output=True, text=True, timeout=10
        )
        staged = subprocess.run(
            ["git", "diff", "--staged", "--name-only"],
            capture_output=True, text=True, timeout=10
        )
    except (subprocess.TimeoutExpired, FileNotFoundError):
        logger.warning("git 命令執行失敗")
        return 0  # git 失敗不阻擋

    changed_files = set()
    if unstaged.stdout.strip():
        changed_files.update(unstaged.stdout.strip().split("\n"))
    if staged.stdout.strip():
        changed_files.update(staged.stdout.strip().split("\n"))

    if not changed_files:
        logger.info("無未 commit 變更，放行")
        return 0

    files_list = "\n".join(f"  - {f}" for f in sorted(changed_files))
    message = BLOCK_MESSAGE.format(files=files_list)
    print(message, file=sys.stderr)
    logger.warning("阻擋 worktree 派發：%d 個未 commit 檔案", len(changed_files))
    return 2


if __name__ == "__main__":
    sys.exit(run_hook_safely(main, "worktree-commit-before-dispatch"))
