"""RED tests for ticket_system/commands/track_snapshot.py 增強 (W10-017.1 Phase 3a).

對應 sage Phase 2 §4.1 (S1-S11) + §5 (R1-R4) + §6 (F1-F2)。

Phase 3b 實作後預期全部變綠。RED 原因：
- track_snapshot.py 尚未呼叫 checkpoint_state / view function
- 尚未有「當前建議 / Ready Check」區塊輸出
- 既有 _get_uncommitted_count 仍呼叫 git status (S8 雙重 I/O 違規)
"""

from __future__ import annotations

import argparse
import io
import json
import sys
from typing import Any, List, Optional

import pytest

from ticket_system.lib.checkpoint_state import CheckpointState


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_state(
    *,
    current_phase: str = "3",
    ready_for_clear: bool = True,
    active_agents: int = 0,
    uncommitted_files: Optional[int] = 0,
    unmerged_worktrees: Optional[List[str]] = None,
    active_handoff: Optional[str] = None,
    in_progress_tickets: Optional[List[str]] = None,
    data_sources: Optional[dict] = None,
    computed_at: str = "2026-04-19T12:00:00+00:00",
    ticket_id: Optional[str] = None,
) -> CheckpointState:
    return CheckpointState(
        current_phase=current_phase,
        ready_for_clear=ready_for_clear,
        pending_checks=[],
        active_agents=active_agents,
        unmerged_worktrees=unmerged_worktrees or [],
        active_handoff=active_handoff,
        in_progress_tickets=in_progress_tickets or [],
        data_sources=data_sources or {
            "git-status": "ok",
            "dispatch-active": "ok",
            "handoff-pending": "ok",
            "ticket-query": "ok",
            "git-worktree": "ok",
        },
        computed_at=computed_at,
        uncommitted_files=uncommitted_files,
        _ticket_id=ticket_id,
    )


def _patch_checkpoint_state(monkeypatch, state_or_exc):
    """Patch commands.track_snapshot 的 checkpoint_state 引用點。"""
    from ticket_system.commands import track_snapshot as mod

    def fake(*args, **kwargs):
        if isinstance(state_or_exc, BaseException):
            raise state_or_exc
        return state_or_exc

    monkeypatch.setattr(mod, "checkpoint_state", fake)


def _run_snapshot(monkeypatch, state_or_exc) -> tuple[int, str, str]:
    """執行 execute_snapshot，回傳 (rc, stdout, stderr)."""
    from ticket_system.commands.track_snapshot import execute_snapshot

    _patch_checkpoint_state(monkeypatch, state_or_exc)
    out_buf, err_buf = io.StringIO(), io.StringIO()
    saved_out, saved_err = sys.stdout, sys.stderr
    sys.stdout, sys.stderr = out_buf, err_buf
    try:
        rc = execute_snapshot(argparse.Namespace())
    finally:
        sys.stdout, sys.stderr = saved_out, saved_err
    return rc, out_buf.getvalue(), err_buf.getvalue()


# ---------------------------------------------------------------------------
# S1-S5: 當前建議 / Ready Check 區塊（增強核心）
# ---------------------------------------------------------------------------


def test_S1_snapshot_includes_current_suggestion_section(monkeypatch):
    state = _make_state(current_phase="1", uncommitted_files=3, ready_for_clear=False)
    rc, out, _ = _run_snapshot(monkeypatch, state)
    assert "--- 當前建議 ---" in out
    assert "Checkpoint:" in out
    assert "C1 未提交變更" in out
    assert "下一步:" in out
    assert "git add" in out and "git commit" in out
    assert "(3 檔)" in out


def test_S2_snapshot_includes_ready_check_checklist(monkeypatch):
    state = _make_state(current_phase="1", uncommitted_files=3, ready_for_clear=False)
    rc, out, _ = _run_snapshot(monkeypatch, state)
    assert "--- /clear Ready Check ---" in out
    # 至少 4 個 checklist 行 (active agents / uncommitted / worktree / handoff)
    checklist_lines = [
        ln for ln in out.splitlines() if ln.strip().startswith(("[x]", "[ ]", "[?]"))
    ]
    assert len(checklist_lines) >= 4


def test_S3_snapshot_ready_check_detects_uncommitted(monkeypatch):
    state = _make_state(current_phase="1", uncommitted_files=3, ready_for_clear=False)
    rc, out, _ = _run_snapshot(monkeypatch, state)
    assert "[ ] 無未提交變更" in out
    assert "uncommitted_files=3" in out
    assert "git add" in out and "git commit" in out


def test_S4_snapshot_ready_check_detects_active_agents(monkeypatch):
    state = _make_state(
        current_phase="1.85", active_agents=2, ready_for_clear=False
    )
    rc, out, _ = _run_snapshot(monkeypatch, state)
    assert "[ ] 無活躍代理人" in out
    assert "active_agents=2" in out
    assert "ticket track agent-status" in out


def test_S5_snapshot_clean_state_shows_c3_ready(monkeypatch):
    state = _make_state(current_phase="3", ready_for_clear=True)
    rc, out, _ = _run_snapshot(monkeypatch, state)
    assert "C3 流程完成" in out
    assert "ready for /clear" in out
    # checklist 全 [x]
    no_pass = [ln for ln in out.splitlines() if ln.strip().startswith("[ ]")]
    assert len(no_pass) == 0, f"Expected all [x], found unchecked: {no_pass}"


# ---------------------------------------------------------------------------
# S6-S7: exit code & pipeline hint
# ---------------------------------------------------------------------------


def test_S6_snapshot_exit_code_always_zero_when_not_ready(monkeypatch):
    state = _make_state(current_phase="1", uncommitted_files=3, ready_for_clear=False)
    rc, _, _ = _run_snapshot(monkeypatch, state)
    assert rc == 0


def test_S7_snapshot_displays_pipeline_hint_for_handoff_ready(monkeypatch):
    state = _make_state(current_phase="1", uncommitted_files=3, ready_for_clear=False)
    rc, out, _ = _run_snapshot(monkeypatch, state)
    assert "ticket track handoff-ready" in out


# ---------------------------------------------------------------------------
# S8: 雙重 I/O 驗證 (commands 層禁直接呼叫 git status)
# ---------------------------------------------------------------------------


def test_S8_snapshot_uncommitted_count_from_state_not_subprocess(monkeypatch):
    """commands 層不應再呼叫 git status；snapshot 只從 state.uncommitted_files 取值."""
    import subprocess

    from ticket_system.commands import track_snapshot as mod

    state = _make_state(current_phase="1", uncommitted_files=5, ready_for_clear=False)
    _patch_checkpoint_state(monkeypatch, state)

    git_status_calls: List[List[str]] = []
    real_run = subprocess.run

    def spy_run(cmd, *args, **kwargs):
        if isinstance(cmd, (list, tuple)) and len(cmd) >= 2:
            if cmd[0] == "git" and cmd[1] == "status":
                git_status_calls.append(list(cmd))
        # 透傳給原始（讓 _get_git_branch 等無關呼叫保持運作）
        return real_run(cmd, *args, **kwargs)

    # 注意：只 patch commands.track_snapshot 內的 subprocess (mod.subprocess)
    monkeypatch.setattr(mod.subprocess, "run", spy_run)

    out_buf = io.StringIO()
    saved = sys.stdout
    sys.stdout = out_buf
    try:
        from ticket_system.commands.track_snapshot import execute_snapshot
        execute_snapshot(argparse.Namespace())
    finally:
        sys.stdout = saved

    # commands 層不應呼叫 git status
    assert len(git_status_calls) == 0, (
        f"commands.track_snapshot should not invoke git status directly; "
        f"got: {git_status_calls}"
    )


# ---------------------------------------------------------------------------
# S9-S11: git status 區塊 / fail-open / 時間
# ---------------------------------------------------------------------------


def test_S9_snapshot_git_status_section_uses_state_uncommitted(monkeypatch):
    state = _make_state(current_phase="1", uncommitted_files=5, ready_for_clear=False)
    rc, out, _ = _run_snapshot(monkeypatch, state)
    assert "--- Git 狀態 ---" in out
    assert "未提交: 5" in out


def test_S10_snapshot_git_status_section_when_data_source_unavailable(monkeypatch):
    """uncommitted_files=None 表示資料源失敗，顯示「資料源不可用」."""
    state = _make_state(
        current_phase="3",
        uncommitted_files=None,
        data_sources={"git-status": "FileNotFoundError: ...", "dispatch-active": "ok",
                      "handoff-pending": "ok", "ticket-query": "ok", "git-worktree": "ok"},
        ready_for_clear=False,
    )
    rc, out, _ = _run_snapshot(monkeypatch, state)
    assert "未提交:" in out and "資料源不可用" in out


def test_S11_snapshot_uses_local_time_from_state_computed_at(monkeypatch):
    """時間欄位呼叫 format_local_time(state) 而非 datetime.now()."""
    state = _make_state(computed_at="2026-04-19T12:00:00+00:00")
    rc, out, _ = _run_snapshot(monkeypatch, state)
    # 時間行應出現 "2026" (從 state.computed_at 解析)
    time_lines = [ln for ln in out.splitlines() if ln.startswith("時間:")]
    assert len(time_lines) >= 1
    assert "2026" in time_lines[0]
    # 含 "local" 標記（format_local_time 的契約）
    assert "local" in time_lines[0].lower()


# ---------------------------------------------------------------------------
# R1-R4: 既有 snapshot 區塊 baseline regression
# ---------------------------------------------------------------------------


def test_R1_snapshot_baseline_outputs_project_snapshot_header(monkeypatch):
    state = _make_state()
    rc, out, _ = _run_snapshot(monkeypatch, state)
    assert "=== Project Snapshot ===" in out


def test_R2_snapshot_baseline_outputs_branch_line(monkeypatch):
    state = _make_state()
    rc, out, _ = _run_snapshot(monkeypatch, state)
    assert "分支:" in out


def test_R3_snapshot_baseline_outputs_version_progress_section(monkeypatch):
    state = _make_state()
    rc, out, _ = _run_snapshot(monkeypatch, state)
    assert "--- 版本進度 ---" in out


def test_R4_snapshot_baseline_outputs_in_progress_tasks_section(monkeypatch):
    state = _make_state()
    rc, out, _ = _run_snapshot(monkeypatch, state)
    assert "--- 進行中任務 ---" in out


# ---------------------------------------------------------------------------
# F1-F2: fail-open 路徑（IO_ERRORS vs 其他例外）
# ---------------------------------------------------------------------------


def test_F1_snapshot_fail_open_on_io_error_continues_with_degraded_section(
    monkeypatch,
):
    """IO_ERRORS (FileNotFoundError) → exit 0，既有區塊仍輸出，當前建議區塊降級顯示."""
    rc, out, err = _run_snapshot(monkeypatch, FileNotFoundError("dispatch-active.json"))
    assert rc == 0
    # 既有靜態區塊仍輸出
    assert "--- 版本進度 ---" in out
    assert "--- 進行中任務 ---" in out
    # 當前建議或 Ready Check 區塊顯示「資料源異常」
    assert "資料源異常" in out or "資料源不可用" in out
    # v2.2 Q2 規定：stderr 應有 WARN 行
    assert "WARN" in err or "warn" in err.lower()


def test_F2_snapshot_internal_error_writes_stderr_exits_1(monkeypatch):
    """非 IO_ERRORS (RuntimeError) → exit 1，stderr 寫入."""
    rc, _, err = _run_snapshot(monkeypatch, RuntimeError("unexpected"))
    assert rc == 1
    assert "internal error" in err.lower() or "unexpected" in err
