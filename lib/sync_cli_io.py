"""sync 腳本共用的終端輸出與 git 執行輔助。"""

import os
import subprocess
import sys


def print_color(msg: str, color: str = "yellow") -> None:
    """Print colored message (ANSI codes, gracefully degrades on Windows)."""
    colors = {"green": "\033[0;32m", "yellow": "\033[1;33m", "red": "\033[0;31m"}
    nc = "\033[0m"
    if sys.platform == "win32" and not os.environ.get("TERM"):
        print(msg)
    else:
        print(f"{colors.get(color, '')}{msg}{nc}")


def run_git(args: list[str], cwd: str | None = None, check: bool = True) -> subprocess.CompletedProcess:
    """Run a git command and return the result."""
    result = subprocess.run(
        ["git", *args],
        capture_output=True,
        text=True,
        cwd=cwd,
    )
    if check and result.returncode != 0:
        print_color(f"git {' '.join(args)} 失敗: {result.stderr}", "red")
        sys.exit(1)
    return result
