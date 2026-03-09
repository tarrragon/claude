#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Branch Verify Hook - PreToolUse Hook 用於編輯前檢查分支

在 Edit 或 Write 工具執行前檢查當前分支是否為保護分支。
如果是保護分支，會拒絕（deny）操作並提示用戶切換到 feature 分支。

Hook Event: PreToolUse
Matcher: Edit, Write
Decision: "allow" (feature 分支) | "deny" (保護分支)

重構紀錄 (v0.28.0):
- 使用 .claude/lib/git_utils 共用模組
- 使用 .claude/lib/hook_io 共用模組
- 消除重複程式碼

重構紀錄 (v0.31.0-W22-001.3):
- 遷移至統一日誌系統 (hook_utils)

修改紀錄 (0.31.1-W5-001):
- 將保護分支決策從 "ask" 改為 "deny"（預防 Edit 操作在保護分支上執行）
- 優化 block 訊息，包含詳細的分支切換指引
- 移除未使用的 worktree_info 變數
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
    tool_input = input_data.get("tool_input") or {}

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

        logger.info(f"在保護分支 '{current_branch}' 上嘗試編輯檔案 {file_path}，操作已阻止")
        output = create_pretooluse_output(
            "deny",
            f"""保護分支編輯被阻止

對不起，當前在保護分支 '{current_branch}' 上，無法直接編輯檔案：
{file_path}

保護分支用於穩定開發，需要在獨立分支上進行更改。

建議的分支切換方式：

1. 建立新 feature 分支並切換：
   git checkout -b feat/your-feature

2. 或使用 git worktree 建立獨立工作空間：
   git worktree add ../book-feat feat/your-feature

請先建立並切換到 feature 分支後再進行編輯。"""
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
