#!/usr/bin/env -S uv run --quiet --script
# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""
Released Dispatch Restore Hook - PreToolUse(Bash) 分派群組第一位

功能: 已釋放（ticket track dispatch-check --release）的子代理人以任何路徑恢復後，
      在它自己第一次呼叫 Bash 時，以 payload 的 agent_id 比對釋放紀錄並把派發條目放回。
      涵蓋不經 SendMessage 的恢復路徑（背景工作完成後代理人自行恢復）；SendMessage 路徑
      仍由 active-dispatch-tracker-hook 的 PostToolUse(SendMessage) 處理。

為何掛在 PreToolUse:Bash 分派群組第一位:
  hook-dispatcher 的序列段依 registry 順序在同一行程內執行，排第一位的放回必定先於
  同群組的 bare-commit-guard 與 workspace-wipe-guard 判定；兩者是條目缺席時看不到
  恢復中代理人的守衛，且都只看 Bash。不另開全工具註冊：同事件的獨立 hook 並行執行、
  不保證先後，且每次工具呼叫都要多啟動一個行程。

比對: agent_id 完全相等（實機觀測：子代理人 payload 的 agent_id 與 spawn 回傳 ID 逐字相同）。

輸出: 不輸出任何決策（不影響同群組其他守衛的判定）。
失敗語意: fail-open。放回失敗時寫 stderr 與日誌，結束碼 0，不 deny。
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
sys.path.insert(0, str(Path(__file__).parent.parent))

from lib import setup_hook_logging, run_hook_safely, read_json_from_stdin
from lib.git_utils import get_project_root
from lib.dispatch_tracker import restore_released_by_agent_id

HOOK_NAME = "released-dispatch-restore"


def main() -> int:
    logger = setup_hook_logging(HOOK_NAME)
    try:
        input_data = read_json_from_stdin(logger)
    except (json.JSONDecodeError, EOFError):
        logger.warning("無法解析 stdin JSON，放行")
        return 0
    if not input_data or input_data.get("tool_name") != "Bash":
        return 0

    agent_id = input_data.get("agent_id")
    if not isinstance(agent_id, str) or not agent_id:
        # 主線程（無 agent_id）：沒有可放回的代理人，不讀狀態檔
        return 0

    try:
        entry = restore_released_by_agent_id(get_project_root(), agent_id)
    except Exception as e:  # fail-open：放回失敗只讓守衛暫時看不到該代理人，不擋命令
        logger.warning("已釋放條目放回失敗 (agent_id=%s): %s", agent_id, e)
        sys.stderr.write(f"[{HOOK_NAME}] 代理人 {agent_id} 的派發條目放回失敗: {e}\n")
        return 0

    if entry is not None:
        logger.info(
            "已釋放代理人恢復後首次 Bash，派發條目已放回 (agent_id=%s, agent_handle=%s)",
            agent_id, entry.get("agent_handle") or "none",
        )
    return 0


if __name__ == "__main__":
    sys.exit(run_hook_safely(main, HOOK_NAME))
