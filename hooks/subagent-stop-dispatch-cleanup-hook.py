#!/usr/bin/env python3
# /// script
# requires-python = ">=3.9"
# dependencies = []
# ///
"""
SubagentStop Dispatch Cleanup Hook

功能: 代理人真正完成時精準清理 dispatch-active.json 記錄 + 完成廣播。
觸發時機: SubagentStop（CC runtime 保證代理人真正停止才觸發）
行為: 不阻擋（exit 0），在 additionalContext 輸出 [OK]/[WAIT] 狀態

來源: W10-066 — 從 PostToolUse(Agent) 遷移清理和廣播職責到 SubagentStop
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from hook_utils import setup_hook_logging, run_hook_safely, read_json_from_stdin

sys.path.insert(0, str(Path(__file__).parent / "lib"))
from dispatch_tracker import (
    clear_dispatch_by_id,
    clear_oldest_null_agent_id_entry,
    get_active_dispatches,
    get_state_file_path,
)

HOOK_NAME = "subagent-stop-dispatch-cleanup"


def main() -> int:
    """SubagentStop 主邏輯：精準清理 + fallback + 三態廣播。"""
    logger = setup_hook_logging(HOOK_NAME)

    try:
        input_data = read_json_from_stdin(logger)
    except (json.JSONDecodeError, EOFError):
        logger.warning("無法解析 stdin JSON")
        return 0

    if not input_data:
        logger.debug("stdin 無資料，跳過")
        return 0

    agent_id = input_data.get("agent_id", "")

    if not agent_id:
        logger.error("SubagentStop 無 agent_id（schema violation）")
        return 0

    # 定位專案根目錄
    project_root = Path(__file__).resolve().parent.parent.parent
    state_file = get_state_file_path(project_root)

    if not state_file.exists():
        logger.debug("dispatch-active.json 不存在，跳過")
        return 0

    messages = []
    cleared = False

    # 主路徑：agent_id 精準清理
    cleared = clear_dispatch_by_id(project_root, agent_id)

    if not cleared:
        # Fallback：清理 agent_id=null 且 dispatched_at 最早的一筆（FIFO）
        # SubagentStop input 無 description 欄位，無法做 description 匹配
        fallback_cleared = clear_oldest_null_agent_id_entry(project_root)
        if fallback_cleared:
            logger.info(
                "SubagentStop fallback 清理（agent_id=%s 無精準匹配，FIFO 清理最早 null entry）",
                agent_id,
            )
            cleared = True
        else:
            logger.warning(
                "SubagentStop agent_id=%s 無匹配記錄（精準和 FIFO 兩路徑皆失敗）",
                agent_id,
            )

    if cleared:
        messages.append(f"已清理派發記錄 agent_id={agent_id}")

    # 三態廣播（從 active-dispatch-tracker-hook 遷移）
    remaining = get_active_dispatches(project_root)
    if remaining:
        agents_list = ", ".join(
            d.get("agent_description", "?") for d in remaining
        )
        messages.append(
            "[WAIT] 仍有 {} 個代理人在執行: {}".format(len(remaining), agents_list)
        )
    elif cleared:
        messages.append("[OK] 所有代理人已完成，可開始驗收")

    if not messages:
        return 0

    context = " | ".join(messages)
    print(json.dumps({
        "hookSpecificOutput": {
            "hookEventName": "SubagentStop",
            "additionalContext": context,
        }
    }))

    return 0


if __name__ == "__main__":
    sys.exit(run_hook_safely(main, HOOK_NAME))
