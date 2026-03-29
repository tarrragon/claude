#!/usr/bin/env python3
# /// script
# requires-python = ">=3.9"
# dependencies = []
# ///
"""
Agent Dispatch Validation Hook - PreToolUse Hook

功能：強制實作代理人使用 isolation: "worktree" 派發。
實作代理人會修改檔案和執行 git 操作，在主倉庫工作會污染 .git/HEAD。
使用 worktree 隔離可從物理上防止分支切換影響主線程。

Hook 類型：PreToolUse
匹配工具：Agent
退出碼：0 = 放行，2 = 阻擋（stderr 回饋給 Claude）
"""

import json
import sys

from hook_utils import setup_hook_logging, run_hook_safely

# 需要 worktree 隔離的實作代理人
IMPLEMENTATION_AGENTS = frozenset({
    "parsley-flutter-developer",
    "fennel-go-developer",
    "thyme-python-developer",
    "cinnamon-refactor-owl",
    "pepper-test-implementer",
    "mint-format-specialist",
})

BLOCK_MESSAGE_TEMPLATE = """錯誤：實作代理人 {agent} 必須使用 isolation: "worktree" 派發

為什麼阻止：
  實作代理人會修改檔案和執行 git 操作，在主倉庫工作會污染 .git/HEAD。
  使用 worktree 隔離可從物理上防止分支切換影響主線程。

修復方式：
  在 Agent 呼叫中加入 isolation: "worktree" 參數

詳見: .claude/pm-rules/parallel-dispatch.md（Worktree 隔離章節）"""


def main() -> int:
    """Hook 主邏輯。"""
    logger = setup_hook_logging("agent-dispatch-validation")

    try:
        input_data = json.load(sys.stdin)
    except (json.JSONDecodeError, EOFError):
        logger.warning("無法解析 stdin JSON，放行")
        return 0

    tool_name = input_data.get("tool_name", "")
    if tool_name != "Agent":
        return 0

    # Claude Code PreToolUse hook 的 tool_input 可能以 JSON 字串或 dict 傳入，
    # 取決於 Claude Code 版本。雙型別處理確保兩種情況都能正確解析。
    raw_input = input_data.get("tool_input") or "{}"
    if isinstance(raw_input, str):
        try:
            tool_input = json.loads(raw_input)
        except json.JSONDecodeError:
            logger.warning("tool_input JSON 解析失敗，放行")
            return 0
    else:
        tool_input = raw_input
    subagent_type = tool_input.get("subagent_type", "")

    # 無 subagent_type 或非實作代理人 → 放行
    if not subagent_type or subagent_type not in IMPLEMENTATION_AGENTS:
        logger.info("放行：subagent_type=%s", subagent_type or "(empty)")
        return 0

    # 實作代理人：檢查 isolation 參數
    isolation = tool_input.get("isolation", "")
    if isolation == "worktree":
        logger.info("通過：%s 使用 worktree 隔離", subagent_type)
        return 0

    # 缺少 worktree → 阻擋
    message = BLOCK_MESSAGE_TEMPLATE.format(agent=subagent_type)
    print(message, file=sys.stderr)
    logger.warning("阻擋：%s 未使用 worktree（isolation=%s）", subagent_type, isolation or "(none)")
    return 2


if __name__ == "__main__":
    sys.exit(run_hook_safely(main, "agent-dispatch-validation"))
