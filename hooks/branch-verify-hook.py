#!/usr/bin/env -S uv run --quiet --script
# /// script
# requires-python = ">=3.10"
# dependencies = []
# ///
"""
Branch Verify Hook - PreToolUse Hook 用於編輯前檢查分支

在 Edit 或 Write 工具執行前檢查當前分支是否為保護分支。
如果是保護分支，會詢問用戶是否繼續或建立新分支。

Hook Event: PreToolUse
Matcher: Edit, Write

輸入格式 (stdin):
{
    "tool_name": "Edit",
    "tool_input": {
        "file_path": "/path/to/file",
        ...
    }
}

輸出格式:
{
    "hookSpecificOutput": {
        "hookEventName": "PreToolUse",
        "permissionDecision": "allow" | "block" | "ask",
        "permissionDecisionReason": "原因說明",
        "userPrompt": "詢問用戶的訊息（僅當 decision 為 ask 時）"
    }
}
"""

import fnmatch
import json
import os
import subprocess
import sys
from typing import Optional


# 保護分支列表（支援 glob 模式）
PROTECTED_BRANCHES = [
    "main",
    "master",
    "develop",
    "release/*",
    "production",
]

# 允許編輯的分支模式
ALLOWED_BRANCHES = [
    "feat/*",
    "feature/*",
    "fix/*",
    "hotfix/*",
    "bugfix/*",
    "chore/*",
    "docs/*",
    "refactor/*",
    "test/*",
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

    if current_worktree:
        worktrees.append(current_worktree)

    return worktrees


def is_protected_branch(branch: str) -> bool:
    """檢查是否為保護分支"""
    for pattern in PROTECTED_BRANCHES:
        if fnmatch.fnmatch(branch, pattern):
            return True
    return False


def is_allowed_branch(branch: str) -> bool:
    """檢查是否為允許編輯的分支"""
    for pattern in ALLOWED_BRANCHES:
        if fnmatch.fnmatch(branch, pattern):
            return True
    return False


def get_project_root() -> str:
    """獲取專案根目錄"""
    success, output = run_git_command(["rev-parse", "--show-toplevel"])
    return output if success else os.getcwd()


def generate_worktree_info() -> str:
    """生成 worktree 資訊字串"""
    worktrees = get_worktree_list()
    if len(worktrees) <= 1:
        return ""

    info = "\n現有 Worktree:\n"
    for wt in worktrees:
        branch = wt.get("branch", "detached")
        path = wt.get("path", "unknown")
        info += f"  - {branch}: {path}\n"
    return info


def create_output(
    decision: str,
    reason: str,
    user_prompt: Optional[str] = None
) -> dict:
    """創建標準 Hook 輸出"""
    output = {
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": decision,
            "permissionDecisionReason": reason
        }
    }
    if user_prompt:
        output["hookSpecificOutput"]["userPrompt"] = user_prompt
    return output


def main():
    try:
        # 讀取 stdin 輸入
        input_data = json.load(sys.stdin)
    except json.JSONDecodeError:
        # 無法解析輸入，允許繼續
        output = create_output("allow", "無法解析輸入，默認允許")
        print(json.dumps(output, ensure_ascii=False))
        return 0

    tool_name = input_data.get("tool_name", "")
    tool_input = input_data.get("tool_input", {})

    # 只檢查 Edit 和 Write 工具
    if tool_name not in ["Edit", "Write"]:
        output = create_output("allow", f"工具 {tool_name} 不需要分支檢查")
        print(json.dumps(output, ensure_ascii=False))
        return 0

    # 獲取當前分支
    current_branch = get_current_branch()
    if not current_branch:
        output = create_output("allow", "無法獲取分支資訊，默認允許")
        print(json.dumps(output, ensure_ascii=False))
        return 0

    # 檢查是否為允許的分支
    if is_allowed_branch(current_branch):
        output = create_output(
            "allow",
            f"當前在 feature 分支 '{current_branch}' 上，允許編輯"
        )
        print(json.dumps(output, ensure_ascii=False))
        return 0

    # 檢查是否為保護分支
    if is_protected_branch(current_branch):
        file_path = tool_input.get("file_path", "unknown")
        worktree_info = generate_worktree_info()

        user_prompt = f"""
⚠️ 分支保護警告

當前在保護分支 '{current_branch}' 上嘗試編輯檔案：
{file_path}

保護分支不應直接編輯，建議：
1. 建立 feature 分支進行開發
2. 使用 git worktree 建立獨立工作空間
{worktree_info}
是否仍要在保護分支上繼續編輯？
"""
        output = create_output(
            "ask",
            f"在保護分支 '{current_branch}' 上嘗試編輯，需要用戶確認",
            user_prompt.strip()
        )
        print(json.dumps(output, ensure_ascii=False))
        return 0

    # 其他分支，允許編輯
    output = create_output(
        "allow",
        f"當前在分支 '{current_branch}' 上，允許編輯"
    )
    print(json.dumps(output, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
