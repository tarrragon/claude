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

改進 (v1.3.0, W13-011):
- PC-076 防護落地：列出全部 tracked-modified + untracked
- 分組顯示（staged / modified / untracked），上限提升至 50 + 完整清單提示
- 雙通道輸出（stderr + logger.warning），避免 PM 誤認工作區乾淨
- 情況 1/2/3/4 皆呼叫 _report_uncommitted_changes（修復前僅情況 1）

改進 (v1.2.0):
- 使用 get_uncommitted_files() 高階 API
- 遷移離開原始的 porcelain 格式解析

改進 (v1.1.0):
- 使用 common_functions 統一 logging 和 output
- 避免 stderr 污染
"""

import sys
from pathlib import Path

# 添加 lib 目錄到路徑（M-003 標準化）
sys.path.insert(0, str(Path(__file__).parent))
sys.path.insert(0, str(Path(__file__).parent.parent))
# git_utils 位於 .claude/lib/（專案級共用程式庫）

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
    print(f"[Hook Import Warning] {Path(__file__).name}: {e}", file=sys.stderr)
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
        return []


# 顯示設定常數
# W13-011：上限提升至 50（PC-076 防護全量列出），超過則提示用 git status 取完整清單
MAX_UNCOMMITTED_FILES_DISPLAY = 50


def _classify_files(files):
    """
    將 FileStatus 列表依 staged / modified / untracked 分組。

    分組規則（PC-076 防護）：
    - staged：is_staged 且非 untracked（X 位置含 M/A/D/R/C）
    - modified：非 staged 且非 untracked（Y 位置含 M），常為前 session 遺留
    - untracked：?? 狀態

    Returns:
        dict: {"staged": [...], "modified": [...], "untracked": [...]}
    """
    staged, modified, untracked = [], [], []
    for f in files:
        if f.is_untracked:
            untracked.append(f)
        elif f.is_staged:
            staged.append(f)
        else:
            modified.append(f)
    return {"staged": staged, "modified": modified, "untracked": untracked}


def _report_uncommitted_changes(logger) -> None:
    """
    偵測並報告未提交的變更（W13-011 改寫，PC-076 防護落地）。

    變更：
    1. 列出全部 tracked-modified + untracked，分組（staged / modified / untracked）
    2. 上限 50；超過則顯示「完整清單請執行 git status」提示
    3. 雙通道：hook_output（用戶可見）+ stderr（避免被遮蔽）+ logger.warning（持久化）
    """
    files = get_uncommitted_files()
    if not files:
        return

    groups = _classify_files(files)
    total = len(files)

    # 摘要標頭（含分組計數）
    summary = (
        f"[branch-status-reminder] 偵測到 {total} 個未提交變更："
        f"staged={len(groups['staged'])}, "
        f"modified={len(groups['modified'])}, "
        f"untracked={len(groups['untracked'])}"
    )
    hook_output(summary, "info")
    # 雙通道：stderr（避免 hook_output 走 stdout 被介面截斷）+ logger.warning
    print(summary, file=sys.stderr)
    logger.warning(
        f"uncommitted changes detected: total={total}, "
        f"staged={len(groups['staged'])}, modified={len(groups['modified'])}, "
        f"untracked={len(groups['untracked'])}"
    )

    # 分組列出（每組獨立計數，避免單一上限把某一組壓縮為 0）
    listed = 0
    truncated = False
    for label, items in (
        ("staged", groups["staged"]),
        ("modified", groups["modified"]),
        ("untracked", groups["untracked"]),
    ):
        if not items:
            continue
        hook_output(f"  [{label}] ({len(items)})", "info")
        for f in items:
            if listed >= MAX_UNCOMMITTED_FILES_DISPLAY:
                truncated = True
                break
            hook_output(f"    {f}", "info")
            listed += 1
        if truncated:
            break

    if truncated:
        remaining = total - listed
        hint = f"   ...還有 {remaining} 個未列出；完整清單請執行 git status --porcelain"
        hook_output(hint, "info")
        print(hint, file=sys.stderr)

    hook_output("[提示] 這些變更可能來自前 session 遺留或其他並行 session，commit 前請全量清點（PC-076）", "info")
    hook_output("", "info")


def main():
    logger = setup_hook_logging("branch-status-reminder")

    # 獲取當前分支
    current_branch = get_current_branch()
    if not current_branch:
        logger.warning("Unable to get current branch")
        return 0

    # 檢查是否在正確的 worktree 環境中
    if is_in_worktree() and is_allowed_branch(current_branch):
        logger.debug(f"正確 worktree 環境：{current_branch}，靜默")
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

        _report_uncommitted_changes(logger)

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

        # W13-011：情況 2 也須列未提交變更（PC-076 防護）
        _report_uncommitted_changes(logger)

        hook_output("建議使用 worktree 保持環境隔離：", "info")
        hook_output("  /worktree create <ticket-id>", "info")
        hook_output("", "info")
        logger.debug(f"Currently on development branch in main repo: {current_branch}")

    # 情況 3：在 worktree 但分支不符合 allowed pattern
    elif is_in_worktree() and not is_allowed_branch(current_branch):
        hook_output("[branch-status-reminder] 警告：worktree 分支異常", "warning")
        hook_output(f"當前分支：{current_branch}（detached 或不是預期分支）", "info")
        hook_output("", "info")

        # W13-011：情況 3 也須列未提交變更（PC-076 防護）
        _report_uncommitted_changes(logger)

        logger.warning(f"Worktree branch anomaly detected: {current_branch}")

    # 情況 4：其他異常（通常不會發生）
    else:
        hook_output(f"[branch-status-reminder] 提示：當前在 {current_branch}", "info")
        hook_output("", "info")

        # W13-011：情況 4 也須列未提交變更（PC-076 防護）
        _report_uncommitted_changes(logger)

        logger.debug(f"Current branch: {current_branch}")

    hook_output("=" * 60, "info")
    hook_output("", "info")

    return 0


if __name__ == "__main__":
    sys.exit(main())
