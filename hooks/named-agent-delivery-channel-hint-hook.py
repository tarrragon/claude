#!/usr/bin/env -S uv run --quiet --script
# /// script
# requires-python = ">=3.10"
# dependencies = ["pyyaml"]
# ///
"""
Named Agent Delivery Channel Hint Hook - PreToolUse（matcher: Agent）

Agent 工具呼叫帶 name、在背景執行，且 prompt 沒有要求以 SendMessage 送出報告
本體時，以 additionalContext 提醒派發者。不阻擋派發。

Why：背景 named agent 的最終回覆不送達主線程，主線程只收到 idle 通知；prompt
沒寫交付通道句時產出必然遺失。這個條款寫在 agent-dispatch-template〈帶 name 的
代價〉，派發當下通常不在 context，實際觀測過連續多次派發都沒寫
（tarrragon/claude#54）。

判準：
- 帶 name：tool_input.name 為非空字串
- 背景：run_in_background 為 True，或未帶此欄位。目前 harness 的 Agent 預設在
  背景執行；只有明確為 False 才視為前景。本 hook 只提醒，寧可多提醒一次
- 交付通道句：prompt 同時含 DELIVERY_TOOL_TOKEN 與獨立的 DELIVERY_TARGET_TOKEN
  （前後不接英文字母，中文緊鄰也算，`domain` 之類不算）

受眾：模型。走 additionalContext，不帶 permissionDecision——帶 "allow" 會略過
這次工具呼叫的權限確認，等於放寬權限，不是本 hook 的職責。

失敗模式：不阻擋。lib 匯入失敗時 stderr 提示並 exit 0；未預期例外由
run_hook_safely 寫入日誌檔與 stderr，exit 1（PreToolUse 只有 exit 2 會擋）。
"""

import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))         # .claude/hooks/
sys.path.insert(0, str(Path(__file__).parent.parent))  # .claude/       (lib.*)
try:
    from lib import (
        emit_hook_output,
        read_json_from_stdin,
        run_hook_safely,
        setup_hook_logging,
    )
except ImportError as e:
    print(f"[Hook Import Error] {Path(__file__).name}: {e}", file=sys.stderr)
    sys.exit(0)

HOOK_NAME = "named-agent-delivery-channel-hint"
EXIT_SUCCESS = 0

# 交付通道句判準：兩個字樣同時出現即視為 prompt 已交代交付通道
DELIVERY_TOOL_TOKEN = "SendMessage"
DELIVERY_TARGET_TOKEN = "main"
_TARGET_RE = re.compile(r"(?<![A-Za-z])" + re.escape(DELIVERY_TARGET_TOKEN) + r"(?![A-Za-z])")

HINT = (
    "[Named Agent 交付通道] 這次派發帶 name 且在背景執行，但 prompt 沒有要求以 "
    "SendMessage 把報告本體送到 main。背景 named agent 的最終回覆不會送達主線程，"
    "主線程只會收到 idle 通知，產出可能遺失。若需要它的報告，請在 prompt 寫明："
    "「完成後以 SendMessage({to: \"main\"}) 送出報告本體」；不需要名稱定址時，"
    "也可以不帶 name。依據：.claude/references/agent-dispatch-template.md〈帶 name 的代價〉。"
)


def is_named(tool_input: dict) -> bool:
    name = tool_input.get("name")
    return isinstance(name, str) and bool(name.strip())


def is_background(tool_input: dict) -> bool:
    return tool_input.get("run_in_background", True) is not False


def has_delivery_channel(prompt: str) -> bool:
    return DELIVERY_TOOL_TOKEN in prompt and bool(_TARGET_RE.search(prompt))


def needs_hint(tool_input: dict) -> bool:
    prompt = tool_input.get("prompt") or ""
    return (
        is_named(tool_input)
        and is_background(tool_input)
        and not has_delivery_channel(prompt)
    )


def main() -> int:
    logger = setup_hook_logging(HOOK_NAME)
    input_data = read_json_from_stdin(logger)
    if not input_data or input_data.get("tool_name") != "Agent":
        return EXIT_SUCCESS
    tool_input = input_data.get("tool_input") or {}
    if not needs_hint(tool_input):
        logger.debug("無需提醒（name=%r）", tool_input.get("name"))
        return EXIT_SUCCESS
    logger.info("named 背景派發缺交付通道句，已提醒（name=%r）", tool_input.get("name"))
    emit_hook_output("PreToolUse", HINT, input_data=input_data)
    return EXIT_SUCCESS


if __name__ == "__main__":
    sys.exit(run_hook_safely(main, HOOK_NAME))
