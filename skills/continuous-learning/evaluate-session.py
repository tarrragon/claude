#!/usr/bin/env -S uv run --quiet --script
# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""
Continuous Learning - Session Evaluator

Runs on Stop hook to extract reusable patterns from Claude Code sessions.

Why Stop hook instead of UserPromptSubmit:
- Stop runs once at session end (lightweight)
- UserPromptSubmit runs every message (heavy, adds latency)

Patterns to detect: error_resolution, debugging_techniques, workarounds, project_specific
Patterns to ignore: simple_typos, one_time_fixes, external_api_issues
Extracted skills saved to: .claude/skills/learned/
"""

import json
import os
import sys
from pathlib import Path

# .claude/ 加入搜尋路徑以使用 lib 的統一輸出入口
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from lib import emit_model_reminder


def _read_payload() -> dict:
    """讀 stdin payload；空輸入或解析失敗回傳空 dict。"""
    try:
        text = sys.stdin.read().strip()
        payload = json.loads(text) if text else {}
        return payload if isinstance(payload, dict) else {}
    except Exception:
        # 非標準輸入（無 stdin / 非 JSON）屬預期路徑，視為無 payload
        return {}


def main():
    # Configuration
    script_dir = Path(__file__).parent
    config_file = script_dir / "config.json"

    # Default values
    min_session_length = 10
    learned_skills_path = Path(".claude/skills/learned")

    # Load config if exists
    if config_file.exists():
        try:
            with open(config_file, 'r', encoding='utf-8') as f:
                config = json.load(f)
                min_session_length = config.get('min_session_length', 10)
                learned_skills_path = Path(config.get('learned_skills_path', '.claude/skills/learned'))
        except (json.JSONDecodeError, IOError):
            pass

    # Ensure learned skills directory exists
    learned_skills_path.mkdir(parents=True, exist_ok=True)

    # Stop payload 的 transcript_path 為平台提供的來源（實測 Stop payload 帶此鍵；
    # 環境變數 CLAUDE_TRANSCRIPT_PATH 平台未設定）。讀不到時 fail-open 並記 stderr。
    payload = _read_payload()
    transcript_path = payload.get('transcript_path', '')

    if not transcript_path or not Path(transcript_path).exists():
        print("[ContinuousLearning] transcript_path missing or not found, skipping", file=sys.stderr)
        sys.exit(0)

    # Count messages in session
    message_count = 0
    try:
        with open(transcript_path, 'r', encoding='utf-8') as f:
            content = f.read()
            message_count = content.count('"type":"user"')
    except IOError:
        message_count = 0

    # Skip short sessions
    if message_count < min_session_length:
        print(f"[ContinuousLearning] Session too short ({message_count} messages), skipping", file=sys.stderr)
        sys.exit(0)

    # Stop 的 additionalContext 會讓模型續跑一次（意圖內：讓模型評估可萃取模式）；
    # 續跑後的下一次 Stop 為 stop_hook_active，不得再輸出，避免無限迴圈。
    if payload.get("stop_hook_active"):
        sys.exit(0)

    # Signal to Claude that session should be evaluated for extractable patterns
    emit_model_reminder(
        "Stop",
        f"[ContinuousLearning] Session has {message_count} messages - evaluate for extractable patterns\n"
        f"[ContinuousLearning] Save learned skills to: {learned_skills_path}",
    )


if __name__ == "__main__":
    main()
