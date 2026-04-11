#!/usr/bin/env python3
# /// script
# requires-python = ">=3.9"
# dependencies = []
# ///
"""
Active Dispatch Tracker Hook - PostToolUse (Agent)

功能: Agent 完成後清理 dispatch 記錄、清理超時記錄、偵測 orphan branch
觸發時機: Agent 工具完成後 (PostToolUse, matcher: Agent)
行為: 不阻擋（exit 0），在 additionalContext 輸出狀態

Ticket: 0.17.2-W7-004
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from hook_utils import setup_hook_logging, run_hook_safely, read_json_from_stdin

sys.path.insert(0, str(Path(__file__).parent / "lib"))
from dispatch_tracker import clear_dispatch, cleanup_expired, detect_orphan_branches
from dispatch_tracker import get_state_file_path, get_active_dispatches

HOOK_NAME = "active-dispatch-tracker"


def main() -> int:
    """Hook 主邏輯。"""
    logger = setup_hook_logging(HOOK_NAME)

    try:
        input_data = read_json_from_stdin(logger)
    except (json.JSONDecodeError, EOFError):
        logger.warning("無法解析 stdin JSON")
        return 0

    if not input_data:
        logger.debug("stdin 無資料，跳過")
        return 0

    tool_input = input_data.get("tool_input", {})
    agent_description = tool_input.get("description", "")

    if not agent_description:
        logger.debug("無 agent description，跳過清理")
        return 0

    # 定位專案根目錄
    project_root = Path(__file__).resolve().parent.parent.parent
    state_file = get_state_file_path(project_root)

    if not state_file.exists():
        logger.debug("dispatch-active.json 不存在，跳過")
        return 0

    messages = []

    # 清理對應的 dispatch 記錄
    cleared = clear_dispatch(project_root, agent_description)
    if cleared:
        messages.append(f"已清理派發記錄: {agent_description}")
        logger.info("已清理派發記錄: %s", agent_description)
    else:
        logger.debug("未找到匹配的派發記錄: %s", agent_description)

    # 清理超時記錄
    expired_count = cleanup_expired(project_root)
    if expired_count > 0:
        messages.append(f"已清理 {expired_count} 筆超時派發記錄")
        logger.info("已清理 %d 筆超時派發記錄", expired_count)

    # 偵測 orphan 分支
    orphans = detect_orphan_branches(project_root)
    if orphans:
        orphan_list = ", ".join(orphans)
        messages.append(
            f"[WARNING] 偵測到 {len(orphans)} 個 orphan worktree 分支: {orphan_list}"
        )
        logger.info("偵測到 orphan worktree 分支: %s", orphan_list)

    # 查詢剩餘活躍派發（讓 PM 知道還有幾個代理人在執行）
    remaining = get_active_dispatches(project_root)
    if remaining:
        agents_list = ", ".join(
            d.get("agent_description", "?") for d in remaining
        )
        messages.append(
            "[WAIT] 仍有 {} 個代理人在執行: {}".format(len(remaining), agents_list)
        )
    else:
        messages.append("[OK] 所有代理人已完成，可開始驗收")

    # 輸出 additionalContext
    context = " | ".join(messages)
    print(json.dumps({"additionalContext": context}))

    return 0


if __name__ == "__main__":
    sys.exit(run_hook_safely(main, HOOK_NAME))
