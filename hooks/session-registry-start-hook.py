#!/usr/bin/env python3
# /// script
# requires-python = ">=3.9"
# dependencies = []
# ///

"""
Session Registry Start Hook - SessionStart

功能:
  PM session 啟動時，將自身註冊進跨 worktree 共享的 pm-registry.json
  （落於 `git rev-parse --git-common-dir` 解析出的主 .git/ 目錄），供同一
  repo 上其他並行 PM session 查詢存活狀態。

  子代理人環境（agent_id 存在於 stdin）不觸發，避免將短生命週期的
  subagent 執行誤記為獨立 PM session——registry 本意為 multi-PM 協調層
  （同一 repo 上多個獨立 worktree/branch 的主線程 PM），派發追蹤已由
  dispatch-active.json 承擔，兩者職責不重疊。

  registry 契約 v2（D4 增補 1）：依 stdin 的 `source` 欄位分流——
  `source == "resume"` 時 merge（繼承既有 lease，恢復語意）；其餘
  （startup/clear/未知值）一律 reset（新生 session 不繼承舊 lease，
  防 SessionEnd 漏觸發 + 同 session_id 重開時繼承 zombie lease）。

  非 git 環境（`get_registry_paths` 回傳 None）跳過註冊並 stderr 一次性
  提示（契約 v2 D3：不再 fallback 寫入讀端永不查詢的暫定路徑）。

觸發時機: 每個 CC session 啟動時 (SessionStart)
行為: 不阻擋（SessionStart 本就無 deny 機制），registry 損毀/缺檔時
      重建 + stderr 通知（雙通道可觀測性，異常不靜默）

Registry Schema 契約：見 .claude/lib/pm_registry.py 模組 docstring（SSOT）。

來源:
  - multi-PM 協調層 Phase 1（framework issue tarrragon/claude#77）
  - Registry Schema 契約 v2（釋放時機/欄位/upsert 語意重議，同 issue）
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
from lib.pm_registry import get_registry_paths, register_session

HOOK_NAME = "session-registry-start-hook"
EXIT_SUCCESS = 0


def main() -> int:
    logger = setup_hook_logging(HOOK_NAME)
    input_data = read_json_from_stdin(logger)

    if is_subagent_environment(input_data):
        logger.debug("subagent environment, skip registry registration")
        return EXIT_SUCCESS

    session_id = resolve_session_id(input_data)
    if not session_id:
        message = (
            "[session-registry-start-hook] 無法取得 session_id，跳過 registry 註冊"
            "（本 session 將不列於 `ticket track sessions`，無需處置）"
        )
        sys.stderr.write(message + "\n")
        logger.warning(message)
        return EXIT_SUCCESS

    source = (input_data or {}).get("source", "")

    project_root = get_project_root()
    registry_paths = get_registry_paths(cwd=str(project_root), logger=logger)
    if registry_paths is None:
        message = (
            "[session-registry-start-hook] 非 git 環境，跳過 registry 註冊"
            "（跨 session 協調功能於此環境本不適用，無需處置）"
        )
        sys.stderr.write(message + "\n")
        logger.info(message)
        return EXIT_SUCCESS
    registry_file, lock_file = registry_paths

    try:
        register_session(
            registry_file=registry_file,
            lock_file=lock_file,
            session_id=session_id,
            name=project_root.name,
            project=str(project_root),
            source=source,
            logger=logger,
        )
        logger.info(
            "session 已註冊至 pm-registry: session_id=%s name=%s source=%s",
            session_id,
            project_root.name,
            source or "(empty)",
        )
    except OSError as e:
        message = (
            "[session-registry-start-hook] registry 註冊失敗: {}"
            "（本 session 未寫入 registry，`ticket track sessions` 查詢不到本 session；"
            "下次 heartbeat 觸發時會自我修復補建 entry，無需手動處置）"
        ).format(e)
        sys.stderr.write(message + "\n")
        logger.warning(message)

    return EXIT_SUCCESS


if __name__ == "__main__":
    sys.exit(run_hook_safely(main, HOOK_NAME))
