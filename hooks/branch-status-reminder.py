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

改進 (v1.2.0):
- 使用 get_uncommitted_files() 高階 API
- 遷移離開原始的 porcelain 格式解析

改進 (v1.1.0):
- 使用 common_functions 統一 logging 和 output
- 避免 stderr 污染

重構紀錄 (v0.28.0):
- 使用 .claude/lib/git_utils 共用模組
- 消除重複程式碼

修改紀錄 (0.1.1-W9-002.3):
- 改為靜默條件判斷（正確 worktree 環境時完全靜默）
- 新增 is_in_worktree 和 is_allowed_branch 的判斷
- 僅在異常情況時輸出提醒
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
        is_protected_branch,
        is_allowed_branch,
        is_in_worktree,
        run_git_command,
        get_uncommitted_files,
    )
except ImportError as e:
    # #11 修復：ImportError 不應 exit(1) 阻斷整個 session
    # 應該優雅降級為靜默（Hook 失敗應記錄但不阻塞主程式）
    print(f"[Hook Import Warning] {Path(__file__).name}: {e}", file=sys.stderr)
    # 定義最小化的 fallback 函式以支援優雅降級
    def setup_hook_logging(name):
        import logging
        return logging.getLogger(name)
    def hook_output(msg, level):
        pass  # 靜默
    def get_current_branch():
        return None
    def is_in_worktree():
        return False
    def is_allowed_branch(branch):
        return False
    def is_protected_branch(branch):
        return branch in ["main", "master", "develop"]
    def run_git_command(args, cwd=None, timeout=10):
        return False, "git_utils not available"
    def get_uncommitted_files():
        return []  # 無法查詢時回傳空列表，功能降級


# 顯示設定常數
MAX_UNCOMMITTED_FILES_DISPLAY = 10  # 未提交變更顯示上限，超過則折疊顯示


def _report_uncommitted_changes() -> None:
    """
    偵測並報告未提交的變更

    使用 get_uncommitted_files() 取得未提交變更的結構化資訊，
    如果超過 MAX_UNCOMMITTED_FILES_DISPLAY 個檔案，只顯示前 N 個並提示還有多少個。
    如果沒有未提交變更，則不輸出任何內容。
    """
    files = get_uncommitted_files()

    if not files:
        return

    total_changes = len(files)

    # 輸出未提交變更摘要
    hook_output(f"[branch-status-reminder] 偵測到 {total_changes} 個未提交變更：", "info")

    # 列出前 N 個變更
    for file in files[:MAX_UNCOMMITTED_FILES_DISPLAY]:
        hook_output(f"   {file}", "info")

    # 如果超過上限，顯示還有多少個
    if total_changes > MAX_UNCOMMITTED_FILES_DISPLAY:
        remaining = total_changes - MAX_UNCOMMITTED_FILES_DISPLAY
        hook_output(f"   ...還有 {remaining} 個", "info")

    hook_output("[提示] 這些變更可能來自其他 session，建議先確認後再開始工作", "info")
    hook_output("", "info")


def main():
    logger = setup_hook_logging("branch-status-reminder")

    # 獲取當前分支
    current_branch = get_current_branch()
    if not current_branch:
        logger.warning("Unable to get current branch")
        # 靜默：無法取得分支時保守預設為不輸出
        return 0

    # 檢查是否在正確的 worktree 環境中
    # 靜默條件：在 worktree 中 AND 分支符合 allowed pattern
    if is_in_worktree() and is_allowed_branch(current_branch):
        logger.debug(f"正確 worktree 環境：{current_branch}，靜默")
        # 完全靜默，不輸出任何內容
        return 0

    # 異常情況：以下任一情況時輸出提醒
    hook_output("", "info")
    hook_output("=" * 60, "info")
    hook_output("Branch Worktree Guardian - Session 啟動提醒", "info")
    hook_output("=" * 60, "info")
    hook_output("", "info")

    # 情況 1：在主倉庫且在保護分支上
    if not is_in_worktree() and is_protected_branch(current_branch):
        hook_output(f"[branch-status-reminder] 警告：當前在主倉庫的保護分支 '{current_branch}' 上", "warning")
        hook_output("", "info")

        # 偵測未提交變更
        _report_uncommitted_changes()

        hook_output("建議操作：", "info")
        hook_output("  建立 feature worktree 進行開發：", "info")
        hook_output("  /worktree create <ticket-id>", "info")
        hook_output("", "info")
        hook_output("  或手動建立分支：", "info")
        hook_output("  git checkout -b feat/your-feature", "info")
        hook_output("", "info")
        logger.warning(f"Currently on protected branch in main repo: {current_branch}")

    # 情況 2：在主倉庫且在 allowed 分支上
    elif not is_in_worktree() and is_allowed_branch(current_branch):
        hook_output(f"[branch-status-reminder] 提示：當前在主倉庫的開發分支 '{current_branch}'", "info")
        hook_output("", "info")
        hook_output("建議使用 worktree 保持環境隔離：", "info")
        hook_output("  /worktree create <ticket-id>", "info")
        hook_output("", "info")
        logger.debug(f"Currently on development branch in main repo: {current_branch}")

    # 情況 3：在 worktree 但分支不符合 allowed pattern
    elif is_in_worktree() and not is_allowed_branch(current_branch):
        hook_output("[branch-status-reminder] 警告：worktree 分支異常", "warning")
        hook_output(f"當前分支：{current_branch}（detached 或不是預期分支）", "info")
        hook_output("", "info")
        logger.warning(f"Worktree branch anomaly detected: {current_branch}")

    # 情況 4：其他異常（通常不會發生）
    else:
        hook_output(f"[branch-status-reminder] 提示：當前在 {current_branch}", "info")
        hook_output("", "info")
        logger.debug(f"Current branch: {current_branch}")

    hook_output("=" * 60, "info")
    hook_output("", "info")

    return 0


if __name__ == "__main__":
    sys.exit(main())
