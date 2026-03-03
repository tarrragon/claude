#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Branch Verify Hook - PreToolUse Hook 用於編輯前檢查分支

在 Edit 或 Write 工具執行前檢查當前分支是否為保護分支。
如果是保護分支，會詢問用戶是否繼續或建立新分支。

Hook Event: PreToolUse
Matcher: Edit, Write

重構紀錄 (v0.28.0):
- 使用 .claude/lib/git_utils 共用模組
- 使用 .claude/lib/hook_io 共用模組
- 消除重複程式碼

重構紀錄 (v0.31.0-W22-001.3):
- 遷移至統一日誌系統 (hook_utils)
"""

import sys
from pathlib import Path

# 添加 lib 目錄到路徑
sys.path.insert(0, str(Path(__file__).parent.parent / "lib"))
sys.path.insert(0, str(Path(__file__).parent))

from git_utils import (
    get_current_branch,
    is_protected_branch,
    is_allowed_branch,
    generate_worktree_info,
)
from hook_io import (
    read_hook_input,
    write_hook_output,
    create_pretooluse_output,
)
from hook_utils import setup_hook_logging, run_hook_safely


def main() -> int:
    logger = setup_hook_logging("branch-verify")

    # 讀取輸入
    input_data = read_hook_input()
    if not input_data:
        # 無法解析輸入，允許繼續
        logger.debug("無法解析輸入，默認允許")
        output = create_pretooluse_output("allow", "無法解析輸入，默認允許")
        write_hook_output(output)
        return 0

    tool_name = input_data.get("tool_name", "")
    tool_input = input_data.get("tool_input", {})

    # 只檢查 Edit 和 Write 工具
    if tool_name not in ["Edit", "Write"]:
        logger.debug(f"工具 {tool_name} 不需要分支檢查")
        output = create_pretooluse_output("allow", f"工具 {tool_name} 不需要分支檢查")
        write_hook_output(output)
        return 0

    # 獲取當前分支
    current_branch = get_current_branch()
    if not current_branch:
        logger.warning("無法獲取分支資訊，默認允許")
        output = create_pretooluse_output("allow", "無法獲取分支資訊，默認允許")
        write_hook_output(output)
        return 0

    # 檢查是否為允許的分支
    if is_allowed_branch(current_branch):
        logger.info(f"當前在 feature 分支 '{current_branch}' 上，允許編輯")
        output = create_pretooluse_output(
            "allow",
            f"當前在 feature 分支 '{current_branch}' 上，允許編輯"
        )
        write_hook_output(output)
        return 0

    # 檢查是否為保護分支
    if is_protected_branch(current_branch):
        file_path = tool_input.get("file_path", "unknown")
        worktree_info = generate_worktree_info()

        user_prompt = f"""
分支保護警告

當前在保護分支 '{current_branch}' 上嘗試編輯檔案：
{file_path}

保護分支不應直接編輯，建議：
1. 建立 feature 分支進行開發
2. 使用 git worktree 建立獨立工作空間
{worktree_info}
是否仍要在保護分支上繼續編輯？
"""
        logger.info(f"在保護分支 '{current_branch}' 上嘗試編輯，需要用戶確認")
        output = create_pretooluse_output(
            "ask",
            f"在保護分支 '{current_branch}' 上嘗試編輯，需要用戶確認",
            user_prompt.strip()
        )
        write_hook_output(output)
        return 0

    # 其他分支，允許編輯
    logger.info(f"當前在分支 '{current_branch}' 上，允許編輯")
    output = create_pretooluse_output(
        "allow",
        f"當前在分支 '{current_branch}' 上，允許編輯"
    )
    write_hook_output(output)
    return 0


if __name__ == "__main__":
    exit_code = run_hook_safely(main, "branch-verify")
    sys.exit(exit_code)
