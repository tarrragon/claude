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

輸出：直接輸出文字到 stdout，會顯示在 Session 開始時
"""

import fnmatch
import os
import subprocess
import sys
from datetime import datetime


# 保護分支列表
PROTECTED_BRANCHES = [
    "main",
    "master",
    "develop",
    "release/*",
    "production",
]


def run_git_command(args: list[str], cwd: str | None = None) -> tuple[bool, str]:
    """執行 git 命令並返回結果"""
    try:
        result = subprocess.run(
            ["git"] + args,
            cwd=cwd,
            capture_output=True,
            text=True,
            timeout=10
        )
        if result.returncode == 0:
            return True, result.stdout.strip()
        else:
            return False, result.stderr.strip()
    except Exception as e:
        return False, str(e)


def get_current_branch() -> str | None:
    """獲取當前分支名稱"""
    success, output = run_git_command(["branch", "--show-current"])
    return output if success else None


def get_worktree_list() -> list[dict]:
    """獲取所有 worktree 列表"""
    success, output = run_git_command(["worktree", "list", "--porcelain"])
    if not success:
        return []

    worktrees = []
    current_worktree = {}

    for line in output.split("\n"):
        if line.startswith("worktree "):
            if current_worktree:
                worktrees.append(current_worktree)
            current_worktree = {"path": line[9:]}
        elif line.startswith("branch "):
            current_worktree["branch"] = line[7:].replace("refs/heads/", "")
        elif line == "detached":
            current_worktree["detached"] = True

    if current_worktree:
        worktrees.append(current_worktree)

    return worktrees


def get_current_worktree_path() -> str:
    """獲取當前 worktree 路徑"""
    success, output = run_git_command(["rev-parse", "--show-toplevel"])
    return output if success else os.getcwd()


def is_protected_branch(branch: str) -> bool:
    """檢查是否為保護分支"""
    for pattern in PROTECTED_BRANCHES:
        if fnmatch.fnmatch(branch, pattern):
            return True
    return False


def main():
    print()
    print("=" * 60)
    print("🌿 Branch Worktree Guardian - Session 啟動提醒")
    print("=" * 60)
    print()

    # 獲取當前分支
    current_branch = get_current_branch()
    if not current_branch:
        print("⚠️  無法獲取分支資訊，可能不在 git 倉庫中")
        print()
        return 0

    # 獲取 worktree 資訊
    worktrees = get_worktree_list()
    current_path = get_current_worktree_path()

    # 顯示當前分支
    is_protected = is_protected_branch(current_branch)
    branch_status = "⚠️ 保護分支" if is_protected else "✅ 開發分支"
    print(f"📍 當前分支: {current_branch} ({branch_status})")
    print(f"📁 工作目錄: {current_path}")
    print()

    # 顯示 worktree 列表
    if len(worktrees) > 1:
        print("🌳 現有 Worktree:")
        for wt in worktrees:
            branch = wt.get("branch", "detached")
            path = wt.get("path", "unknown")
            is_current = path == current_path
            marker = " <-- 當前" if is_current else ""
            status = "🔒" if is_protected_branch(branch) else "🔓"
            print(f"   {status} {branch}: {path}{marker}")
        print()

    # 保護分支警告
    if is_protected:
        print("⚠️  警告: 當前在保護分支上")
        print()
        print("建議操作:")
        print("  1. 如果要開始新開發，請先建立 feature 分支")
        print("  2. 使用以下命令創建分支和 worktree:")
        print()
        print("     git checkout -b feat/your-feature")
        print("     git worktree add ../project-your-feature feat/your-feature")
        print("     cd ../project-your-feature")
        print()
        print("  或使用 SKILL 腳本:")
        print("     python .claude/skills/branch-worktree-guardian/scripts/create_feature_worktree.py \\")
        print("         --branch feat/your-feature --worktree ../project-your-feature")
        print()
    else:
        print("✅ 當前在開發分支上，可以安全進行編輯")
        print()

    # 如果有多個 worktree，提醒確認
    if len(worktrees) > 1:
        print("💡 提示: 檢測到多個 worktree，請確認您在正確的工作目錄中")
        print()

    print("=" * 60)
    print()

    return 0


if __name__ == "__main__":
    sys.exit(main())
