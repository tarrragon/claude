#!/usr/bin/env python3
# /// script
# requires-python = ">=3.9"
# dependencies = []
# ///
"""
Worktree Merge Reminder Hook - PostToolUse (Bash)

功能：當偵測到 ticket track complete 命令時，檢查所有 worktree：
1. 未合併（ahead>0）→ 推送 merge 警告（既有功能）
2. 已合併（ahead=0，含 user worktree）→ 推送 cleanup reminder（W11-033 / PC-149 新增）
   - dirty worktree 額外提示先處理變更

Hook 類型：PostToolUse
匹配工具：Bash
退出碼：0 = 通過（stdout 警告顯示給用戶），2 = 阻擋（stderr 回饋給 Claude）
"""

import json
import subprocess
import sys
from pathlib import Path
from typing import List, Optional, Tuple

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "hooks"))

from hook_utils import setup_hook_logging, run_hook_safely, read_json_from_stdin, is_subagent_environment


def parse_worktree_list(logger) -> List[Tuple[str, str]]:
    """解析 git worktree list，回傳 (路徑, 分支名) 列表（排除 main）。"""
    try:
        result = subprocess.run(
            ["git", "worktree", "list", "--porcelain"],
            capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=10
        )
    except (subprocess.TimeoutExpired, FileNotFoundError):
        logger.warning("git worktree list 執行失敗")
        return []

    if result.returncode != 0:
        logger.warning("git worktree list 非零退出碼: %d", result.returncode)
        return []

    worktrees = []
    current_path: Optional[str] = None
    current_branch: Optional[str] = None

    for line in result.stdout.splitlines():
        if line.startswith("worktree "):
            current_path = line[len("worktree "):]
        elif line.startswith("branch "):
            # branch refs/heads/feat/xxx -> feat/xxx
            ref = line[len("branch "):]
            current_branch = ref.replace("refs/heads/", "")
        elif line == "":
            # 空行分隔每個 worktree 條目
            if current_path and current_branch and current_branch not in ("main", "master"):
                worktrees.append((current_path, current_branch))
            current_path = None
            current_branch = None

    # 處理最後一個條目（porcelain 輸出末尾可能無空行）
    if current_path and current_branch and current_branch not in ("main", "master"):
        worktrees.append((current_path, current_branch))

    return worktrees


def get_unmerged_commits(branch: str, logger) -> List[str]:
    """取得分支相對於 main 的未合併 commit 摘要。"""
    try:
        result = subprocess.run(
            ["git", "log", f"main..{branch}", "--oneline"],
            capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=10
        )
    except (subprocess.TimeoutExpired, FileNotFoundError):
        logger.warning("git log main..%s 執行失敗", branch)
        return []

    if result.returncode != 0:
        logger.debug("git log main..%s 非零退出碼: %d", branch, result.returncode)
        return []

    commits = [line for line in result.stdout.strip().splitlines() if line]
    return commits


def is_worktree_dirty(path: str, logger) -> bool:
    """檢查 worktree 是否有未提交變更（含未追蹤檔案）。

    Args:
        path: worktree 絕對路徑
        logger: logger 實例

    Returns:
        True 表示 dirty（status --porcelain 非空），False 表示 clean 或無法判斷。
    """
    try:
        result = subprocess.run(
            ["git", "-C", path, "status", "--porcelain"],
            capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=10
        )
    except (subprocess.TimeoutExpired, FileNotFoundError):
        logger.warning("git -C %s status 執行失敗", path)
        return False

    if result.returncode != 0:
        logger.debug("git -C %s status 非零退出碼: %d", path, result.returncode)
        return False

    return bool(result.stdout.strip())


def is_ticket_complete_command(input_data: dict) -> bool:
    """判斷 Bash 輸出是否為 ticket track complete 命令。"""
    # 檢查工具輸入（命令本身）
    tool_input = input_data.get("tool_input", {})
    command = tool_input.get("command", "")

    if "ticket" in command and "complete" in command:
        return True

    return False


def main() -> int:
    """Hook 主邏輯。"""
    logger = setup_hook_logging("worktree-merge-reminder")

    try:
        input_data = read_json_from_stdin(logger)
    except (json.JSONDecodeError, EOFError):
        logger.warning("無法解析 stdin JSON")
        return 0

    if not input_data:
        return 0

    # subagent 環境跳過（代理人不執行 complete）
    if is_subagent_environment(input_data):
        return 0

    # 只在 ticket complete 命令時觸發
    if not is_ticket_complete_command(input_data):
        return 0

    logger.info("偵測到 ticket complete，檢查 worktree 合併狀態")

    worktrees = parse_worktree_list(logger)
    if not worktrees:
        logger.debug("無非 main 的 worktree")
        return 0

    # 分類：未合併 vs 已合併（ahead=0）
    unmerged = []
    merged = []  # (path, branch, dirty)
    for wt_path, branch in worktrees:
        commits = get_unmerged_commits(branch, logger)
        if commits:
            unmerged.append((wt_path, branch, commits))
        else:
            dirty = is_worktree_dirty(wt_path, logger)
            merged.append((wt_path, branch, dirty))

    if not unmerged and not merged:
        logger.info("所有 worktree 已合併且無需清理")
        return 0

    lines: List[str] = []

    # Section 1: 未合併警告（既有區塊）
    if unmerged:
        lines.append("[Worktree 合併提醒] 以下 worktree 有未合併回 main 的 commit：")
        lines.append("")
        for wt_path, branch, commits in unmerged:
            lines.append(f"  分支: {branch}")
            lines.append(f"  路徑: {wt_path}")
            lines.append(f"  待合併 commit: {len(commits)} 個")
            for commit in commits[:5]:
                lines.append(f"    - {commit}")
            if len(commits) > 5:
                lines.append(f"    ... 還有 {len(commits) - 5} 個")
            lines.append(f"  建議: git merge {branch} --no-edit")
            lines.append("")
        lines.append("請在 ticket 完成前合併這些 worktree 的變更。")
        if merged:
            lines.append("")

    # Section 2: 已合併 cleanup reminder（W11-033 / PC-149 新增）
    if merged:
        lines.append("[Worktree 清理提醒] 以下 worktree 已完全合併回 main，建議清理：")
        lines.append("")
        for wt_path, branch, dirty in merged:
            lines.append(f"  分支: {branch}")
            lines.append(f"  路徑: {wt_path}")
            if dirty:
                lines.append("  狀態: 未提交變更（dirty）— 請先處理未提交/未追蹤檔案再移除")
                lines.append(f"  建議: cd {wt_path} && git status   # 確認變更")
                lines.append(f"        git worktree remove {wt_path} --force   # 強制移除")
            else:
                lines.append("  狀態: clean")
                lines.append(f"  建議: git worktree remove {wt_path}")
            lines.append("")
        lines.append("PC-149: ticket 完成後 worktree 殘留會累積 disk 與視圖污染。")

    message = "\n".join(lines)
    output = {
        "hookSpecificOutput": {
            "hookEventName": "PostToolUse",
            "additionalContext": message
        }
    }
    print(json.dumps(output, ensure_ascii=False))
    if unmerged:
        logger.warning("發現 %d 個 worktree 有未合併 commit", len(unmerged))
    if merged:
        logger.info("發現 %d 個已合併 worktree 待清理", len(merged))

    # 回傳 0（警告但不阻擋），讓 PM 決定是否處理
    return 0


if __name__ == "__main__":
    sys.exit(run_hook_safely(main, "worktree-merge-reminder"))
