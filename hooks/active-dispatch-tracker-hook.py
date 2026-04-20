#!/usr/bin/env python3
# /// script
# requires-python = ">=3.9"
# dependencies = []
# ///
"""
Active Dispatch Tracker Hook - PostToolUse (Agent)

功能: PostToolUse(Agent) 觸發時補寫 agent_id + housekeeping（超時清理/orphan 偵測）。
      dispatch 記錄清理和完成廣播已遷移至 SubagentStop handler（W10-066）。
觸發時機: Agent 工具完成後 (PostToolUse, matcher: Agent)
行為: 不阻擋（exit 0），在 additionalContext 輸出 housekeeping 訊息
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from hook_utils import setup_hook_logging, run_hook_safely, read_json_from_stdin

sys.path.insert(0, str(Path(__file__).parent / "lib"))
from dispatch_tracker import (
    update_dispatch_agent_id,
    cleanup_expired,
    detect_orphan_branches,
    get_state_file_path,
)

HOOK_NAME = "active-dispatch-tracker"


def main() -> int:
    """Hook 主邏輯：補 agent_id + housekeeping。"""
    logger = setup_hook_logging(HOOK_NAME)

    try:
        input_data = read_json_from_stdin(logger)
    except (json.JSONDecodeError, EOFError):
        logger.warning("無法解析 stdin JSON")
        return 0

    if not input_data:
        logger.debug("stdin 無資料，跳過")
        return 0

    # 從 PostToolUse input 取得 tool_use_id 和 tool_response.agentId
    tool_use_id = input_data.get("tool_use_id", "")
    tool_response = input_data.get("tool_response", {})
    if isinstance(tool_response, str):
        tool_response = {}
    agent_id_from_response = tool_response.get("agentId")

    # 定位專案根目錄
    project_root = Path(__file__).resolve().parent.parent.parent
    state_file = get_state_file_path(project_root)

    if not state_file.exists():
        logger.debug("dispatch-active.json 不存在，跳過")
        return 0

    messages = []

    # 補 agent_id（不區分 background/前台，統一補寫）
    if agent_id_from_response and tool_use_id:
        updated = update_dispatch_agent_id(
            project_root, tool_use_id, agent_id_from_response
        )
        if not updated:
            # 前台模式下 SubagentStop 可能先到已清理 entry，這是正常現象
            logger.debug(
                "tool_use_id=%s 找不到 entry（可能已被 SubagentStop 先清）",
                tool_use_id,
            )
    elif not agent_id_from_response:
        logger.warning("tool_response 無 agentId")

    # Housekeeping: 清理超時記錄
    expired_count = cleanup_expired(project_root)
    if expired_count > 0:
        messages.append(f"已清理 {expired_count} 筆超時派發記錄")
        logger.info("已清理 %d 筆超時派發記錄", expired_count)

    # Housekeeping: 偵測 orphan 分支
    orphans = detect_orphan_branches(project_root)
    if orphans:
        orphan_list = ", ".join(orphans)
        messages.append(
            f"[WARNING] 偵測到 {len(orphans)} 個 orphan worktree 分支: {orphan_list}"
        )
        logger.info("偵測到 orphan worktree 分支: %s", orphan_list)

    # 不再做 clear_dispatch、不再做 [OK]/[WAIT] 廣播（由 SubagentStop handler 負責）

    if not messages:
        return 0

    context = " | ".join(messages)
    print(json.dumps({
        "hookSpecificOutput": {
            "hookEventName": "PostToolUse",
            "additionalContext": context,
        }
    }))

    return 0


if __name__ == "__main__":
    sys.exit(run_hook_safely(main, HOOK_NAME))
