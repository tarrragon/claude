#!/usr/bin/env -S uv run --quiet --script
# /// script
# requires-python = ">=3.10"
# dependencies = []
# ///
"""domain-import-lint-hook.py — domain 層 import 方向 lint（ARCH-BAL-001 防護）

lib/domain/ 禁止 import data/ / presentation/ / flutter/ / riverpod。
掛載於 PreToolUse:Bash（commit 時觸發），違反 exit 2 阻擋。

Ticket: 0.1.0-W2-015（2026-09-04 遷移至 hook_utils 統一日誌）
"""

from __future__ import annotations

import os
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))  # .claude/ — for `from lib import ...`

from lib import setup_hook_logging, run_hook_safely, read_json_from_stdin  # noqa: E402

DOMAIN_DIR = "lib/domain"

FORBIDDEN_PATTERNS = [
    re.compile(r"import\s.*package:flutter_balance/data/"),
    re.compile(r"import\s.*package:flutter_balance/presentation/"),
    re.compile(r"import\s.*package:flutter_balance/core/ui/"),
    re.compile(r"import\s.*package:flutter/"),
    re.compile(r"import\s.*package:flutter_riverpod/"),
    re.compile(r"import\s.*package:riverpod/"),
    re.compile(r"import\s.*dart:ui"),
]


def is_commit_command(command: str) -> bool:
    return "git commit" in command or "git merge" in command


def scan_domain_imports(project_root: str) -> list[str]:
    domain_path = Path(project_root) / DOMAIN_DIR
    if not domain_path.is_dir():
        return []

    violations = []
    for dart_file in domain_path.rglob("*.dart"):
        with open(dart_file, "r", encoding="utf-8") as f:
            for line_no, line in enumerate(f, 1):
                stripped = line.strip()
                if not stripped.startswith("import"):
                    continue
                for pattern in FORBIDDEN_PATTERNS:
                    if pattern.search(stripped):
                        rel = dart_file.relative_to(project_root)
                        violations.append(f"  {rel}:{line_no}: {stripped}")
    return violations


def main() -> int:
    logger = setup_hook_logging("domain-import-lint-hook")

    hook_input = read_json_from_stdin(logger)
    if hook_input is None:
        return 0

    tool_name = hook_input.get("tool_name", "")
    if tool_name != "Bash":
        logger.debug("非 Bash 工具，跳過: %s", tool_name)
        return 0

    tool_input = hook_input.get("tool_input", {})
    command = tool_input.get("command", "")
    if not is_commit_command(command):
        logger.debug("非 commit/merge 命令，跳過")
        return 0

    project_root = os.environ.get("CLAUDE_PROJECT_DIR", "")
    if not project_root:
        logger.info("CLAUDE_PROJECT_DIR 未設定，跳過掃描")
        return 0

    violations = scan_domain_imports(project_root)
    if violations:
        msg = (
            "[domain-import-lint] domain 層 import 方向違規\n\n"
            + "\n".join(violations)
            + "\n\ndomain/ 禁止 import data/ / presentation/ / flutter/ / riverpod\n"
            "（ARCH-BAL-001 防護，ticket 0.1.0-W2-015）"
        )
        logger.info("domain import lint 阻擋：命中 %d 處違規", len(violations))
        print(msg, file=sys.stderr)
        return 2

    logger.debug("domain import lint 通過（無違規）")
    return 0


if __name__ == "__main__":
    sys.exit(run_hook_safely(main, "domain-import-lint-hook"))
