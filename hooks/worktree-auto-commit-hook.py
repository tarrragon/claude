#!/usr/bin/env -S uv run --quiet --script
# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///

"""
Worktree Auto-Commit Hook - Stop

功能: 代理人在 worktree 環境結束時，自動 commit 未提交的變更。
防止 Claude Code 內建清理邏輯因「無 commit」而刪除 worktree，導致工作遺失。

觸發時機: Stop event（session 結束時）
行為: 不阻擋（exit 0），僅在 worktree 環境有未提交變更時自動 commit

根因修復: 代理人完成工作後未 git commit → worktree 被清理 → 工作遺失
Ticket: 0.17.0-W4-006
"""

import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from hook_utils import setup_hook_logging, run_hook_safely

# ============================================================================
# 常數定義
# ============================================================================

HOOK_NAME = "worktree-auto-commit"
GIT_TIMEOUT = 10
AUTO_COMMIT_MESSAGE = "auto: worktree agent work completed (uncommitted changes preserved)"


# ============================================================================
# 核心邏輯
# ============================================================================


def is_worktree_environment(logger) -> bool:
    """偵測當前是否在 git worktree 環境中。

    Worktree 的 .git 是一個檔案（內含 gitdir 指向），而非目錄。
    """
    # 方法 1: 檢查 .git 是否為檔案
    cwd = Path.cwd()
    git_path = cwd / ".git"
    if git_path.is_file():
        logger.info("偵測到 worktree 環境（.git 為檔案）: %s", cwd)
        return True

    # 方法 2: 用 git rev-parse 確認
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--git-common-dir"],
            capture_output=True,
            text=True,
            timeout=GIT_TIMEOUT,
        )
        if result.returncode == 0:
            common_dir = result.stdout.strip()
            git_dir_result = subprocess.run(
                ["git", "rev-parse", "--git-dir"],
                capture_output=True,
                text=True,
                timeout=GIT_TIMEOUT,
            )
            if git_dir_result.returncode == 0:
                git_dir = git_dir_result.stdout.strip()
                # 在 worktree 中，git-dir 和 git-common-dir 不同
                if Path(common_dir).resolve() != Path(git_dir).resolve():
                    logger.info("偵測到 worktree 環境（git-dir != common-dir）")
                    return True
    except (subprocess.TimeoutExpired, FileNotFoundError):
        logger.warning("git rev-parse 執行失敗")

    return False


def has_uncommitted_changes(logger) -> bool:
    """檢查是否有未 commit 的變更（含 untracked 檔案）。"""
    try:
        result = subprocess.run(
            ["git", "--no-optional-locks", "status", "--porcelain"],
            capture_output=True,
            text=True,
            timeout=GIT_TIMEOUT,
        )
        if result.returncode != 0:
            logger.warning("git status 失敗: %s", result.stderr.strip())
            return False

        changes = result.stdout.strip()
        if changes:
            file_count = len(changes.splitlines())
            logger.info("偵測到 %d 個未提交的變更", file_count)
            return True
        return False

    except subprocess.TimeoutExpired:
        logger.warning("git status 逾時")
        return False
    except FileNotFoundError:
        logger.warning("找不到 git")
        return False


def auto_commit(logger) -> bool:
    """執行 git add -A && git commit。回傳是否成功。"""
    try:
        # Stage 所有變更
        add_result = subprocess.run(
            ["git", "add", "-A"],
            capture_output=True,
            text=True,
            timeout=GIT_TIMEOUT,
        )
        if add_result.returncode != 0:
            logger.error("git add 失敗: %s", add_result.stderr.strip())
            sys.stderr.write(
                f"[{HOOK_NAME}] git add 失敗: {add_result.stderr.strip()}\n"
            )
            return False

        # Commit
        commit_result = subprocess.run(
            ["git", "commit", "-m", AUTO_COMMIT_MESSAGE, "--no-verify"],
            capture_output=True,
            text=True,
            timeout=GIT_TIMEOUT,
        )
        if commit_result.returncode != 0:
            logger.error("git commit 失敗: %s", commit_result.stderr.strip())
            sys.stderr.write(
                f"[{HOOK_NAME}] git commit 失敗: {commit_result.stderr.strip()}\n"
            )
            return False

        logger.info("自動 commit 成功: %s", AUTO_COMMIT_MESSAGE)
        return True

    except subprocess.TimeoutExpired:
        logger.error("git 操作逾時")
        sys.stderr.write(f"[{HOOK_NAME}] git 操作逾時\n")
        return False
    except FileNotFoundError:
        logger.error("找不到 git")
        sys.stderr.write(f"[{HOOK_NAME}] 找不到 git\n")
        return False


def main() -> int:
    """Hook 主邏輯。"""
    logger = setup_hook_logging(HOOK_NAME)
    logger.info("Stop hook 開始執行")

    # 僅在 worktree 環境中執行
    if not is_worktree_environment(logger):
        logger.debug("非 worktree 環境，跳過")
        return 0

    # 檢查是否有未提交變更
    if not has_uncommitted_changes(logger):
        logger.debug("worktree 中無未提交變更，跳過")
        return 0

    # 自動 commit 保留工作成果
    logger.info("worktree 中有未提交變更，執行自動 commit")
    success = auto_commit(logger)

    if success:
        sys.stderr.write(
            f"[{HOOK_NAME}] worktree 未提交變更已自動 commit 保留\n"
        )
    else:
        sys.stderr.write(
            f"[{HOOK_NAME}] [WARNING] 自動 commit 失敗，worktree 變更可能遺失\n"
        )

    # 不論成功或失敗都回傳 0，不阻擋退出
    return 0


if __name__ == "__main__":
    sys.exit(run_hook_safely(main, HOOK_NAME))
