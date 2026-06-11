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

sys.path.insert(0, str(Path(__file__).parent))

from hook_utils import (
    setup_hook_logging,
    read_json_from_stdin,
    get_project_root,
)

sys.path.insert(0, str(Path(__file__).parent / "lib"))
from dispatch_tracker import get_active_dispatches

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
            encoding="utf-8",
            errors="replace",
            timeout=GIT_STATUS_TIMEOUT,
            cwd=project_root,
        )
        if result.returncode != 0:
            logger.warning("git status failed: %s", result.stderr.strip())
            return []

        files = []
        # 禁止對 stdout 整體 strip：porcelain 格式為「XY filename」（X=index、
        # Y=worktree 兩個狀態字元），worktree-modified 的 X 為前導空白；整體
        # strip 會剝除第一行的前導空白，使 line[3:] 多切一個路徑首字元
        # （.claude/ 變 claude/），進而繞過 EXCLUDED_PATH_PREFIXES 豁免。
        for line in result.stdout.splitlines():
            if not line.strip():
                continue
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
            capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=GIT_STATUS_TIMEOUT,
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
                capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=GIT_STATUS_TIMEOUT,
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

    # 檢查 worktree 未合併 commit
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
    if has_uncommitted or has_unmerged_worktrees or has_unmerged_branches:
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
