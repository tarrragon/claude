#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# dependencies = []
# ///
"""
Verify Branch - 驗證當前分支是否適合進行編輯

Usage:
    uv run .claude/skills/branch-worktree-guardian/scripts/verify_branch.py
    uv run .claude/skills/branch-worktree-guardian/scripts/verify_branch.py --path /path/to/project
    uv run .claude/skills/branch-worktree-guardian/scripts/verify_branch.py --json
"""

import argparse
import fnmatch
import json
import os
import subprocess
import sys
from dataclasses import dataclass
from typing import Optional


# 保護分支列表（支援 glob 模式）
PROTECTED_BRANCHES = [
    "main",
    "master",
    "develop",
    "release/*",
    "production",
]


@dataclass
class BranchVerificationResult:
    """分支驗證結果"""
    is_protected: bool
    current_branch: str
    worktree_path: str
    worktrees: list[dict]
    message: str
    recommendation: Optional[str] = None


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


def get_worktree_list(cwd: str | None = None) -> list[dict]:
    """獲取所有 worktree 列表"""
    success, output = run_git_command(["worktree", "list", "--porcelain"], cwd)
    if not success:
        return []

    worktrees = []
    current_worktree = {}

    for line in output.split("\n"):
        if line.startswith("worktree "):
            if current_worktree:
                worktrees.append(current_worktree)
            current_worktree = {"path": line[9:]}
        elif line.startswith("HEAD "):
            current_worktree["head"] = line[5:]
        elif line.startswith("branch "):
            current_worktree["branch"] = line[7:].replace("refs/heads/", "")
        elif line == "bare":
            current_worktree["bare"] = True
        elif line == "detached":
            current_worktree["detached"] = True

    if current_worktree:
        worktrees.append(current_worktree)

    return worktrees


def is_protected_branch(branch: str) -> bool:
    """檢查是否為保護分支"""
    for pattern in PROTECTED_BRANCHES:
        if fnmatch.fnmatch(branch, pattern):
            return True
    return False


def get_current_worktree_path(cwd: str | None = None) -> str:
    """獲取當前 worktree 路徑"""
    success, output = run_git_command(["rev-parse", "--show-toplevel"], cwd)
    return output if success else os.getcwd()


def verify_branch(path: str | None = None) -> BranchVerificationResult:
    """
    驗證指定路徑的分支狀態

    Args:
        path: 要檢查的目錄路徑，預設為當前目錄

    Returns:
        BranchVerificationResult 包含驗證結果
    """
    cwd = path or os.getcwd()

    # 獲取當前分支
    current_branch = get_current_branch(cwd)
    if not current_branch:
        return BranchVerificationResult(
            is_protected=False,
            current_branch="unknown",
            worktree_path=cwd,
            worktrees=[],
            message="無法獲取當前分支，可能不在 git 倉庫中"
        )

    # 獲取 worktree 資訊
    worktrees = get_worktree_list(cwd)
    worktree_path = get_current_worktree_path(cwd)

    # 檢查是否為保護分支
    is_protected = is_protected_branch(current_branch)

    if is_protected:
        return BranchVerificationResult(
            is_protected=True,
            current_branch=current_branch,
            worktree_path=worktree_path,
            worktrees=worktrees,
            message=f"警告: 當前在保護分支 '{current_branch}' 上",
            recommendation="建議建立 feature 分支進行開發"
        )
    else:
        return BranchVerificationResult(
            is_protected=False,
            current_branch=current_branch,
            worktree_path=worktree_path,
            worktrees=worktrees,
            message=f"當前在分支 '{current_branch}' 上，可以安全編輯"
        )


def main():
    parser = argparse.ArgumentParser(
        description="驗證當前分支是否適合進行編輯"
    )
    parser.add_argument(
        "--path", "-p",
        default=None,
        help="要檢查的目錄路徑 (預設: 當前目錄)"
    )
    parser.add_argument(
        "--json", "-j",
        action="store_true",
        help="以 JSON 格式輸出"
    )
    parser.add_argument(
        "--quiet", "-q",
        action="store_true",
        help="只返回 exit code，不輸出文字"
    )

    args = parser.parse_args()

    result = verify_branch(args.path)

    if args.quiet:
        return 1 if result.is_protected else 0

    if args.json:
        output = {
            "is_protected": result.is_protected,
            "current_branch": result.current_branch,
            "worktree_path": result.worktree_path,
            "worktrees": result.worktrees,
            "message": result.message,
            "recommendation": result.recommendation
        }
        print(json.dumps(output, ensure_ascii=False, indent=2))
    else:
        print("=" * 50)
        print("Branch Verification Report")
        print("=" * 50)
        print()
        print(f"當前分支: {result.current_branch}")
        print(f"Worktree 路徑: {result.worktree_path}")
        print()

        if result.worktrees:
            print("所有 Worktree:")
            for wt in result.worktrees:
                branch = wt.get("branch", "detached")
                path = wt.get("path", "unknown")
                marker = " <-- 當前" if path == result.worktree_path else ""
                print(f"  - {branch}: {path}{marker}")
            print()

        if result.is_protected:
            print(f"⚠️  {result.message}")
            if result.recommendation:
                print(f"💡 {result.recommendation}")
        else:
            print(f"✅ {result.message}")

        print("=" * 50)

    return 1 if result.is_protected else 0


if __name__ == "__main__":
    sys.exit(main())
