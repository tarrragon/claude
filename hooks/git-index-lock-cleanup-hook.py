#!/usr/bin/env -S uv run --quiet --script
# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""
Git Index Lock Cleanup Hook

Purpose: 在 git commit/add 前自動清理過期的 .git/index.lock
Source: IMP-046 — Hook/Agent 的 git 操作與主線程 commit 競爭 index.lock

Trigger: PreToolUse (Bash: git commit, git add)

邏輯:
1. 偵測 Bash 命令是否包含 git commit 或 git add
2. 檢查 .git/index.lock 是否存在
3. 如果存在且超過 STALE_THRESHOLD_SECONDS 秒，自動移除並輸出警告
4. 如果存在但很新，輸出警告但不移除（可能有正在進行的 git 操作）
"""

import logging
import os
import sys
import time
from pathlib import Path

# 添加 lib 目錄到路徑
sys.path.insert(0, str(Path(__file__).parent))
sys.path.insert(0, str(Path(__file__).parent.parent))

from lib.hook_io import read_hook_input, write_hook_output, create_simple_output
from lib.git_utils import get_project_root
from lib import setup_hook_logging, run_hook_safely

# 超過此秒數的 index.lock 視為殘留，自動移除
STALE_THRESHOLD_SECONDS = 5

HOOK_NAME = "git-index-lock-cleanup"


def is_git_write_command(tool_input: dict) -> bool:
    """判斷是否為 git 寫入操作命令。"""
    command = tool_input.get("command", "")
    return "git commit" in command or "git add" in command


def check_and_cleanup_index_lock(logger: logging.Logger) -> str | None:
    """檢查並清理過期的 index.lock。

    Returns:
        警告訊息（如果有清理動作或 lock 存在），否則 None
    """
    project_root = get_project_root()
    if not project_root:
        return None

    lock_path = os.path.join(project_root, ".git", "index.lock")

    if not os.path.exists(lock_path):
        return None

    # 計算 lock 檔案的年齡
    try:
        lock_age = time.time() - os.path.getmtime(lock_path)
    except OSError as e:
        logger.warning("無法讀取 index.lock 資訊: %s", e)
        return None

    if lock_age > STALE_THRESHOLD_SECONDS:
        # 過期的 lock，自動移除
        try:
            os.remove(lock_path)
            msg = (
                f"[IMP-046] 自動移除過期的 .git/index.lock"
                f"（已存在 {lock_age:.0f} 秒，閾值 {STALE_THRESHOLD_SECONDS} 秒）"
            )
            logger.info(msg)
            return msg
        except OSError as e:
            msg = f"[IMP-046] 無法移除 .git/index.lock: {e}"
            logger.error(msg)
            return msg
    else:
        # lock 很新，可能有正在進行的 git 操作
        # PC-139: 外部 GUI app（Fork / GitKraken / SourceTree / VS Code Git）
        # 週期性 fork git status/diff 子進程也會短暫持有 index.lock，
        # 非自家 hook/Bash 串接所致；訊息提示 PM 同時檢查外部進程，避免誤判方向白等 lock 自清。
        msg = (
            f"[WARNING] .git/index.lock 存在（{lock_age:.0f} 秒），"
            f"可能有其他 git 操作進行中，不自動移除。\n"
            f"來源排查：\n"
            f"  1. 自家 hook/Bash 串接 git 寫入（拆分為獨立呼叫，見 bash-tool-usage-rules.md 規則三）\n"
            f"  2. 外部 GUI app fork 子進程（Fork / GitKraken / SourceTree / VS Code Git）— PC-139\n"
            f"     偵測指令：ps aux | grep -iE \"(Fork|GitKraken|SourceTree)\\.app|VS.Code.*git\" | grep -v grep\n"
            f"  3. 確認無自家操作進行中後，可安全執行：rm .git/index.lock\n"
            f"參見 .claude/error-patterns/process-compliance/PC-139-git-index-lock-source-misattribution-gui-app-fork.md"
        )
        logger.warning(msg)
        return msg


def main():
    logger = setup_hook_logging(HOOK_NAME)

    hook_input = read_hook_input()
    if not hook_input:
        write_hook_output(create_simple_output("approve"))
        return

    tool_name = hook_input.get("tool_name", "")
    tool_input = hook_input.get("tool_input", {})

    # 只處理 Bash 的 git 寫入命令
    if tool_name != "Bash" or not is_git_write_command(tool_input):
        write_hook_output(create_simple_output("approve"))
        return

    result_msg = check_and_cleanup_index_lock(logger)

    if result_msg:
        write_hook_output(create_simple_output("approve", result_msg))
    else:
        write_hook_output(create_simple_output("approve"))


if __name__ == "__main__":
    run_hook_safely(main, HOOK_NAME)
