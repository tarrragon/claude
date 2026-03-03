#!/usr/bin/env -S uv run --quiet --script
# /// script
# requires-python = ">=3.10"
# dependencies = []
# ///
"""
Branch Status Reminder - SessionStart Hook 用於顯示分支狀態

在 Session 啟動時顯示當前分支狀態和 worktree 列表，
如果在保護分支上，會提醒建立 feature 分支。

Hook Event: SessionStart

改進 (v1.1.0):
- 使用 common_functions 統一 logging 和 output
- 避免 stderr 污染

重構紀錄 (v0.28.0):
- 使用 .claude/lib/git_utils 共用模組
- 消除重複程式碼
"""

import sys
from pathlib import Path

# 添加 lib 目錄到路徑（M-003 標準化）
sys.path.insert(0, str(Path(__file__).parent))
# git_utils 位於 .claude/lib/（專案級共用程式庫）
sys.path.insert(0, str(Path(__file__).parent.parent / "lib"))

try:
    from hook_utils import setup_hook_logging
    from lib.common_functions import hook_output
    from git_utils import (
        get_current_branch,
        get_project_root,
        get_worktree_list,
        is_protected_branch,
    )
except ImportError as e:
    print(f"[Hook Import Error] {Path(__file__).name}: {e}", file=sys.stderr)
    sys.exit(1)


def main():
    logger = setup_hook_logging("branch-status-reminder")

    hook_output("", "info")
    hook_output("=" * 60, "info")
    hook_output("Branch Worktree Guardian - Session 啟動提醒", "info")
    hook_output("=" * 60, "info")
    hook_output("", "info")

    # 獲取當前分支
    current_branch = get_current_branch()
    if not current_branch:
        hook_output("警告: 無法獲取分支資訊，可能不在 git 倉庫中", "warning")
        hook_output("", "info")
        logger.warning("Unable to get current branch")
        return 0

    # 獲取 worktree 資訊
    worktrees = get_worktree_list()
    current_path = get_project_root()

    # 顯示當前分支
    is_protected = is_protected_branch(current_branch)
    branch_status = "保護分支" if is_protected else "開發分支"
    hook_output(f"當前分支: {current_branch} ({branch_status})", "info")
    hook_output(f"工作目錄: {current_path}", "info")
    hook_output("", "info")
    logger.debug(f"Current branch: {current_branch} ({branch_status})")

    # 顯示 worktree 列表
    if len(worktrees) > 1:
        hook_output("現有 Worktree:", "info")
        for wt in worktrees:
            branch = wt.get("branch", "detached")
            path = wt.get("path", "unknown")
            is_current = path == current_path
            marker = " <-- 當前" if is_current else ""
            status = "[保護]" if is_protected_branch(branch) else "[開發]"
            hook_output(f"   {status} {branch}: {path}{marker}", "info")
        hook_output("", "info")

    # 保護分支警告
    if is_protected:
        hook_output("警告: 當前在保護分支上", "warning")
        hook_output("", "info")
        hook_output("建議操作:", "info")
        hook_output("  1. 如果要開始新開發，請先建立 feature 分支", "info")
        hook_output("  2. 使用以下命令創建分支和 worktree:", "info")
        hook_output("", "info")
        hook_output("     git checkout -b feat/your-feature", "info")
        hook_output("     git worktree add ../project-your-feature feat/your-feature", "info")
        hook_output("     cd ../project-your-feature", "info")
        hook_output("", "info")
        hook_output("  或使用 SKILL 腳本:", "info")
        hook_output("     python .claude/skills/branch-worktree-guardian/scripts/create_feature_worktree.py \\", "info")
        hook_output("         --branch feat/your-feature --worktree ../project-your-feature", "info")
        hook_output("", "info")
        logger.warning(f"Currently on protected branch: {current_branch}")
    else:
        hook_output("當前在開發分支上，可以安全進行編輯", "info")
        hook_output("", "info")
        logger.debug(f"Currently on development branch: {current_branch}")

    # 如果有多個 worktree，提醒確認
    if len(worktrees) > 1:
        hook_output("提示: 檢測到多個 worktree，請確認您在正確的工作目錄中", "info")
        hook_output("", "info")
        logger.debug(f"Multiple worktrees detected: {len(worktrees)}")

    hook_output("=" * 60, "info")
    hook_output("", "info")

    return 0


if __name__ == "__main__":
    sys.exit(main())
