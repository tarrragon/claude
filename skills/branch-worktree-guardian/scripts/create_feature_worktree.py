#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# dependencies = []
# ///
"""
Create Feature Worktree - 創建新的 feature 分支和對應的 worktree

Usage:
    uv run .claude/skills/branch-worktree-guardian/scripts/create_feature_worktree.py \
        --branch feat/new-feature \
        --worktree ../project-new-feature

    uv run .claude/skills/branch-worktree-guardian/scripts/create_feature_worktree.py \
        --branch feat/new-feature \
        --worktree ../project-new-feature \
        --base develop
"""

import argparse
import os
import subprocess
import sys
from pathlib import Path


def run_git_command(args: list[str], cwd: str | None = None) -> tuple[bool, str]:
    """執行 git 命令並返回結果"""
    try:
        result = subprocess.run(
            ["git"] + args,
            cwd=cwd,
            capture_output=True,
            text=True,
            timeout=30
        )
        if result.returncode == 0:
            return True, result.stdout.strip()
        else:
            return False, result.stderr.strip()
    except subprocess.TimeoutExpired:
        return False, "命令執行超時"
    except Exception as e:
        return False, str(e)


def get_current_branch(cwd: str | None = None) -> str | None:
    """獲取當前分支名稱"""
    success, output = run_git_command(["branch", "--show-current"], cwd)
    return output if success else None


def branch_exists(branch: str, cwd: str | None = None) -> bool:
    """檢查分支是否已存在"""
    success, _ = run_git_command(["rev-parse", "--verify", branch], cwd)
    return success


def worktree_exists(path: str) -> bool:
    """檢查 worktree 路徑是否已存在"""
    return os.path.exists(path)


def create_feature_worktree(
    branch: str,
    worktree_path: str,
    base_branch: str = "main"
) -> tuple[bool, str]:
    """
    創建 feature 分支和對應的 worktree

    Args:
        branch: 新分支名稱
        worktree_path: worktree 目錄路徑
        base_branch: 基礎分支（預設 main）

    Returns:
        (成功與否, 訊息)
    """
    # 轉換為絕對路徑
    worktree_abs_path = os.path.abspath(worktree_path)

    # 檢查 worktree 路徑是否已存在
    if worktree_exists(worktree_abs_path):
        return False, f"Worktree 路徑已存在: {worktree_abs_path}"

    # 檢查分支是否已存在
    if branch_exists(branch):
        return False, f"分支已存在: {branch}"

    # 檢查基礎分支是否存在
    if not branch_exists(base_branch):
        return False, f"基礎分支不存在: {base_branch}"

    # 從基礎分支創建新分支
    success, msg = run_git_command(["checkout", "-b", branch, base_branch])
    if not success:
        return False, f"創建分支失敗: {msg}"

    # 創建 worktree
    success, msg = run_git_command(["worktree", "add", worktree_abs_path, branch])
    if not success:
        # 回滾：刪除剛創建的分支
        run_git_command(["branch", "-D", branch])
        return False, f"創建 worktree 失敗: {msg}"

    return True, f"成功創建分支 '{branch}' 和 worktree '{worktree_abs_path}'"


def main():
    parser = argparse.ArgumentParser(
        description="創建新的 feature 分支和對應的 worktree"
    )
    parser.add_argument(
        "--branch", "-b",
        required=True,
        help="新分支名稱 (例如: feat/new-feature)"
    )
    parser.add_argument(
        "--worktree", "-w",
        required=True,
        help="Worktree 目錄路徑 (例如: ../project-new-feature)"
    )
    parser.add_argument(
        "--base",
        default="main",
        help="基礎分支 (預設: main)"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="只顯示將要執行的操作，不實際執行"
    )

    args = parser.parse_args()

    if args.dry_run:
        print("=== Dry Run 模式 ===")
        print(f"將要執行的操作:")
        print(f"  1. 從 '{args.base}' 創建分支 '{args.branch}'")
        print(f"  2. 創建 worktree 到 '{os.path.abspath(args.worktree)}'")
        print()
        print("實際執行請移除 --dry-run 參數")
        return 0

    print(f"正在創建 feature worktree...")
    print(f"  分支: {args.branch}")
    print(f"  基礎: {args.base}")
    print(f"  路徑: {os.path.abspath(args.worktree)}")
    print()

    success, message = create_feature_worktree(
        branch=args.branch,
        worktree_path=args.worktree,
        base_branch=args.base
    )

    if success:
        print(f"✅ {message}")
        print()
        print("下一步:")
        print(f"  cd {os.path.abspath(args.worktree)}")
        return 0
    else:
        print(f"❌ {message}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
