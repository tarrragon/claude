#!/usr/bin/env -S uv run --quiet --script
# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///

"""
Dispatch Record Hook - PreToolUse (Agent)

功能:
  Agent 派發前，記錄派發資訊到 dispatch-active.json。
  搭配 active-dispatch-tracker-hook.py（PostToolUse:Agent）的 clear_dispatch 形成完整的
  記錄-清理生命週期。

  PM 可透過 `cat .claude/dispatch-active.json` 查詢活躍派發數量。

觸發時機: Agent 工具呼叫前 (PreToolUse, matcher: Agent)
行為: 不阻擋（exit 0），記錄派發後靜默通過

來源:
  - PC-050 — PM 在代理人仍在工作時誤判完成
  - W12-002 — dispatch-active.json 從未被寫入（缺少記錄端）
Ticket: 0.17.3-W12-002
"""

import json
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from hook_utils import (
    setup_hook_logging,
    read_json_from_stdin,
    extract_tool_input,
    is_subagent_environment,
    get_project_root,
    run_hook_safely,
)
from lib.dispatch_tracker import record_dispatch

# ============================================================================
# 常數定義
# ============================================================================

HOOK_NAME = "dispatch-record-hook"
EXIT_SUCCESS = 0


# ============================================================================
# 核心邏輯
# ============================================================================


def main() -> int:
    """主函式"""
    logger = setup_hook_logging(HOOK_NAME)

    input_data = read_json_from_stdin(logger)

    # 子代理人環境不觸發（避免巢狀記錄）
    if is_subagent_environment(input_data):
        logger.debug("subagent environment, skip")
        return EXIT_SUCCESS

    if not input_data:
        logger.debug("no input data")
        return EXIT_SUCCESS

    tool_input = extract_tool_input(input_data, logger)

    # 取得代理人資訊
    agent_description = tool_input.get("description", "unknown")
    isolation = tool_input.get("isolation", "")

    # 取得專案根目錄
    project_root = get_project_root()

    # 記錄派發
    try:
        record_dispatch(
            project_root=project_root,
            agent_description=agent_description,
            branch_name="worktree" if isolation == "worktree" else "",
        )
        logger.info(
            "recorded dispatch: %s (isolation=%s)",
            agent_description,
            isolation or "none",
        )
    except Exception as e:
        # 記錄失敗不阻擋派發
        logger.warning("record_dispatch failed: %s", e)

    return EXIT_SUCCESS


if __name__ == "__main__":
    sys.exit(run_hook_safely(main, HOOK_NAME))
