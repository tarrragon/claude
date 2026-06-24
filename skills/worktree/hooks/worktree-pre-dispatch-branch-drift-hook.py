#!/usr/bin/env python3
# /// script
# requires-python = ">=3.9"
# dependencies = []
# ///
"""
Worktree Pre-Dispatch Branch Drift Check Hook - PreToolUse (Agent)

Guard B（來源 1.2.0-W1-028 事故二）：派發 worktree subagent 前，檢查主 repo HEAD
是否仍在預期分支（main/master）。偵測「主 repo 漂移到 feat 分支」。

事故重現：cwd 污染後 main repo HEAD 漂移到 feat/1.2.0-W1-025-terminal-frame，
PM 後續 `git -C <main> merge` 落在誤切分支而非 main，push 顯示 up-to-date、
`git log main` 無對應 ticket → 工作落錯位置難以察覺。

本 hook 在 worktree 派發前若主 repo 不在 main/master → 阻擋（exit 2），
要求 PM 先 `git checkout main` 校正，避免在漂移基底上開新 worktree。

Hook 類型：PreToolUse
匹配工具：Agent
退出碼：0 = 放行，2 = 阻擋（stderr 回饋給 Claude）
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "hooks"))

from lib import setup_hook_logging, run_hook_safely, read_json_from_stdin, run_git


EXPECTED_BRANCHES = ("main", "master")

BLOCK_MESSAGE = """[1.2.0-W1-028 Guard B] 主 repo HEAD 漂移，禁止派發 worktree subagent

當前主 repo 分支: {current}
預期分支: main 或 master

事故背景：主 repo 漂移到 feat 分支時派發 worktree，後續 merge 會落在誤切分支
而非 main（push 顯示 up-to-date 卻 `git log main` 查無交付物）。這正是
1.2.0-W1-028 事故二的根因。

修復方式：
  1. 用固定值確認當前狀態（tool-output-trust 規則 3，勿靠 cwd-relative 推斷）：
       git branch --show-current
  2. 校正回 main：git checkout main
  3. 確認後再派發 worktree subagent

提醒：worktree ticket 寫入命令一律用子 shell 包裹避免 cwd 污染：
  (cd <project-root> && ticket ...)

詳見：.claude/pm-rules/worktree-operations.md（階段 1：派發前 / Guard B）"""


def main() -> int:
    """Hook 主邏輯。"""
    logger = setup_hook_logging("worktree-pre-dispatch-branch-drift")

    input_data = read_json_from_stdin(logger)
    if not input_data:
        return 0

    tool_input = input_data.get("tool_input") or {}
    isolation = tool_input.get("isolation", "")

    # 只檢查 worktree 隔離派發
    if isolation != "worktree":
        logger.debug("非 worktree 隔離派發，跳過 Guard B")
        return 0

    # 查主 repo HEAD（不指定 cwd = hook 執行於主 repo 工作目錄）
    current = run_git(["git", "symbolic-ref", "--short", "HEAD"], timeout=10, logger=logger)
    if current is None:
        # detached HEAD 或 git 失敗：無法判斷，放行不阻擋（可觀測性規則 4 已記錄）
        logger.warning("無法取得主 repo 當前分支（detached/git 失敗），放行")
        return 0

    if current in EXPECTED_BRANCHES:
        logger.info("主 repo 在預期分支 %s，放行 worktree 派發", current)
        return 0

    print(BLOCK_MESSAGE.format(current=current), file=sys.stderr)
    logger.warning("阻擋 worktree 派發：主 repo HEAD 漂移到 %s", current)
    return 2


if __name__ == "__main__":
    sys.exit(run_hook_safely(main, "worktree-pre-dispatch-branch-drift"))
