#!/usr/bin/env python3
# /// script
# requires-python = ">=3.9"
# dependencies = []
# ///

"""
Session Registry Stop Hook - Stop

功能:
  主線程停止（每回合結束、等待下個用戶輸入）時，將自身自 pm-registry.json
  移除（graceful release）。下次 UserPromptSubmit 觸發時，heartbeat hook
  的自我修復語意會重新補建 entry；異常終止（程序被 kill、崩潰）未經過
  本 hook 的殘留 entry，交由查詢端的 30 分鐘 stale 閾值判定收斂（本 hook
  是快速/常見路徑，stale 閾值是慢速/異常終止的 fallback 路徑）。

  背景代理人監控中（stdin.background_tasks 非空）時跳過釋放：PM 主線程
  雖進入 Stop，但仍在協調背景派發（非真正閒置等待用戶輸入），此時移除
  entry 會讓其他並行 PM 誤判本 session 已結束。

  子代理人環境（agent_id 存在於 stdin）不觸發，理由同 session-registry-
  start-hook.py——subagent 本就未被本 hook 組註冊進 registry。

觸發時機: 主線程每回合停止時 (Stop)
行為: 不阻擋（無 block 決策），無 stdout 輸出

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
from lib.pm_registry import get_registry_paths, release_session

HOOK_NAME = "session-registry-stop-hook"
EXIT_SUCCESS = 0


def resolve_session_id(input_data) -> str:
    """優先取 stdin session_id，缺失時 fallback CC runtime 環境變數。"""
    if input_data:
        sid = input_data.get("session_id")
        if sid:
            return sid
    return os.environ.get(ENV_SESSION_ID, "")


def has_background_agents(input_data, logger) -> bool:
    """判斷是否有背景代理人執行中（弱依賴策略：只判斷 list 非空）。

    欄位不存在（舊版 CC runtime）/ 非 list / 空 list 皆回 False，
    此時視為「真正閒置」，不阻擋 release（與既有 handoff-auto-resume-
    stop-hook.py 的 has_background_agents 同判準，各自獨立實作——
    兩者用途不同不共用模組：本 hook 只需布林早退，不需該檔額外的
    started_at fallback 推斷邏輯）。
    """
    if not isinstance(input_data, dict):
        return False
    bg_tasks = input_data.get("background_tasks")
    if not isinstance(bg_tasks, list):
        return False
    has_active = len(bg_tasks) > 0
    if has_active:
        logger.info(
            "background_tasks 非空（%d 項），跳過 registry 釋放", len(bg_tasks)
        )
    return has_active


def main() -> int:
    logger = setup_hook_logging(HOOK_NAME)
    input_data = read_json_from_stdin(logger)

    if is_subagent_environment(input_data):
        logger.debug("subagent environment, skip registry release")
        return EXIT_SUCCESS

    if has_background_agents(input_data or {}, logger):
        return EXIT_SUCCESS

    session_id = resolve_session_id(input_data)
    if not session_id:
        message = "[session-registry-stop-hook] 無法取得 session_id，跳過 registry 釋放"
        sys.stderr.write(message + "\n")
        logger.warning(message)
        return EXIT_SUCCESS

    project_root = get_project_root()
    registry_file, lock_file = get_registry_paths(cwd=str(project_root))

    try:
        released = release_session(
            registry_file=registry_file,
            lock_file=lock_file,
            session_id=session_id,
            logger=logger,
        )
        if released:
            logger.info("session 已自 pm-registry 釋放: session_id=%s", session_id)
        else:
            logger.debug("registry 內無此 session entry，無需釋放: session_id=%s", session_id)
    except OSError as e:
        message = "[session-registry-stop-hook] registry 釋放失敗: {}".format(e)
        sys.stderr.write(message + "\n")
        logger.warning(message)

    return EXIT_SUCCESS


if __name__ == "__main__":
    sys.exit(run_hook_safely(main, HOOK_NAME))
