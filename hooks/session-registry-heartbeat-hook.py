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

  雙心跳事件源（契約 v2 D1b 增補 3，禁止未來以「簡化」為由刪減任一方）：
  本 hook（UserPromptSubmit）蓋回合開頭；session-registry-stop-heartbeat-
  hook.py（Stop）蓋回合結尾。長回合（teammate 訊息驅動、無 UserPrompt
  Submit 觸發）期間仍有心跳覆蓋——單留任一事件源會重新打開觀測空洞
  （實測：代理協作密集的活躍 session heartbeat 停滯 55 分被誤判 STALE）。

  非 git 環境（`get_registry_paths` 回傳 None）跳過更新並 stderr 一次性
  提示（契約 v2 D3：不再 fallback 寫入讀端永不查詢的暫定路徑）。

觸發時機: 每次用戶提交 prompt (UserPromptSubmit)
行為: 不阻擋、無 stdout 輸出（純背景寫入，不影響 prompt 流程）

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
from lib.pm_registry import get_registry_paths, update_heartbeat

HOOK_NAME = "session-registry-heartbeat-hook"
EXIT_SUCCESS = 0


def main() -> int:
    logger = setup_hook_logging(HOOK_NAME)
    input_data = read_json_from_stdin(logger)

    if is_subagent_environment(input_data):
        logger.debug("subagent environment, skip heartbeat update")
        return EXIT_SUCCESS

    session_id = resolve_session_id(input_data)
    if not session_id:
        message = (
            "[session-registry-heartbeat-hook] 無法取得 session_id，跳過心跳更新"
            "（若持續發生，本 session 逾 30 分鐘後會被其他 session 判定為 STALE；"
            "請檢查 CLAUDE_CODE_SESSION_ID 環境變數是否正常）"
        )
        sys.stderr.write(message + "\n")
        logger.warning(message)
        return EXIT_SUCCESS

    project_root = get_project_root()
    registry_paths = get_registry_paths(cwd=str(project_root), logger=logger)
    if registry_paths is None:
        message = (
            "[session-registry-heartbeat-hook] 非 git 環境，跳過心跳更新"
            "（跨 session 協調功能於此環境本不適用，無需處置）"
        )
        sys.stderr.write(message + "\n")
        logger.info(message)
        return EXIT_SUCCESS
    registry_file, lock_file = registry_paths

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
        message = (
            "[session-registry-heartbeat-hook] heartbeat 更新失敗: {}"
            "（本次心跳未寫入，下次 UserPromptSubmit 觸發時會重試，單次失敗通常無需處置）"
        ).format(e)
        sys.stderr.write(message + "\n")
        logger.warning(message)

    return EXIT_SUCCESS


if __name__ == "__main__":
    sys.exit(run_hook_safely(main, HOOK_NAME))
