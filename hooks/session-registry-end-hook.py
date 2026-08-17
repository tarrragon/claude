#!/usr/bin/env python3
# /// script
# requires-python = ">=3.9"
# dependencies = []
# ///

"""
Session Registry End Hook - SessionEnd

功能:
  PM session 正常結束（含 /clear、視窗關閉等 graceful 路徑）時，將自身
  自 pm-registry.json 移除（graceful release）。本專案首次註冊 SessionEnd
  事件，acceptance 要求實機 /clear 驗證本 hook 確實觸發（liveness 證據）。

  取代 v1 掛在 Stop 的釋放邏輯（契約 v2 D1）：Stop 每回合觸發非 session
  終結，v1 設計使 debounce 淪為 dead code、Phase 2 lease 欄位每回合被
  清空重建（見 session-registry-stop-heartbeat-hook.py docstring「v1 到
  v2 的變更」段完整說明）。SessionEnd 語意正確對齊「整個 session 結束一
  次」，background_tasks 守衛（v1 用於避免 PM 仍在協調背景派發時被誤判
  結束）隨之不再需要而移除——SessionEnd 本就只在 session 真正結束時觸發。

  kill/crash 等非 graceful 終止不觸發 SessionEnd，由 30 分 TTL 兜底
  （stale 判定留待後續階段實作，本票不處理 reclaim）。

  子代理人環境（agent_id 存在於 stdin）不觸發，理由同 session-registry-
  start-hook.py——subagent 本就未被 SessionStart/heartbeat 兩支 hook
  註冊進 registry，SessionEnd 對應找不到 entry 屬正常無操作。

  非 git 環境（`get_registry_paths` 回傳 None）跳過釋放並 stderr 一次性
  提示（契約 v2 D3：不再 fallback 寫入讀端永不查詢的暫定路徑）。

觸發時機: CC session 正常結束時 (SessionEnd)
行為: 不阻擋（SessionEnd 無 deny 機制），無 stdout 輸出

Registry Schema 契約：見 .claude/lib/pm_registry.py 模組 docstring（SSOT）。

來源:
  - Registry Schema 契約 v2 D1（釋放時機改掛 SessionEnd，framework issue
    tarrragon/claude#77）
"""

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
    resolve_session_id,
)
from lib.pm_registry import get_registry_paths, release_session

HOOK_NAME = "session-registry-end-hook"
EXIT_SUCCESS = 0


def main() -> int:
    logger = setup_hook_logging(HOOK_NAME)
    input_data = read_json_from_stdin(logger)

    if is_subagent_environment(input_data):
        logger.debug("subagent environment, skip registry release")
        return EXIT_SUCCESS

    session_id = resolve_session_id(input_data)
    if not session_id:
        message = (
            "[session-registry-end-hook] 無法取得 session_id，跳過 registry 釋放"
            "（本 session 的 registry entry 若存在將殘留，逾 30 分鐘由 STALE 判定自然淘汰，"
            "無需手動處置）"
        )
        sys.stderr.write(message + "\n")
        logger.warning(message)
        return EXIT_SUCCESS

    project_root = get_project_root()
    registry_paths = get_registry_paths(cwd=str(project_root), logger=logger)
    if registry_paths is None:
        message = (
            "[session-registry-end-hook] 非 git 環境，跳過 registry 釋放"
            "（跨 session 協調功能於此環境本不適用，無需處置）"
        )
        sys.stderr.write(message + "\n")
        logger.info(message)
        return EXIT_SUCCESS
    registry_file, lock_file = registry_paths

    try:
        released = release_session(
            registry_file=registry_file,
            lock_file=lock_file,
            session_id=session_id,
            logger=logger,
        )
        if released:
            logger.info("session 已自 pm-registry 釋放（SessionEnd）: session_id=%s", session_id)
        else:
            logger.debug("registry 內無此 session entry，無需釋放: session_id=%s", session_id)
    except OSError as e:
        message = (
            "[session-registry-end-hook] registry 釋放失敗: {}"
            "（本 session 的 registry entry 未被移除，逾 30 分鐘由 STALE 判定自然淘汰，"
            "無需手動處置）"
        ).format(e)
        sys.stderr.write(message + "\n")
        logger.warning(message)

    return EXIT_SUCCESS


if __name__ == "__main__":
    sys.exit(run_hook_safely(main, HOOK_NAME))
