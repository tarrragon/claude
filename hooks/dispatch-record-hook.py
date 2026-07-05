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

  1.5.0-W5-005.2 擴充（派發身份前移）:
  派發時提取 prompt 首行 Ticket ID（PC-065 格式）與 subagent_type，
  僅在 who.current 為無主態時經 ticket CLI 綁定執行者身份。
  已綁定態不覆蓋——審查型派發（如 acceptance-auditor 對他人票）的 prompt
  首行同樣含 Ticket ID，無條件綁定會 clobber 真執行者身份。

觸發時機: Agent 工具呼叫前 (PreToolUse, matcher: Agent)
行為: 不阻擋（exit 0），記錄派發後靜默通過；身份綁定全失敗路徑僅 log warning

來源:
  - PC-050 — PM 在代理人仍在工作時誤判完成
  - dispatch-active.json 從未被寫入（缺少記錄端）
  - W5-005 F1a — 17% completed 票身份從未回填，派發時已知身份未落 ticket
"""

import json
import logging
import re
import subprocess
import sys
from pathlib import Path
from typing import Optional

sys.path.insert(0, str(Path(__file__).parent))
sys.path.insert(0, str(Path(__file__).parent.parent))

from lib import (
    setup_hook_logging,
    read_json_from_stdin,
    extract_tool_input,
    is_subagent_environment,
    get_project_root,
    run_hook_safely,
)
from lib.dispatch_tracker import record_dispatch

# ============================================================================
# 常數定義
# ============================================================================

HOOK_NAME = "dispatch-record-hook"
EXIT_SUCCESS = 0

# Ticket ID 格式（PC-065 prompt 首行慣例）；(?:\.\d+)* 涵蓋子票後綴（如 1.5.0-W5-005.2）
TICKET_ID_PATTERN = re.compile(r"(\d+\.\d+\.\d+-W\d+-\d+(?:\.\d+)*)")

# who.current 無主態值：create 未指定 --who 時為字面 "pending"，
# PM 建票模板慣用 "待派發"；execute_get_field 對缺值輸出 "?"
UNBOUND_WHO_VALUES = {"pending", "待派發", "?", ""}

# ticket CLI 逾時秒數（shim 經 uv run 解析，冷啟動可達數秒）
TICKET_CLI_TIMEOUT = 15


# ============================================================================
# 派發身份前移（1.5.0-W5-005.2）
# ============================================================================


def extract_ticket_id(prompt: str) -> Optional[str]:
    """從派發 prompt 首行提取 Ticket ID；非 ticket 派發（無 ID）回傳 None。"""
    if not prompt or not prompt.strip():
        return None
    first_line = prompt.strip().splitlines()[0]
    match = TICKET_ID_PATTERN.search(first_line)
    return match.group(1) if match else None


def _run_ticket_cli(
    args: list, project_root: Path, logger: logging.Logger
) -> Optional[str]:
    """執行 ticket CLI 子命令，回傳 stdout；任何失敗回 None（非阻擋）。"""
    cmd = ["ticket", "track"] + args
    try:
        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=TICKET_CLI_TIMEOUT,
            cwd=project_root,
        )
        if proc.returncode != 0:
            logger.warning(
                "ticket CLI 非零退出 (rc=%s, cmd=%s): %s",
                proc.returncode,
                " ".join(cmd),
                proc.stderr.strip()[:200],
            )
            return None
        return proc.stdout
    except (subprocess.TimeoutExpired, OSError) as e:
        logger.warning("ticket CLI 執行失敗 (cmd=%s): %s", " ".join(cmd), e)
        return None


def parse_who_value(stdout: str) -> Optional[str]:
    """解析 `ticket track who <id>` 輸出（格式 `Who: <value>`）；解析失敗回 None。"""
    if not stdout:
        return None
    for line in stdout.splitlines():
        if line.startswith("Who:"):
            return line[len("Who:"):].strip()
    return None


def bind_dispatch_identity(
    ticket_id: str,
    subagent_type: str,
    project_root: Path,
    logger: logging.Logger,
) -> bool:
    """無主態時將 who.current 綁定為派發的 subagent_type；回傳是否實際綁定。

    讀寫皆走 ticket CLI 而非直接 parse/Edit ticket md——維持寫入路徑收斂
    （W5-005 F3），避免 hook 成為另一個繞過驗證閘的寫入者。
    """
    who_stdout = _run_ticket_cli(["who", ticket_id], project_root, logger)
    if who_stdout is None:
        return False

    current_who = parse_who_value(who_stdout)
    if current_who is None:
        logger.warning("無法解析 who 輸出，跳過身份綁定: %s", who_stdout.strip()[:100])
        return False

    if current_who not in UNBOUND_WHO_VALUES:
        logger.debug("who.current 已綁定 (%s)，不覆蓋", current_who)
        return False

    set_stdout = _run_ticket_cli(
        ["set-who", ticket_id, subagent_type], project_root, logger
    )
    if set_stdout is None:
        return False

    logger.info("派發身份已綁定: %s -> who.current=%s", ticket_id, subagent_type)
    return True


# ============================================================================
# 核心邏輯
# ============================================================================


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

    # 記錄派發
    try:
        record_dispatch(
            project_root=project_root,
            agent_description=agent_description,
            tool_use_id=tool_use_id,
            branch_name="worktree" if isolation == "worktree" else "",
        )
        logger.info(
            "recorded dispatch: %s (isolation=%s)",
            agent_description,
            isolation or "none",
        )
    except Exception as e:
        # 記錄失敗不阻擋派發
        logger.warning("record_dispatch failed: %s", e)

    # 派發身份前移（1.5.0-W5-005.2）：prompt 含 Ticket ID 且指名 subagent_type
    # 時才嘗試綁定；缺任一者代表無穩定身份可綁（generic 派發），跳過
    ticket_id = extract_ticket_id(tool_input.get("prompt", ""))
    subagent_type = (tool_input.get("subagent_type") or "").strip()
    if ticket_id and subagent_type:
        try:
            bind_dispatch_identity(ticket_id, subagent_type, project_root, logger)
        except Exception as e:
            # 綁定失敗不阻擋派發（agent 端仍有 claim --as fallback）
            logger.warning("bind_dispatch_identity failed: %s", e)

    return EXIT_SUCCESS


if __name__ == "__main__":
    sys.exit(run_hook_safely(main, HOOK_NAME))
