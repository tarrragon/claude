#!/usr/bin/env python3
# /// script
# requires-python = ">=3.9"
# dependencies = []
# ///
"""
Worktree Commit-Before-Dispatch Hook - PreToolUse (Agent)

功能：派發 worktree agent 前，檢查 main 上是否有未 commit 的 tracked 變更。
未 commit 的變更可能在 worktree 操作後因 stash/checkout 丟失（PC-019）。

Hook 類型：PreToolUse
匹配工具：Agent
退出碼：0 = 放行，2 = 阻擋（stderr 回饋給 Claude）
"""

import json
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "hooks"))

from lib import setup_hook_logging, run_hook_safely, read_json_from_stdin


BLOCK_MESSAGE = """[PC-019 防護] main 上有未 commit 的 tracked 變更，禁止派發 worktree agent

未 commit 的檔案：
{files}

修復方式：
  先 commit main 上的變更，再派發 worktree agent
  git add <files> && git commit -m "chore: pre-dispatch commit"

詳見: .claude/pm-rules/worktree-operations.md（階段 1：派發前）"""

# W3-007 方案 A：origin/main 落後 local main 警告訊息（非阻擋）
ORIGIN_BEHIND_WARNING = """[W3-007 警告] origin/main 落後 local main {count} 個 commit

CC runtime 的 worktree 隔離以 origin/main（remote-tracking ref）為 base，
而非 local main HEAD。origin/main 落後時，worktree 會建在 stale 基底上，
缺少最新本地 commit（W2-013 實證需 agent 手動 recovery）。

建議：派發前先 push local main
  git push origin main

詳見: .claude/pm-rules/parallel-dispatch.md（worktree base 與 push-first 紀律）"""


def _warn_if_origin_behind(logger) -> None:
    """檢查 origin/main 是否落後 local main，若落後則 stderr 警告（不阻擋）。

    W3-007 方案 A：worktree 隔離以 origin/main 為 base，origin/main 落後時
    worktree 建在 stale 基底。此處僅警告，派發決策仍交由 PM。

    Args:
        logger: hook logger，供記錄檢查結果與失敗原因（可觀測性規則 4）
    """
    try:
        # 計算 origin/main..main 的 commit 數（local main 領先 origin/main 的量）
        result = subprocess.run(
            ["git", "rev-list", "--count", "origin/main..main"],
            capture_output=True, text=True, encoding="utf-8",
            errors="replace", timeout=10
        )
    except (subprocess.TimeoutExpired, FileNotFoundError) as exc:
        # git 不可用 / 超時：無法判斷，記錄後略過（不阻擋派發）
        logger.warning("origin/main 落後檢查失敗：%s", exc)
        return

    if result.returncode != 0:
        # origin/main ref 不存在（未 push 過 / 無 remote）等情況，略過
        logger.info("origin/main 落後檢查略過（git rev-list 非零退出）")
        return

    count_str = result.stdout.strip()
    if not count_str.isdigit():
        logger.info("origin/main 落後檢查略過（無法解析 commit 數）")
        return

    behind_count = int(count_str)
    if behind_count > 0:
        print(ORIGIN_BEHIND_WARNING.format(count=behind_count), file=sys.stderr)
        logger.warning("origin/main 落後 local main %d 個 commit", behind_count)
    else:
        logger.info("origin/main 與 local main 同步，無需警告")


def main() -> int:
    """Hook 主邏輯。"""
    logger = setup_hook_logging("worktree-commit-before-dispatch")

    try:
        input_data = read_json_from_stdin(logger)
    except (json.JSONDecodeError, EOFError):
        logger.warning("無法解析 stdin JSON")
        return 0  # 解析失敗不阻擋

    if not input_data:
        return 0

    tool_input = input_data.get("tool_input", {})
    isolation = tool_input.get("isolation", "")

    # 只檢查 worktree 隔離的派發
    if isolation != "worktree":
        logger.debug("非 worktree 隔離，跳過檢查")
        return 0

    logger.info("偵測到 worktree 派發，檢查未 commit 變更")

    # W3-007 方案 A：先警告 origin/main 落後（非阻擋，需在可能 return 2 前發出）
    _warn_if_origin_behind(logger)

    # 檢查 tracked 檔案是否有未 commit 的變更
    try:
        unstaged = subprocess.run(
            ["git", "diff", "--name-only"],
            capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=10
        )
        staged = subprocess.run(
            ["git", "diff", "--staged", "--name-only"],
            capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=10
        )
    except (subprocess.TimeoutExpired, FileNotFoundError):
        logger.warning("git 命令執行失敗")
        return 0  # git 失敗不阻擋

    changed_files = set()
    if unstaged.stdout.strip():
        changed_files.update(unstaged.stdout.strip().split("\n"))
    if staged.stdout.strip():
        changed_files.update(staged.stdout.strip().split("\n"))

    if not changed_files:
        logger.info("無未 commit 變更，放行")
        return 0

    files_list = "\n".join(f"  - {f}" for f in sorted(changed_files))
    message = BLOCK_MESSAGE.format(files=files_list)
    print(message, file=sys.stderr)
    logger.warning("阻擋 worktree 派發：%d 個未 commit 檔案", len(changed_files))
    return 2


if __name__ == "__main__":
    sys.exit(run_hook_safely(main, "worktree-commit-before-dispatch"))
