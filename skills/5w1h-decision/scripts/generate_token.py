#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# dependencies = []
# ///
"""
5W1H Session Token Generator

Generates unique session tokens for 5W1H decision framework tracking.
Format: 5W1H-{YYYYMMDD}-{HHMMSS}-{random}
Example: 5W1H-20250925-191735-a7b3c2

Usage:
    uv run .claude/skills/5w1h-decision/scripts/generate_token.py
"""

import os
import random
import string
import sys
from datetime import datetime
from pathlib import Path


def generate_random_suffix(length: int = 6) -> str:
    """Generate random alphanumeric suffix."""
    chars = string.ascii_lowercase + string.digits
    return "".join(random.choices(chars, k=length))


def generate_token() -> str:
    """Generate 5W1H session token."""
    now = datetime.now()
    date_part = now.strftime("%Y%m%d")
    time_part = now.strftime("%H%M%S")
    random_part = generate_random_suffix()
    return f"5W1H-{date_part}-{time_part}-{random_part}"


def save_token(token: str) -> Path:
    """Save token to session file."""
    # Determine project root
    script_dir = Path(__file__).parent
    project_root = script_dir.parent.parent.parent.parent

    # Create token directory
    token_dir = project_root / ".claude" / "hook-logs" / "5w1h-tokens"
    token_dir.mkdir(parents=True, exist_ok=True)

    # Save token file
    token_file = token_dir / f"session-{datetime.now().strftime('%Y%m%d-%H%M%S')}.token"
    token_file.write_text(token)

    return token_file


def main() -> int:
    """Main entry point."""
    token = generate_token()

    # Check for --save flag
    if "--save" in sys.argv:
        token_file = save_token(token)
        print(f"Token: {token}")
        print(f"Saved: {token_file}")
    else:
        print(token)

    return 0


if __name__ == "__main__":
    sys.exit(main())
