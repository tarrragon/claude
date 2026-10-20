#!/usr/bin/env -S uv run --quiet --script
# /// script
# requires-python = ">=3.11"
# dependencies = ["pyyaml"]
# ///
"""
Worktree 和分支檢查 Hook - PreToolUse Hook

功能: 在 git push/merge/cherry-pick 前，自動掃描所有 worktree 和未合併分支，
      並在 merge/cherry-pick 前比對主倉庫 HEAD 是否指向預期的合併目標分支。
防護措施: 避免遺漏其他 session 在不同 worktree 或 feature branch 上的進度，
          以及避免合併到錯誤的分支。

觸發時機: Bash 工具執行前，命令實際呼叫 git push/merge/cherry-pick（含 git -C 等全域選項；
          echo 或引號內字樣不觸發；無法解析時 fail-open 並記日誌）

行為:
  1. 執行 git worktree list 掃描所有 worktree
  2. 對每個 worktree（排除主倉庫）執行 git status --short 檢查未提交變更
  3. 執行 git branch --no-merged main 檢查未合併分支
  4. (merge/cherry-pick) 檢查主倉庫 HEAD 是否指向 main/master，不符時輸出 WARNING
  5. 有發現時：以 additionalContext 輸出 WARNING，列出所有未提交/未合併的詳情
  6. 無發現時：靜默通過
  7. 永遠 exit 0（不阻止操作，僅警告）
"""

import logging
import sys
import subprocess
from pathlib import Path
from dataclasses import dataclass
from typing import List, Tuple, Optional

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "hooks"))
sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

try:
    from lib.git_command_parse import contains_git_word, find_git_invocations
    from lib import (
        setup_hook_logging,
        run_hook_safely,
        read_hook_input,
        emit_model_reminder,
    )
except ImportError as e:
    print(f"[Hook Import Warning] {Path(__file__).name}: {e}", file=sys.stderr)
    # lib 不可用，僅用 stdlib 補寫檔案日誌（規則 4：stderr + 檔案雙通道）
    try:
        import os as _os
        from datetime import datetime as _dt
        _root = Path(_os.environ.get("CLAUDE_PROJECT_DIR") or Path(__file__).resolve().parents[4])
        _log_dir = _root / ".claude" / "hook-logs" / "worktree-branch-check"
        _log_dir.mkdir(parents=True, exist_ok=True)
        with open(_log_dir / f"worktree-branch-check-{_dt.now():%Y%m%d}.log", "a", encoding="utf-8") as _fh:
            _fh.write(f"{_dt.now():%Y-%m-%d %H:%M:%S} - worktree-branch-check - ERROR - lib import failed, fallback active: {e}\n")
    except Exception as _log_err:
        print(f"[Hook Import Warning] worktree-branch-check: log write failed: {_log_err}", file=sys.stderr)
    # Fallback: 最小化日誌設定，run_hook_safely 退化為直接呼叫（無 liveness 記錄）
    import logging
    def setup_hook_logging(name):
        return logging.getLogger(name)
    def run_hook_safely(main_func, hook_name, fail_closed=False):
        return main_func()
    def contains_git_word(command):
        return False  # 解析模組不可用：fail-open（匯入警告已輸出至 stderr）
    def find_git_invocations(command, subcommands, base_dir=None, scan=False):
        return []
    def emit_model_reminder(event, text, *, audience="all", input_data=None):
        return None
    def read_hook_input():
        import json
        try:
            return json.load(sys.stdin)
        except Exception:
            return {}


# ============================================================================
# 常數定義
# ============================================================================

HOOK_NAME = "worktree-branch-check"
EXIT_SUCCESS = 0

# Worktree 列表相關常數
WORKTREE_PREFIX = "worktree "
HEAD_PREFIX = "HEAD "
DETACHED_PREFIX = "detached"
BRANCH_PREFIX = "branch "

# Git 命令超時（秒）
GIT_COMMAND_TIMEOUT = 10

# 預期的合併目標分支名稱
EXPECTED_TARGET_BRANCHES = ("main", "master")

# 以共用命令解析辨識的 git 子命令
MERGE_SUBCOMMANDS = frozenset({"merge", "cherry-pick"})
CHECKED_SUBCOMMANDS = MERGE_SUBCOMMANDS | {"push"}

# 目標分支比對警告訊息
TARGET_BRANCH_WARNING_HEADER = "[WARNING] 主倉庫 HEAD 未指向預期的合併目標分支"
TARGET_BRANCH_WARNING_CURRENT = "  當前分支: {current_branch}"
TARGET_BRANCH_WARNING_EXPECTED = "  預期分支: main 或 master"
TARGET_BRANCH_WARNING_SUGGESTION = "  建議執行: git checkout main"


# ============================================================================
# 資料結構
# ============================================================================

@dataclass
class WorktreeInfo:
    """Worktree 資訊"""
    path: str          # worktree 絕對路徑
    branch: str        # 當前分支名稱（或 detached）
    is_main: bool      # 是否為主倉庫
    uncommitted_count: int = 0  # 未提交變更數量


@dataclass
class CheckResult:
    """檢查結果"""
    has_uncommitted_worktrees: bool
    has_unmerged_branches: bool
    uncommitted_worktrees: List[WorktreeInfo]
    unmerged_branches: List[str]


# ============================================================================
# 主要邏輯
# ============================================================================

def run_git_command(args: List[str], cwd: Optional[str] = None) -> Tuple[bool, str]:
    """
    執行 git 命令

    Args:
        args: git 命令參數（不含 'git' 前綴）
        cwd: 執行目錄

    Returns:
        (success, output)
    """
    try:
        cmd = ["git"] + args
        result = subprocess.run(
            cmd,
            cwd=cwd,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=GIT_COMMAND_TIMEOUT
        )
        return (result.returncode == 0, result.stdout.strip())
    except subprocess.TimeoutExpired:
        logging.getLogger("worktree-branch-check").warning(
            f"run_git_command 逾時: git {' '.join(args[:3])} (timeout {GIT_COMMAND_TIMEOUT}s)"
        )
        return False, "timeout"
    except Exception as e:
        logging.getLogger("worktree-branch-check").warning(
            f"run_git_command 失敗: git {' '.join(args[:3])} ({type(e).__name__}: {e})"
        )
        return False, str(e)


def get_worktree_list() -> List[WorktreeInfo]:
    """
    獲取所有 worktree 列表

    git worktree list --porcelain 輸出格式：
    worktree /path/to/main
    HEAD abc123...
    branch refs/heads/main

    worktree /path/to/worktree1
    HEAD def456...
    branch refs/heads/feat/ticket-123
    ...

    Returns:
        List[WorktreeInfo]
    """
    success, output = run_git_command(["worktree", "list", "--porcelain"])
    if not success or not output:
        return []

    worktrees = []
    lines = output.split('\n')
    i = 0

    while i < len(lines):
        line = lines[i].strip()

        # 解析 worktree 路徑
        if line.startswith(WORKTREE_PREFIX):
            path = line[len(WORKTREE_PREFIX):]

            # 初始化分支資訊
            branch = "unknown"

            # 掃描接下來的行直到找到 branch 或 detached
            j = i + 1
            while j < len(lines):
                next_line = lines[j].strip()

                if next_line.startswith(BRANCH_PREFIX):
                    branch_full = next_line[len(BRANCH_PREFIX):]
                    # 提取分支名稱（移除 refs/heads/ 前綴）
                    if branch_full.startswith("refs/heads/"):
                        branch = branch_full[len("refs/heads/"):]
                    else:
                        branch = branch_full
                    break

                elif "detached" in next_line:
                    branch = "detached"
                    break

                elif next_line.startswith(WORKTREE_PREFIX):
                    # 遇到下一個 worktree，停止掃描
                    break

                j += 1

            # is_main 依 git worktree list --porcelain 的輸出順序判定：git 保證
            # 主倉庫（primary working tree）永遠是第一筆條目，故 index==0 即為主倉庫。
            # 不可再依分支名推論——linked worktree 檢出 main/master 分支時，分支名
            # 推論會誤判該 worktree 為主倉庫，導致其未提交變更被靜默忽略（實測驗證）。
            is_main = len(worktrees) == 0

            worktree = WorktreeInfo(
                path=path,
                branch=branch,
                is_main=is_main,
                uncommitted_count=0
            )
            worktrees.append(worktree)
            i = j

        else:
            i += 1

    return worktrees


def get_uncommitted_count(worktree_path: str) -> int:
    """
    獲取 worktree 中的未提交變更數量

    Args:
        worktree_path: worktree 路徑

    Returns:
        未提交變更的檔案數量
    """
    success, output = run_git_command(["--no-optional-locks", "status", "--short"], cwd=worktree_path)
    if not success or not output:
        return 0

    # 統計非空行數
    return len([line for line in output.split('\n') if line.strip()])


def get_unmerged_branches() -> List[str]:
    """
    獲取未合併到 main 的分支列表

    Returns:
        未合併分支名稱列表
    """
    # plumbing 輸出不含 porcelain 的 '* ' / '+ ' 前綴（worktree checkout 分支）
    success, output = run_git_command([
        "for-each-ref", "--no-merged=main",
        "--format=%(refname:short)", "refs/heads",
    ])
    if not success or not output:
        return []

    return [line.strip() for line in output.split('\n') if line.strip()]


def check_git_state() -> CheckResult:
    """
    檢查所有 worktree 和未合併分支的狀態

    Returns:
        CheckResult 物件
    """
    # 獲取 worktree 列表
    worktrees = get_worktree_list()

    # 檢查每個 worktree 的未提交變更（排除主倉庫）
    uncommitted_worktrees = []
    for wt in worktrees:
        # 排除主倉庫（primary working tree，由 is_main 依 worktree list 順序判定）。
        # 不可再併入 wt.branch in ["main", "master"] 分支名判準——is_main 改為順序法
        # 後，若保留分支名 OR 條件，linked worktree 檢出 main 分支時仍會被此條件
        # 排除，等同讓修正失效（分支名判準才是漏報的根因，見上方 is_main 賦值註解）。
        if wt.is_main:
            continue

        uncommitted_count = get_uncommitted_count(wt.path)
        if uncommitted_count > 0:
            wt.uncommitted_count = uncommitted_count
            uncommitted_worktrees.append(wt)

    # 獲取未合併分支（來自主倉庫 git worktree，即 is_main=True 的那個）
    unmerged_branches = get_unmerged_branches()

    return CheckResult(
        has_uncommitted_worktrees=len(uncommitted_worktrees) > 0,
        has_unmerged_branches=len(unmerged_branches) > 0,
        uncommitted_worktrees=uncommitted_worktrees,
        unmerged_branches=unmerged_branches
    )


def format_warning_output(result: CheckResult) -> str:
    """
    格式化警告輸出

    Args:
        result: CheckResult 物件

    Returns:
        格式化的警告訊息
    """
    lines = []
    lines.append("[WARNING] 偵測到未合併的 worktree/分支進度")
    lines.append("=" * 60)

    # 未提交變更的 Worktree
    if result.uncommitted_worktrees:
        lines.append(f"未提交變更的 Worktree ({len(result.uncommitted_worktrees)}):")
        for wt in result.uncommitted_worktrees:
            # 提取 worktree 名稱（路徑最後一個部分）
            wt_name = Path(wt.path).name if wt.path else "unknown"
            file_word = "個未追蹤檔案"
            lines.append(f"  - {wt_name} [{wt.branch}]: {wt.uncommitted_count} {file_word}")
        lines.append("")

    # 未合併分支
    if result.unmerged_branches:
        lines.append(f"未合併分支 ({len(result.unmerged_branches)}):")
        for branch in result.unmerged_branches:
            lines.append(f"  - {branch}")
        lines.append("")

    lines.append("建議：先處理這些變更再推送，避免遺漏進度")
    lines.append("=" * 60)

    return "\n".join(lines)


def extract_command(bash_command: str) -> str:
    """
    從 Bash 命令中提取核心命令

    Args:
        bash_command: 完整 Bash 命令

    Returns:
        核心命令部分
    """
    return bash_command.strip().split()[0] if bash_command else ""


def _find_invocations(bash_command: str, subcommands) -> list:
    """以共用解析找出指定子命令的 git 呼叫；無法解析時 fail-open 回空清單並記日誌。"""
    if not contains_git_word(bash_command):
        return []
    invocations = find_git_invocations(bash_command, subcommands)
    if invocations is None:
        logging.getLogger("worktree-branch-check").warning(
            f"無法解析命令（長度 {len(bash_command)}），fail-open 不檢查"
        )
        return []
    return invocations


def is_merge_or_cherry_pick(bash_command: str) -> bool:
    """判斷命令是否實際呼叫 git merge 或 git cherry-pick（含 git -C 等全域選項形式）。"""
    return bool(_find_invocations(bash_command, MERGE_SUBCOMMANDS))


def should_check_git_operation(bash_command: str) -> bool:
    """判斷是否應執行 worktree/分支檢查（實際呼叫 push、merge 或 cherry-pick）。"""
    return bool(_find_invocations(bash_command, CHECKED_SUBCOMMANDS))


def check_target_branch() -> Optional[str]:
    """
    檢查主倉庫 HEAD 是否指向預期的合併目標分支（main 或 master）

    Returns:
        不符時回傳警告訊息，符合時回傳 None
    """
    success, current_branch = run_git_command(["symbolic-ref", "--short", "HEAD"])
    if not success:
        # detached HEAD 或其他異常，不阻止
        return None

    if current_branch in EXPECTED_TARGET_BRANCHES:
        return None

    lines = [
        TARGET_BRANCH_WARNING_HEADER,
        "=" * 60,
        TARGET_BRANCH_WARNING_CURRENT.format(current_branch=current_branch),
        TARGET_BRANCH_WARNING_EXPECTED,
        TARGET_BRANCH_WARNING_SUGGESTION,
        "=" * 60,
    ]
    return "\n".join(lines)


def main() -> int:
    """Hook 主邏輯"""
    logger = setup_hook_logging("worktree-branch-check")

    # 解析 PreToolUse payload，比對對象僅限 tool_input.command
    # 解析失敗或無命令時 fail-open 靜默通過
    payload = read_hook_input() if not sys.stdin.isatty() else {}
    tool_input = payload.get("tool_input") if isinstance(payload, dict) else None
    command = tool_input.get("command") if isinstance(tool_input, dict) else None
    bash_command = command.strip() if isinstance(command, str) else ""

    if not bash_command:
        logger.warning("無法從 payload 取得 tool_input.command，靜默通過")
        return EXIT_SUCCESS

    # 判斷是否應執行檢查
    if not should_check_git_operation(bash_command):
        logger.debug(f"命令（長度 {len(bash_command)}）不需要 worktree 檢查，靜默通過")
        return EXIT_SUCCESS

    logger.info("偵測到 push/merge/cherry-pick 命令，執行 worktree 和分支檢查")

    # 兩類警告合併為單一 additionalContext 輸出（hook 只能輸出一份 JSON）
    warnings: List[str] = []

    # 目標分支比對（僅 merge/cherry-pick，push 不需要）
    if is_merge_or_cherry_pick(bash_command):
        target_warning = check_target_branch()
        if target_warning:
            warnings.append(target_warning)
            logger.warning("主倉庫 HEAD 未指向預期的合併目標分支")

    # 執行 worktree 和未合併分支檢查
    result = check_git_state()

    # 如果有發現，收集警告
    if result.has_uncommitted_worktrees or result.has_unmerged_branches:
        warnings.append(format_warning_output(result))
        logger.warning(f"偵測到未合併進度：{len(result.uncommitted_worktrees)} 個 worktree，{len(result.unmerged_branches)} 個分支")
    else:
        # 無發現，靜默通過
        logger.debug("無未提交或未合併進度，靜默通過")

    if warnings:
        # 提醒對象是模型，走 additionalContext（exit 0 stderr 對模型不可見）
        emit_model_reminder(
            "PreToolUse", "\n\n".join(warnings), input_data=payload
        )

    # 永遠 exit 0，不阻止操作
    return EXIT_SUCCESS


if __name__ == "__main__":
    sys.exit(run_hook_safely(main, HOOK_NAME))
