#!/usr/bin/env -S uv run --quiet --script
# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///

"""
Agent Dispatch Logger Hook - PostToolUse (Agent)

功能: 記錄 Agent 派發的 prompt 和 response 摘要到 JSONL 檔案，
     供失敗時快速追溯（無需從 conversation JSON 手動解析）。

觸發時機: Agent 工具完成後 (PostToolUse, matcher: Agent)
行為: 不阻擋（exit 0），僅記錄到 JSONL
儲存: .claude/logs/agent-dispatch.jsonl

來源: W2-014 分析結論（P1 實作項目）
Ticket: 0.17.2-W3-002
"""

import json
import os
import re
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from hook_utils import (
    setup_hook_logging,
    read_json_from_stdin,
    extract_tool_input,
    extract_tool_response,
    is_subagent_environment,
    get_project_root,
)

# ============================================================================
# 常數定義
# ============================================================================

HOOK_NAME = "agent-dispatch-logger"
EXIT_SUCCESS = 0
LOG_DIR = ".claude/logs"
LOG_FILE = "agent-dispatch.jsonl"
MAX_LOG_SIZE = 1_000_000  # 1MB
PREVIEW_LENGTH = 500  # prompt/response 預覽字元數

# 失敗關鍵字（啟發式判斷）
FAILURE_KEYWORDS = [
    "exhausted",
    "error",
    "failed",
    "failure",
    "exception",
    "merge conflict",
    "file not found",
    "No such file",
    "Permission denied",
    "index.lock",
]

# Ticket ID 正則
TICKET_ID_PATTERN = re.compile(r"\d+\.\d+\.\d+-W\d+-\d+(?:\.\d+)?")

# 預設輸出
DEFAULT_OUTPUT = {
    "hookSpecificOutput": {},
}


def extract_ticket_id(prompt: str) -> str:
    """從 prompt 中正則提取 ticket_id"""
    match = TICKET_ID_PATTERN.search(prompt)
    return match.group(0) if match else ""


def check_failure_indicators(response_text: str) -> dict:
    """啟發式判斷成功/失敗"""
    has_error = any(kw.lower() in response_text.lower() for kw in FAILURE_KEYWORDS)
    response_length = len(response_text)
    # 極短回應（< 100 字元）可能是截斷
    is_truncated = response_length < 100 and response_length > 0

    return {
        "has_error_keywords": has_error,
        "response_length": response_length,
        "possibly_truncated": is_truncated,
    }


def rotate_log(log_path: Path):
    """超過 MAX_LOG_SIZE 時 rotate"""
    if log_path.exists() and log_path.stat().st_size > MAX_LOG_SIZE:
        rotated = log_path.with_suffix(".jsonl.old")
        if rotated.exists():
            rotated.unlink()
        log_path.rename(rotated)


def write_log_entry(log_path: Path, entry: dict):
    """寫入 JSONL 記錄"""
    log_path.parent.mkdir(parents=True, exist_ok=True)
    rotate_log(log_path)
    with open(log_path, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")


def main():
    logger = setup_hook_logging(HOOK_NAME)

    input_data = read_json_from_stdin(logger)
    if not input_data:
        json.dump(DEFAULT_OUTPUT, sys.stdout)
        sys.exit(EXIT_SUCCESS)

    # Subagent 環境不記錄（避免遞迴）
    if is_subagent_environment(input_data):
        json.dump(DEFAULT_OUTPUT, sys.stdout)
        sys.exit(EXIT_SUCCESS)

    tool_input = extract_tool_input(input_data, logger)
    tool_response = extract_tool_response(input_data, logger)

    # 提取欄位
    prompt = tool_input.get("prompt", "")
    description = tool_input.get("description", "")
    subagent_type = tool_input.get("subagent_type", "")
    isolation = tool_input.get("isolation", "")

    # tool_response 對 Agent 是純文字（在 result 欄位或直接是字串）
    if isinstance(tool_response, dict):
        response_text = tool_response.get("result", str(tool_response))
    else:
        response_text = str(tool_response) if tool_response else ""

    # 組裝記錄
    ticket_id = extract_ticket_id(prompt)
    success_indicators = check_failure_indicators(response_text)

    entry = {
        "timestamp": datetime.now().isoformat(timespec="seconds"),
        "ticket_id": ticket_id,
        "agent_description": description,
        "agent_type": subagent_type,
        "isolation": isolation,
        "prompt_preview": prompt[:PREVIEW_LENGTH],
        "response_preview": response_text[:PREVIEW_LENGTH],
        "success_indicators": success_indicators,
    }

    # 寫入日誌
    root = get_project_root()
    if root:
        log_path = Path(root) / LOG_DIR / LOG_FILE
        try:
            write_log_entry(log_path, entry)
            logger.info(
                "Logged agent dispatch: %s (%s)", description, ticket_id or "no-ticket"
            )
        except OSError as e:
            logger.warning("Failed to write agent log: %s", e)

    json.dump(DEFAULT_OUTPUT, sys.stdout)
    sys.exit(EXIT_SUCCESS)


if __name__ == "__main__":
    main()
