#!/usr/bin/env python3
# /// script
# requires-python = ">=3.9"
# dependencies = []
# ///
"""
Agent Prompt Length Guard Hook - PreToolUse Hook

功能：
  1. 硬上限：檢查 Agent/Task 派發的 prompt 行數是否超過 30 行限制（PC-040）。
     超過表示 context 未正確存入 Ticket，應先更新 Ticket Context Bundle。
  2. 軟提示（W17-048 方案 B）：prompt 介於 10-30 行且未偵測到模板關鍵字時，
     輸出提示到 stderr 但仍放行（exit 0），引導 PM 改用派發模板結構。

Hook 類型：PreToolUse
匹配工具：Agent, Task
退出碼：0 = 放行（含軟提示），2 = 阻擋（stderr 回饋給 Claude）
"""

import json
import sys

from hook_utils import setup_hook_logging, run_hook_safely, read_json_from_stdin

PROMPT_LINE_LIMIT = 30
SOFT_HINT_THRESHOLD = 10

# 模板關鍵字：PM 使用派發模板時 prompt 通常會含以下任一
# （中文關鍵字大小寫不變；英文關鍵字大小寫敏感以減少誤判）
TEMPLATE_KEYWORDS = [
    "讀取 Ticket",
    "讀取 ticket",
    "ticket track full",
    "ticket track query",
    "Context Bundle",
    "依 ticket",
]

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

SOFT_HINT_TEMPLATE = """提示：Agent prompt 為 {actual} 行，但未偵測到模板關鍵字（W17-048 方案 B）

建議結構：
  Ticket: {{ticket_id}}

  ## 任務
  {{簡短動作描述}}

  讀取 ticket：`ticket track full {{ticket_id}}`
  依 Context Bundle 執行流程。

模板：.claude/references/agent-dispatch-template.md
"""


def has_template_keywords(prompt: str) -> bool:
    """檢查 prompt 是否包含任一模板關鍵字。

    判斷：只要包含 TEMPLATE_KEYWORDS 任一項即視為已使用模板結構，
    不再輸出軟提示。
    """
    return any(keyword in prompt for keyword in TEMPLATE_KEYWORDS)


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

    # Layer 1: 硬上限（> 30 行直接阻擋）
    if line_count > PROMPT_LINE_LIMIT:
        message = BLOCK_MESSAGE_TEMPLATE.format(
            limit=PROMPT_LINE_LIMIT, actual=line_count
        )
        print(message, file=sys.stderr)
        logger.warning("阻擋：prompt %d 行超過 %d 行限制", line_count, PROMPT_LINE_LIMIT)
        return 2

    # Layer 2: 軟提示（10 < line_count <= 30 且缺關鍵字時提示但放行）
    if line_count > SOFT_HINT_THRESHOLD and not has_template_keywords(prompt):
        hint = SOFT_HINT_TEMPLATE.format(actual=line_count)
        print(hint, file=sys.stderr)
        logger.info(
            "軟提示：prompt %d 行缺模板關鍵字（threshold=%d, limit=%d）",
            line_count, SOFT_HINT_THRESHOLD, PROMPT_LINE_LIMIT,
        )
        return 0

    logger.info("通過：prompt %d 行（限制 %d）", line_count, PROMPT_LINE_LIMIT)
    return 0


if __name__ == "__main__":
    sys.exit(run_hook_safely(main, "agent-prompt-length-guard"))
