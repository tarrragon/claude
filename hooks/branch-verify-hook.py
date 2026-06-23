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

重構紀錄:
- 遷移至統一日誌系統 (hook_utils)

修改紀錄:
- 將保護分支決策從 "ask" 改為 "deny"（預防 Edit 操作在保護分支上執行）
- 優化 block 訊息，包含詳細的分支切換指引
- 移除未使用的 worktree_info 變數
- 新增路徑豁免邏輯（.claude/, docs/, CLAUDE.md, README.md 在保護分支上允許編輯）
- 新增 is_exempt_path_on_protected_branch() 函式
- 在保護分支上，豁免路徑不阻止編輯
- 強化 worktree 環境支援：當檔案路徑無法推導 cwd 時，嘗試從 CLAUDE_PROJECT_DIR 推導
- 在 feat/* 分支上，所有路徑檢查均跳過（明確 early return）
"""

import os
import sys
from pathlib import Path
from typing import Optional

# 添加 lib 目錄到路徑
sys.path.insert(0, str(Path(__file__).parent))
sys.path.insert(0, str(Path(__file__).parent.parent))

from lib.git_utils import (
    get_current_branch,
    get_project_root,
    is_protected_branch,
    is_allowed_branch,
    generate_worktree_info,
    find_target_repo,
)
from lib.hook_io import (
    read_hook_input,
    write_hook_output,
    create_pretooluse_output,
)
from hook_utils import setup_hook_logging, run_hook_safely


# 跨專案豁免清單（W17-149）：當目標檔案不在本專案 repo 時，使用通用清單
# 不使用本專案約定的 .claude/、docs/ 等前綴（那是 book_overview_v1 約定，外部 repo 不適用）
GENERIC_EXEMPT_EXACT = [
    "README.md",
    "CHANGELOG.md",
    ".gitignore",
    ".gitattributes",
]


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


def _is_same_repo(target_repo: Optional[str], host_root: str) -> bool:
    """判斷 target_repo 是否與 host project 相同。"""
    if not target_repo:
        return True  # 無法判斷時視為同 repo（保守，套用本專案豁免）
    return os.path.realpath(target_repo) == os.path.realpath(host_root)


def is_exempt_path_on_protected_branch(
    file_path: str,
    cwd: "str | None" = None,
    target_repo: "str | None" = None,
) -> bool:
    """
    判斷此路徑是否在保護分支上被豁免（允許編輯）

    W17-149: 區分 same-repo（本專案豁免清單）vs cross-repo（通用豁免清單）

    Args:
        file_path: 要編輯的檔案路徑
        cwd: 用於 host project 偵測的 cwd
        target_repo: 目標檔案所屬的 repo 根目錄（從 find_target_repo 取得）

    Returns:
        bool: True 表示豁免（允許編輯），False 表示不豁免
    """
    host_root = get_project_root(cwd=cwd)
    same_repo = _is_same_repo(target_repo, host_root)

    if not same_repo:
        # 跨專案：使用通用豁免清單（不套用 .claude/、docs/ 等本專案約定）
        # 計算相對於目標 repo 的路徑
        if target_repo and file_path.startswith(target_repo):
            normalized = file_path[len(target_repo):].lstrip("/")
        else:
            normalized = file_path.lstrip("/") if file_path.startswith("/") else file_path
        return normalized in GENERIC_EXEMPT_EXACT

    # Same repo：使用本專案豁免清單
    exempt_prefixes = [
        ".claude/",
        "docs/",
        "scripts/experiments/",  # 實驗一次性腳本（W15-023，對應 docs/experiments/ 報告）
    ]
    exempt_exact = [
        "CLAUDE.md",
        "README.md",
        "CHANGELOG.md",
        "package.json",
        "manifest.json",
        ".gitignore",  # repo 層級忽略清單（W10-033）
        ".gitattributes",  # repo 層級檔案屬性（W10-054.1.1）
    ]

    # 非專案檔案（不在 host_root 內）一律豁免（保留原行為）
    if file_path.startswith("/") and not file_path.startswith(host_root):
        return True

    if file_path.startswith(host_root):
        normalized = file_path[len(host_root):].lstrip("/")
    else:
        normalized = file_path.lstrip("/")

    for prefix in exempt_prefixes:
        if normalized.startswith(prefix):
            return True
    return normalized in exempt_exact


def build_cross_repo_deny_message(
    file_path: str,
    target_repo: str,
    target_branch: str,
    suggested_branch: str = "feat/cross-repo-edit",
) -> str:
    """W17-149: 跨專案保護分支 deny 訊息，附目標 repo 切換指令。"""
    return f"""保護分支編輯被阻止（跨專案）

目標檔案位於外部 repo，且該 repo 當前在保護分支：
- 檔案路徑：{file_path}
- 目標 repo：{target_repo}
- 目標 branch：{target_branch}

跨專案豁免清單僅含通用文件（README.md / CHANGELOG.md / .gitignore / .gitattributes），
此檔案不在豁免清單內，需先切換到 feature 分支再編輯。

複製以下指令切換目標 repo 分支（在另一個 terminal 執行）：

  cd {target_repo}
  git status
  git checkout -b {suggested_branch}

完成切換後即可重試本次編輯。"""


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

        # W17-149: 偵測目標 repo，判斷是否跨專案
        target_repo = find_target_repo(file_path) if file_path and file_path.startswith("/") else None
        host_root = get_project_root()
        is_cross_repo = (
            target_repo is not None
            and os.path.realpath(target_repo) != os.path.realpath(host_root)
        )

        # 檢查是否為豁免路徑（在保護分支上允許編輯）
        if is_exempt_path_on_protected_branch(file_path, cwd=file_dir, target_repo=target_repo):
            logger.info(f"在保護分支 '{current_branch}' 上編輯豁免路徑 {file_path}，允許")
            output = create_pretooluse_output(
                "allow",
                f"在保護分支上編輯豁免路徑：{file_path}"
            )
            write_hook_output(output)
            return 0

        logger.info(f"在保護分支 '{current_branch}' 上嘗試編輯非豁免檔案 {file_path}，操作已阻止 (cross_repo={is_cross_repo})")

        if is_cross_repo:
            # W17-149: 跨專案保護分支：附目標 repo 切換指令
            deny_message = build_cross_repo_deny_message(
                file_path=file_path,
                target_repo=target_repo,
                target_branch=current_branch,
            )
            output = create_pretooluse_output("deny", deny_message)
            write_hook_output(output)
            return 0

        # 同 repo 路徑判斷
        project_root = host_root
        is_project_file = file_path.startswith(project_root) if file_path.startswith("/") else True

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
- CLAUDE.md、README.md、CHANGELOG.md """
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
