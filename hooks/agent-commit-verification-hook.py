#!/usr/bin/env -S uv run --quiet --script
# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///

"""
Agent Commit Verification Hook - SubagentStop

功能:
  1. Agent 真正完成後，檢查是否有未 commit 的變更。
  2. 檢查 worktree 和 feature 分支是否有未合併到 main 的 commit。
  3. 根據代理人是否使用 worktree 隔離，條件性輸出 CWD 還原提醒。
  4. 輸出整合的「PM 立即動作」摘要，指引 PM 下一步操作。
  5. 掃描 hook-logs 輸出 hook error 摘要。

觸發時機: SubagentStop（CC runtime 代理人真正停止時觸發，W10-067 遷移自 PostToolUse）
行為: 不阻擋（exit 0），有警告時以 top-level systemMessage（純顯示通道）輸出。
  無內容時靜默退出。
  自激迴圈防護（1.0.0-W1-055.1）：
  1. stop_hook_active=true（runtime 因 stop hook 而繼續）時靜默 exit 0（CC hook
     規格的防迴圈欄位）。
  2. Hook error 摘要以錯誤記錄 fingerprint 做 TTL 去重，相同錯誤集合在 TTL 內
     不重複播報（W1-074/075/076 觀測的重播症狀）。
  3. 輸出通道自 hookSpecificOutput.additionalContext 回退 systemMessage：W1-055
     ANA 活體確證 additionalContext 投遞對象是「停止中的 subagent」（注入其對話
     並令其繼續，H1 confidence 0.95），與本 hook「通知 PM 主線程」意圖不符。

來源:
  - PC-024 — 代理人完成實作但跳過 git commit，變更未持久化
  - W10-067 — 從 PostToolUse 遷移至 SubagentStop，解決 background 啟動誤觸發
  - 0.19.1-W1-046 — CC 2.1.163 解禁後曾改用 additionalContext（已由 W1-055.1 回退）
  - 1.0.0-W1-055.1 — 自激迴圈斷路器 + hook error fingerprint dedup + 通道回退
"""

import hashlib
import json
import logging
import re
import subprocess
import sys
import time
from pathlib import Path
from typing import Callable, NamedTuple

sys.path.insert(0, str(Path(__file__).parent))
sys.path.insert(0, str(Path(__file__).parent.parent))

from lib import (
    setup_hook_logging,
    read_json_from_stdin,
    get_project_root,
    get_worktree_list as shared_get_worktree_list,
    get_uncommitted_files as shared_get_uncommitted_files,
)

from lib.dispatch_tracker import get_active_dispatches

# ============================================================================
# 常數定義
# ============================================================================

HOOK_NAME = "agent-commit-verification-hook"
EXIT_SUCCESS = 0

# 預設輸出格式（靜默通過）
# 無內容時靜默退出（不輸出任何 JSON）；有警告時以 top-level systemMessage
# （純顯示通道）輸出。1.0.0-W1-055.1 自 additionalContext 回退：該欄位會注入
# 停止中的 subagent 並令其繼續（自激迴圈），與通知 PM 的意圖不符。

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

# Worktree 未提交變更警告訊息（0.2.1-W3-283，issue 46 症狀四驗收側）
MSG_WORKTREE_UNCOMMITTED_TITLE = "[Worktree 未提交警告] 以下 worktree 有未 commit 的變更"
MSG_WORKTREE_UNCOMMITTED_BODY = (
    "Agent 完成後，以下 worktree 內有未提交的變更（可能是未落地的產品碼）。\n"
    "分支 commit 歷史看不到這些內容，merge 後仍會遺漏：\n"
)
MSG_WORKTREE_UNCOMMITTED_SUGGESTION = "[強制] 確認內容並 commit 後才能進行 ticket complete 或驗收"

# Worktree 合併提醒訊息
MSG_WORKTREE_MERGE_TITLE = "[Worktree 合併提醒] 有未合併回 main 的 commit"
MSG_WORKTREE_MERGE_BODY = (
    "Agent 完成後，以下 worktree 有 commit 尚未合併回 main。\n"
    "請在進行下一步前先合併：\n"
)
MSG_WORKTREE_MERGE_SUGGESTION = "[強制] 合併後才能進行 ticket complete 或切換任務"

# Feature 分支未合併提醒訊息
MSG_FEATURE_BRANCH_TITLE = "[Feature 分支提醒] 有未合併回 main 的 commit"
MSG_FEATURE_BRANCH_BODY = (
    "Agent 完成後，以下 feature 分支有 commit 尚未合併回 main。\n"
    "代理人的變更可能在這些分支上，請先合併再驗收：\n"
)

# PM 立即動作摘要訊息
MSG_PM_ACTION_TITLE = "[PM 立即動作]"

# Feature 分支前綴（用於偵測代理人建立的分支）
FEATURE_BRANCH_PREFIXES = ("feat/", "feature/", "fix/", "refactor/")

# Hook error 摘要
HOOK_ERROR_SCAN_MINUTES = 5
# Hook error 摘要去重 TTL（1.0.0-W1-055.1 修復 2）：相同錯誤集合（fingerprint）
# 在 TTL 內只播報一次。TTL 取掃描視窗（5 分鐘）的兩倍，確保同一批錯誤記錄
# 在其可見視窗內不會二次播報；新錯誤出現會改變 fingerprint、立即播報。
HOOK_ERROR_DEDUP_TTL_SECONDS = HOOK_ERROR_SCAN_MINUTES * 60 * 2
# Log level 精確匹配：`[timestamp] LEVEL - message` 格式，僅 ERROR/CRITICAL/FATAL 視為錯誤
# 使用 regex 避免純字串匹配造成誤報（例如用戶命令字串含 "ERROR"/"FAIL"/"Exception" 關鍵字）
HOOK_ERROR_LOG_LEVEL_RE = re.compile(r"\] (ERROR|CRITICAL|FATAL) -")
# Python Traceback 標記（行首），同樣是真實 Hook 錯誤訊號
HOOK_ERROR_TRACEBACK_RE = re.compile(r"^Traceback \(most recent call last\):", re.MULTILINE)
MSG_HOOK_ERROR_TITLE = "[Hook Error 摘要] 代理人執行期間偵測到 Hook 錯誤"
MSG_HOOK_ERROR_BODY = (
    "以下 Hook 在最近 {minutes} 分鐘內有錯誤記錄（可能影響代理人執行）：\n"
)


# ============================================================================
# Worktree 回傳型別（0.2.1-W3-287：具名化取代位置解構）
# ============================================================================


class WorktreeInfo(NamedTuple):
    """單一 worktree 的路徑與分支。"""

    path: str
    branch: str


class WorktreeItems(NamedTuple):
    """單一 worktree 附帶的項目清單（語意依呼叫端而定：未提交檔案或未合併
    commit 摘要）。get_worktree_uncommitted_files 與 get_unmerged_worktrees
    共用此型別——兩者形狀相同（路徑 + 分支 + 字串清單），僅 items 語意不同，
    以泛型欄位名 items 明示，避免誤植為固定語意的 files/commits。
    """

    path: str
    branch: str
    items: list[str]


# ============================================================================
# 核心邏輯
# ============================================================================


def get_uncommitted_files(project_root: str, logger: logging.Logger) -> list[str]:
    """取得未 commit 的檔案清單（排除豁免路徑）

    0.2.1-W3-286：改用 lib.git_utils.get_uncommitted_files 共用實作，取代
    自行 subprocess + porcelain 解析。舊版整體 strip 曾剝除首行前導空白
    致路徑截斷（IMP-BAL-007 / 0.2.1-W3-284），共用層已修復且與本 hook 原本
    的行首空白保留邏輯一致，收斂不改變解析結果。

    Args:
        project_root: 專案根目錄路徑
        logger: Logger 實例（共用層失敗時內部靜默回傳空列表，不再區分
            timeout/not-found/非零退出碼，三者皆與「無變更」同歸空列表——
            對本 hook 而言結果一致：無檔案清單即不觸發警告）

    Returns:
        list[str]: 未 commit 的檔案路徑清單
    """
    file_statuses = shared_get_uncommitted_files(cwd=project_root)
    files = []
    for fs in file_statuses:
        if any(fs.file_path.startswith(prefix) for prefix in EXCLUDED_PATH_PREFIXES):
            continue
        files.append(fs.file_path)
    return files


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


def list_worktrees(project_root: str, logger: logging.Logger) -> list[WorktreeInfo]:
    """取得所有非 main 的 worktree 清單。

    0.2.1-W3-286：改用 lib.git_utils.get_worktree_list(exclude_main=True)
    共用實作，取代自行 subprocess + porcelain 解析（原 _parse_worktree_
    list_output，0.2.1-W3-283 從 get_unmerged_worktrees 抽出的版本）。
    detached worktree（無 branch 值）依共用層慣例保留於原始清單，此處以
    `wt.get("branch")` 真值過濾排除——與原行為一致（detached 因無分支可供
    `git log main..branch` 比對，本就不出現在 WorktreeInfo 清單中）。

    Args:
        project_root: 專案根目錄路徑
        logger: Logger 實例（保留參數維持既有呼叫端簽章相容）

    Returns:
        list[WorktreeInfo]: 具名 (path, branch) 清單；git 查詢失敗時回傳空清單
    """
    worktrees = shared_get_worktree_list(cwd=project_root, exclude_main=True)
    return [WorktreeInfo(wt["path"], wt["branch"]) for wt in worktrees if wt.get("branch")]


def get_worktree_uncommitted_files(
    worktrees: list[WorktreeInfo], logger: logging.Logger
) -> list[WorktreeItems]:
    """逐 worktree 檢查未提交變更（issue 46 症狀四驗收側主防線）。

    既有 get_uncommitted_files 以主 repo 為 cwd 跑 git status，看不見
    worktree 的獨立 working tree；代理人在 worktree 完成實作但產品碼從未
    commit 時，主 repo 檢查與 get_unmerged_worktrees（只查 commit 歷史）
    皆為綠燈，PM 端無從得知。本函式對每個 worktree 獨立執行
    `git -C <path> status --porcelain`，於代理人回報當下即可見未落地內容。

    EXCLUDED_PATH_PREFIXES 沿用主 repo 檢查的同一份排除清單（`.claude/` /
    `docs/`）。排除理由是工作流前提，不是資產性質：本專案框架修改
    （`.claude/` 下的規則、方法論、hook）目前不經 worktree 派發，故此
    路徑下的未提交變更不落在「產品碼遺失」風險範圍內。若此前提改變
    （框架修改開始走 worktree 派發），本排除即成偵測盲區，需重新評估
    是否仍適用。維持與主 repo 檢查一致的判準，避免同一份清單在兩處
    產生不同語意（0.2.1-W3-288 SR-2 / 0.2.1-W3-293）。

    Args:
        worktrees: WorktreeInfo 清單（由 list_worktrees 取得）
        logger: Logger 實例

    Returns:
        list[WorktreeItems]: (path, branch, items=未提交檔案) 清單；
        僅含有未提交變更（過濾豁免路徑後非空）的 worktree
    """
    result: list[WorktreeItems] = []
    for wt_path, branch in worktrees:
        file_statuses = shared_get_uncommitted_files(cwd=wt_path)
        files = [
            fs.file_path
            for fs in file_statuses
            if not any(fs.file_path.startswith(prefix) for prefix in EXCLUDED_PATH_PREFIXES)
        ]

        if files:
            result.append(WorktreeItems(wt_path, branch, files))

    return result


def _build_worktree_items_message(
    title: str,
    body: str,
    worktrees: list[WorktreeItems],
    item_label: str,
    command_for: Callable[[WorktreeItems], str],
    suggestion: str,
) -> str:
    """組裝 worktree 項目清單訊息的共用骨架（0.2.1-W3-287：合併原
    build_worktree_uncommitted_message 與 build_worktree_merge_message，
    截斷上限統一取 MAX_FILES_DISPLAY，取代原本各自寫死不同上限的漂移）。

    Args:
        title / body: 訊息標題與說明本文
        worktrees: WorktreeItems 清單
        item_label: 項目清單標頭描述（如「未提交檔案」／「commit」）
        command_for: (WorktreeItems) -> str，產生該 worktree 的建議指令行
        suggestion: 訊息尾端的強制動作提示
    """
    lines = [MSG_SEPARATOR, title, MSG_SEPARATOR, "", body]

    for wt in worktrees:
        lines.append(f"  分支: {wt.branch}")
        lines.append(f"  路徑: {wt.path}")
        lines.append(f"  {item_label} ({len(wt.items)} 個):")
        display_count = min(len(wt.items), MAX_FILES_DISPLAY)
        for item in wt.items[:display_count]:
            lines.append(f"    - {item}")
        remaining = len(wt.items) - display_count
        if remaining > 0:
            lines.append(f"    {MSG_MORE_FILES.format(remaining)}")
        lines.append(f"  建議: {command_for(wt)}")
        lines.append("")

    lines.append(suggestion)
    lines.append(MSG_SEPARATOR)
    return "\n".join(lines)


def build_worktree_uncommitted_message(
    uncommitted: list[WorktreeItems],
) -> str:
    """建構 worktree 未提交變更警告訊息（與主 repo 檢查訊息區分來源）。"""
    return _build_worktree_items_message(
        MSG_WORKTREE_UNCOMMITTED_TITLE,
        MSG_WORKTREE_UNCOMMITTED_BODY,
        uncommitted,
        "未提交檔案",
        lambda wt: f'git -C {wt.path} add <files> && git -C {wt.path} commit -m "..." -- <files>',
        MSG_WORKTREE_UNCOMMITTED_SUGGESTION,
    )


def get_unmerged_worktrees(
    project_root: str, logger: logging.Logger, worktrees: list[WorktreeInfo] | None = None
) -> list[WorktreeItems]:
    """取得有未合併 commit 的 worktree 清單

    Args:
        project_root: 專案根目錄路徑
        logger: Logger 實例
        worktrees: 已解析的 worktree 清單（避免重複查詢，None 時自行查詢）。
            實際呼叫端（main()）恆傳值；None 分支僅供測試單獨驗證本函式的
            自行查詢路徑

    Returns:
        list[WorktreeItems]: (path, branch, items=commit 摘要) 清單
    """
    if worktrees is None:
        worktrees = list_worktrees(project_root, logger)

    # 檢查每個 worktree 是否有未合併 commit
    unmerged: list[WorktreeItems] = []
    for wt_path, branch in worktrees:
        try:
            log_result = subprocess.run(
                ["git", "log", f"main..{branch}", "--oneline"],
                capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=GIT_STATUS_TIMEOUT,
                cwd=project_root,
            )
            if log_result.returncode == 0 and log_result.stdout.strip():
                commits = [l for l in log_result.stdout.strip().splitlines() if l]
                if commits:
                    unmerged.append(WorktreeItems(wt_path, branch, commits))
        except (subprocess.TimeoutExpired, FileNotFoundError):
            continue

    return unmerged


def build_worktree_merge_message(
    unmerged: list[WorktreeItems],
) -> str:
    """建構 worktree 合併提醒訊息"""
    return _build_worktree_items_message(
        MSG_WORKTREE_MERGE_TITLE,
        MSG_WORKTREE_MERGE_BODY,
        unmerged,
        "commit",
        lambda wt: f"git merge {wt.branch} --no-edit",
        MSG_WORKTREE_MERGE_SUGGESTION,
    )


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
            capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=GIT_STATUS_TIMEOUT,
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
                capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=GIT_STATUS_TIMEOUT,
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


def _has_hook_error(content: str) -> bool:
    """判斷 log 檔內容是否包含真實 Hook 錯誤。

    只採計以下兩種訊號，避免純字串匹配誤報：
      1. log level 為 ERROR/CRITICAL/FATAL 的 log 行（格式 `] LEVEL -`）
      2. Python Traceback 標記（行首 `Traceback (most recent call last):`）

    INFO/DEBUG/WARNING 訊息中夾帶 "ERROR"/"FAIL"/"Exception" 等關鍵字
    （例如回放使用者命令字串）不視為錯誤。
    """
    if HOOK_ERROR_LOG_LEVEL_RE.search(content):
        return True
    if HOOK_ERROR_TRACEBACK_RE.search(content):
        return True
    return False


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
                    if _has_hook_error(content):
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


def _get_error_dedup_state_file(project_root) -> Path:
    """Hook error 摘要去重 state 檔路徑（hook-logs 已被 .gitignore 排除）。"""
    return (
        Path(project_root) / ".claude" / "hook-logs" / HOOK_NAME
        / "hook-error-broadcast-dedup.json"
    )


def build_error_fingerprint(hook_errors: list[tuple[str, int]]) -> str:
    """以排序後的（hook 名稱, 錯誤數）清單計算 fingerprint。

    相同錯誤集合 → 相同 fingerprint → TTL 內去重；任一 hook 新增錯誤記錄
    會改變計數 → fingerprint 變化 → 立即播報（新事件不被舊播報遮蔽）。
    """
    canonical = json.dumps(sorted(hook_errors), ensure_ascii=False)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def check_and_record_broadcast(
    state_file: Path,
    key: str,
    ttl_seconds: int,
    logger: logging.Logger,
    now: float | None = None,
) -> bool:
    """檢查同 key 是否在 TTL 內已播報過；未播報過則記錄本次播報。

    Returns:
        bool: True 表示 TTL 內已播報過（呼叫端應跳過輸出）；False 表示
              首次播報（已記錄 timestamp）。

    state 檔損毀或 IO 失敗時 fail-open（回 False 照常播報）：dedup 層異常
    寧可重複通知，不可吞掉真實通知（quality-baseline 規則 4 可觀測性）。

    註：與 subagent-stop-dispatch-cleanup-hook.py 的同名函式刻意重複——
    hook 檔名含 hyphen 無法互相 import，且 1.0.0-W1-055.1 約束僅允許修改
    兩個 hook 本體；抽共用 lib 屬範圍外決策。
    """
    if now is None:
        now = time.time()

    state: dict = {}
    try:
        if state_file.exists():
            raw = json.loads(state_file.read_text(encoding="utf-8"))
            if isinstance(raw, dict):
                # 載入時順手剪除過期 entry，state 檔不無限成長
                state = {
                    k: v
                    for k, v in raw.items()
                    if isinstance(v, (int, float)) and now - v < ttl_seconds
                }
    except (OSError, json.JSONDecodeError, ValueError) as e:
        logger.debug("dedup state 讀取失敗（fail-open 照常播報）: %s", e)
        state = {}

    if key in state:
        return True

    state[key] = now
    try:
        state_file.parent.mkdir(parents=True, exist_ok=True)
        state_file.write_text(json.dumps(state), encoding="utf-8")
    except OSError as e:
        logger.debug("dedup state 寫入失敗（fail-open 照常播報）: %s", e)
    return False


def _lookup_agent_info(project_root, agent_id, logger):
    """從 dispatch-active.json 查詢代理人的 description 和 worktree 資訊。

    SubagentStop input 無 tool_input（缺 description/isolation），
    需從 dispatch-active.json 交叉查詢。

    Returns:
        tuple[str, bool]: (agent_description, uses_worktree)
    """
    try:
        dispatches = get_active_dispatches(project_root)
        for d in dispatches:
            if d.get("agent_id") == agent_id:
                desc = d.get("agent_description", "unknown")
                uses_wt = bool(d.get("branch_name"))
                return desc, uses_wt
    except Exception as e:
        logger.debug("dispatch-active.json lookup failed: %s", e)

    return "unknown", False


def main() -> None:
    """主函式 — SubagentStop 驅動，代理人真正完成時觸發。"""
    logger = setup_hook_logging(HOOK_NAME)

    input_data = read_json_from_stdin(logger)

    if not input_data:
        logger.debug("no input data")
        # W17-160: SubagentStop schema — 無內容時靜默退出，不輸出 hookSpecificOutput 殼
        sys.exit(EXIT_SUCCESS)

    # SubagentStop input 含 agent_id（CC runtime 保證）
    agent_id = input_data.get("agent_id", "")
    if not agent_id:
        logger.debug("no agent_id in SubagentStop input, skip")
        sys.exit(EXIT_SUCCESS)

    # 自激迴圈斷路器（1.0.0-W1-055.1 修復 1）：stop_hook_active=true 表示本次
    # 停止是「上一輪 stop hook 輸出令 agent 繼續」的結果，任何輸出都會再度
    # 延續迴圈 —— 靜默退出。
    if input_data.get("stop_hook_active"):
        logger.debug(
            "stop_hook_active=true（stop hook 引發的繼續），靜默退出避免自激迴圈"
        )
        sys.exit(EXIT_SUCCESS)

    # 取得專案根目錄
    project_root = get_project_root()

    # 從 dispatch-active.json 查詢 agent 資訊
    agent_description, agent_uses_worktree = _lookup_agent_info(
        project_root, agent_id, logger
    )

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
        sys.stderr.write(f"[{HOOK_NAME}] {MSG_UNCOMMITTED_DETECTED}\n")
    else:
        logger.debug("no uncommitted files after agent completed")

    # 0.2.1-W3-283：解析一次 worktree 清單，供未合併 commit 檢查與未提交
    # 變更檢查共用，避免重複 `git worktree list` 呼叫
    all_worktrees = list_worktrees(str(project_root), logger)

    # 檢查 worktree 未提交變更（issue 46 症狀四驗收側，先於合併檢查獨立判定）
    worktree_uncommitted = get_worktree_uncommitted_files(all_worktrees, logger)
    has_worktree_uncommitted = bool(worktree_uncommitted)
    if worktree_uncommitted:
        total_wt_files = sum(len(wt.items) for wt in worktree_uncommitted)
        logger.warning(
            "worktree uncommitted changes detected: %d worktrees, %d files",
            len(worktree_uncommitted), total_wt_files,
        )
        messages.append(build_worktree_uncommitted_message(worktree_uncommitted))

    # 檢查 worktree 未合併 commit
    unmerged_worktrees = get_unmerged_worktrees(str(project_root), logger, all_worktrees)
    worktree_branch_names = {wt.branch for wt in unmerged_worktrees}
    if unmerged_worktrees:
        has_unmerged_worktrees = True
        first_unmerged_branch = unmerged_worktrees[0].branch
        total_commits = sum(len(wt.items) for wt in unmerged_worktrees)
        logger.warning(
            "unmerged worktrees detected: %d worktrees, %d commits",
            len(unmerged_worktrees), total_commits,
        )
        messages.append(build_worktree_merge_message(unmerged_worktrees))

    # 檢查 feature 分支未合併 commit
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

    # CWD 還原提醒：只在 worktree 代理人時顯示
    if agent_uses_worktree:
        messages.append(build_cwd_restore_message(str(project_root)))
        logger.info("cwd restore reminder appended (worktree agent)")
    else:
        logger.debug("cwd restore reminder skipped (non-worktree agent)")

    # Hook error 摘要（1.0.0-W1-055.1 修復 2：fingerprint 去重，相同錯誤集合
    # 在 TTL 內不重複播報）
    hook_errors = scan_hook_errors(str(project_root), HOOK_ERROR_SCAN_MINUTES, logger)
    if hook_errors:
        fingerprint = build_error_fingerprint(hook_errors)
        if check_and_record_broadcast(
            _get_error_dedup_state_file(project_root),
            fingerprint,
            HOOK_ERROR_DEDUP_TTL_SECONDS,
            logger,
        ):
            logger.info(
                "hook error 摘要 dedup 命中（TTL 內已播報相同 fingerprint），跳過"
            )
        else:
            messages.append(build_hook_error_message(hook_errors))

    # PM 立即動作摘要
    if has_uncommitted or has_worktree_uncommitted or has_unmerged_worktrees or has_unmerged_branches:
        messages.append(build_pm_action_summary(
            str(project_root),
            has_uncommitted,
            has_unmerged_worktrees,
            has_unmerged_branches,
            first_unmerged_branch,
        ))

    # 1.0.0-W1-055.1 修復 4：通道回退 top-level systemMessage（純顯示）。
    # additionalContext 經 W1-055 活體確證會注入「停止中的 subagent」並令其
    # 繼續（自激迴圈核心），與「通知 PM 主線程」意圖不符。
    # 無訊息時靜默不輸出（不送空殼）。
    if messages:
        combined_message = "\n\n".join(messages)
        print(json.dumps({"systemMessage": combined_message}, ensure_ascii=False))
    sys.exit(EXIT_SUCCESS)


if __name__ == "__main__":
    main()
