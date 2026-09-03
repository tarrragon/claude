#!/usr/bin/env python3
# /// script
# requires-python = ">=3.9"
# dependencies = ["pyyaml"]
# ///
"""
Active Dispatch Tracker Hook - PostToolUse (Agent)

功能: PostToolUse(Agent) 觸發時記錄派發到 dispatch-active.json（含 agent_id）+
      housekeeping（超時清理/orphan 偵測）。
      dispatch 記錄清理和完成廣播已遷移至 SubagentStop handler（W10-066）。

觸發時機: Agent 工具完成後 (PostToolUse, matcher: Agent)
行為: 不阻擋（exit 0），在 additionalContext 輸出 housekeeping 訊息

背景（幽靈派發記錄修復票，承接 who.current 綁定遷移票 / issue 47）：
  記錄派發資訊的職責原本掛在 dispatch-record-hook.py（PreToolUse:Agent）。
  PreToolUse(Agent) matcher 下所有 hook 皆會執行、deny 為彙總結果，該 hook
  的寫入無法感知同批次是否已被其他 PreToolUse hook（如 PC-019）拒絕——被
  阻擋的派發仍會留下 agent_id=None 的幽靈記錄，因無對應 agent 啟動，
  SubagentStop 永不觸發、記錄永不清除，進而污染 bare-commit-guard 的並行
  判定。

  who.current 綁定遷移票已把身份綁定用同一理由遷至 PostToolUse，本次比照
  同一先例把 dispatch-active.json 記錄本身也遷過來。實測驗證（本票派發
  自身：PreToolUse dispatch-record-hook 與 PostToolUse active-dispatch-
  tracker 相隔僅 2 秒，agent_id 已補齊，此時被派發的 agent 仍在執行中）
  確認 PostToolUse(Agent) 於背景/worktree 派發時在「派發啟動」當下觸發，
  非等 agent 完成才觸發——移至 PostToolUse 不會延誤 bare-commit-guard 需
  要讀到記錄的時間窗。PostToolUse 只在 Agent 工具實際執行（未被任何
  PreToolUse hook deny）後才觸發，天然具備「派發已成功」語意，不需在寫
  入端重建交易回滾。

來源:
  - PC-050 — PM 在代理人仍在工作時誤判完成
  - who.current 綁定遷移票（issue 47 殘留缺口修復）
  - 幽靈派發記錄修復票（dispatch-active.json 記錄遷移至 PostToolUse）
  - multi-PM 協調層 Phase 1（framework issue tarrragon/claude#77）—
    補 session_id/ticket_id/files 欄位，供 pm-registry 交叉比對
  - SubagentStop 刪除記錄前提失準修復票 — 補 name 欄位（named agent 的
    subagent_type），配合 SubagentStop 改標記不刪除，殘留代理人排查時
    需要此欄位反查身份
  - 識別碼命名空間修復票 — 補 agent_handle 欄位（Agent 工具的 name
    參數，非上方 subagent_type persona）。實測 tool_response.agentId
    對 named 派發不可靠（68% 缺席，即使有值也與 SubagentStop 回報的
    agent_id 屬不同命名空間），agent_handle 於 dispatch 當下同步可得，
    供 SubagentStop 精準比對（見 dispatch_tracker.py 模組 docstring）
"""

import json
import sys
from pathlib import Path
from typing import Optional

sys.path.insert(0, str(Path(__file__).parent))
sys.path.insert(0, str(Path(__file__).parent.parent))

from lib import (
    setup_hook_logging,
    run_hook_safely,
    read_json_from_stdin,
    emit_hook_output,
    extract_tool_input,
    is_subagent_environment,
    resolve_session_id,
)
# dispatch-active.json 為跨 worktree 全域狀態，用 git_utils 版
# get_project_root（CLAUDE_PROJECT_DIR 導向，恆指主 repo），而非
# lib.hook_base 的 worktree 感知版本（見 ARCH-BAL-020）
from lib.git_utils import get_project_root

from lib.dispatch_tracker import (
    record_dispatch,
    cleanup_expired,
    detect_orphan_branches,
)
from lib.hook_ticket import extract_where_files
from lib.ticket_id_pattern import SEARCH_WITH_SUFFIX_RE, extract_ticket_id_anchored

HOOK_NAME = "active-dispatch-tracker"


def extract_ticket_id(prompt: str, description: str) -> Optional[str]:
    """從派發 prompt 首行提取 Ticket ID；缺則從 description 全文搜尋補。

    與原 dispatch-record-hook.py（PreToolUse）的同名函式邏輯一致，記錄職
    責搬遷時一併移過來（PostToolUse 亦能讀到 tool_input，見
    dispatch-identity-bind-hook.py 的先例）。
    """
    if prompt and prompt.strip():
        first_line = prompt.strip().splitlines()[0]
        ticket_id = extract_ticket_id_anchored(first_line)
        if ticket_id:
            return ticket_id

    if description:
        match = SEARCH_WITH_SUFFIX_RE.search(description)
        if match:
            return match.group(1)

    return None


def main() -> int:
    """Hook 主邏輯：記錄派發（含 agent_id）+ housekeeping。"""
    logger = setup_hook_logging(HOOK_NAME)

    try:
        input_data = read_json_from_stdin(logger)
    except (json.JSONDecodeError, EOFError):
        logger.warning("無法解析 stdin JSON")
        return 0

    # 子代理人環境不觸發（避免巢狀記錄，與原 dispatch-record-hook.py 一致）
    if is_subagent_environment(input_data):
        logger.debug("subagent environment, skip")
        return 0

    if not input_data:
        logger.debug("stdin 無資料，跳過")
        return 0

    tool_input = extract_tool_input(input_data, logger)
    tool_use_id = input_data.get("tool_use_id", "")
    tool_response = input_data.get("tool_response", {})
    if isinstance(tool_response, str):
        tool_response = {}
    agent_id_from_response = tool_response.get("agentId")
    if not agent_id_from_response:
        logger.warning("tool_response 無 agentId")

    project_root = get_project_root()

    agent_description = tool_input.get("description", "unknown")
    isolation = tool_input.get("isolation", "")
    session_id = resolve_session_id(input_data)
    ticket_id = extract_ticket_id(tool_input.get("prompt", ""), agent_description)
    name = tool_input.get("subagent_type", "") or ""
    # 可定址短 handle（Agent 工具的 name 參數，非上方 subagent_type
    # persona）。CC runtime 會把此值編入 SubagentStop 回報的 agent_id
    # （格式 a<handle>-<hex>），dispatch 當下同步可得，用於
    # mark_turn_ended_by_handle 的精準比對（見 dispatch_tracker.py
    # 模組 docstring「agent_handle 欄位」段的完整根因與依據）。
    agent_handle = tool_input.get("name", "") or ""

    files = []
    if ticket_id:
        try:
            files = extract_where_files(ticket_id, project_root=project_root, logger=logger)
        except Exception as e:
            logger.warning("extract_where_files failed (ticket_id=%s): %s", ticket_id, e)

    try:
        record_dispatch(
            project_root=project_root,
            agent_description=agent_description,
            tool_use_id=tool_use_id,
            ticket_id=ticket_id or "",
            files=files,
            branch_name="worktree" if isolation == "worktree" else "",
            agent_id=agent_id_from_response,
            session_id=session_id,
            name=name,
            agent_handle=agent_handle,
        )
        logger.info(
            "recorded dispatch: %s (isolation=%s, ticket_id=%s, files=%d, "
            "agent_id=%s, session_id=%s, name=%s, agent_handle=%s)",
            agent_description,
            isolation or "none",
            ticket_id or "none",
            len(files),
            agent_id_from_response or "none",
            session_id or "none",
            name or "none",
            agent_handle or "none",
        )
    except Exception as e:
        # 記錄失敗不阻擋（PostToolUse 不可阻擋已完成的工具呼叫）
        logger.warning("record_dispatch failed: %s", e)

    messages = []

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
    # housekeeping 訊息為 PM-only：統一出口過濾 subagent 觸發（PC-V1-004 防護 C）
    emit_hook_output(
        "PostToolUse",
        additional_context=context,
        audience="pm_only",
        input_data=input_data,
    )

    return 0


if __name__ == "__main__":
    sys.exit(run_hook_safely(main, HOOK_NAME))
