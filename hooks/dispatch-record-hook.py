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

  0.2.1-W3-302：派發身份綁定（who.current，原 1.5.0-W5-005.2 擴充）已遷移至
  獨立的 PostToolUse(Agent) hook（dispatch-identity-bind-hook.py）。原因：
  PreToolUse(Agent) matcher 下所有 hook 皆會執行、deny 為彙總結果，本 hook
  的寫入無法感知同批次是否已被其他 PreToolUse hook（如 PC-019）拒絕，混合
  批次（非 worktree 票 + worktree 票同訊息派發）因此仍會自我阻塞（issue 47
  殘留缺口）。PostToolUse 只在工具實際執行後觸發，天然具備「派發已成功」
  語意，不需在寫入端重建交易回滾。本 hook 之後僅負責 dispatch-active.json
  記錄，不再涉及 who.current 寫入。

觸發時機: Agent 工具呼叫前 (PreToolUse, matcher: Agent)
行為: 不阻擋（exit 0），記錄派發後靜默通過

來源:
  - PC-050 — PM 在代理人仍在工作時誤判完成
  - dispatch-active.json 從未被寫入（缺少記錄端）
  - 0.2.1-W3-302 — who.current 綁定遷移至 PostToolUse（issue 47 殘留缺口修復）
  - multi-PM 協調層 Phase 1（framework issue tarrragon/claude#77）—
    補 session_id/parent_session_id/ticket_id/files 欄位，供 pm-registry
    交叉比對「哪個 PM session 派發了哪些工作」
"""

import os
import re
import sys
from pathlib import Path
from typing import Optional

sys.path.insert(0, str(Path(__file__).parent))
sys.path.insert(0, str(Path(__file__).parent.parent))

from lib import (
    setup_hook_logging,
    read_json_from_stdin,
    extract_tool_input,
    extract_where_files,
    is_subagent_environment,
    get_project_root,
    run_hook_safely,
    ENV_SESSION_ID,
)
from lib.dispatch_tracker import record_dispatch

# ============================================================================
# 常數定義
# ============================================================================

HOOK_NAME = "dispatch-record-hook"
EXIT_SUCCESS = 0

# Ticket ID 格式（與 dispatch-identity-bind-hook.py 同 pattern）
TICKET_ID_PATTERN = re.compile(r"(\d+\.\d+\.\d+-W\d+-\d+(?:\.\d+)*)")


# ============================================================================
# 核心邏輯
# ============================================================================


def extract_ticket_id(prompt: str, description: str) -> Optional[str]:
    """從 prompt 首行提取 Ticket ID；缺則從 description 全文搜尋補。

    prompt 比對範圍限首行，與 dispatch-identity-bind-hook.py 的
    extract_ticket_id 一致（PC-065 prompt 首行慣例——派發目標票應在
    prompt 首行）。全文搜尋會被 prompt 內文提及的前置/相關票（如 Context
    Bundle 引用先前結論收尾用的其他票 ID）誤配對搶先命中，連帶 files 查
    表也查到錯的票；首行沒有命中即代表本次派發未依慣例把目標票放在首
    行，改信任 description（通常是 PM 顯式標註的短標籤）補位，而非在全
    文亂猜。description 保留全文搜尋——其來源通常是簡短標籤，無固定位
    置慣例。
    """
    if prompt and prompt.strip():
        first_line = prompt.strip().splitlines()[0]
        match = TICKET_ID_PATTERN.search(first_line)
        if match:
            return match.group(1)

    if description:
        match = TICKET_ID_PATTERN.search(description)
        if match:
            return match.group(1)

    return None


def resolve_session_id(input_data: dict) -> str:
    """優先取 stdin session_id，缺失時 fallback CC runtime 環境變數。"""
    if input_data:
        sid = input_data.get("session_id")
        if sid:
            return sid
    return os.environ.get(ENV_SESSION_ID, "")


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

    # 取得 tool_use_id（PreToolUse 頂層欄位，用於 PostToolUse 補 agent_id）
    tool_use_id = input_data.get("tool_use_id", "")
    if not tool_use_id:
        logger.warning("PreToolUse 無 tool_use_id，使用 fallback 識別符")
        import time
        tool_use_id = f"unknown_{int(time.time())}"

    # 取得專案根目錄
    project_root = get_project_root()

    # 派發者（PM）自身 session_id；parent_session_id 依契約與 session_id
    # 同值（非血緣欄位，供 subagent 端自我歸屬所屬 PM session）
    session_id = resolve_session_id(input_data)
    parent_session_id = session_id

    # Ticket ID：prompt 內 regex 提取，缺則從 description 補
    ticket_id = extract_ticket_id(tool_input.get("prompt", ""), agent_description)

    # files：Ticket ID 可解析時查表 where.files；無 Ticket ID 則空清單
    files = []
    if ticket_id:
        try:
            files = extract_where_files(ticket_id, project_root=project_root, logger=logger)
        except Exception as e:
            logger.warning("extract_where_files failed (ticket_id=%s): %s", ticket_id, e)

    # 記錄派發
    try:
        record_dispatch(
            project_root=project_root,
            agent_description=agent_description,
            tool_use_id=tool_use_id,
            ticket_id=ticket_id or "",
            files=files,
            branch_name="worktree" if isolation == "worktree" else "",
            session_id=session_id,
            parent_session_id=parent_session_id,
        )
        logger.info(
            "recorded dispatch: %s (isolation=%s, ticket_id=%s, files=%d, session_id=%s)",
            agent_description,
            isolation or "none",
            ticket_id or "none",
            len(files),
            session_id or "none",
        )
    except Exception as e:
        # 記錄失敗不阻擋派發
        logger.warning("record_dispatch failed: %s", e)

    # 派發身份綁定（who.current）已遷移至 dispatch-identity-bind-hook.py
    # （PostToolUse:Agent，0.2.1-W3-302）。本 hook 不再處理身份綁定。

    return EXIT_SUCCESS


if __name__ == "__main__":
    sys.exit(run_hook_safely(main, HOOK_NAME))
