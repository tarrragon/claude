"""Ticket 專案狀態快照命令（W10-017.1 v2 增強版）。

v2 變更：
- 整合 checkpoint_state() + lib/checkpoint_view 渲染「當前建議」+「Ready Check」區塊
- 移除既有 _get_uncommitted_count 獨立 git status 呼叫，改從 state.uncommitted_files 取值（v2 §1.2 / §3.4）
- 時間欄位用 format_local_time(state)（v2.2 Q4）
- fail-open: IO_ERRORS exit 0 + stderr WARN（v2.2 Q2）；其他例外 exit 1（v2.1 §3.5）
"""

import argparse
import re
import subprocess
import sys
from typing import Any, Dict, List

from ticket_system.lib.checkpoint_state import (
    IO_ERRORS,
    CheckpointState,
    PendingCheck,
    _utc_now_iso,
    checkpoint_state,
)
from ticket_system.lib.checkpoint_view import (
    format_local_time,
    render_current_suggestion,
    render_ready_check,
)
from ticket_system.lib.constants import (
    STATUS_BLOCKED,
    STATUS_CLOSED,
    STATUS_COMPLETED,
    STATUS_IN_PROGRESS,
    STATUS_PENDING,
    WORK_LOGS_DIR,
)
from ticket_system.lib.paths import get_project_root
from ticket_system.lib.ticket_loader import list_tickets

VERSION_PATTERN = re.compile(r"^v(\d+\.\d+\.\d+)$")


def execute_snapshot(args: argparse.Namespace) -> int:
    """執行 snapshot 命令（v2 增強）。

    Returns:
        0: 永遠（含 IO_ERRORS fail-open，v2.2 Q2 AD-1）；
        1: 非 IO_ERRORS 內部錯誤（v2.1 §3.5）
    """
    try:
        state = checkpoint_state(caller="snapshot", log_metrics=True)
    except IO_ERRORS as e:
        # v2.2 Q2: fail-open exit 0 + stderr WARN
        sys.stderr.write(f"WARN: data source(s) unavailable: {e}\n")
        return _render_degraded_snapshot(error=str(e))
    except Exception as e:
        # 非 IO_ERRORS：規則 4 stderr + exit 1
        sys.stderr.write(f"snapshot internal error: {e}\n")
        return 1

    return _render_full_snapshot(state)


def _render_full_snapshot(state: CheckpointState) -> int:
    """渲染完整 snapshot（state 推導成功路徑）。"""
    versions = _scan_all_versions()
    branch = _get_git_branch()

    print("=== Project Snapshot ===")
    print(f"時間: {format_local_time(state)}")
    print(f"分支: {branch}")
    print()

    _print_version_progress(versions)
    _print_in_progress_tasks(versions)
    _print_pending_summary(versions)
    _print_git_status_from_state(branch, state)
    print()
    print(render_current_suggestion(state))
    print()
    print(render_ready_check(state, caller="snapshot"))
    return 0


def _build_degraded_state(error: str) -> CheckpointState:
    """建立 degraded CheckpointState：所有資料源 fallback + pending_check 註記錯誤。

    用於 execute_snapshot IO_ERRORS 降級路徑，讓 render_current_suggestion +
    render_ready_check 可直接複用（W10-017.11 AC 4 DRY）。

    資料源 fallback 對齊 DATA_SOURCES：
      uncommitted_files=None（資料源不可用，Ready Check 走 [?] 分支）
      active_agents=0, unmerged_worktrees=[], active_handoff=None, in_progress_tickets=[]
    這組 fallback 會落入 PRIORITIES FALLBACK（C3 流程完成），current_phase="3"。
    """
    pending = [
        PendingCheck(
            check_id="data_source_degraded",
            reason=f"snapshot degraded: {error}",
            blocker=False,
            auto_detectable=False,
        )
    ]
    return CheckpointState(
        current_phase="3",
        ready_for_clear=False,
        pending_checks=pending,
        active_agents=0,
        unmerged_worktrees=[],
        active_handoff=None,
        in_progress_tickets=[],
        data_sources={"degraded": f"IO_ERRORS: {error}"},
        computed_at=_utc_now_iso(),
        uncommitted_files=None,
    )


def _render_degraded_snapshot(error: str) -> int:
    """fail-open 降級渲染：既有靜態區塊仍輸出，動態區塊複用 render_* 函式。

    W10-017.11 AC 4：複用 render_current_suggestion + render_ready_check 避免
    與 _render_full_snapshot 重複實作「當前建議 / Ready Check」兩區塊。
    """
    versions = _scan_all_versions()
    branch = _get_git_branch()
    state = _build_degraded_state(error)

    print("=== Project Snapshot ===")
    print(f"分支: {branch}")
    print()

    _print_version_progress(versions)
    _print_in_progress_tasks(versions)
    _print_pending_summary(versions)
    print("--- Git 狀態 ---")
    print(f"  分支: {branch}")
    print(f"  未提交: 資料源不可用 ({error})")
    print()
    print(render_current_suggestion(state))
    print()
    print(render_ready_check(state, caller="snapshot"))
    return 0


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


def _print_git_status_from_state(branch: str, state: CheckpointState) -> None:
    """輸出 git 狀態（v2 §3.4：從 state.uncommitted_files 取值，不再呼叫 git status）。"""
    print("--- Git 狀態 ---")
    print(f"  分支: {branch}")
    if state.uncommitted_files is None:
        print("  未提交: 資料源不可用")
    else:
        print(f"  未提交: {state.uncommitted_files} 個檔案")


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
        r = subprocess.run(
            ["git", "branch", "--show-current"],
            capture_output=True, text=True, timeout=5,
        )
        return r.stdout.strip() or "unknown"
    except Exception:
        return "unknown"
