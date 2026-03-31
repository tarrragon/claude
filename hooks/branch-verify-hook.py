#!/usr/bin/env -S uv run --quiet --script
# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
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

修改紀錄 (0.1.1-W9-002.3):
- 新增路徑豁免邏輯（.claude/, docs/, CLAUDE.md, README.md 在保護分支上允許編輯）
- 新增 is_exempt_path_on_protected_branch() 函式
- 在保護分支上，豁免路徑不阻止編輯

修改紀錄 (0.16.2-W6-001):
- 強化 worktree 環境支援：當檔案路徑無法推導 cwd 時，嘗試從 CLAUDE_PROJECT_DIR 推導
- 在 feat/* 分支上，所有路徑檢查均跳過（明確 early return）
"""

import os
import sys
from pathlib import Path

# 添加 lib 目錄到路徑
sys.path.insert(0, str(Path(__file__).parent.parent / "lib"))
sys.path.insert(0, str(Path(__file__).parent))

from git_utils import (
    get_current_branch,
    get_project_root,
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


def _resolve_cwd_for_branch_detection(file_path: str) -> "str | None":
    """
    從檔案路徑推導用於分支偵測的工作目錄

    優先使用檔案所在目錄（支援 worktree 環境）。
    如果檔案路徑非絕對路徑，fallback 到 CLAUDE_PROJECT_DIR。

    Args:
        file_path: 被編輯的檔案路徑

    Returns:
        str | None: 用於 git 命令的工作目錄，None 表示使用預設 cwd
    """
    if file_path and file_path.startswith("/"):
        parent = str(Path(file_path).parent)
        # 如果父目錄存在，使用它；否則向上尋找存在的目錄
        check_dir = parent
        while check_dir and check_dir != "/" and not Path(check_dir).exists():
            check_dir = str(Path(check_dir).parent)
        if check_dir and check_dir != "/" and Path(check_dir).exists():
            return check_dir

    # Fallback: 使用 CLAUDE_PROJECT_DIR（可能是 worktree 路徑）
    project_dir = os.getenv("CLAUDE_PROJECT_DIR")
    if project_dir and Path(project_dir).exists():
        return project_dir

    return None


def is_exempt_path_on_protected_branch(file_path: str, cwd: str | None = None) -> bool:
    """
    判斷此路徑是否在保護分支上被豁免（允許編輯）

    適用場景：需要在 main 分支上更新規則、文件、Ticket 時

    邏輯：
    1. 如果 file_path 不在專案根目錄下（如 auto-memory 路徑），視為非專案檔案，直接豁免
    2. 如果 file_path 在專案根目錄下，檢查是否匹配豁免路徑前綴或精確路徑

    Args:
        file_path: 要編輯的檔案路徑

    Returns:
        bool: True 表示豁免（允許編輯），False 表示不豁免（需要 deny）

    Example:
        if is_exempt_path_on_protected_branch(".claude/rules/core/decision-tree.md"):
            print("Allowed to edit .claude/ files on main")
    """
    # 豁免的路徑字首
    exempt_prefixes = [
        ".claude/",
        "docs/",
    ]

    # 豁免的精確路徑
    exempt_exact = [
        "CLAUDE.md",
        "README.md",
    ]

    project_root = get_project_root(cwd=cwd)

    # 檢查 file_path 是否為絕對路徑且不在專案根目錄下
    # 非專案檔案（如 auto-memory）不受保護分支限制，直接豁免
    if file_path.startswith("/") and not file_path.startswith(project_root):
        return True

    # 正規化路徑：將絕對路徑轉為相對於專案根目錄的路徑
    # Edit 工具傳入絕對路徑（如 /Users/.../project/.claude/rules/...），
    # 需轉為相對路徑（.claude/rules/...）才能正確比對豁免前綴
    if file_path.startswith(project_root):
        normalized = file_path[len(project_root):].lstrip("/")
    else:
        # file_path 已是相對路徑或其他格式，直接使用
        normalized = file_path.lstrip("/")

    # 檢查字首
    for prefix in exempt_prefixes:
        if normalized.startswith(prefix):
            return True

    # 檢查精確匹配
    if normalized in exempt_exact:
        return True

    return False


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

    # 從被編輯檔案路徑推導 git repo context（支援 worktree 環境）
    file_path = tool_input.get("file_path", "")
    file_dir = _resolve_cwd_for_branch_detection(file_path)

    # 獲取當前分支
    current_branch = get_current_branch(cwd=file_dir)
    if not current_branch:
        logger.warning("無法獲取分支資訊，默認允許")
        output = create_pretooluse_output("allow", "無法獲取分支資訊，默認允許")
        write_hook_output(output)
        return 0

    # 檢查是否為允許的分支（feat/*, fix/* 等）
    # 在開發分支上，所有路徑均允許編輯，不需要進一步檢查
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

        # 檢查是否為豁免路徑（在保護分支上允許編輯）
        if is_exempt_path_on_protected_branch(file_path, cwd=file_dir):
            logger.info(f"在保護分支 '{current_branch}' 上編輯豁免路徑 {file_path}，允許")
            output = create_pretooluse_output(
                "allow",
                f"在保護分支上編輯豁免路徑：{file_path}"
            )
            write_hook_output(output)
            return 0

        # 判斷是否為專案檔案
        project_root = get_project_root(cwd=file_dir)
        is_project_file = file_path.startswith(project_root) if file_path.startswith("/") else True

        logger.info(f"在保護分支 '{current_branch}' 上嘗試編輯非豁免檔案 {file_path}，操作已阻止")

        if is_project_file:
            # 專案內的檔案
            deny_message = f"""保護分支編輯被阻止

對不起，當前在保護分支 '{current_branch}' 上，無法直接編輯檔案：
{file_path}

保護分支用於穩定開發，需要在獨立分支上進行更改。

建議的操作方式：

1. 建立 feature worktree（推薦）：
   /worktree create <ticket-id>

2. 或手動建立分支：
   git checkout -b feat/your-feature

豁免路徑（允許在保護分支上編輯）：
- .claude/ （規則、配置、Hook、方法論）
- docs/ （工作日誌、Ticket 檔案）
- CLAUDE.md、README.md """
        else:
            # 非專案檔案（應該不會發生，但保留說明）
            deny_message = f"""保護分支編輯被阻止

對不起，當前在保護分支 '{current_branch}' 上，無法編輯檔案：
{file_path}

此操作可能涉及系統檔案或外部 auto-memory 的特殊處理。
請切換到 feature 分支後重試。"""

        output = create_pretooluse_output("deny", deny_message)
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
