#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# ///
"""PostToolUse hook: git commit 後自動背景 fetch。

讓 statusline 的 vN（遠端領先）指標保持最新。
"""
import json
import subprocess
import sys


def main() -> None:
    data = json.load(sys.stdin)

    tool_name = data.get("tool_name", "")
    if tool_name != "Bash":
        return

    tool_input = data.get("tool_input", {})
    command = tool_input.get("command", "")

    if "git commit" not in command:
        return

    stdout = data.get("stdout", "")
    if "create mode" not in stdout and "] " not in stdout:
        return

    # Commit succeeded — background fetch
    subprocess.Popen(
        ["git", "fetch", "--quiet", "--all"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )


if __name__ == "__main__":
    main()
