#!/usr/bin/env -S uv run --quiet --script
# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""
Strategic Compact Suggester

Runs on PreToolUse or periodically to suggest manual compaction at logical intervals.

Why manual over auto-compact:
- Auto-compact happens at arbitrary points, often mid-task
- Strategic compacting preserves context through logical phases
- Compact after exploration, before execution
- Compact after completing a milestone, before starting next

Criteria for suggesting compact:
- Session has been running for extended period
- Large number of tool calls made
- Transitioning from research/exploration to implementation
- Plan has been finalized
"""

import os
import sys
from pathlib import Path


def main():
    # Track tool call count (increment in a temp file)
    pid = os.getpid()
    counter_file = Path(f"/tmp/claude-tool-count-{pid}")
    threshold = int(os.environ.get('COMPACT_THRESHOLD', '50'))

    # Initialize or increment counter
    if counter_file.exists():
        try:
            count = int(counter_file.read_text().strip())
            count += 1
        except (ValueError, IOError):
            count = 1
    else:
        count = 1

    counter_file.write_text(str(count))

    # Suggest compact after threshold tool calls
    if count == threshold:
        print(f"[StrategicCompact] {threshold} tool calls reached - consider /compact if transitioning phases", file=sys.stderr)

    # Suggest at regular intervals after threshold
    if count > threshold and count % 25 == 0:
        print(f"[StrategicCompact] {count} tool calls - good checkpoint for /compact if context is stale", file=sys.stderr)


if __name__ == "__main__":
    main()
