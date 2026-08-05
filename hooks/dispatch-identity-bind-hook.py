#!/usr/bin/env python3
# /// script
# requires-python = ">=3.9"
# dependencies = []
# ///

"""
Dispatch Identity Bind Hook - PostToolUse (Agent)

功能:
  Agent 派發「確定成功後」（PostToolUse），才將 who.current 綁定為派發的
  subagent_type。取代原本掛在 PreToolUse（dispatch-record-hook.py）的
  無條件寫入。

  背景（0.2.1-W3-302，承接 issue 47 / 0.2.1-W3-226）：
  PreToolUse(Agent) matcher 下所有 hook 皆會執行、deny 為彙總結果——
  worktree-commit-before-dispatch-hook.py（PC-019）只檢查
  isolation == "worktree" 的派發並可能回傳 exit 2 阻擋，但
  dispatch-record-hook.py 的身份綁定寫入不受該 deny 影響（兩者條件方向
  相反，各自獨立判斷）。混合批次（同訊息內非 worktree 票 + worktree 票）
  派發時，非 worktree 票的 who.current 寫入會弄髒主 repo，隨後 worktree
  票被 PC-019 擋下；且被擋下的派發仍留下 who.current 已綁但 agent 從未
  啟動的半套狀態。

  PostToolUse 只在 Agent 工具實際執行（未被任何 PreToolUse hook deny）
  後才觸發，天然具備「派發已成功」語意，不需在寫入端重建交易回滾。
  worktree 隔離派發維持 0.2.1-W3-226 的跳過行為——worktree 尚未建立、
  寫入必落在主 repo，由 worktree 代理人自行執行 `claim --as` 完成綁定。

觸發時機: Agent 工具呼叫完成後 (PostToolUse, matcher: Agent)
行為: 不阻擋（exit 0），身份綁定全失敗路徑僅 log warning

來源:
  - framework issue 47（混合批次自我阻塞殘留缺口）
  - 0.2.1-W3-226（worktree 隔離派發跳過綁定的既有判斷邏輯，原封不動保留）
  - 1.5.0-W5-005.2（派發身份前移的原始設計；本次僅搬遷觸發時機）
"""

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

# ============================================================================
# 常數定義
# ============================================================================

HOOK_NAME = "dispatch-identity-bind-hook"
EXIT_SUCCESS = 0

# Ticket ID 格式（PC-065 prompt 首行慣例）；(?:\.\d+)* 涵蓋子票後綴（如 1.5.0-W5-005.2）
TICKET_ID_PATTERN = re.compile(r"(\d+\.\d+\.\d+-W\d+-\d+(?:\.\d+)*)")

# who.current 無主態值：create 未指定 --who 時為字面 "pending"，
# PM 建票模板慣用 "待派發"；execute_get_field 對缺值輸出 "?"
UNBOUND_WHO_VALUES = {"pending", "待派發", "?", ""}

# ticket CLI 逾時秒數（shim 經 uv run 解析，冷啟動可達數秒）
TICKET_CLI_TIMEOUT = 15


# ============================================================================
# 派發身份綁定（原 dispatch-record-hook.py 1.5.0-W5-005.2，0.2.1-W3-302 遷移）
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

    isolation = tool_input.get("isolation", "")
    ticket_id = extract_ticket_id(tool_input.get("prompt", ""))
    subagent_type = (tool_input.get("subagent_type") or "").strip()

    # 0.2.1-W3-226（原封不動延用）：worktree 隔離派發時跳過。本 hook 已在
    # PostToolUse 觸發，Agent 呼叫已實際執行，但 worktree 建立與 cwd 切換
    # 是 worktree 代理人自身流程的一部分，get_project_root() 此處仍解析到
    # 主 repo（PostToolUse 觸發當下呼叫端 cwd 未變）。worktree 代理人依
    # dispatch 指示會自行執行 `claim --as`（其 cwd 已在 worktree 內，
    # get_project_root() 的 worktree 偵測正確落在 worktree 副本），此處
    # 綁定於主 repo 純屬多餘，且與 worktree 內 claim 寫入的 started_at
    # 屬兩份不同副本的雙寫，合併時衝突。非 worktree（共享 working tree）
    # 派發不受影響，維持原行為。
    if isolation == "worktree":
        if ticket_id and subagent_type:
            logger.info(
                "worktree 隔離派發，跳過主 repo 端身份綁定（0.2.1-W3-226），"
                "交由 worktree 內 claim --as 處理: %s",
                ticket_id,
            )
        return EXIT_SUCCESS

    if not (ticket_id and subagent_type):
        logger.debug("無 Ticket ID 或 subagent_type，跳過身份綁定")
        return EXIT_SUCCESS

    project_root = get_project_root()
    try:
        bind_dispatch_identity(ticket_id, subagent_type, project_root, logger)
    except Exception as e:
        # 綁定失敗不阻擋（agent 端仍有 claim --as fallback）
        logger.warning("bind_dispatch_identity failed: %s", e)

    return EXIT_SUCCESS


if __name__ == "__main__":
    sys.exit(run_hook_safely(main, HOOK_NAME))
