#!/usr/bin/env -S uv run --quiet --script
# /// script
# requires-python = ">=3.11"
# dependencies = []
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

    # Commit succeeded — synchronous fetch with timeout
    # 使用 subprocess.run 確保 fetch 完成後 hook 才返回，
    # 避免背景 fetch 持有 index.lock 與下一個 git 操作競爭（IMP-046）
    try:
        subprocess.run(
            ["git", "fetch", "--quiet", "--all"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            timeout=4,
        )
    except subprocess.TimeoutExpired:
        print(
            "[WARNING] git fetch timeout after 4s, process killed",
            file=sys.stderr,
        )


if __name__ == "__main__":
    main()
