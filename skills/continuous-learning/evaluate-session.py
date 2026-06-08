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

    # Get transcript path from environment (set by Claude Code)
    transcript_path = os.environ.get('CLAUDE_TRANSCRIPT_PATH', '')

    if not transcript_path or not Path(transcript_path).exists():
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

    # Signal to Claude that session should be evaluated for extractable patterns
    print(f"[ContinuousLearning] Session has {message_count} messages - evaluate for extractable patterns", file=sys.stderr)
    print(f"[ContinuousLearning] Save learned skills to: {learned_skills_path}", file=sys.stderr)


if __name__ == "__main__":
    main()
