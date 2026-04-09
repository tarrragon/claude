"""Ticket 專案狀態快照命令"""
import argparse
import re
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List

from ticket_system.lib.ticket_loader import list_tickets
from ticket_system.lib.constants import (
    STATUS_PENDING,
    STATUS_IN_PROGRESS,
    STATUS_COMPLETED,
    STATUS_BLOCKED,
    STATUS_CLOSED,
    WORK_LOGS_DIR,
)
from ticket_system.lib.paths import get_project_root
VERSION_PATTERN = re.compile(r"^v(\d+\.\d+\.\d+)$")


def execute_snapshot(args: argparse.Namespace) -> int:
    """執行 snapshot 命令"""
    try:
        versions = _scan_all_versions()
        branch = _get_git_branch()
        uncommitted = _get_uncommitted_count()

        print("=== Project Snapshot ===")
        print(f"時間: {datetime.now().strftime('%Y-%m-%d %H:%M')}")
        print(f"分支: {branch}")
        print()

        _print_version_progress(versions)
        _print_in_progress_tasks(versions)
        _print_pending_summary(versions)
        _print_git_status(branch, uncommitted)

        return 0
    except Exception as e:
        print(f"[Error] snapshot 失敗: {e}", file=sys.stderr)
        return 1


def _scan_all_versions() -> List[str]:
    """掃描所有版本目錄"""
    root = get_project_root()
    work_logs = root / WORK_LOGS_DIR
    if not work_logs.exists():
        return []

    versions = set()
    # 新式階層：docs/work-logs/v{major}/v{major}.{minor}/v{version}/
    for major_dir in work_logs.iterdir():
        if not major_dir.is_dir() or not major_dir.name.startswith("v"):
            continue
        for minor_dir in major_dir.iterdir():
            if not minor_dir.is_dir():
                continue
            for patch_dir in minor_dir.iterdir():
                m = VERSION_PATTERN.match(patch_dir.name)
                if patch_dir.is_dir() and m:
                    versions.add(m.group(1))
    # 舊式平行：docs/work-logs/v{version}/
    for d in work_logs.iterdir():
        m = VERSION_PATTERN.match(d.name)
        if d.is_dir() and m:
            versions.add(m.group(1))

    return sorted(versions, key=lambda v: tuple(int(x) for x in v.split(".")))


def _print_version_progress(versions: List[str]) -> None:
    """輸出各版本進度"""
    print("--- 版本進度 ---")
    for version in versions:
        tickets = list_tickets(version)
        if not tickets:
            continue
        counts = _count_by_status(tickets)
        closed = counts[STATUS_CLOSED]
        active_total = len(tickets) - closed
        parts = []
        if counts[STATUS_PENDING]:
            parts.append(f"{counts[STATUS_PENDING]} pending")
        if counts[STATUS_IN_PROGRESS]:
            parts.append(f"{counts[STATUS_IN_PROGRESS]} in_progress")
        if counts[STATUS_BLOCKED]:
            parts.append(f"{counts[STATUS_BLOCKED]} blocked")
        if closed:
            parts.append(f"{closed} closed")
        suffix = f" ({', '.join(parts)})" if parts else ""
        print(f"  v{version}: {counts[STATUS_COMPLETED]}/{active_total} 完成{suffix}")
    print()


def _print_in_progress_tasks(versions: List[str]) -> None:
    """輸出進行中任務詳情"""
    print("--- 進行中任務 ---")
    found = False
    for version in versions:
        for t in list_tickets(version):
            if t.get("status") == STATUS_IN_PROGRESS:
                who = t.get("who", {})
                current = who.get("current", "pending") if isinstance(who, dict) else str(who)
                print(f"  {t.get('id')} | {current} | {t.get('title', '')}")
                found = True
    if not found:
        print("  （無）")
    print()


def _print_pending_summary(versions: List[str]) -> None:
    """輸出待處理任務按 Wave 分組"""
    print("--- 待處理任務摘要 ---")
    found = False
    for version in versions:
        pending = [t for t in list_tickets(version) if t.get("status") == STATUS_PENDING]
        if not pending:
            continue
        found = True
        wave_counts = {}
        for t in pending:
            parts = t.get("id", "").split("-")
            wave = parts[1] if len(parts) >= 2 else "?"
            wave_counts[wave] = wave_counts.get(wave, 0) + 1
        summary = " | ".join(f"{w}: {c}" for w, c in sorted(wave_counts.items()))
        print(f"  v{version}: {summary}")
    if not found:
        print("  （無待處理任務）")
    print()


def _print_git_status(branch: str, uncommitted: int) -> None:
    """輸出 git 狀態"""
    print("--- Git 狀態 ---")
    print(f"  分支: {branch}")
    print(f"  未提交: {uncommitted} 個檔案")


def _count_by_status(tickets: List[Dict[str, Any]]) -> Dict[str, int]:
    """按狀態計數"""
    counts = {
        STATUS_PENDING: 0, STATUS_IN_PROGRESS: 0,
        STATUS_COMPLETED: 0, STATUS_BLOCKED: 0, STATUS_CLOSED: 0,
    }
    for t in tickets:
        s = t.get("status", STATUS_PENDING)
        if s in counts:
            counts[s] += 1
    return counts


def _get_git_branch() -> str:
    """取得當前 git 分支"""
    try:
        r = subprocess.run(["git", "branch", "--show-current"], capture_output=True, text=True, timeout=5)
        return r.stdout.strip() or "unknown"
    except Exception:
        return "unknown"


def _get_uncommitted_count() -> int:
    """取得未提交檔案數"""
    try:
        r = subprocess.run(["git", "status", "--short"], capture_output=True, text=True, timeout=5)
        return len([l for l in r.stdout.strip().split("\n") if l.strip()])
    except Exception:
        return -1
