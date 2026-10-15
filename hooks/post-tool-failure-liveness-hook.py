#!/usr/bin/env -S uv run --quiet --script
# /// script
# requires-python = ">=3.11"
# dependencies = ["pyyaml"]
# ///
"""
PostToolUseFailure(Bash) 探針 Hook

目的:
  PostToolUseFailure:Bash 群組的最小成員。run_hook_safely 在 main 執行前寫入 liveness
  索引，本 hook 另把失敗事件的關鍵欄位記入日誌，使「失敗事件確實經分派器送達」可由
  hook-logs 直接查證。失敗類 hook 搬入群組前，群組因此不為空。

觸發時機: PostToolUseFailure (Bash)
輸入契約: 頂層 error、is_interrupt、duration_ms、hook_event_name；無 tool_response
輸出: 無（失敗事件無阻擋語意；本 hook 恆 exit 0，不寫 stdout）
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from lib import read_json_from_stdin, run_hook_safely, setup_hook_logging

HOOK_NAME = "post-tool-failure-liveness-hook"
ERROR_PREVIEW_CHARS = 120


def summarize_failure(input_data: dict) -> str:
    """失敗事件摘要：事件名、是否中斷、耗時、error 前 N 字（單行）"""
    error = str(input_data.get("error", "")).replace("\n", " ")[:ERROR_PREVIEW_CHARS]
    return "event={} interrupt={} duration_ms={} error={}".format(
        input_data.get("hook_event_name", ""),
        input_data.get("is_interrupt", False),
        input_data.get("duration_ms", ""),
        error,
    )


def main() -> int:
    logger = setup_hook_logging(HOOK_NAME)
    input_data = read_json_from_stdin(logger)
    if input_data is None:
        return 0
    logger.info("收到失敗事件 %s", summarize_failure(input_data))
    return 0


if __name__ == "__main__":
    sys.exit(run_hook_safely(main, HOOK_NAME))
