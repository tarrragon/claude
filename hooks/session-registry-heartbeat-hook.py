#!/usr/bin/env python3
# /// script
# requires-python = ">=3.9"
# dependencies = []
# ///

"""
Session Registry Heartbeat Hook - UserPromptSubmit

功能:
  每次用戶提交 prompt 時，更新自身在 pm-registry.json 的 heartbeat_ts，
  讓其他並行 PM session 能判斷本 session 是否仍存活（stale 判定由查詢端
  `ticket track sessions` 負責，本 hook 只負責寫入新鮮的時間戳）。

  Debounce >= 60 秒：距上次心跳未滿 60 秒時跳過寫入，避免高頻互動場景
  下每個 prompt 都觸發一次 flock 保護的 read-modify-write。

  entry 缺失時（registry 曾損毀重建、或 SessionStart 註冊失敗）自我修復
  補建，避免永久缺席直到下次 SessionStart（見 lib.pm_registry.update_
  heartbeat 的 upsert 語意）。

  子代理人環境（agent_id 存在於 stdin）不觸發，理由同 session-registry-
  start-hook.py。

觸發時機: 每次用戶提交 prompt (UserPromptSubmit)
行為: 不阻擋、無 stdout 輸出（純背景寫入，不影響 prompt 流程）

Registry Schema 契約：見 .claude/lib/pm_registry.py 模組 docstring（SSOT）。

來源:
  - multi-PM 協調層 Phase 1（framework issue tarrragon/claude#77）
"""

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
sys.path.insert(0, str(Path(__file__).parent.parent))

from lib import (
    setup_hook_logging,
    read_json_from_stdin,
    is_subagent_environment,
    get_project_root,
    run_hook_safely,
    ENV_SESSION_ID,
)
from lib.pm_registry import get_registry_paths, update_heartbeat

HOOK_NAME = "session-registry-heartbeat-hook"
EXIT_SUCCESS = 0


def resolve_session_id(input_data) -> str:
    """優先取 stdin session_id，缺失時 fallback CC runtime 環境變數。"""
    if input_data:
        sid = input_data.get("session_id")
        if sid:
            return sid
    return os.environ.get(ENV_SESSION_ID, "")


def main() -> int:
    logger = setup_hook_logging(HOOK_NAME)
    input_data = read_json_from_stdin(logger)

    if is_subagent_environment(input_data):
        logger.debug("subagent environment, skip heartbeat update")
        return EXIT_SUCCESS

    session_id = resolve_session_id(input_data)
    if not session_id:
        message = "[session-registry-heartbeat-hook] 無法取得 session_id，跳過心跳更新"
        sys.stderr.write(message + "\n")
        logger.warning(message)
        return EXIT_SUCCESS

    project_root = get_project_root()
    registry_file, lock_file = get_registry_paths(cwd=str(project_root))

    try:
        wrote = update_heartbeat(
            registry_file=registry_file,
            lock_file=lock_file,
            session_id=session_id,
            name=project_root.name,
            project=str(project_root),
            logger=logger,
        )
        if wrote:
            logger.info("heartbeat 已更新: session_id=%s", session_id)
        else:
            logger.debug("heartbeat debounce 命中，跳過寫入: session_id=%s", session_id)
    except OSError as e:
        message = "[session-registry-heartbeat-hook] heartbeat 更新失敗: {}".format(e)
        sys.stderr.write(message + "\n")
        logger.warning(message)

    return EXIT_SUCCESS


if __name__ == "__main__":
    sys.exit(run_hook_safely(main, HOOK_NAME))
