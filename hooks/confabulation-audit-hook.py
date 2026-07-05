#!/usr/bin/env -S uv run --quiet --script
# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""
Confabulation Audit Hook (Stop)

Session 結束時檢查 confabulation 常見副作用指標：
1. 髒工作區（宣稱 commit 但未實際 commit）
2. in_progress ticket 未收尾（宣稱 complete 但未實際 complete）

輸出差異報告到 stderr + hook-logs。
不預防 confabulation（無法），僅提供事後可觀測性。

Source: 1.5.0-W5-014.1 / PC-166 防護 B 延伸
"""

import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
sys.path.insert(0, str(Path(__file__).parent.parent))

from lib import (
    setup_hook_logging,
    run_hook_safely,
    get_project_root,
)

HOOK_NAME = "confabulation-audit"


def run_command(cmd: list[str], cwd: str | None = None, timeout: int = 10) -> tuple[int, str]:
    try:
        result = subprocess.run(
            cmd, capture_output=True, text=True, timeout=timeout, cwd=cwd
        )
        return result.returncode, result.stdout.strip()
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
        return 1, ""


def check_dirty_worktree(project_root: str) -> list[str]:
    """Check for uncommitted changes (potential confabulated commit)."""
    rc, output = run_command(["git", "status", "--porcelain"], cwd=project_root)
    if rc != 0 or not output:
        return []

    findings = []
    lines = output.splitlines()
    modified = [l for l in lines if l.startswith((" M", "M ", "MM"))]
    untracked = [l for l in lines if l.startswith("??")]
    staged = [l for l in lines if l.startswith(("A ", "D ", "R "))]

    if modified:
        findings.append(f"未 commit 的修改: {len(modified)} 檔")
    if staged:
        findings.append(f"已 stage 未 commit: {len(staged)} 檔")
    if untracked:
        count = len(untracked)
        if count <= 5:
            findings.append(f"未追蹤檔案: {count} 檔")

    return findings


def check_in_progress_tickets(project_root: str) -> list[str]:
    """Check for tickets still in_progress at session end."""
    rc, output = run_command(
        ["ticket", "track", "list", "--status", "in_progress", "--format", "ids"],
        cwd=project_root,
        timeout=30,
    )
    if rc != 0 or not output:
        return []

    ticket_ids = [line.strip() for line in output.splitlines() if line.strip()]
    if not ticket_ids:
        return []

    return [f"in_progress ticket 未收尾: {', '.join(ticket_ids)}"]


def main() -> int:
    logger = setup_hook_logging(HOOK_NAME)

    try:
        project_root = str(get_project_root())
    except Exception:
        return 0

    findings: list[str] = []

    findings.extend(check_dirty_worktree(project_root))
    findings.extend(check_in_progress_tickets(project_root))

    if not findings:
        logger.info("Session 結束審計: 無異常指標")
        return 0

    report_lines = [
        "",
        "============================================================",
        "[Confabulation Audit] Session 結束狀態檢查",
        "============================================================",
        "",
    ]
    for f in findings:
        report_lines.append(f"  [WARNING] {f}")
    report_lines.extend([
        "",
        "上述指標可能表示 session 中有未落地的操作（PC-166 副作用）。",
        "若為正常中斷（用戶主動結束），可忽略。",
        "============================================================",
    ])

    report = "\n".join(report_lines)
    sys.stderr.write(report + "\n")
    logger.warning(f"Session 結束審計發現 {len(findings)} 項異常指標")
    for f in findings:
        logger.warning(f"  {f}")

    return 0


if __name__ == "__main__":
    sys.exit(run_hook_safely(main, HOOK_NAME))
