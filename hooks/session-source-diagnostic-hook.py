#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""SessionStart source diagnostic hook (W3-028.2).

Records SessionStart event source field for /resume bg session verification.
Pure observer: never blocks session startup, dual-channel failure logging.
"""
import json
import sys
from datetime import datetime
from pathlib import Path


def main() -> int:
    log_dir = Path(__file__).resolve().parent.parent / "hook-logs" / "session-source-diagnostic"
    log_file = log_dir / "diagnostic.log"
    try:
        payload = json.loads(sys.stdin.read() or "{}")
        source = payload.get("source", "<missing>")
        session_id = (payload.get("session_id", "<missing>") or "")[:8]
        ts = datetime.now().isoformat(timespec="seconds")
        log_dir.mkdir(parents=True, exist_ok=True)
        with log_file.open("a", encoding="utf-8") as f:
            f.write(f"[{ts}] source={source} session_id={session_id}\n")
    except Exception as exc:
        sys.stderr.write(f"[session-source-diagnostic-hook] error: {exc}\n")
        try:
            log_dir.mkdir(parents=True, exist_ok=True)
            with log_file.open("a", encoding="utf-8") as f:
                f.write(f"[{datetime.now().isoformat(timespec='seconds')}] ERROR: {exc}\n")
        except Exception:
            pass
    return 0


if __name__ == "__main__":
    sys.exit(main())
