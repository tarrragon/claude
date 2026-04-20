#!/usr/bin/env python3
# /// script
# requires-python = ">=3.9"
# dependencies = []
# ///
"""
Agent Prompt Length Guard Hook - PreToolUse Hook

功能：檢查 Agent/Task 派發的 prompt 行數是否超過 30 行限制（PC-040）。
超過表示 context 未正確存入 Ticket，應先更新 Ticket Context Bundle。

Hook 類型：PreToolUse
匹配工具：Agent, Task
退出碼：0 = 放行，2 = 阻擋（stderr 回饋給 Claude）
"""

import json
import sys

from hook_utils import setup_hook_logging, run_hook_safely, read_json_from_stdin

PROMPT_LINE_LIMIT = 30

BLOCK_MESSAGE_TEMPLATE = """錯誤：Agent prompt 超過 {limit} 行限制（實際: {actual} 行）（PC-040）

為什麼阻止：
  Agent prompt 不得超過 {limit} 行。超過表示 context 未正確存入 Ticket。
  Context 應存入 Ticket 的 Context Bundle，而非 Agent prompt。

修復方式：
  1. 將分析結果寫入 Ticket Context Bundle
     → ticket track append-log <id> --section "Problem Analysis" "### Context Bundle\\n..."
  2. Agent prompt 只需包含：Ticket ID + 動作指令 + 「讀取 Ticket」
  3. 參考模板：.claude/pm-rules/context-bundle-spec.md

詳見: .claude/error-patterns/process-compliance/PC-040-context-in-prompt-not-ticket.md"""


def main() -> int:
    """Hook 主邏輯。"""
    logger = setup_hook_logging("agent-prompt-length-guard")

    try:
        input_data = read_json_from_stdin(logger)
    except (json.JSONDecodeError, EOFError):
        logger.warning("無法解析 stdin JSON，放行")
        return 0

    if not input_data:
        return 0

    tool_name = input_data.get("tool_name", "")
    if tool_name not in ("Agent", "Task"):
        return 0

    # tool_input 可能以 JSON 字串或 dict 傳入
    raw_input = input_data.get("tool_input") or "{}"
    if isinstance(raw_input, str):
        try:
            tool_input = json.loads(raw_input)
        except json.JSONDecodeError:
            logger.warning("tool_input JSON 解析失敗，放行")
            return 0
    else:
        tool_input = raw_input

    prompt = tool_input.get("prompt", "")
    if not prompt:
        return 0

    line_count = len(prompt.strip().splitlines())

    if line_count <= PROMPT_LINE_LIMIT:
        logger.info("通過：prompt %d 行（限制 %d）", line_count, PROMPT_LINE_LIMIT)
        return 0

    # 超過限制 → 阻擋
    message = BLOCK_MESSAGE_TEMPLATE.format(
        limit=PROMPT_LINE_LIMIT, actual=line_count
    )
    print(message, file=sys.stderr)
    logger.warning("阻擋：prompt %d 行超過 %d 行限制", line_count, PROMPT_LINE_LIMIT)
    return 2


if __name__ == "__main__":
    sys.exit(run_hook_safely(main, "agent-prompt-length-guard"))
