#!/usr/bin/env python3
# /// script
# requires-python = ">=3.9"
# dependencies = []
# ///

"""
Isolated Subagent Main-Write Guard Hook - PreToolUse (Edit|Write|NotebookEdit|Bash)

功能:
  隔離（isolation: worktree）子代理人的 worktree 被清除、恢復後，其寫入會直接
  落在主 repo 的共用 working tree / index。本 hook 在該情境下以
  additionalContext 要求代理人停手、寫 NeedsContext、交回 PM 重派
  （Edit/Write/NotebookEdit 以 permissionDecision deny 阻擋；Bash 維持 warn）。

觸發條件（全部成立才介入）:
  1. payload 有 agent_id，且經 dispatch-active.json 映射命中 entry
     （agent_id 精確比對，或 agent_handle 錨定正規式 ^a<handle>-<hex>$）
  2. 命中 entry 的 branch_name == "worktree"
  3. 寫入落在主 repo：
     - Edit/Write/NotebookEdit: 目標路徑在主 repo 根下且不在 .claude/worktrees/ 下
     - Bash git add/mv/rm/commit/restore --staged: payload cwd 等於主 repo 根
       （實測：payload cwd 反映代理人基準目錄，不反映命令內 cd）

fail-open: agent_id / 映射 / 目標路徑 / cwd 缺失或狀態檔讀取失敗 -> 放行並記 info。
hook 自身例外 -> 放行，stderr 與日誌皆留紀錄。

已知缺口（不涵蓋）: Bash 重導向 / sed -i / python 等寫檔；git -C <主 repo>；
PM（無 agent_id）；映射過期（entry 已被 TTL 清除）。

排除: ticket CLI（刻意寫主 checkout 的票）。
"""

import json
import os
import re
import sys
from pathlib import Path
from typing import Dict, Optional

sys.path.insert(0, str(Path(__file__).parent))
sys.path.insert(0, str(Path(__file__).parent.parent))

from lib import (
    setup_hook_logging,
    read_json_from_stdin,
    run_hook_safely,
    get_project_root,
    generate_hook_output,
)
from lib import dispatch_tracker

HOOK_NAME = "isolated-subagent-main-write-guard-hook"
EXIT_SUCCESS = 0

WORKTREE_BRANCH_MARKER = "worktree"
WORKTREES_SEGMENT = os.sep + ".claude" + os.sep + "worktrees"
FILE_TOOL_KEYS = {"Edit": "file_path", "Write": "file_path", "NotebookEdit": "notebook_path"}

_SEGMENT_SPLIT = re.compile(r"&&|\|\||;|\||\n")
_ENV_PREFIX = re.compile(r"^(?:\w+=\S*\s+)+")
_GIT_PREFIX = r"^git(?:\s+-c\s+\S+)*\s+"
_GIT_WRITE = re.compile(_GIT_PREFIX + r"(?:add|mv|rm|commit)\b")
_GIT_RESTORE = re.compile(_GIT_PREFIX + r"restore\b(?=.*(?:--staged|\s-S\b))")

WARN_MESSAGE = (
    "[隔離失效警告] 你是 isolation: worktree 派發的代理人，但這次寫入落在主 repo 的共用 "
    "working tree（{target}）。worktree 可能已被清除，繼續寫入會污染其他 session 的工作區與 index。"
    "請立即停手：不要再執行任何寫入，於 ticket 的 NeedsContext 章節記錄「隔離失效、寫入目標落在主 repo」"
    "與目前已做的變更，然後交回 PM 重新派發。"
)


def main_root_from(root: Path) -> Path:
    """若 root 位於 <main>/.claude/worktrees/<name>，回傳 <main>，否則原樣回傳。"""
    s = str(root)
    idx = s.find(WORKTREES_SEGMENT)
    return Path(s[:idx]) if idx >= 0 else root


def resolve_main_root() -> Path:
    return main_root_from(Path(get_project_root()))


def _norm(p: str) -> str:
    return os.path.normpath(os.path.realpath(p))


def _is_under(path: str, root: str) -> bool:
    return path == root or path.startswith(root + os.sep)


def find_isolated_entry(agent_id: str, main_root: Path, logger) -> Optional[Dict]:
    """依 agent_id 經 dispatch_tracker 查映射，回傳 branch_name == worktree 的 entry。"""
    for d in dispatch_tracker.get_active_dispatches(main_root):
        hit = d.get("agent_id") == agent_id
        handle = d.get("agent_handle") or ""
        if not hit and handle:
            hit = re.match("^a" + re.escape(handle) + "-[0-9a-f]+$", agent_id) is not None
        if hit:
            if d.get("branch_name") == WORKTREE_BRANCH_MARKER:
                return d
            logger.info("映射命中但 branch_name 非 worktree，放行: %s", agent_id)
            return None
    logger.info("agent_id 無映射，fail-open 放行: %s", agent_id)
    return None


def _bash_is_main_git_write(command: str) -> bool:
    for seg in _SEGMENT_SPLIT.split(command):
        seg = _ENV_PREFIX.sub("", seg.strip())
        if not seg or seg.startswith("ticket "):
            continue
        if _GIT_WRITE.match(seg) or _GIT_RESTORE.match(seg):
            return True
    return False


def write_target(input_data: dict, main_root: Path, logger) -> Optional[str]:
    """回傳落在主 repo 的寫入目標描述；非主 repo 寫入或資訊不足回傳 None。"""
    tool = input_data.get("tool_name", "")
    tool_input = input_data.get("tool_input") or {}
    root = _norm(str(main_root))
    if tool in FILE_TOOL_KEYS:
        path = tool_input.get(FILE_TOOL_KEYS[tool])
        if not path:
            logger.info("缺 file_path，fail-open 放行: %s", tool)
            return None
        target = _norm(path)
        if _is_under(target, root) and not _is_under(target, root + WORKTREES_SEGMENT):
            return target
        return None
    if tool == "Bash":
        cwd = input_data.get("cwd")
        if not cwd:
            logger.info("缺 cwd，fail-open 放行")
            return None
        if _norm(cwd) == root and _bash_is_main_git_write(tool_input.get("command", "")):
            return "cwd=" + root
        return None
    return None


def evaluate(input_data: dict, main_root: Path, logger) -> Optional[str]:
    """回傳警告訊息（需介入）或 None（放行）。"""
    agent_id = input_data.get("agent_id")
    if not agent_id:
        return None
    target = write_target(input_data, main_root, logger)
    if target is None:
        return None
    if find_isolated_entry(agent_id, main_root, logger) is None:
        return None
    decision = "deny" if input_data.get("tool_name") in FILE_TOOL_KEYS else "warn"
    logger.info("隔離代理人寫入落在主 repo，%s: agent_id=%s target=%s", decision, agent_id, target)
    return WARN_MESSAGE.format(target=target)


def main() -> int:
    logger = setup_hook_logging(HOOK_NAME)
    input_data = read_json_from_stdin(logger)
    if not input_data:
        return EXIT_SUCCESS
    try:
        message = evaluate(input_data, resolve_main_root(), logger)
    except Exception as e:  # fail-open：hook 自身例外不得阻擋工具，stderr 與日誌皆留紀錄
        logger.critical("hook 例外，fail-open 放行: %s", e, exc_info=True)
        sys.stderr.write("[%s] 例外，已放行: %s\n" % (HOOK_NAME, e))
        return EXIT_SUCCESS
    if message and input_data.get("tool_name") in FILE_TOOL_KEYS:
        print(json.dumps(generate_hook_output(
            "PreToolUse", permission_decision="deny", permission_decision_reason=message), ensure_ascii=False))
    elif message:
        print(json.dumps(generate_hook_output("PreToolUse", additional_context=message), ensure_ascii=False))
    return EXIT_SUCCESS


if __name__ == "__main__":
    sys.exit(run_hook_safely(main, HOOK_NAME))
