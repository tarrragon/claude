#!/usr/bin/env -S uv run --quiet --script
# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///

"""
Agent Commit Verification Hook - PostToolUse (Agent)

功能:
  1. Agent 完成工作後，檢查是否有未 commit 的變更。
     若偵測到未 commit 的修改，輸出警告提醒 PM 確認。
  2. 檢查 worktree 和 feature 分支是否有未合併到 main 的 commit。
  3. 根據代理人是否使用 worktree 隔離，條件性輸出 CWD 還原提醒。
  4. 輸出整合的「PM 立即動作」摘要，指引 PM 下一步操作。

觸發時機: Agent 工具完成後 (PostToolUse, matcher: Agent)
行為: 不阻擋（exit 0），僅在 additionalContext 輸出警告

來源:
  - PC-024 — 代理人完成實作但跳過 git commit，變更未持久化
  - 0.17.0-W5-005 — Worktree 代理人完成後主線程 Shell cwd 被污染
  - 0.17.3-W10-001 — feature 分支偵測 + CWD 條件化 + PM 立即動作摘要
Ticket: 0.2.0-W3-022, 0.17.0-W5-005, 0.17.3-W10-001
"""

import json
import logging
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from hook_utils import (
    setup_hook_logging,
    read_json_from_stdin,
    extract_tool_input,
    is_subagent_environment,
    get_project_root,
)

# ============================================================================
# 常數定義
# ============================================================================

HOOK_NAME = "agent-commit-verification-hook"
EXIT_SUCCESS = 0

# 預設輸出格式（靜默通過）
DEFAULT_OUTPUT = {
    "hookSpecificOutput": {
        "hookEventName": "PostToolUse"
    }
}

# Git 命令超時（秒）
GIT_STATUS_TIMEOUT = 5

# 顯示的最大未 commit 檔案數
MAX_FILES_DISPLAY = 15

# 排除的路徑前綴（不視為需要 commit 的變更）
EXCLUDED_PATH_PREFIXES = (
    ".claude/",
    "docs/",
)

# 訊息常數
MSG_SEPARATOR = "============================================================"
MSG_TITLE = "[Agent Commit 驗證警告]"
MSG_UNCOMMITTED_DETECTED = "偵測到代理人完成工作後有未 commit 的變更"
MSG_AGENT_DESCRIPTION = "代理人描述"
MSG_UNCOMMITTED_FILES = "未 commit 的檔案"
MSG_MORE_FILES = "... 還有 {} 個檔案"
MSG_SUGGESTED_ACTION = "建議動作"
MSG_SUGGESTION_REVIEW = "1. 確認變更內容是否符合預期"
MSG_SUGGESTION_COMMIT = '2. 執行 commit：git add <files> && git commit -m "feat: <description>"'
MSG_SUGGESTION_DISCARD = "3. 若不需要：git checkout -- <files>"

# cwd 還原提醒訊息（防止 worktree 代理人完成後 Shell cwd 被污染）
MSG_CWD_RESTORE_TITLE = "[Agent 完成 - 工作目錄還原提醒]"
MSG_CWD_RESTORE_BODY = (
    "Worktree 代理人完成後，主線程的 Bash Shell 工作目錄可能被污染到 worktree 路徑。\n"
    "後續的 git 操作（status/add/commit）會在錯誤的分支上執行。\n"
    "\n"
    "[強制] 執行下一個 Bash 命令前，先確認並還原工作目錄：\n"
    "  cd {project_root} && pwd && git branch --show-current"
)

# Worktree 合併提醒訊息（來源：0.17.2-W2-018）
MSG_WORKTREE_MERGE_TITLE = "[Worktree 合併提醒] 有未合併回 main 的 commit"
MSG_WORKTREE_MERGE_BODY = (
    "Agent 完成後，以下 worktree 有 commit 尚未合併回 main。\n"
    "請在進行下一步前先合併：\n"
)
MSG_WORKTREE_MERGE_SUGGESTION = "[強制] 合併後才能進行 ticket complete 或切換任務"

# Feature 分支未合併提醒訊息（來源：0.17.3-W10-001）
MSG_FEATURE_BRANCH_TITLE = "[Feature 分支提醒] 有未合併回 main 的 commit"
MSG_FEATURE_BRANCH_BODY = (
    "Agent 完成後，以下 feature 分支有 commit 尚未合併回 main。\n"
    "代理人的變更可能在這些分支上，請先合併再驗收：\n"
)

# PM 立即動作摘要訊息（來源：0.17.3-W10-001）
MSG_PM_ACTION_TITLE = "[PM 立即動作]"

# Feature 分支前綴（用於偵測代理人建立的分支）
FEATURE_BRANCH_PREFIXES = ("feat/", "feature/", "fix/", "refactor/")

# Hook error 摘要（來源：0.18.0-W4-003）
HOOK_ERROR_SCAN_MINUTES = 5
HOOK_ERROR_KEYWORDS = ("ERROR", "FAIL", "Exception", "Traceback", "TypeError", "NameError")
MSG_HOOK_ERROR_TITLE = "[Hook Error 摘要] 代理人執行期間偵測到 Hook 錯誤"
MSG_HOOK_ERROR_BODY = (
    "以下 Hook 在最近 {minutes} 分鐘內有錯誤記錄（可能影響代理人執行）：\n"
)


# ============================================================================
# 核心邏輯
# ============================================================================


def get_uncommitted_files(project_root: str, logger: logging.Logger) -> list[str]:
    """取得未 commit 的檔案清單（排除豁免路徑）

    Args:
        project_root: 專案根目錄路徑
        logger: Logger 實例

    Returns:
        list[str]: 未 commit 的檔案路徑清單
    """
    try:
        result = subprocess.run(
            ["git", "--no-optional-locks", "status", "--porcelain"],
            capture_output=True,
            text=True,
            timeout=GIT_STATUS_TIMEOUT,
            cwd=project_root,
        )
        if result.returncode != 0:
            logger.warning("git status failed: %s", result.stderr.strip())
            return []

        files = []
        for line in result.stdout.strip().splitlines():
            if len(line) < 4:
                continue
            # git status --porcelain 格式: XY filename
            file_path = line[3:].strip()
            # 排除豁免路徑
            if any(file_path.startswith(prefix) for prefix in EXCLUDED_PATH_PREFIXES):
                continue
            files.append(file_path)
        return files

    except subprocess.TimeoutExpired:
        logger.warning("git status timeout")
        return []
    except FileNotFoundError:
        logger.warning("git not found")
        return []


def build_warning_message(
    agent_description: str,
    uncommitted_files: list[str],
) -> str:
    """建構警告訊息

    Args:
        agent_description: 代理人的描述
        uncommitted_files: 未 commit 的檔案清單

    Returns:
        str: 格式化的警告訊息
    """
    lines = [
        MSG_SEPARATOR,
        MSG_TITLE,
        MSG_SEPARATOR,
        "",
        MSG_UNCOMMITTED_DETECTED,
        "",
        f"{MSG_AGENT_DESCRIPTION}: {agent_description}",
        "",
        f"{MSG_UNCOMMITTED_FILES} ({len(uncommitted_files)} 個):",
    ]

    display_count = min(len(uncommitted_files), MAX_FILES_DISPLAY)
    for file_path in uncommitted_files[:display_count]:
        lines.append(f"  - {file_path}")

    remaining = len(uncommitted_files) - display_count
    if remaining > 0:
        lines.append(f"  {MSG_MORE_FILES.format(remaining)}")

    lines.extend([
        "",
        f"{MSG_SUGGESTED_ACTION}:",
        f"  {MSG_SUGGESTION_REVIEW}",
        f"  {MSG_SUGGESTION_COMMIT}",
        f"  {MSG_SUGGESTION_DISCARD}",
        MSG_SEPARATOR,
    ])

    return "\n".join(lines)


def get_unmerged_worktrees(project_root: str, logger: logging.Logger) -> list[tuple[str, str, list[str]]]:
    """取得有未合併 commit 的 worktree 清單

    Args:
        project_root: 專案根目錄路徑
        logger: Logger 實例

    Returns:
        list[tuple[str, str, list[str]]]: [(路徑, 分支, [commit 摘要])]
    """
    try:
        result = subprocess.run(
            ["git", "worktree", "list", "--porcelain"],
            capture_output=True, text=True, timeout=GIT_STATUS_TIMEOUT,
            cwd=project_root,
        )
        if result.returncode != 0:
            return []
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return []

    # 解析 worktree 清單
    worktrees = []
    current_path = None
    current_branch = None
    for line in result.stdout.splitlines():
        if line.startswith("worktree "):
            current_path = line[len("worktree "):]
        elif line.startswith("branch "):
            current_branch = line[len("branch refs/heads/"):]
        elif line == "":
            if current_path and current_branch and current_branch not in ("main", "master"):
                worktrees.append((current_path, current_branch))
            current_path = None
            current_branch = None
    if current_path and current_branch and current_branch not in ("main", "master"):
        worktrees.append((current_path, current_branch))

    # 檢查每個 worktree 是否有未合併 commit
    unmerged = []
    for wt_path, branch in worktrees:
        try:
            log_result = subprocess.run(
                ["git", "log", f"main..{branch}", "--oneline"],
                capture_output=True, text=True, timeout=GIT_STATUS_TIMEOUT,
                cwd=project_root,
            )
            if log_result.returncode == 0 and log_result.stdout.strip():
                commits = [l for l in log_result.stdout.strip().splitlines() if l]
                if commits:
                    unmerged.append((wt_path, branch, commits))
        except (subprocess.TimeoutExpired, FileNotFoundError):
            continue

    return unmerged


def build_worktree_merge_message(
    unmerged: list[tuple[str, str, list[str]]],
) -> str:
    """建構 worktree 合併提醒訊息"""
    lines = [
        MSG_SEPARATOR,
        MSG_WORKTREE_MERGE_TITLE,
        MSG_SEPARATOR,
        "",
        MSG_WORKTREE_MERGE_BODY,
    ]

    for wt_path, branch, commits in unmerged:
        lines.append(f"  [{branch}] {len(commits)} 個 commit 待合併")
        lines.append(f"  路徑: {wt_path}")
        for c in commits[:5]:
            lines.append(f"    - {c}")
        if len(commits) > 5:
            lines.append(f"    ... 還有 {len(commits) - 5} 個")
        lines.append(f"  建議: git merge {branch} --no-edit")
        lines.append("")

    lines.append(MSG_WORKTREE_MERGE_SUGGESTION)
    lines.append(MSG_SEPARATOR)
    return "\n".join(lines)


def get_unmerged_feature_branches(
    project_root: str,
    logger: logging.Logger,
    worktree_branches: set[str] | None = None,
) -> list[tuple[str, list[str]]]:
    """取得有未合併 commit 的 feature 分支清單（排除 worktree 分支避免重複）

    Args:
        project_root: 專案根目錄路徑
        logger: Logger 實例
        worktree_branches: 已被 worktree 偵測涵蓋的分支名稱集合

    Returns:
        list[tuple[str, list[str]]]: [(分支名, [commit 摘要])]
    """
    if worktree_branches is None:
        worktree_branches = set()

    try:
        result = subprocess.run(
            ["git", "branch", "--format=%(refname:short)"],
            capture_output=True, text=True, timeout=GIT_STATUS_TIMEOUT,
            cwd=project_root,
        )
        if result.returncode != 0:
            return []
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return []

    unmerged = []
    for branch in result.stdout.strip().splitlines():
        branch = branch.strip()
        if not branch or branch in ("main", "master"):
            continue
        # 跳過已被 worktree 偵測涵蓋的分支
        if branch in worktree_branches:
            continue
        # 只偵測 feature 相關分支
        if not any(branch.startswith(prefix) for prefix in FEATURE_BRANCH_PREFIXES):
            continue

        try:
            log_result = subprocess.run(
                ["git", "log", f"main..{branch}", "--oneline"],
                capture_output=True, text=True, timeout=GIT_STATUS_TIMEOUT,
                cwd=project_root,
            )
            if log_result.returncode == 0 and log_result.stdout.strip():
                commits = [line for line in log_result.stdout.strip().splitlines() if line]
                if commits:
                    unmerged.append((branch, commits))
        except (subprocess.TimeoutExpired, FileNotFoundError):
            continue

    return unmerged


def build_feature_branch_message(
    unmerged: list[tuple[str, list[str]]],
) -> str:
    """建構 feature 分支合併提醒訊息"""
    lines = [
        MSG_SEPARATOR,
        MSG_FEATURE_BRANCH_TITLE,
        MSG_SEPARATOR,
        "",
        MSG_FEATURE_BRANCH_BODY,
    ]

    for branch, commits in unmerged:
        lines.append(f"  [{branch}] {len(commits)} 個 commit 待合併")
        for c in commits[:5]:
            lines.append(f"    - {c}")
        if len(commits) > 5:
            lines.append(f"    ... 還有 {len(commits) - 5} 個")
        lines.append(f"  建議: git checkout main && git merge {branch} --no-edit")
        lines.append("")

    lines.append(MSG_SEPARATOR)
    return "\n".join(lines)


def build_pm_action_summary(
    project_root: str,
    has_uncommitted: bool,
    has_unmerged_worktrees: bool,
    has_unmerged_branches: bool,
    unmerged_branch_name: str | None = None,
) -> str:
    """建構 PM 立即動作摘要（根據偵測狀態動態生成）"""
    lines = [
        MSG_SEPARATOR,
        MSG_PM_ACTION_TITLE,
        MSG_SEPARATOR,
        "",
    ]

    step = 1
    # 一律建議確認工作目錄
    lines.append(f"{step}. 確認工作目錄: cd {project_root} && pwd && git branch --show-current")
    step += 1

    if has_uncommitted:
        lines.append(f"{step}. 確認變更後 commit: git add <files> && git commit -m \"...\"")
        step += 1

    if has_unmerged_worktrees or has_unmerged_branches:
        branch_hint = f" {unmerged_branch_name}" if unmerged_branch_name else " <branch>"
        lines.append(f"{step}. 合併到 main: git checkout main && git merge{branch_hint} --no-edit")
        step += 1

    lines.append(f"{step}. 驗證: npm test")
    lines.append("")
    lines.append(MSG_SEPARATOR)
    return "\n".join(lines)


def build_cwd_restore_message(project_root: str) -> str:
    """建構工作目錄還原提醒訊息

    Args:
        project_root: 專案根目錄路徑

    Returns:
        str: 格式化的還原提醒訊息
    """
    lines = [
        MSG_SEPARATOR,
        MSG_CWD_RESTORE_TITLE,
        MSG_SEPARATOR,
        "",
        MSG_CWD_RESTORE_BODY.format(project_root=project_root),
        MSG_SEPARATOR,
    ]
    return "\n".join(lines)


def scan_hook_errors(project_root: str, minutes: int, logger: logging.Logger) -> list[tuple[str, int]]:
    """掃描 hook-logs 目錄，找出最近 N 分鐘內含有錯誤的 Hook

    Args:
        project_root: 專案根目錄路徑
        minutes: 掃描的時間範圍（分鐘）
        logger: Logger 實例

    Returns:
        list[tuple[str, int]]: [(Hook 名稱, 錯誤數量)] 清單
    """
    import os
    import time

    hook_logs_dir = Path(project_root) / ".claude" / "hook-logs"
    if not hook_logs_dir.is_dir():
        logger.debug("hook-logs directory not found")
        return []

    cutoff_time = time.time() - (minutes * 60)
    error_counts: dict[str, int] = {}

    try:
        for hook_dir in hook_logs_dir.iterdir():
            if not hook_dir.is_dir():
                continue
            hook_name = hook_dir.name
            for log_file in hook_dir.glob("*.log"):
                try:
                    if log_file.stat().st_mtime < cutoff_time:
                        continue
                    content = log_file.read_text(encoding="utf-8", errors="ignore")
                    if any(kw in content for kw in HOOK_ERROR_KEYWORDS):
                        error_counts[hook_name] = error_counts.get(hook_name, 0) + 1
                except OSError:
                    continue
    except OSError as e:
        logger.info(f"hook-logs scan failed (non-blocking): {e}")
        return []

    result = sorted(error_counts.items(), key=lambda x: x[1], reverse=True)
    if result:
        logger.info(f"found hook errors in {len(result)} hooks (last {minutes} min)")
    return result


def build_hook_error_message(hook_errors: list[tuple[str, int]]) -> str:
    """建構 Hook error 摘要訊息

    Args:
        hook_errors: [(Hook 名稱, 錯誤數量)] 清單

    Returns:
        str: 格式化的摘要訊息
    """
    lines = [
        MSG_SEPARATOR,
        MSG_HOOK_ERROR_TITLE,
        MSG_SEPARATOR,
        "",
        MSG_HOOK_ERROR_BODY.format(minutes=HOOK_ERROR_SCAN_MINUTES),
    ]
    for hook_name, count in hook_errors[:10]:
        lines.append(f"  - {hook_name}: {count} 個錯誤記錄")
    if len(hook_errors) > 10:
        lines.append(f"  ... 還有 {len(hook_errors) - 10} 個 Hook")
    lines.append("")
    lines.append("建議：檢查 .claude/hook-logs/ 確認錯誤是否影響代理人執行。")
    lines.append(MSG_SEPARATOR)
    return "\n".join(lines)


def main() -> None:
    """主函式"""
    logger = setup_hook_logging(HOOK_NAME)

    input_data = read_json_from_stdin(logger)

    # 子代理人環境不觸發（避免巢狀警告）
    if is_subagent_environment(input_data):
        logger.debug("subagent environment, skip")
        print(json.dumps(DEFAULT_OUTPUT))
        sys.exit(EXIT_SUCCESS)
    if not input_data:
        logger.debug("no input data")
        print(json.dumps(DEFAULT_OUTPUT))
        sys.exit(EXIT_SUCCESS)

    tool_input = extract_tool_input(input_data, logger)

    # 取得代理人描述
    agent_description = tool_input.get("description", "unknown")

    # 取得專案根目錄（使用 CLAUDE_PROJECT_DIR 環境變數，確保是主倉庫而非 worktree）
    project_root = get_project_root()

    # 判斷代理人是否使用 worktree 隔離
    agent_uses_worktree = tool_input.get("isolation") == "worktree"

    # 檢查未 commit 的檔案
    uncommitted_files = get_uncommitted_files(str(project_root), logger)

    # 建構訊息
    messages = []
    has_uncommitted = False
    has_unmerged_worktrees = False
    has_unmerged_branches = False
    first_unmerged_branch = None

    if uncommitted_files:
        has_uncommitted = True
        logger.info(
            "uncommitted files detected after agent: %s (%d files)",
            agent_description,
            len(uncommitted_files),
        )
        messages.append(build_warning_message(agent_description, uncommitted_files))

        # 同時輸出到 stderr（雙通道可觀測性）
        sys.stderr.write(f"[{HOOK_NAME}] {MSG_UNCOMMITTED_DETECTED}\n")
    else:
        logger.debug("no uncommitted files after agent completed")

    # 檢查 worktree 未合併 commit（來源：0.17.2-W2-018）
    unmerged_worktrees = get_unmerged_worktrees(str(project_root), logger)
    worktree_branch_names = {branch for _, branch, _ in unmerged_worktrees}
    if unmerged_worktrees:
        has_unmerged_worktrees = True
        first_unmerged_branch = unmerged_worktrees[0][1]
        total_commits = sum(len(c) for _, _, c in unmerged_worktrees)
        logger.warning(
            "unmerged worktrees detected: %d worktrees, %d commits",
            len(unmerged_worktrees), total_commits,
        )
        messages.append(build_worktree_merge_message(unmerged_worktrees))

    # 檢查 feature 分支未合併 commit（來源：0.17.3-W10-001）
    unmerged_branches = get_unmerged_feature_branches(
        str(project_root), logger, worktree_branch_names,
    )
    if unmerged_branches:
        has_unmerged_branches = True
        if not first_unmerged_branch:
            first_unmerged_branch = unmerged_branches[0][0]
        total_commits = sum(len(c) for _, c in unmerged_branches)
        logger.warning(
            "unmerged feature branches detected: %d branches, %d commits",
            len(unmerged_branches), total_commits,
        )
        messages.append(build_feature_branch_message(unmerged_branches))

    # CWD 還原提醒：只在 worktree 代理人時顯示（來源：0.17.3-W10-001）
    if agent_uses_worktree:
        messages.append(build_cwd_restore_message(str(project_root)))
        logger.info("cwd restore reminder appended (worktree agent, project_root=%s)", project_root)
    else:
        logger.debug("cwd restore reminder skipped (non-worktree agent)")

    # Hook error 摘要（來源：0.18.0-W4-003）
    hook_errors = scan_hook_errors(str(project_root), HOOK_ERROR_SCAN_MINUTES, logger)
    if hook_errors:
        messages.append(build_hook_error_message(hook_errors))

    # PM 立即動作摘要（來源：0.17.3-W10-001）
    if has_uncommitted or has_unmerged_worktrees or has_unmerged_branches:
        messages.append(build_pm_action_summary(
            str(project_root),
            has_uncommitted,
            has_unmerged_worktrees,
            has_unmerged_branches,
            first_unmerged_branch,
        ))

    combined_message = "\n\n".join(messages)

    output = {
        "hookSpecificOutput": {
            "hookEventName": "PostToolUse",
            "additionalContext": combined_message,
        }
    }
    print(json.dumps(output))
    sys.exit(EXIT_SUCCESS)


if __name__ == "__main__":
    main()
