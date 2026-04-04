#!/usr/bin/env -S uv run --quiet --script
# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///

"""
Worktree Base Distance Check Hook - PreToolUse (Agent)

功能:
  在 Agent(isolation: "worktree") 派發前，檢查現有 worktree 的基底 commit
  與 main HEAD 的距離。若任一 worktree 落後超過閾值，輸出警告提醒 PM。

觸發時機: Agent 工具呼叫前 (PreToolUse, matcher: Agent)
行為: 不阻擋（decision 始終為 "approve"），僅在 additionalContext 輸出警告

來源:
  - W5-006 — worktree 分支可能基於舊 commit，代理人在過時程式碼上工作
Ticket: 0.17.0-W5-008
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

HOOK_NAME = "worktree-base-distance-check-hook"
EXIT_SUCCESS = 0

# 基底距離閾值（超過此值視為過時）
MAX_BASE_DISTANCE = 5

# Git 命令超時（秒）
GIT_COMMAND_TIMEOUT = 10

# 訊息常數
MSG_SEPARATOR = "============================================================"
MSG_TITLE = "[Worktree 基底距離警告]"
MSG_STALE_DETECTED = "存在 {count} 個過時 worktree（基底落後 main {threshold}+ commits）"
MSG_WORKTREE_DETAIL = "  - {path} (HEAD: {head_short}, 落後 {distance} commits)"
MSG_SUGGEST_CLEANUP = "建議先清理：git worktree remove <path> --force"
MSG_SUGGEST_REBASE = "或 rebase：git -C <path> rebase main"


# ============================================================================
# 核心邏輯
# ============================================================================


def get_worktree_list(project_root: str, logger: logging.Logger) -> list[dict]:
    """取得所有 worktree 清單（排除主 worktree）

    Args:
        project_root: 專案根目錄路徑
        logger: Logger 實例

    Returns:
        list[dict]: worktree 資訊清單，每項包含 path 和 head
    """
    try:
        result = subprocess.run(
            ["git", "worktree", "list", "--porcelain"],
            capture_output=True,
            text=True,
            timeout=GIT_COMMAND_TIMEOUT,
            cwd=project_root,
        )
        if result.returncode != 0:
            logger.warning("git worktree list failed: %s", result.stderr.strip())
            return []

        worktrees = []
        current_wt: dict[str, str] = {}
        for line in result.stdout.splitlines():
            if line.startswith("worktree "):
                current_wt = {"path": line[len("worktree "):]}
            elif line.startswith("HEAD "):
                current_wt["head"] = line[len("HEAD "):]
            elif line == "" and current_wt:
                worktrees.append(current_wt)
                current_wt = {}
        if current_wt:
            worktrees.append(current_wt)

        # 排除主 worktree（第一個就是主 worktree）
        if worktrees:
            worktrees = worktrees[1:]

        return worktrees

    except subprocess.TimeoutExpired:
        logger.warning("git worktree list timeout")
        return []
    except FileNotFoundError:
        logger.warning("git not found")
        return []


def get_base_distance(
    project_root: str,
    worktree_head: str,
    logger: logging.Logger,
) -> int:
    """計算 worktree HEAD 與 main HEAD 之間的 commit 距離

    使用 git rev-list --count main...<worktree-head> 取得雙向距離總數。

    Args:
        project_root: 專案根目錄路徑
        worktree_head: worktree 的 HEAD commit hash
        logger: Logger 實例

    Returns:
        int: commit 距離，錯誤時回傳 -1
    """
    try:
        result = subprocess.run(
            ["git", "rev-list", "--count", f"main...{worktree_head}"],
            capture_output=True,
            text=True,
            timeout=GIT_COMMAND_TIMEOUT,
            cwd=project_root,
        )
        if result.returncode != 0:
            logger.warning(
                "git rev-list failed for %s: %s",
                worktree_head[:8],
                result.stderr.strip(),
            )
            return -1

        return int(result.stdout.strip())

    except (subprocess.TimeoutExpired, ValueError) as exc:
        logger.warning("get_base_distance error: %s", exc)
        return -1


def build_warning_message(stale_worktrees: list[dict]) -> str:
    """建構過時 worktree 警告訊息

    Args:
        stale_worktrees: 過時 worktree 資訊清單

    Returns:
        str: 格式化的警告訊息
    """
    lines = [
        MSG_SEPARATOR,
        MSG_TITLE,
        MSG_SEPARATOR,
        "",
        MSG_STALE_DETECTED.format(
            count=len(stale_worktrees),
            threshold=MAX_BASE_DISTANCE,
        ),
        "",
    ]

    for wt in stale_worktrees:
        lines.append(
            MSG_WORKTREE_DETAIL.format(
                path=wt["path"],
                head_short=wt["head"][:8],
                distance=wt["distance"],
            )
        )

    lines.extend([
        "",
        MSG_SUGGEST_CLEANUP,
        MSG_SUGGEST_REBASE,
        MSG_SEPARATOR,
    ])

    return "\n".join(lines)


def main() -> None:
    """主函式"""
    logger = setup_hook_logging(HOOK_NAME)

    input_data = read_json_from_stdin(logger)

    # 預設輸出（靜默通過）
    default_output = {"decision": "approve"}

    # 子代理人環境不觸發
    if is_subagent_environment(input_data):
        logger.debug("subagent environment, skip")
        print(json.dumps(default_output))
        sys.exit(EXIT_SUCCESS)

    if not input_data:
        logger.debug("no input data")
        print(json.dumps(default_output))
        sys.exit(EXIT_SUCCESS)

    tool_input = extract_tool_input(input_data, logger)

    # 僅在 isolation == "worktree" 時觸發檢查
    isolation = tool_input.get("isolation", "")
    if isolation != "worktree":
        logger.debug("isolation is not worktree (%s), skip", isolation)
        print(json.dumps(default_output))
        sys.exit(EXIT_SUCCESS)

    # 取得專案根目錄
    project_root = str(get_project_root())

    # 取得所有 worktree
    worktrees = get_worktree_list(project_root, logger)
    if not worktrees:
        logger.debug("no secondary worktrees found")
        print(json.dumps(default_output))
        sys.exit(EXIT_SUCCESS)

    # 檢查每個 worktree 的基底距離
    stale_worktrees = []
    for wt in worktrees:
        head = wt.get("head", "")
        if not head:
            continue
        distance = get_base_distance(project_root, head, logger)
        if distance > MAX_BASE_DISTANCE:
            stale_worktrees.append({
                "path": wt["path"],
                "head": head,
                "distance": distance,
            })

    if not stale_worktrees:
        logger.debug("all worktrees within acceptable distance")
        print(json.dumps(default_output))
        sys.exit(EXIT_SUCCESS)

    # 有過時 worktree，輸出警告
    warning_msg = build_warning_message(stale_worktrees)
    logger.info(
        "stale worktrees detected: %d (threshold: %d commits)",
        len(stale_worktrees),
        MAX_BASE_DISTANCE,
    )

    # 雙通道可觀測性：同時輸出到 stderr
    sys.stderr.write(
        f"[{HOOK_NAME}] "
        f"{MSG_STALE_DETECTED.format(count=len(stale_worktrees), threshold=MAX_BASE_DISTANCE)}\n"
    )

    output = {
        "decision": "approve",
        "additionalContext": warning_msg,
    }
    print(json.dumps(output))
    sys.exit(EXIT_SUCCESS)


if __name__ == "__main__":
    main()
